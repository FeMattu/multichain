# Runtime

Builds the emulated network and runs the real MultiChain nodes on it.

```
runtime/
├── fabric/          core_emulator.py | netns.py | docker_backend.py, behind base.py
├── netem/           profiles.py (pure impairment → tc), apply.py, clear.py
├── multichain/      install, treasury, initialize, health, lifecycle, rpc
├── roles/           the five bash role scripts that run inside the nodes
├── collectors/      rpc, process, system, logs, and the sampler thread
├── session.py       the run: one object, one cleanup path
├── manifest.py      the run's own record of itself
├── shell.py         command execution and privilege handling
└── cli.py           the runtime half of `experiments.cli`
```

## The parts worth knowing about

**`fabric/`** — three backends, one interface. CORE is primary; `netns` builds
the same thing from `ip`/veth/`tc` so the harness runs without CORE; `docker`
is declared and fails at configuration time with the reason. `auto` prefers
CORE and logs what was missing when it falls back.

**Two planes.** The emulated plane carries P2P and node-to-node RPC through
routers with per-link netem. The management plane is an unimpaired bridge used
only by the harness's collectors — polling twenty nodes over the paths under
measurement would perturb them. See
[../docs/architecture.md](../docs/architecture.md).

**`netem/profiles.py` is pure.** It builds `tc` argument lists and executes
nothing, which is what makes the impairment mapping testable without root.

**`roles/`** — migrated from `shadow/tools/role_*.sh` with their on-chain
knowledge intact. They speak JSON-RPC over `curl`, not `multichain-cli`,
because every process touching Bitcoin Core's RNG pays a 100 ms
`Strengthen()` busy-loop once — affordable for a person, not for twenty nodes
polled every thirty seconds on the host already running twenty daemons.
`_common.sh` explains it at length.

**`session.py`** — a context manager, so there is exactly one cleanup path.
Ctrl+C, a dead daemon, a fabric failure and a clean finish all leave through
`__exit__`: roles stopped first, daemons stopped over RPC so their databases
flush, impairment cleared, fabric destroyed, manifest written. It never
deletes results.

**`shell.py`** — one place decides how a privileged command is invoked, which
is what makes `--dry-run` show the exact sequence a real run would issue.

## Adding a fabric backend

Subclass `fabric/base.py:Fabric` and implement `preflight`, `build`,
`teardown`, `exec_argv`, `spawn`, `apply_impairment` and `clear_impairment`,
then register it in `fabric/factory.py`. `preflight` returns the reasons it
cannot run here — a list of sentences a user can act on, not a boolean.
