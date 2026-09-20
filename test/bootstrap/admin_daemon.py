#!/usr/bin/env python3
"""The observer: a separate process bound to the admin node, sampling the chain.

Started by ``bootstrap_network.py`` as soon as the admin node answers RPC, and left
running until it is told to stop. It never writes to the chain — it only reads, and
everything it reads it writes verbatim to its own ``events.jsonl``. That separation is
what lets phase 1 of the analysis be a pure normalisation: nothing is aggregated, nothing
is tested, nothing is interpreted while the run is still going.

Two sampling cadences, because the quantities have different natural grains:

* **per block** — the block list, and the round-level audit RPCs whose answer is only
  defined for one height (``wpoalistscores``, ``wpoalistdelays``,
  ``wpoalisteffectiveweights``, ``wpoalistfinalweights``). Sampling these once per epoch
  would throw away the round-by-round structure that the streak and timer-race tests are
  built on.
* **per epoch** — the WeightEngine audit family, which is *defined* per epoch and only
  answerable once the epoch is buried, plus the streams and the permission/peer state.

Run standalone for a live look at a chain this harness started::

    python3 test/bootstrap/admin_daemon.py --config <profile> --run-dir <run> [--until-height N]
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import (  # noqa: E402
    STREAM_ESG,
    STREAM_MALUS,
    STREAM_MEMBERSHIP,
    STREAM_WEIGHTS,
    load_profile,
)
from event_log import (  # noqa: E402
    EVENT_EPOCH_ENTERED,
    EVENT_NODE_STOPPED,
    EventLog,
)
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402

#: Audit RPCs whose answer is defined for a single round (block height).
ROUND_RPCS = (
    "wpoalistscores",
    "wpoalistdelays",
    "wpoalisteffectiveweights",
    "wpoalistfinalweights",
)

#: Audit RPCs whose answer is defined for a single buried epoch.
EPOCH_RPCS = (
    "weightlistcontributions",
    "weightlistclusterweights",
    "weightlistreturns",
    "weightlistearnings",
    "weightlistbalances",
)

#: Protocol streams, read whole at each epoch boundary. The profile's informative stream
#: is appended to these at construction: without it there is no on-chain record of the
#: company traffic, and phase 2 could only report what the daemons *believed* they sent.
PROTOCOL_STREAMS = (STREAM_WEIGHTS, STREAM_MALUS, STREAM_ESG, STREAM_MEMBERSHIP)


class AdminDaemon:
    """Samples one node and writes what it sees."""

    def __init__(
        self,
        profile,
        run_dir: Path,
        rpc: RpcClient,
        log: EventLog,
        until_height: Optional[int] = None,
    ) -> None:
        self.profile = profile
        self.run_dir = Path(run_dir)
        self.rpc = rpc
        self.log = log
        self.until_height = until_height
        self.streams = tuple(PROTOCOL_STREAMS) + (profile.traffic["event_stream"],)
        self.stop_flag = self.run_dir / "STOP"
        self._running = True
        self._last_block_sampled = 0
        self._last_epoch_sampled = 0
        self._last_round_height = 0

    # -- control -----------------------------------------------------------------------

    def request_stop(self, *_: Any) -> None:
        self._running = False

    def should_stop(self, tip: int) -> bool:
        """Stop on a signal, on the sentinel file, or once the target height is reached.

        The sentinel file exists because the orchestrator may have to stop this process
        from outside its own process group, and a file is the one channel that works
        whether the daemon is a child, a grandchild or an orphan.
        """
        if not self._running or self.stop_flag.exists():
            return True
        return self.until_height is not None and tip >= self.until_height

    # -- sampling ----------------------------------------------------------------------

    def sample_blocks(self, tip: int) -> None:
        """Every block since the last sample, plus its round-level audit.

        ``listblocks`` takes a ``from-to`` string. The window is capped so that a daemon
        that fell behind — or one started against a chain already in progress — cannot
        ask for ten thousand blocks in one call and time out.
        """
        if tip <= self._last_block_sampled:
            return
        first = self._last_block_sampled + 1
        last = min(tip, first + 199)
        try:
            blocks = self.rpc.call("listblocks", "%d-%d" % (first, last), True)
        except (RpcError, RpcTransportError) as exc:
            self.log.rpc_error("listblocks", exc, tip, window="%d-%d" % (first, last))
            return
        self.log.snapshot("listblocks", tip, blocks, window_first=first, window_last=last)
        self._last_block_sampled = last

        # The same window, audited for the winner's REAL private score. Sampled here
        # rather than in sample_round because it is a property of a block that exists,
        # not of a round being decided -- and because the weights it reads are only
        # exact while the tip is still inside the audited height's own epoch, which a
        # per-block cadence keeps true (the answer carries weight_epoch_stale either
        # way). The round RPCs above score the PUBLIC Efraimidis form, which is not the
        # quantity the election ran on; this is.
        try:
            self.log.snapshot(
                "wpoalistblocksortition",
                tip,
                self.rpc.call("wpoalistblocksortition", "%d-%d" % (first, last)),
                window_first=first,
                window_last=last,
            )
        except (RpcError, RpcTransportError) as exc:
            self.log.rpc_error("wpoalistblocksortition", exc, tip,
                               window="%d-%d" % (first, last))

        try:
            self.log.snapshot("getlastblockinfo", tip, self.rpc.call("getlastblockinfo", 0))
        except (RpcError, RpcTransportError) as exc:
            self.log.rpc_error("getlastblockinfo", exc, tip)

    def sample_round(self, tip: int) -> None:
        """The four round-audit families for the *next* round.

        ``tip + 1`` is the round being decided now: the audit RPCs default to it, and
        asking for a past height replays the seed rather than the live state. The daemon
        records one sample per height and never twice for the same one, so that a fast
        poll cannot inflate the round count.
        """
        height = tip + 1
        if height <= self._last_round_height:
            return
        for method in ROUND_RPCS:
            try:
                self.log.snapshot(
                    method, tip, self.rpc.call(method, height), round_height=height
                )
            except RpcError as exc:
                # Before the registry has anything in it, "Round not evaluable" is the
                # expected answer, not a fault. It is still recorded: the height at which
                # it stops appearing is when wPoA actually took over.
                self.log.rpc_error(method, exc, tip, round_height=height)
            except RpcTransportError as exc:
                self.log.rpc_error(method, exc, tip, round_height=height)
                return
        self._last_round_height = height

    def sample_registry(self, tip: int) -> None:
        """The published weight registry and the malus accumulators."""
        for method in ("getallweights", "getallmalus"):
            try:
                self.log.snapshot(method, tip, self.rpc.call(method))
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error(method, exc, tip)

    def sample_epoch(self, tip: int, epoch: int) -> None:
        """Everything defined per epoch, for the newest buried one.

        The epoch argument is passed explicitly rather than left to default: the default
        is "newest buried", which would silently move under the daemon between two calls
        of the same sample and put two different epochs in one snapshot.
        """
        buried = self.profile.last_buried_epoch(tip)
        if buried < 1:
            return
        for method in EPOCH_RPCS:
            try:
                self.log.snapshot(
                    method, tip, self.rpc.call(method, buried), epoch=buried
                )
            except RpcError as exc:
                self.log.rpc_error(method, exc, tip, epoch=buried)
            except RpcTransportError as exc:
                self.log.rpc_error(method, exc, tip, epoch=buried)
                return
        try:
            self.log.snapshot("weightverifyweights", tip, self.rpc.call("weightverifyweights"))
        except (RpcError, RpcTransportError) as exc:
            self.log.rpc_error("weightverifyweights", exc, tip)

    def sample_streams(self, tip: int) -> None:
        """Each stream read whole.

        ``count`` is always explicit: ``liststreamitems`` defaults to 10 and would
        silently truncate every read to the last ten items.
        """
        for stream in self.streams:
            try:
                items = self.rpc.stream_items(stream)
            except RpcError as exc:
                # A stream that does not exist yet is normal early on.
                self.log.rpc_error("liststreamitems", exc, tip, stream=stream)
                continue
            except RpcTransportError as exc:
                self.log.rpc_error("liststreamitems", exc, tip, stream=stream)
                return
            self.log.snapshot("liststreamitems", tip, items, stream=stream, n_items=len(items))

    def sample_state(self, tip: int) -> None:
        """Node, peer and permission state — the context a result is read against."""
        for method, args in (
            ("getinfo", ()),
            ("getblockchaininfo", ()),
            ("listminers", (True,)),
            ("getpeerinfo", ()),
            ("listpermissions", ("*", "*", False)),
        ):
            try:
                self.log.snapshot(method, tip, self.rpc.call(method, *args))
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error(method, exc, tip)

    # -- the loop ----------------------------------------------------------------------

    def run(self, poll_s: float = 1.0) -> int:
        """Sample until told to stop. Returns the last tip height seen."""
        info = self.rpc.wait_ready(self.profile.runtime["startup_timeout_s"])
        tip = int(info.get("blocks", 0))
        self.log.set_address(self.rpc.own_address())
        self.log.note(
            "admin_daemon attached",
            tip,
            chain=self.profile.chain_name,
            rpc_port=self.rpc.port,
            until_height=self.until_height,
            epoch_length=self.profile.epoch_length,
        )
        self.sample_state(tip)

        while True:
            try:
                tip = self.rpc.block_height()
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error("getinfo", exc, None)
                if self.should_stop(0):
                    break
                time.sleep(poll_s)
                continue

            self.sample_blocks(tip)
            self.sample_round(tip)
            self.sample_registry(tip)

            epoch = self.profile.last_buried_epoch(tip)
            if epoch > self._last_epoch_sampled:
                self.log.emit(
                    EVENT_EPOCH_ENTERED,
                    tip,
                    {"buried_epoch": epoch, "previous": self._last_epoch_sampled},
                )
                self.sample_epoch(tip, epoch)
                self.sample_streams(tip)
                self.sample_state(tip)
                self._last_epoch_sampled = epoch

            if self.should_stop(tip):
                break
            time.sleep(poll_s)

        # One last full sweep: the final epoch is the one most likely to be half-written,
        # and this is the cheapest possible insurance against losing it.
        self.sample_blocks(tip)
        self.sample_registry(tip)
        self.sample_epoch(tip, self.profile.last_buried_epoch(tip))
        self.sample_streams(tip)
        self.sample_state(tip)
        self.log.emit(
            EVENT_NODE_STOPPED,
            tip,
            {
                "reason": "target height" if self.until_height and tip >= self.until_height
                else "stop requested",
                "final_height": tip,
                "rpc_calls": self.rpc.calls,
                "rpc_failures": self.rpc.failures,
                "event_counts": dict(self.log.counts),
            },
        )
        return tip


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True, help="path to the profile YAML")
    parser.add_argument("--run-dir", required=True, help="the run directory to write into")
    parser.add_argument("--chain-home", default=None, help="override the datadir root")
    parser.add_argument(
        "--until-height", type=int, default=None, help="stop once the tip reaches this"
    )
    parser.add_argument("--poll", type=float, default=1.0, help="seconds between samples")
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"
    admin = profile.admin

    log = EventLog(run_dir, admin.node_id, admin.role, epoch_length=profile.epoch_length)
    rpc = RpcClient.from_datadir(
        chain_home / admin.node_id,
        profile.chain_name,
        profile.rpc_host(admin.node_id),
        admin.rpc_port,
        node_id=admin.node_id,
        timeout=profile.runtime["rpc_timeout_s"],
    )
    daemon = AdminDaemon(profile, run_dir, rpc, log, args.until_height)
    signal.signal(signal.SIGTERM, daemon.request_stop)
    signal.signal(signal.SIGINT, daemon.request_stop)
    try:
        daemon.run(args.poll)
    finally:
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
