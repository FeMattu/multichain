#!/usr/bin/env python3
"""One miner node's restitution generator. One OS process per miner.

Miners earn the fees of the transactions they include and periodically **return** GAS to
the treasury. This is the only flow in the whole harness that produces ``R_k``, and the
actor matters absolutely: the engine reads ``r_e[miner_address]`` and nothing else, so a
company paying the treasury credits a key no cluster ever reads and leaves ``R_k = 0``
for everybody while looking, from the outside, exactly like activity.

``R_k`` is what makes the feedback loop observable::

    g_k     = Entrate_k - (Uscite_k - R_k)          (Def. guadagno)
    saldo_k = saldo_k^(e-1) + g_k                   (Def. saldo)
    rho_k   = clamp(R_k, [0, saldo_k]) / saldo_k    (Def. tasso-restituzione)
    w_k^(e) = W_k^(e) * [ rho_k^(e-1) * lambda + (1 - lambda) ]

With no restitution, ``rho`` is pinned at 0, the bracket collapses to the constant
``1 - lambda``, and the WeightEngine's only endogenous feedback channel is inert — which
is precisely what the lag-1 Spearman test in phase 3 exists to detect.

Mining itself needs no RPC: the node self-elects. And mining does not help the miner's
own ``tau`` either — ``tau`` counts transactions whose inputs the address *signed*, and a
coinbase has no resolvable input signer. These restitutions are a miner's only activity.

Every amount inside one miner-epoch is **distinct**, so a constant can never masquerade
as a measurement.

    python3 test/traffic/miner_gas_daemon.py --config <profile> --run-dir <run> --node-id miner-1
"""

from __future__ import annotations

import argparse
import json
import random
import signal
import sys
import time
from pathlib import Path
from typing import List, Optional, Set

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bootstrap"))

from config_loader import Profile, load_profile  # noqa: E402
from event_log import (  # noqa: E402
    EVENT_EPOCH_PLAN,
    EVENT_GAS_RETURN_SENT,
    EVENT_NODE_STOPPED,
    EventLog,
)
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402


class MinerGasDaemon:
    """Returns GAS to the treasury, epoch by epoch."""

    def __init__(
        self,
        profile: Profile,
        node_id: str,
        run_dir: Path,
        rpc: RpcClient,
        log: EventLog,
        treasury: str,
    ) -> None:
        self.profile = profile
        self.node_id = node_id
        self.run_dir = Path(run_dir)
        self.rpc = rpc
        self.log = log
        self.treasury = treasury
        self.stop_flag = self.run_dir / "STOP"
        self._running = True
        self.rng: random.Random = profile.rng("miner-returns", node_id)
        self.sent_total = 0
        self.failed_total = 0
        self.returned_total = 0.0

    def request_stop(self, *_: object) -> None:
        self._running = False

    def should_stop(self, tip: int) -> bool:
        return (
            not self._running
            or self.stop_flag.exists()
            or tip >= self.profile.target_height
        )

    # -- one epoch ---------------------------------------------------------------------

    def plan_epoch(self) -> int:
        low, high = self.profile.traffic["miner_gas_returns_per_epoch_range"]
        return self.rng.randint(low, high)

    def distinct_amount(self, used: Set[float]) -> float:
        """An amount not yet used in this miner-epoch.

        Two decimals give enough distinct values for any plausible count; after enough
        collisions the loop gives up and returns a value anyway rather than spinning,
        because a repeated amount is a cosmetic flaw and a hung daemon is not.
        """
        low, high = self.profile.traffic["restitution_amount_range"]
        for _ in range(64):
            amount = round(self.rng.uniform(low, high), 2)
            if amount > 0 and amount not in used:
                return amount
        return round(self.rng.uniform(low, high), 2)

    def run_epoch(self, epoch: int, tip: int) -> None:
        planned = self.plan_epoch()
        epoch_seconds = self.profile.epoch_length * self.profile.target_block_time
        budget = max(1.0, epoch_seconds * 0.85)
        mean_gap = budget / max(1, planned)

        self.log.emit(
            EVENT_EPOCH_PLAN,
            tip,
            {
                "epoch": epoch,
                "planned_returns": planned,
                "treasury_address": self.treasury,
                "mean_gap_s": round(mean_gap, 3),
            },
        )
        if planned == 0:
            # A miner may legitimately return nothing in an epoch. Recorded explicitly so
            # phase 1 can tell "returned nothing" from "was not sampled".
            self.log.note("epoch returns complete", tip, epoch=epoch, planned=0, sent=0)
            return

        used: Set[float] = set()
        sent = 0
        for sequence in range(planned):
            if self.should_stop(tip):
                break
            try:
                tip = self.rpc.block_height()
                balance = self.rpc.native_balance()
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error("getinfo", exc, None, epoch=epoch)
                time.sleep(3.0)
                continue

            amount = self.distinct_amount(used)
            if balance < amount:
                # Never return more than is held: the ledger would refuse it, and the
                # balance is the natural cap on R_k anyway.
                self.log.note(
                    "return skipped: insufficient balance",
                    tip,
                    epoch=epoch,
                    sequence=sequence,
                    balance=balance,
                    wanted=amount,
                )
                time.sleep(min(5.0, mean_gap))
                continue

            try:
                txid = self.rpc.call("sendfrom", self.log.node_address, self.treasury, amount)
            except (RpcError, RpcTransportError) as exc:
                self.failed_total += 1
                self.log.rpc_error(
                    "sendfrom", exc, tip, epoch=epoch, amount=amount, to=self.treasury
                )
                time.sleep(min(5.0, mean_gap))
                continue

            used.add(amount)
            sent += 1
            self.sent_total += 1
            self.returned_total += amount
            self.log.emit(
                EVENT_GAS_RETURN_SENT,
                tip,
                {
                    "txid": txid,
                    "epoch": epoch,
                    "sequence": sequence,
                    "amount": amount,
                    "treasury_address": self.treasury,
                    "balance_before": balance,
                    "planned_this_epoch": planned,
                },
            )
            time.sleep(min(epoch_seconds, self.rng.expovariate(1.0 / mean_gap)))

        self.log.note(
            "epoch returns complete",
            tip,
            epoch=epoch,
            planned=planned,
            sent=sent,
            returned_total=round(self.returned_total, 8),
        )

    # -- per-epoch local audit ---------------------------------------------------------

    def sample_local(self, epoch: int, tip: int) -> None:
        """This miner's own view of its cluster's economics.

        Recorded from the miner rather than from the admin because these are the
        ``*getlocal*`` variants: they resolve "this node's" address internally, and
        reading them here is what makes the value attributable to this process.
        """
        buried = self.profile.last_buried_epoch(tip)
        if buried < 1:
            return
        for method in (
            "weightgetlocalreturns",
            "weightgetlocalearnings",
            "weightgetlocalbalance",
            "weightgetlocalclusterweight",
        ):
            try:
                self.log.snapshot(method, tip, self.rpc.call(method, buried), epoch=buried)
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error(method, exc, tip, epoch=buried)

    # -- the loop ----------------------------------------------------------------------

    def run(self) -> int:
        info = self.rpc.wait_ready(self.profile.runtime["startup_timeout_s"])
        tip = int(info.get("blocks", 0))
        self.log.set_address(self.rpc.own_address())
        self.log.note(
            "miner_gas_daemon attached",
            tip,
            treasury_address=self.treasury,
            returns_range=self.profile.traffic["miner_gas_returns_per_epoch_range"],
        )

        current_epoch = 0
        last_sampled = 0
        while not self.should_stop(tip):
            try:
                tip = self.rpc.block_height()
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error("getinfo", exc, None)
                time.sleep(3.0)
                continue

            buried = self.profile.last_buried_epoch(tip)
            if buried > last_sampled:
                self.sample_local(buried, tip)
                last_sampled = buried

            epoch = self.profile.epoch_of_height(tip)
            if epoch > current_epoch:
                current_epoch = epoch
                self.run_epoch(epoch, tip)
            else:
                time.sleep(2.0)

        self.sample_local(self.profile.last_buried_epoch(tip), tip)
        self.log.emit(
            EVENT_NODE_STOPPED,
            tip,
            {
                "sent_total": self.sent_total,
                "failed_total": self.failed_total,
                "returned_total": round(self.returned_total, 8),
                "last_epoch": current_epoch,
                "rpc_calls": self.rpc.calls,
                "rpc_failures": self.rpc.failures,
            },
        )
        return self.sent_total


def read_treasury(run_dir: Path) -> str:
    manifest = run_dir / "manifest.json"
    if manifest.is_file():
        data = json.loads(manifest.read_text(encoding="utf-8"))
        address = data.get("treasury_address")
        if address:
            return str(address)
    treasury_file = run_dir / "treasury.txt"
    if treasury_file.is_file():
        return treasury_file.read_text(encoding="utf-8").strip()
    raise SystemExit(
        "no treasury address in %s; the orchestrator writes it before starting the "
        "traffic daemons" % run_dir
    )


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    parser.add_argument("--node-id", required=True, help="e.g. miner-1")
    parser.add_argument("--treasury", default=None, help="override the treasury address")
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    node = profile.node(args.node_id)
    if node.role != "miner":
        raise SystemExit("%s is a %s, not a miner" % (args.node_id, node.role))

    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"
    treasury = args.treasury or read_treasury(run_dir)

    log = EventLog(run_dir, node.node_id, node.role, epoch_length=profile.epoch_length)
    rpc = RpcClient.from_datadir(
        chain_home / node.node_id,
        profile.chain_name,
        profile.host,
        node.rpc_port,
        node_id=node.node_id,
        timeout=profile.runtime["rpc_timeout_s"],
    )
    daemon = MinerGasDaemon(profile, node.node_id, run_dir, rpc, log, treasury)
    signal.signal(signal.SIGTERM, daemon.request_stop)
    signal.signal(signal.SIGINT, daemon.request_stop)
    try:
        daemon.run()
    finally:
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
