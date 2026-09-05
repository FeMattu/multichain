#!/usr/bin/env python3
"""
Estrae le metriche di una run e scrive un riepilogo leggibile + CSV.

Sorgente primaria: lo snapshot JSON prodotto dal nodo admin poco prima dello
stop (metrics/*.json). E' preferito al parsing dei debug.log perche' listblocks
riporta direttamente il proposer di ogni altezza. I debug.log servono solo per
i contatori diagnostici della wPoA (reveal VRF, seed RANDAO, fallback).

Metriche prodotte:
  * intervallo fra blocchi: media, deviazione standard, mediana, min/max,
    confrontati con target-block-time;
  * distribuzione dei proposer contro i pesi pubblicati, con test chi-quadro;
  * fork e riorganizzazioni: divergenza dei best-hash fra nodi a fine run;
  * traiettoria per epoca dei pesi pubblicati su wpoa-weights (una casella
    vuota significa "invariato": il registro non ripubblica un peso uguale);
  * distribuzione dei delay di sortition per miner e saturazione della banda;
  * ESG certificati, adesioni ai cluster, riconciliazione, rifornimenti GAS;
  * contatori diagnostici dai debug.log dei 10 nodi.
"""

import argparse
import json
import math
import os
import re
import statistics
import sys
from collections import Counter, defaultdict


class Checks(object):
    """Named verdicts, rendered as the headline table and as summary.json.

    Every section registers what it actually decided, instead of leaving the reader to
    infer it from a wall of numbers. `value` is the single figure that justifies the
    verdict, so the table stays readable at a glance and the JSON stays comparable
    across runs and across levels.
    """

    OK, WARN, FAIL, NA = "OK", "ATTENZIONE", "ERRORE", "n/d"
    _RANK = {OK: 0, NA: 1, WARN: 2, FAIL: 3}

    def __init__(self):
        self.rows = []

    def add(self, name, status, detail, value=None):
        self.rows.append({"check": name, "esito": status,
                          "valore": value, "dettaglio": detail})

    def worst(self):
        if not self.rows:
            return self.NA
        return max((r["esito"] for r in self.rows), key=lambda st: self._RANK.get(st, 1))

    def render(self):
        if not self.rows:
            return []
        mark = {self.OK: "OK  ", self.WARN: "WARN", self.FAIL: "FAIL", self.NA: " -  "}
        w = max(len(r["check"]) for r in self.rows)
        tally = Counter(r["esito"] for r in self.rows)
        breakdown = ", ".join("{} {}".format(tally[k], lbl)
                              for k, lbl in ((self.OK, "OK"), (self.WARN, "da guardare"),
                                             (self.FAIL, "falliti"), (self.NA, "non valutati"))
                              if tally[k])
        lines = ["",
                 "== VERDETTI =====================================================",
                 "  Esito complessivo: {}   ({} su {} controlli)".format(
                     self.worst(), breakdown, len(self.rows)),
                 ""]
        for r in self.rows:
            val = "" if r["valore"] is None else str(r["valore"])
            lines.append("  [{}] {:<{w}}  {:>14}   {}".format(
                mark.get(r["esito"], "?   "), r["check"], val, r["dettaglio"], w=w))
        lines.append("")
        lines.append("  Il dettaglio di ogni voce e' nella sezione omonima piu' sotto.")
        return lines


def read_chain_params(m, args):
    """Chain parameters AS THE CHAIN HAS THEM, falling back to the CLI arguments.

    The caller passes what it believes it configured; getblockchainparams reports what the
    chain actually runs on. They can differ -- a value may be raised at genesis, or a
    runtime flag may not have reached params.dat -- and every threshold in this report
    (the wPoA start height, the epoch geometry, the native spacing) has to be computed
    from the real one or the whole summary is quietly wrong.
    """
    cp = load_result(os.path.join(m, "chainparams.json"))
    got = {}
    if isinstance(cp, dict):
        got = cp
    return {
        "setup_blocks": int(got.get("setup-first-blocks", args.setup_blocks)),
        "epoch_len": int(got.get("weight-epoch-length", args.epoch_len)),
        "tbt": int(got.get("target-block-time", args.tbt)),
        "mining_diversity": float(got.get("mining-diversity", -1.0)),
        "from_chain": bool(got),
    }


def native_spacing(miner_count, diversity):
    """The spacing mc_Permissions::IsBarredByDiversity would impose, replicated exactly.

    diversity = floor(miner_count * d) + 1, clamped to [1, miner_count]. A spacing of 1 is
    inert (a block is barred when height - last <= spacing-1 = 0, never true); 2 or more
    forbids the same signer on consecutive heights.
    """
    if miner_count <= 0 or diversity < 0:
        return None
    sp = int(miner_count * diversity - 1e-9) + 1
    return max(1, min(sp, miner_count))


def load_result(path):
    """Carica un file di risposta JSON-RPC e ne restituisce il campo result."""
    if not os.path.exists(path):
        return None
    try:
        with open(path) as fh:
            payload = json.load(fh)
    except (ValueError, OSError):
        return None
    if isinstance(payload, dict) and payload.get("error"):
        return None
    return payload.get("result") if isinstance(payload, dict) else payload


def chi_square(observed, expected):
    """Statistica chi-quadro e gradi di liberta'; None se atteso troppo piccolo."""
    if not observed or len(observed) != len(expected):
        return None, None
    if any(e < 5 for e in expected):
        return None, None
    stat = sum((o - e) ** 2 / e for o, e in zip(observed, expected))
    return stat, len(observed) - 1


# valori critici al 5% per df = 1..8 (sufficiente: al massimo 3 miner)
CHI2_CRIT_05 = {1: 3.841, 2: 5.991, 3: 7.815, 4: 9.488,
                5: 11.070, 6: 12.592, 7: 14.067, 8: 15.507}


def analyse_blocks(blocks, setup_blocks, tbt, out, chk=None, facts=None):
    measured = [b for b in blocks if b["height"] > setup_blocks]
    out.append("")
    out.append("── Blocchi ────────────────────────────────────────────────────")
    out.append("  totale prodotti      : {}".format(len(blocks)))
    out.append("  fase di setup (PoA)  : {} blocchi (height 1..{})".format(
        min(len(blocks), setup_blocks), setup_blocks))
    out.append("  finestra wPoA misurata: {} blocchi (height {}..{})".format(
        len(measured),
        measured[0]["height"] if measured else "-",
        measured[-1]["height"] if measured else "-"))

    if len(measured) < 3:
        out.append("  ATTENZIONE: finestra troppo corta per le statistiche.")
        if chk:
            chk.add("liveness wPoA", Checks.FAIL,
                    "solo {} blocchi oltre setup-first-blocks: la catena non e' "
                    "avanzata sotto wPoA".format(len(measured)), len(measured))
        return measured

    if chk:
        chk.add("liveness wPoA", Checks.OK,
                "la catena ha prodotto blocchi oltre l'altezza di transizione",
                "{} blocchi".format(len(measured)))

    deltas = [measured[i]["time"] - measured[i - 1]["time"]
              for i in range(1, len(measured))]
    deltas = [d for d in deltas if d >= 0]
    if deltas:
        mean = statistics.mean(deltas)
        out.append("")
        out.append("  intervallo fra blocchi (finestra wPoA), target = {} s:".format(tbt))
        out.append("    media   {:8.2f} s     scarto vs target {:+.2f} s ({:+.1f}%)".format(
            mean, mean - tbt, 100.0 * (mean - tbt) / tbt))
        out.append("    mediana {:8.2f} s".format(statistics.median(deltas)))
        out.append("    dev.std {:8.2f} s".format(
            statistics.pstdev(deltas) if len(deltas) > 1 else 0.0))
        out.append("    min/max {:8.2f} / {:.2f} s".format(min(deltas), max(deltas)))
        if facts is not None:
            facts["intervallo_medio_s"] = round(mean, 3)
            facts["intervallo_target_s"] = tbt
            facts["blocchi_finestra_wpoa"] = len(measured)
            facts["blocchi_totali"] = len(blocks)
        if chk:
            drift = abs(mean - tbt) / tbt if tbt else 0.0
            chk.add("ritmo dei blocchi",
                    Checks.OK if drift <= 0.20 else Checks.WARN,
                    "intervallo medio vs target {} s ({:+.1f}%)".format(tbt, 100.0 * (mean - tbt) / tbt),
                    "{:.2f} s".format(mean))
    return measured


def analyse_proposers(measured, weights_by_addr, host_by_addr, out, chk=None, facts=None):
    out.append("")
    out.append("── Distribuzione dei proposer vs peso pubblicato ──────────────")
    counts = Counter(b["miner"] for b in measured)
    if not counts:
        out.append("  nessun proposer registrato.")
        return
    total_blocks = sum(counts.values())
    addrs = sorted(counts, key=lambda a: -counts[a])
    total_w = sum(weights_by_addr.get(a, 0) for a in addrs)

    out.append("  {:<6} {:<40} {:>7} {:>9} {:>9} {:>9}".format(
        "host", "indirizzo", "blocchi", "quota", "peso", "attesa"))
    observed, expected = [], []
    for a in addrs:
        w = weights_by_addr.get(a, 0)
        share = counts[a] / total_blocks
        exp_share = (w / total_w) if total_w else 0.0
        observed.append(counts[a])
        expected.append(exp_share * total_blocks)
        out.append("  {:<6} {:<40} {:>7} {:>8.1%} {:>9} {:>8.1%}".format(
            host_by_addr.get(a, "?"), a, counts[a], share, w or "-", exp_share))

    # Le vittorie consecutive sono la firma della selezione pesata: le altezze sono
    # estratte in modo indipendente, quindi la frequenza attesa e' sum_i p_i^2. Il valore
    # e' riportato qui e giudicato nella sezione "Spacing", dove si conosce anche lo
    # spacing nativo che si applicherebbe.
    seq = [b["miner"] for b in measured]
    consec = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
    shares = [counts[a] / total_blocks for a in addrs]
    exp_consec = sum(p * p for p in shares) * max(0, len(seq) - 1)
    longest, cur = 1, 1
    for i in range(1, len(seq)):
        cur = cur + 1 if seq[i] == seq[i - 1] else 1
        longest = max(longest, cur)
    out.append("")
    out.append("  blocchi consecutivi dello stesso proposer: {} osservati, "
               "{:.1f} attesi".format(consec, exp_consec))
    out.append("  sequenza piu' lunga dello stesso proposer: {} blocchi".format(longest))
    if facts is not None:
        facts["consecutivi_osservati"] = consec
        facts["consecutivi_attesi"] = round(exp_consec, 1)
        facts["sequenza_massima"] = longest
        facts["proposer"] = {
            host_by_addr.get(a, a): {
                "blocchi": counts[a],
                "quota": round(counts[a] / total_blocks, 4),
                "peso": weights_by_addr.get(a, 0),
            } for a in addrs
        }

    stat, df = chi_square(observed, expected)
    if stat is None:
        out.append("")
        out.append("  chi-quadro non applicabile (frequenze attese < 5): "
                   "servono piu' blocchi misurati.")
        if chk:
            chk.add("distribuzione dei proposer", Checks.NA,
                    "frequenze attese < 5: finestra troppo corta per il test", None)
    else:
        crit = CHI2_CRIT_05.get(df)
        verdict = "compatibile" if (crit and stat <= crit) else "NON compatibile"
        out.append("")
        out.append("  chi-quadro = {:.3f}  (df={}, critico 5% = {})  -> {} con la "
                   "selezione pesata".format(stat, df, crit, verdict))
        if facts is not None:
            facts["chi_quadro"] = round(stat, 3)
            facts["chi_quadro_critico_5pct"] = crit
        if chk:
            chk.add("distribuzione dei proposer",
                    Checks.OK if (crit and stat <= crit) else Checks.WARN,
                    "chi-quadro vs critico 5% = {} (df={}): {} con i pesi".format(
                        crit, df, verdict),
                    "{:.3f}".format(stat))
        out.append("  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra")
        out.append("      le epoche il test e' solo indicativo: va letto insieme alla")
        out.append("      traiettoria per epoca riportata sopra.")


def analyse_weights(weights_items, host_by_addr, out):
    """Traiettoria per epoca dei pesi pubblicati su wpoa-weights."""
    out.append("")
    out.append("── Traiettoria dei pesi (stream wpoa-weights) ─────────────────")
    if not weights_items:
        out.append("  nessun record pubblicato.")
        return {}

    latest, per_height = {}, defaultdict(dict)
    for item in weights_items:
        data = item.get("data")
        if not isinstance(data, dict) or "json" not in data:
            continue
        rec = data["json"]
        addr = rec.get("node_address")
        weight = rec.get("weight")
        # 'epoch' e' presente solo sui record prodotti dal weight engine; il
        # percorso statico -weight non lo stampa (non deriva da alcuna epoca).
        key = rec.get("epoch")
        label = "e{}".format(key) if key is not None else "h{}".format(rec.get("height", "?"))
        if addr is None or weight is None:
            continue
        latest[addr] = weight
        per_height[(key if key is not None else 10 ** 6, label)][addr] = weight

    addrs = sorted(latest, key=lambda a: host_by_addr.get(a, a))
    header = "  {:<10}".format("epoca") + "".join(
        "{:>10}".format(host_by_addr.get(a, a[:8])) for a in addrs)
    out.append(header)
    for h in sorted(per_height):
        row = "  {:<10}".format(h[1]) + "".join(
            "{:>10}".format(per_height[h].get(a, "")) for a in addrs)
        out.append(row)
    out.append("  record totali: {}".format(len(weights_items)))
    return latest


def analyse_bootstrap_and_spacing(m, cp, facts, out, chk):
    """The two invariants the harness used to work around instead of measuring.

    BOOTSTRAP. wpoa-weights is created by the node itself (ThreadWeightEngine calls
    EnsureStreamReady before the epoch gate), not by role_admin.sh. What matters is that it
    exists BEFORE wPoA starts electing: if it appeared only after setup-first-blocks the
    registry would be empty exactly when the selector first needed it.

    SPACING. The native mining-diversity rule is round-robin and would forbid the same
    signer on consecutive heights; it is neutralised on wPoA-governed heights at its source.
    The run is only able to demonstrate that when the configured spacing would actually
    bite (>= 2) -- with spacing 1 the rule is inert anyway and the observation proves
    nothing either way, which is stated rather than glossed over.
    """
    out.append("")
    out.append("── Invarianti: bootstrap del registro e spacing ───────────────")

    setup = cp["setup_blocks"]

    # -- bootstrap del registro dei pesi ------------------------------------
    h_txt = os.path.join(m, "wpoa_weights_stream_height.txt")
    stream_h = None
    if os.path.exists(h_txt):
        raw = open(h_txt).read().strip()
        if raw.isdigit():
            stream_h = int(raw)
    if stream_h is None:
        out.append("  stream wpoa-weights   : altezza di comparsa non registrata")
        chk.add("bootstrap wpoa-weights", Checks.NA,
                "altezza di comparsa non registrata dallo snapshot", None)
    else:
        out.append("  stream wpoa-weights   : visibile entro height {} "
                   "(la wPoA ingaggia a {})".format(stream_h, setup))
        facts["stream_visibile_a_height"] = stream_h
        if stream_h < setup:
            out.append("  -> creato dal nodo con {} blocchi di margine sulla transizione."
                       .format(setup - stream_h))
            chk.add("bootstrap wpoa-weights", Checks.OK,
                    "stream creato dal nodo prima della transizione wPoA (a {})".format(setup),
                    "height {}".format(stream_h))
        else:
            out.append("  -> ATTENZIONE: comparso a transizione gia' avvenuta: il registro")
            out.append("     era vuoto quando il selettore ne aveva bisogno.")
            chk.add("bootstrap wpoa-weights", Checks.FAIL,
                    "stream comparso solo a height {}, oltre la transizione {}".format(
                        stream_h, setup),
                    "height {}".format(stream_h))

    # -- spacing nativo -----------------------------------------------------
    perms = load_result(os.path.join(m, "permissions_mine.json")) or []
    miners = set()
    if isinstance(perms, list):
        for e in perms:
            if isinstance(e, dict) and e.get("address"):
                miners.add(e["address"])
    n_miners = len(miners)
    d = cp["mining_diversity"]
    sp = native_spacing(n_miners, d)

    if sp is None:
        out.append("  spacing nativo        : non calcolabile "
                   "(mining-diversity o conteggio miner assenti)")
        chk.add("spacing inerte sotto wPoA", Checks.NA,
                "mining-diversity o numero di miner non disponibili", None)
        return

    out.append("  mining-diversity      : {:g}  su {} indirizzi con permesso mine"
               .format(d, n_miners))
    out.append("  spacing nativo        : {} blocchi fra due blocchi dello stesso "
               "firmatario".format(sp))
    facts["mining_diversity"] = d
    facts["miner_con_permesso"] = n_miners
    facts["spacing_nativo"] = sp

    consec = facts.get("consecutivi_osservati")
    exp = facts.get("consecutivi_attesi")

    if sp < 2:
        out.append("  -> spacing 1: la regola nativa e' inerte per costruzione a questo")
        out.append("     numero di miner, quindi questa run NON discrimina. Serve un d o")
        out.append("     un N che portino lo spacing a >= 2 per metterla alla prova.")
        chk.add("spacing inerte sotto wPoA", Checks.NA,
                "spacing nativo 1: inerte comunque, la run non discrimina",
                "spacing {}".format(sp))
        return

    if consec is None:
        chk.add("spacing inerte sotto wPoA", Checks.NA,
                "nessun conteggio di blocchi consecutivi disponibile", None)
        return

    out.append("  -> con spacing {} la regola nativa VIETEREBBE due blocchi di fila allo"
               .format(sp))
    out.append("     stesso proposer. Osservati: {} (attesi {} sotto selezione pesata)."
               .format(consec, exp))
    if consec > 0:
        out.append("     Le vittorie consecutive avvengono: il vincolo e' neutralizzato")
        out.append("     sulle altezze governate dalla wPoA, come previsto (5.12.3).")
        chk.add("spacing inerte sotto wPoA", Checks.OK,
                "spacing {} vieterebbe i blocchi di fila, ma se ne osservano {} (attesi {})"
                .format(sp, consec, exp),
                "{} consecutivi".format(consec))
    else:
        out.append("     ZERO su una finestra in cui se ne attendevano {}: il vincolo e'"
                   .format(exp))
        out.append("     tornato vincolante e la distribuzione collassa sul round robin.")
        chk.add("spacing inerte sotto wPoA", Checks.FAIL,
                "0 blocchi consecutivi con spacing {} attivo (attesi {}): regressione del gate"
                .format(sp, exp),
                "0 consecutivi")


def analyse_consistency(run, out, chk=None):
    out.append("")
    out.append("── Consistenza fra nodi a fine run ────────────────────────────")
    path = os.path.join(run, "metrics", "node_state.csv")
    if not os.path.exists(path):
        out.append("  node_state.csv assente (snapshot non eseguito).")
        if chk:
            chk.add("consistenza fra nodi", Checks.NA, "snapshot per-nodo non eseguito", None)
        return
    rows = [l.strip().split(",") for l in open(path) if l.strip()][1:]
    if not rows:
        out.append("  nessun dato.")
        return
    out.append("  {:<8} {:>8} {:>7} {:>12}  {:<18} {}".format(
        "host", "height", "peers", "GAS", "best hash", "hash a -6"))
    tips, deep = Counter(), Counter()
    for r in rows:
        if len(r) < 6:
            continue
        host, height, bhash, dhash, peers, bal = r[0], r[1], r[2], r[3], r[4], r[5]
        tips[bhash] += 1
        deep[dhash] += 1
        out.append("  {:<8} {:>8} {:>7} {:>12}  {:<18} {}".format(
            host, height, peers, bal, bhash[:16], dhash[:16]))
    heights = {int(r[1]) for r in rows if len(r) >= 2 and r[1].isdigit()}
    spread = (max(heights) - min(heights)) if heights else 0
    if len(tips) == 1:
        out.append("  -> tutti i nodi sulla stessa testa: nessun fork.")
        if chk:
            chk.add("consistenza fra nodi", Checks.OK,
                    "tutti i nodi sulla stessa testa", "{} nodi".format(len(rows)))
    elif spread <= 1 and len(deep) == 1:
        out.append("  -> teste diverse ma altezze a {} blocco di distanza e stesso hash "
                   "sepolto:".format(spread))
        out.append("     e' il normale ritardo di propagazione fra i nodi, non un fork.")
        if chk:
            chk.add("consistenza fra nodi", Checks.OK,
                    "teste a {} blocco di distanza, stesso hash sepolto: propagazione".format(spread),
                    "{} teste".format(len(tips)))
    elif len(deep) == 1:
        out.append("  -> {} teste distinte ma prefisso comune 6 blocchi sotto: "
                   "corsa al tip in corso, non un fork persistente.".format(len(tips)))
        out.append("     E' il caso previsto quando due delay cadono a distanza inferiore")
        out.append("     alla latenza di propagazione (Sez. 3.3.2 / 5.10.5).")
        if chk:
            chk.add("consistenza fra nodi", Checks.OK,
                    "prefisso comune 6 blocchi sotto: corsa al tip, non un fork",
                    "{} teste".format(len(tips)))
    else:
        out.append("  -> ATTENZIONE: {} teste E {} prefissi sepolti distinti: "
                   "fork persistente.".format(len(tips), len(deep)))
        if chk:
            chk.add("consistenza fra nodi", Checks.FAIL,
                    "{} teste e {} prefissi sepolti distinti: fork persistente".format(
                        len(tips), len(deep)),
                    "{} prefissi".format(len(deep)))


def analyse_logs(run, chain, out, chk=None, facts=None):
    """Contatori diagnostici dai debug.log dei nodi."""
    patterns = {
        "blocchi validati dalla sortition": r"VerifyBlockMinerWPoA: sortition OK",
        "blocchi RIFIUTATI dalla sortition": r"VerifyBlockMinerWPoA: sortition (REJECT|reject|mismatch|FAIL)",
        "seed RANDAO derivati":            r"\[wPoA-RANDAO\] seed for height",
        "fold di fallback RANDAO":         r"\[wPoA-RANDAO\].*fallback",
        "score di sortition calcolati":    r"wPoA-sortition height=\d+ score=",
        "attese per mappa pesi vuota":     r"cannot score \(unsynced or unweighted\)",
        "pesi registrati sullo stream":    r"\[StreamWeightRegistry\] Weight registered",
        "letture della mappa dei pesi":    r"\[StreamWeightRegistry\] All nodes weights",
        "epoche calcolate dal motore":     r"\[WeightEngine\] epoch \d+:",
        "report di malus valutati":        r"\[MalusRegistry\]",
    }
    counts = defaultdict(int)
    data_dir = os.path.join(run, "data")
    if not os.path.isdir(data_dir):
        return
    for host in sorted(os.listdir(data_dir)):
        log = os.path.join(data_dir, host, chain, "debug.log")
        if not os.path.exists(log):
            continue
        with open(log, errors="replace") as fh:
            for line in fh:
                for name, pat in patterns.items():
                    if re.search(pat, line):
                        counts[name] += 1
    out.append("")
    out.append("── Contatori diagnostici (somma sui debug.log) ────────────────")
    for name in patterns:
        out.append("  {:<32} {}".format(name, counts[name]))
    if facts is not None:
        facts["contatori_log"] = {k: counts[k] for k in patterns}

    if chk is None:
        return

    # I contatori che hanno un significato di PASS/FAIL, non solo informativo.
    rejects = counts["blocchi RIFIUTATI dalla sortition"]
    chk.add("validazione sortition",
            Checks.OK if rejects == 0 else Checks.FAIL,
            "blocchi rifiutati dalla sortition sotto operativita' onesta",
            rejects)

    stalls = counts["attese per mappa pesi vuota"]
    ok_blocks = counts["blocchi validati dalla sortition"]
    if stalls == 0:
        chk.add("registro dei pesi popolato", Checks.OK,
                "nessuna attesa per mappa pesi vuota", 0)
    elif ok_blocks > 0:
        # Qualche attesa a ridosso della transizione e' fisiologica; solo se la catena
        # non fosse mai ripartita sarebbe un problema, e lo direbbe la liveness.
        chk.add("registro dei pesi popolato", Checks.WARN,
                "{} attese per mappa vuota, ma la catena e' comunque avanzata".format(stalls),
                stalls)
    else:
        chk.add("registro dei pesi popolato", Checks.FAIL,
                "attese per mappa pesi vuota e nessun blocco validato: stallo", stalls)

    folds = counts["fold di fallback RANDAO"]
    chk.add("beacon RANDAO",
            Checks.OK if folds == 0 else Checks.WARN,
            "fold di fallback (reveal mancanti) sulle altezze governate", folds)


DELAY_RE = re.compile(
    r"wPoA-sortition height=(\d+) score=([0-9.eE+-]+) delay=([0-9.]+)s")


def analyse_delays(run, chain, setup_blocks, tbt, delta, out):
    """Delay di sortition per miner e MARGINE della timer race.

    Il margine G = D_(2) - D_(1) (Def. 5.15) e' la grandezza che decide se la
    corsa dei timer gira sullo score o sul rumore: quando G scende sotto la
    varianza della latenza di rete, il vincitore osservato puo' non essere il
    vincitore designato dallo score (Prop. 5.18). E' quindi la misura che
    spiega uno scostamento fra distribuzione dei proposer e distribuzione dei
    pesi, e va letta insieme a quella tabella.
    """
    per_host = defaultdict(list)
    per_height = defaultdict(dict)
    data_dir = os.path.join(run, "data")
    if not os.path.isdir(data_dir):
        return
    for host in sorted(os.listdir(data_dir)):
        log = os.path.join(data_dir, host, chain, "debug.log")
        if not os.path.exists(log):
            continue
        with open(log, errors="replace") as fh:
            for line in fh:
                m = DELAY_RE.search(line)
                if not m:
                    continue
                h, delay = int(m.group(1)), float(m.group(3))
                if h <= setup_blocks:
                    continue
                per_host[host].append(delay)
                # una stessa altezza puo' essere ricalcolata: tieni l'ultimo valore
                per_height[h][host] = delay
    if not per_host:
        return

    dmax = delta * tbt
    band_lo, band_hi = tbt - dmax, tbt + dmax
    span = band_hi - band_lo

    out.append("")
    out.append("── Delay di sortition per miner ───────────────────────────────")
    out.append("  banda: [{:.2f}, {:.2f}] s   (T={} s, delta={}, Dmax={:.2f} s)".format(
        band_lo, band_hi, tbt, delta, dmax))
    out.append("  {:<6} {:>8} {:>9} {:>9} {:>9} {:>14}".format(
        "host", "campioni", "min s", "media s", "max s", "pos. in banda"))
    for host in sorted(per_host):
        vals = per_host[host]
        mean = statistics.mean(vals)
        out.append("  {:<6} {:>8} {:>9.3f} {:>9.3f} {:>9.3f} {:>13.1%}".format(
            host, len(vals), min(vals), mean, max(vals), (mean - band_lo) / span))
    out.append("  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)")

    margins = []
    for h, d in per_height.items():
        if len(d) >= 2:
            ordered = sorted(d.values())
            margins.append(ordered[1] - ordered[0])
    if not margins:
        return
    margins.sort()
    tiny = sum(1 for g in margins if g < 0.1)
    out.append("")
    out.append("  margine della timer race G = D(2) - D(1)   (Def. 5.15, su {} round):".format(
        len(margins)))
    out.append("    media   {:8.3f} s".format(statistics.mean(margins)))
    out.append("    mediana {:8.3f} s".format(statistics.median(margins)))
    out.append("    minimo  {:8.3f} s".format(margins[0]))
    out.append("    5o perc.{:8.3f} s".format(margins[max(0, len(margins) // 20)]))
    out.append("    round con G < 100 ms: {} su {} ({:.1%})".format(
        tiny, len(margins), tiny / len(margins)))
    if tiny / len(margins) > 0.05:
        out.append("")
        out.append("  In questi round il margine e' dell'ordine della latenza di rete:")
        out.append("  il vincitore osservato puo' differire da quello designato dallo")
        out.append("  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce")
        out.append("  rispetto ai pesi. Per allargare il margine: alzare target-block-time")
        out.append("  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction")
        out.append("  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).")


def tail_csv(run, name, out, title, limit=12):
    path = os.path.join(run, "metrics", name)
    if not os.path.exists(path):
        return
    lines = [l.rstrip() for l in open(path) if l.strip()]
    if not lines:
        return
    out.append("")
    out.append("── {} ({}) ──".format(title, name))
    for line in lines[:limit]:
        out.append("  " + line)
    if len(lines) > limit:
        out.append("  ... ({} righe totali)".format(len(lines)))


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True)
    ap.add_argument("--chain", required=True)
    ap.add_argument("--level", required=True)
    ap.add_argument("--setup-blocks", type=int, default=60)
    ap.add_argument("--epoch-len", type=int, default=12)
    ap.add_argument("--tbt", type=int, default=15)
    ap.add_argument("--delta", type=float, default=0.5,
                    help="wpoa-sortition-delta usato nella run")
    args = ap.parse_args()

    m = os.path.join(args.run, "metrics")
    chk = Checks()
    facts = {}
    cp = read_chain_params(m, args)

    head = ["",
            "══════════════════════════════════════════════════════════════════",
            "  POESIA / wPoA — riepilogo run: livello {}".format(args.level),
            "══════════════════════════════════════════════════════════════════",
            "",
            "  parametri di catena{}: setup-first-blocks={}  weight-epoch-length={}  "
            "target-block-time={}s  mining-diversity={}".format(
                "" if cp["from_chain"] else " (dai soli argomenti: chainparams.json assente)",
                cp["setup_blocks"], cp["epoch_len"], cp["tbt"],
                "{:g}".format(cp["mining_diversity"]) if cp["mining_diversity"] >= 0 else "n/d")]
    out = []

    # indirizzo -> host, dai file depositati durante il bootstrap
    host_by_addr = {}
    shared = os.path.join(args.run, "shared")
    if os.path.isdir(shared):
        for fn in sorted(os.listdir(shared)):
            if fn.endswith(".addr"):
                addr = open(os.path.join(shared, fn)).read().strip()
                if addr:
                    host_by_addr[addr] = fn[:-5]

    blocks = load_result(os.path.join(m, "blocks.json")) or []
    weights_items = load_result(os.path.join(m, "weights.json")) or []

    if not blocks:
        out.append("")
        out.append("  NESSUN BLOCCO nello snapshot: la simulazione non ha prodotto")
        out.append("  catena, oppure lo snapshot finale non e' stato eseguito.")
        out.append("  Controlla {}/shadow.log e i debug.log dei nodi.".format(args.run))
    else:
        measured = analyse_blocks(blocks, cp["setup_blocks"], cp["tbt"], out, chk, facts)
        latest_w = analyse_weights(weights_items, host_by_addr, out)
        analyse_proposers(measured, latest_w, host_by_addr, out, chk, facts)
        analyse_bootstrap_and_spacing(m, cp, facts, out, chk)
        analyse_delays(args.run, args.chain, cp["setup_blocks"], cp["tbt"],
                       args.delta, out)

    analyse_consistency(args.run, out, chk)
    tail_csv(args.run, "esg_scores.csv", out, "ESG certificati dal CA")
    tail_csv(args.run, "membership.csv", out, "Adesioni ai cluster")
    tail_csv(args.run, "reconciliation.csv", out, "Riconciliazione verso il treasury")
    tail_csv(args.run, "gas_transfers.csv", out, "Movimenti GAS (init + rifornimenti)")
    analyse_logs(args.run, args.chain, out, chk, facts)

    verify = load_result(os.path.join(m, "verify.json"))
    if verify is not None:
        out.append("")
        out.append("── weightverifyweights (ricomputazione indipendente) ──────────")
        out.append("  " + json.dumps(verify)[:600])

    out.append("")

    # I verdetti vanno IN TESTA: chi apre il file deve vedere l'esito prima dei numeri
    # che lo giustificano, non doverlo ricostruire leggendo tutto.
    text = "\n".join(head + chk.render() + out)
    print(text)
    with open(os.path.join(m, "summary.txt"), "w") as fh:
        fh.write(text + "\n")

    # Gemello machine-readable: stessi verdetti e stesse cifre, in una forma che
    # compare_levels.py e l'analisi degli esperimenti possono aggregare senza dover
    # ri-parsare il testo (che e' pensato per essere letto, non consumato).
    payload = {
        "livello": args.level,
        "chain": args.chain,
        "parametri": cp,
        "esito": chk.worst(),
        "verdetti": chk.rows,
        "metriche": facts,
    }
    with open(os.path.join(m, "summary.json"), "w") as fh:
        json.dump(payload, fh, indent=2, sort_keys=True)
        fh.write("\n")

    print("[collect_metrics] riepilogo in {}/summary.txt e {}/summary.json"
          .format(m, m))
    return 0 if chk.worst() != Checks.FAIL else 1


if __name__ == "__main__":
    sys.exit(main())
