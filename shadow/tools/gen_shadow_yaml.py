#!/usr/bin/env python3
"""
Genera shadow.yaml per un livello: mappa i 10 nodi del .gml sugli host della
simulazione e ne scandisce la timeline dei processi.

TIMELINE DEL BOOTSTRAP (tutto dentro la simulazione, perche' l'orologio di
Shadow parte dal 2000-01-01 e un datadir cotto nativamente verrebbe rifiutato
per "block timestamp too far in the future"):

  t=0            admin: multichaind -> genesi, premine, crea gli stream input
  t=T_FIRST      9 nodi: primo avvio, depositano il proprio indirizzo, escono
  t=T_GRANT      admin: grant permessi + high1 al CA + crea wpoa-weights e lo
                 stream di filiera + distribuisce il GAS iniziale
  t=T_JOIN       9 nodi: multichaind vero, join e sync
  t=T_REGISTER   CA: ESG certificati; miner e aziende: membership
  t=T_TRAFFIC    aziende: traffico; miner: riconciliazione; admin: refill GAS
  height=setup   la wPoA subentra alla PoA nativa: inizio finestra di misura

L'ordine non e' arbitrario: senza record di membership e ESG confermati il
weight engine non ha cluster da valutare, non pubblica nulla su wpoa-weights e
la catena si ferma esattamente a setup-first-blocks con
"cannot score (unsynced or unweighted)".
"""

import argparse
import json
import os
import sys

# indirizzi IP statici: leggibili nei log e stabili fra i livelli
IP_BASE = {"admin": "11.0.0.10", "ca": "11.0.0.11",
           "m1": "11.0.0.21", "m2": "11.0.0.22", "m3": "11.0.0.23",
           "c1": "11.0.0.31", "c2": "11.0.0.32", "c3": "11.0.0.33",
           "c4": "11.0.0.34", "c5": "11.0.0.35"}

# eterogeneita' deliberata: tau_i e rho_k diversi -> W_k e w_k diversi
TX_INTERVAL = {"c1": 8, "c2": 12, "c3": 16, "c4": 20, "c5": 25}   # secondi simulati
RECONCILE_RATE = {"m1": "0.95", "m2": "0.60", "m3": "0.20"}       # frazione riconciliata

RPC_PORT = 27000
P2P_PORT = 27001


def q(value):
    return '"{}"'.format(str(value).replace('"', '\\"'))


def env_block(env, indent):
    pad = " " * indent
    return "\n".join("{}{}: {}".format(pad, k, q(v)) for k, v in sorted(env.items()))


def proc(path, args, start, env, indent=6, final=None):
    pad = " " * indent
    out = ["{}- path: {}".format(pad, path)]
    out.append("{}  args: [{}]".format(pad, ", ".join(q(a) for a in args)))
    out.append("{}  start_time: {}s".format(pad, start))
    if final:
        out.append("{}  expected_final_state: {}".format(pad, final))
    out.append("{}  environment:".format(pad))
    out.append(env_block(env, indent + 4))
    return "\n".join(out)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("level_json")
    ap.add_argument("--gml", required=True)
    ap.add_argument("--run", required=True, help="directory di run (assoluta)")
    ap.add_argument("--tools", required=True, help="directory tools/ (assoluta)")
    ap.add_argument("--bindir", required=True, help="directory dei binari multichain")
    ap.add_argument("--chain", required=True)
    ap.add_argument("--tbt", type=int, default=15)
    ap.add_argument("--setup-blocks", type=int, default=60)
    ap.add_argument("--measure-blocks", type=int, default=200)
    ap.add_argument("--epoch-len", type=int, default=12)
    ap.add_argument("--rng-seed", type=int, default=20260827)
    ap.add_argument("--rpcuser", default="poesia")
    ap.add_argument("--rpcpass", default="poesiarpc")
    ap.add_argument("--stream", default="poesia-supplychain")
    ap.add_argument("-o", "--output", required=True)
    args = ap.parse_args()

    level = json.load(open(args.level_json))
    nodes = level["nodes"]
    by_host = {n["host"]: n for n in nodes}
    miners = [n["host"] for n in nodes if n["role"] == "miner"]
    companies = [n["host"] for n in nodes if n["role"] == "company"]

    # --- timeline -----------------------------------------------------------
    t_first, t_grant, t_join, t_register, t_traffic = 30, 60, 150, 260, 340
    stop = t_traffic + (args.setup_blocks + args.measure_blocks) * args.tbt + 600

    treasury = ""
    tj = os.path.join(os.path.dirname(args.tools), "config", "treasury.json")
    if os.path.exists(tj):
        treasury = json.load(open(tj))["address"]

    admin_ip = IP_BASE["admin"]
    seed = "{}@{}:{}".format(args.chain, admin_ip, P2P_PORT)

    common = {
        "POESIA_RUN": args.run, "POESIA_CHAIN": args.chain,
        "POESIA_BINDIR": args.bindir, "POESIA_SEED": seed,
        "POESIA_ADMIN_IP": admin_ip, "POESIA_RPCPORT": RPC_PORT,
        "POESIA_P2PPORT": P2P_PORT, "POESIA_RPCUSER": args.rpcuser,
        "POESIA_RPCPASS": args.rpcpass, "POESIA_MINERS": " ".join(miners),
        "POESIA_COMPANIES": " ".join(companies), "POESIA_TREASURY": treasury,
        "POESIA_EPOCHLEN": args.epoch_len, "POESIA_RNG_SEED": args.rng_seed,
        "POESIA_STREAM": args.stream,
    }
    for h, ip in IP_BASE.items():
        common["POESIA_IP_{}".format(h)] = ip

    out = ["# GENERATO da tools/gen_shadow_yaml.py — non modificare a mano.",
           "# livello: {} ({})".format(level["name"], level["description"]),
           "",
           "general:",
           "  stop_time: {}s".format(stop),
           "  # Necessario: senza, i busy-loop del nodo (Strengthen() in",
           "  # random.cpp) bloccherebbero l'avanzamento del tempo simulato.",
           "  model_unblocked_syscall_latency: true",
           "  progress: true",
           "  seed: {}".format(args.rng_seed % 100000),
           "",
           "network:",
           "  graph:",
           "    type: gml",
           "    file:",
           "      path: {}".format(args.gml),
           "",
           "hosts:"]

    for n in nodes:
        host, role = n["host"], n["role"]
        ip = IP_BASE[host]
        datadir = os.path.join(args.run, "data", host)
        env = dict(common)
        env.update({"POESIA_HOST": host, "POESIA_ROLE": role, "POESIA_IP": ip,
                    "POESIA_CLUSTER": n.get("cluster", "")})

        daemon_args = ["-datadir=" + datadir, "-port={}".format(P2P_PORT),
                       "-rpcport={}".format(RPC_PORT), "-externalip=" + ip,
                       "-dnsseed=0", "-discover=0", "-debug=wpoa"]
        daemon_args += ["-addnode={}".format(IP_BASE[m]) for m in miners if m != host]
        if host != "admin":
            daemon_args.append("-addnode={}".format(admin_ip))

        out.append("  {}:".format(host))
        out.append("    network_node_id: {}".format(n["id"]))
        out.append("    ip_addr: {}".format(ip))
        out.append("    processes:")

        if role == "admin":
            out.append(proc(os.path.join(args.bindir, "multichaind"),
                            [args.chain] + daemon_args, 0, env, final="running"))
            out.append(proc("/usr/bin/bash",
                            [os.path.join(args.tools, "role_admin.sh"), "grant"],
                            t_grant, env))
            out.append(proc("/usr/bin/bash",
                            [os.path.join(args.tools, "role_admin.sh"), "refill"],
                            t_traffic, env, final="running"))
            # snapshot finale: dump dello stato della catena poco prima dello stop
            out.append(proc("/usr/bin/bash",
                            [os.path.join(args.tools, "role_admin.sh"), "snapshot"],
                            stop - 120, env))
        else:
            out.append(proc("/usr/bin/bash",
                            [os.path.join(args.tools, "node_first_launch.sh")],
                            t_first, env))
            out.append(proc(os.path.join(args.bindir, "multichaind"),
                            [seed] + daemon_args, t_join, env, final="running"))
            if role == "miner":
                env["POESIA_RECONCILE_RATE"] = RECONCILE_RATE.get(host, "0.6")
                out.append(proc("/usr/bin/bash",
                                [os.path.join(args.tools, "role_miner.sh"), "register"],
                                t_register, env))
                out.append(proc("/usr/bin/bash",
                                [os.path.join(args.tools, "role_miner.sh"), "reconcile"],
                                t_traffic, env, final="running"))
            elif role == "ca":
                out.append(proc("/usr/bin/bash",
                                [os.path.join(args.tools, "role_ca.sh")],
                                t_register, env))
            elif role == "company":
                env["POESIA_TX_INTERVAL"] = TX_INTERVAL.get(host, 15)
                out.append(proc("/usr/bin/bash",
                                [os.path.join(args.tools, "role_company.sh"), "register"],
                                t_register, env))
                out.append(proc("/usr/bin/bash",
                                [os.path.join(args.tools, "role_company.sh"), "traffic"],
                                t_traffic, env, final="running"))
        out.append("")

    with open(args.output, "w") as fh:
        fh.write("\n".join(out) + "\n")

    print("[gen_shadow_yaml] {} -> {}".format(level["name"], args.output))
    print("[gen_shadow_yaml]   host: {}".format(", ".join(n["host"] for n in nodes)))
    print("[gen_shadow_yaml]   cluster: " + ", ".join(
        "{}<-{}".format(m, "+".join(c for c in companies if by_host[c].get("cluster") == m) or "-")
        for m in miners))
    print("[gen_shadow_yaml]   stop_time = {}s simulati "
          "({} blocchi di setup + {} misurati a {}s)".format(
              stop, args.setup_blocks, args.measure_blocks, args.tbt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
