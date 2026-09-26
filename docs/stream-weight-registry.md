# `stream_weight_registry.h` + `stream_weight_registry.cpp`

> **Type:** reference · **Register:** technical-direct · **Verified against the code:**
> 2026-09-25, commit `af06a6ef`
>
> Walkthrough of the **Phase 1 weight registry**: the `StreamWeightRegistry` facade over the
> `wpoa-weights` stream, its write path, its confirmed and height-scoped read paths, the
> self-publication rule, the activation latch and the static registration thread. The pure
> helpers it relies on are in [weight-record.md](weight-record.md); how it fits the whole
> system, in [wpoa-weight-engine-architecture.md §4.1](wpoa-weight-engine-architecture.md#41-phase-1-the-weight-registry).

These two files form a single logical compilation unit (interface + implementation)
and are documented together because they are tightly coupled:

| File | Role |
|------|------|
| `stream_weight_registry.h` | **Public interface** (declarations): the `StreamWeightRegistry` class, the constants, the globals `g_node_weight` and `g_wpoa_weights_enabled`, and the thread entry point `ThreadRegisterNodeWeight`. This is what the other files (`init.cpp`, `rpc/rpcwpoa.cpp`, the selector, the sortition and the weight engine) include in order to "see" the weight registry. |
| `stream_weight_registry.cpp` | **Implementation** (definitions): all the real logic for stream creation, subscription, publishing, reading and decoding of weight records. |

### Why the `.h` / `.cpp` split?

It is the classic C++ interface/implementation separation:

- **The header contains only declarations** (what exists) → it can be included by many
  files without duplicating code and without *multiple definition* errors at link time.
- **The `.cpp` contains the definitions** (how it works) → compiled once into a single
  `.o` object.

The header uses **forward declarations** instead of heavy `#include`s:

```cpp
struct mc_WalletTxs;
struct mc_EntityDetails;
```

This declares "these types exist" without pulling in all of their definitions (which
live in heavy MultiChain wallet headers). Since the header uses these types only as
**pointers** (`mc_WalletTxs*`, `mc_EntityDetails*`), the compiler only needs to know
they are types: the size of a pointer is known regardless. The full definitions are
included only in the `.cpp`, where they are actually needed. The result: a file that
includes the header (e.g. `rpclist.cpp`) compiles faster and does not depend on the
entire wallet subsystem.

---

## Table of contents
  - [Why the .h / .cpp split?](#why-the-h--cpp-split)
- [The class at a glance](#the-class-at-a-glance)
- [1. The header stream_weight_registry.h](#1-the-header-stream_weight_registryh)
  - [1.1 Includes and where they come from](#11-includes-and-where-they-come-from)
  - [1.2 The two constants (#define)](#12-the-two-constants-define)
  - [1.3 The StreamWeightRegistry class — the "facade"](#13-the-streamweightregistry-class--the-facade)
  - [1.4 Global elements declared in the header](#14-global-elements-declared-in-the-header)
- [2. The implementation stream_weight_registry.cpp](#2-the-implementation-stream_weight_registrycpp)
  - [2.1 Includes and what they bring](#21-includes-and-what-they-bring)
  - [2.2 The global variable and module-level constants](#22-the-global-variable-and-module-level-constants)
  - [2.3 Constructor, destructor and address resolution](#23-constructor-destructor-and-address-resolution)
  - [2.4 Stream management](#24-stream-management)
  - [2.5 Writing a record: PublishWeightRecord()](#25-writing-a-record-publishweightrecord)
  - [2.6 Orchestrating the write: RegisterLocalWeight()](#26-orchestrating-the-write-registerlocalweight)
  - [2.7 Reading records — the most delicate path](#27-reading-records--the-most-delicate-path)
  - [2.8 The public read methods (thin wrappers over ReadAllRecords)](#28-the-public-read-methods-thin-wrappers-over-readallrecords)
  - [2.9 The deferred registration thread](#29-the-deferred-registration-thread)
  - [2.10 The three RPC functions (defined in rpc/rpcwpoa.cpp)](#210-the-three-rpc-functions-defined-in-rpcrpcwpoacpp)
- [3. How this file connects to the others](#3-how-this-file-connects-to-the-others)
- [Related documents](#related-documents)

---
## The class at a glance

```mermaid
flowchart TD
    CTOR[Constructor: ResolveLocalAddress] --> STATE[Private state:<br/>m_pWalletTxs borrowed, m_StreamName,<br/>m_LocalAddress, m_Create, m_Subscribe]

    subgraph write [Write path]
        RLW[RegisterLocalWeight] --> ESR[EnsureStreamReady]
        ESR --> ESE[EnsureStreamExists → createcmd]
        ESR --> ESUB[EnsureSubscribed → subscribe]
        RLW --> IDEM{GetNodeWeight == weight?}
        IDEM -->|no| PWR[PublishWeightRecord → publishfrom]
    end

    subgraph read [Read path — one shared core]
        RAR[ReadAllRecords<br/>optional height bound] --> DEC[DecodeWeightRecord<br/>+ self-publication rule]
        RAR --> LATCH[(g_wpoa_ever_electable<br/>WPoAEverElectable)]
        GLW[GetLocalWeight] --> RAR
        GNW[GetNodeWeight] --> RAR
        GAN[GetAllNodesWeights] --> RAR
        GAS[GetAllNodesWeightsAsOf h] --> RAR
        GWE[GetAllNodesWeightsWithEpoch] --> RAR
        ILR[IsLocalWeightRegistered] --> RAR
        DPW[DebugPrintWeights] --> RAR
        WFL[WaitForLocalWeight] --> RAR
    end

    THREAD[ThreadRegisterNodeWeight<br/>background retry loop] --> RLW
    THREAD --> WFL
    WE[ThreadWeightEngine] --> ESR
    WE --> RLW
    WE --> GWE
    RPC[getlocalweight / getnodeweight / getallweights] --> GLW & GNW & GAN
    CONS[selector, sortition miner + validator,<br/>round audit RPCs] --> GAS
```

---

## 1. The header `stream_weight_registry.h`

### 1.1 Includes and where they come from

```cpp
#include <map>
#include <string>
#include <stdint.h>
#include "wpoa/stream_setup_state.h"  // mc_StreamSetupState
```

- `<map>` — `std::map`, the ordered key→value container from the **STL** (C++ Standard
  Template Library). Used for `std::map<std::string, uint32_t>` = address→weight map.
- `<string>` — `std::string`, also STL.
- `<stdint.h>` — the **standard C** header that defines the fixed-width integer types:
  `uint32_t` (32-bit unsigned integer, 0…4,294,967,295) and `int64_t` (64-bit signed
  integer). The weight is a `uint32_t`: it cannot be negative and 32 bits are more
  than enough.
- `"wpoa/stream_setup_state.h"` — the pure create/subscribe state machine shared by the
  three components that create streams on demand (this registry, the malus registry and
  the weight-engine reader). See [§2.4](#24-stream-management).

### 1.2 The two constants (`#define`)

```cpp
#define MC_WPOA_WEIGHTS_STREAM_NAME     "wpoa-weights"
#define MC_WPOA_DEFAULT_WEIGHT          100
```

- `MC_WPOA_WEIGHTS_STREAM_NAME` — the name of the append-only **MultiChain stream** on
  which weight records are written. A "stream" in MultiChain is an append-only registry
  of key/data items, native to the protocol.
- `MC_WPOA_DEFAULT_WEIGHT` — the default weight (100) used if the node does not pass
  `-weight` on the command line.

They are `#define`s (preprocessor macros) rather than `const`: this is the MultiChain
code style, which prefixes all global constants with `MC_`. They are substituted
textually by the preprocessor before compilation.

### 1.3 The `StreamWeightRegistry` class — the "facade"

The header describes it as a *"thin, opaque facade over the wpoa-weights stream"*.
**Facade** = a pattern that hides internal complexity (the MultiChain stream,
transactions, DB reads) behind a few simple methods. The rest of the node never touches
the stream directly: it uses only these public methods.

#### Public methods (the contract with the outside)

| Method | What it returns / does |
|--------|------------------------|
| `StreamWeightRegistry(mc_WalletTxs* pwalletIn)` | Constructor: resolves the local address and stores the stream name. |
| `bool RegisterLocalWeight(uint32_t weight, uint32_t epoch = 0)` | Registers this node's weight on the stream (creates stream + subscribes + publishes if needed). `epoch` is the epoch the value was computed **for**; the weight engine passes it, the static `-weight` path leaves it 0 — see [§2.5](#25-writing-a-record-publishweightrecord). |
| `bool EnsureStreamReady()` | Create the stream (closed) if missing, then subscribe. Public because the weight engine must call it **before** it has anything to publish ([§2.4](#24-stream-management)). |
| `uint32_t GetLocalWeight()` | Latest **confirmed** weight of this node, 0 if not registered. |
| `std::map<std::string,uint32_t> GetAllNodesWeights()` | address→weight map for every validator, over the whole confirmed prefix — the node's view *now*. Right for the read RPCs; **wrong** for anything that must reproduce a decision taken at a height. Forged records are already gone: see [§2.7](#27-reading-records--the-most-delicate-path). |
| `std::map<std::string,uint32_t> GetAllNodesWeightsAsOf(int max_block)` | The same map restricted to records confirmed at or before `max_block`. **The read every consensus path uses**, with `max_block = height - 1`, so the map is a function of the chain prefix. Negative means unbounded — the two share one implementation. |
| `int FirstPositiveWeightBlock()` | Height of the first block that confirmed a positive weight, or −1. Chain-derived; currently not called by any consensus path ([§2.7](#27-reading-records--the-most-delicate-path)). |
| `void GetAllNodesWeightsWithEpoch(std::map<std::string,uint32_t>& weights, std::map<std::string,uint32_t>& epochs)` | The same map, plus the epoch each value was published for. Consumed by the verifier, which can only compare a value against the epoch it claims. |
| `uint32_t GetNodeWeight(const std::string&)` | Confirmed weight of a specific address. |
| `bool IsLocalWeightRegistered()` | true if at least one confirmed record exists for this node. |
| `void DebugPrintWeights()` | Prints the entire registry state to the log. |
| `bool WaitForLocalWeight(...)` | Blocks until the published weight is confirmed on-chain (with a timeout). |
| `std::string GetLocalAddress() const` | Inline getter of the resolved local address. |

Note on `GetLocalAddress() const`: it is defined **inline in the header**
(`{ return m_LocalAddress; }`) and marked `const`, meaning it promises not to modify
the object's state. It is a simple getter, so there is no reason to put it in the `.cpp`.

#### Private members (internal state)

```cpp
mc_WalletTxs* m_pWalletTxs;   //!< "borrowed" pointer, not owned
std::string   m_StreamName;   //!< "wpoa-weights"
std::string   m_LocalAddress; //!< node address, computed once
mc_StreamSetupState m_Create;      //!< see wpoa/stream_setup_state.h
mc_StreamSetupState m_Subscribe;
```

- The `m_` prefix denotes "member" (MultiChain convention).
- `//!<` is a **Doxygen**-style comment ("documents the member to its left").
- **"borrowed pointer, not owned"**: `m_pWalletTxs` points to an object
  (`pwalletTxsMain`) created and destroyed elsewhere (in `init.cpp`). The destructor
  `~StreamWeightRegistry` does **not** free it — see the comment in the `.cpp`. This
  avoids a double-free.
- `m_Create` / `m_Subscribe` implement idempotency **and** bounded retry: each says,
  per tick, whether to issue the call, wait for one already in flight, or give up after
  `MC_WPOA_STREAM_SETUP_MAX_FAILURES` (20) failures ([§2.4](#24-stream-management)).

#### Private methods (hidden implementation details)

```cpp
void ResolveLocalAddress();
bool GetStreamEntity(mc_EntityDetails* entity);
bool EnsureStreamExists();
bool EnsureSubscribed();
bool PublishWeightRecord(uint32_t weight, uint32_t epoch);
bool ReadAllRecords(std::map<std::string, uint32_t>& out_latest,
                    std::map<std::string, uint32_t>* out_epochs = NULL,
                    int* out_first_positive_block = NULL,
                    int max_block = -1);
```

They are private because they are the "building blocks" used by the public methods: no
other file should be able to call them.

### 1.4 Global elements declared in the header

```cpp
void ThreadRegisterNodeWeight(uint32_t weight);
extern uint32_t g_node_weight;
extern bool g_wpoa_weights_enabled;
```

- `ThreadRegisterNodeWeight` — a free function (not a method) executed as a
  **background thread**, launched by `AppInit2` in `init.cpp` when the weights stream is
  on and the weight engine is off.
- `extern uint32_t g_node_weight` — `extern` means "this variable is **defined
  elsewhere**" (in the `.cpp`). The header only declares it, so several files can refer
  to the same global variable without duplicating it. The `g_` prefix = global.
- `extern bool g_wpoa_weights_enabled` — the Phase 1 gate, resolved once in `AppInit2`
  and forced on by any higher phase ([node-startup.md](node-startup.md)).
- The three RPC handlers (`getlocalweight`, `getallweights`, `getnodeweight`) are no longer
  declared here: like every handler they live in
  [`rpc/rpcwpoa.cpp`](../src/rpc/rpcwpoa.cpp) with prototypes in `rpc/rpcserver.h`
  ([§2.10](#210-the-three-rpc-functions-defined-in-rpcrpcwpoacpp)).
- `WPoAEverElectable()`, the activation latch this file maintains, is declared in
  `wpoa_selector.h` — its consumers are the selector's diversity hook and the miner.

---

## 2. The implementation `stream_weight_registry.cpp`

### 2.1 Includes and what they bring

```cpp
#include "wpoa/stream_weight_registry.h"
#include "rpc/rpcwallet.h"      // create/publish/subscribe, wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "structs/base58.h"     // CBitcoinAddress
#include "core/init.h"          // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"          // chainActive, cs_main, IsInitialBlockDownload
#include "utils/util.h"         // GetArg, LogPrintf, RenameThread, GetBoolArg
#include "utils/utiltime.h"     // MilliSleep, GetTime
#include "wpoa/weight_record.h" // mc_ParseWeightRecordJson, mc_AccumulateLatestWeight
#include "wpoa/wpoa_selector.h" // WPoAWeightRecordInScope
#include <boost/foreach.hpp>
```

Each include is the source of symbols used in the file:

- `rpcwallet.h` → declares the reused RPC handlers as C++ functions: `createcmd`,
  `subscribe`, `publish`. It also transitively pulls in `wallettxs.h` (types
  `mc_WalletTxs`, `mc_TxEntityStat`, `mc_TxEntityRow`, `mc_Buffer`) and `multichain.h`
  (`mc_gState`, `mc_EntityDetails`, constants `MC_ENT_TYPE_*`, `MC_TET_*`, `MC_AST_*`).
- `rpcutils.h` → `OpReturnFormatEntry`, the function that decodes an OP_RETURN payload
  into a `json_spirit::Value`.
- `base58.h` → `CBitcoinAddress`, the class that converts a public key / ID into an
  address string in Base58Check format.
- `init.h` → the global pointers `pwalletMain`, `pwalletTxsMain` and
  `ShutdownRequested()`.
- `main.h` → `chainActive` (the active chain), the global lock `cs_main`,
  `IsInitialBlockDownload()`.
- `util.h` → MultiChain utilities: `GetArg`/`GetBoolArg` (read CLI/config parameters),
  `LogPrintf` (log to `debug.log`), `RenameThread` (gives the thread an OS name).
- `utiltime.h` → `MilliSleep` (sleep in ms) and `GetTime` (UNIX timestamp in seconds).
- `weight_record.h` → the pure parsing/aggregation helpers and the self-publication
  predicate. See [weight-record.md](weight-record.md).
- `wpoa_selector.h` → `WPoAWeightRecordInScope`, the pure height-scope predicate of
  [§2.7](#27-reading-records--the-most-delicate-path), and the declaration of
  `WPoAEverElectable`.
- `<boost/foreach.hpp>` → the `BOOST_FOREACH` macro from the **Boost** library
  (included here because it is used indirectly; the main loop uses classic `for` loops).

```cpp
using namespace std;
using namespace json_spirit;
```

These bring STL symbols (`string`, `map`…) and json_spirit symbols (`Value`, `Object`,
`Array`, `Pair`) into scope without having to qualify them with their namespace.

### 2.2 The global variable and module-level constants

```cpp
uint32_t g_node_weight = MC_WPOA_DEFAULT_WEIGHT;   // THIS is the DEFINITION
bool g_wpoa_weights_enabled = false;
```

These are the **definitions** of the variables declared `extern` in the header.
`g_node_weight` is initialised to 100 and overwritten by `init.cpp` with the value of
`-weight`; `g_wpoa_weights_enabled` is resolved there from `params.dat` and the flags.

```cpp
static const int MC_WPOA_RETRY_INTERVAL_MS = 3000;   // how often the thread retries
static const int MC_WPOA_MAX_ATTEMPTS      = 200;    // ~10 minutes worst case
static const int MC_WPOA_CONFIRM_ATTEMPTS  = 20;     // 20*3s = ~60s waiting for confirmation
```

`static` at file scope = **visibility limited to this compilation unit** (internal
linkage): these do not collide with same-named symbols elsewhere. They are the timing
parameters of the registration thread. The bound on failed create/subscribe attempts is
not here: it is `MC_WPOA_STREAM_SETUP_MAX_FAILURES`, with the state machine it belongs to.

### 2.3 Constructor, destructor and address resolution

```cpp
StreamWeightRegistry::StreamWeightRegistry(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs         = pwalletIn;
    m_StreamName         = MC_WPOA_WEIGHTS_STREAM_NAME;
    m_LocalAddress       = "";
    ResolveLocalAddress();
}
```

The constructor stores the wallet-txs pointer, sets the stream name and immediately
computes the local address; `m_Create` and `m_Subscribe` start in their default
"act" state.

```cpp
StreamWeightRegistry::~StreamWeightRegistry()
{
    // m_pWalletTxs is borrowed, nothing to free.
}
```

Empty destructor: it confirms that the pointer is "borrowed".

#### `ResolveLocalAddress()` — who is this validator?

```cpp
void StreamWeightRegistry::ResolveLocalAddress()
{
    m_LocalAddress = "unknown";
    if (pwalletMain == NULL) { /* WARNING, use placeholder */ return; }

    CPubKey pkey;
    {
        LOCK(pwalletMain->cs_wallet);
        if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_MINE))
        {
            if (!pwalletMain->GetKeyFromAddressBook(pkey, MC_PTP_CONNECT))
            {
                pkey = pwalletMain->vchDefaultKey;
            }
        }
    }

    if (pkey.IsValid())
        m_LocalAddress = CBitcoinAddress(pkey.GetID()).ToString();
    else
        LogPrintf("... no valid node address, using placeholder\n");
}
```

Line by line:

- `CPubKey pkey;` — `CPubKey` is the MultiChain/Bitcoin class that represents an ECDSA
  **public key**.
- `LOCK(pwalletMain->cs_wallet);` — `LOCK` is a MultiChain macro (built on
  `boost::mutex`/`CCriticalSection`) that acquires a mutex for the duration of the `{}`
  scope. `cs_wallet` protects the wallet structures from concurrent access. It is
  needed because this function can be called both from an RPC (server thread) and from
  the background registration thread.
- **Address selection priority**: a wPoA weight belongs to a miner/validator, so the
  preference is:
  1. the **mining** address (`MC_PTP_MINE` = mine permission),
  2. otherwise the **connect** address (`MC_PTP_CONNECT` = connect permission),
  3. otherwise the wallet's **default key** (`vchDefaultKey`).

  `MC_PTP_*` are the MultiChain permission bits. `GetKeyFromAddressBook` looks up a key
  with that permission in the wallet.
- `pkey.IsValid()` — verifies that it is a valid key.
- `CBitcoinAddress(pkey.GetID()).ToString()` — `pkey.GetID()` produces a `CKeyID`
  (hash160 of the public key); `CBitcoinAddress(...)` wraps it and `.ToString()`
  serialises it into the readable Base58Check address format. This is the validator
  identifier used as the **key** in the stream.

### 2.4 Stream management

#### `GetStreamEntity()` — does the stream exist?

```cpp
bool StreamWeightRegistry::GetStreamEntity(mc_EntityDetails* entity)
{
    if (mc_gState == NULL || mc_gState->m_Assets == NULL) return false;
    if (mc_gState->m_Assets->FindEntityByName(entity, m_StreamName.c_str()) == 0) return false;
    return (entity->GetEntityType() == MC_ENT_TYPE_STREAM);
}
```

- `mc_gState` — the **MultiChain global state** (singleton), which holds all entities
  (assets, streams, etc.).
- `mc_gState->m_Assets` — the entity database (`mc_AssetDB`).
- `FindEntityByName(entity, name)` — looks up an entity by name; returns 0 if not found,
  fills `*entity` if found.
- `entity->GetEntityType() == MC_ENT_TYPE_STREAM` — confirms the found entity really is
  a stream and not, e.g., an asset with the same name.
- `m_StreamName.c_str()` — converts the `std::string` into a `const char*` C-string,
  as required by the MultiChain API.

#### `EnsureStreamExists()` — create the stream if missing

```cpp
mc_EntityDetails entity;
if (GetStreamEntity(&entity)) return true;      // already exists (also ends a multi-admin race)
if (m_Create.Next() != MC_SSA_ACT) return false; // in flight, or given up

Array params;
params.push_back(string("stream"));
params.push_back(m_StreamName);
params.push_back(false);

try {
    Value result = createcmd(params, false);
    m_Create.RecordBroadcast();                  // latch ONLY on a real broadcast
    LogPrintf("... create tx broadcast: %s\n", ..., result.get_str().c_str());
}
catch (const Object& objError)  { m_Create.RecordFailure(); /* no create permission / no funds yet */ }
catch (const std::exception& e) { m_Create.RecordFailure(); }
return false; // not usable until confirmed
```

Key points:

- It builds a json_spirit `Array` equivalent to the RPC parameters
  `create ["stream", "wpoa-weights", false]`. The trailing `false` makes the stream
  **closed**: publishing a weight record needs an explicit per-stream write permission,
  so weight updates stay confined to the consortium's authorized publishers rather than
  resting on convention (Def. 5.16). Grant a publisher with
  `grant <address> wpoa-weights.write`. Reading only needs a subscription. This is the
  same policy the `weight-engine-*` input streams use; the malus registry
  ([malus-registry.md](malus-registry.md)) is deliberately the opposite.
- `createcmd(params, false)` — calls the `create` RPC handler **directly in-process**
  (the same one invoked from the command line). The second parameter `false` = `fHelp`
  (we do not want the help, we want to execute). This is the central pattern:
  **writes reuse MultiChain's RPC handlers** rather than re-implementing transaction
  construction.
- **Double `catch`**: MultiChain RPC handlers throw a `json_spirit::Object` (the JSON-RPC
  error object) on a domain error, or a `std::exception` on a generic error. Both are
  caught.
- **Latch after the call, never before.** An earlier version set an "attempted" flag
  *before* `createcmd`, so a single transient throw — no `create` permission yet, no
  spendable output yet — was remembered as success and the stream never appeared. The
  state machine records a broadcast only when the call returned, counts failures, and
  gives up after `MC_WPOA_STREAM_SETUP_MAX_FAILURES` so a node that will never have
  `create` (every non-admin) stops trying. Unit-tested in the `activation` suite.
- It returns `false` even when the broadcast succeeds: the stream becomes usable **only
  once the `create` transaction is confirmed in a block**.

#### `EnsureSubscribed()` — does this node read the stream?

```cpp
mc_EntityDetails entity;
if (!GetStreamEntity(&entity)) return false;

mc_TxEntityStat entStat;
entStat.Zero();
memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
if (m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat)) return true;  // already subscribed

if (m_Subscribe.Next() != MC_SSA_ACT) return false;   // import still catching up

Array params;
params.push_back(m_StreamName);
try {
    subscribe(params, false);
    m_Subscribe.RecordBroadcast();
    return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
}
catch (...) { m_Subscribe.RecordFailure(); ... }
return false;
```

- `mc_TxEntityStat` — a struct that identifies an "entity" (here the stream) in the
  **wallet transaction database** (`mc_WalletTxs`). `Zero()` clears it.
- `entity.GetTxID()` returns the TXID (32 bytes) of the transaction that created the
  stream. `MC_AST_SHORT_TXID_OFFSET` and `MC_AST_SHORT_TXID_SIZE` extract the
  **short-txid** (a portion of the txid used as a compact stream identifier). The
  `memcpy` copies those bytes into `entStat`.
- `entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;` — combines two
  flags: `MC_TET_STREAM` (it is a stream) and `MC_TET_CHAINPOS` (indexed by chain
  position). The bitwise OR (`|`) merges the two flags into a single value.
- `WRPFindEntity` — looks the entity up in the wallet index: if found, the node is
  already subscribed.
- If not subscribed, it calls the RPC handler `subscribe(["wpoa-weights"])`. After the
  subscribe it re-checks, because for a short stream the import can complete
  immediately. A redundant subscribe would restart the stream rescan, hence the same
  state machine.

#### `EnsureStreamReady()` — create, then subscribe

```cpp
if (m_pWalletTxs == NULL || pwalletMain == NULL) return false;
if (!EnsureStreamExists()) return false;
return EnsureSubscribed();
```

Public, because **order** matters. `RegisterLocalWeight` calls it, but the weight engine
also calls it on every tick *before* its epoch gate. When the create was reachable only
from `RegisterLocalWeight`, it was sequenced after an event that needed the stream: a
clean network deadlocked, because nobody could publish a weight without the stream and
the stream was only created by a node that had a weight. Creating it early uses only the
`create` permission the genesis admin holds from block 1
([weight-engine.md §4](weight-engine.md#4-the-engine-thread)).

### 2.5 Writing a record: `PublishWeightRecord()`

```cpp
Object record;
record.push_back(Pair("timestamp", (int64_t)GetTime()));
record.push_back(Pair("node_address", m_LocalAddress));
record.push_back(Pair("weight", (int64_t)weight));
if (epoch > 0)                                 // omitted by the static -weight path
{
    record.push_back(Pair("epoch", (int64_t)epoch));
}

int height = 0;
{
    LOCK(cs_main);
    if (chainActive.Tip() != NULL) height = chainActive.Height();
}
record.push_back(Pair("height", height));

Object data_obj;
data_obj.push_back(Pair("json", record));

Array params;
params.push_back(m_LocalAddress);          // publishFROM this address
params.push_back(m_StreamName);
params.push_back(m_LocalAddress);          // ...and use it as the item key
params.push_back(data_obj);

try {
    Value result = publishfrom(params, false);
    LogPrintf("... Weight registered: %s = %u (tx %s)\n", ...);
    return true;
}
catch (...) { ... }
return false;
```

It builds the record's JSON payload:

- `Object` and `Pair` are json_spirit types. `Pair(name, value)` is a key/value pair;
  `Object` is the list of pairs.
- `GetTime()` → current UNIX timestamp (seconds). Cast to `int64_t` because json_spirit
  distinguishes 64-bit integers.
- `node_address` → the validator's address.
- `weight` → the weight (cast to `int64_t`).
- `height` → the current chain height. `chainActive.Tip()` is the top block;
  `chainActive.Height()` its height. Protected by `LOCK(cs_main)` because the chain can
  change concurrently.
- `epoch` → the epoch the weight was computed **for**, and the only field that is
  *conditional*. A weight is a claim about a specific epoch, so a verifier can only
  compare a published value against a recomputation of the *same* epoch; without the
  field, a value correctly published for epoch `e` would be checked against epoch `e+1`
  the moment the epoch rolled over, and an honest node would be flagged as wrong. The
  weight engine stamps it because it knows which epoch it computed for; the static
  `-weight` path omits it, because a hand-set weight is not derived from any epoch and
  there is nothing to recompute it against. Its absence therefore means *"not subject to
  value verification"* — which is correct in both cases, and keeps records written before
  the field was introduced readable.
- The record is wrapped in `{"json": <record>}`: this is the format MultiChain uses to
  represent a **UBJSON** datum in a stream item.

Finally it calls
`publishfrom([<address>, "wpoa-weights", <address-as-key>, {"json":{...}}])`. The stream
item's **key** is the node's address: this way each node writes records under its own key,
and reading the history shows each address's weight evolution.

> **`publishfrom`, not `publish` — and this is not cosmetic.** A weight record is
> **self-published**: the reader discards it unless the transaction's *signer* is the
> `node_address` in the payload (§2.7). Plain `publish` lets the wallet choose whichever
> address funds the transaction, which on a multi-address wallet need not be
> `m_LocalAddress` — the record would then be perfectly well-formed and silently discarded
> by every peer. Naming the address explicitly makes the signer and the declared node the
> same by construction. Full rationale:
> [weight-engine.md §5.1](weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others).

### 2.6 Orchestrating the write: `RegisterLocalWeight()`

```cpp
if (weight == 0) { /* ERROR: weight must be > 0 */ return false; }
if (m_pWalletTxs == NULL || pwalletMain == NULL) { /* ERROR wallet */ return false; }

if (!EnsureStreamReady()) return false;    // created/subscribed now, or awaiting confirmation

uint32_t current = GetNodeWeight(m_LocalAddress);
if (current == weight) { /* already registered */ return true; }   // IDEMPOTENCY

return PublishWeightRecord(weight, epoch);
```

Sequence: validate input → ensure stream → ensure subscription → **check idempotency**
(if the latest confirmed weight already equals it, do not re-publish) → publish. This
method is designed to be called repeatedly in a retry loop without side effects.

### 2.7 Reading records — the most delicate path

#### `DecodeWeightRecord()` (file-static function)

```cpp
static bool DecodeWeightRecord(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                               string& out_addr, uint32_t& out_weight, uint32_t& out_epoch,
                               std::vector<string>& out_publishers, bool& out_forged)
{
    mc_Script script; // local instance -> thread-safe (no shared buffer)

    for (int j = 0; j < (int)wtx.vout.size(); j++)
    {
        const CScript& spk = wtx.vout[j].scriptPubKey;
        if (spk.size() == 0) continue;
        CScript::const_iterator pc = spk.begin();

        script.Clear();
        script.SetScript((unsigned char*)(&pc[0]), (size_t)(spk.end() - pc), MC_SCR_TYPE_SCRIPTPUBKEY);

        if (!script.IsOpReturnScript())  continue;
        if (script.GetNumElements() == 0) continue;

        uint32_t format;
        unsigned char* chunk_hashes = NULL;
        int chunk_count = 0;
        int64_t total_chunk_size = 0;
        script.ExtractAndDeleteDataFormat(&format, &chunk_hashes, &chunk_count, &total_chunk_size);

        unsigned char short_txid[MC_AST_SHORT_TXID_SIZE];
        script.SetElement(0);
        if (script.GetEntity(short_txid) != 0) continue;
        if (memcmp(short_txid, stream_short_txid, MC_AST_SHORT_TXID_SIZE) != 0) continue;

        int n = script.GetNumElements();
        if (n < 1) continue;
        size_t data_size = 0;
        const unsigned char* data = script.GetData(n - 1, &data_size);
        if (data == NULL || data_size == 0) continue;

        string format_text;
        Value v = OpReturnFormatEntry(data, data_size, wtx.GetHash(), j, format, &format_text);
        if (mc_ParseWeightRecordJson(v, out_addr, out_weight, &out_epoch))
        {
            ExtractItemPublishers(wtx, j, out_publishers);

            // Self-publication: the signer must BE the node the record is about.
            if (!mc_StreamItemIsSelfAttested(out_addr, out_publishers))
            {
                out_forged = true;      // decodable, but published on another's behalf
                out_weight = 0;
                return false;           // DISCARD: never enters the weight map
            }
            return true;
        }
    }
    return false;
}
```

#### The self-publication rule (consensus-critical)

Parsing a record establishes only that it is **well formed**. A weight record describes
its own publisher's cluster, so it is valid only if the address that **signed** the
transaction is the `node_address` the payload declares. A record naming another cluster is
**discarded** — not flagged, not down-weighted — so it never reaches the weight map and no
node can publish a weight on another cluster's behalf. This is what makes it safe to grant
`wpoa-weights.write` to **every** node rather than to one designated publisher per cluster.

- `ExtractItemPublishers(...)` recovers the signing addresses from the transaction's
  **input scripts**, mirroring MultiChain's own extraction in `StreamItemEntry1`
  ([`rpcwalletutils.cpp`](../src/rpc/rpcwalletutils.cpp)): for each input it recovers the
  address embedded in the `scriptSig` and keeps it only when the signature commits to the
  whole transaction (`SIGHASH_ALL`) or to this very output (`SIGHASH_SINGLE` at the same
  index) — a signature committing to neither does not authenticate this item. A payload
  field can claim anything; an input signature cannot.
- `mc_StreamItemIsSelfAttested(...)` ([`weight_record.h`](../src/wpoa/weight_record.h)) is the rule
  itself, and it is the **same** predicate `weight-engine-membership` applies. One
  implementation, shared by both layers: two copies of a consensus-critical predicate
  could drift into a node discarding a record it does not accuse, or vice versa.
- It **fails closed**: an item whose signer cannot be recovered is rejected. The evidence
  — a single transaction — is always available, so its absence means the record is
  undecodable rather than merely unverified.
- `out_forged` distinguishes *"discarded because it was published on another's behalf"*
  from *"this output is not one of our items"*. `ReadAllRecords` logs the former
  unconditionally (not only under `-wpoadebug`): it is a provable protocol violation and
  the evidence a malus accusation is built on.

This rule answers only **who wrote** a record. Whether the **value** is correct is a
separate, independently decidable question, answered by re-running the whole weight
pipeline over the public inputs — see
[weight-engine.md §5.1](weight-engine.md#51-every-node-publishes-its-own-weight-and-every-node-checks-the-others).

`static` = a function visible only in this file. It extracts `(address, weight)` from a
stream-item transaction. Steps:

- `CWalletTx` — a transaction as stored in the wallet; `wtx.vout` is the vector of
  outputs.
- `CScript` / `scriptPubKey` — the output's locking script. A stream item's data travels
  in an **OP_RETURN** output.
- `mc_Script` — the MultiChain script parser. **It is created locally inside the
  function**: this is the key to thread-safety, because it avoids sharing global temporary
  buffers between different threads (the comment stresses this).
- `SetScript(...)` — loads the raw scriptPubKey bytes into the parser. The cast
  `(unsigned char*)(&pc[0])` takes the byte pointer, `spk.end() - pc` the length,
  `MC_SCR_TYPE_SCRIPTPUBKEY` the type.
- `IsOpReturnScript()` — skips outputs that are not OP_RETURN (e.g. the change output).
- `ExtractAndDeleteDataFormat(...)` — removes the data-format meta element (mirroring
  `StreamItemEntry`, the MultiChain function that formats items).
- `SetElement(0)` + `GetEntity(short_txid)` — element 0 of the OP_RETURN must identify
  the stream. `memcmp` compares the short-txid with our stream's: if different, the item
  belongs to another stream → skip.
- `GetData(n-1, &data_size)` — the last element holds the item's data (in Phase 1,
  on-chain records only).
- **`OpReturnFormatEntry(...)`** — the critical point. It decodes the bytes into a
  `json_spirit::Value`. The comment explains why the **6-argument overload** is used
  (with `format_text` as an out-parameter): this directly produces `{"json": {...}}`,
  exactly as `StreamItemEntry`/`liststreamitems` do. The 3-argument overload would
  instead wrap it as `{"format":"json","formatdata":{"json":{...}}}`, and
  `mc_ParseWeightRecordJson` would reject it because there is no `"json"` key at the top
  level. **This discrepancy was the cause of the bug** where decoding silently failed
  for every item (cf. the "stream read bug fix" commit). See
  [multichain-internals.md](multichain-internals.md) §5.
- Finally `mc_ParseWeightRecordJson(v, out_addr, out_weight, &out_epoch)` (from `weight_record.h`)
  extracts the address, weight and optional epoch. If it succeeds, the self-publication
  rule below decides whether the record is kept.

#### `ReadAllRecords()` — the read core

```cpp
bool ReadAllRecords(std::map<std::string, uint32_t>& out_latest,
                    std::map<std::string, uint32_t>* out_epochs = NULL,
                    int* out_first_positive_block = NULL,
                    int max_block = -1);

static const bool dbg = GetBoolArg("-wpoadebug", false);
out_latest.clear();
if (m_pWalletTxs == NULL) { ...; return false; }

mc_EntityDetails entity;
if (!GetStreamEntity(&entity)) { ...; return false; } // stream not created

mc_TxEntityStat entStat;
entStat.Zero();
memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
```

`static const bool dbg` — read **once** (because of `static`) from the `-wpoadebug`
flag. It enables verbose tracing logs.

Then the fundamental part, explained by a long comment in the code:

```cpp
bool found;
m_pWalletTxs->Lock();
found = m_pWalletTxs->FindEntity(&entStat);
m_pWalletTxs->UnLock();
if (!found) return false; // not subscribed
```

**Why `FindEntity` and not `WRPFindEntity`?** (the key design difference)

- The **WRP\*** family (`WRPGetListSize`/`WRPGetList`/`WRPGetWalletTx`) reads from a
  *snapshot* whose position (`m_ReadLastPos`) is advanced **only** inside the RPC
  read-lock protocol: a reader must hold `WRPReadLock()` and the snapshot advances on the
  writer side via `WRPSync()`. A self-contained reader that does **not** participate in
  that protocol (this background thread, and read RPCs that do not take the WRP read
  lock) would see a **stale** snapshot and report 0 items forever, even after the publish
  tx is mined.
- The **non-WRP** methods (`FindEntity`/`GetListSize`/`GetList`/`GetWalletTx`) self-lock
  via `Lock(0,0)` and read the **live** position (`m_LastPos`), so they see every
  confirmed item as soon as its block connects.
- `FindEntity` does not lock internally, so it must be guarded manually with
  `Lock()`/`UnLock()`.

This is the reason for the note in the header: *"We deliberately do NOT use the WRP\*
read family."* See [multichain-internals.md](multichain-internals.md) §4.

```cpp
int confirmed = 0;
int total = m_pWalletTxs->GetListSize(&entStat.m_Entity, entStat.m_Generation, &confirmed);
if (confirmed <= 0) return true; // subscribed but no confirmed items -> empty map
```

`GetListSize` returns in its return value the total (including unconfirmed mempool
items) and, via the **out-param** `&confirmed`, the number of **confirmed** items
(`m_LastClearedPos`). Only the confirmed ones are used: **a weight registry that feeds
consensus must be identical on every node**, whereas the mempool differs per node. A
weight only "counts" when it is on-chain.

```cpp
mc_Buffer rows;
rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

int list_err = m_pWalletTxs->GetList(&entStat.m_Entity, entStat.m_Generation, 1, confirmed, &rows);
if (list_err != MC_ERR_NOERROR) return false;
```

- `mc_Buffer` — a generic MultiChain buffer; `Initialize` tells it the key size and row
  size (`sizeof(mc_TxEntityRow)`).
- `GetList(entity, generation, 1, confirmed, &rows)` — reads items from position **1**
  up to `confirmed`, i.e. **only the confirmed prefix**, in **ascending** order (oldest
  to newest).

```cpp
const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

for (int i = 0; i < rows.GetCount(); i++)
{
    mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);

    if (er->m_Flags & MC_TFL_IS_EXTENSION) continue;   // skip extension (chunked) rows
    if (!WPoAWeightRecordInScope(er->m_Block, max_block)) continue;   // height scope

    uint256 hash;
    memcpy(hash.begin(), er->m_TxId, MC_TDB_TXID_SIZE);

    int err = MC_ERR_NOERROR;
    mc_TxDefRow txdef;
    CWalletTx wtx = m_pWalletTxs->GetWalletTx(hash, &txdef, &err);
    if (err != MC_ERR_NOERROR) continue;

    string addr; uint32_t w = 0; uint32_t rec_epoch = 0;
    std::vector<string> publishers; bool forged = false;
    bool decoded = DecodeWeightRecord(wtx, stream_short_txid, addr, w, rec_epoch,
                                      publishers, forged);
    if (forged)
    {
        // Logged UNCONDITIONALLY, not only under -wpoadebug: a provable protocol
        // violation, and the evidence the malus registry accuses on (§2.7).
        LogPrintf("[wPoA] wpoa-weights record for '%s' DISCARDED: not signed by that "
                  "address ...", addr.c_str(), ...);
        continue;
    }
    if (decoded)
    {
        mc_AccumulateLatestWeight(out_latest, addr, w);   // newest wins
        if (out_epochs != NULL) (*out_epochs)[addr] = rec_epoch;
        if (w > 0 && !g_wpoa_ever_electable)
        {
            g_wpoa_ever_electable = true;                 // the activation latch
            LogPrintf("[wPoA] ACTIVATED: the registry now carries a positive weight ...");
        }
        if (out_first_positive_block != NULL && w > 0 && er->m_Block >= 0)
            /* keep the lowest such block */;
    }
}
return true;
```

- Each row (`mc_TxEntityRow`) represents a stream item.
- `MC_TFL_IS_EXTENSION` — the flag for extension rows (chunked/off-chain items). Since we
  only publish small on-chain JSON, these never occur; they are skipped defensively.
- `uint256` — the Bitcoin type for 256-bit hashes. The TXID is reconstructed from the
  row bytes.
- `GetWalletTx(hash, &txdef, &err)` — retrieves the full transaction from the wallet.
- `DecodeWeightRecord(...)` — extracts `(addr, w, epoch)` and the signing addresses, as
  seen above, and reports through `forged` whether the record was published on somebody
  else's behalf.
- **`forged` short-circuits the accumulation.** A forged record is dropped *before* it can
  reach the map, so no consumer of `GetAllNodesWeights()` ever has to know about the rule:
  by the time a weight is visible it has already been checked. The log line is
  unconditional because it is the evidence an accusation is built on.
- `out_epochs` is optional (`NULL` when the caller only wants the weights). Filling it is
  what lets the verifier compare a value against the epoch it actually claims.
- **The height scope** is applied before decoding, so a row outside it cannot influence
  the newest-wins fold. `WPoAWeightRecordInScope(record_block, max_block)` is pure:
  unbounded (`max_block < 0`) admits everything; under a bound, a row with no block of its
  own (`m_Block < 0`) is excluded, because a record with no height cannot be shown to
  precede one, and guessing would reintroduce the per-node divergence the bound removes.
  Bounding by the parent height is self-enforcing: to evaluate a block at `h+1` a node must
  hold its parent, and holding the parent means holding every transaction confirmed at or
  before `h`.
- **The activation latch.** `g_wpoa_ever_electable` flips the first time any read meets a
  positive weight, and never flips back; `WPoAEverElectable()` exposes it. It is a plain
  `bool` on purpose: its consumers (the miner's native fallback and the mining-diversity
  hook) run on paths that already hold locks, and an earlier version that asked the chain
  directly hung the node there. Semantics:
  [weight-engine.md §4bis](weight-engine.md#4bis-deferred-activation--when-wpoa-actually-takes-over).
  Because it is set by *any* read — scoped or not — and reset on restart, it is node-local
  state rather than a function of the prefix;
  [wpoa-weight-engine-architecture.md §10](wpoa-weight-engine-architecture.md#10-known-limits-and-open-points)
  records this as an open point, together with the chain-derived alternative that
  `out_first_positive_block` / `FirstPositiveWeightBlock()` already compute.
- **`mc_AccumulateLatestWeight(out_latest, addr, w)`** — because we iterate in ascending
  order (old→new), overwriting the per-address map makes the **last record win**. This
  helper lives in `weight_record.h`.

### 2.8 The public read methods (thin wrappers over `ReadAllRecords`)

They all call `ReadAllRecords` and then filter/aggregate:

```cpp
uint32_t GetNodeWeight(addr)          → look up addr in the map, return weight or 0
uint32_t GetLocalWeight()             → same but for m_LocalAddress, with a WARNING if 0
std::map GetAllNodesWeights()         → the whole map (and log sum/count) — unscoped
std::map GetAllNodesWeightsAsOf(h)    → the whole map, records confirmed at or before h
void GetAllNodesWeightsWithEpoch(w,e) → the map plus each record's epoch
int FirstPositiveWeightBlock()        → first block with a positive weight, or -1
bool IsLocalWeightRegistered()        → true if m_LocalAddress is in the map
void DebugPrintWeights()              → formatted print of the whole registry
```

`GetAllNodesWeights()` is `GetAllNodesWeightsAsOf(-1)` in all but name: one implementation,
so the scoped and unscoped reads cannot drift apart. Every consensus caller — the Phase 2
selector, the sortition miner via `WPoABuildRoundContext`, the sortition validator, and the
round audit RPCs — uses the scoped form with `height - 1`.

`WaitForLocalWeight(weight, max_attempts, interval_ms)`:

```cpp
for (int i = 0; i < max_attempts; i++)
{
    if (ShutdownRequested()) return false;
    std::map<std::string,uint32_t> weights;
    ReadAllRecords(weights);
    auto it = weights.find(m_LocalAddress);
    if (it != weights.end() && it->second == weight) return true;
    MilliSleep(interval_ms);
}
return false;
```

Polling: it re-reads the state every `interval_ms` until this node's confirmed weight
equals the expected value, with a shutdown guard. It exists so the thread can print the
debug dump with the **confirmed** value rather than 0.

### 2.9 The deferred registration thread

```cpp
static bool NodeReadyForWeightRegistration()
{
    { LOCK(cs_main); if (chainActive.Tip() == NULL) return false; }   // need a tip
    if (GetBoolArg("-offline", false)) return true;                   // offline: OK right away
    return !IsInitialBlockDownload();                                 // otherwise wait for IBD to finish
}
```

The node is "ready" when a chain tip exists and (unless `-offline`) the **Initial Block
Download** has finished. Deliberately **not** requiring peers: a single permitted miner
produces blocks on its own.

```cpp
void ThreadRegisterNodeWeight(uint32_t weight)
{
    RenameThread("mc-wpoa-weight");
    if (pwalletTxsMain == NULL || pwalletMain == NULL) { ...; return; }

    StreamWeightRegistry registry(pwalletTxsMain);
    int attempts = 0;

    while (!ShutdownRequested())
    {
        MilliSleep(MC_WPOA_RETRY_INTERVAL_MS);
        if (ShutdownRequested()) break;
        if (!NodeReadyForWeightRegistration()) continue;   // gate, does not count as an attempt

        attempts++;
        if (registry.RegisterLocalWeight(weight))
        {
            if (registry.WaitForLocalWeight(weight, MC_WPOA_CONFIRM_ATTEMPTS, MC_WPOA_RETRY_INTERVAL_MS))
                LogPrintf("... Weight confirmed on-chain\n");
            else
                LogPrintf("... Weight submitted; awaiting a block ...\n");
            registry.DebugPrintWeights();
            return;   // success -> the thread terminates
        }

        if (attempts >= MC_WPOA_MAX_ATTEMPTS) { ...; return; }  // give up
    }
}
```

- `RenameThread("mc-wpoa-weight")` — gives the thread a name (useful in `top`/debug).
- It creates **only one** `StreamWeightRegistry` instance, so the `m_Create` /
  `m_Subscribe` state persists across attempts.
- A retry loop with `MilliSleep` between passes; it exits on the first success or after
  `MC_WPOA_MAX_ATTEMPTS` (200) attempts (~10 minutes). The readiness gate does not consume
  attempts.
- After a successful `RegisterLocalWeight`, it waits for on-chain confirmation and prints
  the dump.

### 2.10 The three RPC functions (defined in `rpc/rpcwpoa.cpp`)

They are **not** in this file: like every other handler in the node they live under
`src/rpc/`, in [`rpc/rpcwpoa.cpp`](../src/rpc/rpcwpoa.cpp), and are registered in
`rpclist.cpp`. They are documented here because they are thin callers of the class
above — each one builds a `StreamWeightRegistry` and reads it.

Common structure (example `getlocalweight`):

```cpp
Value getlocalweight(const Array& params, bool fHelp)
{
    if (fHelp || params.size() != 0)
        throw runtime_error("getlocalweight\n...help...");
    if (pwalletTxsMain == NULL)
        throw JSONRPCError(RPC_WALLET_ERROR, "Wallet not available");

    StreamWeightRegistry registry(pwalletTxsMain);
    Object obj;
    obj.push_back(Pair("address",    registry.GetLocalAddress()));
    obj.push_back(Pair("weight",     (int64_t)registry.GetLocalWeight()));
    obj.push_back(Pair("registered", registry.IsLocalWeightRegistered()));
    return obj;
}
```

- **Standard RPC signature**: `Value f(const Array& params, bool fHelp)`.
- If `fHelp` is true or the arguments are wrong, it throws `runtime_error` with the help
  text (the RPC server intercepts it and shows it to the user).
- `JSONRPCError(code, message)` — a helper that builds the JSON-RPC error object;
  `RPC_WALLET_ERROR` is a standard code.
- Each handler creates a `StreamWeightRegistry` **on the fly** (reading `pwalletTxsMain`),
  queries the public methods and packs the result into a json_spirit `Object`.

The other two:

- `getallweights` — returns `{validators, total, weights:{addr:weight,...}}`, summing the
  weights.
- `getnodeweight "address"` — requires 1 argument (`params.size() != 1`), reads
  `params[0].get_str()` and returns `{address, weight}`.

---

## 3. How this file connects to the others

```mermaid
flowchart TD
    CLI[-weight CLI] --> INIT

    subgraph initcpp [core/init.cpp - AppInit2]
        INIT[validate -weight<br/>g_node_weight = value<br/>create_thread ThreadRegisterNodeWeight]
    end

    INIT -->|launches, engine off| THREAD[ThreadRegisterNodeWeight<br/>this file, uses StreamWeightRegistry]
    INIT -->|launches, engine on| WET[ThreadWeightEngine<br/>weight_engine.cpp]

    THREAD -->|writes| WR[createcmd / subscribe / publishfrom<br/>rpcwallet.h — RPC handlers]
    WET -->|EnsureStreamReady, RegisterLocalWeight w,e| WR
    THREAD -->|reads and parsing| WREC[weight_record.h<br/>mc_ParseWeightRecordJson<br/>mc_AccumulateLatestWeight<br/>mc_StreamItemIsSelfAttested]

    RPCLIST[rpc/rpcwpoa.cpp handlers, registered by rpc/rpclist.cpp] -.->|getlocalweight / getallweights / getnodeweight| THREAD
    SEL[wpoa_selector.cpp, private_sortition.cpp] -.->|GetAllNodesWeightsAsOf h-1| THREAD
```

- **`core/init.h`** declares `pwalletMain`, `pwalletTxsMain`, `ShutdownRequested()` that
  this file uses; **`core/init.cpp`** reads `-weight`, sets `g_node_weight` and launches
  `ThreadRegisterNodeWeight`. → see [node-startup.md](node-startup.md).
- **`weight_record.h`** provides the two pure parsing/aggregation helpers used by
  `DecodeWeightRecord`/`ReadAllRecords`. → see [weight-record.md](weight-record.md).
- **`rpc/rpcwpoa.cpp`** defines the three RPC handlers over this class, and
  **`rpc/rpclist.cpp`** registers them in the server dispatcher. →
  see [rpc-registration.md](rpc-registration.md).
- **`rpcwallet.h`** provides the `createcmd`/`subscribe`/`publishfrom` handlers reused for
  writes. → see [multichain-internals.md](multichain-internals.md) §6.
- **`wpoa_selector.cpp`** and **`private_sortition.cpp`** read the scoped map for every
  election; **`weight_engine.cpp`** publishes through this class and reads the map with
  epochs to verify it. → see [wpoa-selector.md](wpoa-selector.md),
  [private-sortition.md](private-sortition.md), [weight-engine.md](weight-engine.md).

---

## Related documents

- [../src/wpoa/README.md](../src/wpoa/README.md) — feature entry point and architecture diagram.
- [phase1-implementation-guide.md](phase1-implementation-guide.md) — the original design rationale (historical).
- [multichain-internals.md](multichain-internals.md) — the host APIs this class calls.
- [weight-record.md](weight-record.md) — the pure helpers used on the read path.
