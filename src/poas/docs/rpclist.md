# `rpc/rpclist.cpp` (solo la parte wPoA)

> Come richiesto, di questo file si spiega **il minimo indispensabile**: cos'è, come funziona il meccanismo di registrazione dei comandi RPC e **come vi sono stati aggiunti** i tre comandi wPoA. Il resto del file è la tabella standard dei comandi RPC di MultiChain e non viene dettagliato.

## 1. A cosa serve questo file

`rpclist.cpp` contiene la **tabella di dispatch** di tutti i comandi RPC del nodo: la mappa "nome comando testuale → funzione C++ che lo implementa". Quando un client invia una chiamata RPC/JSON (es. `getlocalweight`), il server RPC cerca il nome in questa tabella e invoca la funzione associata.

La tabella è un array di struct `CRPCCommand`:

```cpp
static const CRPCCommand vRPCCommands[] =
{ //  category    name            actor (function)   okSafeMode  threadSafe  reqWallet
  ...
};
```

Ogni riga ha 6 campi (commentati nell'header della tabella):

| Campo | Significato |
|-------|-------------|
| `category` | Categoria mostrata in `help` (raggruppa i comandi). |
| `name` | Nome testuale del comando invocato dal client. |
| `actor (function)` | Puntatore alla funzione C++ che implementa il comando (firma `Value f(const Array&, bool)`). |
| `okSafeMode` | Se il comando è eseguibile in "safe mode". |
| `threadSafe` | Se può girare senza il lock globale RPC (gestisce il proprio locking). |
| `reqWallet` | Se richiede un wallet abilitato per funzionare. |

## 2. L'aggiunta dei comandi wPoA

### 2.1 L'include (riga 13)

```cpp
#include "poas/stream_weight_registry.h"
```
Questo è l'unico collegamento necessario: porta in `rpclist.cpp` i **prototipi** delle tre funzioni handler dichiarate nell'header del registro:

```cpp
json_spirit::Value getlocalweight(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getallweights (const json_spirit::Array& params, bool fHelp);
json_spirit::Value getnodeweight (const json_spirit::Array& params, bool fHelp);
```
Senza questo include, i nomi `getlocalweight` ecc. usati nella tabella sarebbero simboli sconosciuti al compilatore. **Le funzioni sono definite altrove** (in `stream_weight_registry.cpp`): qui servono solo le dichiarazioni per prenderne l'indirizzo.

### 2.2 Le tre righe registrate (righe 135-140)

```cpp
#ifdef ENABLE_WALLET
    /* wPoA weight registry (Phase 1) */
    { "wpoa",  "getlocalweight",  &getlocalweight,  true,  true,  true },
    { "wpoa",  "getallweights",   &getallweights,   true,  true,  true },
    { "wpoa",  "getnodeweight",   &getnodeweight,   true,  true,  true },
#endif
```

Lettura dei campi per questi comandi:

- **`category = "wpoa"`** — crea una nuova categoria "wpoa" nell'output di `help`, così i tre comandi appaiono raggruppati.
- **`name`** — il nome con cui il client li invoca: `getlocalweight`, `getallweights`, `getnodeweight`.
- **`actor = &getlocalweight` ecc.** — l'operatore `&` prende l'**indirizzo della funzione** (puntatore a funzione). È così che la tabella collega il nome all'implementazione in `stream_weight_registry.cpp`.
- **`okSafeMode = true`** — sono comandi di sola lettura, sicuri anche in safe mode.
- **`threadSafe = true`** — non richiedono il lock globale RPC. È corretto perché i metodi di lettura del registro **si auto-bloccano** (usano `mc_WalletTxs::Lock()`/`UnLock()`, vedi `docs/stream_weight_registry.md` §2.7). Possono quindi girare in modo concorrente in sicurezza.
- **`reqWallet = true`** — richiedono il wallet: le letture usano `pwalletTxsMain` e ogni handler lancia `RPC_WALLET_ERROR` se il wallet non è disponibile.

- **`#ifdef ENABLE_WALLET`** — come per il blocco in `init.cpp`, i comandi esistono solo se il nodo è compilato con supporto wallet. Coerenza necessaria: senza wallet gli handler non potrebbero funzionare.

### 2.3 Come la tabella arriva al server RPC

In fondo al file:

```cpp
void mc_InitRPCList(std::vector<CRPCCommand>& vStaticRPCCommands,
                    std::vector<CRPCCommand>& vStaticRPCWalletReadCommands)
{
    ...
    for (vcidx = 0; vcidx < (sizeof(vRPCCommands)/sizeof(vRPCCommands[0])); vcidx++)
        vStaticRPCCommands.push_back(vRPCCommands[vcidx]);
    ...
}
```

- `mc_InitRPCList` viene chiamata all'avvio del server RPC e **copia** l'array statico `vRPCCommands` (incluse le nostre 3 righe) in un vettore che il dispatcher userà a runtime.
- `sizeof(vRPCCommands) / sizeof(vRPCCommands[0])` è l'idioma C classico per calcolare il **numero di elementi** di un array: dimensione totale dell'array diviso dimensione di un elemento.

Da questo momento, digitando `getlocalweight` sul client, il server trova la riga, chiama `&getlocalweight`, che esegue la logica di lettura del registro e ritorna il JSON risultante.

## 3. Riepilogo: cosa è stato "toccato" per aggiungere i comandi

Aggiungere un comando RPC in MultiChain richiede esattamente questi tre passi, tutti presenti qui:

1. **Dichiarare** l'handler in un header (`stream_weight_registry.h`).
2. **Definire** l'handler in un `.cpp` (`stream_weight_registry.cpp`, funzioni `getlocalweight`/`getallweights`/`getnodeweight`).
3. **Registrarlo** nella tabella `vRPCCommands` di `rpclist.cpp` (le 3 righe sopra) più l'`#include` dell'header.

## 4. Collegamenti con gli altri file

```
  Client RPC:  multichain-cli <chain> getallweights
        │
        ▼
  Server RPC  ──►  cerca "getallweights" in vRPCCommands   [rpclist.cpp]
        │                          │
        │                          └─► &getallweights (puntatore)
        ▼
  getallweights(params, fHelp)                              [stream_weight_registry.cpp]
        └─► StreamWeightRegistry(pwalletTxsMain).GetAllNodesWeights()
                └─► ReadAllRecords() → mc_ParseWeightRecordJson()   [weight_record.h]
```

- **`stream_weight_registry.h`** → fornisce i prototipi degli handler (via `#include`).
- **`stream_weight_registry.cpp`** → contiene le definizioni reali degli handler.
- Non c'è alcun legame con `init.cpp`: la registrazione RPC e l'avvio del thread di scrittura sono percorsi indipendenti. Le RPC leggono lo stato corrente qualunque esso sia (anche vuoto).

> Per il funzionamento interno degli handler e delle letture vedi `docs/stream_weight_registry.md`; per il parsing dei record vedi `docs/weight_record.md`.
