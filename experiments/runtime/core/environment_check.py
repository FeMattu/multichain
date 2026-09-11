"""Is CORE usable here, and may we proceed without it?

Two separate questions, deliberately kept apart.

:func:`check_core` answers the first as a fact: what is installed, what
answers, what the current privileges allow. It never decides anything.

:func:`require_core_or_consent` answers the second as a **decision that
belongs to the user**. A fabric that silently degrades from CORE to plain
namespaces produces a run that looks the same, is labelled the same and is
compared with the others as though it were the same — and the only record of
the substitution is one line of log nobody reads. So: no consent, no run.

Consent is one of exactly two things, and nothing else counts:

* an interactive ``y`` at the prompt;
* ``--allow-fallback-without-core`` on the command line.

A non-interactive session without the flag exits with
``ENVIRONMENT_UNAVAILABLE``. That is the point: a cron job that quietly
switched backends would be the worst version of this.
"""

from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass, field

from ...exit_codes import EnvironmentError_

LOG = logging.getLogger("experiments.runtime.core.check")

#: What the netns fabric gives up relative to CORE. Shown verbatim at the
#: prompt, because "lower fidelity" on its own is not informed consent.
FIDELITY_NOTE = """\
  What you keep with the netns fabric:
    - the same kernel primitives CORE drives: network namespaces, veth, tc/netem
    - per-link, per-direction delay, jitter, loss and bandwidth
    - real multichaind processes, real sockets, real time
  What you give up:
    - CORE's session management: no GUI, no live topology inspection, no
      per-node console, and no supervision of the emulated nodes by CORE itself
    - CORE's own link model. The harness installs qdiscs directly, so a value
      CORE would have rendered differently is rendered by this harness instead
    - mobility, wireless models and any CORE service you may have configured
  What does NOT change:
    - the topology, the impairment values, the node roles, the chain
      parameters, the collected metrics and the CSV schema"""


@dataclass
class CoreStatus:
    """What was found, as facts."""

    python_api: bool = False
    python_api_detail: str = ""
    daemon_binary: str = ""
    daemon_reachable: bool = False
    daemon_detail: str = ""
    netns_usable: bool = False
    netns_detail: str = ""
    tc_available: bool = False
    ip_available: bool = False
    privileged: bool = False
    privilege_detail: str = ""
    problems: list = field(default_factory=list)

    @property
    def usable(self) -> bool:
        """CORE can actually drive a session here."""
        return self.python_api and self.daemon_reachable and self.netns_usable

    def as_dict(self) -> dict:
        return {
            "usable": self.usable,
            "python_api": self.python_api,
            "python_api_detail": self.python_api_detail,
            "daemon_binary": self.daemon_binary,
            "daemon_reachable": self.daemon_reachable,
            "daemon_detail": self.daemon_detail,
            "netns_usable": self.netns_usable,
            "netns_detail": self.netns_detail,
            "tc_available": self.tc_available,
            "ip_available": self.ip_available,
            "privileged": self.privileged,
            "privilege_detail": self.privilege_detail,
            "problems": list(self.problems),
        }

    def reason(self) -> str:
        return "; ".join(self.problems) if self.problems else "CORE is usable"


class FallbackRefused(EnvironmentError_):
    """CORE is unavailable and the user did not consent to the fallback."""


def _which(name: str) -> str:
    found = shutil.which(name)
    if found:
        return found
    for directory in ("/sbin", "/usr/sbin", "/usr/local/sbin"):
        candidate = os.path.join(directory, name)
        if os.path.isfile(candidate) and os.access(candidate, os.X_OK):
            return candidate
    return ""


def check_core(address: str = "127.0.0.1:50051") -> CoreStatus:
    """Probe CORE and the primitives any fabric needs. Decides nothing."""
    status = CoreStatus()

    # 1. the Python API
    try:
        from core.api.grpc import client as _client  # type: ignore  # noqa: F401

        status.python_api = True
        status.python_api_detail = "core.api.grpc importable"
    except ImportError as exc:
        status.python_api_detail = str(exc)
        status.problems.append("CORE's Python API is not installed (%s)" % exc)

    # 2. the daemon binary, and whether anything answers
    status.daemon_binary = _which("core-daemon")
    if not status.daemon_binary:
        status.problems.append("core-daemon is not on PATH")
    if status.python_api:
        try:
            from core.api.grpc import client as core_client  # type: ignore

            handle = core_client.CoreGrpcClient(address)
            handle.connect()
            handle.get_sessions()
            handle.close()
            status.daemon_reachable = True
            status.daemon_detail = "answered at %s" % address
        except Exception as exc:  # noqa: BLE001 - any transport failure is one answer
            status.daemon_detail = "%s: %s" % (exc.__class__.__name__, exc)
            status.problems.append(
                "no CORE daemon answering at %s (%s)" % (address, exc.__class__.__name__))
    elif status.daemon_binary:
        status.daemon_detail = "binary present but the Python API is missing, so untested"

    # 3. privileges, without which nothing below matters
    if os.geteuid() == 0:
        status.privileged = True
        status.privilege_detail = "running as root"
    else:
        sudo = shutil.which("sudo")
        if sudo and subprocess.run([sudo, "-n", "true"],
                                   capture_output=True).returncode == 0:
            status.privileged = True
            status.privilege_detail = "passwordless sudo"
        else:
            status.privilege_detail = (
                "not root and sudo needs a password" if sudo else "not root and no sudo")
            status.problems.append("no CAP_NET_ADMIN: " + status.privilege_detail)

    # 4. network namespaces
    if not os.path.isdir("/proc/self/ns"):
        status.netns_detail = "/proc/self/ns is missing"
        status.problems.append("network namespaces are unavailable on this kernel")
    else:
        probe = subprocess.run(["ip", "netns", "list"], capture_output=True, text=True) \
            if _which("ip") else None
        if probe is None:
            status.netns_detail = "iproute2 is missing"
        elif probe.returncode == 0:
            status.netns_usable = True
            status.netns_detail = "ip netns list works"
        else:
            status.netns_detail = (probe.stderr or probe.stdout).strip()[:160]
            status.problems.append("ip netns is not usable: " + status.netns_detail)

    # 5. the two tools every backend needs
    status.ip_available = bool(_which("ip"))
    status.tc_available = bool(_which("tc"))
    if not status.ip_available:
        status.problems.append("ip (iproute2) is not installed")
    if not status.tc_available:
        status.problems.append("tc (iproute2) is not installed: no impairment can be applied")

    return status


def render_prompt(status: CoreStatus, fallback: str) -> str:
    return (
        "\n"
        "CORE is not available, or is not correctly configured in this environment.\n"
        "Detected reason: %s\n"
        "\n"
        "Alternative mode available: %s\n"
        "This mode offers lower topological fidelity than CORE.\n"
        "\n%s\n"
        "\n"
        "Proceed anyway with the fallback mode? [y/N] " % (status.reason(), fallback, FIDELITY_NOTE)
    )


def require_core_or_consent(
    *,
    requested_backend: str,
    address: str = "127.0.0.1:50051",
    allow_fallback: bool = False,
    assume_yes: bool = False,
    fallback_name: str = "netns (Linux network namespaces + tc/netem)",
    stream=None,
) -> tuple[str, CoreStatus]:
    """Decide which backend to use, asking the user when CORE is missing.

    Returns ``(backend, status)``. Raises :class:`FallbackRefused` — exit code
    2 — when CORE is unavailable and nobody consented.

    ``requested_backend`` is honoured when it is explicit: someone who asked
    for ``netns`` has already made the choice and is not asked again. Only
    ``auto`` and ``core`` reach the gate.
    """
    stream = stream or sys.stderr
    status = check_core(address)

    if requested_backend == "netns":
        LOG.info("backend netns requested explicitly: CORE is not consulted")
        return "netns", status
    if requested_backend == "docker":
        return "docker", status

    if status.usable:
        LOG.info("CORE is available: %s", status.daemon_detail)
        return "core", status

    if requested_backend == "core":
        raise EnvironmentError_(
            "fabric.backend is 'core' but CORE cannot run here:\n  - %s"
            % "\n  - ".join(status.problems),
            hint="start core-daemon, or choose the netns backend explicitly, or "
                 "pass --allow-fallback-without-core",
        )

    # requested_backend == "auto": the gate.
    if allow_fallback or assume_yes:
        LOG.warning(
            "CORE unavailable (%s); continuing on %s because the fallback was "
            "authorised explicitly", status.reason(), fallback_name)
        return "netns", status

    if not (hasattr(stream, "isatty") and stream.isatty() and sys.stdin.isatty()):
        raise FallbackRefused(
            "CORE is not available (%s) and this session is not interactive, so "
            "nobody can consent to the fallback.\n"
            "The run was NOT started: a non-interactive job must never switch "
            "backend on its own." % status.reason(),
            hint="pass --allow-fallback-without-core to authorise the netns "
                 "fabric deliberately, or set fabric.backend: netns in the "
                 "descriptor if that is what you always want",
        )

    stream.write(render_prompt(status, fallback_name))
    stream.flush()
    try:
        answer = input().strip().lower()
    except (EOFError, KeyboardInterrupt):
        answer = ""
    if answer in ("y", "yes"):
        LOG.warning("fallback to %s authorised interactively", fallback_name)
        return "netns", status
    raise FallbackRefused(
        "CORE is not available (%s) and the fallback was declined. Nothing was "
        "started." % status.reason(),
        hint="install CORE and start core-daemon, or re-run with "
             "--allow-fallback-without-core",
    )
