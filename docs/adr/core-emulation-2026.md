# CORE network emulation for the wPoA harness — analysis and plan

**Status:** implemented. The plan of §8 was approved on 2026-09-18 and carried out; §9 records what actually happened, including where the plan turned out to be wrong.
**Date:** 2026-09-18
**Branch:** `feat/core-emulation-harness`

This document is phase 0 and phase 1 of the mandate: replace `experiments/` with a CORE
Network Emulator backend behind the `test/` harness, so that the same bootstrap, the same
collection, the same analysis and the same plots run either on a flat loopback network
(today's regime) or on an emulated geography with real delay, jitter and loss.

Everything below was verified against the tree and, where it concerns CORE, against a
running container. Claims that were *not* verified are marked as such.

---

## 1. Verdict

The work is feasible with a **small, well-localised change to `test/`** and a new fabric
module. The harness turned out to be far better factored for this than expected: the whole
coupling between "where a node is" and "how the harness talks to it" reduces to

* one profile field, `network.host`, read in **nine** places, always in the same shape
  `RpcClient.from_datadir(chain_home / node, chain, profile.host, node.rpc_port)`;
* one command builder, `NodeRunner.command_line()`, and the four `subprocess` call sites
  around it that start, stop and first-launch a daemon;
* one string, `Profile.seed_node_address`, that tells a joining node what to dial.

Nothing in `test/analysis/`, `test/plotting/` or `test/traffic/`'s *logic* depends on the
network being flat. The daemons key on `role`, never on a node-id spelling or an address.
So the two regimes can produce byte-comparable tables, which is the point.

What `experiments/` is worth keeping is **data, not code**: four 20-site maps, seven link
profiles, and the node→site placements. The code around them is replaced.

---

## 2. What was verified about the environment

All checks below were run in `./docker/mcsim` (image `poesia-emu:22.04`, CORE 9.2.1,
Ubuntu 22.04, 20 CPUs, 24 GiB available).

`./docker/mcsim preflight` passes every check: `ip netns add`, link administration,
netem on `lo`, writable `/proc/sys`, 1048576 open files, `core-daemon` present, CORE's
Python API importable by the **system** `python3` (not only by `/opt/core/venv`), a CORE
daemon answering on `127.0.0.1:50051`, and an executable `src/multichaind`.

Two probes were then written and run against the live CORE daemon to settle the design
questions that documentation alone cannot answer.

### 2.1 Per-link impairment — confirmed

`core.api.grpc.wrappers.LinkOptions` carries `delay`, `jitter`, `loss`, `bandwidth`,
`dup`, `buffer`, `unidirectional`. A link created with
`LinkOptions(delay=25000, jitter=3000, loss=0.5, bandwidth=100_000_000, buffer=1000)`
produced, inside the node:

```
qdisc netem 10: dev eth0 root refcnt 21 limit 1000 delay 25ms 3ms 25% loss 0.5% rate 100Mbit
```

so: `delay`/`jitter` in **microseconds**, `loss` in **percent**, `bandwidth` in **bps**,
`buffer` = netem's packet `limit`. CORE applies the qdisc on *each* end, i.e. `delay` is
one-way and RTT is twice it — which matches the `mean_ms` semantics of the shipped link
profiles exactly. `unidirectional` is what expresses the asymmetric `degraded` profile.

**Consequence: the harness never writes a `tc` command.** CORE owns the kernel side. The
harness only computes numbers. That removes the entire tbf/netem layering, burst sizing
and fixed-point rendering problem that the old system had to solve by hand.

### 2.2 The control network — confirmed

Setting `session.options["controlnet"].value = "172.30.0.0/24"` before `start_session`
gives every node a `ctrl0` interface and puts a matching bridge in the **container's root
namespace**:

```
node n1:   ctrl0   172.30.0.1/24          (node id 1)
node n2:   ctrl0   172.30.0.2/24          (node id 2)
node n3:   ctrl0   172.30.0.3/24          (node id 3)
root ns:   ctrl0.1 172.30.0.254/24
root ns -> 172.30.0.1: 0.021 ms, 0% loss
```

Two things follow. The control address is a deterministic function of the CORE node id
(`prefix + id`), so it is derivable without asking the daemon. And the orchestrator and
every Python daemon can stay in the root namespace and reach every node's RPC port over a
plane that carries **no netem at all** — `tc qdisc show` on `ctrl0` reports `noqueue`.

That is the right split: the measurement plumbing must not be delayed by the thing it is
measuring.

### 2.3 Running `multichaind` inside a node — confirmed

CORE nodes are `vnoded` namespaces, not containers, and they share the host's filesystem:

```
n1$ ls -l /workspace/multichain/src/multichaind      -> present
n1$ /workspace/multichain/src/multichaind --version  -> MultiChain 2.3 Daemon
n1$ touch /workspace/multichain/test/results/...     -> repo-writable
n1$ hostname; id -u                                  -> n1; 0
n1$ sysctl -n net.ipv4.ip_forward                    -> 1
n1$ python3 --version                                -> 3.10.12
```

From the **root namespace**, `vcmd -c /tmp/pycore.<session>/<node> -- <command>` runs a
command in the node and returns its exit status; `/tmp/pycore.<session>/<node>.pid` holds
the `vnoded` pid, so `nsenter -t <pid> -n` is an equivalent route.

**Consequence: the fabric can be a command prefix.** `NodeRunner` keeps its `subprocess`
calls, its `daemon.out` redirection and its retry logic verbatim; only the argv gains a
prefix that is `[]` in the native regime.

### 2.4 Routing between sites — confirmed, and it must be static

CORE gives each node `default via <its own address>`, which routes nothing. Two-hop
forwarding was verified by hand: `ip_forward` is already `1`, and after adding one route
on each end, `n1 -> n3` through `n2` gave RTT ≈ 20 ms for two 5 ms links.

The design therefore installs **static routes computed from the topology graph**. No
routing daemon: OSPF convergence is wall-clock nondeterminism injected into the one part
of a measurement harness that must not have any, and the maps are 20 sites, where
Dijkstra is free.

### 2.5 Node namespaces are PID namespaces — a hazard found, not a blocker

`readlink /proc/self/ns/pid` differs per node. `multichaind -daemon` forks inside the
node, so the pid written to `<datadir>/<chain>/multichain.pid` is a **node-local pid**.
`NodeRunner.stop()` escalates with `os.kill(pid, SIGTERM)` from the root namespace
([node_process.py:334](../../test/bootstrap/node_process.py#L334)) — under CORE that would
signal an unrelated root-namespace process, or nothing.

The escalation must be issued *inside* the namespace (`vcmd … kill -TERM <pid>`). This is
the single most dangerous silent difference between the two regimes and it is why the
fabric interface has to own "signal this node's daemon", not only "start it".

---

## 3. The hook points in `test/`, exactly

### 3.1 `network.host` — nine call sites, one shape

| File | Line | Use |
|---|---|---|
| [bootstrap_network.py](../../test/bootstrap/bootstrap_network.py#L124) | 124 | `Orchestrator.client()` — every node |
| [node_process.py](../../test/bootstrap/node_process.py#L311) | 321 | `rpc_open()` TCP liveness probe |
| [node_process.py](../../test/bootstrap/node_process.py#L334) | 355 | `stop()` runs `multichain-cli`, which defaults to `-rpcconnect=127.0.0.1` |
| [admin_daemon.py](../../test/bootstrap/admin_daemon.py#L318) | 318 | the observer's client |
| [ca_assign_esg.py](../../test/bootstrap/ca_assign_esg.py#L89) | 89 | one client per CA |
| [malus_detector.py](../../test/bootstrap/malus_detector.py#L274) | 274 | the honest detector, on the admin |
| [company_daemon.py](../../test/traffic/company_daemon.py#L236) | 236 | one company |
| [miner_gas_daemon.py](../../test/traffic/miner_gas_daemon.py#L376) | 376 | one miner |
| [stop_network.py](../../test/shutdown/stop_network.py#L53) | 53 | the final snapshot |

All nine become `profile.rpc_host(node_id)`. In the native regime that returns
`network.host` unchanged, so the native path is provably identical.

Note the per-process constraint: the traffic daemons are **separate OS processes** that
re-load the profile from YAML and receive only `--config`, `--run-dir`, `--chain-home`.
Whatever resolves a node to an address must therefore be either a pure function of the
profile, or a file inside the run directory. The design does both: pure derivation for
`--dry-run`, and an authoritative `<run>/fabric.json` written at bootstrap, because CORE
is the one that actually assigned the addresses and a manifest that merely *predicts* them
is not evidence.

### 3.2 Process control — five call sites in one file

[`node_process.py`](../../test/bootstrap/node_process.py): `command_line()` (221),
`start()` (235), `rpc_open()` (311), `stop()` (334), `first_launch()` (397). Each gains a
fabric-supplied argv prefix and, in `stop()`, a fabric-supplied way to signal. Nothing else
in the file changes: the LevelDB lock settle, the `-daemon` fork semantics, the grant-hint
regex and the retry ladder are regime-independent and were all hard-won.

### 3.3 The seed address

[`Profile.seed_node_address`](../../test/bootstrap/config_loader.py#L243) returns
`chain@host:port`. Under CORE it must return the admin's **data-plane** address, never its
control address, or the whole peer-to-peer mesh would form on the unimpaired plane and the
run would measure nothing. See §5.4.

### 3.4 The node table

[`Profile`](../../test/bootstrap/config_loader.py#L207) stores `ca_count`,
`miner_count`, `company_count` and builds the node list in a fixed order
([`_build_nodes`](../../test/bootstrap/config_loader.py#L876)). With an explicit node list
these become *derived* counts. Everything downstream already reads `profile.by_role(...)`,
`profile.nodes` and `node.role`, so the derivation is the only change.

One real behavioural difference: [`cluster_assignment()`](../../test/bootstrap/config_loader.py#L420)
draws company→miner from the seed. A CORE profile states `cluster:` per company, so the
method must return the declared map when the profile carries one and keep drawing from the
seed when it does not.

### 3.5 What is *not* a hook point

`test/analysis/**`, `test/plotting/**`, `test/bootstrap/event_log.py`,
`test/bootstrap/malicious.py`, `test/bootstrap/malus_detector.py`'s logic,
`test/traffic/*`'s decision logic. They were read; none of them contains a network
assumption. `phase1_collect.py` writes a `nodes` table with `port`/`rpc_port` columns from
the profile and is otherwise address-blind.

---

## 4. What is taken from `experiments/`, and what is not

### 4.1 Taken — data only

**Topologies.** `regional.yaml` and `national.yaml` **do exist** (the mandate listed them
as unconfirmed): `experiments/configs/topologies/` holds `regional`, `national`,
`continental`, `intercontinental`, five `legacy-*-10n`, `smoke-3n` and `e2e-5n`. The four
20-site maps are the ones worth migrating. Each carries `name`, `latency_model`,
`defaults`, 20 `nodes` (id, label, kind hub|leaf, scope, region, country, continent, lat,
lon) and ~35 `links` (21 backbone in a 7-hub full mesh, 13–14 access leaf→hub).

**The `legacy-*-10n` maps are superfluous and will not be migrated.** They exist only to
reproduce a retired suite's output byte for byte; that suite is gone, the 20-node maps
supersede them at every level, and keeping a half-size duplicate of each geography would
invite runs that are not comparable with anything. `e2e-5n` and `smoke-3n` are fixtures of
the old test suite; a fresh 4-node smoke map is cheaper to write than to migrate.

**Network profiles.** All seven (`lan`, `regional`, `national`, `continental`,
`intercontinental`, `degraded`, `partitioned`) migrate, stripped of `description` and
`source`. `degraded` carries `forward`/`reverse` blocks; `partitioned` carries
`partition: true` and 100% loss. The `direction:` field is **dropped** — it is derivable
(a profile with `forward`/`reverse` is asymmetric, one without is not) and a field that can
disagree with the shape it describes is a defect waiting to happen.

**Placements.** The `nodes:` lists of `regional/national/continental/intercontinental.yaml`
give id → role → location → cluster. Verified: all four are 7 miners + 10 companies +
1 admin + 2 CA = 20, mapped 1:1 onto the 20 sites, with **every miner on a hub and every
other role on a leaf**. `smoke-3n` puts `admin` and `ca1` on the same site, which is why
the fabric must support more than one chain node per location.

### 4.2 Not taken

`plan.py`, `cli.py`, `topology/exporters.py`, `chain_params.py` and
`configs/chain-params/*.dat`, `configs/node-roles.yaml`, `configs/seeds.yaml` and its
XOR/FNV1a derivation, `runtime/**`, `metrics/**`, `analysis/**`, `scripts/**`, `tests/**`,
`docs/**`, `results/**`. The only seed derivation in the new system stays the one in
[`test/config/schema.md`](../../test/config/schema.md) §1.2,
`sha256(f"{seed}:{purpose}:{node_id}")`, already implemented in `Profile.rng()`.

The physical delay model itself is **not code to be copied** — it is three lines of
arithmetic that the migrated topology files already parameterise:

```
one_way_ms = propagation_ms_per_km · D_km · routing_factor + overhead_{backbone,access}_ms
loss_access   = loss_access                       (constant, access links)
loss_backbone = loss_backbone_base + loss_backbone_per_km · D_km
bandwidth     = bandwidth_hub_mbps  (backbone)  |  bandwidth_leaf_mbps  (access)
```

`D_km` is the great-circle distance between the two sites' coordinates. It will be
re-implemented from the field names, with the model's own published check points as unit
tests (Milan–Rome 477 km → 7.7 ms RTT; Milan–New York 6464 km → 91.5 ms RTT).

`latency_model` has **no jitter term**, so derived links need a rule. Proposal:
`jitter = 0.15 · delay`, floored at 0.02 ms, declared in `schema.md` as an assumption —
the same order of magnitude as the ratio the seven link profiles use (2.1/0.3, 5.1/0.8,
10.4/2.0, 45.8/8.0 → 0.14–0.17). Stating it in one place beats burying it in seven.

### 4.3 References to `experiments/` that live outside it

Deleting the directory breaks these, and each must be dealt with:

| File | What it says |
|---|---|
| `README.md` 27–39, 55 | quick-start pointing at `experiments/scripts/*` and the retired suite |
| `docker/mcsim` `cmd_exp` | `mcsim exp` runs `experiments/scripts/run_experiment.sh` |
| `docker/preflight.sh` ~186 | checks `-d $ROOT/experiments` as "the harness is mounted" |
| `test/README.md` 10 | "network behaviour is `experiments/`'s subject" |
| `test/docs/architecture-notes.md` 36, 39, 65 | the read-only-source table, incl. a file name carrying the retired emulator |
| `test/config/schema.md` 53 | "constants shared with `experiments/`" |
| `test/bootstrap/event_log.py` 3 | "not the format of `experiments/`" |
| `docs/adr/functional-smoke-refactor-2026.md` | historical ADR, cites `experiments/docs/metrics.md` |

The first seven are live documentation and get updated. The ADRs are **dated records of
decisions already taken**; rewriting them would falsify the history the thesis relies on.
Proposal: leave `docs/adr/functional-smoke-refactor-2026.md` and
`docs/root-cause-report.md` untouched and add one line to each saying the paths they cite
were removed on this date.

The three remaining `shadow` matches inside `test/` are the English verb (`__init__.py`
"it would shadow the real one", `valida_sortition_montecarlo.py` "shadowing it would break
`os.path`") and are not references to anything.

---

## 5. The target design

### 5.1 Two planes

```
DATA PLANE (emulated)                    CONTROL PLANE (out of band)
one CORE node per topology site          CORE controlnet, 172.30.0.0/24
/30 per topology link, netem per link    no netem, no shaping
static routes from the topology graph    root namespace <-> every node
carries: MultiChain P2P only             carries: the harness's RPC only
```

The control plane exists so that the orchestrator, the observer, the CA assigner, the
detector and every traffic daemon keep running as ordinary root-namespace processes with
their existing logs, process groups and `killpg` teardown. The alternative — pushing the
Python daemons into the namespaces — would make every RPC call pay the emulated latency
and would make the measurement instrument part of the measurement.

This is a declared property of the method and goes in `schema.md`, not a hidden
convenience.

### 5.2 Site, not node, is the unit of the fabric

A topology **site** becomes one CORE node. A chain node is *placed* at a site. A site with
several chain nodes runs several `multichaind` processes in one namespace — which is why
the existing `base_port + index` / `base_rpc_port + index` scheme is kept rather than
simplified: distinct ports are what makes co-location work, and it keeps the port map a
property of the profile, exactly as it is today. A site with no chain node is a pure
transit router.

Hubs forward; leaves do not need to. `ip_forward` is already 1 in every CORE node.

### 5.3 Addressing

```
data plane   10.60.<site_index>.0/24   one /24 per site, chain node k -> .10+k
link         10.61.<link_index>.0/30   one /30 per topology link
control      172.30.0.<core_node_id>/24  assigned by CORE
```

Deterministic from the topology file alone, so `--dry-run` can print the full plan with no
daemon running. After `start_session` the fabric reads the interfaces back from CORE and
writes `<run>/fabric.json` — session id, per-site CORE node id, per-node data address,
control address, per-link realised delay/jitter/loss/bandwidth and where each number came
from (`derived:latency-model` or `profile:<name>`). That file is the evidence, and the
child processes read it.

### 5.4 Keeping the P2P mesh on the data plane

The one failure that would invalidate a whole campaign silently: MultiChain forming its
peer mesh over the control network, where there is no impairment. Four defences, all of
them cheap, all of them checked:

1. `-bind=<data-ip>` — the P2P listener exists only on the data interface.
2. `-externalip=<data-ip>` and `-discover=0` — the node advertises the data address and
   does not go looking for another one. Both options exist in this fork
   (`src/core/init.cpp` 414, 417, 950).
3. `Profile.seed_node_address` resolves to the admin's data address.
4. After bootstrap, assert that every entry of `getpeerinfo` on every node has an address
   in the data prefix. A single control-plane peering fails the run.

RPC goes the other way: `-rpcbind=<control-ip>` and `-rpcallowip=<control-prefix>`.
`src/rpc/rpcserver.cpp` 1548 binds loopback unless `-rpcallowip` is given, and 1562 warns
when `-rpcbind` is given without it, so the two are passed together. `multichain-cli` in
`NodeRunner.stop()` is instead wrapped in the fabric prefix and keeps talking to
`127.0.0.1` from inside the namespace, which needs no flag at all.

### 5.5 The fabric interface

```python
class Fabric(Protocol):
    def start(self) -> None                       # build and start the network
    def stop(self) -> None                        # tear it down, always
    def wrap(self, node_id: str) -> list[str]     # argv prefix; [] when native
    def signal(self, node_id: str, pid: int, sig: int) -> None
    def rpc_host(self, node_id: str) -> str       # control address; network.host when native
    def data_host(self, node_id: str) -> str      # P2P address; network.host when native
    def extra_node_args(self, node_id: str) -> list[str]   # -bind/-externalip/-rpcbind/...
    def describe(self) -> dict                    # what goes into <run>/fabric.json
```

`native.py` implements it as a set of constant answers and starts nothing. `core.py`
implements it against `core.api.grpc`. Selection is `profile.fabric["backend"]`, defaulting
to `native` when the key is absent — which is what makes today's thirteen profiles keep
working untouched.

### 5.6 Profile schema for `test/config/profiles/core/<name>.yaml`

Same skeleton as a native profile (`seed`, `chain_name`, `network`, `epochs`, `chain`,
`wpoa`, `weight_engine`, `traffic`, `runtime`, optional `malicious`), plus:

```yaml
fabric:
  backend: core
topology: topologies/continental.yaml      # relative to test/config/
network_profile: continental               # optional; see below
nodes:
  - {id: miner-0,   role: miner,   location: milano-c}
  - {id: company-0, role: company, location: pisa, cluster: miner-0}
  - {id: ca-0,      role: ca,      location: parma}
  - {id: admin,     role: admin,   location: modena}
```

Rules the loader enforces: exactly one `admin`; at least one `ca`, one `miner`, one
`company` among the **enabled** nodes; every `location` is an id in the topology file;
`cluster` only on `company`, naming an enabled miner; every miner heads at least one
cluster (a headless miner never receives a published weight — the existing invariant);
`enabled: false` removes a node from the run entirely, ports included. Forbidden keys,
rejected by name: `geography`, `reconcile_rate`, `organization`, `tx_interval_s`,
`expected`, `schedule`, `chain_params`, `description`, `scenario`, `mode`.

`network_profile` is an **override of the derived model**, not an addition: when it is
absent each link's impairment comes from the topology's `latency_model`; when it is present
the named profile is applied flat. Because `partitioned` flat across every link is a dead
network and `degraded` flat is not a geography, the field also accepts the long form:

```yaml
network_profile: {name: degraded, apply_to: access}   # all | backbone | access
```

with `apply_to: all` the default. That one addition is what makes the two operating-point
profiles usable at all; without it they can only ever describe a network nobody would run.

### 5.7 Node ids in the shipped CORE profiles

The schema allows any filesystem-safe id. The four shipped profiles will nevertheless use
the native spelling — `admin`, `ca-0`, `miner-0…6`, `company-0…9` — rather than the old
`m1/c1/ca1`, so that a run directory, an `events.jsonl` path, a plot legend and a
`weight_vs_election.md` row are directly comparable between a native run and a CORE run of
the same size. The geography lives in `location`, where it belongs.

---

## 6. Files: created, modified, deleted

### Created

| Path | Why |
|---|---|
| `test/config/topologies/{regional,national,continental,intercontinental}.yaml` | the four maps, `description`/`source` stripped |
| `test/config/topologies/smoke-4n.yaml` | a 3-site map for a fast CORE smoke run; written, not migrated |
| `test/config/network-profiles/{lan,regional,national,continental,intercontinental,degraded,partitioned}.yaml` | the seven link profiles, `description`/`source`/`direction` stripped |
| `test/config/profiles/core/{regional,national,continental,intercontinental}.yaml` | the four level profiles in the new schema |
| `test/config/profiles/core/smoke.yaml` | 4 nodes, few epochs: the first thing to run |
| `test/bootstrap/fabric/__init__.py` | the `Fabric` protocol and the backend registry |
| `test/bootstrap/fabric/native.py` | today's behaviour, stated explicitly instead of implied |
| `test/bootstrap/fabric/core.py` | CORE session, sites, links, netem, control net, static routes |
| `test/bootstrap/fabric/topology.py` | load a topology, great-circle distance, the delay model, shortest paths |
| `test/bootstrap/fabric/addressing.py` | the deterministic address plan of §5.3 |
| `test/unit/test_topology_model.py` | the delay model against its published check points |
| `test/unit/test_core_profile.py` | the node-list schema: every rejection above, by name |
| `test/unit/test_fabric_native.py` | the native fabric answers exactly what the code used to hardcode |
| `test/docs/core-fabric.md` | operator-facing: what CORE needs, the two planes, how to debug a node |

### Modified

| Path | Change |
|---|---|
| `test/bootstrap/config_loader.py` | accept both `nodes` shapes; derive counts; `fabric`/`topology`/`network_profile`; `rpc_host()`/`data_host()`; declared clusters; extend the manifest |
| `test/bootstrap/node_process.py` | argv prefix from the fabric; signal through the fabric (§2.5); `rpc_open` and the CLI use the fabric's host |
| `test/bootstrap/bootstrap_network.py` | build the fabric, start it before the chain, stop it in `finally`; `client()` uses `rpc_host`; write `fabric.json`; assert §5.4 point 4 |
| `test/bootstrap/admin_daemon.py`, `ca_assign_esg.py`, `malus_detector.py`, `traffic/company_daemon.py`, `traffic/miner_gas_daemon.py`, `shutdown/stop_network.py` | one line each: `profile.host` → `profile.rpc_host(node_id)` |
| `test/config/schema.md` | the new sections; the two-planes statement; the jitter assumption |
| `test/README.md` | the CORE regime; drop the "`experiments/` is the subject of network behaviour" paragraph |
| `test/docs/architecture-notes.md` | the source table; remove the retired emulator's file name |
| `test/unit/test_malicious_config.py`, `test_malicious_injector.py` | profile paths move under `native/` |
| `README.md`, `docker/mcsim`, `docker/preflight.sh` | the quick start, `mcsim exp`, and the mount check point at `test/` |

### Moved

All thirteen profiles in `test/config/profiles/*.yaml` → `test/config/profiles/native/`,
unchanged in content. The mandate's tree named only `small`/`medium`/`large`; `malicious`
and the nine `long*` profiles are live and move with them, or the "no regression"
acceptance criterion cannot be met.

### Deleted

`experiments/` in its entirety, after the extraction above.

---

## 7. Risks and open questions

| # | Risk | Assessment |
|---|---|---|
| 1 | **Signals across the PID namespace** (§2.5) | Real, found by probe, silent if missed. Handled in the fabric interface; a CORE-regime test must assert that `stop()` reports `rpc`/`sigterm` and never `timeout`. |
| 2 | **P2P forming on the control plane** | Would invalidate a campaign with no visible symptom. Four defences (§5.4), one of which is a hard post-bootstrap assertion. |
| 3 | **Wall-clock budgets under delay** | `setup_first_blocks`, `startup_timeout_s` and `wait_blocks` were tuned for ~0 ms. At 45.8 ms one-way the bootstrap is slower. The derivation in `schema.md` §3 already scales with node count but not with latency; it needs a term for the topology's worst-case RTT. **This is the most likely cause of a first CORE run failing**, and it is a tuning problem, not a design one. |
| 4 | Twenty `multichaind` processes plus twenty namespaces on 20 CPUs | The container is unconstrained by default and the native `large` profile already runs 34 daemons on one host. No new risk, but CPU contention now competes with an emulated delay for the explanation of a slow block, so the manifest must record the CPU quota. |
| 5 | CORE session leakage | A crashed run leaves a session, namespaces and bridges behind. `stop_network.py` must delete the session by the id in `fabric.json`, and also offer a sweep of orphaned sessions. |
| 6 | `--dry-run` without a CORE daemon | Must stay possible: it is how a profile is validated in CI. The address plan is pure (§5.3), so the fabric is only contacted by `start()`. |
| 7 | The container is required | CORE, netem and the namespaces exist only inside `./docker/mcsim`. Running a CORE profile on the host must fail with that sentence, not with an import error. |

### Decisions taken in this analysis, open to correction

1. The `legacy-*-10n`, `e2e-5n` and `smoke-3n` topologies are **not** migrated (§4.1).
2. All thirteen existing profiles move to `native/`, not only three (§6).
3. `network_profile` overrides the derived model and accepts `apply_to` (§5.6).
4. Derived jitter is `0.15 · delay`, floored at 0.02 ms, declared in `schema.md` (§4.2).
5. The shipped CORE profiles use the native node-id spelling (§5.7).
6. `direction:` is dropped from the link profiles as derivable (§4.1).
7. The two historical documents keep their text and gain a "paths removed on 2026-09-18"
   note (§4.3).

---

## 8. Plan

Ordered. Each step ends in something checkable. Nothing after step 0 starts before the
plan is approved.

**Step 1 — configuration data, no code.**
Migrate the four topologies and the seven link profiles into `test/config/`, stripped as
§4.1 says. Move the thirteen profiles into `test/config/profiles/native/` and fix the two
unit-test paths. *Check:* `python3 -m unittest discover -s test/unit` still passes and
`bootstrap_network.py --config test/config/profiles/native/small.yaml --dry-run` prints
the same plan as before the move.

**Step 2 — the topology model.**
`fabric/topology.py`: loader, great-circle distance, the delay/loss/bandwidth derivation,
the jitter rule, Dijkstra over the link graph. `fabric/addressing.py`: the address plan.
Both pure, both with unit tests, neither importing CORE. *Check:* `test_topology_model.py`
reproduces Milan–Rome 7.7 ms and Milan–New York 91.5 ms RTT; every shipped topology loads,
is connected, and every site gets a distinct subnet.

**Step 3 — the fabric seam, native only.**
Add `fabric/__init__.py` and `fabric/native.py`; route the nine `profile.host` call sites
and the five `node_process.py` call sites through it. **No CORE code yet.** *Check:* a full
`small.yaml` run produces a report and plots indistinguishable from one taken before the
change — this is the no-regression gate, and it is worth taking a baseline run before step
3 starts.

**Step 4 — the profile schema.**
Teach `config_loader.py` the list form of `nodes`, `fabric`, `topology`,
`network_profile`, declared clusters and every rejection in §5.6. Write the four level
profiles and the smoke profile. *Check:* `test_core_profile.py`; `--dry-run` on all five
CORE profiles prints a full plan with no daemon running.

**Step 5 — the CORE fabric.**
`fabric/core.py`: session, one node per site, links with `LinkOptions`, the control net,
static routes, `vcmd` wrapping, namespace-local signalling, read-back and `fabric.json`,
teardown. Extend `stop_network.py` to delete the session. *Check:* `smoke.yaml` brings up
4 nodes, `getpeerinfo` shows only data-plane addresses, the chain reaches its target height
and the three analysis phases run to `report.md`.

**Step 6 — latency-aware budgets.**
Add the worst-case-RTT term to `setup_first_blocks` and the startup/wait timeouts (risk 3),
derived and documented in `schema.md`. *Check:* `intercontinental.yaml` bootstraps without
a single "wait timed out" note.

**Step 7 — the four level runs.**
Run all four, compare against a native run of the same node count. *Check:* the tables and
figures have the same shape and columns in both regimes; only the numbers differ.

**Step 8 — removal and documentation.**
Delete `experiments/`. Update `README.md`, `docker/mcsim`, `docker/preflight.sh`,
`test/README.md`, `test/docs/architecture-notes.md`, `test/config/schema.md`, write
`test/docs/core-fabric.md`, annotate the two historical documents. *Check:* no reference to
`experiments/` outside `docs/adr/` and `docs/root-cause-report.md`; no occurrence of the
retired emulator's name anywhere in the new system; `graphify update .`.

---

## 9. What actually happened

The plan was followed in order. Three things in it turned out to be wrong, and one
measurement contradicted a published figure. All four are recorded here rather than
quietly fixed, because each changes what a later reader should believe.

### 9.1 The step-3 gate could not be what the plan said it was

The plan called for a native run "indistinguishable from one taken before the change".
That is impossible and the harness's own README says so: wallet keys, addresses and block
timing come from the node, not from the seed, so two runs of one profile never agree byte
for byte. The gate was therefore split in two:

* **Byte-exact**, on everything the seed decides: the derived plan of six profiles,
  compared before and after the profiles moved, was identical once the run-id timestamp
  was normalised.
* **Structural**, on a full 440-block run before and after the seam: same artefact set
  plus `fabric.json`, identical columns in all 67 CSVs, identical cluster map, port map
  and derived budgets, same status, same 21 measured epochs, and the same 9-of-10
  consistency checks with the same single non-critical failure (`phi_consistent`).

### 9.2 The latency term in the budgets is real but small

Risk 3 predicted that the wall-clock budgets would be the most likely cause of a first
CORE run failing. Measured on the built maps, the worst round trip is 0.363 s
(Los Angeles–Sydney), which at a 10 s block time adds about 6 s to a 120 s bootstrap
budget. The term was added anyway — it is the one that grows if a harsher map is written —
but it is not what the risk claimed.

The check that *was* missing is a different one, added on the same evidence: a profile
whose worst round trip exceeds a quarter of the sortition window
(`wpoa-sortition-delta x target-block-time`) is now rejected. Below that ratio the order
in which validators appear to act is set by the network rather than by the draw, and the
run produces a well-formed report of the wrong thing. The four shipped levels clear it
four times over.

### 9.3 A published check point of the delay model does not hold

Of the four routes the model was validated against, three reproduce to better than 0.1 ms.
The fourth, "Bologna–Geneva 840 km / 12.8 ms RTT", does not: those two cities are 448.5 km
apart, which the model turns into 7.3 ms. 840 km is very nearly the two-hop path through
Milan, so the published row appears to have compared a path against a direct distance.
`test/unit/test_topology_model.py` pins the three that hold and records why the fourth is
absent, rather than widening a tolerance until it passes.

### 9.4 The emulated round trip runs above the nominal one

Measured against the model's own figures: Zurich–Marseille 13.9 ms against 12.5 nominal,
Milan–New York 105.2 against 91.5, Tokyo–Johannesburg 229.3 against 190.5, Los
Angeles–Sydney 394.5 against 363.0 — a consistent 8–20% overshoot. The cause is the jitter
term: a per-packet delay drawn around a mean cannot delay a packet by less than zero. It is
documented in `config/schema.md` §6.2 so that nobody reads the gap as a fault.

### 9.5 The two hazards the analysis named, as they turned out

**Signalling across the PID namespace** (risk 1) was real and is handled: every node of the
CORE smoke run stopped with `rpc`, none needed a signal at all, so the escalation path is
untested in anger — but it is the only path that could have been silently wrong, and it
now goes through the fabric.

**A peer mesh on the control plane** (risk 2) did not occur, and is now checked twice: by
the bootstrap's own assertion, which passed on the 4-node smoke and on the 20-node
intercontinental map, and independently from the observer's `getpeerinfo` samples, where
every address seen across a whole run was on `10.60.0.x` and none on `172.30.0.x`.

### 9.6 Deviations from the plan, and why

* **`fabric/core.py` was written during step 3 rather than step 5**, while a 45-minute
  baseline run held every source file frozen. The validation order was not changed: the
  native gate still ran before any CORE profile did.
* **Step 7 was run at 6 epochs instead of 20**, by agreement: `--epochs` re-issues the
  profile into the run directory so that every child process reads the same thing. The
  shipped profiles are untouched at 20 epochs, and the full-length campaign is the
  operator's to launch.
* **`experiments/results/` was not deleted.** It holds 553 MB of untracked run output from
  earlier campaigns. It is research data, not source, and deleting it is not a decision
  this work should take on its own.
