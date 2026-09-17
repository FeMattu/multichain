"""The malicious-miner experiment: configuration, selection, pacing and payloads.

**Pure logic only.** Nothing here opens a socket, reads a file or calls an RPC, so every
decision the experiment makes is unit-testable without a chain (``test/unit/``). The two
places that *do* talk to a node — the injector in
[`../traffic/miner_gas_daemon.py`](../traffic/miner_gas_daemon.py) and the honest detector
in [`malus_detector.py`](malus_detector.py) — consume this module and add nothing of their
own to the decisions.

Only **two** of the four malus kinds are implementable from outside the node, and this
module supports exactly those two:

``selfwrite``
    A record on a self-attested stream (``weight-engine-membership`` or ``wpoa-weights``)
    whose ``node_address`` is somebody else's, signed by the accused. The readers discard
    it on ``mc_StreamItemIsSelfAttested`` (`src/wpoa/weight_record.h`), and the report is
    the exact negation of that same predicate — so a record that is accused is precisely
    a record that was discarded.

``badweight``
    A ``wpoa-weights`` record the accused both signs *and* is the subject of — so it is
    **not** a selfwrite, the two being kept disjoint by `MalusRegistry::ValidDataIntegrityReport`
    — stating an epoch and a weight that does not survive re-running the pipeline over
    that epoch's public inputs.

``delay`` and ``equiv`` are **not** implemented and cannot be: the first needs a block
timestamped earlier than the miner's own sortition score entitles it to, the second two
distinct blocks at one height from one key. Both are produced inside
``miner.cpp``/``multichainblock.cpp``, and producing them would mean modifying the C++
consensus core.

Determinism
-----------
The daemons are separate OS processes and are forbidden to coordinate at runtime, so every
decision is *derived* rather than shared, in the same idiom the profile already uses for
its traffic RNGs::

    sub_seed = int(sha256("<seed>:<part>:<part>:...").hexdigest()[:16], 16)

Two runs of the same profile against the same chain therefore make the same decisions in
the same order in every process, with no message passing and no mutable shared file.
"""

from __future__ import annotations

import hashlib
import math
import random
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

# --------------------------------------------------------------------------------------
# Vocabulary
# --------------------------------------------------------------------------------------

#: Bumped whenever the shape of the resolved plan or of the ground-truth log changes, so a
#: run directory carries the version of the code that produced it and phase 1 can refuse a
#: shape it does not understand instead of misreading it.
SCHEMA_VERSION = "malicious/1"

ACTION_SELFWRITE = "selfwrite"
ACTION_BADWEIGHT = "badweight"

#: The kinds this harness can produce from outside the node. Deliberately a subset of the
#: four the registry accepts.
SUPPORTED_ACTIONS: Tuple[str, ...] = (ACTION_SELFWRITE, ACTION_BADWEIGHT)

#: The two that exist in the protocol but cannot be injected without touching the C++
#: core. Named explicitly so a profile asking for one gets the reason, not "unknown key".
UNIMPLEMENTABLE_ACTIONS: Dict[str, str] = {
    "delay": "a block timestamped earlier than its own sortition score entitles it to is "
             "produced inside miner.cpp; injecting one means modifying the consensus core",
    "equiv": "two distinct blocks at one height from one key is produced inside miner.cpp; "
             "injecting one means modifying the consensus core",
}

#: Stream names a selfwrite may target. Both are self-attested; no other stream has a rule
#: to break, and `ValidDataIntegrityReport` refuses a report naming one that has not.
SELF_ATTESTED_STREAMS = ("weight-engine-membership", "wpoa-weights")

#: Exactly one opportunity per malicious miner per epoch.
#:
#: WHY THIS AND NOT A BLOCK, A WIN OR A POLL CYCLE. The denominator has to be countable
#: per (miner, epoch) and independent of how the miner is faring, or the controller
#: diverges: a miner already penalised to Psi = 0 wins no blocks, so counting wins would
#: give it no opportunities and freeze its realised rate at whatever it was when the
#: penalty landed. A poll cycle would make the denominator a function of the daemon's
#: sleep schedule. An epoch is neither: every malicious miner gets exactly one opportunity
#: per epoch of the active window, whatever its weight, its malus or its luck.
#:
#: It is also the protocol's own grain for both implemented kinds. A weight is published
#: once per epoch and a membership declaration is a per-epoch statement, so a second
#: opportunity inside one epoch would either repeat the same record or — with
#: p(BadWeight) = 2.0 against M_max = 4.0 — saturate M inside a single epoch and destroy
#: the decay dynamics the experiment exists to observe.
OPPORTUNITIES_PER_EPOCH = 1

_DEFAULTS: Dict[str, Any] = {
    "enabled": False,
    "miner_count": 0,
    "target_action_rate": 0.0,
    "seed": None,          # None -> the profile's own seed
    "actions": {ACTION_SELFWRITE: 0.5, ACTION_BADWEIGHT: 0.5},
    "start_epoch": 1,
    "stop_epoch": None,    # None -> to the end of the run
    "selfwrite_stream": SELF_ATTESTED_STREAMS[0],
}

_KEYS = frozenset(_DEFAULTS)


class MaliciousConfigError(ValueError):
    """A ``malicious`` section that cannot be run.

    A distinct type, rather than ``config_loader.ConfigError``, so this module stays free
    of any import from the loader and can be exercised on its own. The loader catches it
    and re-raises it as its own error, so a profile author sees one error type.
    """


# --------------------------------------------------------------------------------------
# Validation
# --------------------------------------------------------------------------------------


def _require_number(value: Any, where: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise MaliciousConfigError("%s must be a number, got %r" % (where, value))
    number = float(value)
    if not math.isfinite(number):
        raise MaliciousConfigError("%s must be finite, got %r" % (where, value))
    return number


def _require_int(value: Any, where: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise MaliciousConfigError("%s must be an integer, got %r" % (where, value))
    return int(value)


def validate(raw: Any, miner_count: int, epoch_count: int, profile_seed: int) -> Dict[str, Any]:
    """Validate one ``malicious`` section and return it with every default filled in.

    ``miner_count`` and ``epoch_count`` come from the profile, so the two cross-checks
    that actually matter — a count that exceeds the miners there are, a window that lies
    outside the run — are caught here rather than surfacing as an empty result set three
    phases later.

    An absent section is **not** an error: it yields the disabled plan, and a profile
    without the section must behave exactly as it did before this feature existed.
    """
    if raw is None:
        return dict(_DEFAULTS, seed=profile_seed, enabled=False, actions=dict(_DEFAULTS["actions"]))
    if not isinstance(raw, dict):
        raise MaliciousConfigError(
            "malicious must be a mapping, got %s" % type(raw).__name__
        )

    unknown = sorted(set(raw) - _KEYS)
    if unknown:
        raise MaliciousConfigError(
            "unknown malicious key(s): %s. Allowed: %s"
            % (", ".join(unknown), ", ".join(sorted(_KEYS)))
        )

    out: Dict[str, Any] = dict(_DEFAULTS)
    out["actions"] = dict(_DEFAULTS["actions"])
    out.update({k: v for k, v in raw.items()})

    # -- enabled -----------------------------------------------------------------------
    if not isinstance(out["enabled"], bool):
        raise MaliciousConfigError("malicious.enabled must be true or false")

    # -- seed --------------------------------------------------------------------------
    if out["seed"] is None:
        out["seed"] = profile_seed
    else:
        seed = _require_int(out["seed"], "malicious.seed")
        if seed < 0:
            raise MaliciousConfigError("malicious.seed must be a non-negative integer")
        out["seed"] = seed

    # -- miner_count -------------------------------------------------------------------
    count = _require_int(out["miner_count"], "malicious.miner_count")
    if count < 0 or count > miner_count:
        raise MaliciousConfigError(
            "malicious.miner_count = %d is out of range: it must be between 0 and "
            "nodes.miner_count = %d" % (count, miner_count)
        )
    out["miner_count"] = count

    # -- target_action_rate ------------------------------------------------------------
    rate = _require_number(out["target_action_rate"], "malicious.target_action_rate")
    if not (0.0 <= rate <= 1.0):
        raise MaliciousConfigError(
            "malicious.target_action_rate = %r is out of range: it is a share of the "
            "available malicious opportunities and must lie in [0, 1]" % (rate,)
        )
    out["target_action_rate"] = rate

    # -- actions -----------------------------------------------------------------------
    actions_raw = out["actions"]
    if not isinstance(actions_raw, dict) or not actions_raw:
        raise MaliciousConfigError(
            "malicious.actions must be a non-empty mapping of action name to weight"
        )
    weights: Dict[str, float] = {}
    for name, value in actions_raw.items():
        if name in UNIMPLEMENTABLE_ACTIONS:
            raise MaliciousConfigError(
                "malicious.actions.%s is not implementable from the harness: %s. Only %s "
                "are supported."
                % (name, UNIMPLEMENTABLE_ACTIONS[name], " and ".join(SUPPORTED_ACTIONS))
            )
        if name not in SUPPORTED_ACTIONS:
            raise MaliciousConfigError(
                "malicious.actions.%s is not a known action. Supported: %s"
                % (name, ", ".join(SUPPORTED_ACTIONS))
            )
        weight = _require_number(value, "malicious.actions.%s" % name)
        if weight < 0:
            raise MaliciousConfigError(
                "malicious.actions.%s = %r must not be negative" % (name, value)
            )
        weights[name] = weight
    if sum(weights.values()) <= 0.0:
        raise MaliciousConfigError(
            "malicious.actions weights are all zero: no action could ever be chosen, "
            "which is not the same thing as malicious.enabled = false and is almost "
            "certainly not what was meant"
        )
    out["actions"] = normalise_actions(weights)

    # -- selfwrite_stream --------------------------------------------------------------
    stream = out["selfwrite_stream"]
    if stream not in SELF_ATTESTED_STREAMS:
        raise MaliciousConfigError(
            "malicious.selfwrite_stream must be one of %s: only a self-attested stream "
            "has a rule a selfwrite can break, and the registry refuses a report naming "
            "any other" % ", ".join(SELF_ATTESTED_STREAMS)
        )

    # -- window ------------------------------------------------------------------------
    start = _require_int(out["start_epoch"], "malicious.start_epoch")
    if start < 1:
        raise MaliciousConfigError(
            "malicious.start_epoch must be >= 1: epochs are 1-based in the protocol "
            "(HeightToEpoch = height / length + 1)"
        )
    if start > epoch_count:
        raise MaliciousConfigError(
            "malicious.start_epoch = %d lies past the last sampled epoch (epochs.count = "
            "%d): no opportunity would ever arise" % (start, epoch_count)
        )
    out["start_epoch"] = start

    if out["stop_epoch"] is not None:
        stop = _require_int(out["stop_epoch"], "malicious.stop_epoch")
        if stop < start:
            raise MaliciousConfigError(
                "malicious.stop_epoch = %d is before malicious.start_epoch = %d"
                % (stop, start)
            )
        out["stop_epoch"] = stop

    # -- coherence ---------------------------------------------------------------------
    if out["enabled"] and count == 0:
        raise MaliciousConfigError(
            "malicious.enabled is true but malicious.miner_count is 0: nothing would be "
            "injected. Set enabled = false instead, so the run records that the "
            "experiment was deliberately not run."
        )
    if out["enabled"] and rate == 0.0:
        raise MaliciousConfigError(
            "malicious.enabled is true but malicious.target_action_rate is 0: every "
            "opportunity would be declined. Set enabled = false instead."
        )
    return out


def normalise_actions(weights: Dict[str, float]) -> Dict[str, float]:
    """Scale the action weights to sum to 1, in a fixed key order.

    The order is fixed (:data:`SUPPORTED_ACTIONS`) rather than insertion order, so the
    cumulative draw below lands on the same action for the same random draw whatever order
    the profile happened to list them in.
    """
    total = float(sum(weights.get(name, 0.0) for name in SUPPORTED_ACTIONS))
    if total <= 0:
        raise MaliciousConfigError("action weights sum to zero")
    return {
        name: weights.get(name, 0.0) / total
        for name in SUPPORTED_ACTIONS
        if weights.get(name, 0.0) > 0.0
    }


# --------------------------------------------------------------------------------------
# Deterministic derivation
# --------------------------------------------------------------------------------------


def derive_seed(*parts: Any) -> int:
    """A 64-bit seed from an ordered tuple of facts. Same idiom as ``Profile.rng``."""
    material = ":".join(str(part) for part in parts)
    return int(hashlib.sha256(material.encode("utf-8")).hexdigest()[:16], 16)


def rng_for(*parts: Any) -> random.Random:
    """A generator seeded from :func:`derive_seed`."""
    return random.Random(derive_seed(*parts))


def select_miners(seed: int, miner_ids: Sequence[str], count: int) -> List[str]:
    """Pick ``count`` miners, reproducibly, from a seeded shuffle.

    Returned in **profile order**, not in draw order: the set is what matters and a stable
    order makes two manifests of the same profile diffable. ``count = 0`` yields the empty
    list, and a count equal to the number of miners yields all of them — an experiment
    where nobody is honest is a legitimate configuration, and the detector then has to run
    somewhere other than a miner (it runs on the admin; see ``malus_detector.py``).
    """
    if count <= 0:
        return []
    order = list(miner_ids)
    rng_for(seed, "malicious-selection").shuffle(order)
    chosen = set(order[:count])
    return [node_id for node_id in miner_ids if node_id in chosen]


def quota_shares(
    miner_ids: Sequence[str], initial_weights: Optional[Dict[str, float]] = None
) -> Dict[str, float]:
    """How the aggregate target is split across the malicious miners.

    Proportional to each miner's **initial share of the published weight**, so a miner that
    carries more of the election's probability mass also carries more of the misbehaviour —
    which is the interesting case, since that is where a malus has the largest effect on
    the distribution.

    Falls back to a uniform split when no weight is available (the registry is empty early
    in a run) or when every weight is zero. The fallback is recorded in the ground-truth
    log rather than silently applied: a uniform split and a weight-proportional split that
    *happens* to be uniform are different facts.
    """
    if not miner_ids:
        return {}
    uniform = 1.0 / len(miner_ids)
    if not initial_weights:
        return {node_id: uniform for node_id in miner_ids}
    values = {node_id: max(0.0, float(initial_weights.get(node_id) or 0.0)) for node_id in miner_ids}
    total = sum(values.values())
    if total <= 0:
        return {node_id: uniform for node_id in miner_ids}
    return {node_id: values[node_id] / total for node_id in miner_ids}


def per_miner_rate(target_action_rate: float, n_malicious: int, share: float) -> float:
    """This miner's own target rate, from the aggregate one and its quota share.

    The aggregate target is ``target_action_rate * O_total`` actions over ``O_total``
    opportunities. Miner *m* is allotted ``share_m`` of those actions, and — because every
    malicious miner sees exactly one opportunity per epoch of the window
    (:data:`OPPORTUNITIES_PER_EPOCH`) — exactly ``O_total / n`` of the opportunities. Its
    own rate is therefore ``target * n * share_m``, which collapses to ``target`` when the
    split is uniform.

    Clamped to 1: a miner holding more than ``1/(n*target)`` of the weight would otherwise
    be asked for more actions than it has opportunities, and the deficit would grow without
    bound instead of saturating.
    """
    if n_malicious <= 0:
        return 0.0
    return max(0.0, min(1.0, target_action_rate * n_malicious * share))


class RateController:
    """A deficit controller over one miner's own opportunities.

    At opportunity *k* the miner *should* have attempted ``rate * k`` actions and has
    attempted ``a``. The probability of acting now is the deficit ``rate * k - a``, clamped
    to ``[0, 1]``:

    * the expectation of the attempt count tracks ``rate * k``, so the realised rate
      converges on the target without any coordination between miners;
    * a miner that has fallen behind (deficit near or above 1) acts at every opportunity
      until it has caught up, which is what makes a short run land near the target instead
      of systematically under it;
    * the clamp at 0 is what stops a miner that has run *ahead* — which happens whenever
      the target is not an exact multiple of ``1/k`` — from being asked to act again, so
      the target is never systematically overshot.

    It is a pure object: the caller supplies the uniform draw, so the same sequence of
    draws always yields the same sequence of decisions.
    """

    def __init__(self, rate: float, opportunities: int = 0, attempted: int = 0) -> None:
        self.rate = max(0.0, min(1.0, float(rate)))
        #: Restored from the ground-truth log on a restart, so a daemon that died halfway
        #: resumes its own controller rather than starting a second one from zero.
        self.opportunities = int(opportunities)
        self.attempted = int(attempted)

    @property
    def realised_rate(self) -> Optional[float]:
        return (self.attempted / self.opportunities) if self.opportunities else None

    def deficit(self) -> float:
        """The deficit the *next* opportunity would be judged against."""
        return self.rate * (self.opportunities + 1) - self.attempted

    def offer(self, draw: float) -> Dict[str, Any]:
        """Account for one opportunity and decide. ``draw`` is uniform on [0, 1)."""
        self.opportunities += 1
        deficit = self.rate * self.opportunities - self.attempted
        probability = max(0.0, min(1.0, deficit))
        act = draw < probability
        if act:
            self.attempted += 1
        return {
            "opportunity_index": self.opportunities,
            "target_rate": self.rate,
            "deficit": deficit,
            "probability": probability,
            "draw": draw,
            "act": act,
            "attempted_after": self.attempted,
            "realised_rate": self.realised_rate,
        }


def choose_action(actions: Dict[str, float], draw: float) -> str:
    """Pick an action from the normalised mix. ``draw`` is uniform on [0, 1).

    Iterated in :data:`SUPPORTED_ACTIONS` order so the mapping from draw to action is a
    property of the mix, not of how the profile spelled it.
    """
    cumulative = 0.0
    last = ""
    for name in SUPPORTED_ACTIONS:
        weight = actions.get(name, 0.0)
        if weight <= 0:
            continue
        last = name
        cumulative += weight
        if draw < cumulative:
            return name
    if not last:
        raise MaliciousConfigError("no action carries a positive weight")
    return last   # floating-point residue at draw ~ 1.0


def action_id(run_id: str, miner_id: str, epoch: int, opportunity_index: int, action: str) -> str:
    """A stable identity for one intended action.

    Derived from facts that are all decided *before* anything is broadcast, so a daemon
    that is killed between deciding and publishing recomputes exactly the same id on its
    next start. That is what makes the on-chain check idempotent: the id is used as the
    **stream item key**, so ``liststreamkeyitems <stream> <action_id>`` answers "has this
    exact action already landed?" without any local state at all.
    """
    return hashlib.sha256(
        ("%s|%s|%d|%d|%s" % (run_id, miner_id, epoch, opportunity_index, action)).encode("utf-8")
    ).hexdigest()[:24]


def opportunity_rng(seed: int, miner_id: str, epoch: int, opportunity_index: int) -> random.Random:
    """The generator for one opportunity: seeded from the plan seed, the miner, the epoch
    and the opportunity counter, and from nothing else.

    No shared state, no wall clock, no chain data. Two runs of the same profile make the
    same decisions in the same order, and a restarted daemon resumes the same sequence
    rather than a fresh one.
    """
    return rng_for(seed, "malicious-opportunity", miner_id, epoch, opportunity_index)


# --------------------------------------------------------------------------------------
# Payloads
# --------------------------------------------------------------------------------------
#
# Every payload below is built to satisfy EXACTLY ONE evidence predicate of
# MalusRegistry::ValidDataIntegrityReport, and to stay syntactically decodable by the same
# parsers the honest readers use (mc_ParseWeightRecordJson, mc_ParseMembershipRecordJson).
# A malformed payload would be discarded before it ever reached the predicate, and the
# experiment would measure "the node ignores garbage" rather than "the node proves a
# specific offence".


def selfwrite_membership_payload(
    declared_address: str, miner_address: str, timestamp: int
) -> Dict[str, Any]:
    """A membership record naming somebody else.

    Shape per ``mc_ParseMembershipRecordJson``: ``node_address`` and ``miner_address`` both
    non-empty strings, ``timestamp`` an exact non-negative integer that fits in a uint32.
    The record parses; what it violates is the self-attestation rule, because the signer
    will be the attacker and ``node_address`` is not.

    Membership is the preferred target over ``wpoa-weights``: the forged record touches a
    stream the *engine* reads rather than the one the *election* reads, so the injection
    cannot perturb the weight registry even for the moment before it is discarded.
    """
    if not declared_address or not miner_address:
        raise MaliciousConfigError("a membership record needs both addresses")
    stamp = int(timestamp)
    if stamp < 0 or stamp > 0xFFFFFFFF:
        raise MaliciousConfigError("timestamp must fit in a uint32")
    return {
        "json": {
            "node_address": declared_address,
            "miner_address": miner_address,
            "timestamp": stamp,
        }
    }


def selfwrite_weights_payload(declared_address: str, weight: int, epoch: int) -> Dict[str, Any]:
    """A ``wpoa-weights`` record naming somebody else.

    The alternative selfwrite target, selectable with ``malicious.selfwrite_stream``. It
    parses under ``mc_ParseWeightRecordJson`` (non-empty address, strictly positive
    integer weight) and is discarded by the reader for the same reason as above — so the
    registry is unaffected — but it does put a discarded record on the stream the election
    reads, which is a different experiment and is therefore opt-in.
    """
    if not declared_address:
        raise MaliciousConfigError("a weight record needs a declared address")
    value = int(weight)
    if value <= 0:
        raise MaliciousConfigError("a weight record needs a strictly positive weight")
    return {"json": {"node_address": declared_address, "weight": value, "epoch": int(epoch)}}


def badweight_payload(own_address: str, weight: int, epoch: int) -> Dict[str, Any]:
    """A ``wpoa-weights`` record about *oneself*, carrying a false value.

    Every field is what the predicate needs it to be:

    * ``node_address`` is the signer's own, so the record is self-attested and the report
      is a ``badweight`` rather than a ``selfwrite`` — the registry keeps the two disjoint
      and refuses a badweight the accused did not sign;
    * ``epoch`` is stated and non-zero, because a record with no epoch is not
      value-verifiable at all (the static ``-weight`` path) and cannot be accused;
    * ``weight`` is a strictly positive integer, so the record parses and enters the map,
      which is what makes this the one implemented offence that actually *succeeds* until
      somebody recomputes it.
    """
    if not own_address:
        raise MaliciousConfigError("a weight record needs a declared address")
    value = int(weight)
    if value <= 0:
        raise MaliciousConfigError("a weight record needs a strictly positive weight")
    if int(epoch) <= 0:
        raise MaliciousConfigError(
            "a badweight record must state a non-zero epoch: a weight with no epoch is "
            "not value-verifiable, so the registry refuses to accuse it"
        )
    return {"json": {"node_address": own_address, "weight": value, "epoch": int(epoch)}}


def falsify_weight(true_weight: int, rng: random.Random) -> int:
    """A weight deliberately different from the one the pipeline recomputes.

    Inflated rather than deflated, and by a visible factor: a deflated weight would be a
    self-harming attack nobody would mount, and a value one unit away would be
    indistinguishable in a plot from a rounding artefact. The result is clamped to a
    strictly positive integer and forced to differ from the true value, since a record
    whose value happens to be *correct* is refused by the registry with exactly that
    reason and would be scored as a failed injection rather than a detected one.
    """
    base = max(1, int(true_weight))
    factor = 1.5 + rng.random() * 1.5          # [1.5, 3.0)
    value = int(round(base * factor))
    if value <= base:
        value = base + max(1, base // 2)
    return max(1, value)


def pick_victim(own_address: str, candidates: Sequence[str], rng: random.Random) -> str:
    """The address a selfwrite falsely names.

    Any address other than the signer's satisfies the predicate, but a *real participant's*
    is chosen so the forgery is the one an attacker would actually attempt — a record that
    would have moved a real cluster had the self-attestation rule not discarded it.
    """
    others = sorted({address for address in candidates if address and address != own_address})
    if not others:
        raise MaliciousConfigError(
            "no address other than the signer's is available to name in a selfwrite"
        )
    return others[rng.randrange(len(others))]


# --------------------------------------------------------------------------------------
# The resolved plan
# --------------------------------------------------------------------------------------


def active_window(plan: Dict[str, Any], epoch: int) -> bool:
    """Is ``epoch`` inside the plan's window? ``stop_epoch = None`` means "to the end"."""
    if not plan.get("enabled"):
        return False
    if epoch < int(plan.get("start_epoch") or 1):
        return False
    stop = plan.get("stop_epoch")
    return stop is None or epoch <= int(stop)


def resolve_plan(
    config: Dict[str, Any],
    miner_ids: Sequence[str],
    addresses: Optional[Dict[str, str]] = None,
    initial_weights: Optional[Dict[str, float]] = None,
) -> Dict[str, Any]:
    """The immutable description of one run's malicious experiment.

    Everything the injector and the analysis need, decided once and written to
    ``<run>/malicious_manifest.json``. It carries the *resolved* configuration rather than
    a pointer to the profile, so re-analysing a finished run cannot pick up a profile that
    has been edited since — which would silently reinterpret what the run did.
    """
    selected = select_miners(int(config["seed"]), miner_ids, int(config["miner_count"]))
    shares = quota_shares(
        selected,
        {node_id: initial_weights.get(node_id) for node_id in selected} if initial_weights else None,
    )
    n = len(selected)
    rates = {
        node_id: per_miner_rate(float(config["target_action_rate"]), n, shares.get(node_id, 0.0))
        for node_id in selected
    }
    address_of = addresses or {}
    return {
        "schema_version": SCHEMA_VERSION,
        "enabled": bool(config["enabled"]),
        "seed": int(config["seed"]),
        "target_action_rate": float(config["target_action_rate"]),
        "miner_count": int(config["miner_count"]),
        "actions": dict(config["actions"]),
        "start_epoch": int(config["start_epoch"]),
        "stop_epoch": config["stop_epoch"],
        "selfwrite_stream": config["selfwrite_stream"],
        "opportunities_per_epoch": OPPORTUNITIES_PER_EPOCH,
        "all_miner_ids": list(miner_ids),
        "malicious_miner_ids": selected,
        "malicious_miner_addresses": {
            node_id: address_of.get(node_id, "") for node_id in selected
        },
        "honest_miner_ids": [m for m in miner_ids if m not in set(selected)],
        "quota_shares": shares,
        "quota_share_source": "initial_published_weight" if initial_weights else "uniform",
        "per_miner_target_rate": rates,
        "unimplementable_actions": dict(UNIMPLEMENTABLE_ACTIONS),
    }


def disabled_plan(miner_ids: Sequence[str]) -> Dict[str, Any]:
    """The plan a profile without a ``malicious`` section produces.

    Written unconditionally, so every run directory carries the same file and phase 1 never
    has to distinguish "the experiment was off" from "this run predates the feature".
    """
    return resolve_plan(
        dict(_DEFAULTS, enabled=False, miner_count=0, seed=0, actions=dict(_DEFAULTS["actions"])),
        miner_ids,
    )


__all__ = [
    "ACTION_BADWEIGHT",
    "ACTION_SELFWRITE",
    "MaliciousConfigError",
    "OPPORTUNITIES_PER_EPOCH",
    "RateController",
    "SCHEMA_VERSION",
    "SELF_ATTESTED_STREAMS",
    "SUPPORTED_ACTIONS",
    "UNIMPLEMENTABLE_ACTIONS",
    "action_id",
    "active_window",
    "badweight_payload",
    "choose_action",
    "derive_seed",
    "disabled_plan",
    "falsify_weight",
    "normalise_actions",
    "opportunity_rng",
    "per_miner_rate",
    "pick_victim",
    "quota_shares",
    "resolve_plan",
    "rng_for",
    "select_miners",
    "selfwrite_membership_payload",
    "selfwrite_weights_payload",
    "validate",
]
