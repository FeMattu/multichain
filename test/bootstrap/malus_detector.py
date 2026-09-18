#!/usr/bin/env python3
"""The honest side: scan the input streams, report proved misbehaviour, record the verdict.

One process, attached to the **admin** node — the one node that is up for the whole run,
holds funds to pay the report fee, is subscribed to every stream and runs the weight
engine, so it can recompute a ``badweight`` and read a ``selfwrite``. It models an honest
validator exercising ``reportmalus``; running exactly one detector keeps every offence
reported at most once, which matters because the accumulator folds *every* valid report and
two reports of one offence would double-count it.

**It does not read the malicious daemons' ground truth.** Its only inputs are the public
streams and the node's own ``reportmalus`` predicate. For each confirmed item on a
self-attested stream it simply asks the node to report it; the node's ``Valid()`` check —
the same one every peer runs — accepts a genuine offence and refuses an honest record, and
this daemon records whichever answer came back. That independence is the whole point: the
detector's verdicts and the malicious daemons' ground truth are produced by two parties that
never talk, so comparing them in phase 3 measures detection rather than bookkeeping.

Three verdicts, all logged:

``reported``
    the node accepted the evidence and published a malus report; the report txid and the
    height it was reported at are recorded, which is what detection latency is measured
    from.
``refused``
    the node's predicate rejected the evidence — an honest record, or a ``badweight`` whose
    value recomputes correctly. This is the false-positive check: a run where every honest
    record is refused is a run where the mechanism does not punish the innocent.
``deferred``
    the node cannot yet decide — a ``badweight`` whose epoch is not buried here yet. Not
    terminal: retried on a later tick.

    python3 test/bootstrap/malus_detector.py --config <profile> --run-dir <run>
"""

from __future__ import annotations

import argparse
import signal
import sys
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

sys.path.insert(0, str(Path(__file__).resolve().parent))

import malicious as M  # noqa: E402
from config_loader import STREAM_MEMBERSHIP, STREAM_WEIGHTS, load_profile  # noqa: E402
from event_log import EVENT_MALUS_DETECTION, EVENT_NODE_STOPPED, EventLog, replay  # noqa: E402
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402

#: Streams a data-integrity offence can live on. Membership carries only selfwrite;
#: wpoa-weights carries both, disambiguated by whether the signer is the subject.
SCANNED_STREAMS = (STREAM_WEIGHTS, STREAM_MEMBERSHIP)

#: Substrings of a refusal reason that mean "cannot tell yet", not "not an offence". The
#: node fails closed on an unrecomputable epoch, and that is a deferral, not a verdict.
_DEFERRAL_MARKERS = (
    "cannot recompute",
    "not yet",
    "unreadable",
    "not buried",
    "pruned",
    "not found in this node's view",
    "unconfirmed",
    "not confirmed",
)


class MalusDetector:
    """Reads the self-attested streams and reports what the node proves is misbehaviour."""

    def __init__(self, profile, run_dir: Path, rpc: RpcClient, log: EventLog) -> None:
        self.profile = profile
        self.run_dir = Path(run_dir)
        self.rpc = rpc
        self.log = log
        self.stop_flag = self.run_dir / "STOP"
        self._running = True
        #: (kind, evidence_txid) already decided terminally — reported or refused — so a
        #: rescan never reports one offence twice or re-refuses an honest record.
        self._decided: Set[Tuple[str, str]] = set(self._replay_decided())

    def request_stop(self, *_: Any) -> None:
        self._running = False

    def should_stop(self, tip: int) -> bool:
        if not self._running or self.stop_flag.exists():
            return True
        return tip >= self.profile.target_height

    # -- restart recovery --------------------------------------------------------------

    def _replay_decided(self) -> List[Tuple[str, str]]:
        """Terminal verdicts from this detector's own log, so a restart resumes cleanly."""
        decided: List[Tuple[str, str]] = []
        for rec in replay(self.run_dir, self.log.node_id, (EVENT_MALUS_DETECTION,)):
            payload = rec.get("payload", {})
            if payload.get("verdict") in ("reported", "refused"):
                decided.append((payload.get("kind", ""), payload.get("evidence_txid", "")))
        return decided

    # -- one scan ----------------------------------------------------------------------

    def _candidates(self, stream: str) -> List[Dict[str, Any]]:
        """Confirmed items on ``stream`` that are *shaped* like an offence.

        The shaping test here is cheap and only narrows what to hand the node — the node's
        ``reportmalus`` predicate is the authority on validity. An item with no signer or
        no confirm height cannot be reported at all and is skipped.
        """
        try:
            items = self.rpc.stream_items(stream)
        except (RpcError, RpcTransportError):
            return []
        out: List[Dict[str, Any]] = []
        for item in items or []:
            txid = item.get("txid")
            publishers = item.get("publishers") or []
            height = item.get("blockheight")
            if not txid or not publishers or height is None:
                continue
            declared = self._declared_address(item)
            if not declared:
                continue
            signer = publishers[0]
            if stream == STREAM_MEMBERSHIP:
                # Only a forged membership (declared != signer) is an offence here.
                if declared != signer:
                    out.append({"kind": M.ACTION_SELFWRITE, "signer": signer,
                                "height": int(height), "txid": txid})
            else:  # wpoa-weights
                if declared != signer:
                    out.append({"kind": M.ACTION_SELFWRITE, "signer": signer,
                                "height": int(height), "txid": txid})
                else:
                    # A self-published weight: only reportmalus can tell whether its value
                    # is false, so every one is offered and the node's recomputation decides.
                    out.append({"kind": M.ACTION_BADWEIGHT, "signer": signer,
                                "height": int(height), "txid": txid})
        return out

    @staticmethod
    def _declared_address(item: Dict[str, Any]) -> str:
        """The ``node_address`` a stream item's payload declares, across item shapes."""
        data = item.get("data")
        if isinstance(data, dict):
            inner = data.get("json", data)
            if isinstance(inner, dict):
                return str(inner.get("node_address", "") or "")
        return ""

    def scan(self, tip: int) -> None:
        for stream in SCANNED_STREAMS:
            for candidate in self._candidates(stream):
                key = (candidate["kind"], candidate["txid"])
                if key in self._decided:
                    continue
                self._attempt(stream, candidate, tip)

    def _attempt(self, stream: str, candidate: Dict[str, Any], tip: int) -> None:
        kind = candidate["kind"]
        signer = candidate["signer"]
        height = candidate["height"]
        txid = candidate["txid"]
        try:
            report_txid = self.rpc.call("reportmalus", kind, signer, height, txid)
        except RpcError as exc:
            reason = str(getattr(exc, "message", "") or exc)
            deferred = any(marker in reason.lower() for marker in _DEFERRAL_MARKERS)
            self._emit(
                tip, "deferred" if deferred else "refused",
                kind, signer, height, txid, stream, reason=reason,
            )
            if not deferred:
                self._decided.add((kind, txid))
            return
        except RpcTransportError as exc:
            # The node did not answer: not a verdict. Retried next tick.
            self.log.rpc_error("reportmalus", exc, tip, kind=kind, evidence_txid=txid)
            return

        self._decided.add((kind, txid))
        self._emit(
            tip, "reported", kind, signer, height, txid, stream, report_txid=report_txid
        )

    def _emit(
        self,
        tip: int,
        verdict: str,
        kind: str,
        accused: str,
        offence_height: int,
        evidence_txid: str,
        stream: str,
        report_txid: str = "",
        reason: str = "",
    ) -> None:
        self.log.emit(
            EVENT_MALUS_DETECTION,
            tip,
            {
                "verdict": verdict,           # reported | refused | deferred
                "kind": kind,
                "accused_address": accused,
                "offence_height": offence_height,
                "offence_epoch": offence_height // self.profile.epoch_length,
                "evidence_txid": evidence_txid,
                "stream": stream,
                "report_txid": report_txid or None,
                "detect_height": tip,
                "detect_epoch": tip // self.profile.epoch_length,
                "reason": reason or None,
            },
        )

    # -- the loop ----------------------------------------------------------------------

    def run(self, poll_s: float = 2.0) -> int:
        info = self.rpc.wait_ready(self.profile.runtime["startup_timeout_s"])
        tip = int(info.get("blocks", 0))
        self.log.set_address(self.rpc.own_address())
        self.log.note("malus_detector attached", tip, streams=list(SCANNED_STREAMS))
        while not self.should_stop(tip):
            try:
                tip = self.rpc.block_height()
            except (RpcError, RpcTransportError) as exc:
                self.log.rpc_error("getinfo", exc, None)
                time.sleep(poll_s)
                continue
            self.scan(tip)
            if self.should_stop(tip):
                break
            time.sleep(poll_s)

        # A final scan: an offence confirmed in the last epoch becomes recomputable only
        # once its epoch buries, which may be after the loop's last ordinary tick.
        self.scan(tip)
        self.log.emit(
            EVENT_NODE_STOPPED,
            tip,
            {
                "reason": "target height" if tip >= self.profile.target_height
                else "stop requested",
                "final_height": tip,
                "decided": len(self._decided),
                "rpc_calls": self.rpc.calls,
                "rpc_failures": self.rpc.failures,
            },
        )
        return tip


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    parser.add_argument("--poll", type=float, default=2.0)
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"
    admin = profile.admin

    # A run without an enabled malicious experiment has nothing to detect. The daemon
    # still starts and exits cleanly, so the orchestrator can spawn it unconditionally.
    log = EventLog(run_dir, "malus-detector", admin.role, epoch_length=profile.epoch_length)
    rpc = RpcClient.from_datadir(
        chain_home / admin.node_id,
        profile.chain_name,
        profile.rpc_host(admin.node_id),
        admin.rpc_port,
        node_id="malus-detector",
        timeout=profile.runtime["rpc_timeout_s"],
    )
    detector = MalusDetector(profile, run_dir, rpc, log)
    signal.signal(signal.SIGTERM, detector.request_stop)
    signal.signal(signal.SIGINT, detector.request_stop)
    try:
        detector.run(args.poll)
    finally:
        log.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
