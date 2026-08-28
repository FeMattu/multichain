#!/usr/bin/env python3
"""
Estrazione e normalizzazione delle run Shadow in `esperimenti/`.

Esplora dinamicamente l'albero `<root>/runN-tbt-Ts/<livello>/run/metrics/`,
ispeziona lo schema reale di ogni file prima di leggerlo, e scrive in `--out`
una manciata di CSV normalizzati piu' un report di schema e un indice delle run.

    python3 tools/analizza_esperimenti.py --root esperimenti/
    python3 tools/analizza_esperimenti.py --root esperimenti/ --recompute-chisq
    python3 tools/analizza_esperimenti.py --root esperimenti/ --force

Sola lettura su `--root`; scrive esclusivamente in `--out`.

Dipendenze: sola libreria standard. pandas e scipy sono usati **se presenti**
(vedi USING_PANDAS / USING_SCIPY nel log) ma non sono richiesti: su questa
macchina non sono installati, e la pipeline resta corretta senza di loro.
"""

import argparse
import csv
import json
import logging
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import scipy.stats as _scipy_stats
    USING_SCIPY = True
except ImportError:
    _scipy_stats = None
    USING_SCIPY = False

try:
    import pandas as _pd
    USING_PANDAS = True
except ImportError:
    _pd = None
    USING_PANDAS = False


LOG = logging.getLogger("analizza")

LEVELS = ["regionale", "nazionale", "continentale", "intercontinentale"]

# Valori critici della chi-quadro al 5%, per gradi di liberta'. Tabulati qui
# perche' scipy non e' una dipendenza garantita.
CHI2_CRIT_05 = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488, 5: 11.070,
                6: 12.592, 7: 14.067, 8: 15.507, 9: 16.919, 10: 18.307}

# RTT massimo end-to-end per livello, in ms (da check_topology.py --matrix).
# Serve solo come etichetta dell'asse "geografia": se networkx e' disponibile
# viene ricalcolato dal .gml, altrimenti si usa questo fallback.
RTT_FALLBACK = {"regionale": 10.0, "nazionale": 22.0,
                "continentale": 44.7, "intercontinentale": 112.0}

RUN_DIR_RE = re.compile(r"^run(\d+)-tbt-(\d+)s$")
DELAY_RE = re.compile(
    r"wPoA-sortition height=(\d+) score=([0-9.eE+-]+) delay=([0-9.]+)s")
CHI2_RE = re.compile(
    r"chi-quadro = ([0-9.]+)\s+\(df=(\d+), critico 5% = ([0-9.]+)\)\s+->\s+(.+)")

# Parametri di params.dat che descrivono un esperimento. Chiave = nome nel file.
PARAM_KEYS = [
    "chain-name", "target-block-time", "setup-first-blocks", "mining-diversity",
    "mining-turnover", "weight-epoch-length", "weight-kappa", "weight-alpha",
    "weight-lambda", "wpoa-sortition-delta", "wpoa-sortition-lambda",
    "wpoa-randao-lookback", "dump-function", "enable-wpoa",
    "enable-wpoa-selection", "enable-wpoa-sortition", "enable-wpoa-malus",
    "enable-weight-engine", "minimum-relay-fee", "first-block-reward",
]


# --------------------------------------------------------------------------
# utilita' di lettura, tolleranti ai file mancanti o malformati
# --------------------------------------------------------------------------

def is_noise(path):
    """I file `*:Zone.Identifier` sono artefatti di WSL/NTFS, non dati."""
    return ":Zone.Identifier" in path.name


def read_json(path):
    if not path.exists():
        return None
    try:
        with path.open(encoding="utf-8", errors="replace") as fh:
            return json.load(fh)
    except (ValueError, OSError) as exc:
        LOG.warning("JSON illeggibile %s: %s", path, exc)
        return None


def rpc_result(path):
    """Estrae il campo `result` da uno snapshot JSON-RPC, o None."""
    payload = read_json(path)
    if payload is None:
        return None
    if isinstance(payload, dict):
        if payload.get("error"):
            LOG.warning("RPC in errore in %s: %s", path, payload["error"])
            return None
        return payload.get("result")
    return payload


def read_csv_rows(path, expected_cols=None, has_header=None):
    """Legge un CSV di metrics/ restituendo (header, righe).

    `has_header=None` autorileva: se la prima cella e' un nome di colonna noto
    (non numerico e non un indirizzo) la riga e' trattata come intestazione.
    Serve perche' `membership.csv` e `gas_transfers.csv` sono scritti SENZA
    intestazione, mentre gli altri CSV ce l'hanno.
    """
    if not path.exists():
        return None, []
    try:
        with path.open(encoding="utf-8", errors="replace", newline="") as fh:
            rows = [r for r in csv.reader(fh) if r and any(c.strip() for c in r)]
    except OSError as exc:
        LOG.warning("CSV illeggibile %s: %s", path, exc)
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
    """params.dat: righe `chiave = valore   # commento`."""
    out = {}
    if not path.exists():
        return out
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as exc:
        LOG.warning("params.dat illeggibile %s: %s", path, exc)
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
# discovery
# --------------------------------------------------------------------------

def discover_runs(root):
    """Trova tutte le coppie (cartella-run, livello) sotto `root`.

    Non hardcoda ne' l'insieme delle run ne' quello dei livelli: enumera le
    directory che corrispondono al pattern `runN-tbt-Ts` e, dentro ciascuna,
    ogni sottodirectory che contenga `run/metrics/`. Aggiungere run nuove e
    rilanciare basta.
    """
    found = []
    if not root.is_dir():
        LOG.error("root inesistente: %s", root)
        return found
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        m = RUN_DIR_RE.match(run_dir.name)
        if not m:
            LOG.debug("ignoro directory non conforme: %s", run_dir.name)
            continue
        run_index, tbt_from_name = int(m.group(1)), int(m.group(2))
        for level_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            metrics = level_dir / "run" / "metrics"
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
    LOG.info("trovate %d run in %s", len(found), root)
    return found


def find_debug_logs(data_dir):
    """I debug.log stanno in `data/<host>/debug.log` nelle run archiviate e in
    `data/<host>/<chain>/debug.log` in quelle appena eseguite: si cercano
    entrambe le forme, restituendo (host, path)."""
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
# ispezione dello schema
# --------------------------------------------------------------------------

def describe_json(payload, depth=0):
    if isinstance(payload, dict):
        return "oggetto{%s}" % ", ".join(sorted(payload)[:12])
    if isinstance(payload, list):
        if not payload:
            return "lista vuota"
        head = payload[0]
        if isinstance(head, dict):
            return "lista[%d] di oggetti{%s}" % (len(payload), ", ".join(sorted(head)[:12]))
        return "lista[%d] di %s" % (len(payload), type(head).__name__)
    return type(payload).__name__


def inspect_schema(runs, out_dir):
    """Elenca cosa esiste davvero in ogni metrics/, e con quale schema.

    E' il passo che precede il parser: se un file cambia nome o colonne, la
    divergenza compare qui prima di propagarsi in una tabella sbagliata.
    """
    per_file_headers = defaultdict(Counter)
    per_file_presence = Counter()
    lines = ["# Schema reale di `metrics/`", "",
             "Generato da `tools/analizza_esperimenti.py`: elenca i file "
             "effettivamente presenti in ogni run e lo schema dedotto, cosi' "
             "si sa da quale campo viene ogni numero delle tabelle.", ""]

    for run in runs:
        metrics = run["metrics"]
        if not metrics.is_dir():
            continue
        for path in sorted(metrics.iterdir()):
            if is_noise(path) or not path.is_file():
                continue
            per_file_presence[path.name] += 1
            if path.suffix == ".csv":
                header, rows = read_csv_rows(path)
                first = rows[0] if rows else []
                if header:
                    per_file_headers[path.name]["header: " + ",".join(header)] += 1
                else:
                    per_file_headers[path.name][
                        "senza header, %d colonne (es. %s)" % (len(first), ",".join(first[:4]))] += 1
            elif path.suffix == ".json":
                payload = read_json(path)
                if payload is None:
                    per_file_headers[path.name]["illeggibile"] += 1
                    continue
                if isinstance(payload, dict) and "result" in payload:
                    per_file_headers[path.name][
                        "JSON-RPC, result = " + describe_json(payload["result"])] += 1
                else:
                    per_file_headers[path.name][describe_json(payload)] += 1
            else:
                per_file_headers[path.name]["testo"] += 1

    total = len(runs)
    lines.append("## File per run (%d run esaminate)" % total)
    lines.append("")
    lines.append("| file | presente in | schema osservato |")
    lines.append("|---|---|---|")
    for name in sorted(per_file_presence):
        variants = per_file_headers[name]
        desc = "<br>".join("`%s` (%d run)" % (k, v) for k, v in variants.most_common())
        flag = "" if per_file_presence[name] == total else " ⚠"
        lines.append("| `%s` | %d/%d%s | %s |" % (name, per_file_presence[name], total, flag, desc))
    lines.append("")
    lines.append("## Note sullo schema, verificate sul campo")
    lines.append("")
    lines.append("* `membership.csv` e `gas_transfers.csv` sono scritti **senza riga di "
                 "intestazione**: le colonne sono rispettivamente "
                 "`host,address,miner_address` e `height,tipo,host,importo`.")
    lines.append("* `node_state.csv` ha una colonna dal nome **variabile** "
                 "(`hash_a_<N>`, con N = altezza di riferimento della run): il "
                 "parser la individua per posizione, non per nome.")
    lines.append("* i file `*:Zone.Identifier` sono artefatti di WSL/NTFS e vengono ignorati.")
    lines.append("* i `debug.log` stanno in `data/<host>/debug.log` nelle run "
                 "archiviate e in `data/<host>/<chain>/debug.log` in quelle "
                 "appena eseguite: si cercano entrambe le forme.")
    lines.append("* il chi-quadro **non** e' in un file dati: esiste solo come "
                 "testo in `summary.txt`, da cui viene estratto con regex "
                 "(`--recompute-chisq` lo ricalcola come controprova).")
    lines.append("* `weights.json` porta gia' `epoch` in ogni record, quindi la "
                 "traiettoria per epoca non richiede di rimappare le altezze.")
    lines.append("* `admin_getinfo.json` espone `setupblocks` e `chainname`: e' "
                 "la fonte piu' autorevole per la lunghezza del setup, "
                 "incrociata con `params.dat`.")
    (out_dir / "metrics_schema_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    LOG.info("scritto metrics_schema_report.md")


# --------------------------------------------------------------------------
# estrazione per singola run
# --------------------------------------------------------------------------

def chi_square(observed, expected):
    stat = 0.0
    for obs, exp in zip(observed, expected):
        if exp > 0:
            stat += (obs - exp) ** 2 / exp
    return stat, max(1, len(observed) - 1)


def extract_meta(run):
    """Metadati della run: params.dat sigillato + getinfo, non il nome cartella."""
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
    # Il nome cartella e' una promessa, params.dat e' il fatto: se divergono
    # la run e' etichettata male e ogni confronto per tbt sarebbe falsato.
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
    return meta


def extract_host_maps(run):
    """host -> indirizzo (da esg_scores.csv) e host -> cluster (da membership.csv)."""
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


def extract_blocks(run, meta):
    blocks = rpc_result(run["metrics"] / "blocks.json")
    if not isinstance(blocks, list):
        return None, []
    blocks = [b for b in blocks if isinstance(b, dict) and "height" in b]
    blocks.sort(key=lambda b: b["height"])
    setup = meta["setup_blocks"]
    measured = [b for b in blocks if b["height"] > setup]
    if len(measured) < 3:
        return None, blocks
    deltas = [measured[i]["time"] - measured[i - 1]["time"]
              for i in range(1, len(measured))]
    deltas = [d for d in deltas if d >= 0]
    target = meta["tbt"]
    row = {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": target,
        "blocchi_totali": len(blocks), "setup_blocks": setup,
        "blocchi_misurati": len(measured),
        "dt_medio_s": round(statistics.mean(deltas), 3) if deltas else "",
        "dt_mediana_s": round(statistics.median(deltas), 3) if deltas else "",
        "dt_sd_s": round(statistics.pstdev(deltas), 3) if len(deltas) > 1 else 0.0,
        "dt_min_s": min(deltas) if deltas else "",
        "dt_max_s": max(deltas) if deltas else "",
        "target_s": target,
        "scarto_s": round(statistics.mean(deltas) - target, 3) if deltas else "",
        "scarto_pct": round((statistics.mean(deltas) - target) / target * 100, 2)
                      if deltas and target else "",
    }
    return row, measured


def extract_weights(run, meta, host_by_addr):
    """Traiettoria dei pesi per epoca dallo stream wpoa-weights."""
    items = rpc_result(run["metrics"] / "weights.json")
    traj, latest = [], {}
    if not isinstance(items, list):
        return traj, latest
    for item in items:
        data = (item or {}).get("data") or {}
        rec = data.get("json") if isinstance(data, dict) else None
        if not isinstance(rec, dict):
            continue
        addr = rec.get("node_address")
        weight = rec.get("weight")
        if addr is None or weight is None:
            continue
        epoch = as_int(rec.get("epoch"))
        height = as_int(rec.get("height"))
        traj.append({
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "host": host_by_addr.get(addr, addr[:10]), "address": addr,
            "epoca": epoch if epoch is not None else "",
            "peso": as_int(weight), "height": height if height is not None else "",
        })
        # "l'ultimo vince": ordina per (epoca, altezza) e tieni il piu' recente
        key = (epoch or 0, height or 0)
        if addr not in latest or key >= latest[addr][0]:
            latest[addr] = (key, as_int(weight))
    return traj, {a: w for a, (_k, w) in latest.items()}


def extract_proposers(run, meta, measured, latest_weights, host_by_addr, delays):
    """Distribuzione dei proposer, alternanze e chi-quadro."""
    if not measured:
        return [], None, None
    counts = Counter(b.get("miner") for b in measured if b.get("miner"))
    total = sum(counts.values())
    if not total:
        return [], None, None

    # I candidati sono gli indirizzi con peso pubblicato positivo: admin e ca
    # non hanno peso e non devono comparire fra le attese (Cor. 5.4).
    weighted = {a: w for a, w in latest_weights.items() if w and w > 0}
    addrs = sorted(set(weighted) | set(counts))
    w_tot = sum(weighted.get(a, 0) for a in addrs) or 0

    rows, observed, expected, shares = [], [], [], []
    for addr in addrs:
        host = host_by_addr.get(addr, addr[:10])
        obs = counts.get(addr, 0)
        weight = weighted.get(addr, 0)
        share_obs = obs / total
        share_exp = (weight / w_tot) if w_tot else ""
        d = delays.get(host, {})
        rows.append({
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "host": host, "address": addr,
            "blocchi": obs, "quota_osservata": round(share_obs, 5),
            "peso_ultimo": weight,
            "quota_attesa": round(share_exp, 5) if share_exp != "" else "",
            "delay_campioni": d.get("n", ""),
            "delay_medio_s": d.get("mean", ""),
            "delay_min_s": d.get("min", ""),
            "delay_max_s": d.get("max", ""),
            "delay_pos_in_banda": d.get("pos", ""),
        })
        observed.append(obs)
        expected.append(share_exp * total if share_exp != "" else 0.0)
        shares.append(share_obs)

    seq = [b.get("miner") for b in measured if b.get("miner")]
    consec = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
    alt = {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
        "blocchi_misurati": len(seq),
        "consecutivi_osservati": consec,
        "consecutivi_attesi": round(sum(p * p for p in shares) * max(0, len(seq) - 1), 2),
    }

    chi = None
    if w_tot and all(e > 0 for e in expected):
        stat, df = chi_square(observed, expected)
        crit = CHI2_CRIT_05.get(df, "")
        chi = {
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "chi2_ricalcolato": round(stat, 4), "df": df, "critico_5pct": crit,
            "compatibile_ricalcolato": int(bool(crit) and stat <= crit),
            "min_attesa": round(min(expected), 2),
            "campione_sufficiente": int(min(expected) >= 5),
        }
    return rows, alt, chi


def extract_chisq_from_summary(run, meta):
    """Il chi-quadro esiste solo come testo in summary.txt: lo si estrae da li'."""
    path = run["metrics"] / "summary.txt"
    if not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None
    m = CHI2_RE.search(text)
    if not m:
        return None
    verdict = m.group(4).strip()
    return {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
        "chi2_summary": float(m.group(1)), "df_summary": int(m.group(2)),
        "critico_summary": float(m.group(3)),
        "compatibile_summary": int(not verdict.upper().startswith("NON")),
        "verdetto_summary": verdict,
    }


def extract_delays(run, meta):
    """Delay di sortition per host e margine G della timer race (Def. 5.15)."""
    per_host, per_height = defaultdict(list), defaultdict(dict)
    setup = meta["setup_blocks"]
    for host, log_path in find_debug_logs(run["data"]):
        try:
            with log_path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "wPoA-sortition" not in line:
                        continue
                    m = DELAY_RE.search(line)
                    if not m:
                        continue
                    height, delay = int(m.group(1)), float(m.group(3))
                    if height <= setup:
                        continue
                    per_host[host].append(delay)
                    per_height[height][host] = delay
        except OSError as exc:
            LOG.warning("debug.log illeggibile %s: %s", log_path, exc)

    tbt, delta = meta["tbt"], meta["delta"] or 0.5
    dmax = delta * tbt
    band_lo, band_hi = tbt - dmax, tbt + dmax
    span = (band_hi - band_lo) or 1.0

    summary = {}
    for host, vals in per_host.items():
        mean = statistics.mean(vals)
        summary[host] = {
            "n": len(vals), "mean": round(mean, 3),
            "min": round(min(vals), 3), "max": round(max(vals), 3),
            "pos": round((mean - band_lo) / span, 4),
        }

    margins = sorted(sorted(d.values())[1] - sorted(d.values())[0]
                     for d in per_height.values() if len(d) >= 2)
    margin_row = None
    if margins:
        tiny = sum(1 for g in margins if g < 0.1)
        margin_row = {
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "rtt_max_ms": meta["rtt_max_ms"],
            "banda_dmax_s": round(dmax, 3),
            "round": len(margins),
            "G_medio_s": round(statistics.mean(margins), 4),
            "G_mediano_s": round(statistics.median(margins), 4),
            "G_min_s": round(margins[0], 4),
            "G_p05_s": round(margins[max(0, len(margins) // 20)], 4),
            "round_G_sotto_100ms": tiny,
            "frazione_G_sotto_100ms": round(tiny / len(margins), 4),
            "G_mediano_su_Dmax": round(statistics.median(margins) / dmax, 4) if dmax else "",
        }
    return summary, margin_row


def extract_epoch_view(meta, measured, traj, host_by_addr):
    """Quota osservata per epoca contro peso pubblicato per quella epoca.

    E' la tabella dell'asse 1 (dentro lo stesso esperimento): mostra se la
    distribuzione converge verso i pesi man mano che questi si stabilizzano.
    """
    if not measured or not traj:
        return []
    epoch_len = meta["epoch_len"] or 12
    per_epoch = defaultdict(Counter)
    for b in measured:
        epoch = b["height"] // epoch_len + 1
        if b.get("miner"):
            per_epoch[epoch][b["miner"]] += 1

    # peso pubblicato piu' recente con epoca <= e, per indirizzo
    by_addr = defaultdict(list)
    for rec in traj:
        if rec["epoca"] != "" and rec["peso"] is not None:
            by_addr[rec["address"]].append((rec["epoca"], rec["peso"]))
    for addr in by_addr:
        by_addr[addr].sort()

    def weight_at(addr, epoch):
        best = None
        for e, w in by_addr.get(addr, []):
            if e <= epoch:
                best = w
            else:
                break
        return best

    rows = []
    for epoch in sorted(per_epoch):
        counts = per_epoch[epoch]
        total = sum(counts.values())
        addrs = sorted(set(counts) | set(by_addr))
        weights = {a: (weight_at(a, epoch) or 0) for a in addrs}
        w_tot = sum(weights.values())
        for addr in addrs:
            if not weights[addr] and not counts.get(addr):
                continue
            rows.append({
                "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
                "epoca": epoch, "host": host_by_addr.get(addr, addr[:10]),
                "address": addr,
                "blocchi_epoca": counts.get(addr, 0),
                "quota_osservata_epoca": round(counts.get(addr, 0) / total, 5) if total else "",
                "peso_epoca": weights[addr],
                "quota_peso_epoca": round(weights[addr] / w_tot, 5) if w_tot else "",
                "W_tot_epoca": w_tot,
                "rapporto_Wtot_su_wi": round(w_tot / weights[addr], 3) if weights[addr] else "",
            })
    return rows


def extract_consistency(run, meta):
    """Fork: teste distinte a fine run, dal node_state.csv."""
    path = run["metrics"] / "node_state.csv"
    header, rows = read_csv_rows(path, has_header=True)
    if not rows:
        return None
    # header: host,height,besthash,hash_a_<N>,peers,balance -> per posizione,
    # perche' il nome della 4a colonna dipende dall'altezza della run.
    tips, deep, heights, divergent = Counter(), Counter(), [], []
    for row in rows:
        if len(row) < 6:
            continue
        host, height, besthash, deephash = row[0], as_int(row[1]), row[2], row[3]
        tips[besthash] += 1
        deep[deephash] += 1
        if height is not None:
            heights.append(height)
    if not tips:
        return None
    top_tip = tips.most_common(1)[0][0]
    for row in rows:
        if len(row) >= 3 and row[2] != top_tip:
            divergent.append(row[0])
    spread = (max(heights) - min(heights)) if heights else 0
    if len(tips) == 1:
        verdict = "nessun fork"
    elif spread <= 1 and len(deep) == 1:
        verdict = "ritardo di propagazione"
    elif len(deep) == 1:
        verdict = "corsa al tip"
    else:
        verdict = "fork persistente"
    return {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
        "nodi": len(rows), "teste_distinte": len(tips),
        "hash_sepolti_distinti": len(deep),
        "altezza_min": min(heights) if heights else "",
        "altezza_max": max(heights) if heights else "",
        "spread_altezze": spread,
        "host_divergenti": " ".join(divergent),
        "verdetto": verdict,
    }


def extract_gas(run, meta):
    """Distribuzione, rifornimenti e riconciliazione del GAS."""
    _, transfers = read_csv_rows(run["metrics"] / "gas_transfers.csv", has_header=False)
    init_total = refill_total = 0.0
    n_init = n_refill = 0
    for row in transfers:
        if len(row) < 4:
            continue
        kind, amount = row[1].strip(), as_float(row[3], 0.0) or 0.0
        if kind == "init":
            init_total += amount
            n_init += 1
        elif kind == "refill":
            refill_total += amount
            n_refill += 1

    header, recon = read_csv_rows(
        run["metrics"] / "reconciliation.csv",
        expected_cols=["height", "epoch", "miner", "balance", "sent"])
    per_miner, sent_total = Counter(), 0.0
    epochs = set()
    for row in recon:
        if len(row) < 5:
            continue
        miner, sent = row[2].strip(), as_float(row[4], 0.0) or 0.0
        per_miner[miner] += sent
        sent_total += sent
        e = as_int(row[1])
        if e is not None:
            epochs.add(e)

    treasury = rpc_result(run["metrics"] / "treasury_balance.json")
    treasury_qty = ""
    if isinstance(treasury, list) and treasury and isinstance(treasury[0], dict):
        treasury_qty = treasury[0].get("qty", "")

    row = {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
        "gas_distribuito_init": round(init_total, 4), "movimenti_init": n_init,
        "gas_rifornito": round(refill_total, 4), "rifornimenti": n_refill,
        "gas_riconciliato_totale": round(sent_total, 4),
        "epoche_con_riconciliazione": len(epochs),
        "saldo_treasury": treasury_qty,
    }
    for miner in ("m1", "m2", "m3"):
        row["riconciliato_%s" % miner] = round(per_miner.get(miner, 0.0), 4)
    return row


def extract_verify_and_malus(run, meta):
    verify = rpc_result(run["metrics"] / "verify.json")
    vrow = None
    if isinstance(verify, dict):
        entries = verify.get("entries") or []
        vrow = {
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "epoca": verify.get("epoch", ""),
            "verificato": int(bool(verify.get("verified"))),
            "record": verify.get("records", ""),
            "non_validi": verify.get("invalid", ""),
            "verdetti": " ".join(str(e.get("verdict", "?")) for e in entries),
        }
    malus = rpc_result(run["metrics"] / "malus.json")
    n_malus = len(malus) if isinstance(malus, list) else 0
    return vrow, n_malus


def extract_esg(run, meta, esg_by_host, cluster_by_host, addr_by_host):
    rows = []
    for host in sorted(esg_by_host):
        rows.append({
            "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
            "host": host, "address": addr_by_host.get(host, ""),
            "esg": esg_by_host[host], "cluster": cluster_by_host.get(host, ""),
        })
    return rows


# --------------------------------------------------------------------------
# orchestrazione
# --------------------------------------------------------------------------

TABLES = [
    "run_index", "block_times", "proposers", "chisq", "alternanze",
    "forks", "gas", "weights_trajectory", "epoch_shares",
    "sortition_margins", "esg", "verify",
]


def fingerprint(run):
    """Impronta della run: nomi, dimensioni e mtime dei file sorgente.

    Se non cambia, i risultati in cache sono ancora validi. E' una cache
    volutamente ingenua — correttezza prima di tutto: al minimo dubbio
    (`--force`, o impronta diversa) si ricalcola l'intera run.
    """
    parts = []
    for base in (run["metrics"], run["data"]):
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file() or is_noise(path):
                continue
            if path.name not in ("debug.log",) and path.parent != run["metrics"]:
                continue
            try:
                st = path.stat()
            except OSError:
                continue
            parts.append("%s:%d:%d" % (path.name, st.st_size, int(st.st_mtime)))
    return "|".join(parts)


def process_run(run, args):
    meta = extract_meta(run)
    result = {t: [] for t in TABLES}

    if not run["metrics"].is_dir():
        LOG.warning("%s: metrics/ assente, run saltata", run["run_id"])
        meta["stato"] = "incompleta"
        meta["note"] = "metrics/ assente"
        meta["malus_events_found"] = 0
        result["run_index"].append(meta)
        return result

    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = extract_host_maps(run)
    block_row, measured = extract_blocks(run, meta)
    traj, latest_weights = extract_weights(run, meta, host_by_addr)
    delays, margin_row = extract_delays(run, meta)
    prop_rows, alt_row, chi_row = extract_proposers(
        run, meta, measured, latest_weights, host_by_addr, delays)
    chi_summary = extract_chisq_from_summary(run, meta)
    fork_row = extract_consistency(run, meta)
    gas_row = extract_gas(run, meta)
    verify_row, n_malus = extract_verify_and_malus(run, meta)
    epoch_rows = extract_epoch_view(meta, measured, traj, host_by_addr)

    # Il chi-quadro autorevole e' quello di summary.txt; il ricalcolo entra
    # solo con --recompute-chisq, come controprova indipendente.
    chi_out = dict(chi_summary) if chi_summary else {
        "run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"],
        "chi2_summary": "", "df_summary": "", "critico_summary": "",
        "compatibile_summary": "", "verdetto_summary": "assente da summary.txt",
    }
    if args.recompute_chisq and chi_row:
        chi_out.update(chi_row)
        if chi_summary and chi_row:
            delta = abs(chi_row["chi2_ricalcolato"] - chi_summary["chi2_summary"])
            chi_out["scarto_ricalcolo"] = round(delta, 4)
            if delta > 0.05:
                LOG.warning("%s: chi-quadro summary %.3f vs ricalcolato %.3f",
                            meta["run_id"], chi_summary["chi2_summary"],
                            chi_row["chi2_ricalcolato"])
        if USING_SCIPY and chi_row.get("df"):
            chi_out["p_value"] = round(
                float(_scipy_stats.chi2.sf(chi_row["chi2_ricalcolato"], chi_row["df"])), 6)

    problems = []
    if not block_row:
        problems.append("blocchi insufficienti")
    if not prop_rows:
        problems.append("nessun proposer")
    if not traj:
        problems.append("traiettoria pesi vuota")
    if meta["tbt_mismatch"]:
        problems.append("tbt del nome cartella != params.dat")
    if meta.get("setup_mismatch"):
        problems.append("setup-first-blocks != setupblocks di getinfo")
    if not meta["params_trovato"]:
        problems.append("params.dat assente")

    meta["stato"] = "completa" if not problems else "parziale"
    meta["note"] = "; ".join(problems)
    meta["malus_events_found"] = n_malus
    meta["blocchi_misurati"] = block_row["blocchi_misurati"] if block_row else 0
    meta["fork_verdetto"] = fork_row["verdetto"] if fork_row else ""
    meta["path"] = str(run["path"])

    result["run_index"].append(meta)
    if block_row:
        result["block_times"].append(block_row)
    result["proposers"].extend(prop_rows)
    result["chisq"].append(chi_out)
    if alt_row:
        result["alternanze"].append(alt_row)
    if fork_row:
        result["forks"].append(fork_row)
    result["gas"].append(gas_row)
    result["weights_trajectory"].extend(traj)
    result["epoch_shares"].extend(epoch_rows)
    if margin_row:
        result["sortition_margins"].append(margin_row)
    result["esg"].extend(extract_esg(run, meta, esg_by_host, cluster_by_host, addr_by_host))
    if verify_row:
        result["verify"].append(verify_row)

    LOG.info("%s: %s | %d blocchi misurati | %d record di peso | %d malus | %s",
             meta["run_id"], meta["stato"], meta["blocchi_misurati"], len(traj),
             n_malus, meta["note"] or "nessun problema")
    return result


def write_table(out_dir, name, rows):
    path = out_dir / ("%s.csv" % name)
    if not rows:
        path.write_text("", encoding="utf-8")
        LOG.warning("tabella %s vuota", name)
        return
    fields = []
    for row in rows:
        for key in row:
            if key not in fields:
                fields.append(key)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)
    LOG.info("scritto %s (%d righe, %d colonne)", path.name, len(rows), len(fields))


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default="esperimenti",
                    help="cartella degli esperimenti (sola lettura)")
    ap.add_argument("--out", default="analisi",
                    help="cartella di output (unica scritta)")
    ap.add_argument("--recompute-chisq", action="store_true",
                    help="ricalcola il chi-quadro come controprova del valore in summary.txt")
    ap.add_argument("--force", action="store_true",
                    help="ignora la cache e ricalcola tutte le run")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.FileHandler(out_dir / "estrazione.log", mode="w",
                                      encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)])

    LOG.info("root=%s out=%s pandas=%s scipy=%s recompute_chisq=%s",
             root, out_dir, USING_PANDAS, USING_SCIPY, args.recompute_chisq)
    if not USING_PANDAS:
        LOG.info("pandas non installato: le tabelle sono scritte con il modulo csv "
                 "standard, lo schema dei file non cambia")

    runs = discover_runs(root)
    if not runs:
        LOG.error("nessuna run trovata: controlla --root")
        return 1

    inspect_schema(runs, out_dir)

    tables = {t: [] for t in TABLES}
    reused = 0
    for run in runs:
        cache_file = cache_dir / (run["run_id"].replace("/", "__") + ".json")
        fp = fingerprint(run)
        cached = None
        if not args.force and cache_file.exists():
            cached = read_json(cache_file)
            if cached and cached.get("fingerprint") == fp \
                    and cached.get("recompute_chisq") == bool(args.recompute_chisq):
                for name in TABLES:
                    tables[name].extend(cached["tables"].get(name, []))
                reused += 1
                LOG.info("%s: invariata, riuso la cache", run["run_id"])
                continue
        try:
            result = process_run(run, args)
        except Exception as exc:            # una run rotta non ferma le altre
            LOG.exception("%s: estrazione fallita (%s), run saltata",
                          run["run_id"], exc)
            tables["run_index"].append({
                "run_id": run["run_id"], "livello": run["livello"],
                "tbt": run["tbt_dirname"], "stato": "errore",
                "note": str(exc), "malus_events_found": "",
                "path": str(run["path"])})
            continue
        for name in TABLES:
            tables[name].extend(result[name])
        cache_file.write_text(json.dumps(
            {"fingerprint": fp, "recompute_chisq": bool(args.recompute_chisq),
             "tables": result}, ensure_ascii=False), encoding="utf-8")

    for name in TABLES:
        write_table(out_dir, name, tables[name])

    idx = tables["run_index"]
    n_malus = sum(1 for r in idx if as_int(r.get("malus_events_found"), 0))
    LOG.info("--- riepilogo ---")
    LOG.info("run totali %d (riusate dalla cache: %d)", len(idx), reused)
    for stato in ("completa", "parziale", "incompleta", "errore"):
        n = sum(1 for r in idx if r.get("stato") == stato)
        if n:
            LOG.info("  stato %-11s %d", stato, n)
    LOG.info("run con almeno un evento di malus registrato: %d su %d", n_malus, len(idx))
    if not n_malus:
        LOG.info("  -> nessun record sul registro dei malus in nessuna run: "
                 "il meccanismo del Cap. 5.11.3 non e' testato da questa campagna")
    mism = [r["run_id"] for r in idx if as_int(r.get("tbt_mismatch"), 0)]
    if mism:
        LOG.warning("run con tbt del nome cartella diverso da params.dat: %s",
                    ", ".join(mism))
    else:
        LOG.info("nessuna run anomala: il tbt del nome cartella coincide sempre "
                 "con quello sigillato in params.dat")
    LOG.info("output in %s", out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
