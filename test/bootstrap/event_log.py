"""The run's own event log: one JSON Lines file per node process.

Deliberately **not** the ``runtime/data/*/debug.log`` format of ``experiments/``. That
format is the node's, shaped by what the C++ chose to print; this one is the harness's,
shaped by what phase 1 has to read. One line is one fact, and every line is traceable to
a single RPC call or a single txid.

Layout::

    test/results/run-<name>-<UTC>/logs/<role>-<index>/events.jsonl

Schema — every line carries all eight fields, ``null`` where a field does not apply, so a
reader never has to test for a missing key:

===================  ======================================================================
``timestamp_utc``    ISO-8601 with a ``Z`` suffix, microsecond precision
``node_role``        ``admin`` | ``ca`` | ``miner`` | ``company``
``node_id``          ``admin``, ``miner-2``, … — also the log directory name
``node_address``     the node's wallet address, or ``null`` before it is known
``block_height``     tip height **as the emitting node saw it**, not a global clock
``epoch_index``      ``block_height // epoch_length``, 1-based; ``0`` = before epoch 1
``event_type``       see below
``payload``          free-form object; carries ``txid`` whenever a transaction was sent
===================  ======================================================================

There is no aggregation and no test at this layer, by design: phase 1 of the analysis
pipeline may only read and normalise, so anything computed here would be a conclusion
drawn before the data was complete.

Writes are line-buffered and flushed per record. A run that stalls at epoch 12 still
leaves 12 epochs of evidence, which is exactly the case where the evidence matters most.
"""

from __future__ import annotations

import datetime as _dt
import json
import os
import threading
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, Optional

# -- event types -----------------------------------------------------------------------
# Listed so that a reader of phase1_collect.py can see the whole vocabulary in one place.

EVENT_NODE_STARTED = "node_started"
EVENT_NODE_STOPPED = "node_stopped"
EVENT_PERMISSION_GRANTED = "permission_granted"
EVENT_STREAM_CREATED = "stream_created"
EVENT_STREAM_SUBSCRIBED = "stream_subscribed"
EVENT_GAS_SEEDED = "gas_seeded"
EVENT_GAS_REFUELLED = "gas_refuelled"
EVENT_MEMBERSHIP_REGISTERED = "membership_registered"
EVENT_ESG_SET = "esg_set"
EVENT_TRAFFIC_TX_SENT = "traffic_tx_sent"
EVENT_GAS_RETURN_SENT = "gas_return_sent"
EVENT_EPOCH_ENTERED = "epoch_entered"
EVENT_EPOCH_PLAN = "epoch_plan"
EVENT_SNAPSHOT = "snapshot"
EVENT_RPC_ERROR = "rpc_error"
EVENT_HARNESS_NOTE = "harness_note"

# -- the malicious-miner experiment ----------------------------------------------------
# Written only when a profile carries an enabled ``malicious`` section. They are the
# GROUND TRUTH of the experiment: what was offered, what was decided, what was broadcast
# and what the honest side made of it. Four types, in the order the evidence is produced.

#: One line per opportunity, per malicious miner, whether or not an action followed. The
#: line that says "no action" is as load-bearing as the one that says "acted": without it
#: the denominator of the realised rate would have to be guessed from the epoch geometry.
EVENT_MALICIOUS_OPPORTUNITY = "malicious_opportunity"

#: One line per action actually broadcast, carrying the txid. Distinct from the decision
#: above because a decided action can still fail to reach the node.
EVENT_MALICIOUS_ACTION_SENT = "malicious_action_sent"

#: One line per action observed CONFIRMED on chain. The third of the three states the
#: analysis must never conflate — attempted, sent, confirmed — because only a confirmed
#: action can carry a malus.
EVENT_MALICIOUS_ACTION_CONFIRMED = "malicious_action_confirmed"

#: One line per verdict of the honest detector, reported or refused. A refusal is kept:
#: it is what makes the false-positive rate measurable rather than assumed to be zero.
EVENT_MALUS_DETECTION = "malus_detection"

#: Snapshot kinds written by ``admin_daemon.py``. The value is the RPC that produced it,
#: so phase 1 can normalise each shape without guessing.
SNAPSHOT_KINDS = (
    "getinfo",
    "getblockchaininfo",
    "getlastblockinfo",
    "listblocks",
    "getallweights",
    "getallmalus",
    "wpoalistscores",
    "wpoalistdelays",
    "wpoalisteffectiveweights",
    "wpoalistfinalweights",
    "weightlistcontributions",
    "weightlistclusterweights",
    "weightlistreturns",
    "weightlistearnings",
    "weightlistbalances",
    "weightverifyweights",
    "liststreamitems",
    "listminers",
    "listpermissions",
    "getpeerinfo",
)


def utc_now() -> str:
    """ISO-8601 in UTC with a ``Z`` suffix — sortable as text, unambiguous as a timestamp."""
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def run_id(chain_name: str, when: Optional[_dt.datetime] = None) -> str:
    """``run-<chain>-<UTC>`` — the run directory name."""
    moment = when or _dt.datetime.now(_dt.timezone.utc)
    return "run-%s-%s" % (chain_name, moment.strftime("%Y%m%dT%H%M%SZ"))


class EventLog:
    """Append-only JSONL writer for one node process.

    Thread-safe because ``admin_daemon.py`` samples from a timer while the main loop
    writes; the lock costs nothing at this rate and removes a class of interleaved-line
    corruption that would only show up in the data.
    """

    def __init__(
        self,
        run_dir: str | Path,
        node_id: str,
        node_role: str,
        node_address: Optional[str] = None,
        epoch_length: int = 1,
    ) -> None:
        self.run_dir = Path(run_dir)
        self.node_id = node_id
        self.node_role = node_role
        self.node_address = node_address
        self.epoch_length = max(1, int(epoch_length))
        self.dir = self.run_dir / "logs" / node_id
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / "events.jsonl"
        self._lock = threading.Lock()
        self._handle = open(self.path, "a", encoding="utf-8", buffering=1)
        #: Count of every line written, by type. Reported at shutdown.
        self.counts: Dict[str, int] = {}

    # -- lifecycle ---------------------------------------------------------------------

    def set_address(self, address: Optional[str]) -> None:
        self.node_address = address

    def close(self) -> None:
        with self._lock:
            if not self._handle.closed:
                try:
                    self._handle.flush()
                    os.fsync(self._handle.fileno())
                except OSError:
                    pass
                self._handle.close()

    def __enter__(self) -> "EventLog":
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # -- writing -----------------------------------------------------------------------

    def emit(
        self,
        event_type: str,
        block_height: Optional[int] = None,
        payload: Optional[Dict[str, Any]] = None,
        node_address: Optional[str] = None,
    ) -> None:
        """Write one line.

        ``epoch_index`` is derived here rather than passed, so that the height and the
        epoch on a line can never disagree.
        """
        height = None if block_height is None else int(block_height)
        record = {
            "timestamp_utc": utc_now(),
            "node_role": self.node_role,
            "node_id": self.node_id,
            "node_address": node_address if node_address is not None else self.node_address,
            "block_height": height,
            "epoch_index": None if height is None else height // self.epoch_length,
            "event_type": event_type,
            "payload": payload or {},
        }
        line = json.dumps(record, default=_json_default, separators=(",", ":"))
        with self._lock:
            self._handle.write(line + "\n")
            self.counts[event_type] = self.counts.get(event_type, 0) + 1

    # -- shorthands used by more than one daemon ---------------------------------------

    def rpc_error(
        self,
        method: str,
        error: BaseException,
        block_height: Optional[int] = None,
        **context: Any,
    ) -> None:
        """Record a failed call.

        Every failure is logged, including the ones the harness recovers from: a run
        whose company daemons quietly lost a third of their publishes to a fee-policy
        rejection would otherwise report a low tau as a protocol result.
        """
        payload: Dict[str, Any] = {
            "method": method,
            "error": str(error),
            "error_class": type(error).__name__,
        }
        code = getattr(error, "code", None)
        if code is not None:
            payload["code"] = code
        payload.update(context)
        self.emit(EVENT_RPC_ERROR, block_height, payload)

    def note(self, message: str, block_height: Optional[int] = None, **context: Any) -> None:
        """A harness-level remark: a decision taken, a wait entered, a budget derived."""
        payload = {"message": message}
        payload.update(context)
        self.emit(EVENT_HARNESS_NOTE, block_height, payload)

    def snapshot(self, kind: str, block_height: Optional[int], data: Any, **context: Any) -> None:
        """One read-only RPC answer, verbatim.

        Stored unmodified: normalising here would be an aggregation, and phase 1 is the
        only place allowed to reshape anything.
        """
        payload: Dict[str, Any] = {"kind": kind, "data": data}
        payload.update(context)
        self.emit(EVENT_SNAPSHOT, block_height, payload)


def replay(
    run_dir: str | Path, node_id: str, event_types: Optional[Iterable[str]] = None
) -> Iterator[Dict[str, Any]]:
    """Read back one node's own log, in file order.

    THE LOG IS THE JOURNAL. A daemon that is restarted has to know what it already did,
    and the alternative — a second, private state file beside the events — would be a
    parallel log that could disagree with the evidence. Reading the evidence back
    guarantees the two can never diverge, because there is only one.

    ``events.jsonl`` is opened in append mode by every incarnation of a daemon, so a
    restart adds to the same file rather than truncating it, which is what makes this
    work. A truncated final line (a process killed mid-write) is skipped, exactly as
    ``phase1_collect.read_events`` skips it.
    """
    path = Path(run_dir) / "logs" / node_id / "events.jsonl"
    if not path.is_file():
        return
    wanted = None if event_types is None else set(event_types)
    with open(path, "r", encoding="utf-8", errors="replace") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if wanted is None or record.get("event_type") in wanted:
                yield record


def _json_default(value: Any) -> Any:
    """Last resort for anything json cannot encode — never silently drop a field."""
    if isinstance(value, (_dt.datetime, _dt.date)):
        return value.isoformat()
    if isinstance(value, set):
        return sorted(value)
    if isinstance(value, Path):
        return str(value)
    return repr(value)


__all__ = [
    "EVENT_EPOCH_ENTERED",
    "EVENT_MALICIOUS_ACTION_CONFIRMED",
    "EVENT_MALICIOUS_ACTION_SENT",
    "EVENT_MALICIOUS_OPPORTUNITY",
    "EVENT_MALUS_DETECTION",
    "EVENT_EPOCH_PLAN",
    "EVENT_ESG_SET",
    "EVENT_GAS_REFUELLED",
    "EVENT_GAS_RETURN_SENT",
    "EVENT_GAS_SEEDED",
    "EVENT_HARNESS_NOTE",
    "EVENT_MEMBERSHIP_REGISTERED",
    "EVENT_NODE_STARTED",
    "EVENT_NODE_STOPPED",
    "EVENT_PERMISSION_GRANTED",
    "EVENT_RPC_ERROR",
    "EVENT_SNAPSHOT",
    "EVENT_STREAM_CREATED",
    "EVENT_STREAM_SUBSCRIBED",
    "EVENT_TRAFFIC_TX_SENT",
    "EventLog",
    "SNAPSHOT_KINDS",
    "replay",
    "run_id",
    "utc_now",
]
