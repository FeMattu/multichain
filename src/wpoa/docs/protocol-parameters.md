# wPoA — Catalogo dei parametri di protocollo

> **Registro: tecnico-diretto.** Documento di riferimento per API e
> configurazione. Frasi brevi, terminologia di codice invariata, nomi di flag e
> parametri esattamente come nel codice. Per il modello teorico del consenso e le
> proprietà di sicurezza si rimanda a
> [thesis-project-overview.md](thesis-project-overview.md), che è a registro
> formale-accademico.

> **Fonte unica.** Questo file è l'**unica** sede autoritativa dei parametri del
> protocollo. Nessun altro documento deve ripeterne default, range o semantica: gli
> altri file lo **linkano**. Se un parametro cambia nel codice, si aggiorna qui e
> solo qui.

Ogni riferimento `file:riga` punta al codice al momento dell'ultima revisione di
questo documento. La colonna «Definizione» indica dove il parametro è **dichiarato**
come parametro di catena; la colonna «Validazione» dove il suo valore è
**verificato** all'avvio del nodo.

---

## 1. Modello di configurazione

Ogni switch wPoA e ogni parametro del weight engine è un **parametro di catena**
(protocollo `20014`). Si imposta una volta, alla creazione della catena, e finisce
in `params.dat`:

```bash
./src/multichain-util create mychain -enablewpoa=1
```

Qualsiasi nodo che si unisce alla rete **eredita** la configurazione da
`params.dat` e parte correttamente **senza alcun flag** da riga di comando:

```bash
./src/multichaind mychain                       # il creatore / un nodo locale
./src/multichaind mychain@<seed-ip>:<port>      # un nodo che si unisce
```

Gli stessi nomi funzionano anche come **flag runtime** su `multichaind`. Un flag
runtime sovrascrive il valore ereditato **solo per quel nodo** (CLI vince).

### 1.1 I parametri sono hash-enforced

Nessuna voce del blocco wPoA/weight di
[`paramlist.h`](../../chainparams/paramlist.h) porta il flag `MC_PRM_NOHASH`:
tutte sono `MC_PRM_USER | MC_PRM_CLONE` più il proprio tipo. **I parametri
partecipano quindi all'hash di `params.dat`.**

> **Conseguenza operativa.** Un override CLI locale di un parametro
> consensus-critical non è una personalizzazione innocua: fa divergere questo nodo
> dal resto del validator set e **rischia un fork silenzioso**. `AppInit2` registra
> un avviso esplicito su ogni override divergente, ma **non** impedisce l'avvio.
> Usare gli override solo in test isolati.

Una precedente nota di progetto descriveva questi parametri come `MC_PRM_NOHASH`
(ereditabili ma non vincolati crittograficamente). Quella descrizione è **superata**.

### 1.2 Master switch e precedenza

`-enablewpoa` (alias `-wpoaenable`) accende **ogni** fase. Un flag
`-enablewpoa*` più specifico sovrascrive la propria fase.

```bash
# Stack completo tranne la sortition:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0
```

Risoluzione in tre livelli, nell'ordine: valore ereditato da `params.dat` →
master runtime `-enablewpoa`/`-wpoaenable` → flag esplicito della singola fase
(vince). L'espansione del master a tempo di creazione è in
[`params.cpp`](../../chainparams/params.cpp) (`Read(argc,argv)`); la risoluzione
runtime in [`init.cpp`](../../core/init.cpp) (`AppInit2`).

### 1.3 Vincoli di dipendenza (fallimento netto)

Le fasi vanno abilitate dal basso verso l'alto:

```
weights -> selection -> vrf -> randao -> sortition -> malus
                                     \
                                      weight engine (richiede weights)
```

Abilitare una fase senza il suo prerequisito è **rifiutato** alla creazione della
catena **e** all'avvio del nodo, con errore esplicito: il nodo si rifiuta di
partire anziché eseguire una fase inerte.

| Vincolo | Errore in |
|---|---|
| `enablewpoaselection` richiede `enablewpoaweights` | `init.cpp:3334` |
| `enablewpoavrf` richiede `enablewpoaselection` | `init.cpp:3336` |
| `enablewpoarandao` richiede `enablewpoavrf` | `init.cpp:3338` |
| `enablewpoasortition` richiede `enablewpoarandao` | `init.cpp:3340` |
| `enablewpoasortition` richiede `wpoarandaolookback >= 1` | `init.cpp:3342` |
| `enablewpoamalus` richiede `enablewpoasortition` | `init.cpp:3426` |
| `wpoamalusequivpoints` deve essere `>` `wpoamalusdelaypoints` | `init.cpp:3419` |
| `enableweightengine` richiede `enablewpoaweights` | `init.cpp:3498` |

Il vincolo `k >= 1` non è arbitrario: il reveal prodotto dalla sortition alimenta
`R_tot[n]`, mentre il suo stesso seed legge `R_tot[n-k]`. Con `k = 0` la
dipendenza sarebbe circolare.

---

## 2. Catalogo — fasi wPoA

Tutti consensus-critical, tutti hash-enforced, tutti da mantenere **identici** su
ogni validatore.

| Flag CLI | `params.dat` | Tipo | Default | Range valido | Definizione | Effetto sul consenso |
|---|---|---|---|---|---|---|
| `-enablewpoa`, `-wpoaenable` | `enable-wpoa` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:164` | Master: accende tutte le fasi. Sovrascritto per fase dai flag specifici. |
| `-enablewpoaweights` | `enable-wpoa-weights` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:168` | Fase 1: attiva lo stream `wpoa-weights`. Nessun effetto diretto sull'elezione, ma è il substrato dati di tutte le fasi successive. Eseguibile in autonomia. |
| `-enablewpoaselection` | `enable-wpoa-selection` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:172` | Fase 2: elezione del proposer proporzionale al peso (Efraimidis–Spirakis). Sostituisce il gate round-robin mining-diversity sulle altezze governate da wPoA. |
| `-dumpfunction` | `dump-function` | `STRING(16)` | `none` | `none` \| `sqrt` \| `log` | `paramlist.h:176` | Compressione whale `f(w)` applicata **prima** del sorteggio. Cambia la distribuzione effettiva dei proposer. |
| `-enablewpoavrf` | `enable-wpoa-vrf` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:180` | Fase 3a: ogni proposer eletto pubblica un reveal verificabile `(R, pi)`; i peer rifiutano un blocco privo di reveal valido. La selezione non cambia. |
| `-enablewpoarandao` | `enable-wpoa-randao` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:184` | Fase 3b: il seed di selezione diventa `H(R_tot[n-k] || h[n] || n+1)` anziché l'hash del blocco precedente. Cambia solo la sorgente del seed. |
| `-wpoarandaolookback` | `wpoa-randao-lookback` | `UINT32` | `1` | `0` .. `1000000`; **`>= 1`** se la sortition è attiva | `paramlist.h:188` | Distanza di lookback `k` dell'accumulatore. Determina quale `R_tot` alimenta il seed. |
| `-enablewpoasortition` | `enable-wpoa-sortition` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:192` | Fase 4: sortition privata. Ogni validatore calcola il proprio score con un VRF sotto la propria chiave e si auto-elegge tramite un ritardo di mining. Il proposer è imprevedibile finché non agisce. |
| `-wpoasortitiondelta` | `wpoa-sortition-delta` | `STRING(32)` | `0.5` | `(0, 1)` — estremi esclusi | `paramlist.h:196` | Semi-larghezza della banda di ritardo, come **frazione** di `target-block-time`. Valori piccoli: banda stretta, più fork. Valori grandi: più latenza. |
| `-wpoasortitionlambda` | `wpoa-sortition-lambda` | `STRING(32)` | `0` (disattivo) | `[0, 1]` | `paramlist.h:200` | Guadagno del feedback globale `Phi`, che ricentra il tempo medio di blocco sul target. `0` disattiva il feedback. |

### 2.1 Il ritardo di mining della Fase 4

Il ritardo **non** è una rampa aperta: è una **banda** centrata su
`target-block-time`.

```
score_norm = 1 - e^{-W * score}                                    (Def. 5.10)
D_i        = T_block + delta * T_block * (2 * score_norm - 1) + lambda * Phi   (Def. 5.13)
```

dove `T_block` è il nativo `targetblocktime`
([`paramlist.h:29`](../../chainparams/paramlist.h#L29)), `delta` è
`-wpoasortitiondelta`, `lambda` è `-wpoasortitionlambda`, e `W` è la somma dei
pesi efficaci compressi. Implementazione: `PrivateSortition::MiningDelay()` in
[`private_sortition.h`](../private_sortition.h).

Il fattore `W` è ciò che rende reale la normalizzazione: senza di esso il valore
eredita la scala di `E/w` e collassa verso `0` per ogni candidato appena i pesi
raggiungono le centinaia. Con esso, lo score normalizzato del **vincitore** è
esattamente `U(0,1)`, quindi il suo ritardo è uniforme sulla banda e il tempo medio
di blocco cade sul target.

Il validatore accetta un blocco se e solo se
`block.nTime >= parent.nTime + MiningDelay(score_i, ...)`. Questa barriera
temporale **sostituisce** il confronto di uguaglianza sull'argmin pubblico, e la sua
auto-distensione è il meccanismo di liveness: non esiste soglia rigida, quindi il
validatore online con score minimo prima o poi propone sempre.

Dettaglio completo: [phase4-implementation-guide.md](phase4-implementation-guide.md)
e [private-sortition.md](private-sortition.md).

---

## 3. Catalogo — registro del malus comportamentale

Richiede `-enablewpoasortition`: entrambi i tipi di evidenza sono provati contro il
reveal VRF del blocco sul seed del beacon.

| Flag CLI | `params.dat` | Tipo | Default | Range valido | Definizione | Effetto sul consenso |
|---|---|---|---|---|---|---|
| `-enablewpoamalus` | `enable-wpoa-malus` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:204` | Attiva lo stream aperto `wpoa-weights-malus` ed elegge sul peso efficace `w_eff = w * Psi` anziché su quello grezzo. Inerte quando nessuno porta violazioni (`Psi = 1`). |
| `-wpoamalusmu` | `wpoa-malus-mu` | `STRING(32)` | `0.5` | `[0, 1)` — `1` escluso | `paramlist.h:208` | Persistenza dell'accumulatore: frazione di `M` trasportata all'epoca successiva. **`mu < 1` è ciò che rende reversibile un'esclusione.** |
| `-wpoamalusmax` | `wpoa-malus-max` | `STRING(32)` | `4` | `> 0` | `paramlist.h:212` | Soglia `M_max` alla quale `Psi` raggiunge `0` e il validatore diventa ineleggibile. |
| `-wpoamalusequivpoints` | `wpoa-malus-equiv-points` | `STRING(32)` | `4` | `> 0`, e **`>` delay-points** | `paramlist.h:216` | Punteggio di una equivocazione provata (due blocchi distinti alla stessa altezza) — una colpa di *safety*. |
| `-wpoamalusdelaypoints` | `wpoa-malus-delay-points` | `STRING(32)` | `0.25` | `> 0` | `paramlist.h:220` | Punteggio di una violazione di ritardo provata (blocco minato prima di quanto il proprio score consentisse) — una colpa di *scheduling*. |

La correzione è `Psi = max(0, 1 - M/M_max)`, con `M` media mobile esponenziale.
Poiché `mu < 1`, un'esclusione si azzera sempre dopo un numero finito di epoche
pulite: **non esiste ban permanente**. Lo stream è deliberatamente **aperto** —
chiunque può segnalare, nessuno è creduto: ogni nodo ri-deriva l'evidenza dai dati
pubblici della catena, quindi una segnalazione falsa viene scartata in modo
identico su tutti i nodi e non muove alcun peso.

Dettaglio: [malus-registry.md](malus-registry.md).

---

## 4. Catalogo — weight engine

Il weight engine **produce** i pesi che il livello wPoA consuma, quindi richiede lo
stream dei pesi. Dettaglio del modulo: [weight-engine.md](weight-engine.md).

| Flag CLI | `params.dat` | Tipo | Default | Range valido | Definizione | Effetto sul consenso |
|---|---|---|---|---|---|---|
| `-enableweightengine` | `enable-weight-engine` | `BOOLEAN` | `0` | `0` / `1` | `paramlist.h:225` | Deriva il peso di ogni cluster dagli input on-chain (membership / ESG / activity / reconciliation) una volta per epoca, **al posto** dello `-weight` statico. |
| `-weightepochlength` | `weight-epoch-length` | `UINT32` | `100` | `[1, 1000000]` | `paramlist.h:229` | Lunghezza dell'epoca in blocchi. L'epoca e' **1-based**: `epoch(height) = height / n + 1`. Determina i confini di epoca su cui miner e validatori devono concordare. |
| `-weightkappa` | `weight-kappa` | `STRING(32)` | `100` | `> 0` | `paramlist.h:233` | Costante di normalizzazione `kappa` nel contributo aziendale `c_i = ESG_i * tau_i / kappa`. |
| `-weightalpha` | `weight-alpha` | `STRING(32)` | `0.2` | `[0, 1]` | `paramlist.h:237` | Costante di allocazione `alpha` in `A_k = alpha * Theta * W_k / W_tot`. |
| `-weightlambda` | `weight-lambda` | `STRING(32)` | `0.5` | `[0, 1)` — `1` escluso | `paramlist.h:241` | Smorzamento del feedback comportamentale in `w_k = W_k * [rho_{k,e-1} * lambda + (1 - lambda)]`. **`lambda < 1` è un requisito di correttezza**, non una preferenza: garantisce la positività del peso. |

Due costanti correlate **non** sono ancora parametri di catena, e sono fissate a
tempo di compilazione in
[`weight_streams.h`](../../weight_engine/weight_streams.h):

| Costante | Valore | Nota |
|---|---|---|
| `MC_WEIGHT_DEFAULT_STABILITY_MARGIN` | `6` | Margine di stabilità in blocchi. Un'epoca è calcolata solo quando è **sepolta** — il suo ultimo blocco è almeno così sotto la punta — così un riorg superficiale non può far leggere blocchi diversi a due nodi. Deve essere `>=` del riorg più profondo possibile. Il codice stesso raccomanda di promuoverlo a parametro di catena prima della produzione. |
| `MC_WEIGHT_DEFAULT_EPOCH_LENGTH` | `100` | Default di fallback di `weightepochlength` quando `params.dat` non è leggibile. |

---

## 5. Parametro per-nodo — `-weight`

**`-weight` è l'unico parametro di questo catalogo che NON è un parametro di
catena.** È un flag runtime puro: ogni validatore imposta il proprio.

| Flag CLI | Tipo | Default | Range valido | Definizione | Validazione |
|---|---|---|---|---|---|
| `-weight=<n>` | intero | `100` | `> 0` (interi positivi) | `MC_WPOA_DEFAULT_WEIGHT`, [`stream_weight_registry.h:28`](../stream_weight_registry.h) | `init.cpp:3234` — `-weight <= 0` impedisce l'avvio |

### 5.1 `-weight` è la via di ripiego, non quella principale

Con `-enableweightengine=1` il valore di `-weight` viene parsato, validato, scritto
in `g_node_weight` e registrato nel log — e poi **mai pubblicato**. I due publisher
sono **mutuamente esclusivi già all'avvio** (`init.cpp`, fine del blocco wPoA di
`AppInit2`):

```cpp
if (g_wpoa_weights_enabled && pwalletMain && pwalletTxsMain && !fDisableWallet)
{
    if (g_weight_engine_enabled)
        threadGroup.create_thread(boost::bind(&ThreadWeightEngine));                     // peso dinamico w_k
    else
        threadGroup.create_thread(boost::bind(&ThreadRegisterNodeWeight, g_node_weight)); // peso statico
}
```

Non esiste alcuna sovrascrittura a runtime: è una scelta esclusiva del thread di
pubblicazione. La differenza è osservabile — con l'engine attivo, `-weight=500` non
produce un record poi superato: non produce **nessun** record.

Entrambi i percorsi scrivono lo stesso stream `wpoa-weights`, dove la lettura è
**newest-confirmed-wins**. Il consenso è quindi indifferente a quale publisher abbia
prodotto il record.

### 5.2 Impostare il proprio peso richiede autorizzazione

Lo stream `wpoa-weights` è creato **CLOSED**: serve il permesso
`wpoa-weights.write` per pubblicare. Un nodo senza quel permesso vede la propria
publish fallire e **non compare nella mappa dei pesi: non ha alcun peso
nell'elezione**. Concessione esplicita:

```bash
multichain-cli <chain> grant <address> wpoa-weights.write
```

**Un nodo non autorizzato non può in alcun modo imporre il proprio peso**, né via
`-weight` né via RPC. Dettaglio del modello di autorizzazione a due gate:
[weight-engine.md](weight-engine.md) e
[stream-weight-registry.md](stream-weight-registry.md).

---

## 6. Validazione dei valori all'avvio

I parametri reali viaggiano come `MC_PRM_STRING` e sono convertiti in `AppInit2`
con controlli NaN/Inf-safe: un valore non finito è rifiutato, non propagato.

| Parametro | Controllo | Riga |
|---|---|---|
| `-weight` | intero `> 0` | `init.cpp:3234` |
| `-wpoarandaolookback` | intero non negativo | `init.cpp:3285` |
| `-wpoasortitiondelta` | numero in `(0, 1)` | `init.cpp:3297` |
| `-wpoasortitionlambda` | numero in `[0, 1]` | `init.cpp:3308` |
| `-wpoamalusmu` | numero in `[0, 1)` | `init.cpp:3394` |
| `-wpoamalusmax` | numero `> 0` | `init.cpp:3400` |
| `-wpoamalusequivpoints` | numero `> 0` | `init.cpp:3406` |
| `-wpoamalusdelaypoints` | numero `> 0` | `init.cpp:3412` |
| `-weightepochlength` | intero in `[1, 1000000]` | `init.cpp:3468` |
| `-weightkappa` | numero `> 0` (e `< 1e18`) | `init.cpp:3479` |
| `-weightalpha` | numero in `[0, 1]` | `init.cpp:3485` |
| `-weightlambda` | numero in `[0, 1)` | `init.cpp:3491` |

Ogni violazione produce un `InitError` con messaggio esplicito: il nodo non parte.

---

## 7. Ricette di configurazione

```bash
# Solo Fase 1 — raccogliere i pesi sullo stream, nient'altro:
./src/multichain-util create mychain -enablewpoaweights=1

# Stack completo, configurazione ereditata da ogni nodo che si unisce:
./src/multichain-util create mychain -enablewpoa=1

# Stack completo tranne la sortition (il flag specifico vince sul master):
./src/multichain-util create mychain -enablewpoa=1 -enablewpoasortition=0

# Stack completo con banda piu' stretta e feedback attivo:
./src/multichain-util create mychain -enablewpoa=1 \
    -wpoasortitiondelta=0.3 -wpoasortitionlambda=0.5

# Stack completo con malus comportamentale:
./src/multichain-util create mychain -enablewpoa=1 -enablewpoamalus=1

# Pesi dinamici derivati dagli input on-chain, epoca di 200 blocchi:
./src/multichain-util create mychain -enablewpoa=1 \
    -enableweightengine=1 -weightepochlength=200

# Peso statico per-nodo (solo se il weight engine e' disattivo):
./src/multichaind mychain -weight=250
```

---

## 8. Riferimenti

- [node-startup.md](node-startup.md) — come gli switch sono letti da `params.dat`,
  risolti e collegati in `AppInit2`, e come parte il thread di pubblicazione.
- [weight-engine.md](weight-engine.md) — il modulo che produce i pesi: stream di
  input, pipeline di calcolo, RPC amministrativi, modello di autorizzazione.
- [implementation-status.md](implementation-status.md) — stato di implementazione
  di ogni fase.
- [implementation-guide.md](implementation-guide.md) — indice generale e mappa
  delle fasi.
