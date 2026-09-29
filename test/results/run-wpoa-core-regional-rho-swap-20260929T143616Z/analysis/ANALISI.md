# Analisi della run run-wpoa-core-regional-rho-swap-20260929T143616Z

Run: `test/results/run-wpoa-core-regional-rho-swap-20260929T143616Z`
Timestamp UTC della run: 2026-09-29T14:36:16Z
Catena: `wpoa-core-regional-rho-swap` — profilo: `test/config/profiles/core/regional-rho-swap.yaml` — regime: core
Analisi prodotta il: 2026-09-29

> **Scopo della run: l'esperimento controllato sul tasso di restituzione `rho`.** In ogni
> altra run della campagna tutti i miner estraggono le restituzioni dallo stesso range, quindi
> `rho` differisce fra i miner solo per caso. Qui due miner con ESG e cluster quasi identici
> ricevono comportamenti opposti e se li **scambiano a metà run** (disegno crossover):
>
> | miner | epoche 1–14 | epoche 15–30 |
> |---|---|---|
> | miner-1 (1aqjwAwmci…, ESG 56, 6 aziende) | generoso: 16–20 restituzioni da 200–250 | tirchio: 0–2 da 50–100 |
> | miner-3 (1EXHKJyuBU…, ESG 55, 6 aziende) | tirchio | generoso |
> | miner-0, miner-2, miner-4 | range comune (0–20 da 50–250), controlli | range comune |
>
> Tutto il resto (seed, mappa, nodi, cluster, traffico, δ = 0,5, `lambda_w` = 0,99, parametri di
> catena) è identico a `regional-long23h-feedback`. Geometria 30×100 e funding dei miner
> (180 200) sono identici a `regional-d025` e `regional-d075`. La run è completa: `status = ok`,
> altezza 3124 su un target di 3120, 30 epoche misurate (2–31), 2 900 round wPoA. **Nessuna
> azienda è caduta al bootstrap** (6 aziende per cluster in tutte le 31 epoche).

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| nome catena, seed | `wpoa-core-regional-rho-swap`, 20260905 | `manifest.json` |
| regime, topologia | `core`, mappa `regional` (20 siti, 7 hub), latenza peggiore sul percorso 5,137 ms | `manifest.json` → `fabric` |
| nodi | 1 admin, 2 CA, 5 miner, 30 aziende (38), tutte attive | `manifest.json`; `phase2/epoch_engine.csv` |
| epoche | 30 da 100 blocchi; misurate 2–31, la 31 parziale (21 blocchi) | `manifest.json` |
| altezza finale / esito | 3124 (target 3120), `status = ok` | `manifest.json`, `shutdown.json` |
| smorzamento | `none` | `phase1/config.csv` |
| `target-block-time`, δ, λ | 8 s; 0,5 (`Delta_max` = 4 s); 0,3 | `phase1/config.csv` |
| bound del feedback `M` | `min(4; 8·0,5/0,3 = 13,3) = 4,0 s` | derivato |
| malus | attivo; `mu` 0,5, `M_max` 3; **nessuna violazione iniettata** | `phase1/config.csv`, `malicious_manifest.json` |
| weight engine | `kappa` 100, **`lambda_w` = 0,99**, `weight-alpha` 0,2 (inerte) | `phase1/config.csv` |
| `setup-first-blocks`, `mining-diversity` | 220; 0,0 | `phase1/config.csv` |
| `initial-block-reward` / premine | 0 / 3,5·10¹⁴ | `phase1/config.csv` |
| traffico | aziende 30–60 tx/epoca; range comune delle restituzioni [0, 20] × [50, 250] | `manifest.json` → `traffic` |
| **override delle restituzioni** | come nella tabella in testa | `manifest.json` → `traffic.miner_return_overrides` |
| funding dei miner | 180 200 ciascuno, uguale per tutti (dimensionato sul range massimo) | `manifest.json` → `derived.miner_seed_gas` |
| log | `sortition_miner_log`, `fork_score_log` attivi | `manifest.json` → `runtime` |

**ESG certificati:** miner-2 75, miner-1 56, miner-3 55, miner-4 49, miner-0 29.
**Pesi alla prima epoca misurata** (epoca 2, esito stocastico di `ESG × tau`, prima che il
trattamento entri nel peso): miner-4 9 181 (0,264), miner-3 7 868 (0,227), miner-2 7 699 (0,225),
miner-1 6 369 (0,182), miner-0 3 512 (0,101).

**GAS restituito in totale:** miner-3 67 538, miner-1 58 142, miner-2 55 733, miner-0 48 382,
miner-4 45 220.

## 2. Executive summary

- **`rho` arriva al peso e all'elezione, e il test lo dimostra.** Contro l'ipotesi "l'elezione
  segue lo stesso peso senza il fattore di `rho`", il rapporto di verosimiglianza sui 2 900 round
  vale +207,8, a **20,0 deviazioni standard** dalla sua media sotto quella nulla (−222,7 ± 21,6;
  p < 5·10⁻⁵). Sotto il modello con retroazione l'osservazione cade al quantile 0,43, cioè è un
  valore tipico. Il chi-quadro sui totali rigetta il modello senza retroazione (p = 0,0002) e non
  quello con (p = 0,80).
- **Lo scambio si vede sui singoli miner.**
  - miner-1 passa dal 28,1 % al **7,7 %** dei blocchi: −20,4 punti contro −20,0 previsti dal
    modello; senza retroazione se ne prevederebbero −3,0.
  - miner-3 passa dall'11,4 % al **36,9 %**: +25,4 punti contro +26,5 previsti; senza retroazione
    +2,9.
  - Rispetto al modello senza retroazione lo scarto vale z = −12,8 e +14,3; rispetto a quello con
    retroazione z = −0,3 e −0,7.
- **Ritardo esattamente quello previsto.** Lo scambio è dichiarato all'epoca 15 e arriva alle
  elezioni all'epoca 17: le restituzioni dell'epoca `e` entrano nel peso in vigore dall'epoca
  `e + 2`.
- **Il resto del meccanismo è pulito.** χ² aggregato 1,47 (p = 0,83); 8 violazioni di Wilson su
  150 (7,5 attese); 1 rigetto del GoF per epoca su 30; `E_i` privato 1,0046; score del vincitore
  uniforme (KS p = 0,51); block time 8,06 s; il malus non ha effetto.
- **Rilievo di implementazione (§5).** A h 2637 miner-2 ha rifiutato come invalido un blocco
  valido (`missing VRF reveal`) e lo ha marcato `BLOCK_FAILED_VALID`. La rete è poi convergita
  sul ramo di miner-2 con una riorganizzazione di profondità 2, la prima della campagna. Il
  blocco peggiore di h 2637 è quindi rimasto in catena. Un evento su 2 900 round, senza effetto
  sui risultati.

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **A.1, `E_i` pubblico** ([phase2/candidate_long.csv](phase2/candidate_long.csv)): n = 14 505,
  media **0,9996** (banda ±0,0163), `√n·D` = 0,864. **Conforme.**
- **A.2, argmin di `score_norm` pubblico:** 2 901 round, media 0,4873, `√n·D` = **1,554**, sopra il
  critico di 1,358 (p ≈ 0,02). **Lieve scostamento.** È lo score pubblico HMAC, indipendente da
  quello del voto: l'argmin sugli score privati è pulito (sotto). Sulla d075 era la media di
  `E_i` pubblico a uscire dalla banda; in due run lo scarto cade su due statistiche diverse della
  stessa forma pubblica. Non tocca l'elezione, ma è da tenere d'occhio.
- **Score privati** (`analysis/private/priv.json`, 5 miner su 5, 2 898 round completi): `E_i`
  media **1,0046** (banda ±0,0163), `√n·D` = 0,636; argmin di `score_norm` media 0,5034,
  `√n·D` = 0,791. **Conforme.**
- **Q2** ([phase3/timer_race.md](phase3/timer_race.md)): score del vincitore vero, media 0,5036,
  KS p = **0,514** (round in corsa: 0,4991, p = 0,678). **Conforme.**
- **Prop. 5.17** ([phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv)): miner-2 (18UgQcEGcW…)
  1,034; miner-0 (1AGTXj8maw…) 1,031; miner-3 (1EXHKJyuBU…) 0,962; miner-4 (1TM3NZRQ46…) 1,090;
  miner-1 (1aqjwAwmci…) 0,934. Nessun KS sotto 0,05. **Conforme.**
- **A.3:** mismatch di `score_norm` massimo 5,1·10⁻¹⁵, 0 righe su 14 505. **Conforme.**

### 3.2 Correttezza meccanica del delay

0 righe su 14 505 oltre 1,5 ms, massimo 4,1·10⁻¹⁴ s
([phase3/consistency_checks.csv](phase3/consistency_checks.csv),
[plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)). **Conforme.**

### 3.3 Quota di blocchi contro peso

- **Aggregato** ([phase3/weight_vs_election.md](phase3/weight_vs_election.md)): sui 2 898 blocchi
  wPoA χ² = 1,70, TV = 0,0093. Quote spettanti e osservate: miner-2 0,2651/0,2571, miner-3
  0,2432/0,2419, miner-4 0,2310/0,2315, miner-1 0,1725/0,1798, miner-0 0,0882/0,0897. Riga `all`
  della pipeline: χ² 1,47, p = 0,83. **Conforme.** Le quote aggregate di miner-1 e miner-3 sono
  medie di due regimi opposti: il confronto informativo è per fase, in §3.13.
- **Wilson** ([phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv)):
  **8 violazioni su 150** (7,5 attese, binomiale p = 0,48), sparse fra 5 miner e 7 epoche;
  larghezza media 0,15. **Conforme.**
- **GoF per epoca:** 1 rigetto su 30 (epoca 15, p = 0,016; 1,5 attesi); p-value uniformi
  (KS p = 0,46). Residuo standardizzato con deviazione standard **0,996**. **Conforme.**
  La sovradispersione vista sulla d075 (5/30, deviazione standard 1,12) qui non c'è: rafforza
  l'ipotesi che là fosse una fluttuazione.
- **Epoca 2** (21 blocchi di setup): sui 79 blocchi wPoA χ² = 1,58, nessun artefatto.

### 3.4 Comportamento longitudinale

GLM β1 = **1,091** [1,016; 1,166], "NOT consistent" rispetto a 1, ma la nulla simulata sulle
quote reali è **1,112** [1,036; 1,187]: conforme, l'H0 fissa è mal specificata. Log-rapporti:
pendenza **1,004**, intercetta −0,021, r = 0,918 (296 coppie). Sign test: p = 0,002 (miner-1),
0,006 (miner-3), 0,026, 0,16, 0,29. I due miner trattati, con i pesi che si muovono di più,
danno il segnale più forte. **Conforme.**

### 3.5 Timer race, margine e inversioni

- **Q1:** `corr(dt_prev, delay_true)` = 0,983; residuo 0,055 ± 0,431 s, costante per terzi (0,429 /
  0,430 / 0,434). **Conforme.**
- **Margine:** pubblico 2,371 s, KS contro la simulazione esatta p = 0,112, contro `Beta(1,n)`
  p = 0 (straw man); privato 2,33 s. **Conforme.**
- **`sigma`:** `S1` 0,000377 s; `S2` pubblico 3,22 s; bound pubblico saturato a 1 (**vacuo**);
  "inversioni" pubbliche 74,6 % (artefatto dello score pubblico). Il tasso reale è in §3.5.1.
- **Vantaggio dell'uscente:** ripetizione 0,2635 contro 0,2565 (p = 0,21); il designato privato
  coincide con l'uscente nel 26,3 % dei round contro il 25,5 % atteso; timer ancorato al padre
  in 15 742 righe su 15 742. **Conforme.**

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Fonte: `chains/miner-{0..4}/.../debug.log`, analizzati con `analysis/private/priv.py`, lo stesso
script di d025 e d075. Copertura: 5 miner su 5, 2 898 round su 2 900.

- **(a)** Quote designate contro spettanti: χ² = 1,61 (p ≈ 0,81). **Conforme.**
- **(b) Inversioni reali: 5 su 2 898 (0,17 %)**, più quella di h 2637 descritta in §5, che
  `blocks.csv` non registra: in totale 6 (0,21 %). Quattro delle cinque (h 2355, 2952, 3033,
  3077) sono round vinti **al bordo alto della banda**: i timer dei primi candidati stanno fra
  11,85 e 12,0 s e distano pochi millisecondi (h 2355: 11,848 contro 11,848 s). Per la
  Prop. 5.11 circa l'1 % dei round cade lì per costruzione (qui 26 round, 0,9 %), e in quei
  round la latenza decide. Una sola (h 1286) è un'inversione ordinaria, con margine 0,27 s. Una
  sola va all'uscente. La concentrazione nell'ultimo terzo (0 / 1 / 4) su 5 eventi non è
  interpretabile. **Conforme.** Il tasso è come in d025 (0,21 %), sopra la d075 (0), sotto
  `regional-feedback` sull'intera run (0,31 %).
- **(c) Fork:** 19,2 % dei round (557), con 897 orfani. **In 556 fork su 557** la catena tiene il
  blocco di score minimo. L'eccezione (h 2638) confronta due blocchi con genitori diversi, e
  quindi seed diversi: non è una fork fra fratelli ma la coda dell'evento di h 2637 (§5).
  Primo arrivo diverso dal designato in 268 round (9,2 %); la regola nativa avrebbe scelto il
  blocco finale nel 62,3 % delle valutazioni contese, quella per score nel 99,9 %. Le `displace`
  vanno tutte verso lo score migliore; 336 `defer`, nessun rilascio per scadenza.
  Riorganizzazioni: tutte di profondità 1, **tranne una di profondità 2** su quattro nodi,
  alle 20:31:04 (§5). Permanenza massima su un blocco poi orfano: 3,4 s, lo stesso evento.
  **Lieve scostamento**, per l'evento isolato.
- **(d) Prop. 5.18:** il rumore simmetrico con σ ≈ 0,35 s dà il 9,8 % di inversioni istantanee
  contro il 9,2 % osservato, e il 28,7 % all'uscente fra gli eleggibili contro il 27,0 %
  osservato (54/200). **Conforme**, in linea con `regional-feedback` (stessa δ).

### 3.6 Stabilità del block time e correzione globale

`dt_prev` medio **8,064 s** (deviazione standard 2,38; per terzi 8,11 / 8,00 / 8,08; per epoca
7,75–8,44). `Phi`: media −0,062 s, deviazione standard 0,609 s, range [−2,08; +1,83] s, 0 round
a ±M, 10,6 % di cambi di segno. `phi_consistent = FAIL` è atteso. **Conforme.** È lo stesso
profilo della run `regional-feedback` (8,07 s, deviazione standard 2,41 s): il trattamento
economico non tocca la temporizzazione.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **Identità del motore:** errore massimo 2,4·10⁻¹⁶ su `W_k_raw` e 9,4·10⁻¹⁵ sulla ricorsione;
  ESG costanti; 129 verifiche `ok` su 130. L'unica diversa è un campione a h 405 in cui il
  record più recente di miner-4 era già quello dell'epoca successiva (`other-epoch`, 0 invalid).
  **Conforme.**
- **Retroazione `rho → peso`:** Spearman lag-1 aggregata **0,754** (p ≈ 0, n = 150), contro 0,60
  della d075 e circa 0 nelle run con `lambda_w` = 0,5. `rho` ha media 0,0101 e arriva fino a
  0,029. Il fattore `0,99·rho + 0,01` va da 0,010 a 0,038. Nella figura
  [plots/rho_effect_weight.png](plots/rho_effect_weight.png) il pannello (a) mostra `rho` dei
  due miner trattati su due livelli netti (≈0,022 e ≈0,0005) che si scambiano all'epoca 17,
  mentre i controlli oscillano fra 0 e 0,019. **Conforme.**
- **`gini_delta`:** pendenza **positiva**, 0,0035 per epoca (Spearman 0,60, p = 0,0003). **Atteso
  per disegno, non un difetto del motore.** Dal secondo periodo il miner reso generoso è
  miner-3, che ha già il peso grezzo più alto dei due: la retroazione allarga il divario rispetto
  agli input ESG×tau, mentre nel primo periodo lo riduceva. È l'effetto del trattamento
  misurato con un'altra statistica.

### 3.8 Concentrazione

Aggregato: HHI teorico 0,2203 contro osservato 0,2184, N_eff 4,58, Nakamoto(1/2) = 2, Gini
osservato 0,159. **Conforme.** Per periodo la concentrazione cambia col trattamento:
miner-3 generoso arriva a una quota spettante di 0,44 in un'epoca.

### 3.9 Streak e ripetizioni

`L_max` aggregato 7 contro 7,65 (p = 0,84); ripetizione 0,2635 contro 0,2565 (p = 0,21); per
epoca nessun rigetto su `L_max` e uno sulla ripetizione (epoca 27). **Conforme.**

### 3.10 Malus

Caso J.1: M = 0 e Psi = 1 in 155 celle su 155, invarianti veri, nessuna rilevazione; il file
`malus_effectiveness.md` non esiste. **Conforme.**

### 3.11 Correlazione guadagno/transazioni e rielezione

- **Punto 1:** la correlazione con i blocchi vinti è alta e mediata dal peso: `w_k_published`
  0,85, `earnings_g_k` 0,64, `W_k_raw` 0,59.
- **Punto 2:** sui residui, tutte le correlazioni stanno fra −0,06 e +0,03 (p ≥ 0,47), **compresi
  `rho` e `R_k`**. **Conforme.** È la verifica chiave per questa run: `rho` agisce **solo**
  attraverso il peso. A parità di peso spettante, restituire di più non dà nessun vantaggio
  ulteriore.

### 3.12 Integrità della run

- **Controlli critici:** 7 su 7 PASS. Fra i non critici, `phi_consistent` FAIL è atteso;
  `certified_scores_reflected_in_the_engine` è PASS (nessuna azienda caduta);
  `traffic_counts_within_configured_range` è PASS su 1 015 coppie, verificate con i range **per
  miner e per epoca**, quindi anche l'override è stato rispettato dai daemon.
- **Errori RPC:** 408, tutti fra 14:36 e 14:50Z, cioè "Round not evaluable" del bootstrap.
- **`true_winner_mismatch`:** 0. Tuttavia `blocks.csv` registra a h 2637 il blocco rimasto
  orfano (§5): è il residuo noto del difetto del blocco orfano, qui dovuto a una
  riorganizzazione più profonda del margine di assestamento del collector. **Lieve scostamento.**

### 3.13 Esperimento controllato su `rho`

Fonte: [phase3/rho_contrast.md](phase3/rho_contrast.md) e i file `rho_contrast_*.csv`; figure
[plots/rho_effect_weight.png](plots/rho_effect_weight.png) e
[plots/rho_effect_election.png](plots/rho_effect_election.png).

- **Cosa misura:** ogni round è confrontato con due ipotesi.
  - Con retroazione: le quote che l'elezione ha usato.
  - Senza retroazione: lo stesso peso diviso per il fattore `0,99·rho_prev + 0,01`, cioè ciò che
    il motore avrebbe pubblicato con `lambda_w` = 0, a parità di ESG, `tau`, malus e smorzamento.
  
  Ogni peso è ricondotto alla riga del motore che l'ha prodotto (2 900 round su 2 901, l'ultimo
  non è stato minato).
- **Test di verosimiglianza:** LLR = **+207,8**. Sotto "nessuna retroazione" la media è −222,7
  (deviazione standard 21,6), quindi l'osservato sta a **20,0 deviazioni standard** (p < 5·10⁻⁵,
  il minimo della simulazione con 20 000 estrazioni). Sotto "con retroazione" la media è +211,3
  ± 19,7 e l'osservato cade al quantile **0,43**.
- **Chi-quadro sui totali, round per round:**

  | ambito | con retroazione | senza retroazione |
  |---|---:|---:|
  | tutta la run (2 900 round) | χ² 1,61, p = 0,80 | χ² 25,1, p = 0,0002 |
  | periodo 1 (miner-1 generoso, 1 400 round) | 1,78, p = 0,78 | 171,6, p < 0,0001 |
  | periodo 2 (miner-3 generoso, 1 414 round) | 1,49, p = 0,83 | 152,2, p < 0,0001 |

- **Quote per miner e fase trattata:**

  | miner | fase | `rho` in vigore | spettante senza retroazione | spettante con retroazione | osservata [Wilson 95 %] |
  |---|---|---:|---:|---:|---|
  | miner-1 | generoso | 0,0219 | 0,168 | 0,273 | **0,281** [0,258; 0,305] |
  | miner-1 | tirchio | 0,0010 | 0,137 | 0,073 | **0,077** [0,064; 0,092] |
  | miner-3 | tirchio | 0,0002 | 0,211 | 0,111 | **0,114** [0,099; 0,132] |
  | miner-3 | generoso | 0,0229 | 0,240 | 0,376 | **0,369** [0,344; 0,394] |
  | miner-0 | comune | 0,0086 | 0,095 | 0,088 | 0,090 [0,080; 0,102] |
  | miner-2 | comune | 0,0097 | 0,272 | 0,265 | 0,258 [0,242; 0,274] |
  | miner-4 | comune | 0,0082 | 0,254 | 0,231 | 0,231 [0,216; 0,247] |

  In tutte e sette le righe la quota osservata sta nell'intervallo attorno al valore con
  retroazione (|z| ≤ 0,93). Contro il valore senza retroazione i due miner trattati stanno a
  z = +11,3, −6,6, −8,9 e +11,3.
- **Variazione dentro lo stesso miner** (ESG e cluster si elidono):
  - miner-1, da generoso a tirchio: −20,4 punti osservati, −20,0 previsti con retroazione, −3,0
    senza (z contro la nulla senza retroazione −12,8).
  - miner-3, da tirchio a generoso: +25,4 osservati, +26,5 previsti, +2,9 senza (z = +14,3).
- **Controlli:** i tre miner con il range comune restano al loro posto; la differenza fra le due
  ipotesi per loro è piccola, perché la loro `rho` sta vicino alla media.
- **Giudizio: conforme.** La retroazione di `rho` agisce sul peso e sull'elezione esattamente
  nella misura prevista dal modello, con il ritardo di due epoche previsto dall'allineamento del
  motore. In assenza di retroazione i dati sarebbero incompatibili a 20 deviazioni standard.

## 4. Punti di forza

- **Effetto causale di `rho` isolato e misurato.** Stesso miner, stessi ESG e cluster: uno
  scambio di comportamento sposta la quota di −20,4 e +25,4 punti, contro −20,0 e +26,5 previsti.
  L'ipotesi "nessuna retroazione" è esclusa a 20 deviazioni standard.
- **`rho` agisce solo attraverso il peso:** i residui rispetto al peso spettante non dipendono
  da `rho` né da `R_k` (|r| ≤ 0,04).
- **Proporzionalità, randomness e meccanica come nelle run di riferimento:** χ² p = 0,83,
  deviazione standard del residuo standardizzato 0,996, `E_i` privato 1,0046, Q2 p = 0,51,
  delay mismatch 0.
- **Nessuna azienda caduta al bootstrap**, a differenza delle cinque run da 38 nodi precedenti
  (le due `whale-none`, `whale-sqrt`, d025 e d075).

## 5. Punti critici / da approfondire

- **Rifiuto spurio di un blocco valido e riorganizzazione di profondità 2 (h 2637–2639).**
  1. A h 2637 miner-3 produce `0079a4…` (score 1,743·10⁻⁵). Tutti i nodi lo verificano
     (`verify OK`), **tranne miner-2**, che lo scarta con `VerifyBlockMinerWPoA: REJECT …
     missing VRF reveal (sortition)` nello stesso secondo in cui costruisce il proprio blocco
     alla stessa altezza (`00236788…`, score 1,868·10⁻⁵).
  2. `AcceptBlock` marca il blocco scartato `BLOCK_FAILED_VALID`, quindi miner-2 non può più
     accettare nessuna catena che lo contenga, e prosegue sul proprio ramo a h 2638 e 2639.
  3. A h 2639 gli altri nodi confrontano per score due punte con antenati diversi e scelgono
     quella di miner-2. Quattro nodi fanno una riorganizzazione di profondità 2, e il blocco
     peggiore di h 2637 entra nella catena finale.
  - *Entità:* un'inversione in più su 2 900 round, nessun effetto misurabile sulle quote.
    Potenzialmente però grave: se la rete fosse rimasta sull'altro ramo, miner-2 sarebbe
    rimasto isolato in modo permanente.
  - *Causa più probabile, da confermare:* `FindBlockVRF` (`src/protocol/multichainblock.cpp`)
    legge il coinbase attraverso il buffer globale `mc_gState->m_TmpScript1`, lo stesso che
    usa `FindSigner`, raggiungibile anche dai thread RPC (`rpcblockchain.cpp`). Il codice stesso
    avverte, in `randao_accumulator.cpp`, che quel buffer non va toccato fuori dal percorso di
    validazione, e per questo l'estrazione del reveal lì usa una copia locale
    (`WPoAExtractBlockReveal`).
  - *Serve:*
    1. far usare a `FindBlockVRF` un `mc_Script` locale, come `WPoAExtractBlockReveal`;
    2. non marcare `BLOCK_FAILED_VALID` un blocco per un errore di lettura del reveal, ma
       rifiutarlo in modo transitorio;
    3. limitare il confronto per score alle punte con lo stesso genitore.
    
    Poi verificare su una run lunga che non si ripeta.
- **`blocks.csv` registra a h 2637 il blocco orfano:** è il residuo del difetto del blocco orfano
  con una riorganizzazione più profonda del margine di assestamento del collector. Effetto: un
  blocco su 2 900.
- **Argmin di `score_norm` pubblico con `√n·D` = 1,55:** riguarda la forma pubblica HMAC, non
  quella del voto (pulita). Insieme all'`E_i` pubblico della d075 va controllato con un test
  mirato sulla funzione HMAC della pipeline.
- **GLM "NOT consistent":** di nuovo l'H0 mal specificata (nulla simulata 1,112 [1,036; 1,187]).

## 6. Conclusione

- **Affidabilità della sortition: conforme.** χ² p = 0,83; 8/150 violazioni di Wilson; 1/30
  rigetti per epoca; inversioni reali 0,21 %.
- **Qualità della randomness: conforme** sugli score del voto (`E_i` 1,0046, Q2 p = 0,51); lieve
  scostamento sulla forma pubblica.
- **Smorzamento:** non applicabile.
- **Malus: conforme**, effetto nullo in 155/155 celle.
- **Block time: conforme**, 8,06 s, `Phi` mai saturato.
- **Retroazione di `rho`, lo scopo della run: conforme e dimostrata.** Restituire di più alza il
  peso e le elezioni del miner nella misura prevista dal modello, con due epoche di ritardo, e
  smettere di restituire le abbassa. L'ipotesi opposta è esclusa a 20 deviazioni standard.

Il solo punto aperto di rilievo riguarda l'implementazione: un rifiuto spurio e permanente di un
blocco valido, con una causa candidata precisa e una correzione identificata.
