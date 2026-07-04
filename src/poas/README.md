# wPoA — Phase 1: Stream Weight Registry

This module implements **Phase 1** of a Weighted Proof-of-Authority (wPoA)
selector for MultiChain: an append-only registry of per-validator *weights*,
stored on a native MultiChain stream and exposed through a small, opaque API.

Nodes never see the internal mechanism (stream layout, transaction plumbing,
indexes). They only use:

- the startup parameter `-weight=<n>`, and
- the RPC commands `getlocalweight`, `getallweights`, `getnodeweight`.

Files:

| File | Purpose |
|------|---------|
| `stream_weight_registry.h`   | Public API (`StreamWeightRegistry`, deferred thread, RPC decls) |
| `stream_weight_registry.cpp` | Implementation |
| `README.md`                  | This document |

---

## 1. High-level design

```
                          startup (-weight=N)
                                  │
        AppInit2 ─────────────────┼──── validates N>0, stores g_node_weight
                                  │
                                  ▼
                    ThreadRegisterNodeWeight(N)         (background thread)
                                  │
                 wait until node ready (tip + synced + peers)
                                  │
        RegisterLocalWeight(N) ───┼── EnsureStreamExists()  → create   (tx)
                                  ├── EnsureSubscribed()    → subscribe
                                  └── PublishWeightRecord() → publish   (tx)
                                              │
                       ┌──────────────────────┴───────────────────────┐
                       ▼                                               ▼
              stream "wpoa-weights"  (append-only, on-chain)   debug.log output
                       ▲
                       │  low-level, self-locking reads (any thread)
     GetLocalWeight / GetNodeWeight / GetAllNodesWeights / DebugPrintWeights
                       ▲
                       │
        RPC: getlocalweight · getnodeweight · getallweights
```

### Why a background thread instead of a synchronous startup publish?

Writing to a stream is a **blockchain transaction**. It requires a loaded and
unlocked wallet, an address with the right permissions, funds for the fee, the
target stream to already exist and be confirmed, and network connectivity so the
transaction can propagate and be mined. None of that is guaranteed the moment
`AppInit2` finishes. Equally, a record only becomes *readable* once its
transaction is mined **and** imported into the local stream subscription.

So registration is **deferred**: a background thread waits until the node is
ready and then registers, retrying as needed. Startup is never blocked, and the
read API degrades gracefully (returns `0` / an empty map) until data is
confirmed.

### Two mechanisms, chosen deliberately

- **Writes** reuse MultiChain's in-process RPC handlers (`createcmd`,
  `subscribe`, `publish` from `rpc/rpcserver.h`). This reuses all of
  MultiChain's permission, fee and validation logic. These handlers do not
  require an RPC worker slot, so they are safe to call from our thread.
- **Reads** use the low-level `mc_WalletTxs` WRP API
  (`WRPFindEntity` → `WRPGetListSize` → `WRPGetList` → `WRPGetWalletTx`), which
  is self-locking and slot-free, therefore callable from **any** thread. The RPC
  read commands are just thin wrappers so operators can query weights on demand.

---

## 2. Data model

One stream, `wpoa-weights` (created on first use). Each item:

- **key** = the publishing node's address (enables per-node lookups),
- **data** = a JSON object:

```json
{
  "timestamp": 1751630400,
  "node_address": "1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD",
  "weight": 100,
  "height": 42
}
```

The stream is **append-only**. The *current* weight of a node is the value in
its **most recent** record. Because `GetList` returns items in chain order
(oldest → newest), the reader simply overwrites a per-address map while
iterating, so the newest record wins.

---

## 3. Critical functions (pseudocode)

### RegisterLocalWeight(weight)
```
if weight == 0: log error; return false
if not EnsureStreamExists(): return false      # created now or awaiting confirmation
if not EnsureSubscribed():   return false      # subscription import in progress
if GetNodeWeight(local) == weight:             # idempotent: nothing changed
    return true
return PublishWeightRecord(weight)             # publish {"json": {...}}, key=address
```

### ReadAllRecords(out_map)  — the read core
```
entity = FindEntityByName("wpoa-weights")      # false ⇒ stream not created yet
build mc_TxEntityStat from entity short-txid, type = STREAM|CHAINPOS
if not WRPFindEntity(stat): return false        # not subscribed
total = WRPGetListSize(stat)
if total == 0: return true                      # subscribed but empty
rows = WRPGetList(stat, from=1, count=total)    # ascending
for each row:
    wtx = WRPGetWalletTx(row.txid)
    if DecodeWeightRecord(wtx, short_txid → (addr, weight)):
        out_map[addr] = weight                  # newest wins
```

### DecodeWeightRecord(wtx, stream_short_txid → addr, weight)
```
for each vout:
    parse scriptPubKey into mc_Script
    if not OP_RETURN: continue
    ExtractAndDeleteDataFormat()                 # strip format meta element
    if element[0] entity != stream_short_txid: continue
    data = element[last]                          # on-chain item payload
    value = OpReturnFormatEntry(data, format)     # {"json": {...}} for UBJSON
    addr, weight = value.json.node_address, value.json.weight
```

---

## 4. Public API (`StreamWeightRegistry`)

| Method | Meaning |
|--------|---------|
| `RegisterLocalWeight(w)` | Ensure stream + subscription, then publish the local weight if changed. |
| `GetLocalWeight()` | Latest confirmed weight for this node (`0` if none). |
| `GetNodeWeight(addr)` | Latest confirmed weight for `addr` (`0` if none). |
| `GetAllNodesWeights()` | `map<address, weight>` for every validator. |
| `IsLocalWeightRegistered()` | Whether this node has a confirmed record. |
| `DebugPrintWeights()` | Log the full registry state. |

The node's own address is resolved as: mining address (`MC_PTP_MINE`) →
connect address (`MC_PTP_CONNECT`) → wallet default key.

---

## 5. RPC commands

```
getlocalweight
  → { "address": "...", "weight": n, "registered": true|false }

getnodeweight "address"
  → { "address": "...", "weight": n }

getallweights
  → { "validators": n, "total": n, "weights": { "addr": w, ... } }
```

---

## 6. Building

The module is compiled into `libbitcoin_wallet`. Because `src/Makefile.am` was
changed, regenerate the build files before compiling:

```bash
cd /home/mattu/multichain
./autogen.sh          # or: autoreconf -i
./configure           # your usual flags
make
```

---

## 7. Manual test (3 nodes: weights 100, 80, 50)

1. Start node A (chain admin) with `-weight=100`. It creates `wpoa-weights`,
   subscribes, and — once a block confirms the create — publishes its record.
2. Start nodes B (`-weight=80`) and C (`-weight=50`), each connected to the
   chain and granted `connect,send,receive` (and `mine` if they validate).
3. After the registration transactions are mined, on any node:

```bash
multichain-cli <chain> getallweights
```

Expected (order may vary):

```json
{
  "validators": 3,
  "total": 230,
  "weights": {
    "1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD": 100,
    "1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2": 80,
    "1dice8EMCQAqQxWhZgWmwBYz4MPnPCfQNV": 50
  }
}
```

`DebugPrintWeights()` (emitted to `debug.log` after successful registration)
prints:

```
[StreamWeightRegistry] ════════════════════════════════════════
[StreamWeightRegistry] === WEIGHT REGISTRY DEBUG LOG ===
[StreamWeightRegistry] Stream: wpoa-weights
[StreamWeightRegistry] Local Node Address: 1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD
[StreamWeightRegistry] Local Weight: 100
[StreamWeightRegistry] ────────────────────────────────────────
[StreamWeightRegistry] All Registered Nodes:
[StreamWeightRegistry]   1A1z7agoat3FwzZqK6YXYaSJKcqF5L5KvD: 100
[StreamWeightRegistry]   1BvBMSEYstWetqTFn5Au4m4GFg7xJaNVN2: 80
[StreamWeightRegistry]   1dice8EMCQAqQxWhZgWmwBYz4MPnPCfQNV: 50
[StreamWeightRegistry] Total Weight (sum): 230
[StreamWeightRegistry] Number of Validators: 3
[StreamWeightRegistry] ════════════════════════════════════════
```

### Notes / expected behaviour
- Weights **do not change on restart** unless `-weight` is changed: the
  idempotency check skips re-publishing an unchanged weight; a changed value
  appends a new record that then wins.
- Immediately after a fresh publish, the record is unconfirmed and may not yet
  appear in reads — this is expected; it shows up once mined and imported.

---

## 8. Edge cases handled

| Situation | Behaviour |
|-----------|-----------|
| Stream does not exist | Created automatically (once) on first registration. |
| Node not subscribed | Subscribed automatically before reads. |
| Stream empty | `GetAllNodesWeights()` returns an empty map. |
| Node never registered | `GetLocalWeight()` returns `0` with a warning. |
| `-weight <= 0` | Startup fails with `InitError`. |
| No valid node address | Placeholder address + warning; registration is skipped. |
| Concurrent writers | Stream order is preserved by the chain; newest record wins. |

---

## 9. Limitations & future work

- **Phase 1 is registry-only** — weights are recorded and queried, but not yet
  used to bias block production / validator selection (that is Phase 2).
- On-chain records only (no off-chain / large payloads).
- No authorization beyond MultiChain stream write permissions: any writer can
  publish its own weight. A future phase should restrict who may set weights
  (e.g. admin-signed updates) and add **dynamic weights**, **slashing**, and
  weight decay.
- Re-registration appends a new record rather than mutating in place (inherent
  to append-only streams); a trimming/checkpoint strategy may be added later.
```
