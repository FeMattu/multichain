# Guida ai dati, ai test statistici e ai grafici di un esperimento wPoA

> Documento **generico**: non si riferisce a nessuna run in particolare. Serve a capire *cosa*
> viene misurato in un esperimento wPoA, *perché* quella misura esiste, *dove* si trova e *come*
> si legge — sia nelle tabelle sia nelle figure.
>
> Ogni run finita produce la stessa struttura. Questa guida la descrive una volta per tutte.

---

## Indice

1. [Il sistema in due paragrafi](#1-il-sistema-in-due-paragrafi)
2. [Come è organizzata l'analisi: tre fasi](#2-come-è-organizzata-lanalisi-tre-fasi)
3. [Fase 1 — i dati raccolti](#3-fase-1--i-dati-raccolti)
4. [Fase 2 — gli aggregati](#4-fase-2--gli-aggregati)
5. [Fase 3 — i test statistici](#5-fase-3--i-test-statistici)
6. [I controlli di consistenza](#6-i-controlli-di-consistenza)
7. [I grafici e come leggerli](#7-i-grafici-e-come-leggerli)
8. [Glossario delle colonne ricorrenti](#8-glossario-delle-colonne-ricorrenti)
9. [Come si legge un numero senza sbagliare](#9-come-si-legge-un-numero-senza-sbagliare)
10. [Costanti e convenzioni](#10-costanti-e-convenzioni)

---

## 1. Il sistema in due paragrafi

wPoA sostituisce il turno fisso (round robin) di MultiChain con una **lotteria pesata e segreta**.
A ogni round ogni validatore estrae localmente, con una funzione pseudocasuale verificabile (VRF),
un numero segreto; lo divide per il proprio **peso**; chi ottiene il valore più basso ha vinto. La
matematica garantisce che la probabilità di vincere sia esattamente proporzionale al peso.

Poiché nessuno può vedere il numero degli altri, il vincitore non può essere annunciato: ciascun
validatore converte il proprio punteggio in un **ritardo** prima di poter proporre il blocco. Il
ritardo più corto spetta al punteggio migliore, quindi chi vince la "corsa dei timer" è lo stesso
che avrebbe vinto la lotteria. Il **peso** non è fisso: lo calcola un motore separato a partire da
punteggi ESG certificati e dall'attività on-chain del *cluster* (un miner più le aziende sue
clienti). A valle il peso può essere ridotto da un **malus** (se il validatore ha commesso
violazioni dimostrabili) e **compresso** da una funzione di smorzamento, prima di entrare nella
lotteria.

L'esperimento serve a verificare, con dati veri prodotti da nodi veri, che tutto questo si comporti
come la teoria prevede.

---

## 2. Come è organizzata l'analisi: tre fasi

```
logs/<nodo>/events.jsonl   →   analysis/phase1/   →   analysis/phase2/   →   analysis/phase3/
    (i log dei nodi)           (tabelle piatte)       (aggregati)            (i test)
                                                            ↓
                                                    analysis/plots/  (le figure)
```

**Ogni fase legge solo l'output della precedente.** È una regola, non una convenzione: serve a
rendere ogni numero sorprendente di un report ritracciabile all'indietro fino a una singola riga di
log e alla chiamata RPC che l'ha prodotta.

| Fase | Cosa fa | Cosa **non** fa |
|---|---|---|
| **phase1 — collect** | legge i log, normalizza le forme, scrive tabelle piatte: **un record in ingresso = una riga in uscita** | nessuna aggregazione, nessuna somma, nessun test |
| **phase2 — aggregate** | unisce le tabelle nei tre "grani" che i test consumano (round, epoca, cluster) e **ricalcola il ritardo** in modo indipendente | nessun test, nessuna decisione |
| **phase3 — analyze** | **l'unica fase che testa**: intervalli di confidenza, bontà di adattamento, concentrazione, streak, timer race, andamento longitudinale, malus, più i controlli di consistenza | — |
| **plots** | disegna le figure **solo** da phase2 e phase3 | non legge mai i dati grezzi |

L'ultima riga è importante: poiché le figure sono disegnate dalle stesse tabelle che i test leggono,
**una figura e un p-value non possono mai essere in disaccordo** sulla stessa quantità.

---

## 3. Fase 1 — i dati raccolti

File in `<run>/analysis/phase1/`. Le uniche derivazioni ammesse sono due funzioni pure dell'altezza
di blocco: `epoch = altezza // lunghezza_epoca` e `in_setup = altezza <= setup-first-blocks`.

### 3.1 La catena e l'elezione

| File | Cosa contiene | A cosa serve, in parole semplici |
|---|---|---|
| `blocks.csv` | un blocco per riga: altezza, hash, **chi l'ha minato**, orario, n. transazioni, epoca | è la verità di base: chi ha prodotto cosa e quando. Da qui si contano i blocchi vinti da ciascuno |
| `round_scores.csv` | per ogni round e ogni candidato: punteggio, peso, peso efficace, seed usato | il numero segreto che ciascuno ha estratto, e con quale peso l'ha diviso |
| `round_delays.csv` | per ogni round e candidato: ritardo calcolato, punteggio normalizzato, `target-block-time`, `delta`, `lambda`, `feedback_phi` | tutti gli ingredienti del ritardo nella forma **pubblica** `HMAC-SHA256(seed, indirizzo)`. Serve a ricalcolare e verificare la *formula*, non a stabilire chi doveva vincere (regola 10 di §9) |
| `block_sortition.csv` | per ogni blocco: il punteggio **privato reale** del vincitore, ricomputato dal reveal VRF che il blocco stesso pubblica, più `delay`, `earliest_time` e il contesto del round | l'unica fonte del punteggio su cui l'elezione ha davvero girato. Alimenta le colonne `_true` e i test Q1/Q2 di `timer_race.md` |
| `round_effective_weights.csv` | peso grezzo → peso dopo il **solo** smorzamento | isola l'effetto della compressione |
| `round_final_weights.csv` | la catena completa: peso grezzo → malus (`Psi`) → smorzamento → peso finale | mostra quale dei due stadi ha spostato il peso |
| `registry_weights.csv` | fotografie del registro dei pesi pubblicato sulla catena | cosa la rete *credeva* fossero i pesi, momento per momento |

### 3.2 Il motore del peso

| File | Cosa contiene | A cosa serve |
|---|---|---|
| `esg_events.csv` | ogni pubblicazione di punteggio ESG da parte di una Certification Authority | il punto di partenza del peso: chi ha certificato chi, e con che voto |
| `epoch_contributions.csv` | contributo di ogni azienda per epoca: ESG × attività ÷ κ | quanto ogni azienda ha aggiunto al peso del proprio cluster |
| `epoch_cluster_weights.csv` | per cluster ed epoca: ESG del miner, sua attività, contributi delle aziende, peso grezzo, peso finale, peso pubblicato | il calcolo del peso, passo per passo e verificabile |
| `epoch_earnings.csv` | entrate, uscite, guadagno, saldo, restituzioni, tasso di restituzione | il flusso economico del cluster, che alimenta la retroazione fra epoche |
| `epoch_returns.csv` | quanto ogni miner ha restituito al treasury in ogni epoca | l'unico canale con cui il comportamento passato influenza il peso futuro |
| `epoch_balances.csv` | saldo per miner ed epoca | il denominatore del tasso di restituzione |
| `membership_events.csv` | registrazioni di appartenenza azienda → cluster | chi contribuisce al peso di chi |
| `verification.csv` | esito del ricalcolo indipendente dei pesi pubblicati: `published` contro `recomputed` | verifica che nessuno abbia pubblicato un peso "inventato" |

### 3.3 Il traffico e la rete

| File | Cosa contiene | A cosa serve |
|---|---|---|
| `traffic_tx.csv` | ogni transazione informativa emessa dalle aziende | genera l'attività (`tau`) che fa muovere i pesi |
| `epoch_plans.csv` | quanto ogni daemon **aveva pianificato** di emettere | confronto piano/realtà: se sono diversi, qualcosa non è arrivato sulla catena |
| `gas_returns.csv` | ogni singola restituzione verso il treasury, con importo e saldo precedente | il dettaglio delle restituzioni tentate |
| `gas_transfers.csv` | i finanziamenti iniziali (premine → nodi) | da dove viene il GAS che i miner poi restituiscono |
| `stream_items.csv` | ogni record confermato su ogni stream, con il payload JSON | l'archivio completo di cosa è stato scritto sulla catena |
| `topology_paths.csv` | **(solo regime `core`)** ritardo di percorso fra ogni coppia di validatori | quanto sono "lontani" due validatori sulla mappa emulata |
| `peers.csv`, `node_state.csv`, `miners.csv`, `permissions.csv`, `nodes.csv` | stato della rete, connessioni, permessi, mappa nodo↔indirizzo | serve a capire se un nodo era vivo, connesso e autorizzato |
| `rpc_errors.csv` | errori delle chiamate RPC durante la run | un volume alto vicino a un'epoca anomala è un'ipotesi esplicativa |

### 3.4 Il malus e l'esperimento con i miner malevoli

| File | Cosa contiene | Quando è pieno |
|---|---|---|
| `malus.csv` | per ogni istante campionato: accumulatore `M`, fattore `Psi`, peso, peso efficace, se escluso | **sempre** (il meccanismo è sempre attivo) |
| `malus_detections.csv` | le segnalazioni di violazione emesse dal rilevatore onesto | solo se qualcuno ha davvero violato |
| `malicious_miners.csv` | quali miner sono stati designati malevoli e con che quota | solo se il profilo ha una sezione `malicious` |
| `malicious_opportunities.csv` | ogni occasione in cui un miner malevolo *poteva* agire, e se ha agito | idem |
| `malicious_actions.csv` | le azioni effettivamente tentate | idem |
| `malicious_confirmations.csv` | quali azioni sono finite in un blocco | idem |

> Se il profilo non ha la sezione `malicious`, questi file esistono ma sono **vuoti**. Non è un
> errore: significa che quella run non ha misurato l'efficacia del malus, solo che il malus non
> penalizza nessuno senza motivo.

---

## 4. Fase 2 — gli aggregati

File in `<run>/analysis/phase2/`. Qui i dati vengono riorganizzati nei tre "grani" che i test usano.

| File | Grana | Cosa contiene, e perché è utile |
|---|---|---|
| `candidate_long.csv` | **una riga per (round, candidato)** | la tabella più fine: peso grezzo, malus, peso efficace, punteggio, punteggio normalizzato, ritardo loggato, **ritardo ricalcolato**, scarto fra i due, se il candidato era eleggibile, se ha vinto, e la sua posizione in classifica per punteggio e per ritardo |
| `round_level.csv` | **una riga per round** | la competizione vista dall'alto: chi ha vinto, il **margine** fra i due ritardi più veloci, il punteggio minimo e il secondo, `Phi`, se c'è stata **inversione** (ha minato qualcuno diverso dall'`argmin`), il tempo fra un blocco e il precedente. Le colonne `_public` derivano dal punteggio pubblico e **non** misurano l'ordinamento reale (regola 10 di §9); quelle `_true` sì |
| `epoch_level.csv` | **una riga per (epoca, validatore)** | blocchi vinti contro blocchi spettanti: è ciò che consumano l'intervallo di Wilson e il test di bontà di adattamento |
| `epoch_engine.csv` | **una riga per (epoca, cluster)** | il motore del peso: ESG, attività, contributi, peso grezzo, tasso di restituzione, peso finale e pubblicato, blocchi vinti |
| `epoch_concentration.csv` | **una riga per epoca** | tutti gli indici di concentrazione, calcolati **due volte**: sui pesi (teorici) e sui blocchi (osservati) |
| `epoch_traffic.csv` | **una riga per (epoca, nodo)** | pianificato → inviato → **effettivamente sulla catena**: trasforma "il daemon dice di aver inviato 42" in un'affermazione verificabile |
| `malus_state.csv` | **una riga per (epoca, validatore)** | `M`, `Psi`, peso efficace, più tre **invarianti** booleani che devono valere sempre |

### Il ricalcolo del ritardo: la verifica più importante di questa fase

Il nodo calcola il ritardo con

```
D_i = T_block + delta · T_block · (2 · punteggio_normalizzato − 1) + lambda · Phi
```

e la fase 2 **lo ricalcola dagli stessi ingressi** e confronta. La colonna `delay_mismatch_public_s` deve
essere praticamente zero (la tolleranza è 1,5 ms). Se non lo è, l'harness e il nodo **non sono
d'accordo sul meccanismo stesso**, e ogni risultato sulla corsa dei timer perde valore.

> ⚠ Questo verifica che i due **calcolino** la stessa formula. Non verifica che lo scheduler del
> nodo **rispetti** il ritardo calcolato: quello lo dice `true_corr_dt_delay` (test Q1 di
> `timer_race.md`), **non** il tasso di inversione, che sulla forma pubblica non misura
> l'ordinamento (regola 10 di §9).

---

## 5. Fase 3 — i test statistici

File in `<run>/analysis/phase3/`. Ogni test è scritto dalla sua forma chiusa: `scipy` è presente nel
container ma **deliberatamente non usato**, perché un risultato di tesi il cui p-value dipende dalla
versione di una libreria installata è più difficile da difendere di uno la cui aritmetica è visibile
nel file.

Per ogni test qui sotto: **cosa chiede**, **come funziona** (l'idea, non la dimostrazione), **dove
si legge**, **come si legge**, **le trappole**.

---

### 5.1 Intervallo di Wilson — *il test di riferimento, validatore per validatore*

**Cosa chiede.** Un validatore aveva un peso che gli dava diritto a una certa quota dei blocchi
dell'epoca. Ne ha vinti `O_i` su `B`. La quota osservata è compatibile con quella spettante?

**Come funziona.** Attorno alla quota osservata si costruisce un intervallo di confidenza al 95 %.
Se la quota spettante ci cade dentro, la differenza è spiegabile dal caso. Si usa l'intervallo di
Wilson e non quello "da manuale" (`p ± z·√(p(1−p)/n)`) perché quest'ultimo sbaglia esattamente dove
serve: con pochi blocchi produce intervalli che escono da `[0,1]`, e **si annulla quando un
validatore non ha vinto nulla** — che è proprio l'osservazione che più avrebbe bisogno di un
intervallo.

**Dove si legge.** `weight_election_wilson_coverage.csv`, `wpoa_epoch_validators.csv`,
`weight_vs_election.md`.

**Come si legge.**

| Colonna | Significato |
|---|---|
| `p_theoretical` | la quota **spettante**, dal peso efficace (dopo malus e smorzamento) |
| `p_hat` | la quota **osservata** (`O_i / B`) |
| `wilson95_low`, `wilson95_high` | gli estremi dell'intervallo |
| `p_theoretical_inside_wilson95` | `yes` = compatibile, `no` = fuori |
| `wilson95_width` | **la risoluzione della run**: quanto è larga la lente con cui si guarda |

**Trappole.**

- **Contare le violazioni senza correggere per i confronti multipli è un errore.** Con `V`
  validatori e `E` epoche, circa il **5 %** degli intervalli escluderà la quota spettante **per
  puro caso**. Il file riporta sempre `expected_rejections` accanto a quelle osservate: è il
  confronto giusto.
- **Un `p_hat` lontano da `p_theoretical` non significa nulla se l'intervallo è largo.** Dichiarare
  sempre `wilson95_width` medio accanto al giudizio.
- Questo test dice **quale** validatore è fuori linea, non **se l'epoca nel complesso** lo è. Per
  quello serve il test successivo.

---

### 5.2 Bontà di adattamento (goodness of fit) — *il test congiunto sull'epoca*

**Cosa chiede.** Dato il vettore dei pesi in vigore, l'intero vettore dei blocchi vinti è
un'estrazione plausibile da una lotteria pesata?

**Come funziona.** Si confrontano i conteggi osservati con quelli attesi. Tre stimatori diversi,
scelti automaticamente perché ciascuno è sbagliato fuori dal proprio campo:

| Stimatore | Quando si usa | Perché |
|---|---|---|
| **chi-quadro asintotico** | ogni conteggio atteso ≥ 5 | il classico `Σ(O−E)²/E`. Sotto quella soglia l'approssimazione sbaglia **nella direzione che fabbrica significatività** |
| **enumerazione multinomiale esatta** | al massimo 3 classi | nessuna approssimazione; fattibile solo perché il numero di combinazioni esplode oltre le 3 classi |
| **Monte Carlo** | tutti gli altri casi | 20 000 estrazioni sotto l'ipotesi nulla |

**La variante round-per-round non è un raffinamento, è una correzione.** La quota di un validatore
può cambiare **dentro** un'epoca (un record di peso si conferma, scatta un malus, cambia l'insieme
dei validatori). Mettere tutta l'epoca in un unico multinomiale con un solo vettore di quote testa
un'ipotesi che **non è mai stata in vigore**. Quando `share_changed_within_epoch` è vero, la colonna
da leggere è `gof_mc_round_by_round_p`.

**Dove si legge.** `wpoa_epoch_tests.csv` (una riga per epoca, più una riga `all` sull'intera run).

**Come si legge.**

| Colonna | Significato |
|---|---|
| `gof_p_value` | piccolo (< 0,05) = l'epoca è distinguibile da una lotteria pesata |
| `gof_method` | quale dei tre stimatori è stato usato |
| `gof_reject_alpha05` | il verdetto a soglia 5 % |
| `MAE_p`, `MaxAE_p`, `TV` | **quanto**, non **se**: errore medio, errore massimo e distanza totale fra quote |

**Trappole.**

- Un p-value dice «è distinguibile?», le tre distanze dicono «di quanto?». Su run con pochi blocchi
  **la seconda domanda è quasi sempre la più informativa**: un rigetto con `MAE_p = 0,003` su quote
  del 10 % è un effetto reale ma minuscolo.
- Anche qui vale la correzione per confronti multipli: con 60 epoche, **3 rigetti sono attesi**.
- Il test assume round **indipendenti**. Se non lo sono (§5.4), i p-value sono troppo generosi e
  vanno corretti.

---

### 5.3 Concentrazione — *il potere è concentrato?*

**Cosa chiede.** Un consenso pesato può superare ogni test di adattamento e restare comunque un
cattivo esito: se i **pesi** sono concentrati, l'elezione riproduce fedelmente quella
concentrazione. Questi indici misurano ciò su cui i p-value tacciono.

**Come funziona.** Cinque indici, perché si contraddicono in modo utile:

| Indice | Cos'è | Come si legge |
|---|---|---|
| **HHI** | `Σ s_i²` sulle quote | più alto = più concentrato. Dominato dai grandi |
| **N_eff = 1/HHI** | "quanti validatori di pari dimensione darebbero questo HHI" | il numero da citare a chi non conosce l'HHI. 4 validatori con quote (0,7 / 0,1 / 0,1 / 0,1) danno N_eff ≈ 1,9: **una catena a 4 che si comporta come una a 2** |
| **Coefficiente di Nakamoto** | quanti validatori bastano per raggiungere 1/3, 1/2, 2/3 del totale | l'indice rilevante per la **sicurezza**: risponde a "quanti devono mettersi d'accordo" |
| **Gini** | disuguaglianza, da 0 (tutti uguali) a 1 (tutto a uno) | confrontabile fra run con numeri di validatori diversi |
| **Entropia normalizzata** | 1 = distribuzione piatta, 0 = totale concentrazione | complemento naturale dell'HHI |

**Tutto è calcolato due volte**: sulle quote **teoriche** (ciò a cui i pesi danno diritto) e su
quelle **osservate** (ciò che i blocchi hanno consegnato).

**Dove si legge.** `epoch_concentration.csv`, colonne `theoretical_*` e `observed_*`; nella riga
`all` di `wpoa_epoch_tests.csv` come `p_theoretical_*` e `p_hat_*`.

**Come si legge.** Il numero interessante è **il divario fra le due colonne**: la concentrazione
teorica è una proprietà del motore del peso, quella osservata è una proprietà dell'elezione. Un
divario grande punta il dito sulla lotteria, non sui pesi.

**Trappola principale.** Con pochi blocchi per epoca, la concentrazione **osservata** è
sistematicamente più alta di quella teorica **per pura varianza campionaria**: è un artefatto, non
concentrazione reale. Il confronto affidabile è la **riga aggregata** su tutta la run, dove il
campione è molto più grande.

---

### 5.4 Streak e ripetizioni — *i round sono davvero indipendenti?*

**Cosa chiede.** Una lotteria pesata estrae in modo indipendente a ogni round, quindi le serie di
vittorie consecutive **sono attese**: un validatore con il 40 % del peso vince tre volte di fila
circa il 6 % delle volte. La domanda non è mai «ci sono state serie» ma «**ce ne sono state più**, o
**più lunghe**, di quante ne produrrebbe un'estrazione indipendente».

**Come funziona.** Il confronto non si fa con una formula chiusa a quote uguali, perché qui le quote
non sono né uguali né costanti. Si **simula** l'ipotesi nulla con **le quote che hanno governato
ogni singolo round** (10 000 estrazioni). Due statistiche, perché intercettano difetti diversi:

| Statistica | Cosa coglie |
|---|---|
| `L_max` — la serie più lunga di vittorie consecutive | un validatore che ogni tanto "sequestra" la catena per un tratto |
| `repeat_prob` — la frazione di coppie di round adiacenti vinte dallo stesso | una **vischiosità lieve ma diffusa** su tutta la run, che `L_max` non vedrebbe |

**Dove si legge.** `wpoa_epoch_tests.csv` (`L_max_observed`, `L_max_mc_mean`, `L_max_mc_p_value`,
`repeat_prob_observed`, `repeat_prob_mc_mean`, `repeat_prob_mc_p_value`) e `streak.md`.

**Come si legge.** Si confronta sempre l'**osservato** con la **media Monte Carlo**, mai con un
valore astratto. Il p-value è a una coda: solo *più* serie del previsto è un rilievo.

**Perché conta molto.** Un `repeat_prob` alto con un `L_max` normale è la firma di un round robin
che trapela — che è esattamente ciò che `mining-diversity` al suo valore di fabbrica (0,3)
produce, e il motivo per cui i profili lo mettono a 0.

**Conseguenza da non dimenticare.** Se `repeat_prob` eccede il valore atteso, **i round non sono
indipendenti** e i test §5.1 e §5.2 — che lo assumono — danno p-value troppo generosi. Si corregge
con il fattore di inflazione della varianza:

```
VIF = (1 + r1) / (1 − r1)        r1 = autocorrelazione lag-1 dell'indicatore "ha vinto i"
chi2_corretto = chi2_nominale / VIF
violazioni di Wilson attese ≈ 0,05 · VIF · N        (invece di 0,05 · N)
```

---

### 5.5 La corsa dei timer — *il ritardo fa davvero quello che deve?*

**Cosa chiede.** Ogni validatore converte il proprio punteggio in un ritardo e aspetta. Il
**margine** `G = D₍₂₎ − D₍₁₎` — la distanza fra il più veloce e il secondo — è la finestra dentro
cui qualunque disturbo (jitter dello scheduler, propagazione, deriva degli orologi) può ribaltare
l'esito.

**Tre test, deliberatamente di rango diverso.**

| # | Test | Status | Come si legge |
|---|---|---|---|
| 1 | KS contro `Beta(1, n)` | **straw man dichiarato** | assume che tutti i pesi siano uguali. **È *atteso* rigettare** quando non lo sono. È calcolato apposta perché il report possa mostrarlo rigettare, invece di lasciare il dubbio che nessuno abbia controllato. **Leggerne il rigetto come un difetto è l'errore che questo test esiste per prevenire** |
| 2 | KS contro la **distribuzione esatta simulata** | **il test vero** | gli stessi ritardi vengono simulati dal modello che il nodo implementa davvero, con i pesi in vigore in ogni round. È l'ipotesi nulla che **non** dovrebbe essere rigettata |
| 3 | **Prop. 5.17** — il controllo analitico | verifica lo stadio del punteggio | il "distacco standardizzato" fra i due punteggi migliori deve essere `Exp(1)`, quindi con **media 1**. Testa il punteggio *prima* della trasformazione in ritardo: un fallimento qui con un successo nel test 2 localizza il guasto nella trasformazione, non nell'estrazione |

**L'inversione.** Si chiama *inversione* il round in cui a produrre il blocco **non** è stato il
validatore che la lotteria aveva designato. La teoria ne dà un limite superiore:

```
P[inversione] ≤ (3/2) · (n · sigma / D_max)^(2/3)
```

dove `n` è il numero di candidati, `D_max` l'ampiezza della banda dei ritardi e `sigma` la
deviazione standard del disturbo. Il disturbo è scomposto in due sorgenti:

| Sorgente | Cos'è | Nota |
|---|---|---|
| `S1_topology` | dispersione del ritardo di propagazione fra coppie di validatori sui percorsi minimi della mappa emulata | in regime **`native`** vale 0 perché **è assente** (tutti i nodi sono processi locali, non c'è mappa), **non** perché sia risultato piccolo |
| `S2_scheduler_residual_sd` | quanto la spaziatura reale dei blocchi si discosta dal ritardo che avrebbe dovuto produrla | **è la sorgente primaria** nella maggior parte delle run, ed è quella con cui il limite viene valutato |
| `S2b_inversion_gap` | dispersione del margine sui soli round che hanno effettivamente invertito | diagnostica di supporto |

**Dove si legge.** `wpoa_timer_race.csv` (una riga), `wpoa_sigma.csv` (tre righe),
`wpoa_prop517.csv` (una riga per vincitore), `timer_race.md`.

**Come si legge.**

- `ks_mc_p` **alto** (non significativo) = la distribuzione dei ritardi calcolati è quella prevista.
  Questo è il numero da leggere.
- `ks_beta_p` = 0 → **ignorare**, è lo straw man.
- `mean_standardised_gap` ≈ 1 → Prop. 5.17 verificata.
- `inversion_observed_rate_public` va confrontato con **due** riferimenti:
  - `inversion_mc_prob_gaussian_sigma_S2_public` — quanto il rumore misurato spiegherebbe;
  - **`1 − 1/n`** — il valore che si otterrebbe se il produttore fosse scelto **a caso** fra gli `n`
    candidati. Con 10 candidati vale 0,900.

> ⛔ **Prima di tutto il resto: questa metrica vale `1 − 1/n` per costruzione.** L'argmin con cui il
> vincitore viene confrontato è quello della forma **pubblica**, indipendente dal punteggio VRF
> privato che ha davvero armato i timer, quindi il confronto è fra il vincitore e un'estrazione
> casuale. Non può risultare diverso da `1 − 1/n` qualunque cosa faccia il protocollo. Per
> l'ordinamento reale si leggono i test Q1/Q2 in cima a `timer_race.md`; qui sotto resta la lettura
> storica, valida solo come audit del modello. Vedi la regola 10 di §9.

> ⚠ **La distinzione più importante di questa sezione**, se mai si disponesse di un tasso di
> inversione costruito sul punteggio vero. Un'inversione "alta" e un'inversione pari a `1 − 1/n`
> sono affermazioni qualitativamente diverse. La prima dice «il rumore perturba l'ordinamento»; la
> seconda dice «**l'esito è indipendente** dall'ordinamento», che è molto più grave. Confrontare
> sempre con `1 − 1/n` prima di parlare di rumore.
>
> ⚠ **Un limite superiore pari a 1,0 è vacuo** e non conferma nulla: significa solo che la
> disuguaglianza non vincola. In quel caso l'unico confronto utile è con la simulazione.
>
> ⚠ Il docstring del modulo `stat/timer_race.py` afferma che `S1` non è misurato in nessun regime.
> **È obsoleto rispetto al codice**: il chiamante in `phase3_analyze.py` fornisce effettivamente i
> ritardi di percorso quando `phase1/topology_paths.csv` esiste. La colonna `note` nella riga del
> CSV è aggiornata e distingue correttamente i due casi.

---

### 5.6 Andamento longitudinale — *la relazione peso↔vittorie regge nel tempo?*

**Cosa chiede.** Tutti i test precedenti guardano **una** epoca. Questi guardano **attraverso** le
epoche, che è dove vive la retroazione del motore del peso e dove una deriva lenta — quella che
nessun p-value di singola epoca coglierebbe — diventa visibile.

**Quattro strumenti.**

| # | Strumento | Ipotesi nulla | Come si legge |
|---|---|---|---|
| 1 | **Guadagni prima-contro-ultima epoca** | — | quota spettante e osservata nella prima e nell'ultima epoca misurata, **con gli intervalli**: un "guadagno" più piccolo della larghezza dell'intervallo non è un guadagno |
| 2 | **Sign test sulla monotonia** | la quota si muove nella **stessa direzione** del peso | non assume nessuna forma funzionale, ed è per questo il primo da guardare. Il p-value è la coda binomiale **esatta**, perché con una dozzina di coppie informative l'approssimazione normale sbaglia nella direzione che fabbrica significatività |
| 3 | **GLM logit su `log(peso)`** | **`beta1 = 1`**: raddoppiare il peso deve raddoppiare il rapporto di quote | previsione netta e falsificabile. Si legge `beta1` **con il suo intervallo di confidenza**: se l'intervallo contiene 1, l'ipotesi regge |
| 4 | **Regressione dei log-rapporti a coppie** | **pendenza 1, intercetta 0** | per ogni coppia di validatori in ogni epoca, `log(O_i/O_j)` contro `log(p_i/p_j)`. È invariante al numero di blocchi e a qualunque distorsione moltiplicativa comune: una distorsione sistematica si vede come pendenza diversa da 1 **anche se ogni singola epoca passa il proprio test** |

**Dove si legge.** `wpoa_longitudinal_fits.csv` (righe `monotonicity`, `binomial_logit_glm_log_weight`,
`log_ratio_regression`), `wpoa_longitudinal_validators.csv`, `wpoa_longitudinal_logratios.csv`,
`longitudinal.md`.

**Trappola.** Con poche epoche questi test hanno **pochissima potenza**. `n_points` accanto a ogni
coefficiente non è decorazione: una pendenza di 0,6 stimata da quattro punti non dice nulla. Un
intervallo di confidenza largo un'unità intera su `beta1` significa che il test **non discrimina**,
non che l'ipotesi sia confermata.

---

### 5.7 Retroazione del motore del peso

**Cosa chiede.** Il peso di un'epoca dipende dal comportamento dell'epoca precedente attraverso un
solo canale: il **tasso di restituzione** al treasury. Quel canale funziona?

**Dove si legge.** `weight_engine_correlations.csv` (correlazione di Spearman fra il tasso di
restituzione all'epoca `e` e il peso pubblicato in `e+1`, per cluster e complessiva),
`weight_engine_gini.csv` e `weight_engine_gini_summary.csv`.

**Come si legge.**

- `spearman_rho` con `spearman_p`: correlazione positiva e significativa = il canale funziona.
- `gini_delta = Gini(peso pubblicato) − Gini(input ESG×attività)`: dice se **il motore amplifica la
  disuguaglianza che riceve in ingresso**. Una pendenza positiva della sua traiettoria nel tempo
  significa che il divario si allarga.

**Trappola decisiva.** Prima di concludere che «la retroazione non funziona», **verificare che il
tasso di restituzione abbia varianza**. Se il modello di traffico fa restituire ai miner una
frazione trascurabile del proprio saldo, quel tasso resta schiacciato vicino a zero e il fattore
moltiplicativo che ne deriva occupa una porzione minima del suo intervallo utile: **l'assenza di
correlazione era prevedibile prima di guardare i dati**, e non dice niente sul codice.

---

### 5.8 Malus — *la penalità funziona?*

Prima di tutto, **due cose diverse da non confondere mai**:

1. **il meccanismo è attivo** (`enable-wpoa-malus = true`): lo è su **ogni** catena e non è
   configurabile;
2. **sono state iniettate violazioni** (`malicious.enabled` nel profilo): questo sì, è opzionale.

**Se non ci sono violazioni iniettate**, l'unica cosa misurabile è che il malus **non penalizzi
nessuno**: `M = 0`, `Psi = 1`, e i tre invarianti verificati ovunque. È una verifica di sicurezza,
non di efficacia.

**Se ci sono**, si misura la catena completa:

| Misura | File | Come si legge |
|---|---|---|
| **funnel** | `malus_funnel.csv` | `opportunità → tentativi → inviate → confermate → malus valido → segnalate`. Quanto si perde a ogni passaggio |
| **qualità del rilevatore** | `malus_detection.csv` | `precision`, `recall`, `f1` per tipo di violazione |
| **latenza** | `malus_latency.csv` | di **rilevazione** (conferma → primo report, in blocchi) e di **attivazione** (in epoche) |
| **effetto sul peso** | `malus_weight_effect.csv`, `malus_weight_effect_matched.csv` | variazione del peso efficace dei penalizzati, **confrontata con un gruppo di controllo appaiato per banda di peso** |
| **invarianti** | `malus_invariants.csv` | tre booleani che devono valere sempre |

**Tre stati tenuti rigorosamente distinti**, perché confonderli è il modo più facile di sopravvalutare
il meccanismo:

- **tentata** — il controllore del miner malevolo ha deciso di agire (verità di base, dal suo log);
- **confermata** — la transazione è finita in un blocco (ancora verità di base);
- **malus valido** — un nodo onesto ha accettato l'evidenza e ha pubblicato una segnalazione (il
  verdetto del rilevatore, prodotto **senza leggere** la verità di base).

`precision` e `recall` usano sempre le azioni **confermate** come classe positiva, mai quelle
tentate: un'azione mai confermata non può portare un malus, quindi contarla come mancata rilevazione
penalizzerebbe il rilevatore per la tempistica della catena.

**Cosa aspettarsi.**

- Un record valido riferito all'epoca `e` **agisce dall'epoca `e+1`**: una latenza di attivazione di
  almeno un'epoca è **attesa e corretta**.
- La riduzione delle elezioni deve essere **proporzionale a `Psi`**, non arbitraria.
- L'esclusione non è mai permanente: senza nuove violazioni l'accumulatore decade
  geometricamente e il validatore rientra dopo un numero finito e calcolabile di epoche.
- Un `recall < 1` con un solo rilevatore onesto è un **limite noto del setup**, non necessariamente
  un difetto del protocollo.

---

### 5.9 I due test di sanità della casualità

Questi non sono nei CSV: si ricavano da `phase2/candidate_long.csv`. Sono i più importanti di tutti,
perché **non dipendono da nulla** — né dai pesi, né dallo smorzamento, né dal malus, né dal traffico,
né dalla topologia.

| Test | Come si ricava | Valore atteso |
|---|---|---|
| **punteggio grezzo `Exp(1)`** | `E_i = punteggio × peso_efficace`, sulle righe con `in_setup = False` | media **1**; istogramma che segue `e^(−x)`; KS con `D ≤ 1,358/√n` al 5 % |
| **punteggio normalizzato del vincitore `Uniform(0,1)`** | il **minimo** di `score_norm` fra i candidati di ogni round | media **0,5**; KS con lo stesso critico |

**Se uno dei due fallisce, ogni altra metrica a valle perde di significato**: significa che la
generazione di casualità è difettosa, non che lo scenario è particolare.

> ⚠ **La trappola più insidiosa di tutta l'analisi.** Per il secondo test, *sulle colonne
> `_public`*, si deve usare il **minimo per round**, non le righe con `is_winner = True`.
> `is_winner` marca **chi ha minato il blocco**, che sotto disturbo può non essere il vincitore
> della lotteria. Inoltre, con `n` pesi vicini, la media di `score_norm_public` su un candidato
> *qualsiasi* vale circa `1 − 1/(n+1)` — per esempio ≈ 0,909 con 10 candidati. Chi usasse
> `is_winner` vedrebbe 0,91 invece di 0,50 e concluderebbe, sbagliando, che la VRF è rotta.

**Sul punteggio vero la logica si capovolge, ed è il test Q2 di `timer_race.md`.** Con
`score_norm_true` — il punteggio reale del vincitore, ricomputato dal reveal VRF del suo blocco —
prendere proprio la riga del vincitore **è** il test: se il vincitore è l'argmin del campo, il suo
punteggio normalizzato è `U(0,1)` con media 0,5 (Prop. 5.10); se invece vince un validatore
qualsiasi, si legge la media ≈ `1 − 1/(n+1)` ≈ 0,909. La stessa aritmetica che sulle colonne
pubbliche produce un falso allarme, su quelle vere è il segnale — e serve **solo** il vincitore,
mai i punteggi privati degli altri candidati, che nessun nodo può calcolare. Vedi la regola 10 di
§9.

---

## 6. I controlli di consistenza

File: `consistency_checks.csv`. **Non sono test di ipotesi**: sono controlli di non-regressione che
esistono per **fallire rumorosamente** quando la raccolta o la pipeline hanno un bug — un NaN, un
peso negativo, un indirizzo sconosciuto.

| Controllo | Critico | Cosa verifica |
|---|---|---|
| `registry_weights_finite_and_positive` | sì | nessun peso è NaN, infinito o negativo |
| `no_phantom_validator_in_registry` | sì | ogni indirizzo con un peso è un miner conosciuto |
| `malus_finite_and_psi_in_unit_interval` | sì | ogni `Psi` sta in `[0,1]` |
| `delay_recompute_mismatch_rounds_is_zero` | sì | harness e nodo calcolano lo stesso ritardo |
| `every_esg_publication_reached_the_stream` | sì | nessuna certificazione ESG è andata persa |
| `only_miners_pay_the_treasury` | sì | solo i miner pagano il treasury (è l'unico attore di cui il motore legge le restituzioni) |
| `at_least_one_fully_measured_epoch` | sì | esiste almeno un'epoca interamente oltre la fase di setup |
| `certified_scores_reflected_in_the_engine` | no | ogni indirizzo certificato ha un ESG non nullo nella vista del motore |
| `traffic_counts_within_configured_range` | no | i conteggi on-chain rientrano nei range configurati |
| `phi_consistent` | no | `Phi` assume un solo valore su tutta la run |

**Se un controllo critico fallisce**, l'intestazione di `report.md` lo dichiara con
`Overall: FAIL — ... the statistics below are not safe to read`, e i numeri di quella run non vanno
usati senza una spiegazione esplicita.

> ⚠ **`phi_consistent = FAIL` non è un difetto.** `Phi` è per costruzione una funzione dello stato
> della catena e **deve** variare nel tempo. Il controllo è una sonda tarata su run in cui la
> retroazione è spenta, ed è marcato non critico proprio per questo.

---

## 7. I grafici e come leggerli

Tutte le figure stanno in `<run>/analysis/plots/`, indicizzate da un `README.md` generato
automaticamente. **Sopra le 6 entità**, una figura che disegna una serie per entità diventa
illeggibile: in quel caso viene scritta **una figura per entità** in una sottocartella omonima.

### 7.1 La figura principale

| Figura | Assi | Come si legge |
|---|---|---|
| **`weight_vs_election.png`** | quota **spettante** → quota **osservata**, un punto per (validatore, epoca), più barre per epoca | è **la figura per cui l'esperimento esiste**. I punti dovrebbero disporsi lungo la diagonale. **Attenzione all'ampiezza dell'asse x**: se i punti formano una *striscia verticale*, le quote spettanti sono quasi tutte uguali e la run **non può** testare la proporzionalità — non è un difetto del sistema, è un limite dell'esperimento |

### 7.2 Peso ed elezione

| Figura | Assi | Come si legge |
|---|---|---|
| `weights_over_time.png` (+ cartella per miner) | epoca → peso | il peso grezzo, quello dopo il malus e quello dopo lo smorzamento **su pannelli separati**: i tre differiscono per esattamente le due trasformazioni che il protocollo applica, e vederli separati è come si capisce **quale stadio** ha spostato il peso |
| `weights_boxplot_per_epoch.png` | epoca → distribuzione del peso finale fra i miner | **una scatola che si allarga** = il motore sta separando i miner; **una mediana che deriva** = li sta muovendo tutti insieme |
| `election_share_distribution.png` | epoca → quota vinta, più torta cumulativa | chi ha vinto quanto, nel tempo e in totale |
| `concentration_over_time.png` | epoca → HHI / Nakamoto / Gini | **due linee**: teorica (dai pesi) e osservata (dai blocchi). **Il divario fra le due è una proprietà dell'elezione; una linea teorica che sale è una proprietà del motore del peso** |
| `esg_scores.png` (+ per ruolo) | entità → punteggio ESG certificato | il punto di partenza di tutto. Un miner senza punteggio certificato avrebbe peso 0 e renderebbe la lotteria uniforme |

### 7.3 Diagnostica peso ↔ elezione

| Figura | Assi | Come si legge |
|---|---|---|
| `p_value_uniformity.png` | p-value della bontà di adattamento → n. di epoche | sotto l'ipotesi nulla i p-value sono **uniformi**: l'istogramma dovrebbe essere piatto sulla linea attesa. **Un picco vicino a zero** = la *media* del modello è sbagliata; **un'inclinazione graduale verso sinistra** = è solo la *varianza* a essere sottostimata (tipicamente per dipendenza fra round, §5.4). Due diagnosi molto diverse |
| `wilson_violation_heatmap.png` | epoca × validatore, rosso = fuori intervallo | i totali di riga e colonna dicono **chi** e **quando**. Rosso sparso = caso; **una riga rossa continua** = quel validatore ha un problema persistente; **una colonna rossa** = quell'epoca ha qualcosa di anomalo |
| `residual_boxplot_by_validator.png` | validatore → distribuzione di `quota osservata − quota spettante` | **una scatola centrata su zero = validatore eletto al proprio tasso**. Uno scostamento costante verso l'alto o il basso è sovra- o sotto-rappresentazione **sistematica**, non rumore |
| `delay_recompute_mismatch.png` (+ per miner) | epoca → `|ritardo ricalcolato − ritardo loggato|` (scala logaritmica) | deve stare **molti ordini di grandezza sotto** la linea di tolleranza. Uno scarto di **circa un secondo esatto** su pochi round è un artefatto noto del modo in cui il nodo scrive i numeri in JSON, non un difetto della lotteria |

### 7.4 Corsa dei timer

| Figura | Assi | Come si legge |
|---|---|---|
| `margin_distribution.png` | margine fra i due ritardi più veloci (s) → densità | la forma attesa è decrescente (quasi esponenziale). Le due linee verticali sono la **media osservata** e quella **simulata**: devono coincidere |
| `sigma_decomposition.png` | sorgente → `sigma` in secondi | di cosa è fatto il disturbo. **Se `S1` (propagazione) è molto più piccolo di `S2` (scheduler), la rete non è la causa dominante** — ed è esattamente il confronto che i due regimi `native`/`core` esistono per permettere |
| `prop517_gap_by_validator.png` | vincitore → distacco standardizzato medio | tutte le barre dovrebbero stare sulla linea a **1**. Una sola barra fuori è quel validatore; **tutte** fuori è il meccanismo |
| `inversion_bound_vs_observed.png` | tre barre: limite teorico, simulazione, osservato | l'osservato **sotto** il limite è il risultato atteso, non un risultato debole. **Se il limite è saturo a 1,0 è vacuo** e il confronto utile è con la simulazione |
| `phi_over_time.png` | altezza di blocco → `Phi` | `Phi` sposta **tutti** i ritardi insieme, quindi da solo non può cambiare chi vince. La linea della **mediana mobile** è ciò che distingue una deriva lenta da un salto |

### 7.5 Motore del peso

| Figura | Assi | Come si legge |
|---|---|---|
| `rho_vs_next_weight.png` (+ per miner) | tasso di restituzione all'epoca `e` → peso pubblicato in `e+1` | l'unico canale di retroazione endogeno. **Guardare prima l'ampiezza dell'asse x**: se il tasso è schiacciato vicino a zero, la nuvola non può mostrare nulla |
| `rho_feedback_by_validator.png` | forza della correlazione per cluster | una dispersione attorno a zero su una run corta **è il quadro atteso, non un rilievo** |
| `gini_delta_trajectory.png` | epoca → `Gini(pubblicato) − Gini(input)` | **sopra zero** = i pesi pubblicati sono più diseguali degli ingressi che li hanno prodotti; **pendenza in salita** = il divario si allarga nel tempo |
| `traffic_per_epoch.png` | epoca → transazioni: pianificate / inviate / **sulla catena** | **il divario fra "inviate" e "sulla catena"** è il numero di pubblicazioni che la catena ha rifiutato — di solito per politica sulle commissioni — e deprime l'attività senza generare alcun errore visibile |
| `sign_test_by_validator.png` | validatore → p del sign test | con poche coppie il test **non può** raggiungere 0,05: una barra vicino a 1 di solito parla della **lunghezza della run**, non del validatore |
| `longitudinal_logratio.png` | `log(rapporto quote spettanti)` → `log(rapporto quote osservate)` | la retta stimata contro la diagonale. **La larghezza della nuvola dice quanto è corta la run**; lo scostamento della retta dalla diagonale dice quanto l'elezione si allontana dalla proporzionalità |

### 7.6 Malus *(riempite solo se l'esperimento con miner malevoli è stato eseguito)*

| Figura | Come si legge |
|---|---|
| `malus_action_funnel.png` | il funnel per tipo: quanto si perde fra tentativo, conferma e segnalazione |
| `malus_state_trajectory.png` | `M`, `Psi`, peso grezzo ed efficace dei miner malevoli, epoca per epoca: si vede l'accumulo e poi il decadimento |
| `malus_detection_latency.png` | ECDF delle latenze di rilevazione e attivazione: quanto tempo passa fra l'atto e la sua conseguenza |
| `malus_weight_effect.png` | variazione del peso efficace, malevoli contro onesti |
| `malus_invariant_audit.png` | epoca × validatore: **verde = invariante rispettato, rosso = violato**. Un solo rosso è un rilievo |

> Se l'esperimento non è stato eseguito, queste figure esistono ma riportano esplicitamente
> *"no malicious miner had a malus trajectory to plot"*. Non sono un errore.

---

## 8. Glossario delle colonne ricorrenti

| Colonna | Significato |
|---|---|
| `in_setup` | il round cade sotto `setup-first-blocks`, dove governa il round robin nativo di MultiChain: **da escludere da ogni test** |
| `epoch` | indice di epoca, `altezza // lunghezza_epoca` |
| `weight_raw` / `w_raw_*` | peso grezzo pubblicato dal motore |
| `malus` / `M` | accumulatore delle violazioni valide |
| `malus_factor` / `psi` / `Psi` | fattore di correzione comportamentale, in `[0,1]`. `1` = nessuna penalità |
| `weight_after_malus` | peso × `Psi` |
| `weight_effective` / `w_eff_*` | peso dopo **malus e smorzamento**: **è ciò che la lotteria consuma davvero** |
| `W_tot_effective` | somma dei pesi efficaci dei candidati eleggibili del round |
| `p_theoretical` | quota **spettante** = `peso efficace / W_tot` |
| `p_hat` / `p_observed` | quota **osservata** = blocchi vinti / blocchi dell'epoca |
| `O_i` | blocchi vinti dal validatore nell'epoca |
| `E_i` | **attenzione, due significati diversi**: in `round_scores`/`candidate_long` è il punteggio esponenziale grezzo; in `epoch_level`/`wpoa_epoch_validators` è il **conteggio atteso** di blocchi |
| `score` | punteggio della lotteria = `E_i / peso efficace` |
| `score_norm_public` | punteggio normalizzato in `(0,1)` nella forma pubblica, l'argomento della funzione di ritardo del *modello* |
| `score_norm_true` | lo stesso, ma dal punteggio **privato reale** del vincitore: `U(0,1)` se il vincitore è l'argmin |
| `delay_logged_public_s` | ritardo che la forma pubblica attribuisce al candidato |
| `delay_true_s` | ritardo a cui il punteggio reale del vincitore lo autorizzava |
| `residual_true_s` | `tempo reale fra i blocchi − delay_true_s`: il residuo di una grandezza contro sé stessa |
| `delay_recomputed_s` | lo stesso ritardo ricalcolato dall'harness |
| `margin_G_public_s` | distanza fra i due ritardi più veloci del round, forma pubblica |
| `phi_s` | termine di correzione globale, uguale per tutti i candidati del round |
| `inversion_public` | vero se a minare non è stato l'argmin **della forma pubblica**: vale `1 − 1/n` per costruzione, non è una misura del protocollo (regola 10 di §9) |
| `rank_by_score_public` / `rank_by_delay_public` | posizione in classifica del candidato nel round, forma pubblica |
| `is_winner` | **ha minato il blocco** — non necessariamente il vincitore della lotteria |
| `eligible` | il validatore poteva partecipare a quel round |
| `scheduler_residual_public_s` | `tempo reale fra i blocchi − ritardo pubblico del produttore`: differenza fra due estrazioni indipendenti, non un residuo di scheduler |
| `dt_prev_s` | tempo trascorso dal blocco precedente |
| `tau` / `miner_activity` | attività diretta del miner nell'epoca |
| `companies_contribution_sum` | somma dei contributi delle aziende del cluster |
| `W_k_raw` | peso grezzo del cluster |
| `rho` / `return_rate_rho` | tasso di restituzione = restituito / saldo disponibile |
| `w_k_published` | peso pubblicato sul registro, in **unità intere ×100** rispetto a `w_k_final` |

---

## 9. Come si legge un numero senza sbagliare

Dieci regole che valgono per ogni run.

1. **Mai giudicare su un singolo round, blocco o epoca.** Il sistema è stocastico su più livelli
   indipendenti: pesi derivati da punteggi ESG casuali, traffico casuale, VRF, e in regime `core`
   anche la rete. Solo le tendenze aggregate sono interpretabili.
2. **Correggere sempre per i confronti multipli.** Con `N` test a soglia 5 %, `0,05 · N` rigetti
   sono **attesi**. La pipeline fornisce già `expected_rejections`: usarlo.
3. **Dichiarare sempre la risoluzione.** Un intervallo largo non è un risultato. Se lo spread delle
   quote spettanti è molto minore della larghezza media dell'intervallo di Wilson, **quella run non
   può testare la proporzionalità**, e la sua assenza di evidenza non è evidenza di assenza.
4. **Escludere le epoche `in_setup`**: lì gira il round robin nativo, non wPoA.
5. **Trattare a parte l'ultima epoca**: è quasi sempre parziale, quindi con intervalli larghi e
   concentrazione apparente più alta.
6. **Un test etichettato *straw man* che rigetta non è un rilievo.** Vale per il KS contro
   `Beta(1, n)`.
7. **Zero non significa sempre la stessa cosa.** `S1 = 0` in regime `native` significa **assente**,
   non "piccola". Un tasso di rilevazione 0 su zero azioni non è lo stesso fatto di un tasso 0 su
   cinquanta. La pipeline restituisce `None` con una nota anziché `0` proprio per questo.
8. **Un limite superiore saturo a 1,0 è vacuo**, non una conferma.
9. **Prima di dichiarare un difetto, controllare l'indipendenza dei round.** Se `repeat_prob`
   eccede il valore atteso, i p-value nominali di Wilson e del chi-quadro sono troppo generosi:
   applicare la correzione per il VIF (§5.4). Molto spesso ciò che sembra uno scostamento è una
   varianza sottostimata.
10. **Verificare sempre che lo strumento misuri la grandezza privata reale, non la sua
    controparte pubblica ricomputabile.** Dove il protocollo usa un segreto — una chiave VRF,
    una chiave di firma — esiste quasi sempre una forma pubblica *della stessa formula* che
    chiunque può ricalcolare, e che una RPC di audit può offrire in buona fede. Non è la stessa
    variabile aleatoria: è **indipendente** da quella vera. Un test costruito sopra di essa
    restituisce il proprio valore nullo qualunque cosa faccia il protocollo, e lo restituisce con
    l'aria di un risultato.

    Il caso concreto di questa campagna: `round_scores` / `round_delays` provengono da
    `wpoalistscores` / `wpoalistdelays`, che assegnano il punteggio con la forma **pubblica**
    `HMAC-SHA256(seed, indirizzo)` — l'unica calcolabile per un validatore di cui non si possiede
    la chiave segreta. Sotto sortition privata l'elezione estrae invece da una VRF sotto la chiave
    di *ciascun* proponente. Di conseguenza `inversion_rate_public` vale `1 − 1/n` per
    costruzione (0,9103 misurato su `core-intercontinental` con n = 10, contro 0,90 previsto),
    `corr(block_time, delay_public)` vale 0, e `sigma_S2` non è un residuo di scheduler ma la
    deviazione standard della differenza fra due estrazioni indipendenti dalla stessa banda.
    Nessuno di quei numeri può mostrare il meccanismo rotto **né** funzionante.

    Regola operativa: prima di citare una metrica, risalire alla RPC che la alimenta e chiedersi
    *quale chiave serve per calcolare questa quantità*. Se la risposta è "una chiave che il nodo
    interrogato non ha", la metrica è un audit del modello, non una misura del protocollo. Le
    colonne affidabili portano il suffisso `_true` e nascono da `block_sortition`, dove il
    punteggio è ricomputato dal reveal VRF che il blocco vincente pubblica — l'unico candidato la
    cui grandezza privata è, a posteriori, pubblicamente verificabile. Quelle con suffisso
    `_public` restano nei file per tracciabilità all'indietro, non come evidenza.

### Parametri che possono mascherare il meccanismo

| Parametro | Se vale... | Conseguenza |
|---|---|---|
| `mining-diversity` | `> 0` | la regola nativa di spaziatura può diventare vincolante e **far collassare la distribuzione osservata sul round robin**, mascherando proprio ciò che si vuole misurare. I profili della campagna lo mettono a `0` |
| `setup-first-blocks` | — | sotto quell'altezza governa il round robin nativo |
| `initial-block-reward` | `0` | nessuna ricompensa da mining: se i miner non ricevono GAS, il tasso di restituzione resta nullo e **la retroazione fra epoche è inerte** |
| `weight-alpha` | qualsiasi | **parametro inerte**: il binario lo valida e non lo legge mai. Mantenuto solo perché rimuovere un campo protetto da hash renderebbe le catene esistenti non raggiungibili |
| `dump-function` | `log` | la funzione logaritmica **non è omogenea**, quindi la scala intera ×100 del registro **non si elide** e comprime ulteriormente i pesi efficaci. Con `none` e `sqrt` la scala è ininfluente |

---

## 10. Costanti e convenzioni

**Costanti metodologiche**, fissate nel codice (`test/analysis/pipeline/stat/`) e **non
configurabili dal profilo**:

| Costante | Valore | Cosa governa |
|---|---|---|
| `ALPHA` | `0.05` | soglia di significatività |
| `MC_GOF` | `20000` | estrazioni Monte Carlo per la bontà di adattamento |
| `MC_STREAK` | `10000` | estrazioni Monte Carlo per gli streak |
| `ANALYSIS_SEED` | `20260905` | seme del generatore **dei test** |

Il seme dell'analisi è **deliberatamente indipendente** da quello dell'esperimento: il seme del
profilo controlla la rete e il traffico, questo controlla i test. Due run con semi di rete diversi
restano così confrontabili sotto una procedura di test identica, e rieseguire l'analisi sugli stessi
dati riproduce esattamente gli stessi numeri.

**Convenzioni condivise da tutti i test:**

- I p-value Monte Carlo sono `(successi + 1) / (estrazioni + 1)`. Il `+1` mantiene la stima non
  distorta e **impedisce che venga mai riportato un p-value esattamente 0** per una simulazione
  finita.
- Una quantità non calcolabile è restituita come `None` con un campo `*_note` che spiega perché,
  **mai come `0` o `NaN`**: uno zero che significa "nessun dato" è indistinguibile da uno zero che
  significa "nessun effetto", e il secondo è un risultato.
- Nessuna dipendenza da `scipy` o `statsmodels`: coda del chi-quadro, distribuzione di Kolmogorov,
  *t* di Student, coda binomiale esatta e fit logit IRLS sono tutti calcolati dalle rispettive forme
  chiuse, accurate a circa `1e-12` — diversi ordini di grandezza più fini della risoluzione Monte
  Carlo che comunque limita i risultati.

**Come rigenerare l'analisi di una run già eseguita** (senza rifare la rete):

```bash
./docker/mcsim run python3 test/analysis/pipeline/phase1_collect.py   --run-dir <run>
./docker/mcsim run python3 test/analysis/pipeline/phase2_aggregate.py --run-dir <run>
./docker/mcsim run python3 test/analysis/pipeline/phase3_analyze.py   --run-dir <run>
./docker/mcsim run python3 test/plotting/generate_plots.py            --run-dir <run>
```

---

## Dove guardare per primo

Se si apre una run e si ha poco tempo, in quest'ordine:

1. **`analysis/phase3/report.md`** — l'intestazione dice subito se i controlli critici sono passati.
   Se dice `FAIL`, fermarsi lì: i numeri sotto non sono affidabili.
2. **I due test di casualità (§5.9)** — se falliscono, nient'altro conta.
3. **`analysis/phase3/weight_vs_election.md`** e **`plots/weight_vs_election.png`** — il confronto
   per cui l'esperimento esiste.
4. **`plots/p_value_uniformity.png`** — la forma dell'istogramma distingue in un colpo d'occhio
   «media sbagliata» da «varianza sottostimata».
5. **`analysis/phase3/timer_race.md`** — i test Q1/Q2 sul punteggio **vero** del vincitore
   (`true_corr_dt_delay`, `true_score_norm_mean`). Il tasso di inversione che segue è sulla forma
   pubblica: vale `1 − 1/n` per costruzione (regola 10 di §9).
6. **`analysis/ANALISI.md`**, se presente — l'analisi discorsiva di quella specifica run.

> Nota: `test/results/.gitignore` esclude dal versionamento tutto il contenuto della cartella,
> incluso questo file. È voluto: le run sono prove, non sorgenti. Per versionare questa guida va
> spostata altrove o aggiunta un'eccezione esplicita a quel `.gitignore`.
