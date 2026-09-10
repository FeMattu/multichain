# Architecture

## What this replaces, and why

The previous suite ran MultiChain under [Shadow](https://shadow.github.io/), a
discrete-event network **simulator**. Shadow intercepts the syscalls of real
binaries and advances a virtual clock, so a run is deterministic and can be
faster or slower than real time. That is a genuine strength, and it produced
the campaign now archived under
[`../analysis/historical/`](../analysis/historical/).

It also imposed three costs that shaped everything about that suite, and none
of them was about the protocol:

1. **The clock had to be paid for.** `Strengthen()` in
   `src/utils/random.cpp` busy-waits until 100 ms of clock have passed. Under
   Shadow `clock_gettime` goes through the vDSO, credited 10 ns by default, so
   a node needed *tens of minutes of wall clock* to boot. The workaround —
   `--unblocked-vdso-latency 20us` — was mandatory, and it charged simulated
   latency to every clock call, which then showed up in the measured block
   time. The archived mean of 17.9 s against a 15 s target contains that
   artefact.
2. **The clock started on 2000-01-01 and could not be moved.** A data
   directory prepared natively carried blocks dated today and the node
   rejected them as *"block timestamp too far in the future"*. So the entire
   bootstrap had to happen inside the simulation, and no step could use an
   interpreter, because a Python process started inside the simulation moved
   the simulated clock of whichever node was meant to be doing something else.
3. **Jitter was never implemented.** Every archived topology carries
   `jitter "0 us"` on every edge — not a modelling choice, a missing feature
   ([shadow/shadow#3601](https://github.com/shadow/shadow/issues/3601)).

The new harness **emulates** instead of simulating: the binaries run
unmodified on a real Linux network built out of namespaces, veth pairs and
`tc`, in real time. All three costs disappear. What replaces them is host
contention — twenty `multichaind` processes really do compete for real CPU —
which is why every run records its own load and every report says to check it
before attributing a block-time gap to the protocol.

### Simulation and emulation, in one line each

**Simulation** models the network and controls time; results are reproducible
but carry the simulator's own costs. **Emulation** builds a real network and
lets time run; results carry the host's costs instead. Neither is more correct
— they answer different questions, and their timestamps are not comparable.
[metrics.md](metrics.md) says how to keep them apart.

## The shape of the thing

```
descriptor (YAML)
      │
      ├── topology (YAML) ──── network profiles (YAML)
      ├── chain parameters (KEY=VALUE, hash-enforced)
      └── nodes: role, location, cluster, heterogeneity
      │
      ▼
  ExperimentPlan ......... resolved once: addresses, ports, peers, schedule,
      │                    setup-first-blocks. Everything downstream reads it
      │                    rather than re-deriving, so the exporter, the
      │                    fabric, the initialiser and the manifest cannot
      │                    disagree.
      ▼
   ┌─────────────────────────────────────────────────────────┐
   │ Fabric        core | netns | docker                      │
   │   builds routers, links, routes and impairment           │
   ├─────────────────────────────────────────────────────────┤
   │ MultiChain    multichain-util create → params.dat        │
   │   then 20 real multichaind, bootstrapped in order        │
   ├─────────────────────────────────────────────────────────┤
   │ Collectors    RPC, /proc, logs — sampled on an interval  │
   └─────────────────────────────────────────────────────────┘
      │
      ▼
  run directory ......... config/ runtime/ logs/ raw/ metrics/ plots/ reports/
      │
      ▼
  metrics extractors → analysis pipeline → reports
```

## Why CORE, and why a second backend exists

The brief asks for CORE, and CORE is the primary backend: it owns the session,
builds the nodes and links, and gives the topology a GUI a reviewer can open.
The harness describes the topology to it over gRPC and then runs MultiChain in
the namespaces CORE created.

`netns` exists for two reasons that are not about preference:

* CORE is not always installed, and a harness that cannot run without it
  cannot be tested, developed or reviewed on an ordinary machine. The
  environment this was built on has no CORE, and every non-privileged part of
  it is exercised there.
* The primitives are the same ones CORE drives — `ip netns`, veth, `tc`. There
  is no fidelity gap to explain; there is a management gap, and CORE manages
  better.

`backend: auto` prefers CORE and falls back to `netns` **with a log line
saying what CORE was missing**. It never falls back silently: a run whose
backend was chosen for it must be able to say so from its own manifest.

### The two planes, and why they are separate

This is the design decision most worth reviewing.

```
EMULATED PLANE                          MANAGEMENT PLANE
routers, /30 links, netem               one flat bridge, no impairment
carries: P2P, node→node RPC             carries: the harness's collectors
11.0.0.0/24 identity on lo              172.30.0.0/24
```

A node's identity is a `/32` on its loopback, so its address does not change
with the path taken. Every topology link becomes a veth pair on its own `/30`,
routers forward with static routes computed from the topology's minimum-delay
paths, and netem sits on egress — the forward impairment on the interface at
the link's source end, the reverse on the target end, which is how an
asymmetric profile stays asymmetric.

The management plane exists because polling perturbs. Twenty nodes sampled
every ten seconds over the impaired paths would add measurable traffic to
exactly the paths being measured. Node-to-node RPC *does* travel the emulated
plane, because that is the experiment; the harness's own observation does not,
because it is not.

### Why native first, and what Docker would take

Running `multichaind` in a container is easy; `docker/` already builds an
image with the toolchain. The obstacle is not the network — a container's
namespace can be handed to CORE or moved into the netns fabric. It is the
shared run directory.

Every role script, every collector and the whole analysis pipeline address one
filesystem layout: `<run>/runtime/data/<node>`, `<run>/logs/<node>`, and the
`runtime/shared/` directory the two-phase permissioned join uses to exchange
wallet addresses. Reproducing that across twenty containers means one of two
things:

* **bind-mount the run root into all of them** — which makes the container
  isolation cosmetic, since every node then writes to the same host tree; or
* **fetch through the Docker API instead** — which makes the two modes produce
  different artefacts, and comparability is the entire point.

Neither is small, and a backend that quietly produced slightly different CSVs
would be worse than none. So: `native` is implemented, `docker` is declared
behind the same interface and fails at *configuration* time with that
explanation rather than at minute forty of a run. Choosing between the two
designs above is an open decision, not an oversight.

## How long a run lasts

```
measure_blocks = measure_epochs × weight-epoch-length
duration       = traffic_start + (setup_first_blocks + measure_blocks) × tbt + 600
```

* `traffic_start` (340 s by default) is the end of the bootstrap timeline.
* the middle term is the blocks that must actually be mined: the native PoA
  phase plus the wPoA measurement window.
* 600 s is the final snapshot plus a closing margin.

At `tbt = 10 s`, epoch 12, setup 64: `340 + (64 + 192)×10 + 600 = 3500 s`.
An explicit `schedule.duration_s` overrides it; the automatic value is still
recorded in the manifest so the difference stays visible.

### The setup constraint

The native PoA phase must last long enough for membership and ESG records to
confirm, for the epoch holding them to be buried behind the weight engine's
stability margin, and for the first weights to be published:

```
setup_min = ceil(traffic_start / tbt) + weight-epoch-length + 6 + 12
```

with an absolute floor of 60 blocks. Below it, wPoA takes over on an empty
weight map and the chain stops with `cannot score (unsynced or unweighted)` —
a failure that appears minutes later and says nothing about its cause. An
explicit value below the minimum is refused at configuration time.

`multichain-util` may raise `setup-first-blocks` further at genesis. The
effective value is re-read from the written `params.dat`, and it — not the
configured one — decides the measurement window.

## The bootstrap order

Not arbitrary. Each step is a precondition for the next, and each boundary has
a health check that names the missing precondition rather than letting the
chain stall later.

| t | who | what |
|---|---|---|
| 0 | admin | `multichaind` → genesis, premine, input streams |
| 30 s | everyone else | first launch: publish the wallet address, exit |
| 60 s | admin | grants, `wpoa-weights` (closed), the application stream, `high1` to the CAs, GAS distribution |
| 150 s | everyone else | `multichaind` proper: join and sync |
| 260 s | CAs, miners, companies | certified ESG scores; cluster membership |
| 340 s | companies, miners, admin | traffic, reconciliation, GAS refill, epoch sampling |
| height = setup | all | **wPoA takes over from native PoA** — the window opens |
| stop − 120 s | admin | final chain snapshot |

Two steps in that list are easy to omit and fatal to omit:

* **`wpoa-weights` must be created explicitly, CLOSED.** With the weight
  engine on, the registry does not create the stream until it has a weight to
  publish, and it has no weight until membership and ESG records exist. Nobody
  creates it, nobody publishes, and the chain stops at `setup-first-blocks`.
* **The admin must `subscribe` explicitly.** It is not a cluster head, so it
  publishes no weight and the registry never subscribes it — and the final
  snapshot and `weightverifyweights` then fail with *"Not subscribed to this
  stream"*.

## Failure and cleanup

One cleanup path, reached from every exit: Ctrl+C, a dead daemon, a fabric
failure, a missing file and a normal finish all leave through `Session.__exit__`.

```
stop the role scripts        (first, so no generator is still publishing)
stop the daemons over RPC    (so their databases flush)
  → SIGTERM → SIGKILL        (only if RPC did not answer)
clear the impairment
destroy the fabric
write the manifest
```

Stopping over RPC first is worth the twenty seconds: a data directory killed
mid-write comes back as `Corrupted block database detected`, and the run's own
artefacts become unreadable — losing exactly the data the run existed to
produce.

**Cleanup never deletes results.** A run that failed at minute forty still
holds forty minutes of debug logs, and those are usually why it failed.

Cleanup also works from a different process, given only the session prefix,
which is what lets `clean_experiment.sh` recover from a hard kill:
namespaces are discovered from the live system rather than remembered, and
stray veth ends left in the root namespace get their qdiscs stripped — a
leftover netem qdisc would silently impair the next run.

## Deviations from the brief's suggested layout

Two, both deliberate:

* `runtime/fabric/` rather than `runtime/core/`. CORE installs a top-level
  Python package named `core`; a sibling module of the same name inside this
  package shadows it under some import orders and produces a confusing
  `ImportError` deep inside the gRPC client. The CORE backend is
  `runtime/fabric/core_emulator.py` for the same reason.
* `experiments/docs/` rather than a top-level `docs/`, matching the tree the
  brief itself draws.
