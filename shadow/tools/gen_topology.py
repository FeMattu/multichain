#!/usr/bin/env python3
"""
Genera il file .gml di un livello a partire dalla sua definizione in
config/levels/<livello>.json.

MODELLO DI LATENZA (identico sui quattro livelli, e' questo che li rende
confrontabili fra loro):

    latenza_one_way_ms = 0.005 * D_km * 1.4 + overhead
    RTT_ms             = 2 * latenza_one_way_ms

dove
  * 0.005 ms/km  e' il ritardo di propagazione in fibra (v ~ 2e5 km/s);
  * 1.4          e' il fattore di instradamento: il percorso fisico e' piu'
                 lungo della distanza in linea d'aria;
  * overhead     e' il costo di commutazione/aggregazione del percorso, non
                 proporzionale alla distanza: 0.5 ms sulla dorsale,
                 1.0 ms sui collegamenti di accesso (ultimo miglio).

Validazione del modello contro misure reali:

    tratta              D_km    RTT modello   RTT reale
    Bologna-Ginevra      840      12.8 ms      ~9.5 ms
    Milano-Roma          480       7.7 ms      ~9   ms
    Milano-Madrid       1190      17.7 ms      ~20  ms
    Milano-New York     6400      90.6 ms      ~90  ms

L'attributo `jitter` resta 0 su ogni arco: il campo NON e' implementato da
Shadow (issue shadow/shadow#3601). La variabilita' temporale nella simulazione
proviene da (a) eterogeneita' dei percorsi, (b) packet loss stocastico,
(c) contesa reale su CPU e lock dei processi simulati.
"""

import argparse
import json
import math
import os
import sys

# --- costanti del modello ---------------------------------------------------
PROP_MS_PER_KM = 0.005     # propagazione in fibra, one-way
ROUTING_FACTOR = 1.4       # allungamento del percorso fisico
# VINCOLI DEL PARSER GML DI SHADOW 3.3 (verificati sul campo, e non documentati
# nel manuale). Il .gml prodotto qui li rispetta tutti; il file originale
# fornito per il livello regionale ne violava due su tre e Shadow lo rifiutava:
#
#   1. niente commenti: una riga che inizia con '#' fa fallire il parse con
#      "Failed to parse the network graph ... in Verify";
#   2. blocchi node/edge in forma CANONICA multi-riga. La forma compatta
#      `node [ id 0 label "x" ]` fa fallire il parse con "... in MultiSpace";
#   3. le stringhe con unita' vogliono una magnitudine INTERA: `latency "0.2 ms"`
#      produce "Edge 'latency' is not a valid unit: invalid digit found in
#      string". Per questo le latenze sono emesse in microsecondi interi.
OVERHEAD_BACKBONE_MS = 0.5
OVERHEAD_ACCESS_MS = 1.0
LOOPBACK_MS = 0.2          # self-loop: latenza intra-nodo

LOSS_ACCESS = 0.0004                 # ultimo miglio: costante
LOSS_BACKBONE_BASE = 0.0002          # dorsale: cresce con la distanza
LOSS_BACKBONE_PER_KM = 2.0e-7

BW_HUB = ("1 Gbit", "1 Gbit")            # (down, up)
BW_LEAF = ("200 Mbit", "50 Mbit")

EARTH_RADIUS_KM = 6371.0


def short_label(label):
    """'HUB_US_New_York' -> 'New_York'; 'La_Spezia' -> 'La_Spezia'."""
    parts = label.split("_")
    if parts and parts[0] == "HUB":
        return "_".join(parts[2:])
    return label


def haversine_km(lat1, lon1, lat2, lon2):
    """Distanza in linea d'aria (great circle) fra due punti, in km."""
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_RADIUS_KM * math.asin(math.sqrt(a))


def one_way_ms(dist_km, is_access):
    overhead = OVERHEAD_ACCESS_MS if is_access else OVERHEAD_BACKBONE_MS
    return PROP_MS_PER_KM * dist_km * ROUTING_FACTOR + overhead


def packet_loss(dist_km, is_access):
    if is_access:
        return LOSS_ACCESS
    return LOSS_BACKBONE_BASE + LOSS_BACKBONE_PER_KM * dist_km


def build(level):
    nodes = {n["id"]: n for n in level["nodes"]}
    lines = ["graph [", "  directed 0"]

    for n in level["nodes"]:
        down, up = BW_HUB if n["role"] == "miner" else BW_LEAF
        lines += ["  node [",
                  "    id {}".format(n["id"]),
                  '    label "{}"'.format(n["label"]),
                  '    host_bandwidth_down "{}"'.format(down),
                  '    host_bandwidth_up "{}"'.format(up),
                  "  ]"]

    for n in level["nodes"]:
        lines += ["  edge [",
                  "    source {}".format(n["id"]),
                  "    target {}".format(n["id"]),
                  '    label "loop_{}"'.format(short_label(n["label"])),
                  '    latency "{} us"'.format(int(round(LOOPBACK_MS * 1000))),
                  '    jitter "0 us"',
                  "    packet_loss 0.0",
                  "  ]"]

    rows = []
    for pairs, is_access in ((level["backbone"], False), (level["access"], True)):
        for a, b in pairs:
            na, nb = nodes[a], nodes[b]
            d = haversine_km(na["lat"], na["lon"], nb["lat"], nb["lon"])
            lat = one_way_ms(d, is_access)
            loss = packet_loss(d, is_access)
            label = "{}-{}".format(short_label(na["label"]), short_label(nb["label"]))
            lines += ["  edge [",
                      "    source {}".format(a),
                      "    target {}".format(b),
                      '    label "{}"'.format(label),
                      '    latency "{} us"'.format(int(round(lat * 1000))),
                      '    jitter "0 us"',
                      "    packet_loss {:.7f}".format(loss),
                      "  ]"]
            rows.append((label, d, lat, 2 * lat))

    lines.append("]")
    return "\n".join(lines) + "\n", rows


def normalize(src_gml):
    """Riscrive un .gml esistente nella forma che Shadow accetta.

    Serve per il file regionale originale: ne conserva latenze, banda e
    packet_loss e ne cambia solo la sintassi (blocchi multi-riga, latenze in
    microsecondi interi, nessun commento).
    """
    import networkx as nx

    g = nx.read_gml(src_gml, label="id")
    lines = ["graph [", "  directed 0"]
    for n, data in sorted(g.nodes(data=True)):
        lines += ["  node [", "    id {}".format(n)]
        if "label" in data:
            lines.append('    label "{}"'.format(data["label"]))
        for key in ("host_bandwidth_down", "host_bandwidth_up"):
            if key in data:
                lines.append('    {} "{}"'.format(key, data[key]))
        lines.append("  ]")

    rows = []
    for u, v, data in g.edges(data=True):
        ms = float(str(data.get("latency", "0 ms")).replace("ms", "").strip())
        lines += ["  edge [",
                  "    source {}".format(u),
                  "    target {}".format(v)]
        if "label" in data:
            lines.append('    label "{}"'.format(data["label"]))
        lines += ['    latency "{} us"'.format(int(round(ms * 1000))),
                  '    jitter "0 us"',
                  "    packet_loss {}".format(data.get("packet_loss", 0.0)),
                  "  ]"]
        if u != v:
            rows.append((data.get("label", "{}-{}".format(u, v)), float("nan"), ms, 2 * ms))
    lines.append("]")
    return "\n".join(lines) + "\n", rows


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level_json", help="config/levels/<livello>.json")
    ap.add_argument("--from-gml", metavar="FILE",
                    help="invece di generare dal modello, normalizza un .gml "
                         "esistente nella sintassi accettata da Shadow")
    ap.add_argument("-o", "--output", required=True, help="file .gml da scrivere")
    ap.add_argument("--table", action="store_true",
                    help="stampa la tabella distanza/latenza/RTT degli archi")
    args = ap.parse_args()

    with open(args.level_json) as fh:
        level = json.load(fh)

    if args.from_gml:
        gml, rows = normalize(args.from_gml)
    else:
        gml, rows = build(level)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as fh:
        fh.write(gml)

    print("[gen_topology] {} -> {} ({} nodi, {} archi)".format(
        level["name"], args.output, len(level["nodes"]),
        len(level["backbone"]) + len(level["access"])))

    if args.table:
        print("\n  {:<34} {:>9} {:>12} {:>10}".format("arco", "D (km)", "one-way ms", "RTT ms"))
        print("  " + "-" * 68)
        for label, d, lat, rtt in rows:
            dist = "     n/d" if d != d else "{:>9.1f}".format(d)
            print("  {:<34} {} {:>12.3f} {:>10.2f}".format(label, dist, lat, rtt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
