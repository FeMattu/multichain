# `weight_record.h`

Documentazione tecnica dettagliata degli **helper puri per i record di peso** wPoA — Fase 1.

## 1. Ruolo e filosofia del file

Questo è un header **header-only** (tutte le funzioni sono `inline`, non c'è un `.cpp` associato). Contiene due sole funzioni libere:

- `mc_ParseWeightRecordJson(...)` — trasforma un payload JSON di uno stream item in `(node_address, weight)`.
- `mc_AccumulateLatestWeight(...)` — piega un record nella mappa "indirizzo → ultimo peso".

### Perché è un file separato e "dependency-light"?

Il commento in testa lo spiega:
> *"This header intentionally depends only on json_spirit (plus `<string>`), so the parsing/aggregation logic can be unit-tested in isolation, without linking the wallet / node runtime."*

Cioè: la **logica di parsing** è isolata dal resto del sistema. `stream_weight_registry.cpp` dipende dall'intero runtime del nodo (wallet, catena, DB transazioni). Se il parsing vivesse lì, per testarlo servirebbe avviare mezzo nodo. Estraendolo in un header che dipende **solo** da `json_spirit` + `<string>` + `<map>`, il test unitario (`src/poas/test/wpoa_weight_tests.cpp`) può includere solo questo header, costruire a mano un `json_spirit::Value` e verificare il parsing — senza linkare wallet, rete o database.

### Perché `inline` e header-only?

Le funzioni `inline` definite in un header possono essere incluse in più `.cpp` senza violare la **ODR** (One Definition Rule): il linker fonde le definizioni identiche. Questo evita di dover creare un `weight_record.cpp` e aggiungerlo al Makefile solo per due funzioni piccole. È lo schema tipico per utility pure e testabili.

## 2. Include

```cpp
#include <map>
#include <string>
#include <stdint.h>
#include "json/json_spirit_value.h"
#include <boost/foreach.hpp>
```

- `<map>` → `std::map` per la funzione di accumulo.
- `<string>` → `std::string`.
- `<stdint.h>` → `uint32_t`, `int64_t` (tipi interi a larghezza fissa, C standard).
- `json/json_spirit_value.h` → **json_spirit**: `Value`, `Object`, `Pair`, e l'enum dei tipi (`obj_type`, `str_type`, `int_type`, `real_type`).
- `boost/foreach.hpp` → la macro `BOOST_FOREACH`, usata per iterare sugli elementi degli oggetti JSON in modo compatibile con C++98/03 (stile del codebase MultiChain, che precede i range-based `for` del C++11).

Nota: qui **non** c'è alcun `#include` di header del wallet/rete. È esattamente il punto: dipendenze minime.

## 3. `mc_ParseWeightRecordJson` — parsing e validazione

```cpp
inline bool mc_ParseWeightRecordJson(const json_spirit::Value& data_value,
                                     std::string& node_address, uint32_t& weight)
```

### Contratto (dal commento Doxygen)
- **Input** `data_value`: il valore prodotto da `OpReturnFormatEntry` per un item JSON, cioè un oggetto della forma `{ "json": { "node_address": "...", "weight": n, ... } }`.
- **Output** (per riferimento): `node_address` e `weight`.
- **Ritorno**: `true` solo per un record ben formato con indirizzo non vuoto e peso intero **strettamente positivo**; `false` altrimenti.

Il passaggio per riferimento (`std::string&`, `uint32_t&`) è il modo idiomatico C++ pre-C++17 di "ritornare più valori": la funzione restituisce un `bool` di successo e scrive i risultati nelle variabili del chiamante.

### 3.1 Azzeramento e controllo del tipo

```cpp
node_address = "";
weight = 0;
if (data_value.type() != json_spirit::obj_type) return false;
```
Prima azzera gli output (così in caso di fallimento il chiamante ha valori puliti), poi verifica che il valore JSON sia un **oggetto** (`obj_type`). `.type()` è il metodo json_spirit che ritorna il tipo di un `Value`.

### 3.2 Doppio formato di `OpReturnFormatEntry` (robustezza)

```cpp
const json_spirit::Object* obj = &data_value.get_obj();

json_spirit::Value formatdata_val;
bool have_formatdata = false;
BOOST_FOREACH(const json_spirit::Pair& p, *obj)
{
    if (p.name_ == "formatdata" && p.value_.type() == json_spirit::obj_type)
    {
        formatdata_val = p.value_;
        have_formatdata = true;
        break;
    }
}
if (have_formatdata)
    obj = &formatdata_val.get_obj();
```

Il commento nel file spiega che `OpReturnFormatEntry` ha **due forme di output** a seconda dell'overload usato:
- overload a **6/7 argomenti** (come `StreamItemEntry`): `{"json": {...}}` — diretto;
- overload a **3 argomenti**: `{"format":"json","formatdata":{"json":{...}}}` — incapsulato.

Questa funzione accetta **entrambi**: se trova una chiave `"formatdata"` che è un oggetto, ci "scende dentro" e continua a cercare `"json"` a quel livello. Questo rende il parser tollerante rispetto a quale overload lo alimenta.

Dettagli tecnici:
- `.get_obj()` → estrae il `json_spirit::Object` (una lista di `Pair`) dal `Value`.
- `obj` è un **puntatore** a `Object` così può essere ridiretto verso il livello annidato senza copiare.
- `json_spirit::Pair` ha due campi: `p.name_` (chiave, `std::string`) e `p.value_` (valore, `Value`). Il trailing underscore è la convenzione di json_spirit per i membri.
- `BOOST_FOREACH(const Pair& p, *obj)` → itera su tutte le coppie dell'oggetto.

> Collegamento importante: è proprio qui che si intreccia il bug fix descritto in `stream_weight_registry.cpp`. `DecodeWeightRecord` usa l'overload a 6 argomenti (forma diretta `{"json":{...}}`); questo parser accetta anche la forma incapsulata per sicurezza.

### 3.3 Estrazione dell'oggetto `"json"`

```cpp
json_spirit::Value json_val;
bool have_json = false;
BOOST_FOREACH(const json_spirit::Pair& p, *obj)
{
    if (p.name_ == "json") { json_val = p.value_; have_json = true; break; }
}
if (!have_json || json_val.type() != json_spirit::obj_type) return false;
```
Cerca la chiave `"json"`. Se manca, o non è un oggetto, il record non è valido → `false`.

### 3.4 Lettura dei campi `node_address` e `weight`

```cpp
std::string addr;
int64_t w = -1;
BOOST_FOREACH(const json_spirit::Pair& p, json_val.get_obj())
{
    if (p.name_ == "node_address" && p.value_.type() == json_spirit::str_type)
        addr = p.value_.get_str();
    else if (p.name_ == "weight")
    {
        if (p.value_.type() == json_spirit::int_type)
            w = p.value_.get_int64();
        else if (p.value_.type() == json_spirit::real_type)
            w = (int64_t)p.value_.get_real();
    }
}
```

- `node_address` deve essere una stringa (`str_type`) → `.get_str()`.
- `weight` è accettato sia come **intero** (`int_type` → `.get_int64()`) sia come **reale** (`real_type` → `.get_real()` castato a `int64_t`). Questo perché json_spirit può classificare un numero come reale a seconda di come è stato serializzato/deserializzato dallo strato UBJSON; accettare entrambi evita falsi negativi.
- `w` è inizializzato a `-1` così che, se il campo `weight` manca del tutto, resti negativo e faccia fallire la validazione successiva.

### 3.5 Validazione finale e conversione

```cpp
if (addr.empty() || w <= 0) return false;
node_address = addr;
weight = (uint32_t)w;
return true;
```
- Rifiuta indirizzo vuoto o peso ≤ 0 (il peso deve essere **strettamente positivo** — coerente con `RegisterLocalWeight` che rifiuta `weight == 0`).
- Solo a validazione superata scrive gli output e ritorna `true`. Il cast `(uint32_t)w` è sicuro perché `w > 0` è già garantito.

## 4. `mc_AccumulateLatestWeight` — aggregazione "l'ultimo vince"

```cpp
inline void mc_AccumulateLatestWeight(std::map<std::string, uint32_t>& latest,
                                      const std::string& node_address, uint32_t weight)
{
    latest[node_address] = weight;
}
```

Una sola riga, ma con una semantica precisa documentata dal commento:
> *"...the newest value for an address overwrites any earlier one."*

`latest[node_address] = weight` usa `operator[]` di `std::map`: se la chiave esiste, **sovrascrive** il valore; se non esiste, la inserisce. Poiché `ReadAllRecords` in `stream_weight_registry.cpp` itera i record in ordine **cronologico crescente** (vecchio → nuovo), la sovrascrittura fa sì che l'**ultimo record confermato** di ogni indirizzo prevalga. Estrarre questa riga in una funzione a sé la rende:
1. auto-documentante (il nome esprime l'intento),
2. testabile in isolamento,
3. l'unico punto in cui è codificata la regola "newest wins" (se cambiasse la politica, si tocca un solo posto).

## 5. Collegamenti con gli altri file

- **`stream_weight_registry.cpp`** include questo header (`#include "poas/weight_record.h"`) e usa:
  - `mc_ParseWeightRecordJson` dentro `DecodeWeightRecord` per estrarre `(addr, weight)` dal `Value` prodotto da `OpReturnFormatEntry`;
  - `mc_AccumulateLatestWeight` dentro `ReadAllRecords` per costruire la mappa indirizzo→peso.
- **`src/poas/test/wpoa_weight_tests.cpp`** include **solo** questo header per testare il parsing in isolamento — che è l'intera ragion d'essere del file.
- Non dipende da nessun altro file wPoA: è la "foglia" pura del sottosistema.

```
  stream_weight_registry.cpp                 wpoa_weight_tests.cpp
        │  usa in DecodeWeightRecord/               │  testa in isolamento
        │  ReadAllRecords                           │
        ▼                                           ▼
   ┌──────────────────────────────────────────────────┐
   │  weight_record.h  (solo json_spirit + STL)         │
   │  • mc_ParseWeightRecordJson                        │
   │  • mc_AccumulateLatestWeight                       │
   └──────────────────────────────────────────────────┘
```
