# wPoA — Report di analisi root-cause (Fase 1)

Repo: `/home/mattu/multichain` — fork di MultiChain 2.3
Branch di partenza dell'analisi: `tests/shadow-simulator` (HEAD `7e7d9a6`)
Data: 2026-09-03

Tutti i path in questo documento sono stati **verificati per ricerca nel codice**, non ipotizzati.
La struttura reale del fork differisce dall'upstream nominale: i moduli custom vivono in
`src/wpoa/` e `src/weight_engine/`, e l'harness di orchestrazione in `shadow/tools/` oltre che
in `src/wpoa/test/`.

---

## 0. Sintesi esecutiva

Due bug, entrambi confermati, ma **lo stato di partenza non è quello atteso dal mandato**:

* **Bug 1 (spacing di mining-diversity)** è già stato patchato *parzialmente* dal commit
  `c81e513` ("wPoA: drop the mining-diversity spacing on wPoA-governed heights"), che è
  antenato di HEAD. La patch copre 2 call-site su ~9. Restano scoperti call-site che
  riproducono lo stesso bug in contesti diversi, e **il call-site più dannoso non è quello
  già patchato**: è `CWallet::GetKeyFromAddressBook(..., MC_PTP_MINE)`, che il miner wPoA
  invoca su di sé a ogni round. Inoltre la patch esistente introduce una **divergenza di
  consenso** non intenzionale (valutazione delle permission in mempool).
* **Bug 2 (bootstrap stream `wpoa-weights`)** è confermato ed è un problema di **ordinamento**,
  non una dipendenza circolare irrisolvibile. L'harness `shadow/tools/role_admin.sh` lo aggira
  già lato script; il codice C++ resta però deadlockato su qualunque rete pulita avviata senza
  quell'harness, e l'harness `src/wpoa/test/functional_lib.sh` non lo aggira (si limita ad
  attendere, e rinuncia con un WARNING).

Conseguenza sulla strategia: **non moltiplico le patch sui singoli call-site**. Il Bug 1 va
corretto nel suo *unico punto di verità* (`IsBarredByDiversity`), che neutralizza tutti i
call-site in un colpo solo, e le due patch puntuali esistenti vanno ricondotte a `CanMine()`
per eliminare la divergenza mempool. Argomentazione completa in §2.4 e §4.

---

## 1. Mappa dei file coinvolti (path reali confermati)

| Ruolo | Path reale | Simbolo / riga |
|---|---|---|
| Vincolo `mining-diversity` nativo | `src/permissions/permission.cpp` | `mc_Permissions::CanMine` :1692 |
| Aritmetica dello spacing | `src/permissions/permission.cpp` | `mc_Permissions::IsBarredByDiversity` :1979 |
| Dichiarazioni | `src/permissions/permission.h` | `CanMine` :365, `IsBarredByDiversity` :395 |
| Verifica permesso miner lato consenso | `src/protocol/multichainblock.cpp` | `CheckBlockPermissions` :1150 (check a :1200-1210) |
| Percorso di validazione wPoA | `src/protocol/multichainblock.cpp` | `VerifyBlockMinerWPoA` :769, dispatch da `VerifyBlockMiner` :923 (early return :942) |
| Replay diversity nativo (ramo non-wPoA) | `src/protocol/multichainblock.cpp` | `CanMineBlockOnFork` :1090, :1100 |
| Costruzione nuovo blocco | `src/miner/miner.cpp` | `CreateNewBlock` — probe `canMine` :723-738 |
| Timing / elezione miner | `src/miner/miner.cpp` | ramo wPoA Phase 2 :1203-1249; ramo Phase 4 sortition :~1141-1195; path nativo :1250+ |
| Pool miner nativo | `src/miner/miner.cpp` | `LastActiveMiners` :969 (`CanMine` :1014) |
| Predicato di attivazione wPoA | `src/wpoa/wpoa_selector.cpp` | `WPoAActiveAtHeight` :48; flag `g_wpoa_enabled` :23 |
| Registro pesi | `src/wpoa/stream_weight_registry.{h,cpp}` | classe `StreamWeightRegistry`; `EnsureStreamExists` cpp:115, `EnsureSubscribed` cpp:160, `RegisterLocalWeight` cpp:272, `ThreadRegisterNodeWeight` cpp:774 |
| Motore pesi (publisher reale) | `src/weight_engine/weight_engine.cpp` | `ThreadWeightEngine` :225 (publish a :358) |
| Auto-create stream di input (precedente) | `src/weight_engine/weight_reader.cpp` | `EnsureOneStream` :~60, `EnsureInputStreams` :134 |
| Resolve dei flag wPoA | `src/core/init.cpp` | blocco :3231-3365, commit dei global :3348-3358; lancio thread :3637-3650 |
| Guard di dipendenza weight engine | `src/core/init.cpp` | :3586-3590 (`InitError` esistente, pattern per il nuovo guard di ordinamento) |
| Margine di stabilità delle epoche | `src/weight_engine/weight_streams.h` | `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` :147 (= 6) |
| Parametri di chain wPoA | `src/chainparams/paramlist.h` | `enablewpoa*` :161-209 (protocollo 20014), `miningdiversity` :115 |
| Harness shadow (rete geografica) | `shadow/tools/role_admin.sh` | `do_grant` :53, create `wpoa-weights` :88-93 |
| Harness funzionale wPoA | `src/wpoa/test/functional_lib.sh` | `fl_start_network` :188, `fl_grant_weights_write` :233 |
| Test funzionale di sistema | `src/wpoa/test/functional_test_wpoa_system.sh` | orchestrazione in coda al file |
| Suite unit wPoA | `src/wpoa/test/run_unit_tests.sh` + `*_tests.cpp` | Boost.Test self-contained |

### Duplicazione logica tra percorso wPoA e percorso standard

`VerifyBlockMiner` (`multichainblock.cpp:923`) fa **early return** verso
`VerifyBlockMinerWPoA` quando `WPoAActiveAtHeight(pindexNew->nHeight)` è vero
(:942-945). Quindi il replay nativo del diversity (`CanMineBlockOnFork`, :1090/:1100)
**non è raggiungibile** sulle altezze governate da wPoA: i due percorsi sono mutuamente
esclusivi, non duplicati. `CheckBlockPermissions` invece è **comune ai due regimi** (è
chiamata a monte, per ogni altezza) — ed è per questo che è lì che il bug si manifestava.

---

## 2. Bug 1 — spacing di mining-diversity attivo sotto wPoA

### 2.1 Meccanica del difetto

`IsBarredByDiversity(block, last, miner_count)` (`permission.cpp:1979`):

```
diversity = (miner_count * miningdiversity - 1) / 1000000      // MC_PRM_DECIMAL_GRANULARITY
diversity++                                                     // clamp in [1, miner_count]
if ((block - last) <= diversity - 1) return 1;                  // barrato
```

`miningdiversity` ha default `300000` = 0.3 (`paramlist.h:116`). Quindi:

| N miner | `diversity` | condizione di barra | effetto |
|---|---|---|---|
| 3 | `(900000-1)/1e6 + 1` = **1** | `(block-last) <= 0` | mai vero (Δ≥1) → **inerte** |
| 4 | `(1200000-1)/1e6 + 1` = **2** | `(block-last) <= 1` | **barra due blocchi consecutivi** |
| 10 | `(3000000-1)/1e6 + 1` = **3** | `(block-last) <= 2` | barra due round di distanza |

Questo **conferma quantitativamente** il mascheramento: `NODES` di default è `3`
(`functional_lib.sh:37`), quindi tutta la suite funzionale girava in un regime in cui lo
spacing è aritmeticamente inerte. Da 4 miner in su morde.

Sotto wPoA ogni indirizzo con permesso `mine` partecipa a **ogni** round e la selezione è
pesata: un validatore pesante vince legittimamente due round consecutivi. Lo spacing
round-robin nativo lo rifiuta.

### 2.2 Grafo delle chiamate — ogni call-site di `CanMine()` e classificazione

Ricerca esaustiva (`grep -rn "CanMine\s*(" src/`), più i consumatori indiretti via
`GetAllPermissions` e `IsBarredByDiversity`.

| # | Call-site | Contesto | Raggiungibile sotto wPoA? | Verdetto |
|---|---|---|---|---|
| 1 | `permission.cpp:1692` | definizione di `CanMine` | — | invariata (il gate va sotto, in `IsBarredByDiversity`) |
| 2 | `permission.cpp:1209` (`GetAllPermissions`) | `if(type & MC_PTP_MINE) result \|= CanMine(...)` | **sì** | **BUG — da correggere** (vedi §2.3, è il vettore più dannoso) |
| 3 | `permission.cpp:1727` (`CanMine`) | applicazione interna dello spacing | sì | corretta dal gate |
| 4 | `permission.cpp:1853` (`CanMineBlock`) | funzione non usata (commento upstream: *"function not used"*) | no (dead) | corretta dal gate, nessun rischio |
| 5 | `permission.cpp:1967` (`CanMineBlockOnFork`) | replay diversity su fork | **no** — early return :942 | corretta dal gate (difesa in profondità) |
| 6 | `multichainblock.cpp:1206` (`CheckBlockPermissions`) | **ammissione del blocco** | sì | **già patchato** da `c81e513`, ma con difetto mempool → da ricondurre a `CanMine()` |
| 7 | `miner.cpp:736` (`CreateNewBlock`) | probe `canMine` per il self-test di validità | sì | **già patchato** da `c81e513`, stesso difetto mempool → da ricondurre |
| 8 | `miner.cpp:1014` (`LastActiveMiners`) | pool miner del timing **nativo** | **no** — il ramo wPoA a :1203 fa sempre `return` prima di :1360 | **invariata** |
| 9 | `multichainblock.cpp:1090`, `:1100` (`CanMineBlockOnFork`) | replay nativo | **no** — early return :942 | **invariata** |
| 10 | `multichaintx.cpp:1811` | esenzione `receive` per il coinbase del miner | **sì** | **BUG latente — da correggere** (vedi §2.3) |
| 11 | `main.cpp:3710` (`UpdateChainMiningStatus`) | calcolo di `pindexNew->nCanMine` | **sì** | **BUG — da correggere** (vedi §2.3) |
| 12 | `main.cpp:4496` | copia commentata di `UpdateChainMiningStatus` | dead code | invariata |
| 13 | `rpcpermissions.cpp:711` | RPC di introspezione permessi | sì | **invariata per scelta**: deve riportare il permesso *effettivo*; sotto wPoA il gate lo rende automaticamente coerente |
| 14 | `rpcpermissions.cpp:1434` (`IsBarredByDiversity`) | stima `listminers` del prossimo blocco ammesso | sì | corretta dal gate: il `while` esce subito, `m_WaitBlocks=0`, `m_NextAllowed=next_block` — che sotto wPoA **è la risposta giusta** |

#### Consumatori indiretti via `GetAllPermissions` (#2) — il vettore principale

`CWallet::GetKeyFromAddressBook(result, type)` (`wallet/wallet.cpp:3611`) usa
`GetAllPermissions(NULL, keyID, type)` e accetta la chiave solo se `perm == type`
(`wallet.cpp:3626` e `:3642`). Con `type == MC_PTP_MINE`, se `CanMine()` ritorna 0 per
spacing, **la chiave di mining locale viene dichiarata inesistente**. Call-site raggiungibili
sotto wPoA:

| Path | Riga | Effetto quando il nodo ha minato il blocco precedente |
|---|---|---|
| `src/miner/miner.cpp` | **1205** — ramo wPoA Phase 2 | `kThisMiner` invalido → log *"no local mining key, waiting"* → `MiningStartTime = now + 3600` → **il proposer eletto non mina il proprio blocco: stallo di un'ora** |
| `src/miner/miner.cpp` | **1154** — ramo wPoA Phase 4 (sortition privata) | idem, sul path di produzione |
| `src/miner/miner.cpp` | 906 (`CreateNewBlock`), 1092, 1136, 1365, 1430 | selezione chiave coinbase / path nativo |
| `src/core/main.cpp` | 3942, 3994, 6923, 7000 | `nCanMine` → ordinamento di fork-choice |
| `src/wpoa/stream_weight_registry.cpp` | **75-77** (`ResolveLocalAddress`) | `GetKeyFromAddressBook(MC_PTP_MINE)` fallisce → **fallback su `MC_PTP_CONNECT`, cioè un indirizzo DIVERSO** → `m_LocalAddress` cambia identità a seconda che il nodo abbia minato o no |
| `src/weight_engine/weight_publisher.cpp` | **72-74** | identico |

L'ultimo punto è quello che **collega i due bug**: `StreamWeightRegistry` viene costruito
ex-novo a ogni chiamata di `WPoASelectProposer` (`wpoa_selector.cpp:~93`), quindi
`m_LocalAddress` può oscillare fra due indirizzi diversi *dello stesso nodo* in funzione di
chi ha minato il blocco precedente. Conseguenze: il confronto `sProposer == sLocalAddr` nel
miner (`miner.cpp:1230`) può essere fatto contro l'identità sbagliata, e un record di peso
può essere pubblicato sotto un indirizzo che non è quello registrato come validatore
(record self-published → scartato da ogni peer, cfr. `PublishWeightRecord`).

#### `main.cpp:3710` → fork-choice (#11)

`nCanMine` è consumato dal comparatore `CBlockIndexWorkComparator` (`main.cpp:172-174`):

```cpp
if((pa->nCanMine > 0) && (pb->nCanMine == 0)) return false;
if((pa->nCanMine == 0) && (pb->nCanMine > 0)) return true;
```

Un blocco il cui miner risulta barrato prende `nCanMine = 0` e il suo ramo viene
**declassato** in `setBlockIndexCandidates`. Sotto wPoA, la seconda vittoria consecutiva di
un validatore declassa il tip legittimo: pressione di reorg spuria e mancato avanzamento.
È lo stesso bug in un contesto completamente diverso (scelta della catena, non ammissione
del blocco) — esattamente il tipo di call-site che il mandato chiedeva di cercare.

#### `multichaintx.cpp:1811` (#10)

```cpp
if(tx.IsCoinBase()) fCanReceive |= mc_gState->m_Permissions->CanMine(NULL,ptr);
```

Esenzione: il miner può pagarsi il coinbase senza permesso `receive`. Sotto wPoA, alla
seconda vittoria consecutiva `CanMine` è 0 → l'esenzione svanisce → un validatore con
`mine` **ma senza `receive`** vede rifiutata la propria coinbase, e quindi il blocco.
Latente negli harness attuali (concedono sempre `connect,send,receive,mine`), reale in
produzione con permessi minimi.

### 2.3 Difetto introdotto dalla patch esistente `c81e513` — divergenza mempool

La patch sostituisce `CanMine()` con `CanCustom(NULL, addr, MC_PTP_MINE)`. Ma:

| | `GetPermission(..., checkmempool)` |
|---|---|
| `CanMine` (`permission.cpp:1719`) | `check_mempool = 0` |
| `CanCustom` (`permission.cpp:1635`) → `GetPermission(e,a,t)` (`:1179`) | `checkmempool = **1**` |

Quindi la patch non ha solo tolto lo spacing (voluto): ha anche **acceso la valutazione dei
grant di permesso ancora in mempool** dentro `CheckBlockPermissions`, che è un controllo di
**consenso**. Il mempool è per definizione locale e diverso su ogni nodo: un blocco firmato
da un indirizzo il cui grant `mine` è ancora non confermato verrebbe **accettato dal nodo che
ha la tx in mempool e rifiutato da chi non l'ha**. È una divergenza di consenso, cioè un
fork. Non osservata negli harness perché i grant confermano molto prima dell'uso, ma è un
difetto reale e va rimosso.

`CanCustom` è inoltre privo dei due short-circuit di `CanMine`
(`IsProtocolMultichain()==0`, `MCP_ANYONE_CAN_MINE`): innocuo qui solo perché
`WPoAActiveAtHeight` già ritorna `false` in entrambi i casi — una dipendenza implicita e
fragile fra due funzioni distanti.

### 2.4 Scelta della correzione: punto singolo di verità

Due opzioni:

**(A) Patchare ogni call-site** sostituendo `CanMine()` con il permesso grezzo sotto wPoA.
*Contro*: ~7 punti da toccare in 5 file, in `permission.cpp` / `wallet.cpp` / `main.cpp` /
`multichaintx.cpp`; ogni nuovo call-site futuro reintroduce il bug; duplica il predicato di
attivazione in codice non-wPoA; è esattamente il pattern che ha già prodotto una patch
incompleta e con effetti collaterali (§2.3).

**(B) Neutralizzare lo spacing alla fonte**, in `IsBarredByDiversity`, quando l'altezza è
governata da wPoA. *Pro*: una sola modifica semantica in un solo punto; corregge in un colpo
tutti i call-site della tabella (#2, #3, #5, #10, #11, #14) e tutti i consumatori indiretti
via `GetKeyFromAddressBook`; `IsBarredByDiversity` riceve già l'**altezza** come primo
argomento, quindi il gate è una funzione pura di `(height, chain params)` — identica su miner
e validatore, che è il requisito di design dichiarato in `wpoa_selector.cpp:66-70`; permette
di **ripristinare `CanMine()`** nei due punti patchati, eliminando la divergenza mempool.

**Scelta: (B)**, più il ripristino di `CanMine()` nei due punti di `c81e513`.

#### Vincolo di linking (verificato) e sua soluzione

`permissions/permission.cpp` è compilato in **tre** target (`src/Makefile.am`):

* `multichain_libbitcoin_multichain_a` (:361) — **non** include `wpoa/*`
* `libbitcoinconsensus_la` (:698) — libreria di consenso standalone
* (via la prima) i tool `multichain-util` / `multichain-cli`

`wpoa/wpoa_selector.cpp` sta **solo** in `libbitcoin_wallet_a` (:311). Chiamare
`WPoAActiveAtHeight()` direttamente da `permission.cpp` produrrebbe un **simbolo
irrisolto** in `libbitcoinconsensus` e nei tool → build rotta.

Soluzione adottata: **hook a puntatore a funzione**. `permission.{h,cpp}` dichiara/definisce
`mc_WPoAGovernsMiningHook`, inizializzato a `NULL`; `wpoa/wpoa_selector.cpp` lo installa a
**static-init time** (prima di `main()`) puntando a un thunk su `WPoAActiveAtHeight`. Così:

* zero nuove dipendenze di link: i target senza `wpoa/*` mantengono l'hook `NULL` e quindi il
  comportamento nativo **byte-identico**;
* **zero duplicazione** del predicato: `WPoAActiveAtHeight` resta l'unica definizione di
  "wPoA governa l'altezza h";
* nessun nuovo rischio di ordinamento di init: il valore del gate segue `g_wpoa_enabled`
  esattamente come ogni altro consumatore wPoA.

---

## 3. Bug 2 — bootstrap dello stream `wpoa-weights` (priorità)

### 3.1 Sequenza di bootstrap ricostruita

Chi *dovrebbe* creare lo stream: il **nodo admin di genesi**, l'unico con permesso `create`
su una chain permissioned. Il codice che lo fa esiste già:
`StreamWeightRegistry::EnsureStreamExists()` (`stream_weight_registry.cpp:115`), che emette
`create ["stream","wpoa-weights",false]` → **CLOSED**, come da Def. 5.16.

Il problema è **quando** viene chiamata. `EnsureStreamExists()` è `private` e ha **un solo
chiamante**: `RegisterLocalWeight()` (`:283`). E `RegisterLocalWeight` viene invocata in due
modi mutuamente esclusivi, decisi in `init.cpp:3641-3650`:

```
if (g_wpoa_weights_enabled && wallet) {
    if (g_weight_engine_enabled)  ThreadWeightEngine();          // path reale
    else                          ThreadRegisterNodeWeight(g_node_weight);  // fallback -weight
}
```

**Path `-weight` statico** (`ThreadRegisterNodeWeight`, `:774`): chiama
`registry.RegisterLocalWeight(weight)` **subito**, con `weight = g_node_weight` (default 100).
Un peso c'è sempre → `EnsureStreamExists()` gira al primo tick → l'admin crea lo stream.
**Il ciclo non si presenta.**

**Path weight engine** (`ThreadWeightEngine`, `weight_engine.cpp:225`) — quello reale in
produzione: `RegisterLocalWeight` è raggiunta **solo in coda** a una catena di gate
(`:279-355`):

```
NodeReadyForWeight()                       → tip presente, IBD finito
reader.EnsureInputStreams()                → membership + esg creati e sottoscritti
WeightEngineActiveAtHeight(height)
epoch = (height - STABILITY_MARGIN + 1)/len  ≥ 1     → serve un'epoca SEPOLTA
ComputeLocalWeightForEpoch(...)            → serve essere miner CERTIFICATO
   └─► RegisterLocalWeight(w, epoch)  ─►  EnsureStreamExists()
```

### 3.2 Perché il ciclo non si rompe da solo

```
wpoa-weights non esiste
   └─► GetAllNodesWeights() ritorna {} su ogni nodo
        └─► WPoASelectProposer() non elegge nessuno  ("0 validators, total=0")
             └─► nessun nodo mina oltre setup-first-blocks
                  └─► l'altezza non avanza → nessuna epoca si seppellisce
                       └─► ComputeLocalWeightForEpoch() non produce mai un peso
                            └─► RegisterLocalWeight() non viene mai chiamata
                                 └─► EnsureStreamExists() non viene mai chiamata
                                      └─► wpoa-weights non esiste  ◄── chiusura del ciclo
```

L'altezza di innesco è la stessa per i due lati: `WPoAActiveAtHeight` ingaggia a
`height >= setupfirstblocks` (`wpoa_selector.cpp:71-73`). Fino a lì la chain avanza con le
regole native; da lì in poi serve il registro pesi, che non esiste. Da cui lo stallo esatto
osservato: `0 validators, total=0` e `cannot score (unsynced or unweighted)`.

**Non è una dipendenza circolare irrisolvibile: è un problema di ordinamento.** La creazione
dello stream non dipende *logicamente* dall'avere un peso da pubblicare — dipende solo dal
permesso `create`, disponibile sull'admin **dal blocco 1**. Il ciclo esiste solo perché la
creazione è stata *implementata come effetto collaterale della pubblicazione*, cioè
sequenziata dopo un evento che a sua volta la richiede. Spostare la creazione **prima** del
gate d'epoca rompe questa metà del ciclo in modo deterministico: la precondizione (permesso
`create`, wallet pronto, tip presente) è soddisfatta a ogni avvio di rete pulita,
indipendentemente dallo stato dei pesi.

#### L'invariante di ordinamento (correzione all'analisi iniziale)

Anticipare la `create` **non è però sufficiente da sola**, e questo va detto con precisione
perché cambia il progetto della patch. Lo stallo ha due metà indipendenti:

1. **lo stream non esiste** → i grant `.write` vengono scartati in silenzio e nulla è
   pubblicabile;
2. **il registro è vuoto** → `WPoASelectProposer` non elegge nessuno e nessun nodo mina.

Anticipare la `create` risolve (1). Ma (2) dipende da *quando il primo peso diventa
calcolabile*, che è funzione dei soli parametri di chain:

```
prima epoca sepolta a  h_w = weight-epoch-length + STABILITY_MARGIN - 1
wPoA ingaggia a         h_p = setup-first-blocks
```

Il registro è popolato in tempo **se e solo se** vale l'invariante

> **`setup-first-blocks  >  weight-epoch-length + STABILITY_MARGIN - 1`**

con `MC_WEIGHT_DEFAULT_STABILITY_MARGIN = 6` (`weight_streams.h:147`).

Verifica sui valori reali:

| Configurazione | epoch-length | margine | h_w | setup-first-blocks | invariante |
|---|---|---|---|---|---|
| **default di prodotto** (`paramlist.h:112`, `:238`) | 100 | 6 | **105** | **60** | **VIOLATA** → stallo |
| shadow (`shadow/config/params.overrides`) | 12 | 6 | 17 | 60 | soddisfatta |

Il default di prodotto **viola l'invariante**: una rete pulita avviata con
`-enablewpoa=1 -enableweightengine=1` e per il resto parametri di default si ferma a quota 60,
che è esattamente il sintomo riportato. L'harness shadow non incappa nello stallo perché la
sua configurazione la rispetta per costruzione — e lo dichiara nel commento accanto al
parametro:

```
WEIGHT_EPOCH_LENGTH=12
SETUP_FIRST_BLOCKS=60         # > epoca(12) + margine di stabilita'(6) = 18
```

Quindi il `create` esplicito di `role_admin.sh` non è ciò che tiene in piedi la rete shadow:
la tiene in piedi **l'invariante rispettata**. Il `create` esplicito rimuove soltanto la
latenza e i grant persi della metà (1).

Conseguenza sul progetto della correzione: la patch deve coprire **entrambe** le metà —
anticipare la creazione (deterministica, sempre) *e* rendere rilevabile la violazione
dell'invariante, che altrimenti si manifesta come uno stallo muto a quota
`setup-first-blocks` senza alcun messaggio che ne indichi la causa.

La prova che questo è il pattern corretto è **già nello stesso codebase**:
`reader.EnsureInputStreams()` (`weight_reader.cpp:134`, `EnsureOneStream` :~60) crea
`weight-engine-membership` e `weight-engine-esg` — anch'essi CLOSED — ed è chiamata
**incondizionatamente a ogni tick, prima di qualunque gate d'epoca** (`weight_engine.cpp:262`).
`wpoa-weights` è l'unico dei tre stream a non avere questo trattamento. Il bug è
un'**asimmetria**, non una scelta di design.

### 3.3 Difetto secondario: latch permanente su fallimento transitorio

In `EnsureStreamExists` (`:123-127`, `:139`) e in `EnsureOneStream`:

```cpp
m_CreateAttempted = true;      // ← impostato PRIMA del try
try { createcmd(params,false); } catch (...) { /* log */ }
```

Il flag latcha **anche quando la `create` fallisce**. E l'oggetto `registry` in
`ThreadWeightEngine` / `ThreadRegisterNodeWeight` vive per tutta la durata del thread:
un fallimento **transitorio** (wallet non ancora sbloccato, UTXO non disponibili, grant
`create` non ancora confermato) **incastra il nodo per sempre** — il loop continua a girare
ma non ritenterà mai la `create`. Va corretto insieme al bug principale: senza questo, la
soluzione lato codice sarebbe affidabile solo al primo colpo.

### 3.4 Stato attuale degli harness

| Harness | Crea `wpoa-weights`? | Nota |
|---|---|---|
| `shadow/tools/role_admin.sh` :88-93 | **sì**, idempotente (`rpc_ok ... \|\| "gia' presente"`), CLOSED, prima dei grant `.write` :97, con `wait_stream` | workaround già in essere; il commento :82-87 documenta esattamente questo stallo |
| `src/wpoa/test/functional_lib.sh` :233 | **no** | `fl_grant_weights_write` si limita ad **attendere** che lo stream compaia (60 tentativi), poi *"WARNING: wpoa-weights does not exist yet; write grants skipped"* e prosegue. Con il weight engine attivo l'attesa non può mai essere soddisfatta |
| `src/weight_engine/test/functional_test_weight_engine.sh` | no | single-node, usa il path `-weight` (dove il ciclo non si presenta) |

### 3.5 Scelta: harness-only vs auto-creazione lato codice

**Opzione H — solo harness** (creare esplicitamente lo stream in `role_admin.sh` /
`functional_lib.sh` prima dei grant).
*Pro*: zero rischio sul codice di consenso; già dimostrata funzionante in `role_admin.sh`.
*Contro*: **non è una correzione, è un workaround**. Vale solo per le reti avviate da quegli
script. Qualunque rete pulita avviata da un operatore, o dal secondo harness, o in
produzione, resta deadlockata. Rende la vitalità del protocollo dipendente da un passo
manuale non documentato nel codice. E lascia il difetto §3.3 in piedi.

**Opzione C — auto-creazione idempotente lato nodo.**
*Pro*: rompe il ciclo **all'origine**, su ogni avvio, senza passi operativi; il permesso
`create` è già il gate di sicurezza corretto (i non-admin non possono creare, e non devono);
riallinea `wpoa-weights` al trattamento già riservato agli altri due stream (§3.2), quindi
riduce il codice speciale invece di aggiungerne; consente di correggere §3.3 nello stesso
punto; rende il test funzionale una verifica del *prodotto*, non dell'harness.
*Contro*: tocca il path di startup del nodo; va reso robusto su rete multi-admin (§5).

**Scelta: Opzione C**, implementata da sola. Le due opzioni sono **ridondanti**, non
complementari: entrambe garantiscono "lo stream esiste prima che serva un peso", e la H è un
sottoinsieme operativo della C. Con la C attiva, il `create` di `role_admin.sh` diventa un
no-op benigno (resta idempotente e innocuo — **non lo rimuovo**, è la belt-and-braces per le
reti shadow già in esecuzione), e il loop d'attesa di `functional_lib.sh:233` **inizia a
essere soddisfatto**, quindi non richiede modifiche.

### 3.6 Copertura della seconda metà: rilevare la violazione dell'invariante

Per l'invariante di §3.2 servono tre possibilità:

**(i) `InitError` bloccante** sulla combinazione di parametri che stallerà.
*Contro, decisivo*: un nodo che si unisce a una chain **già oltre** `setup-first-blocks` —
avanzata con pesi pubblicati per altra via (il path `-weight` statico su alcuni nodi, o una
pubblicazione manuale) — sincronizza da quota 0 e vedrebbe la stessa combinazione di
parametri, rifiutando di partire su una rete sana. Rischio di *bricking* su deployment
esistenti: **scartata**.

**(ii) Fallback del selettore alle regole native a registro vuoto.** Cambierebbe la semantica
di consenso dell'elezione, ed è asimmetrico rispetto a `VerifyBlockMinerWPoA`, che a registro
vuoto già *salta* il controllo (`multichainblock.cpp:902`): il validatore è permissivo, il
miner si rifiuta di minare, e proprio da questa asimmetria nasce lo stallo. Toccare il
consenso per un problema di configurazione è sproporzionato: **scartata**.

**(iii) WARNING di avvio specifico**, che nomina i tre numeri e la quota esatta alla quale la
rete si fermerà, emesso solo quando il weight engine **e** la selezione wPoA sono entrambi
attivi. Non può rompere nulla, e trasforma uno stallo muto in un errore diagnosticabile al
primo avvio. È anche il pattern **già in uso nello stesso blocco** di `init.cpp` per le
divergenze consensus-critical (`init.cpp:3599-3606`, `:3620-3626`).

**Scelta: (iii)**, insieme all'Opzione C. Le due sono complementari e non ridondanti:
la C garantisce l'ordinamento nella metà che il codice controlla (esistenza dello stream),
la (iii) rende immediatamente visibile la metà che dipende dalla configurazione di chain e
che il codice non può correggere da sé senza toccare il consenso.

---

## 4. Interazione fra i due fix e decisione sul merge

I due fix sono **logicamente indipendenti** (uno tocca il gate del permesso di mining, l'altro
l'ordinamento del bootstrap dello stream) ma hanno **un punto di contatto reale**, individuato
in §2.2: `StreamWeightRegistry::ResolveLocalAddress()` (`stream_weight_registry.cpp:75-77`) e
`weight_publisher.cpp:72-74` usano `GetKeyFromAddressBook(MC_PTP_MINE)`, che è affetto dal
Bug 1. Finché il Bug 1 non è corretto, l'identità locale usata per pubblicare il peso può
cambiare a seconda che il nodo abbia minato il blocco precedente.

Conseguenza pratica: il **test funzionale del Fix 2** (rete pulita, N≥4, weight engine attivo,
verifica che al passaggio a wPoA il registro non sia vuoto) su un branch che contenga *solo*
il Fix 2 potrebbe risultare instabile per una causa che appartiene al Fix 1.

Decisione: i due fix restano su **branch separati e non mergiati**, come richiesto — nessuno
dei due dipende dall'altro per *compilare* o per essere revisionato. La dipendenza è solo di
*stabilità osservata a runtime* e viene dichiarata qui e nella docstring del test, non
risolta con un merge di comodo. In fase di integrazione i due branch vanno applicati insieme.

---

## 5. Rischi collaterali per modifica proposta

### Fix 1 — gate in `IsBarredByDiversity`

| Rischio | Valutazione |
|---|---|
| **Chain che non usano wPoA** | Hook `NULL` (tool, `libbitcoinconsensus`) o `g_wpoa_enabled == false` → `IsBarredByDiversity` invariata **byte per byte**. `WPoAActiveAtHeight` ritorna già `false` anche se `IsProtocolMultichain()==0` o `MCP_ANYONE_CAN_MINE`. |
| **Altezze pre-setup sulla stessa chain wPoA** | `WPoAActiveAtHeight` è `height >= setupfirstblocks`; sotto quella soglia lo spacing resta pienamente attivo, come oggi. |
| **Reti a 3 nodi (dove il bug era mascherato)** | A N=3 lo spacing calcolato è 1, cioè già inerte (§2.1): il gate non può cambiare nulla di osservabile. Da verificare comunque per regressione con la suite a `NODES=3`. |
| **Caso d=0 / peso uniforme / wPoA disattivo** | `miningdiversity = 0` → `diversity = 0+1 = 1` → già inerte, indipendentemente dal gate. Peso uniforme con wPoA attivo: la selezione resta pesata (uniforme), il gate toglie solo lo spacing, che è il comportamento voluto. |
| **Rimozione dello spacing = perdita di una garanzia di sicurezza?** | Sotto wPoA la rotazione dei proposer è garantita dalla selezione pesata + beacon VRF/RANDAO, non dallo spacing round-robin: sono due meccanismi alternativi per lo stesso scopo, e il design (§5.12.3) prescrive esplicitamente il primo. Sulle altezze non-wPoA nulla cambia. |
| **Ripristino di `CanMine()` nei 2 punti di `c81e513`** | Ripristina la semantica `checkmempool=0` corretta per il consenso (§2.3). Nessuna perdita: lo spacing è già neutralizzato dal gate. |
| **`listminers` (`rpcpermissions.cpp:1434`)** | `m_WaitBlocks` diventa 0 e `m_NextAllowed` = prossimo blocco per ogni miner attivo. È semanticamente corretto sotto wPoA, ma **cambia l'output di un'RPC**: da annotare per chi ne consuma il valore. |
| **Ordinamento di init (pre-esistente)** | `g_wpoa_enabled` è assegnato a `init.cpp:3349`, **dopo** `LoadBlockIndex` (:2761) e `ActivateBestChain` (:3086). Durante il caricamento iniziale tutti i predicati wPoA valgono `false`, quindi `UpdateChainMiningStatus` calcola `nCanMine` con lo spacing. **Difetto pre-esistente**, che affligge in egual misura `VerifyBlockMiner` e ogni altro consumatore wPoA; non introdotto né peggiorato da questa patch. Impatto limitato al ranking di fork-choice di blocchi già accettati. Segnalato, fuori scope. |

### Fix 2 — auto-creazione idempotente

| Rischio | Valutazione |
|---|---|
| **Idempotenza su chiamate ripetute** | `EnsureStreamExists` interroga `FindEntityByName` a ogni invocazione e ritorna subito `true` se lo stream c'è: nessuna seconda `create`. |
| **Race fra più admin che creano in parallelo** | I nomi di stream sono unici: se due `create` finiscono nello stesso blocco una viene rifiutata in accettazione tx. Il perdente al tick successivo trova lo stream del vincitore via `FindEntityByName` e converge. **Condizione necessaria**: il latch non deve impedire il re-check — garantita perché il controllo di esistenza precede il latch. |
| **Retry illimitati su nodi non-admin** | La `create` su un nodo senza permesso `create` fallisce *sempre*. Correggendo §3.3 con un retry non limitato si otterrebbe spam di log ogni 3 s. Mitigazione: contatore di tentativi **limitato** (non un booleano), così i fallimenti transitori vengono superati e quelli permanenti smettono. |
| **Nodi senza permesso `create`** | Comportamento corretto e invariato: non creano, attendono, sottoscrivono. La sicurezza resta affidata alle permission MultiChain, non a convenzioni. |
| **Chain senza weight engine** | Il path `-weight` chiamava già `EnsureStreamExists` al primo tick: nessun cambio di comportamento osservabile. |
| **Chain con `enablewpoaweights=0`** | `init.cpp:3641` non lancia alcun thread: lo stream non viene mai creato, come oggi. |
| **Creazione anticipata dello stream** | Lo stream viene creato prima che esista un peso: `getallweights` riporterà `0 validators` su uno stream **esistente e vuoto** invece che su uno stream assente. Stato transitorio corretto e più diagnosticabile di oggi. |
| **Ordine rispetto a `setup-first-blocks`** | La `create` parte appena il nodo è pronto (tip presente, IBD finito), cioè **molto prima** di `setupfirstblocks` (default 30 nell'harness): confermata con ampio margine prima che wPoA ingaggi. È il margine che rompe il ciclo in modo riproducibile. |
| **Ordine rispetto ai grant `.write`** | Un grant `wpoa-weights.write` emesso prima che lo stream esista viene silenziosamente scartato — è esattamente il motivo per cui `functional_lib.sh:227-232` li ri-emette. Con la creazione anticipata, il grant iniziale di `_fl_bootstrap_node:173` ha molte più probabilità di attecchire, e il re-issue resta come rete di sicurezza. |
| **Retry limitato invece del latch permanente** | Il latch resta sul **broadcast riuscito** (mai due tx di `create`, quindi nessun rischio di stream duplicato se MultiChain accettasse un nome già presente ma non confermato); il retry limitato agisce solo sui **fallimenti**. Costo peggiore su un nodo senza permesso `create`: N tentativi falliti e poi silenzio, invece di uno solo. |
| **Create trasmessa ma mai confermata** | Se la tx di `create` finisce in mempool e la catena si ferma, il latch impedisce la ri-trasmissione. Difetto pre-esistente, non peggiorato: con la correzione la `create` parte mentre la catena avanza sotto regole native, quindi conferma con ampio margine. Annotato, non risolto. |
| **WARNING sull'invariante — falsi positivi** | Il warning si attiva solo con weight engine **e** selezione wPoA entrambi attivi. Su un nodo che si unisce a una chain sana già oltre `setup-first-blocks` (avanzata con pesi pubblicati per altra via) il warning è un falso positivo: è il prezzo di non usare un `InitError`, che invece impedirebbe l'avvio (cfr. §3.6). Testo del messaggio esplicito sul fatto che riguarda l'avvio di una rete **pulita**. |
| **WARNING sull'invariante — nessun effetto sul consenso** | È solo una `LogPrintf`: non cambia flag, parametri o percorsi di validazione. |

---

## 6. Piano di intervento (esito della Fase 1)

**Branch `fix/wpoa-diversity-spacing-canmine`**
1. `src/permissions/permission.h` — dichiarare l'hook `mc_WPoAGovernsMiningHook`.
2. `src/permissions/permission.cpp` — definirlo `NULL`; gate in testa a `IsBarredByDiversity`.
3. `src/wpoa/wpoa_selector.cpp` — thunk su `WPoAActiveAtHeight` + installazione a static-init.
4. `src/protocol/multichainblock.cpp` — ripristinare `CanMine()` in `CheckBlockPermissions`.
5. `src/miner/miner.cpp` — ripristinare `CanMine()` nel probe di `CreateNewBlock`.
6. Test: caso di regressione mirato "doppia vittoria consecutiva a N≥4 accettata".

**Branch `fix/wpoa-weights-stream-bootstrap`**
1. `src/wpoa/stream_weight_registry.h/.cpp` — esporre `EnsureStreamReady()` pubblica;
   sostituire il latch booleano di `create` con "latch sul broadcast riuscito + retry
   limitato sui fallimenti", così un errore transitorio non incastra il nodo per sempre.
2. `src/weight_engine/weight_engine.cpp` — chiamare `EnsureStreamReady()` accanto a
   `EnsureInputStreams()`, **prima** del gate d'epoca.
3. `src/core/init.cpp` — WARNING di avvio sulla violazione dell'invariante di §3.2, con i tre
   numeri e la quota di stallo prevista.
4. Test: rete pulita con weight engine su configurazione che rispetta l'invariante; verifica
   che lo stream esista **prima** della transizione, che il registro non sia vuoto alla quota
   di transizione e che almeno un validatore sia punteggiabile.

Nessun merge nel branch principale: i due fix sono indipendenti (§4).

---

## 7. Esito della verifica sperimentale

Tutte le esecuzioni sotto sono su rete reale multi-nodo (non simulata), con i binari
compilati dai rispettivi branch. Build pulita su entrambi (`EXIT=0`), inclusi
`multichain-util`, `multichain-cli` e `libbitcoinconsensus.la`: sono esattamente i target
che avrebbero fallito con un simbolo irrisolto se il gate fosse stato scritto come chiamata
diretta a `WPoAActiveAtHeight` da `permission.cpp` (§2.4).

Controllo dei simboli, a conferma del progetto dell'hook:

| Target | `mc_WPoAGovernsMiningHook` | thunk + installer |
|---|---|---|
| `multichaind` | presente (BSS) | **presente** → gate attivo |
| `multichain-util` | presente (BSS, = NULL) | assente → comportamento nativo invariato |
| `libbitcoinconsensus` | presente (= NULL) | assente → comportamento nativo invariato |

### Fix 1 — `fix/wpoa-diversity-spacing-canmine`

Aritmetica dello spacing verificata contro la formula C++ (`fl_native_diversity_spacing`):
`d=0.3` → N=3 ⇒ 1 (inerte), N=4 ⇒ 2, N=10 ⇒ 3; `d=0` → 1 a ogni N (il caso "d=0 non
alterato" è confermato per costruzione).

| Esecuzione | Esito |
|---|---|
| `NODES=4 WEIGHTS="100 200 400 800"` | **PASS** (9/9 check). Spacing nativo = 2 (regime in cui il bug morde). **19 coppie di blocchi consecutivi dello stesso miner** su una finestra di 30 blocchi, tutte accettate. 0 `Permission denied for miner`, 0 `cannot mine now`, 0 `no local mining key`. |
| `NODES=3` (regime in cui il bug era mascherato) | **PASS** (10/10 check). Il check rileva correttamente spacing = 1 e dichiara il regime inerte; le tre asserzioni sui sintomi girano comunque e sono a zero. Lo scenario dedicato a 4 nodi parte in automatico e riproduce **19 coppie consecutive**, tutte accettate. |

Le 19 coppie consecutive sono la misura diretta della correzione: ognuna di esse, prima
della patch, sarebbe stata rifiutata in `CheckBlockPermissions` oppure — più probabilmente —
non sarebbe mai stata prodotta, perché il proposer eletto si sarebbe considerato privo di
chiave di mining (`GetKeyFromAddressBook`, §2.2) e avrebbe dormito un'ora.

Per confronto, la misura citata nel commento di `shadow/config/params.overrides` sullo stesso
fenomeno: *"0 blocchi consecutivi su 190 misurati, contro ~99 attesi"* con `MINING_DIVERSITY`
attivo — ed è la ragione per cui quella configurazione ha dovuto azzerare `MINING_DIVERSITY`
per poter misurare la sola selezione pesata. Con questa correzione l'azzeramento non è più
necessario: lo spacing è inerte sulle altezze governate da wPoA e resta pienamente attivo
altrove.

### Fix 2 — `fix/wpoa-weights-stream-bootstrap`

Rete pulita a 3 nodi, `-enablewpoa=1 -enableweightengine=1 -weightepochlength=10`,
`setup-first-blocks=30` (invariante di §3.2 soddisfatta: `30 > 10+6-1 = 15`).

| Check | Esito | Evidenza |
|---|---|---|
| `stream_created_early` | **PASS** | `wpoa-weights` esiste **a quota 7**, cioè prima della transizione (30) e prima che un peso sia calcolabile (15). Prima della patch a quota 7 lo stream non poteva esistere. Creato CLOSED (`restrict.write = true`), come da Def. 5.16 |
| `no_stall_at_transition` | **PASS** | catena a quota 60 > 30 |
| `registry_populated` | **PASS** | tutti e 3 i nodi riportano `validators=3`; 3 validatori con peso non nullo (punteggiabili) |
| `no_scoring_stall_logs` | **PASS** | **0** occorrenze di `cannot score (unsynced or unweighted)` su ogni nodo |
| `weights_agree_across_nodes` | **PASS** | nessuna divergenza sull'aggregato |

Pipeline dei pesi confermata end-to-end dal log del nodo, non solo dalle RPC:

```
[WeightEngine] epoch 2 (height 25): w_k = 3750 for 19tAT23FWx8TYAHje...
[StreamWeightRegistry] All nodes weights: 3 validators, total=6750
```

cioè il peso è stato **derivato** dal motore (membership self-attestata + ESG firmata dalla
CA + attività e riconciliazione dai blocchi) e pubblicato, con il registro popolato **prima**
della quota 30. Nella stessa esecuzione si contano 10 elezioni `wPoA-sortition` fra le quote
30 e 59: la catena è governata da wPoA e avanza.

**Controllo negativo del WARNING.** Sulla configurazione di test (invariante soddisfatta) il
warning è correttamente **assente**. Su parametri di default, invece, si attiva con i numeri
esatti:

```
[WeightEngine] WARNING: bootstrap ordering. The first weight cannot exist before height 105
(weight-epoch-length=100 + stability margin=6 - 1), but wPoA starts electing proposers at
setup-first-blocks=60. On a clean network the weights stream is still empty there, no
proposer can be elected, and the chain will stall at height 60. Set setup-first-blocks
greater than 105, or lower weight-epoch-length, in params.dat BEFORE starting the network.
```

### Indipendenza dei due branch (verifica)

Intersezione dei file modificati dai due branch rispetto a `master`: **vuota**. Merge di
prova (`git merge-tree`, senza effetti collaterali): **0 conflitti**. Nessun merge eseguito,
come da §4.

---

## 8. Seguito — floor di `setup-first-blocks` derivato alla genesi

Branch: `fix/wpoa-setup-first-blocks-floor` (da `master`, commit `8e1ca88`).

### 8.1 Il FAIL segnalato su `diversity_spacing_4n` non era una regressione

Sintomi riportati: `0` coppie consecutive con spacing 2 e **137** occorrenze di
`no local mining key, waiting`. È la firma esatta del bug **pre-fix** descritto in §2.2.

Causa: **binario stale**. `src/multichaind` era del 09-04 10:04 — la build del branch
`fix/wpoa-weights-stream-bootstrap`, che parte da `master` e **non** contiene il Fix 1. I
sorgenti erano del 09-05 (post-merge), ma non era stato rifatto `make`. Verifica diretta sul
binario: `0` occorrenze di `WPoAGovernsMiningThunk` e nessun simbolo
`mc_WPoAGovernsMiningHook`. Dopo `make`, entrambi presenti. Nessuna correzione di codice
necessaria — è servito solo ricompilare.

### 8.2 L'invariante diventa un valore derivato

Fino a qui l'invariante di §3.2 era solo *segnalata* da un WARNING. Ora è **derivata**:
quando il weight engine alimenta la selezione wPoA, `setup-first-blocks` viene alzato al
suo floor; un valore maggiore resta intatto (una fase di setup più lunga è una scelta
legittima dell'operatore).

**Correzione all'aritmetica richiesta.** Il floor non è `epoch + margin`. Quella è la quota
in cui il primo peso diventa *calcolabile*; ma il selettore legge **solo item confermati**, e
il valore deve ancora essere notato dal tick del motore, pubblicato e **minato** — in un
blocco che le regole **native** possano ancora produrre, perché da `setup-first-blocks` in
poi un blocco richiede proprio il registro che quel blocco popolerebbe. Con il floor a
`epoch + margin` il blocco di conferma cade esattamente sulla prima quota wPoA: **deadlock
largo un blocco**. Da cui `MC_WEIGHT_SETUP_PUBLISH_MARGIN` (3 blocchi: tick del motore,
conferma, propagazione) e il `+1`:

```
first_computable = weight-epoch-length + STABILITY_MARGIN - 1
floor            = first_computable + MC_WEIGHT_SETUP_PUBLISH_MARGIN + 1
```

Per `epoch=40`: calcolabile a 45, confermabile entro 48, floor **49**.

### 8.3 Dove viene applicato, e perché solo lì

Solo sul percorso di **creazione** della catena:

* `AppInit2`, sul ramo del nodo di genesi, **prima** di `Build()` — che calcola l'hash dei
  parametri. Il valore corretto entra così nell'identità della catena e raggiunge ogni nodo
  che si unisce tramite la normale eredità di `params.dat`.
* `multichain-util create` / `clone`, così che il file che l'operatore apre sia già coerente.

Riscriverlo su una catena **già avviata** non deve mai accadere: `setup-first-blocks` è
hash-enforced e cambiarlo dopo forkerebbe la rete. Il WARNING di runtime di §3.6 resta come
rete di sicurezza per le catene create prima di questa regola.

I due switch sono passati **dal chiamante**, non letti da `params.dat`: alla genesi possono
arrivare da riga di comando su un file che dice ancora `false` — ed è esattamente la
configurazione che si blocca. La risoluzione ricalca quella di `AppInit2` (master switch da
CLI incluso), di proposito: derivare il floor da una wPoA che poi non gira allungherebbe
inutilmente il setup.

`SetParam()` non è utilizzabile — serve solo parametri `CALCULATED`/`COMMENT` e rifiuta
quelli già presenti — quindi il valore è scritto direttamente nello store dei parametri.
Non è esposto come helper generico "sovrascrivi un parametro utente": riscrivere un
parametro hash-enforced è legittimo **solo** qui.

### 8.4 Verifica

| Caso | Configurazione | Esito |
|---|---|---|
| valore troppo basso, flag in params.dat | epoch 40, setup 20 | **20 → 46/49**, WARNING, scritto in `params.dat` |
| valore troppo basso, flag da CLI | params.dat `false`, `-enablewpoa -enableweightengine` | **20 → 49** — il caso che una lettura da solo `params.dat` avrebbe mancato |
| valore sufficiente | epoch 40, setup 90 | **90 invariato** |
| weight engine spento | epoch 40, setup 20 | **20 invariato** |
| `multichain-util create` | `-enableweightengine=1 -weightepochlength=40 -setupfirstblocks=20` | **20 → 46**, WARNING a video, in `params.dat` |

**End-to-end sulla configurazione che prima si bloccava** (3 nodi, epoch 40,
`setup-first-blocks` 20 — che senza floor si ferma a quota 20 con 0 pubblicazioni di peso):
6/6 check PASS. Floor 20→49; catena a **162**; `validators=3 total=2250` su tutti i nodi;
**0** `cannot score (unsynced or unweighted)`; pesi concordi.

Il check `setup_first_blocks_floor` legge il valore da `getblockchainparams`, non dal file
del nodo seed: dimostra che il valore corretto è davvero quello **della catena**, quindi
ereditato da tutti.

### 8.5 Constatazione collaterale (non corretta qui)

`AppInit2` risolve i flag wPoA leggendo da `params.dat` le sole chiavi **per-fase**
(`enable-wpoa-weights`, `enable-wpoa-selection`, …); il master `enable-wpoa` è consultato
**solo** da riga di comando (`init.cpp:3321-3324`). Quindi impostare unicamente
`enable-wpoa = true` nel file lascia tutte le fasi spente — e, con
`enable-weight-engine = true`, il nodo si rifiuta di partire con
*"-enableweightengine requires the wPoA weights stream"*.

Fuori dallo scope di questo branch, quindi **non corretta**. Il test di bootstrap la aggira
mettendo in `params.dat` la sola `weight-epoch-length` (il valore da cui il floor deriva, e
che deve essere di catena) e passando gli switch da CLI, con il commento che ne spiega il
motivo.
