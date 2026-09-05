#!/usr/bin/env python3
"""Phase 1 - raw collection. One directory per (run, area): <out>/<run>/<area>/phase1/.

Nothing is aggregated and nothing is tested here. Every row is traceable to a
log line (source_file / source_line) or to an on-chain record (txid). The only
non-raw columns are the height->epoch label and the in-setup flag, which are
pure functions of the sealed configuration and are needed by every later
filter; they are recomputed in phase 2 anyway through the same function.

Inputs (read-only):  esperimenti/<run>/<area>/{run/metrics, run/data, shadow.yaml}
                     config/levels/<area>.json, the .gml referenced by shadow.yaml
Outputs:             config.csv, manifest.json and the tables listed in TABLES.

    python3 tools/pipeline/phase1_collect.py --root esperimenti --out risultati
"""

import argparse
import json
import logging
import sys
from collections import Counter, OrderedDict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from pipeline import common as C  # noqa: E402

LOG = logging.getLogger("pipeline.phase1")

TABLES = [
    "blocks", "sortition_scores", "phi", "verify_lines", "sortition_ok_blocks", "rejects",
    "weight_engine_log", "malus_log", "weights_stream", "esg_stream", "membership_stream",
    "malus_stream", "traffic", "gas_transfers", "gas_balances", "reconciliation",
    "verify_snapshot", "node_state", "unconfirmed_txids", "topology_latency", "topology_edges",
    "hosts",
]

# Column order of every table, fixed so that an empty table still has a header.
COLUMNS = {
    "blocks": ["height", "hash", "miner_address", "miner_host", "time", "txcount",
               "confirmations", "epoch", "in_setup"],
    "sortition_scores": ["height", "epoch", "in_setup", "host", "address", "score_raw",
                         "delay_logged_s", "start_in_s", "log_timestamp", "duplicate_index",
                         "source_file", "source_line"],
    "phi": ["tip_height", "round_height", "host", "window", "mean_spacing_s", "tblock_s",
            "phi_s", "phi_bound_s", "log_timestamp", "n_occurrences", "source_file",
            "source_line"],
    "verify_lines": ["height", "signer_address", "signer_host", "score", "delay_floor_s",
                     "ntime", "parent_ntime", "n_hosts_seen", "hosts_seen", "n_lines",
                     "first_log_timestamp", "first_source_file", "first_source_line"],
    "sortition_ok_blocks": ["height", "block_hash", "proposer_address", "proposer_host",
                            "n_hosts_seen", "hosts_seen", "n_lines", "first_log_timestamp",
                            "first_source_file", "first_source_line"],
    "rejects": ["height", "block_hash", "reason", "host", "log_timestamp", "source_file",
                "source_line"],
    "weight_engine_log": ["kind", "epoch", "height", "weight", "address", "host",
                          "checked", "total", "other_epoch", "log_timestamp", "source_file",
                          "source_line"],
    "malus_log": ["height", "epoch", "M", "psi", "w", "w_eff", "host", "log_timestamp",
                  "source_file", "source_line"],
    "weights_stream": ["txid", "publisher_address", "publisher_host", "node_address",
                       "node_host", "weight", "epoch_tag", "height_payload",
                       "timestamp_payload", "blocktime", "confirmations", "confirm_height",
                       "confirm_height_source"],
    "esg_stream": ["txid", "publisher_address", "publisher_host", "node_address", "node_host",
                   "esg", "blocktime", "confirm_height"],
    "membership_stream": ["txid", "publisher_address", "publisher_host", "node_address",
                          "node_host", "miner_address", "miner_host", "blocktime",
                          "confirm_height"],
    "malus_stream": ["txid", "publisher_address", "node_address", "kind", "points",
                     "height_payload", "confirm_height", "raw_json"],
    "traffic": ["send_height", "host", "address", "seq", "txid", "error", "confirm_height"],
    "gas_transfers": ["send_height", "kind", "to_host", "amount_gas"],
    "gas_balances": ["sample_height", "host", "balance_gas"],
    "reconciliation": ["send_height", "epoch_harness", "miner_host", "balance_before_gas",
                       "sent_gas", "assumed_confirm_height"],
    "verify_snapshot": ["epoch", "verified", "records", "invalid", "address", "host",
                        "published", "published_epoch", "recomputed", "verdict"],
    "node_state": ["host", "height", "besthash", "hash_at_reference", "peers", "balance_gas"],
    "unconfirmed_txids": ["txid", "hosts_seen"],
    "topology_latency": ["host_a", "host_b", "one_way_ms", "rtt_ms", "hops"],
    "topology_edges": ["source", "target", "latency_ms", "jitter", "packet_loss"],
    "hosts": ["host", "address", "role", "cluster_head_host", "esg", "gml_node_id", "label",
              "lat", "lon"],
}

# params.dat key -> (thesis symbol, prompt section)
PARAM_SYMBOLS = {
    "target-block-time": "T_block", "wpoa-sortition-delta": "delta",
    "wpoa-sortition-lambda": "lambda (delay feedback)", "wpoa-randao-lookback": "k (RANDAO)",
    "dump-function": "g(.)", "enable-wpoa-malus": "malus on/off", "wpoa-malus-mu": "mu",
    "wpoa-malus-max": "M_max", "wpoa-malus-equiv-points": "p(Equiv)",
    "wpoa-malus-delay-points": "p(Delay)", "wpoa-malus-selfwrite-points": "p(SelfWrite)",
    "wpoa-malus-badweight-points": "p(BadWeight)", "weight-epoch-length": "L",
    "weight-kappa": "kappa", "weight-alpha": "alpha", "weight-lambda": "lambda_w",
    "weight-treasury-address": "treasury", "setup-first-blocks": "setup blocks",
    "mining-diversity": "spacing (mining-diversity)", "mining-turnover": "mining-turnover",
    "native-currency-multiple": "GAS raw units", "initial-block-reward": "block reward",
    "first-block-reward": "first block reward", "minimum-relay-fee": "relay fee",
}

LOG_NEEDLES = ("wPoA-sortition height=", "feedback height=", "verify OK height=",
               "sortition OK block", "REJECT block", "[WeightEngine] epoch",
               "[wpoa-malus] height=")


def _rel(path, run):
    try:
        return str(Path(path).relative_to(run["path"]))
    except ValueError:
        return str(path)


def scan_debug_logs(run, meta, host_by_addr):
    """Stream every host's debug.log once; returns the log-derived raw tables."""
    setup, L = meta["setup_blocks"], meta["epoch_len"]
    scores, rejects, we_log, malus_log = [], [], [], []
    phi = OrderedDict()        # (host, tip) -> row
    verify = OrderedDict()     # (height, signer, ntime, parent, delay) -> row
    sort_ok = OrderedDict()    # (height, hash) -> row
    dup = Counter()
    for host, path in C.find_debug_logs(run["data"]):
        rel = _rel(path, run)
        for no, ts, line in C.iter_log_lines(path, LOG_NEEDLES):
            if "wPoA-sortition height=" in line:
                m = C.SCORE_RE.search(line)
                if not m:
                    continue
                h = int(m.group(1))
                key = (host, h)
                dup[key] += 1
                scores.append({
                    "height": h, "epoch": C.epoch_of(h, L), "in_setup": int(h <= setup),
                    "host": host, "address": m.group(5), "score_raw": m.group(2),
                    "delay_logged_s": m.group(3), "start_in_s": m.group(4),
                    "log_timestamp": ts, "duplicate_index": dup[key] - 1,
                    "source_file": rel, "source_line": no})
            elif "feedback height=" in line:
                m = C.PHI_RE.search(line)
                if not m:
                    continue
                tip = int(m.group(1))
                key = (host, tip)
                if key in phi:
                    phi[key]["n_occurrences"] += 1
                    continue
                phi[key] = {
                    "tip_height": tip, "round_height": tip + 1, "host": host,
                    "window": int(m.group(2)), "mean_spacing_s": m.group(3),
                    "tblock_s": m.group(4), "phi_s": m.group(5), "phi_bound_s": m.group(6),
                    "log_timestamp": ts, "n_occurrences": 1, "source_file": rel,
                    "source_line": no}
            elif "verify OK height=" in line:
                m = C.VERIFY_OK_RE.search(line)
                if not m:
                    continue
                key = (int(m.group(1)), m.group(2), int(m.group(5)), int(m.group(6)),
                       int(m.group(4)))
                if key in verify:
                    verify[key]["n_lines"] += 1
                    if host not in verify[key]["_hosts"]:
                        verify[key]["_hosts"].append(host)
                    continue
                verify[key] = {
                    "height": key[0], "signer_address": key[1],
                    "signer_host": host_by_addr.get(key[1], ""), "score": m.group(3),
                    "delay_floor_s": key[4], "ntime": key[2], "parent_ntime": key[3],
                    "_hosts": [host], "n_lines": 1, "first_log_timestamp": ts,
                    "first_source_file": rel, "first_source_line": no}
            elif "sortition OK block" in line:
                m = C.SORT_OK_RE.search(line)
                if not m:
                    continue
                key = (int(m.group(2)), m.group(1))
                if key in sort_ok:
                    sort_ok[key]["n_lines"] += 1
                    if host not in sort_ok[key]["_hosts"]:
                        sort_ok[key]["_hosts"].append(host)
                    continue
                sort_ok[key] = {
                    "height": key[0], "block_hash": key[1], "proposer_address": m.group(3),
                    "proposer_host": host_by_addr.get(m.group(3), ""), "_hosts": [host],
                    "n_lines": 1, "first_log_timestamp": ts, "first_source_file": rel,
                    "first_source_line": no}
            elif "REJECT block" in line:
                m = C.REJECT_RE.search(line)
                if not m:
                    continue
                rejects.append({"height": int(m.group(2)), "block_hash": m.group(1),
                                "reason": m.group(3).strip(), "host": host,
                                "log_timestamp": ts, "source_file": rel, "source_line": no})
            elif "[WeightEngine] epoch" in line:
                m = C.WE_PUB_RE.search(line)
                if m:
                    we_log.append({"kind": "publication", "epoch": int(m.group(1)),
                                   "height": int(m.group(2)), "weight": int(m.group(3)),
                                   "address": m.group(4), "host": host, "checked": "",
                                   "total": "", "other_epoch": "", "log_timestamp": ts,
                                   "source_file": rel, "source_line": no})
                    continue
                m = C.WE_OK_RE.search(line)
                if m:
                    we_log.append({"kind": "verification_ok", "epoch": int(m.group(1)),
                                   "height": "", "weight": "", "address": "", "host": host,
                                   "checked": int(m.group(2)), "total": int(m.group(3)),
                                   "other_epoch": int(m.group(4)), "log_timestamp": ts,
                                   "source_file": rel, "source_line": no})
                    continue
                m = C.WE_FAIL_RE.search(line)
                if m:
                    we_log.append({"kind": "verification_failed", "epoch": int(m.group(1)),
                                   "height": "", "weight": "", "address": "", "host": host,
                                   "checked": int(m.group(2)), "total": int(m.group(3)),
                                   "other_epoch": "", "log_timestamp": ts,
                                   "source_file": rel, "source_line": no})
                    continue
                m = C.WE_NOTVER_RE.search(line)
                if m:
                    we_log.append({"kind": "not_verified", "epoch": int(m.group(1)),
                                   "height": "", "weight": "", "address": "", "host": host,
                                   "checked": "", "total": "", "other_epoch": "",
                                   "log_timestamp": ts, "source_file": rel,
                                   "source_line": no})
            elif "[wpoa-malus] height=" in line:
                m = C.MALUS_APPLY_RE.search(line)
                if not m:
                    continue
                malus_log.append({"height": int(m.group(1)), "epoch": int(m.group(2)),
                                  "M": m.group(3), "psi": m.group(4), "w": m.group(5),
                                  "w_eff": m.group(6), "host": host, "log_timestamp": ts,
                                  "source_file": rel, "source_line": no})
    scores.sort(key=lambda r: (r["height"], r["host"], r["duplicate_index"]))
    for table in (verify, sort_ok):
        for row in table.values():
            hosts = row.pop("_hosts")
            row["n_hosts_seen"] = len(hosts)
            row["hosts_seen"] = " ".join(sorted(hosts))
    return {
        "sortition_scores": scores,
        "phi": sorted(phi.values(), key=lambda r: (r["tip_height"], r["host"])),
        "verify_lines": sorted(verify.values(), key=lambda r: (r["height"], r["ntime"])),
        "sortition_ok_blocks": sorted(sort_ok.values(), key=lambda r: (r["height"], r["block_hash"])),
        "rejects": rejects, "weight_engine_log": we_log, "malus_log": malus_log,
    }


def stream_items(run, name, txindex):
    """Generic reader of a liststreamitems snapshot: (item, payload, confirm_height)."""
    for item in (C.rpc_result(run["metrics"] / name) or []):
        if not isinstance(item, dict):
            continue
        payload = ((item.get("data") or {}).get("json")) or {}
        yield item, payload, C.tx_height(txindex, item.get("txid", ""))


def collect_metrics(run, meta, maps, txindex, unconfirmed):
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    L, setup = meta["epoch_len"], meta["setup_blocks"]
    out = {}

    blocks = C.rpc_result(run["metrics"] / "blocks.json") or []
    rows = []
    for b in sorted((b for b in blocks if isinstance(b, dict) and "height" in b),
                    key=lambda b: b["height"]):
        rows.append({"height": b["height"], "hash": b.get("hash", ""),
                     "miner_address": b.get("miner", ""),
                     "miner_host": host_by_addr.get(b.get("miner", ""), ""),
                     "time": b.get("time", ""), "txcount": b.get("txcount", ""),
                     "confirmations": b.get("confirmations", ""),
                     "epoch": C.epoch_of(b["height"], L), "in_setup": int(b["height"] <= setup)})
    out["blocks"] = rows

    rows = []
    for item, p, hc in stream_items(run, "weights.json", txindex):
        pub = (item.get("publishers") or [""])[0]
        rows.append({"txid": item.get("txid", ""), "publisher_address": pub,
                     "publisher_host": host_by_addr.get(pub, ""),
                     "node_address": p.get("node_address", ""),
                     "node_host": host_by_addr.get(p.get("node_address", ""), ""),
                     "weight": p.get("weight", ""), "epoch_tag": p.get("epoch", ""),
                     "height_payload": p.get("height", ""),
                     "timestamp_payload": p.get("timestamp", ""),
                     "blocktime": item.get("blocktime", ""),
                     "confirmations": item.get("confirmations", ""),
                     "confirm_height": hc if hc is not None else "",
                     "confirm_height_source": "txs.log UpdateTx" if hc is not None else "not found in txs.log"})
    rows.sort(key=lambda r: (r["confirm_height"] if r["confirm_height"] != "" else 10 ** 9,
                             r["epoch_tag"] or 0))
    out["weights_stream"] = rows

    rows = []
    for item, p, hc in stream_items(run, "esg.json", txindex):
        pub = (item.get("publishers") or [""])[0]
        addr = p.get("node_address") or (item.get("keys") or [""])[0]
        rows.append({"txid": item.get("txid", ""), "publisher_address": pub,
                     "publisher_host": host_by_addr.get(pub, ""), "node_address": addr,
                     "node_host": host_by_addr.get(addr, ""), "esg": p.get("esg", ""),
                     "blocktime": item.get("blocktime", ""),
                     "confirm_height": hc if hc is not None else ""})
    out["esg_stream"] = rows

    rows = []
    for item, p, hc in stream_items(run, "membership.json", txindex):
        pub = (item.get("publishers") or [""])[0]
        rows.append({"txid": item.get("txid", ""), "publisher_address": pub,
                     "publisher_host": host_by_addr.get(pub, ""),
                     "node_address": p.get("node_address", ""),
                     "node_host": host_by_addr.get(p.get("node_address", ""), ""),
                     "miner_address": p.get("miner_address", ""),
                     "miner_host": host_by_addr.get(p.get("miner_address", ""), ""),
                     "blocktime": item.get("blocktime", ""),
                     "confirm_height": hc if hc is not None else ""})
    out["membership_stream"] = rows

    rows = []
    for item, p, hc in stream_items(run, "malus.json", txindex):
        pub = (item.get("publishers") or [""])[0]
        rows.append({"txid": item.get("txid", ""), "publisher_address": pub,
                     "node_address": p.get("node_address", p.get("address", "")),
                     "kind": p.get("kind", p.get("type", "")),
                     "points": p.get("points", ""), "height_payload": p.get("height", ""),
                     "confirm_height": hc if hc is not None else "",
                     "raw_json": json.dumps(p, sort_keys=True)})
    out["malus_stream"] = rows

    rows = []
    _h, csv_rows = C.read_csv_rows(run["metrics"] / "traffic.csv",
                                   expected_cols=["height", "host", "seq", "txid_or_error"])
    for r in csv_rows:
        if len(r) < 4:
            continue
        txid = r[3].strip()
        is_tx = len(txid) == 64 and all(c in "0123456789abcdef" for c in txid)
        hc = C.tx_height(txindex, txid) if is_tx else None
        rows.append({"send_height": C.as_int(r[0], ""), "host": r[1].strip(),
                     "address": addr_by_host.get(r[1].strip(), ""), "seq": C.as_int(r[2], ""),
                     "txid": txid if is_tx else "", "error": "" if is_tx else txid,
                     "confirm_height": hc if hc is not None else ""})
    out["traffic"] = rows

    rows = []
    _h, csv_rows = C.read_csv_rows(run["metrics"] / "gas_transfers.csv",
                                   expected_cols=["height", "tipo", "host", "importo"],
                                   has_header=False)
    for r in csv_rows:
        if len(r) < 4:
            continue
        rows.append({"send_height": C.as_int(r[0], ""), "kind": r[1].strip(),
                     "to_host": r[2].strip(), "amount_gas": C.as_float(r[3], "")})
    out["gas_transfers"] = rows

    rows = []
    _h, csv_rows = C.read_csv_rows(run["metrics"] / "gas_balances.csv",
                                   expected_cols=["height", "host", "balance"])
    for r in csv_rows:
        if len(r) < 3:
            continue
        rows.append({"sample_height": C.as_int(r[0], ""), "host": r[1].strip(),
                     "balance_gas": C.as_float(r[2], "")})
    out["gas_balances"] = rows

    rows = []
    _h, csv_rows = C.read_csv_rows(run["metrics"] / "reconciliation.csv",
                                   expected_cols=["height", "epoch", "miner", "balance", "sent"])
    for r in csv_rows:
        if len(r) < 5:
            continue
        hs = C.as_int(r[0])
        rows.append({"send_height": hs if hs is not None else "", "epoch_harness": C.as_int(r[1], ""),
                     "miner_host": r[2].strip(), "balance_before_gas": C.as_float(r[3], ""),
                     "sent_gas": C.as_float(r[4], ""),
                     "assumed_confirm_height": (hs + 1) if hs is not None else ""})
    out["reconciliation"] = rows

    rows = []
    v = C.rpc_result(run["metrics"] / "verify.json") or {}
    if isinstance(v, dict):
        for e in v.get("entries", []) or []:
            rows.append({"epoch": v.get("epoch", ""), "verified": v.get("verified", ""),
                         "records": v.get("records", ""), "invalid": v.get("invalid", ""),
                         "address": e.get("address", ""),
                         "host": host_by_addr.get(e.get("address", ""), ""),
                         "published": e.get("published", ""),
                         "published_epoch": e.get("published_epoch", ""),
                         "recomputed": e.get("recomputed", ""), "verdict": e.get("verdict", "")})
    out["verify_snapshot"] = rows

    rows = []
    header, csv_rows = C.read_csv_rows(run["metrics"] / "node_state.csv", has_header=True)
    for r in csv_rows:
        if len(r) < 6:
            continue
        rows.append({"host": r[0].strip(), "height": C.as_int(r[1], ""), "besthash": r[2].strip(),
                     "hash_at_reference": r[3].strip(), "peers": C.as_int(r[4], ""),
                     "balance_gas": C.as_float(r[5], "")})
    out["node_state"] = rows
    out["node_state_header"] = header

    out["unconfirmed_txids"] = [{"txid": t, "hosts_seen": " ".join(h)} for t, h in unconfirmed]
    return out


def collect_topology(run, cfg_root, yaml_info):
    """Hosts table (roles, cluster, coordinates) and latency matrix from the .gml."""
    level_json = Path(cfg_root) / "levels" / ("%s.json" % run["livello"])
    gml = yaml_info.get("gml_path") or ""
    if gml and not Path(gml).is_file():
        # the yaml stores the absolute path of the machine that ran the campaign:
        # fall back to the sibling <area>/ directory of the shadow tree
        alt = Path(cfg_root).parent / run["livello"] / Path(gml).name
        gml = str(alt) if alt.is_file() else gml
    lat_rows, extra = C.topology_latency(gml, level_json)
    edges = extra.get("edges", []) if isinstance(extra, dict) else []
    note = extra if isinstance(extra, str) else ""
    level = C.read_json(level_json) or {}
    nodes = {n["host"]: n for n in level.get("nodes", []) if "host" in n}
    return lat_rows, edges, nodes, note, gml, str(level_json)


def build_config_rows(run, meta, params_host, startup, yaml_info, final_height, rtt_max_miners, rtt_max_all, gml, level_json):
    """Long table: one row per parameter with its source (prompt section 4.3)."""
    rows = []

    def add(param, value, source, symbol="", note=""):
        rows.append({"parameter": param, "value": value, "source": source,
                     "thesis_symbol": symbol, "note": note})

    add("experiment_id", run["run_dir"], "directory name", "", "the sealed configuration; tbt confirmed by params.dat")
    add("area", run["livello"], "directory name", "geographic level")
    add("replication_id", 1, "campaign design", "", "no replicas in the archived campaign: single seed")
    for key in C.PARAM_KEYS:
        val = meta.get(key.replace("-", "_"), "")
        add(key, val, "params.dat (%s)" % params_host if val != "" else "params.dat: absent",
            PARAM_SYMBOLS.get(key, ""))
    # start-up lines of the node: the parameters the binary actually applied
    su_map = {"sortition_delta": "wpoa-sortition-delta", "sortition_lambda": "wpoa-sortition-lambda",
              "dump_function": "dump-function", "randao_lookback": "wpoa-randao-lookback",
              "malus_mu": "wpoa-malus-mu", "malus_max": "wpoa-malus-max",
              "malus_equiv_points": "wpoa-malus-equiv-points",
              "malus_delay_points": "wpoa-malus-delay-points",
              "malus_selfwrite_points": "wpoa-malus-selfwrite-points",
              "malus_badweight_points": "wpoa-malus-badweight-points",
              "weight_epoch_length": "weight-epoch-length", "weight_kappa": "weight-kappa",
              "weight_alpha": "weight-alpha", "weight_lambda": "weight-lambda",
              "weight_treasury_address": "weight-treasury-address"}
    for k, pkey in su_map.items():
        if k in startup:
            pval = str(meta.get(pkey.replace("-", "_"), ""))
            same = pval == startup[k] or C.as_float(pval) == C.as_float(startup[k])
            note = "" if same else "DIFFERS from params.dat value '%s'" % pval
            if pval in ("[null]", "") and startup[k] != "":
                note = "params.dat has '%s': the start-up line is the effective value (D4)" % (pval or "absent")
            add(pkey + " (startup)", startup[k], "debug.log start-up line", PARAM_SYMBOLS.get(pkey, ""), note)
    add("setupblocks (getinfo)", meta.get("setupblocks_getinfo", ""), "admin_getinfo.json", "setup blocks")
    add("chainname", meta.get("chainname_getinfo", ""), "admin_getinfo.json")
    add("protocolversion", meta.get("protocolversion", ""), "admin_getinfo.json")
    add("final_height", final_height, "metrics/final_height.txt", "run length")
    add("shadow_general_seed", yaml_info.get("general_seed", ""), "shadow.yaml general.seed")
    env = yaml_info.get("env", {})
    add("poesia_rng_seed", env.get("POESIA_RNG_SEED", ""), "shadow.yaml env POESIA_RNG_SEED")
    add("poesia_epochlen", env.get("POESIA_EPOCHLEN", ""), "shadow.yaml env POESIA_EPOCHLEN")
    add("topology_gml", gml, "shadow.yaml network.graph.file.path")
    add("topology_level_json", level_json, "config/levels")
    add("rtt_max_between_miners_ms", rtt_max_miners, "shortest path on the .gml (deterministic; jitter 0 us)")
    add("rtt_max_all_hosts_ms", rtt_max_all, "shortest path on the .gml (deterministic; jitter 0 us)")
    add("stability_margin_blocks", C.STABILITY_MARGIN, "C++ constant MC_WEIGHT_DEFAULT_STABILITY_MARGIN")
    return rows


def collect_run(run, out_root, cfg_root):
    meta = C.extract_meta(run)
    maps = C.extract_host_maps(run)
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    out_dir = Path(out_root) / run["run_dir"] / run["livello"] / "phase1"
    out_dir.mkdir(parents=True, exist_ok=True)
    warnings = []

    txindex, unconfirmed = C.build_tx_index(run)
    tables = collect_metrics(run, meta, maps, txindex, unconfirmed)
    tables.update(scan_debug_logs(run, meta, host_by_addr))

    yaml_info = C.parse_shadow_yaml(run["path"] / "shadow.yaml")
    lat_rows, edges, level_nodes, topo_note, gml, level_json = collect_topology(run, cfg_root, yaml_info)
    tables["topology_latency"] = lat_rows
    tables["topology_edges"] = edges
    if topo_note:
        warnings.append(topo_note)

    hosts = []
    all_hosts = sorted(set(addr_by_host) | set(level_nodes) | {h for h, _p in C.find_debug_logs(run["data"])})
    for h in all_hosts:
        n = level_nodes.get(h, {})
        role = n.get("role", "")
        if not role:
            role = "miner" if h.startswith("m") else ("company" if h.startswith("c") and h != "ca" else h)
        hosts.append({"host": h, "address": addr_by_host.get(h, ""), "role": role,
                      "cluster_head_host": cluster_by_host.get(h, ""), "esg": esg_by_host.get(h, ""),
                      "gml_node_id": n.get("id", ""), "label": n.get("label", ""),
                      "lat": n.get("lat", ""), "lon": n.get("lon", "")})
    tables["hosts"] = hosts
    miners = [h["host"] for h in hosts if h["role"] == "miner"]
    rtt_max_miners = max([r["rtt_ms"] for r in lat_rows if r["host_a"] in miners and r["host_b"] in miners] or [""]) if lat_rows else ""
    rtt_max_all = max([r["rtt_ms"] for r in lat_rows] or [""]) if lat_rows else ""

    params_host = meta.get("params_da_host", "?")
    startup = {}
    for host, path in C.find_debug_logs(run["data"]):
        if host in miners:
            startup = C.parse_startup_params(path)
            startup_host = host
            if startup:
                break
    final_height = ""
    fh = run["metrics"] / "final_height.txt"
    if fh.is_file():
        final_height = C.as_int(fh.read_text().strip(), "")
    if final_height == "" and tables["blocks"]:
        final_height = tables["blocks"][-1]["height"]
        warnings.append("final_height.txt missing: final height taken from blocks.json")

    config_rows = build_config_rows(run, meta, params_host, startup, yaml_info, final_height,
                                    rtt_max_miners, rtt_max_all, gml, level_json)
    C.write_csv(out_dir / "config.csv", config_rows,
                ["parameter", "value", "source", "thesis_symbol", "note"])

    counts = {}
    for name in TABLES:
        counts[name] = C.write_csv(out_dir / (name + ".csv"), tables.get(name, []), COLUMNS[name])

    # consistency notes that are still raw facts (no derivation): duplicates and coverage
    dup_scores = sum(1 for r in tables["sortition_scores"] if r["duplicate_index"])
    if dup_scores:
        warnings.append("%d sortition score lines are re-logged for the same (host, height)" % dup_scores)
    if not tables["sortition_scores"]:
        warnings.append("no sortition score lines found in debug.log")
    if meta.get("tbt_mismatch"):
        warnings.append("target-block-time in params.dat differs from the directory name")
    if not meta.get("params_trovato"):
        warnings.append("params.dat not found")
    if not startup:
        warnings.append("start-up lines not found in the miners' debug.log")

    L = meta["epoch_len"]
    epochs = []
    if final_height != "":
        for e in range(1, C.epoch_of(final_height, L) + 1):
            lo, hi = C.epoch_bounds(e, L)
            epochs.append({"epoch": e, "start_height": lo, "end_height": hi,
                           "buried": bool(C.epoch_buried(e, L, final_height)),
                           "fully_measured": lo > meta["setup_blocks"],
                           "partially_in_setup": lo <= meta["setup_blocks"] < hi})

    manifest = OrderedDict([
        ("experiment_id", run["run_dir"]), ("area", run["livello"]), ("replication_id", 1),
        ("run_id", run["run_id"]), ("source_path", str(run["path"])),
        ("target_block_time", meta["tbt"]), ("weight_epoch_length", L),
        ("setup_blocks", meta["setup_blocks"]), ("final_height", final_height),
        ("dump_function", meta.get("dump_function", "")),
        ("malus_enabled", meta.get("enable_wpoa_malus", "")),
        ("params", {k.replace("-", "_"): meta.get(k.replace("-", "_"), "") for k in C.PARAM_KEYS}),
        ("params_source_host", params_host),
        ("startup_params", startup), ("startup_params_host", startup_host if startup else ""),
        ("shadow", {"general_seed": yaml_info.get("general_seed", ""),
                    "poesia_rng_seed": yaml_info.get("env", {}).get("POESIA_RNG_SEED", ""),
                    "gml": gml, "level_json": level_json,
                    "rtt_max_between_miners_ms": rtt_max_miners,
                    "rtt_max_all_hosts_ms": rtt_max_all}),
        ("hosts", hosts), ("miners", miners), ("epochs", epochs),
        ("row_counts", counts), ("warnings", warnings),
        ("phase", 1),
    ])
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1, ensure_ascii=False),
                                           encoding="utf-8")
    LOG.info("%s: phase1 written (%d score lines, %d blocks, %d verify lines, %d competing-block lines)",
             run["run_id"], counts["sortition_scores"], counts["blocks"], counts["verify_lines"],
             counts["sortition_ok_blocks"])
    return manifest


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="esperimenti", help="archived campaign (read-only)")
    ap.add_argument("--out", default="risultati", help="output root")
    ap.add_argument("--config-root", default="config", help="shadow/config (levels/*.json)")
    ap.add_argument("--only", default="", help="substring filter on run_id (e.g. run2 or regionale)")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO,
                        format="%(asctime)s %(levelname)-7s %(message)s")
    root = Path(args.root).expanduser().resolve()
    runs = [r for r in C.discover_runs(root) if args.only in r["run_id"]]
    if not runs:
        LOG.error("no runs found under %s", root)
        return 1
    for run in runs:
        try:
            collect_run(run, Path(args.out).expanduser().resolve(), Path(args.config_root).expanduser().resolve())
        except Exception as exc:              # a broken run must not stop the others
            LOG.exception("%s: phase1 failed: %s", run["run_id"], exc)
    return 0


if __name__ == "__main__":
    sys.exit(main())
