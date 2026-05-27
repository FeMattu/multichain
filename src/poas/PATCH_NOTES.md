# PoAS — Note di implementazione e correzione inconsistenze

## 1. Mappa delle inconsistenze trovate

| Problema nella bozza originale | Realtà nel codebase |
|---|---|
| `#include "util.h"` | `#include "utils/util.h"` |
| `#include "hash.h"` | `#include "structs/hash.h"` |
| `#include "uint256.h"` | `#include "structs/uint256.h"` |
| Modifica a `src/main.cpp` | Il file è `src/core/main.cpp` |
| Modifica a `src/validation.cpp` | **Non esiste**. La validazione del miner è in `src/protocol/multichainblock.cpp` → `CheckBlockPermissions()` |
| Funzione `GetEligibleMiners()` | **Non esiste**. Usare `mc_gState->m_Permissions->CanMine()` + `GetActiveMinerCount()` |
| Funzione `GetBlockMinerAddress()` | **Non esiste**. L'indirizzo si ricava da `block.vSigner` (già fatto in `CheckBlockPermissions`) |
| `boost::mutex` / `std::mutex` | Nel codebase si usa `boost::mutex` (C++03 compat) |
| File nuovo in `src/poas/` | OK — la directory deve essere creata e aggiunta al Makefile |

---

## 2. Patch per `src/miner/miner.cpp`

### 2a. Aggiunta degli include (in cima al file, dopo gli include esistenti)

```cpp
// === wPoA: include ===
#include "poas/wpoa_selector.h"
#include "poas/weight_registry.h"
#include "structs/base58.h"   // già presente in miner.cpp, ma necessario per CBitcoinAddress
```

### 2b. Funzione helper `ShouldIMineNextBlock`

Da inserire **prima** della funzione `BitcoinMiner` (cerca `void BitcoinMiner`):

```cpp
// === wPoA: selezione pesata del prossimo miner ===
// Chiamata dentro il loop di BitcoinMiner, dopo il controllo nativo
// di mining-diversity (cerca: "GetMaxActiveMinersCount" o "CanMine").
//
// @param hashPrevBlock    Hash del blocco sulla cima della chain ora
// @param myAddress        Indirizzo Base58 di questo nodo (da kMiner)
// @param eligibleMiners   Lista già filtrata: permesso mine + diversity OK
// @return true  → questo nodo è il vincitore, può proporre il blocco
//         false → non è il turno di questo nodo
static bool ShouldIMineNextBlock(
    const uint256&           hashPrevBlock,
    const std::string&       myAddress,
    const std::vector<std::string>& eligibleMiners)
{
    // Con 0 o 1 candidato non serve il calcolo wPoA
    if (eligibleMiners.empty()) return true;
    if (eligibleMiners.size() == 1)
        return (eligibleMiners[0] == myAddress);

    std::string winner = WPoASelector::selectWinner(eligibleMiners, hashPrevBlock);
    bool iAmWinner = (winner == myAddress);

    LogPrintf("wPoA: sono il vincitore? %s  (mio=%s  vincitore=%s)\n",
              iAmWinner ? "SI" : "NO", myAddress, winner);
    return iAmWinner;
}
```

### 2c. Come costruire `eligibleMiners` dentro `BitcoinMiner`

Cerca il punto in `BitcoinMiner` dove il nodo decide se deve dormire
o procedere al mining. Il blocco rilevante contiene chiamate a
`mc_gState->m_Permissions->CanMine(...)` e
`GetMaxActiveMinersCount()`.

**Subito dopo** il controllo nativo di diversity che decide se questo
nodo può minare, aggiungi:

```cpp
// === wPoA: raccolta candidati eleggibili ===
// Costruiamo la lista degli indirizzi che:
//   (a) hanno il permesso 'mine' sul blocco corrente
//   (b) soddisfano già il vincolo mining-diversity nativo
//
// NB: il metodo più semplice per la simulazione è passare solo
//     il nostro indirizzo e il numero di miner attivi — se vogliamo
//     la selezione completa dobbiamo iterare su tutti i miner noti.
//
// Per ora usiamo l'approccio minimo: se il nodo nativo ci dice che
// possiamo minare, passiamo la decisione finale a wPoA con la lista
// completa (che costruiamo sotto).

std::vector<std::string> eligibleMiners;
{
    // Itera sul wallet per trovare tutti gli indirizzi locali con
    // permesso mine — in una rete di test tutti i nodi sono locali
    // oppure noti. In produzione questa lista andrebbe distribuita
    // tramite un meccanismo separato (fuori scope per la simulazione).
    //
    // NOTA: nella simulazione il modo più rapido è popolare
    // eligibleMiners con gli indirizzi che hanno il permesso mine
    // leggendoli da mc_gState->m_Permissions (vedi GetMinerList RPC).
    // Per ora inseriamo l'indirizzo corrente + quelli noti al wallet.

    BOOST_FOREACH(const PAIRTYPE(CBitcoinAddress, CAddressBookData)& item,
                  pwalletMain->mapAddressBook)
    {
        CKeyID keyID;
        if (item.first.GetKeyID(keyID)) {
            if (mc_gState->m_Permissions->CanMine(NULL, keyID.begin())) {
                eligibleMiners.push_back(item.first.ToString());
            }
        }
    }
}

// Ottieni il tuo indirizzo Base58 corrente (da kMiner, già calcolato sopra)
std::string myAddressStr = CBitcoinAddress(kMiner.GetPubKey().GetID()).ToString();

if (!ShouldIMineNextBlock(pblock->hashPrevBlock, myAddressStr, eligibleMiners)) {
    // Non è il nostro turno secondo wPoA — dormiamo e riproviamo
    MilliSleep(200);
    continue; // torna all'inizio del loop di BitcoinMiner
}
// === fine wPoA ===
```

---

## 3. Patch per `src/protocol/multichainblock.cpp`

Questa è la posizione **corretta** per la validazione (NON `main.cpp`,
NON `validation.cpp` — che non esiste in questo codebase).

La funzione da modificare è `CheckBlockPermissions`, che si trova
alla riga ~925.

### Include da aggiungere in cima a `multichainblock.cpp`

```cpp
// === wPoA ===
#include "poas/wpoa_selector.h"
#include "poas/weight_registry.h"
```

### Modifica dentro `CheckBlockPermissions`

Trova il blocco:
```cpp
    if(checked)
    {    
        CKeyID pubKeyHash=pubKeyOut.GetID();
        memcpy(lpMinerAddress,pubKeyHash.begin(),20);
        if(!mc_gState->m_Permissions->CanMine(NULL,pubKeyHash.begin()))
        {
            LogPrintf("mchn: Permission denied for miner ...\n");
            checked = false;
        }
    }
```

**Dopo** il controllo `CanMine` esistente (e solo se `checked` è ancora
`true`), aggiungi la verifica wPoA:

```cpp
        // === wPoA: verifica che il miner sia il vincitore atteso ===
        if (checked && prev_block != NULL)
        {
            // Indirizzo Base58 del miner che ha firmato questo blocco
            std::string actualMiner =
                CBitcoinAddress(pubKeyHash).ToString();

            // Costruisci la lista degli eleggibili per questo blocco.
            // Usiamo lo stesso approccio del miner: tutti gli indirizzi
            // con permesso mine che soddisfano mining-diversity.
            // Per la simulazione, usiamo GetMinerCount() come proxy:
            // se c'è un solo miner, saltiamo il controllo wPoA.
            if (mc_gState->m_Permissions->GetMinerCount() > 1)
            {
                // In questa fase semplificata non abbiamo accesso al
                // wallet, quindi usiamo un'euristica: costruiamo la
                // lista degli indirizzi con permesso mine leggendo dal
                // ledger dei permessi tramite l'RPC interno.
                //
                // NOTA PER LA SIMULAZIONE: il modo più robusto è
                // mantenere una lista globale (es. vEligibleMiners)
                // aggiornata da BitcoinMiner e consultata qui.
                // Per ora procediamo solo se la lista è disponibile.

                extern std::vector<std::string> g_wPoAEligibleMiners; // vedi sotto
                extern uint256 g_wPoAPrevHash;

                if (!g_wPoAEligibleMiners.empty() &&
                    g_wPoAPrevHash == prev_block->GetBlockHash())
                {
                    std::string expectedWinner = WPoASelector::selectWinner(
                        g_wPoAEligibleMiners,
                        prev_block->GetBlockHash()
                    );

                    if (!expectedWinner.empty() && actualMiner != expectedWinner)
                    {
                        LogPrintf("wPoA: VIOLAZIONE — atteso %s, ricevuto %s\n",
                                  expectedWinner, actualMiner);
                        checked = false;
                        // La funzione già restituisce `checked` al chiamante
                        // che in ConnectBlock() chiama state.DoS(0, error(...))
                    }
                }
            }
        }
        // === fine wPoA ===
```

### Variabili globali da aggiungere (in `src/core/main.cpp` o in un nuovo `src/poas/wpoa_state.cpp`)

```cpp
// Stato condiviso tra miner.cpp e multichainblock.cpp
// Aggiornato da BitcoinMiner prima di proporre ogni blocco.
std::vector<std::string> g_wPoAEligibleMiners;
uint256                  g_wPoAPrevHash;
```

Da dichiarare come `extern` negli header e da aggiornare in
`miner.cpp` ogni volta che si costruisce `eligibleMiners`.

---

## 4. Inizializzazione dei pesi (in `src/core/init.cpp`)

Cerca la funzione `AppInit2`. Dopo la riga che inizializza
`mc_gState` (cerca `mc_gState = new mc_State`), aggiungi:

```cpp
// === wPoA: carica i pesi da <datadir>/weights.json ===
WeightRegistry::getInstance().loadFromFile();
// Include necessario in init.cpp:
//   #include "poas/weight_registry.h"
```

---

## 5. Aggiornamento del Makefile

In `src/Makefile.am`, nel blocco `libbitcoin_server_a_SOURCES` (o
equivalente), aggiungi i nuovi file `.cpp` se mai ne crei uno.
Per ora i due header-only non richiedono modifiche al Makefile.

Se crei `src/poas/wpoa_state.cpp` per le variabili globali, aggiungilo:

```makefile
  poas/wpoa_state.cpp \
```

---

## 6. Riepilogo file modificati/creati

| File | Operazione |
|---|---|
| `src/poas/weight_registry.h` | **NUOVO** — registry pesi (header-only) |
| `src/poas/wpoa_selector.h` | **NUOVO** — algoritmo selezione (header-only) |
| `src/poas/wpoa_state.cpp` | **NUOVO** (opzionale) — variabili globali condivise |
| `src/miner/miner.cpp` | **MODIFICA** — aggiunta selezione wPoA prima di proporre blocco |
| `src/protocol/multichainblock.cpp` | **MODIFICA** — verifica wPoA in `CheckBlockPermissions` |
| `src/core/init.cpp` | **MODIFICA** — caricamento weights.json all'avvio |

I file `src/core/main.cpp` e `src/validation.cpp` **NON vanno toccati**
per questa implementazione.
