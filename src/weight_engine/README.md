# WeightEngine

Computes the dynamic, ESG-derived validator weight `w_k` that the wPoA layer
(`src/wpoa/`) consumes to elect proposers. It **produces** the weights; it does
not select.

The module reference is [`../wpoa/docs/weight-engine.md`](../wpoa/docs/weight-engine.md).
This file is only a map of the directory and its tests.

## Source layout

| File | What it is |
|---|---|
| `weight_engine.h` | **Pure core**: the math of the pipeline (`c_i → W_k → g_k → saldo_k → rho_k → w_k`). No globals, no node dependencies. |
| `weight_engine.cpp` | `ThreadWeightEngine` — the background thread: ensure streams, gate on a buried epoch, verify peers, publish the local `w_k`. |
| `weight_records.h` | **Pure core**: parsers and accumulators for the input records, plus the chain-derived reconciliation rules (`mc_ValuePaidToTreasury`, `mc_AccumulateReconciliation`). |
| `weight_reader.cpp/.h` | Stream reading, subscription, and the single block/undo pass that derives `tau`, `R_k` and the per-address flows (`ComputeEpochFacts`). |
| `weight_verifier.h` | **Pure core**: `mc_VerifyPublishedWeights` — compare published weights against an independent recomputation, epoch-scoped. |
| `weight_verifier.cpp` | The node-coupled half: run the recomputation, compare, cache the verdicts. |
| `weight_publisher.cpp/.h` | The write path behind the two input RPCs: caller-address resolution (including the Certification Authority gate), round-trip validation and publication. |
| [`../rpc/rpcweightengine.cpp`](../rpc/rpcweightengine.cpp) | The RPC handlers themselves: `weightsetesg` (Certification Authority only), `weightregistermembership` (public self-write), `weightverifyweights` (open read), and the read-only **epoch audit** — `weight{getlocal,getnode,list}` × `contribution` / `clusterweight` / `returns` / `earnings` / `balance`, one family per pipeline definition. |
| `weight_authorization.h` | **Pure core**: per-stream write policy. |
| `weight_streams.h` | Stream names and the **default** parameter values (`MC_WEIGHT_DEFAULT_*`, the stability and setup-publish margins). |

Two published input streams, `weight-engine-membership` and `weight-engine-esg`.
`tau` and `R_k` are **derived from the blocks**, not published — see
[`../wpoa/docs/adr/reconciliation-onchain.md`](../wpoa/docs/adr/reconciliation-onchain.md).

## Tests

**Unit** — [`test/`](test/), node-free Boost.Test modules compiled straight from
source:

```bash
./src/weight_engine/test/run_unit_tests.sh            # every suite
./src/weight_engine/test/run_unit_tests.sh records    # just one
./src/weight_engine/test/run_unit_tests.sh --list
```

Suites: `records` (input parsers + reconciliation rules), `authorization`
(per-stream write policy), `engine` (the pipeline math), `verifier` (published-weight
verification). No node build needed, and no autotools — the runner invokes `g++`
directly.

**Functional** — [`../../test/functional/weight_engine/`](../../test/functional/weight_engine/).
They moved out of this module because a functional run exercises wPoA, the weight
engine, the malus registry and the streams together; see
[`../../docs/adr/test-restructure-2026.md`](../../docs/adr/test-restructure-2026.md).

```bash
./test/functional/run_functional_tests.sh --suite weight-engine
./test/functional/run_functional_tests.sh --suite weight-engine-bootstrap
./test/functional/run_functional_tests.sh --suite weight-engine-large --fast
```

**Experimental** — [`test/experimental/`](test/experimental/) is **not** a test: it
is the MyLedger economic simulation harness. It has no pass/fail contract; its
product is CSVs, an `.xlsx` report and a log for offline analysis. It stays in this
module because its research question ("does the deployed engine compute the weight
the POESIA / Vers_2 model specifies?") is a weight-engine question.

```bash
./src/weight_engine/test/experimental/run_experiment.sh
```

> Note on GAS: MultiChain defaults `initial-block-reward = 0`, so there is no
> spendable native currency. The experimental harness therefore models GAS as an
> issued divisible **asset**. `ComputeEpochFacts` reads **native** values, so on a
> chain without native currency `R_k`, the credits and the debits are all 0 and the
> restitution-rate feedback is inert. Any test that needs that feedback to move must
> enable the native currency in its own `params.dat` — the large-network functional
> suite does exactly that.

## Chain parameters

All consensus-critical, all hash-enforced, all in `params.dat`. Full table in
[`../wpoa/docs/protocol-parameters.md`](../wpoa/docs/protocol-parameters.md).

| Flag | `params.dat` key | Default |
|---|---|---|
| `-enableweightengine` | `enable-weight-engine` | off |
| `-weightepochlength` | `weight-epoch-length` | 100 |
| `-weightkappa` | `weight-kappa` | 100.0 |
| `-weightalpha` | `weight-alpha` | 0.2 |
| `-weightlambda` | `weight-lambda` | 0.5, in `[0, 1)` |
| `-weighttreasuryaddress` | `weight-treasury-address` | empty → `R_k = 0` |
