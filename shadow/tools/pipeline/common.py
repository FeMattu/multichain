#!/usr/bin/env python3
"""Shared pure helpers of the Shadow pipeline.

Everything here is deterministic and free of statistics: discovery of the
archived runs, reading of `params.dat` / RPC snapshots / harness CSVs, the
`txs.log` confirmation index, the height->epoch map (ONE function for both the
wPoA and the weight-engine modules), the damping and malus functions of the
protocol, the weight-engine fold of Chapter 6, the regular expressions of the
`debug.log` lines, and the topology latency matrix.

The functions in the section "moved from analizza_esperimenti.py" were
extracted verbatim (same behaviour, English docstrings) from the legacy
`tools/analizza_esperimenti.py`, which now re-imports them from here so that
the two code paths cannot drift apart.

Standard library only, except optional scipy (Spearman p-value) and optional
networkx (topology matrix); both absences are declared, never silently patched.
"""

import csv
import json
import logging
import math
import re
from collections import Counter
from pathlib import Path

try:
    import scipy.stats as _scipy_stats
    USING_SCIPY = True
except ImportError:                                   # pragma: no cover
    _scipy_stats = None
    USING_SCIPY = False

try:
    import networkx as _nx
    USING_NETWORKX = True
except ImportError:                                   # pragma: no cover
    _nx = None
    USING_NETWORKX = False

LOG = logging.getLogger("pipeline.common")

# --------------------------------------------------------------------------
# constants shared with the legacy script
# --------------------------------------------------------------------------

LEVELS = ["regionale", "nazionale", "continentale", "intercontinentale"]

# Maximum end-to-end RTT per geographic level, in ms (from check_topology.py
# --matrix). Only a label for the "geography" axis: when networkx is available
# it is recomputed from the .gml, otherwise this fallback is used.
RTT_FALLBACK = {"regionale": 10.0, "nazionale": 22.0,
                "continentale": 44.7, "intercontinentale": 112.0}

RUN_DIR_RE = re.compile(r"^run(\d+)-tbt-(\d+)s$")
DELAY_RE = re.compile(
    r"wPoA-sortition height=(\d+) score=([0-9.eE+-]+) delay=([0-9.]+)s")

# params.dat keys that describe an experiment. Key = name in the file.
PARAM_KEYS = [
    "chain-name", "target-block-time", "setup-first-blocks", "mining-diversity",
    "mining-turnover", "weight-epoch-length", "weight-kappa", "weight-alpha",
    "weight-lambda", "wpoa-sortition-delta", "wpoa-sortition-lambda",
    "wpoa-randao-lookback", "dump-function", "enable-wpoa",
    "enable-wpoa-selection", "enable-wpoa-sortition", "enable-wpoa-malus",
    "enable-weight-engine", "minimum-relay-fee", "first-block-reward",
    "weight-treasury-address", "wpoa-malus-mu", "wpoa-malus-max",
    "wpoa-malus-equiv-points", "wpoa-malus-delay-points",
    "wpoa-malus-selfwrite-points", "wpoa-malus-badweight-points",
    # GAS conversion: `native-currency-multiple` is the number of raw units per
    # display unit. RPCs (hence every harness CSV) speak in display units, i.e.
    # already GAS; only chain parameters expressed in raw units need conversion.
    "native-currency-multiple", "initial-block-reward",
]

UPDATETX_RE = re.compile(r"UpdateTx ([0-9a-f]{8,}), block (-?\d+)")
NEWTX_RE = re.compile(r"NewTx ([0-9a-f]{64}), block (-?\d+)")

# Tables written by the legacy script under `<run>/<level>/`.
PER_RUN_TABLES = ["peso_riconciliazione", "account_ledger", "gas_transfers",
                  "esg_publish", "membership_events", "traffic_events",
                  "tabellone_eventi", "errori_integrita", "disuguaglianza_pesi"]

# Prefix with which txs.log abbreviates a txid in UpdateTx lines.
TXID_PREFIX_LEN = 10

FAMILY_PARAMS = ["target_block_time", "mining_diversity", "weight_epoch_length",
                 "weight_kappa", "weight_lambda", "wpoa_sortition_delta",
                 "wpoa_sortition_lambda", "wpoa_randao_lookback", "dump_function"]

# MC_WEIGHT_DEFAULT_STABILITY_MARGIN in src/weight_engine/weight_streams.h.
STABILITY_MARGIN = 6

# --------------------------------------------------------------------------
# debug.log line formats (all verified on the archived runs, see the phase-0
# report, section 2.5). Timestamps have 1 s resolution.
# --------------------------------------------------------------------------

LOG_TS_RE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}) ")
# mchn-miner: wPoA-sortition height=64 score=9.11e-06 delay=12.434s -> start in 12.434s (local=1Kz...)
SCORE_RE = re.compile(
    r"wPoA-sortition height=(\d+) score=([0-9.eE+-]+) delay=([0-9.]+)s -> start in "
    r"([0-9.]+)s \(local=(\w+)\)")
# [wpoa-sortition] feedback height=63 window=12 mean_spacing=10.750s Tblock=10.000s -> Phi=-0.750s (|Phi| <= 5.000s)
PHI_RE = re.compile(
    r"\[wpoa-sortition\] feedback height=(\d+) window=(\d+) mean_spacing=([0-9.]+)s "
    r"Tblock=([0-9.]+)s -> Phi=([+-][0-9.]+)s \(\|Phi\| <= ([0-9.]+)s\)")
# [wpoa-sortition] verify OK height=64 signer=1Kz... score=9.11e-06 delay=12s nTime=946685447 parent=946685434
VERIFY_OK_RE = re.compile(
    r"\[wpoa-sortition\] verify OK height=(\d+) signer=(\w+) score=([0-9.eE+-]+) "
    r"delay=(\d+)s nTime=(\d+) parent=(\d+)")
# VerifyBlockMinerWPoA: sortition OK block <hash> (height 64) proposer 1Kz...
SORT_OK_RE = re.compile(
    r"VerifyBlockMinerWPoA: sortition OK block ([0-9a-f]+) \(height (\d+)\) proposer (\w+)")
# VerifyBlockMinerWPoA: REJECT block <hash> (height N): <reason>   (0 occurrences in the campaign)
REJECT_RE = re.compile(
    r"VerifyBlockMinerWPoA: REJECT block ([0-9a-f]+) \(height (\d+)\): (.*)$")
# [WeightEngine] epoch 1 (height 27): w_k = 1 for 1Kz...
WE_PUB_RE = re.compile(
    r"\[WeightEngine\] epoch (\d+) \(height (-?\d+)\): w_k = (\d+) for (\w+)")
WE_OK_RE = re.compile(
    r"\[WeightEngine\] epoch (\d+): (\d+) of (\d+) published weight\(s\) checked "
    r"against the independent recomputation, all matching \((\d+) about another epoch")
WE_FAIL_RE = re.compile(
    r"\[WeightEngine\] epoch (\d+): (\d+) of (\d+) published weight\(s\) FAILED "
    r"independent verification")
WE_NOTVER_RE = re.compile(
    r"\[WeightEngine\] epoch (\d+): published weights NOT verified")
# [wpoa-malus] height=… epoch=… M=… Psi=… w=… -> w_eff=…   (0 occurrences in the campaign)
MALUS_APPLY_RE = re.compile(
    r"\[wpoa-malus\] height=(\d+) epoch=(\d+) M=([0-9.eE+-]+) Psi=([0-9.eE+-]+) "
    r"w=(\d+) -> w_eff=(\d+)")
RANDAO_RE = re.compile(r"\[wPoA-RANDAO\] seed for height=(\d+)")
# start-up lines (the node's own statement of the parameters it applies)
START_WPOA_RE = re.compile(
    r"\[wPoA\] (.*?)sortition (ON|OFF)(?: \(delta=([0-9.]+), lambda=([0-9.]+)\))?; "
    r"dumping=(\w+)")
START_RANDAO_RE = re.compile(r"RANDAO ON \(k=(\d+)\)")
START_MALUS_RE = re.compile(
    r"\[wPoA-malus\] ON; mu=([0-9.]+); Mmax=([0-9.]+); p\(equiv\)=([0-9.]+); "
    r"p\(delay\)=([0-9.]+); p\(selfwrite\)=([0-9.]+); p\(badweight\)=([0-9.]+)")
START_WE_RE = re.compile(
    r"\[WeightEngine\] ON; epoch-length=(\d+) blocks; kappa=([0-9.]+); alpha=([0-9.]+); "
    r"lambda=([0-9.]+); treasury=(\w+)")

# Reject reasons of VerifyBlockMinerWPoA (src/protocol/multichainblock.cpp).
REJECT_REASONS = [
    "no signer", "invalid signer pubkey", "missing VRF reveal",
    "block mined too early for its sortition score", "invalid VRF reveal",
    "miner is not the elected proposer",
]


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: tolerant readers
# --------------------------------------------------------------------------

def is_noise(path):
    """`*:Zone.Identifier` files are WSL/NTFS artefacts, not data."""
    return ":Zone.Identifier" in path.name


def read_json(path):
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        LOG.warning("unreadable JSON %s: %s", path, exc)
        return None


def rpc_result(path):
    """The `result` field of a JSON-RPC snapshot, or None."""
    payload = read_json(path)
    if payload is None:
        return None
    if isinstance(payload, dict):
        if payload.get("error"):
            LOG.warning("RPC error in %s: %s", path, payload["error"])
            return None
        return payload.get("result")
    return payload


def read_csv_rows(path, expected_cols=None, has_header=None):
    """Read a metrics/ CSV returning (header, rows).

    `has_header=None` autodetects: if the first row equals `expected_cols` it
    is treated as a header. Needed because `membership.csv` and
    `gas_transfers.csv` are written WITHOUT a header while the others have one.
    """
    if not path.exists():
        return None, []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    except OSError as exc:
        LOG.warning("unreadable CSV %s: %s", path, exc)
        return None, []
    if not rows:
        return None, []
    if has_header is None:
        first = rows[0]
        has_header = bool(expected_cols) and [c.strip() for c in first] == expected_cols
    if has_header:
        return [c.strip() for c in rows[0]], rows[1:]
    return None, rows


def parse_params_dat(path):
    """params.dat: lines `key = value   # comment`, restricted to PARAM_KEYS."""
    out = {}
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        LOG.warning("unreadable params.dat %s: %s", path, exc)
        return out
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, rest = line.partition("=")
        key = key.strip()
        if key not in PARAM_KEYS:
            continue
        value = rest.split("#", 1)[0].strip()
        if value:
            out[key] = value
    return out


def as_float(text, default=None):
    try:
        return float(str(text).strip())
    except (TypeError, ValueError):
        return default


def as_int(text, default=None):
    try:
        return int(float(str(text).strip()))
    except (TypeError, ValueError):
        return default


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: discovery
# --------------------------------------------------------------------------

def discover_runs(root):
    """All (run-directory, level) pairs under `root`.

    Neither the set of runs nor the set of levels is hardcoded: directories
    matching `runN-tbt-Ts` are enumerated and, inside each, every
    sub-directory containing `run/metrics/` is a level. A level is such only
    if it carries `run/metrics/` (other folders may live inside a run dir).
    """
    found = []
    if not root.is_dir():
        LOG.error("root does not exist: %s", root)
        return found
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        m = RUN_DIR_RE.match(run_dir.name)
        if not m:
            LOG.debug("ignoring non-conforming directory: %s", run_dir.name)
            continue
        run_index, tbt_from_name = int(m.group(1)), int(m.group(2))
        for level_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            metrics = level_dir / "run" / "metrics"
            if not metrics.is_dir():
                LOG.debug("ignoring %s: no run/metrics", level_dir.name)
                continue
            found.append({
                "run_id": "%s/%s" % (run_dir.name, level_dir.name),
                "run_dir": run_dir.name,
                "run_index": run_index,
                "tbt_dirname": tbt_from_name,
                "livello": level_dir.name,
                "path": level_dir,
                "metrics": metrics,
                "data": level_dir / "run" / "data",
            })
    LOG.info("found %d runs in %s", len(found), root)
    return found


def find_debug_logs(data_dir):
    """debug.log lives in `data/<host>/debug.log` (archived runs) or in
    `data/<host>/<chain>/debug.log` (fresh runs); returns (host, path)."""
    out = []
    if not data_dir.is_dir():
        return out
    for host_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        direct = host_dir / "debug.log"
        if direct.is_file():
            out.append((host_dir.name, direct))
            continue
        for sub in sorted(p for p in host_dir.iterdir() if p.is_dir()):
            nested = sub / "debug.log"
            if nested.is_file():
                out.append((host_dir.name, nested))
                break
    return out


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: run metadata and host maps
# --------------------------------------------------------------------------

def extract_meta(run):
    """Run metadata from the sealed params.dat + getinfo, not from the dir name."""
    meta = {
        "run_id": run["run_id"], "run_dir": run["run_dir"],
        "run_index": run["run_index"], "livello": run["livello"],
        "tbt_dirname": run["tbt_dirname"],
    }
    params = {}
    if run["data"].is_dir():
        for host_dir in sorted(p for p in run["data"].iterdir() if p.is_dir()):
            params = parse_params_dat(host_dir / "params.dat")
            if params:
                meta["params_da_host"] = host_dir.name
                break
    meta["params_trovato"] = bool(params)
    for key in PARAM_KEYS:
        meta[key.replace("-", "_")] = params.get(key, "")

    info = rpc_result(run["metrics"] / "admin_getinfo.json") or {}
    meta["setupblocks_getinfo"] = info.get("setupblocks", "")
    meta["chainname_getinfo"] = info.get("chainname", "")
    meta["protocolversion"] = info.get("protocolversion", "")

    tbt_params = as_int(params.get("target-block-time"))
    meta["tbt"] = tbt_params if tbt_params is not None else run["tbt_dirname"]
    meta["tbt_params"] = tbt_params if tbt_params is not None else ""
    # The directory name is a promise, params.dat is the fact.
    meta["tbt_mismatch"] = int(tbt_params is not None and tbt_params != run["tbt_dirname"])

    setup_params = as_int(params.get("setup-first-blocks"))
    setup_info = as_int(info.get("setupblocks"))
    meta["setup_blocks"] = setup_params if setup_params is not None else (setup_info or 0)
    meta["setup_mismatch"] = int(
        setup_params is not None and setup_info is not None and setup_params != setup_info)

    meta["epoch_len"] = as_int(params.get("weight-epoch-length"), 12)
    meta["mining_diversity_val"] = as_float(params.get("mining-diversity"))
    meta["delta"] = as_float(params.get("wpoa-sortition-delta"), 0.5)
    meta["lambda_sortition"] = as_float(params.get("wpoa-sortition-lambda"), 0.0)
    meta["rtt_max_ms"] = RTT_FALLBACK.get(run["livello"], "")

    # GAS conversion: read run by run, never hardcoded.
    ncm = as_float(params.get("native-currency-multiple"))
    meta["native_currency_multiple"] = ncm if ncm is not None else ""
    meta["fonte_conversione_gas"] = (
        "params.dat di %s (native-currency-multiple)" % meta.get("params_da_host", "?")
        if ncm is not None else "non disponibile: nessun params.dat leggibile")
    return meta


def extract_host_maps(run):
    """host -> address (esg_scores.csv) and host -> cluster head (membership.csv)."""
    addr_by_host, host_by_addr, esg_by_host = {}, {}, {}
    header, rows = read_csv_rows(run["metrics"] / "esg_scores.csv",
                                 expected_cols=["host", "address", "esg"])
    for row in rows:
        if len(row) < 3:
            continue
        host, addr, esg = row[0].strip(), row[1].strip(), as_float(row[2])
        addr_by_host[host] = addr
        host_by_addr[addr] = host
        esg_by_host[host] = esg

    cluster_by_host = {}
    _, mrows = read_csv_rows(run["metrics"] / "membership.csv", has_header=False)
    for row in mrows:
        if len(row) < 3:
            continue
        host, _addr, miner_addr = row[0].strip(), row[1].strip(), row[2].strip()
        cluster_by_host[host] = host_by_addr.get(miner_addr, miner_addr)
    return addr_by_host, host_by_addr, esg_by_host, cluster_by_host


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: txs.log index and protocol functions
# --------------------------------------------------------------------------

def build_tx_index(run):
    """Confirmation index: txid prefix -> height of the block that confirmed it.

    The metrics/ CSVs record the height at the moment the RPC was SENT, not
    the confirmation height; `data/<host>/txs.log` carries
    `UpdateTx <prefix>, block <N>` with the real one. Also returns the txids
    created and never confirmed (NewTx without an UpdateTx with block >= 0).
    """
    conf = {}
    seen_new = {}
    for host, path in _txs_logs(run["data"]):
        try:
            text = path.read_text(errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            m = UPDATETX_RE.search(line)
            if m:
                height = int(m.group(2))
                if height >= 0:
                    pre = m.group(1)[:TXID_PREFIX_LEN]
                    if pre not in conf or height < conf[pre]:
                        conf[pre] = height
                continue
            m = NEWTX_RE.search(line)
            if m:
                seen_new.setdefault(m.group(1), set()).add(host)
                # A node that receives a transaction already inside a block
                # records it directly as NewTx with the height.
                height = int(m.group(2))
                if height >= 0:
                    pre = m.group(1)[:TXID_PREFIX_LEN]
                    if pre not in conf or height < conf[pre]:
                        conf[pre] = height
    non_confermate = [(txid, sorted(hosts)) for txid, hosts in sorted(seen_new.items())
                      if txid[:TXID_PREFIX_LEN] not in conf]
    return conf, non_confermate


def _txs_logs(data_dir):
    """`txs.log` lives in `data/<host>/` or `data/<host>/<chain>/`."""
    out = []
    if not data_dir.is_dir():
        return out
    for host_dir in sorted(p for p in data_dir.iterdir() if p.is_dir()):
        direct = host_dir / "txs.log"
        if direct.is_file():
            out.append((host_dir.name, direct))
            continue
        for sub in sorted(p for p in host_dir.iterdir() if p.is_dir()):
            nested = sub / "txs.log"
            if nested.is_file():
                out.append((host_dir.name, nested))
                break
    return out


def tx_height(index, txid):
    """Confirmation height of a txid, or None if never confirmed."""
    if not txid or len(txid) < TXID_PREFIX_LEN:
        return None
    return index.get(txid[:TXID_PREFIX_LEN])


def epoch_of(height, epoch_len):
    """epoch(h) = h // L + 1: the map of HeightToEpoch (weight_engine.h) and of the thesis.

    This is the ONLY height->epoch function of the pipeline; both the wPoA and
    the weight-engine modules go through it.
    """
    if height is None or not epoch_len or epoch_len < 1:
        return None
    return int(height) // int(epoch_len) + 1


def apply_dumping(weight, dump_function):
    """g(.) of Def. 5.9, as in wpoa_selector.h::ApplyDumping."""
    w = float(weight)
    if dump_function == "sqrt":
        return math.sqrt(w)
    if dump_function == "log":
        return math.log(1.0 + w)
    return w


def malus_correction(accumulator, m_max):
    """Psi = max(0, 1 - M / M_max), Def. 5.24 (malus_record.h::CorrectionFactor)."""
    if not m_max or m_max <= 0:
        return 1.0
    psi = 1.0 - float(accumulator) / float(m_max)
    if psi <= 0.0:
        return 0.0
    return min(psi, 1.0)


def effective_after_malus(weight, psi):
    """w_eff = w * Psi with the rounding and floor of EffectiveWeight."""
    if weight == 0 or psi <= 0.0:
        return 0
    if psi >= 1.0:
        return int(weight)
    w = float(weight) * psi
    if w >= float(weight):
        return int(weight)
    r = int(math.floor(w + 0.5))
    return r if r else 1


def _gas_balance_samples(run):
    """host -> [(height, balance)] sorted; gas_balances.csv is a periodic SAMPLE."""
    samples = {}
    _h, rows = read_csv_rows(run["metrics"] / "gas_balances.csv",
                             expected_cols=["height", "host", "balance"])
    for row in rows:
        if len(row) < 3:
            continue
        height, host, bal = as_int(row[0]), row[1].strip(), as_float(row[2])
        if height is None or bal is None:
            continue
        samples.setdefault(host, []).append((height, bal))
    for host in samples:
        samples[host].sort()
    return samples


def _next_sample(samples, host, height):
    """First balance sample at or after `height`, or (None, None)."""
    for h, bal in samples.get(host, []):
        if h >= height:
            return h, bal
    return None, None


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: event tables (column names kept as in
# the legacy per-run tables, which still consume them)
# --------------------------------------------------------------------------

def extract_event_tables(run, meta, maps, txindex):
    """The four relational event tables plus the denormalised event board.

    Source of truth: the separate tables. The board is a convenience view.
    """
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    epoch_len = meta["epoch_len"]
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    out = {name: [] for name in PER_RUN_TABLES}

    # --- supply-chain traffic: the direct source of tau_i -------------------
    _h, rows = read_csv_rows(run["metrics"] / "traffic.csv",
                             expected_cols=["height", "host", "seq", "txid_or_error"])
    for row in rows:
        if len(row) < 4:
            continue
        h_send, host, seq, txid = as_int(row[0]), row[1].strip(), as_int(row[2]), row[3].strip()
        is_tx = len(txid) == 64 and all(c in "0123456789abcdef" for c in txid)
        h_conf = tx_height(txindex, txid) if is_tx else None
        if not is_tx:
            esito, dettaglio = "errore", txid
        elif h_conf is None:
            esito, dettaglio = "non_confermata", "txid mai comparso in un blocco"
        else:
            esito, dettaglio = "ok", ""
        rec = dict(base)
        rec.update({
            "height_invio": h_send if h_send is not None else "",
            "height_conferma": h_conf if h_conf is not None else "",
            "epoca": epoch_of(h_conf, epoch_len) or "",
            "nodo_publisher": host,
            "indirizzo": addr_by_host.get(host, ""),
            "miner_cluster": cluster_by_host.get(host, ""),
            "seq": seq if seq is not None else "",
            "esito": esito, "dettaglio_errore": dettaglio, "txid": txid if is_tx else "",
        })
        out["traffic_events"].append(rec)

    # --- ESG publications (closed stream, delegated CA only) ----------------
    for item in (rpc_result(run["metrics"] / "esg.json") or []):
        if not isinstance(item, dict):
            continue
        payload = ((item.get("data") or {}).get("json")) or {}
        addr = payload.get("node_address") or (item.get("keys") or [""])[0]
        pub_addr = (item.get("publishers") or [""])[0]
        h_conf = tx_height(txindex, item.get("txid", ""))
        rec = dict(base)
        rec.update({
            "height_conferma": h_conf if h_conf is not None else "",
            "epoca": epoch_of(h_conf, epoch_len) or "",
            "nodo_certificato": host_by_addr.get(addr, addr[:10]),
            "indirizzo_certificato": addr,
            "esg_score": payload.get("esg", ""),
            "publisher": host_by_addr.get(pub_addr, "ca"),
            "publisher_indirizzo": pub_addr,
            "txid": item.get("txid", ""),
        })
        out["esg_publish"].append(rec)

    # --- cluster memberships (self-attested) --------------------------------
    for item in (rpc_result(run["metrics"] / "membership.json") or []):
        if not isinstance(item, dict):
            continue
        payload = ((item.get("data") or {}).get("json")) or {}
        addr = payload.get("node_address", "")
        miner = payload.get("miner_address", "")
        h_conf = tx_height(txindex, item.get("txid", ""))
        rec = dict(base)
        rec.update({
            "height_conferma": h_conf if h_conf is not None else "",
            "epoca": epoch_of(h_conf, epoch_len) or "",
            "azienda": host_by_addr.get(addr, addr[:10]),
            "indirizzo": addr,
            "miner_cluster": host_by_addr.get(miner, miner[:10]),
            "miner_indirizzo": miner,
            "evento": "adesione" if addr != miner else "auto-adesione del miner",
            "txid": item.get("txid", ""),
        })
        out["membership_events"].append(rec)

    # --- GAS movements: init/refill from the admin + reconciliations --------
    # DECLARED LIMIT: gas_transfers.csv carries no txid, so for init/refill the
    # height is the SEND height; gas_balances.csv is a periodic sample and does
    # not include the admin.
    samples = _gas_balance_samples(run)
    _h, rows = read_csv_rows(run["metrics"] / "gas_transfers.csv",
                             expected_cols=["height", "tipo", "host", "importo"],
                             has_header=False)
    for row in rows:
        if len(row) < 4:
            continue
        h_send, tipo, dest, amount = as_int(row[0]), row[1].strip(), row[2].strip(), as_float(row[3])
        sh, sbal = _next_sample(samples, dest, h_send if h_send is not None else 0)
        rec = dict(base)
        rec.update({
            "height": h_send if h_send is not None else "",
            "height_conferma": "",
            "epoca": epoch_of(h_send, epoch_len) or "",
            "tipo": tipo,
            "nodo_mittente": "admin", "indirizzo_mittente": addr_by_host.get("admin", ""),
            "nodo_destinatario": dest, "indirizzo_destinatario": addr_by_host.get(dest, ""),
            "importo_gas": amount if amount is not None else "",
            "saldo_mittente_dopo": "",
            "fonte_saldo_mittente": "non_disponibile (l'admin non e' campionato in gas_balances.csv)",
            "saldo_destinatario_dopo": sbal if sbal is not None else "",
            "fonte_saldo_destinatario": ("campione a height=%d" % sh) if sh is not None
                                        else "non_disponibile",
            "note": "l'admin finanzia il nodo: init = dotazione iniziale, "
                    "refill = rifornimento sotto soglia; height e' l'altezza di INVIO, "
                    "non di conferma (gas_transfers.csv non porta il txid)",
        })
        out["gas_transfers"].append(rec)

    _h, rows = read_csv_rows(run["metrics"] / "reconciliation.csv",
                             expected_cols=["height", "epoch", "miner", "balance", "sent"])
    treasury = meta.get("weight_treasury_address", "")
    for row in rows:
        if len(row) < 5:
            continue
        h_send, ep, miner = as_int(row[0]), as_int(row[1]), row[2].strip()
        bal, sent = as_float(row[3]), as_float(row[4])
        # The transaction enters the mempool at the recorded height and is
        # confirmed in the next block: model validated on the runs.
        h_conf = (h_send + 1) if h_send is not None else None
        rec = dict(base)
        rec.update({
            "height": h_send if h_send is not None else "",
            "height_conferma": h_conf if h_conf is not None else "",
            "epoca": epoch_of(h_conf, epoch_len) or "",
            "tipo": "reconcile",
            "nodo_mittente": miner, "indirizzo_mittente": addr_by_host.get(miner, ""),
            "nodo_destinatario": "treasury", "indirizzo_destinatario": treasury,
            "importo_gas": sent if sent is not None else "",
            "saldo_mittente_prima": bal if bal is not None else "",
            "saldo_mittente_dopo": round(bal - sent, 4)
                                   if (bal is not None and sent is not None) else "",
            "fonte_saldo_mittente": "getbalance del miner stesso subito prima "
                                    "dell'invio, meno sent",
            "saldo_destinatario_dopo": "",
            "fonte_saldo_destinatario": "non_disponibile (il treasury e' letto solo a fine run)",
            "note": "il miner paga il treasury: e' la R_k dell'epoca (Cap. 6.4). "
                    "sent=0 significa nessun invio (saldo sotto la riserva o RPC fallita); "
                    "epoca registrata dall'harness = %s, epoca di conferma usata qui = %s"
                    % (ep, epoch_of(h_conf, epoch_len)),
        })
        out["gas_transfers"].append(rec)

    # --- denormalised board (convenience view) -----------------------------
    for rec in out["traffic_events"]:
        out["tabellone_eventi"].append(dict(base, **{
            "height": rec["height_conferma"] or rec["height_invio"], "epoca": rec["epoca"],
            "categoria_evento": "traffico", "nodo_mittente": rec["nodo_publisher"],
            "nodo_destinatario": "stream applicativo", "importo": rec["seq"],
            "unita": "seq", "note": rec["esito"]}))
    for rec in out["esg_publish"]:
        out["tabellone_eventi"].append(dict(base, **{
            "height": rec["height_conferma"], "epoca": rec["epoca"],
            "categoria_evento": "esg", "nodo_mittente": rec["publisher"],
            "nodo_destinatario": rec["nodo_certificato"], "importo": rec["esg_score"],
            "unita": "punteggio ESG", "note": "stream chiuso, scrive solo la CA delegata"}))
    for rec in out["membership_events"]:
        out["tabellone_eventi"].append(dict(base, **{
            "height": rec["height_conferma"], "epoca": rec["epoca"],
            "categoria_evento": "membership", "nodo_mittente": rec["azienda"],
            "nodo_destinatario": rec["miner_cluster"], "importo": "", "unita": "",
            "note": rec["evento"]}))
    for rec in out["gas_transfers"]:
        out["tabellone_eventi"].append(dict(base, **{
            "height": rec["height_conferma"] or rec["height"], "epoca": rec["epoca"],
            "categoria_evento": "gas/" + rec["tipo"], "nodo_mittente": rec["nodo_mittente"],
            "nodo_destinatario": rec["nodo_destinatario"], "importo": rec["importo_gas"],
            "unita": "GAS", "note": rec["note"].split(";")[0]}))
    out["tabellone_eventi"].sort(
        key=lambda r: (as_int(r.get("height"), 10 ** 9), r.get("categoria_evento", "")))
    return out


def _weight_records(run, txindex):
    """wpoa-weights records with the REAL height at which they became readable.

    The `height` inside the payload is what the publisher had in hand when it
    built the record; what matters for selection is the height at which the
    transaction was confirmed, because before that block no other node can
    read the weight.
    """
    recs = []
    for item in (rpc_result(run["metrics"] / "weights.json") or []):
        if not isinstance(item, dict):
            continue
        payload = ((item.get("data") or {}).get("json")) or {}
        addr, weight = payload.get("node_address"), payload.get("weight")
        if addr is None or weight is None:
            continue
        recs.append({
            "address": addr,
            "epoca": as_int(payload.get("epoch")),
            "peso": as_int(weight),
            "height_payload": as_int(payload.get("height")),
            "height_conferma": tx_height(txindex, item.get("txid", "")),
            "txid": item.get("txid", ""),
        })
    recs.sort(key=lambda r: (r["height_conferma"] if r["height_conferma"] is not None
                             else 10 ** 9, r["epoca"] or 0))
    return recs


def _inforce_shares(records, blocks, setup, dump_fn, psi_by_epoch, epoch_len, m_max):
    """For every measured block, each miner's expected share with the IN-FORCE weight.

    A block at height h is proposed reading the weight map at tip h-1: only
    records confirmed before h count. Tying the blocks of epoch e to the record
    stamped `epoch=e` would be wrong, because the engine publishes the weight
    of epoch e after the epoch has ended: the record stamped e enters into
    force inside epoch e+1.
    """
    per_block = []
    inforce = {}
    idx = 0
    for blk in blocks:
        h = blk["height"]
        while idx < len(records) and records[idx]["height_conferma"] is not None \
                and records[idx]["height_conferma"] < h:
            rec = records[idx]
            inforce[rec["address"]] = rec
            idx += 1
        if h <= setup or not inforce:
            continue
        eff = {}
        for addr, rec in inforce.items():
            psi = psi_by_epoch.get((addr, (epoch_of(h, epoch_len) or 1) - 1), 1.0)
            eff[addr] = apply_dumping(effective_after_malus(rec["peso"], psi), dump_fn)
        tot = sum(eff.values())
        if tot <= 0:
            continue
        per_block.append((h, blk.get("miner"), {a: v / tot for a, v in eff.items()},
                          {a: r["epoca"] for a, r in inforce.items()}))
    return per_block


# --------------------------------------------------------------------------
# weight-engine fold of Chapter 6 (extracted from compute_weight_reconciliation;
# the legacy function now calls these two and adds its test columns on top)
# --------------------------------------------------------------------------

def weight_engine_inputs_pure(memberships, esgs, traffic_ok, reconciliations, wrecs,
                              epoch_len, n_malus_rec=0):
    """Public inputs of the weight engine from plain tuples (no file access).

    memberships     [(company_address, miner_address, epoch_or_None)]
    esgs            [(address, esg_value_or_None, epoch_or_None, publisher_address)]
    traffic_ok      [(address, epoch)]  confirmed supply-chain transactions
    reconciliations [(miner_address, epoch, amount_gas)]  sent > 0 only counts
    wrecs           weight records as returned by _weight_records
    Returns the dict consumed by weight_engine_fold (see weight_engine_inputs).
    """
    cluster_addr, memb_epoch = {}, {}
    tau = Counter()
    for addr, miner, ep in memberships:
        if addr and ep:
            tau[(addr, ep)] += 1                # the membership publication itself is activity
        if not addr or not miner:
            continue
        cluster_addr.setdefault(miner, set())
        if addr != miner:                       # the miner is not its own company
            cluster_addr[miner].add(addr)
        memb_epoch[addr] = min(memb_epoch.get(addr, 10 ** 9), ep or 10 ** 9)
    esg_addr, esg_epoch = {}, {}
    for addr, val, ep, pub in esgs:
        if pub and ep:
            tau[(pub, ep)] += 1                 # the ESG publication is activity of the CA
        if not addr or val is None:
            continue
        esg_addr[addr] = val
        esg_epoch[addr] = min(esg_epoch.get(addr, 10 ** 9), ep or 10 ** 9)
    for addr, ep in traffic_ok:
        if addr and ep:
            tau[(addr, ep)] += 1
    for rec in wrecs:
        ep = epoch_of(rec["height_conferma"], epoch_len)
        if ep:
            tau[(rec["address"], ep)] += 1
    reconciled = Counter()
    for addr, ep, amount in reconciliations:
        if not addr or not ep or not amount or amount <= 0:
            continue                            # sent=0: no transaction issued
        tau[(addr, ep)] += 1
        reconciled[(addr, ep)] += amount

    published, pub_height = {}, {}
    for rec in wrecs:
        if rec["epoca"] is not None:
            published[(rec["address"], rec["epoca"])] = rec["peso"]
            pub_height[(rec["address"], rec["epoca"])] = rec["height_conferma"]

    miners = sorted(cluster_addr) or sorted({a for a, _e in published})
    return {
        "cluster_addr": cluster_addr, "memb_epoch": memb_epoch,
        "esg_addr": esg_addr, "esg_epoch": esg_epoch,
        "tau": tau, "reconciled": reconciled, "wrecs": wrecs,
        "published": published, "pub_height": pub_height,
        "miners": miners, "n_malus_rec": n_malus_rec, "malus_points": Counter(),
    }


def weight_engine_inputs(run, meta, events, txindex):
    """Legacy adapter: the same inputs from the event tables of extract_event_tables."""
    memberships = [(r["indirizzo"], r["miner_indirizzo"], r["epoca"] or None)
                   for r in events["membership_events"]]
    esgs = [(r["indirizzo_certificato"], as_float(r["esg_score"]), r["epoca"] or None,
             r.get("publisher_indirizzo", "")) for r in events["esg_publish"]]
    traffic_ok = [(r["indirizzo"], r["epoca"]) for r in events["traffic_events"]
                  if r["esito"] == "ok" and r["epoca"]]
    reconciliations = [(r["indirizzo_mittente"], r["epoca"], as_float(r["importo_gas"], 0.0) or 0.0)
                       for r in events["gas_transfers"] if r["tipo"] == "reconcile" and r["epoca"]]
    wrecs = _weight_records(run, txindex)
    n_malus_rec = sum(1 for _ in (rpc_result(run["metrics"] / "malus.json") or []))
    return weight_engine_inputs_pure(memberships, esgs, traffic_ok, reconciliations, wrecs,
                                     meta["epoch_len"], n_malus_rec)


def weight_engine_params(meta):
    """(kappa, alpha, lambda_w, mu, m_max, dump_fn) from the run metadata."""
    kappa = as_float(meta.get("weight_kappa"), 100.0) or 100.0
    alpha = as_float(meta.get("weight_alpha"), 0.2)
    lam = as_float(meta.get("weight_lambda"), 0.5)
    mu = as_float(meta.get("wpoa_malus_mu"), 0.5)
    m_max = as_float(meta.get("wpoa_malus_max"), 4.0)
    dump_fn = (str(meta.get("dump_function") or "none")).strip().lower() or "none"
    return kappa, alpha, lam, mu, m_max, dump_fn


def weight_engine_fold(inputs, meta, max_epoch):
    """Forward fold, epoch by epoch, of weight_engine.h::ComputeEpoch.

    theta is the CODE definition (sum of tau over the companies in clusters,
    D1 of the phase-0 report); the thesis definition is computed separately
    by phase 2. The published integer is round-half-away(w * kappa) clamped
    to >= 1 (ToIntegerWeight, D2).

    Returns (derived, psi_by_epoch, malus_by_epoch) where
    derived[(miner, e)] = {esg_miner, tau_miner, contrib, theta, raw, alloc,
    rho, rho_prev, balance_prev, balance, reconciled, w, int_weight, malus}.
    """
    kappa, alpha, lam, mu, m_max, _dump = weight_engine_params(meta)
    miners = inputs["miners"]
    tau, reconciled = inputs["tau"], inputs["reconciled"]
    cluster_addr, memb_epoch = inputs["cluster_addr"], inputs["memb_epoch"]
    esg_addr, esg_epoch = inputs["esg_addr"], inputs["esg_epoch"]
    malus_points = inputs["malus_points"]
    psi_by_epoch, malus_by_epoch = {}, {}
    state = {m: (0.0, 0.0) for m in miners}     # (B^(e-1), rho^(e-1))
    derived = {}
    for e in range(1, max_epoch + 1):
        esg_e = {a: v for a, v in esg_addr.items() if esg_epoch.get(a, 10 ** 9) <= e}
        comp_e = {m: sorted(c for c in cluster_addr.get(m, ())
                            if memb_epoch.get(c, 10 ** 9) <= e) for m in miners}
        theta = float(sum(tau[(c, e)] for m in miners for c in comp_e[m]))
        raw, contrib = {}, {}
        for m in miners:
            if memb_epoch.get(m, 10 ** 9) > e:
                raw[m], contrib[m] = 0.0, []
                continue
            parts = [(c, esg_e.get(c, 0.0), tau[(c, e)],
                      esg_e.get(c, 0.0) * tau[(c, e)] / kappa) for c in comp_e[m]]
            contrib[m] = parts
            raw[m] = esg_e.get(m, 0.0) * (tau[(m, e)] + sum(p[3] for p in parts))
        total_raw = sum(raw.values())
        new_state = {}
        for m in miners:
            b_prev, rho_prev = state.get(m, (0.0, 0.0)) if e >= 2 else (0.0, 0.0)
            alloc = 0.0 if total_raw <= 0 else alpha * theta * raw[m] / total_raw
            r_k = float(reconciled[(m, e)])
            denom = alloc + b_prev
            clamped = 0.0 if denom <= 0 else min(max(r_k, 0.0), denom)
            rho = 0.0 if denom <= 0 else clamped / denom
            balance = alloc - clamped + b_prev
            w = raw[m] if e <= 1 else raw[m] * (rho_prev * lam + (1.0 - lam))
            scaled = w * kappa
            iw = 1 if not (scaled >= 1.0) else int(math.floor(scaled + 0.5))
            m_acc = mu * malus_by_epoch.get((m, e - 1), 0.0) + malus_points[(m, e)]
            malus_by_epoch[(m, e)] = m_acc
            psi_by_epoch[(m, e)] = malus_correction(m_acc, m_max)
            derived[(m, e)] = {
                "esg_miner": esg_e.get(m, 0.0), "tau_miner": tau[(m, e)],
                "contrib": contrib[m], "theta": theta, "raw": raw[m],
                "alloc": alloc, "rho": rho, "rho_prev": rho_prev if e >= 2 else "",
                "balance_prev": b_prev, "balance": balance, "reconciled": r_k,
                "w": w, "int_weight": iw, "malus": m_acc,
            }
            new_state[m] = (balance, rho)
        state = new_state
    return derived, psi_by_epoch, malus_by_epoch


# --------------------------------------------------------------------------
# moved from analizza_esperimenti.py: descriptive helpers and families
# --------------------------------------------------------------------------

def gini(values):
    """Gini index on non-negative values. 0 = equal split, ->1 = all to one.
    Defined as half the relative mean absolute difference."""
    vals = [float(v) for v in values if v is not None and float(v) >= 0]
    n = len(vals)
    total = sum(vals)
    if n < 2 or total <= 0:
        return 0.0
    vals.sort()
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return cum / (n * total)


def normalized_entropy(values):
    """H/H_max over the shares: 1 = equal split, 0 = a single host holds everything."""
    vals = [float(v) for v in values if v is not None and float(v) > 0]
    total = sum(vals)
    if len(vals) < 2 or total <= 0:
        return 0.0
    h = -sum((v / total) * math.log(v / total) for v in vals)
    return h / math.log(len(vals))


def _spearman(xs, ys):
    """(rho, p, n) of Spearman, or ('', '', n) when the sample does not allow it.

    With scipy the p-value comes from scipy.stats.spearmanr; without it only
    the coefficient on ranks is computed and the p-value stays empty.
    """
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return "", "", len(pairs)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return "", "", len(pairs)     # a constant series: rho is undefined
    if USING_SCIPY:
        res = _scipy_stats.spearmanr(xs, ys)
        rho, pval = float(res[0]), float(res[1])
        return round(rho, 6), round(pval, 6), len(pairs)

    def ranks(vals):
        order = sorted(range(len(vals)), key=lambda i: vals[i])
        out = [0.0] * len(vals)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and vals[order[j + 1]] == vals[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    rx, ry = ranks(xs), ranks(ys)
    mx, my = sum(rx) / len(rx), sum(ry) / len(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return (round(num / den, 6) if den else ""), "", len(pairs)


def build_families(index):
    """Families of runs differing in EXACTLY one parameter, built from the index.

    The geographic level enters the grouping key when it is NOT the variable
    under study; when it is (family `livello`), everything else enters the key.
    """
    from collections import defaultdict
    out = []
    for param in FAMILY_PARAMS + ["livello"]:
        gruppi = defaultdict(list)
        for row in index:
            if row.get("stato") in ("errore", "incompleta"):
                continue
            chiave = tuple((k, str(row.get(k, ""))) for k in FAMILY_PARAMS + ["livello"]
                           if k != param)
            gruppi[chiave].append(row)
        for chiave, rows in gruppi.items():
            valori = sorted({str(r.get(param, "")) for r in rows})
            if len(valori) < 2:
                continue
            out.append({
                "parametro_variato": param,
                "valori": " | ".join(valori),
                "n_run": len(rows),
                "run_id": " ".join(sorted(r["run_id"] for r in rows)),
                "costanti": "; ".join("%s=%s" % (k, v) for k, v in chiave),
            })
    out.sort(key=lambda r: (r["parametro_variato"], r["costanti"]))
    return out


# --------------------------------------------------------------------------
# new helpers of the pipeline
# --------------------------------------------------------------------------

def epoch_bounds(epoch, epoch_len):
    """Heights covered by epoch e: [(e-1)L, eL-1]."""
    return (epoch - 1) * epoch_len, epoch * epoch_len - 1


def epoch_buried(epoch, epoch_len, tip_height, margin=STABILITY_MARGIN):
    """True when the last block of the epoch has `margin` blocks on top of it."""
    _lo, hi = epoch_bounds(epoch, epoch_len)
    return tip_height >= hi + margin


def normalized_score(score, w_tot):
    """1 - exp(-W_tot * score) (private_sortition.h)."""
    return 1.0 - math.exp(-float(w_tot) * float(score))


def phi_bound(tbt, delta, lam):
    """Clip bound of Phi: min(T/2, T(1-delta)/lambda); infinite when lambda = 0."""
    if not lam:
        return float("inf")
    return min(tbt / 2.0, tbt * (1.0 - delta) / lam)


def sortition_delay(score, w_tot, tbt, delta, lam, phi):
    """D = T + delta*T*(2*norm - 1) + lambda*Phi, clamped to [0, 100000]."""
    norm = normalized_score(score, w_tot)
    d = tbt + delta * tbt * (2.0 * norm - 1.0) + lam * phi
    return min(max(d, 0.0), 100000.0)


def iter_log_lines(path, needles):
    """Stream a debug.log yielding (line_no, timestamp, line) for lines that
    contain at least one of `needles`; the substring test skips ~93 % of the
    lines (RANDAO) before any regex runs."""
    with path.open(encoding="utf-8", errors="replace") as fh:
        for no, line in enumerate(fh, 1):
            for needle in needles:
                if needle in line:
                    m = LOG_TS_RE.match(line)
                    yield no, (m.group(1) if m else ""), line.rstrip("\n")
                    break


def parse_startup_params(path):
    """The parameters a node declares in its start-up lines.

    Returns a dict with keys among: sortition_delta, sortition_lambda,
    dump_function, randao_lookback, malus_mu, malus_max, malus_equiv_points,
    malus_delay_points, malus_selfwrite_points, malus_badweight_points,
    weight_epoch_length, weight_kappa, weight_alpha, weight_lambda,
    weight_treasury_address. Only the first 4000 lines are scanned.
    """
    out = {}
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            for no, line in enumerate(fh):
                if no > 4000 or len(out) >= 15:
                    break
                if "[wPoA] " in line:
                    m = START_WPOA_RE.search(line)
                    if m:
                        if m.group(3) is not None:
                            out["sortition_delta"] = m.group(3)
                            out["sortition_lambda"] = m.group(4)
                        out["dump_function"] = m.group(5)
                    m = START_RANDAO_RE.search(line)
                    if m:
                        out["randao_lookback"] = m.group(1)
                elif "[wPoA-malus] ON" in line:
                    m = START_MALUS_RE.search(line)
                    if m:
                        out.update({
                            "malus_mu": m.group(1), "malus_max": m.group(2),
                            "malus_equiv_points": m.group(3), "malus_delay_points": m.group(4),
                            "malus_selfwrite_points": m.group(5),
                            "malus_badweight_points": m.group(6)})
                elif "[WeightEngine] ON" in line:
                    m = START_WE_RE.search(line)
                    if m:
                        out.update({
                            "weight_epoch_length": m.group(1), "weight_kappa": m.group(2),
                            "weight_alpha": m.group(3), "weight_lambda": m.group(4),
                            "weight_treasury_address": m.group(5)})
    except OSError as exc:
        LOG.warning("unreadable debug.log %s: %s", path, exc)
    return out


def parse_shadow_yaml(path):
    """seed, GML path and the POESIA_* environment of the first host from a
    Shadow yaml, read line by line (no yaml dependency)."""
    out = {"general_seed": "", "gml_path": "", "env": {}}
    if not path or not Path(path).is_file():
        return out
    env_re = re.compile(r'^\s+(POESIA_[A-Z0-9_]+):\s*"?([^"]*)"?\s*$')
    for line in Path(path).read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if s.startswith("seed:") and not out["general_seed"]:
            out["general_seed"] = s.split(":", 1)[1].strip()
        elif s.startswith("path:") and s.endswith(".gml") and not out["gml_path"]:
            out["gml_path"] = s.split(":", 1)[1].strip()
        else:
            m = env_re.match(line)
            if m and m.group(1) not in out["env"]:
                out["env"][m.group(1)] = m.group(2)
    return out


def parse_shadow_ms(value):
    """Convert a Shadow quantity with unit ('200 us', '3 ms') to milliseconds."""
    text = str(value).strip()
    for suffix, factor in (("ns", 1e-6), ("us", 1e-3), ("ms", 1.0), ("s", 1000.0)):
        if text.endswith(suffix):
            return float(text[:-len(suffix)].strip()) * factor
    return float(text)


def topology_latency(gml_path, level_json_path):
    """One-way shortest-path latency (ms) between hosts from the .gml, plus the
    declared jitter and packet loss of every edge.

    Returns (rows, note): rows = [{host_a, host_b, one_way_ms, rtt_ms, hops}],
    note = why it is empty when it is. Requires networkx and the level json
    (GML node id -> host name).
    """
    if not USING_NETWORKX:
        return [], "not computable: networkx not installed"
    if not gml_path or not Path(gml_path).is_file():
        return [], "not computable: .gml not found (%s)" % gml_path
    level = read_json(Path(level_json_path)) if level_json_path else None
    if not level or "nodes" not in level:
        return [], "not computable: level json without nodes (%s)" % level_json_path
    host_of = {int(n["id"]): n["host"] for n in level["nodes"] if "host" in n}
    g = _nx.read_gml(str(gml_path), label="id")
    simple = _nx.Graph()
    edge_meta = []
    for u, v, data in g.edges(data=True):
        ms = parse_shadow_ms(data.get("latency", "0 ms"))
        edge_meta.append({"source": u, "target": v, "latency_ms": ms,
                          "jitter": str(data.get("jitter", "")),
                          "packet_loss": data.get("packet_loss", "")})
        if u == v:
            continue
        if simple.has_edge(u, v):
            simple[u][v]["ms"] = min(simple[u][v]["ms"], ms)
        else:
            simple.add_edge(u, v, ms=ms)
    paths = dict(_nx.all_pairs_dijkstra_path_length(simple, weight="ms"))
    hops = dict(_nx.all_pairs_shortest_path_length(simple))
    rows = []
    for a in sorted(host_of):
        for b in sorted(host_of):
            if a >= b:
                continue
            ms = paths.get(a, {}).get(b)
            if ms is None:
                continue
            rows.append({"host_a": host_of[a], "host_b": host_of[b],
                         "one_way_ms": round(ms, 4), "rtt_ms": round(2 * ms, 4),
                         "hops": hops.get(a, {}).get(b, "")})
    return rows, {"edges": edge_meta}


def run_slug(run):
    """Directory-safe identifier `<run_dir>__<area>`."""
    return "%s__%s" % (run["run_dir"], run["livello"])


def write_csv(path, rows, fieldnames=None):
    """Write a list of dicts as CSV; an empty list still writes the header
    when `fieldnames` is given (so that 'empty' is distinguishable from 'absent')."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if fieldnames is None:
        fieldnames = []
        for r in rows:
            for k in r:
                if k not in fieldnames:
                    fieldnames.append(k)
    with path.open("w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)
    return len(rows)


def read_csv_dicts(path):
    """Read a CSV written by the pipeline as a list of dicts (strings)."""
    path = Path(path)
    if not path.is_file():
        return []
    with path.open(encoding="utf-8", newline="") as fh:
        return list(csv.DictReader(fh))


def fnum(text, default=None):
    """Float from a pipeline CSV cell ('' -> default)."""
    if text is None or text == "":
        return default
    try:
        return float(text)
    except (TypeError, ValueError):
        return default


def inum(text, default=None):
    if text is None or text == "":
        return default
    try:
        return int(float(text))
    except (TypeError, ValueError):
        return default
