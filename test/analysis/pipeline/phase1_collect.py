#!/usr/bin/env python3
"""Phase 1 — collect. Read the raw logs, normalise their shapes, write flat tables.

**The rule of this phase: no aggregation, no test, no interpretation.** One input record
becomes one output row. The only derivations permitted are the two that are pure functions
of a height and the chain parameters:

* ``epoch = height // weight_epoch_length``
* ``in_setup = height <= setup_first_blocks``

Anything else — a sum, a share, a rate — belongs to phase 2, and a statistic belongs to
phase 3. The discipline is what makes a surprising number in a final report traceable back
through a phase-2 row to a phase-1 row to a single line of a node's ``events.jsonl`` and the
RPC call that produced it.

**What it reads**: ``<run>/logs/*/events.jsonl`` and ``<run>/manifest.json``. Nothing else,
and in particular nothing from the chain — by the time this runs the nodes are gone.

**What it writes**: ``<run>/analysis/phase1/*.csv`` plus a ``manifest.json``.

The normalisation this phase exists for: the audit RPCs do **not** agree on a result shape.
``weightlistreturns`` and ``weightlistbalances`` map an address to a bare number;
``weightlistcontributions``, ``weightlistclusterweights``, ``weightlistearnings`` and the
four ``wpoalist*`` families map an address to an object; ``getallweights`` maps an address
to a bare number; ``weightverifyweights`` returns an array. Every one of them becomes the
same thing here: a long table with one row per (sample, address).
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import OrderedDict
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "bootstrap"))

from config_loader import STABILITY_MARGIN, ConfigError, load_profile  # noqa: E402

#: Column order is fixed per table, so an empty table still has a usable header and two
#: runs produce diffable CSVs.
COLUMNS: "OrderedDict[str, List[str]]" = OrderedDict(
    [
        ("nodes", ["node_id", "role", "address", "port", "rpc_port", "cluster_head_node_id",
                   "cluster_head_address", "is_admin", "is_treasury"]),
        ("config", ["parameter", "value", "source", "note"]),
        # The emulated map's propagation, validator pair by validator pair. Empty in the
        # native regime, where there is no map and nothing to propagate across.
        ("topology_paths", ["validator_i", "validator_j", "site_i", "site_j",
                            "path_delay_ms"]),
        ("blocks", ["height", "hash", "miner_address", "time", "txcount", "confirmations",
                    "epoch", "in_setup"]),
        ("round_scores", ["round_height", "epoch", "in_setup", "address", "score", "weight",
                          "effective_weight", "eligible", "seed", "seed_source",
                          "dumping_function", "total_effective_weight", "sample_height"]),
        ("round_delays", ["round_height", "epoch", "in_setup", "address", "delay_s", "score",
                          "score_norm", "effective_weight", "eligible", "target_block_time",
                          "delta", "lambda_s", "feedback_phi", "seed", "seed_source",
                          "dumping_function", "total_effective_weight", "sample_height"]),
        ("round_effective_weights", ["round_height", "epoch", "in_setup", "address",
                                     "raw_weight", "dumping_function", "effective_weight",
                                     "sample_height"]),
        ("round_final_weights", ["round_height", "epoch", "in_setup", "address", "raw_weight",
                                 "malus", "malus_factor", "weight_after_malus",
                                 "dumping_function",
                                 "effective_weight_after_malus_and_dumping", "eligible",
                                 "malus_epoch", "sample_height"]),
        ("registry_weights", ["sample_height", "epoch", "address", "weight", "validators",
                              "total"]),
        ("malus", ["sample_height", "epoch", "address", "malus", "psi", "weight", "effective",
                   "excluded", "epochs_to_clear", "enabled"]),
        ("epoch_contributions", ["epoch", "address", "cluster", "esg_score", "activity",
                                 "kappa", "contribution", "sample_height"]),
        ("epoch_cluster_weights", ["epoch", "miner", "miner_esg_score", "miner_activity",
                                   "companies", "companies_contribution_sum", "kappa",
                                   "raw_cluster_weight", "previous_epoch_return_rate",
                                   "lambda_w", "final_cluster_weight", "published_weight",
                                   "sample_height"]),
        ("epoch_returns", ["epoch", "miner", "treasury_address", "returns", "sample_height"]),
        ("epoch_earnings", ["epoch", "miner", "income", "expenses_gross",
                            "expenses_excl_return", "earnings", "return_amount", "balance",
                            "return_rate", "sample_height"]),
        ("epoch_balances", ["epoch", "miner", "balance", "sample_height"]),
        ("verification", ["epoch", "verified", "records", "invalid", "address", "published",
                          "published_epoch", "recomputed", "verdict", "sample_height"]),
        ("esg_events", ["timestamp_utc", "block_height", "epoch", "ca_node_id",
                        "target_node_id", "target_role", "target_address", "esg_score",
                        "txid"]),
        ("membership_events", ["timestamp_utc", "block_height", "epoch", "node_id",
                               "node_address", "miner_node_id", "miner_address",
                               "is_cluster_head", "txid"]),
        ("traffic_tx", ["timestamp_utc", "block_height", "epoch", "node_id", "node_address",
                        "declared_epoch", "sequence", "stream", "key", "txid",
                        "planned_this_epoch"]),
        ("gas_returns", ["timestamp_utc", "block_height", "epoch", "node_id", "node_address",
                         "declared_epoch", "sequence", "amount", "treasury_address",
                         "balance_before", "txid", "planned_this_epoch"]),
        ("gas_transfers", ["timestamp_utc", "block_height", "epoch", "kind", "node_id",
                           "role", "amount", "balance_before", "txid"]),
        ("epoch_plans", ["timestamp_utc", "block_height", "node_id", "node_role", "epoch",
                         "planned_tx", "planned_returns", "mean_gap_s"]),
        ("stream_items", ["stream", "txid", "publisher", "key", "confirm_height", "epoch",
                          "blocktime", "confirmations", "data_json", "sample_height"]),
        ("miners", ["sample_height", "address", "islocal", "permitted",
                    "diversitywaitblocks"]),
        ("permissions", ["sample_height", "address", "type", "entity", "startblock",
                         "endblock"]),
        ("peers", ["sample_height", "peer_id", "addr", "subver", "inbound",
                   "startingheight", "synced_blocks"]),
        ("node_state", ["sample_height", "node_id", "blocks", "connections", "balance"]),
        ("rpc_errors", ["timestamp_utc", "node_id", "node_role", "block_height", "method",
                        "code", "error", "context_json"]),
        # -- the malicious-miner experiment --------------------------------------------
        # These five are empty on a plain run, and their headers still write, so phase 2
        # can read them unconditionally and a diff of two runs stays clean.
        ("malicious_config", ["parameter", "value", "source"]),
        ("malicious_miners", ["node_id", "address", "is_malicious", "quota_share",
                              "target_rate", "quota_share_source"]),
        ("malicious_opportunities", ["timestamp_utc", "block_height", "epoch", "miner",
                                     "node_address", "opportunity_index",
                                     "opportunities_denominator", "target_rate", "deficit",
                                     "probability", "draw", "act", "action", "action_id",
                                     "attempted_so_far", "realised_rate"]),
        ("malicious_actions", ["timestamp_utc", "block_height", "epoch", "miner",
                               "node_address", "opportunity_index", "action", "action_id",
                               "stream", "txid", "declared_address", "declared_weight",
                               "true_weight", "target_epoch"]),
        ("malicious_confirmations", ["timestamp_utc", "block_height", "epoch", "miner",
                                     "node_address", "action", "action_id", "stream", "txid",
                                     "confirm_height", "declared_address", "declared_weight",
                                     "target_epoch"]),
        ("malus_detections", ["timestamp_utc", "detect_height", "detect_epoch", "verdict",
                              "kind", "accused_address", "offence_height", "offence_epoch",
                              "evidence_txid", "stream", "report_txid", "reason"]),
    ]
)


class Phase1Error(RuntimeError):
    """The run directory does not hold enough to collect."""


# --------------------------------------------------------------------------------------
# reading
# --------------------------------------------------------------------------------------


def read_events(run_dir: Path) -> Iterator[Dict[str, Any]]:
    """Every event line of every node, in file order.

    A truncated final line is skipped rather than fatal: a run killed mid-write is exactly
    when the preceding evidence matters most, and losing it to a JSON error would be the
    worst possible trade.
    """
    for path in sorted((run_dir / "logs").glob("*/events.jsonl")):
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            for number, line in enumerate(handle, start=1):
                line = line.strip()
                if not line:
                    continue
                try:
                    record = json.loads(line)
                except ValueError:
                    continue
                record["_source_file"] = path.name
                record["_source_dir"] = path.parent.name
                record["_source_line"] = number
                yield record


def _num(value: Any) -> Any:
    """Pass numbers through, map ``None``/non-numeric to ``''`` so a CSV cell stays empty."""
    if value is None or isinstance(value, bool):
        return value if isinstance(value, bool) else ""
    if isinstance(value, (int, float)):
        return value
    try:
        return float(value)
    except (TypeError, ValueError):
        return value


class Collector:
    """Accumulates rows per table while walking the events once."""

    def __init__(self, profile, manifest: Dict[str, Any]) -> None:
        self.profile = profile
        self.manifest = manifest
        self.tables: Dict[str, List[Dict[str, Any]]] = {name: [] for name in COLUMNS}
        self.setup_blocks = int(
            manifest.get("effective_setup_first_blocks")
            or manifest.get("derived", {}).get("setup_first_blocks_requested")
            or 0
        )
        self.epoch_length = int(
            manifest.get("epochs", {}).get("length_blocks") or profile.epoch_length
        )
        #: Guards against double-counting: the admin daemon re-samples a stream at every
        #: epoch boundary, so the same item arrives many times.
        self._seen_stream_items: set = set()
        self._seen_rounds: Dict[str, set] = {}
        self._seen_epoch_rows: Dict[str, set] = {}

    # -- helpers -----------------------------------------------------------------------

    def epoch_of(self, height: Optional[int]) -> Any:
        if height is None or height == "":
            return ""
        return int(height) // self.epoch_length

    def in_setup(self, height: Optional[int]) -> Any:
        if height is None or height == "":
            return ""
        return bool(int(height) <= self.setup_blocks)

    def add(self, table: str, **row: Any) -> None:
        self.tables[table].append(row)

    def _once(self, store: str, key: Any) -> bool:
        """``True`` the first time a key is offered, ``False`` afterwards."""
        seen = self._seen_rounds.setdefault(store, set())
        if key in seen:
            return False
        seen.add(key)
        return True

    # -- static tables -----------------------------------------------------------------

    def collect_nodes(self) -> None:
        addresses = self.manifest.get("addresses", {}) or {}
        clusters = self.manifest.get("clusters", {}) or {}
        treasury = self.manifest.get("treasury_address")
        for node in self.profile.nodes:
            head = clusters.get(node.node_id, node.node_id if node.role == "miner" else "")
            self.add(
                "nodes",
                node_id=node.node_id,
                role=node.role,
                address=addresses.get(node.node_id, ""),
                port=node.port,
                rpc_port=node.rpc_port,
                cluster_head_node_id=head,
                cluster_head_address=addresses.get(head, "") if head else "",
                is_admin=node.is_admin,
                is_treasury=False,
            )
        if treasury:
            self.add(
                "nodes",
                node_id="treasury",
                role="treasury",
                address=treasury,
                port="",
                rpc_port="",
                cluster_head_node_id="",
                cluster_head_address="",
                is_admin=False,
                is_treasury=True,
            )

    def collect_topology_paths(self, run_dir: Path) -> None:
        """One row per ordered pair of validators: how long a block takes to cross.

        Read from ``<run>/fabric.json``, which the orchestrator wrote when it built the
        network, and normalised into a table like everything else phase 1 touches — no
        aggregation, no statistic, just the shortest-path delay the map implies between
        the sites two validators sit at.

        This is the input ``S1`` never had. The quantity is the **end-to-end path** delay
        between validators, not the delay of a single cable: what the inversion bound is
        about is how far apart two validators are in seeing the same block, and a cable
        between two sites that host no validator contributes nothing to that.

        Absent in a native run, where every node is a local process: the table is then
        empty and S1 is reported as not measurable, which is the truth of that regime.
        """
        manifest = Path(run_dir) / "fabric.json"
        if not manifest.is_file():
            return
        try:
            described = json.loads(manifest.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return
        sites = {n: e.get("site") for n, e in (described.get("nodes") or {}).items()}
        links = described.get("links") or []
        if not links or not sites:
            return

        # Dijkstra over the realised cables, weighted by the delay each one actually got.
        graph: Dict[str, Dict[str, float]] = {}
        for link in links:
            a, b = link.get("source"), link.get("target")
            delay = (link.get("forward") or {}).get("delay_ms")
            if a is None or b is None or delay is None:
                continue
            graph.setdefault(a, {})[b] = float(delay)
            graph.setdefault(b, {})[a] = float(delay)

        def shortest(source: str) -> Dict[str, float]:
            import heapq
            best = {source: 0.0}
            queue = [(0.0, source)]
            seen = set()
            while queue:
                cost, here = heapq.heappop(queue)
                if here in seen:
                    continue
                seen.add(here)
                for peer, weight in graph.get(here, {}).items():
                    if peer in seen:
                        continue
                    step = cost + weight
                    if step < best.get(peer, float("inf")):
                        best[peer] = step
                        heapq.heappush(queue, (step, peer))
            return best

        miners = sorted(r["node_id"] for r in self.tables.get("nodes", [])
                        if r.get("role") == "miner")
        cache: Dict[str, Dict[str, float]] = {}
        for a in miners:
            site_a = sites.get(a)
            if not site_a:
                continue
            if site_a not in cache:
                cache[site_a] = shortest(site_a)
            for bnode in miners:
                if bnode <= a:
                    continue
                site_b = sites.get(bnode)
                if not site_b:
                    continue
                delay = 0.0 if site_a == site_b else cache[site_a].get(site_b)
                if delay is None:
                    continue
                self.add("topology_paths", validator_i=a, validator_j=bnode,
                         site_i=site_a, site_j=site_b, path_delay_ms=round(delay, 6))

    def collect_config(self) -> None:
        """Every parameter that governed the run, with where the value came from."""
        effective = self.manifest.get("effective_chain_params", {}) or {}
        for key in sorted(effective):
            self.add(
                "config",
                parameter=key,
                value=effective[key],
                source="params.dat (effective, read back from the chain)",
                note="",
            )
        derived = self.manifest.get("derived", {}) or {}
        for key in sorted(derived):
            self.add("config", parameter=key, value=derived[key], source="derived", note="")
        for key in ("seed", "chain_name", "final_height", "status", "treasury_address",
                    "rpc_transport", "measured_epochs"):
            if key in self.manifest:
                self.add("config", parameter=key, value=self.manifest[key],
                         source="run manifest", note="")
        self.add(
            "config",
            parameter="stability_margin",
            value=STABILITY_MARGIN,
            source="compile-time constant of the node",
            note="MC_WEIGHT_DEFAULT_STABILITY_MARGIN; not a chain parameter",
        )

    def collect_malicious_plan(self) -> None:
        """The resolved malicious plan, flattened into two tables.

        ``malicious_config`` carries the scalars, ``malicious_miners`` one row per miner —
        malicious and honest alike, because the honest miners are the matched comparison
        group phase 3's counterfactual needs. Both are written even when the experiment
        was off (every row then simply says ``is_malicious = false``), so the shape is
        constant across runs.
        """
        plan = self.manifest.get("malicious_plan") or {}
        for key in ("schema_version", "enabled", "seed", "target_action_rate",
                    "miner_count", "start_epoch", "stop_epoch", "selfwrite_stream",
                    "opportunities_per_epoch", "quota_share_source"):
            if key in plan:
                self.add("malicious_config", parameter=key, value=plan[key],
                         source="malicious_plan")
        for name, weight in (plan.get("actions") or {}).items():
            self.add("malicious_config", parameter="action_weight.%s" % name, value=weight,
                     source="malicious_plan")

        malicious = set(plan.get("malicious_miner_ids", []))
        addresses = plan.get("malicious_miner_addresses", {}) or {}
        shares = plan.get("quota_shares", {}) or {}
        rates = plan.get("per_miner_target_rate", {}) or {}
        manifest_addresses = self.manifest.get("addresses", {}) or {}
        for node_id in plan.get("all_miner_ids", []):
            self.add(
                "malicious_miners",
                node_id=node_id,
                address=addresses.get(node_id) or manifest_addresses.get(node_id, ""),
                is_malicious=node_id in malicious,
                quota_share=_num(shares.get(node_id)),
                target_rate=_num(rates.get(node_id)),
                quota_share_source=plan.get("quota_share_source", ""),
            )

    # -- snapshots ---------------------------------------------------------------------

    def collect_snapshot(self, event: Dict[str, Any]) -> None:
        payload = event.get("payload") or {}
        kind = payload.get("kind")
        data = payload.get("data")
        height = event.get("block_height")
        handler = getattr(self, "_snap_%s" % (kind or "").replace("-", "_"), None)
        if handler is not None:
            handler(payload, data, height)

    def _snap_listblocks(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        for block in data or []:
            block_height = block.get("height")
            if block_height is None or not self._once("blocks", block_height):
                continue
            self.add(
                "blocks",
                height=block_height,
                hash=block.get("hash", ""),
                miner_address=block.get("miner", ""),
                time=block.get("time", ""),
                txcount=block.get("txcount", ""),
                confirmations=block.get("confirmations", ""),
                epoch=self.epoch_of(block_height),
                in_setup=self.in_setup(block_height),
            )

    def _snap_getlastblockinfo(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        block_height = data.get("height")
        if block_height is None or not self._once("blocks", block_height):
            return
        self.add(
            "blocks",
            height=block_height,
            hash=data.get("hash", ""),
            miner_address=data.get("miner", ""),
            time=data.get("time", ""),
            txcount=data.get("txcount", ""),
            confirmations=data.get("confirmations", ""),
            epoch=self.epoch_of(block_height),
            in_setup=self.in_setup(block_height),
        )

    def _snap_wpoalistscores(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        round_height = payload.get("round_height", data.get("height"))
        if round_height is None or not self._once("round_scores", round_height):
            return
        for address, entry in (data.get("scores") or {}).items():
            entry = entry if isinstance(entry, dict) else {"score": entry}
            self.add(
                "round_scores",
                round_height=round_height,
                epoch=self.epoch_of(round_height),
                in_setup=self.in_setup(round_height),
                address=address,
                score=_num(entry.get("score")),
                weight=_num(entry.get("weight")),
                effective_weight=_num(entry.get("effective_weight")),
                eligible=entry.get("eligible", ""),
                seed=data.get("seed", ""),
                seed_source=data.get("seed_source", ""),
                dumping_function=data.get("dumping_function", ""),
                total_effective_weight=_num(data.get("total_effective_weight")),
                sample_height=height,
            )

    def _snap_wpoalistdelays(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        round_height = payload.get("round_height", data.get("height"))
        if round_height is None or not self._once("round_delays", round_height):
            return
        for address, entry in (data.get("delays") or {}).items():
            entry = entry if isinstance(entry, dict) else {"delay": entry}
            self.add(
                "round_delays",
                round_height=round_height,
                epoch=self.epoch_of(round_height),
                in_setup=self.in_setup(round_height),
                address=address,
                delay_s=_num(entry.get("delay")),
                score=_num(entry.get("score")),
                score_norm=_num(entry.get("score_norm")),
                effective_weight=_num(entry.get("effective_weight")),
                eligible=entry.get("eligible", ""),
                target_block_time=_num(data.get("target_block_time")),
                delta=_num(data.get("delta")),
                lambda_s=_num(data.get("lambda")),
                feedback_phi=_num(data.get("feedback")),
                seed=data.get("seed", ""),
                seed_source=data.get("seed_source", ""),
                dumping_function=data.get("dumping_function", ""),
                total_effective_weight=_num(data.get("total_effective_weight")),
                sample_height=height,
            )

    def _snap_wpoalisteffectiveweights(
        self, payload: Dict[str, Any], data: Any, height: Any
    ) -> None:
        if not isinstance(data, dict):
            return
        round_height = payload.get("round_height", data.get("height"))
        if round_height is None or not self._once("round_effective_weights", round_height):
            return
        for address, entry in (data.get("effective_weights") or {}).items():
            entry = entry if isinstance(entry, dict) else {"effective_weight": entry}
            self.add(
                "round_effective_weights",
                round_height=round_height,
                epoch=self.epoch_of(round_height),
                in_setup=self.in_setup(round_height),
                address=address,
                raw_weight=_num(entry.get("raw_weight")),
                dumping_function=entry.get("dumping_function", data.get("dumping_function", "")),
                effective_weight=_num(entry.get("effective_weight")),
                sample_height=height,
            )

    def _snap_wpoalistfinalweights(
        self, payload: Dict[str, Any], data: Any, height: Any
    ) -> None:
        if not isinstance(data, dict):
            return
        round_height = payload.get("round_height", data.get("height"))
        if round_height is None or not self._once("round_final_weights", round_height):
            return
        for address, entry in (data.get("final_weights") or {}).items():
            entry = entry if isinstance(entry, dict) else {}
            self.add(
                "round_final_weights",
                round_height=round_height,
                epoch=self.epoch_of(round_height),
                in_setup=self.in_setup(round_height),
                address=address,
                raw_weight=_num(entry.get("raw_weight")),
                malus=_num(entry.get("malus")),
                malus_factor=_num(entry.get("malus_factor")),
                weight_after_malus=_num(entry.get("weight_after_malus")),
                dumping_function=entry.get("dumping_function", data.get("dumping_function", "")),
                effective_weight_after_malus_and_dumping=_num(
                    entry.get("effective_weight_after_malus_and_dumping")
                ),
                eligible=entry.get("eligible", ""),
                malus_epoch=_num(data.get("malus_epoch")),
                sample_height=height,
            )

    def _snap_getallweights(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        # Address -> bare number here, unlike the wpoalist* families.
        for address, weight in (data.get("weights") or {}).items():
            self.add(
                "registry_weights",
                sample_height=height,
                epoch=self.epoch_of(height),
                address=address,
                weight=_num(weight),
                validators=_num(data.get("validators")),
                total=_num(data.get("total")),
            )

    def _snap_getallmalus(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        for address, entry in (data.get("validators") or {}).items():
            entry = entry if isinstance(entry, dict) else {}
            self.add(
                "malus",
                sample_height=height,
                epoch=_num(data.get("epoch")),
                address=address,
                malus=_num(entry.get("malus")),
                psi=_num(entry.get("psi")),
                weight=_num(entry.get("weight")),
                effective=_num(entry.get("effective")),
                excluded=entry.get("excluded", ""),
                epochs_to_clear=_num(entry.get("epochs_to_clear")),
                enabled=data.get("enabled", ""),
            )

    def _snap_weightlistcontributions(
        self, payload: Dict[str, Any], data: Any, height: Any
    ) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch", payload.get("epoch"))
        for address, entry in (data.get("contributions") or {}).items():
            if not self._once("epoch_contributions", (epoch, address)):
                continue
            entry = entry if isinstance(entry, dict) else {}
            self.add(
                "epoch_contributions",
                epoch=_num(epoch),
                address=address,
                cluster=entry.get("cluster", ""),
                esg_score=_num(entry.get("esg_score")),
                activity=_num(entry.get("activity")),
                kappa=_num(entry.get("kappa", data.get("kappa"))),
                contribution=_num(entry.get("contribution")),
                sample_height=height,
            )

    def _snap_weightlistclusterweights(
        self, payload: Dict[str, Any], data: Any, height: Any
    ) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch", payload.get("epoch"))
        for miner, entry in (data.get("cluster_weights") or {}).items():
            if not self._once("epoch_cluster_weights", (epoch, miner)):
                continue
            entry = entry if isinstance(entry, dict) else {}
            self.add(
                "epoch_cluster_weights",
                epoch=_num(entry.get("epoch", epoch)),
                miner=miner,
                miner_esg_score=_num(entry.get("miner_esg_score")),
                miner_activity=_num(entry.get("miner_activity")),
                companies=_num(entry.get("companies")),
                companies_contribution_sum=_num(entry.get("companies_contribution_sum")),
                kappa=_num(entry.get("kappa", data.get("kappa"))),
                raw_cluster_weight=_num(entry.get("raw_cluster_weight")),
                # JSON null at epoch 1: there is no previous rate, which is different from
                # a rate of zero and must not be flattened into one.
                previous_epoch_return_rate=_num(entry.get("previous_epoch_return_rate")),
                lambda_w=_num(entry.get("lambda_w", data.get("lambda_w"))),
                final_cluster_weight=_num(entry.get("final_cluster_weight")),
                published_weight=_num(entry.get("published_weight")),
                sample_height=height,
            )

    def _snap_weightlistreturns(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch", payload.get("epoch"))
        treasury = data.get("treasury_address", "")
        # Address -> bare number, unlike its sibling families.
        for miner, value in (data.get("returns") or {}).items():
            if not self._once("epoch_returns", (epoch, miner)):
                continue
            amount = value.get("returns") if isinstance(value, dict) else value
            self.add(
                "epoch_returns",
                epoch=_num(epoch),
                miner=miner,
                treasury_address=treasury,
                returns=_num(amount),
                sample_height=height,
            )

    def _snap_weightlistearnings(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch", payload.get("epoch"))
        for miner, entry in (data.get("earnings") or {}).items():
            if not self._once("epoch_earnings", (epoch, miner)):
                continue
            entry = entry if isinstance(entry, dict) else {}
            self.add(
                "epoch_earnings",
                epoch=_num(entry.get("epoch", epoch)),
                miner=miner,
                income=_num(entry.get("income")),
                expenses_gross=_num(entry.get("expenses_gross")),
                expenses_excl_return=_num(entry.get("expenses_excl_return")),
                earnings=_num(entry.get("earnings")),
                return_amount=_num(entry.get("return_amount")),
                balance=_num(entry.get("balance")),
                return_rate=_num(entry.get("return_rate")),
                sample_height=height,
            )

    def _snap_weightlistbalances(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch", payload.get("epoch"))
        # Address -> bare number again.
        for miner, value in (data.get("balances") or {}).items():
            if not self._once("epoch_balances", (epoch, miner)):
                continue
            balance = value.get("balance") if isinstance(value, dict) else value
            self.add(
                "epoch_balances",
                epoch=_num(epoch),
                miner=miner,
                balance=_num(balance),
                sample_height=height,
            )

    def _snap_weightverifyweights(
        self, payload: Dict[str, Any], data: Any, height: Any
    ) -> None:
        if not isinstance(data, dict):
            return
        epoch = data.get("epoch")
        # An array, unlike every other family.
        for entry in data.get("entries") or []:
            address = entry.get("address", "")
            if not self._once("verification", (epoch, address)):
                continue
            self.add(
                "verification",
                epoch=_num(epoch),
                verified=data.get("verified", ""),
                records=_num(data.get("records")),
                invalid=_num(data.get("invalid")),
                address=address,
                published=_num(entry.get("published")),
                published_epoch=_num(entry.get("published_epoch")),
                recomputed=_num(entry.get("recomputed")),
                verdict=entry.get("verdict", ""),
                sample_height=height,
            )

    def _snap_liststreamitems(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        stream = payload.get("stream", "")
        for item in data or []:
            txid = item.get("txid", "")
            key = (stream, txid)
            if key in self._seen_stream_items:
                continue
            self._seen_stream_items.add(txid and key or (stream, id(item)))
            publishers = item.get("publishers") or []
            keys = item.get("keys") or []
            confirm_height = item.get("blockheight", "")
            self.add(
                "stream_items",
                stream=stream,
                txid=txid,
                publisher=publishers[0] if publishers else "",
                key=keys[0] if keys else "",
                confirm_height=confirm_height,
                epoch=self.epoch_of(confirm_height) if confirm_height != "" else "",
                blocktime=item.get("blocktime", ""),
                confirmations=item.get("confirmations", ""),
                data_json=json.dumps(item.get("data"), separators=(",", ":"))[:2000],
                sample_height=height,
            )

    def _snap_listminers(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        for entry in data or []:
            self.add(
                "miners",
                sample_height=height,
                address=entry.get("address", ""),
                islocal=entry.get("islocal", ""),
                permitted=entry.get("permitted", ""),
                diversitywaitblocks=_num(entry.get("diversitywaitblocks")),
            )

    def _snap_listpermissions(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        for entry in data or []:
            entity = entry.get("for")
            if isinstance(entity, dict):
                entity_name = entity.get("name", entity.get("streamref", ""))
            else:
                entity_name = ""
            self.add(
                "permissions",
                sample_height=height,
                address=entry.get("address", ""),
                type=entry.get("type", ""),
                entity=entity_name,
                startblock=_num(entry.get("startblock")),
                endblock=_num(entry.get("endblock")),
            )

    def _snap_getpeerinfo(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        for entry in data or []:
            self.add(
                "peers",
                sample_height=height,
                peer_id=entry.get("id", ""),
                addr=entry.get("addr", ""),
                subver=entry.get("subver", ""),
                inbound=entry.get("inbound", ""),
                startingheight=_num(entry.get("startingheight")),
                synced_blocks=_num(entry.get("synced_blocks")),
            )

    def _snap_getinfo(self, payload: Dict[str, Any], data: Any, height: Any) -> None:
        if not isinstance(data, dict):
            return
        self.add(
            "node_state",
            sample_height=height,
            node_id=payload.get("node_id", ""),
            blocks=_num(data.get("blocks")),
            connections=_num(data.get("connections")),
            balance=_num(data.get("balance")),
        )

    # -- non-snapshot events -----------------------------------------------------------

    def collect_event(self, event: Dict[str, Any]) -> None:
        kind = event.get("event_type")
        payload = event.get("payload") or {}
        height = event.get("block_height")
        epoch = self.epoch_of(height)

        if kind == "snapshot":
            self.collect_snapshot(event)
        elif kind == "esg_set":
            self.add(
                "esg_events",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=epoch,
                ca_node_id=payload.get("ca_node_id", ""),
                target_node_id=payload.get("target_node_id", ""),
                target_role=payload.get("target_role", ""),
                target_address=payload.get("target_address", ""),
                esg_score=_num(payload.get("esg_score")),
                txid=payload.get("txid", ""),
            )
        elif kind == "membership_registered":
            self.add(
                "membership_events",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=epoch,
                node_id=payload.get("node_id", ""),
                node_address=event.get("node_address", ""),
                miner_node_id=payload.get("miner_node_id", ""),
                miner_address=payload.get("miner_address", ""),
                is_cluster_head=payload.get("is_cluster_head", ""),
                txid=payload.get("txid", ""),
            )
        elif kind == "traffic_tx_sent":
            self.add(
                "traffic_tx",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=epoch,
                node_id=event.get("node_id", ""),
                node_address=event.get("node_address", ""),
                declared_epoch=_num(payload.get("epoch")),
                sequence=_num(payload.get("sequence")),
                stream=payload.get("stream", ""),
                key=payload.get("key", ""),
                txid=payload.get("txid", ""),
                planned_this_epoch=_num(payload.get("planned_this_epoch")),
            )
        elif kind == "gas_return_sent":
            self.add(
                "gas_returns",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=epoch,
                node_id=event.get("node_id", ""),
                node_address=event.get("node_address", ""),
                declared_epoch=_num(payload.get("epoch")),
                sequence=_num(payload.get("sequence")),
                amount=_num(payload.get("amount")),
                treasury_address=payload.get("treasury_address", ""),
                balance_before=_num(payload.get("balance_before")),
                txid=payload.get("txid", ""),
                planned_this_epoch=_num(payload.get("planned_this_epoch")),
            )
        elif kind in ("gas_seeded", "gas_refuelled"):
            self.add(
                "gas_transfers",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=epoch,
                kind="seed" if kind == "gas_seeded" else "refuel",
                node_id=payload.get("node_id", ""),
                role=payload.get("role", ""),
                amount=_num(payload.get("amount")),
                balance_before=_num(payload.get("balance_before")),
                txid=payload.get("txid", ""),
            )
        elif kind == "epoch_plan":
            self.add(
                "epoch_plans",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                node_id=event.get("node_id", ""),
                node_role=event.get("node_role", ""),
                epoch=_num(payload.get("epoch")),
                planned_tx=_num(payload.get("planned_tx")),
                planned_returns=_num(payload.get("planned_returns")),
                mean_gap_s=_num(payload.get("mean_gap_s")),
            )
        elif kind == "malicious_opportunity":
            self.add(
                "malicious_opportunities",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=_num(payload.get("epoch")),
                miner=payload.get("miner", event.get("node_id", "")),
                node_address=event.get("node_address", ""),
                opportunity_index=_num(payload.get("opportunity_index")),
                opportunities_denominator=_num(payload.get("opportunities_denominator")),
                target_rate=_num(payload.get("target_rate")),
                deficit=_num(payload.get("deficit")),
                probability=_num(payload.get("probability")),
                draw=_num(payload.get("draw")),
                act=payload.get("act", ""),
                action=payload.get("action", ""),
                action_id=payload.get("action_id", ""),
                attempted_so_far=_num(payload.get("attempted_so_far")),
                realised_rate=_num(payload.get("realised_rate")),
            )
        elif kind == "malicious_action_sent":
            self.add(
                "malicious_actions",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=_num(payload.get("epoch")),
                miner=payload.get("miner", event.get("node_id", "")),
                node_address=event.get("node_address", ""),
                opportunity_index=_num(payload.get("opportunity_index")),
                action=payload.get("action", ""),
                action_id=payload.get("action_id", ""),
                stream=payload.get("stream", ""),
                txid=payload.get("txid", ""),
                declared_address=payload.get("declared_address", ""),
                declared_weight=_num(payload.get("declared_weight")),
                true_weight=_num(payload.get("true_weight")),
                target_epoch=_num(payload.get("target_epoch")),
            )
        elif kind == "malicious_action_confirmed":
            self.add(
                "malicious_confirmations",
                timestamp_utc=event.get("timestamp_utc", ""),
                block_height=height,
                epoch=_num(payload.get("epoch")),
                miner=payload.get("miner", event.get("node_id", "")),
                node_address=event.get("node_address", ""),
                action=payload.get("action", ""),
                action_id=payload.get("action_id", ""),
                stream=payload.get("stream", ""),
                txid=payload.get("txid", ""),
                confirm_height=_num(payload.get("confirm_height")),
                declared_address=payload.get("declared_address", ""),
                declared_weight=_num(payload.get("declared_weight")),
                target_epoch=_num(payload.get("target_epoch")),
            )
        elif kind == "malus_detection":
            self.add(
                "malus_detections",
                timestamp_utc=event.get("timestamp_utc", ""),
                detect_height=_num(payload.get("detect_height", height)),
                detect_epoch=_num(payload.get("detect_epoch")),
                verdict=payload.get("verdict", ""),
                kind=payload.get("kind", ""),
                accused_address=payload.get("accused_address", ""),
                offence_height=_num(payload.get("offence_height")),
                offence_epoch=_num(payload.get("offence_epoch")),
                evidence_txid=payload.get("evidence_txid", ""),
                stream=payload.get("stream", ""),
                report_txid=payload.get("report_txid", ""),
                reason=str(payload.get("reason") or "")[:300],
            )
        elif kind == "rpc_error":
            context = {
                k: v
                for k, v in payload.items()
                if k not in ("method", "error", "error_class", "code")
            }
            self.add(
                "rpc_errors",
                timestamp_utc=event.get("timestamp_utc", ""),
                node_id=event.get("node_id", ""),
                node_role=event.get("node_role", ""),
                block_height=height,
                method=payload.get("method", ""),
                code=payload.get("code", ""),
                error=str(payload.get("error", ""))[:300],
                context_json=json.dumps(context, separators=(",", ":"))[:600],
            )

    # -- output ------------------------------------------------------------------------

    def write(self, out_dir: Path) -> Dict[str, int]:
        out_dir.mkdir(parents=True, exist_ok=True)
        counts: Dict[str, int] = {}
        for name, columns in COLUMNS.items():
            rows = self.tables[name]
            counts[name] = len(rows)
            with open(out_dir / ("%s.csv" % name), "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=columns, extrasaction="ignore")
                writer.writeheader()
                for row in rows:
                    writer.writerow({c: row.get(c, "") for c in columns})
        return counts


def collect(run_dir: Path, profile_path: Optional[Path] = None) -> Dict[str, Any]:
    """Run phase 1 over a finished run directory."""
    manifest_path = run_dir / "manifest.json"
    if not manifest_path.is_file():
        raise Phase1Error(
            "no manifest.json in %s: either the run never started or this is not a run "
            "directory" % run_dir
        )
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    profile = load_profile(profile_path or manifest["profile_path"])

    collector = Collector(profile, manifest)
    collector.collect_nodes()
    # After the node table: the paths are between validators, so it needs their roles.
    collector.collect_topology_paths(run_dir)
    collector.collect_config()
    collector.collect_malicious_plan()
    for event in read_events(run_dir):
        collector.collect_event(event)

    out_dir = run_dir / "analysis" / "phase1"
    counts = collector.write(out_dir)

    blocks = collector.tables["blocks"]
    heights = [int(b["height"]) for b in blocks if b.get("height") not in ("", None)]
    epochs_seen = sorted({int(b["epoch"]) for b in blocks if b.get("epoch") not in ("", None)})
    out_manifest = {
        "phase": 1,
        "run_dir": str(run_dir),
        "profile_path": str(profile.path),
        "chain_name": manifest.get("chain_name"),
        "seed": manifest.get("seed"),
        "epoch_length": collector.epoch_length,
        "setup_first_blocks": collector.setup_blocks,
        "stability_margin": STABILITY_MARGIN,
        "final_height": max(heights) if heights else 0,
        "n_blocks": len(heights),
        "epochs_seen": epochs_seen,
        "last_buried_epoch": profile.last_buried_epoch(max(heights) if heights else 0),
        "treasury_address": manifest.get("treasury_address"),
        "clusters": manifest.get("clusters", {}),
        "addresses": manifest.get("addresses", {}),
        "run_status": manifest.get("status"),
        "row_counts": counts,
    }
    # Headline facts of the malicious experiment, lifted from the run's resolved plan so
    # phase 3 can read the target rate and the selection without re-opening the plan.
    plan = manifest.get("malicious_plan") or {}
    out_manifest.update(
        {
            "malicious_enabled": bool(plan.get("enabled")),
            "malicious_target_action_rate": plan.get("target_action_rate"),
            "malicious_miner_ids": plan.get("malicious_miner_ids", []),
            "malicious_seed": plan.get("seed"),
            "malicious_actions": plan.get("actions", {}),
        }
    )
    (out_dir / "manifest.json").write_text(
        json.dumps(out_manifest, indent=2, default=str), encoding="utf-8"
    )
    return out_manifest


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", default=None, help="profile YAML (default: from the manifest)")
    parser.add_argument("--run-dir", required=True)
    args = parser.parse_args(argv)

    try:
        manifest = collect(Path(args.run_dir), Path(args.config) if args.config else None)
    except (Phase1Error, ConfigError) as exc:
        print("[phase1] %s" % exc, file=sys.stderr)
        return 1

    print("[phase1] %d blocks, epochs %s, final height %d"
          % (manifest["n_blocks"],
             "%s-%s" % (manifest["epochs_seen"][0], manifest["epochs_seen"][-1])
             if manifest["epochs_seen"] else "none",
             manifest["final_height"]))
    for name, count in sorted(manifest["row_counts"].items()):
        if count:
            print("    %-26s %6d rows" % (name, count))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
