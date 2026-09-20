# PROMPT — Analisi GLOBALE e incrementale degli esperimenti wPoA

> **Questo file è un prompt operativo, non documentazione.** Chi lo legge è una sessione di
> Claude Code a cui è stato dato *soltanto* questo file. Non c'è una tesi allegata, non c'è
> contesto di sessioni precedenti, non c'è un elenco di run fornito dall'utente.
>
> **Output finale obbligatorio:** il file `test/results/ANALISI-WPOA.md`, scritto su disco,
> **aggiornato in modo incrementale** se già esiste.
>
> Questo prompt **non** analizza una singola run: aggrega e confronta run già analizzate
> individualmente. L'analisi di singola run è compito di `PROMPT_ANALISI_WPOA.md`, nella
> radice del repository.

---

## 0. Dove sono le cose, concretamente

| Cosa | Percorso reale |
|---|---|
| radice degli esperimenti | **`test/results/`** (non `results/`) |
| una singola run | `test/results/run-wpoa-<name>-<UTC>/` |
| analisi di singola run | `test/results/run-wpoa-<name>-<UTC>/analysis/ANALISI.md` |
| **output di questo prompt** | **`test/results/ANALISI-WPOA.md`** |
| prompt di singola run | `PROMPT_ANALISI_WPOA.md` (radice del repo) |
| pipeline di analisi | `test/analysis/pipeline/phase{1,2,3}_*.py`, `test/analysis/pipeline/stat/` |
| generatore di figure | `test/plotting/generate_plots.py` |
| profili degli esperimenti | `test/config/profiles/native/`, `test/config/profiles/core/` |
| formato dei profili | `test/config/schema.md` |
| sorgenti del protocollo | `src/wpoa/` (`wpoa_selector.h`, `private_sortition.{h,cpp}`, `malus_registry.cpp`) |

Due avvertenze operative:

1. **`test/results/.gitignore` ignora tutto** (`*`, con sole eccezioni `.gitignore` e `.gitkeep`).
   Anche `ANALISI-WPOA.md` sarà quindi **non versionato**. È corretto così: il report vive con le
   prove che lo sostengono. Se serve versionarlo, va aggiunta una riga `!ANALISI-WPOA.md` a quel
   `.gitignore` — **non farlo di iniziativa**, al massimo segnalalo.
2. **Alcune cartelle di run possono essere di proprietà `root`** (create dal container di
   emulazione) e non scrivibili dall'utente. Questo riguarda i file *dentro* la run; il report
   globale sta in `test/results/`, che è dell'utente, quindi normalmente si scrive senza problemi.
   Se incontri un `EACCES`, dillo e proponi `sudo chown`, non aggirarlo silenziosamente.

---

## 1. Ruolo e contesto: cos'è il sistema e cosa prevede la teoria

### 1.1 In una frase

wPoA è un fork di **MultiChain** (blockchain permissioned UTXO derivata da Bitcoin Core) in cui la
Proof of Authority nativa — un round robin egalitario fra miner autorizzati — è sostituita da una
**weighted private sortition**: a ogni round ciascun validatore calcola localmente, tramite una VRF
su un seed RANDAO pubblico, uno score segreto; la trasformazione di **Efraimidis–Spirakis** rende
la probabilità di vittoria proporzionale al peso; lo score è poi mappato in modo monotono su un
**delay di scheduling**, cosicché la timer race locale già presente in MultiChain elegga il
vincitore della sortition senza introdurre alcun sotto-protocollo di rivelazione.

Il peso non è statico: è prodotto da un **weight engine** che aggrega score ESG certificati e
partecipazione on-chain a livello di *cluster* (un miner più le aziende sue clienti), con
**retroazione inter-epoca**. A valle, il peso è corretto da un **malus comportamentale** e
**smorzato** da una funzione concava opzionale prima di entrare nella sortition.

### 1.2 Lo stack

```
L0  VRF nativa su secp256k1 (prova + verifica, unicità verificabile)
L1  Registro dei pesi         -> stream `wpoa-weights`
    Registro dei malus        -> stream `wpoa-weights-malus` (scrittura universale)
L2  Accumulatore RANDAO       -> beacon pubblico, seed del round
L3  Sortition privata pesata  -> score_i = E_i / w_eff_i, argmin vince
L4  Delay / timer race        -> D_i = T_block + Delta_max*(2*score_norm_i - 1) + lambda*Phi
```

### 1.3 Le formule, per intero

#### (a) Elezione pesata — *Teorema 5.3 (Efraimidis–Spirakis)*

```
E_i     = -ln(u_i)              con u_i ~ Uniform(0,1) dalla VRF  ->  E_i ~ Exp(1), i.i.d., E[E_i] = 1
score_i = E_i / w_i
Pr[ argmin_i score_i = j ] = w_j / sum_k w_k          (esatto, non asintotico)
```

Estensione a pesi non negativi: con `score_i = +infinito` per `w_i = 0`, la formula resta valida e
quei validatori vincono con probabilità 0, purché almeno un candidato abbia peso positivo.

> **La variabile `E_i` è il test di sanità universale.** La sua distribuzione `Exp(1)` con media 1
> non dipende da pesi, smorzamento, malus, traffico, numero di candidati, topologia o regime. Se
> fallisce anche in **una sola run**, è un problema strutturale della generazione di randomness e
> va trattato con priorità massima, perché mette in dubbio ogni metrica a valle di **tutte** le run.

#### (b) Smorzamento del peso — *Sez. 5.8*

Funzione `g: R>=0 -> R>=0` monotona crescente e concava. Peso efficace `w_tilde_i = g(w_i)`:

```
Pr[ i eletto ] = g(w_i) / sum_k g(w_k)
```

| `dump-function` | `g(w)` | Effetto |
|---|---|---|
| `none` | `g(w) = w` | proporzionalità lineare, **nessuna compressione** |
| `sqrt` | `g(w) = sqrt(w)` | compressione moderata, vantaggio sub-lineare ma significativo |
| `log` | `g(w) = ln(1+w)` | compressione aggressiva, forte livellamento |

Proprietà da usare nel confronto trasversale:

- **L'ordinamento non cambia mai**: `g` è crescente, quindi chi ha peso maggiore resta più
  probabile. Un'inversione **sistematica** di ordinamento è un difetto; una episodica è rumore.
- **Su pesi omogenei lo smorzamento è a effetto nullo.** Se `w_i == w` per ogni `i`, la
  distribuzione torna uniforme, identica al caso `none`. Più i pesi sono ravvicinati, meno lo
  smorzamento si vede. **È il caso più frequente in queste run** e non va scambiato per un difetto.
- Compressione del vantaggio: per `w_i > w_j > 0` vale `g(w_i)/g(w_j) <= w_i/w_j`.

**Tabella 5.1 — riferimento quantitativo** (una "balena" con `w = 100` contro 4 pari con `w = 10`;
peso totale 140):

| Configurazione | P(balena) | P(ciascun piccolo) | Quota balena | Rapporto balena/piccolo |
|---|---:|---:|---:|---:|
| `none` (nessuno smorzamento) | 0,714 | 0,071 | **71,4 %** | 10,0 |
| `sqrt` — `g(w)=√w` | 0,442 | 0,140 | **44,2 %** | 3,2 |
| `log` — `g(w)=ln(1+w)` | 0,325 | 0,169 | **32,5 %** | 1,9 |

**Ordine di compressione atteso: `none` più concentrato > `sqrt` intermedio > `log` più livellato.**
È questo ordinamento — non i numeri assoluti — che il confronto trasversale deve verificare, perché
i pesi reali di ogni run sono diversi da quelli della tabella.

#### (c) Score normalizzato e delay — *Sez. 5.9*

Con `W_tot` = somma dei pesi **efficaci** dei candidati eleggibili del round:

```
score_norm_i = 1 - exp( -W_tot * score_i )   in (0,1)
d_i          = Delta_max * ( 2 * score_norm_i - 1 )        [psi(x) = 2x - 1]
D_i          = T_block + d_i + lambda * Phi
Delta_max    = delta * T_block,   delta in (0,1)
```

`T_block` = `target-block-time`, `delta` = `wpoa-sortition-delta`, `lambda` = `wpoa-sortition-lambda`.
Poiché `x -> 1 - exp(-W_tot*x)` è strettamente crescente,
`argmin_i D_i = argmin_i score_norm_i = argmin_i score_i`: **il vincitore della timer race coincide
con il vincitore della sortition**, e la probabilità di elezione resta quella del Teorema 5.3.

**Proposizione 5.11**: lo `score_norm` del **vincitore della sortition** (l'`argmin`, non
necessariamente chi ha minato) è `~ Uniform(0,1)`, esattamente, indipendentemente dal numero di
candidati e dai pesi.

#### (d) Correzione globale `Phi` — *Def. 5.12–5.14, Cor. 5.15*

`Phi` è additivo e **comune a tutti i candidati del round**: si elide in ogni differenza fra timer,
quindi **non altera l'ordinamento né le probabilità**. Implementazione reale
(`src/wpoa/private_sortition.cpp`, `WPoASortitionFeedback`):

```
mean_spacing = ( time(tip) - time(tip - 12) ) / 12        finestra fissa di 12 blocchi
Phi          = clip( T_block - mean_spacing , -M , +M )
M            = min( 0.5 * T_block , M* )      con  M* = T_block * (1 - delta) / lambda
```

Vincolo di ammissibilità del timer: `Delta_max <= T_block - lambda*M`. Con `lambda = 0` la
correzione è disattivata. Atteso: la media dei block time converge a `T_block`.

#### (e) Malus comportamentale — *Sez. 5.10.3, 7.8*

Stream `wpoa-weights-malus`, a scrittura universale; ogni nodo applica un predicato di validità
locale e i nodi onesti concordano sempre. Quattro tipi:

| `kind` | Famiglia | Prova contro |
|---|---|---|
| `Equiv` | comportamentale | due blocchi distinti alla stessa altezza con VRF valida sullo stesso seed |
| `Delay` | comportamentale | blocco con timestamp anteriore al proprio `D_i` |
| `SelfWrite` | integrità dati | transazione firmata da `j` che pubblica un record con `addr != j` |
| `BadWeight` | integrità dati | record `wpoa-weights` firmato dal soggetto corretto ma non ricalcolabile |

```
M_i^(e)   = mu * M_i^(e-1) + somma dei p(kind) dei record VALIDI dell'epoca e,   M_i^(0) = 0
Psi_i^(e) = max( 0 , 1 - M_i^(e) / M_max )   in [0,1]
w_eff_i   = w_i * Psi_i^(e)
```

Parametri: `wpoa-malus-mu`, `wpoa-malus-max`, `wpoa-malus-{equiv,delay,selfwrite,badweight}-points`.
Ordinamento inteso: `p(Equiv) > p(BadWeight) > p(SelfWrite) > p(Delay)`.

Proprietà da verificare nel confronto:

- `M = 0` ⇒ `Psi = 1` ⇒ **effetto nullo sul comportamento onesto** (invariante duro, deve valere in
  ogni run senza violazioni iniettate);
- `Psi` sempre in `[0,1]`, `w_eff = w · Psi` (invarianti duri);
- **latenza di applicazione**: un record valido riferito all'epoca `e` agisce da `e+1`;
- **reversibilità**: senza nuove violazioni `M_i^(e0+k) = mu^k · M_i^(e0)`, quindi il validatore
  rientra dopo `k* = ceil( ln(M/M_max) / ln(1/mu) )` epoche. Nessun ban permanente.

#### (f) Calcolo del peso (weight engine) — *Cap. 6*

```
c_i^(e)  = ESG_i * tau_i^(e) / kappa                          contributo aziendale pesato
W_k^(e)  = ESG_Mk * ( tau_Mk^(e) + somma_{i in C_k} c_i^(e) )  peso GREZZO del cluster

g_k^(e)     = Entrate_k^(e) - Uscite_k^(e)      (escluse le restituzioni dell'epoca)
saldo_k^(e) = saldo_k^(e-1) + g_k^(e),   saldo_k^(0) = 0
R_k^(e)     = trasferimenti confermati dal miner k al treasury nell'epoca e
rho_k^(e)   = R_k^(e) / saldo_k^(e)   in [0,1]                 TASSO DI RESTITUZIONE

w_k^(1) = W_k^(1)
w_k^(e) = W_k^(e) * [ rho_k^(e-1) * lambda_w + (1 - lambda_w) ]      per e >= 2
```

`lambda_w` = parametro di catena `weight-lambda`, in `[0,1)`. Osservazioni decisive:

- Il peso cresce con **attività** (`tau`) e **ESG**, non direttamente col guadagno; il guadagno
  entra solo al denominatore di `rho`.
- `rho` è **l'unico canale endogeno** di retroazione. Con `lambda_w = 0.5` il fattore
  `rho·lambda_w + (1-lambda_w)` vive in `[0.5, 1.0]`: al massimo un fattore 2.
- `weight-alpha` è **inerte**: validato e mai letto dal binario. **Non commentarlo mai come se
  agisse.**

Ordine di applicazione: `w_k` (engine) → `× Psi` (malus) → `g(·)` (dumping) → `w_eff` per la sortition.

### 1.4 Sensibilità della timer race alla latenza di rete — *Sez. 5.9.5* **(il cuore del confronto native/core)**

Questa è la sezione che giustifica l'esistenza dei due regimi. Va riportata per intero perché è il
metro con cui giudicare se lo scostamento osservato in `core` è *atteso* o *anomalo*.

#### Margine della timer race

```
G^(n+1) = D_(2)^(n+1) - D_(1)^(n+1)  >= 0
```

Poiché `T_block + lambda*Phi` è comune a tutti i candidati, **si elide**: `G` è identico calcolato
sui `D_i` o sui soli `d_i`.

#### Proposizione 5.17 — margine esatto fra vincitore e secondo *(esatta, nessuna approssimazione)*

Condizionatamente al vincitore `i*`:

```
score_(2) - score_(1)  ~  Exp( W_tot - w_eff_{i*} )
E[ score_(2) - score_(1) | i* ] = 1 / ( W_tot - w_eff_{i*} )
```

Equivalentemente il **gap standardizzato** `(score_(2) - score_(1)) * (W_tot - w_eff_{i*})` è
`Exp(1)`, con **media attesa 1**. Se il vincitore non concentra una frazione dominante del peso, il
peso residuo è alto e il margine si comprime; se la concentra, il margine si allarga.

#### Proposizione 5.18 — impatto della latenza sull'esito

Modellando la latenza di propagazione come rumore additivo `L_i`, **indipendente per candidato, a
media nulla e deviazione standard `sigma`** (jitter standard: la rete non favorisce nessuno
sistematicamente), il tempo osservato per il candidato `i` è `D_i + L_i`. Sotto l'assunzione che gli
`score_norm` siano approssimabili come i.i.d. uniformi (ragionevole **solo a pesi non concentrati**;
da tenere distinta dal risultato esatto di Prop. 5.11, che riguarda il solo vincitore):

```
E[G] = 2 * Delta_max / (n + 1)
G = 2 * Delta_max * X,   X ~ Beta(1, n),   Pr[G < t] = 1 - (1 - t/(2*Delta_max))^n <= n*t/(2*Delta_max)

Pr[ vincitore osservato != vincitore designato ]  <=  2*sigma^2 / t^2  +  n*t / (2*Delta_max)
                                                  =   O( ( n * sigma / Delta_max )^(2/3) )
```

Interpretazione, che è esattamente il predittore da usare nel confronto native/core:

- la probabilità di **inversione** (vincitore osservato ≠ `argmin score`) **cresce** con il numero
  di candidati `n` e con il rumore `sigma`, e **decresce** con l'ampiezza di banda `Delta_max`;
- l'esponente è `2/3` su `sigma`, non su `sigma²`: `n·sigma/Delta_max` è adimensionale;
- vincolo di dimensionamento pratico: `Delta_max >~ n * sigma * eps^(-3/2)` per tenere l'inversione
  sotto `eps`. Tira in direzione **opposta** al vincolo di ammissibilità
  `Delta_max <= T_block - lambda*M`: l'esistenza di un `Delta_max` che soddisfi entrambi **non è
  garantita a priori** e va verificata numericamente.

#### Cosa ci si aspetta in `native` e cosa in `core`

| | **native** | **core** |
|---|---|---|
| rete | nessuna: un solo namespace, loopback, nessun netem | una namespace per sito, delay/jitter/perdita per link |
| `sigma` di propagazione | **assente per costruzione** (non "piccola") | misurabile dalla mappa |
| inversione attesa | ~0 nel caso ideale: senza rumore l'`argmin` vince sempre | > 0, e **quantificabile** con Prop. 5.18 |
| ruolo | **baseline di correttezza**: uno scostamento ha una sola spiegazione candidata | la rete diventa un soggetto, non un disturbo |

**Il confronto corretto è questo**: si misura `sigma` in `core`, si inserisce in Prop. 5.18 con `n`
e `Delta_max` reali della run, si ottiene un bound, e si confronta con l'inversione osservata. Tre
esiti possibili:

1. inversione `core` > inversione `native`, e **entro** il bound → **coerente con la teoria**, la
   latenza fa quello che la tesi prevede;
2. inversione `core` ≈ inversione `native` → **la rete non è la causa**: la sorgente del rumore è
   locale al nodo, e il bound non c'entra;
3. inversione `core` **sopra** il bound, o inversione alta **anche in `native`** → **anomalia**:
   o un bug, o parametri di rete non realistici, o una sorgente di rumore non modellata.

> ⛔ **Prerequisito: `inversion_*_public` non può rispondere a nessuna delle tre domande sopra.**
> Il confronto che quella colonna calcola è fra il vincitore osservato e l'`argmin` della forma
> **pubblica** del punteggio, `HMAC-SHA256(seed, indirizzo)`, che è l'unica ricomputabile da
> `wpoalistdelays` per un validatore di cui il nodo non ha la chiave segreta. Sotto sortition
> privata i timer sono armati da una VRF sotto la chiave di *ciascun* proponente: le due grandezze
> sono variabili aleatorie **indipendenti**, quindi l'inversione così definita vale `1 - 1/n` per
> costruzione, sempre, sia che il meccanismo funzioni sia che sia rotto. Misurato su
> `core-intercontinental`: 0,9103 contro 0,90 previsti, con `winner_rank_by_delay_public` piatto
> (media 5,495 su 1..10) e `corr(dt_prev, delay_public)` = 0,014. Anche `sigma_S2` = 3,47 s non è
> un residuo di scheduler: è la deviazione standard della differenza fra due estrazioni
> indipendenti dalla stessa banda.
>
> Le tre alternative (coerente / rete non è la causa / anomalia) vanno quindi decise sui test
> **Q1 e Q2** in cima a `timer_race.md`, costruiti sul punteggio **vero** del vincitore ricomputato
> dal reveal VRF del suo blocco (`block_sortition.csv`, colonne `_true`):
> `true_corr_dt_delay` (~1 se il ritardo è rispettato, ~0 se disaccoppiato) e
> `true_score_norm_mean` (0,5 se vince l'argmin, ~0,909 se vince un validatore qualsiasi).
> Vedi la regola 10 di §9 della GUIDA.

> ⚠ **Due punti di riferimento numerici da tenere sempre a mente**, una volta che si disponga di un
> tasso di inversione costruito sul punteggio vero.
> - Se il produttore del blocco fosse scelto **uniformemente a caso** fra gli `n` candidati,
>   l'inversione varrebbe esattamente `1 - 1/n` (0,900 per n = 10). Un'inversione osservata che
>   coincide con `1 - 1/n` non è "rumore forte": è **indipendenza totale** fra sortition e
>   produzione, che è un'affermazione qualitativamente diversa e molto più grave.
> - Un bound di Prop. 5.18 pari a **1,0 è vacuo** e non conferma nulla. Se il bound satura, il
>   confronto utile è contro la **probabilità simulata**
>   (`inversion_mc_prob_gaussian_sigma_S2_public`), non contro il bound.

#### Sicurezza sotto jitter — *Sez. 5.6 e 5.11.3*

La sortition privata esiste per rendere **imprevedibile il proposer**: nel modello pubblico di base
(walk cumulativo sul seed) l'identità del proposer di `n+1` è calcolabile da chiunque un intero
intervallo di blocco prima, esponendolo a DDoS mirato. Il contesto permissioned **mitiga ma non
elimina** la minaccia (un validatore fidato non è immune a attacchi di rete; osservatori esterni
possono comunque inviare pacchetti; un validatore compromesso trae lo stesso vantaggio).

Ai fini del confronto native/core: il jitter **non deve** introdurre problemi di *safety*. Sotto
jitter ci si aspetta più **fork transitorie**, non doppie elezioni valide né blocchi accettati
fuori dalla barra temporale.

> ⚠ **Le fork transitorie non sono risolte da un tie-break sullo score.** Nel codice non esiste
> alcuna regola di fork-choice basata sul punteggio: `CBlockIndexWorkComparator`
> (`src/core/main.cpp:160-193`) ordina per `nChainWork`, poi per la clausola MultiChain
> `nCanMine`/`nHeightMinedByMe`, poi per `nSequenceId` — **first-seen**, locale al nodo — e infine
> per indirizzo del puntatore. Lo score interviene solo prima: lato miner come ritardo, lato
> validatore come barra temporale per-blocco (`WPoASortitionVerifyProposer`), che è un test di
> ammissibilità isolato e non un confronto fra candidati concorrenti. Una fork si chiude quando un
> ramo si allunga, non quando qualcuno confronta due punteggi. L'unico tie-break "per score" nel
> codice è quello lessicografico dentro `SelectProposer` (`wpoa_selector.h:236-252`), che
> appartiene al percorso pubblico Fase 2/3b e non è attivo quando governa la sortition privata.

Da verificare in ogni run `core`:

- nessuna equivocazione (`Equiv`) registrata;
- nessuna violazione di delay (`Delay`) registrata;
- l'altezza finale della catena coerente con il numero di blocchi misurati (fork risolte, non
  accumulate).

### 1.5 Contesto sperimentale: cosa è casuale, e perché una run non basta

Il sistema è **stocastico su più livelli indipendenti**, tutti derivati dal `seed` del profilo ma
comunque campioni:

1. **score ESG** estratti in `esg_score_range` (tipicamente `[1, 100]`) per ogni miner e azienda;
2. **assegnazione azienda → cluster**, se non fissata nel profilo;
3. **traffico**: tx per azienda per epoca, numero e importo delle restituzioni per miner;
4. **VRF**: lo score di ogni candidato a ogni round;
5. **rete** (solo `core`): delay, jitter, perdita per link.

**Conseguenza per il report globale**: una proprietà osservata in **una** run può essere un
artefatto del campione. Ogni affermazione del report deve dichiarare **su quante run indipendenti
si basa**, e quel giudizio va ricalcolato — rafforzato o indebolito — a ogni nuova esecuzione.

**Conseguenza pratica ricorrente**: poiché i pesi nascono da `ESG × tau` con ESG uniforme, i pesi
dei cluster risultano quasi sempre **dello stesso ordine** (tipicamente entro un fattore 2–8 fra
minimo e massimo). **Non c'è quasi mai una balena.** Ne segue che lo smorzamento produce effetti
piccoli, e che la Tabella 5.1 va usata per l'**ordine di compressione**, non come previsione
numerica.

### 1.6 Parametri che possono mascherare wPoA

- `mining-diversity`: regola nativa di spacing. **Se > 0 può diventare vincolante e far collassare
  la distribuzione osservata sul round robin nativo.** Nei profili della campagna è `0.0`. Se una
  run lo ha `> 0`, le sue metriche di quota **non sono comparabili** con le altre: escludila dal
  confronto per smorzamento e dillo.
- `setup-first-blocks`: sotto quell'altezza gira il round robin nativo. Le epoche relative sono
  marcate `in_setup` e già escluse dalla pipeline.
- `initial-block-reward = 0`: nessuna ricompensa da mining. Se i miner non ricevono GAS, `rho = 0`
  per tutti e **il canale di retroazione inter-epoca è inerte**. Verificalo prima di concludere
  qualcosa sulla retroazione.
- `mining-turnover`: euristica locale nativa, senza effetto sul meccanismo misurato.

---

## 2. Input atteso

L'utente esegue questo prompt **ogni volta che ha aggiunto uno o più esperimenti** a
`test/results/`, **senza dire quali sono nuovi**. Scoprirlo è compito tuo:

- l'elenco delle run è quello **realmente presente su disco**, mai un elenco fisso o ricordato;
- lo stato di ciò che è già stato incorporato sta nella **tabella di tracciamento** dentro
  `test/results/ANALISI-WPOA.md`, se quel file esiste;
- se il file non esiste, **tutte** le run trovate sono nuove.

L'utente può anche non passare alcun argomento: il prompt è autosufficiente.

---

## 3. Procedura obbligatoria

### 3.1 Passo 1 — Scoperta e inventario delle run

```bash
ls -d test/results/run-wpoa-*/ 2>/dev/null
```

Per ciascuna cartella trovata, verifica la presenza di:

| File | Ruolo | Se manca |
|---|---|---|
| `manifest.json` | configurazione risolta della run | la cartella non è una run valida: segnalala e scartala |
| `analysis/ANALISI.md` | analisi di singola run | **run incompleta**: vedi sotto |
| `analysis/phase3/` | tabelle dei test | run non analizzata: come sopra |

**Regola sulle run incomplete.** Una run priva di `analysis/ANALISI.md`:

- **non entra** in nessun confronto quantitativo del report;
- **viene comunque elencata** nella tabella di tracciamento con stato
  `INCOMPLETA — analizzare prima con PROMPT_ANALISI_WPOA.md`;
- **non le si inventano numeri**, nemmeno se `analysis/phase3/` contiene i CSV. Il motivo non è
  tecnico ma metodologico: senza l'analisi di singola run mancano il giudizio per metrica e
  l'identificazione delle finestre contaminate, e un numero aggregato letto fuori da quel contesto
  può essere fuorviante.

> Nota: al momento della scrittura di questo prompt, `test/results/` conteneva tre run, di cui una
> (`run-wpoa-long10h-medium-sqrt-20260917T221554Z`) **senza** `ANALISI.md`. È esattamente il caso
> sopra. Non assumere che sia ancora così: **conta sempre da disco.**

### 3.2 Passo 2 — Determinare lo stato incrementale

1. Se `test/results/ANALISI-WPOA.md` **esiste**, leggilo per intero ed estrai dalla **tabella di
   tracciamento** l'elenco delle run già incorporate, con la loro data di incorporazione.
2. Calcola tre insiemi:
   - **nuove**: presenti su disco, assenti dalla tabella;
   - **da aggiornare**: presenti in tabella, ma il cui `analysis/ANALISI.md` ha un `mtime`
     posteriore alla data di incorporazione registrata (usa `stat -c '%y' <file>`);
   - **invariate**: tutte le altre.
3. Se il file **non esiste**, tutte le run sono nuove.
4. Se una run in tabella **non esiste più** su disco (cartella cancellata o archiviata in `.tar.gz`),
   **non rimuoverla dalla tabella**: marcala `ARCHIVIATA` e conserva i suoi numeri già estratti. Il
   report è una memoria cumulativa della campagna, non uno specchio della cartella.

> ⚠ **Le sezioni aggregate vanno sempre ricalcolate sull'insieme COMPLETO** delle run valide, non
> solo sulle nuove. L'incrementalità riguarda l'*estrazione* dei dati, non il *confronto*.

### 3.3 Passo 3 — Estrazione dati strutturati per ogni run valida

Per ogni run nuova o da aggiornare, estrai i campi seguenti. **Le fonti autorevoli sono
`manifest.json`, `analysis/phase1/config.csv` e i CSV di `analysis/phase3/`.** I file `.md` della
pipeline servono per il contesto, non per i numeri.

#### (a) Identità e configurazione — da `manifest.json` e `analysis/phase1/config.csv`

| Campo | Dove |
|---|---|
| nome run, timestamp UTC | dal nome della cartella `run-wpoa-<name>-<UTC>` |
| `chain_name`, `seed`, `profile_path` | `manifest.json` |
| **regime native/core** | vedi (b) — **non fidarsi di un solo campo** |
| `dump-function` | `manifest.json` `wpoa_params`, **confermato** da `phase1/config.csv` |
| `delta`, `lambda` | `wpoa-sortition-delta`, `wpoa-sortition-lambda` |
| `M` del feedback | ricavalo: `min(0.5*T, T*(1-delta)/lambda)` |
| parametri malus | `wpoa-malus-*` |
| `enable-wpoa-malus` | `phase1/config.csv` — è `true` su ogni catena, **non è configurabile** |
| **violazioni iniettate** | `manifest.json` `malicious.enabled` + `malicious_manifest.json` |
| `weight-kappa`, `weight-lambda` | `weight_engine_params` |
| **`target-block-time`** | `chain_params` — **può differire fra run** |
| `setup-first-blocks` | `phase1/config.csv` |
| `mining-diversity` | `phase1/config.csv` — se `> 0`, run non comparabile (§1.6) |
| n. validatori, aziende, CA | `manifest.json` `nodes` |
| epoche × lunghezza | `manifest.json` `epochs` |
| durata / altezza finale | `final_height`, `derived.target_height`, `status`, `error` |
| modello di traffico | `manifest.json` `traffic` |
| `runtime.api_decimal_digits` | serve per riconoscere un artefatto noto, vedi §3.6 |

#### (b) Determinare il regime — catena di fallback obbligatoria

Il campo `fabric` **non esiste nei manifest più vecchi** (vale `None`). Applica in ordine:

1. `manifest.json` → `fabric.backend` ∈ `{"native", "core"}` → usa quello;
2. altrimenti: esiste `<run>/fabric.json` **e** `analysis/phase1/topology_paths.csv` ha righe? →
   **core**;
3. altrimenti: `analysis/phase3/wpoa_sigma.csv`, riga `S1_topology`, colonna `n` → `n > 0` →
   **core**, `n == 0` → **native**;
4. altrimenti: dichiara il regime **indeterminato** e non usare quella run nel confronto
   native/core (ma tienila negli altri confronti).

> `S1_topology = 0` in regime `native` significa **assente**, non "piccola". Non presentarlo mai
> come "rete quasi perfetta".

#### (c) Numeri chiave per il confronto — dai CSV di `analysis/phase3/`

Tutti questi file esistono anche nelle run prodotte da versioni più vecchie della pipeline:

| Metrica | File e colonne |
|---|---|
| ordinamento reale (Q1/Q2) | `wpoa_timer_race.csv` → `true_corr_dt_delay`, `true_score_norm_mean`, `true_score_norm_ks_p_uniform`, `true_residual_sd_s` — **questi** rispondono sull'ordinamento |
| inversione osservata (forma pubblica, `1 - 1/n` per costruzione) | `wpoa_timer_race.csv` → `inversion_observed_rate_public`, `inversion_observed_n_public` |
| bound e simulazione di Prop. 5.18 | `wpoa_timer_race.csv` → `inversion_bound_public`, `inversion_mc_prob_gaussian_sigma_S2_public` |
| margine `G` | `wpoa_timer_race.csv` → `G_mean_s`, `G_median_s`, `ks_mc_p` (test di **riferimento**), `ks_beta_p` (**straw man**) |
| banda e candidati | `wpoa_timer_race.csv` → `D_max`, `n_candidates`, `target_block_time`, `delta`, `lambda` |
| decomposizione del rumore | `wpoa_sigma.csv` → righe `S1_topology`, `S2_scheduler_residual_sd`, `S2b_inversion_gap` |
| Prop. 5.17 | `wpoa_prop517.csv` → `mean_standardised_gap` (atteso 1), `ks_p` per vincitore |
| aderenza quota/peso, aggregata | `wpoa_epoch_tests.csv`, riga `epoch == "all"` → `n_blocks`, `gof_chi2`, `gof_df`, `gof_p_value`, `MAE_p`, `MaxAE_p`, `TV` |
| concentrazione aggregata | stessa riga → `p_theoretical_HHI` vs `p_hat_HHI`, `_gini`, `_N_eff`, `_nakamoto_1_2` |
| streak / ripetizioni | stessa riga → `repeat_prob_observed`, `repeat_prob_mc_mean`, `repeat_prob_mc_p_value`, `L_max_*` |
| copertura di Wilson | `weight_election_wilson_coverage.csv` → conteggio `violation`; larghezza da `wpoa_epoch_validators.csv` → `wilson95_width` |
| uniformità dei p-value | `weight_election_pvalue_uniformity.csv` → `n_epochs`, `n_rejections`, `expected_rejections`, `ks_statistic_vs_uniform`, `ks_p_value` |
| proporzionalità longitudinale | `wpoa_longitudinal_fits.csv` → riga `binomial_logit_glm_log_weight`: `beta1`, `beta1_ci_low/high`, `beta1_consistent_with_1`; riga `log_ratio_regression`: `slope`, `intercept`, `pearson_r`; righe `monotonicity`: `concordance_rate`, `sign_test_p_greater` |
| retroazione del peso | `weight_engine_correlations.csv` (riga `(pooled)`), `weight_engine_gini_summary.csv` → `slope`, `spearman_rho/p` |
| malus | `malus_invariants.csv` (3 invarianti booleani), `malus_detection.csv`, `malus_funnel.csv`, `malus_latency.csv`, `malus_weight_effect_matched.csv` |
| controlli di consistenza | `consistency_checks.csv` → `check`, `critical`, `passed`, `detail` |
| dinamica dei pesi | `wpoa_epoch_validators.csv` → `w_raw_end`, `w_eff_end`, `p_theoretical`, `p_hat` |

**Metriche non presenti in nessun CSV, da ricalcolare** (la procedura è la stessa del prompt di
singola run, e va rifatta qui perché serve un valore per ogni run, uniforme):

- **`E_i ~ Exp(1)`**: da `analysis/phase2/candidate_long.csv`, righe con `in_setup = False`,
  `E_i = score × weight_effective`. Riporta media (attesa 1, IC95 `1 ± 1.96/sqrt(n)`) e KS contro
  `F(x) = 1 - exp(-x)` con critico al 5 % `D <= 1.358/sqrt(n)`.
- **`score_norm` dell'argmin `~ U(0,1)`**: raggruppa `candidate_long.csv` per `height` e prendi il
  **minimo** di `score_norm` per round. **Non usare le righe `is_winner`**: quelle marcano chi ha
  *minato*, non l'`argmin`, e su pesi vicini la loro media vale ≈ `1 - 1/(n+1)`, non 0,5.
- **rank di sortition del produttore**: distribuzione di `rank_by_score` sulle righe `is_winner`.
  Confrontala con l'uniforme `1/n` (chi-quadro su `n-1` gdl). È il modo più diretto per distinguere
  "rumore che perturba" da "indipendenza totale".
- **dipendenza fra round e VIF**: da `analysis/phase1/blocks.csv` (righe `in_setup = False`), la
  probabilità di ripetizione consecutiva, l'autocorrelazione lag-1 per validatore e il fattore di
  inflazione della varianza `VIF = (1+r1)/(1-r1)` mediato sui validatori. Serve al punto §3.6.

#### (d) Sintesi qualitativa — da `analysis/ANALISI.md` della run

Il file segue una struttura fissa imposta da `PROMPT_ANALISI_WPOA.md`:

```
# Analisi della run <nome>
## 1. Configurazione della run
## 2. Executive summary
## 3. Analisi per metrica   (3.1 ... 3.N)
## 4. Punti di forza
## 5. Punti critici / da approfondire
## 6. Conclusione
```

Estrai: l'**executive summary** (§2), l'elenco dei **punti di forza** (§4) e quello dei **punti
critici** (§5), più la tabella dei cinque assi in §6 se presente. Servono per verificare che le
conclusioni delle analisi singole siano **coerenti fra loro** e per non ri-derivare da zero
giudizi già argomentati.

#### (e) Normalizzazione obbligatoria prima di confrontare

**`target-block-time` può differire fra run** (nella campagna esistente vale sia 7 s sia 10 s).
Ogni grandezza temporale va quindi resa adimensionale prima del confronto:

| Grandezza | Forma comparabile |
|---|---|
| block time medio | `block_time_medio / T_block` (atteso 1,0) oppure scostamento in % |
| margine `G` | `G_mean_s / Delta_max`, con `Delta_max = delta · T_block` |
| `sigma` | `sigma / Delta_max`, che è la variabile che entra in Prop. 5.18 |
| `Phi` | `|Phi| / M` per la saturazione; `lambda·Phi / T_block` per l'autorità |
| delay | sempre in frazione di `T_block` |

Analogamente, il numero di candidati `n` differisce: l'inversione va sempre letta **contro
`1 - 1/n` della sua run**, non contro un valore assoluto.

### 3.4 Passo 4 — Confronto trasversale, dimensione per dimensione

Per ogni dimensione, aggrega **tutte** le run pertinenti, non una sola. Dichiara sempre quante run
sostengono ogni affermazione e **nomina le run**.

#### (A) Native vs Core — la dimensione principale

Confronta, **a parità delle altre condizioni dove possibile** (e dichiarando esplicitamente quando
non è possibile):

1. **Aderenza fra vincitore designato e vincitore osservato**: si legge su Q1/Q2, non
   sull'inversione pubblica. Costruisci la tabella
   `regime | run | n | Delta_max | sigma_S1 | true_corr_dt_delay | true_residual_sd_s |
   true_score_norm_mean | KS p vs U(0,1)`. La tabella storica
   `inversione osservata | inversione simulata | 1-1/n | bound`, tutta sulle colonne `_public`,
   va riportata solo come audit del modello e con la nota che vale `1 - 1/n` per costruzione.
2. **Applica il test di §1.4**: l'inversione in `core` è maggiore di quella in `native`? È dentro
   il bound? Se `sigma_S1 << sigma_S2`, la rete **non** è la sorgente dominante del rumore, e va
   detto — è il confronto che i due regimi esistono per permettere.
3. **Block time**: scostamento percentuale dal target per regime; deriva nel tempo (Spearman
   epoca ↔ block time medio); stato di `Phi` (saturo? oscillante? entrambi diagnosticabili da
   `phase2/round_level.csv` colonna `phi_s`).
4. **Safety sotto jitter** (§1.4): nelle run `core`, verifica che non compaiano record `Equiv` né
   `Delay` in `phase1/malus_detections.csv`, e che l'altezza finale sia coerente con i blocchi
   misurati. Fork transitorie risolte sono attese; doppie elezioni valide no.
5. **Giudizio esplicito** fra i tre esiti di §1.4: coerente con la teoria / la rete non è la causa /
   anomalia.

#### (B) Funzione di smorzamento

1. Per ogni run, ricava i pesi **grezzi** di fine run (`wpoa_epoch_validators.csv` → `w_raw_end`) e
   ricalcola le quote attese sotto le **tre** funzioni `none`, `sqrt`, `log` sugli **stessi** pesi.
   Questo rende le run confrontabili nonostante i pesi diversi.
2. Costruisci la tabella `run | dump-function reale | rapporto pesi grezzi max/min | rapporto pesi
   efficaci max/min | quota del validatore dominante osservata | quota attesa sotto none/sqrt/log |
   spread delle quote attese`.
3. Verifica l'**ordine di compressione**: `none` > `sqrt` > `log` in concentrazione. È questo che
   deve tornare, non i valori della Tabella 5.1.
4. **Segnala le run che si discostano dall'ordinamento atteso** — e prima di chiamarle anomalie,
   controlla se i pesi di quella run erano già quasi omogenei (§1.3b: in quel caso lo smorzamento è
   a effetto nullo **per costruzione** e l'ordinamento non è misurabile).
5. **Dichiara la potenza del test**: spread delle quote attese contro larghezza media
   dell'intervallo di Wilson. Se lo spread è molto minore della risoluzione, quella run **non può**
   testare la proporzionalità e va esclusa dalle conclusioni su questa dimensione, non usata come
   evidenza contraria.

#### (C) Malus attivo vs disattivo

**Distingui rigorosamente due cose**, perché confonderle produce conclusioni false:

1. **il meccanismo è attivo** — `enable-wpoa-malus = true`: lo è su **ogni** catena della campagna
   e non è configurabile;
2. **sono state iniettate violazioni** — `malicious.enabled` in `manifest.json`.

Il confronto richiesto è sul punto 2. Per ogni run con iniezione, confronta con le run senza, a
parità di altre condizioni:

- funnel `opportunities → attempts → sent → confirmed → valid_malus → reported`;
- `precision`/`recall`/`f1` per kind (`malus_detection.csv`);
- latenza di rilevazione (blocchi) e di **attivazione** (epoche — ricorda che un record dell'epoca
  `e` agisce da `e+1`: una latenza ≥ 1 epoca è **attesa**);
- riduzione delle elezioni dei penalizzati, **proporzionale a `Psi`**, contro il gruppo di controllo
  appaiato per banda di peso (`malus_weight_effect_matched.csv`);
- reversibilità: decadimento `mu^k` e `epochs_to_clear`.

**Se nessuna run ha iniezione** (caso possibile e, al momento della scrittura di questo prompt,
quello reale), il confronto **non è eseguibile**. Scrivilo esplicitamente nel report come
*dimensione a copertura zero*, riporta l'unica evidenza disponibile — l'effetto **esattamente
nullo** su comportamento onesto (`M = 0`, `Psi = 1`, invarianti verificati) su tutte le run — e
inseriscilo fra i suggerimenti di §3.4 della struttura di output.

#### (D) Qualità della randomness (VRF) — la proprietà universale

Verifica su **tutte** le run, indipendentemente da regime e configurazione:

- `E_i ~ Exp(1)`: media e KS;
- `score_norm` dell'argmin `~ U(0,1)`: media e KS;
- Prop. 5.17: `mean_standardised_gap` ≈ 1;
- margine `G`: `ks_mc_p` (il test di riferimento).

Costruisci una tabella con una riga per run e una colonna per test. **Una sola violazione in una
sola run va evidenziata con priorità alta**, perché questa è la proprietà che non dipende da niente:
se cade, non è lo scenario, è la generazione di randomness.

#### (E) Altre dimensioni realmente presenti nei config

Tratta allo stesso modo ogni altra variabile che trovi effettivamente diversa fra run — per esempio
**numero di validatori** (che cambia `1-1/n` e il margine atteso `2·Delta_max/(n+1)`), **durata /
numero di blocchi** (che cambia la potenza statistica), **`target-block-time`**, **modello di
generazione del traffico** (`company_tx_per_epoch_range`, `miner_gas_returns_per_epoch_range`,
`restitution_amount_range`, `esg_score_range`), **`miner_seed_gas`** (che governa quanto il canale
`rho` sia esercitabile). Per ciascuna: aggrega le run comparabili, descrivi il pattern, evidenzia le
eccezioni.

### 3.5 Passo 5 — Classificare ogni conclusione in tre categorie, sempre separate

| Categoria | Criterio | Come presentarla |
|---|---|---|
| **Confermata con alta confidenza** | osservata in modo **consistente su tutte le run pertinenti**, con seed/traffico/configurazioni diversi | elenco puntato con **numero di run a supporto** e range dei valori osservati |
| **Dipendente dallo scenario** | attesa solo sotto certe condizioni, e **coerente con la teoria** per quella configurazione | elenco puntato con la **configurazione associata**; **non** è un'anomalia |
| **Anomalia** | scostamento dalla teoria **imprevisto** data la configurazione di quella run | elenco puntato, distinguendo **"in più run indipendenti"** (probabile problema reale) da **"isolata"** (probabile rumore campionario, da rivedere) |

Esempi del confine fra la seconda e la terza categoria, da applicare letteralmente:

- dominanza forte di un validatore con `dump-function = none` e peso concentrato → **scenario**,
  non anomalia: è quello che il Teorema 5.3 prevede;
- effetto nullo dello smorzamento su pesi quasi omogenei → **scenario**: §1.3b lo prevede;
- inversione maggiore in `core` che in `native`, entro il bound di Prop. 5.18 → **scenario**;
- inversione alta **anche in `native`**, dove `sigma` di propagazione è assente → **anomalia**;
- `E_i` che devia da `Exp(1)` in una qualsiasi run → **anomalia a priorità massima**.

### 3.6 Passo 6 — Artefatti noti dello strumento, da non scambiare per risultati

Questi sono fatti sulla pipeline e sul nodo, verificati nel repository. **Riconoscerli è
obbligatorio**, altrimenti il report globale replica falsi allarmi su tutte le run.

| Artefatto | Come si riconosce | Cosa NON è |
|---|---|---|
| **KS contro `Beta(1,n)`** (`ks_beta_p`) | la pipeline lo etichetta `STRAW MAN` nel campo `ks_beta_note` | non è un rilievo: assume pesi uniformi ed è *atteso* rigettare. Il test valido è `ks_mc_p` |
| **`phi_consistent = FAIL`** | check `critical = no` in `consistency_checks.csv`, "N distinct Phi values" | non è un difetto: `Phi` è per costruzione funzione dello stato della catena e **deve** variare |
| **`S1_topology = 0`** | regime `native` | significa **assente**, non "piccola" |
| **bound di Prop. 5.18 = 1,0** | `inversion_bound` in `wpoa_timer_race.csv` | è **vacuo**: non conferma nulla, usa `inversion_mc_prob_gaussian_sigma_S2` |
| **`weight-alpha`** | presente in `config.csv` con valore `0.2` | **inerte**: il binario lo valida e non lo legge mai. Mai commentarlo come se agisse |
| **scala fixed-point ×100** | `w_k_published = 100 × w_k_final` | è la rappresentazione intera del registro, non una discrepanza. Ma attenzione: `log` non è omogenea, quindi con `dump-function = log` la scala **non si elide** e comprime ulteriormente; `none` e `sqrt` sono immuni |
| **mismatch del delay ≈ 1,0 s esatto** | `delay_recompute_mismatch_rounds_is_zero` FAIL con `max |delta| ≈ 0,99999...` su pochi round, **e** `runtime.api_decimal_digits` diverso da 17 nel manifest | è il **JSON writer del nodo** che arrotonda in scrittura e tronca in emissione — diagnosticato in `test/analysis/pipeline/tools/verify_json_double_rendering.py`. **Non** è un difetto della sortition. Le run recenti lo evitano con `api_decimal_digits: 17` |
| **ultima epoca parziale** | `n_blocks` molto minore della lunghezza d'epoca | intervalli larghi e concentrazione apparente più alta: escludila da ogni tendenza |
| **epoca 1 / `in_setup`** | round sotto `setup-first-blocks` | lì gira il round robin nativo: già esclusa dalla pipeline, non reintrodurla |

**Correzione obbligatoria per la dipendenza fra round.** Il chi-quadro multinomiale e gli intervalli
di Wilson assumono round **indipendenti**. Se la probabilità di ripetizione osservata eccede
`Σpᵢ²`, l'assunzione cade e i p-value nominali sono anti-conservativi. Prima di dichiarare uno
scostamento dalle quote attese, ricalcola con il VIF (§3.3c):

```
chi2_corretto = chi2_nominale / VIF
violazioni di Wilson attese ≈ 0.05 * VIF * N     (invece di 0.05 * N)
```

Se la correzione riconcilia i dati, **non c'è scostamento**: c'è una varianza sottostimata. Se non
li riconcilia, lo scostamento è reale. **Discriminante visivo utile**: l'istogramma dei p-value per
epoca (`plots/p_value_uniformity.png`, o ricalcolato da `wpoa_epoch_tests.csv`) mostra un **picco**
in zero quando la *media* è mal specificata, e un'**inclinazione graduale** quando è solo la
*varianza* a esserlo.

### 3.7 Passo 7 — Attenzione alla variabilità campionaria

- Ogni proprietà nel report dichiara **su quante run indipendenti** si basa. Una riga del tipo
  «confermato (3/3 run)» è ammessa; «il sistema funziona» senza numeri non lo è.
- Una proprietà osservata in **una sola** run non è mai "confermata": va in *anomalia isolata* o in
  *comportamento dipendente dallo scenario*, a seconda che contraddica o segua la teoria.
- I giudizi già scritti nelle versioni precedenti del report **vanno rivisti**, non ereditati: una
  proprietà "confermata su 2 run" che una terza run smentisce scende di categoria, e il report deve
  dirlo esplicitamente insieme alla run che l'ha smentita.
- Quando due run differiscono per **più di una** variabile, non attribuire la differenza a una sola:
  dichiara la confusione e indica quale run mancante la risolverebbe.

---

## 4. Struttura obbligatoria di `test/results/ANALISI-WPOA.md`

Se il file esiste, **aggiornalo mantenendo questa struttura**; non riscriverlo da zero e non
cambiarne l'ordine delle sezioni. Se una sezione esistente non ha più contenuto, lasciala con una
riga che spiega perché.

```markdown
# Analisi globale degli esperimenti wPoA

Ultimo aggiornamento: <data e ora>
Run incorporate: <N valide> su <M totali trovate in test/results/>

## 1. Tabella di tracciamento delle run

<tabella: nome run | regime | data esecuzione (dal timestamp UTC della cartella) |
 data di incorporazione in questo report | config sintetica (dump-function, malus iniettato,
 n. validatori, T_block, epoche×lunghezza) | stato (INCORPORATA / INCOMPLETA / ARCHIVIATA)>

> Questa tabella è lo stato persistente del report: non va mai svuotata, solo estesa.

## 2. Executive summary globale

<10-15 righe. Stato di salute del sistema wPoA sulla base di TUTTI gli esperimenti
 disponibili. Deve dire esplicitamente: quante run, di quale diversità (quanti native,
 quanti core, quali dump-function coperte, quante con malus iniettato), e quali sono
 le due o tre conclusioni che reggono su tutte.>

## 3. Confronto Native vs Core

<tabella comparativa con le metriche chiave affiancate, normalizzate secondo §3.3e>
<commento: la latenza e il jitter introducono scostamenti rispetto al caso ideale?
 Sono entro la tolleranza teorica di Prop. 5.18? Quale dei tre esiti di §1.4 si applica?>
<verifica di safety sotto jitter: Equiv, Delay, coerenza dell'altezza finale>

## 4. Confronto per funzione di smorzamento

<tabella: run | dump-function | rapporto pesi grezzi | rapporto pesi efficaci |
 quota del dominante osservata | quote attese ricalcolate sotto none/sqrt/log sugli
 stessi pesi | potenza del test (spread vs larghezza di Wilson)>
<verifica dell'ordine di compressione none > sqrt > log; eccezioni nominate>

## 5. Efficacia del malus

<confronto fra run con e senza violazioni iniettate. Se nessuna run ha iniezione,
 dichiararlo come dimensione a copertura zero e riportare la sola evidenza disponibile:
 effetto esattamente nullo sul comportamento onesto.>

## 6. Robustezza della randomness (VRF)

<tabella: una riga per run, colonne E_i ~ Exp(1) (media, KS), score_norm dell'argmin
 ~ U(0,1) (media, KS), Prop. 5.17 (gap medio), margine G (ks_mc_p). Eccezioni in evidenza.>

## 7. Altre dimensioni di variazione

<una sottosezione per ogni dimensione realmente presente: n. validatori, durata,
 target-block-time, modello di traffico, ecc.>

## 8. Proprietà confermate con alta confidenza

<elenco puntato; per ciascuna: numero di run a supporto, range dei valori osservati,
 nomi delle run>

## 9. Comportamenti dipendenti dallo scenario

<elenco puntato; per ciascuno: la configurazione che lo produce e perché è coerente
 con la teoria>

## 10. Anomalie da investigare

<elenco puntato, in due gruppi espliciti:
 - "osservate in più run indipendenti" (probabile problema reale)
 - "isolate a una singola run" (possibile rumore campionario, da rivedere)
 con riferimento alle run specifiche e ai numeri>

## 11. Run incomplete o escluse

<elenco delle run senza ANALISI.md o con controlli critici falliti, con il motivo
 dell'esclusione e il rimando a PROMPT_ANALISI_WPOA.md>

## 12. Conclusione complessiva

<stato di maturità e affidabilità del sistema wPoA alla luce di tutti gli esperimenti,
 più i suggerimenti su quali configurazioni aggiuntive varrebbe la pena eseguire per
 rafforzare o smentire le ipotesi ancora scenario-dipendenti e le anomalie isolate>
```

### 4.1 Come usare i controlli critici nel decidere l'inclusione

`analysis/phase3/consistency_checks.csv` contiene controlli con `critical = True`. Se **uno o più
controlli critici falliscono**, l'intestazione di `phase3/report.md` di quella run riporta
`Overall: FAIL — ... the statistics below are not safe to read`. In quel caso:

- **non includere i numeri di quella run nei confronti quantitativi**;
- elencala nella sezione 11 con il nome del check fallito e il suo `detail`;
- **eccezione motivata**: se il fallimento è un artefatto noto di §3.6 (tipicamente il mismatch del
  delay ≈ 1,0 s dovuto al rendering JSON), puoi includere la run **dichiarando esplicitamente**
  l'artefatto, il perché non inficia le metriche usate, e quali metriche resti prudente escludere.
  Non farlo mai in silenzio.

---

## 5. Istruzioni operative finali — da rileggere a ogni esecuzione

1. **Esegui sempre prima la scoperta delle run reali** in `test/results/` con `ls -d
   test/results/run-wpoa-*/`. Non assumere mai un elenco fisso, né quello citato come esempio in
   questo file, né quello della tabella di tracciamento: la tabella dice cosa era già stato
   incorporato, il disco dice cosa c'è ora.
2. **Aggiorna `test/results/ANALISI-WPOA.md` in modo incrementale**: preserva la tabella di
   tracciamento, aggiungi solo le run nuove o modificate, ma **ricalcola tutte le sezioni aggregate**
   (confronti, proprietà confermate, anomalie) sull'insieme **completo e aggiornato** delle run
   valide, non solo su quelle nuove.
3. **Se una run manca del proprio `analysis/ANALISI.md`**, non includerla nei confronti
   quantitativi: elencala nella sezione 11 come run da analizzare singolarmente prima, rimandando a
   `PROMPT_ANALISI_WPOA.md`. **Non inventare mai numeri per run incomplete**, nemmeno se i CSV di
   `analysis/phase3/` sono presenti.
4. **Ogni affermazione deve essere tracciabile** a numeri reali provenienti dagli `ANALISI.md` o dai
   CSV delle run. Mai generica. **Cita sempre a quali run specifiche si riferisce** ogni pattern e
   ogni eccezione, per nome di cartella.
5. **Normalizza prima di confrontare** (§3.3e): `target-block-time`, numero di candidati e
   `Delta_max` differiscono fra run, e un confronto su valori assoluti è privo di significato.
6. **Passa sempre dalla lista di artefatti noti di §3.6** prima di dichiarare un'anomalia, e applica
   la correzione per il VIF prima di dichiarare uno scostamento dalle quote attese.
7. **Se una run ha una configurazione non prevista qui** — una `dump-function` diversa da
   `none`/`sqrt`/`log`, `lambda = 0`, `mining-diversity > 0`, un regime nuovo — **leggi il codice
   reale prima di commentarla**: `src/wpoa/wpoa_selector.h` (`ApplyDumping`),
   `src/wpoa/private_sortition.{h,cpp}` (score, delay, `Phi`), `src/wpoa/malus_registry.cpp`,
   `test/config/schema.md`, `test/analysis/pipeline/` e `test/plotting/generate_plots.py`.
   **Il codice vince sempre su questo documento.**
8. **Scrivi sempre il file su disco**, non limitarti a mostrarlo in chat. Ricorda che
   `test/results/.gitignore` lo rende non versionato: è previsto, segnalalo solo se l'utente chiede
   come conservarlo.
