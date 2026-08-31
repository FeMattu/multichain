#!/usr/bin/env python3
"""
Estrazione, ricostruzione e verifica delle run Shadow in `esperimenti/`.

Esplora dinamicamente l'albero `<root>/runN-tbt-Ts/<livello>/run/metrics/`,
ispeziona lo schema reale di ogni file prima di leggerlo, rifa' da zero la
catena del peso del Cap. 6 e scrive in `--out` la struttura seguente:

    analisi/
      fogli-di-analisi/          tabelle globali (una riga per run o run x dim.),
                                 report di schema, log di estrazione
      esperimenti/<run>/<liv>/   mirror di `esperimenti/`: peso_riconciliazione,
                                 account_ledger, tabelle degli eventi,
                                 errori_integrita, disuguaglianza_pesi
      esperimenti/<run>/file-analisi-dati-di-tutti-gli-esp-in-area/
                                 confronto fra le aree della stessa run
      plots/                     grafici, scritti dalla sessione di analisi
      report_generale.md         scritto dalla sessione di analisi, non da qui

    python3 tools/analizza_esperimenti.py --root esperimenti/ --out analisi/
    python3 tools/analizza_esperimenti.py --root esperimenti/ --recompute-chisq
    python3 tools/analizza_esperimenti.py --root esperimenti/ --force

Questo script RACCOGLIE, RICOSTRUISCE, VERIFICA ARITMETICAMENTE e calcola i test
statistici. Non interpreta: l'interpretazione e' compito di una sessione
successiva, guidata da `analisi/PROMPT_ANALISI.md`.

Sola lettura su `--root`: `esperimenti/` non viene mai scritto ne' cancellato.
L'unico albero scritto e' `--out`. Il primo giro dopo la riorganizzazione
trasloca li' anche l'output della struttura precedente (le vecchie cartelle
`esperimenti/<run>/<livello>/dati/`), spostandolo invece di ricalcolarlo.

Il validatore Monte Carlo dell'algoritmo di elezione (Sez. 4.8) e' uno script a
se': `tools/valida_sortition_montecarlo.py`.

Dipendenze: sola libreria standard. pandas e scipy sono usati **se presenti**
(vedi USING_PANDAS / USING_SCIPY in testa a `estrazione.log`): scipy fornisce il
p-value di Spearman e del chi-quadro, senza di lui il coefficiente si calcola
comunque sui ranghi e il p-value resta dichiarato mancante, mai stimato.
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
    "weight-treasury-address", "wpoa-malus-mu", "wpoa-malus-max",
    "wpoa-malus-equiv-points", "wpoa-malus-delay-points",
    "wpoa-malus-selfwrite-points", "wpoa-malus-badweight-points",
    # La conversione GAS: `native-currency-multiple` e' il numero di unita'
    # grezze per unita' di visualizzazione. Le RPC (e quindi ogni CSV scritto
    # dall'harness) parlano in unita' di visualizzazione, cioe' gia' in GAS; a
    # richiedere la conversione sono i soli parametri di catena espressi in
    # unita' grezze, i due premi di mining qui sotto e minimum-relay-fee.
    "native-currency-multiple", "initial-block-reward",
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
            # Dalla riorganizzazione dell'output, dentro `runN-tbt-Ts/` vivono
            # anche cartelle che NON sono livelli geografici (il confronto fra
            # aree). Un livello e' tale solo se porta con se' `run/metrics/`.
            if not metrics.is_dir():
                LOG.debug("ignoro %s: non contiene run/metrics", level_dir.name)
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

    # Conversione GAS: letta run per run, mai hardcodata. Se params.dat manca il
    # campo resta vuoto e ogni riga che ne dipende (il premio di mining) viene
    # omessa invece che stimata.
    ncm = as_float(params.get("native-currency-multiple"))
    meta["native_currency_multiple"] = ncm if ncm is not None else ""
    meta["fonte_conversione_gas"] = (
        "params.dat di %s (native-currency-multiple)" % meta.get("params_da_host", "?")
        if ncm is not None else "non disponibile: nessun params.dat leggibile")
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
# ricostruzione della catena del peso (Cap. 6) e tabelle degli eventi
# --------------------------------------------------------------------------
#
# ORDINE DI COMPOSIZIONE DEL PESO. Il sorgente compone il peso in un ordine
# diverso da quello che si legge nella catena "peso pubblicato -> g(.) ->
# malus" della documentazione di progetto: il malus entra PRIMA dello
# smorzamento, non dopo.
#
#   w_k^e                pubblicato su wpoa-weights (intero)
#   w_eff = w_k * Psi^(e-1)   malus_registry.cpp: WPoAApplyMalus(weights, height),
#                        chiamato su tutta la mappa dei pesi (Def. 5.22) con Psi
#                        dell'epoca PRECEDENTE, prima di qualunque selezione
#   g(w_eff)             wpoa_selector.h: ApplyDumping(weight, dumping), applicata
#                        dal selettore al valore gia' corretto
#
# Con g non lineare g(w * Psi) != g(w) * Psi, quindi l'ordine conta appena una
# delle due leve e' attiva. In questa campagna sono entrambe inerti
# (dump-function = none, nessun record di malus) e i tre valori coincidono, ma
# le colonne seguono l'ordine del sorgente perche' una run con
# `dumpfunction = sqrt` o con malus attivi resti leggibile senza modifiche.

UPDATETX_RE = re.compile(r"UpdateTx ([0-9a-f]{8,}), block (-?\d+)")
NEWTX_RE = re.compile(r"NewTx ([0-9a-f]{64}), block (-?\d+)")

# Tabelle scritte dentro `<run>/<livello>/dati/`, accanto ai dati che descrivono.
PER_RUN_TABLES = ["peso_riconciliazione", "account_ledger", "gas_transfers",
                  "esg_publish", "membership_events", "traffic_events",
                  "tabellone_eventi", "errori_integrita", "disuguaglianza_pesi"]

# Il prefisso con cui txs.log abbrevia un txid nelle righe UpdateTx.
TXID_PREFIX_LEN = 10


def build_tx_index(run):
    """Indice delle conferme: prefisso del txid -> altezza del blocco che l'ha confermato.

    I CSV in `metrics/` registrano l'altezza al momento dell'INVIO della RPC, non
    quella di conferma: usarla per assegnare una transazione a un'epoca sbaglia
    sistematicamente al confine fra epoche, ed e' proprio al confine che il
    motore dei pesi cambia risultato. `data/<host>/txs.log` porta invece
    `UpdateTx <prefisso>, block <N>` con l'altezza reale.

    Restituisce anche i txid creati e mai confermati (`NewTx` senza `UpdateTx`
    con block >= 0): sono la firma di una transazione caduta — orfana o
    rifiutata dalla mempool — e sono l'unico modo di distinguere "il nodo ha
    riconciliato" da "il nodo ha provato a riconciliare".
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
                # Un nodo che riceve una transazione gia' dentro un blocco la
                # registra direttamente come NewTx con l'altezza: senza questo
                # ramo quelle transazioni risulterebbero "mai confermate".
                height = int(m.group(2))
                if height >= 0:
                    pre = m.group(1)[:TXID_PREFIX_LEN]
                    if pre not in conf or height < conf[pre]:
                        conf[pre] = height
    # Chi ha CREATO la transazione non e' deducibile da txs.log — un nodo la
    # registra sia quando la firma sia quando la riceve — quindi si riportano
    # tutti i nodi che l'hanno vista, senza attribuirne la paternita'.
    non_confermate = [(txid, sorted(hosts)) for txid, hosts in sorted(seen_new.items())
                      if txid[:TXID_PREFIX_LEN] not in conf]
    return conf, non_confermate


def _txs_logs(data_dir):
    """`txs.log` sta in `data/<host>/` o in `data/<host>/<chain>/`, come i debug.log."""
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
    """Altezza di conferma di un txid, o None se non e' mai stato confermato."""
    if not txid or len(txid) < TXID_PREFIX_LEN:
        return None
    return index.get(txid[:TXID_PREFIX_LEN])


def epoch_of(height, epoch_len):
    """epoca(h) = h // len + 1, la stessa mappa di HeightToEpoch nel sorgente."""
    if height is None or not epoch_len or epoch_len < 1:
        return None
    return int(height) // int(epoch_len) + 1


def apply_dumping(weight, dump_function):
    """g(.) di Def. 5.9, nella forma di wpoa_selector.h::ApplyDumping."""
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
    """w_eff = w * Psi, con l'arrotondamento e il pavimento di EffectiveWeight."""
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
    """host -> [(height, saldo)] ordinati: gas_balances.csv e' un CAMPIONE periodico
    scritto dal ciclo di rifornimento dell'admin, non un'istantanea per movimento."""
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
    """Primo campione di saldo a partire da `height`, o (None, None)."""
    for h, bal in samples.get(host, []):
        if h >= height:
            return h, bal
    return None, None


def extract_event_tables(run, meta, maps, txindex):
    """Le quattro tabelle relazionali degli eventi, piu' il tabellone denormalizzato.

    Fonte di verita': le tabelle separate. Il tabellone e' una vista di comodo
    per filtrare rapidamente su un singolo host senza incrociare quattro file.
    """
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    epoch_len = meta["epoch_len"]
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    out = {name: [] for name in PER_RUN_TABLES}

    # --- traffico di filiera: la fonte diretta di tau_i --------------------
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

    # --- pubblicazioni ESG (stream chiuso, solo la CA delegata) ------------
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

    # --- adesioni ai cluster (auto-attestate) ------------------------------
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

    # --- movimenti di GAS: init/refill dall'admin + riconciliazioni --------
    #
    # LIMITE DICHIARATO. `gas_transfers.csv` non porta il txid, quindi per
    # init/refill l'altezza e' quella di INVIO e la conferma non e'
    # dimostrabile; `gas_balances.csv` e' un campione periodico e non contiene
    # affatto l'admin, quindi il saldo del mittente dopo un init/refill non e'
    # ricostruibile. Le colonne restano, con la fonte dichiarata riga per riga.
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
        # La transazione entra in mempool all'altezza registrata e viene
        # confermata nel blocco successivo: modello validato sulle run (vedi
        # verifica_riconciliazione.log). Non e' una conferma dimostrata.
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

    # --- tabellone denormalizzato (vista di comodo) -----------------------
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
    """I record di wpoa-weights con l'altezza REALE in cui sono diventati leggibili.

    Il campo `height` dentro il payload e' l'altezza che il publisher aveva in
    mano quando ha costruito il record; quella che conta per la selezione e'
    l'altezza in cui la transazione e' stata confermata, perche' prima di quel
    blocco nessun altro nodo puo' leggere il peso.
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
    """Per ogni blocco misurato, la quota attesa di ciascun miner con il peso VIGENTE.

    Un blocco all'altezza h e' proposto leggendo la mappa dei pesi alla punta
    h-1: valgono quindi i soli record confermati prima di h. Legare invece i
    blocchi dell'epoca e al record marcato `epoch=e` sarebbe sbagliato, perche'
    il motore pubblica il peso dell'epoca e a epoca gia' finita — il record
    marcato e entra in vigore dentro l'epoca e+1.
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


def compute_weight_reconciliation(run, meta, maps, events, txindex, blocks, window):
    """La tabella di riconciliazione del peso: una riga per (epoca, miner).

    Rifa' la catena del Cap. 6 dagli input pubblici — adesioni, ESG, attivita'
    tau e riconciliazione R lette dai blocchi dell'epoca — e la confronta con il
    peso davvero pubblicato su wpoa-weights. E' la verifica della Sez. 5.11.1
    (ricalcolabilita') fatta epoca per epoca invece che solo sull'ultima.
    """
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    epoch_len = meta["epoch_len"]
    kappa = as_float(meta.get("weight_kappa"), 100.0) or 100.0
    alpha = as_float(meta.get("weight_alpha"), 0.2)
    lam = as_float(meta.get("weight_lambda"), 0.5)
    mu = as_float(meta.get("wpoa_malus_mu"), 0.5)
    m_max = as_float(meta.get("wpoa_malus_max"), 4.0)
    dump_fn = (str(meta.get("dump_function") or "none")).strip().lower() or "none"
    log = []

    # --- input statici: cluster, ESG e l'epoca da cui sono leggibili -------
    cluster_addr, memb_epoch = {}, {}
    for rec in events["membership_events"]:
        addr, miner = rec["indirizzo"], rec["miner_indirizzo"]
        if not addr or not miner:
            continue
        cluster_addr.setdefault(miner, set())
        if addr != miner:                       # il miner non e' azienda di se stesso
            cluster_addr[miner].add(addr)
        memb_epoch[addr] = min(memb_epoch.get(addr, 10 ** 9), rec["epoca"] or 10 ** 9)
    esg_addr, esg_epoch = {}, {}
    for rec in events["esg_publish"]:
        addr = rec["indirizzo_certificato"]
        val = as_float(rec["esg_score"])
        if not addr or val is None:
            continue
        esg_addr[addr] = val
        esg_epoch[addr] = min(esg_epoch.get(addr, 10 ** 9), rec["epoca"] or 10 ** 9)

    # --- input derivati dai blocchi: tau (attivita') e R (riconciliazione) --
    tau = Counter()
    for rec in events["traffic_events"]:
        if rec["esito"] == "ok" and rec["epoca"]:
            tau[(rec["indirizzo"], rec["epoca"])] += 1
    for rec in events["esg_publish"] + events["membership_events"]:
        pub = rec.get("publisher_indirizzo") or rec.get("indirizzo")
        if pub and rec["epoca"]:
            tau[(pub, rec["epoca"])] += 1
    wrecs = _weight_records(run, txindex)
    for rec in wrecs:
        ep = epoch_of(rec["height_conferma"], epoch_len)
        if ep:
            tau[(rec["address"], ep)] += 1
    reconciled = Counter()
    for rec in events["gas_transfers"]:
        if rec["tipo"] != "reconcile" or not rec["epoca"]:
            continue
        amount = as_float(rec["importo_gas"], 0.0) or 0.0
        if amount <= 0:
            continue                            # sent=0: nessuna transazione emessa
        tau[(rec["indirizzo_mittente"], rec["epoca"])] += 1
        reconciled[(rec["indirizzo_mittente"], rec["epoca"])] += amount

    # --- malus: accumulatore M e correzione Psi, per epoca -----------------
    malus_points = Counter()
    n_malus_rec = 0
    for item in (rpc_result(run["metrics"] / "malus.json") or []):
        n_malus_rec += 1                        # nessuna run di questa campagna ne ha
    psi_by_epoch, malus_by_epoch = {}, {}

    published, pub_height = {}, {}
    for rec in wrecs:
        if rec["epoca"] is not None:
            published[(rec["address"], rec["epoca"])] = rec["peso"]
            pub_height[(rec["address"], rec["epoca"])] = rec["height_conferma"]

    miners = sorted(cluster_addr) or sorted({a for a, _e in published})
    max_epoch = max([e for _a, e in published] +
                    [epoch_of(b["height"], epoch_len) or 1 for b in blocks] + [1])

    # --- il fold in avanti, epoca per epoca (weight_engine.h::ComputeEpoch) -
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

    # --- quote osservate e attese, con il peso VIGENTE blocco per blocco ---
    per_block = _inforce_shares(wrecs, blocks, meta["setup_blocks"], dump_fn,
                                psi_by_epoch, epoch_len, m_max)
    exp_ep, obs_ep, tot_ep = defaultdict(Counter), defaultdict(Counter), Counter()
    for h, miner_addr, shares, _stamps in per_block:
        e = epoch_of(h, epoch_len)
        tot_ep[e] += 1
        if miner_addr:
            obs_ep[e][miner_addr] += 1
        for a, q in shares.items():
            exp_ep[e][a] += q

    def chi_over(epochs):
        obs, exp = Counter(), Counter()
        n = 0
        for e in epochs:
            n += tot_ep[e]
            obs.update(obs_ep[e])
            for a, v in exp_ep[e].items():
                exp[a] += v
        if n == 0 or not exp:
            return None
        addrs = sorted(exp)
        chi = sum((obs[a] - exp[a]) ** 2 / exp[a] for a in addrs if exp[a] > 0)
        df = max(len(addrs) - 1, 1)
        return {"chi2": chi, "df": df, "n": n,
                "critico": CHI2_CRIT_05.get(df, ""),
                "attesa_min": min(exp[a] for a in addrs),
                "obs": obs, "exp": exp}

    # --- righe: una per (epoca, miner) ------------------------------------
    rows = []
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    n_scarti = 0
    for e in range(1, max_epoch + 1):
        snapshot = {}
        for m in miners:
            best = None
            for (a, ee), w in published.items():
                if a == m and ee <= e and (best is None or ee > best[0]):
                    best = (ee, w)
            if best:
                psi = psi_by_epoch.get((m, e - 1), 1.0)
                snapshot[m] = apply_dumping(effective_after_malus(best[1], psi), dump_fn)
        w_tot = sum(snapshot.values())
        ce = chi_over([e])
        cw = chi_over(range(max(1, e - window + 1), e + 1))
        for m in miners:
            d = derived.get((m, e))
            if d is None:
                continue
            pubw = published.get((m, e))
            psi = psi_by_epoch.get((m, e - 1), 1.0)
            after_malus = effective_after_malus(pubw, psi) if pubw is not None else ""
            efficace = apply_dumping(after_malus, dump_fn) if pubw is not None else ""
            scarto = (d["int_weight"] - pubw) if pubw is not None else ""
            if pubw is None:
                esito = "non pubblicato in questa epoca"
            elif scarto == 0:
                esito = "esatto"
            else:
                esito = "scostamento"
                n_scarti += 1
                log.append(
                    "  epoca %-4d %-4s pubblicato=%-10s ricalcolato=%-10s scarto=%+d  "
                    "(rho^(e-1) usata dal motore = %.4f contro %.4f ricalcolata)"
                    % (e, host_by_addr.get(m, m[:8]), pubw, d["int_weight"], scarto,
                       (pubw / (d["raw"] * kappa) - (1 - lam)) / lam
                       if d["raw"] > 0 and lam > 0 else float("nan"),
                       d["rho_prev"] if isinstance(d["rho_prev"], float) else float("nan")))
            # Le liste per azienda sono ordinate per NOME host, non per indirizzo:
            # gli indirizzi sono generati per nodo e cambiano da un livello
            # all'altro, quindi ordinarci sopra renderebbe due liste identiche
            # testualmente diverse e falserebbe ogni confronto fra aree.
            parts = sorted(d["contrib"], key=lambda t: host_by_addr.get(t[0], t[0]))
            row = dict(base)
            row.update({
                "epoca": e, "host": host_by_addr.get(m, m[:10]), "indirizzo": m,
                "esg_miner": round(d["esg_miner"], 4),
                "esg_cluster_medio": round(
                    sum(p[1] for p in parts) / len(parts), 4)
                    if parts else "",
                "esg_cluster_lista": ",".join(
                    "%s:%.2f" % (host_by_addr.get(p[0], p[0][:6]), p[1]) for p in parts),
                "attivita_miner_tau": d["tau_miner"],
                "attivita_cluster_tau_somma": sum(p[2] for p in parts),
                "attivita_cluster_tau_lista": ",".join(
                    "%s:%d" % (host_by_addr.get(p[0], p[0][:6]), p[2]) for p in parts),
                "contributi_c_i_lista": ",".join(
                    "%s:%.4f" % (host_by_addr.get(p[0], p[0][:6]), p[3]) for p in parts),
                "theta_epoca": d["theta"],
                "peso_grezzo_epoca": round(d["raw"], 6),
                "allocazione_A_k": round(d["alloc"], 6),
                "saldo_B_precedente": round(d["balance_prev"], 6),
                "saldo_B_epoca": round(d["balance"], 6),
                "riconciliato_R_k": round(d["reconciled"], 4),
                "rho_epoca": round(d["rho"], 6),
                "rho_epoca_precedente": round(d["rho_prev"], 6)
                                        if isinstance(d["rho_prev"], float) else "",
                "peso_pubblicato_epoca": pubw if pubw is not None else "",
                "peso_pubblicato_ricalcolato": d["int_weight"],
                "scarto_ricalcolo": scarto,
                "esito_ricalcolo": esito,
                "height_pubblicazione": pub_height.get((m, e), ""),
                "malus_accumulatore_epoca": round(d["malus"], 6),
                "fattore_correzione_malus": round(psi, 6),
                "peso_dopo_malus": after_malus,
                "dump_function_usata": dump_fn,
                "peso_efficace_epoca": efficace,
                "peso_effettivo_epoca": efficace,
                "W_tot_epoca": round(w_tot, 4) if w_tot else "",
                "quota_peso_epoca": round(snapshot.get(m, 0.0) / w_tot, 6) if w_tot else "",
                "blocchi_minati_epoca": obs_ep[e][m],
                "blocchi_totali_epoca": tot_ep[e],
                "quota_osservata_epoca": round(obs_ep[e][m] / tot_ep[e], 6)
                                          if tot_ep[e] else "",
                "quota_attesa_vigenza": round(exp_ep[e][m] / tot_ep[e], 6)
                                         if tot_ep[e] else "",
            })
            row["scostamento_quota"] = (
                round(row["quota_osservata_epoca"] - row["quota_attesa_vigenza"], 6)
                if tot_ep[e] else "")
            row.update({
                "chi2_epoca": round(ce["chi2"], 4) if ce else "",
                "df_epoca": ce["df"] if ce else "",
                "chi2_critico_5pct": ce["critico"] if ce else "",
                "compatibile_epoca": (int(ce["chi2"] <= ce["critico"])
                                      if ce and ce["critico"] else ""),
                "attesa_minima_epoca": round(ce["attesa_min"], 3) if ce else "",
                "campione_sufficiente_epoca": int(ce["attesa_min"] >= 5) if ce else "",
                "finestra_epoche": window,
                "blocchi_finestra": cw["n"] if cw else "",
                "chi2_finestra": round(cw["chi2"], 4) if cw else "",
                "df_finestra": cw["df"] if cw else "",
                "compatibile_finestra": (int(cw["chi2"] <= cw["critico"])
                                         if cw and cw["critico"] else ""),
                "attesa_minima_finestra": round(cw["attesa_min"], 3) if cw else "",
                "campione_sufficiente_finestra": int(cw["attesa_min"] >= 5) if cw else "",
            })
            rows.append(row)
    return rows, log, n_scarti, n_malus_rec


VERIFICA_HEADER = """# verifica della ricalcolabilita' del peso (Sez. 5.11.1), epoca per epoca
#
# Ogni riga di peso_riconciliazione.csv ricostruisce w_k^(e) dai soli input
# pubblici — adesioni, ESG, attivita' tau e riconciliazione R lette dai blocchi
# dell'epoca — e lo confronta con il valore davvero pubblicato su wpoa-weights.
#
# MODELLO DELLA RICONCILIAZIONE. reconciliation.csv registra l'altezza di INVIO
# della RPC, non quella di conferma, e non porta il txid: la transazione viene
# quindi attribuita al blocco successivo (height + 1). E' un modello, non un
# fatto misurato. Dove il modello sbaglia — una riconciliazione accettata in
# mempool ma poi caduta come orfana, per esempio — il peso ricalcolato diverge
# da quello pubblicato, e la riga finisce qui sotto.
#
# Uno scarto NON dimostra da solo che il protocollo abbia violato la
# ricalcolabilita': il verificatore interno di ogni nodo
# (weightverifyweights / weight_verifier.h) ricalcola gli stessi pesi dai
# blocchi veri e il suo esito e' in verify.csv. Le due verifiche vanno lette
# insieme: e' la discordanza fra loro a essere significativa.
"""


def write_per_run_outputs(mirror, run, payload, log_lines, unconfirmed):
    """Scrive `analisi/esperimenti/<run>/<livello>/`, mirror di `esperimenti/`.

    L'albero `esperimenti/` resta di sola lettura per intero: il dettaglio
    per-esperimento vive sotto `analisi/`, nella stessa posizione relativa, cosi'
    che il percorso di una tabella di analisi si ricavi da quello dei dati che
    descrive semplicemente cambiando la radice.
    """
    out_dir = mirror / run["run_dir"] / run["livello"]
    out_dir.mkdir(parents=True, exist_ok=True)
    for name in PER_RUN_TABLES:
        write_table(out_dir, name, payload.get(name, []))
    lines = [VERIFICA_HEADER]
    if log_lines:
        lines.append("## righe in cui il peso ricalcolato non torna (%d)\n" % len(log_lines))
        lines.extend(log_lines)
    else:
        lines.append("## nessuno scarto: ogni peso pubblicato e' stato riprodotto "
                     "esattamente dai suoi input dichiarati\n")
    if unconfirmed:
        lines.append("\n## transazioni viste e mai confermate (da data/<host>/txs.log)")
        lines.append("# Una transazione caduta — orfana o rifiutata dalla mempool — e' la "
                     "causa piu' comune di uno scarto: l'harness la registra come "
                     "inviata, la catena non l'ha mai messa in un blocco. I nodi "
                     "elencati sono quelli che l'hanno VISTA, non necessariamente "
                     "quello che l'ha firmata: txs.log non distingue i due casi.")
        for txid, hosts in unconfirmed[:20]:
            lines.append("  %s  vista da: %s" % (txid, ", ".join(hosts)))
        if len(unconfirmed) > 20:
            lines.append("  (%d transazioni non elencate)" % (len(unconfirmed) - 20))
    else:
        lines.append("\n## nessuna transazione caduta: ogni transazione vista dai nodi "
                     "e' finita in un blocco")
    (out_dir / "verifica_riconciliazione.log").write_text(
        "\n".join(lines) + "\n", encoding="utf-8")
    return out_dir


def write_area_comparison(mirror, run_dir_name, per_level):
    """`runN-tbt-Ts/file-analisi-dati-di-tutti-gli-esp-in-area/`: confronto fra le
    quattro aree della STESSA run.

    L'attesa di partenza e' che a parita' di run cambi solo la latenza — ESG e
    adesioni sono identici per costruzione — e che quindi la traiettoria del
    peso coincida fra i livelli, restando legittimamente diversa la sola quota
    osservata. La misura la smentisce, e per un motivo strutturale: tau conta le
    transazioni confermate in una FINESTRA DI DODICI BLOCCHI, mentre il traffico
    e' generato a tempo reale. Un'epoca dura piu' secondi dove i blocchi sono
    piu' lenti, quindi ci cadono dentro piu' transazioni: cambia tau, cambia
    W_k, cambia il peso. Non e' un difetto dei dati, e' la latenza che entra nel
    peso attraverso il throughput.

    Il riepilogo distingue quindi le due cause: divergenze con ESG identico e
    tau diverso (canale latenza -> throughput -> attivita', atteso) e divergenze
    con ESG diverso (quelle si', anomalie nei dati: seed o certificazione non
    riprodotti).
    """
    out_dir = mirror / run_dir_name / "file-analisi-dati-di-tutti-gli-esp-in-area"
    out_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    for livello in sorted(per_level):
        rows.extend(per_level[livello])
    write_table(out_dir, "confronto_aree_peso", rows)

    by_key = defaultdict(dict)
    for r in rows:
        by_key[(r["epoca"], r["host"])][r["livello"]] = r
    livelli = sorted({r["livello"] for r in rows})

    div_attivita, div_esg, uguali = [], [], 0
    for key, per_liv in by_key.items():
        pesi = {l: r["peso_pubblicato_epoca"] for l, r in per_liv.items()
                if r["peso_pubblicato_epoca"] != ""}
        if len(set(pesi.values())) <= 1:
            uguali += 1
            continue
        esg = {(r["esg_miner"], r["esg_cluster_lista"]) for r in per_liv.values()}
        (div_esg if len(esg) > 1 else div_attivita).append(key)
    divergenti = sorted(div_attivita + div_esg)

    md = ["# Confronto fra aree — %s\n" % run_dir_name,
          "Livelli confrontati: %s.\n" % ", ".join(livelli),
          "## Traiettoria del peso\n",
          "L'attesa di partenza e' che il peso **non** dipenda dall'area: a parita' di",
          "run gli ESG certificati e le adesioni ai cluster sono identici per",
          "costruzione, e cambia solo la latenza. La misura la smentisce, e il motivo",
          "e' strutturale: `tau` conta le transazioni confermate in una finestra di",
          "dodici **blocchi**, mentre il traffico e' generato a **tempo reale**. Dove i",
          "blocchi sono piu' lenti l'epoca dura piu' secondi e ci cadono dentro piu'",
          "transazioni: cambia `tau`, cambia `W_k`, cambia il peso pubblicato. La",
          "latenza entra quindi nel peso, ma per la via del throughput, non del",
          "protocollo di selezione.\n",
          "Le divergenze vanno percio' separate in due famiglie:\n",
          "| famiglia | coppie (epoca, host) | lettura |",
          "|---|---|---|",
          "| peso identico fra i livelli | %d | nessuna divergenza da spiegare |" % uguali,
          "| peso diverso, **ESG identico**, `tau` diverso | %d | atteso: canale "
          "latenza -> throughput -> attivita' |" % len(div_attivita),
          "| peso diverso, **ESG diverso** | %d | anomalia nei dati: seed o "
          "certificazione ESG non riprodotti |" % len(div_esg),
          ""]
    if div_esg:
        md.append("Le %d coppie con ESG diverso sono elencate per prime nella tabella"
                  " qui sotto e vanno indagate: **non** sono spiegabili con la"
                  " latenza.\n" % len(div_esg))
    else:
        md.append("**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e"
                  " le adesioni sono state riprodotte identiche in tutte le aree, e"
                  " ogni divergenza di peso e' riconducibile alla sola attivita'"
                  " misurata.\n")

    md.append("## Divergenze di peso, con l'attivita' che le spiega\n")
    if not divergenti:
        md.append("Nessuna divergenza.\n")
    else:
        md.append("| epoca | host | causa | " +
                  " | ".join("%s (peso / tau cluster)" % l for l in livelli) + " |")
        md.append("|---|---|---|" + "---|" * len(livelli))
        ordinate = div_esg + [k for k in sorted(div_attivita)]
        for key in ordinate[:40]:
            causa = "ESG diverso" if key in div_esg else "tau diverso"
            celle = []
            for l in livelli:
                r = by_key[key].get(l)
                celle.append("%s / %s" % (r["peso_pubblicato_epoca"] or "—",
                                          r["attivita_cluster_tau_somma"])
                             if r else "—")
            md.append("| %s | %s | %s | %s |" % (key[0], key[1], causa, " | ".join(celle)))
        if len(ordinate) > 40:
            md.append("\n(%d righe non elencate: il dettaglio e' in "
                      "`confronto_aree_peso.csv`)" % (len(ordinate) - 40))

    md.append("\n## Quota osservata per epoca\n")
    md.append("Qui la differenza fra livelli e' invece **legittima e attesa**: e'"
              " l'effetto della latenza sulla corsa dei timer, a parita' di peso"
              " vigente. Le epoche della fase di setup non hanno blocchi misurati e"
              " sono omesse.\n")
    md.append("| epoca | host | " + " | ".join(livelli) + " | spread |")
    md.append("|---|---|" + "---|" * (len(livelli) + 1))
    n_quote = 0
    for key in sorted(by_key):
        vals = [as_float(by_key[key][l]["quota_osservata_epoca"])
                if l in by_key[key] else None for l in livelli]
        noti = [v for v in vals if v is not None]
        if not noti:
            continue
        n_quote += 1
        if n_quote > 60:
            continue
        spread = (max(noti) - min(noti)) if len(noti) > 1 else 0.0
        md.append("| %s | %s | %s | %.3f |" % (
            key[0], key[1],
            " | ".join("%.3f" % v if v is not None else "—" for v in vals), spread))
    if n_quote > 60:
        md.append("\n(%d righe non elencate: il dettaglio completo e' in "
                  "`confronto_aree_peso.csv`)" % (n_quote - 60))
    (out_dir / "confronto_aree_riepilogo.md").write_text(
        "\n".join(md) + "\n", encoding="utf-8")
    return out_dir, len(div_esg)



# --------------------------------------------------------------------------
# Sez. 4.3 - bilancio GAS per nodo (account_ledger.csv)
# --------------------------------------------------------------------------
#
# UNITA'. Ogni colonna monetaria di ogni tabella e' in GAS, cioe' nell'unita' di
# VISUALIZZAZIONE della valuta nativa. Le RPC di MultiChain (`getbalance`,
# `send`, `listassets`) parlano gia' in unita' di visualizzazione, quindi i CSV
# scritti dall'harness — `gas_balances.csv`, `gas_transfers.csv`,
# `reconciliation.csv`, la colonna `balance` di `node_state.csv`, `qty` di
# `treasury_balance.json` — sono GAS e non richiedono conversione. Richiedono
# conversione i soli PARAMETRI di catena, che `params.dat` esprime in unita'
# grezze: `first-block-reward`, `initial-block-reward`, `minimum-relay-fee`.
# Il fattore e' `native-currency-multiple`, letto da params.dat run per run e
# riportato in run_index.csv insieme alla sua fonte: non e' mai hardcodato.

GAS_EPS = 1e-6

# Tipi di movimento del registro dei conti (Sez. 4.3).
LEDGER_KINDS = ("init", "refill", "reconcile", "mining_reward", "fee", "altro")


def resolve_special_addresses(run, maps):
    """Indirizzi di `admin` e `ca`, che non compaiono in `esg_scores.csv`.

    `esg_scores.csv` elenca i soli nodi certificati (miner e aziende): admin e
    ca movimentano GAS ma non hanno peso, quindi i loro indirizzi vanno presi
    altrove. `ca` e' il publisher dello stream ESG (stream chiuso: scrive solo
    la CA delegata); `admin` e' l'unico indirizzo con permesso di mining che non
    sia un miner con peso — ed e' un fatto rilevante di per se', perche' rende
    verificabile il Cor. 5.4 su un nodo che POTREBBE minare e non lo fa mai.
    """
    addr_by_host, host_by_addr, _esg, _cluster = maps
    out = {}
    for item in (rpc_result(run["metrics"] / "esg.json") or []):
        pubs = (item or {}).get("publishers") or []
        if pubs:
            out["ca"] = pubs[0]
            break
    known = set(addr_by_host.values()) | {out.get("ca", "")}
    for item in (rpc_result(run["metrics"] / "permissions_mine.json") or []):
        addr = (item or {}).get("address")
        if addr and addr not in known:
            out["admin"] = addr
            break
    return out


def _final_balances(run):
    """host -> saldo GAS a fine run, da node_state.csv. E' l'unica misura del
    saldo dell'admin, che il campionamento di gas_balances.csv non copre."""
    out = {}
    _h, rows = read_csv_rows(run["metrics"] / "node_state.csv", has_header=True)
    for row in rows:
        if len(row) < 6:
            continue
        bal = as_float(row[5])
        if bal is not None:
            out[row[0].strip()] = bal
    return out


def build_account_ledger(run, meta, maps, events, blocks, specials):
    """Un movimento per riga, per ogni nodo, admin e ca inclusi (Sez. 4.3).

    Tre famiglie di righe, con provenienza diversa e dichiarata:

    * `init` / `refill` / `reconcile` — **[M]**: l'importo e' letto da
      `gas_transfers.csv` e `reconciliation.csv`. L'altezza e' quella di INVIO
      della RPC (la conferma non e' dimostrabile: quei CSV non portano il txid),
      tranne per `reconcile`, dove si usa il modello height+1 gia' adottato
      altrove nella pipeline.
    * `mining_reward` — **[I]**: ricostruito da `blocks.json` x il premio di
      catena letto da `params.dat` (`first-block-reward` per il blocco 1,
      `initial-block-reward` per i successivi), convertito in GAS. Non e'
      registrato da nessuna metrica: in questa campagna il premio per blocco e'
      zero e l'unica riga e' il premine del blocco 1.
    * `fee` — **[I]**: il RESIDUO fra due campioni consecutivi di
      `gas_balances.csv` una volta tolti i movimenti noti. Nessuna metrica
      registra la fee di una singola transazione (dipende dalla dimensione in
      byte, non dal solo `minimum-relay-fee`), quindi la fee non e' attribuibile
      a una transazione: e' attribuibile all'intervallo fra due campioni, ed e'
      cosi' che viene riportata. Il segno distingue chi paga (azienda che
      pubblica) da chi incassa (miner che include il blocco).

    Il residuo chiude il registro per costruzione: `saldo_gas_dopo` coincide con
    il campione misurato a ogni altezza campionata, e la riga finale lo riporta
    sul saldo di fine run di `node_state.csv`. E' questo che rende
    `coerente_con_saldo` una verifica vera e non una tautologia: un saldo
    negativo in un punto qualsiasi della sequenza e' un dato certamente
    sbagliato, non un artefatto del modello.
    """
    addr_by_host, host_by_addr, _esg, _cluster = maps
    epoch_len = meta["epoch_len"]
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    ncm = as_float(meta.get("native_currency_multiple"), 0.0) or 0.0
    treasury = meta.get("weight_treasury_address", "")

    addr_of = dict(addr_by_host)
    addr_of.update(specials)
    host_of = {a: h for h, a in addr_of.items()}

    moves = defaultdict(list)      # host -> [(height, tipo, importo, controparte, motivo, rif)]

    for rec in events["gas_transfers"]:
        amount = as_float(rec.get("importo_gas"))
        if amount is None:
            continue
        tipo = rec.get("tipo", "altro")
        if tipo == "reconcile":
            h = as_int(rec.get("height_conferma"))
            if h is None:
                h = as_int(rec.get("height"))
            # `reconciliation.csv` porta il saldo che il MINER stesso ha letto con
            # getbalance subito prima di inviare: e' la misura piu' autorevole del
            # suo saldo, piu' del campione periodico dell'admin, che e' preso in
            # un altro istante dello stesso blocco. Viene usata come ancora.
            moves[rec["nodo_mittente"]].append(
                (h, "reconcile", -amount, "treasury",
                 "riconciliazione al treasury: e' la R_k dell'epoca (Def. 6.7)", "",
                 as_float(rec.get("saldo_mittente_prima"))))
            continue
        h = as_int(rec.get("height"))
        moves[rec["nodo_destinatario"]].append(
            (h, tipo, amount, "admin",
             "dotazione iniziale" if tipo == "init" else "rifornimento sotto soglia",
             "", None))
        moves["admin"].append(
            (h, tipo, -amount, rec["nodo_destinatario"],
             "l'admin finanzia %s" % rec["nodo_destinatario"], "", None))

    # --- premio di mining: ricostruito, mai misurato ----------------------
    first_reward = as_float(meta.get("first_block_reward"))
    per_block_reward = as_float(meta.get("initial_block_reward"), 0.0) or 0.0
    n_reward = 0
    if ncm > 0:
        for blk in blocks:
            h = blk.get("height")
            raw = first_reward if h == 1 else per_block_reward
            if raw is None or raw <= 0:
                continue
            host = host_of.get(blk.get("miner"), blk.get("miner", "")[:10])
            moves[host].append((h, "mining_reward", raw / ncm, "coinbase",
                                "premio di catena del blocco %s, ricostruito da "
                                "params.dat (nessuna metrica lo registra)" % h,
                                blk.get("hash", ""), None))
            n_reward += 1

    # --- residuo per intervallo campionato: le fee ------------------------
    samples = _gas_balance_samples(run)
    finali = _final_balances(run)
    rows = []
    for host in sorted(set(moves) | set(samples) | set(finali)):
        seq = sorted(moves.get(host, []),
                     key=lambda t: (t[0] if t[0] is not None else 10 ** 9))
        campioni = samples.get(host, [])
        running = 0.0
        idx = 0
        out_rows = []

        def anchor(height, saldo, motivo):
            """Riporta il saldo modellato su un saldo MISURATO, emettendo la
            differenza come residuo di fee. Senza questo passo il registro
            oscillerebbe: `gas_transfers.csv` porta l'altezza di INVIO e
            `gas_balances.csv` e' un campione preso in un altro istante dello
            stesso blocco, quindi le due fonti si incrociano fuori ordine."""
            nonlocal running
            if saldo is None:
                return
            residuo = saldo - running
            if abs(residuo) > GAS_EPS:
                emit(height, "fee", residuo, "rete (fee di blocco)", motivo, "")

        def emit(height, tipo, amount, controparte, motivo, rif, saldo_misurato=None):
            anchor(height, saldo_misurato,
                   "residuo verso il saldo che il nodo stesso ha letto subito prima "
                   "di spendere: chiude lo scarto fra le due fonti di saldo")
            nonlocal running
            running += amount
            out_rows.append({
                "height": height if height is not None else "",
                "epoca": epoch_of(height, epoch_len) or "",
                "nodo": host,
                "indirizzo": addr_of.get(host, ""),
                "tipo_movimento": tipo,
                "importo_gas": round(amount, 6),
                "controparte": controparte,
                "motivo": motivo,
                "saldo_gas_dopo": round(running, 6),
                "txid_o_riferimento": rif,
                "coerente_con_saldo": int(running >= -GAS_EPS),
            })

        for h_camp, bal_camp in campioni:
            while idx < len(seq) and (seq[idx][0] is not None and seq[idx][0] <= h_camp):
                emit(*seq[idx])
                idx += 1
            anchor(h_camp, bal_camp,
                   "residuo fra il campione precedente e questo, una volta tolti i "
                   "movimenti noti: e' la fee pagata (segno -) o incassata (segno +) "
                   "nell'intervallo, non attribuibile a una singola transazione")
        while idx < len(seq):
            emit(*seq[idx])
            idx += 1
        anchor(max([b["height"] for b in blocks] or [0]), finali.get(host),
               "residuo fino al saldo di fine run letto da node_state.csv: per "
               "l'admin e' l'unica misura disponibile, gas_balances.csv non lo campiona")
        for row in out_rows:
            r = dict(base)
            r.update(row)
            rows.append(r)
    rows.sort(key=lambda r: (r["nodo"], as_int(r["height"], 10 ** 9)))
    return rows, n_reward


# --------------------------------------------------------------------------
# Sez. 4.6 - concentrazione del peso (disuguaglianza_pesi.csv)
# --------------------------------------------------------------------------

def gini(values):
    """Indice di Gini su valori non negativi. 0 = equidistribuzione, ->1 = tutto
    a uno solo. Definito come meta' della differenza media relativa, la forma
    che non richiede di ordinare in classi."""
    vals = [float(v) for v in values if v is not None and float(v) >= 0]
    n = len(vals)
    total = sum(vals)
    if n < 2 or total <= 0:
        return 0.0
    vals.sort()
    cum = sum((2 * (i + 1) - n - 1) * v for i, v in enumerate(vals))
    return cum / (n * total)


def normalized_entropy(values):
    """H/H_max sulle quote: 1 = equidistribuzione, 0 = un solo host ha tutto."""
    vals = [float(v) for v in values if v is not None and float(v) > 0]
    total = sum(vals)
    if len(vals) < 2 or total <= 0:
        return 0.0
    h = -sum((v / total) * math.log(v / total) for v in vals)
    return h / math.log(len(vals))


def build_inequality(pr_rows, meta):
    """Una riga per epoca: quanto e' concentrato il peso, e quanto lo erano gia'
    gli input.

    `gini_atteso_da_input` e' calcolato sul peso GREZZO W_k^e — la stessa
    quantita' prima che la retroazione rho la tocchi — perche' il confronto ha
    senso solo fra grandezze definite sulla stessa unita' (il cluster). La
    lettura letterale "Gini sui c_i^e" e' comunque riportata a fianco come
    `gini_contributi_c_i`, sulle singole aziende: dice quanto e' diseguale
    l'attivita' di filiera, non quanto lo e' il potere di elezione.

    Nessuna interpretazione qui: il confronto fra i due Gini e' un numero, non
    un verdetto. Vale la Sez. 1.3 — un peso che si concentra perche' un cluster
    e' piu' virtuoso e' il protocollo che funziona, non un'anomalia.
    """
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    per_epoch = defaultdict(list)
    for row in pr_rows:
        per_epoch[row["epoca"]].append(row)
    out = []
    for epoca in sorted(per_epoch):
        rows = per_epoch[epoca]
        pub = [(r["host"], as_float(r["peso_pubblicato_epoca"]))
               for r in rows if r["peso_pubblicato_epoca"] != ""]
        eff = [as_float(r["peso_efficace_epoca"]) for r in rows
               if r["peso_efficace_epoca"] != ""]
        grezzi = [as_float(r["peso_grezzo_epoca"], 0.0) for r in rows]
        c_i = []
        for r in rows:
            for part in (r["contributi_c_i_lista"] or "").split(","):
                if ":" in part:
                    v = as_float(part.rsplit(":", 1)[1])
                    if v is not None:
                        c_i.append(v)
        pesi = [w for _h, w in pub if w is not None]
        tot = sum(pesi)
        dominante, quota_dom = "", ""
        if pesi and tot > 0:
            host_dom, w_dom = max(((h, w) for h, w in pub if w is not None),
                                  key=lambda t: t[1])
            dominante, quota_dom = host_dom, round(w_dom / tot, 6)
        r = dict(base)
        r.update({
            "epoca": epoca,
            "n_host_con_peso": len(pesi),
            "gini_peso_pubblicato": round(gini(pesi), 6),
            "gini_peso_effettivo": round(gini(eff), 6),
            "entropia_normalizzata_peso": round(normalized_entropy(pesi), 6),
            "host_dominante": dominante,
            "quota_host_dominante": quota_dom,
            "gini_atteso_da_input": round(gini(grezzi), 6),
            "gini_contributi_c_i": round(gini(c_i), 6),
            "delta_gini_pubblicato_input": round(gini(pesi) - gini(grezzi), 6),
        })
        out.append(r)
    return out


# --------------------------------------------------------------------------
# Sez. 4.5 - tabella unica dei controlli di integrita'
# --------------------------------------------------------------------------
#
# SEVERITA'. [H] hard: il dato e' certamente sbagliato e invalida ogni lettura
# che vi si appoggi. [P] probabile: lo scostamento esiste, ma un artefatto noto
# e dichiarato lo spiega senza chiamare in causa il protocollo. [I] informativo:
# nessun errore, ma un limite della campagna da non perdere di vista.

def build_integrity(run, meta, pr_rows, ledger, events, blocks, maps, specials, verify_row):
    addr_by_host, host_by_addr, _esg, _cluster = maps
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    out = []

    def add(height, epoca, host, tipo, sev, desc, atteso, osservato, rif):
        r = dict(base)
        r.update({"height": height, "epoca": epoca, "host": host,
                  "tipo_controllo": tipo, "severita": sev, "descrizione": desc,
                  "valore_atteso": atteso, "valore_osservato": osservato,
                  "riferimento_riga_sorgente": rif})
        out.append(r)

    # --- spesa senza copertura ---------------------------------------------
    #
    # E' il controllo AUTOREVOLE sul GAS, e va fatto per primo: confronta due
    # numeri letti nello stesso istante dallo stesso nodo — il `getbalance` che
    # il miner esegue subito prima di riconciliare e l'importo che invia. Non
    # dipende da nessun modello di attribuzione delle altezze, quindi una
    # violazione qui e' un dato certamente sbagliato: [H].
    scoperti = set()
    _h, recon = read_csv_rows(run["metrics"] / "reconciliation.csv",
                              expected_cols=["height", "epoch", "miner", "balance", "sent"])
    for row in recon:
        if len(row) < 5:
            continue
        bal, sent = as_float(row[3]), as_float(row[4])
        if bal is None or sent is None:
            continue
        if sent > bal + GAS_EPS:
            scoperti.add(row[2].strip())
            add(as_int(row[0]), as_int(row[1]), row[2].strip(),
                "autorizzazione_spesa_mancante", "[H]",
                "riconciliazione superiore al saldo che il miner stesso ha letto "
                "subito prima di inviarla",
                "sent <= balance", "sent=%s balance=%s" % (sent, bal),
                "reconciliation.csv")

    # --- saldi negativi nel registro ricostruito ---------------------------
    #
    # SPIEGAZIONE NOTA, da escludere prima di gridare all'anomalia. Il registro
    # incrocia tre fonti con orologi diversi: `gas_transfers.csv` porta
    # l'altezza di INVIO della RPC dell'admin (la conferma non e' dimostrabile,
    # manca il txid), `gas_balances.csv` e' un campione che l'admin prende
    # ciclando sui nodi — l'altezza e' quella dell'admin a inizio ciclo, non
    # quella della lettura — e `reconciliation.csv` porta il saldo letto dal
    # miner. Un rifornimento inviato e non ancora confermato, o un campione
    # preso prima che lo fosse, produce un'escursione negativa che non e' un
    # nodo a corto di GAS. Severita' [P], quindi, a meno che lo stesso nodo
    # NON risulti anche scoperto nel controllo qui sopra, che non dipende da
    # nessun modello: allora [H].
    for row in ledger:
        if row["coerente_con_saldo"]:
            continue
        hard = row["nodo"] in scoperti
        add(row["height"], row["epoca"], row["nodo"], "saldo_negativo",
            "[H]" if hard else "[P]",
            "il registro ricostruito porta il saldo sotto zero. "
            + ("Il nodo risulta scoperto anche in reconciliation.csv, che non "
               "dipende da nessun modello di attribuzione: e' un dato sbagliato."
               if hard else
               "Spiegato dall'incrocio di fonti con altezze non omogenee (invio "
               "contro conferma contro campione): il controllo indipendente "
               "sent <= balance non segnala nulla per questo nodo."),
            ">= 0", row["saldo_gas_dopo"],
            "account_ledger.csv (%s, height %s)" % (row["nodo"], row["height"]))

    # --- ricalcolabilita' del peso (Sez. 5.11.1) --------------------------
    for row in pr_rows:
        if row["esito_ricalcolo"] != "scostamento":
            continue
        sev = "[P]" if verify_row and verify_row.get("verificato") else "[H]"
        add(row["height_pubblicazione"], row["epoca"], row["host"],
            "peso_non_ricalcolabile", sev,
            "il peso pubblicato non e' riprodotto dal ricalcolo indipendente dagli "
            "input pubblici dell'epoca. Severita' [P] quando il verificatore "
            "interno (weightverifyweights) dichiara comunque validi i record: in "
            "quel caso a divergere e' il modello di attribuzione dell'altezza "
            "usato qui, non il peso sulla catena",
            row["peso_pubblicato_ricalcolato"], row["peso_pubblicato_epoca"],
            "peso_riconciliazione.csv (epoca %s, %s)" % (row["epoca"], row["host"]))

    # --- tau: il contatore usato nel peso contro quello ricostruibile dagli
    #     eventi di traffico (Sez. 4.4) -----------------------------------
    # tau_i di un'azienda = pubblicazioni di filiera confermate nell'epoca +
    # il proprio record di adesione, che e' una transazione confermata come le
    # altre e conta come attivita' nell'epoca in cui entra in un blocco. Le
    # aziende non pubblicano altro: lo stream ESG e' chiuso (scrive la sola CA)
    # e non riconciliano. Il confronto e' quindi esatto, non approssimato — ed
    # e' il motivo per cui vale la pena farlo: coglie qualunque divergenza fra
    # il contatore che entra in c_i e le transazioni davvero ricostruibili.
    tau_ric, n_non_traffico = Counter(), 0
    for rec in events["traffic_events"]:
        if rec["esito"] == "ok" and rec["epoca"]:
            tau_ric[(rec["nodo_publisher"], rec["epoca"])] += 1
    for rec in events["membership_events"]:
        if rec["epoca"]:
            tau_ric[(rec["azienda"], rec["epoca"])] += 1
            n_non_traffico += 1
    for row in pr_rows:
        for part in (row["attivita_cluster_tau_lista"] or "").split(","):
            if ":" not in part:
                continue
            host, val = part.rsplit(":", 1)
            n = as_int(val, 0) or 0
            osservato = tau_ric.get((host, row["epoca"]), 0)
            if n != osservato:
                add("", row["epoca"], host, "tau_incoerente", "[H]",
                    "il tau usato nel contributo c_i non coincide con le transazioni "
                    "confermate dell'azienda ricostruibili da traffic_events.csv piu' "
                    "membership_events.csv",
                    osservato, n,
                    "peso_riconciliazione.csv / traffic_events.csv (epoca %s, %s)"
                    % (row["epoca"], host))
    if n_non_traffico:
        add("", "", "", "altro", "[I]",
            "%d record di adesione entrano in tau come attivita' confermata, oltre "
            "alle pubblicazioni di filiera: e' corretto (sono transazioni in un "
            "blocco) ma va tenuto presente leggendo tau come 'traffico'"
            % n_non_traffico, "n/d", n_non_traffico, "membership_events.csv")

    # --- Cor. 5.4: un candidato senza peso non deve mai essere eletto ------
    setup = meta["setup_blocks"]
    for blk in blocks:
        if blk.get("height", 0) <= setup:
            continue
        miner = blk.get("miner")
        if miner and miner in specials.values():
            add(blk["height"], epoch_of(blk["height"], meta["epoch_len"]),
                host_by_addr.get(miner, miner[:10]), "altro", "[H]",
                "un nodo strutturalmente senza peso (admin/ca) ha proposto un "
                "blocco fuori dalla fase di setup: violerebbe il Cor. 5.4",
                "nessun blocco", "blocco %s" % blk["height"], "blocks.json")

    # --- vincoli sui parametri: lambda_w in [0,1) per costruzione ----------
    lam = as_float(meta.get("weight_lambda"))
    if lam is not None and not (0.0 <= lam < 1.0):
        add("", "", "", "altro", "[H]",
            "weight-lambda fuori dall'intervallo semiaperto [0,1) richiesto "
            "dall'Oss. 6.2: con lambda = 1 il peso perde la positivita' garantita",
            "0 <= lambda < 1", lam, "params.dat")

    # --- limiti dichiarati della campagna, non errori ---------------------
    if not meta.get("malus_events_found"):
        add("", "", "", "altro", "[I]",
            "nessun record sul registro dei malus: le Def. 5.17-5.24 (quattro tipi "
            "di violazione, decadimento reversibile) non sono esercitate da questa "
            "run, e Psi vale 1 in ogni epoca", "n/d", 0, "malus.json")
    if (meta.get("dump_function") or "none") == "none":
        add("", "", "", "altro", "[I]",
            "dump-function = none: lo smorzamento anti-whale (Def. 5.9) e' inerte, "
            "quindi peso_efficace_epoca coincide con peso_dopo_malus per costruzione",
            "n/d", "none", "params.dat")
    insuff = sum(1 for r in pr_rows if r.get("campione_sufficiente_epoca") == 0)
    if insuff:
        add("", "", "", "altro", "[I]",
            "%d righe (epoca x host) con attesa minima sotto 5: il chi-quadro per "
            "epoca non ha campione sufficiente e va letto solo insieme a quello a "
            "finestra scorrevole" % insuff, ">= 5", "< 5",
            "peso_riconciliazione.csv")
    return out


# --------------------------------------------------------------------------
# Sez. 4.9 - test aggiuntivi, aggregati su tutta la campagna
# --------------------------------------------------------------------------

def _spearman(xs, ys):
    """(rho, p) di Spearman, o ('', '') se il campione non lo consente.

    Con scipy si usa scipy.stats.spearmanr; senza, si calcola il solo
    coefficiente sui ranghi (Pearson sui ranghi) e il p-value resta vuoto —
    dichiarato, mai stimato.
    """
    pairs = [(x, y) for x, y in zip(xs, ys) if x is not None and y is not None]
    if len(pairs) < 3:
        return "", "", len(pairs)
    xs = [p[0] for p in pairs]
    ys = [p[1] for p in pairs]
    if len(set(xs)) < 2 or len(set(ys)) < 2:
        return "", "", len(pairs)     # una serie costante: rho non e' definito
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


def build_correlations(meta, pr_rows, ledger):
    """Sez. 4.9.1 - il canale selezione -> GAS -> riconciliazione -> peso futuro.

    Due correlazioni per host, tenute separate perche' rispondono a due domande
    diverse:

    * `gas_fee_epoca` vs `rho_epoca` — il canale ECONOMICO: un miner che vince
      piu' blocchi incassa piu' fee, quindi ha piu' GAS da riconciliare. Le fee
      sono l'unica entrata guadagnata: i rifornimenti dell'admin sono un
      trasferimento, non un guadagno, e sono riportati a parte
      (`gas_entrate_epoca`) proprio per non confonderli.
    * `rho_epoca(e)` vs `peso_pubblicato_epoca(e+1)` — il canale FORMALE, vero
      per costruzione dalla Def. 6.9. Va riportato lo stesso: e' la verifica
      diretta che la formula implementata sia quella dichiarata.

    NON si correlano blocchi minati e peso: quella e' l'implicazione inversa,
    gia' garantita dal Teor. 5.3, e un coefficiente alto non direbbe nulla di
    nuovo.
    """
    base = {"run_id": meta["run_id"], "livello": meta["livello"], "tbt": meta["tbt"]}
    fee_ep, in_ep = Counter(), Counter()
    for row in ledger:
        amount = as_float(row["importo_gas"], 0.0) or 0.0
        key = (row["nodo"], row["epoca"])
        if amount > 0:
            in_ep[key] += amount
            if row["tipo_movimento"] == "fee":
                fee_ep[key] += amount
    by_host = defaultdict(dict)
    for row in pr_rows:
        by_host[row["host"]][row["epoca"]] = row

    out = []
    for host in sorted(by_host):
        epoche = sorted(by_host[host])
        rho = [as_float(by_host[host][e].get("rho_epoca")) for e in epoche]
        fee = [fee_ep.get((host, e), 0.0) for e in epoche]
        entrate = [in_ep.get((host, e), 0.0) for e in epoche]
        w_next = [as_float(by_host[host].get(e + 1, {}).get("peso_pubblicato_epoca"))
                  for e in epoche]
        r1, p1, n1 = _spearman(fee, rho)
        r2, p2, n2 = _spearman(entrate, rho)
        r3, p3, n3 = _spearman(rho, w_next)
        r = dict(base)
        r.update({
            "host": host, "epoche": len(epoche),
            "spearman_fee_vs_rho": r1, "p_fee_vs_rho": p1, "n_fee_vs_rho": n1,
            "spearman_entrate_vs_rho": r2, "p_entrate_vs_rho": p2,
            "n_entrate_vs_rho": n2,
            "spearman_rho_vs_peso_successivo": r3,
            "p_rho_vs_peso_successivo": p3, "n_rho_vs_peso_successivo": n3,
        })
        out.append(r)
    return out


def build_delay_ordering(proposers, weights_note="peso_ultimo"):
    """Sez. 4.9.2 / Prop. 5.12 - il delay medio deve essere ordinato per peso
    DECRESCENTE: piu' peso, piu' basso lo score, prima si mina. La correzione
    globale lambda*Phi_n e' comune a tutti i candidati del round e non altera
    l'ordinamento, quindi una violazione non e' spiegabile con la retroazione.
    """
    per_run = defaultdict(list)
    for row in proposers:
        per_run[(row["run_id"], row["livello"], row["tbt"])].append(row)
    out = []
    for (run_id, livello, tbt), rows in sorted(per_run.items()):
        usable = [r for r in rows
                  if as_float(r.get("delay_medio_s")) is not None
                  and as_int(r.get(weights_note), 0)]
        usable.sort(key=lambda r: -as_int(r[weights_note], 0))
        inversioni = []
        for i in range(1, len(usable)):
            prev, cur = usable[i - 1], usable[i]
            if as_float(prev["delay_medio_s"]) > as_float(cur["delay_medio_s"]):
                inversioni.append("%s(%s)>%s(%s)" % (
                    prev["host"], prev["delay_medio_s"],
                    cur["host"], cur["delay_medio_s"]))
        out.append({
            "run_id": run_id, "livello": livello, "tbt": tbt,
            "host_confrontati": len(usable),
            "ordine_per_peso_decrescente": " > ".join(
                "%s:%s" % (r["host"], r[weights_note]) for r in usable),
            "delay_nello_stesso_ordine": " > ".join(
                "%s:%s" % (r["host"], r["delay_medio_s"]) for r in usable),
            "inversioni": len(inversioni),
            "dettaglio_inversioni": "; ".join(inversioni),
            "ordinamento_rispettato": int(not inversioni) if len(usable) >= 2 else "",
        })
    return out


def _linfit(xs, ys):
    """Minimi quadrati y = a + b x, con R^2. ('','','') se il campione non basta."""
    pairs = [(x, y) for x, y in zip(xs, ys)
             if x is not None and y is not None
             and math.isfinite(x) and math.isfinite(y)]
    n = len(pairs)
    if n < 3:
        return "", "", "", n
    mx = sum(p[0] for p in pairs) / n
    my = sum(p[1] for p in pairs) / n
    sxx = sum((p[0] - mx) ** 2 for p in pairs)
    if sxx <= 0:
        return "", "", "", n
    sxy = sum((p[0] - mx) * (p[1] - my) for p in pairs)
    b = sxy / sxx
    a = my - b * mx
    sst = sum((p[1] - my) ** 2 for p in pairs)
    ssr = sum((p[1] - (a + b * p[0])) ** 2 for p in pairs)
    r2 = (1.0 - ssr / sst) if sst > 0 else ""
    return round(a, 6), round(b, 6), (round(r2, 6) if r2 != "" else ""), n


def build_prop518_fit(margins):
    """Sez. 4.9.3 - la legge di scala della Prop. 5.18.

    Pr[G < t] = 1 - (1 - t/(2 Dmax))^n e' esatta: a t e n fissi la frazione di
    round con margine sotto t decresce come 1/Dmax. Si riportano due fit, uno
    per famiglia geografica (il livello) e uno su tutta la campagna:

    * lineare, `frazione` contro `1/Dmax` — la forma attesa al primo ordine;
    * log-log, `ln(frazione)` contro `ln(Dmax)` — l'esponente empirico, che il
      modello vuole vicino a -1.

    Nessuna conclusione qui: coefficienti e R^2, e basta.
    """
    out = []
    gruppi = {"tutta la campagna": margins}
    for row in margins:
        gruppi.setdefault("livello=%s" % row["livello"], []).append(row)
    for nome, rows in sorted(gruppi.items()):
        xs_lin, ys_lin, xs_log, ys_log = [], [], [], []
        for r in rows:
            dmax = as_float(r.get("banda_dmax_s"))
            frac = as_float(r.get("frazione_G_sotto_100ms"))
            if not dmax or dmax <= 0 or frac is None:
                continue
            xs_lin.append(1.0 / dmax)
            ys_lin.append(frac)
            if frac > 0:
                xs_log.append(math.log(dmax))
                ys_log.append(math.log(frac))
        a1, b1, r1, n1 = _linfit(xs_lin, ys_lin)
        a2, b2, r2, n2 = _linfit(xs_log, ys_log)
        out.append({
            "gruppo": nome,
            "punti_lineare": n1, "lin_intercetta": a1, "lin_pendenza": b1,
            "lin_r2": r1,
            "punti_loglog": n2, "log_intercetta": a2,
            "log_esponente": b2, "log_r2": r2,
            "esponente_atteso": -1,
            "nota": "il fit lineare e' frazione(G<100ms) contro 1/Dmax; il log-log "
                    "e' ln(frazione) contro ln(Dmax), la cui pendenza e' l'esponente "
                    "empirico della legge di scala",
        })
    return out


# Parametri che definiscono una famiglia di confronto: due run appartengono
# alla stessa famiglia per il parametro P se differiscono SOLO per P.
FAMILY_PARAMS = ["target_block_time", "mining_diversity", "weight_epoch_length",
                 "weight_kappa", "weight_lambda", "wpoa_sortition_delta",
                 "wpoa_sortition_lambda", "wpoa_randao_lookback", "dump_function"]


def build_families(index):
    """Sez. 4.9.5 - le famiglie di run che differiscono per ESATTAMENTE un
    parametro, costruite dall'indice invece che dichiarate a mano.

    Il livello geografico entra nella chiave di raggruppamento quando NON e' la
    variabile in esame; quando lo e' (famiglia `livello`), entra invece nella
    chiave tutto il resto. Gli assi 2 e 3 della campagna attuale — livello a tbt
    costante, tbt a livello costante — sono i due casi particolari che questo
    meccanismo produce da solo, senza che siano scritti da nessuna parte.
    """
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
# struttura di output e trasloco dalla struttura precedente
# --------------------------------------------------------------------------
#
# La struttura richiesta (Sez. 4) e':
#
#   analisi/
#     fogli-di-analisi/          tabelle globali, una riga per run o run x dim.
#     esperimenti/<run>/<liv>/   mirror di esperimenti/, solo output di analisi
#     plots/                     grafici, scritti dalla sessione di analisi
#     report_generale.md         scritto dalla sessione di analisi, non qui
#
# La versione precedente della pipeline scriveva le tabelle globali diritte in
# `analisi/` e il dettaglio per-esperimento dentro `esperimenti/<run>/<liv>/dati/`,
# cioe' DENTRO l'albero dei dati grezzi. Il trasloco sposta i file invece di
# ricalcolarli e cancella le cartelle vecchie: l'albero `esperimenti/` torna di
# sola lettura per intero, come vuole la Sez. 3.

LEGACY_GLOBAL = [t + ".csv" for t in (
    "run_index", "block_times", "proposers", "chisq", "alternanze", "forks",
    "gas", "weights_trajectory", "epoch_shares", "sortition_margins", "esg",
    "verify")] + ["metrics_schema_report.md", "estrazione.log"]


def _move_into(src, dst_dir, log):
    """Sposta `src` dentro `dst_dir`, sovrascrivendo. Restituisce 1 se mosso."""
    if not src.exists():
        return 0
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / src.name
    try:
        if dst.exists():
            dst.unlink()
        src.replace(dst)
    except OSError as exc:
        log.append("  NON spostato %s: %s" % (src, exc))
        return 0
    log.append("  %s -> %s" % (src, dst))
    return 1


def migrate_legacy_outputs(root, out_dir, sheets, mirror):
    """Porta l'output della struttura precedente in quella della Sez. 4.

    Non ricalcola nulla: sposta. Cio' che viene rigenerato nello stesso giro
    sara' semplicemente riscritto sopra; cio' che non lo e' (un file di una run
    non piu' presente sotto `esperimenti/`) sopravvive al trasloco invece di
    sparire senza che nessuno se ne accorga.
    """
    log, moved = [], 0
    for name in LEGACY_GLOBAL:
        moved += _move_into(out_dir / name, sheets, log)
    if not root.is_dir():
        return moved, log
    for run_dir in sorted(p for p in root.iterdir() if p.is_dir()):
        area = run_dir / "file-analisi-dati-di-tutti-gli-esp-in-area"
        if area.is_dir():
            for f in sorted(area.iterdir()):
                if f.is_file():
                    moved += _move_into(f, mirror / run_dir.name / area.name, log)
            try:
                area.rmdir()
                log.append("  rimossa la cartella vuota %s" % area)
            except OSError as exc:
                log.append("  cartella %s non rimossa: %s" % (area, exc))
        for level_dir in sorted(p for p in run_dir.iterdir() if p.is_dir()):
            dati = level_dir / "dati"
            if not dati.is_dir():
                continue
            for f in sorted(dati.iterdir()):
                if f.is_file():
                    moved += _move_into(
                        f, mirror / run_dir.name / level_dir.name, log)
            try:
                dati.rmdir()
                log.append("  rimossa la cartella vuota %s" % dati)
            except OSError as exc:
                log.append("  cartella %s non rimossa: %s" % (dati, exc))
    return moved, log


def append_schema_notes(sheets, index):
    """Aggiunge al report di schema le due determinazioni della Sez. 2 che non si
    leggono da `metrics/`: la conversione GAS e la natura del generatore di
    traffico."""
    path = sheets / "metrics_schema_report.md"
    righe = ["", "## Conversione GAS, run per run (Sez. 2.3)", "",
             "Le RPC di MultiChain restituiscono la valuta nativa gia' in unita' di",
             "**visualizzazione**: `getbalance`, l'importo di `send`, `qty` di",
             "`listassets`. Ogni CSV scritto dall'harness ne e' una copia diretta —",
             "`gas_balances.csv`, `gas_transfers.csv`, `reconciliation.csv`, la colonna",
             "`balance` di `node_state.csv`, `treasury_balance.json` — quindi e' **gia' in",
             "GAS** e non va convertito: convertirlo una seconda volta sarebbe l'errore.",
             "",
             "A essere in unita' **grezze** sono i soli parametri di catena in",
             "`params.dat`: `first-block-reward`, `initial-block-reward`,",
             "`minimum-relay-fee`, `maximum-per-output`. La pipeline li divide per",
             "`native-currency-multiple`, letto run per run e mai assunto:",
             "",
             "| run | native-currency-multiple | fonte | first-block-reward (GAS) | initial-block-reward (GAS) | minimum-relay-fee (GAS/1000B) |",
             "|---|---|---|---|---|---|"]
    for row in index:
        ncm = as_float(row.get("native_currency_multiple"))
        def gas(key):
            raw = as_float(row.get(key))
            if raw is None or not ncm:
                return "n/d"
            return ("%.8f" % (raw / ncm)).rstrip("0").rstrip(".") or "0"
        righe.append("| `%s` | %s | %s | %s | %s | %s |" % (
            row.get("run_id", ""), row.get("native_currency_multiple", "n/d"),
            row.get("fonte_conversione_gas", "n/d"), gas("first_block_reward"),
            gas("initial_block_reward"), gas("minimum_relay_fee")))
    righe += [
        "",
        "## Il generatore di traffico e' esogeno (Sez. 2.4)",
        "",
        "Determinato leggendo l'harness, non assunto. `tools/role_company.sh`, fase",
        "`traffic`: un ciclo `while true` che pubblica un item sullo stream applicativo",
        "e poi `sleep $POESIA_TX_INTERVAL`. L'intervallo e' fisso per azienda e",
        "dichiarato nello `shadow.yaml`; il ciclo non legge ne' chi ha vinto il blocco,",
        "ne' il proprio saldo, ne' il peso pubblicato. Anche `tools/role_miner.sh` fase",
        "`reconcile` e' a tasso fisso (`POESIA_RECONCILE_RATE` per miner), applicato al",
        "saldo del momento.",
        "",
        "Conseguenza per l'analisi: **non esiste un anello di retroazione dal risultato",
        "delle elezioni al traffico**. Il canale selezione -> fee incassate ->",
        "riconciliazione -> rho -> peso dell'epoca successiva esiste (le fee dipendono",
        "da quanti blocchi il miner include), ma il traffico che alimenta `tau` no. Un",
        "eventuale ciclo osservato nei dati non puo' quindi passare per `tau`.",
        "",
        "## Nota sulle dipendenze Python",
        "",
        "`pandas`, `scipy` e `numpy` sono presenti in questo ambiente e vengono usati",
        "dove servono (Spearman via `scipy.stats.spearmanr`); la pipeline resta pero'",
        "corretta senza, con il coefficiente calcolato sui ranghi e il p-value",
        "dichiarato mancante invece che stimato. Lo stato effettivo di ogni giro e' la",
        "riga `pandas=... scipy=...` in testa a `estrazione.log`.",
        ""]
    try:
        with path.open("a", encoding="utf-8") as fh:
            fh.write("\n".join(righe) + "\n")
    except OSError as exc:
        LOG.error("impossibile completare metrics_schema_report.md: %s", exc)


# --------------------------------------------------------------------------
# orchestrazione
# --------------------------------------------------------------------------

TABLES = [
    "run_index", "block_times", "proposers", "chisq", "alternanze",
    "forks", "gas", "weights_trajectory", "epoch_shares",
    "sortition_margins", "esg", "verify",
    # aggregato su tutte le run del corrispondente file per-esperimento
    "disuguaglianza_pesi",
    # test della Sez. 4.9 che si calcolano per run e si leggono aggregati
    "correlazioni",
]

# Tabelle globali costruite alla fine, dall'insieme di tutte le run.
TABLES_AGGREGATE = ["famiglie_confronto", "ordinamento_delay", "fit_prop518"]


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
        result["_per_run"] = {"tables": {}, "log": [], "unconfirmed": {}, "scarti": 0}
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
    # serve gia' qui: build_integrity lo legge per dichiarare che il meccanismo
    # dei malus non e' esercitato da questa run.
    meta["malus_events_found"] = n_malus
    epoch_rows = extract_epoch_view(meta, measured, traj, host_by_addr)

    # Ricostruzione della catena del peso (Cap. 6) e tabelle degli eventi:
    # vivono in `<livello>/dati/`, accanto ai dati che descrivono, non qui.
    per_run = {"tables": {}, "log": [], "unconfirmed": {}, "scarti": 0}
    if not args.niente_dati_per_run:
        try:
            txindex, unconfirmed = build_tx_index(run)
            maps = (addr_by_host, host_by_addr, esg_by_host, cluster_by_host)
            events = extract_event_tables(run, meta, maps, txindex)
            all_blocks = rpc_result(run["metrics"] / "blocks.json") or []
            all_blocks = sorted(
                (b for b in all_blocks if isinstance(b, dict) and "height" in b),
                key=lambda b: b["height"])
            pr_rows, pr_log, n_scarti, n_mal_rec = compute_weight_reconciliation(
                run, meta, maps, events, txindex, all_blocks, args.finestra_epoche)
            events["peso_riconciliazione"] = pr_rows

            # Sez. 4.3/4.5/4.6: il bilancio per nodo, la concentrazione del peso
            # e la tabella unica dei controlli, tutte derivate da quanto sopra.
            specials = resolve_special_addresses(run, maps)
            ledger, n_reward = build_account_ledger(
                run, meta, maps, events, all_blocks, specials)
            events["account_ledger"] = ledger
            events["disuguaglianza_pesi"] = build_inequality(pr_rows, meta)
            events["errori_integrita"] = build_integrity(
                run, meta, pr_rows, ledger, events, all_blocks, maps,
                specials, verify_row)
            result["disuguaglianza_pesi"] = events["disuguaglianza_pesi"]
            result["correlazioni"] = build_correlations(meta, pr_rows, ledger)

            per_run = {"tables": events, "log": pr_log,
                       "unconfirmed": unconfirmed, "scarti": n_scarti}
            meta["righe_peso_riconciliazione"] = len(pr_rows)
            meta["scarti_ricalcolo_peso"] = n_scarti
            meta["righe_account_ledger"] = len(ledger)
            meta["premi_mining_ricostruiti"] = n_reward
            for sev in ("[H]", "[P]", "[I]"):
                meta["errori_%s" % sev.strip("[]")] = sum(
                    1 for r in events["errori_integrita"] if r["severita"] == sev)
            LOG.info("%s: %d righe di riconciliazione del peso, %d scarti di ricalcolo",
                     meta["run_id"], len(pr_rows), n_scarti)
            if n_scarti:
                problems_extra = "%d pesi non riprodotti dal ricalcolo" % n_scarti
                LOG.warning("%s: %s (dettaglio in dati/verifica_riconciliazione.log)",
                            meta["run_id"], problems_extra)
        except Exception as exc:      # il dettaglio per-run non deve fermare il resto
            LOG.exception("%s: ricostruzione del peso fallita (%s)", meta["run_id"], exc)
            meta["righe_peso_riconciliazione"] = 0
            meta["scarti_ricalcolo_peso"] = ""
    result["_per_run"] = per_run

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
    ap.add_argument("--finestra-epoche", type=int, default=5, dest="finestra_epoche",
                    help="ampiezza in epoche della finestra scorrevole del chi-quadro "
                         "(default 5): compromesso fra 'ultimo peso' e 'epoca singola'")
    ap.add_argument("--niente-dati-per-run", action="store_true", dest="niente_dati_per_run",
                    help="non scrivere le cartelle dati/ e file-analisi-dati-...: "
                         "produce la sola vista globale in --out")
    ap.add_argument("--force", action="store_true",
                    help="ignora la cache e ricalcola tutte le run")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    root = Path(args.root).expanduser().resolve()
    out_dir = Path(args.out).expanduser().resolve()
    sheets = out_dir / "fogli-di-analisi"
    mirror = out_dir / "esperimenti"
    for d in (out_dir, sheets, mirror, out_dir / "plots"):
        d.mkdir(parents=True, exist_ok=True)
    cache_dir = out_dir / ".cache"
    cache_dir.mkdir(exist_ok=True)

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(message)s",
        handlers=[logging.FileHandler(sheets / "estrazione.log", mode="w",
                                      encoding="utf-8"),
                  logging.StreamHandler(sys.stdout)])

    LOG.info("root=%s out=%s pandas=%s scipy=%s recompute_chisq=%s",
             root, out_dir, USING_PANDAS, USING_SCIPY, args.recompute_chisq)

    moved, movelog = migrate_legacy_outputs(root, out_dir, sheets, mirror)
    if moved:
        LOG.info("trasloco dalla struttura precedente: %d file spostati", moved)
        for line in movelog:
            LOG.info("%s", line)
    else:
        LOG.info("nessun output della struttura precedente da traslocare")
    if not USING_PANDAS:
        LOG.info("pandas non installato: le tabelle sono scritte con il modulo csv "
                 "standard, lo schema dei file non cambia")

    runs = discover_runs(root)
    if not runs:
        LOG.error("nessuna run trovata: controlla --root")
        return 1

    inspect_schema(runs, sheets)

    tables = {t: [] for t in TABLES}
    reused = 0
    # peso_riconciliazione per cartella-run e livello, per il confronto fra aree.
    per_area = defaultdict(dict)
    opzioni = {"recompute_chisq": bool(args.recompute_chisq),
               "finestra_epoche": int(args.finestra_epoche),
               "dati_per_run": not args.niente_dati_per_run,
               # Versione dello schema di output: cambiarla invalida la cache
               # senza costringere a --force. Va incrementata a ogni colonna o
               # tabella nuova, altrimenti una run gia' in cache tornerebbe con
               # lo schema vecchio e le tabelle globali sarebbero disomogenee.
               "schema": 2}
    for run in runs:
        cache_file = cache_dir / (run["run_id"].replace("/", "__") + ".json")
        fp = fingerprint(run)
        result = None
        if not args.force and cache_file.exists():
            cached = read_json(cache_file)
            # La cache porta con se' anche il dettaglio per-run, che viene
            # riscritto sotto: un `dati/` cancellato a mano si rigenera senza
            # dover rifare l'estrazione.
            if cached and cached.get("fingerprint") == fp \
                    and cached.get("opzioni") == opzioni:
                result = cached["tables"]
                reused += 1
                LOG.info("%s: invariata, riuso la cache", run["run_id"])
        if result is None:
            try:
                result = process_run(run, args)
            except Exception as exc:        # una run rotta non ferma le altre
                LOG.exception("%s: estrazione fallita (%s), run saltata",
                              run["run_id"], exc)
                tables["run_index"].append({
                    "run_id": run["run_id"], "livello": run["livello"],
                    "tbt": run["tbt_dirname"], "stato": "errore",
                    "note": str(exc), "malus_events_found": "",
                    "path": str(run["path"])})
                continue
            cache_file.write_text(json.dumps(
                {"fingerprint": fp, "opzioni": opzioni, "tables": result},
                ensure_ascii=False), encoding="utf-8")
        for name in TABLES:
            tables[name].extend(result.get(name, []))
        per_run = result.get("_per_run") or {}
        if not args.niente_dati_per_run and per_run.get("tables"):
            try:
                out = write_per_run_outputs(mirror, run, per_run["tables"],
                                            per_run["log"], per_run["unconfirmed"])
                LOG.info("%s: dettaglio per-run scritto in %s", run["run_id"], out)
            except OSError as exc:
                LOG.error("%s: impossibile scrivere dati/ (%s)", run["run_id"], exc)
            per_area[run["run_dir"]][run["livello"]] = \
                per_run["tables"].get("peso_riconciliazione", [])

    # --- test aggregati della Sez. 4.9, che esistono solo su tutta la campagna
    idx_ok = [r for r in tables["run_index"] if r.get("stato") not in ("errore",)]
    aggregate = {
        "famiglie_confronto": build_families(idx_ok),
        "ordinamento_delay": build_delay_ordering(tables["proposers"]),
        "fit_prop518": build_prop518_fit(tables["sortition_margins"]),
    }

    for name in TABLES:
        write_table(sheets, name, tables[name])
    for name in TABLES_AGGREGATE:
        write_table(sheets, name, aggregate[name])
    append_schema_notes(sheets, tables["run_index"])

    divergenze_area = {}
    for run_dir_name, per_level in sorted(per_area.items()):
        try:
            area_dir, n_div = write_area_comparison(mirror, run_dir_name, per_level)
            divergenze_area[run_dir_name] = n_div
            LOG.info("%s: confronto fra aree in %s (%d divergenze di peso NON "
                     "spiegate dall'attivita')", run_dir_name, area_dir, n_div)
        except OSError as exc:
            LOG.error("%s: impossibile scrivere il confronto fra aree (%s)",
                      run_dir_name, exc)

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
    scarti = sum(as_int(r.get("scarti_ricalcolo_peso"), 0) or 0 for r in idx)
    righe_pr = sum(as_int(r.get("righe_peso_riconciliazione"), 0) or 0 for r in idx)
    if righe_pr:
        LOG.info("riconciliazione del peso: %d righe (epoca x host) su %d run, "
                 "%d pesi non riprodotti dal ricalcolo", righe_pr, len(idx), scarti)
        if not scarti:
            LOG.info("  -> ogni peso pubblicato e' stato riprodotto esattamente dai "
                     "suoi input dichiarati: la Sez. 5.11.1 regge epoca per epoca")
    div_tot = sum(divergenze_area.values())
    if divergenze_area:
        LOG.info("confronto fra aree: %d coppie (epoca, host) con peso diverso fra "
                 "livelli E ESG diverso", div_tot)
        if not div_tot:
            LOG.info("  -> ESG e adesioni identici in tutte le aree: le differenze di "
                     "peso fra livelli vengono tutte dall'attivita' tau, che conta le "
                     "transazioni di una finestra di 12 BLOCCHI mentre il traffico e' "
                     "generato a tempo reale")
    # --- controlli di integrita' e test aggiuntivi ------------------------
    for sev, etichetta in (("H", "hard"), ("P", "probabile"), ("I", "informativo")):
        n = sum(as_int(r.get("errori_%s" % sev), 0) or 0 for r in idx)
        LOG.info("errori_integrita.csv, severita' [%s] (%s): %d righe su tutta la "
                 "campagna", sev, etichetta, n)
    inversioni = [r for r in aggregate["ordinamento_delay"] if r.get("inversioni")]
    if inversioni:
        LOG.warning("Prop. 5.12: ordinamento delay-peso violato in %d run su %d: %s",
                    len(inversioni), len(aggregate["ordinamento_delay"]),
                    ", ".join(r["run_id"] for r in inversioni))
    else:
        LOG.info("Prop. 5.12: il delay medio e' ordinato per peso decrescente in "
                 "tutte le %d run confrontabili", len(aggregate["ordinamento_delay"]))
    LOG.info("famiglie di confronto trovate automaticamente: %d",
             len(aggregate["famiglie_confronto"]))
    for fam in aggregate["famiglie_confronto"]:
        LOG.debug("  %s = {%s} su %d run", fam["parametro_variato"],
                  fam["valori"], fam["n_run"])
    LOG.info("tabelle globali in %s", sheets)
    if args.niente_dati_per_run:
        LOG.info("dettaglio per-esperimento disattivato (--niente-dati-per-run)")
    else:
        LOG.info("dettaglio per-esperimento in %s/<run>/<livello>/", mirror)
    LOG.info("il Monte Carlo della Sez. 4.8 e' uno script a se': "
             "tools/valida_sortition_montecarlo.py")
    return 0


if __name__ == "__main__":
    sys.exit(main())
