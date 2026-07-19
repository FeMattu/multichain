# `core/init.h` + `core/init.cpp` (wPoA parts)

> **⚠ Updated in protocol 20014 — the wPoA switches are now chain parameters.**
> The per-section walkthrough below (§2.4-§2.8) describes the *original* model, in
> which each phase was a standalone runtime flag read with `GetBoolArg(...)`. That
> single resolution block has since been replaced. The current behaviour is:
>
> - **Every wPoA switch is a `params.dat` chain parameter** (defined in
>   [`chainparams/paramlist.h`](../../chainparams/paramlist.h), relevant from protocol
>   `20014`, `MC_PRM_NOHASH`): `enablewpoa` (master), `enablewpoaweights`,
>   `enablewpoaselection`, `dumpfunction`, `enablewpoavrf`, `enablewpoarandao`,
>   `wpoarandaolookback`, `enablewpoasortition`, `wpoasortitiondelay`. They are set at
>   `multichain-util create` time (or edited into `params.dat`) and **inherited** by
>   every node that joins — a fresh node needs no wPoA command-line flags.
> - **`AppInit2` resolves each phase** as: explicit runtime `-enablewpoa*` flag → else
>   the runtime master `-enablewpoa`/`-wpoaenable` (on/off) → else the inherited
>   `params.dat` value. The runtime flag overriding the inherited value logs a
>   consensus-fork warning.
> - **The `-enablewpoa` master switch** (creation-time master expansion lives in
>   [`chainparams/params.cpp`](../../chainparams/params.cpp) `Read`) turns the whole
>   protocol on; specific `-enablewpoa*` flags override it per phase.
> - **Dependency constraints are hard failures** (both at creation and startup):
>   `weights → selection → vrf → randao → sortition`, and sortition needs `k≥1`.
> - **Phase 1 (the weights stream) is gated** on `enablewpoaweights` / `g_wpoa_weights_enabled`
>   (default off) — the registration thread only launches when it is on. It is forced
>   on whenever any higher phase is active.
>
> See the **Startup configuration** section of [`../README.md`](../README.md) and the
> `/* MCHN START - wPoA startup resolution */` block in `init.cpp` for the authoritative
> current logic; the code snippets below are retained for phase-by-phase background.

> Documentation of the **node-startup integration** for wPoA. `init.cpp` is huge (it
> drives the entire MultiChain node bootstrap); here we document **only** the wPoA parts:
> the Phase 1 `-weight` handling + registration thread (§2.1-2.3), the Phase 2
> `-enablewpoaselection` (§2.4) and `-dumpfunction` (§2.5) flags, the Phase 3a `-enablewpoavrf`
> (§2.6) flag, the Phase 3b `-enablewpoarandao` / `-wpoarandaolookback` (§2.7) flags, and
> the Phase 4 `-enablewpoasortition` / `-wpoasortitiondelay` (§2.8) flags.
> The rest is the standard MultiChain/Bitcoin startup engine.

`init.h` and `init.cpp` are documented together because they form the classic
interface/implementation pair: `init.h` declares the global symbols that the other
modules (including `stream_weight_registry.cpp`) use; `init.cpp` defines them and
contains `AppInit2`, the startup function.

## 1. What `init.h` provides to the weight subsystem

`init.h` is the header that `stream_weight_registry.cpp` includes
(`#include "core/init.h"`) to access three things:

```cpp
extern CWallet* pwalletMain;          // the main wallet
extern mc_WalletTxs* pwalletTxsMain;  // the wallet transaction DB
...
bool ShutdownRequested();             // true once shutdown has been requested
```

- `pwalletMain` — global pointer to the wallet (`CWallet`). `ResolveLocalAddress()` uses
  it to derive the validator address. `extern` = declared here, defined in the `.cpp`.
- `pwalletTxsMain` — global pointer to the wallet transaction database (`mc_WalletTxs`).
  It is the "borrowed" pointer passed to the `StreamWeightRegistry` constructor and used
  for all reads (`FindEntity`/`GetList`/`GetWalletTx`).
- `ShutdownRequested()` — used by the `ThreadRegisterNodeWeight` thread and by
  `WaitForLocalWeight` to break out of their loops when the node is shutting down.

The **forward declarations** at the top of the header:
```cpp
class CWallet;
struct mc_WalletTxs;
```
declare the types without including their heavy definitions (the same principle explained
in [stream-weight-registry.md](stream-weight-registry.md)): the header only needs to use
them as pointers.

Also note:
```cpp
bool AppInit2(boost::thread_group& threadGroup, int OutputPipe=STDOUT_FILENO);
```
This is the signature of the node's startup function. The parameter
`boost::thread_group& threadGroup` is Boost's **thread container** into which all of the
node's background threads are registered — and it is there that the weight-registration
thread will be attached.

## 2. The integration in `init.cpp`

### 2.1 The include (line 43)

```cpp
#include "wpoa/stream_weight_registry.h"
```
This brings into `init.cpp` the constant `MC_WPOA_DEFAULT_WEIGHT`, the variable
`g_node_weight` and the function `ThreadRegisterNodeWeight` — everything needed to start
registration.

### 2.2 The help text for the `-weight` parameter (line 564)

Inside `HelpMessage(...)` (the function that generates the `--help` text):

```cpp
strUsage += "  -weight=<n>                              "
    + strprintf(_("wPoA validator weight for this node, positive integer "
                  "(default: %u). Registered on the wpoa-weights stream."),
                MC_WPOA_DEFAULT_WEIGHT) + "\n";
```

- `strUsage += ...` — accumulates lines of help text.
- `_( "..." )` — the Bitcoin/MultiChain **translation** (i18n) macro: it marks the string
  as translatable.
- `strprintf(...)` — a type-safe version of `sprintf` that returns a `std::string`; `%u`
  is replaced with `MC_WPOA_DEFAULT_WEIGHT` (100).

Effect: `multichaind --help` documents the `-weight` parameter.

### 2.3 The registration block (lines 3171-3191)

This is the point where, at the end of `AppInit2`, the node configures and starts weight
registration:

```cpp
/* MCHN START - wPoA weight registry (Phase 1) */
#ifdef ENABLE_WALLET
    {
        int64_t weight_arg = GetArg("-weight", MC_WPOA_DEFAULT_WEIGHT);
        if (weight_arg <= 0)
        {
            return InitError(strprintf(_("Invalid -weight value %d: must be a positive integer."), weight_arg));
        }
        g_node_weight = (uint32_t)weight_arg;
        LogPrintf("[StreamWeightRegistry] Node weight configured: %u\n", g_node_weight);

        if (pwalletMain && pwalletTxsMain && !fDisableWallet)
        {
            threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight));
        }
    }
#endif
/* MCHN END */
```

Line-by-line analysis:

- **`#ifdef ENABLE_WALLET` … `#endif`** — a preprocessor directive: the whole block is
  compiled **only** if the wallet is enabled. The weight requires a wallet (to sign and
  pay for the create/publish transactions). Consistently, in `rpclist.cpp` the three RPCs
  are also inside `#ifdef ENABLE_WALLET`.

- **`{ ... }`** — the brace scope creates a local block so the variables (`weight_arg`)
  do not pollute the rest of `AppInit2`.

- **`GetArg("-weight", MC_WPOA_DEFAULT_WEIGHT)`** — reads the `-weight` parameter from the
  command line / config file. If absent, it uses the default 100. It returns an `int64_t`
  so it can detect negative/zero values before the cast.

- **`if (weight_arg <= 0) return InitError(...)`** — validation: the weight must be
  strictly positive. `InitError(msg)` is the standard MultiChain helper that logs the
  error, shows it to the user and fails startup (returns `false` from `AppInit2`).
  `strprintf` with `%d` inserts the invalid value into the message.

- **`g_node_weight = (uint32_t)weight_arg;`** — sets the global variable (defined in
  `stream_weight_registry.cpp`, declared `extern` in its header). From this moment the
  rest of the system knows the configured weight. The cast is safe because
  `weight_arg > 0` is already guaranteed.

- **`LogPrintf(...)`** — logs the configured weight to `debug.log`.

- **`if (pwalletMain && pwalletTxsMain && !fDisableWallet)`** — launches the thread only
  if the wallet is actually available and not disabled at runtime (`fDisableWallet`).
  Without a wallet you could not publish, so there is no point starting the thread.

- **`threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight))`**
  — the heart of the integration:
  - `boost::bind(&ThreadRegisterNodeWeight, g_node_weight)` creates a **functor** (a
    callable object) that, when invoked, runs `ThreadRegisterNodeWeight(g_node_weight)`.
    `boost::bind` "freezes" the argument `g_node_weight` into the call.
  - `threadGroup.create_thread(...)` creates a new system thread that runs that functor
    and registers it in the node's `boost::thread_group` (so it will be joined/interrupted
    cleanly at shutdown).
  - **Why a separate thread?** The comment explains it: registration is a *transaction*,
    so it can only happen once the wallet, permissions, stream and network connectivity
    are ready. Running it inline would block node startup. By delegating it to a
    background thread, `AppInit2` returns immediately and the thread retries until the
    conditions are met (cf. `NodeReadyForWeightRegistration` in
    [stream-weight-registry.md](stream-weight-registry.md)).

- **`/* MCHN START */ ... /* MCHN END */`** — marker comments used throughout the
  MultiChain codebase to delimit MultiChain additions from the original Bitcoin code.

### 2.4 wPoA Phase 2: the `-enablewpoa` flag (lines 3183-3187)

Phase 2 adds a second `#include` and one more parse step **inside the same
`#ifdef ENABLE_WALLET` block**, right after the `-weight` handling and before the
registration thread is launched:

```cpp
#include "wpoa/wpoa_selector.h"   // init.cpp:44 — g_wpoa_enabled

// ... inside AppInit2, after the -weight handling:
// wPoA Phase 2: weighted proposer selection. Default off — when unset the
// node keeps its native round-robin mining-diversity behavior unchanged.
g_wpoa_enabled = GetBoolArg("-enablewpoa", false);
LogPrintf("[wPoA] Weighted proposer selection %s\n",
          g_wpoa_enabled ? "ENABLED (-enablewpoa=1)" : "disabled (native mining-diversity)");
```

Line-by-line:

- **`#include "wpoa/wpoa_selector.h"`** — brings in the declaration
  `extern bool g_wpoa_enabled;` (and the selector functions, though `init.cpp` only
  writes the flag).
- **`GetBoolArg("-enablewpoa", false)`** — reads the boolean flag from the command
  line / config file, defaulting to `false`. `GetBoolArg` treats `-enablewpoa`,
  `-enablewpoa=1`, `-enablewpoa=true` as true and an absent flag as the default.
- **`g_wpoa_enabled = ...`** — sets the global defined in `wpoa_selector.cpp`. This is
  the **single** write of the flag; it happens on the init thread before any miner or
  validator thread reads it, so it needs no lock. From here on
  `WPoAActiveAtHeight` (and therefore the miner and validator) can see whether wPoA is
  enabled.
- **`LogPrintf("[wPoA] ...")`** — records the effective mode at startup, so an operator
  can confirm from `debug.log` whether the node is running the weighted-selection path or
  the native one.

Why here, next to `-weight`? Both are the node's wPoA configuration knobs, both are
wallet-gated (`#ifdef ENABLE_WALLET`), and both must be resolved before the node starts
mining/validating. As of Phase 3a, `HelpMessage` also documents `-enablewpoa` (and
`-enablewpoavrf`, §2.6) — the two `strUsage += "  -enablewpoa …"` /
`"  -enablewpoavrf …"` lines were added next to the `-weight`/`-dumpfunction` lines, so
`multichaind --help` now lists every wPoA flag.

Unlike `-weight`, `-enablewpoa` launches **no thread**: it only flips a boolean that the
miner (`miner/miner.cpp`) and validator (`protocol/multichainblock.cpp`) consult at
runtime. See [miner-integration.md](miner-integration.md) and
[block-validation.md](block-validation.md).

### 2.5 wPoA Phase 2: the `-dumpfunction` flag

The final wPoA knob, parsed in the same `#ifdef ENABLE_WALLET` block right after
`-enablewpoa`, chooses the **weight-dumping (damping) function**: the transform applied to
every validator weight *before* the Efraimidis–Spirakis draw. Its purpose is to stop a
single large stake ("whale") from dominating proposer selection and to keep any one
validator's win share from growing without bound as its weight climbs. See
[wpoa-selector.md §2.2](wpoa-selector.md) for the math.

```cpp
// wPoA Phase 2: weight-dumping (damping) function. ... Default "none" = raw weights.
std::string dump_arg = GetArg("-dumpfunction", "none");
if (boost::iequals(dump_arg, "none"))      g_dumping_function = DUMP_NONE;
else if (boost::iequals(dump_arg, "sqrt")) g_dumping_function = DUMP_SQRT;
else if (boost::iequals(dump_arg, "log"))  g_dumping_function = DUMP_LOG;
else return InitError(strprintf(_("Invalid -dumpfunction value '%s': must be none, sqrt or log."), dump_arg));
LogPrintf("[wPoA] Weight-dumping function: %s\n", ...);
```

Line-by-line:

- **`GetArg("-dumpfunction", "none")`** — reads the parameter as a **string** (the
  `std::string`-defaulted `GetArg` overload), defaulting to `"none"`. String values
  (`none`/`sqrt`/`log`) are chosen over opaque integers so a `multichain.conf` entry is
  self-documenting.
- **`boost::iequals(...)`** — case-insensitive compare (from
  `boost/algorithm/string/predicate.hpp`, already included), so `SQRT`, `Sqrt` and `sqrt`
  are all accepted. Each branch sets the global `g_dumping_function` (defined in
  `wpoa_selector.cpp`, declared `extern` in its header — like `g_wpoa_enabled`).
- **`else return InitError(...)`** — an unrecognized value **fails startup** rather than
  silently falling back. This is deliberate: the dumping function is **consensus-critical**
  (every node must agree, or the elected proposer differs and the chain forks), so a typo
  must be loud, not a silent divergence. This mirrors the strict validation of `-weight`.
- **`LogPrintf(...)`** — records the effective transform (`none`/`sqrt`/`log`) at startup so
  an operator can confirm it from `debug.log`; the selector also echoes it on every
  election under `-debug=wpoa`.

Like `-enablewpoa`, `-dumpfunction` launches **no thread** — it only sets a global that the
selector core reads once per election (via `WPoASelectProposer`, the sole reader). It is
wallet-gated for the same reason: it is only meaningful on a node that participates in wPoA.

> **Operational note.** Because it is consensus-critical, `-dumpfunction` must be set
> **identically on every mining/validating node** and, in practice, fixed for the life of
> the chain (or coordinated at a known height). It is a *node* configuration flag today,
> not a chain parameter, so nothing enforces cross-node agreement automatically — the same
> accepted-risk category as `-enablewpoa`.

### 2.6 wPoA Phase 3a: the `-enablewpoavrf` flag

Phase 3a adds the VRF randomness beacon (see
[phase3a-implementation-guide.md](phase3a-implementation-guide.md)). Its only startup
footprint is one more boolean, parsed in the **same `#ifdef ENABLE_WALLET` block**, right
after `-enablewpoavrf`'s sibling flags:

```cpp
// wPoA Phase 3a: VRF randomness beacon. Default off. When enabled, each
// wPoA-elected proposer publishes a verifiable pseudorandom reveal in its
// block and every peer verifies it. Must be uniform across the validator
// set (like -enablewpoa) or nodes disagree on block validity.
g_wpoa_vrf_enabled = GetBoolArg("-enablewpoavrf", false);
LogPrintf("[wPoA] VRF randomness beacon %s\n",
          g_wpoa_vrf_enabled ? "ENABLED (-enablewpoavrf=1)" : "disabled");
```

Line-by-line:

- **`GetBoolArg("-enablewpoavrf", false)`** — reads the boolean flag, defaulting to
  `false`. `GetBoolArg` treats `-enablewpoavrf`, `-enablewpoavrf=1`, `-enablewpoavrf=true`
  as true and an absent flag as the default. So a Phase-2 or plain node is byte-for-byte
  unchanged.
- **`g_wpoa_vrf_enabled = …`** — sets the global defined in `wpoa_selector.cpp` and declared
  `extern` in `wpoa_selector.h` (see [wpoa-selector.md §5](wpoa-selector.md)). This is the
  **single** write of the flag; it happens on the init thread before any miner or validator
  thread reads it, so it needs no lock. From here `WPoAVRFActiveAtHeight` — and therefore
  the prover ([vrf-prover.md](vrf-prover.md)) and verifier ([vrf-verifier.md](vrf-verifier.md))
  — can see whether the beacon is on.
- **`LogPrintf("[wPoA] VRF randomness beacon …")`** — records the effective mode at startup
  so an operator can confirm from `debug.log` whether the beacon is running.

There is also a `HelpMessage` line, added next to the `-enablewpoa` one:

```cpp
strUsage += "  -enablewpoavrf                           "
    + _("Enable the wPoA VRF randomness beacon: each elected proposer publishes a "
        "verifiable pseudorandom reveal, verified by peers (default: 0). Requires "
        "-enablewpoa; must be identical on all nodes.") + "\n";
```

Like `-enablewpoa`/`-dumpfunction`, `-enablewpoavrf` launches **no thread**: it only flips
a boolean that the prover (`miner/miner.cpp`) and verifier (`protocol/multichainblock.cpp`)
consult at runtime. It is **consensus-affecting** and must be set identically across the
validator set — the same accepted-risk category as `-enablewpoa`. It only has an effect
where wPoA already governs the height, because `WPoAVRFActiveAtHeight` = the flag **AND**
`WPoAActiveAtHeight` (so `-enablewpoavrf` without `-enablewpoa` does nothing).

### 2.7 wPoA Phase 3b: the `-enablewpoarandao` / `-wpoarandaolookback` flags

Phase 3b adds the RANDAO beacon seed (see
[phase3b-implementation-guide.md](phase3b-implementation-guide.md)). Its startup footprint is
a boolean plus an integer lookback, parsed in the **same `#ifdef ENABLE_WALLET` block**, right
after the `-enablewpoavrf` handling:

```cpp
// wPoA Phase 3b: RANDAO accumulator + lookback selection seed. Default off.
// When enabled, selection is seeded by H(R_tot[n-k] ‖ h[n-1] ‖ n) over the
// accumulated Phase-3a reveals instead of the plain previous block hash. It
// REQUIRES -enablewpoavrf (it consumes those reveals); a lone flag stays inert.
g_wpoa_randao_enabled = GetBoolArg("-enablewpoarandao", false);
int64_t randao_k = GetArg("-wpoarandaolookback", MC_WPOA_DEFAULT_RANDAO_LOOKBACK);
if (randao_k < 0 || randao_k > 1000000)
    return InitError(strprintf(_("Invalid -wpoarandaolookback value %d: must be a non-negative integer."), randao_k));
g_wpoa_randao_lookback = (int)randao_k;
if (g_wpoa_randao_enabled && !g_wpoa_vrf_enabled)
    LogPrintf("[wPoA] WARNING: -enablewpoarandao set without -enablewpoavrf; "
              "the RANDAO beacon has no reveals to accumulate and stays inert.\n");
LogPrintf("[wPoA] RANDAO beacon seed %s (lookback k=%d)\n",
          g_wpoa_randao_enabled ? "ENABLED (-enablewpoarandao=1)" : "disabled",
          g_wpoa_randao_lookback);
```

Line-by-line:

- **`GetBoolArg("-enablewpoarandao", false)`** — the on/off switch, defaulting to `false`, so a
  Phase-3a or plain node is byte-for-byte unchanged.
- **`GetArg("-wpoarandaolookback", MC_WPOA_DEFAULT_RANDAO_LOOKBACK)`** — the lookback `k`
  (default `1`), read as an integer and **validated** (`0 ≤ k ≤ 1e6`); an out-of-range value is
  a fatal `InitError` rather than a silent fork risk. It is **consensus-critical** — every node
  must run the same `k`.
- **`g_wpoa_randao_enabled` / `g_wpoa_randao_lookback = …`** — the two globals defined in
  `randao_accumulator.cpp` and declared `extern` in `randao_accumulator.h`
  (see [randao-accumulator.md](randao-accumulator.md)). Written once on the init thread before
  any miner/validator thread reads them, so they need no lock. From here
  `WPoARANDAOActiveAtHeight` — and therefore `WPoARandaoSelectionSeed` at both selection call
  sites — can see whether the beacon seed is on.
- **The `!g_wpoa_vrf_enabled` warning** — a lone `-enablewpoarandao` has nothing to accumulate
  (`WPoARANDAOActiveAtHeight` = the flag **AND** `WPoAVRFActiveAtHeight`), so it stays inert;
  the warning makes the misconfiguration visible in `debug.log`.

Two `HelpMessage` lines are added next to the `-enablewpoavrf` one:

```cpp
strUsage += "  -enablewpoarandao                        "
    + _("Enable the wPoA RANDAO beacon seed: seed proposer selection from the accumulated "
        "per-block VRF reveals instead of the previous block hash (default: 0). Requires "
        "-enablewpoavrf; must be identical on all nodes.") + "\n";
strUsage += "  -wpoarandaolookback=<k>                  "
    + strprintf(_("wPoA RANDAO lookback distance k in seed[n+1]=H(R_tot[n-k] | h[n-1] | n) "
        "(default: %u). Must be identical on all nodes."), MC_WPOA_DEFAULT_RANDAO_LOOKBACK) + "\n";
```

Like the other wPoA flags, these launch **no thread**: they only set globals the miner and
validator consult at runtime. Both are **consensus-affecting** and must be uniform across the
validator set — the same accepted-risk category as `-enablewpoa`/`-enablewpoavrf`.

### 2.8 wPoA Phase 4: the `-enablewpoasortition` / `-wpoasortitiondelay` flags

Phase 4 adds private (VRF-scored) sortition — the security fix (see
[phase4-implementation-guide.md](phase4-implementation-guide.md)). Its startup footprint is a
boolean plus a floating-point delay scale, parsed in the **same `#ifdef ENABLE_WALLET` block**,
right after the `-enablewpoarandao` handling:

```cpp
// wPoA Phase 4: private (VRF-scored) sortition. Default off. Consumes the beacon
// seed as its public VRF input, so it REQUIRES -enablewpoarandao; a lone flag stays
// inert. The delay scale enters the validator's time bar and must match on all nodes.
g_wpoa_sortition_enabled = GetBoolArg("-enablewpoasortition", false);

std::string sortition_delay_arg =
    GetArg("-wpoasortitiondelay", strprintf("%g", (double)MC_WPOA_DEFAULT_SORTITION_DELAY));
char* end = NULL;
double sortition_delay = strtod(sortition_delay_arg.c_str(), &end);
if (end == sortition_delay_arg.c_str() || *end != '\0' ||
    !(sortition_delay >= 0.0) || sortition_delay > PrivateSortition::MaxDelaySeconds())
    return InitError(strprintf(_("Invalid -wpoasortitiondelay value '%s': ..."), sortition_delay_arg));
g_wpoa_sortition_delay = sortition_delay;

if (g_wpoa_sortition_enabled)
{
    if (!g_wpoa_randao_enabled)
        LogPrintf("[wPoA] WARNING: -enablewpoasortition set without -enablewpoarandao; "
                  "private sortition has no beacon seed to score and stays inert.\n");
    else if (g_wpoa_randao_lookback < 1)
        return InitError(_("wPoA private sortition requires -wpoarandaolookback >= 1: ... circular."));
}
LogPrintf("[wPoA] Private sortition %s (delay scale=%g s)\n",
          g_wpoa_sortition_enabled ? "ENABLED (-enablewpoasortition=1)" : "disabled",
          g_wpoa_sortition_delay);
```

Line-by-line:

- **`GetBoolArg("-enablewpoasortition", false)`** — the on/off switch, defaulting to `false`, so
  a Phase 3b (public-election) node is byte-for-byte unchanged.
- **`-wpoasortitiondelay`** — the delay scale `s` in `delay = s · score · Σf(w)`, read as a
  string and parsed with `strtod` so a fractional value is accepted; validated to be a finite,
  non-negative number `≤ PrivateSortition::MaxDelaySeconds()`. It is **consensus-critical** (it
  enters the validator's time bar), so every node must run the same value.
- **`g_wpoa_sortition_enabled` / `g_wpoa_sortition_delay = …`** — the two globals defined in
  `private_sortition.cpp` and declared `extern` in `private_sortition.h`
  (see [private-sortition.md](private-sortition.md)). Written once on the init thread, so no lock.
- **The `!g_wpoa_randao_enabled` warning** — a lone `-enablewpoasortition` has no beacon seed to
  evaluate (`WPoASortitionActiveAtHeight` = the flag **AND** `WPoARANDAOActiveAtHeight`), so it
  stays inert; the warning makes the misconfiguration visible.
- **The `k >= 1` fatal check** — the **circularity guard**: the sortition reveal `R[n]` feeds
  `R_tot[n]` while its own seed reads `R_tot[n-k]`, so `k = 0` would make the selection seed
  circular. When sortition is on, `k = 0` is a fatal `InitError`, not a silent fork risk.

Two `HelpMessage` lines are added next to the `-wpoarandaolookback` one, describing
`-enablewpoasortition` and `-wpoasortitiondelay`. Like the other wPoA flags they launch **no
thread**; both are consensus-affecting and must be uniform across the validator set.

## 3. The complete startup flow

```mermaid
flowchart TD
    START([multichaind -weight=250]) --> APP

    subgraph app [AppInit2 — init.cpp]
        INIT1[initialise wallet, chain, RPC ...]
        GETARG["GetArg(-weight, 100) → weight_arg = 250"]
        VAL{weight_arg greater than 0?}
        SETG[g_node_weight = 250<br/>writes the global in stream_weight_registry.cpp]
        LAUNCH[threadGroup.create_thread<br/>ThreadRegisterNodeWeight, 250]
        INIT1 --> GETARG --> VAL
        VAL -->|no| ERR[InitError → startup fails]
        VAL -->|yes| SETG --> LAUNCH
    end

    LAUNCH -->|launches background thread| THREAD[ThreadRegisterNodeWeight 250<br/>stream_weight_registry.cpp]
    THREAD --> LOOP[loop: wait for readiness → RegisterLocalWeight 250<br/>→ create / subscribe / publish on wpoa-weights]
```

## 4. Links to the other files

- **`init.h` → `stream_weight_registry.cpp`**: provides `pwalletMain`, `pwalletTxsMain`,
  `ShutdownRequested()` used by the registry.
- **`stream_weight_registry.h` → `init.cpp`**: provides `MC_WPOA_DEFAULT_WEIGHT`,
  `g_node_weight` and `ThreadRegisterNodeWeight` used in the startup block.
- **`init.cpp`** is the **only** place that launches the thread and sets `g_node_weight`
  (Phase 1), `g_wpoa_enabled` and `g_dumping_function` (Phase 2), `g_wpoa_vrf_enabled`
  (Phase 3a), `g_wpoa_randao_enabled` / `g_wpoa_randao_lookback` (Phase 3b), and
  `g_wpoa_sortition_enabled` / `g_wpoa_sortition_delay` (Phase 4); it is the bridge between the
  user's configuration (`-weight`, `-enablewpoa`, `-dumpfunction`, `-enablewpoavrf`,
  `-enablewpoarandao`, `-wpoarandaolookback`, `-enablewpoasortition`, `-wpoasortitiondelay`) and
  the wPoA subsystem.
- The read RPCs (in `rpclist.cpp`) are **independent** of this startup: they work even if
  the thread has not registered anything yet (they simply return 0 / an empty map).
- **`wpoa_selector.cpp`** defines `g_wpoa_enabled`, `g_dumping_function` and
  `g_wpoa_vrf_enabled`; **`randao_accumulator.cpp`** defines `g_wpoa_randao_enabled` and
  `g_wpoa_randao_lookback`; `init.cpp` writes them all. The miner and validator read
  `g_wpoa_enabled` via `WPoAActiveAtHeight`, `g_dumping_function` once per election inside
  `WPoASelectProposer`, `g_wpoa_vrf_enabled` via `WPoAVRFActiveAtHeight`, and the Phase 3b
  globals via `WPoARANDAOActiveAtHeight` / `WPoARandaoSelectionSeed`.

---

## Related documents

- [../README.md](../README.md) — feature entry point and architecture diagram.
- [stream-weight-registry.md](stream-weight-registry.md) — the thread and class this
  startup launches (Phase 1).
- [wpoa-selector.md](wpoa-selector.md) — the selector core that reads `g_wpoa_enabled`
  (Phase 2) and defines the `g_wpoa_vrf_enabled` / `WPoAVRFActiveAtHeight` glue (Phase 3a,
  §5).
- [miner-integration.md](miner-integration.md) / [block-validation.md](block-validation.md)
  — the runtime consumers of the `-enablewpoa` flag.
- [vrf-prover.md](vrf-prover.md) / [vrf-verifier.md](vrf-verifier.md) — the runtime
  consumers of the `-enablewpoavrf` flag (Phase 3a).
- [randao-accumulator.md](randao-accumulator.md) — the accumulator/seed core and glue that
  consume the `-enablewpoarandao` / `-wpoarandaolookback` flags (Phase 3b).
- [rpc-registration.md](rpc-registration.md) — the (independent) RPC-command path.
- [phase1-implementation-guide.md](phase1-implementation-guide.md) §7.4 /
  [phase2-implementation-guide.md](phase2-implementation-guide.md) §7.5 /
  [phase3a-implementation-guide.md](phase3a-implementation-guide.md) §8.6 /
  [phase3b-implementation-guide.md](phase3b-implementation-guide.md) §7.5 — the same
  integration from the design guides' perspective.
