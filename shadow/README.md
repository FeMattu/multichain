# Simulazioni Shadow multi-livello — POESIA / wPoA

Banco di prova per la Weighted Proof-of-Authority su reti geograficamente
distribuite. Ogni livello e' la **stessa rete** — stessi 10 nodi, stessi ruoli,
stessi cluster, stessi parametri di protocollo — dispiegata su una geografia
via via piu' ampia. L'unica variabile indipendente e' la **latenza di rete**:
tutto il resto e' tenuto fisso apposta.

| livello | geografia | RTT max fra host |
|---|---|---|
| `regionale` | Toscana / Liguria / Emilia-Romagna | 10.0 ms |
| `nazionale` | Italia (Nord / Centro / Sud + isole) | 22.0 ms |
| `continentale` | Europa (Milano / Frankfurt / Madrid) | 44.7 ms |
| `intercontinentale` | Europa + Nord America (… / New York) | 112.0 ms |

(RTT end-to-end peggiore fra due host, misurato da `check_topology.py --matrix`.)

Quei quattro livelli sono l'impianto **storico**, lanciato con
`./run.sh area=<livello>` e oggi **deprecato**. Il modo supportato e' la
**configurazione dichiarativa**: un solo descrittore JSON per esperimento,
passato con `--config=`, che referenzia per path parametri di catena e topologia
e dichiara la dislocazione dei nodi. Vale la pena leggere la sezione
[Configurazione dichiarativa](#configurazione-dichiarativa) prima di tutto il
resto: permette di variare **un asse alla volta** — dump function, topologia,
`target-block-time`, numero di nodi — riusando gli altri intatti, cosa che il
modo livelli non consentiva.

---

## Uso

```bash
cd multichain/shadow

./run.sh --config=config/simulations/tbt10s-cont-sqrt-5n.json
```

Un solo argomento, nessun altro parametro: tutto sta nel descrittore di
simulazione. `run.sh` rifiuta qualunque altro argomento accanto a `--config=`,
proprio perche' non esista un secondo posto dove la configurazione possa vivere.

Output in `runs/<nome-simulazione>/`:

```
runs/<nome>/
├── data/<host>/          datadir isolato per nodo (blocchi, wallet, debug.log)
├── shared/<host>.addr    indirizzi raccolti durante il bootstrap
├── metrics/              CSV, snapshot JSON, summary.txt, summary_epoche.txt
│   └── epoche/           campionamenti a ogni epoca (verifica, fork, treasury)
├── shadow.yaml           generato da tools/gen_simulation.py
├── shadow.data/          output di Shadow (stdout/stderr per processo)
└── shadow.log            log del simulatore
```

---

## Configurazione dichiarativa

La configurazione e' divisa in **tre assi indipendenti**, ognuno in una cartella
e in un formato propri. Il descrittore di simulazione e' l'unico file che li
mette insieme, e li referenzia **per path**: cambiare un asse significa cambiare
una riga, e i due file confrontati differiscono per quella riga soltanto.

```
config/
├── simulation.schema.json         JSON Schema del descrittore (draft-07)
├── blockchain/*.dat               ASSE 1 — parametri di catena
├── topologies/*.gml               ASSE 2 — latenze/banda fra i network node
└── simulations/*.json             descrittori: referenziano 1 e 2, dichiarano i nodi
```

### Il descrittore di simulazione

```json
{
  "name": "tbt10s-cont-sqrt-5n",
  "description": "testo libero, finisce in testa allo shadow.yaml",
  "seed": 42,
  "blockchain_params_file": "config/blockchain/params-tbt10s-sqrt.dat",
  "topology_file": "config/topologies/continental-10n.gml",
  "shadow": {
    "stop_time": "auto",
    "time_granularity": "host_native",
    "parallelism": 0
  },
  "scaling": { "factor": 2, "ca_count": 2 },
  "nodes": {
    "miners": [
      { "id": "m1", "location": "Milano", "network_node_id": 0 },
      { "id": "m2", "location": "Frankfurt", "network_node_id": 1 }
    ],
    "ca":    [ { "id": "ca1", "location": "London", "network_node_id": 8 } ],
    "admin": [ { "id": "admin1", "location": "Zurich", "network_node_id": 3 } ]
  }
}
```

| campo | obbligatorio | significato |
|---|---|---|
| `name` | si' | minuscole, cifre e trattini. Da' il nome a `runs/<name>/` e, senza trattini, alla catena (`poesia<name>`) |
| `description` | no | testo libero, riportato in testa allo `shadow.yaml` |
| `seed` | no (`20260827`) | alimenta `general.seed` di Shadow e l'estrazione degli ESG |
| `blockchain_params_file` | si' | path del `.dat` con i parametri di catena |
| `topology_file` | si' | path del `.gml` passato a `network.graph.file.path` |
| `shadow.stop_time` | no (`auto`) | `auto` calcola, una durata esplicita sovrascrive |
| `shadow.time_granularity` | no (`host_native`) | vedi la tabella piu' sotto |
| `shadow.parallelism` | no (`0`) | `general.parallelism`; `0` = un thread per core |
| `scaling.factor` | dipende | intero in `[1, 5]`; obbligatorio se `nodes.companies` e' assente |
| `scaling.ca_count` | no | ridondante: se presente **deve** coincidere con `len(nodes.ca)` |
| `nodes.miners` | si' | almeno 1 |
| `nodes.companies` | no | se assente, generato da `scaling.factor` |
| `nodes.ca` | si' | **da 1 a 3** |
| `nodes.admin` | si' | **esattamente 1** |

Ogni nodo e' `{id, location, network_node_id}`; le aziende accettano in piu' un
`cluster` facoltativo (l'`id` del miner di cui diventano membri).

**`location` e' documentale**: le latenze vengono dal `.gml`, non da li'. Chi
decide la posizione di rete e' `network_node_id`, e piu' host possono
condividere lo stesso — e' cosi' che 18 host stanno su una topologia a 10 nodi.

**Generazione automatica delle aziende.** Se `nodes.companies` e' assente:

```
n_companies = n_miners × scaling.factor        (sempre lineare, factor intero in [1,5])
```

Le aziende generate si chiamano `c1..cN` e prendono `location` e
`network_node_id` **a rotazione** fra quelli dei miner, con `cluster` impostato
al miner corrispondente. Non esistono varianti `sqrt`/`log` per questo campo:
`sqrt|none|log` nei nomi dei file riguarda la *dump function*, non lo scaling.

**Vincoli validati** — `tools/gen_simulation.py` valida contro
`config/simulation.schema.json` e poi esegue i controlli incrociati, fallendo
con un messaggio esplicito: `admin` esattamente 1, `ca` fra 1 e 3,
`scaling.factor` intero in `[1,5]` (`2.0` viene rifiutato, non e' un intero),
`ca_count` coerente con `nodes.ca`, `id` unici fra tutte le categorie, e ogni
`network_node_id` realmente presente nella topologia referenziata — l'errore
elenca i nodi disponibili con la loro etichetta.

### Asse 1 — parametri di catena (`config/blockchain/*.dat`)

Formato `KEY=VALUE` sourceable da bash, **lo stesso di `config/params.overrides`**:
`tools/prepare_params.sh` li traduce in flag di `multichain-util create` e in
`sed` su `params.dat`. Sono valori di **catena**: hash-enforced, ereditati da
ogni nodo che si unisce (protocollo 20014).

`SETUP_FIRST_BLOCKS` accetta `auto` (vedi *Vincolo sul setup*); `MEASURE_EPOCHS`
non e' un parametro di catena e serve solo al calcolo di `stop_time`.

#### La dump function

E' la compressione anti-balena `f(w)` applicata al peso **prima** dell'estrazione
di Efraimidis–Spirakis. Nel file `.dat` e' `WPOA_DUMPFUNCTION`, diventa il flag
di nodo `-dumpfunction` e finisce in `params.dat` come chiave `dump-function`.

| valore | `f(w)` | effetto |
|---|---|---|
| `none` | `w` | nessuna compressione: il peso entra tal quale |
| `sqrt` | `√w` | un divario di peso 10× compra ~3.2× di probabilita' |
| `log` | `log(1+w)` | compressione piu' aggressiva sulle code alte |

E' **consenso-critica**: un validatore con un valore diverso dagli altri
rifiuterebbe i loro blocchi. Per questo sta in `params.dat` e non sulla riga di
comando. Riferimenti: `src/wpoa/docs/wpoa-selector.md` §2.2 e
`src/wpoa/docs/protocol-parameters.md`.

### Asse 2 — topologia (`config/topologies/*.gml`)

Vedi `config/topologies/README.md` per provenienza, rigenerazione e i vincoli
del parser GML di Shadow. In sintesi: `continental-10n.gml` e' byte-identico
alla topologia continentale storica (stessa definizione di livello, stesso
generatore); `intercontinental-global-10n.gml` e' nuovo e porta la tratta
peggiore da ~90 ms a 407 ms di RTT.

### Granularita' temporale (`shadow.time_granularity`)

Campi impostati nello `shadow.yaml` generato, secondo la
[Shadow Config Specification](https://shadow.github.io/docs/guide/shadow_config_spec.html):

| valore | `general.model_unblocked_syscall_latency` | `experimental.runahead` | `experimental.use_dynamic_runahead` |
|---|---|---|---|
| `host_native` (default) | `true` | `"1 ns"` | `false` |
| `fast` | `true` | `"1 ms"` | `true` |
| durata esplicita, es. `"5 ms"` | `true` | il valore dato | `false` |

Due cose non ovvie, entrambe verificate sul sorgente di Shadow 3.3:

**`runahead` e' un limite inferiore, non il valore usato.** Shadow calcola
`max(latenza minima del grafo, runahead)` (`src/main/core/runahead.rs`). Quindi
per *minimizzare* l'approssimazione non si mette un valore piccolo ma un
**pavimento inerte**: `1 ns` non vincola nulla e lascia vincere la latenza
minima della topologia — nei `.gml` di questo repo il self-loop da `200 us`.
Mettere `"1 ms"`, che e' il default documentato, **alzerebbe** il runahead a
1 ms e renderebbe la simulazione meno fedele, non piu'.

**`model_unblocked_syscall_latency` resta `true` anche in `fast`.** Non e' una
scelta di fedelta': senza, il busy-loop `Strengthen()` di `random.cpp` impedisce
l'avanzamento del tempo simulato e i nodi non arrivano ad avviarsi (vedi
*Vincoli di Shadow scoperti sul campo*). `fast` rilassa quindi il solo runahead.

`experimental.unblocked_vdso_latency` vale sempre `20 us`: era il flag
obbligatorio `--unblocked-vdso-latency` di `run.sh`, ora e' un campo dello
`shadow.yaml` — ed e' il motivo per cui `run.sh` non ha piu' argomenti.

### Calcolo automatico di `stop_time`

Con `"stop_time": "auto"` (o il campo omesso):

```
measure_blocks = MEASURE_EPOCHS × WEIGHT_EPOCH_LENGTH
stop_time      = 340 + (setup_first_blocks + measure_blocks) × TARGET_BLOCK_TIME + 600
```

* **340 s** — fine della timeline di bootstrap (`T_TRAFFIC`): da li' le aziende
  generano traffico e i miner riconciliano.
* **termine centrale** — i blocchi che devono essere effettivamente minati: la
  fase PoA nativa piu' la finestra di misura sotto wPoA.
* **600 s** — snapshot finale e margine di chiusura.

`MEASURE_EPOCHS` vale 16 e si sovrascrive nel file `.dat`. Esempio a
`tbt=10 s`, epoca 12, setup 64: `340 + (64 + 192)×10 + 600 = 3500 s`.

Una durata esplicita (`"stop_time": "30 min"`, `"8500 s"`) **sovrascrive** il
calcolo: l'utente ha sempre l'ultima parola. Il valore automatico che sarebbe
stato usato viene comunque riportato nel commento dello `shadow.yaml`, cosi' la
differenza resta visibile.

Il `setup_first_blocks` usato qui e' quello **effettivo** riletto da
`params.dat` dopo `prepare_params.sh`: `multichain-util` puo' averlo alzato da
solo al pavimento derivato al genesi, e senza rileggerlo la finestra di misura
si accorcerebbe in silenzio.

### Cambiare un asse alla volta

```bash
# asse 'dump function': stessa catena, stessa topologia, stessi nodi
./run.sh --config=config/simulations/tbt10s-cont-none-5n.json
./run.sh --config=config/simulations/tbt10s-cont-sqrt-5n.json
./run.sh --config=config/simulations/tbt10s-cont-log-5n.json

# asse 'topologia': stessa catena, stessi nodi, latenze da 45 ms a 407 ms
./run.sh --config=config/simulations/tbt10s-cont-sqrt-5n.json
./run.sh --config=config/simulations/tbt10s-inter-sqrt-5n.json

# asse 'target-block-time': stessa topologia, stessi nodi, stessa dump function
./run.sh --config=config/simulations/tbt10s-cont-sqrt-5n.json
./run.sh --config=config/simulations/tbt30s-cont-sqrt-5n.json
```

Che gli assi siano davvero indipendenti e' verificabile con `diff`:

```bash
diff config/simulations/tbt10s-cont-{sqrt,none}-5n.json   # name + blockchain_params_file
diff config/blockchain/params-tbt10s-{sqrt,none}.dat      # solo WPOA_DUMPFUNCTION
diff config/blockchain/params-tbt{10,30}s-sqrt.dat        # solo TARGET_BLOCK_TIME
```

### Configurazioni predefinite

Tutte con 5 miner, 10 aziende generate (`factor: 2`), 2 CA, 1 admin, `seed: 42`,
`time_granularity: host_native`.

| descrittore | tbt | topologia | dumping | `stop_time` |
|---|---|---|---|---|
| `tbt10s-cont-sqrt-5n.json` | 10 s | continentale | `sqrt` | auto (3500 s) |
| `tbt10s-cont-none-5n.json` | 10 s | continentale | `none` | auto (3500 s) |
| `tbt10s-cont-log-5n.json` | 10 s | continentale | `log` | auto (3500 s) |
| `tbt10s-inter-sqrt-5n.json` | 10 s | globale | `sqrt` | auto (3500 s) |
| `tbt10s-inter-none-5n.json` | 10 s | globale | `none` | auto (3500 s) |
| `tbt10s-inter-log-5n.json` | 10 s | globale | `log` | auto (3500 s) |
| `tbt30s-cont-sqrt-5n.json` | 30 s | continentale | `sqrt` | **`"8500 s"`** esplicito |

Miner continentali: Milano, Frankfurt, Madrid, Amsterdam, Paris (nodi 0, 1, 2,
5, 7). Miner globali: Milano, Madrid, New York, Singapore, San Paolo (nodi 0–4).

L'ultima riga usa `stop_time` esplicito **di proposito**: il valore coincide con
quello che il calcolo automatico produce oggi, e pinnandolo il confronto con
`tbt10s-cont-sqrt-5n` resta valido anche se in futuro `MEASURE_EPOCHS` o il
pavimento derivato di `setup-first-blocks` dovessero cambiare.

### Migrazione dal modo livelli

Il lancio `./run.sh area=<livello>` **e' deprecato** ma continua a funzionare:
stampa un avviso e prosegue, e le quattro run storiche restano riproducibili.

| modo livelli | modo dichiarativo |
|---|---|
| `area=<livello>` | `topology_file` + la sezione `nodes` |
| `tbt=`, `epochlen=`, `setup=` | il file in `config/blockchain/` |
| `blocks=` | `MEASURE_EPOCHS` nel file `.dat` |
| `seed=` | `"seed"` nel descrittore |
| `vdso=` | sempre `20 us`, in `experimental.unblocked_vdso_latency` |
| `dry=1` | — |
| output in `<livello>/run/` | output in `runs/<name>/` |

I due modi non si toccano: `config/params.overrides`, `config/levels/*.json` e
le topologie in `<livello>/` restano dove sono e servono solo al modo deprecato.

---

## La rete simulata

10 nodi, identici su tutti i livelli. La struttura dei cluster (2 / 2 / 1) e'
scelta perche' i tre `W_k` risultino **strutturalmente diversi**: se i cluster
fossero simmetrici la selezione pesata sarebbe indistinguibile da una uniforme.

| host | ruolo | cluster | note |
|---|---|---|---|
| `m1` `m2` `m3` | miner / validatore | capo cluster | i 3 hub a 1 Gbit del `.gml` |
| `c1` `c2` | azienda | `m1` | pubblicano tracciabilita' di filiera |
| `c3` `c4` | azienda | `m2` | |
| `c5` | azienda | `m3` | |
| `admin` | Apuana SB | — | genesi, permessi, premine GAS, rifornimenti |
| `ca` | Certification Authority | — | pubblica gli ESG certificati (ruolo `high1`) |

`admin` e `ca` non sono capi cluster e non hanno peso: sotto wPoA sono
**strutturalmente ineleggibili** (Cor. 5.4, peso nullo → score `+inf`), quindi
non serve revocare loro il permesso `mine` — che invece serve all'`admin`
durante la fase di setup, quando mina da solo in attesa che i miner entrino.

### Eterogeneita' deliberata

Perche' i pesi divergano fra cluster e fra epoche:

* **ESG** — il CA estrae un punteggio uniforme in `(0, 100)` per ciascuno degli
  8 partecipanti, seminato con `seed=`;
* **attivita' `tau_i`** — ogni azienda pubblica a un ritmo diverso
  (`c1` 8 s → `c5` 25 s per item);
* **riconciliazione `rho_k`** — ogni miner rimanda al treasury una frazione
  diversa del GAS incassato (`m1` 95 %, `m2` 60 %, `m3` 20 %).

---

## Modello di latenza

```
latenza_one_way_ms = 0.005 · D_km · 1.4 + overhead        RTT = 2 · latenza
```

`0.005 ms/km` e' la propagazione in fibra (v ≈ 2·10⁵ km/s), `1.4` il fattore di
instradamento (il percorso fisico e' piu' lungo della distanza in linea d'aria),
`overhead` il costo di commutazione: **0.5 ms** sulla dorsale, **1.0 ms** sui
collegamenti di accesso. Le distanze sono great-circle da lat/lon in
`config/levels/*.json`.

Validazione contro misure reali:

| tratta | D | RTT modello | RTT reale |
|---|---|---|---|
| Bologna–Ginevra | 840 km | 12.8 ms | ~9.5 ms |
| Milano–Roma | 477 km | 7.7 ms | ~9 ms |
| Milano–Madrid | 1188 km | 17.6 ms | ~20 ms |
| Milano–New York | 6464 km | 91.5 ms | ~90 ms |

Il modello e' leggermente **conservativo** (pessimista) sulle brevi distanze e
molto accurato su quelle lunghe, che sono quelle che contano per l'esperimento.

`jitter` resta `0 ms` su ogni arco: **il campo non e' implementato da Shadow**
(issue `shadow/shadow#3601`). La variabilita' temporale nella simulazione
proviene da (a) eterogeneita' dei percorsi, (b) `packet_loss` stocastico
(0.0004 in accesso, `0.0002 + 2·10⁻⁷·D` sulla dorsale), (c) contesa reale su CPU
e lock fra i processi simulati.

### Il file `.gml` regionale originale

Il file fornito e' conservato in
`regionale/topologia_myledger_regionale.gml.orig` e resta usabile con
`topology=orig`, che pero' lo **normalizza** prima di darlo a Shadow: cosi'
com'e' non e' caricabile (vedi *Vincoli di Shadow*, punto 4). Le sue latenze di accesso (1.0–1.8 ms) coincidono di fatto con
quelle del modello; quelle di dorsale sono invece ~3× superiori (4 ms fra
Firenze e Bologna, contro 1.07 ms). Usato cosi' com'e', il livello regionale
risulterebbe **piu' lento del nazionale a parita' di distanza** e i quattro
livelli non sarebbero confrontabili: per questo il default rigenera anche il
regionale con il modello comune. Nodi, ruoli, struttura degli archi e banda
restano quelli del file originale.

### Dimensionare `tbt` per livello

Con `tbt=15 s` e `delta=0.5` la banda di ritardo vale `Δmax = 7.5 s`, cioe' ~80
volte l'RTT peggiore anche a New York. La legge di scala della Prop. 5.18,

```
Pr[inversione del vincitore] = O( (n·σ / Δmax)^{2/3} )
```

rende quindi l'effetto della geografia trascurabile: **a 15 s i quattro livelli
si comportano quasi allo stesso modo, ed e' il risultato atteso**. Per rendere
la latenza una variabile dominante bisogna comprimere `tbt` (e con esso `Δmax`,
che ne e' una frazione):

| livello | RTT max | `tbt` per un `Δmax` ≈ 20–40× RTT | `tbt` per stressare la timer race |
|---|---|---|---|
| regionale | 10 ms | 15 s | 2 s |
| nazionale | 22 ms | 15 s | 3 s |
| continentale | 45 ms | 15 s | 5 s |
| intercontinentale | 112 ms | 15 s | 10 s |

Il confronto interessante e' quindi **a `tbt` costante fra i livelli** (isola
l'effetto della geografia) e, separatamente, **a `tbt` decrescente** (mostra
dove la timer race inizia a girare sul rumore invece che sullo score).

---

## Vincoli di Shadow scoperti sul campo

Tre proprieta' del simulatore hanno determinato l'architettura di questa suite.
Sono documentate qui perche' non sono ovvie e ricomparirebbero in qualunque
altro tentativo.

### 1. `--unblocked-vdso-latency` e' obbligatorio

`Strengthen()` in `src/utils/random.cpp` e' un busy-loop che rimescola SHA512
finche' non sono passati 100 ms di orologio:

```cpp
int64_t stop = GetTimeMicros() + microseconds;
do { for (int i = 0; i < 1000; ++i) { /* SHA512 */ } ... }
while (GetTimeMicros() < stop);
```

`clock_gettime` e `gettimeofday` passano dal **vDSO**, a cui Shadow accredita
**10 ns** di default: servono 5 milioni di iterazioni per far avanzare
l'orologio di 100 ms, cioe' decine di minuti di wall clock **per processo**.
Con i default il nodo non arriva nemmeno ad aprire `debug.log`.

`--unblocked-vdso-latency 20us` porta il boot a ~2 s. La distorsione e'
contenuta perche' il loop e' pagato **una volta sola per processo**
(`SeedStartup`, al primo uso dell'RNG): `RandAddPeriodic()` non ha chiamanti nel
fork, quindi non c'e' costo ricorrente. Alzare invece
`--unblocked-syscall-latency` non serve: la latenza da correggere e' quella
vDSO.

E' anche la ragione per cui i role script parlano JSON-RPC via **`curl`** e non
via `multichain-cli`: ogni invocazione della CLI pagherebbe di nuovo quei 100 ms.

### 2. L'orologio simulato parte dal 2000-01-01 e non e' configurabile

Non esiste opzione di epoch in Shadow 3.3. Un datadir preparato nativamente
porta blocchi datati oggi, e il nodo li rifiuta all'avvio:

```
ERROR: Block time: 1787842836. Node time: 946684800
ERROR: CheckBlockHeader() : block timestamp too far in the future
: Corrupted block database detected.
```

Percio' **tutto il bootstrap avviene dentro la simulazione**. L'unico passo
nativo e' `multichain-util create`, che scrive `params.dat` — file che non
contiene alcun timestamp finche' la genesi non e' sigillata.

### 3. `wpoa-weights` va creato esplicitamente, o la catena si ferma

Con il weight engine attivo il registro dei pesi non crea il proprio stream
finche' non ha un peso da pubblicare, e non ha un peso finche' non esistono
record di membership e ESG. Al raggiungimento di `setup-first-blocks` la wPoA
subentra, trova la mappa vuota e nessuno propone:

```
[StreamWeightRegistry] All nodes weights: 0 validators, total=0
mchn-miner: wPoA-sortition height=60 cannot score (unsynced or unweighted), waiting
```

`role_admin.sh grant` crea quindi `wpoa-weights` esplicitamente (CLOSED, come
farebbe `StreamWeightRegistry::EnsureStreamExists()`) prima di concedere i
permessi di scrittura.

### 4. Il parser GML di Shadow e' piu' rigido di quanto documentato

Tre vincoli, tutti verificati sul campo e nessuno riportato nel manuale. Il file
`.gml` originale ne violava due, e Shadow lo rifiutava prima ancora di avviare
la simulazione:

| vincolo | errore se violato |
|---|---|
| nessuna riga di commento (`#`) | `Failed to parse the network graph ... in Verify` |
| blocchi `node`/`edge` in forma canonica multi-riga: `node [ id 0 label "x" ]` su una riga sola non e' accettato | `... in MultiSpace` |
| magnitudini **intere** nelle stringhe con unita': `latency "0.2 ms"` non e' valido | `Edge 'latency' is not a valid unit: invalid digit found in string` |

`gen_topology.py` emette quindi latenze in **microsecondi interi** e blocchi
multi-riga senza commenti; `check_topology.py` verifica il terzo vincolo prima
di lanciare Shadow. Con `topology=orig` il file originale viene normalizzato
automaticamente (stessi valori, sintassi diversa) invece di essere passato
com'e'.

### 5. Altri ostacoli incontrati e come sono risolti

**`maxtxfee` va alzato insieme alla fee.** Il wallet ha un tetto di default di
`0.1` unita' di valuta nativa per transazione (`DEFAULT_TRANSACTION_MAXFEE`,
`wallet/wallet.cpp:36`). Con `minimum-relay-fee = 0.2 GAS / 1000 byte`, ogni
transazione oltre i ~500 byte richiede piu' di quel tetto e
`CreateTransaction` la rifiuta con `Transaction too large for fee policy`
(`walletcoins.cpp:2465`). Colpisce le `publish` su stream — quindi membership,
ESG e traffico — ma non le `send`, piu' piccole: il sintomo e' una rete che
sembra funzionare mentre nessun record viene mai pubblicato.
`prepare_params.sh` scrive quindi `maxtxfee=10.0` in ogni `multichain.conf`.

**Il nodo admin va iscritto esplicitamente agli stream.** Non essendo capo
cluster non pubblica pesi, e il registro iscrive solo i nodi che pubblicano:
senza `subscribe` lo snapshot finale e `weightverifyweights` fallirebbero con
`Not subscribed to this stream`. `subscribe` esegue un rescan, quindi indicizza
anche gli item gia' confermati.

**Il CA paga le fee come gli altri.** Pubblica 8 record ESG e senza dotazione
iniziale fallisce con `Insufficient funds`: e' incluso nella distribuzione e nel
ciclo di rifornimento.

**`no local mining key, waiting`** compare a raffica nei `debug.log` dei miner
anche quando minano regolarmente: e' una condizione transitoria del ciclo di
mining, non un errore. Nella run di validazione i tre miner hanno prodotto
blocchi (34 / 29 / 17 su 80) pur emettendo quel messaggio centinaia di volte.

---

## Fedelta' e limiti noti

**L'intervallo fra blocchi risulta leggermente sovrastimato.** Nella run di
validazione (regionale, `tbt=15`) la media misurata e' 17.9 s contro un target
di 15 s. Due contributi si sommano al ritardo di protocollo: il tempo di
propagazione e validazione del blocco, e la latenza simulata che Shadow addebita
alle chiamate vDSO (`vdso=20us`). Il secondo e' un artefatto del simulatore, non
del protocollo: per stimarlo basta ripetere la stessa run con `vdso=5us` e
`vdso=50us` e osservare come si sposta la media. E' la prima verifica da fare
prima di attribuire uno scostamento del block time alla retroazione `λΦ`.

**Il campione minimo per il chi-quadro.** Con 3 miner il test richiede almeno 5
blocchi attesi per miner: con quote molto sbilanciate servono parecchie
centinaia di blocchi misurati perche' il test sia applicabile. `blocks=200` e'
sufficiente in configurazioni equilibrate; con un miner molto dominante conviene
`blocks=500`.

**I pesi cambiano fra le epoche.** Il test confronta la distribuzione osservata
con l'ULTIMO peso pubblicato. Se la traiettoria per epoca mostra pesi che
variano molto, il confronto e' indicativo e va letto insieme alla traiettoria,
non al posto di essa.

---

## Timeline del bootstrap

| t simulato | chi | cosa |
|---|---|---|
| 0 s | `admin` | `multichaind` → genesi, premine, creazione degli stream input |
| 30 s | gli altri 9 | primo avvio: creano wallet, stampano l'indirizzo, escono |
| 60 s | `admin` | grant permessi, `high1` al CA, crea `wpoa-weights` e lo stream di filiera, distribuisce il GAS |
| 150 s | gli altri 9 | `multichaind` vero: join e sync |
| 260 s | `ca`, miner, aziende | ESG certificati; adesioni ai cluster |
| 340 s | aziende, miner, `admin` | traffico, riconciliazione, rifornimento GAS |
| height = `setup` | tutti | **la wPoA subentra alla PoA nativa** → inizio finestra di misura |
| stop − 120 s | `admin` | snapshot finale dello stato della catena |

Il join a due fasi e' quello nativo di MultiChain: su una catena permissioned il
primo avvio di un nodo non entra in rete, stampa il proprio indirizzo e termina
in attesa dei permessi. `node_first_launch.sh` cattura quell'indirizzo in
`shared/<host>.addr`; il join vero e' un secondo processo schedulato piu' avanti.

### Vincolo sul setup

La fase di setup deve durare abbastanza da far confermare membership e ESG,
seppellire l'epoca che li contiene (epoca + 6 blocchi di margine di stabilita')
e pubblicare i pesi. `run.sh` calcola il minimo

```
setup_min = ceil(340 / tbt) + epochlen + 6 + 12
```

e lo applica se `setup=` non e' stato passato; se e' stato passato e risulta
troppo corto, si ferma con un errore invece di produrre una run che stallerebbe.

Nel modo dichiarativo vale la stessa formula, con un pavimento assoluto di 60
blocchi: `tools/gen_simulation.py` la applica quando il file `.dat` dice
`SETUP_FIRST_BLOCKS=auto`, e rifiuta con un errore esplicito un valore intero
che risulti sotto `setup_min`. A monte c'e' comunque la derivazione fatta da
`multichain-util` al genesi, che puo' alzare ulteriormente il valore: e' quello
riletto da `params.dat` a decidere la finestra di misura.

---

## Economia del GAS

Segue il cap. 4.2.1 / 4.3.1 della tesi.

* **premine**: `first-block-reward = 10⁶ GAS`, `initial-block-reward = 0` →
  l'intera quantita' nasce con la genesi ed e' di Apuana SB, senza conio
  successivo;
* **fee**: `minimum-relay-fee = 0.2 GAS / 1000 byte` ≈ **0.2 GAS a transazione**,
  incassata dal miner che la include;
* **distribuzione**: l'`admin` versa 100 GAS a ogni azienda e 50 GAS a ogni
  miner (fondo cassa per riconciliare);
* **rifornimento**: `role_admin.sh refill` interroga ogni 30 s il saldo di ogni
  nodo e, sotto i 20 GAS, ne versa altri 100. **Nessuna run si ferma perche' un
  nodo ha esaurito il GAS**; ogni movimento e' tracciato in
  `metrics/gas_transfers.csv`;
* **riconciliazione**: ogni miner rimanda al treasury una frazione del proprio
  saldo a ogni epoca. E' questo trasferimento — derivato dai blocchi confermati,
  mai dichiarato — a costituire `R_k` (Def. 6.7) e quindi `rho_k`, la
  retroazione inter-epoca sul peso.

Il treasury esiste per una via traversa, documentata in `tools/gen_treasury.sh`:
`weight-treasury-address` e' hash-enforced e va scritto in `params.dat` prima
della genesi, ma l'indirizzo dell'admin nasce *con* la genesi. Si spezza la
circolarita' **pinnando lo spazio degli indirizzi** (`address-pubkeyhash-version`
e affini, normalmente casuali per catena) e pre-generando una coppia di chiavi
riusabile su tutti i livelli. La chiave e' importata **watch-only** nel wallet
dell'admin: il saldo riconciliato e' osservabile senza inquinare il saldo
spendibile che serve ai rifornimenti.

---

## Metriche

`tools/collect_metrics.py` gira in coda a ogni run e scrive
`metrics/summary.txt`. La sorgente primaria e' lo **snapshot JSON** prodotto dal
nodo admin (`listblocks` riporta il proposer di ogni altezza): il parsing dei
`debug.log` serve solo ai contatori diagnostici.

* intervallo fra blocchi nella finestra wPoA (media, mediana, σ, min/max) contro
  `target-block-time` — misura diretta dell'effetto della retroazione `λΦ`;
* **distribuzione dei proposer contro i pesi pubblicati**, con test chi-quadro:
  e' la verifica sperimentale del Teor. 5.3;
* traiettoria per epoca dei pesi su `wpoa-weights`;
* consistenza fra nodi a fine run (altezze e best-hash divergenti = fork
  persistente);
* ESG certificati, adesioni, riconciliazione, movimenti GAS;
* `weightverifyweights`: la ricomputazione indipendente dei pesi pubblicati.

### Le stesse analisi, epoca per epoca

`tools/summary_per_epoca.py` gira subito dopo e scrive
`metrics/summary_epoche.txt`: stessa struttura, ma un blocco per epoca invece di
uno per run. La differenza non e' cosmetica. Il riepilogo di run confronta i
blocchi di **tutta** la finestra con l'**ultimo** peso pubblicato, e lo dichiara:
se il peso e' cambiato fra le epoche — ed e' esattamente cio' che il weight
engine fa — il test e' solo indicativo. Il riepilogo per epoca confronta invece
i blocchi di ogni epoca col peso che era davvero **leggibile alla punta della
catena** mentre venivano proposti.

Attenzione allo sfasamento di una epoca: il record marcato `epoch = e` viene
pubblicato a epoca **gia' chiusa**, dopo il margine di stabilita', quindi entra
in vigore dentro l'epoca `e+1`. La colonna `marca` della tabella "Peso VIGENTE"
lo rende leggibile a occhio.

Ogni blocco riporta, per quella sola epoca: intervallo fra blocchi contro il
target; peso vigente e peso marcato; la catena del peso anello per anello
(ESG, `tau`, `c_i`, `Theta`, `W_k`, `A_k`, `B`, `R_k`, `rho`, `w_k` pubblicato e
ricalcolato); proposer **osservati e attesi** con il chi-quadro dell'epoca e
quello a finestra scorrevole, ciascuno con la propria attesa minima e il
verdetto sulla sufficienza del campione; delay di sortition e margine `G`;
riconciliazione; la verifica indipendente dei pesi nodo per nodo. In testa, un
"quadro d'insieme" con una riga per epoca.

Il chi-quadro su una singola epoca di 12 blocchi ha attesa minima intorno a 1 e
**non e' concludente**: il file lo dice in ogni blocco invece di lasciarlo
dedurre. E' la finestra scorrevole a portare il campione a un livello leggibile
— o un `weight-epoch-length` piu' lungo, come nella run a epoche da 100 blocchi,
dove l'attesa minima supera 5 e il test per epoca diventa valido da solo.

### Campionamenti a ogni epoca (`metrics/epoche/`)

`role_admin.sh epoch_watch` gira **dentro** la simulazione, dal momento in cui
parte il traffico, e a ogni epoca chiusa e sepolta appende cio' che a fine run
non sarebbe piu' ricostruibile:

* `verify_epoche.jsonl` — `weightverifyweights` a quella epoca. La RPC riporta
  solo l'**ultima** epoca che il nodo ha verificato, quindi lo snapshot finale
  ne conserverebbe una sola;
* `node_state_epoche.csv` — altezza, best-hash e peer di ogni nodo a quella
  epoca: e' cio' che rende visibile un fork **riassorbito** a metà run, che
  `node_state.csv` (istantanea finale) non mostrerebbe;
* `treasury_epoche.csv` — il saldo del treasury come serie, non come numero
  finale.

Il campionamento usa solo bash e curl, mai un interprete: per lo stesso motivo
per cui `sim_common.sh` usa curl e non `multichain-cli` (vedi *Vincoli di
Shadow*), un processo Python avviato a ogni epoca dentro la simulazione
sposterebbe l'orologio simulato del nodo che nel frattempo deve rifornire il
GAS. Il `.txt` viene percio' costruito **fuori** da Shadow, a simulazione
conclusa, da `run.sh`.

Le epoche interamente dentro la fase di setup non vengono campionate: non hanno
blocchi governati dalla wPoA. Le epoche pronte vengono recuperate **tutte** a
ogni controllo, non solo l'ultima: la finestra di sepoltura e' larga poche
altezze e con `target-block-time` basso un solo campionamento per ciclo
salterebbe epoche intere.

`tools/compare_levels.py` mette in fila le run dei quattro livelli in una sola
tabella (RTT massimo, block time, quote dei proposer, margine della timer race,
alternanze, numero di teste distinte): e' il confronto che l'esperimento vuole
produrre, e va lanciato dopo aver eseguito i livelli che interessano.

### Lo Spacing nativo resta vincolante sotto wPoA

E' il risultato piu' netto emerso dalla validazione, ed e' la prima cosa da
controllare prima di interpretare qualunque distribuzione dei proposer.

Nelle prime run (`mining-diversity = 0.3`, N = 4 indirizzi con permesso `mine`)
**nessun miner ha mai firmato due blocchi consecutivi: 0 su 380 blocchi
misurati sui quattro livelli**, contro le ~34 coppie attese per livello da una
selezione pesata (la probabilita' teorica e' la somma dei quadrati delle quote).
Zero non e' un esito statistico: e' la firma di un vincolo di alternanza attivo.

Il vincolo e' lo **Spacing** di `mining-diversity`, che vale `ceil(d*(N-1))`:
con `d = 0.3` e `N = 4` vale esattamente 1, cioe' "mai due blocchi di fila allo
stesso firmatario". La distribuzione osservata collassava quindi su un round
robin (circa 40 / 35 / 25 %) qualunque fossero i pesi pubblicati.

La tesi (Sez. 5.12.3) prevede che sotto wPoA lo Spacing sia rimosso, e
`VerifyBlockMinerWPoA` in effetti non lo applica in validazione; la misura dice
che sul percorso del **miner** resta invece efficace — esattamente il caso di cui
avverte la Sez. 7.4. `params.overrides` imposta percio' `MINING_DIVERSITY=0`,
che lo rende inerte per costruzione (`ceil(0) = 0`).

**Controprova.** La stessa configurazione con `d = 0` (regionale, 109 blocchi
misurati):

| | m1 | m2 | m3 | chi-quadro (df=2, critico 5% = 5.991) |
|---|---|---|---|---|
| `d = 0.3` — quota osservata | 39 % | 33 % | 28 % | **69.50 → non compatibile** |
| `d = 0` — quota osservata | 65.1 % | 27.5 % | 7.3 % | **0.479 → compatibile** |
| `d = 0` — quota attesa dai pesi | 62.2 % | 30.5 % | 7.3 % | |

E le alternanze tornano quelle previste: 62 blocchi consecutivi dello stesso
proposer osservati contro 54.6 attesi (erano 0 contro 34.6). **E' la verifica
sperimentale del Teor. 5.3**: rimosso il vincolo residuo, la selezione pesata
riproduce le probabilita' w_i / W_tot entro il rumore statistico.

Rialzare `MINING_DIVERSITY` e' a sua volta un esperimento sensato: misura quanto
lo spacing residuo interferisca con la selezione pesata.

### Come leggere la distribuzione dei proposer

Il confronto fra quota di blocchi e quota di peso e' il cuore dell'esperimento,
ma va letto insieme alla tabella dei **delay di sortition**, che il riepilogo
stampa subito sotto. Il motivo e' nella catena che porta dal peso al timer
(Sez. 5.10):

```
score_i      = E_i / w_i                     E_i ~ Exp(1)
score_norm_i = 1 - exp(-W_tot · score_i)     = 1 - exp(-E_i · W_tot/w_i)
D_i          = T + Δmax·(2·score_norm_i - 1) + λΦ
```

`score_norm` dipende solo dal **rapporto** `W_tot/w_i`. Per un candidato con
quota di peso piccola quel rapporto e' grande, l'esponenziale satura verso 1 e
il suo delay si schiaccia contro il tetto della banda: tutti i candidati poco
pesanti finiscono separati fra loro da frazioni di secondo. Quando quella
separazione scende sotto la varianza di rete, il vincitore della timer race e'
deciso dalla latenza e non dallo score — e' esattamente il regime della
Prop. 5.18, e la distribuzione osservata si appiattisce rispetto ai pesi.

Nelle run di validazione i delay medi misurati sono ordinati correttamente per
peso (16.4 / 18.8 / 21.0 s con pesi 83k / 41k / 10k), ma compressi verso l'alto:
il miner piu' leggero passa il 90 % della banda nella sua parte superiore. Con
`mining-diversity = 0` questa compressione **non** impedisce alla distribuzione
di restare compatibile con i pesi (chi-quadro 0.479), perche' solo l'1.7 % dei
round ha un margine sotto i 100 ms. E' pero' il meccanismo che degrada per primo
quando si comprime `tbt`: a `tbt` piccolo la stessa compressione porta il margine
sotto la varianza di rete e la selezione inizia a girare sul rumore.

Se invece si vuole *verificare* la proporzionalita' del Teor. 5.3 in condizioni
non degeneri, bisogna riportare i candidati nella parte non satura della curva:

* alzare `tbt` (allarga `Δmax = δ·T` in valore assoluto, quindi la separazione
  in secondi fra candidati vicini);
* usare `dumpfunction=sqrt` o `log` in `config/params.overrides`, che comprime i
  rapporti fra i pesi — e' precisamente la funzione di smorzamento della
  Def. 5.9;
* ridurre l'eterogeneita' dei cluster (traffico e ESG piu' simili), a costo di
  rendere l'esperimento meno interessante.


---

## Struttura

```
shadow/
├── run.sh                     dispatcher: --config=<descrittore>
├── config/
│   ├── simulation.schema.json JSON Schema del descrittore di simulazione
│   ├── blockchain/*.dat       ASSE 1 — parametri di catena riusabili
│   ├── topologies/*.gml       ASSE 2 — topologie riusabili (+ README.md)
│   ├── simulations/*.json     descrittori: l'unico file passato a run.sh
│   ├── treasury.json          coppia di chiavi del treasury (generata una volta)
│   ├── params.overrides       [modo livelli] parametri comuni ai 4 livelli
│   └── levels/*.json          [modo livelli] nodi, ruoli, coordinate, archi
├── tools/
│   ├── gen_simulation.py      descrittore → shadow.yaml (validazione + timeline)
│   ├── gen_topology.py        modello di latenza → .gml
│   ├── check_topology.py      validazione networkx + matrice RTT
│   ├── gen_shadow_yaml.py     [modo livelli] .gml + ruoli → shadow.yaml
│   ├── gen_treasury.sh        coppia di chiavi del treasury (una tantum)
│   ├── prepare_params.sh      params.dat nativo (unico passo fuori simulazione)
│   ├── sim_common.sh          helper JSON-RPC via curl, usati dentro Shadow
│   ├── rpc.sh                 client RPC a riga di comando
│   ├── node_first_launch.sh   fase 1 del join
│   ├── role_admin.sh          grant / refill GAS / snapshot finale
│   ├── role_ca.sh             certificazione ESG
│   ├── role_miner.sh          membership + riconciliazione
│   ├── role_company.sh        membership + traffico di filiera
│   ├── collect_metrics.py     snapshot + debug.log → summary.txt
│   ├── summary_per_epoca.py   le stesse analisi, epoca per epoca →
│   │                          summary_epoche.txt
│   └── compare_levels.py      tabella di confronto fra i quattro livelli
├── runs/<nome>/               output delle simulazioni (non versionato)
│   ├── shadow.yaml            generato da gen_simulation.py
│   └── data|shared|metrics/
└── <livello>/                 [modo livelli, deprecato]
    ├── topologia_myledger_<livello>.gml
    ├── shadow.yaml            generato
    └── run/                   output della run (non versionato)
```

Nulla fuori da questa directory viene toccato: il fork wPoA e' usato come
binario, non modificato.

---

## Riproducibilita'

`seed=` alimenta sia il seme di Shadow sia l'estrazione degli ESG. A parita' di
seed, binario e host, la stessa run produce gli stessi ESG e la stessa
schedulazione. Restano due sorgenti di non-determinismo note e non eliminabili:

* Shadow non riesce a emulare `cpuid` su questa piattaforma (WSL2), quindi
  `rdrand`/`rdseed` restano nativi — lo segnala esso stesso all'avvio;
* i punteggi ESG usano `srand()`/`rand()` di `awk`, la cui sequenza dipende
  dall'implementazione di awk installata.
