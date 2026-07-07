# `stream_weight_registry.h` + `stream_weight_registry.cpp`

Documentazione tecnica dettagliata del **cuore della gestione del peso wPoA (Weighted Proof of Authority) — Fase 1**.

Questi due file formano una singola unità di compilazione logica (interfaccia + implementazione) e vengono trattati insieme perché sono strettamente accoppiati:

| File | Ruolo |
|------|-------|
| `stream_weight_registry.h` | **Interfaccia pubblica** (dichiarazioni): la classe `StreamWeightRegistry`, le costanti, la variabile globale `g_node_weight`, il punto di ingresso del thread `ThreadRegisterNodeWeight` e i prototipi delle 3 funzioni RPC. È ciò che gli altri file (`init.cpp`, `rpclist.cpp`) includono per "vedere" il registro dei pesi. |
| `stream_weight_registry.cpp` | **Implementazione** (definizioni): tutta la logica reale di creazione stream, sottoscrizione, pubblicazione, lettura e decodifica dei record di peso. |

### Perché la separazione `.h` / `.cpp`?
È la regola classica C++ di separazione interfaccia/implementazione:

- **L'header contiene solo dichiarazioni** (cosa esiste) → può essere incluso da molti file senza duplicare codice ed evitando errori di *multiple definition* al link.
- **Il `.cpp` contiene le definizioni** (come funziona) → compilato una sola volta in un oggetto `.o`.

Nell'header vengono usate le **forward declaration** invece degli `#include` pesanti:

```cpp
struct mc_WalletTxs;
struct mc_EntityDetails;
```

Questo dichiara "esistono questi tipi" senza tirare dentro tutte le loro definizioni (che vivono in header pesanti del wallet MultiChain). Poiché l'header usa questi tipi solo come **puntatori** (`mc_WalletTxs*`, `mc_EntityDetails*`), al compilatore basta sapere che sono tipi: la dimensione di un puntatore è nota a prescindere. Le definizioni complete vengono incluse solo nel `.cpp`, dove servono davvero. Risultato: chi include l'header (es. `rpclist.cpp`) compila più velocemente e non dipende dall'intero sottosistema wallet.

---

## 1. L'header `stream_weight_registry.h`

### 1.1 Include e loro provenienza

```cpp
#include <map>
#include <string>
#include <stdint.h>
#include "json/json_spirit_value.h"
```

- `<map>` — `std::map`, container ordinato chiave→valore della **STL** (Standard Template Library C++). Usato per `std::map<std::string, uint32_t>` = mappa indirizzo→peso.
- `<string>` — `std::string`, sempre STL.
- `<stdint.h>` — header **C standard** che definisce i tipi interi a larghezza fissa: `uint32_t` (intero senza segno a 32 bit, 0…4.294.967.295) e `int64_t` (intero con segno a 64 bit). Il peso è un `uint32_t`: non può essere negativo e 32 bit sono ampiamente sufficienti.
- `"json/json_spirit_value.h"` — **json_spirit**, la libreria JSON usata in tutto MultiChain/Bitcoin Core. Fornisce `json_spirit::Value`, `Object`, `Array`, `Pair`. Serve qui perché i prototipi RPC ritornano `json_spirit::Value`.

### 1.2 Le due costanti (`#define`)

```cpp
#define MC_WPOA_WEIGHTS_STREAM_NAME     "wpoa-weights"
#define MC_WPOA_DEFAULT_WEIGHT          100
```

- `MC_WPOA_WEIGHTS_STREAM_NAME` — il nome dello **stream MultiChain** append-only su cui vengono scritti i record di peso. Uno "stream" in MultiChain è un registro append-only di elementi chiave/dato, nativo del protocollo.
- `MC_WPOA_DEFAULT_WEIGHT` — peso di default (100) se il nodo non passa `-weight` sulla riga di comando.

Sono `#define` (macro del preprocessore) e non `const`: è lo stile del codice MultiChain, che prefissa tutte le costanti globali con `MC_`. Vengono sostituite testualmente dal preprocessore prima della compilazione.

### 1.3 La classe `StreamWeightRegistry` — la "facade"

L'header la descrive come una *"thin, opaque facade over the wpoa-weights stream"*. **Facade** = pattern che nasconde la complessità interna (stream MultiChain, transazioni, lettura DB) dietro pochi metodi semplici. Il resto del nodo non tocca mai lo stream direttamente: usa solo questi metodi pubblici.

#### Metodi pubblici (contratto verso l'esterno)

| Metodo | Cosa restituisce / fa |
|--------|-----------------------|
| `StreamWeightRegistry(mc_WalletTxs* pwalletIn)` | Costruttore: risolve l'indirizzo locale e memorizza il nome dello stream. |
| `bool RegisterLocalWeight(uint32_t weight)` | Registra il peso di questo nodo sullo stream (crea stream + sottoscrive + pubblica se serve). |
| `uint32_t GetLocalWeight()` | Ultimo peso **confermato** di questo nodo, 0 se non registrato. |
| `std::map<std::string,uint32_t> GetAllNodesWeights()` | Mappa indirizzo→peso per ogni validatore. |
| `uint32_t GetNodeWeight(const std::string&)` | Peso confermato di un indirizzo specifico. |
| `bool IsLocalWeightRegistered()` | true se esiste almeno un record confermato per questo nodo. |
| `void DebugPrintWeights()` | Stampa l'intero stato del registro nel log. |
| `bool WaitForLocalWeight(...)` | Blocca finché il peso pubblicato non è confermato on-chain (con timeout). |
| `std::string GetLocalAddress() const` | Getter inline dell'indirizzo locale risolto. |

Nota su `GetLocalAddress() const`: è definito **inline nell'header** (`{ return m_LocalAddress; }`) ed è marcato `const`, cioè promette di non modificare lo stato dell'oggetto. È un semplice getter, quindi non serve metterlo nel `.cpp`.

#### Membri privati (stato interno)

```cpp
mc_WalletTxs* m_pWalletTxs;   //!< puntatore "in prestito", non posseduto
std::string   m_StreamName;   //!< "wpoa-weights"
std::string   m_LocalAddress; //!< indirizzo nodo, calcolato una volta
bool m_CreateAttempted;       //!< evita di emettere >1 tx create
bool m_SubscribeAttempted;    //!< evita subscribe ridondanti
```

- Il prefisso `m_` indica "member" (convenzione MultiChain).
- `//!<` è un commento in stile **Doxygen** ("documenta il membro alla sua sinistra").
- **"borrowed pointer, not owned"**: `m_pWalletTxs` punta a un oggetto (`pwalletTxsMain`) creato e distrutto altrove (in `init.cpp`). Il distruttore `~StreamWeightRegistry` **non** lo libera — vedi commento nel `.cpp`. Questo evita double-free.
- I due flag `m_CreateAttempted`/`m_SubscribeAttempted` implementano un'idempotenza: garantiscono che il thread di retry non spammi transazioni `create`/`subscribe` a ogni giro.

#### Metodi privati (dettagli implementativi nascosti)

```cpp
void ResolveLocalAddress();
bool GetStreamEntity(mc_EntityDetails* entity);
bool EnsureStreamExists();
bool EnsureSubscribed();
bool PublishWeightRecord(uint32_t weight);
bool ReadAllRecords(std::map<std::string, uint32_t>& out_latest);
```

Sono privati perché sono i "mattoni" usati dai metodi pubblici: nessun altro file deve poterli chiamare.

### 1.4 Elementi globali dichiarati nell'header

```cpp
void ThreadRegisterNodeWeight(uint32_t weight);
extern uint32_t g_node_weight;

json_spirit::Value getlocalweight(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getallweights(const json_spirit::Array& params, bool fHelp);
json_spirit::Value getnodeweight(const json_spirit::Array& params, bool fHelp);
```

- `ThreadRegisterNodeWeight` — funzione libera (non metodo) eseguita come **thread in background**, lanciata da `AppInit2` in `init.cpp`.
- `extern uint32_t g_node_weight` — `extern` significa "questa variabile è **definita altrove**" (nel `.cpp`, riga 23). L'header la dichiara soltanto, così più file possono riferirsi alla stessa variabile globale senza duplicarla. Il prefisso `g_` = global.
- I 3 prototipi RPC hanno la **firma standard degli handler RPC di Bitcoin/MultiChain**: `Value f(const Array& params, bool fHelp)`. Sono dichiarati qui e registrati in `rpclist.cpp` (vedi `docs/rpclist.md`).

---

## 2. L'implementazione `stream_weight_registry.cpp`

### 2.1 Include e cosa portano

```cpp
#include "poas/stream_weight_registry.h"
#include "rpc/rpcwallet.h"      // create/publish/subscribe, wallet.h, wallettxs.h, multichain.h
#include "rpc/rpcutils.h"       // OpReturnFormatEntry
#include "structs/base58.h"     // CBitcoinAddress
#include "core/init.h"          // pwalletMain, pwalletTxsMain, ShutdownRequested
#include "core/main.h"          // chainActive, cs_main, IsInitialBlockDownload
#include "utils/util.h"         // GetArg, LogPrintf, RenameThread, GetBoolArg
#include "utils/utiltime.h"     // MilliSleep, GetTime
#include "poas/weight_record.h" // mc_ParseWeightRecordJson, mc_AccumulateLatestWeight
#include <boost/foreach.hpp>
```

Ogni include è la fonte di simboli usati nel file:

- `rpcwallet.h` → dichiara gli handler RPC riusati come funzioni C++: `createcmd`, `subscribe`, `publish`. Tira dentro anche `wallettxs.h` (tipi `mc_WalletTxs`, `mc_TxEntityStat`, `mc_TxEntityRow`, `mc_Buffer`) e `multichain.h` (`mc_gState`, `mc_EntityDetails`, costanti `MC_ENT_TYPE_*`, `MC_TET_*`, `MC_AST_*`).
- `rpcutils.h` → `OpReturnFormatEntry`, la funzione che decodifica il payload di un OP_RETURN in un `json_spirit::Value`.
- `base58.h` → `CBitcoinAddress`, la classe che converte una chiave pubblica/ID in una stringa indirizzo in formato Base58Check.
- `init.h` → i puntatori globali `pwalletMain`, `pwalletTxsMain` e `ShutdownRequested()`.
- `main.h` → `chainActive` (la catena attiva), il lock globale `cs_main`, `IsInitialBlockDownload()`.
- `util.h` → utility MultiChain: `GetArg`/`GetBoolArg` (lettura parametri CLI/config), `LogPrintf` (log su `debug.log`), `RenameThread` (dà un nome al thread nell'OS).
- `utiltime.h` → `MilliSleep` (sleep in ms) e `GetTime` (timestamp UNIX in secondi).
- `weight_record.h` → i due helper puri di parsing/aggregazione. Vedi `docs/weight_record.md`.
- `<boost/foreach.hpp>` → la macro `BOOST_FOREACH` della libreria **Boost** (qui inclusa perché usata indirettamente; il loop principale usa comunque cicli `for` classici).

```cpp
using namespace std;
using namespace json_spirit;
```
Portano nello scope i simboli di STL (`string`, `map`…) e json_spirit (`Value`, `Object`, `Array`, `Pair`) senza doverli qualificare col namespace.

### 2.2 La variabile globale e le costanti di modulo

```cpp
uint32_t g_node_weight = MC_WPOA_DEFAULT_WEIGHT;   // riga 23 — QUI è la DEFINIZIONE
```
Questa è la **definizione** della variabile dichiarata `extern` nell'header. Inizializzata a 100; sovrascritta da `init.cpp` con il valore di `-weight`.

```cpp
static const int MC_WPOA_RETRY_INTERVAL_MS = 3000;   // ogni quanto ritenta il thread
static const int MC_WPOA_MAX_ATTEMPTS      = 200;    // ~10 minuti nel caso peggiore
static const int MC_WPOA_CONFIRM_ATTEMPTS  = 20;     // 20*3s = ~60s di attesa conferma
```
`static` a livello di file = **visibilità limitata a questa unità di compilazione** (linkage interno): non collidono con simboli omonimi altrove. Sono i parametri di temporizzazione del thread di registrazione.

### 2.3 Costruttore, distruttore e risoluzione indirizzo

```cpp
StreamWeightRegistry::StreamWeightRegistry(mc_WalletTxs* pwalletIn)
{
    m_pWalletTxs         = pwalletIn;
    m_StreamName         = MC_WPOA_WEIGHTS_STREAM_NAME;
    m_LocalAddress       = "";
    m_CreateAttempted    = false;
    m_SubscribeAttempted = false;
    ResolveLocalAddress();
}
```
Il costruttore memorizza il puntatore al wallet-txs, imposta il nome dello stream, azzera i flag e poi calcola subito l'indirizzo locale.

```cpp
StreamWeightRegistry::~StreamWeightRegistry()
{
    // m_pWalletTxs is borrowed, nothing to free.
}
```
Distruttore vuoto: conferma che il puntatore è "in prestito".

#### `ResolveLocalAddress()` — chi è questo validatore?

```cpp
void StreamWeightRegistry::ResolveLocalAddress()
{
    m_LocalAddress = "unknown";
    if (pwalletMain == NULL) { /* WARNING, usa placeholder */ return; }

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

Riga per riga:
- `CPubKey pkey;` — `CPubKey` è la classe MultiChain/Bitcoin che rappresenta una **chiave pubblica** ECDSA.
- `LOCK(pwalletMain->cs_wallet);` — `LOCK` è una macro MultiChain (basata su `boost::mutex`/`CCriticalSection`) che acquisisce un mutex per la durata dello scope `{}`. `cs_wallet` protegge le strutture del wallet da accessi concorrenti. Serve perché questa funzione può essere chiamata sia da un RPC (thread server) sia dal thread di registrazione in background.
- **Priorità nella scelta dell'indirizzo**: un peso wPoA appartiene a un miner/validatore, quindi si preferisce:
  1. l'indirizzo di **mining** (`MC_PTP_MINE` = permesso di minare),
  2. altrimenti quello di **connect** (`MC_PTP_CONNECT` = permesso di connettersi),
  3. altrimenti la **chiave di default** del wallet (`vchDefaultKey`).
  `MC_PTP_*` sono i bit dei permessi MultiChain. `GetKeyFromAddressBook` cerca nel wallet una chiave con quel permesso.
- `pkey.IsValid()` — verifica che sia una chiave valida.
- `CBitcoinAddress(pkey.GetID()).ToString()` — `pkey.GetID()` produce un `CKeyID` (hash160 della chiave pubblica); `CBitcoinAddress(...)` lo incapsula e `.ToString()` lo serializza nel formato indirizzo Base58Check leggibile. Questo è l'identificatore del validatore usato come **chiave** nello stream.

### 2.4 Gestione dello stream

#### `GetStreamEntity()` — lo stream esiste?

```cpp
bool StreamWeightRegistry::GetStreamEntity(mc_EntityDetails* entity)
{
    if (mc_gState == NULL || mc_gState->m_Assets == NULL) return false;
    if (mc_gState->m_Assets->FindEntityByName(entity, m_StreamName.c_str()) == 0) return false;
    return (entity->GetEntityType() == MC_ENT_TYPE_STREAM);
}
```
- `mc_gState` — lo **stato globale MultiChain** (singleton), che contiene tutte le entità (asset, stream, ecc.).
- `mc_gState->m_Assets` — il database delle entità (`mc_AssetDB`).
- `FindEntityByName(entity, name)` — cerca un'entità per nome; ritorna 0 se non trovata, riempie `*entity` se trovata.
- `entity->GetEntityType() == MC_ENT_TYPE_STREAM` — conferma che l'entità trovata sia effettivamente uno stream e non, ad es., un asset con lo stesso nome.
- `m_StreamName.c_str()` — converte lo `std::string` in `const char*` C-string, richiesto dall'API MultiChain.

#### `EnsureStreamExists()` — crea lo stream se manca

```cpp
mc_EntityDetails entity;
if (GetStreamEntity(&entity)) return true;      // già esiste
if (m_CreateAttempted) return false;            // create già mandato, aspetto conferma

Array params;
params.push_back(string("stream"));
params.push_back(m_StreamName);
params.push_back(true);

m_CreateAttempted = true;
try {
    Value result = createcmd(params, false);
    LogPrintf("... create tx broadcast: %s\n", ..., result.get_str().c_str());
}
catch (const Object& objError) { /* permesso create mancante? */ }
catch (const std::exception& e) { /* altro errore */ }
return false; // non usabile finché non confermato
```

Punti chiave:
- Costruisce un `Array` json_spirit equivalente ai parametri della RPC `create ["stream", "wpoa-weights", true]`. Il `true` finale rende lo stream **aperto**: qualsiasi indirizzo con permesso di scrittura può pubblicare.
- `createcmd(params, false)` — chiama **direttamente in-process** l'handler della RPC `create` (lo stesso invocato da riga di comando). Il secondo parametro `false` = `fHelp` (non vogliamo l'help, vogliamo eseguire). Questo è il pattern centrale: **le scritture riusano gli handler RPC di MultiChain** anziché reimplementare la costruzione delle transazioni.
- **Doppio `catch`**: gli handler RPC di MultiChain lanciano `json_spirit::Object` (l'oggetto errore JSON-RPC) in caso di errore di dominio, oppure `std::exception` per errori generici. Si catturano entrambi.
- `m_CreateAttempted = true` **prima** del try: anche se fallisce, non ritenteremo la creazione a ogni giro (evita spam di transazioni).
- Ritorna `false` anche in caso di successo del broadcast: lo stream diventa utilizzabile **solo quando la transazione `create` viene confermata in un blocco**.

#### `EnsureSubscribed()` — questo nodo legge lo stream?

```cpp
mc_EntityDetails entity;
if (!GetStreamEntity(&entity)) return false;

mc_TxEntityStat entStat;
entStat.Zero();
memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
if (m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat)) return true;  // già sottoscritto

if (m_SubscribeAttempted) return false;

Array params;
params.push_back(m_StreamName);
m_SubscribeAttempted = true;
try {
    subscribe(params, false);
    return m_pWalletTxs != NULL && m_pWalletTxs->WRPFindEntity(&entStat);
}
catch (...) { ... }
return false;
```

- `mc_TxEntityStat` — struttura che identifica un'"entità" (qui lo stream) nel **database delle transazioni del wallet** (`mc_WalletTxs`). `Zero()` la azzera.
- `entity.GetTxID()` restituisce il TXID (32 byte) della transazione che ha creato lo stream. `MC_AST_SHORT_TXID_OFFSET` e `MC_AST_SHORT_TXID_SIZE` estraggono lo **short-txid** (una parte del txid usata come identificatore compatto dello stream). Il `memcpy` copia questi byte in `entStat`.
- `entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;` — combina due flag: `MC_TET_STREAM` (è uno stream) e `MC_TET_CHAINPOS` (indicizzato per posizione in catena). L'OR bit-a-bit (`|`) unisce i due flag in un unico valore.
- `WRPFindEntity` — cerca l'entità nell'indice del wallet: se la trova, il nodo è già sottoscritto.
- Se non sottoscritto, chiama l'handler RPC `subscribe(["wpoa-weights"])`. Dopo la subscribe ricontrolla, perché per uno stream corto l'import può completarsi subito.

### 2.5 Scrittura di un record: `PublishWeightRecord()`

```cpp
Object record;
record.push_back(Pair("timestamp", (int64_t)GetTime()));
record.push_back(Pair("node_address", m_LocalAddress));
record.push_back(Pair("weight", (int64_t)weight));

int height = 0;
{
    LOCK(cs_main);
    if (chainActive.Tip() != NULL) height = chainActive.Height();
}
record.push_back(Pair("height", height));

Object data_obj;
data_obj.push_back(Pair("json", record));

Array params;
params.push_back(m_StreamName);
params.push_back(m_LocalAddress);
params.push_back(data_obj);

try {
    Value result = publish(params, false);
    LogPrintf("... Weight registered: %s = %u (tx %s)\n", ...);
    return true;
}
catch (...) { ... }
return false;
```

Costruisce il payload JSON del record:
- `Object` e `Pair` sono tipi json_spirit. `Pair(nome, valore)` è una coppia chiave/valore; `Object` è la lista di coppie.
- `GetTime()` → timestamp UNIX corrente (secondi). Castato a `int64_t` perché json_spirit distingue interi a 64 bit.
- `node_address` → l'indirizzo del validatore.
- `weight` → il peso (castato a `int64_t`).
- `height` → l'altezza corrente della catena. `chainActive.Tip()` è il blocco in cima; `chainActive.Height()` la sua altezza. Protetto da `LOCK(cs_main)` perché la catena può cambiare in concorrenza.
- Il record viene incapsulato in `{"json": <record>}`: è il formato con cui MultiChain rappresenta un dato **UBJSON** in uno stream item.

Infine chiama `publish(["wpoa-weights", <indirizzo-come-chiave>, {"json":{...}}])`. La **chiave** dello stream item è l'indirizzo del nodo: così ogni nodo scrive record sotto la propria chiave, e leggendo la storia si vede l'evoluzione del peso di ciascun indirizzo.

### 2.6 Orchestrazione della scrittura: `RegisterLocalWeight()`

```cpp
if (weight == 0) { /* ERROR: weight must be > 0 */ return false; }
if (m_pWalletTxs == NULL || pwalletMain == NULL) { /* ERROR wallet */ return false; }

if (!EnsureStreamExists()) return false;   // creato ora o in attesa di conferma
if (!EnsureSubscribed())   return false;   // subscribe/import in corso

uint32_t current = GetNodeWeight(m_LocalAddress);
if (current == weight) { /* già registrato */ return true; }   // IDEMPOTENZA

return PublishWeightRecord(weight);
```

Sequenza: valida input → assicura stream → assicura sottoscrizione → **controlla idempotenza** (se l'ultimo peso confermato è già uguale, non ripubblica) → pubblica. Questo metodo è progettato per essere chiamato ripetutamente in un loop di retry senza effetti collaterali.

### 2.7 Lettura dei record — il percorso più delicato

#### `DecodeWeightRecord()` (funzione statica di file)

```cpp
static bool DecodeWeightRecord(const CWalletTx& wtx, const unsigned char* stream_short_txid,
                               string& out_addr, uint32_t& out_weight)
{
    mc_Script script; // istanza locale -> thread-safe (nessun buffer condiviso)

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
        if (mc_ParseWeightRecordJson(v, out_addr, out_weight)) return true;
    }
    return false;
}
```

`static` = funzione visibile solo in questo file. Estrae `(indirizzo, peso)` da una transazione stream item. Passaggi:

- `CWalletTx` — transazione così come memorizzata nel wallet; `wtx.vout` è il vettore degli output.
- `CScript` / `scriptPubKey` — lo script di blocco dell'output. I dati di uno stream item viaggiano in un output **OP_RETURN**.
- `mc_Script` — parser di script MultiChain. **Viene creato localmente dentro la funzione**: è la chiave della thread-safety, perché evita di condividere buffer temporanei globali tra thread diversi (il commento lo sottolinea).
- `SetScript(...)` — carica i byte grezzi dello scriptPubKey nel parser. Il cast `(unsigned char*)(&pc[0])` prende il puntatore ai byte, `spk.end() - pc` la lunghezza, `MC_SCR_TYPE_SCRIPTPUBKEY` il tipo.
- `IsOpReturnScript()` — salta gli output che non sono OP_RETURN (es. l'output di change).
- `ExtractAndDeleteDataFormat(...)` — rimuove l'elemento meta di formato-dati (mirroring di `StreamItemEntry`, la funzione MultiChain che formatta gli item).
- `SetElement(0)` + `GetEntity(short_txid)` — l'elemento 0 dell'OP_RETURN deve identificare lo stream. `memcmp` confronta lo short-txid con quello del nostro stream: se diverso, l'item appartiene a un altro stream → skip.
- `GetData(n-1, &data_size)` — l'ultimo elemento contiene il dato dell'item (in Fase 1 solo record on-chain).
- **`OpReturnFormatEntry(...)`** — punto critico. Decodifica i byte in un `json_spirit::Value`. Il commento spiega perché si usa l'**overload a 6 argomenti** (con `format_text` in uscita): questo produce direttamente `{"json": {...}}`, esattamente come fanno `StreamItemEntry`/`liststreamitems`. L'overload a 3 argomenti invece incapsulerebbe come `{"format":"json","formatdata":{"json":{...}}}`, e `mc_ParseWeightRecordJson` lo rifiuterebbe perché non c'è la chiave `"json"` al livello superiore. **Questa discrepanza era la causa del bug** per cui la decodifica falliva silenziosamente per ogni item (cfr. l'ultimo commit "stream read bug fix").
- Infine `mc_ParseWeightRecordJson(v, out_addr, out_weight)` (da `weight_record.h`) estrae indirizzo e peso. Se riesce, ritorna.

#### `ReadAllRecords()` — cuore della lettura

```cpp
static const bool dbg = GetBoolArg("-wpoadebug", false);
out_latest.clear();
if (m_pWalletTxs == NULL) { ...; return false; }

mc_EntityDetails entity;
if (!GetStreamEntity(&entity)) { ...; return false; } // stream non creato

mc_TxEntityStat entStat;
entStat.Zero();
memcpy(&entStat, entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET, MC_AST_SHORT_TXID_SIZE);
entStat.m_Entity.m_EntityType = MC_TET_STREAM | MC_TET_CHAINPOS;
```

`static const bool dbg` — letto **una sola volta** (per via di `static`) dal flag `-wpoadebug`. Attiva log verbosi di tracing.

Poi la parte fondamentale, spiegata da un lungo commento nel codice:

```cpp
bool found;
m_pWalletTxs->Lock();
found = m_pWalletTxs->FindEntity(&entStat);
m_pWalletTxs->UnLock();
if (!found) return false; // non sottoscritto
```

**Perché `FindEntity` e non `WRPFindEntity`?** (differenza chiave del design)

- La famiglia **WRP\*** (`WRPGetListSize`/`WRPGetList`/`WRPGetWalletTx`) legge da uno *snapshot* la cui posizione (`m_ReadLastPos`) viene aggiornata **solo** nel protocollo di read-lock RPC: un lettore deve tenere `WRPReadLock()` e lo snapshot avanza dal lato writer via `WRPSync()`. Un lettore autonomo che **non** partecipa a quel protocollo (questo thread di background, e le RPC di lettura che non prendono il WRP read lock) vedrebbe uno snapshot **stale** e riporterebbe 0 item per sempre, anche dopo che la tx di publish è minata.
- I metodi **non-WRP** (`FindEntity`/`GetListSize`/`GetList`/`GetWalletTx`) si auto-bloccano via `Lock(0,0)` e leggono la posizione **live** (`m_LastPos`), quindi vedono ogni item confermato appena il suo blocco si connette.
- `FindEntity` non blocca internamente, quindi va protetto manualmente con `Lock()`/`UnLock()`.

Questa è la ragione dell'annotazione nell'header: *"We deliberately do NOT use the WRP\* read family."*

```cpp
int confirmed = 0;
int total = m_pWalletTxs->GetListSize(&entStat.m_Entity, entStat.m_Generation, &confirmed);
if (confirmed <= 0) return true; // sottoscritto ma nessun item confermato -> mappa vuota
```

`GetListSize` restituisce nel valore di ritorno il totale (inclusi item non confermati in mempool) e via **out-param** `&confirmed` il numero di item **confermati** (`m_LastClearedPos`). Si usano solo i confermati: **un registro pesi che alimenta il consenso deve essere identico su ogni nodo**, mentre la mempool differisce per nodo. Un peso "conta" solo quando è on-chain.

```cpp
mc_Buffer rows;
rows.Initialize(MC_TDB_ENTITY_KEY_SIZE, sizeof(mc_TxEntityRow), MC_BUF_MODE_DEFAULT);

int list_err = m_pWalletTxs->GetList(&entStat.m_Entity, entStat.m_Generation, 1, confirmed, &rows);
if (list_err != MC_ERR_NOERROR) return false;
```

- `mc_Buffer` — buffer generico MultiChain; `Initialize` gli dice la dimensione della chiave e della riga (`sizeof(mc_TxEntityRow)`).
- `GetList(entity, generation, 1, confirmed, &rows)` — legge gli item dalla posizione **1** fino a `confirmed`, quindi **solo il prefisso confermato**, in ordine **ascendente** (dal più vecchio al più recente).

```cpp
const unsigned char* stream_short_txid = entity.GetTxID() + MC_AST_SHORT_TXID_OFFSET;

for (int i = 0; i < rows.GetCount(); i++)
{
    mc_TxEntityRow* er = (mc_TxEntityRow*)rows.GetRow(i);

    if (er->m_Flags & MC_TFL_IS_EXTENSION) continue;   // salta righe di estensione (chunked)

    uint256 hash;
    memcpy(hash.begin(), er->m_TxId, MC_TDB_TXID_SIZE);

    int err = MC_ERR_NOERROR;
    mc_TxDefRow txdef;
    CWalletTx wtx = m_pWalletTxs->GetWalletTx(hash, &txdef, &err);
    if (err != MC_ERR_NOERROR) continue;

    string addr; uint32_t w = 0;
    bool decoded = DecodeWeightRecord(wtx, stream_short_txid, addr, w);
    if (decoded)
        mc_AccumulateLatestWeight(out_latest, addr, w); // il più recente vince
}
return true;
```

- Ogni riga (`mc_TxEntityRow`) rappresenta un item dello stream.
- `MC_TFL_IS_EXTENSION` — flag delle righe di estensione (item chunked/off-chain). Poiché pubblichiamo solo JSON piccoli on-chain, non capitano mai; si saltano difensivamente.
- `uint256` — tipo Bitcoin per hash a 256 bit. Si ricostruisce il TXID dai byte della riga.
- `GetWalletTx(hash, &txdef, &err)` — recupera la transazione completa dal wallet.
- `DecodeWeightRecord(...)` — estrae `(addr, w)` come visto sopra.
- **`mc_AccumulateLatestWeight(out_latest, addr, w)`** — poiché iteriamo in ordine ascendente (vecchio→nuovo), sovrascrivere la mappa per indirizzo fa sì che **l'ultimo record vinca**. Questo helper vive in `weight_record.h`.

### 2.8 I metodi pubblici di lettura (wrapper sottili su `ReadAllRecords`)

Tutti chiamano `ReadAllRecords` e poi filtrano/aggregano:

```cpp
uint32_t GetNodeWeight(addr)  → cerca addr nella mappa, ritorna peso o 0
uint32_t GetLocalWeight()     → come sopra ma per m_LocalAddress, con WARNING se 0
std::map GetAllNodesWeights() → ritorna l'intera mappa (e logga somma/conteggio)
bool IsLocalWeightRegistered()→ true se m_LocalAddress è nella mappa
void DebugPrintWeights()      → stampa formattata di tutto il registro
```

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
Polling: rilegge lo stato ogni `interval_ms` finché il peso confermato del nodo non è uguale a quello atteso, con guardia sullo shutdown. Serve al thread per stampare il dump di debug con il valore **confermato** e non 0.

### 2.9 Il thread di registrazione differita

```cpp
static bool NodeReadyForWeightRegistration()
{
    { LOCK(cs_main); if (chainActive.Tip() == NULL) return false; }   // serve un tip
    if (GetBoolArg("-offline", false)) return true;                   // in offline OK subito
    return !IsInitialBlockDownload();                                 // altrimenti attendi fine IBD
}
```
Il nodo è "pronto" quando esiste un tip di catena e (salvo `-offline`) l'**Initial Block Download** è terminato. Deliberatamente **non** richiede peer: un unico miner permesso produce blocchi da solo.

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
        if (!NodeReadyForWeightRegistration()) continue;   // gate, non conta come tentativo

        attempts++;
        if (registry.RegisterLocalWeight(weight))
        {
            if (registry.WaitForLocalWeight(weight, MC_WPOA_CONFIRM_ATTEMPTS, MC_WPOA_RETRY_INTERVAL_MS))
                LogPrintf("... Weight confirmed on-chain\n");
            else
                LogPrintf("... Weight submitted; awaiting a block ...\n");
            registry.DebugPrintWeights();
            return;   // successo -> il thread termina
        }

        if (attempts >= MC_WPOA_MAX_ATTEMPTS) { ...; return; }  // resa
    }
}
```

- `RenameThread("mc-wpoa-weight")` — assegna un nome al thread (utile in `top`/debug).
- Crea **una sola** istanza di `StreamWeightRegistry` (così i flag `m_CreateAttempted`/`m_SubscribeAttempted` persistono tra i tentativi).
- Loop di retry con `MilliSleep` tra i giri; esce al primo successo o dopo `MC_WPOA_MAX_ATTEMPTS` (200) tentativi (~10 minuti). La readiness gate non consuma tentativi.
- Dopo un `RegisterLocalWeight` riuscito, attende la conferma on-chain e stampa il dump.

### 2.10 Le tre funzioni RPC (definite qui, registrate in `rpclist.cpp`)

Struttura comune (esempio `getlocalweight`):
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

- **Firma standard RPC**: `Value f(const Array& params, bool fHelp)`.
- Se `fHelp` è true o gli argomenti sono errati, lancia `runtime_error` col testo di help (il server RPC lo intercetta e lo mostra all'utente).
- `JSONRPCError(codice, messaggio)` — helper che costruisce l'oggetto errore JSON-RPC; `RPC_WALLET_ERROR` è un codice standard.
- Ogni handler crea un `StreamWeightRegistry` **al volo** (leggendo `pwalletTxsMain`), interroga i metodi pubblici e impacchetta il risultato in un `Object` json_spirit.

Le altre due:
- `getallweights` — ritorna `{validators, total, weights:{addr:peso,...}}` sommando i pesi.
- `getnodeweight "address"` — richiede 1 argomento (`params.size() != 1`), legge `params[0].get_str()` e ritorna `{address, weight}`.

---

## 3. Come questo file si collega agli altri

```
                         ┌───────────────────────────┐
   -weight (CLI) ───────►│  core/init.cpp (AppInit2) │
                         │  • valida -weight          │
                         │  • g_node_weight = ...     │
                         │  • create_thread(          │
                         │      ThreadRegisterNodeWeight)
                         └─────────────┬─────────────┘
                                       │ lancia
                                       ▼
             ┌────────────────────────────────────────────┐
             │  ThreadRegisterNodeWeight (questo file)      │
             │  usa la classe StreamWeightRegistry          │
             └───────┬──────────────────────┬──────────────┘
                     │ scritture             │ letture/parsing
                     ▼                       ▼
     createcmd/subscribe/publish     weight_record.h
     (rpcwallet.h — handler RPC)     mc_ParseWeightRecordJson
                                     mc_AccumulateLatestWeight
                     ▲
                     │ registra i 3 handler RPC
             ┌───────┴───────────────┐
             │  rpc/rpclist.cpp      │  getlocalweight / getallweights / getnodeweight
             └───────────────────────┘
```

- **`core/init.h`** dichiara `pwalletMain`, `pwalletTxsMain`, `ShutdownRequested()` che questo file usa; **`core/init.cpp`** legge `-weight`, imposta `g_node_weight` e lancia `ThreadRegisterNodeWeight`. → vedi `docs/init.md`.
- **`weight_record.h`** fornisce i due helper puri di parsing/aggregazione usati da `DecodeWeightRecord`/`ReadAllRecords`. → vedi `docs/weight_record.md`.
- **`rpc/rpclist.cpp`** registra le tre funzioni RPC nel dispatcher del server. → vedi `docs/rpclist.md`.
- **`rpcwallet.h`** fornisce gli handler `createcmd`/`subscribe`/`publish` riusati per le scritture.
