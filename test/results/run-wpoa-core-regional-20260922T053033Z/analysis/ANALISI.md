# Analisi della run run-wpoa-core-regional-20260922T053033Z

## 0. Avvertenza preliminare — cosa questa run NON può dire

Due limiti vanno dichiarati prima dei numeri, perché delimitano le conclusioni possibili.

**Il tie-break di fork choice era DISATTIVO.** La riga di comando dei nodi
(`chains/*/daemon.out`) non contiene `-enablewpoaforkscore=1`: il flag è default-off e il
profilo `regional-medium15h.yaml` non imposta `runtime.fork_score`. La regola di
ordinamento in vigore in questa run è quindi quella **pre-wPoA, per ordine di arrivo**
(`nSequenceId`). Nessuna affermazione sul rispetto del tie-break by score è ricavabile da
qui.

**Le categorie di debug erano tutte spente.** Nessun `-debug=wpoafork`, nessun
`-debug=wpoa`, nessun `-debug=mcblock`. Conseguenze operative:

- non esiste l'istrumentazione per-candidato dei round contesi;
- non esistono le righe `[wpoa-sortition] verify OK` (quindi niente analisi di divergenza
  `weff`/`as_of` fra nodi, come fatta sulla run di validazione);
- **i reorg non sono loggati**: `Possible reorg` e `Same-height reorg` stanno sotto
  `LogPrint("mcblock", ...)` con `fDebug` (src/core/main.cpp:4105-4108). I 28 debug.log
  contengono **zero** righe `mchn-block`, il che conferma che la categoria era assente.
  Un conteggio di reorg pari a zero da questi log è **vacuo, non è evidenza**.

Ciò che invece è pienamente valido: la correzione di **height-scoping** è incondizionata
(nessun flag), quindi era attiva per l'intera run, e i suoi effetti sono misurabili.

## 1. Configurazione della run

| | |
|---|---|
| profilo | `core/regional-medium15h.yaml` |
| topologia | `regional.yaml` — 20 siti, 34 cavi, one-way 0.75–2.41 ms |
| nodi | 28 (1 admin, 2 CA, 5 miner, 20 company) |
| target-block-time | 12 s |
| delta / lambda | 0.5 / 0.3 |
| dumping | **none** |
| setup-first-blocks | 277 |
| epoche | 30 × 150 previste — **19 misurate** |
| altezza finale | **2884** su 4670 (run interrotta) |
| stato | `interrupted` — SIGINT dell'operatore, teardown completo |

L'interruzione è volontaria e pulita: 28/28 nodi fermati via RPC, snapshot finale
acquisito, pipeline eseguita per intero. Il dataset è integro, solo più corto del previsto.

## 2. Executive summary

Il meccanismo di sortition privata **funziona in modo dimostrabile** su 19 epoche: il
delay effettivo governa la spaziatura dei blocchi (corr = 0.978) e il vincitore medio è
l'argmin del campo (`score_norm` medio 0.50007 contro 0.5 teorico). La correttezza
meccanica è esatta: **zero** mismatch di ricalcolo del delay su 2729 round.

Il punto aperto è distribuzionale: il test KS di uniformità su `score_norm` del vincitore
**rifiuta** (p = 0.02045 aggregato, p = 0.00488 sui soli round in gara). La media è
perfetta, la forma no.

Si è osservata competizione same-height in **96 round su 2729 (3.52%)**, distribuita
uniformemente su tutte le epoche. Nessun blocco è stato rifiutato: zero `mined too early`,
zero `REJECT` su tutti i 28 nodi.

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)
Copertura Wilson: **85 intervalli su 95** contengono la quota spettante (attesi ~4.8
fallimenti per caso ad alpha = 0.05; osservati 10). Goodness-of-fit rifiutato in **4 epoche
su 20**. Ampiezza media dell'intervallo 0.1244 — con 5 miner e 150 blocchi per epoca la
risoluzione è limitata, quindi un eccesso modesto di fallimenti non è di per sé diagnostico.

### 3.2 Correttezza meccanica del delay
**Il risultato più solido della run.** `delay_recompute_mismatch_rounds_is_zero`: PASS, il
delay ricalcolato dalla pipeline coincide con quello registrato dal nodo in **ogni** round
(tolleranza 0.0015 s), e `n_delay_mismatch_public` = **0** su 2729 round.

Questo è anche una conferma indipendente della correzione di height-scoping: su 19 epoche,
con la registry che si muove a ogni confine di epoca, nodo e pipeline concordano sempre su
quale mappa dei pesi governava ciascun round.

| quantità | valore | atteso se funziona |
|---|---:|---:|
| corr(dt_prev, delay_true) | **0.97776** | ~1 |
| residuo medio (s) | 1.19219 | ~0 |
| residuo sd (s) | 0.73339 | ~sigma S1 |

### 3.3 Quota di blocchi contro peso
85/95 intervalli coprono la quota attesa; GoF rifiutato in 4/20 epoche. Vedi
`weight_vs_election.md`.

### 3.5 Timer race, margine e inversioni
| quantità | valore | atteso |
|---|---:|---:|
| round con score reale | 2511 | |
| `score_norm` medio del vincitore | **0.50007** | 0.5 |
| KS vs U(0,1), p | **0.02045** | non rifiutato |
| round in gara | 2436 | |
| — KS sui soli round in gara, p | **0.00488** | non rifiutato |
| vinti al top della banda | 75 (2.88%) | |

La media è praticamente esatta, il che è forte evidenza che l'argmin vince. Ma il KS
rifiuta **anche escludendo** i round vinti al top della banda, che è la correzione che il
prompt stesso prescrive. Quindi il rifiuto non è spiegato dal solo effetto liveness.

Tutte le metriche `_public` (inversion rate 0.789, bound 1.0) sono **non diagnostiche** per
costruzione: sotto sortition privata lo score pubblico è statisticamente indipendente da
quello che ha armato i timer. Il KS contro la distribuzione esatta simulata — il test di
riferimento — **non rifiuta** (p = 0.667).

### 3.6 Stabilità del block time
sigma S1 (topologia) = 0.000377 s, trascurabile su questa mappa regionale. Il residuo medio
di 1.19 s indica un bias sistematico positivo rispetto al delay previsto.

### 3.7 Pesi e retroazione inter-epoca
Spearman lag-1 rho = 0.1264 (p = 0.2352, n = 90): **nessuna** retroazione endogena
significativa. Traiettoria Gini(pubblicato) − Gini(input): pendenza 0.000016 (p = 0.8529) —
il motore non concentra il peso oltre la disuguaglianza dei propri input.

### 3.8 Concentrazione
HHI osservato 0.2240 contro 0.2241 teorico su tutta la run: **aderenza quasi perfetta**.
N_eff 4.46 su 5 validatori, Gini 0.1917, Nakamoto 1/2 = 2 stabile su tutte le epoche.

### 3.12 Integrità e consistenza
**Overall: PASS — ogni check critico regge.** Unico FAIL: `phi_consistent` (64 valori
distinti di Phi), non critico e presente identico nelle run precedenti — non è
conseguenza dell'interruzione.

## 4. Punti di forza
- Correttezza meccanica del delay **esatta** su 2729 round, e con essa la conferma
  indiretta dell'height-scoping su 19 epoche.
- Accoppiamento delay/spaziatura fortissimo (0.978).
- Concentrazione osservata aderente alla teorica a 4 decimali.
- Zero blocchi rifiutati, zero mismatch di ricalcolo.
- Interruzione e teardown puliti: dataset integro.

## 5. Punti critici / da approfondire
1. **KS su `score_norm` rifiuta anche sui round in gara** (p = 0.00488). La media è 0.500
   ma la forma no. Da indagare: è l'ipotesi più interessante aperta dalla run.
2. **Residuo medio +1.19 s** rispetto al delay previsto: bias sistematico da spiegare.
3. **96 round con competizione same-height** risolti per ordine di arrivo, non per score:
   è esattamente la popolazione su cui il tie-break agirebbe, e qui era spento.
4. **Nessuna verifica di convergenza cross-node**: `node_state.csv` campiona il solo admin
   e lo snapshot finale è dell'admin. L'assenza di fork persistenti non è dimostrata.
