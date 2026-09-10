"""Removing impairment, both from a live fabric and from a leaked one.

The second case is the one that matters. A run killed with SIGKILL leaves
qdiscs attached to interfaces inside namespaces that may themselves survive;
deleting the namespace takes them with it, but a partial build can leave veth
ends in the root namespace with a netem qdisc still on them, and those will
quietly impair the next run. :func:`clear_stray_qdiscs` finds and removes
them by name pattern, which is what ``clean_experiment.sh`` calls.
"""

from __future__ import annotations

import logging
import re

from .apply import record_event
from .profiles import clear_commands

LOG = logging.getLogger("experiments.runtime.netem.clear")

#: Interface names the netns fabric creates in the root namespace.
STRAY_PATTERN = re.compile(r"^(pe\d+[ab]|mgp\d+|mg\d+-\S+)$")


def clear_all(fabric, run_root=None) -> int:
    """Remove every qdisc the fabric installed."""
    interfaces = fabric.clear_impairment()
    if run_root is not None:
        record_event(run_root, {"action": "clear-all", "interfaces_touched": interfaces})
    LOG.info("cleared impairment from %d interfaces", interfaces)
    return interfaces


def clear_stray_qdiscs(runner) -> int:
    """Strip qdiscs from leftover veth ends in the root namespace."""
    listing = runner.run(["ip", "-o", "link", "show"], privileged=True, check=False)
    cleared = 0
    for line in listing.stdout.splitlines():
        match = re.match(r"^\d+:\s+([^:@]+)[@:]", line)
        if not match:
            continue
        name = match.group(1).strip()
        if STRAY_PATTERN.match(name):
            for args in clear_commands(name):
                runner.tc(*args, check=False)
            cleared += 1
    if cleared:
        LOG.info("cleared qdiscs from %d stray interfaces", cleared)
    return cleared


def clear_namespace_qdiscs(runner, namespace: str, interfaces: list[str]) -> int:
    """Strip qdiscs from named interfaces inside one namespace."""
    cleared = 0
    for interface in interfaces:
        for args in clear_commands(interface):
            runner.in_netns(namespace, ["tc", *args], check=False)
        cleared += 1
    return cleared
