#!/usr/bin/env python3
"""
Genera shadow.yaml a partire da UN SOLO descrittore di simulazione.

    tools/gen_simulation.py config/simulations/<nome>.json -o <run>/shadow.yaml

E' il generatore della configurazione dichiarativa: il descrittore JSON
referenzia per path i due assi riusabili — i parametri di catena
(config/blockchain/*.dat) e la topologia (config/topologies/*.gml) — e dichiara
la dislocazione dei nodi. Nessun altro parametro arriva da riga di comando.

DUE MODI, perche' il params.dat va scritto PRIMA dello shadow.yaml:

  --emit-env   stampa assegnamenti shell con la configurazione risolta.
               run.sh li valuta e passa i valori a prepare_params.sh.
  (default)    scrive lo shadow.yaml. Con --effective-params rilegge il
               setup-first-blocks EFFETTIVO dal params.dat appena creato:
               multichain-util lo alza da solo a un pavimento derivato quando
               il weight engine alimenta la selezione wPoA (vedi
               mc_MultichainParams::AdjustSetupFirstBlocks), e stop_time deve
               tenerne conto o la finestra di misura si accorcia in silenzio.

TIMELINE DEL BOOTSTRAP — identica a quella di gen_shadow_yaml.py, che questo
file sostituisce per le simulazioni dichiarative. Tutto avviene DENTRO la
simulazione, perche' l'orologio di Shadow parte dal 2000-01-01 e un datadir
cotto nativamente verrebbe rifiutato per "block timestamp too far in the
future":

  t=0            admin: multichaind -> genesi, premine, crea gli stream input
  t=T_FIRST      gli altri nodi: primo avvio, depositano l'indirizzo, escono
  t=T_GRANT      admin: grant permessi + high1 alle CA + crea wpoa-weights e lo
                 stream di filiera + distribuisce il GAS iniziale
  t=T_JOIN       gli altri nodi: multichaind vero, join e sync
  t=T_REGISTER   CA: ESG certificati; miner e aziende: membership
  t=T_TRAFFIC    aziende: traffico; miner: riconciliazione; admin: refill GAS
                 + sorvegliante di epoca
  height=setup   la wPoA subentra alla PoA nativa: inizio finestra di misura

L'ordine non e' arbitrario: senza record di membership e ESG confermati il
weight engine non ha cluster da valutare, non pubblica nulla su wpoa-weights e
la catena si ferma esattamente a setup-first-blocks con
"cannot score (unsynced or unweighted)".
"""

import argparse
import json
import math
import os
import re
import shlex
import sys

# --- timeline del bootstrap, in secondi simulati -----------------------------
T_FIRST, T_GRANT, T_JOIN, T_REGISTER, T_TRAFFIC = 30, 60, 150, 260, 340

# --- vincolo sul setup (stesso di run.sh, vedi README "Vincolo sul setup") ---
STABILITY_MARGIN = 6    # blocchi di sepoltura dell'epoca che porta ESG/membership
SETUP_SLACK = 12        # margine per il tick del weight engine e la propagazione
SETUP_FLOOR = 60        # minimo assoluto, sotto il quale non si scende mai

# --- calcolo automatico di stop_time ----------------------------------------
MEASURE_EPOCHS_DEFAULT = 16   # epoche coperte dopo la fine del setup
T_DRAIN = 600                 # snapshot finale + margine di chiusura, secondi

# --- vincoli di Shadow (vedi README "Vincoli di Shadow scoperti sul campo") --
# Con il default (10 ns) il loop Strengthen() di random.cpp — che gira su
# clock_gettime/gettimeofday, entrambe vDSO — non termina mai in tempo utile e
# il nodo non arriva ad avviarsi. Era il --unblocked-vdso-latency della riga di
# comando: qui e' un campo dello shadow.yaml, cosi' run.sh non ha argomenti.
VDSO_LATENCY = "20 us"

RPC_PORT = 27000
P2P_PORT = 27001

# --- eterogeneita' deliberata: tau_i e rho_k diversi -> W_k e w_k diversi ----
# La scala delle aziende e' quella storica a 5 nodi, ripetuta ciclicamente:
# a 5 aziende riproduce esattamente i valori dei quattro livelli originali.
TX_INTERVAL_LADDER = [8, 12, 16, 20, 25]          # secondi simulati fra due publish
RECONCILE_RATE_MAX, RECONCILE_RATE_MIN = 0.95, 0.20   # frazione riconciliata

# --- allocazione degli indirizzi IP -----------------------------------------
# Statici e leggibili nei log. Sono indipendenti dal network_node_id: la
# topologia decide le latenze, questi decidono solo come i nodi si chiamano.
IP_ADMIN = "11.0.0.10"
IP_CA_BASE = "11.0.0.{}"      # .11 .12 .13 — al massimo 3 CA
IP_MINER_BASE = "11.0.1.{}"
IP_COMPANY_BASE = "11.0.2.{}"

MAX_MINERS = 254
MAX_COMPANIES = 254


class ConfigError(Exception):
    """Errore di configurazione: va mostrato all'utente, non come traceback."""


# ---------------------------------------------------------------------------
# lettura dei file referenziati
# ---------------------------------------------------------------------------

_DAT_LINE = re.compile(r"^\s*([A-Z][A-Z0-9_]*)\s*=\s*(.*?)\s*$")


def read_params_dat(path):
    """Legge un file di parametri di catena in formato KEY=VALUE.

    E' lo stesso formato di config/params.overrides: sourceable da bash, con
    commenti '#' a inizio riga o in coda al valore.
    """
    if not os.path.isfile(path):
        raise ConfigError(
            "blockchain_params_file non trovato: {}\n"
            "       I parametri di catena disponibili sono in config/blockchain/.".format(path))
    out = {}
    with open(path) as fh:
        for lineno, raw in enumerate(fh, 1):
            line = raw.split("#", 1)[0].strip()
            if not line:
                continue
            m = _DAT_LINE.match(line)
            if not m:
                raise ConfigError(
                    "{}:{}: riga non riconosciuta nel file di parametri: {!r}\n"
                    "       Atteso il formato KEY=VALUE di config/params.overrides.".format(
                        path, lineno, raw.rstrip()))
            out[m.group(1)] = m.group(2).strip().strip('"').strip("'")
    return out


_GML_NODE_ID = re.compile(r"^\s*id\s+(\d+)\s*$")


def read_gml_nodes(path):
    """Estrae gli id dei nodi dichiarati nel .gml, con la loro label.

    Basta una lettura testuale: il formato che tools/gen_topology.py emette e'
    canonico e multi-riga (i blocchi compatti Shadow 3.3 li rifiuta comunque).
    """
    if not os.path.isfile(path):
        raise ConfigError(
            "topology_file non trovato: {}\n"
            "       Le topologie disponibili sono in config/topologies/.".format(path))
    nodes, in_node, current = {}, False, None
    with open(path) as fh:
        for raw in fh:
            line = raw.strip()
            if line.startswith("node ["):
                in_node, current = True, None
                continue
            if not in_node:
                continue
            if line == "]":
                in_node, current = False, None
                continue
            m = _GML_NODE_ID.match(raw)
            if m:
                current = int(m.group(1))
                nodes.setdefault(current, "")
            elif line.startswith("label ") and current is not None:
                nodes[current] = line[len("label "):].strip().strip('"')
    if not nodes:
        raise ConfigError("nessun nodo trovato in {}: il file e' una topologia GML valida?".format(path))
    return nodes


def read_effective_setup(params_dat):
    """setup-first-blocks come sta scritto nel params.dat generato.

    multichain-util alza da solo il valore fino al pavimento derivato quando il
    weight engine alimenta la selezione wPoA: il numero che conta per la
    finestra di misura e' questo, non quello chiesto nel file .dat.
    """
    if not os.path.isfile(params_dat):
        return None
    with open(params_dat) as fh:
        for line in fh:
            m = re.match(r"^\s*setup-first-blocks\s*=\s*(\d+)", line)
            if m:
                return int(m.group(1))
    return None


# ---------------------------------------------------------------------------
# validazione
# ---------------------------------------------------------------------------

def validate_schema(config, schema_path):
    """Valida contro config/simulation.schema.json.

    jsonschema e' una dipendenza morbida: se manca, i controlli incrociati piu'
    sotto restano comunque attivi e coprono tutti i vincoli che il README
    promette (admin=1, ca 1-3, factor intero 1-5, id unici, node id esistenti).
    """
    try:
        import jsonschema
    except ImportError:
        print("[gen_simulation] ATTENZIONE: modulo 'jsonschema' assente, "
              "validazione limitata ai controlli incrociati", file=sys.stderr)
        return
    with open(schema_path) as fh:
        schema = json.load(fh)
    validator = jsonschema.Draft7Validator(schema)
    errors = sorted(validator.iter_errors(config), key=lambda e: list(e.absolute_path))
    if errors:
        lines = ["il descrittore di simulazione non rispetta {}:".format(schema_path)]
        for err in errors:
            where = "/".join(str(p) for p in err.absolute_path) or "(radice)"
            lines.append("       - {}: {}".format(where, _friendly(err)))
        raise ConfigError("\n".join(lines))


def _friendly(err):
    """Messaggio leggibile al posto del dump dell'istanza.

    Su un array fuori misura jsonschema stampa l'intero contenuto ("[{...},
    {...}] is too long"), che su nodes.* significa righe illeggibili: quello che
    serve sapere e' quanti elementi ci sono e quanti ne servono.
    """
    schema = err.schema if isinstance(err.schema, dict) else {}
    if err.validator in ("minItems", "maxItems"):
        low, high = schema.get("minItems"), schema.get("maxItems")
        if low == high:
            expected = "esattamente {}".format(low)
        elif low is not None and high is not None:
            expected = "fra {} e {}".format(low, high)
        else:
            expected = "almeno {}".format(low) if low is not None else "al massimo {}".format(high)
        return "ha {} elementi, ne servono {}.".format(len(err.instance), expected)
    if err.validator in ("oneOf", "anyOf"):
        return "valore non ammesso: {!r}. {}".format(
            err.instance, schema.get("description", "")).strip()
    return err.message


def _require_int(value, label):
    """Rifiuta 2.0 dove e' chiesto 2: in JSON Schema draft-07 sono lo stesso tipo."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise ConfigError(
            "{} deve essere un intero, non {!r} ({}).".format(label, value, type(value).__name__))
    return value


def resolve_nodes(config, gml_nodes, topology_file):
    """Costruisce la lista degli host applicando vincoli e generazione automatica."""
    nodes = config["nodes"]
    scaling = config.get("scaling", {})

    miners = list(nodes["miners"])
    cas = list(nodes["ca"])
    admins = list(nodes["admin"])

    # --- vincoli di cardinalita', con messaggi espliciti ---------------------
    if len(admins) != 1:
        raise ConfigError(
            "nodes.admin deve contenere ESATTAMENTE 1 elemento, ne ha {}.\n"
            "       L'amministratore tiene il premine ed e' il seed della rete: "
            "duplicarlo forkerebbe la genesi.".format(len(admins)))
    if not 1 <= len(cas) <= 3:
        raise ConfigError(
            "nodes.ca deve contenere fra 1 e 3 elementi, ne ha {}.".format(len(cas)))
    if not miners:
        raise ConfigError("nodes.miners deve contenere almeno 1 elemento.")
    if len(miners) > MAX_MINERS:
        raise ConfigError(
            "nodes.miners ha {} elementi, il massimo e' {} "
            "(un indirizzo IP per host in 11.0.1.0/24).".format(len(miners), MAX_MINERS))

    if "ca_count" in scaling:
        declared = _require_int(scaling["ca_count"], "scaling.ca_count")
        if declared != len(cas):
            raise ConfigError(
                "scaling.ca_count = {} ma nodes.ca elenca {} nodi.\n"
                "       Il campo e' ridondante: o lo si allinea, o lo si toglie.".format(
                    declared, len(cas)))

    # --- aziende: elenco esplicito oppure generazione lineare ---------------
    companies = list(nodes.get("companies") or [])
    generated = False
    if not companies:
        if "factor" not in scaling:
            raise ConfigError(
                "nodes.companies e' assente e scaling.factor non e' impostato: "
                "non c'e' modo di sapere quante aziende creare.\n"
                "       O si elenca nodes.companies, o si imposta scaling.factor "
                "(intero fra 1 e 5).")
        factor = _require_int(scaling["factor"], "scaling.factor")
        if not 1 <= factor <= 5:
            raise ConfigError(
                "scaling.factor = {} fuori dall'intervallo ammesso [1, 5].".format(factor))
        count = len(miners) * factor
        if count > MAX_COMPANIES:
            raise ConfigError(
                "scaling.factor = {} su {} miner produrrebbe {} aziende, il massimo e' {}.".format(
                    factor, len(miners), count, MAX_COMPANIES))
        # location e network_node_id presi a rotazione fra quelli dei miner
        for i in range(count):
            host = miners[i % len(miners)]
            companies.append({
                "id": "c{}".format(i + 1),
                "location": host["location"],
                "network_node_id": host["network_node_id"],
                "cluster": host["id"],
            })
        generated = True
    elif "factor" in scaling:
        factor = _require_int(scaling["factor"], "scaling.factor")
        if not 1 <= factor <= 5:
            raise ConfigError(
                "scaling.factor = {} fuori dall'intervallo ammesso [1, 5].".format(factor))
        expected = len(miners) * factor
        if len(companies) != expected:
            raise ConfigError(
                "nodes.companies elenca {} aziende ma scaling.factor = {} su {} miner "
                "ne implica {}.\n"
                "       Lo scaling e' sempre lineare (n_companies = n_miners * factor): "
                "o si allinea l'elenco, o si toglie scaling.factor.".format(
                    len(companies), factor, len(miners), expected))

    # --- id unici su TUTTE le categorie -------------------------------------
    seen = {}
    for role, group in (("miner", miners), ("company", companies),
                        ("ca", cas), ("admin", admins)):
        for node in group:
            nid = node["id"]
            if nid in seen:
                extra = ""
                if generated and role == "company":
                    extra = ("\n       Le aziende generate automaticamente si chiamano c1..c{}: "
                             "nessun altro nodo puo' usare quei nomi.".format(len(companies)))
                raise ConfigError(
                    "id host duplicato {!r}: usato da {} e da {}.\n"
                    "       Ogni host ha una propria datadir e un proprio "
                    "POESIA_IP_<id>: gli id devono essere unici.{}".format(
                        nid, seen[nid], role, extra))
            seen[nid] = role

    # --- ogni network_node_id deve esistere nella topologia -----------------
    for role, group in (("miners", miners), ("companies", companies),
                        ("ca", cas), ("admin", admins)):
        for node in group:
            nnid = node["network_node_id"]
            if nnid not in gml_nodes:
                raise ConfigError(
                    "nodes.{}[{}] punta a network_node_id {}, che non esiste in {}.\n"
                    "       Nodi disponibili: {}".format(
                        role, node["id"], nnid, topology_file,
                        ", ".join("{} ({})".format(k, v) for k, v in sorted(gml_nodes.items()))))

    # --- cluster delle aziende: esplicito o a rotazione ---------------------
    miner_ids = [m["id"] for m in miners]
    for i, node in enumerate(companies):
        cluster = node.get("cluster")
        if cluster is None:
            node = dict(node)
            node["cluster"] = miner_ids[i % len(miner_ids)]
            companies[i] = node
        elif cluster not in miner_ids:
            raise ConfigError(
                "l'azienda {!r} dichiara cluster {!r}, che non e' un miner di questa "
                "simulazione.\n       Miner disponibili: {}".format(
                    node["id"], cluster, ", ".join(miner_ids)))

    return miners, companies, cas, admins[0], generated


def assign_hosts(miners, companies, cas, admin):
    """Assegna IP, cluster e parametri di eterogeneita' a ogni host."""
    hosts = []

    hosts.append(dict(admin, role="admin", ip=IP_ADMIN))

    for i, node in enumerate(cas, start=1):
        hosts.append(dict(node, role="ca", ip=IP_CA_BASE.format(10 + i),
                          ca_index=i, ca_count=len(cas)))

    # rho_k: scala lineare dal massimo al minimo, cosi' i miner restano
    # deliberatamente eterogenei qualunque sia il loro numero.
    n = len(miners)
    for i, node in enumerate(miners):
        if n == 1:
            rate = RECONCILE_RATE_MAX
        else:
            rate = RECONCILE_RATE_MAX - i * (RECONCILE_RATE_MAX - RECONCILE_RATE_MIN) / (n - 1)
        hosts.append(dict(node, role="miner", ip=IP_MINER_BASE.format(i + 1),
                          reconcile_rate="{:.4f}".format(rate).rstrip("0").rstrip(".")))

    for i, node in enumerate(companies):
        hosts.append(dict(node, role="company", ip=IP_COMPANY_BASE.format(i + 1),
                          tx_interval=TX_INTERVAL_LADDER[i % len(TX_INTERVAL_LADDER)]))

    return hosts


# ---------------------------------------------------------------------------
# granularita' temporale e tempo di stop
# ---------------------------------------------------------------------------

def granularity_settings(value):
    """Traduce shadow.time_granularity nei campi reali dello shadow.yaml.

    experimental.runahead e' un LIMITE INFERIORE, non il valore usato: Shadow
    calcola max(latenza minima del grafo, runahead) — vedi src/main/core/
    runahead.rs. Quindi "minimo consentito" si ottiene con un pavimento inerte
    (1 ns), che lascia vincere la latenza minima della topologia.

    general.model_unblocked_syscall_latency resta true in OGNI modo, anche
    'fast': senza, il busy-loop Strengthen() di random.cpp impedisce
    l'avanzamento del tempo simulato e i nodi non arrivano ad avviarsi.
    """
    if value == "host_native":
        return {
            "runahead": "1 ns",
            "use_dynamic_runahead": "false",
            "note": "runahead al pavimento inerte: Shadow usa la latenza minima del grafo",
        }
    if value == "fast":
        return {
            "runahead": "1 ms",
            "use_dynamic_runahead": "true",
            "note": "default permissivi di Shadow: piu' veloce, temporalmente meno fedele",
        }
    return {
        "runahead": value,
        "use_dynamic_runahead": "false",
        "note": "runahead imposto a mano dal descrittore di simulazione",
    }


_DURATION = re.compile(r"^(\d+)\s*([a-z]+)$")
_DURATION_SECONDS = {
    "ns": 1e-9, "us": 1e-6, "ms": 1e-3,
    "s": 1, "sec": 1, "secs": 1, "second": 1, "seconds": 1,
    "m": 60, "min": 60, "mins": 60, "minute": 60, "minutes": 60,
    "h": 3600, "hr": 3600, "hrs": 3600, "hour": 3600, "hours": 3600,
}


def duration_to_seconds(text):
    m = _DURATION.match(text.strip())
    if not m or m.group(2) not in _DURATION_SECONDS:
        raise ConfigError("durata non riconosciuta: {!r}".format(text))
    return int(m.group(1)) * _DURATION_SECONDS[m.group(2)]


def resolve_setup_blocks(bc, tbt, epoch_len, params_file):
    """setup-first-blocks: 'auto' lo calcola, un intero esplicito viene validato.

    La fase PoA nativa deve durare abbastanza da far confermare membership ed
    ESG, seppellire l'epoca che li contiene e pubblicare i pesi su
    wpoa-weights. Se la wPoA subentra prima, la mappa dei pesi e' vuota e la
    catena si ferma con "cannot score (unsynced or unweighted)".
    """
    min_setup = math.ceil(T_TRAFFIC / tbt) + epoch_len + STABILITY_MARGIN + SETUP_SLACK
    raw = bc.get("SETUP_FIRST_BLOCKS", "auto")
    if str(raw).strip().lower() == "auto":
        return max(min_setup, SETUP_FLOOR), min_setup
    try:
        setup = int(raw)
    except ValueError:
        raise ConfigError(
            "{}: SETUP_FIRST_BLOCKS deve essere un intero oppure 'auto', "
            "non {!r}.".format(params_file, raw))
    if setup < min_setup:
        raise ConfigError(
            "{}: SETUP_FIRST_BLOCKS = {} e' troppo corto per "
            "TARGET_BLOCK_TIME = {} e WEIGHT_EPOCH_LENGTH = {}.\n"
            "       Con questa combinazione la wPoA subentrerebbe prima che esistano pesi\n"
            "       pubblicati e la catena si fermerebbe. Serve almeno {}, "
            "oppure 'auto'.".format(params_file, setup, tbt, epoch_len, min_setup))
    return setup, min_setup


def resolve_stop_time(config, bc, tbt, epoch_len, setup_blocks):
    """stop_time: esplicito se dato, altrimenti calcolato dai parametri di catena.

        measure_blocks = MEASURE_EPOCHS * WEIGHT_EPOCH_LENGTH
        stop_time      = T_TRAFFIC + (setup + measure_blocks) * TARGET_BLOCK_TIME + T_DRAIN

    T_TRAFFIC copre il bootstrap fino all'avvio del traffico, il termine centrale
    i blocchi che devono essere effettivamente minati (setup PoA nativo piu'
    finestra di misura), T_DRAIN lo snapshot finale e il margine di chiusura.
    """
    measure_epochs = int(bc.get("MEASURE_EPOCHS", MEASURE_EPOCHS_DEFAULT))
    measure_blocks = measure_epochs * epoch_len
    auto = T_TRAFFIC + (setup_blocks + measure_blocks) * tbt + T_DRAIN

    requested = config.get("shadow", {}).get("stop_time", "auto")
    if requested == "auto":
        return auto, measure_blocks, measure_epochs, "auto"
    forced = int(round(duration_to_seconds(requested)))
    return forced, measure_blocks, measure_epochs, requested


# ---------------------------------------------------------------------------
# emissione dello shadow.yaml
# ---------------------------------------------------------------------------

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


def build_yaml(plan):
    hosts = plan["hosts"]
    gran = plan["granularity"]
    miners = [h["id"] for h in hosts if h["role"] == "miner"]
    companies = [h["id"] for h in hosts if h["role"] == "company"]
    cas = [h["id"] for h in hosts if h["role"] == "ca"]
    admin = next(h for h in hosts if h["role"] == "admin")

    seed_env = "{}@{}:{}".format(plan["chain"], admin["ip"], P2P_PORT)

    common = {
        "POESIA_RUN": plan["run"], "POESIA_CHAIN": plan["chain"],
        "POESIA_BINDIR": plan["bindir"], "POESIA_SEED": seed_env,
        "POESIA_ADMIN_IP": admin["ip"], "POESIA_RPCPORT": RPC_PORT,
        "POESIA_P2PPORT": P2P_PORT, "POESIA_RPCUSER": plan["rpcuser"],
        "POESIA_RPCPASS": plan["rpcpass"], "POESIA_MINERS": " ".join(miners),
        "POESIA_COMPANIES": " ".join(companies), "POESIA_CAS": " ".join(cas),
        "POESIA_ADMIN": admin["id"], "POESIA_TREASURY": plan["treasury"],
        "POESIA_EPOCHLEN": plan["epoch_len"], "POESIA_RNG_SEED": plan["seed"],
        # serve al sorvegliante di epoca per non campionare le epoche che
        # cadono interamente dentro la fase di setup, dove la wPoA non governa
        "POESIA_SETUPBLOCKS": plan["setup_blocks"],
        "POESIA_STREAM": plan["stream"],
    }
    for h in hosts:
        common["POESIA_IP_{}".format(h["id"])] = h["ip"]

    tools = plan["tools"]
    out = [
        "# GENERATO da tools/gen_simulation.py — non modificare a mano.",
        "# simulazione: {}".format(plan["name"]),
    ]
    if plan.get("description"):
        out.append("# {}".format(plan["description"]))
    out += [
        "# parametri di catena: {}".format(plan["params_file"]),
        "# topologia:           {}".format(plan["topology_file"]),
        "# {} miner, {} aziende{}, {} CA, 1 admin".format(
            len(miners), len(companies),
            " (generate da scaling.factor)" if plan["companies_generated"] else "",
            len(cas)),
        "",
        "general:",
        "  stop_time: {}s".format(plan["stop_time"]),
        "  # {}".format(plan["stop_time_origin"]),
        "  # Necessario: senza, i busy-loop del nodo (Strengthen() in",
        "  # random.cpp) bloccherebbero l'avanzamento del tempo simulato.",
        "  model_unblocked_syscall_latency: true",
        "  progress: true",
        "  seed: {}".format(plan["seed"] % (2 ** 32)),
        "  parallelism: {}".format(plan["parallelism"]),
        "",
        "experimental:",
        "  # time_granularity: {} — {}".format(plan["time_granularity"], gran["note"]),
        "  runahead: {}".format(q(gran["runahead"])),
        "  use_dynamic_runahead: {}".format(gran["use_dynamic_runahead"]),
        "  # Obbligatorio su questo carico: era --unblocked-vdso-latency di run.sh.",
        "  unblocked_vdso_latency: {}".format(q(VDSO_LATENCY)),
        "",
        "network:",
        "  graph:",
        "    type: gml",
        "    file:",
        "      path: {}".format(plan["topology_abs"]),
        "",
        "hosts:",
    ]

    for h in hosts:
        role = h["role"]
        datadir = os.path.join(plan["run"], "data", h["id"])
        env = dict(common)
        env.update({"POESIA_HOST": h["id"], "POESIA_ROLE": role, "POESIA_IP": h["ip"],
                    "POESIA_CLUSTER": h.get("cluster", ""),
                    "POESIA_LOCATION": h["location"]})

        daemon_args = ["-datadir=" + datadir, "-port={}".format(P2P_PORT),
                       "-rpcport={}".format(RPC_PORT), "-externalip=" + h["ip"],
                       "-dnsseed=0", "-discover=0", "-debug=wpoa"]
        daemon_args += ["-addnode={}".format(m["ip"]) for m in hosts
                        if m["role"] == "miner" and m["id"] != h["id"]]
        if role != "admin":
            daemon_args.append("-addnode={}".format(admin["ip"]))

        out.append("  {}:".format(h["id"]))
        out.append("    network_node_id: {}   # {}".format(
            h["network_node_id"], h["location"]))
        out.append("    ip_addr: {}".format(h["ip"]))
        out.append("    processes:")

        if role == "admin":
            out.append(proc(os.path.join(plan["bindir"], "multichaind"),
                            [plan["chain"]] + daemon_args, 0, env, final="running"))
            out.append(proc("/usr/bin/bash",
                            [os.path.join(tools, "role_admin.sh"), "grant"], T_GRANT, env))
            out.append(proc("/usr/bin/bash",
                            [os.path.join(tools, "role_admin.sh"), "refill"],
                            T_TRAFFIC, env, final="running"))
            # sorvegliante di epoca: a ogni epoca chiusa e sepolta campiona cio'
            # che a fine run non sarebbe piu' ricostruibile. Solo bash e curl:
            # nessun interprete lanciato dentro Shadow.
            out.append(proc("/usr/bin/bash",
                            [os.path.join(tools, "role_admin.sh"), "epoch_watch"],
                            T_TRAFFIC, env, final="running"))
            out.append(proc("/usr/bin/bash",
                            [os.path.join(tools, "role_admin.sh"), "snapshot"],
                            plan["stop_time"] - 120, env))
        else:
            out.append(proc("/usr/bin/bash",
                            [os.path.join(tools, "node_first_launch.sh")], T_FIRST, env))
            out.append(proc(os.path.join(plan["bindir"], "multichaind"),
                            [seed_env] + daemon_args, T_JOIN, env, final="running"))
            if role == "miner":
                env["POESIA_RECONCILE_RATE"] = h["reconcile_rate"]
                out.append(proc("/usr/bin/bash",
                                [os.path.join(tools, "role_miner.sh"), "register"],
                                T_REGISTER, env))
                out.append(proc("/usr/bin/bash",
                                [os.path.join(tools, "role_miner.sh"), "reconcile"],
                                T_TRAFFIC, env, final="running"))
            elif role == "ca":
                # ogni CA certifica una fetta dei target, presa a rotazione:
                # senza questo, N CA scriverebbero N volte lo stesso ESG.
                env["POESIA_CA_INDEX"] = h["ca_index"]
                env["POESIA_CA_COUNT"] = h["ca_count"]
                out.append(proc("/usr/bin/bash",
                                [os.path.join(tools, "role_ca.sh")], T_REGISTER, env))
            elif role == "company":
                env["POESIA_TX_INTERVAL"] = h["tx_interval"]
                out.append(proc("/usr/bin/bash",
                                [os.path.join(tools, "role_company.sh"), "register"],
                                T_REGISTER, env))
                out.append(proc("/usr/bin/bash",
                                [os.path.join(tools, "role_company.sh"), "traffic"],
                                T_TRAFFIC, env, final="running"))
        out.append("")

    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# risoluzione completa
# ---------------------------------------------------------------------------

def resolve(config_path, root, bindir, effective_params=None):
    with open(config_path) as fh:
        try:
            config = json.load(fh)
        except ValueError as exc:
            raise ConfigError("{}: JSON non valido: {}".format(config_path, exc))

    validate_schema(config, os.path.join(root, "config", "simulation.schema.json"))

    params_file = config["blockchain_params_file"]
    topology_file = config["topology_file"]
    params_abs = params_file if os.path.isabs(params_file) else os.path.join(root, params_file)
    topology_abs = topology_file if os.path.isabs(topology_file) else os.path.join(root, topology_file)

    bc = read_params_dat(params_abs)
    gml_nodes = read_gml_nodes(topology_abs)

    miners, companies, cas, admin, generated = resolve_nodes(config, gml_nodes, topology_file)
    hosts = assign_hosts(miners, companies, cas, admin)

    for key in ("TARGET_BLOCK_TIME", "WEIGHT_EPOCH_LENGTH"):
        if key not in bc:
            raise ConfigError("{}: manca il parametro obbligatorio {}.".format(params_file, key))
    tbt = int(bc["TARGET_BLOCK_TIME"])
    epoch_len = int(bc["WEIGHT_EPOCH_LENGTH"])
    if tbt <= 0:
        raise ConfigError("{}: TARGET_BLOCK_TIME deve essere positivo.".format(params_file))

    setup_blocks, min_setup = resolve_setup_blocks(bc, tbt, epoch_len, params_file)
    # Dopo prepare_params.sh vale il setup EFFETTIVO scritto in params.dat:
    # multichain-util puo' averlo alzato al pavimento derivato al genesi.
    if effective_params:
        actual = read_effective_setup(effective_params)
        if actual is not None and actual != setup_blocks:
            print("[gen_simulation] setup-first-blocks effettivo in params.dat: {} "
                  "(chiesto {})".format(actual, setup_blocks), file=sys.stderr)
            setup_blocks = actual

    stop_time, measure_blocks, measure_epochs, stop_src = resolve_stop_time(
        config, bc, tbt, epoch_len, setup_blocks)
    if stop_src == "auto":
        origin = ("stop_time automatico: {} + ({} setup + {} misura) * {}s + {} "
                  "= copre {} epoche dopo il setup".format(
                      T_TRAFFIC, setup_blocks, measure_blocks, tbt, T_DRAIN, measure_epochs))
    else:
        origin = ("stop_time imposto dal descrittore ({}): sovrascrive il calcolo "
                  "automatico, che avrebbe dato {}s".format(
                      stop_src,
                      T_TRAFFIC + (setup_blocks + measure_blocks) * tbt + T_DRAIN))

    name = config["name"]
    treasury = ""
    treasury_json = os.path.join(root, "config", "treasury.json")
    if os.path.exists(treasury_json):
        treasury = json.load(open(treasury_json))["address"]

    shadow_cfg = config.get("shadow", {})
    granularity = shadow_cfg.get("time_granularity", "host_native")

    return {
        "name": name,
        "description": config.get("description", ""),
        # MultiChain vuole un nome di catena senza separatori: stessa
        # convenzione dei livelli storici (poesiacontinentale).
        "chain": "poesia" + re.sub(r"[^a-z0-9]", "", name.lower()),
        "run": os.path.join(root, "runs", name),
        "root": root,
        "tools": os.path.join(root, "tools"),
        "bindir": bindir,
        "params_file": params_file,
        "params_abs": params_abs,
        "topology_file": topology_file,
        "topology_abs": topology_abs,
        "seed": config.get("seed", 20260827),
        "tbt": tbt,
        "epoch_len": epoch_len,
        "setup_blocks": setup_blocks,
        "min_setup": min_setup,
        "measure_blocks": measure_blocks,
        "measure_epochs": measure_epochs,
        "stop_time": stop_time,
        "stop_time_origin": origin,
        "time_granularity": granularity,
        "granularity": granularity_settings(granularity),
        "parallelism": shadow_cfg.get("parallelism", 0),
        "hosts": hosts,
        "treasury": treasury,
        "companies_generated": generated,
        "sortition_delta": bc.get("WPOA_SORTITION_DELTA", "0.5"),
        "dump_function": bc.get("WPOA_DUMPFUNCTION", "none"),
        "rpcuser": "poesia",
        "rpcpass": "poesiarpc",
        "stream": "poesia-supplychain",
    }


def emit_env(plan):
    """Assegnamenti shell con la configurazione risolta, per run.sh."""
    hosts = " ".join(h["id"] for h in plan["hosts"])
    admin = next(h for h in plan["hosts"] if h["role"] == "admin")
    values = [
        ("SIM_NAME", plan["name"]),
        ("SIM_CHAIN", plan["chain"]),
        ("SIM_RUN", plan["run"]),
        ("SIM_PARAMS_FILE", plan["params_abs"]),
        ("SIM_TOPOLOGY", plan["topology_abs"]),
        ("SIM_HOSTS", hosts),
        ("SIM_ADMIN", admin["id"]),
        ("SIM_TBT", plan["tbt"]),
        ("SIM_SETUP", plan["setup_blocks"]),
        ("SIM_EPOCHLEN", plan["epoch_len"]),
        ("SIM_MEASURE_BLOCKS", plan["measure_blocks"]),
        ("SIM_STOP", plan["stop_time"]),
        ("SIM_SEED", plan["seed"]),
        ("SIM_DELTA", plan["sortition_delta"]),
        ("SIM_DUMPFUNCTION", plan["dump_function"]),
        ("SIM_GRANULARITY", plan["time_granularity"]),
    ]
    return "\n".join("{}={}".format(k, shlex.quote(str(v))) for k, v in values) + "\n"


def describe(plan):
    hosts = plan["hosts"]
    counts = {}
    for h in hosts:
        counts[h["role"]] = counts.get(h["role"], 0) + 1
    lines = [
        "[gen_simulation] simulazione: {}".format(plan["name"]),
        "[gen_simulation]   catena         : {}".format(plan["chain"]),
        "[gen_simulation]   parametri      : {} (tbt {}s, epoca {} blocchi, dumping {})".format(
            plan["params_file"], plan["tbt"], plan["epoch_len"], plan["dump_function"]),
        "[gen_simulation]   topologia      : {}".format(plan["topology_file"]),
        "[gen_simulation]   host           : {} totali — {} miner, {} aziende{}, {} CA, {} admin".format(
            len(hosts), counts.get("miner", 0), counts.get("company", 0),
            " generate" if plan["companies_generated"] else "",
            counts.get("ca", 0), counts.get("admin", 0)),
        "[gen_simulation]   setup          : {} blocchi (minimo richiesto {})".format(
            plan["setup_blocks"], plan["min_setup"]),
        "[gen_simulation]   misura         : {} blocchi = {} epoche".format(
            plan["measure_blocks"], plan["measure_epochs"]),
        "[gen_simulation]   stop_time      : {}s — {}".format(
            plan["stop_time"], plan["stop_time_origin"]),
        "[gen_simulation]   granularita'   : {} (runahead {}, dynamic {})".format(
            plan["time_granularity"], plan["granularity"]["runahead"],
            plan["granularity"]["use_dynamic_runahead"]),
    ]
    by_node = {}
    for h in hosts:
        by_node.setdefault(h["network_node_id"], []).append(h["id"])
    lines.append("[gen_simulation]   dislocazione   : " + "; ".join(
        "{}={}".format(k, ",".join(v)) for k, v in sorted(by_node.items())))
    return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("simulation_json", help="config/simulations/<nome>.json")
    ap.add_argument("-o", "--output", help="shadow.yaml da scrivere")
    ap.add_argument("--emit-env", action="store_true",
                    help="stampa la configurazione risolta come assegnamenti shell")
    ap.add_argument("--effective-params", metavar="FILE",
                    help="params.dat gia' creato, da cui rileggere il "
                         "setup-first-blocks effettivo")
    ap.add_argument("--root", default=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                    help="directory shadow/ (default: quella di questo script)")
    ap.add_argument("--bindir", help="directory dei binari multichain")
    args = ap.parse_args()

    root = os.path.abspath(args.root)
    bindir = args.bindir or os.environ.get("BINDIR") or os.path.join(os.path.dirname(root), "src")

    try:
        plan = resolve(args.simulation_json, root, os.path.abspath(bindir),
                       args.effective_params)
    except ConfigError as exc:
        print("ERRORE: {}".format(exc), file=sys.stderr)
        return 2

    if args.emit_env:
        sys.stdout.write(emit_env(plan))
        return 0

    if not args.output:
        print("ERRORE: serve -o <shadow.yaml> (oppure --emit-env).", file=sys.stderr)
        return 2

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w") as fh:
        fh.write(build_yaml(plan))

    print(describe(plan))
    print("[gen_simulation]   scritto        : {}".format(args.output))
    return 0


if __name__ == "__main__":
    sys.exit(main())
