# Weight engine — derivazione on-chain del peso dei validatori

> **Registro: tecnico-diretto.** Documento di riferimento per API, strutture dati,
> flussi RPC e ciclo di vita degli stream. Per la giustificazione teorica del modello
> di peso si rimanda al capitolo di tesi «Gestione del peso», sintetizzato in
> [thesis-project-overview.md](thesis-project-overview.md).

Il weight engine (`src/weight_engine/`) sta **sopra** il consenso wPoA
(`src/wpoa/`). Ogni epoca legge un insieme di stream di input pubblici, calcola il
peso per-cluster `w_k^{(e)}` e lo pubblica sullo **stesso** stream `wpoa-weights`
che il consenso già consuma.

I due livelli sono accoppiati **solo** attraverso quello stream: il consenso non
apprende mai *come* `w_k` è stato prodotto. Questo separa la politica di
assegnazione del peso dalla meccanica dell'elezione, e rende il contratto di
`wpoa-weights` — `{address, integer weight > 0}` — l'unica interfaccia da
preservare.

Parametri di configurazione: [protocol-parameters.md §4](protocol-parameters.md).

---

## Indice

- [1. Perché esiste](#1-perché-esiste)
- [2. Gli stream di input](#2-gli-stream-di-input)
  - [2.1 L'attività non è pubblicata da nessuno](#21-lattività-non-è-pubblicata-da-nessuno)
  - [2.2 Ricostruzione del cluster C_k](#22-ricostruzione-del-cluster-c_k)
  - [2.3 Ciclo di vita degli stream](#23-ciclo-di-vita-degli-stream)
- [3. La pipeline di calcolo](#3-la-pipeline-di-calcolo)
  - [3.1 Determinismo consensus-critical](#31-determinismo-consensus-critical)
  - [3.2 Epoche e margine di stabilità](#32-epoche-e-margine-di-stabilità)
  - [3.3 Relazione col selettore — due livelli distinti](#33-relazione-col-selettore-—-due-livelli-distinti)
  - [3.4 Scostamento deliberato dalla simulazione di riferimento](#34-scostamento-deliberato-dalla-simulazione-di-riferimento)
- [4. Il thread dell'engine](#4-il-thread-dellengine)
- [5. Precedenza: quale publisher scrive](#5-precedenza-quale-publisher-scrive)
- [6. Modello di sicurezza — due gate indipendenti](#6-modello-di-sicurezza-—-due-gate-indipendenti)
  - [6.1 Gate on-chain — imposto dal consenso](#61-gate-on-chain-—-imposto-dal-consenso)
  - [6.2 Gate applicativo — solo questi RPC](#62-gate-applicativo-—-solo-questi-rpc)
  - [6.3 Limite noto — rischio accettato](#63-limite-noto-—-rischio-accettato)
- [7. Il flusso completo](#7-il-flusso-completo)
- [8. Threading](#8-threading)
- [9. File del modulo](#9-file-del-modulo)
  - [9.1 Test](#91-test)
- [10. Riferimenti](#10-riferimenti)

---
## 1. Perché esiste

Il consenso wPoA elegge i proposer in proporzione al peso. La domanda «da dove
viene il peso» non ha una risposta interna al consenso: è una decisione di
governance.

Due risposte sono implementate, mutuamente esclusive:

| | Sorgente del peso | Quando |
|---|---|---|
| **Statica** | Il flag per-nodo `-weight=<n>`, pubblicato così com'è | `-enableweightengine=0` (default) |
| **Dinamica** | `w_k` calcolato dagli input on-chain, una volta per epoca | `-enableweightengine=1` |

La via dinamica è quella prevista per l'esercizio reale. La via statica resta come
ripiego e per i test.

> **`-weight` non è la via principale.** Con l'engine attivo il valore di `-weight`
> viene parsato, validato, scritto in `g_node_weight` e registrato nel log — e poi
> **mai pubblicato**. Vedi [§5](#5-precedenza-quale-publisher-scrive).

---

## 2. Gli stream di input

I quattro input sono deliberatamente chiamati `weight-engine-*`, **non** `wpoa-*`:
appartengono al livello del peso e ai suoi attori esterni (il certificatore,
l'aggregatore di attività, il processo di riconciliazione), non al consenso. Solo lo
stream di **output** `wpoa-weights` appartiene a wPoA. La separazione dei nomi
rispecchia quella delle directory.

Definizioni in [`weight_streams.h`](../../weight_engine/weight_streams.h).

| Stream | Chiave dell'item | Payload | Origine |
|---|---|---|---|
| `weight-engine-membership` | indirizzo del miner | `{"<azienda_addr>": <ts>, ...}` | Admin, via RPC |
| `weight-engine-esg` | indirizzo del nodo | `{"node_address":…, "esg":…}` | Admin, via RPC |
| `weight-engine-reconciliation` | indirizzo del miner | `{"node_address":…, "reconciled":…, "epoch":…}` | Admin, via RPC |
| `weight-engine-activity` | indirizzo del nodo | `{"node_address":…, "tau":…, "epoch":…}` | **Derivato dalla catena** |

### 2.1 L'attività non è pubblicata da nessuno

`tau_i^{(e)}`, il contatore di attività per epoca, è ricavato **direttamente dai
blocchi confermati** dell'epoca da `ComputeActivityForEpoch()`
([`weight_reader.h`](../../weight_engine/weight_reader.h)). È una funzione
deterministica dei blocchi, quindi ogni nodo onesto ricalcola lo stesso valore:
nessun publisher, nessun rischio di scrittura duplicata, nessuna fiducia richiesta.

### 2.2 Ricostruzione del cluster `C_k`

La membership sfrutta il `jsonobjectmerge` nativo di MultiChain
(`getstreamkeysummary` / `mc_MergeValues`): tutti gli item pubblicati sotto la
chiave di un miner sono ripiegati in un unico oggetto i cui **nomi di campo** sono
gli indirizzi delle aziende associate. Il set `C_k` è quindi ricostruito senza
strutture ausiliarie. Parser:
`mc_ParseMembershipClusterJson` in
[`weight_records.h`](../../weight_engine/weight_records.h).

### 2.3 Ciclo di vita degli stream

`WeightStreamReader::EnsureInputStreams()` **crea** gli stream mancanti e vi si
**iscrive**: il primo nodo con permesso di creazione (il nodo genesis / admin) li
porta in esistenza, tutti gli altri li trovano già presenti e si iscrivono.

Gli stream sono creati **CLOSED**: serve `MC_PTP_WRITE` per pubblicare.

---

## 3. La pipeline di calcolo

Implementata verbatim dal capitolo di tesi «Gestione del peso» in
[`weight_engine.h`](../../weight_engine/weight_engine.h), che è un core **puro**:
dipende solo dalla libreria standard C++, quindi è testabile in isolamento.

```
c_i^(e)   = ESG_i * tau_i^(e) / kappa                            (contributo-pesato)
W_k^(e)   = ESG_Mk * ( tau_Mk^(e) + sum_{i in C_k} c_i^(e) )     (peso-grezzo)
A_k^(e)   = alpha * Theta^(e) * W_k^(e) / W_tot^(e)              (allocazione)
rho_k^(e) = R_k^(e) / ( A_k^(e) + B_k^(e-1) )  in [0,1]          (tasso-conformita)
B_k^(e)   = A_k^(e) - R_k^(e) + B_k^(e-1),  B_k^(0) = 0          (riconciliazione)
w_k^(1)   = W_k^(1)                                              (peso-finale, e = 1)
w_k^(e)   = W_k^(e) * [ rho_k^(e-1) * lambda + (1 - lambda) ]    (e >= 2)
```

Il peso intero finale è `ToIntegerWeight(w_k)`, sempre `>= 1` — requisito di
positività del peso, e anche il requisito di Efraimidis–Spirakis
([`wpoa_selector.h`](../wpoa_selector.h)).

### 3.1 Determinismo consensus-critical

`w_k` governa l'elezione del proposer, quindi **ogni nodo onesto deve calcolare lo
stesso intero**. Quattro scelte esplicite lo garantiscono:

1. **Doppia precisione** su tutta la pipeline, coerente col core del selettore
   (`ScoreFromEntropy64`), che già tratta il `double` IEEE-754 come deterministico
   sul validator set a binario identico.
2. **Somme in ordine di indirizzo ascendente** — sia `sum_i c_i` sia `W_tot`. Il
   floating point non è associativo: senza un ordine fissato il risultato
   dipenderebbe dall'ordine di input.
3. **Denominatore `<= 0` in `rho` restituisce `0`**, mai `NaN`/`Inf`. È la
   degenerazione che nella simulazione di riferimento propagava `#DIV/0!`; la forma
   di tesi con `lambda < 1` la evita per costruzione.
4. **`ToIntegerWeight`** arrotonda half-away-from-zero e clampa a
   `[1, UINT32_MAX]`.

### 3.2 Epoche e margine di stabilità

L'epoca è **1-based**:

```
epoch(height) = height / g_weight_epoch_length + 1
```

`HeightToEpoch()` in [`weight_engine.cpp`](../../weight_engine/weight_engine.cpp).
La stessa funzione è riusata dal registro del malus per allineare le epoche
([malus-registry.md](malus-registry.md)).

Un'epoca è calcolata **solo quando è sepolta**: il suo ultimo blocco deve stare
almeno `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` (attualmente `6`) blocchi sotto la
punta della catena. Poiché `tau` è derivato dai blocchi confermati dell'epoca,
questo impedisce che un riorg superficiale vicino alla punta faccia leggere blocchi
diversi a due nodi.

> Il margine è una costante a tempo di compilazione, non un parametro di catena. Il
> codice stesso raccomanda di promuoverlo a parametro hash-enforced prima della
> produzione, insieme a `weightepochlength`. Vedi
> [protocol-parameters.md §4](protocol-parameters.md).

### 3.3 Relazione col selettore — due livelli distinti

Il weight engine produce il peso **grezzo** `w_k`. La compressione whale `f(w_k)`
(`WPoASelector::ApplyDumping`, governata da `-dumpfunction`) resta applicata **a
valle**, al momento dell'elezione, e così il malus `w_eff = w * Psi`.

```
w_k  (engine)  ->  wpoa-weights  ->  w_eff = w * Psi  (malus)  ->  f(w_eff)  (dumping)  ->  elezione
```

I tre livelli sono complementari e vanno tenuti distinti nei diagrammi: `w_k` non è
il valore su cui si sorteggia.

### 3.4 Scostamento deliberato dalla simulazione di riferimento

Questo core segue la **tesi**, che definisce l'allocazione `A_k` sul peso **grezzo**
`W_k`. La simulazione di riferimento `Vers_2` ricava invece la propria voce
"GuadagnoEx" dal peso normalizzato e già corretto dal feedback.

Le due formulazioni **coincidono** per l'epoca 1 e per `W_k` in ogni epoca, ma le
quantità derivate dall'allocazione (`A_k`, `rho_k`, `B_k`) possono divergere dalla
seconda epoca in avanti. La forma di tesi è usata deliberatamente: l'allocazione
segue il merito certificato e corrente (`W_k`), evitando un anello di
feedback-sul-feedback.

---

## 4. Il thread dell'engine

`ThreadWeightEngine()` in
[`weight_engine.cpp`](../../weight_engine/weight_engine.cpp), lanciato da
`AppInit2`.

Ciclo, a ogni iterazione:

1. attende che il wallet, i permessi e la connettività siano pronti, e che l'initial
   block download sia concluso (stesso gate del thread wPoA);
2. `reader.EnsureInputStreams()` — crea gli stream mancanti e si iscrive;
3. individua l'**ultima epoca sepolta**;
4. calcola `w_k` **solo per il proprio** indirizzo di miner, e solo se il nodo locale
   è esso stesso un cluster miner (`ComputeLocalWeightForEpoch`: se
   `clusters.find(local_miner) == clusters.end()`, non c'è nulla da pubblicare);
5. pubblica tramite il percorso condiviso del registry, che assicura l'esistenza di
   `wpoa-weights` e l'idempotenza;
6. dorme `MC_WEIGHT_RETRY_INTERVAL_MS` e ripete.

Un nodo non ancora certificato, con input incompleti, o la cui epoca non è ancora
sepolta, semplicemente non pubblica: nessun errore, nessun valore parziale.

---

## 5. Precedenza: quale publisher scrive

**I due publisher sono mutuamente esclusivi già all'avvio.** Non esiste alcuna
sovrascrittura a runtime. In `AppInit2`, alla fine del blocco wPoA
([`init.cpp`](../../core/init.cpp)):

```cpp
if (g_wpoa_weights_enabled && pwalletMain && pwalletTxsMain && !fDisableWallet)
{
    if (g_weight_engine_enabled)
        threadGroup.create_thread(boost::bind(&ThreadWeightEngine));                     // peso dinamico w_k
    else
        threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight)); // peso statico
}
```

La differenza è **osservabile**: con l'engine attivo, `-weight=500` non produce un
record poi superato — non produce **nessun** record.

Entrambi i percorsi scrivono lo stesso stream. La lettura è
**newest-confirmed-wins** (`mc_AccumulateLatestWeight`,
[`weight_record.h`](../weight_record.h)), quindi il consenso è indifferente a quale
publisher abbia prodotto il record.

---

## 6. Modello di sicurezza — due gate indipendenti

Questa è la parte da leggere con attenzione: i due gate sono distinti e proteggono
cose diverse.

### 6.1 Gate on-chain — imposto dal consenso

Tutti gli stream in gioco — i tre di attestazione e `wpoa-weights` — sono
**CLOSED**. Solo un indirizzo che detiene `MC_PTP_WRITE` sullo stream può
pubblicare. È questo che blocca le scritture arbitrarie, ed è imposto dalle
permission granulari di MultiChain, non per convenzione.

```bash
multichain-cli <chain> grant <address> wpoa-weights.write
multichain-cli <chain> grant <address> weight-engine-esg.write
```

Un nodo senza il permesso vede la propria publish fallire e **non compare nella
mappa dei pesi: non ha alcun peso nell'elezione.**

> **Un nodo non autorizzato non può imporre il proprio peso in alcun modo**, né via
> `-weight`, né via RPC, né pubblicando direttamente.

### 6.2 Gate applicativo — solo questi RPC

Tre input sono **attestazioni esterne** non derivabili on-chain, quindi sono
pubblicati dalla governance tramite RPC admin, ciascuno instradato attraverso
`WeightPublisher` — l'**unico** punto di scrittura per questi stream.

| RPC (categoria `weight`) | Stream | Payload |
|---|---|---|
| `weightsetesg` | `weight-engine-esg` | `{node_address, esg}`, `esg > 0` |
| `weightsetmembership` | `weight-engine-membership` | chiave `miner`, payload `{<azienda>: ts}` |
| `weightsetreconciliation` | `weight-engine-reconciliation` | `{node_address, reconciled, epoch}`, `R >= 0`, `epoch >= 1` |

Registrati in [`rpclist.cpp`](../../rpc/rpclist.cpp). Ogni metodo, **prima** di
pubblicare:

1. valida il record in **round-trip** con lo *stesso* parser W1 che usa il reader
   (`mc_Parse*RecordJson`) — non può quindi emettere un record malformato che il
   reader rifiuterebbe;
2. verifica che l'indirizzo agente sia un **amministratore globale** (`CanAdmin`,
   [`weight_publisher.cpp`](../../weight_engine/weight_publisher.cpp));
3. verifica che quell'indirizzo abbia permesso di scrittura sullo stream;
4. pubblica **da** quell'indirizzo.

Ogni fallimento solleva `JSONRPCError`, così l'RPC chiamante restituisce un errore
preciso.

### 6.3 Limite noto — rischio accettato

Il permesso di scrittura è una concessione **indipendente** dallo status di admin, e
il reader **si fida di qualunque record confermato schema-valido, indipendentemente
dal publisher**.

> La garanzia «admin-only» tiene **solo se** gli operatori concedono `.write` su
> questi stream **esclusivamente** a indirizzi admin / di governance. Un non-admin a
> cui sia stato concesso `.write` potrebbe pubblicare un record schema-valido ma
> **forgiato**, usando il `publishfrom` generico anziché gli RPC `weightset*`, e il
> reader lo accetterebbe.

Irrigidimento raccomandato dal codice stesso: fare in modo che il reader richieda
`CanAdmin(publisher)` prima di ripiegare un record nella matematica del peso. Non
ancora implementato. Fino ad allora, la concessione dei permessi `.write` **è** il
controllo di sicurezza, e va trattata come tale.

---

## 7. Il flusso completo

Il diagramma del flusso di assegnazione del peso — dai due gate di autorizzazione
fino all'elezione del proposer — vive in **una sola sede** per evitare che due copie
divergano:

> **[implementation-status.md §0.1 — Assegnazione del peso di un nodo](implementation-status.md#01-assegnazione-del-peso-di-un-nodo--flusso-autorevole)**

Quel diagramma mostra esplicitamente che il canale autorevole è la scrittura RPC
sullo stream on-chain da parte di un nodo già autorizzato, che il valore on-chain
prevale sul flag locale `-weight`, e che un nodo non autorizzato non può imporre il
proprio peso per nessuna via.

## 8. Threading

Ogni lettura usa l'API wallet **non-WRP**, di basso livello e auto-lockante, e solo
item **confermati** — mai la famiglia `WRP*` / `getstreamkeysummary`, che restituisce
dati stantii fuori dal thread proprietario (vedi la nota in
[stream-weight-registry.md](stream-weight-registry.md)).

`ComputeActivityForEpoch` legge i file di blocco/undo fuori thread, prendendo
`cs_main` solo per uno snapshot minimo della catena.

---

## 9. File del modulo

| File | Ruolo |
|---|---|
| [`weight_streams.h`](../../weight_engine/weight_streams.h) | W1: nomi degli stream, nomi dei campi JSON, default dei parametri. Nessuna logica. |
| [`weight_records.h`](../../weight_engine/weight_records.h) | W1: parser puri dei record (`mc_Parse*RecordJson`), testabili in isolamento. |
| [`weight_engine.h`](../../weight_engine/weight_engine.h) | W2: il core puro di calcolo. Solo libreria standard. |
| [`weight_engine.cpp`](../../weight_engine/weight_engine.cpp) | W3: `HeightToEpoch`, `ThreadWeightEngine`, glue di nodo, globali di configurazione. |
| [`weight_reader.h`](../../weight_engine/weight_reader.h) / [`.cpp`](../../weight_engine/weight_reader.cpp) | W3: `WeightStreamReader` — ciclo di vita degli stream, letture confermate, `ComputeActivityForEpoch`. |
| [`weight_publisher.h`](../../weight_engine/weight_publisher.h) / [`.cpp`](../../weight_engine/weight_publisher.cpp) | W3: l'unico percorso di scrittura validato, e i tre RPC admin. |

### 9.1 Test

Suite di unit test **proprie**, con un runner separato da quello wPoA:

```bash
./src/weight_engine/test/run_unit_tests.sh              # entrambe le suite
./src/weight_engine/test/run_unit_tests.sh engine       # solo una
```

| Suite | File | Copertura |
|---|---|---|
| `records` | [`weight_records_tests.cpp`](../../weight_engine/test/weight_records_tests.cpp) | Parsing dei record, ricostruzione del cluster dal merge JSON. |
| `engine` | [`weight_engine_tests.cpp`](../../weight_engine/test/weight_engine_tests.cpp) | Indipendenza dall'ordine, guardia sul totale nullo, limiti di `rho`, ricorsione del bilancio, positività del peso, clamp di `ToIntegerWeight`, identità di allocazione su più cluster. |

Entrambe sono node-free: non richiedono la build del nodo. Vedi
[testing.md](testing.md).

---

## 10. Riferimenti

- [protocol-parameters.md](protocol-parameters.md) — i cinque parametri dell'engine, con range e
  validazione.
- [stream-weight-registry.md](stream-weight-registry.md) — lo stream `wpoa-weights`
  e la sua API di lettura.
- [malus-registry.md](malus-registry.md) — il registro del malus, che riusa
  `HeightToEpoch`.
- [implementation-status.md](implementation-status.md) — stato di implementazione.
