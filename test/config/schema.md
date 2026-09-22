# Experiment profile format

A profile is a single YAML file describing one functional run: which nodes exist, which
ports they take, how long an epoch is, which chain parameters to bake into `params.dat`,
and how much traffic to generate. Every entry point of the harness takes exactly one
`--config <path-to-profile>`, and **no network or node parameter is hardcoded anywhere in
the code**.

A profile also chooses which of the two **regimes** it runs in, and that is the only thing
that differs between them structurally. Everything downstream — the bootstrap sequence,
the daemons, the three analysis phases, the figures — is the same code either way, which
is what makes a result from one comparable with a result from the other.

| Regime | Where the nodes are | What the network does |
|---|---|---|
| `native` | one host, one namespace, loopback | nothing: no netem, no jitter, no link delay |
| `core` | one namespace per site of a map, cables between them | delay, jitter, loss and capacity, per link |

The native regime is the baseline of correctness: with no network variable, a change in an
observed quantity has exactly one candidate explanation. The CORE regime is where the
network becomes a subject rather than a nuisance. See [§6](#6-the-core-regime).

### Native profiles — [`profiles/native/`](profiles/native/)

| Profile | admin | CA | miners | companies | epochs × length |
|---|---|---|---|---|---|
| [`small.yaml`](profiles/native/small.yaml) | 1 | 1 | 3 | 5 | 20 × 20 |
| [`medium.yaml`](profiles/native/medium.yaml) | 1 | 2 | 5 | 10 | 20 × 30 |
| [`large.yaml`](profiles/native/large.yaml) | 1 | 3 | 10 | 20 | 20 × 40 |
| [`malicious.yaml`](profiles/native/malicious.yaml) | 1 | 2 | 10 | 15 | 20 × 30 |

`malicious.yaml` is the only one with a `malicious` section (2 of its 10 miners misbehave);
the other three leave it out and run the honest baseline. See [§ `malicious`](#malicious-optional).
The nine `long*.yaml` profiles are the long-running campaign variants of the same three
sizes, one per `dump-function`.

### CORE profiles — [`profiles/core/`](profiles/core/)

| Profile | nodes | map | worst one-way path |
|---|---|---|---|
| [`smoke.yaml`](profiles/core/smoke.yaml) | 4 on 3 sites | [`smoke-4n`](topologies/smoke-4n.yaml) | 3.1 ms |
| [`regional.yaml`](profiles/core/regional.yaml) | 20 | [`regional`](topologies/regional.yaml) | 5.1 ms |
| [`national.yaml`](profiles/core/national.yaml) | 20 | [`national`](topologies/national.yaml) | 11.9 ms |
| [`continental.yaml`](profiles/core/continental.yaml) | 20 | [`continental`](topologies/continental.yaml) | 27.8 ms |
| [`intercontinental.yaml`](profiles/core/intercontinental.yaml) | 20 | [`intercontinental`](topologies/intercontinental.yaml) | 181.5 ms |

The four level profiles are identical in everything except `chain_name`, `topology` and
each node's `location`. That is deliberate: the geography is the only independent variable
across them, so a difference in the results is a difference in the network.

Validation lives in [`../bootstrap/config_loader.py`](../bootstrap/config_loader.py) and is
strict: an unknown key is an error, not a warning. A typo in a `params.dat` key would
otherwise be accepted silently by MultiChain itself and you would run with the default.

---

## 1. Two things the profile deliberately cannot set

### 1.1 The wPoA / WeightEngine activation flags

Every chain this harness creates runs the **complete stack, bottom-up**: weights →
selection → VRF → RANDAO → sortition → malus, plus the weight engine. The eight
`enable-*` keys are written by the harness and are **rejected** if they appear in a
profile:

```
enable-wpoa  enable-wpoa-weights  enable-wpoa-selection  enable-wpoa-vrf
enable-wpoa-randao  enable-wpoa-sortition  enable-wpoa-malus  enable-weight-engine
```

Every `multichaind` command line additionally carries `-enablewpoa=1
-enableweightengine=1`. This is not configurable and is not intended to become
configurable — a run of this harness with a phase switched off would not be the same
experiment.

> Writing `enable-wpoa = true` into `params.dat` **does not** switch wPoA on: `AppInit2`
> reads only the per-phase keys. See
> [`../docs/architecture-notes.md`](../docs/architecture-notes.md) §4.3.

### 1.2 The statistical constants

`alpha = 0.05`, Monte-Carlo draws `20000` (GoF) and `10000` (streak), and the analysis
RNG seed `20260905` are **methodological constants**, shared by both regimes. They
live in the code of `analysis/pipeline/stat/` and are not profile fields. The profile's
own `seed` controls the *network and the traffic*, never the tests.

---

## 2. Field reference

### `seed` *(int, required)*

Master RNG seed. One value drives **everything** non-deterministic in the run: which
company joins which cluster, ESG scores, how many transactions each company sends in
each epoch, how those are spread through the epoch, restitution counts and amounts.

Because the daemons are separate OS processes, a single shared `random.Random` object is
impossible. Determinism is preserved by **deriving** each stream from the master seed:

```python
sub_seed = int(sha256(f"{seed}:{purpose}:{node_id}").hexdigest()[:16], 16)
```

Two runs of the same profile therefore draw the same numbers in the same order, in every
process. What the profile cannot make deterministic is the chain itself: wallet keys,
addresses and block timing come from the node, not from the harness.

### `chain_name` *(string, required)*

MultiChain chain name. Lowercase letters, digits and `-`, 1–32 characters.

### `nodes` *(required)*

Two forms. A native profile may use either; a CORE profile must use the list, because a
count cannot say where a node is.

#### Counted form — `{ca_count, miner_count, company_count}`

| Field | Type | Constraint |
|---|---|---|
| `ca_count` | int | `>= 1` |
| `miner_count` | int | `>= 1` |
| `company_count` | int | `>= 1` |

**The admin node is always exactly 1 and is not a field.** Total nodes =
`1 + ca_count + miner_count + company_count`.

Roles are assigned in a fixed order — `admin`, then CAs, then miners, then companies —
and that order also fixes port assignment, so a given profile always produces the same
node-to-port map.

#### List form — one entry per node

```yaml
nodes:
  - {id: admin,     role: admin,   location: modena}
  - {id: ca-0,      role: ca,      location: parma}
  - {id: miner-0,   role: miner,   location: firenze}
  - {id: company-0, role: company, location: pisa, cluster: miner-0}
```

| Field | Type | Required | Note |
|---|---|---|---|
| `id` | string | yes | Unique, `[a-z0-9][a-z0-9._-]*`. It is a directory name (`chains/<id>/`, `logs/<id>/`) and a column value in every analysis table. |
| `role` | enum | yes | `admin` \| `ca` \| `miner` \| `company`. |
| `location` | string | CORE only | An `id` in the topology named by [`topology`](#topology-core-only). |
| `cluster` | string | companies only | The `id` of the miner whose cluster this company joins. |
| `enabled` | bool | no, default `true` | `false` removes the node from the run entirely, ports included, as though it were not written. |

The list's **order fixes the port map**, exactly as the role order does in the counted
form. The shipped CORE profiles list `admin`, then the CAs, then the miners, then the
companies, so a CORE profile and a native profile of the same composition put the same
node on the same port.

Rejected, with the offending id named: more or fewer than one enabled `admin`; no enabled
`ca`, `miner` or `company`; a duplicate `id`; a `location` that is not a site of the
topology; a `cluster` on a non-company; a `cluster` naming something that is not an
enabled miner; and **a miner that heads no cluster** — the cluster map is built only from
confirmed membership records, so a miner nobody joined is never computed and never
published, silently.

#### `cluster` and the seed

In the counted form the company→miner assignment is *drawn* from `seed` and recorded in
`clusters.json`. In the list form it is *declared*, and the same file records the same
thing. A list-form profile that declares no `cluster` anywhere falls back to the draw, so
the two forms differ in what they fix, never in what they produce.

### `fabric` *(optional)*

| Field | Type | Default | Note |
|---|---|---|---|
| `backend` | enum | `native` | `native` \| `core`. |

Absent means `native`, which is why every profile written before the fabric existed still
runs untouched. `core` is what selects the emulator; see [§6](#6-the-core-regime).

### `topology` *(CORE only)*

Path to a map, relative to `test/config/` — for example `topologies/continental.yaml`.
Required when `fabric.backend` is `core`, rejected otherwise. The map declares the sites
a node's `location` may name, the cables between them, and the physical model their delay
is derived from. See [§6.2](#62-where-a-links-numbers-come-from).

### `network_profile` *(optional, CORE only)*

Overrides the derived impairment with a named one from `network-profiles/`.

```yaml
network_profile: continental                          # every link
network_profile: {name: degraded, apply_to: access}   # the access links only
```

| Field | Type | Default | Note |
|---|---|---|---|
| `name` | string | — | A file in [`network-profiles/`](network-profiles/). |
| `apply_to` | enum | `all` | `all` \| `backbone` \| `access`. |

It **overrides** rather than adds: a link the profile applies to takes its numbers whole
and its coordinates stop mattering. `apply_to` exists because the two operating-point
profiles are meaningless applied flat — `partitioned` on every link is a dead network, and
`degraded` on every link is not a geography.

### `network` *(required)*

| Field | Type | Default | Note |
|---|---|---|---|
| `host` | string | `127.0.0.1` | **Native only.** Peers dial loopback explicitly; `getinfo nodeaddress` can report a NAT address. A CORE profile is rejected if it sets this: there, an address belongs to a site of the map and is derived from it. |
| `base_port` | int | — | First P2P port; node *i* gets `base_port + i`. |
| `base_rpc_port` | int | — | First RPC port; node *i* gets `base_rpc_port + i`. |

Both ranges must lie in `1024…65535` and **must not overlap each other** — a single
reused `-port`/`-rpcport` across two nodes is the classic multi-node-on-one-host failure
(`Create-Blockchain.md` §9), so the loader rejects it rather than letting the daemon
half-start.

### `epochs` *(required)*

| Field | Type | Constraint |
|---|---|---|
| `count` | int | `>= 1`. Epochs to sample before shutdown. |
| `length_blocks` | int | `1 … 1000000`. **This is `weight-epoch-length`.** |

`length_blocks` is the single source of truth for the epoch length; writing
`weight-epoch-length` under `weight_engine` is an error that names this field.

An epoch is **block-height based**, never wall-clock. Epoch `e` is first *buried* — and
therefore first computable by the engine — at height `e * length_blocks + 5`.

### `chain` *(optional; every field has a default)*

Standard MultiChain `params.dat` keys, written before the first daemon start.

| Field | Default | Why this default |
|---|---|---|
| `target-block-time` | `2` | Range `2…86400`. 2 s keeps a 400-block run to a few minutes. |
| `mining-diversity` | `0.0` | **Load-bearing.** At the stock `0.3` the round-robin spacing is binding even under wPoA and the observed distribution collapses onto round robin, masking the weighted election entirely. |
| `mining-turnover` | `0.5` | Not hash-enforced. |
| `mine-empty-rounds` | `-1` | Unlimited: the chain must keep producing blocks through quiet stretches, or the epoch clock stops. |
| `mining-requires-peers` | `false` | The admin must be able to mine alone during bootstrap. |
| `maximum-per-output` | `100000000000000` | **`MAX_MONEY` on this chain** (`src/utils/utilwrapper.cpp`). Caps every single output, the premine coinbase included, so it must be raised alongside `first-block-reward`. Over it, the node mines block 1 and then rejects its own block with `txout.nValue too high`, once a second, forever: the chain never leaves height 0 and the bootstrap stops after `starting the admin node` with no error of its own. |
| `first-block-reward` | `100000000000000` | The premine. Thesis §4.2.1: the currency is issued up front. Must be `<= maximum-per-output` **and** `>= gas_demand` (§GAS budgets); both are checked by the loader. |
| `initial-block-reward` | `0` | No incremental minting. |
| `minimum-relay-fee` | `20000000` | 0.2 GAS per 1000 bytes. |
| `anyone-can-connect` | `false` | Permissions are granted explicitly, as the model requires. |
| `setup-first-blocks` | *derived* | See §3. |

### `wpoa` *(optional)*

Only the **non-switch** wPoA keys of `params.dat`, by their exact `params.dat` names:

| Key | Default | Range |
|---|---|---|
| `dump-function` | `none` | `none` \| `sqrt` \| `log` |
| `wpoa-randao-lookback` | *derived:* `length_blocks + 1` | `1 … 1000000` (must be `>= 1`, sortition is on) |
| `wpoa-sortition-delta` | `0.5` | open `(0, 1)` |
| `wpoa-sortition-lambda` | `0.0` | `[0, 1]` |
| `wpoa-malus-mu` | `0.5` | `[0, 1)` |
| `wpoa-malus-max` | `4.0` | `> 0` |
| `wpoa-malus-equiv-points` | `4.0` | `> 0`, strictly `>` delay points |
| `wpoa-malus-delay-points` | `0.25` | `> 0` |
| `wpoa-malus-selfwrite-points` | `1.0` | `> 0` |
| `wpoa-malus-badweight-points` | `2.0` | `> 0`, strictly `>` selfwrite points |

The cross-parameter constraints (`equiv > delay`, `badweight > selfwrite`) are checked by
the loader, not left to the daemon's startup error.

### `weight_engine` *(optional)*

| Key | Default | Range |
|---|---|---|
| `weight-kappa` | `100.0` | `> 0`, `< 1e18` |
| `weight-alpha` | `0.2` | `[0, 1]` — **inert**: the binary parses and validates it, then never reads it. Kept because removing a hash-enforced field would make existing chains unjoinable. |
| `weight-lambda` | `0.5` | `[0, 1)`. `lambda < 1` is a correctness requirement, not a preference: it is what guarantees `w_k > 0`. |

`weight-treasury-address` is **not** a profile field. The treasury is a dedicated address
created on the admin at bootstrap and passed to every node as `-weighttreasuryaddress`;
see §4.

### `traffic` *(optional)*

| Field | Default | Note |
|---|---|---|
| `event_stream` | `supply-chain-events` | The informative stream. Deliberately not a weight-engine stream, and **closed**. |
| `company_tx_per_epoch_range` | `[30, 60]` | Drawn per company **per epoch**. A fixed count gives `tau` no variance and nothing in the weight pipeline moves. |
| `miner_gas_returns_per_epoch_range` | `[0, 5]` | Restitutions per miner per epoch. `0` is allowed. |
| `esg_score_range` | `[1, 100]` | Inclusive; `> 0` is enforced by the node. |
| `restitution_amount_range` | `[1.0, 9.0]` | Amounts within one miner-epoch are distinct, so a constant can never masquerade as a measurement. |

Both endpoints of every range must satisfy `low <= high`.

### `runtime` *(optional)*

| Field | Default | Note |
|---|---|---|
| `bindir` | `src` | Where `multichaind` / `multichain-util` live, relative to the repository root. |
| `chain_home` | `test/results/<run-id>/chains` | Per-node datadirs. |
| `results_root` | `test/results` | Run directories. |
| `rpc_timeout_s` | `30` | Per-call HTTP timeout. |
| `startup_timeout_s` | `120` | How long to wait for a node's RPC to answer `getinfo`. |
| `wpoa_debug` | `false` | Adds `-wpoadebug` to every daemon. **A smoke-test flag, not a campaign one.** It logs every row of the weight registry on every read — including the rows it discards for being outside the height scope — through an unbuffered, globally mutexed logger, on the path the mining thread runs. The number of rows grows by one per validator per epoch, so the total cost grows with `epochs.count` **squared**. The loader refuses the flag when the projection exceeds 2 GB across the run. |
| `api_decimal_digits` | *unset* | `-apidecimaldigits`. **Every shipped profile sets 17**; see below. |
| `shutdown_grace_s` | `30` | Time a node gets to answer `stop` before `SIGTERM`. |

#### Why every profile sets `api_decimal_digits: 17`

The node's JSON writer decides how many decimals a double needs by **rounding** it
(`sprintf` at `src/json/json_spirit_writer_template.h:257`) and then, when that probe
concludes none survive, emits it by **truncating** it (`os_ << (int64_t)value` at `:349`).
A value whose fractional part rounds up to `1.000…0` at the default of fourteen decimals
is therefore reported as its floor: `0.99999999999999944` is printed as `0`, and a delay
of `14.999999999999995` as `14`.

That is not a rounding nuisance. It is a whole unit, and on the audit RPCs it made the
harness and the node appear to disagree about the sortition mechanism itself — the
`delay_recompute_mismatch_rounds_is_zero` check, which invalidates every timer-race result
when it fails.

Seventeen is a double's round-trip precision, so the probe never concludes that no decimal
survives and the truncating branch is never reached. Measured, on the same profile with
the same seed: **26 corrupted values at the default of 14, none at 17.**

Currency amounts are not affected and never were: an amount is an exact multiple of
1e-8, so its fraction has at most eight decimals and cannot round up at the fourteenth.
Only computed, unquantised doubles are exposed — which is to say the wPoA audit values.
`test/analysis/pipeline/tools/verify_json_double_rendering.py` reproduces the writer and
checks any run against it.

### `malicious` *(optional)*

The malicious-miner experiment. **Absent means off**, and a profile without this section
behaves exactly as it did before the feature existed — the same numbers, the same tables.
Only *miners* can be selected. Full rationale:
[`../docs/malicious-miners.md`](../docs/malicious-miners.md).

| Field | Type | Default | Constraint |
|---|---|---|---|
| `enabled` | bool | `false` | When `false`, every other field is ignored. |
| `miner_count` | int | `0` | `0 <= miner_count <= nodes.miner_count`. How many miners misbehave. |
| `target_action_rate` | float | `0.0` | `[0, 1]`. Target share of the malicious *opportunities* to act on. |
| `seed` | int | *the run `seed`* | `>= 0`. Drives the miner selection and every Bernoulli decision. Recorded in the manifest. |
| `actions` | mapping | `{selfwrite: 0.5, badweight: 0.5}` | Non-empty; weights `>= 0`, not all zero; normalised. **Only** `selfwrite` and `badweight`. |
| `start_epoch` | int | `1` | `1 <= start_epoch <= epochs.count`. First epoch an opportunity arises. |
| `stop_epoch` | int/null | `null` | `null` = to the end; otherwise `>= start_epoch`. |
| `selfwrite_stream` | enum | `weight-engine-membership` | `weight-engine-membership` \| `wpoa-weights`. Which self-attested stream a selfwrite targets. |

Only two of the protocol's four malus kinds are producible from outside the node, so the
loader **rejects `delay` and `equiv`** with the reason (they are minted inside
`miner.cpp` / `multichainblock.cpp`, which this work must not touch). `enabled: true` with
`miner_count: 0` or `target_action_rate: 0` is rejected too — that combination is inert,
and `enabled: false` states the same thing without pretending to run.

An **opportunity** is one countable event per malicious miner per epoch of the active
window — not a block won, not a poll cycle — so a miner already penalised to `Psi = 0`
still gets exactly one chance per epoch and the rate controller cannot diverge. The
aggregate target is split across the selected miners in proportion to their initial share
of the published weight (uniform when no weight is available yet), and each miner runs a
deficit controller on its own share, so the total *attempted* actions approach
`target_action_rate` of the total opportunities with no coordination between miners.

The run writes an immutable **`<run>/malicious_manifest.json`** — the resolved config, the
selected miner ids and addresses, the seed, the per-miner target rates and the schema
version — consumed by the traffic daemons and by the analysis.

---

## 3. Derived values

The loader computes these and records them in the run manifest. They are not profile
fields, but they are the ones most likely to be wrong if you change a profile.

### `setup-first-blocks`

Two independent lower bounds, and the harness takes the larger.

**The protocol floor**, applied by the node itself at genesis
(`mc_MultichainParams::AdjustSetupFirstBlocks`), which silently rewrites `params.dat`
*before the hash is taken*:

```
protocol_floor = length_blocks + 9         # = L + STABILITY_MARGIN(6) - 1 + SETUP_PUBLISH_MARGIN(3) + 1
```

**The wall-clock bootstrap budget**, which the node cannot know:

```
boot_s   = 6 * n_nodes / 2 + 60            # daemons start in parallel; they still contend for one host
inputs_s = 12 * target_block_time + n_nodes  # grants, streams, membership and ESG, all confirmed
budget   = ((boot_s + inputs_s) / target_block_time + protocol_floor) * 3 / 2
```

The floor only covers the *epoch geometry* — when the first weight can confirm. It cannot
know how long starting N daemons takes, and past a handful of nodes that is the larger of
the two. The chain then reaches `setup-first-blocks` with an empty registry, wPoA elects
nobody, and **the chain stops dead**. Overshooting merely wastes blocks.

Whatever is written, the harness **re-reads the effective value from
`getblockchainparams`** once the chain is up and records that, because the node may have
raised it.

### `-maxtxfee`

```
maxtxfee = (minimum-relay-fee / 100000000) * 10
```

Wallet policy, not consensus, so it is a per-node command-line flag and changes no chain
parameter. Without it every stream publish above ~500 bytes fails with
`error code: -6 Transaction too large for fee policy` — `send` keeps working while
`publish` dies, so the network looks healthy while no record is ever written.

### GAS budgets

A company must never run dry mid-epoch: it would stop generating `tau` and that epoch's
weight would silently understate it.

```
gas_per_tx = minimum-relay-fee / 100000000            # 1 KB per tx, a deliberate over-estimate
gas_floor  = tx_max * gas_per_tx * 2                  # refuel trigger: covers one more worst-case epoch
gas_seed   = tx_max * gas_per_tx * epochs.count * 1.5 + 50
gas_topup  = gas_seed / 2
miner_seed = returns_max * epochs.count * restitution_hi * 1.2 + 200   # something to return in epoch 1

gas_demand = miner_count * miner_seed + (node_count - 1 - miner_count) * gas_seed
```

`gas_demand` is what `seed_gas` sends in one round, straight from the premine. It has to
fit: `gas_demand <= first-block-reward / 100000000 <= maximum-per-output / 100000000`.
Below the demand, `seed_gas` funds the nodes it reaches and the rest come back `-704`
("Insufficient funds") several minutes into the run, with the fabric, the chain and every
daemon already up. The loader checks both inequalities before anything starts.

Note which term dominates: `miner_seed` is a product of three maxima, so
`restitution_amount_range` and `miner_gas_returns_per_epoch_range` matter as much as the
epoch count. A 222-epoch profile at `restitution_amount_range: [1.0, 9.0]` needs 12 188
per miner; a 100-epoch one at `[50.0, 250.0]` needs 600 200.

### Target height

```
verify_height = (epochs.count + 1) * length_blocks + 5    # epoch N+1 buried, so epoch N is verifiable
target_height = verify_height + 6 + 9
```

---

## 4. What the profile does *not* describe

- **The treasury address.** `weight-treasury-address` is hash-enforced and must be in
  `params.dat` before genesis, but an address is born with the wallet. The harness breaks
  the circularity by passing `-weighttreasuryaddress` uniformly to every node at startup
  instead, and records the address in the run manifest. It is a **dedicated** address,
  never the admin's: with the admin as treasury, a refuel's own change output pays the
  treasury and only a guard inside `mc_AccumulateReconciliation` spares it.
- **Node addresses and wallet keys.** Generated by the node.
- **Which company joins which cluster.** Derived from `seed`, recorded in the manifest.

---

## 5. Minimal example

A native profile:

```yaml
seed: 20260905
chain_name: wpoa-smoke-small

nodes:
  ca_count: 1
  miner_count: 3
  company_count: 5

network:
  base_port: 7447
  base_rpc_port: 8447

epochs:
  count: 20
  length_blocks: 20
```

The same run on an emulated map:

```yaml
seed: 20260905
chain_name: wpoa-core-smoke

fabric:
  backend: core
topology: topologies/smoke-4n.yaml

nodes:
  - {id: admin,     role: admin,   location: bologna}
  - {id: ca-0,      role: ca,      location: bologna}
  - {id: miner-0,   role: miner,   location: firenze}
  - {id: company-0, role: company, location: pisa, cluster: miner-0}

network:
  base_port: 7907
  base_rpc_port: 8907

epochs:
  count: 5
  length_blocks: 20
```

Everything else takes the documented default.

---

## 6. The CORE regime

### 6.1 Two planes, and why the control plane is not emulated

```
DATA PLANE (emulated)                    CONTROL PLANE (out of band)
one namespace per site of the map        one bridge, created by CORE
one /30 per cable, netem on each end     no netem, no shaping
static routes from the map               reaches every node from the host
carries: MultiChain peer-to-peer         carries: the harness's RPC
10.60.0.<site>/32 identities             172.30.0.0/24
```

The orchestrator, the observer, the CA assigner, the malus detector and every traffic
daemon stay ordinary processes on the host and reach each node over the control plane.
That is a **declared property of the method**, not a convenience: pushing them into the
namespaces would make every RPC call pay the emulated latency, and the instrument would
then sit inside the thing it measures. What the emulation acts on is the traffic between
nodes — blocks, transactions, stream records — which is what the geography is a claim
about.

The corollary is the one failure that would invalidate a campaign silently: if the chain
formed its peer mesh on the *control* plane, every run would complete, every report would
read normally, and every number in it would describe a network with no delay. Four things
prevent it, and the fourth is an assertion rather than a precaution:

1. `-bind=<identity>` — the peer-to-peer listener exists only on the data address.
2. `-externalip=<identity>` with `-discover=0` — the node advertises that address instead
   of choosing one of its two interfaces.
3. The seed address a joining node dials is the admin's data address.
4. After the bootstrap, every address in every node's `getpeerinfo` is checked against the
   map's identities. One address that is not on the data plane fails the run.

### 6.2 Where a link's numbers come from

Either the map's own physical model, or a named profile — never both, and every realised
link records which, in `<run>/fabric.json`, as `derived:latency-model` or
`profile:<name>`. A delay that cannot be traced back to a model or to a stated assumption
is not evidence.

The physical model, from the map's `latency_model`:

```
one_way_ms = propagation_ms_per_km · D_km · routing_factor + overhead
             overhead = 0.5 ms on a backbone hop, 1.0 ms on an access hop
loss_%     = access:   loss_access                              (constant)
             backbone: loss_backbone_base + loss_backbone_per_km · D_km
bandwidth  = backbone: defaults.bandwidth_hub_mbps
             access:   defaults.bandwidth_leaf_mbps
```

`D_km` is the great-circle distance between the two sites' coordinates. Three published
check points pin it, in `test/unit/test_topology_model.py`: Milan–Rome 477 km → 7.7 ms
RTT, Milan–Madrid 1188 km → 17.6 ms, Milan–New York 6464 km → 91.5 ms. A change that moves
them changes the meaning of every figure produced under any map, so they fail rather than
being updated.

**Jitter is a declared assumption, not a measurement.** No map carries a jitter term, so a
derived link takes `0.15 × delay`, floored at 0.02 ms. That ratio is the one the seven
shipped link profiles use (2.1/0.3, 5.1/0.8, 10.4/2.0, 45.8/8.0 — 0.14 to 0.17). It is
stated here, in one place, rather than left implicit in seven files.

CORE applies the impairment at **each end** of a cable, so `delay` is one way and the round
trip is twice it — which is what `mean_ms` means in every profile. An asymmetric profile
(`degraded`) is the one case where the two ends differ; it becomes two unidirectional
statements rather than an average, because an average would be a third network nobody
configured.

**The measured round trip runs above the nominal one, by 8–20%.** Measured on the shipped
maps: Zurich–Marseille 13.9 ms against 12.5 nominal, Milan–New York 105.2 against 91.5,
Tokyo–Johannesburg 229.3 against 190.5, Los Angeles–Sydney 394.5 against 363.0. The cause
is the jitter term: a per-packet delay drawn around the mean cannot delay a packet by less
than zero, and ICMP reports the arrival order, so the sampled mean sits above the
configured one. Anyone comparing an observed propagation against the model's own figure
should expect that gap and not read it as a fault.

### 6.2.1 The block time has to clear the network

A profile is **rejected** when the map's worst round trip is more than a quarter of the
sortition window:

```
sortition window  Delta_max = wpoa-sortition-delta x target-block-time
rejected when     worst_round_trip > 0.25 x Delta_max
```

Not a matter of taste. The sortition delay is *drawn* inside that window, and if
propagation were comparable with it, the order in which validators appear to act would be
set by the network rather than by the draw — the election would measure the emulator's
queueing, and it would produce a perfectly well-formed report of the wrong thing. The
check names both numbers and the two ways out (raise `target-block-time`, or raise
`wpoa-sortition-delta`).

The shipped profiles clear it with room: the harshest, `intercontinental`, has a 0.363 s
worst round trip against a 1.25 s limit.

The same worst round trip also enters `setup-first-blocks`, once per bootstrap sync point
(§3). That term is small — about 6 s against a 120 s budget on the harshest map — and it
is there because it is the one that grows if a harsher map is ever written.

### 6.3 Addressing and routing

| Plane | Prefix | Assigned by |
|---|---|---|
| identity | `10.60.0.<site index>/32`, on `lo` | the address plan |
| cable | `10.61.<link index>.0/30` | the address plan |
| control | `172.30.0.<site index>/24` | CORE |

The site index is the map's own order, so the plan is a **pure function of the topology
file**: `--dry-run` prints the whole address map with no emulator running, and a traffic
daemon that re-loads the profile resolves an RPC endpoint without asking CORE anything.
What CORE actually assigned is read back at start and written to `<run>/fabric.json`; a
disagreement with the prediction fails the start rather than becoming a mystery later.

**A site's identity is what chain nodes bind to, not an address per node.** Nodes placed
at the same site run in the same namespace, share its addresses, and are told apart by
port — which is exactly what `base_port + index` already guarantees. Two nodes at one
location are two processes at one place, which is what co-location means.

Routing is static, computed from the map by shortest path weighted by delay, and only ever
*to a /32*: each site holds one route per other site and none for the cables, which
nothing is ever addressed to. There is no routing daemon, because a protocol's convergence
time is wall-clock nondeterminism and it would land in the one part of a measurement
harness that must not have any.

### 6.4 What a CORE run needs

CORE, its namespaces and netem live in the project's container. A CORE profile run outside
it fails saying so; it does not fall back to the native regime, because a run that changed
regime by itself would be labelled, read and compared exactly like one that had not.

```bash
./docker/mcsim preflight      # is the emulator here, and can it build a namespace?
./docker/mcsim run python3 test/bootstrap/bootstrap_network.py \
    --config test/config/profiles/core/smoke.yaml
```

`--dry-run` needs none of that: it validates the profile and prints the plan, addresses
included, wherever Python and PyYAML are.
