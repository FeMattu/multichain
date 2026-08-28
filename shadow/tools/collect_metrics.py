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


def analyse_blocks(blocks, setup_blocks, tbt, out):
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
        return measured

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
    return measured


def analyse_proposers(measured, weights_by_addr, host_by_addr, out):
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

    # Diagnostica dello spacing: sotto selezione pesata la probabilita' che due
    # blocchi consecutivi abbiano lo stesso proposer e' sum_i p_i^2. Se il valore
    # osservato e' ZERO, non e' un caso: significa che una regola di alternanza
    # (lo Spacing di mining-diversity) e' ancora vincolante, e la distribuzione
    # osservata e' quella di un round robin, non quella dei pesi.
    seq = [b["miner"] for b in measured]
    consec = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
    shares = [counts[a] / total_blocks for a in addrs]
    exp_consec = sum(p * p for p in shares) * max(0, len(seq) - 1)
    out.append("")
    out.append("  blocchi consecutivi dello stesso proposer: {} osservati, "
               "{:.1f} attesi".format(consec, exp_consec))
    if consec == 0 and exp_consec >= 3:
        out.append("  -> ZERO alternanze violate su {} blocchi: lo Spacing di "
                   "mining-diversity".format(len(seq)))
        out.append("     e' ancora vincolante sulle altezze governate dalla wPoA. Con")
        out.append("     mining-diversity=d e N indirizzi con permesso mine, lo spacing")
        out.append("     vale ceil(d*(N-1)); a 1 impedisce due blocchi di fila allo stesso")
        out.append("     firmatario e appiattisce la distribuzione verso il round robin,")
        out.append("     indipendentemente dai pesi. Impostare mining-diversity=0 in")
        out.append("     config/params.overrides per renderlo inerte e misurare la sola")
        out.append("     selezione pesata.")

    stat, df = chi_square(observed, expected)
    if stat is None:
        out.append("")
        out.append("  chi-quadro non applicabile (frequenze attese < 5): "
                   "servono piu' blocchi misurati.")
    else:
        crit = CHI2_CRIT_05.get(df)
        verdict = "compatibile" if (crit and stat <= crit) else "NON compatibile"
        out.append("")
        out.append("  chi-quadro = {:.3f}  (df={}, critico 5% = {})  -> {} con la "
                   "selezione pesata".format(stat, df, crit, verdict))
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


def analyse_consistency(run, out):
    out.append("")
    out.append("── Consistenza fra nodi a fine run ────────────────────────────")
    path = os.path.join(run, "metrics", "node_state.csv")
    if not os.path.exists(path):
        out.append("  node_state.csv assente (snapshot non eseguito).")
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
    elif spread <= 1 and len(deep) == 1:
        out.append("  -> teste diverse ma altezze a {} blocco di distanza e stesso hash "
                   "sepolto:".format(spread))
        out.append("     e' il normale ritardo di propagazione fra i nodi, non un fork.")
    elif len(deep) == 1:
        out.append("  -> {} teste distinte ma prefisso comune 6 blocchi sotto: "
                   "corsa al tip in corso, non un fork persistente.".format(len(tips)))
        out.append("     E' il caso previsto quando due delay cadono a distanza inferiore")
        out.append("     alla latenza di propagazione (Sez. 3.3.2 / 5.10.5).")
    else:
        out.append("  -> ATTENZIONE: {} teste E {} prefissi sepolti distinti: "
                   "fork persistente.".format(len(tips), len(deep)))


def analyse_logs(run, chain, out):
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
    out.append("── Contatori diagnostici (somma sui 10 debug.log) ─────────────")
    for name in patterns:
        out.append("  {:<32} {}".format(name, counts[name]))


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
    out = ["",
           "══════════════════════════════════════════════════════════════════",
           "  POESIA / wPoA — riepilogo run: livello {}".format(args.level),
           "══════════════════════════════════════════════════════════════════"]

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
        measured = analyse_blocks(blocks, args.setup_blocks, args.tbt, out)
        latest_w = analyse_weights(weights_items, host_by_addr, out)
        analyse_proposers(measured, latest_w, host_by_addr, out)
        analyse_delays(args.run, args.chain, args.setup_blocks, args.tbt,
                       args.delta, out)

    analyse_consistency(args.run, out)
    tail_csv(args.run, "esg_scores.csv", out, "ESG certificati dal CA")
    tail_csv(args.run, "membership.csv", out, "Adesioni ai cluster")
    tail_csv(args.run, "reconciliation.csv", out, "Riconciliazione verso il treasury")
    tail_csv(args.run, "gas_transfers.csv", out, "Movimenti GAS (init + rifornimenti)")
    analyse_logs(args.run, args.chain, out)

    verify = load_result(os.path.join(m, "verify.json"))
    if verify is not None:
        out.append("")
        out.append("── weightverifyweights (ricomputazione indipendente) ──────────")
        out.append("  " + json.dumps(verify)[:600])

    out.append("")
    text = "\n".join(out)
    print(text)
    with open(os.path.join(m, "summary.txt"), "w") as fh:
        fh.write(text + "\n")
    print("[collect_metrics] riepilogo scritto in {}/summary.txt".format(m))
    return 0


if __name__ == "__main__":
    sys.exit(main())
