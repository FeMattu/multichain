# Troubleshooting

Symptoms, causes, and the fixes. Most of these were found the hard way and
each one is cheap to hit twice.

## Start here

```bash
experiments/scripts/check_environment.sh --experiment <descriptor>
python3 -m experiments.cli experiment dry-run --experiment <descriptor>
```

The first says what is missing; the second shows every command a real run
would issue, without issuing any.

## Environment

### `ip` or `tc` "not installed" but they clearly are

They live in `/usr/sbin`, which is not on a non-root user's `PATH` on Debian
and Ubuntu. `check_environment.sh` reports the real location when it finds
them there.

```bash
export PATH="$PATH:/usr/sbin"
```

### `sudo needs a password, so the harness cannot create namespaces unattended`

A run needs `CAP_NET_ADMIN`. Either run as root, or allow the three tools
without a password:

```
# /etc/sudoers.d/poesia-experiments
your-user ALL=(root) NOPASSWD: /usr/sbin/ip, /usr/sbin/tc, /usr/bin/nsenter
```

Use `sudo -E`, or `MULTICHAIN_BIN`, `EXPERIMENT_ROOT` and `PYTHON` are lost.

Without privileges you still get `validate`, `topology`, `experiment dry-run`,
`metrics`, `analysis` and `report` — everything except building the fabric.

### `the MultiChain binaries are required and were not found`

The message lists every path that was tried, in resolution order.

If it says *"MULTICHAIN_BIN explicitly requested … which is not a file"*, the
variable is wrong and the harness refused to substitute something else — an
explicit request is honoured or refused, never quietly replaced.
`MULTICHAIN_BASE_DIR` is a search location rather than a request, so a wrong
one falls through to `src/`.

Either build them:

```bash
./autogen.sh && ./configure && make -j$(nproc)     # writes into src/
```

or point at an existing build:

```bash
export MULTICHAIN_BIN=/opt/multichain/multichaind
export MULTICHAIN_CLI=/opt/multichain/multichain-cli
export MULTICHAIN_UTIL=/opt/multichain/multichain-util
# or all three at once:
export MULTICHAIN_BASE_DIR=/opt/multichain
```

### `CORE is not available ... and the fallback was declined` (exit 2)

Deliberate. With `fabric.backend: auto` and CORE missing, the harness does
**not** quietly switch to the netns fabric: a run that changed backend on its
own would look, be labelled and be compared exactly like a CORE run, and the
only record would be a log line.

Three ways forward, all explicit:

```bash
sudo core-daemon                       # 1. give it the CORE it asked for
... --allow-fallback-without-core      # 2. authorise the fallback deliberately
... --backend netns                    # 3. say netns is what you want
```

Interactively it asks instead, and the prompt lists exactly what the netns
fabric keeps and gives up. Non-interactively it refuses, because a cron job
must never make that choice for you.

### Nodes start, then `Couldn't connect to the seed node`

The daemons are healthy and the network is not. The most likely cause is the
route: a node's route to the experiment subnet must carry `src <node ip>`.

```bash
sudo ip netns exec poesia-h-m1 ip route
# 11.0.0.0/24 via 10.99.0.10 dev eth0 src 11.0.0.21    <- src must be there
```

Without `src` the kernel sources packets from the interface address, which is
the `/30` link address; no other node has a route back to a `/30`, so the SYN
arrives and the reply is undeliverable. The harness now pins it and verifies
connectivity before starting any daemon, so this should surface as:

```
the fabric was built but does not carry traffic: N of M node pairs cannot
reach each other
```

If it does, check in order: the `src` above, `net.ipv4.ip_forward` on the
routers, and `rp_filter` (the harness sets it to 0, because a mesh of hubs
makes return paths asymmetric and strict mode drops them silently).

### `sch_netem cannot be confirmed from userspace`

The module is either built into the kernel or genuinely absent, and userspace
cannot tell without root. If `tc qdisc add ... netem` then fails:

```bash
sudo modprobe sch_netem sch_tbf
```

On WSL2 this is common: the Microsoft kernel ships the modules but does not
autoload them.

### Ubuntu 20.04

Supported. Python 3.8 is the floor and every dependency bound in
`requirements.txt` is satisfied by the 20.04 archive:

```bash
sudo apt install python3-yaml python3-jsonschema python3-numpy python3-scipy \
                 python3-pandas python3-matplotlib python3-networkx \
                 python3-openpyxl iproute2 curl
```

## The network

### Nodes cannot reach each other

```bash
sudo ip netns list                      # are the namespaces there?
sudo ip netns exec poesia-h-m1 ip addr  # does the node have its /32 on lo?
sudo ip netns exec poesia-h-m1 ip route # is 11.0.0.0/24 routed via the router?
sudo ip netns exec poesia-r-firenze ip route  # does the router know every /32?
```

The most common cause is a leftover fabric from a previous run holding the
addresses:

```bash
sudo -E experiments/scripts/clean_experiment.sh
```

### `Address already in use` on start

A previous run's namespaces or a `multichaind` survived. Same fix; the script
also offers to terminate leftover daemons.

### A run is unexpectedly slow, or the delays look wrong

A netem qdisc left on a veth end in the root namespace by a hard kill. It has
no owner and impairs whatever reuses the interface:

```bash
sudo -E experiments/scripts/clean_experiment.sh     # strips stray qdiscs
sudo tc qdisc show                                  # confirm nothing is left
```

### Impairment is not applied at all

```bash
sudo ip netns exec poesia-r-firenze tc qdisc show
```

Expect `tbf` at the root and `netem` below it on each inter-location
interface. Nothing there means `sch_netem` is missing — see above.

## The chain

### `cannot score (unsynced or unweighted)`, and the chain stops at setup

The single most likely failure, and it has exactly three causes:

1. **`wpoa-weights` was never created.** With the weight engine on, the
   registry does not create the stream until it has a weight to publish, and
   it has no weight until membership and ESG records exist. The admin's
   `grant` phase creates it explicitly, CLOSED. Check
   `logs/<admin>/role-grant.log` for `stream wpoa-weights created`.
2. **No ESG score was published.** Without one every weight is zero. Check
   `logs/<ca>/role-ca.log`; the usual cause is the CA missing `high1`, which
   is *not* implied by being an administrator.
3. **`setup-first-blocks` is too short.** wPoA took over before any weight was
   published. The harness refuses a configured value below the derived
   minimum, but `multichain-util` can also raise it at genesis — check
   `chain_initialization.setup_was_raised_at_genesis` in the manifest.

The `weights published` health check now catches all three *before* the setup
phase ends, so look there first.

### The network looks healthy but no stream record is ever published

`maxtxfee`. The wallet caps a single transaction's fee at 0.1 native units by
default; with `minimum-relay-fee = 0.2 GAS/1000 byte` every publish above
~500 bytes exceeds it and `CreateTransaction` refuses it with *"Transaction
too large for fee policy"*. It hits `publish`, not `send`, so balances move
and records do not.

The harness writes `maxtxfee=10.0` into every `multichain.conf`. If you
changed the relay fee, raise it to match.

### `Not subscribed to this stream` in the final snapshot

The admin is not a cluster head, so it publishes no weight and the registry
never subscribes it. The `grant` phase subscribes it explicitly to
`wpoa-weights`, `weight-engine-esg`, `weight-engine-membership` and
`wpoa-weights-malus`. Check `logs/<admin>/role-grant.log`.

### `Could not parse entity key` on a grant

MultiChain rejects `grant addr "a.write,b.write"`. Stream write permissions
must be granted one stream per call, and the role script does.

### `Corrupted block database detected`

A data directory killed mid-write. The harness stops daemons over RPC first
precisely to avoid this; it happens after a `SIGKILL` or a machine crash. The
data directory is not recoverable — delete the run's `runtime/data/<node>` and
re-run. The **logs and metrics of that run are still valid** and are kept.

### `no local mining key, waiting`, over and over

Not an error. It is a transient state of the mining loop and appears in the
`debug.log` of miners that are producing blocks perfectly well. In the
historical validation run the three miners emitted it hundreds of times while
producing 34 / 29 / 17 blocks out of 80.

### Every miner produces almost exactly the same number of blocks

Native Spacing. `mining-diversity` imposes `ceil(d·(N-1))` blocks between two
blocks of the same signer; with `d = 0.3` and four permitted signers that is
1, so no miner can sign twice in a row and the distribution collapses onto a
round robin whatever the weights say. Every shipped chain-parameter file pins
`MINING_DIVERSITY=0`. Check `metrics/…/run_index.csv`.

## The run

### A node's `role_controller.log` stops early, or is missing

Each node is driven by a Python controller for the whole run, and it logs a
heartbeat every ten ticks. A log that ends at start-up means the controller
died; the scheduler restarts it up to five times and records each restart in
`runtime/role-controllers.json` and in `process_restarts`.

```bash
python3 -c "import json;d=json.load(open('<run>/runtime/role-controllers.json'));
print(d['restarts_total'], d['gave_up'])"
```

A node the scheduler gave up on stops contributing from that moment: a
company stops generating the traffic that drives `tau_i`, a miner stops
reconciling and its `rho_k` silently becomes 1. Check this before reading the
weights as a protocol result.

### It exits with code 4, "incomplete data"

The admin's final snapshot was not taken, so there is no `blocks.json` and
nothing to analyse. Look at `logs/<admin>/role-snapshot.log`. Usually the run
was stopped before `duration - snapshot_before_stop_s`.

### It exits with code 2 before creating anything

The environment. Run `check_environment.sh --experiment <descriptor>`.

### Ctrl+C seems to hang

It is stopping the daemons over RPC, which takes up to 20 s each so their
databases flush. A second Ctrl+C aborts the cleanup — which risks the
corrupted-database case above. Prefer to wait.

### The block time is well above the target

Three candidates, in the order worth checking:

1. **Host contention.** Twenty daemons on few cores. `report_generale.md`
   reports load and per-process CPU; the harness warns before starting when
   node count exceeds four per core.
2. **The emulated network.** Compare `netem_conditions.csv` with the
   propagation figures: if propagation is a large fraction of the target
   block time, the geography is dominating.
3. **The protocol's `λΦ` feedback.** Only conclude this after excluding the
   first two. And note that an archived Shadow figure carries a fourth term
   the new runs do not — see [metrics.md](metrics.md), "Three clocks".

## The analysis

### `analysis run` exits 5 with schema problems

A produced table no longer matches the catalogue. The message names the table
and whether a column is absent or reordered. Either the collector changed and
`metrics/catalogue.py` needs updating, or the change was accidental.

### `no run directory for '<id>'`

```bash
python3 -m experiments.cli results list
```

Runs live under `experiments/results` unless `EXPERIMENT_ROOT` moved them —
and it must be set in the shell doing the analysis too.

### The historical tables are missing after `analysis run`

They come from the migrated pipeline, which needs the admin's final snapshot.
No `raw/metrics/blocks.json`, no historical tables. The new tables
(observations, propagation, forks, netem) do not depend on it and will be
there.

### Re-analysing the archived campaign

```bash
git checkout 6278274 -- shadow/esperimenti shadow/config shadow/risultati
python3 -m experiments.analysis.pipeline.run_pipeline \
    --phase all --root shadow/esperimenti --config shadow/config --out /tmp/risultati
```

## Getting more detail

```bash
python3 -m experiments.cli -v experiment run --experiment <descriptor>
```

Every run keeps `<run>/run.log`, and every node keeps `<run>/logs/<node>/`
with the daemon's stdout, each role script's output and the archived
`debug.log`.
