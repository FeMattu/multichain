#!/usr/bin/env python3
"""
Verifica che un .gml sia una topologia valida per Shadow e per l'esperimento.

Controlli:
  1. il file e' parsabile come GML (networkx);
  2. il grafo e' NON diretto e CONNESSO (Shadow calcola i cammini minimi fra
     tutti i nodi: un grafo disconnesso e' un errore fatale a runtime);
  3. ogni nodo ha host_bandwidth_down / host_bandwidth_up;
  4. ogni nodo ha un self-loop (Shadow lo usa per la latenza intra-nodo);
  5. ogni arco ha `latency` con magnitudine INTERA (Shadow rifiuta "0.2 ms");
     se manca `packet_loss` Shadow assume 0;
  6. il numero di nodi coincide con quello atteso dal livello.

Stampa inoltre la matrice degli RTT end-to-end fra gli host, che e' la
grandezza realmente vista dai nodi MultiChain (somma delle latenze lungo il
cammino minimo, andata + ritorno).
"""

import argparse
import itertools
import sys

try:
    import networkx as nx
except ImportError:
    sys.stderr.write("ERRORE: serve networkx (pip install networkx)\n")
    sys.exit(2)


def parse_ms(value):
    """Converte una stringa con unita' di Shadow in millisecondi."""
    text = str(value).strip()
    for suffix, factor in (("ns", 1e-6), ("us", 1e-3), ("ms", 1.0), ("s", 1000.0)):
        if text.endswith(suffix):
            return float(text[:-len(suffix)].strip()) * factor
    return float(text)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("gml")
    ap.add_argument("--expect-nodes", type=int, default=10)
    ap.add_argument("--matrix", action="store_true", help="stampa la matrice degli RTT")
    args = ap.parse_args()

    errors, warnings = [], []

    try:
        g = nx.read_gml(args.gml, label="id")
    except Exception as exc:                                    # noqa: BLE001
        print("FALLITO: il file non e' un GML valido: {}".format(exc))
        return 1

    if g.is_directed():
        errors.append("il grafo e' diretto; Shadow richiede 'directed 0'")

    if g.number_of_nodes() != args.expect_nodes:
        errors.append("nodi attesi {}, trovati {}".format(args.expect_nodes, g.number_of_nodes()))

    simple = nx.Graph((u, v) for u, v in g.edges() if u != v)
    simple.add_nodes_from(g.nodes())
    if simple.number_of_nodes() and not nx.is_connected(simple):
        comps = [sorted(c) for c in nx.connected_components(simple)]
        errors.append("grafo NON connesso, componenti: {}".format(comps))

    for n, data in g.nodes(data=True):
        for attr in ("host_bandwidth_down", "host_bandwidth_up"):
            if attr not in data:
                errors.append("nodo {}: manca {}".format(n, attr))
        if not g.has_edge(n, n):
            warnings.append("nodo {}: nessun self-loop (latenza intra-nodo = 0)".format(n))

    for u, v, data in g.edges(data=True):
        if "latency" not in data:
            errors.append("arco {}-{}: manca 'latency'".format(u, v))
        if "packet_loss" not in data:
            warnings.append("arco {}-{}: manca 'packet_loss' (Shadow assume 0)".format(u, v))
        lat = str(data.get("latency", ""))
        mag = lat.split()[0] if lat.split() else ""
        if mag and not mag.lstrip("-").isdigit():
            errors.append(
                "arco {}-{}: latency='{}' — Shadow richiede una magnitudine INTERA "
                "('0.2 ms' viene rifiutato, usare '200 us')".format(u, v, lat))
        jit = str(data.get("jitter", "0")).split()[0] if data.get("jitter") else "0"
        if jit not in ("0", "0.0", "None"):
            warnings.append(
                "arco {}-{}: jitter={} ma il campo NON e' implementato da Shadow "
                "(issue shadow/shadow#3601)".format(u, v, data.get("jitter")))

    for w in warnings:
        print("  avviso : {}".format(w))
    for e in errors:
        print("  ERRORE : {}".format(e))

    if errors:
        print("FALLITO: {} ({} errori)".format(args.gml, len(errors)))
        return 1

    if args.matrix:
        for u, v, data in simple.edges(data=True):
            simple[u][v]["ms"] = parse_ms(g[u][v]["latency"])
        paths = dict(nx.all_pairs_dijkstra_path_length(simple, weight="ms"))
        names = {n: g.nodes[n].get("label", str(n)) for n in g.nodes()}
        print("\n  RTT end-to-end (ms), cammino minimo andata+ritorno:")
        rows = sorted(g.nodes())
        print("      " + "".join("{:>8}".format(str(c)) for c in rows))
        for r in rows:
            print("  {:>3} ".format(r) + "".join(
                "{:>8.2f}".format(2 * paths[r][c]) for c in rows) + "  {}".format(names[r]))
        worst = max((2 * paths[a][b], a, b) for a, b in itertools.combinations(rows, 2))
        print("\n  RTT massimo: {:.2f} ms  ({} <-> {})".format(
            worst[0], names[worst[1]], names[worst[2]]))

    print("OK: {} — {} nodi, {} archi, connesso".format(
        args.gml, g.number_of_nodes(), g.number_of_edges()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
