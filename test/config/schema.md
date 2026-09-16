# Experiment profile format

A profile is a single YAML file describing one functional run: how many nodes of each
role, which ports, how long an epoch is, which chain parameters to bake into
`params.dat`, and how much traffic to generate. Every entry point of the harness takes
exactly one `--config <path-to-profile>`, and **no network or node parameter is
hardcoded anywhere in the code**.

Ready-made profiles live in [`profiles/`](profiles/):

| Profile | admin | CA | miners | companies | epochs × length |
|---|---|---|---|---|---|
| [`small.yaml`](profiles/small.yaml) | 1 | 1 | 3 | 5 | 20 × 20 |
| [`medium.yaml`](profiles/medium.yaml) | 1 | 2 | 5 | 10 | 20 × 30 |
| [`large.yaml`](profiles/large.yaml) | 1 | 3 | 10 | 20 | 20 × 40 |

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
RNG seed `20260905` are **methodological constants** shared with `experiments/`. They
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

### `network` *(required)*

| Field | Type | Default | Note |
|---|---|---|---|
| `host` | string | `127.0.0.1` | Peers dial loopback explicitly; `getinfo nodeaddress` can report a NAT address. |
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
| `first-block-reward` | `100000000000000` | The premine. Thesis §4.2.1: the currency is issued up front. |
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
| `wpoa_debug` | `false` | Adds `-wpoadebug` to every daemon. Verbose. |
| `shutdown_grace_s` | `30` | Time a node gets to answer `stop` before `SIGTERM`. |

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
miner_seed = returns_max * epochs.count * 40 + 200    # miners must have something to return in epoch 1
```

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

Everything else takes the documented default.
