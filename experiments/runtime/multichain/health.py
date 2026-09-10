"""Readiness checks between the phases of the bootstrap.

The bootstrap order is not arbitrary — permissions before the join, membership
and ESG before traffic — so each phase has to be able to say whether the
previous one actually landed. Every check here answers one question, returns
a structured verdict rather than raising, and never blocks longer than the
deadline it was given.

Waiting on the wrong thing is a real failure mode: a run that proceeds to the
traffic phase before ``wpoa-weights`` holds a record reaches
``setup-first-blocks`` with an empty weight map and stops with
``cannot score (unsynced or unweighted)``, several minutes later and with a
much less obvious message.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

from .rpc import RpcClient

LOG = logging.getLogger("experiments.runtime.multichain.health")


@dataclass
class Check:
    """One verdict."""

    name: str
    ok: bool
    detail: str = ""
    values: dict = field(default_factory=dict)

    def as_dict(self) -> dict:
        return {"name": self.name, "ok": self.ok, "detail": self.detail, "values": self.values}


@dataclass
class HealthReport:
    checks: list[Check] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return all(check.ok for check in self.checks)

    def add(self, check: Check) -> Check:
        self.checks.append(check)
        level = logging.INFO if check.ok else logging.WARNING
        LOG.log(level, "%s: %s%s", check.name, "ok" if check.ok else "FAILED",
                " - " + check.detail if check.detail else "")
        return check

    def failures(self) -> list[Check]:
        return [check for check in self.checks if not check.ok]

    def as_dict(self) -> dict:
        return {"ok": self.ok, "checks": [check.as_dict() for check in self.checks]}


def wait_daemons(clients: dict[str, RpcClient], timeout_s: float,
                 *, poll_s: float = 2.0) -> Check:
    """Every daemon answers RPC."""
    deadline = time.monotonic() + timeout_s
    pending = dict(clients)
    ready: dict[str, int] = {}
    while pending and time.monotonic() < deadline:
        for node_id, client in list(pending.items()):
            height = client.block_count()
            if height is not None:
                ready[node_id] = height
                pending.pop(node_id)
        if pending:
            time.sleep(poll_s)
    return Check(
        name="daemons responding",
        ok=not pending,
        detail="" if not pending else "no RPC from: " + ", ".join(sorted(pending)),
        values={"ready": ready, "pending": sorted(pending)},
    )


def wait_peers(clients: dict[str, RpcClient], minimum: int, timeout_s: float,
               *, poll_s: float = 5.0) -> Check:
    """Every node has at least ``minimum`` peers.

    A node that never peers is worse than a slow one: it will mine its own
    chain and show up as a fork that never existed on the network.
    """
    deadline = time.monotonic() + timeout_s
    counts: dict[str, int] = {}
    while time.monotonic() < deadline:
        counts = {}
        for node_id, client in clients.items():
            peers, error = client.try_call("getpeerinfo")
            counts[node_id] = 0 if error else len(peers or [])
        short = {k: v for k, v in counts.items() if v < minimum}
        if not short:
            return Check("peer connectivity", True, values={"peers": counts})
        time.sleep(poll_s)
    short = {k: v for k, v in counts.items() if v < minimum}
    return Check(
        "peer connectivity", False,
        detail="below %d peers: %s" % (minimum, ", ".join("%s=%d" % kv for kv in sorted(short.items()))),
        values={"peers": counts, "minimum": minimum},
    )


def wait_stream(client: RpcClient, name: str, timeout_s: float) -> Check:
    ok = client.wait_stream(name, timeout_s)
    return Check("stream %s exists" % name, ok,
                 detail="" if ok else "not confirmed within %gs" % timeout_s)


def wait_weights_published(client: RpcClient, timeout_s: float,
                           *, poll_s: float = 5.0) -> Check:
    """``wpoa-weights`` holds at least one confirmed record.

    This is the gate that decides whether wPoA can take over at all. Checking
    it before the setup phase ends turns an eventual stall into an immediate,
    explicable failure.
    """
    deadline = time.monotonic() + timeout_s
    count = 0
    while time.monotonic() < deadline:
        items, error = client.try_call("liststreamitems", ["wpoa-weights", False, 1000])
        if error is None and items:
            confirmed = [i for i in items if int(i.get("confirmations", 0)) > 0]
            count = len(confirmed)
            if confirmed:
                return Check("weights published", True,
                             values={"confirmed_records": count})
        time.sleep(poll_s)
    return Check(
        "weights published", False,
        detail=("wpoa-weights holds no confirmed record after %gs; wPoA would take over on an "
                "empty weight map and the chain would stop with 'cannot score'" % timeout_s),
        values={"confirmed_records": count},
    )


def check_progress(client: RpcClient, window_s: float, *, minimum_blocks: int = 1) -> Check:
    """The chain advanced by at least ``minimum_blocks`` over ``window_s``."""
    start = client.block_count()
    if start is None:
        return Check("chain progress", False, detail="the reference node does not answer RPC")
    time.sleep(window_s)
    end = client.block_count()
    if end is None:
        return Check("chain progress", False, detail="the reference node stopped answering RPC")
    produced = end - start
    return Check(
        "chain progress", produced >= minimum_blocks,
        detail="" if produced >= minimum_blocks
        else "%d blocks in %gs, expected at least %d" % (produced, window_s, minimum_blocks),
        values={"from": start, "to": end, "blocks": produced, "window_s": window_s},
    )


def check_consistency(clients: dict[str, RpcClient], *, depth: int = 6) -> Check:
    """Every node agrees on the hash at a common buried height.

    The height is absolute and shared. Comparing each node's own ``tip - 6``
    would make nodes at different heights compare different blocks by
    construction, and an ordinary propagation delay would read as a fork.
    """
    heights = {}
    for node_id, client in clients.items():
        height = client.block_count()
        if height is not None:
            heights[node_id] = height
    if not heights:
        return Check("chain consistency", False, detail="no node answered RPC")
    reference = max(1, min(heights.values()) - depth)
    hashes: dict[str, str] = {}
    for node_id, client in clients.items():
        value, error = client.try_call("getblockhash", [reference])
        hashes[node_id] = "unreachable" if error else str(value)
    distinct = sorted(set(hashes.values()) - {"unreachable"})
    ok = len(distinct) <= 1
    return Check(
        "chain consistency", ok,
        detail="" if ok else "%d distinct hashes at height %d: %s"
        % (len(distinct), reference, ", ".join("%s=%s" % (h, hashes[h][:12]) for h in sorted(hashes))),
        values={"reference_height": reference, "heights": heights,
                "distinct_hashes": len(distinct)},
    )
