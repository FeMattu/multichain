# `core/init.h` + `core/init.cpp` (wPoA parts)

> Documentation of the **node-startup integration** for wPoA. `init.cpp` is huge (it
> drives the entire MultiChain node bootstrap); here we document **only** the wPoA parts:
> the Phase 1 `-weight` handling + registration thread (§2.1-2.3), the Phase 2
> `-enablewpoa` (§2.4) and `-dumpfunction` (§2.5) flags, and the Phase 3a `-enablewpoavrf`
> (§2.6) flag. The rest is the standard MultiChain/Bitcoin startup engine.

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
  (Phase 1), `g_wpoa_enabled` and `g_dumping_function` (Phase 2), and `g_wpoa_vrf_enabled`
  (Phase 3a); it is the bridge between the user's configuration (`-weight`, `-enablewpoa`,
  `-dumpfunction`, `-enablewpoavrf`) and the wPoA subsystem.
- The read RPCs (in `rpclist.cpp`) are **independent** of this startup: they work even if
  the thread has not registered anything yet (they simply return 0 / an empty map).
- **`wpoa_selector.cpp`** defines `g_wpoa_enabled`, `g_dumping_function` and
  `g_wpoa_vrf_enabled`; `init.cpp` writes them all. The miner and validator read
  `g_wpoa_enabled` via `WPoAActiveAtHeight`, `g_dumping_function` once per election inside
  `WPoASelectProposer`, and `g_wpoa_vrf_enabled` via `WPoAVRFActiveAtHeight`.

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
- [rpc-registration.md](rpc-registration.md) — the (independent) RPC-command path.
- [phase1-implementation-guide.md](phase1-implementation-guide.md) §7.4 /
  [phase2-implementation-guide.md](phase2-implementation-guide.md) §7.5 /
  [phase3a-implementation-guide.md](phase3a-implementation-guide.md) §8.6 — the same
  integration from the design guides' perspective.
