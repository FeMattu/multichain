# `core/init.h` + `core/init.cpp` (parte wPoA)

Documentazione della **integrazione all'avvio del nodo** per la gestione del peso wPoA. `init.cpp` è enorme (gestisce tutto il bootstrap del nodo MultiChain): qui documentiamo **solo** le parti che riguardano il registro dei pesi. Il resto è il motore di avvio standard di MultiChain/Bitcoin.

`init.h` e `init.cpp` sono trattati insieme perché formano la classica coppia interfaccia/implementazione: `init.h` dichiara i simboli globali che gli altri moduli (incluso `stream_weight_registry.cpp`) usano; `init.cpp` li definisce e contiene `AppInit2`, la funzione di avvio.

## 1. Cosa fornisce `init.h` al sottosistema pesi

`init.h` è l'header che `stream_weight_registry.cpp` include (`#include "core/init.h"`) per accedere a tre cose:

```cpp
extern CWallet* pwalletMain;          // il wallet principale
extern mc_WalletTxs* pwalletTxsMain;  // il DB transazioni del wallet
...
bool ShutdownRequested();             // true quando è stato richiesto lo spegnimento
```

- `pwalletMain` — puntatore globale al wallet (`CWallet`). `ResolveLocalAddress()` lo usa per ricavare l'indirizzo del validatore. `extern` = dichiarato qui, definito nel `.cpp`.
- `pwalletTxsMain` — puntatore globale al database delle transazioni del wallet (`mc_WalletTxs`). È il puntatore "in prestito" passato al costruttore di `StreamWeightRegistry` e usato per tutte le letture (`FindEntity`/`GetList`/`GetWalletTx`).
- `ShutdownRequested()` — usata dal thread `ThreadRegisterNodeWeight` e da `WaitForLocalWeight` per interrompere i loop quando il nodo sta chiudendo.

Le **forward declaration** in cima all'header:
```cpp
class CWallet;
struct mc_WalletTxs;
```
dichiarano i tipi senza includerne le definizioni pesanti (stesso principio spiegato in `docs/stream_weight_registry.md`): all'header basta poterli usare come puntatori.

Nota anche:
```cpp
bool AppInit2(boost::thread_group& threadGroup, int OutputPipe=STDOUT_FILENO);
```
È la firma della funzione di avvio del nodo. Il parametro `boost::thread_group& threadGroup` è il **contenitore di thread** di Boost in cui vengono registrati tutti i thread di background del nodo — ed è lì che verrà agganciato il thread di registrazione del peso.

## 2. L'integrazione in `init.cpp`

### 2.1 L'include (riga 43)

```cpp
#include "poas/stream_weight_registry.h"
```
Porta in `init.cpp` la costante `MC_WPOA_DEFAULT_WEIGHT`, la variabile `g_node_weight` e la funzione `ThreadRegisterNodeWeight` — tutto ciò che serve per avviare la registrazione.

### 2.2 L'help del parametro `-weight` (riga 564)

Dentro `HelpMessage(...)` (la funzione che genera il testo di `--help`):

```cpp
strUsage += "  -weight=<n>                              "
    + strprintf(_("wPoA validator weight for this node, positive integer "
                  "(default: %u). Registered on the wpoa-weights stream."),
                MC_WPOA_DEFAULT_WEIGHT) + "\n";
```

- `strUsage += ...` — accumula righe di testo di aiuto.
- `_( "..." )` — macro di **traduzione** (i18n) di Bitcoin/MultiChain: marca la stringa come traducibile.
- `strprintf(...)` — versione type-safe di `sprintf` che ritorna uno `std::string`; `%u` viene sostituito con `MC_WPOA_DEFAULT_WEIGHT` (100).

Effetto: `multichaind --help` documenta il parametro `-weight`.

### 2.3 Il blocco di registrazione (righe 3171-3191)

Questo è il punto in cui il nodo, alla fine di `AppInit2`, configura e avvia la registrazione del peso:

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

Analisi riga per riga:

- **`#ifdef ENABLE_WALLET` … `#endif`** — direttiva del preprocessore: tutto il blocco viene compilato **solo** se il wallet è abilitato. Il peso richiede un wallet (per firmare e pagare le transazioni di create/publish). Coerentemente, in `rpclist.cpp` anche le 3 RPC sono dentro `#ifdef ENABLE_WALLET`.

- **`{ ... }`** — lo scope a graffe crea un blocco locale così le variabili (`weight_arg`) non inquinano il resto di `AppInit2`.

- **`GetArg("-weight", MC_WPOA_DEFAULT_WEIGHT)`** — legge il parametro `-weight` da riga di comando / file di configurazione. Se assente, usa il default 100. Ritorna un `int64_t` così può rilevare valori negativi/zero prima del cast.

- **`if (weight_arg <= 0) return InitError(...)`** — validazione: il peso deve essere strettamente positivo. `InitError(msg)` è l'helper standard di MultiChain che registra l'errore, lo mostra all'utente e fa fallire l'avvio (ritorna `false` da `AppInit2`). `strprintf` con `%d` inserisce il valore invalido nel messaggio.

- **`g_node_weight = (uint32_t)weight_arg;`** — imposta la variabile globale (definita in `stream_weight_registry.cpp`, dichiarata `extern` nel suo header). Da questo momento tutto il resto del sistema conosce il peso configurato. Il cast è sicuro perché `weight_arg > 0` è già garantito.

- **`LogPrintf(...)`** — logga il peso configurato su `debug.log`.

- **`if (pwalletMain && pwalletTxsMain && !fDisableWallet)`** — lancia il thread solo se il wallet è effettivamente disponibile e non disabilitato a runtime (`fDisableWallet`). Senza wallet non si potrebbe pubblicare, quindi non ha senso avviare il thread.

- **`threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight))`** — il cuore dell'integrazione:
  - `boost::bind(&ThreadRegisterNodeWeight, g_node_weight)` crea un **funtore** (oggetto chiamabile) che, quando invocato, esegue `ThreadRegisterNodeWeight(g_node_weight)`. `boost::bind` "congela" l'argomento `g_node_weight` dentro la chiamata.
  - `threadGroup.create_thread(...)` crea un nuovo thread di sistema che esegue quel funtore e lo registra nel `boost::thread_group` del nodo (così verrà joinato/interrotto ordinatamente allo shutdown).
  - **Perché un thread separato?** Il commento lo spiega: la registrazione è una *transazione*, quindi può avvenire solo quando wallet, permessi, stream e connettività di rete sono pronti. Eseguirla inline bloccherebbe l'avvio del nodo. Delegandola a un thread di background, `AppInit2` ritorna subito e il thread ritenta finché le condizioni non sono soddisfatte (cfr. `NodeReadyForWeightRegistration` in `stream_weight_registry.cpp`).

- **`/* MCHN START */ ... /* MCHN END */`** — commenti-marcatori usati in tutto il codebase MultiChain per delimitare le aggiunte MultiChain rispetto al codice Bitcoin originale.

## 3. Il flusso completo all'avvio

```
  Avvio nodo: multichaind -weight=250
        │
        ▼
  AppInit2(threadGroup)                        [init.cpp]
   ├─ ... inizializza wallet, catena, RPC ...
   ├─ GetArg("-weight", 100)  ──► weight_arg = 250
   ├─ valida (>0)             ──► altrimenti InitError → avvio fallisce
   ├─ g_node_weight = 250                      [scrive la globale di stream_weight_registry.cpp]
   └─ threadGroup.create_thread(
           ThreadRegisterNodeWeight, 250)      [lancia il thread di background]
                     │
                     ▼
        ThreadRegisterNodeWeight(250)          [stream_weight_registry.cpp]
          loop: attende readiness → RegisterLocalWeight(250)
                → create/subscribe/publish sullo stream "wpoa-weights"
```

## 4. Collegamenti con gli altri file

- **`init.h` → `stream_weight_registry.cpp`**: fornisce `pwalletMain`, `pwalletTxsMain`, `ShutdownRequested()` usati dal registro.
- **`stream_weight_registry.h` → `init.cpp`**: fornisce `MC_WPOA_DEFAULT_WEIGHT`, `g_node_weight` e `ThreadRegisterNodeWeight` usati nel blocco di avvio.
- **`init.cpp`** è il **solo** posto che avvia il thread e imposta `g_node_weight`; è il ponte tra la configurazione dell'utente (`-weight`) e il sottosistema pesi.
- Le RPC di lettura (in `rpclist.cpp`) sono **indipendenti** da questo avvio: funzionano anche se il thread non ha ancora registrato nulla (ritornano semplicemente 0 / mappa vuota).

> Per il dettaglio del thread e della classe vedi `docs/stream_weight_registry.md`; per il parsing vedi `docs/weight_record.md`.
