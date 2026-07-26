#!/usr/bin/env python3
# Copyright (c) 2014-2019 Coin Sciences Ltd
# MultiChain code distributed under the GPLv3 license, see COPYING file.
#
# make_report.py -- build the POESIA / "Vers_2" style Excel report from the
# experiment's output CSVs (output/*.csv produced by experimental_test.py).
#
# WORKBOOK LAYOUT (the reference Vers_2 sheet structure)
#
#   Foglio di configurazione  the static inputs: ESG min/max, Tx min/max, the GAS and
#                             engine constants, and per ClusterMiner its Score ESG,
#                             Certificato ISO, Peso % and Reso -- plus the list of the
#                             10 AZIENDE of each cluster with their own ESG scores.
#   Epoch N (one per epoch)   per azienda: Nome utente | Tx Utente | Impatto utente |
#                             Score ESG; then, after each group of 10, the cluster
#                             summary row: Tx Miner | Impatto Cluster | Delay in msec |
#                             Guadagno Ex (EUR) | EUR Resi in Ex | Giacenza | % Reso |
#                             Total GAIN, followed by the engine cross-check block.
#                             Totals for the epoch close the sheet.
#   Riepilogo                 every epoch on one row (Tot Tx, Tot Impatto, GAS
#                             distributed, GAS returned) plus the per-cluster run totals.
#   Pesi & Probabilita        epoch x cluster grid of published weights and selection
#                             probabilities.
#   Proposer log (wpoa)       verbatim wpoa_proposer_log.csv (wpoa mode only).
#   Verifiche                 the invariant checks and their verdicts.
#
# CHANGED FROM THE ORIGINAL (Apuana SB) REPORT. Every economic figure now comes from
# the CHAIN, read and settled by helpers/economics.py while the run is live, and is
# simply formatted here:
#   Tx Miner        transactions the cluster validated (blocks it proposed, coinbase
#                   excluded) -- NOT a modelled number
#   Guadagno Ex     Tx Miner * alpha, alpha = 0.2 GAS = 0.2 EUR per transaction
#   EUR Resi in Ex  the GAS the miner actually transferred to the ADMIN address,
#                   re-read from that transaction
#   Giacenza        the miner's on-chain GAS balance after the reconciliation confirmed
#   % Reso          Resi / Guadagno * 100
#   Total GAIN      running sum of Guadagno
#   Delay in msec   mean inter-block interval of the blocks the cluster proposed
# The previous version recomputed all of these in the reporter from the thesis
# formulas; the recomputed raw weight W_k and allocation A_k are still shown, but only
# as the engine cross-check columns.
#
# Usage:
#   python3 make_report.py                     # reads ./output, writes output/report.xlsx
#   python3 make_report.py --dir DIR --out FILE
#
# Requires openpyxl (pip install --user openpyxl).

import argparse
import csv
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import config

try:
    from openpyxl import Workbook
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter
except ImportError:
    sys.stderr.write(
        "ERROR: openpyxl is required.\n  pip install --user openpyxl\n")
    sys.exit(2)


# ---------------------------------------------------------------------------
# CSV loading
# ---------------------------------------------------------------------------
def load_csv(path):
    if not os.path.isfile(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def to_float(x, default=0.0):
    try:
        return float(x)
    except (TypeError, ValueError):
        return default


def to_int(x, default=0):
    try:
        return int(float(x))
    except (TypeError, ValueError):
        return default


def parse_log_params(outdir):
    """Pull the run's header values out of experiment.log; fall back to config."""
    params = {"kappa": config.KAPPA, "alpha": config.ALPHA,
              "lambda": config.LAMBDA, "mode": "?", "seed": config.SEED}
    path = os.path.join(outdir, "experiment.log")
    if not os.path.isfile(path):
        return params
    with open(path, errors="replace") as f:
        for line in f:
            m = re.search(r"kappa/alpha/lambda\s*:\s*([0-9.]+)\s*/\s*([0-9.]+)\s*/\s*([0-9.]+)", line)
            if m:
                params["kappa"] = float(m.group(1))
                params["alpha"] = float(m.group(2))
                params["lambda"] = float(m.group(3))
            m = re.search(r"^mode\s*:\s*(\w+)", line)
            if m:
                params["mode"] = m.group(1)
            m = re.search(r"^seed\s*:\s*(\d+)", line)
            if m:
                params["seed"] = int(m.group(1))
            if line.strip().startswith("=") and params["mode"] != "?":
                break
    return params


def natural_key(label):
    """Sort ClusterMinerA<ClusterMinerB and Azienda_A1<Azienda_A2<..._A10 naturally."""
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", label)]


# ---------------------------------------------------------------------------
# In-memory model, assembled from the harness CSVs
# ---------------------------------------------------------------------------
class Model(object):
    def __init__(self, outdir):
        self.outdir = outdir
        self.params = parse_log_params(outdir)

        self.cfg = load_csv(os.path.join(outdir, "config_sheet.csv"))
        self.cluster = load_csv(os.path.join(outdir, "cluster_economics.csv"))
        self.company = load_csv(os.path.join(outdir, "company_activity.csv"))
        self.esum = load_csv(os.path.join(outdir, "epochs_summary.csv"))
        self.wev = load_csv(os.path.join(outdir, "weights_evolution.csv"))
        self.plog = load_csv(os.path.join(outdir, "wpoa_proposer_log.csv"))
        self.checks = load_csv(os.path.join(outdir, "assertions.csv"))

        # -- configuration ------------------------------------------------
        self.clusters = []            # ordered cluster labels
        self.cluster_cfg = {}         # label -> dict(esg, iso, reso_rate, companies[])
        for r in self.cfg:
            label = r["cluster"]
            names = [x for x in (r.get("companies") or "").split(";") if x]
            escores = [to_int(x) for x in (r.get("esg_companies") or "").split(";") if x != ""]
            self.clusters.append(label)
            self.cluster_cfg[label] = {
                "letter": r.get("letter", ""),
                "esg": to_int(r.get("esg_cluster")),
                "iso": r.get("iso_certificate", ""),
                "reso_rate": to_float(r.get("reso_rate_nominal")),
                "companies": list(zip(names, escores + [0] * (len(names) - len(escores)))),
            }
        if not self.clusters:                       # fall back to cluster_economics
            self.clusters = sorted({r["cluster"] for r in self.cluster}, key=natural_key)
            for label in self.clusters:
                self.cluster_cfg[label] = {"letter": "", "esg": 0, "iso": "",
                                           "reso_rate": 0.0, "companies": []}

        # -- per epoch ----------------------------------------------------
        self.epochs = sorted({to_int(r["epoch"]) for r in self.cluster})
        self.eco = {}                 # (epoch, cluster) -> row dict (typed)
        for r in self.cluster:
            self.eco[(to_int(r["epoch"]), r["cluster"])] = {
                "esg": to_int(r.get("esg")),
                "iso": r.get("iso", ""),
                "blocks_mined": to_int(r.get("blocks_mined")),
                "tx_miner": to_int(r.get("tx_miner")),
                "tau_miner_signed": to_int(r.get("tau_miner_signed")),
                "impatto_cluster": to_float(r.get("impatto_cluster")),
                "delay_ms": to_float(r.get("delay_ms")),
                "guadagno": to_float(r.get("guadagno")),
                "resi": to_float(r.get("resi")),
                "giacenza": to_float(r.get("giacenza")),
                "pct_reso": to_float(r.get("pct_reso")),
                "total_gain": to_float(r.get("total_gain")),
                "engine_weight": to_int(r.get("engine_weight")),
                "engine_prob": to_float(r.get("engine_prob")),
                "selected": (r.get("selected_proposer") or "").lower() == "yes",
                "raw_weight": to_float(r.get("raw_weight_recomputed")),
                "allocation": to_float(r.get("allocation_recomputed")),
            }

        self.comp = {}                # (epoch, cluster) -> [company row dicts]
        for r in self.company:
            key = (to_int(r["epoch"]), r["cluster"])
            self.comp.setdefault(key, []).append({
                "label": r.get("company", ""),
                "display": r.get("display") or r.get("company", ""),
                "tx": to_int(r.get("tx_utente")),
                "esg": to_int(r.get("esg")),
                "impatto": to_float(r.get("impatto_utente")),
            })
        for key in self.comp:
            self.comp[key].sort(key=lambda x: natural_key(x["label"]))

        # proposer / method / theta per epoch
        self.proposer, self.method, self.theta = {}, {}, {}
        for r in self.esum:
            e = to_int(r["epoch"])
            self.proposer[e] = r.get("proposer_miner", "")
            self.method[e] = r.get("proposer_method", "")
            self.theta[e] = to_int(r.get("theta"))

    def mean_prob(self, cluster):
        """Mean published selection probability over the sampled epochs -- the natural
        reading of the reference sheet's 'Peso %' column."""
        vals = [self.eco[(e, cluster)]["engine_prob"]
                for e in self.epochs if (e, cluster) in self.eco]
        return (sum(vals) / len(vals)) if vals else 0.0

    def run_total(self, cluster, field):
        return sum(self.eco[(e, cluster)][field]
                   for e in self.epochs if (e, cluster) in self.eco)


# ---------------------------------------------------------------------------
# Styling helpers
# ---------------------------------------------------------------------------
THIN = Side(style="thin", color="B0B0B0")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)
HDR_FILL = PatternFill("solid", fgColor="D9E1F2")
BAND_FILL = PatternFill("solid", fgColor="FFF2CC")
MINER_FILL = PatternFill("solid", fgColor="FCE4D6")
TOT_FILL = PatternFill("solid", fgColor="E2EFDA")
SEL_FILL = PatternFill("solid", fgColor="C6EFCE")
FAIL_FILL = PatternFill("solid", fgColor="FFC7CE")
TITLE_FILL = PatternFill("solid", fgColor="4472C4")
BOLD = Font(bold=True)
BOLD_WHITE = Font(bold=True, color="FFFFFF")

MONEY = "0.00"
GAS4 = "0.0000"
PCT = "0.00"
PROB = "0.0000"
IMPACT = "0.000"


def put(ws, r, c, value, *, bold=False, fill=None, num=None, align=None, border=True):
    cell = ws.cell(row=r, column=c, value=value)
    if bold:
        cell.font = BOLD
    if fill:
        cell.fill = fill
    if num:
        cell.number_format = num
    if align:
        cell.alignment = Alignment(horizontal=align, vertical="center")
    if border:
        cell.border = BORDER
    return cell


def banner(ws, row, ncols, text):
    ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=ncols)
    c = ws.cell(row=row, column=1, value=text)
    c.font = BOLD_WHITE
    c.fill = TITLE_FILL
    c.alignment = Alignment(horizontal="left", vertical="center")
    return c


def widths(ws, values, start=1):
    for j, w in enumerate(values, start=start):
        ws.column_dimensions[get_column_letter(j)].width = w


# ---------------------------------------------------------------------------
# Sheet 1 -- Foglio di configurazione
# ---------------------------------------------------------------------------
def write_config_sheet(wb, model):
    ws = wb.create_sheet(title="Foglio di configurazione", index=0)
    ws.sheet_view.showGridLines = False
    p = model.params
    ncomp = max((len(c["companies"]) for c in model.cluster_cfg.values()), default=0)

    banner(ws, 1, 6, "MyLedger / wPoA — Foglio di configurazione")

    r = 3
    put(ws, r, 1, "Parametro", bold=True, fill=HDR_FILL)
    put(ws, r, 2, "Valore", bold=True, fill=HDR_FILL, align="center")
    put(ws, r, 3, "Note", bold=True, fill=HDR_FILL)
    r += 1
    rows = [
        ("Score minimo ESG", config.ESG_MIN, "intero, statico per tutta la run"),
        ("Score massimo ESG", config.ESG_MAX, "intero, statico per tutta la run"),
        ("Numero minimo Tx", config.TX_PER_COMPANY_MIN, "per azienda, per epoca"),
        ("Numero massimo Tx", config.TX_PER_COMPANY_MAX, "per azienda, per epoca"),
        ("alpha (costo per Tx)", p["alpha"], "GAS per transazione — 1 GAS = 1 EUR"),
        ("kappa", p["kappa"], "normalizzazione: Impatto utente = Tx * ESG / kappa"),
        ("lambda", p["lambda"], "smorzamento del feedback di conformita"),
        ("Modalita", p["mode"], "wpoa = selezione pesata; native = round-robin"),
        ("Seed", p["seed"], "ogni scelta casuale deriva da qui"),
        ("Numero cluster", len(model.clusters), "ClusterMiner"),
        ("Aziende per cluster", ncomp, "trasmettono le transazioni"),
        ("Epoche campionate",
         "%d..%d" % (model.epochs[0], model.epochs[-1]) if model.epochs else "-",
         "una scheda per epoca"),
        ("Valuta", config.GAS_ASSET_NAME, "asset divisibile che modella il GAS nativo"),
    ]
    for k, v, note in rows:
        put(ws, r, 1, k, bold=True)
        put(ws, r, 2, v, align="center")
        put(ws, r, 3, note)
        r += 1

    # -- per-cluster: Score ESG, Certificato ISO, Peso %, Reso -------------
    r += 1
    banner(ws, r, 6, "ClusterMiner — Score ESG, Certificato ISO, Peso %, Reso")
    r += 1
    hdr = ["ClusterMiner", "Score ESG", "Certificato ISO", "Peso %", "Reso",
           "Total GAIN (EUR)"]
    for j, h in enumerate(hdr, start=1):
        put(ws, r, j, h, bold=True, fill=HDR_FILL, align="center")
    r += 1
    for label in model.clusters:
        c = model.cluster_cfg[label]
        put(ws, r, 1, label, bold=True, fill=MINER_FILL)
        put(ws, r, 2, c["esg"], align="center")
        put(ws, r, 3, c["iso"])
        # Peso % is the mean published selection probability across the run.
        put(ws, r, 4, model.mean_prob(label) * 100.0, num=PCT, align="center")
        put(ws, r, 5, c["reso_rate"] * 100.0, num=PCT, align="center")
        put(ws, r, 6, model.run_total(label, "guadagno"), num=MONEY, align="center")
        r += 1

    # -- AZIENDE per cluster ----------------------------------------------
    r += 1
    ncols_grid = max(6, 2 * len(model.clusters))
    banner(ws, r, ncols_grid, "AZIENDE per ogni Cluster (nome e Score ESG)")
    r += 1
    for i, label in enumerate(model.clusters):
        col = 1 + 2 * i
        ws.merge_cells(start_row=r, start_column=col, end_row=r, end_column=col + 1)
        put(ws, r, col, label, bold=True, fill=BAND_FILL, align="center")
        put(ws, r, col + 1, None, fill=BAND_FILL)
    r += 1
    for i, label in enumerate(model.clusters):
        col = 1 + 2 * i
        put(ws, r, col, "Nome utente", bold=True, fill=HDR_FILL, align="center")
        put(ws, r, col + 1, "Score ESG", bold=True, fill=HDR_FILL, align="center")
    r += 1
    for row_i in range(ncomp):
        for i, label in enumerate(model.clusters):
            comps = model.cluster_cfg[label]["companies"]
            col = 1 + 2 * i
            if row_i < len(comps):
                put(ws, r, col, comps[row_i][0])
                put(ws, r, col + 1, comps[row_i][1], align="center")
            else:
                put(ws, r, col, None)
                put(ws, r, col + 1, None)
        r += 1

    widths(ws, [26, 14, 30, 12, 12, 16])
    for j in range(7, ncols_grid + 1):
        ws.column_dimensions[get_column_letter(j)].width = 16


# ---------------------------------------------------------------------------
# Per-epoch sheets -- the Vers_2 column layout
# ---------------------------------------------------------------------------
# Columns A-D are the per-azienda block; E-L are the per-cluster summary block
# (filled only on a cluster's summary row); M-Q are the engine cross-check.
COMPANY_COLS = ["Nome utente", "Tx Utente", "Impatto utente", "Score ESG"]
CLUSTER_COLS = ["Tx Miner", "Impatto Cluster", "Delay in msec", "Guadagno Ex (€)",
                "€ Resi in Ex", "Giacenza", "% Reso", "Total GAIN"]
ENGINE_COLS = ["Peso engine w_k", "Prob. selezione", "W_k ricalcolato",
               "A_k ricalcolato", "Proposer"]
ALL_COLS = COMPANY_COLS + CLUSTER_COLS + ENGINE_COLS
NCOLS = len(ALL_COLS)
C_CLUSTER = len(COMPANY_COLS) + 1          # first cluster-block column (E = 5)
C_ENGINE = C_CLUSTER + len(CLUSTER_COLS)   # first engine column (M = 13)
# Number formats, positionally aligned with CLUSTER_COLS / ENGINE_COLS. Module level so
# the totals row can reuse them after the per-cluster loop.
CLUSTER_FMTS = [None, IMPACT, MONEY, MONEY, MONEY, GAS4, PCT, MONEY]
ENGINE_FMTS = [None, PROB, IMPACT, MONEY, None]


def write_epoch_sheet(wb, model, epoch):
    ws = wb.create_sheet(title="Epoch %d" % epoch)
    ws.sheet_view.showGridLines = False

    tot_tx = sum(model.eco[(epoch, c)]["tx_miner"] for c in model.clusters
                 if (epoch, c) in model.eco)
    banner(ws, 1, NCOLS,
           "EPOCH %d  —  modalita %s  —  proposer %s (%s)  —  Tot Tx epoca %d  —  "
           "alpha %g GAS/tx"
           % (epoch, model.params["mode"], model.proposer.get(epoch, "?"),
              model.method.get(epoch, ""), model.theta.get(epoch, 0),
              model.params["alpha"]))

    hr = 2
    for j, name in enumerate(ALL_COLS, start=1):
        fill = HDR_FILL if j < C_CLUSTER else (BAND_FILL if j < C_ENGINE else HDR_FILL)
        put(ws, hr, j, name, bold=True, fill=fill, align="center")

    r = hr + 1
    company_tx_ranges, cluster_rows = [], []
    for label in model.clusters:
        d = model.eco.get((epoch, label))
        if d is None:
            continue
        cfg = model.cluster_cfg[label]
        fill = SEL_FILL if d["selected"] else MINER_FILL

        # cluster band
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=NCOLS)
        band = ws.cell(row=r, column=1,
                       value="%s   —   Score ESG %d   —   %s   —   blocchi proposti %d"
                             % (label, d["esg"], cfg["iso"] or "n/d", d["blocks_mined"]))
        band.font = BOLD
        band.fill = fill
        r += 1

        # the cluster's aziende
        first_company_row = r
        for comp in model.comp.get((epoch, label), []):
            put(ws, r, 1, "    " + comp["display"])
            put(ws, r, 2, comp["tx"], align="center")
            put(ws, r, 3, comp["impatto"], num=IMPACT, align="center")
            put(ws, r, 4, comp["esg"], align="center")
            for j in range(C_CLUSTER, NCOLS + 1):
                put(ws, r, j, None)
            r += 1
        last_company_row = r - 1
        if last_company_row >= first_company_row:
            company_tx_ranges.append((first_company_row, last_company_row))

        # the cluster summary row -- the 8 Vers_2 cluster columns
        put(ws, r, 1, "TOTALE %s" % label, bold=True, fill=fill)
        if last_company_row >= first_company_row:
            put(ws, r, 2, "=SUM(B%d:B%d)" % (first_company_row, last_company_row),
                bold=True, fill=fill, align="center")
            put(ws, r, 3, "=SUM(C%d:C%d)" % (first_company_row, last_company_row),
                bold=True, fill=fill, num=IMPACT, align="center")
        else:
            put(ws, r, 2, 0, bold=True, fill=fill, align="center")
            put(ws, r, 3, d["impatto_cluster"], bold=True, fill=fill, num=IMPACT,
                align="center")
        put(ws, r, 4, d["esg"], bold=True, fill=fill, align="center")
        vals = [d["tx_miner"], d["impatto_cluster"], d["delay_ms"], d["guadagno"],
                d["resi"], d["giacenza"], d["pct_reso"], d["total_gain"]]
        for off, (v, fmt) in enumerate(zip(vals, CLUSTER_FMTS)):
            put(ws, r, C_CLUSTER + off, v, bold=True, fill=fill, num=fmt, align="center")
        eng = [d["engine_weight"], d["engine_prob"], d["raw_weight"], d["allocation"],
               "SELECTED" if d["selected"] else ""]
        for off, (v, fmt) in enumerate(zip(eng, ENGINE_FMTS)):
            put(ws, r, C_ENGINE + off, v, bold=True, fill=fill, num=fmt, align="center")
        cluster_rows.append(r)
        r += 2                                    # spacer between clusters

    # -- epoch totals -----------------------------------------------------
    banner(ws, r, NCOLS, "TOTALI EPOCH %d" % epoch)
    r += 1
    put(ws, r, 1, "Tot Tx Epoch / Tot Impatto", bold=True, fill=TOT_FILL)
    if company_tx_ranges:
        put(ws, r, 2, "=" + "+".join("SUM(B%d:B%d)" % rg for rg in company_tx_ranges),
            bold=True, fill=TOT_FILL, align="center")
        put(ws, r, 3, "=" + "+".join("SUM(C%d:C%d)" % rg for rg in company_tx_ranges),
            bold=True, fill=TOT_FILL, num=IMPACT, align="center")
    else:
        put(ws, r, 2, model.theta.get(epoch, 0), bold=True, fill=TOT_FILL, align="center")
        put(ws, r, 3, 0, bold=True, fill=TOT_FILL, num=IMPACT, align="center")
    put(ws, r, 4, None, fill=TOT_FILL)
    if cluster_rows:
        for off, fmt in enumerate(CLUSTER_FMTS):
            col = get_column_letter(C_CLUSTER + off)
            put(ws, r, C_CLUSTER + off,
                "=" + "+".join("%s%d" % (col, cr) for cr in cluster_rows),
                bold=True, fill=TOT_FILL, num=fmt, align="center")
    for j in range(C_ENGINE, NCOLS + 1):
        put(ws, r, j, None, fill=TOT_FILL)
    r += 1
    put(ws, r, 1, "Total GAS distribuito (= Tot Tx Miner × alpha)", bold=True,
        fill=TOT_FILL)
    put(ws, r, 2, round(tot_tx * model.params["alpha"], 4), bold=True, fill=TOT_FILL,
        num=MONEY, align="center")
    put(ws, r, 3, "GAS = EUR", fill=TOT_FILL)
    for j in range(4, NCOLS + 1):
        put(ws, r, j, None, fill=TOT_FILL)

    # -- per-cluster ESG / ISO recap --------------------------------------
    r += 2
    banner(ws, r, 5, "Riepilogo Score ESG e Certificato ISO per cluster")
    r += 1
    for j, h in enumerate(["ClusterMiner", "Score ESG", "Certificato ISO",
                           "Tx Miner", "Guadagno Ex (€)"], start=1):
        put(ws, r, j, h, bold=True, fill=HDR_FILL, align="center")
    r += 1
    for label in model.clusters:
        d = model.eco.get((epoch, label))
        if d is None:
            continue
        put(ws, r, 1, label, bold=True)
        put(ws, r, 2, d["esg"], align="center")
        put(ws, r, 3, model.cluster_cfg[label]["iso"])
        put(ws, r, 4, d["tx_miner"], align="center")
        put(ws, r, 5, d["guadagno"], num=MONEY, align="center")
        r += 1

    widths(ws, [26, 11, 15, 11, 11, 15, 14, 15, 14, 12, 10, 13, 16, 14, 15, 14, 11])
    ws.freeze_panes = "A3"


# ---------------------------------------------------------------------------
# Riepilogo / Pesi / Proposer / Verifiche
# ---------------------------------------------------------------------------
def write_overview(wb, model):
    ws = wb.create_sheet(title="Riepilogo")
    ws.sheet_view.showGridLines = False
    banner(ws, 1, 8, "Riepilogo per epoca")
    hdr = ["Epoch", "Proposer", "Tot Tx Epoch", "Tot Impatto", "Tot Tx Miner",
           "GAS distribuito", "GAS resi all'ADMIN", "% Reso media"]
    for j, h in enumerate(hdr, start=1):
        put(ws, 2, j, h, bold=True, fill=HDR_FILL, align="center")
    r = 3
    for e in model.epochs:
        rows = [model.eco[(e, c)] for c in model.clusters if (e, c) in model.eco]
        impatto = sum(x["impatto_cluster"] for x in rows)
        guad = sum(x["guadagno"] for x in rows)
        resi = sum(x["resi"] for x in rows)
        pct = (resi / guad * 100.0) if guad > 0 else 0.0
        put(ws, r, 1, e, align="center")
        put(ws, r, 2, model.proposer.get(e, ""), bold=True, align="center")
        put(ws, r, 3, model.theta.get(e, 0), align="center")
        put(ws, r, 4, impatto, num=IMPACT, align="center")
        put(ws, r, 5, sum(x["tx_miner"] for x in rows), align="center")
        put(ws, r, 6, guad, num=MONEY, align="center")
        put(ws, r, 7, resi, num=MONEY, align="center")
        put(ws, r, 8, pct, num=PCT, align="center")
        r += 1

    r += 1
    banner(ws, r, 8, "Totali della run per cluster")
    r += 1
    for j, h in enumerate(["ClusterMiner", "Tx Miner", "Guadagno (EUR)", "Resi (EUR)",
                           "% Reso", "Giacenza finale", "Total GAIN", "Peso % medio"],
                          start=1):
        put(ws, r, j, h, bold=True, fill=HDR_FILL, align="center")
    r += 1
    for label in model.clusters:
        guad = model.run_total(label, "guadagno")
        resi = model.run_total(label, "resi")
        last = model.eco.get((model.epochs[-1], label), {}) if model.epochs else {}
        put(ws, r, 1, label, bold=True, fill=MINER_FILL)
        put(ws, r, 2, model.run_total(label, "tx_miner"), align="center")
        put(ws, r, 3, guad, num=MONEY, align="center")
        put(ws, r, 4, resi, num=MONEY, align="center")
        put(ws, r, 5, (resi / guad * 100.0) if guad > 0 else 0.0, num=PCT, align="center")
        put(ws, r, 6, last.get("giacenza", 0.0), num=GAS4, align="center")
        put(ws, r, 7, last.get("total_gain", 0.0), num=MONEY, align="center")
        put(ws, r, 8, model.mean_prob(label) * 100.0, num=PCT, align="center")
        r += 1
    widths(ws, [26, 14, 16, 14, 12, 16, 14, 14])


def write_weights_matrix(wb, model):
    ws = wb.create_sheet(title="Pesi & Probabilita")
    ws.sheet_view.showGridLines = False
    n = len(model.clusters)
    banner(ws, 1, n + 2, "Peso pubblicato dall'engine (wpoa-weights) per epoca × cluster")
    hr = 2
    put(ws, hr, 1, "Epoch", bold=True, fill=HDR_FILL, align="center")
    for j, m in enumerate(model.clusters, start=2):
        put(ws, hr, j, m, bold=True, fill=HDR_FILL, align="center")
    put(ws, hr, n + 2, "Proposer", bold=True, fill=HDR_FILL, align="center")
    r = hr + 1
    for e in model.epochs:
        put(ws, r, 1, e, align="center")
        for j, m in enumerate(model.clusters, start=2):
            put(ws, r, j, model.eco.get((e, m), {}).get("engine_weight", 0), align="center")
        put(ws, r, n + 2, model.proposer.get(e, ""), align="center", bold=True)
        r += 1

    r += 1
    banner(ws, r, n + 2, "Probabilita di selezione (peso / Σ pesi)")
    r += 1
    put(ws, r, 1, "Epoch", bold=True, fill=HDR_FILL, align="center")
    for j, m in enumerate(model.clusters, start=2):
        put(ws, r, j, m, bold=True, fill=HDR_FILL, align="center")
    r += 1
    for e in model.epochs:
        put(ws, r, 1, e, align="center")
        for j, m in enumerate(model.clusters, start=2):
            put(ws, r, j, model.eco.get((e, m), {}).get("engine_prob", 0.0),
                num=PROB, align="center")
        r += 1
    ws.column_dimensions["A"].width = 10
    for j in range(2, n + 3):
        ws.column_dimensions[get_column_letter(j)].width = 18


def write_proposer_log(wb, model):
    if not model.plog:
        return
    ws = wb.create_sheet(title="Proposer log (wpoa)")
    ws.sheet_view.showGridLines = False
    headers = list(model.plog[0].keys())
    for j, h in enumerate(headers, start=1):
        put(ws, 1, j, h, bold=True, fill=HDR_FILL, align="center")
    for i, row in enumerate(model.plog, start=2):
        for j, h in enumerate(headers, start=1):
            v = row[h]
            put(ws, i, j, to_float(v) if re.fullmatch(r"-?\d+(\.\d+)?", v or "") else v,
                align="center")
    for j, h in enumerate(headers, start=1):
        ws.column_dimensions[get_column_letter(j)].width = max(14, min(32, len(h) + 2))


def write_checks(wb, model):
    if not model.checks:
        return
    ws = wb.create_sheet(title="Verifiche")
    ws.sheet_view.showGridLines = False
    banner(ws, 1, 4, "Invarianti verificate a fine run (output/assertions.csv)")
    for j, h in enumerate(["Check", "Ambito", "Esito", "Dettaglio"], start=1):
        put(ws, 2, j, h, bold=True, fill=HDR_FILL, align="center")
    r = 3
    for c in model.checks:
        ok = (c.get("verdict") or "").upper() == "PASS"
        fill = TOT_FILL if ok else FAIL_FILL
        put(ws, r, 1, c.get("check", ""), bold=True, fill=fill)
        put(ws, r, 2, c.get("scope", ""), fill=fill)
        put(ws, r, 3, c.get("verdict", ""), bold=True, fill=fill, align="center")
        put(ws, r, 4, c.get("detail", ""), fill=fill)
        r += 1
    widths(ws, [30, 24, 10, 110])


# ---------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(
        description="Vers_2 / POESIA-style xlsx report from the experiment output")
    ap.add_argument("--dir", default=os.path.join(HERE, "output"),
                    help="directory with the experiment CSVs (default: ./output)")
    ap.add_argument("--out", default=None,
                    help="output .xlsx path (default: <dir>/report.xlsx)")
    args = ap.parse_args()

    outdir = args.dir
    out_xlsx = args.out or os.path.join(outdir, "report.xlsx")

    model = Model(outdir)
    if not model.epochs:
        sys.stderr.write(
            "ERROR: no epoch data found in %s -- run experimental_test.py first "
            "(cluster_economics.csv is missing or empty).\n" % outdir)
        return 1

    wb = Workbook()
    wb.remove(wb.active)                     # drop the default empty sheet
    write_config_sheet(wb, model)
    for e in model.epochs:
        write_epoch_sheet(wb, model, e)
    write_overview(wb, model)
    write_weights_matrix(wb, model)
    write_proposer_log(wb, model)
    write_checks(wb, model)

    wb.save(out_xlsx)
    print("wrote %s" % out_xlsx)
    print("  sheets: Foglio di configurazione, %d epoch sheet(s) (%d..%d), "
          "Riepilogo, Pesi & Probabilita%s%s"
          % (len(model.epochs), model.epochs[0], model.epochs[-1],
             ", Proposer log" if model.plog else "",
             ", Verifiche" if model.checks else ""))
    return 0


if __name__ == "__main__":
    sys.exit(main())
