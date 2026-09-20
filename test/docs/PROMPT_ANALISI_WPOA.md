# PROMPT — Analisi di una run sperimentale wPoA

> **Questo file è un prompt operativo, non documentazione.** Chi lo legge è una sessione di
> Claude Code a cui è stato dato *soltanto* questo file più il percorso di una cartella di run.
> Tutto ciò che serve per produrre il report è contenuto qui: non esiste alcuna tesi da
> consultare, nessun capitolo da aprire, nessun contesto di sessioni precedenti.
>
> **Output finale obbligatorio:** il file `<percorso-run>/analysis/ANALISI.md`, scritto su disco.

---

## 0. Come si usa

L'utente fornisce il percorso di una cartella di run, per esempio:

```
test/results/run-wpoa-core-intercontinental-20260918T231018Z/
test/results/run-wpoa-long-10h-medium-sqrt/run-wpoa-long10h-medium-sqrt-20260917T221554Z/
```

**Attenzione al nesting:** alcune run sono state estratte da un `.tar.gz` e la cartella
indicata dall'utente può contenere a sua volta la vera cartella di run. La cartella di run è
**quella che contiene `manifest.json` e la sottocartella `analysis/`**. Se il percorso fornito
non li contiene, scendere di un livello prima di fare qualunque altra cosa.

Da lì in avanti tutti i percorsi in questo documento sono relativi a `<RUN>/`.

---

## 1. Ruolo e contesto: cos'è il sistema che stai analizzando

### 1.1 In una frase

wPoA è un fork di **MultiChain** (blockchain permissioned UTXO derivata da Bitcoin Core) in
cui la Proof of Authority nativa — un round robin egalitario fra miner autorizzati — è
sostituita da una **weighted private sortition**: a ogni round ciascun validatore calcola
localmente, tramite una VRF su un seed RANDAO pubblico, uno score segreto; la trasformazione
di **Efraimidis–Spirakis** rende la probabilità di vittoria proporzionale al peso del
validatore; lo score è poi mappato in modo monotono su un **delay di scheduling**, cosicché la
timer race locale già presente in MultiChain elegga il vincitore della sortition senza
introdurre alcun sotto-protocollo di rivelazione.

Il peso non è un parametro statico: è prodotto da un **weight engine** che aggrega score ESG
certificati e partecipazione on-chain a livello di *cluster* (un miner più le aziende sue
clienti), con una **retroazione inter-epoca**. A valle, il peso è corretto da un **malus
comportamentale** (violazioni provate on-chain) e **smorzato** da una funzione concava
opzionale prima di entrare nella sortition.

### 1.2 Lo stack, dal basso

```
L0  VRF nativa su secp256k1 (prova + verifica, unicità verificabile)
L1  Registro dei pesi         -> stream `wpoa-weights`
    Registro dei malus        -> stream `wpoa-weights-malus` (scrittura universale)
L2  Accumulatore RANDAO       -> beacon pubblico, seed del round
L3  Sortition privata pesata  -> score_i = E_i / w_eff_i, argmin vince
L4  Delay / timer race        -> D_i = T_block + Delta_max*(2*score_norm_i - 1) + lambda*Phi
```

Sopra allo stack, indipendente da esso, gira il **weight engine** che pubblica `w_k` epoca per
epoca sullo stream `wpoa-weights`.

### 1.3 Formule (tutte quelle che servono, per intero)

#### (a) Score di elezione e proporzionalità — *Teorema 5.3 (Efraimidis–Spirakis)*

Ogni validatore ricava dalla propria VRF un campione privato `u_i ~ Uniform(0,1)` e pone

```
E_i     = -ln(u_i)              ->  E_i ~ Exp(1),  i.i.d.,  E[E_i] = 1
score_i = E_i / w_i
```

Vince il validatore di **score minimo**. Allora, esattamente:

```
Pr[ argmin_i score_i = j ] = w_j / sum_k w_k
```

Il risultato è esatto, non asintotico, e vale per **qualsiasi** vettore di pesi `w_i > 0`.
Estensione a pesi non negativi: se alcuni `w_i = 0` (convenzione `score_i = +infinito`), la
formula resta valida e quei validatori vincono con probabilità 0, purché almeno un candidato
conservi peso strettamente positivo.

> **Corollario operativo, da usare come test primario di qualità della randomness:**
> la variabile **grezza** `E_i` (score *prima* della divisione per il peso) deve distribuirsi
> come `Exp(1)` con media 1, **indipendentemente da tutto il resto** — pesi, smorzamento,
> malus, traffico, numero di candidati, topologia di rete. Se questo test fallisce, la VRF o
> il suo consumo sono difettosi e **ogni metrica a valle perde di significato**.

#### (b) Smorzamento del peso — *Sezione 5.8*

Una funzione di smorzamento `g: R>=0 -> R>=0`, monotona crescente e concava, definisce il
**peso efficace** `w_tilde_i = g(w_i)`. La probabilità di elezione reale diventa

```
Pr[ i eletto ] = g(w_i) / sum_k g(w_k)
```

Le tre varianti previste dal parametro di catena `dump-function`:

| `dump-function` | `g(w)`      | Effetto |
|---|---|---|
| `none` | `g(w) = w`        | Proporzionalità lineare, **nessuna compressione** |
| `sqrt` | `g(w) = sqrt(w)`  | Compressione moderata, il peso resta un vantaggio significativo ma sub-lineare |
| `log`  | `g(w) = ln(1+w)`  | Compressione aggressiva, livella fortemente le quote |

Proprietà da tenere presenti nel giudizio:

- Lo smorzamento **non altera mai l'ordinamento**: `g` è crescente, quindi chi ha peso maggiore
  resta più probabile. Un'inversione di ordinamento osservata *sistematicamente* sarebbe un
  difetto, non un effetto dello smorzamento.
- **Su pesi omogenei lo smorzamento è a effetto nullo.** Se `w_i == w` per ogni `i`, allora
  `g(w_i) == g(w)` e la distribuzione torna uniforme, identica al caso `none`. Più in generale,
  per pesi vicini a un valore comune l'effetto è del primo ordine nello scarto: **quanto più i
  pesi sono ravvicinati, tanto meno lo smorzamento si vede.** Questo è il caso più frequente
  in queste run (vedi §3.2, punto sui pesi effettivi): non concludere che "lo smorzamento non
  funziona" osservando quote quasi uguali su pesi quasi uguali.
- Compressione del vantaggio: per `w_i > w_j > 0` vale `g(w_i)/g(w_j) <= w_i/w_j`.

**Tabella di riferimento quantitativo** (una "balena" con `w = 100` contro 4 validatori pari
con `w = 10` ciascuno; peso totale 140):

| Configurazione | P(balena) | P(ciascun piccolo) | Quota balena | Rapporto balena/piccolo |
|---|---:|---:|---:|---:|
| `none` (nessuno smorzamento) | 0,714 | 0,071 | **71,4 %** | 10,0 |
| `sqrt` — `g(w)=sqrt(w)`      | 0,442 | 0,140 | **44,2 %** | 3,2 |
| `log` — `g(w)=ln(1+w)`       | 0,325 | 0,169 | **32,5 %** | 1,9 |

Usala per validare gli **ordini di grandezza**, ricalcolando le quote attese sui pesi reali
della run: non aspettarti questi numeri se la run non ha una balena.

#### (c) Score normalizzato e delay — *Sezione 5.9*

Con `W_tot` = somma dei pesi **efficaci** dei candidati eleggibili del round:

```
score_norm_i = 1 - exp( -W_tot * score_i )   in (0,1)
d_i          = Delta_max * ( 2 * score_norm_i - 1 )        [psi(x) = 2x - 1]
D_i          = T_block + d_i + lambda * Phi
Delta_max    = delta * T_block,   delta in (0,1)
```

- `T_block` = `target-block-time`, `delta` = `wpoa-sortition-delta`, `lambda` =
  `wpoa-sortition-lambda`.
- `x -> 1 - exp(-W_tot*x)` è strettamente crescente, quindi
  `argmin_i D_i = argmin_i score_norm_i = argmin_i score_i`: **il vincitore della timer race
  coincide con il vincitore della sortition**, e la probabilità di elezione resta quella del
  Teorema 5.3 (o del Corollario sullo smorzamento).
- La banda dei delay è `(T_block - Delta_max + lambda*Phi, T_block + Delta_max + lambda*Phi)`.

**Proposizione 5.11 — distribuzione uniforme dello score normalizzato del vincitore:**

```
score_norm del vincitore della sortition  ~  Uniform(0,1)
```

esattamente, **indipendentemente dal numero di candidati e dalla distribuzione dei pesi**.
Secondo test di sanità della randomness, da verificare subito dopo il test su `E_i`.

> ⚠ **Trappola da evitare nei dati.** "Vincitore" in Prop. 5.11 significa
> **`argmin` dello score** (il vincitore *designato* dalla sortition), non il nodo che ha
> effettivamente prodotto il blocco. Sotto latenza di rete i due possono differire
> (*inversione*, §1.3(f)). Nei CSV della run la colonna `is_winner` marca **chi ha minato il
> blocco**. Il test di Prop. 5.11 va quindi fatto sul **minimo di `score_norm_public` fra i
> candidati dello stesso round**, non sullo `score_norm_public` della riga con
> `is_winner = True`.
>
> Sul punteggio **vero** la logica si capovolge: `score_norm_true` esiste solo per il vincitore
> (è ricomputato dal reveal VRF del suo blocco) e prendere proprio quella riga **è** il test —
> media 0,5 se vince l'argmin, ≈ `1 - 1/(n+1)` se vince un validatore qualsiasi. È il test Q2 in
> cima a `timer_race.md`.

#### (d) Correzione globale `Phi` — *Definizioni 5.12–5.14, Corollario 5.15*

`Phi` è un termine **additivo e comune a tutti i candidati del round**, funzione deterministica
del solo stato finalizzato. Poiché è identico per tutti, si elide in ogni differenza fra
timer: **non altera l'ordinamento né le probabilità di elezione**, corregge solo la traiettoria
temporale aggregata della rete. Implementazione effettiva nel codice
(`src/wpoa/private_sortition.cpp`, `WPoASortitionFeedback`):

```
mean_spacing = ( time(tip) - time(tip - 12) ) / 12        finestra fissa di 12 blocchi
Phi          = clip( T_block - mean_spacing , -M , +M )
M            = min( 0.5 * T_block , M* )      con  M* = T_block * (1 - delta) / lambda
```

Blocchi troppo lenti (`mean_spacing > T_block`) → `Phi < 0` → timer più corti; troppo veloci →
`Phi > 0` → timer più lunghi. Vincolo di ammissibilità del timer (`D_i >= 0` sempre):
`Delta_max <= T_block - lambda*M`. Se `lambda = 0` la correzione è disattivata e
`Delta_max <= T_block` è l'unico vincolo.

**Conseguenza attesa:** la media dei block time realizzati deve convergere verso `T_block`. Se
si allontana sistematicamente, le cause da indagare sono: `lambda` troppo basso (correzione
troppo debole), `Phi` **saturato** a `±M` per lunghi tratti (la correzione è al massimo e non
basta), oppure un `lambda` troppo alto che produce **oscillazione persistente** invece di
convergenza (retroazione a guadagno eccessivo: correzioni sovradimensionate che invertono di
segno round dopo round).

#### (e) Margine della timer race — *Proposizione 5.17 (esatta)*

Siano `score_(1) <= score_(2)` i due score minimi del round e `i*` il vincitore. Allora,
esattamente:

```
score_(2) - score_(1)  ~  Exp( W_tot - w_eff_{i*} )
E[ score_(2) - score_(1) | i* ] = 1 / ( W_tot - w_eff_{i*} )
```

Equivalentemente il **gap standardizzato** `(score_(2) - score_(1)) * (W_tot - w_eff_{i*})` è
`Exp(1)`, **con media attesa 1**. È il test che la pipeline calcola per vincitore in
`phase3/wpoa_prop517.csv`.

Sul margine in *tempo* `G = D_(2) - D_(1)`: poiché `T_block + lambda*Phi` è comune a tutti i
candidati, si elide, e `G` è identico calcolato sui `D_i` o sui soli `d_i`. Sotto l'assunzione
(**approssimata, valida solo a pesi non concentrati**) che gli `score_norm` siano i.i.d.
uniformi, con `n` candidati:

```
G = 2 * Delta_max * X,   X ~ Beta(1, n),   E[G] = 2 * Delta_max / (n + 1)
Pr[G < t] = 1 - (1 - t/(2*Delta_max))^n
```

Questo test `Beta(1,n)` è esplicitamente etichettato **straw man** nella pipeline: assume pesi
uniformi ed è *atteso* rigettare quando non lo sono. Il test di riferimento è il KS contro la
distribuzione esatta simulata della sortition implementata.

#### (f) Inversione del vincitore sotto latenza — *Proposizione 5.18*

Modellando la latenza di propagazione come rumore additivo indipendente `L_i` a media nulla e
deviazione standard `sigma`, il vincitore osservato `î` può differire dal vincitore designato
`i*`. Per ogni soglia `t > 0`:

```
Pr[ î != i* ]  <=  2*sigma^2 / t^2  +  n*t / (2*Delta_max)
```

e ottimizzando in `t`:

```
Pr[ î != i* ]  =  O( ( n * sigma / Delta_max )^(2/3) )
```

La probabilità di inversione **cresce** con il numero di candidati `n` e con il rumore `sigma`,
**decresce** con l'ampiezza di banda `Delta_max`. Vincolo di dimensionamento pratico:
`Delta_max >~ n * sigma * eps^(-3/2)` per tenere l'inversione sotto `eps` — che tira in
direzione opposta al vincolo di ammissibilità `Delta_max <= T_block - lambda*M`. I due vincoli
possono essere incompatibili: è una verifica numerica, non una garanzia a priori.

**Un'inversione non rompe la safety né l'ordinamento teorico** (Prop. 5.10 resta vera in
assenza di errori di propagazione): sposta l'aderenza *empirica* della distribuzione osservata
rispetto a quella pesata. Un tasso di inversione alto è la spiegazione candidata numero uno
quando la sortition è perfetta (`E_i` ed `score_norm` puliti) ma la quota osservata per
validatore non segue il peso.

#### (g) Malus comportamentale — *Sezioni 5.10.3 e 7.8*

Stream `wpoa-weights-malus`, a **scrittura universale**: chiunque può segnalare, perché la
fiducia sta nella verificabilità crittografica dell'evidenza e non nell'identità del
segnalante. Ogni nodo applica autonomamente un **predicato di validità locale** e i nodi onesti
concordano sempre sul verdetto. Quattro tipi di violazione, in due famiglie:

| `kind` | Famiglia | Prova contro | Cosa attacca |
|---|---|---|---|
| `Equiv` | comportamentale | due blocchi distinti alla stessa altezza con VRF valida sullo stesso seed | safety (fork concorrenti) |
| `Delay` | comportamentale | blocco con timestamp anteriore al proprio `D_i` | correttezza dello scheduling |
| `SelfWrite` | integrità dei dati | transazione firmata da `j` che pubblica un record con `addr != j` su stream auto-attestato | input del calcolo del peso (tentativo, comunque scartato dai lettori onesti) |
| `BadWeight` | integrità dei dati | record `wpoa-weights` firmato dal soggetto corretto ma con `w != w_k` ricalcolato | input del calcolo del peso (**ha effetto** finché nessuno lo confuta) |

Accumulazione e correzione del peso:

```
M_i^(e) = mu * M_i^(e-1) + somma dei p(kind) dei record VALIDI dell'epoca e,   M_i^(0) = 0
Psi_i^(e) = max( 0 , 1 - M_i^(e) / M_max )   in [0,1]
w_eff_i   = w_i * Psi_i^(e)
```

Parametri di catena: `wpoa-malus-mu` = `mu`, `wpoa-malus-max` = `M_max`, e i punteggi
`wpoa-malus-equiv-points`, `wpoa-malus-delay-points`, `wpoa-malus-selfwrite-points`,
`wpoa-malus-badweight-points`. Ordinamento inteso dal protocollo:
`p(Equiv) > p(BadWeight) > p(SelfWrite) > p(Delay)`.

Proprietà da verificare nei dati:

- `M = 0` ⇒ `Psi = 1` ⇒ **effetto nullo sul comportamento onesto** (invariante duro).
- `Psi` è sempre in `[0,1]`, e `w_eff` deve coincidere con `w * Psi` (invariante duro).
- **Latenza di applicazione:** un record valido riferito all'epoca `e` agisce a partire
  dall'epoca `e+1`. Non cercare l'effetto del malus nella stessa epoca in cui è provato.
- **Reversibilità (nessun ban permanente):** in assenza di nuove violazioni,
  `M_i^(e0+k) = mu^k * M_i^(e0)`, quindi il validatore torna eleggibile dopo
  `k* = ceil( ln(M_i^(e0)/M_max) / ln(1/mu) )` epoche. Con `mu = 0.5` e `M_max = 4`, un
  validatore a `M = 8` rientra dopo 1 epoca pulita.
- Un impossibilità di verificare (epoca non ancora sepolta, nodo non sincronizzato) conta come
  **non valido**: l'incapacità di verificare non deve mai tradursi in penalità.

#### (h) Calcolo del peso (weight engine) — *Capitolo 6*

Il peso **non è statico**: evolve di epoca in epoca. Pipeline completa:

```
ESG_i, ESG_Mk  > 0        score ESG certificati, STATICI fra epoche (cambiano solo su
                          ri-certificazione esplicita)
tau_i^(e)                 attività dell'azienda i nell'epoca e (transazioni emesse)
tau_Mk^(e)                attività diretta del miner k

c_i^(e)  = ESG_i * tau_i^(e) / kappa                         contributo aziendale pesato
W_k^(e)  = ESG_Mk * ( tau_Mk^(e) + somma_{i in C_k} c_i^(e) ) peso GREZZO del cluster
```

Retroazione inter-epoca, unico canale endogeno:

```
g_k^(e)     = Entrate_k^(e) - Uscite_k^(e)          (escluse le restituzioni dell'epoca)
saldo_k^(e) = saldo_k^(e-1) + g_k^(e),   saldo_k^(0) = 0
R_k^(e)     = trasferimenti in native-currency dal miner k all'indirizzo di treasury,
              confermati nei blocchi dell'epoca e
rho_k^(e)   = R_k^(e) / saldo_k^(e)   in [0,1]      TASSO DI RESTITUZIONE
```

Peso definitivo, con `lambda_w` = parametro di catena `weight-lambda`, `lambda_w in [0,1)`:

```
w_k^(1) = W_k^(1)
w_k^(e) = W_k^(e) * [ rho_k^(e-1) * lambda_w + (1 - lambda_w) ]      per e >= 2
```

Osservazioni **decisive** per formulare le ipotesi attese:

- Il peso cresce con l'**attività** (`tau`) e con lo **score ESG**, e **non** direttamente con
  il guadagno. Il guadagno entra solo indirettamente, attraverso il `saldo` che compare al
  denominatore di `rho`.
- **Chi restituisce di più al treasury viene premiato**, chi trattiene GAS viene attenuato, nella
  misura regolata da `lambda_w`. `lambda_w -> 0` disattiva la retroazione (il peso collassa sul
  solo peso grezzo); `lambda_w` prossimo a 1 rende il peso quasi interamente governato da `rho`.
- `W_k^(e) = 0` **se e solo se** il cluster è stato del tutto inattivo nell'epoca.
- `weight-alpha` è un parametro **inerte**: il binario lo valida e poi non lo legge mai. È
  mantenuto solo perché rimuovere un campo hash-enforced renderebbe le catene esistenti non
  raggiungibili. **Non commentarlo come se avesse un effetto.**

Ordine finale di applicazione, dal peso pubblicato a ciò che la sortition consuma:

```
w_k (weight engine)  ->  * Psi (malus)  ->  g( . ) (dumping)  ->  w_eff usato da Efraimidis-Spirakis
```

### 1.4 Contesto sperimentale: cosa è casuale in una run

Il sistema è **intrinsecamente stocastico su più livelli indipendenti**. Questo va detto
esplicitamente nel report e va tenuto presente in ogni giudizio:

1. **Score ESG** estratti a caso in `esg_score_range` (tipicamente `[1, 100]`) e assegnati da
   una CA a ogni miner e a ogni azienda.
2. **Assegnazione azienda → cluster**, se non fissata esplicitamente nel profilo.
3. **Traffico**: numero di transazioni per azienda per epoca estratto in
   `company_tx_per_epoch_range`; numero e importo delle restituzioni per miner per epoca
   estratti in `miner_gas_returns_per_epoch_range` e `restitution_amount_range`.
4. **VRF**: lo score di ogni candidato a ogni round.
5. **Rete** (solo regime `core`): delay, jitter, perdita per link.

Tutto (1–3) è derivato deterministicamente dal `seed` del profilo, ma **è comunque un
campione**: due profili identici con seed diversi danno pesi diversi. Di conseguenza il sistema
**non va giudicato su singoli blocchi o singoli round**, ma su tendenze aggregate, con bande di
confidenza e con la correzione per confronti multipli.

**Conseguenza pratica ricorrente:** poiché i pesi nascono da `ESG × tau` con ESG uniforme in
`[1,100]` e `tau` in un range stretto, i pesi dei cluster risultano quasi sempre **dello stesso
ordine di grandezza** — tipicamente entro un fattore 2–3 fra il minimo e il massimo. **Non c'è
quasi mai una balena.** Per questo:

- le quote teoriche per validatore stanno in genere fra 0,07 e 0,15 con 10 miner;
- **lo smorzamento produce un effetto piccolo e difficile da vedere**, ed è corretto così
  (§1.3(b)): un `sqrt` o un `log` su pesi già omogenei quasi non sposta nulla;
- la Tabella 5.1 va usata solo come riferimento di ordine di grandezza per un ipotetico caso a
  pesi disomogenei, **non** come previsione per una run tipica.

Se invece la run *ha* un validatore con peso nettamente dominante, allora sì: con
`dump-function = none` deve dominare le elezioni in misura proporzionale al peso, e **questo è
comportamento corretto, non un bug**.

### 1.5 Parametri nativi MultiChain che possono mascherare wPoA

- `mining-diversity`: regola di consenso nativa che impone uno spacing minimo fra blocchi
  dello stesso miner. **Se > 0 può diventare vincolante e far collassare la distribuzione
  osservata sul round robin nativo**, mascherando esattamente ciò che si vuole misurare. Nei
  profili di questa campagna è impostato a `0.0` proprio per questo. Se in una run è `> 0`,
  dirlo esplicitamente e trattare tutte le metriche di quota come non conclusive.
- `setup-first-blocks`: i blocchi fino a questa altezza girano sotto **round robin nativo**, non
  sotto wPoA. Le epoche i cui round cadono a quell'altezza o sotto vanno **escluse**; la
  pipeline lo fa già e le marca con `in_setup = True`.
- `initial-block-reward`: su queste catene è tipicamente `0`, quindi **non esiste ricompensa da
  mining**. Le entrate dei miner sono fee più trasferimenti dal premine dell'admin. Se in una
  run i miner non ricevono GAS, `saldo_k` resta a zero, `R_k = 0`, `rho = 0` per tutti e **il
  canale di retroazione inter-epoca è inerte**: in quel caso `w_k = W_k * (1 - lambda_w)`, un
  riscalamento costante. **Non leggere l'assenza di correlazione `rho → peso` come un bug se
  `rho` è identicamente nullo**: verificalo prima.
- `mining-turnover`: euristica locale non verificabile di MultiChain, senza effetto sul
  meccanismo wPoA misurato qui.

---

## 2. Input atteso: la struttura reale di una run

### 2.1 Radice della run

| File | Cosa contiene |
|---|---|
| `manifest.json` | **La configurazione completa della run.** Profilo risolto, valori derivati, parametri di catena effettivi, tabella nodi, indirizzi, cluster, altezza finale, esito. È la fonte primaria per il passo §3.1. |
| `addresses.json` | mappa `node_id -> indirizzo`. Serve per etichettare i validatori. |
| `clusters.json` | mappa `company -> miner` (composizione dei cluster). |
| `malicious_manifest.json` | il piano malicious risolto. **Sempre presente**, anche quando `enabled = false`. |
| `treasury.txt` | indirizzo di treasury della rete. |
| `fabric.json` | (solo regime `core`) la mappa di rete emulata: siti, cavi, impairment. |
| `shutdown.json` | esito della chiusura dei nodi. |
| `logs/<node>/events.jsonl` | log JSON Lines per singolo daemon. **Fonte di ultima istanza**: usalo solo se un dato manca in `analysis/`. |
| `chains/<node>/` | data directory dei nodi. Spesso non leggibile (permessi `root`). Non serve. |

### 2.2 `analysis/` — la struttura delle tre fasi

Regola architetturale della pipeline, da rispettare anche in lettura: **ogni fase legge solo
l'output della precedente**, e le figure sono disegnate **solo** da `phase2`/`phase3`, mai dai
dati grezzi — così una figura e un test non possono mai essere in disaccordo sulla stessa
quantità.

- `analysis/phase1/` — tabelle piatte, una riga per record di input. Nessuna aggregazione,
  nessun test.
- `analysis/phase2/` — aggregazione a grana round / epoca / cluster, più il **ricalcolo
  indipendente del delay** a partire dagli input loggati.
- `analysis/phase3/` — l'unica fase che **testa**. Intervalli di Wilson, goodness of fit,
  concentrazione, streak, timer race, longitudinale, retroazione del weight engine, e i
  controlli di consistenza.
- `analysis/plots/` — le figure, più un `README.md` che le indicizza.

### 2.3 `analysis/phase1/` — dati normalizzati

| File | Cosa rappresenta |
|---|---|
| `config.csv` | `parameter,value,source,note` — i parametri effettivi **riletti dalla catena** (`params.dat`). Fonte di verità per i parametri di protocollo. |
| `blocks.csv` | `height,hash,miner_address,time,txcount,confirmations,epoch,in_setup` — un blocco per riga. |
| `round_scores.csv` | Per round e per candidato: `score`, `weight`, `effective_weight`, `eligible`, `seed`, `seed_source`, `dumping_function`, `total_effective_weight`. **Da qui si ricava `E_i = score * effective_weight`.** |
| `round_effective_weights.csv` | `raw_weight` → `effective_weight` dopo il solo smorzamento. |
| `round_final_weights.csv` | La catena completa: `raw_weight`, `malus`, `malus_factor` (= `Psi`), `weight_after_malus`, `dumping_function`, `effective_weight_after_malus_and_dumping`, `eligible`, `malus_epoch`. |
| `round_delays.csv` | `delay_s`, `score`, `score_norm`, `effective_weight`, `target_block_time`, `delta`, `lambda_s`, `feedback_phi`, `seed`, `dumping_function`, `total_effective_weight`. Tutti gli input del delay, loggati dal nodo. |
| `registry_weights.csv` | Snapshot del registro dei pesi: `sample_height,epoch,address,weight,validators,total`. |
| `malus.csv` | Snapshot dello stato malus: `address,malus,psi,weight,effective,excluded,epochs_to_clear,enabled`. |
| `malus_detections.csv` | Report di malus emessi dal detector onesto: `verdict,kind,accused_address,offence_height,evidence_txid,...`. **Vuoto se nessuno ha segnalato.** |
| `epoch_cluster_weights.csv` | Il weight engine epoca per epoca, per cluster: `miner_esg_score`, `miner_activity`, `companies`, `companies_contribution_sum`, `kappa`, `raw_cluster_weight`, `previous_epoch_return_rate`, `lambda_w`, `final_cluster_weight`, `published_weight`. |
| `epoch_contributions.csv` | Contributo per azienda: `address,cluster,esg_score,activity,kappa,contribution`. |
| `epoch_earnings.csv` | `income,expenses_gross,expenses_excl_return,earnings,return_amount,balance,return_rate` per miner ed epoca. |
| `epoch_returns.csv` | `returns` verso `treasury_address`, per miner ed epoca. |
| `epoch_balances.csv` | Saldo per miner ed epoca. |
| `esg_events.csv` | Ogni pubblicazione di score ESG da parte di una CA: `ca_node_id,target_node_id,target_role,target_address,esg_score,txid`. |
| `membership_events.csv` | Registrazioni di appartenenza al cluster. |
| `gas_returns.csv` | Ogni singola restituzione verso il treasury, con `amount`, `balance_before`, `txid`. |
| `gas_transfers.csv` | Trasferimenti di funding (premine → nodi). |
| `traffic_tx.csv` | Ogni transazione informativa emessa dalle aziende. |
| `epoch_plans.csv` | Quanto ciascun daemon **aveva pianificato** di emettere (`planned_tx`, `planned_returns`, `mean_gap_s`). |
| `stream_items.csv` | Ogni record confermato su ogni stream, con `data_json`. |
| `verification.csv` | Esito di `weightverifyweights`: `published` vs `recomputed`, `verdict`. **Questo è il canale che rileverebbe un `BadWeight`.** |
| `permissions.csv`, `miners.csv`, `nodes.csv`, `peers.csv`, `node_state.csv` | Stato di rete e permessi. `nodes.csv` dà `node_id ↔ address ↔ cluster_head`. |
| `topology_paths.csv` | (regime `core`) `validator_i,validator_j,path_delay_ms` sui percorsi minimi della mappa. |
| `rpc_errors.csv` | Errori RPC durante la run. Un numero non nullo non è di per sé un difetto (timeout benigni), ma va guardato. |
| `malicious_*.csv` | Piano, opportunità, azioni e conferme dell'esperimento malicious. **Vuoti se `enabled = false`.** |
| `manifest.json` | Manifesto della fase. |

### 2.4 `analysis/phase2/` — aggregati e ricalcolo

| File | Cosa rappresenta |
|---|---|
| `candidate_long.csv` | **La tabella centrale.** Una riga per `(round, candidato)`: `weight_raw`, `malus`, `malus_factor`, `weight_after_malus`, `weight_effective`, `W_tot_effective`, `p_theoretical`, `score_public`, `score_norm_public`, `score_norm_recomputed_public`, `score_norm_mismatch_public`, `delay_logged_public_s`, `delay_recomputed_public_s`, `delay_mismatch_public_s`, `delay_recompute_ok_public`, `eligible`, `is_winner`, `rank_by_delay_public`, `rank_by_score_public`. **Ogni colonna di punteggio qui è la forma pubblica `HMAC-SHA256(seed, indirizzo)`**, indipendente dal punteggio VRF privato con cui l'elezione ha girato: serve a verificare la *formula*, non l'ordinamento (regola 10 di §9 della GUIDA). |
| `round_level.csv` | Una riga per round: `winner_address`, `n_candidates`, `n_eligible`, `delay_min_public_s`, `delay_winner_public_s`, `margin_G_public_s`, `score_min_public`, `score_second_public`, `score_gap_2_1_public`, `W_tot_effective`, `weff_argmin_public`, `p_winner`, `phi_s`, `target_block_time`, `delta`, `lambda_s`, `argmin_delay_address_public`, `inversion_public`, `winner_rank_by_delay_public`, `block_time`, `dt_prev_s`, `scheduler_residual_public_s`, `txcount`, `n_delay_mismatch_public`, più le colonne del punteggio **vero** del vincitore: `score_true`, `score_norm_true`, `delay_true_s`, `earliest_time_true`, `residual_true_s`, `weff_winner_true`, `verdict_true`, `weight_epoch_stale`. |
| `epoch_level.csv` | Una riga per `(epoca, validatore)`: `O_i` (blocchi vinti), `n_blocks_epoch`, `p_theoretical_blockweighted`, `p_theoretical_start/end`, `share_changed_within_epoch`, `p_observed`, `E_i` (**qui `E_i` è il conteggio *atteso* di blocchi, non la variabile esponenziale** — non confonderli), `w_raw_start/end`, `w_eff_start/end`, `psi`, `delay_mean_public_s/min/max`. |
| `epoch_engine.csv` | Il weight engine per epoca e cluster: `miner_esg_score`, `miner_activity`, `W_k_raw`, `rho_prev`, `lambda_w`, `w_k_final`, `w_k_published`, `R_k`, `earnings_g_k`, `balance_saldo`, `return_rate_rho`, `income`, `expenses_gross`, `w_published_next_epoch`, `n_blocks_won_epoch`. |
| `epoch_concentration.csv` | HHI, `N_eff`, Gini, entropia normalizzata e soglie di Nakamoto (1/3, 1/2, 2/3), **teorici e osservati**, più `gini_published_weight`, `gini_input_esg_tau`, `gini_delta`. |
| `epoch_traffic.csv` | Per `(epoca, nodo)`: `planned`, `sent_logged`, `onchain_stream_items`, `onchain_confirmed_this_epoch`, `onchain_returns`, `full_epoch`, `in_range`, `range_low`, `range_high`. |
| `malus_state.csv` | Per `(epoca, indirizzo)`: `M`, `psi`, `weight_raw`, `weight_effective`, `excluded`, `epochs_to_clear`, `weff_recomputed`, e i tre invarianti `invariant_psi_in_unit`, `invariant_weff_matches`, `invariant_clean_psi_one`. |
| `malus_actions.csv`, `malus_detection_events.csv`, `malus_funnel.csv`, `malus_rate_by_miner.csv` | Il funnel dell'esperimento malicious: opportunità → tentativi → inviate → confermate → malus valido → segnalate. **Vuoti/degeneri se `enabled = false`.** |

### 2.5 `analysis/phase3/` — i test

**Report Markdown già generati** (leggili sempre per primi, sono il riassunto autorevole della
pipeline):

| File | Contenuto |
|---|---|
| `report.md` | Report funzionale complessivo: tabella d'intestazione della run, verdetto complessivo, i controlli di consistenza, la sintesi peso↔elezione, la tabella di concentrazione per epoca, il feedback del weight engine e le note di metodo. |
| `weight_vs_election.md` | **Il confronto per cui l'esperimento esiste.** Per ogni `(epoca, validatore)`: `w_final`, `p_theoretical`, `O_i`, `B`, `p_hat`, intervallo di Wilson 95 % e se contiene la quota spettante; poi la tabella di goodness-of-fit per epoca e una sezione "How to read this". |
| `streak.md` | Per epoca: lunghezza massima di vittorie consecutive osservata contro la media Monte-Carlo, e probabilità di ripetizione osservata contro quella Monte-Carlo, con i rispettivi p-value. |
| `timer_race.md` | Margine `G`, decomposizione del rumore in `sigma_S1` (topologia) e `sigma_S2` (residuo dello scheduler), bound di inversione (Prop. 5.18), probabilità simulata e tasso osservato. |
| `longitudinal.md` | GLM logit su `log(peso)` (`beta1 = 1` è l'ipotesi nulla della sortition pesata), regressione dei log-rapporti a coppie (pendenza 1, intercetta 0 attese) e sign test per validatore. |
| `malus_effectiveness.md` | **Presente solo se l'esperimento malicious è stato eseguito.** |

**Tabelle CSV:**

| File | Contenuto |
|---|---|
| `consistency_checks.csv` | `check,critical,passed,detail` — controlli di non-regressione, non test di ipotesi. Esistono per fallire rumorosamente quando la raccolta o la pipeline hanno un bug. |
| `wpoa_epoch_tests.csv` | Una riga per epoca con **tutto**: `gof_chi2`, `gof_df`, `gof_method`, `gof_p_value`, `gof_reject_alpha05`, `gof_mc_round_by_round_p`, `MAE_p`, `MaxAE_p`, `TV`, `share_changes_within_epoch`, streak (`L_max_observed`, `L_max_mc_mean`, `L_max_mc_p_value`, `repeat_prob_*`), concentrazione teorica e osservata (`p_theoretical_HHI/N_eff/gini/entropy_norm/nakamoto_*`, `p_hat_*`, `delta_*`), `delay_recompute_mismatch_rounds`, e inversione (`inversion_n`, `inversion_rate`, `inversion_wilson95_low/high`). |
| `wpoa_epoch_validators.csv` | Una riga per `(epoca, validatore)`: `O_i`, `n_blocks`, `p_hat`, `wilson95_low/high/width`, `p_theoretical`, `E_i` (atteso), `abs_error_p`, `excess_p`, `p_theoretical_inside_wilson95`, `binomial_two_sided_p`, `w_raw_end`, `w_eff_end`, `psi`. |
| `weight_election_wilson_coverage.csv` | Copertura degli intervalli di Wilson: `inside_wilson95`, `violation`, `p_hat`, `p_theoretical`. |
| `weight_election_residuals.csv` | Residui `p_hat - p_theoretical` per `(validatore, epoca)`. |
| `weight_election_pvalue_uniformity.csv` | `n_epochs`, `n_rejections`, `alpha`, `expected_rejections`, `ks_statistic_vs_uniform`, `ks_p_value`, `binomial_p_value_rejection_count`. |
| `wpoa_timer_race.csv` | Riga unica: `G_mean_s`, `G_median_s`, KS contro `Beta(1,n)` (straw man) e KS contro la simulazione esatta (riferimento), `inversion_bound_sigma_S1/S2`, `inversion_bound`, `inversion_mc_prob_gaussian_sigma_S2`, `inversion_observed_n`, `inversion_observed_rate`, più `target_block_time`, `delta`, `lambda`, `phi`, `D_max`, `n_candidates`. |
| `wpoa_sigma.csv` | Le tre stime di rumore: `S1_topology`, `S2_scheduler_residual_sd`, `S2b_inversion_gap`, con `sigma_s`, `n` e una nota che spiega cosa misurano. |
| `wpoa_prop517.csv` | Prop. 5.17 per vincitore: `ks_stat`, `ks_p`, `mean_standardised_gap` contro `expected_mean = 1.0`. |
| `wpoa_longitudinal_fits.csv` | Tre famiglie di fit: `monotonicity` (sign test per validatore), il GLM logit (`beta1`, `beta1_ci_low/high`, `beta1_consistent_with_1`, `converged`) e la regressione dei log-rapporti (`slope`, `intercept`, `pearson_r/p`, `spearman_rho/p`). |
| `wpoa_longitudinal_logratios.csv` | Ogni coppia `(epoca, i, j)` con `log_ratio_observed` e `log_ratio_theoretical`. |
| `wpoa_longitudinal_validators.csv` | Prima epoca contro ultima per validatore: `gain_observed`, `gain_theoretical`, `intervals_overlap`. |
| `weight_engine_epoch.csv` | Copia a grana epoca/cluster del weight engine (come `phase2/epoch_engine.csv`). |
| `weight_engine_correlations.csv` | Spearman lag-1 `rho(e) → peso pubblicato in e+1`, per cluster head e complessivo. |
| `weight_engine_gini.csv`, `weight_engine_gini_summary.csv` | `gini_published_weight` vs `gini_input_esg_tau` e la loro differenza, per epoca; poi pendenza, intercetta e Spearman della traiettoria. **Pendenza positiva = il motore concentra il peso oltre la disuguaglianza dei propri input.** |
| `malus_detection.csv` | Per `kind`: `true_positive`, `false_positive`, `false_negative`, `precision`, `recall`, `f1`. |
| `malus_funnel.csv`, `malus_latency.csv`, `malus_rate.csv` | Funnel, latenze (rilevazione e attivazione) e tassi. |
| `malus_invariants.csv` | Per `(epoca, validatore)`: `M`, `psi`, `weight_effective`, `weff_recomputed` e i tre invarianti booleani. |
| `malus_weight_effect.csv`, `malus_weight_effect_matched.csv` | Variazione relativa del peso efficace prima/dopo, malicious contro onesti, anche appaiati per banda di peso. |

**Costanti metodologiche fissate nel codice** (`analysis/pipeline/stat/`), non configurabili dal
profilo: `alpha = 0.05`, 20 000 estrazioni Monte-Carlo per il goodness of fit, 10 000 per gli
streak, seed dell'analisi `20260905`. I p-value Monte-Carlo sono `(hits + 1)/(draws + 1)`,
quindi **uno zero esatto non viene mai riportato**. Non è usato né `scipy` né `statsmodels`:
code chi-quadro, distribuzione di Kolmogorov, t di Student, binomiale esatta e fit logit IRLS
sono calcolati dalle rispettive forme chiuse.

### 2.6 `analysis/plots/` — le figure

`analysis/plots/README.md` le indicizza. Sopra le 6 entità, una figura che disegna una serie
per entità viene scritta **una per entità** in una sottocartella omonima, invece che come
griglia.

**Figure aggregate:**

| File | Cosa mostra (asse x → asse y) |
|---|---|
| `weight_vs_election.png` | epoca → quota di blocchi: barre quota spettante vs osservata, più scatter "entitled share (final weight)" vs "observed share", un punto per `(validatore, epoca)`. |
| `weights_over_time.png` | epoca → peso, una serie per miner. |
| `weights_boxplot_per_epoch.png` | epoca → distribuzione del peso finale (dopo malus e smorzamento) fra i miner. |
| `election_share_distribution.png` | epoca → quota di blocchi vinti per validatore, più torta cumulativa sull'intera run. |
| `concentration_over_time.png` | epoca → HHI / `N_eff` / Gini / entropia: **spettante contro consegnato**. |
| `esg_scores.png` | score ESG certificati per entità (e `esg_scores/miner.png`, `esg_scores/company.png`). |
| `gini_delta_trajectory.png` | epoca → `Gini(pubblicato) − Gini(input)`. Titolo: "il motore amplifica la disuguaglianza dei propri input?". |
| `margin_distribution.png` | margine fra i due delay più veloci (s) → densità. |
| `rho_vs_next_weight.png` | `rho` all'epoca `e` → peso pubblicato all'epoca `e+1`. L'unico canale di retroazione endogeno. |
| `traffic_per_epoch.png` | epoca → transazioni informative: pianificate, inviate, effettivamente on-chain. |
| `p_value_uniformity.png` | p-value del goodness of fit → numero di epoche (istogramma contro l'uniforme attesa sotto H0). |
| `wilson_violation_heatmap.png` | epoca × validatore, rosso dove la quota spettante cade fuori dall'intervallo di Wilson 95 %. |
| `residual_boxplot_by_validator.png` | validatore → distribuzione dei residui `p_hat − p_theoretical`. |
| `delay_recompute_mismatch.png` | epoca → `|delay ricalcolato − delay loggato|` in secondi. **Deve essere ~0.** |
| `rho_feedback_by_validator.png` | Spearman lag-1 per cluster head. |
| `longitudinal_logratio.png` | `log(rapporto quote spettanti i/j)` → `log(rapporto quote osservate i/j)`. Proporzionalità ⇒ pendenza 1, intercetta 0. |
| `sign_test_by_validator.png` | validatore → p del sign test esatto a una coda (la quota si muove col peso?). |
| `sigma_decomposition.png` | sorgente → `sigma` in secondi: di cosa è fatto il bound di inversione. |
| `prop517_gap_by_validator.png` | vincitore → gap standardizzato medio; atteso 1 (Exp(1)). |
| `inversion_bound_vs_observed.png` | bound di Prop. 5.18, simulazione e osservazione a confronto. |
| `phi_over_time.png` | altezza di blocco → `Phi`; il titolo riporta il numero di valori distinti. |
| `malus_action_funnel.png` | funnel delle azioni malicious per kind. |
| `malus_state_trajectory.png` | epoca → `M`, `Psi`, peso grezzo e peso efficace dei miner malicious. |
| `malus_detection_latency.png` | latenza (blocchi / epoche) → ECDF; rilevazione (conferma → primo report) e attivazione. |
| `malus_weight_effect.png` | validatore → variazione relativa del peso efficace, malicious vs onesti. |
| `malus_invariant_audit.png` | epoca × validatore: verde = invariante rispettato, rosso = violato. |

**Figure per entità** (una cartella per famiglia, un `.png` per miner):
`weight_vs_election/`, `weights_over_time/`, `election_share/`, `rho_vs_next_weight/`,
`delay_recompute_mismatch/`, `esg_scores/`.

### 2.7 Etichettatura delle entità

Nei CSV i validatori sono identificati dall'**indirizzo MultiChain** (es.
`1PbfzPSC5Naensz8uRDZq3dCQLonfG85wx283k`), spesso troncato a 12 caratteri nei report Markdown.
I nomi leggibili (`miner-0`, `company-3`, `admin`, `ca-0`) stanno in `addresses.json`,
`analysis/phase1/nodes.csv` e nella tabella `node_table` / `addresses` del `manifest.json`.

**Nel report finale usa sempre la forma `miner-N (1PbfzPSC5Nae…)`**, mai l'indirizzo nudo:
altrimenti il testo è illeggibile. Costruisci la mappa inversa `indirizzo → node_id` all'inizio
del lavoro.

---

## 3. Procedura obbligatoria

### 3.1 Passo 1 — Leggere la configurazione della run

Leggere `<RUN>/manifest.json` (fonte primaria) e `<RUN>/analysis/phase1/config.csv` (i parametri
**effettivi riletti dalla catena**: se i due divergono, vale `config.csv` e la divergenza è essa
stessa un rilievo da segnalare).

Estrarre almeno:

| Voce | Dove |
|---|---|
| nome catena, seed, profilo, regime (`native` / `core`) | `chain_name`, `seed`, `profile_path`, `fabric.backend` |
| topologia e latenza peggiore (solo `core`) | `fabric.topology.*`, `derived.worst_path_delay_ms` |
| numero di nodi per ruolo | `nodes.*` |
| epoche: numero e lunghezza | `epochs.count`, `epochs.length_blocks` |
| altezza finale raggiunta, esito | `final_height`, `status`, `error` |
| **funzione di smorzamento** | `wpoa_params.dump-function` → `none` / `sqrt` / `log` |
| `target-block-time` | `chain_params.target-block-time` |
| **banda del delay** `delta` | `wpoa_params.wpoa-sortition-delta` (⇒ `Delta_max = delta * T_block`) |
| **guadagno della correzione globale** `lambda` | `wpoa_params.wpoa-sortition-lambda` |
| bound del feedback `M` | ricavalo: `M = min(0.5*T_block, T_block*(1-delta)/lambda)` |
| parametri malus | `wpoa-malus-mu`, `wpoa-malus-max`, `*-equiv-points`, `*-delay-points`, `*-selfwrite-points`, `*-badweight-points` |
| **stato del sistema malus** | `effective_chain_params.enable-wpoa-malus` (attivo sempre) **e** `malicious.enabled` (se sono state *iniettate* violazioni) |
| parametri weight engine | `weight-kappa`, `weight-lambda` (= `lambda_w`), `weight-alpha` (**inerte**) |
| `setup-first-blocks` | `effective_chain_params.setup-first-blocks`, `derived.setup_first_blocks_requested` |
| `mining-diversity`, `mining-turnover`, `initial-block-reward`, `first-block-reward` | `chain_params.*` |
| modello di generazione del traffico | `traffic.company_tx_per_epoch_range`, `traffic.miner_gas_returns_per_epoch_range`, `traffic.esg_score_range`, `traffic.restitution_amount_range`, `traffic.event_stream` |
| lookback RANDAO | `wpoa-randao-lookback` |
| piano malicious | `malicious_manifest.json`: `enabled`, `miner_count`, `target_action_rate`, `actions`, `start_epoch`, `stop_epoch`, `malicious_miner_ids` |

**Pesi iniziali per validatore.** ⚠ Non esiste un campo di configurazione "peso iniziale": i
pesi **emergono** dalla pipeline `ESG × tau`. Ricavali da:

- `analysis/phase1/esg_events.csv` → score ESG certificato per ogni miner e azienda;
- `analysis/phase2/epoch_engine.csv` (o `phase1/epoch_cluster_weights.csv`) → `W_k_raw` e
  `w_k_published` alla **prima epoca misurata**;
- `analysis/phase2/epoch_level.csv` → `w_raw_start`, `w_eff_start` per validatore.

Riporta questi valori in `ANALISI.md` come "pesi effettivi alla prima epoca misurata",
**dicendo esplicitamente che sono un esito stocastico e non una configurazione**.

**Tutto questo va nella prima tabella di `ANALISI.md`**, con una colonna "valore" e una colonna
"fonte (file)".

### 3.2 Passo 2 — Costruire le ipotesi attese, caso per caso

Premessa da scrivere nel report: **il sistema è intrinsecamente stocastico** (pesi derivati da
ESG casuali, traffico casuale, VRF, e in regime `core` anche la rete). Nessun giudizio si dà su
singoli blocchi o singoli round: solo su tendenze aggregate, con bande di confidenza e con la
correzione per confronti multipli.

Costruisci le ipotesi in quest'ordine, che è anche l'ordine di dipendenza logica.

---

#### (A) Qualità della randomness — *da verificare per primo, sempre*

Se questi due test falliscono, **ogni metrica a valle è inaffidabile** e va detto in apertura
dell'executive summary.

**A.1 — `E_i ~ Exp(1)`.** La variabile grezza non è in nessuna colonna: **si ricava**. Da
`analysis/phase2/candidate_long.csv`, scartando le righe con `in_setup = True`:

```
E_i = score * weight_effective
```

(equivalentemente `score * effective_weight` da `analysis/phase1/round_scores.csv`).

Verifica:
- media empirica ≈ 1; intervallo di accettazione `1 ± 1.96/sqrt(n)`;
- istogramma sovrapposto alla densità teorica `f(x) = exp(-x)`;
- test di Kolmogorov–Smirnov contro `Exp(1)`: la CDF è `F(x) = 1 - exp(-x)`, e il valore
  critico al 5 % è `D <= 1.358 / sqrt(n)` (equivalentemente `sqrt(n)*D <= 1.358`).

Deviazione della media ben oltre `1 ± 1.96/sqrt(n)`, o `sqrt(n)*D` ben sopra 1.36, indica un
difetto nella VRF, nel seed RANDAO o nella normalizzazione dello score.

**A.2 — `score_norm` del vincitore `~ Uniform(0,1)` (Prop. 5.11).** Raggruppa
`candidate_long.csv` per `height` (escluse le righe `in_setup`) e prendi **il minimo di
`score_norm` in ogni round**. Quel campione deve essere uniforme su `(0,1)`: media ≈ 0,5, KS
contro `F(x) = x` con lo stesso valore critico `1.358/sqrt(n)`.

> **Non usare `is_winner` per questo test.** `is_winner` marca chi ha *minato* il blocco, che
> sotto latenza può non essere l'`argmin` della sortition. Sulle righe `is_winner` la media di
> `score_norm` può risultare molto lontana da 0,5 **senza che ci sia alcun difetto della VRF**:
> è la firma dell'inversione, da leggere nella sezione (E), non qui.

**A.3 — coerenza della normalizzazione.** In `candidate_long.csv`, `score_norm_mismatch` deve
essere nullo (o sotto la tolleranza) su ogni riga: è il confronto fra lo `score_norm` loggato
dal nodo e quello ricalcolato dalla pipeline.

---

#### (B) Correttezza meccanica del delay

`delay_recompute_mismatch_rounds` (in `phase3/wpoa_epoch_tests.csv` e nel controllo critico
`delay_recompute_mismatch_rounds_is_zero` di `consistency_checks.csv`) **deve essere 0** su ogni
epoca, con tolleranza `1,5 ms`. La pipeline ricalcola `D_i` dagli input loggati con la formula
di §1.3(c): un mismatch significa che l'harness e il nodo **sono in disaccordo sul meccanismo
stesso**, ed è un difetto grave, non un rumore statistico. Figura:
`plots/delay_recompute_mismatch.png` e la cartella per miner.

---

#### (C) Quota di blocchi contro peso — il confronto principale

La quota attesa di ciascun validatore è

```
p_theoretical_i = w_eff_i / sum_k w_eff_k
```

dove `w_eff` è `effective_weight_after_malus_and_dumping`, cioè **ciò che l'elezione consuma
davvero**, dopo malus e dopo smorzamento — non il peso pubblicato grezzo. La pipeline lo
pondera per blocco sui round dell'epoca, così un'epoca in cui i pesi si sono mossi è riassunta
da ciò che era in vigore e non da uno snapshot di un estremo.

Ipotesi attese **per caso di smorzamento**:

- **`dump-function = none`** — `g(w) = w`, proporzionalità lineare e **non compressa**. La quota
  di blocchi di ciascun validatore deve avvicinarsi a `w_i / W_tot` misurato sui **pesi
  effettivi nel tempo** (non solo sul peso della prima epoca: il peso evolve per retroazione,
  §1.3(h)). Se esiste un validatore con peso iniziale alto **e** attività/restituzione
  costantemente elevate, la sua quota deve risultare sproporzionatamente alta e crescente (o
  stabile all'estremo superiore): **questo è atteso e corretto, non un difetto**. Va distinto
  da un bug proprio perché è spiegabile dal peso effettivo misurato epoca per epoca.
- **`dump-function = sqrt`** — la quota del validatore più pesante deve risultare **compressa
  rispetto al caso `none`** ma restare superiore a quella degli altri. Ricalcola la quota attesa
  con `g(w) = sqrt(w)` sui pesi reali della run e confrontala con l'osservata. Solo se la run ha
  pesi fortemente disomogenei ci si può aspettare un ordine di grandezza confrontabile con la
  riga `sqrt` della Tabella 5.1 (44,2 % contro 71,4 % nel caso a balena).
- **`dump-function = log`** — compressione ancora più marcata (riga `log` della Tabella 5.1:
  32,5 %). Verificare che **l'ordinamento relativo resti comunque preservato**: chi ha peso più
  alto deve essere eletto più spesso, **mai il contrario**. Un'inversione sistematica di
  ordinamento (non episodica) sarebbe un difetto.
- **Qualsiasi altro valore di `dump-function`** non elencato qui: **non inventare il
  comportamento atteso**. Leggi il codice reale — `src/wpoa/wpoa_selector.cpp`,
  `src/wpoa/private_sortition.{h,cpp}` — per capire cosa fa `g`, e solo dopo commenta i dati.

Come si giudica, concretamente:

1. **Intervalli di Wilson** (`weight_vs_election.md`, `phase3/weight_election_wilson_coverage.csv`,
   `plots/wilson_violation_heatmap.png`). Ad `alpha = 0.05` ci si aspetta che **circa il 5 %**
   degli intervalli **non** contenga la quota spettante, per puro caso. Con `N` coppie
   `(epoca, validatore)`, l'attesa è `0.05*N` violazioni. **Solo un conteggio nettamente sopra
   l'attesa è un rilievo.** Il file `weight_election_pvalue_uniformity.csv` riporta già
   `expected_rejections` e un `binomial_p_value_rejection_count`: usali, non ricontarli a occhio.
2. **Larghezza media dell'intervallo** (`wilson95_width`): è la **risoluzione** della run. Un
   `p_hat` lontano da `p_theoretical` non significa nulla se l'intervallo è largo. Riporta
   sempre la larghezza media accanto al giudizio.
3. **Goodness of fit per epoca** (`gof_p_value`, `gof_reject_alpha05` in `wpoa_epoch_tests.csv`;
   istogramma in `plots/p_value_uniformity.png`). È il test *congiunto* su tutti i validatori
   dell'epoca ed è "il test vero": gli intervalli per validatore dicono *quale* validatore è
   fuori linea, il chi-quadro dice se l'epoca **nel suo complesso** è distinguibile da una
   sortition pesata. Anche qui l'attesa sotto H0 è `0.05 * n_epoche` rigetti; sotto H0 i p-value
   devono essere **uniformi su (0,1)**, ed è esattamente ciò che testano `ks_statistic_vs_uniform`
   e `ks_p_value`.
4. **Quando i pesi si muovono dentro l'epoca** (`share_changes_within_epoch = True`), il test
   multinomiale aggregato verifica un'ipotesi nulla **mai realmente in vigore**: in quel caso la
   colonna da leggere è `gof_mc_round_by_round_p`. Dillo nel report.
5. **Test aggregato su tutta la run** (riga `all`): è molto più potente delle singole epoche. Un
   rigetto sull'aggregato con `MAE_p` piccolo indica un effetto sistematico **piccolo ma reale**
   — tipicamente l'inversione (E) — non un fallimento della sortition.

---

#### (D) Comportamento longitudinale (fra epoche)

File: `phase3/longitudinal.md`, `wpoa_longitudinal_fits.csv`, `wpoa_longitudinal_logratios.csv`,
`wpoa_longitudinal_validators.csv`; figure `longitudinal_logratio.png`,
`sign_test_by_validator.png`.

- **GLM logit su `log(peso)`**: l'ipotesi nulla della sortition pesata è `beta1 = 1`. Leggi
  `beta1`, il suo intervallo di confidenza al 95 % e `beta1_consistent_with_1`, e controlla che
  `converged = True`. `beta1 < 1` significa che la quota osservata risponde al peso **meno** che
  proporzionalmente (compressione in eccesso rispetto al modello); `beta1 > 1`, più che
  proporzionalmente.
- **Regressione dei log-rapporti a coppie**: la proporzionalità implica **pendenza 1 e intercetta
  0**. Riporta anche `pearson_r`: una pendenza vicina a 1 con `r` basso significa che la
  relazione è corretta in media ma sommersa dal rumore campionario, ed è una conclusione diversa
  da una pendenza sbagliata.
- **Sign test per validatore**: "la quota osservata si muove con il peso?". Attenzione ai
  confronti multipli: con 10 validatori, uno o due p sotto 0,05 sono attesi per caso.

> **Interpretazione importante.** `beta1 < 1` e pendenza dei log-rapporti `< 1` sono la firma
> tipica di una **compressione empirica** della sortition: succede quando un rumore indipendente
> dal peso (la latenza, §(E)) mescola l'esito. Prima di attribuirla al meccanismo di selezione,
> **controlla sempre il tasso di inversione**: se è alto, la spiegazione è quella.

---

#### (E) Timer race, margine e inversioni

File: `phase3/timer_race.md`, `wpoa_timer_race.csv`, `wpoa_sigma.csv`, `wpoa_prop517.csv`;
figure `margin_distribution.png`, `sigma_decomposition.png`, `prop517_gap_by_validator.png`,
`inversion_bound_vs_observed.png`.

- **Prop. 5.17** — `mean_standardised_gap` deve valere ≈ 1 per ogni vincitore, con `ks_p` non
  significativo. È un controllo di correttezza del nucleo di sortition, indipendente dalla rete.
- **Margine `G`** — il KS contro `Beta(1,n)` è **uno straw man dichiarato**: assume pesi uniformi
  ed è *atteso* rigettare quando non lo sono. Un `ks_beta_p = 0` **non è un rilievo**; scriverlo
  come tale sarebbe un falso allarme. Il test da leggere è `ks_mc_p`, il KS contro la
  distribuzione esatta simulata della sortition implementata.
- **Decomposizione del rumore** (`wpoa_sigma.csv`):
  - `S1_topology` — dispersione del delay end-to-end fra coppie di validatori sui percorsi
    minimi della mappa emulata. **In regime `native` è riportato come 0 perché è *assente*, non
    perché sia risultato piccolo**: non interpretarlo come "rete perfetta".
  - `S2_scheduler_residual_sd` — quanto la spaziatura effettiva dei blocchi si discosta dal
    proprio delay. È la sorgente **primaria** nella maggior parte delle run.
  - `S2b_inversion_gap` — dispersione del margine sui soli round che hanno effettivamente
    invertito.
  - Il bound di Prop. 5.18 poggia **su `S2` soltanto**: se combinare le due sorgenti sia
    corretto è una decisione di modello non presa, quindi `S1` è riportato *accanto* al bound e
    non dentro.
- **Inversione** — confronta `inversion_observed_rate` con `inversion_mc_prob_gaussian_sigma_S2`
  (la simulazione) e con `inversion_bound` (il maggiorante teorico; un bound **saturato a
  1,0 è vacuo** e va detto, non spacciato per conferma). Un tasso di inversione alto significa
  che il blocco è prodotto spesso da un candidato che **non** era l'`argmin` della sortition:
  è la causa candidata numero uno di una quota osservata che non segue il peso, **pur restando
  la sortition formalmente corretta** (§1.3(f)). Leggi `inversion_rate` anche per epoca in
  `wpoa_epoch_tests.csv` con il suo intervallo di Wilson, per vedere se cresce nel tempo.

---

#### (F) Stabilità del block time e correzione globale `Phi`

File: `phase2/round_level.csv` (`dt_prev_s`, `block_time`, `phi_s`, `scheduler_residual_s`),
`phase1/round_delays.csv` (`feedback_phi`); figura `phi_over_time.png`.

Attesa: la **media dei block time realizzati converge verso `target-block-time`** grazie al
termine di correzione globale. Verifica concreta:

1. Calcola media e deviazione standard di `dt_prev_s` sui round non-setup, e la media per epoca
   (per vedere se c'è deriva).
2. Confronta la media dei delay effettivi `delay_logged_s` con `T_block`. Ricorda che la banda è
   `T_block ± Delta_max + lambda*Phi`.
3. Guarda `phi_over_time.png` e la serie `phi_s`:
   - se `Phi` resta **incollato a `±M`** per lunghi tratti, il feedback è **saturato**: la
     correzione è al massimo e non basta. Calcola `M = min(0.5*T_block, T_block*(1-delta)/lambda)`
     e verifica esplicitamente la saturazione, non a occhio;
   - se `Phi` **oscilla di segno con ampiezza comparabile round dopo round** e la media del block
     time oscilla con lui invece di convergere, il guadagno `lambda` è troppo aggressivo;
   - se `Phi` è quasi sempre piccolo e la media è sul target, il controllo funziona.
4. Se la media si allontana **sistematicamente** dal target, le cause plausibili da elencare
   sono: `lambda` troppo basso, `M` saturato, oppure una sorgente di ritardo esterna al modello
   (latenza di rete, contesa di CPU fra daemon sullo stesso host, I/O).

> **Nota sul controllo `phi_consistent` in `consistency_checks.csv`.** Quel check verifica se
> `Phi` assume **un solo valore** su tutta la run, ed è marcato **non critico**. `Phi` è per
> costruzione una funzione dello stato della catena e quindi **varia nel tempo per design**: un
> `FAIL` con N valori distinti **non è un difetto**. Non riportarlo come punto critico; al
> massimo notalo come "atteso, il check è una sonda di non-regressione tarata su run in cui il
> feedback è spento".

---

#### (G) Evoluzione dei pesi e retroazione inter-epoca

File: `phase2/epoch_engine.csv`, `phase3/weight_engine_epoch.csv`,
`weight_engine_correlations.csv`, `weight_engine_gini.csv`, `weight_engine_gini_summary.csv`;
figure `weights_over_time.png`, `weights_boxplot_per_epoch.png`, `rho_vs_next_weight.png`,
`rho_feedback_by_validator.png`, `gini_delta_trajectory.png`, `esg_scores.png`.

Ipotesi attese:

- **Il peso segue l'attività.** `W_k_raw = ESG_Mk * (miner_activity + companies_contribution_sum)`:
  verifica l'identità direttamente sulle colonne di `epoch_engine.csv`. Deve tornare
  numericamente.
- **Il peso pubblicato segue la formula ricorsiva.** Verifica
  `w_k_final ≈ W_k_raw * (rho_prev * lambda_w + (1 - lambda_w))` per `e >= 2`, e
  `w_k_final ≈ W_k_raw` per la prima epoca. Deve tornare numericamente; se non torna, è un
  difetto del motore di peso.
- **Retroazione `rho → peso successivo`.** È **l'unico canale endogeno**. Leggi
  `weight_engine_correlations.csv` (Spearman lag-1 di `rho(e)` contro il peso pubblicato in
  `e+1`) e `rho_vs_next_weight.png`. Con `lambda_w = 0.5` il fattore moltiplicativo vale
  `0.5*rho + 0.5 ∈ [0.5, 1]`, quindi la retroazione può spostare il peso **al massimo di un
  fattore 2**: un effetto reale ma modesto, **facilmente sommerso dalla varianza di `tau`**, che
  entra moltiplicativamente e varia di epoca in epoca. **Una Spearman piccola e non significativa
  non è di per sé un difetto**; diventa un rilievo solo se `rho` ha varianza apprezzabile e il
  peso pubblicato non ne risente affatto. **Verifica sempre prima che `rho` non sia
  identicamente 0** (caso `initial-block-reward = 0` senza funding, §1.5).
- **I pesi dei validatori più attivi crescono; i meno attivi restano stabili o calano.** Verifica
  la monotonia/plausibilità su `weights_over_time.png` e con una Spearman `epoca → peso` per
  validatore. Ricorda che `tau` è **riestratto ogni epoca**: il peso è atteso *rumoroso*, non
  monotono perfetto.
- **Il motore non deve concentrare oltre i propri input.** `gini_delta = Gini(peso pubblicato) −
  Gini(input ESG×tau)`: una **pendenza positiva** della traiettoria significa che il motore
  amplifica la disuguaglianza dei propri input. Leggi `slope`, `spearman_rho` e `spearman_p` in
  `weight_engine_gini_summary.csv`.
- **Gli score ESG devono essere statici.** Per definizione cambiano solo su ri-certificazione
  esplicita. Se `miner_esg_score` varia fra epoche in `epoch_engine.csv` senza un evento
  corrispondente in `esg_events.csv`, è un difetto.

---

#### (H) Concentrazione del potere di mining

File: `phase2/epoch_concentration.csv`, le colonne `p_theoretical_*` / `p_hat_*` / `delta_*` di
`wpoa_epoch_tests.csv`, la sezione "Concentration" di `report.md`; figura
`concentration_over_time.png`.

Il confronto corretto è sempre **teorico contro osservato nella stessa epoca**, mai osservato
contro un ideale astratto:

- `HHI` osservato contro teorico; `N_eff = 1/HHI` (numero efficace di validatori);
- `Gini` osservato contro teorico;
- soglie di Nakamoto 1/3, 1/2, 2/3 (quanti validatori bastano a superare la soglia).

Con `m` validatori a pesi quasi uguali, `HHI_teorico ≈ 1/m` e `N_eff ≈ m`. L'HHI **osservato**
su una singola epoca è sistematicamente **più alto** del teorico per pura varianza multinomiale
con pochi blocchi per epoca: è un artefatto di campione, non concentrazione reale. Il confronto
affidabile è la riga aggregata su tutta la run, dove il campione è molto più grande. **Dillo
esplicitamente** invece di segnalare un falso allarme per epoca.

---

#### (I) Streak e ripetizioni

File: `phase3/streak.md`, colonne `L_max_*` e `repeat_prob_*` di `wpoa_epoch_tests.csv`.

Domanda: un validatore vince più round consecutivi, o si ripete più spesso, di quanto
produrrebbe un'estrazione pesata? Il riferimento è un **Monte-Carlo costruito sugli stessi pesi
che l'elezione ha usato**, quindi è il confronto giusto (non un'uniforme). Leggi
`L_max_observed` contro `L_max_mc_mean` con `L_max_mc_p_value`, e `repeat_prob_observed` contro
`repeat_prob_mc_mean` con il suo p-value.

Un eccesso **sistematico** di ripetizioni (p-value molto piccoli in quasi tutte le epoche, non
solo in alcune) indica che l'esito dei round **non è indipendente**: candidati per cui una
sorgente di vantaggio persiste da un round al successivo. Cause plausibili da elencare: rumore
di rete persistente per nodo (un nodo sistematicamente più veloce nel propagare vince più spesso
la timer race, §(E)), oppure un seed che non si rinfresca correttamente fra round. Correla
sempre questo risultato con il tasso di inversione prima di concludere.

---

#### (J) Malus

**Distingui due cose diverse e non confonderle mai:**

1. **Il meccanismo di malus è attivo** — `enable-wpoa-malus = true` in `config.csv`. Su queste
   catene è **sempre** attivo: fa parte dello stack completo e non è configurabile.
2. **Sono state iniettate violazioni** — `malicious.enabled` nel `manifest.json` /
   `malicious_manifest.json`.

**Caso J.1 — nessuna violazione iniettata (`malicious.enabled = false`).**

È lo scenario più comune. Attese:

- `phase1/malus_detections.csv`, `phase1/malicious_*.csv`, `phase2/malus_actions.csv`,
  `phase2/malus_detection_events.csv`, `phase3/malus_rate.csv` **vuoti**;
- `M = 0` e `Psi = 1` per **ogni** validatore e **ogni** epoca in `phase2/malus_state.csv` e
  `phase3/malus_invariants.csv`; `invariant_clean_psi_one` vero ovunque;
- `weight_effective == weight_raw * Psi == weight_raw` — cioè **effetto nullo sul comportamento
  onesto**, che è esattamente ciò che il protocollo garantisce;
- **nessuna riduzione di peso o di elezioni** attribuibile al malus deve essere visibile. Se
  osservi un `Psi < 1` o una `M > 0` senza alcun record di malus, è un difetto grave (peso
  penalizzato senza evidenza).
- Le figure `malus_*.png` sono presenti ma vuote/degeneri, e `malus_effectiveness.md` **non
  esiste**. **Dillo esplicitamente, non inventare risultati.**
- Eventuali comportamenti anomali di un validatore osservabili nei log **non devono** riflettersi
  in una riduzione del suo peso o delle sue elezioni: senza evidenza provata on-chain non c'è
  penalità, per costruzione.

**Caso J.2 — violazioni iniettate (`malicious.enabled = true`).**

Attese, nell'ordine del funnel:

1. **Funnel** (`phase2/malus_funnel.csv`, `phase3/malus_funnel.csv`,
   `plots/malus_action_funnel.png`): `opportunities → attempts → sent → confirmed →
   valid_malus → reported`. Il tasso di tentativi deve avvicinarsi a `target_action_rate`
   (un'**opportunità** è un evento contabile per miner malicious per epoca della finestra
   attiva, non un blocco vinto). Solo `selfwrite` e `badweight` sono iniettabili: `delay` ed
   `equiv` nascono dentro il core di consenso e il loader li **rifiuta**.
2. **Rilevazione** (`phase3/malus_detection.csv`): `precision`, `recall`, `f1` per kind. La
   classe positiva sono le azioni **confermate**, perché un'azione mai confermata non può
   portare malus. Un `recall < 1` con un solo detector onesto sull'admin è un limite noto del
   setup, non necessariamente un difetto del protocollo: dillo.
3. **Latenza** (`phase3/malus_latency.csv`, `plots/malus_detection_latency.png`): latenza di
   rilevazione (conferma → primo report, in blocchi) e latenza di **attivazione** (in epoche).
   Ricorda: un record valido riferito all'epoca `e` **agisce da `e+1`**, quindi una latenza di
   attivazione di almeno 1 epoca è **attesa e corretta**.
4. **Effetto sul peso** (`phase2/malus_state.csv`, `plots/malus_state_trajectory.png`,
   `plots/malus_weight_effect.png`, `phase3/malus_weight_effect_matched.csv`): dopo ciascun
   evento di malus la quota di elezioni successive del validatore penalizzato deve **diminuire
   in modo visibile** rispetto al periodo precedente l'evento, **proporzionalmente all'entità
   della penalità applicata al peso** — cioè in proporzione a `Psi = max(0, 1 - M/M_max)`.
   Verifica quantitativamente: confronta la quota nelle epoche con `Psi < 1` contro quella nelle
   epoche con `Psi = 1`, e contro `Psi` stesso. Usa il confronto **appaiato per banda di peso**
   contro i miner onesti (`malus_weight_effect_matched.csv`) per non attribuire al malus una
   differenza che è solo differenza di peso.
5. **Invarianti** (`phase3/malus_invariants.csv`, `plots/malus_invariant_audit.png`): i tre
   invarianti `invariant_psi_in_unit`, `invariant_weff_matches`, `invariant_clean_psi_one`
   devono valere **ovunque**. Un solo rosso è un rilievo.
6. **Reversibilità**: verifica su `malus_state.csv` che `M` decada come `mu^k` nelle epoche senza
   nuove violazioni e che `epochs_to_clear` sia coerente con
   `ceil( ln(M/M_max) / ln(1/mu) )`. Nessuna esclusione deve risultare permanente.
7. **Esclusione a peso nullo**: se `M >= M_max` allora `Psi = 0`, `w_eff = 0` e il validatore
   deve vincere **zero** round (la sortition lo esclude con probabilità 1). Verificalo.

---

#### (K) Correlazione fra guadagno/transazioni e rielezione

Il peso **non dipende direttamente dal volume di transazioni processate né dal guadagno**:
dipende dall'"operosità" aggregata del cluster (`tau` delle aziende e del miner, moltiplicata
per gli ESG) e, indirettamente, dal tasso di restituzione `rho` (§1.3(h)). Una transazione
**non deve** dare un vantaggio diretto e non tracciato nella sortition.

Verifica concreta:

1. Calcola la correlazione fra `n_blocks_won_epoch` e ciascuna di: `earnings_g_k`, `income`,
   `miner_activity`, `companies_contribution_sum`, `W_k_raw`, `w_k_published`
   (tutte in `epoch_engine.csv`).
2. Poi calcola la **correlazione parziale a peso fissato**: dentro gruppi di epoche a peso
   comparabile, oppure correlando i **residui** `p_hat - p_theoretical`
   (`phase3/weight_election_residuals.csv`) con guadagno e volume di transazioni.
3. **Ipotesi attesa:** al punto 1 una correlazione positiva è normale ed è **interamente
   mediata dal peso** (più `tau` → più peso → più blocchi). Al punto 2 la correlazione deve
   **sparire**: i residui rispetto alla quota attesa non devono dipendere da guadagno o volume.
4. Se al punto 2 resta una correlazione significativa, è il segnale di un **canale di influenza
   non documentato** — un bug o una via per cui il traffico entra nell'elezione fuori dal peso.
   Segnalalo come punto critico di massima priorità e indica quale dato ulteriore servirebbe per
   confermarlo.

---

#### (L) Integrità dei dati e dell'esecuzione della run

Da controllare sempre, perché invalidano tutto il resto se falliscono:

- `phase3/consistency_checks.csv` — i check con `critical = yes` **devono** passare tutti. Sono
  controlli di non-regressione (non test di ipotesi): esistono per fallire rumorosamente quando
  la raccolta o la pipeline hanno un bug. Elencali uno per uno con l'esito. Per i `critical = no`
  che falliscono, valuta caso per caso (vedi la nota su `phi_consistent`, §(F)).
- `phase1/verification.csv` — l'esito di `weightverifyweights`: `published` contro `recomputed`,
  con `verdict`. Qualsiasi `verdict` negativo significa un peso pubblicato **non ricalcolabile**,
  cioè esattamente ciò che il malus `BadWeight` sanziona. Va segnalato.
- `phase2/epoch_traffic.csv` — `in_range`: ogni coppia `(epoca, nodo)` completa deve avere un
  conteggio on-chain dentro il range configurato. Prima e ultima epoca sono parziali e vanno
  escluse.
- `manifest.json`: `status`, `error`, `final_height` contro `derived.target_height`. Una run
  troncata ha meno potenza statistica nelle ultime epoche, e va detto.
- `phase1/rpc_errors.csv` — volume e tipo degli errori. Non necessariamente un difetto, ma un
  volume alto vicino a un'epoca anomala è un'ipotesi esplicativa.
- **Ultima epoca**: è quasi sempre **parziale** (la run si ferma a metà epoca). Le sue metriche
  hanno pochi blocchi, intervalli larghi e concentrazione apparentemente più alta. **Trattala
  separatamente e non usarla per concludere una tendenza.**

---

### 3.3 Passo 3 — Catalogare ed esaminare ogni file e ogni grafico

Enumera il contenuto reale di `<RUN>/analysis/` (`phase1/`, `phase2/`, `phase3/`, `plots/` e
tutte le sottocartelle per entità). Per **ciascun file effettivamente presente**:

1. **Aprilo.** I `.md` vanno letti; i `.csv` vanno aperti e riassunti numericamente (media,
   mediana, min, max, conteggi, trend per epoca — non "sembra"); i `.png` vanno **guardati** con
   lo strumento di lettura immagini, non solo citati.
2. **Descrivi l'andamento effettivo**, con numeri: valori, percentuali, pendenze, p-value.
3. **Confrontalo con l'ipotesi attesa** formulata al passo §3.2, nominando il punto (A)…(L)
   corrispondente.
4. **Esprimi un giudizio esplicito**, scegliendo una delle tre etichette:
   - **conforme** — punto di forza. Indica il **grado di aderenza** osservato, con un numero.
     Esempio della forma richiesta: *"la media empirica di `E_i` è 0,9992 contro 1 atteso, entro
     lo 0,1 %, e il KS dà `sqrt(n)*D = 0,79` contro un critico di 1,36 al 5 %"*.
   - **lieve scostamento** — differenza presente ma compatibile con la varianza campionaria.
     Quantificala e spiega perché la ritieni compatibile.
   - **scostamento significativo da indagare** — punto critico. Riporta **l'entità** dello
     scostamento e le **cause plausibili** date le variabili in gioco: casualità intrinseca del
     campione, configurazione specifica della run, latenza di rete, dimensione campionaria
     insufficiente per un test affidabile, oppure bug potenziale (e in quale componente).

**Regole anti-falso-allarme, da applicare sempre:**

- Non giudicare mai su un singolo round, un singolo blocco o una singola epoca. Usa intervalli o
  bande di confidenza, e se più run confrontabili sono disponibili nella stessa cartella
  `results/` usale come riferimento.
- Correggi per confronti multipli: con `N` test ad `alpha = 0.05`, `0.05*N` rigetti sono
  **attesi**. La pipeline fornisce già `expected_rejections`: usalo.
- Le epoche `in_setup = True` vanno **escluse** da ogni test: lì gira il round robin nativo.
- L'ultima epoca è tipicamente parziale: trattala a parte.
- Un intervallo largo non è un risultato: dichiara sempre la risoluzione (`wilson95_width`
  medio).
- Un test etichettato **straw man** nella pipeline (il KS contro `Beta(1,n)`) che rigetta **non è
  un rilievo**.
- `sigma_S1 = 0` in regime `native` significa **assente**, non "piccolo".
- Un bound saturato a 1,0 è **vacuo**, non una conferma.
- `phi_consistent = FAIL` non è un difetto (§(F)).
- `weight-alpha` è inerte: non commentarlo come se agisse.

**Se un file o una metrica attesa non esiste in quella run, scrivilo esplicitamente** nella
sezione corrispondente (es. *"`malus_effectiveness.md` non è presente: l'esperimento malicious
non è stato eseguito in questa run"*), **e non inventare risultati**.

### 3.4 Passo 4 — Sintesi complessiva

Valuta se il sistema, **nel suo insieme**, si comporta come atteso dal modello teorico, con un
giudizio esplicito e argomentato con numeri su ciascuno di questi cinque assi:

| Asse | Domanda | Evidenza principale |
|---|---|---|
| **Affidabilità della sortition** | L'elezione è proporzionale al peso **effettivo** (dopo malus e smorzamento)? | copertura di Wilson, GoF per epoca e aggregato, GLM `beta1`, log-rapporti |
| **Qualità della randomness (VRF)** | `E_i ~ Exp(1)`? `score_norm` dell'argmin `~ U(0,1)`? Prop. 5.17 con media 1? | §3.2(A), `wpoa_prop517.csv` |
| **Efficacia dello smorzamento** | Se attivo, comprime il vantaggio dei pesi grandi **preservando l'ordinamento**? Se i pesi sono omogenei, l'effetto nullo è atteso? | quote ricalcolate con `g` sui pesi reali, concentrazione |
| **Efficacia del malus** | Se iniettato: rilevato, applicato con la latenza giusta, proporzionale a `Psi`, reversibile? Se non iniettato: effetto **esattamente nullo**? | §3.2(J) |
| **Stabilità del block time** | La media converge a `target-block-time`? `Phi` è saturato o oscillante? | §3.2(F) |

---

## 4. Output richiesto

Scrivi **su disco** il file `<RUN>/analysis/ANALISI.md`, in italiano, con **esattamente** questa
struttura:

```markdown
# Analisi della run <nome-cartella>

Run: `<percorso relativo alla root del repo>`
Timestamp UTC della run: <estratto dal nome cartella>
Catena: `<chain_name>` — profilo: `<profile_path>` — regime: <native|core>
Analisi prodotta il: <data>

## 1. Configurazione della run

<tabella: parametro | valore | fonte (file) — tutti i parametri del passo 3.1>

## 2. Executive summary

<5-10 righe. Il sistema funziona come atteso? Dove sì e dove no, una frase per punto,
ciascuna con un numero a supporto. Se un test di randomness è fallito, dirlo qui in
apertura perché invalida tutto il resto.>

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)
### 3.2 Correttezza meccanica del delay
### 3.3 Quota di blocchi contro peso
### 3.4 Comportamento longitudinale
### 3.5 Timer race, margine e inversioni
### 3.6 Stabilità del block time e correzione globale
### 3.7 Evoluzione dei pesi e retroazione inter-epoca
### 3.8 Concentrazione
### 3.9 Streak e ripetizioni
### 3.10 Malus
### 3.11 Correlazione guadagno/transazioni e rielezione
### 3.12 Integrità della run e controlli di consistenza

<Per OGNI grafico e OGNI statistica reale trovata, una voce con:
 - **File**: percorso relativo (es. `analysis/plots/margin_distribution.png`)
 - **Cosa misura**: una o due frasi
 - **Osservato**: valore o andamento, con numeri
 - **Atteso**: valore o andamento teorico, con la formula o la soglia di riferimento
 - **Giudizio**: conforme | lieve scostamento | scostamento significativo da indagare
   + motivazione quantitativa>

## 4. Punti di forza

<elenco puntato: i comportamenti che confermano più chiaramente la correttezza del
sistema, ciascuno con numeri/percentuali a supporto>

## 5. Punti critici / da approfondire

<elenco puntato: ciò che si discosta dall'atteso, con
 - entità dello scostamento (numeri)
 - ipotesi sulla causa
 - quale ulteriore dato, grafico o run servirebbe per confermare o escludere l'ipotesi>

## 6. Conclusione

<sintesi finale sullo stato di salute del meccanismo wPoA in questa run, sui cinque assi
della tabella del passo 3.4>
```

Regole di forma:

- Ogni riferimento a file usa il **percorso relativo alla cartella di run** e la sintassi di link
  Markdown, così è cliccabile: `[analysis/plots/margin_distribution.png](analysis/plots/margin_distribution.png)`.
- I validatori si citano come `miner-N (1PbfzPSC5Nae…)`, mai come indirizzo nudo.
- Ogni giudizio porta almeno un numero. Nessuna frase del tipo "il comportamento sembra
  corretto" senza una cifra accanto.

---

## 5. Istruzioni operative finali — da rileggere a ogni esecuzione

1. **Non assumere nulla che non sia verificabile nei file reali della run indicata.** Ogni
   affermazione del report deve poter essere ricondotta a un file, a una colonna e a un valore.
2. **Se un file o una metrica attesa non esiste in quella run, dillo esplicitamente** invece di
   inventare risultati. "`malus_effectiveness.md` non è presente perché l'esperimento malicious
   non è stato eseguito" è una risposta corretta; un paragrafo di analisi del malus in una run
   senza malus non lo è.
3. **Se la run ha una configurazione non prevista qui** — una `dump-function` diversa da
   `none`/`sqrt`/`log`, un `lambda = 0`, un `mining-diversity > 0`, un regime o un profilo nuovo
   — **leggi il codice reale prima di commentare i dati**. Riferimenti:
   `src/wpoa/wpoa_selector.cpp` e `src/wpoa/private_sortition.{h,cpp}` (smorzamento, score,
   delay, `Phi`), `src/wpoa/malus_registry.cpp` (malus), `test/config/schema.md` (formato e
   default del profilo), `test/analysis/pipeline/` (cosa calcola esattamente ogni metrica),
   `test/plotting/generate_plots.py` (cosa disegna esattamente ogni figura),
   `test/README.md` (architettura dell'harness). **Il codice vince sempre su questo documento.**
4. **Il giudizio è sempre ancorato a numeri e percentuali estratti dai dati, mai generico.**
5. **Scrivi sempre il file `<RUN>/analysis/ANALISI.md` come output finale**, non limitarti a
   mostrare il testo in chat.
6. **Prima di dichiarare un difetto, passa dalla lista anti-falso-allarme di §3.3.** La maggior
   parte degli scostamenti apparenti in queste run ha tre spiegazioni ordinarie, in quest'ordine
   di frequenza: varianza campionaria con pochi blocchi per epoca; confronti multipli non
   corretti; inversione della timer race dovuta alla latenza, che lascia la sortition
   formalmente corretta ma ne comprime l'aderenza empirica.
