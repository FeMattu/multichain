#!/usr/bin/env python3
"""One company node's traffic generator. One OS process per company.

A company's transactions are **informative**, never transfers of value: stream
publications carrying a data payload. The thesis is explicit that "lo scopo delle
transazioni non è il trasferimento di valore monetario tra i partecipanti, ma
esclusivamente la trasmissione autenticata e immutabile di informazioni". The GAS a
company holds exists only to pay the fee. Company-to-company transfer is a bug, and this
daemon never makes one.

What the traffic is for: each confirmed transaction the company **signed** raises its
activity counter ``tau_i``, which enters its contribution ``c_i = ESG_i * tau_i / kappa``
and from there the raw weight of the cluster it joined. Traffic is the only way the
company influences anything.

Two properties of the generation matter more than the volume:

* **The count is drawn per company, per epoch.** A fixed count gives ``tau`` no variance
  and nothing in the weight pipeline moves.
* **The transactions are spread through the epoch, not sent in a burst.** Each is
  followed by an independent random sleep sized from the epoch's expected duration, so
  the activity is spread over the blocks of the epoch rather than landing in one or two.
  A burst would make ``tau`` a function of when the daemon woke up.

Epochs are detected from the node's own tip height. The daemon polls its own node, not
the admin's — it must react to what its node sees.

    python3 test/traffic/company_daemon.py --config <profile> --run-dir <run> --node-id company-3
"""

from __future__ import annotations

import argparse
import binascii
import random
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bootstrap"))

from config_loader import Profile, load_profile  # noqa: E402
from event_log import (  # noqa: E402
    EVENT_EPOCH_PLAN,
    EVENT_NODE_STOPPED,
    EVENT_TRAFFIC_TX_SENT,
    EventLog,
)
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402


class CompanyDaemon:
    """Publishes informative transactions, epoch by epoch."""

    def __init__(
        self,
        profile: Profile,
        node_id: str,
        run_dir: Path,
        rpc: RpcClient,
        log: EventLog,
    ) -> None:
        self.profile = profile
        self.node_id = node_id
        self.run_dir = Path(run_dir)
        self.rpc = rpc
        self.log = log
        self.stream = profile.traffic["event_stream"]
        self.stop_flag = self.run_dir / "STOP"
        self._running = True
        #: Seeded from the master seed and this node's id, so a rerun of the profile
        #: produces the same schedule in this process without coordinating with any other.
        self.rng: random.Random = profile.rng("company-traffic", node_id)
        self.sent_total = 0
        self.failed_total = 0

    def request_stop(self, *_: object) -> None:
        self._running = False

    def should_stop(self, tip: int) -> bool:
        return (
            not self._running
            or self.stop_flag.exists()
            or tip >= self.profile.target_height
        )

    # -- one epoch ---------------------------------------------------------------------

    def plan_epoch(self, epoch: int) -> int:
        low, high = self.profile.traffic["company_tx_per_epoch_range"]
        return self.rng.randint(low, high)

    def payload(self, epoch: int, sequence: int) -> str:
        """A hex payload standing in for a lavorazione / passaggio-di-proprietà record.

        An information carrier with no monetary value, exactly as thesis §4.2.1 describes:
        it pays a fee and creates no transfer between companies.
        """
        text = "epoch=%d node=%s seq=%d ts=%d" % (epoch, self.node_id, sequence, int(time.time()))
        return binascii.hexlify(text.encode("utf-8")).decode("ascii")

    def run_epoch(self, epoch: int, tip: int) -> None:
        """Publish this epoch's quota, spread across its expected duration."""
        planned = self.plan_epoch(epoch)
        epoch_seconds = self.profile.epoch_length * self.profile.target_block_time
        # Leave a margin so the last transaction still lands inside the epoch even if the
        # sleeps run long; a transaction that slips into epoch e+1 is counted there.
        budget = max(1.0, epoch_seconds * 0.85)
        mean_gap = budget / max(1, planned)

        self.log.emit(
            EVENT_EPOCH_PLAN,
            tip,
            {
                "epoch": epoch,
                "planned_tx": planned,
                "epoch_seconds_expected": epoch_seconds,
                "mean_gap_s": round(mean_gap, 3),
            },
        )

        sent = 0
        for sequence in range(planned):
            if self.should_stop(tip):
                break
            key = "lot-%d-%s-%d" % (epoch, self.node_id, sequence)
            try:
                tip = self.rpc.block_height()
            except (RpcError, RpcTransportError):
                pass
            try:
                txid = self.rpc.call("publish", self.stream, key, self.payload(epoch, sequence))
            except (RpcError, RpcTransportError) as exc:
                self.failed_total += 1
                self.log.rpc_error(
                    "publish", exc, tip, epoch=epoch, stream=self.stream, key=key
                )
                # A fee-policy or funding failure will repeat for every remaining
                # transaction of this epoch; sleeping the normal gap keeps the daemon
                # from spinning through the whole quota in a tight loop.
                time.sleep(min(5.0, mean_gap))
                continue
            sent += 1
            self.sent_total += 1
            self.log.emit(
                EVENT_TRAFFIC_TX_SENT,
                tip,
                {
                    "txid": txid,
                    "epoch": epoch,
                    "sequence": sequence,
                    "stream": self.stream,
                    "key": key,
                    "planned_this_epoch": planned,
                },
            )
            # Exponential gaps: independent of one another, and their sum concentrates on
            # the budget, so the quota spreads over the epoch instead of arriving at its
            # start or its end.
            time.sleep(min(epoch_seconds, self.rng.expovariate(1.0 / mean_gap)))

        self.log.note(
            "epoch traffic complete",
            tip,
            epoch=epoch,
            planned=planned,
            sent=sent,
            failed_so_far=self.failed_total,
        )

    # -- the loop ----------------------------------------------------------------------

    def run(self) -> int:
        info = self.rpc.wait_ready(self.profile.runtime["startup_timeout_s"])
        tip = int(info.get("blocks", 0))
        self.log.set_address(self.rpc.own_address())
        self.log.note(
            "company_daemon attached",
            tip,
            stream=self.stream,
            tx_range=self.profile.traffic["company_tx_per_epoch_range"],
        )

        current_epoch = 0
        while not self.should_stop(tip):
            try:
                tip = self.rpc.block_height()
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error("getinfo", exc, None)
                time.sleep(3.0)
                continue

            epoch = self.profile.epoch_of_height(tip)
            if epoch > current_epoch:
                current_epoch = epoch
                self.run_epoch(epoch, tip)
            else:
                time.sleep(2.0)

        self.log.emit(
            EVENT_NODE_STOPPED,
            tip,
            {
                "sent_total": self.sent_total,
                "failed_total": self.failed_total,
                "last_epoch": current_epoch,
                "rpc_calls": self.rpc.calls,
                "rpc_failures": self.rpc.failures,
            },
        )
        return self.sent_total


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    parser.add_argument("--node-id", required=True, help="e.g. company-3")
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    node = profile.node(args.node_id)
    if node.role != "company":
        raise SystemExit("%s is a %s, not a company" % (args.node_id, node.role))

    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"
    log = EventLog(run_dir, node.node_id, node.role, epoch_length=profile.epoch_length)
    rpc = RpcClient.from_datadir(
        chain_home / node.node_id,
        profile.chain_name,
        profile.rpc_host(node.node_id),
        node.rpc_port,
        node_id=node.node_id,
        timeout=profile.runtime["rpc_timeout_s"],
    )
    daemon = CompanyDaemon(profile, node.node_id, run_dir, rpc, log)
    signal.signal(signal.SIGTERM, daemon.request_stop)
    signal.signal(signal.SIGINT, daemon.request_stop)
    try:
        daemon.run()
    finally:
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
