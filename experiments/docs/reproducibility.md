# Reproducibility

What is controlled, what is not, and how to replay a run.

## Replaying a run

Every run copies its own inputs into `<run>/config/`, so it is replayable from
its own directory without reference to the repository state at the time:

```bash
sudo -E experiments/scripts/run_experiment.sh \
    --experiment experiments/results/<run-id>/config/experiment.yaml \
    --seed $(python3 -c "import json;print(json.load(open('experiments/results/<run-id>/manifest.json'))['seed'])")
```

The manifest also records the commit, so the exact code can be recovered:

```bash
git checkout $(python3 -c "import json;print(json.load(open('.../manifest.json'))['git_commit'])")
```

`git_dirty` in the manifest says whether the working tree was clean. A run
made from a dirty tree is not reproducible from the commit alone, and the
manifest says so rather than letting you assume otherwise.

## Seeds

One master seed per experiment; everything else is a pure function of it:

```
derived(purpose) = (master XOR fnv1a32(purpose)) & 0x7FFFFFFF
```

FNV-1a, not `hash()` — Python's is randomised per process and would make the
derivation unreproducible between runs of the same code. Purposes are `esg`,
`workload`, `netem`, `node_seed` and `placement`; per-node seeds derive from
`purpose/node_id`, so no two nodes share one.

```bash
python3 -m experiments.cli experiment dry-run \
    --experiment experiments/configs/experiments/regional.yaml --seed 12345
```

prints every derived seed before anything runs.

## What is controlled

| | how |
|---|---|
| topology and link impairment | fully declared; the exporter is deterministic |
| addresses, ports, peer lists | derived from the plan, same input → same output |
| ESG scores | drawn from `derive(master, "esg")` |
| workload intervals, reconciliation rates | declared per node in the descriptor |
| the bootstrap schedule | declared in seconds |
| chain parameters | hash-enforced; the effective `params.dat` is archived in the run |
| which binary ran | path, SHA-256 and version in the manifest |

`tests/unit/test_plan.py` asserts that the same descriptor and seed produce an
identical plan.

## What is not controlled, and is declared

These are real limits, not oversights. A run is reproducible *in
distribution*, not sample by sample.

1. **MultiChain's own RNG.** Wallet addresses differ between runs. Every
   artefact keys on the **host name**, never on an address, so this changes
   nothing downstream — but it does mean two runs are not byte-identical.
2. **netem's kernel-side generators.** The `seed` field of a profile is
   recorded in the manifest, but the kernel does not accept a seed for netem's
   loss and jitter. Those are reproducible in distribution only.
3. **Wall-clock scheduling.** Real execution means the Linux scheduler decides
   the interleaving. Two runs of the same configuration will not produce the
   same block at the same second. This is the price of emulation over
   simulation, and it is the whole reason the analysis works on distributions
   and test statistics rather than on individual events.
4. **Host contention.** Twenty `multichaind` processes compete for real CPU.
   The harness records load and per-process CPU at both ends of the run so a
   drift can be attributed correctly; it warns before starting when the node
   count exceeds four per core.

### The consequence for interpretation

A single run is one sample. Statements about the protocol need replicas: run
the same descriptor with several seeds and compare the distributions, rather
than reading one run's block time as a measurement of `λΦ`.

## The manifest

Written before anything starts and rewritten at every phase boundary, so a run
killed half way still leaves a manifest saying how far it got. Writes are
atomic — a half-written manifest is the one artefact that must never be
corrupt.

```json
{
  "run_id": "run-regional-20260910T101500Z",
  "status": "completed",
  "scenario": "regional",
  "seed": 20260910,
  "git_commit": "…", "git_dirty": false,
  "multichain_binary": "/…/src/multichaind",
  "multichain_version": "MultiChain 2.3 Daemon (Community Edition, protocol …)",
  "multichain_binaries": {"multichaind": {"sha256": "…"}, "…": {}},
  "fabric_backend": "netns",
  "core_version": "",
  "os_pretty": "Ubuntu 22.04.5 LTS", "kernel": "…",
  "kernel_modules": {"sch_netem": "loaded", "veth": "loaded"},
  "node_count": 20, "miner_count": 7,
  "setup_first_blocks": 64, "measure_blocks": 192,
  "started_at": "…", "ended_at": "…",
  "phases": [], "health": {}, "errors": []
}
```

`chain_initialization.setup_was_raised_at_genesis` is worth checking: when
true, `multichain-util` raised `setup-first-blocks` above the configured
value, and the measurement window followed the effective one.

## Why the RPC credentials are versioned

`configs/multichain.yaml` carries `poesia` / `poesiarpc` in plain text. They
are the credentials of an isolated emulated network that never touches a real
chain, and versioning them is what makes a run reproducible from the
repository alone. They are not a secret and must never be reused anywhere
that has one.

The one thing that *was* treated as a secret is the treasury private key: the
historical `treasury.json` shipped it, nothing in the harness spends from the
treasury, and the migrated file therefore carries the address alone. See
[migration-from-shadow.md](migration-from-shadow.md).

## Reproducing the archived campaign

The analysis code was migrated, not rewritten, and still reads the legacy
layout:

```bash
git checkout 6278274 -- shadow/esperimenti shadow/config shadow/risultati
python3 -m pytest experiments/tests/golden/test_legacy_pipeline.py -v
```

That test re-runs all three phases and diffs the result against the archive.
[../analysis/historical/README.md](../analysis/historical/README.md) lists the
three expected differences and why each is expected.
