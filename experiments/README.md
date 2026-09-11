# POESIA / wPoA — real network emulation

Runs the **real** MultiChain binaries of this fork on an emulated network and
produces the same analytical artefacts the previous Shadow suite produced.

Nothing here simulates the protocol. Every block, every stream record and
every RPC answer comes from an actual `multichaind` process; the network
underneath it is built from Linux namespaces, veth pairs and `tc`, either
through [CORE](https://github.com/coreemu/core) or directly.

This replaces `shadow/`. What moved, what was archived and what changed is in
[docs/migration-from-shadow.md](docs/migration-from-shadow.md); the archived
campaign itself is in [analysis/historical/](analysis/historical/), labelled
as Shadow results throughout.

---

## Five minutes

```bash
# 1. can this machine do it?
experiments/scripts/check_environment.sh

# 2. is the configuration sound? (no privileges needed)
python3 -m experiments.cli validate \
    --experiment experiments/configs/experiments/regional.yaml

# 3. what would a run actually do? (still nothing touched)
python3 -m experiments.cli experiment dry-run \
    --experiment experiments/configs/experiments/regional.yaml --seed 12345

# 4. the smallest real thing: three nodes, ~7 minutes
sudo -E experiments/scripts/run_experiment.sh \
    --experiment experiments/configs/experiments/smoke-3n.yaml
```

Step 4 needs root (or passwordless sudo) and the MultiChain binaries. Steps
1–3 need neither.

## Twenty nodes

```bash
sudo -E experiments/scripts/run_experiment.sh \
    --experiment experiments/configs/experiments/intercontinental.yaml \
    --seed 12345
```

7 miners, 10 companies, 3 administrative nodes (1 governance + 2 Certification
Authorities), on 20 locations across five continents. About 58 minutes at the
default schedule: 340 s of bootstrap, 64 blocks of native PoA setup, then 192
blocks measured under wPoA at a 10 s target.

The script validates, checks the environment, clears any leftover fabric,
runs, analyses and writes the reports. `--dry-run` stops after showing the
plan; `--no-analysis` stops after the run.

Swap the geography by swapping one line — the four level descriptors differ in
**geography and nothing else**:

```bash
diff experiments/configs/experiments/regional.yaml \
     experiments/configs/experiments/intercontinental.yaml
```

## Without root

`sudo` is the normal way, but not the only one:

```bash
experiments/scripts/run_unprivileged.sh \
    --experiment experiments/configs/experiments/e2e-5n.yaml
```

`unshare -Urnm` gives the harness a user namespace in which it is uid 0, with
real `CAP_NET_ADMIN` over its own network namespace — `ip netns`, veth and
`tc`/netem all work, and every file is created as you. It is how the
verification run in this tree was produced. It cannot reach a CORE daemon
(that runs as root, outside), so the backend is always `netns`.

## What comes out

```
experiments/results/run-<name>-<UTC>/
├── manifest.json          what ran, on what, with which commit and binary
├── config/                the exact inputs, copied in — the run is replayable alone
├── runtime/               topology-realized.json, netem-events.jsonl, node data
├── logs/<node>/           daemon stdout, each role script, the archived debug.log
├── raw/                   the admin's chain snapshot + the sampler's time series
├── metrics/               the catalogued tables
├── analysis/              the three-phase pipeline's phase1/2/3
├── plots/
└── reports/               report_generale.md and the four others
```

## The pipeline

Each stage is a command, and each is runnable on its own.

| stage | command |
|---|---|
| check the machine | `cli env check --experiment <descriptor>` |
| check CORE specifically | `cli env check` reports it; the run refuses to fall back without consent |
| validate | `cli validate --experiment <descriptor>` |
| generate a topology | `cli topology generate --topology <file> --format gml` |
| start the network | `cli network start --experiment <descriptor>` |
| initialise the chain | `cli multichain initialize --run-id <id>` |
| change conditions | `cli network apply-profile --run-id <id> --profile <file>` |
| run | `cli experiment run --experiment <descriptor> --duration 3600 --seed 12345` |
| collect | `cli metrics collect --run-id <id>` |
| analyse | `cli analysis run --run-id <id>` |
| report | `cli report generate --run-id <id>` |
| stop | `cli network stop --run-id <id>` |

`cli` is `python3 -m experiments.cli`, run from the repository root. Each has
a script in [scripts/](scripts/) that wraps it with argument checking and
cleanup traps.

### Exit codes

They are part of the interface: a caller can branch on them.

```
0  success                  3  runtime error       (the network or a node failed)
1  configuration error      4  incomplete data     (too little to analyse)
2  environment unavailable  5  analysis failed
```

## Layout

```
experiments/
├── configs/          schema/ experiments/ topologies/ network-profiles/ chain-params/
├── topology/         the model, generator, validator and exporters
├── runtime/          fabric/ netem/ multichain/ collectors/ roles/ session.py
├── metrics/          the catalogue, extractors, validators, schema report
├── analysis/         pipeline/ legacy/ compatibility/ reporting.py historical/
├── scripts/          twelve operator scripts
├── tests/            unit/ integration/ golden/ fixtures/
├── docs/             the seven documents below
└── results/          run directories (not versioned)
```

Configuration is split into independent axes, referenced by path, so that
changing one is changing one line and two descriptors differ by that line
alone:

```
configs/
├── experiments/*.yaml       what to run: nodes, roles, schedule, seed
├── topologies/*.yaml        the map: locations and links
├── network-profiles/*.yaml  what a link does to a packet
└── chain-params/*.dat       hash-enforced chain values (protocol 20014)
```

## How a run is driven

Every node runs a **controller** for the whole experiment — not a script that
fires once and exits:

```
setup()    admin grants and funds; a miner registers as cluster head; a
           company joins its cluster; the CA publishes the ESG scores
loop(tick) the company generates its workload, the miner reconciles each
           epoch, the admin refills GAS and samples each buried epoch
teardown() the admin takes the final chain snapshot
```

They are supervised: a controller that dies is restarted, and the restart is
recorded in `runtime/role-controllers.json` and in the `process_restarts`
metric. Each writes `logs/<node>/role_controller.log` with a heartbeat, so a
node that stopped working is visible rather than inferred.

Meanwhile the harness polls the admin like a **block explorer**, every two
seconds by default: it walks every intermediate height rather than reading the
tip, keeps every raw answer under `raw/rpc/`, and separately polls all nodes
for the quantities that are relations *between* nodes — fork detection, sync
lag, propagation. `docs/metrics.md` says which is which.

## CORE, and the absence of a silent fallback

`fabric.backend: auto` prefers CORE. When CORE is missing it does **not**
switch to the netns fabric on its own: it asks, and the prompt lists what that
costs. Non-interactively it refuses with exit code 2 unless you pass
`--allow-fallback-without-core`.

The reason is not purity. A run that changed backend by itself would look, be
labelled and be compared exactly like a CORE run, and the only record would be
one line of log nobody reads.

## Nodes and roles

Default composition, declared in `configs/node-roles.yaml` and never hardcoded:

| role | count | what it does |
|---|---:|---|
| `miner` | 7 | wPoA validator and cluster head; the only nodes that mine |
| `company` | 10 | publishes supply-chain items — pays fees, drives `tau_i` |
| `admin` | 1 | genesis, permissions, streams, GAS treasury |
| `ca` | 2 | Certification Authority: holds `high1`, the only writer of ESG scores |

`admin` and `ca` together are the three administrative nodes. They are
separate roles because they are separate **on chain**: being an administrator
does not grant the right to certify an ESG score, and an ESG score is an
attestation nobody can verify cryptographically — restricting who may assert
it is the only defence there is.

Miners and companies are deliberately **heterogeneous** — different
reconciliation rates, different publication intervals. Without that the three
`W_k` would be structurally identical and weighted selection would be
indistinguishable from a uniform draw, which is the one outcome that proves
nothing.

## Requirements

**Mandatory:** Linux with network namespaces, `iproute2` (`ip`, `tc`), Python
3.8+, `PyYAML`, `jsonschema`, the MultiChain binaries, and root or
passwordless sudo for a real run.

**For the analysis:** `numpy`, `scipy`, `pandas`, `matplotlib`, `networkx`,
`openpyxl`.

**Optional:** CORE (the primary fabric backend; `netns` is used without it),
`curl` inside the node namespaces (the role scripts need it), Docker.

Ubuntu 20.04 is supported — see
[docs/troubleshooting.md](docs/troubleshooting.md) for the `apt` line.

## Tests

```bash
python3 -m pytest experiments/tests -q
```

187 pass without privileges or binaries. 12 skip, each saying why. The ones
that need root or MultiChain are **not mocked**:
`tests/integration/test_smoke_real.py` is the only test that may claim an
end-to-end result, and it refuses to run without both.

The golden tests are where the migration is pinned: the migrated topologies
must regenerate every historical `.gml` byte for byte, the CSV column contract
must not shift, and the migrated pipeline must still reproduce the archived
campaign exactly.

## Documentation

| | |
|---|---|
| [docs/architecture.md](docs/architecture.md) | why CORE, why two planes, the bootstrap order, cleanup |
| [docs/migration-from-shadow.md](docs/migration-from-shadow.md) | what moved, what was archived, what changed |
| [docs/topology-model.md](docs/topology-model.md) | locations, links, the shipped maps |
| [docs/network-model.md](docs/network-model.md) | the delay model, profiles, how `tc` is driven |
| [docs/metrics.md](docs/metrics.md) | observed vs derived vs unavailable; **three clocks** |
| [docs/reproducibility.md](docs/reproducibility.md) | seeds, the manifest, what is *not* controlled |
| [docs/troubleshooting.md](docs/troubleshooting.md) | symptoms and fixes |

Component READMEs: [topology/](topology/README.md), [analysis/](analysis/README.md),
[results/](results/README.md).

## One thing to read before comparing anything

The archived campaign measured **simulated** time. This one measures the wall
clock. Proposer shares, chi-square, Gini, weight trajectories and the
timer-race margin are comparable across the two; timestamps and block-time
means are not, and they carry different biases.
[docs/metrics.md](docs/metrics.md), "Three clocks", says exactly which is
which.
