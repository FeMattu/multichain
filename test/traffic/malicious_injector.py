"""The malicious-action injector, driven by an existing miner daemon.

One instance lives inside a ``miner_gas_daemon.py`` process, and **only** on a miner the
run's plan named malicious. It adds no loop and no process of its own: the gas daemon
already ticks once per epoch off its own node's tip, and this hooks that tick. A miner the
plan did not select never constructs one, so the company daemons, the non-miner nodes and
every honest miner are byte-for-byte what they were before this feature existed.

What one opportunity does, in order:

1. **decide** — deterministically, from the plan seed, this miner's id, the epoch and the
   opportunity index, with no coordination and no mutable shared state (`malicious.py`);
2. **record the opportunity** — always, whether or not it acted, so the denominator of
   the realised rate is a logged fact and not an inference;
3. **if it acted** — build the payload for the chosen kind, skip it if this exact action
   (keyed by its deterministic ``action_id``) is already on chain, otherwise publish it
   and log the send;
4. **sweep confirmations** — check which previously-sent actions have now confirmed, and
   log each the first time it does.

Determinism and idempotency, together, are what make a restart safe: the decision for an
epoch is a pure function of the plan and the epoch, so a restarted daemon reaches the same
verdict; and the action's identity is its stream-item key, so the on-chain check refuses
to publish a second copy of something already there.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Dict, List, Optional

import malicious as M
from event_log import (
    EVENT_MALICIOUS_ACTION_CONFIRMED,
    EVENT_MALICIOUS_ACTION_SENT,
    EVENT_MALICIOUS_OPPORTUNITY,
    EventLog,
    replay,
)
from rpc_client import RpcError, RpcTransportError


class MaliciousInjector:
    """Injects malicious actions for one selected miner, one opportunity per epoch."""

    def __init__(
        self,
        profile,
        plan: Dict[str, Any],
        node_id: str,
        own_address: str,
        rpc,
        log: EventLog,
        run_id: str,
        all_addresses: Optional[Dict[str, str]] = None,
    ) -> None:
        self.profile = profile
        self.plan = plan
        self.node_id = node_id
        self.own_address = own_address
        self.rpc = rpc
        self.log = log
        self.run_id = run_id
        self.seed = int(plan["seed"])
        self.start_epoch = int(plan["start_epoch"])
        self.rate = float(plan.get("per_miner_target_rate", {}).get(node_id, 0.0))
        self.selfwrite_stream = plan.get("selfwrite_stream", M.SELF_ATTESTED_STREAMS[0])
        #: The addresses a selfwrite may falsely name: every participant but this signer.
        self.victim_pool = sorted(
            {addr for addr in (all_addresses or {}).values() if addr and addr != own_address}
        )
        #: Confirmations already logged, so a re-sweep does not double-log one.
        self._confirmed_action_ids = set(self._replay_confirmed())
        #: Which epochs already had their opportunity recorded, so a restart mid-epoch
        #: does not record a second one for the same epoch.
        self._offered_epochs = set(self._replay_offered_epochs())

    # -- restart recovery: the log is the journal --------------------------------------

    def _replay_offered_epochs(self) -> List[int]:
        return [
            int(rec.get("payload", {}).get("epoch"))
            for rec in replay(self.log.run_dir, self.node_id, (EVENT_MALICIOUS_OPPORTUNITY,))
            if rec.get("payload", {}).get("epoch") is not None
        ]

    def _replay_confirmed(self) -> List[str]:
        return [
            rec.get("payload", {}).get("action_id")
            for rec in replay(self.log.run_dir, self.node_id, (EVENT_MALICIOUS_ACTION_CONFIRMED,))
            if rec.get("payload", {}).get("action_id")
        ]

    def _replay_sent(self) -> List[Dict[str, Any]]:
        """Every action this miner has broadcast, from its own log."""
        return [
            rec.get("payload", {})
            for rec in replay(self.log.run_dir, self.node_id, (EVENT_MALICIOUS_ACTION_SENT,))
            if rec.get("payload", {}).get("action_id")
        ]

    # -- the deterministic decision ----------------------------------------------------

    def decision_for_epoch(self, epoch: int) -> Dict[str, Any]:
        """Replay the deficit controller from ``start_epoch`` up to ``epoch``.

        Pure: no chain, no clock, no stored state. The controller is rebuilt each time
        rather than carried, so a restarted daemon reaches exactly the state a
        never-restarted one would have — the epochs offered so far are the same, and the
        draws are seeded from the epoch, not from a call counter.
        """
        controller = M.RateController(self.rate)
        result: Dict[str, Any] = {}
        for e in range(self.start_epoch, epoch + 1):
            if not M.active_window(self.plan, e):
                continue
            index = e - self.start_epoch + 1
            draw = M.opportunity_rng(self.seed, self.node_id, e, index).random()
            result = controller.offer(draw)
            result["epoch"] = e
            result["opportunity_index"] = index
        return result

    # -- one opportunity ---------------------------------------------------------------

    def run_opportunity(self, epoch: int, tip: int) -> None:
        """The whole epoch's malicious behaviour: decide, record, maybe publish, sweep.

        The decision is derived deterministically, so a restart re-derives the same verdict.
        The opportunity is logged at most once (the log is the guard against a second line),
        but the injection is guarded by the on-chain check, not by the log — so a crash
        between logging the opportunity and completing the publish still lets the restarted
        daemon finish the send it decided on.
        """
        if not M.active_window(self.plan, epoch):
            return

        decision = self.decision_for_epoch(epoch)
        act = bool(decision.get("act"))
        index = decision.get("opportunity_index")
        action = M.choose_action(self.plan["actions"], self._action_draw(epoch, index)) if act else ""
        aid = M.action_id(self.run_id, self.node_id, epoch, index, action) if act else ""

        if epoch not in self._offered_epochs:
            self.log.emit(
                EVENT_MALICIOUS_OPPORTUNITY,
                tip,
                {
                    "run_id": self.run_id,
                    "epoch": epoch,
                    "miner": self.node_id,
                    "is_malicious": True,
                    "opportunity_index": index,
                    "opportunities_denominator": index,
                    "target_rate": decision.get("target_rate"),
                    "deficit": decision.get("deficit"),
                    "probability": decision.get("probability"),
                    "draw": decision.get("draw"),
                    "act": act,
                    "action": action or None,
                    "action_id": aid or None,
                    "attempted_so_far": decision.get("attempted_after"),
                    "realised_rate": decision.get("realised_rate"),
                },
                node_address=self.own_address,
            )
            self._offered_epochs.add(epoch)

        if act and action:
            self._inject(epoch, tip, action, aid, index)
        self.sweep_confirmations(epoch, tip)

    def _action_draw(self, epoch: int, index: int) -> float:
        """A second independent draw for the action-choice, so which action is chosen is
        not correlated with whether one is taken."""
        return M.opportunity_rng(self.seed, self.node_id, epoch, "%d:action" % index).random()

    # -- publishing --------------------------------------------------------------------

    def _already_on_chain(self, stream: str, action_id: str) -> Optional[dict]:
        """The confirmed item for ``action_id`` on ``stream``, or ``None``.

        The idempotency guard. ``liststreamkeyitems`` answers whether this exact action —
        keyed by its deterministic id — has already landed, so a retry or a restart never
        publishes a second copy. A transport failure here is reported as "unknown" (None)
        rather than "absent": re-publishing on a transient read error is a lesser evil
        than the alternative of never retrying a genuinely lost publish, and the confirmed
        item, when it does appear, is deduplicated by the confirmation sweep.
        """
        try:
            items = self.rpc.stream_key_items(stream, action_id)
        except (RpcError, RpcTransportError):
            return None
        for item in items or []:
            if (item.get("confirmations") or 0) >= 1 or item.get("blockheight") is not None:
                return item
        return items[0] if items else None

    def _inject(self, epoch: int, tip: int, action: str, action_id: str, index: int) -> None:
        if action == M.ACTION_SELFWRITE:
            stream, payload = self._build_selfwrite(epoch)
        elif action == M.ACTION_BADWEIGHT:
            stream, payload = self._build_badweight(epoch, tip)
        else:  # pragma: no cover - choose_action only returns supported kinds
            return
        if payload is None:
            self.log.note(
                "malicious action skipped: payload not constructible",
                tip,
                epoch=epoch,
                action=action,
                action_id=action_id,
            )
            return

        # Already on chain from a previous incarnation? Do not publish a second copy — but
        # still record the send, keyed by action_id so a duplicate line collapses in phase
        # 2. This is what closes the crash window between publishing and logging the send.
        existing = self._already_on_chain(stream, action_id)
        if existing is not None:
            if action_id not in self._sent_action_ids():
                self._emit_sent(epoch, tip, action, action_id, stream,
                                existing.get("txid", ""), payload, index)
            return

        try:
            txid = self.rpc.call("publish", stream, action_id, {"json": payload["json"]})
        except (RpcError, RpcTransportError) as exc:
            self.log.rpc_error(
                "publish", exc, tip, epoch=epoch, action=action, action_id=action_id,
                stream=stream,
            )
            return

        self._emit_sent(epoch, tip, action, action_id, stream, txid, payload, index)

    def _sent_action_ids(self) -> set:
        return {r.get("action_id") for r in self._replay_sent() if r.get("action_id")}

    def _emit_sent(self, epoch, tip, action, action_id, stream, txid, payload, index) -> None:
        self.log.emit(
            EVENT_MALICIOUS_ACTION_SENT,
            tip,
            {
                "run_id": self.run_id,
                "epoch": epoch,
                "miner": self.node_id,
                "opportunity_index": index,
                "action": action,
                "action_id": action_id,
                "stream": stream,
                "txid": txid,
                "declared_address": payload.get("declared_address"),
                "declared_weight": payload.get("declared_weight"),
                "true_weight": payload.get("true_weight"),
                "target_epoch": payload.get("target_epoch"),
            },
            node_address=self.own_address,
        )

    def _build_selfwrite(self, epoch: int):
        """A record on a self-attested stream naming an address other than the signer.

        Signed by this miner (``publish`` uses the node's own address), declaring a
        victim's address — the exact negation of ``mc_StreamItemIsSelfAttested``, so the
        readers discard it and the report proves itself.
        """
        rng = M.opportunity_rng(self.seed, self.node_id, epoch, "selfwrite-victim")
        try:
            victim = M.pick_victim(self.own_address, self.victim_pool, rng)
        except M.MaliciousConfigError:
            return self.selfwrite_stream, None
        if self.selfwrite_stream == "weight-engine-membership":
            body = M.selfwrite_membership_payload(victim, self.own_address, int(time.time()))
        else:
            body = M.selfwrite_weights_payload(victim, 100, epoch)
        return self.selfwrite_stream, {
            "json": body["json"],
            "declared_address": victim,
        }

    def _build_badweight(self, epoch: int, tip: int):
        """A ``wpoa-weights`` record about this miner, carrying a false value.

        The stated epoch is the newest buried one at the opportunity, so the honest
        detector can immediately recompute it and disagree; the false value is derived
        from the true weight (queried per that epoch) so the record is guaranteed to be a
        genuine ``badweight`` and not a coincidentally-correct one, which the registry
        would refuse.
        """
        target_epoch = self.profile.last_buried_epoch(tip)
        if target_epoch < 1:
            # Nothing is buried, so a badweight cannot be substantiated by any node.
            # Skip cleanly rather than publish an unprovable record.
            return "wpoa-weights", None
        true_weight = self._true_weight(target_epoch)
        rng = M.opportunity_rng(self.seed, self.node_id, epoch, "badweight-value")
        false_weight = M.falsify_weight(true_weight, rng)
        body = M.badweight_payload(self.own_address, false_weight, target_epoch)
        return "wpoa-weights", {
            "json": body["json"],
            "declared_address": self.own_address,
            "declared_weight": false_weight,
            "true_weight": true_weight,
            "target_epoch": target_epoch,
        }

    def _true_weight(self, epoch: int) -> int:
        """The weight the honest pipeline yields for this miner's cluster in ``epoch``.

        Best effort: the per-epoch cluster weight when the audit RPC answers, else the
        current published weight, else a nominal 100. The value only sets what to falsify
        *away from*; ``falsify_weight`` forces a strict difference regardless, so an
        imperfect read cannot make the record accidentally correct.
        """
        for method, args, key in (
            ("weightgetnodeclusterweight", (self.own_address, epoch), "final_cluster_weight"),
            ("getnodeweight", (self.own_address,), "weight"),
        ):
            try:
                answer = self.rpc.call(method, *args)
            except (RpcError, RpcTransportError):
                continue
            if isinstance(answer, dict) and answer.get(key) not in (None, ""):
                try:
                    value = int(round(float(answer[key])))
                    if value > 0:
                        return value
                except (TypeError, ValueError):
                    pass
        return 100

    # -- confirmation sweep ------------------------------------------------------------

    def sweep_confirmations(self, epoch: int, tip: int) -> None:
        """Log the first confirmation of each sent-but-unconfirmed action.

        Confirmation is the third state — attempted, sent, confirmed — and only a
        confirmed action can carry a malus, so the analysis needs it recorded separately.
        Read straight off the stream by the action's key, so "confirmed" here means what
        it means everywhere else: an item with a block height.
        """
        for sent in self._replay_sent():
            aid = sent.get("action_id")
            if not aid or aid in self._confirmed_action_ids:
                continue
            stream = sent.get("stream", "wpoa-weights")
            try:
                items = self.rpc.stream_key_items(stream, aid)
            except (RpcError, RpcTransportError):
                continue
            confirmed = next(
                (it for it in (items or [])
                 if (it.get("confirmations") or 0) >= 1 or it.get("blockheight") is not None),
                None,
            )
            if confirmed is None:
                continue
            self._confirmed_action_ids.add(aid)
            self.log.emit(
                EVENT_MALICIOUS_ACTION_CONFIRMED,
                tip,
                {
                    "run_id": self.run_id,
                    "epoch": sent.get("epoch"),
                    "miner": self.node_id,
                    "action": sent.get("action"),
                    "action_id": aid,
                    "stream": stream,
                    "txid": confirmed.get("txid", sent.get("txid", "")),
                    "confirm_height": confirmed.get("blockheight"),
                    "declared_address": sent.get("declared_address"),
                    "declared_weight": sent.get("declared_weight"),
                    "target_epoch": sent.get("target_epoch"),
                },
                node_address=self.own_address,
            )


__all__ = ["MaliciousInjector"]
