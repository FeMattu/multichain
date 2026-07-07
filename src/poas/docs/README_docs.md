# Documentazione tecnica wPoA — Fase 1 (Weight Registry)

Questa cartella contiene la spiegazione tecnica dettagliata dei file che implementano la **gestione del peso** dei validatori nel sistema wPoA (Weighted Proof of Authority) di MultiChain.

## Indice dei documenti

| Documento | File coperti | Profondità |
|-----------|--------------|------------|
| [stream_weight_registry.md](stream_weight_registry.md) | `poas/stream_weight_registry.h` + `.cpp` | **Approfondito** — cuore della gestione peso |
| [weight_record.md](weight_record.md) | `poas/weight_record.h` | **Approfondito** — parsing/aggregazione record |
| [init.md](init.md) | `core/init.h` + `init.cpp` (parte wPoA) | Integrazione all'avvio |
| [rpclist.md](rpclist.md) | `rpc/rpclist.cpp` (parte wPoA) | Minimo — registrazione comandi RPC |

## Mappa d'insieme dei collegamenti

```
              ┌──────────────────────────────────────────────┐
   -weight ──►│  core/init.cpp / init.h                       │
              │  configura g_node_weight, lancia il thread     │
              └───────────────┬──────────────────────────────┘
                              │ ThreadRegisterNodeWeight
                              ▼
   ┌───────────────────────────────────────────────────────────┐
   │  poas/stream_weight_registry.h + .cpp                       │
   │  classe StreamWeightRegistry (facade sullo stream)          │
   │  • scritture: create / subscribe / publish (RPC riusate)    │
   │  • letture:   FindEntity / GetList / GetWalletTx (non-WRP)   │
   │  • 3 handler RPC: getlocalweight/getallweights/getnodeweight │
   └───────┬───────────────────────────────────┬─────────────────┘
           │ parsing/aggregazione              │ registrazione RPC
           ▼                                   ▼
   ┌───────────────────────┐        ┌───────────────────────────┐
   │  poas/weight_record.h │        │  rpc/rpclist.cpp          │
   │  parsing puro JSON     │        │  tabella vRPCCommands     │
   └───────────────────────┘        └───────────────────────────┘
```

## Ordine di lettura consigliato

1. **[stream_weight_registry.md](stream_weight_registry.md)** — capire la classe centrale e il flusso scrittura/lettura.
2. **[weight_record.md](weight_record.md)** — il dettaglio del parsing usato dalle letture.
3. **[init.md](init.md)** — come il nodo avvia la registrazione all'avvio.
4. **[rpclist.md](rpclist.md)** — come i comandi RPC vengono esposti al client.

## Concetti trasversali (validi per tutti i documenti)

- **Separazione `.h`/`.cpp`**: header = dichiarazioni (cosa esiste), `.cpp` = definizioni (come funziona). Le *forward declaration* nell'header evitano include pesanti.
- **`extern` / definizione unica**: le globali (`g_node_weight`, `pwalletMain`, `pwalletTxsMain`) sono dichiarate `extern` negli header e definite una sola volta in un `.cpp`.
- **`#ifdef ENABLE_WALLET`**: tutto il codice pesi è condizionato alla presenza del wallet, perché registrare un peso è una transazione.
- **Riuso degli handler RPC**: le scritture non reimplementano la costruzione delle transazioni ma chiamano in-process `createcmd`/`subscribe`/`publish`.
- **Solo item confermati**: le letture ignorano la mempool, perché un registro che alimenta il consenso deve essere identico su ogni nodo.
