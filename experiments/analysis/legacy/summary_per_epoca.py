#!/usr/bin/env python3
"""
Riepilogo PER EPOCA di una run Shadow: `metrics/summary_epoche.txt`.

Stessa struttura e stesse analisi di `metrics/summary.txt` — intervallo fra
blocchi, distribuzione dei proposer con valori osservati e attesi, chi-quadro,
delay di sortition e margine della timer race, catena del peso, riconciliazione,
traffico, verifica indipendente — ma calcolate **epoca per epoca** invece che una
volta sola su tutta la finestra di misura.

    # tutta la campagna archiviata: un file per esperimento
    python3 tools/summary_per_epoca.py --root esperimenti

    # una singola run (e' la forma che usa run.sh a fine simulazione)
    python3 tools/summary_per_epoca.py --run <rundir> --level continentale

PERCHE' NON BASTA summary.txt. Il riepilogo di run confronta i blocchi di TUTTA
la finestra con l'ULTIMO peso pubblicato, e lo dichiara: se il peso e' cambiato
fra le epoche — ed e' proprio quello che il weight engine fa — il test e' solo
indicativo. Qui ogni epoca e' confrontata col peso che era davvero leggibile
alla punta della catena mentre quei blocchi venivano proposti. Sono due
grandezze diverse e la differenza non e' un dettaglio: il peso marcato `epoch=e`
viene pubblicato a epoca GIA' FINITA e entra in vigore dentro l'epoca `e+1`.

La matematica della catena del peso non e' riscritta qui: viene importata da
`analizza_esperimenti.py`, che la implementa e la verifica contro i pesi
pubblicati. Questo script ne e' la resa testuale per epoca, non una seconda
implementazione — un'unica fonte di verita' per le formule.

Sola libreria standard.
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

from . import analizza_esperimenti as az     # noqa: E402
from ..layout import resolve as resolve_layout  # noqa: E402

W_HEAD = 66        # larghezza delle cornici ═, come in summary.txt
W_SEC = 63         # larghezza delle righe di sezione ─


def head(title):
    return ["", "═" * W_HEAD, "  " + title, "═" * W_HEAD]


def sec(title):
    line = "── {} ".format(title)
    return line + "─" * max(3, W_SEC - len(line))


def fmt(value, spec="{}"):
    """Formatta un numero, o restituisce '-' se il dato non c'e'.

    Mai un valore di comodo al posto di un dato mancante: se una colonna non e'
    ricostruibile per quella epoca resta un trattino, e il lettore lo vede.
    """
    if value is None or value == "":
        return "-"
    try:
        return spec.format(value)
    except (ValueError, TypeError):
        return str(value)


# --------------------------------------------------------------------------
# raccolta dei dati per epoca
# --------------------------------------------------------------------------

def delays_per_epoca(run, meta):
    """Delay di sortition raggruppati per epoca: per host e margine G.

    E' l'unico blocco di analisi che `analizza_esperimenti.py` produce solo
    aggregato su tutta la run, quindi viene ricalcolato qui a partire dalla
    stessa sorgente (le righe `wPoA-sortition height=... delay=...s` dei
    debug.log) e con la stessa regola: le altezze dentro la fase di setup non
    contano, perche' li' la wPoA non governa ancora la selezione.
    """
    epoch_len = meta["epoch_len"]
    setup = meta["setup_blocks"]
    per_epoca_host = defaultdict(lambda: defaultdict(list))
    per_epoca_height = defaultdict(lambda: defaultdict(dict))
    for host, log_path in az.find_debug_logs(run["data"]):
        try:
            with log_path.open(encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if "wPoA-sortition" not in line:
                        continue
                    m = az.DELAY_RE.search(line)
                    if not m:
                        continue
                    height, delay = int(m.group(1)), float(m.group(3))
                    if height <= setup:
                        continue
                    e = az.epoch_of(height, epoch_len)
                    per_epoca_host[e][host].append(delay)
                    per_epoca_height[e][height][host] = delay
        except OSError as exc:
            print("ATTENZIONE: debug.log illeggibile %s: %s" % (log_path, exc),
                  file=sys.stderr)
    out = {}
    for e in sorted(set(per_epoca_host) | set(per_epoca_height)):
        margins = sorted(sorted(d.values())[1] - sorted(d.values())[0]
                         for d in per_epoca_height[e].values() if len(d) >= 2)
        out[e] = {"per_host": dict(per_epoca_host[e]), "margini": margins}
    return out


# Righe del motore dei pesi nei debug.log. Sono l'unica traccia PER EPOCA della
# verifica indipendente che sopravviva a posteriori: la RPC weightverifyweights
# riporta solo l'ultima epoca verificata, ma il motore logga l'esito di OGNI
# epoca appena la chiude, su ogni nodo. (weight_verifier.cpp, righe 68-102;
# weight_engine.cpp riga 360 per la pubblicazione.)
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
RANDAO_RE = re.compile(r"\[wPoA-RANDAO\] seed for height=(\d+)")


def motore_pesi_per_epoca(run, meta):
    """Pubblicazioni e verifiche del weight engine, per epoca, da ogni debug.log.

    Recupera a posteriori cio' che la RPC non conserva: l'esito della verifica
    indipendente epoca per epoca, e su OGNI nodo, non solo sull'admin. E' una
    misura diretta ([M]): e' il nodo stesso che ha scritto quella riga nel
    momento in cui ha chiuso l'epoca.

    Il conteggio `confrontati di totali` non e' un dettaglio: un record marcato
    con un'altra epoca non viene confrontato, e riportare "tutto verificato"
    quando nulla era confrontabile nasconderebbe che la verifica non c'e' stata.
    """
    epoch_len = meta["epoch_len"]
    pub = defaultdict(list)
    ver = defaultdict(dict)
    randao = Counter()
    for host, log_path in az.find_debug_logs(run["data"]):
        try:
            text = log_path.read_text(errors="replace")
        except OSError:
            continue
        for line in text.splitlines():
            if "[wPoA-RANDAO] seed for height=" in line:
                m = RANDAO_RE.search(line)
                if m:
                    e = az.epoch_of(int(m.group(1)), epoch_len)
                    if e:
                        randao[e] += 1
                continue
            if "[WeightEngine] epoch " not in line:
                continue
            m = WE_PUB_RE.search(line)
            if m:
                e = int(m.group(1))
                rec = (host, m.group(4), int(m.group(3)), int(m.group(2)))
                if rec not in pub[e]:
                    pub[e].append(rec)
                continue
            m = WE_OK_RE.search(line)
            if m:
                tot = int(m.group(3))
                ver[int(m.group(1))][host] = {
                    "confrontati": int(m.group(2)), "totali": tot,
                    "non_validi": 0, "altra_epoca": int(m.group(4)),
                    # Un nodo senza record da confrontare non ha "verificato
                    # tutto": non ha verificato niente. Le aziende non
                    # pubblicano pesi, quindi e' il loro caso normale.
                    "esito": ("tutti coincidenti" if tot else
                              "nessun record da confrontare")}
                continue
            m = WE_FAIL_RE.search(line)
            if m:
                ver[int(m.group(1))][host] = {
                    "confrontati": int(m.group(3)), "totali": int(m.group(3)),
                    "non_validi": int(m.group(2)), "altra_epoca": "",
                    "esito": "VERIFICA FALLITA"}
                continue
            m = WE_NOTVER_RE.search(line)
            if m:
                ver[int(m.group(1))].setdefault(host, {
                    "confrontati": 0, "totali": "", "non_validi": "",
                    "altra_epoca": "", "esito": "input non ancora leggibili"})
    return {"pubblicazioni": dict(pub), "verifiche": dict(ver), "randao": randao}


def verify_per_epoca(run):
    """Verdetti di `weightverifyweights` catturati epoca per epoca durante la run.

    NON e' ricostruibile a posteriori: la RPC riporta solo l'ULTIMA epoca che il
    nodo ha verificato, quindi lo snapshot finale ne conserva una sola. Il file
    `metrics/epoche/verify_epoche.jsonl` viene scritto dal sorvegliante di epoca
    (`role_admin.sh epoch_watch`) mentre la simulazione gira. Sulle run
    archiviate prima di quella modifica il file non esiste: le sezioni relative
    lo dichiarano invece di inventare un verdetto.
    """
    path = resolve_layout(run["path"]).epoch_file(
        "verify_epochs.jsonl", "verify_epoche.jsonl")
    out = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        res = rec.get("verify") or {}
        if isinstance(res, dict) and "result" in res:
            res = res["result"] or {}
        e = az.as_int(rec.get("epoca_richiesta"))
        if e is not None:
            out[e] = {"height": az.as_int(rec.get("height")), "res": res}
    return out


def node_state_per_epoca(run):
    """Altezze e best-hash per nodo, campionati a ogni epoca (fork per epoca).

    Anche questo non e' ricostruibile a posteriori: `node_state.csv` e' un'unica
    istantanea di fine run, quindi un fork riassorbito a metà simulazione non
    lascerebbe traccia. Scritto dal sorvegliante di epoca.
    """
    path = resolve_layout(run["path"]).epoch_file(
        "node_state_epochs.csv", "node_state_epoche.csv")
    out = defaultdict(list)
    if not path.is_file():
        return out
    header, rows = az.read_csv_rows(path, has_header=True)
    for row in rows:
        if len(row) < 6:
            continue
        e = az.as_int(row[0])
        if e is None:
            continue
        out[e].append({"height_admin": az.as_int(row[1]), "host": row[2].strip(),
                       "height": az.as_int(row[3]), "besthash": row[4].strip(),
                       "peers": az.as_int(row[5])})
    return out


def treasury_per_epoca(run):
    path = resolve_layout(run["path"]).epoch_file(
        "treasury_epochs.csv", "treasury_epoche.csv")
    out = {}
    if not path.is_file():
        return out
    header, rows = az.read_csv_rows(path, has_header=True)
    for row in rows:
        if len(row) < 3:
            continue
        e = az.as_int(row[0])
        if e is not None:
            out[e] = (az.as_int(row[1]), az.as_float(row[2]))
    return out


def pesi_vigenti_per_epoca(run, meta, blocks, txindex):
    """Per ogni epoca, la mappa dei pesi DAVVERO leggibile al primo e all'ultimo
    blocco dell'epoca, con l'epoca di cui portano la marca.

    Serve a rendere visibile in chiaro lo sfasamento di una epoca fra
    pubblicazione e vigenza: nella colonna `marca` si legge che dentro l'epoca e
    vale, tipicamente, il record marcato e-1.
    """
    epoch_len = meta["epoch_len"]
    setup = meta["setup_blocks"]
    recs = az._weight_records(run, txindex)
    inforce, idx = {}, 0
    out = defaultdict(lambda: {"inizio": {}, "fine": {}})
    for blk in blocks:
        h = blk["height"]
        while idx < len(recs) and recs[idx]["height_conferma"] is not None \
                and recs[idx]["height_conferma"] < h:
            inforce[recs[idx]["address"]] = recs[idx]
            idx += 1
        if h <= setup:
            continue
        e = az.epoch_of(h, epoch_len)
        snap = {a: (r["peso"], r["epoca"]) for a, r in inforce.items()}
        if not out[e]["inizio"]:
            out[e]["inizio"] = snap
        out[e]["fine"] = snap
    return out


# --------------------------------------------------------------------------
# resa testuale, una sezione per epoca
# --------------------------------------------------------------------------

def blocco_epoca(out, e, meta, blocks_e, dt_target, pr_e, delays_e, pesi_e,
                 verify_e, nodi_e, treasury_e, motore_e, host_by_addr, addr_by_host):
    epoch_len = meta["epoch_len"]
    h_lo = (e - 1) * epoch_len
    h_hi = e * epoch_len - 1
    out.append("")
    out.append(sec("Epoca {}  (altezze {}..{})".format(e, h_lo, h_hi)))

    # --- blocchi dell'epoca ------------------------------------------------
    if not blocks_e:
        out.append("  nessun blocco misurato in questa epoca (fase di setup, o "
                   "epoca senza blocchi oltre il setup).")
    else:
        out.append("  blocchi misurati    : {} (height {}..{})".format(
            len(blocks_e), blocks_e[0]["height"], blocks_e[-1]["height"]))
        deltas = [blocks_e[i]["time"] - blocks_e[i - 1]["time"]
                  for i in range(1, len(blocks_e))]
        deltas = [d for d in deltas if d >= 0]
        if deltas:
            mean = statistics.mean(deltas)
            out.append("  intervallo fra blocchi, target = {} s:".format(dt_target))
            out.append("    media   {:8.2f} s     scarto vs target {:+.2f} s ({:+.1f}%)"
                       .format(mean, mean - dt_target,
                               100.0 * (mean - dt_target) / dt_target if dt_target else 0.0))
            out.append("    mediana {:8.2f} s".format(statistics.median(deltas)))
            out.append("    dev.std {:8.2f} s".format(
                statistics.pstdev(deltas) if len(deltas) > 1 else 0.0))
            out.append("    min/max {:8.2f} / {:.2f} s".format(min(deltas), max(deltas)))
        else:
            out.append("  un solo blocco: nessun intervallo misurabile.")

    # --- peso in vigore vs peso marcato ------------------------------------
    vig = (pesi_e or {}).get("fine") or {}
    out.append("")
    out.append("  Peso VIGENTE all'ultimo blocco dell'epoca (mappa leggibile alla punta)")
    if not vig:
        out.append("    nessun peso leggibile: l'epoca precede la prima pubblicazione.")
    else:
        tot_v = sum(w for w, _m in vig.values()) or 0
        out.append("    {:<6} {:>12} {:>8} {:>9}".format("host", "peso", "marca", "quota"))
        for a in sorted(vig, key=lambda a: -vig[a][0]):
            w, marca = vig[a]
            out.append("    {:<6} {:>12} {:>8} {:>8.1%}".format(
                host_by_addr.get(a, a[:6]), w,
                "e{}".format(marca) if marca is not None else "-",
                (w / tot_v) if tot_v else 0.0))
        out.append("    (la marca e' l'epoca di cui il record dichiara il peso: dentro")
        out.append("     l'epoca {} vale di norma il record marcato e{}, perche' il motore".format(e, e - 1))
        out.append("     pubblica a epoca chiusa, dopo il margine di stabilita')")

    # --- catena del peso, anello per anello --------------------------------
    if pr_e:
        out.append("")
        out.append("  Catena del peso di QUESTA epoca (Def. 6.1-6.9)")
        out.append("    {:<6} {:>8} {:>7} {:>10} {:>9} {:>9} {:>8} {:>7} {:>11} {:>11} {:>10}".format(
            "host", "ESG", "tau_Mk", "tau_clus", "W_k", "A_k", "R_k", "rho", "rho(e-1)",
            "w_k pubbl.", "ricalcolo"))
        for r in pr_e:
            out.append("    {:<6} {:>8} {:>7} {:>10} {:>9} {:>9} {:>8} {:>7} {:>11} {:>11} {:>10}".format(
                r["host"], fmt(r["esg_miner"], "{:.2f}"), fmt(r["attivita_miner_tau"]),
                fmt(r["attivita_cluster_tau_somma"]),
                fmt(r["peso_grezzo_epoca"], "{:.1f}"), fmt(r["allocazione_A_k"], "{:.2f}"),
                fmt(r["riconciliato_R_k"], "{:.2f}"), fmt(r["rho_epoca"], "{:.3f}"),
                fmt(r["rho_epoca_precedente"], "{:.3f}"),
                fmt(r["peso_pubblicato_epoca"]), fmt(r["peso_pubblicato_ricalcolato"])))
        esiti = Counter(r["esito_ricalcolo"] for r in pr_e)
        out.append("    ricalcolabilita' (Sez. 5.11.1): " + ", ".join(
            "{} {}".format(n, k) for k, n in sorted(esiti.items())))
        scost = [r for r in pr_e if r["esito_ricalcolo"] == "scostamento"]
        for r in scost:
            out.append("    ATTENZIONE {}: pubblicato {} contro {} ricalcolato "
                       "(scarto {:+})".format(
                           r["host"], r["peso_pubblicato_epoca"],
                           r["peso_pubblicato_ricalcolato"], r["scarto_ricalcolo"]))
        if scost:
            # Uno scostamento qui NON dimostra da solo che il protocollo abbia
            # violato la ricalcolabilita'. Ci sono due ricalcoli indipendenti: il
            # verificatore interno di ogni nodo, che legge i blocchi veri, e
            # questa pipeline, che ricostruisce l'attribuzione delle transazioni
            # alle epoche da txs.log. Quando il primo dice "tutti coincidenti" e
            # il secondo no, a divergere e' il modello di attribuzione, non il
            # peso sulla catena — ed e' la pipeline che va corretta.
            ver_log = (motore_e or {}).get("verifiche") or {}
            falliti = [h for h, v in ver_log.items() if v.get("non_validi")]
            confrontanti = [h for h, v in ver_log.items() if v.get("confrontati")]
            if falliti:
                out.append("    -> i nodi {} segnalano un record NON valido nel proprio"
                           .format(", ".join(sorted(falliti))))
                out.append("       verificatore interno per questa epoca: lo scostamento")
                out.append("       e' sulla CATENA, non nel modello di attribuzione.")
            elif confrontanti:
                out.append("    -> ma il verificatore interno dei nodi {} dichiara TUTTI"
                           .format(", ".join(sorted(confrontanti))))
                out.append("       i record coincidenti per questa epoca (vedi sotto): a")
                out.append("       divergere e' l'attribuzione delle transazioni alle")
                out.append("       epoche fatta qui, non il peso pubblicato sulla catena.")
        contrib = [r for r in pr_e if r["contributi_c_i_lista"]]
        if contrib:
            out.append("    attivita' tau_i delle aziende del cluster, transazioni "
                       "CONFERMATE nell'epoca:")
            for r in contrib:
                out.append("      {:<6} <- {}".format(
                    r["host"], r["attivita_cluster_tau_lista"] or "-"))
            out.append("    contributi c_i = ESG_i*tau_i/kappa  (kappa = {}):".format(
                fmt(meta.get("weight_kappa"))))
            for r in contrib:
                out.append("      {:<6} <- {}".format(r["host"], r["contributi_c_i_lista"]))
            out.append("    Theta (attivita' di rete, somma dei soli tau delle aziende) "
                       "= {}".format(fmt(pr_e[0].get("theta_epoca"), "{:.0f}")))

    # --- proposer: osservati vs attesi, chi-quadro -------------------------
    out.append("")
    out.append("  Distribuzione dei proposer vs peso VIGENTE nell'epoca")
    if not pr_e or not blocks_e:
        out.append("    nessun blocco da confrontare.")
    else:
        tot_blk = pr_e[0]["blocchi_totali_epoca"] or 0
        out.append("    {:<6} {:<40} {:>9} {:>9} {:>9} {:>9}".format(
            "host", "indirizzo", "osservati", "attesi", "q.oss.", "q.attesa"))
        for r in sorted(pr_e, key=lambda r: -(r["blocchi_minati_epoca"] or 0)):
            q_att = az.as_float(r["quota_attesa_vigenza"])
            attesi = (q_att * tot_blk) if (q_att is not None and tot_blk) else None
            out.append("    {:<6} {:<40} {:>9} {:>9} {:>8.1%} {:>8.1%}".format(
                r["host"], r["indirizzo"], r["blocchi_minati_epoca"],
                fmt(attesi, "{:.2f}"),
                az.as_float(r["quota_osservata_epoca"], 0.0) or 0.0,
                q_att if q_att is not None else 0.0))
        out.append("    scostamento massimo |osservata - attesa|: {:.1%}".format(
            max((abs(az.as_float(r["scostamento_quota"], 0.0) or 0.0) for r in pr_e),
                default=0.0)))

        seq = [b.get("miner") for b in blocks_e if b.get("miner")]
        consec = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
        quote = [az.as_float(r["quota_osservata_epoca"], 0.0) or 0.0 for r in pr_e]
        out.append("    blocchi consecutivi dello stesso proposer: {} osservati, "
                   "{:.1f} attesi".format(
                       consec, sum(p * p for p in quote) * max(0, len(seq) - 1)))

        r0 = pr_e[0]
        chi2, df = r0["chi2_epoca"], r0["df_epoca"]
        crit, att_min = r0["chi2_critico_5pct"], r0["attesa_minima_epoca"]
        out.append("")
        if chi2 == "" or chi2 is None:
            out.append("    chi-quadro dell'epoca: non calcolabile (nessuna attesa positiva).")
        else:
            verdetto = ("compatibile" if r0["compatibile_epoca"] == 1
                        else "NON compatibile" if r0["compatibile_epoca"] == 0 else "?")
            out.append("    chi-quadro dell'epoca = {:.3f}  (df={}, critico 5% = {})  -> {}"
                       .format(chi2, df, crit, verdetto))
            out.append("    attesa minima per classe: {}   campione sufficiente (>=5): {}"
                       .format(fmt(att_min, "{:.2f}"),
                               "SI" if r0["campione_sufficiente_epoca"] == 1 else "NO"))
            if r0["campione_sufficiente_epoca"] != 1:
                out.append("    NB: con attesa < 5 il chi-quadro su una sola epoca NON e'")
                out.append("        concludente. Con epoche di {} blocchi e' la norma, non un".format(epoch_len))
                out.append("        difetto: vale la finestra scorrevole qui sotto.")
        if r0["chi2_finestra"] not in ("", None):
            v = ("compatibile" if r0["compatibile_finestra"] == 1
                 else "NON compatibile" if r0["compatibile_finestra"] == 0 else "?")
            out.append("    chi-quadro a finestra ({} epoche, {} blocchi) = {:.3f} "
                       "(df={}, critico 5% = {}) -> {}".format(
                           r0["finestra_epoche"], r0["blocchi_finestra"],
                           r0["chi2_finestra"], r0["df_finestra"],
                           az.CHI2_CRIT_05.get(r0["df_finestra"], "-"), v))
            out.append("    attesa minima nella finestra: {}   sufficiente: {}".format(
                fmt(r0["attesa_minima_finestra"], "{:.2f}"),
                "SI" if r0["campione_sufficiente_finestra"] == 1 else "NO"))

    # --- delay di sortition nell'epoca ------------------------------------
    out.append("")
    tbt = meta["tbt"]
    delta = meta["delta"] or 0.5
    dmax = delta * tbt
    lo, hi = tbt - dmax, tbt + dmax
    span = (hi - lo) or 1.0
    out.append("  Delay di sortition nell'epoca — banda [{:.2f}, {:.2f}] s "
               "(T={} s, delta={}, Dmax={:.2f} s)".format(lo, hi, tbt, delta, dmax))
    if not delays_e or not delays_e.get("per_host"):
        out.append("    nessun campione di delay nei debug.log per questa epoca.")
    else:
        out.append("    {:<6} {:>9} {:>9} {:>9} {:>9} {:>14}".format(
            "host", "campioni", "min s", "media s", "max s", "pos. in banda"))
        for host in sorted(delays_e["per_host"]):
            vals = delays_e["per_host"][host]
            mean = statistics.mean(vals)
            out.append("    {:<6} {:>9} {:>9.3f} {:>9.3f} {:>9.3f} {:>13.1%}".format(
                host, len(vals), min(vals), mean, max(vals), (mean - lo) / span))
        margini = delays_e["margini"]
        if margini:
            tiny = sum(1 for g in margini if g < 0.1)
            out.append("    margine della timer race G = D(2)-D(1) (Def. 5.15, su {} round):"
                       .format(len(margini)))
            out.append("      media {:.3f} s   mediana {:.3f} s   minimo {:.3f} s   "
                       "5o perc. {:.3f} s".format(
                           statistics.mean(margini), statistics.median(margini),
                           margini[0], margini[max(0, len(margini) // 20)]))
            out.append("      round con G < 100 ms: {} su {} ({:.1%})".format(
                tiny, len(margini), tiny / len(margini)))
            if tiny / len(margini) > 0.05:
                out.append("      -> in questi round il margine e' dell'ordine della latenza")
                out.append("         di rete: il vincitore osservato puo' differire da quello")
                out.append("         designato dallo score (Prop. 5.18), e la distribuzione")
                out.append("         dei proposer si appiattisce rispetto ai pesi.")

    # --- riconciliazione e saldo ------------------------------------------
    if pr_e:
        out.append("")
        out.append("  Riconciliazione verso il treasury in questa epoca (Def. 6.7-6.8)")
        out.append("    {:<6} {:>10} {:>12} {:>10} {:>10} {:>9}".format(
            "host", "A_k", "B(e-1)", "R_k", "B(e)", "rho"))
        for r in pr_e:
            def z(v):
                # -0.0000 e' 0: l'arrotondamento di un residuo negativo
                # infinitesimo, non un saldo negativo.
                f = az.as_float(v)
                return (f + 0.0) if f is not None and abs(f) < 5e-5 else v
            out.append("    {:<6} {:>10} {:>12} {:>10} {:>10} {:>9}".format(
                r["host"], fmt(z(r["allocazione_A_k"]), "{:.4f}"),
                fmt(z(r["saldo_B_precedente"]), "{:.4f}"),
                fmt(z(r["riconciliato_R_k"]), "{:.4f}"),
                fmt(z(r["saldo_B_epoca"]), "{:.4f}"), fmt(z(r["rho_epoca"]), "{:.4f}")))
        if treasury_e:
            out.append("    saldo del treasury campionato a height {}: {} GAS".format(
                fmt(treasury_e[0]), fmt(treasury_e[1], "{:.4f}")))
        out.append("    (importi in GAS, unita' di visualizzazione della valuta nativa)")

    # --- verifica indipendente per epoca ----------------------------------
    out.append("")
    out.append("  Verifica indipendente dei pesi pubblicati per l'epoca {}".format(e))
    mot = motore_e or {}
    pubbl = mot.get("pubblicazioni") or []
    if pubbl:
        out.append("    pubblicazioni del motore (da debug.log, [M]): " + "  ".join(
            "{}={} @h{}".format(host_by_addr.get(a, h), w, hh)
            for h, a, w, hh in sorted(pubbl, key=lambda t: t[0])))
    verifiche = mot.get("verifiche") or {}
    if verifiche:
        out.append("    esito della ricomputazione indipendente, nodo per nodo "
                   "(da debug.log, [M]):")
        out.append("      {:<6} {:>12} {:>8} {:>12} {:>12}   {}".format(
            "nodo", "confrontati", "totali", "non validi", "altra epoca", "esito"))
        for host in sorted(verifiche):
            v = verifiche[host]
            out.append("      {:<6} {:>12} {:>8} {:>12} {:>12}   {}".format(
                host, fmt(v["confrontati"]), fmt(v["totali"]), fmt(v["non_validi"]),
                fmt(v["altra_epoca"]), v["esito"]))
        falliti = [h for h, v in verifiche.items() if v["non_validi"]]
        if falliti:
            out.append("      ATTENZIONE: verifica fallita su {} — un peso pubblicato "
                       "non regge la ricomputazione (Sez. 5.11.1).".format(
                           ", ".join(sorted(falliti))))
    else:
        out.append("    nessuna riga di verifica nei debug.log per questa epoca: il")
        out.append("    motore non l'ha ancora chiusa, oppure i log non sono disponibili.")
    out.append("    snapshot RPC weightverifyweights all'epoca {}:".format(e))
    if not verify_e:
        out.append("      non catturato. La RPC riporta solo l'ULTIMA epoca verificata,")
        out.append("      quindi il verdetto per epoca esiste solo se campionato durante")
        out.append("      la run (metrics/epoche/verify_epoche.jsonl, scritto da")
        out.append("      role_admin.sh epoch_watch). Questa run non lo ha: la tabella")
        out.append("      qui sopra, ricavata dai debug.log, resta la fonte per epoca.")
    else:
        res = verify_e["res"]
        out.append("      epoca verificata dal nodo: {}   verified: {}   record: {}   "
                   "non validi: {}".format(
                       res.get("epoch", "-"), res.get("verified", "-"),
                       res.get("records", "-"), res.get("invalid", "-")))
        for ent in (res.get("entries") or []):
            out.append("        {:<40} pubblicato {:>10}  ricalcolato {:>10}  {}".format(
                ent.get("address", "?"), ent.get("published", "-"),
                ent.get("recomputed", "-"), ent.get("verdict", "?")))

    # --- contatori diagnostici che portano un'altezza ---------------------
    n_randao = (motore_e or {}).get("randao_epoca")
    n_score = sum(len(v) for v in (delays_e or {}).get("per_host", {}).values())
    if n_randao is not None or n_score:
        out.append("")
        out.append("  Contatori diagnostici dell'epoca (dai debug.log)")
        out.append("    score di sortition calcolati    {}".format(n_score))
        out.append("    seed RANDAO derivati            {}".format(fmt(n_randao)))
        out.append("    (solo i contatori le cui righe di log portano un'altezza sono")
        out.append("     attribuibili a un'epoca; gli altri restano nel totale di run")
        out.append("     in summary.txt)")

    # --- consistenza fra nodi in questa epoca -----------------------------
    if nodi_e:
        tips = Counter(n["besthash"] for n in nodi_e if n["besthash"])
        heights = [n["height"] for n in nodi_e if n["height"] is not None]
        out.append("")
        out.append("  Consistenza fra nodi campionata in questa epoca")
        out.append("    nodi {}   teste distinte {}   altezze {}..{} (spread {})".format(
            len(nodi_e), len(tips), min(heights) if heights else "-",
            max(heights) if heights else "-",
            (max(heights) - min(heights)) if heights else "-"))
        if len(tips) > 1:
            out.append("    teste diverse: {}".format(
                "  ".join("{}x{}".format(n, t[:16]) for t, n in tips.most_common())))
            out.append("    -> se le altezze distano 1 blocco e' ritardo di propagazione,")
            out.append("       non un fork; a distanze maggiori va indagato.")


def quadro_insieme(out, epoche, per_epoca, dt_target):
    """Una riga per epoca: la vista che si scorre in dieci secondi."""
    out.append("")
    out.append(sec("Quadro d'insieme per epoca"))
    out.append("  {:>6} {:>8} {:>9} {:>9} {:>7} {:>9} {:>6} {:>10} {:>11}".format(
        "epoca", "blocchi", "dt medio", "chi2", "df", "att.min", "suff.",
        "G mediano", "verdetto"))
    for e in epoche:
        d = per_epoca[e]
        pr_e, blocks_e, del_e = d["pr"], d["blocks"], d["delays"]
        deltas = [blocks_e[i]["time"] - blocks_e[i - 1]["time"]
                  for i in range(1, len(blocks_e))]
        deltas = [x for x in deltas if x >= 0]
        r0 = pr_e[0] if pr_e else {}
        margini = (del_e or {}).get("margini") or []
        comp = r0.get("compatibile_epoca", "")
        out.append("  {:>6} {:>8} {:>9} {:>9} {:>7} {:>9} {:>6} {:>10} {:>11}".format(
            e, len(blocks_e),
            fmt(statistics.mean(deltas) if deltas else None, "{:.2f}"),
            fmt(r0.get("chi2_epoca"), "{:.3f}"), fmt(r0.get("df_epoca")),
            fmt(r0.get("attesa_minima_epoca"), "{:.2f}"),
            "SI" if r0.get("campione_sufficiente_epoca") == 1 else "no",
            fmt(statistics.median(margini) if margini else None, "{:.3f}"),
            "compatibile" if comp == 1 else "NON compat." if comp == 0 else "-"))
    out.append("  (dt medio in s; att.min = attesa minima per classe del chi-quadro;")
    out.append("   suff. = attesa minima >= 5, la soglia sotto la quale il test su una")
    out.append("   singola epoca non e' concludente)")


# --------------------------------------------------------------------------
# costruzione del file
# --------------------------------------------------------------------------

def build(run, args):
    meta = az.extract_meta(run)
    maps = az.extract_host_maps(run)
    addr_by_host, host_by_addr, esg_by_host, cluster_by_host = maps
    txindex, _unconf = az.build_tx_index(run)
    events = az.extract_event_tables(run, meta, maps, txindex)

    all_blocks = az.rpc_result(run["metrics"] / "blocks.json") or []
    all_blocks = sorted((b for b in all_blocks if isinstance(b, dict) and "height" in b),
                        key=lambda b: b["height"])
    pr_rows, _log, n_scarti, _n_mal = az.compute_weight_reconciliation(
        run, meta, maps, events, txindex, all_blocks, args.finestra_epoche)

    epoch_len = meta["epoch_len"]
    setup = meta["setup_blocks"]
    dels = delays_per_epoca(run, meta)
    motore = motore_pesi_per_epoca(run, meta)
    ver = verify_per_epoca(run)
    nodi = node_state_per_epoca(run)
    treas = treasury_per_epoca(run)
    pesi = pesi_vigenti_per_epoca(run, meta, all_blocks, txindex)

    blocks_by_epoch = defaultdict(list)
    for b in all_blocks:
        if b["height"] > setup:
            blocks_by_epoch[az.epoch_of(b["height"], epoch_len)].append(b)
    pr_by_epoch = defaultdict(list)
    for r in pr_rows:
        pr_by_epoch[r["epoca"]].append(r)
    for e in pr_by_epoch:
        pr_by_epoch[e].sort(key=lambda r: r["host"])

    # Solo le epoche con blocchi misurati: un'epoca interamente dentro la fase
    # di setup non ha nulla da dire sulla selezione pesata.
    epoche = sorted(e for e in blocks_by_epoch if blocks_by_epoch[e])
    if args.solo_epoca:
        epoche = [e for e in epoche if e in args.solo_epoca]

    out = head("POESIA / wPoA — riepilogo PER EPOCA: livello {}".format(meta["livello"]))
    out.append("")
    out.append(sec("Parametri della run (da params.dat, non dal nome cartella)"))
    out.append("  run                  : {}".format(meta["run_id"]))
    out.append("  catena               : {}".format(meta.get("chain_name") or "-"))
    out.append("  target-block-time    : {} s   (nome cartella: {} s, mismatch: {})".format(
        meta["tbt"], run["tbt_dirname"], "SI" if meta["tbt_mismatch"] else "no"))
    out.append("  setup-first-blocks   : {} blocchi".format(setup))
    out.append("  weight-epoch-length  : {} blocchi   -> epoca(h) = h/{} + 1".format(
        epoch_len, epoch_len))
    out.append("  weight-kappa / alpha / lambda_w : {} / {} / {}".format(
        fmt(meta.get("weight_kappa")), fmt(meta.get("weight_alpha")),
        fmt(meta.get("weight_lambda"))))
    out.append("  wpoa-sortition delta / lambda   : {} / {}".format(
        fmt(meta.get("wpoa_sortition_delta")), fmt(meta.get("wpoa_sortition_lambda"))))
    out.append("  dump-function        : {}   (none = smorzamento anti-whale inerte)".format(
        meta.get("dump_function") or "-"))
    out.append("  mining-diversity     : {}   (0 = Spacing nativo inerte)".format(
        fmt(meta.get("mining_diversity"))))
    out.append("  malus mu / M_max     : {} / {}   record di malus nella run: {}".format(
        fmt(meta.get("wpoa_malus_mu")), fmt(meta.get("wpoa_malus_max")),
        len(az.rpc_result(run["metrics"] / "malus.json") or [])))
    out.append("  blocchi totali       : {}   epoche con blocchi misurati: {}".format(
        len(all_blocks), len(epoche)))
    out.append("  pesi non riprodotti dal ricalcolo, su tutta la run: {}".format(n_scarti))
    out.append("")
    out.append("  COME SI LEGGE. Ogni epoca e' confrontata col peso che era davvero")
    out.append("  leggibile alla punta della catena mentre i suoi blocchi venivano")
    out.append("  proposti, non con l'ultimo peso della run: il record marcato e viene")
    out.append("  pubblicato a epoca chiusa e vale dentro l'epoca e+1. Un peso che")
    out.append("  cresce di epoca in epoca perche' il cluster e' virtuoso, con la quota")
    out.append("  che lo segue, NON e' un'anomalia: e' il comportamento previsto.")

    per_epoca = {}
    for e in epoche:
        per_epoca[e] = {"pr": pr_by_epoch.get(e, []), "blocks": blocks_by_epoch[e],
                        "delays": dels.get(e)}

    if epoche:
        quadro_insieme(out, epoche, per_epoca, meta["tbt"])
    for e in epoche:
        mot_e = {"pubblicazioni": motore["pubblicazioni"].get(e, []),
                 "verifiche": motore["verifiche"].get(e, {}),
                 "randao_epoca": motore["randao"].get(e)}
        blocco_epoca(out, e, meta, blocks_by_epoch[e], meta["tbt"],
                     pr_by_epoch.get(e, []), dels.get(e), pesi.get(e),
                     ver.get(e), nodi.get(e), treas.get(e), mot_e,
                     host_by_addr, addr_by_host)

    out.append("")
    out.append(sec("ESG certificati dal CA (statici, invariati fra le epoche)"))
    for host in sorted(esg_by_host):
        out.append("  {:<6} {:<40} {}".format(
            host, addr_by_host.get(host, "-"), esg_by_host[host]))
    out.append("")
    out.append(sec("Adesioni ai cluster"))
    for host in sorted(cluster_by_host):
        out.append("  {:<6} -> cluster di {}".format(host, cluster_by_host[host]))
    out.append("")
    return "\n".join(out) + "\n"


def make_run(path, livello, tbt_dirname, run_dir, run_index):
    """A discovery record for one run directory, in either layout."""
    path = Path(path)
    if (path / "run").is_dir():          # the deprecated per-level tree
        metrics, data = path / "run" / "metrics", path / "run" / "data"
    else:
        layout = resolve_layout(path)
        metrics, data = layout.metrics, layout.data
    return {"run_id": "{}/{}".format(run_dir, livello) if run_dir else livello,
            "run_dir": run_dir or livello, "run_index": run_index,
            "tbt_dirname": tbt_dirname, "livello": livello, "path": path,
            "metrics": metrics, "data": data}


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", help="albero degli esperimenti: un file per esperimento")
    ap.add_argument("--run", help="una singola directory di run (contiene metrics/)")
    ap.add_argument("--level", default="", help="nome del livello, con --run")
    ap.add_argument("--tbt", type=int, default=0,
                    help="tbt atteso dal nome, con --run (solo per il controllo "
                         "di coerenza: il valore usato viene da params.dat)")
    ap.add_argument("--finestra-epoche", type=int, default=5, dest="finestra_epoche",
                    help="ampiezza della finestra scorrevole del chi-quadro (default 5)")
    ap.add_argument("--solo-epoca", type=int, nargs="*", dest="solo_epoca",
                    help="limita l'output a queste epoche")
    ap.add_argument("--nome", default="summary_epoche.txt",
                    help="nome del file scritto dentro metrics/")
    ap.add_argument("--stdout", action="store_true",
                    help="stampa anche su stdout, come collect_metrics.py")
    args = ap.parse_args()

    if not args.root and not args.run:
        ap.error("serve --root oppure --run")

    runs = []
    if args.run:
        p = Path(args.run).expanduser().resolve()
        runs.append(make_run(p, args.level or p.name, args.tbt or 0,
                             p.parent.name if args.level else "", 0))
    else:
        root = Path(args.root).expanduser().resolve()
        runs = az.discover_runs(root)

    scritti, falliti = 0, 0
    for run in runs:
        if not run["metrics"].is_dir():
            print("SALTATA {}: metrics/ assente".format(run["run_id"]), file=sys.stderr)
            falliti += 1
            continue
        try:
            text = build(run, args)
        except Exception as exc:            # una run rotta non ferma le altre
            print("ERRORE su {}: {}".format(run["run_id"], exc), file=sys.stderr)
            falliti += 1
            continue
        dest = run["metrics"] / args.nome
        dest.write_text(text, encoding="utf-8")
        scritti += 1
        if args.stdout:
            print(text)
        print("[summary_per_epoca] {} -> {} ({} righe)".format(
            run["run_id"], dest, text.count("\n")))
    print("[summary_per_epoca] {} file scritti, {} run saltate/in errore".format(
        scritti, falliti))
    return 0 if scritti else 1


if __name__ == "__main__":
    sys.exit(main())
