#!/usr/bin/env python3
"""
Confronta le run dei quattro livelli in una sola tabella.

Legge lo snapshot di ciascun `<livello>/run/metrics/` e mette in fila le
grandezze che l'esperimento vuole confrontare fra geografie diverse. Va lanciato
dopo aver eseguito i livelli che interessano; quelli senza run vengono saltati.

    python3 tools/compare_levels.py
    python3 tools/compare_levels.py --setup-blocks 60 --tbt 15
"""

import argparse
import json
import os
import re
import statistics
import sys
from collections import Counter, defaultdict

LEVELS = ["regionale", "nazionale", "continentale", "intercontinentale"]
DELAY_RE = re.compile(r"wPoA-sortition height=(\d+) score=[0-9.eE+-]+ delay=([0-9.]+)s")


def load_result(path):
    if not os.path.exists(path):
        return None
    try:
        payload = json.load(open(path))
    except (ValueError, OSError):
        return None
    if isinstance(payload, dict) and payload.get("error"):
        return None
    return payload.get("result") if isinstance(payload, dict) else payload


def max_rtt(gml):
    """RTT end-to-end massimo, per etichettare il livello."""
    try:
        import networkx as nx
    except ImportError:
        return None
    if not os.path.exists(gml):
        return None
    g = nx.read_gml(gml, label="id")
    simple = nx.Graph((u, v) for u, v in g.edges() if u != v)
    for u, v in simple.edges():
        text = str(g[u][v]["latency"]).strip()
        for suf, fac in (("ns", 1e-6), ("us", 1e-3), ("ms", 1.0), ("s", 1000.0)):
            if text.endswith(suf):
                simple[u][v]["ms"] = float(text[:-len(suf)].strip()) * fac
                break
    paths = dict(nx.all_pairs_dijkstra_path_length(simple, weight="ms"))
    return max(2 * paths[a][b] for a in paths for b in paths[a])


def analyse(root, level, setup_blocks, tbt):
    run = os.path.join(root, level, "run")
    m = os.path.join(run, "metrics")
    blocks = load_result(os.path.join(m, "blocks.json"))
    if not blocks:
        return None
    measured = [b for b in blocks if b["height"] > setup_blocks]
    if len(measured) < 3:
        return None

    deltas = [measured[i]["time"] - measured[i - 1]["time"] for i in range(1, len(measured))]
    deltas = [d for d in deltas if d >= 0]
    counts = Counter(b["miner"] for b in measured)
    seq = [b["miner"] for b in measured]
    consec = sum(1 for i in range(1, len(seq)) if seq[i] == seq[i - 1])
    shares = sorted((c / len(measured) for c in counts.values()), reverse=True)

    # margine della timer race, dai debug.log
    per_height = defaultdict(dict)
    chain = "poesia" + level
    data_dir = os.path.join(run, "data")
    if os.path.isdir(data_dir):
        for host in os.listdir(data_dir):
            log = os.path.join(data_dir, host, chain, "debug.log")
            if not os.path.exists(log):
                continue
            with open(log, errors="replace") as fh:
                for line in fh:
                    mm = DELAY_RE.search(line)
                    if mm and int(mm.group(1)) > setup_blocks:
                        per_height[int(mm.group(1))][host] = float(mm.group(2))
    margins = [sorted(d.values())[1] - sorted(d.values())[0]
               for d in per_height.values() if len(d) >= 2]

    state = os.path.join(m, "node_state.csv")
    tips = set()
    if os.path.exists(state):
        for line in list(open(state))[1:]:
            parts = line.strip().split(",")
            if len(parts) >= 3:
                tips.add(parts[2])

    return {
        "rtt": max_rtt(os.path.join(root, level, "topologia_myledger_%s.gml" % level)),
        "blocks": len(measured),
        "mean_dt": statistics.mean(deltas) if deltas else float("nan"),
        "sd_dt": statistics.pstdev(deltas) if len(deltas) > 1 else 0.0,
        "shares": shares,
        "consec": consec,
        "exp_consec": sum(p * p for p in shares) * max(0, len(seq) - 1),
        "g_med": statistics.median(margins) if margins else float("nan"),
        "g_tiny": (sum(1 for x in margins if x < 0.1) / len(margins)) if margins else float("nan"),
        "tips": len(tips),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--root", default=os.path.join(os.path.dirname(__file__), ".."))
    ap.add_argument("--setup-blocks", type=int, default=60)
    ap.add_argument("--tbt", type=int, default=15)
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    rows = [(lv, analyse(root, lv, args.setup_blocks, args.tbt)) for lv in LEVELS]
    rows = [(lv, r) for lv, r in rows if r]
    if not rows:
        print("Nessuna run trovata. Esegui prima ./run.sh area=<livello>.")
        return 1

    print()
    print("  Confronto fra livelli — target-block-time {} s, "
          "finestra oltre il blocco {}".format(args.tbt, args.setup_blocks))
    print()
    print("  {:<19} {:>8} {:>8} {:>9} {:>8} {:>22} {:>9} {:>8} {:>6}".format(
        "livello", "RTT max", "blocchi", "dt medio", "sd dt", "quote proposer",
        "G mediano", "G<100ms", "teste"))
    print("  " + "-" * 108)
    for lv, r in rows:
        shares = " / ".join("{:.0%}".format(p) for p in r["shares"])
        print("  {:<19} {:>7.1f}m {:>8} {:>8.2f}s {:>7.2f}s {:>22} {:>8.2f}s {:>7.1%} {:>6}".format(
            lv, r["rtt"] or 0, r["blocks"], r["mean_dt"], r["sd_dt"], shares,
            r["g_med"], r["g_tiny"], r["tips"]))
    print()
    print("  Blocchi consecutivi dello stesso proposer (osservati vs attesi):")
    for lv, r in rows:
        flag = "  <-- Spacing attivo" if (r["consec"] == 0 and r["exp_consec"] >= 3) else ""
        print("    {:<19} {:>4} vs {:>6.1f}{}".format(lv, r["consec"], r["exp_consec"], flag))
    print()
    print("  Nota: 'RTT max' e' in millisecondi (cammino minimo peggiore fra due host).")
    print("        'G' e' il margine della timer race D(2)-D(1) (Def. 5.15).")
    print("        'teste' e' il numero di best-hash distinti a fine run: 1 = nessun fork.")
    print()
    return 0


if __name__ == "__main__":
    sys.exit(main())
