# Analisi della run run-wpoa-core-regional-whale-none-20260928T170302Z

Run: `test/results/run-wpoa-core-regional-whale-none-20260928T170302Z`
Timestamp UTC della run: 2026-09-28T17:03:02Z
Catena: `wpoa-core-regional-whale-none` — profilo: `test/config/profiles/core/regional-whale-none.yaml` — regime: core
Analisi prodotta il: 2026-09-29

> **Run completa.** Questa run ripete da capo `regional-whale-none` con lo stesso seed, dopo che
> la run `run-wpoa-core-regional-whale-none-20260927T140026Z` era stata interrotta da un blackout a
> h 1627 (15 epoche su 50). Qui `status = ok`, `final_height` 5124 contro un target di 5120, 50
> epoche wPoA misurate (2–51, l'ultima parziale con 21 blocchi) e **4 900 round wPoA**. Questo
> report sostituisce integralmente quello della run interrotta, i cui numeri non vanno più citati.

> **⚠ Difetto dell'harness, ripetuto: due aziende non hanno mai partecipato.** I nodi
> `company-13` (cluster di miner-2) e `company-27` (cluster di miner-1) non rispondevano all'RPC al
> momento della registrazione della membership (`weightregistermembership: Connection refused`, 2
> righe in [phase1/rpc_errors.csv](phase1/rpc_errors.csv)). Il loro `events.jsonl` è vuoto. Effetto:
> la balena (miner-2) lavora con **17 aziende invece di 18**, e miner-1 con **2 invece di 3**
> (`n_companies` in [phase2/epoch_engine.csv](phase2/epoch_engine.csv)). Lo scenario "balena contro
> quattro piccoli" resta intatto, e tutte le quote spettanti sono calcolate sui pesi effettivamente
> pubblicati.

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-regional-whale-none` | `manifest.json` → `chain_name` |
| seed dell'esperimento | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/regional-whale-none.yaml` | `manifest.json` → `profile_path` |
| regime | `core` (rete emulata CORE) | `manifest.json` → `fabric.backend` |
| topologia | `regional`: 20 siti, 7 hub, 34 link; latenza peggiore sul percorso 5,137 ms | `manifest.json` → `fabric.topology`, `derived.worst_path_delay_ms` |
| nodi | 1 admin, 2 CA, 5 miner, 30 aziende (38); **28 aziende effettivamente attive** | `manifest.json` → `nodes`; `phase2/epoch_engine.csv` |
| composizione dei cluster | miner-2: 18 da profilo, **17 effettive**; miner-1: 3 da profilo, **2 effettive**; miner-0, miner-3, miner-4: 3 | `clusters.json`, `phase2/epoch_engine.csv` |
| epoche | 50 da 100 blocchi; misurate 2–51 (epoca 1 in setup), la 51 parziale (21 blocchi) | `manifest.json` → `epochs`, `measured_epochs`; `phase3/report.md` |
| altezza finale / esito | 5124 (manifest), 5125 allo snapshot di chiusura; target 5120; `status = ok`, `error` vuoto | `manifest.json`, `shutdown.json` |
| **funzione di smorzamento** | `none` → `g(w) = w` | `phase1/config.csv` → `dump-function` |
| `target-block-time` | 8 s | `phase1/config.csv` |
| banda del delay `delta` | 0,5 → `Delta_max = 4,0 s` | `phase1/config.csv` → `wpoa-sortition-delta` |
| guadagno della correzione `lambda` | 0,3 | `phase1/config.csv` → `wpoa-sortition-lambda` |
| bound del feedback `M` | `min(0,5·8; 8·0,5/0,3) = min(4; 13,33) = 4,0 s` | derivato |
| parametri malus | `mu` 0,5; `M_max` 4; punti equiv 4, badweight 2, selfwrite 1, delay 0,25 | `phase1/config.csv` |
| stato del malus | meccanismo **attivo** (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`) | `phase1/config.csv`; `malicious_manifest.json` |
| weight engine | `weight-kappa` 100; `weight-lambda` (= `lambda_w`) 0,5; `weight-alpha` 0,2 (**inerte**) | `phase1/config.csv` |
| `setup-first-blocks` | 220 effettivo (220 richiesto) | `phase1/config.csv`; `manifest.json` → `effective_setup_first_blocks` |
| `mining-diversity` | 0,0 (non vincolante) | `phase1/config.csv` |
| `mining-turnover` | 0,5 (euristica locale, nessun effetto su wPoA) | `phase1/config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10¹⁴ (premine) | `phase1/config.csv` |
| traffico | `supply-chain-events`; 30–60 tx per azienda per epoca; 0–20 restituzioni per miner per epoca; importi 50–250; ESG in [1,100] | `manifest.json` → `traffic` |
| lookback RANDAO | 101 | `phase1/config.csv` → `wpoa-randao-lookback` |
| log di runtime | `wpoa_debug: false`, `fork_score_log: true`, `sortition_miner_log: true` | `manifest.json` → `runtime` |
| piano malicious | `enabled = false`, 0 miner, rate 0 | `malicious_manifest.json` |

`params.dat` riletto dalla catena ([phase1/config.csv](phase1/config.csv)) e `manifest.json`
concordano su tutti i parametri di protocollo.

**ESG certificati** (35 pubblicazioni, tutte arrivate sullo stream): miner-2 **75**, miner-1 56,
miner-3 55, miner-4 49, miner-0 29 ([phase1/esg_events.csv](phase1/esg_events.csv)).

**Pesi effettivi alla prima epoca misurata (epoca 2).** Non sono una configurazione ma un esito
stocastico di `ESG × tau` (ESG estratti dal seed, attività riestratta a ogni epoca, composizione
dei cluster fissata dal profilo):

| validatore | `W_k_raw` | `w_k_published` | `p_theoretical` epoca 2 |
|---|---:|---:|---:|
| miner-2 (1E5SXZumxwmJ…) | 30 542 | 1 527 112 | 0,7243 |
| miner-1 (1GdxpDRQg6md…) | 4 483 | 224 168 | 0,1078 |
| miner-4 (1JxbNRFByhbb…) | 3 345 | 167 237 | 0,0806 |
| miner-3 (15VFHPRTt8ae…) | 1 987 | 99 330 | 0,0496 |
| miner-0 (1DDsDhKGKnpN…) | 1 547 | 77 358 | 0,0376 |

Fonte: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
[phase3/wpoa_epoch_validators.csv](phase3/wpoa_epoch_validators.csv). Sull'intera run il peso
pubblicato medio di miner-2 (1,70 M) è **21,5 volte** quello di miner-0 (79 k). È la
configurazione "balena": sui blocchi wPoA la quota spettante media di miner-2 è **0,7349**, contro
lo 0,714 della tabella di riferimento.

## 2. Executive summary

- **La randomness è pulita** su tutti i canali. `E_i` pubblico ha media 1,0001 su 24 505 righe
  (accettazione 1 ± 0,0125), KS `√n·D` = 0,61. Sugli score **privati** dei 5 miner `E_i` ha media
  1,0045 (`√n·D` = 1,20, critico 1,36), e l'argmin di `score_norm` media 0,5036 (`√n·D` 0,66).
  Lo score del vincitore vero ha media 0,5036, con KS p = 0,77 su 4 900 round.
- **La sortition è proporzionale al peso effettivo, anche con una balena.** Sui 4 900 blocchi wPoA
  miner-2 vince il **74,31 %** contro il **73,49 %** spettante (Wilson [73,06; 75,51] %). Il χ²
  aggregato vale 4,38 (p = 0,36, TV 0,0096). Le violazioni di Wilson sono 11 su 250 (12,5
  attese). Il GoF per epoca rigetta 1 volta su 50 (2,5 attese), e i p-value sono uniformi (KS
  p = 0,99).
- **L'unico rigetto per epoca (epoca 2) è un artefatto** della pipeline, che conta i 21 blocchi di
  setup in round robin. Sui 79 blocchi wPoA dell'epoca il χ² vale 2,74 (p Monte-Carlo 0,60).
- **Il "β1 NOT consistent" del GLM (1,536) è un falso allarme.** La nulla simulata con i pesi reali
  dà 1,511 [1,462; 1,560], con P(β1 ≥ 1,536) = 0,16. La regressione dei log-rapporti ha pendenza
  1,048, intercetta −0,080 e r = 0,944.
- **Il timer race funziona.** `corr(dt_prev, delay_true)` vale 0,983 e il delay mismatch è 0 su
  24 505 righe. Le **inversioni reali sono 3 su 4 900 (0,06 %)**. Il 15,5 % dei round ha una fork,
  e in tutti i 759 casi la catena finale tiene il blocco di score minimo. La regola nativa
  (first-seen) avrebbe tenuto il blocco sbagliato in 384 round (7,8 %).
- **Il block time converge**: media 8,064 s contro 8. `Phi` non è mai saturato (|Phi| ≤ 2,17 s
  contro M = 4).
- **Il weight engine è numericamente esatto** (identità ed errore della ricorsione ≤ 4·10⁻¹⁶),
  con 200/200 pesi verificati. La retroazione `rho → peso` è debole (Spearman −0,026), come atteso
  con `rho ≈ 0,005`.
- **Il malus non ha alcun effetto** in assenza di violazioni: M = 0 e Psi = 1 in 255 celle su 255.
- **Rilievi minori:** la probabilità di ripetizione del vincitore (0,578) supera la simulazione
  (0,561, p = 0,029), ma l'eccesso è già nel vincitore designato dalla VRF privata e scende a
  +1,2 punti (z ≈ 1,7) condizionando al vincitore precedente. Due aziende sono cadute al bootstrap
  (§5).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (A.1, calcolato qui)
  - **Cosa misura**: `E_i = score_public · weight_effective` sui round non di setup; deve essere
    `Exp(1)`.
  - **Osservato**: n = 24 505; media **1,0001**; mediana 0,6958 (teorica ln 2 = 0,6931); KS contro
    `1 − e^{−x}`: D = 0,0039, `√n·D` = **0,609**.
  - **Atteso**: media in 1 ± 1,96/√n = [0,9875; 1,0125]; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme**. La media si scosta dello 0,01 % e il KS è al 45 % del valore
    critico. `candidate_long` porta lo score **pubblico** HMAC, che verifica la formula e non
    l'ordinamento; il test sugli score privati è qui sotto.
- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (A.2, calcolato qui)
  - **Cosa misura**: il minimo di `score_norm_public` fra i candidati di ogni round (Prop. 5.11).
  - **Osservato**: 4 901 round; media **0,5029**; KS contro U(0,1): D = 0,0145, `√n·D` = **1,015**.
  - **Atteso**: media 0,5; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme** (scarto 0,6 %, KS al 75 % del critico). Controprova della trappola di
    §1.3(c): sulle righe `is_winner` la media sale a 0,668, come atteso per uno score pubblico
    indipendente da quello privato con cui si è votato.
- **File**: `analysis/private/priv_whale_none.json` (score **privati** da `debug.log`, §3.5.1)
  - **Cosa misura**: `E_i` e l'argmin di `score_norm` ricalcolati dagli score privati che ogni
    miner ha calcolato per sé in ogni round.
  - **Osservato**: 24 500 coppie (5 miner × 4 900 round), media `E_i` **1,0045** (banda ±0,0125),
    `√n·D` = **1,204**. Argmin di `score_norm`: media **0,5036**, `√n·D` = 0,663.
  - **Atteso**: come A.1/A.2.
  - **Giudizio**: **conforme**. Il KS di `E_i` privato è all'89 % del critico: non rigetta, e la media
    è entro la banda.
- **File**: [phase3/timer_race.md](phase3/timer_race.md), sezione "The winner's real score" (Q2)
  - **Cosa misura**: lo `score_norm_true` del vincitore, ricalcolato dal reveal VRF del suo blocco.
  - **Osservato**: 4 900 round; media **0,50364**; KS p = **0,769**. Sui 4 870 round in corsa: media
    0,50060, KS p = 0,915. Solo **30 round (0,61 %)** sono stati vinti al bordo superiore della banda.
  - **Atteso**: U(0,1) se vince l'argmin; ≈ 1 − 1/(n+1) = 0,83 se vincesse un validatore qualsiasi.
  - **Giudizio**: **conforme**. Il vincitore è l'argmin della VRF privata.
- **File**: [phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
  - **Cosa misura**: il gap standardizzato fra i due score minimi (Prop. 5.17), che deve essere
    `Exp(1)`.
  - **Osservato**: miner-2 (1E5SXZumxwmJ…) 0,988 (n = 3 641, KS p 0,34); miner-1 (1GdxpDRQg6md…)
    0,968 (482, p 0,62); miner-4 (1JxbNRFByhbb…) 1,018 (376, p 0,74); miner-3 (15VFHPRTt8ae…)
    1,013 (243, p 0,72); miner-0 (1DDsDhKGKnpN…) **1,138** (158, p **0,027**).
  - **Atteso**: media 1 per ogni vincitore, KS non significativo.
  - **Giudizio**: **conforme**. L'unico KS sotto 0,05 (miner-0) non sopravvive alla correzione per 5
    confronti (Bonferroni: 0,05/5 = 0,01). La sua media (+13,8 %) è a 1,7 errori standard
    (1/√158 = 0,080). Lo stesso miner-0 era a +35 % su 41 osservazioni nella run interrotta: con 4
    volte i dati lo scarto si è ridotto, come ci si aspetta da una fluttuazione.
- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (A.3)
  - **Cosa misura**: `score_norm_mismatch_public` fra il valore loggato e quello ricalcolato.
  - **Osservato**: massimo 2,2·10⁻¹⁶; 0 righe non nulle su 24 505.
  - **Giudizio**: **conforme**, all'errore di macchina.

### 3.2 Correttezza meccanica del delay

- **File**: [phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  (`delay_recompute_mismatch_rounds_is_zero`),
  [plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
  - **Cosa misura**: `|D_i ricalcolato − D_i loggato|` per ogni coppia (candidato, round).
  - **Osservato**: **0 su 24 505** righe oltre la tolleranza; massimo 3,6·10⁻¹⁵ s, dodici ordini di
    grandezza sotto la soglia di 1,5 ms. `delay_recompute_mismatch_rounds` = 0 in tutte le 50
    epoche.
  - **Atteso**: 0 mismatch.
  - **Giudizio**: **conforme**. Harness e nodo concordano esattamente sul meccanismo.

### 3.3 Quota di blocchi contro peso

- **File**: [phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [plots/weight_vs_election.png](plots/weight_vs_election.png),
  [plots/election_share_distribution.png](plots/election_share_distribution.png)
  - **Cosa misura**: la quota osservata `p_hat` contro la quota spettante
    `p_theoretical = w_eff/Σw_eff` (con `g(w) = w`).
  - **Osservato**, sui 4 900 blocchi **wPoA** (blocchi di setup esclusi, calcolato qui con la stessa
    logica delle figure della tesi):

    | validatore | `p_theoretical` | `p_hat` | Wilson 95 % |
    |---|---:|---:|---|
    | miner-2 (1E5SXZumxwmJ…) | 0,7349 | **0,7431** | [0,7306; 0,7551] |
    | miner-1 (1GdxpDRQg6md…) | 0,1001 | 0,0984 | [0,0903; 0,1070] |
    | miner-4 (1JxbNRFByhbb…) | 0,0753 | 0,0767 | [0,0696; 0,0845] |
    | miner-3 (15VFHPRTt8ae…) | 0,0556 | 0,0496 | [0,0439; 0,0560] |
    | miner-0 (1DDsDhKGKnpN…) | 0,0341 | 0,0322 | [0,0277; 0,0376] |

    χ² aggregato = 4,38, 4 gdl, p = 0,36; TV = 0,0096. La tabella "pooled" della pipeline (4 921
    blocchi, compresi i 21 di setup dell'epoca 2) dà numeri quasi identici: miner-2 0,7399 contro
    0,7348, χ² 2,64, p = 0,62. Nello scatter i punti di miner-2 stanno fra 0,62 e 0,88, attorno
    alla diagonale; quelli dei piccoli fra 0 e 0,17.
  - **Atteso** (caso `none`): proporzionalità lineare non compressa. La balena deve dominare in
    proporzione al suo peso (tabella di riferimento: 0,714).
  - **Giudizio**: **conforme**. Lo scarto di miner-2 è di +0,82 punti (z = 1,3), e ogni quota
    spettante cade nel proprio intervallo (miner-3 al limite: 0,0556 contro un estremo di 0,0560).
    Il dominio di miner-2 è **comportamento corretto**, perché è quanto il suo peso effettivo gli
    attribuisce. Per terzo di run lo scarto di miner-2 vale +0,37 / +0,99 / +1,10 punti.
- **File**: [phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png),
  [phase3/wpoa_epoch_validators.csv](phase3/wpoa_epoch_validators.csv)
  - **Cosa misura**: la copertura degli intervalli di Wilson al 95 % per (epoca, validatore).
  - **Osservato**: **11 violazioni su 250**. Tre cadono nell'epoca 2 (miner-2, miner-3, miner-0),
    contaminata dal setup. Le altre sono miner-3 nelle epoche 5, 9, 20, 35 e 43, miner-0 nelle 16 e
    21, miner-2 nella 25. Larghezza media dell'intervallo: **0,113**, che è la risoluzione per
    epoca. Sulle epoche complete la quota spettante della balena cade nel proprio intervallo in 48
    su 49.
  - **Atteso**: 0,05·250 = 12,5 violazioni.
  - **Giudizio**: **conforme** (11 contro 12,5). Miner-3 compare in 6 violazioni su 11, ma in
    direzioni miste; sull'aggregato la sua quota resta dentro l'intervallo (vedi sopra).
- **File**: [phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [plots/p_value_uniformity.png](plots/p_value_uniformity.png)
  - **Cosa misura**: il GoF congiunto per epoca (multinomiale Monte-Carlo, 20 000 estrazioni) e
    l'uniformità dei suoi p-value.
  - **Osservato**: **1 rigetto su 50** (epoca 2, p = 0,0018, TV 0,132). L'epoca più vicina alla
    soglia è la 20 (p = 0,053). KS dei p-value contro U(0,1): D = 0,062, p = 0,988; binomiale sul
    numero di rigetti p = 0,92. L'istogramma è piatto (fra 2 e 8 epoche per decile, attesa 5).
    `share_changes_within_epoch = True` ovunque, ma `gof_mc_round_by_round_p` coincide col pooled
    entro 0,01. Riga `all`: χ² = 2,64, p = 0,62 (round-by-round p = 0,35).
  - **Atteso**: 2,5 rigetti; p-value uniformi.
  - **Giudizio**: **conforme**. Il rigetto dell'epoca 2 è un **artefatto della pipeline**: l'epoca
    (h 200–299) contiene 21 blocchi sotto `setup-first-blocks` = 220, in round robin (miner-0 8,
    miner-3 7, miner-4 3, admin 3). Sui soli 79 blocchi wPoA (miner-2 62, miner-1 9, miner-3 3,
    miner-4 3, miner-0 2) il χ² vale 2,74 (p Monte-Carlo 0,60). Nessun rigetto genuino in 50
    epoche.

### 3.4 Comportamento longitudinale

- **File**: [phase3/longitudinal.md](phase3/longitudinal.md),
  [phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv) (GLM logit)
  - **Cosa misura**: `logit(p_hat) = β0 + β1·log(w_eff)`, con H0 della pipeline `β1 = 1`.
  - **Osservato**: β1 = **1,5359** [1,4996; 1,5722], `converged = True`, n = 250 → "NOT
    consistent".
  - **Atteso**: l'H0 `β1 = 1` è **mal specificata** con pochi validatori. Sotto `p = w/W` vale
    `logit p = log w − log(W − w)`, la cui pendenza è ≈ 1/(1 − p), molto maggiore di 1 con un
    validatore a p ≈ 0,73. Ricalibrazione con 2 000 simulazioni multinomiali sulle `p_theoretical`
    reali di ogni epoca, rifittate con la stessa `binomial_logit_glm` della pipeline
    (`analysis/private/glm_mc.py`): β1 nullo = **1,511** [1,462; 1,560]; P(β1_sim ≥ 1,536) = 0,16.
  - **Giudizio**: **conforme**. Il valore osservato sta dentro l'intervallo al 95 % della sua nulla
    corretta. Il "NOT consistent" è un falso allarme dello strumento, non del protocollo.
- **File**: [phase3/wpoa_longitudinal_logratios.csv](phase3/wpoa_longitudinal_logratios.csv),
  [plots/longitudinal_logratio.png](plots/longitudinal_logratio.png)
  - **Cosa misura**: la regressione dei log-rapporti delle quote osservate su quelli spettanti, a
    coppie.
  - **Osservato**: pendenza **1,048**, intercetta **−0,080**, Pearson r = **0,944** (488 coppie),
    Spearman 0,920.
  - **Atteso**: pendenza 1, intercetta 0.
  - **Giudizio**: **conforme**. Pendenza entro il 4,8 % e r alto. L'intercetta negativa è piccola
    (−0,08 in log, cioè −8 % sul rapporto) ed è dominata dalle coppie con quote piccole, dove
    `log(0)` esclude le epoche a zero vittorie e seleziona le epoche fortunate.
- **File**: [phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv)
  (monotonicity), [plots/sign_test_by_validator.png](plots/sign_test_by_validator.png),
  [phase3/wpoa_longitudinal_validators.csv](phase3/wpoa_longitudinal_validators.csv)
  - **Cosa misura**: se, per ciascun validatore, la quota si muove col peso fra un'epoca e l'altra
    (sign test esatto a una coda).
  - **Osservato**: concordanza fra 0,60 e 0,67 per tutti; p = 0,024 (miner-3), 0,022 (miner-0),
    0,022 (miner-1), 0,072 (miner-2), 0,121 (miner-4). Prima contro ultima epoca: intervalli
    sovrapposti per tutti e 5.
  - **Atteso**: concordanza > 0,5 per tutti. Con pesi che variano del ±15–30 % fra epoche e 100
    blocchi per epoca, la potenza è moderata.
  - **Giudizio**: **conforme**. Tutti e 5 i validatori si muovono nel verso del peso, 3 in modo
    significativo al 5 %. Il segnale è più netto che nella run interrotta (1 su 5), grazie alle 49
    coppie di epoche invece di 14.

### 3.5 Timer race, margine e inversioni

- **File**: [phase3/timer_race.md](phase3/timer_race.md),
  [phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv) (Q1)
  - **Cosa misura**: `corr(dt_prev, delay_true)`, cioè se la spaziatura dei blocchi segue il delay
    vero del vincitore.
  - **Osservato**: **0,9832** (4 900 round); residuo medio 0,054 s, deviazione standard 0,432 s.
    Per terzo di run la deviazione standard del residuo è 0,435 / 0,427 / 0,434 s, la media
    0,043 / 0,049 / 0,071 s.
  - **Atteso**: ≈1 se il meccanismo funziona, ≈0 se è disaccoppiato.
  - **Giudizio**: **conforme**. Il rumore di scheduling è di ~0,43 s e **non cresce** nel tempo.
- **File**: [plots/margin_distribution.png](plots/margin_distribution.png),
  [phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv)
  - **Cosa misura**: il margine `G` fra i due delay più rapidi (forma pubblica).
  - **Osservato**: media 2,839 s (mediana 2,417 s) contro 2,885 s della simulazione esatta. KS di
    riferimento: p = **0,507**. KS contro `Beta(1,n)`: p = 0,000. L'istogramma decresce da 0,36 a
    0,03 fra 0 e 8 s. Sugli score privati il margine vale in media 2,865 s (mediana 2,431 s), con il
    14,7 % dei round sotto 0,5 s.
  - **Atteso**: il KS contro la simulazione esatta non deve rigettare. `Beta(1,n)` è uno **straw
    man** (pesi uniformi, qui fortemente disomogenei).
  - **Giudizio**: **conforme** (scarto della media −1,6 %). Il rigetto `Beta(1,n)` **non è un
    rilievo**.
- **File**: [phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [plots/sigma_decomposition.png](plots/sigma_decomposition.png),
  [plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
  - **Cosa misura**: la decomposizione del rumore e il bound di Prop. 5.18.
  - **Osservato**: `S1_topology` = 0,000377 s (misurato sulla mappa regionale).
    `S2_scheduler_residual_sd` = 3,468 s e `S2b` = 2,071 s, **entrambi sullo score pubblico**. Bound
    = 1,0; probabilità MC 0,506; inversioni pubbliche osservate 2 148/4 901 = 0,438.
  - **Atteso**: sullo score pubblico il tasso di "inversione" è un artefatto di costruzione (score
    indipendente da quello privato con cui si vota). Il bound saturato a 1 è **vacuo**.
  - **Giudizio**: **conforme come audit del modello, non informativo sull'ordinamento**. Il 43,8 %
    **non** è un tasso di inversione reale, che è in §3.5.1 (0,06 %). `S2` pubblico (3,5 s) va letto
    accanto al rumore vero di 0,43 s (Q1).
- **Vantaggio del miner uscente** (da [phase2/round_level.csv](phase2/round_level.csv),
  [phase3/streak.md](phase3/streak.md) e dagli score privati)
  - **Osservato**: il tasso di ripetizione del vincitore è **0,578**, contro 0,561 della simulazione
    Monte-Carlo sugli stessi pesi (p = 0,029). Per terzo: 0,566 / 0,587 / 0,581. Tre controlli
    dicono che l'eccesso **non** viene da un vantaggio temporale dell'uscente:
    1. lo `score_norm_true` dei vincitori ripetuti ha media 0,507 (KS `√n·D` 0,95 su 2 832 round),
       contro 0,499 dei non ripetuti. Un uscente che vincesse senza essere l'argmin alzerebbe
       questa media verso 0,83;
    2. il residuo vero medio è lo stesso per i ripetuti e i non ripetuti (0,056 contro 0,052 s);
    3. sugli score privati il **vincitore designato** coincide con l'uscente nel 57,8 % dei round,
       la stessa frequenza della catena finale. Condizionando al vincitore effettivo del round
       precedente, l'attesa è 0,566: l'eccesso scende a +1,2 punti (z ≈ 1,7).
    Il lag dell'uscente (0,60 s contro 1,59 s degli altri) è il ritardo con cui ciascun nodo vede il
    blocco padre e arma il timer, ma il timer è ancorato al padre ("parent anchor", 26 208/26 208
    righe `anchor=parent`) e quindi non si traduce in un vantaggio.
  - **Atteso**: senza vantaggio dell'uscente, probabilità di ripetizione ≈ Σp² per round.
  - **Giudizio**: **lieve scostamento**. L'eccesso aggregato (+1,7 punti sulla simulazione
    incondizionata) si spiega per circa metà con la quota di miner-2 lievemente sopra la spettante
    (+0,8 punti, entro Wilson) e per il resto con +1,2 punti non significativi. Sta già
    nell'estrazione VRF, non nella corsa dei timer.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Fonte: `chains/miner-{0..4}/wpoa-core-regional-whale-none/debug.log`, letti come root dal
container, copiati in `analysis/private/` e analizzati con `analysis/private/priv.py` (lo stesso
script della run `regional-d025`). Esito in `analysis/private/priv_whale_none.json`. **Copertura
completa:** con `sortition_miner_log: true` ogni miner logga il proprio score privato e il delay di
ogni round che valuta. Score privati di **5 miner su 5, 4 900 round su 4 900**; 26 208 righe di
scheduling, di cui 24 510 sul padre rimasto nella catena finale.

- **(a) Sortition privata.** `E_i` privato: media 1,0045, `√n·D` = 1,20 (§3.1). Quote dei vincitori
  designati contro le spettanti: miner-2 0,7435/0,7349, miner-1 0,0982/0,1001, miner-4 0,0767/0,0753,
  miner-3 0,0494/0,0556, miner-0 0,0322/0,0341; χ² = 4,68 con 4 gdl (p ≈ 0,32). Il designato
  coincide con l'uscente nel 57,8 % dei round, contro il 56,6 % atteso dati i pesi e l'uscente
  effettivo. **Giudizio: conforme.** Le quote designate riproducono quelle osservate in §3.3: lo
  scarto di miner-2 è già nell'estrazione, non nella rete.
- **(b) Inversioni reali.** In **3 round su 4 900 (0,061 %)** la catena finale tiene un blocco che
  non è l'argmin privato: 1 / 1 / 1 per terzo di run. Due vanno a miner-1 e una a miner-3; i
  designati erano miner-2 in due casi e miner-1 in uno. **Nessuna va all'uscente**. Il margine
  di delay fra vincitore e designato vale in media 0,32 s (massimo 0,56 s).
  `true_winner_mismatch` in `round_level.csv` è 0 su 4 901 righe: `blocks.csv` è coerente con
  `block_sortition.csv`. **Giudizio: conforme.**
- **(c) Fork.** Il **15,5 %** dei round (759/4 900) ha visto più di un blocco alla stessa altezza,
  con 1 337 blocchi poi orfani e fino a 5 blocchi per altezza. La quota è stabile per terzo (14,8 /
  15,6 / 16,1 %). **In tutti i 759 fork la catena finale tiene il blocco di score minimo.** Sulle
  3 858 valutazioni contese (ultima per nodo e altezza) la regola per score sceglie il blocco finale
  nel 100 % dei casi, la regola nativa (colonna `legacy`) nel 64,8 %. Dove le due divergono (1 357
  valutazioni, 606 altezze) vince sempre la regola per score. **Il primo blocco arrivato non era
  quello finale in 384 round (7,8 %)**: sono le inversioni che la regola first-seen avrebbe
  prodotto, il 20,8 % delle quali a favore dell'uscente. Le 2 402 `displace` vanno tutte verso lo
  score migliore. Ci sono 556 `defer` e 202 `retarget-abort`. La **profondità massima di
  riorganizzazione è 1 blocco** su tutti e 5 i miner (da 241 riorganizzazioni per miner-2 a 595 per
  miner-0). Un nodo resta su un blocco poi orfano al massimo **1,36 s** (mediana −0,16 s,
  95° percentile 0,57 s). **Giudizio: conforme.**
- **(d) Prop. 5.18 sui delay reali.** Simulazione Monte-Carlo sui delay privati di ogni round, 20
  repliche. Rumore simmetrico gaussiano: σ = 0,2 s → 5,0 % di inversioni istantanee; 0,3 s → 7,1 %;
  0,35 s → 8,0 %; 0,4 s → 9,2 %. La quota a favore dell'uscente è ~19 %, e ~40 % fra i round in
  cui l'uscente non era il designato. Con un vantaggio di 0,1 s all'uscente (σ = 0,35 s): 7,7 %,
  quota all'uscente 27 % (49 % fra gli eleggibili). Con 0,3 s: 7,3 %, 47 % (66 %). Osservato
  (first-arrival): **7,8 %**, **20,8 %** all'uscente, **42,6 %** (80/188) fra gli eleggibili, stabile
  per terzi (7,9 / 7,7 / 7,9 %). **Il modello simmetrico con σ ≈ 0,3–0,35 s riproduce sia il tasso
  sia chi ne beneficia**; il modello con vantaggio sovrastima la quota all'uscente. Il σ implicito
  (0,3–0,35 s) è coerente con il residuo di scheduling (0,43 s) e non cresce nel tempo. Il bound di
  Prop. 5.18 riguarda le inversioni istantanee: il tie-break per score le riduce poi al 0,06 %
  finale. **Giudizio: conforme.**

### 3.6 Stabilità del block time e correzione globale

- **File**: [phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`, `phi_s`,
  `delay_true_s`)
  - **Cosa misura**: lo spacing dei blocchi realizzato e il ritardo vero del vincitore.
  - **Osservato**: `dt_prev` medio **8,064 s** (deviazione standard 2,37, mediana 8,0, min 3, max
    13; n = 4 900). Per terzo 8,03 / 8,08 / 8,09 s. Per epoca fra 7,57 (ep. 35) e 8,40 s (ep. 29),
    senza deriva. Delay vero medio del vincitore 8,010 s.
  - **Atteso**: convergenza a `T_block` = 8 s, dentro la banda 8 ± 4 + 0,3·Phi.
  - **Giudizio**: **conforme** (+0,8 % sul target).
- **File**: [plots/phi_over_time.png](plots/phi_over_time.png),
  [phase3/consistency_checks.csv](phase3/consistency_checks.csv) (`phi_consistent`)
  - **Cosa misura**: la traiettoria del termine di feedback `Phi`.
  - **Osservato**: 49 valori distinti; media −0,063 s, deviazione standard 0,616 s, range
    [−2,00; +2,17] s. **0 round a ±M** (M = 4 s); 256 round con Phi = 0; 470 cambi di segno su
    4 900 transizioni (9,6 %). La mediana mobile (finestra 408) resta fra −0,33 e +0,17 s per tutta
    la run, senza tendenza.
  - **Atteso**: Phi piccolo e centrato se il controllo funziona; saturazione o alternanza di segno
    round per round indicherebbero guadagno insufficiente o eccessivo.
  - **Giudizio**: **conforme**. Il massimo |Phi| è il 54 % di M e la variabilità è lenta.
    `phi_consistent = FAIL` **non è un difetto**: il check (non critico) è una sonda tarata su run a
    feedback spento. A differenza delle run lunghe precedenti alle correzioni, qui non c'è
    rallentamento a fine run: il terzo finale ha lo stesso block time del primo.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv) (identità del motore)
  - **Cosa misura**: `W_k_raw = ESG_Mk·(tau_Mk + Σc_i)` e
    `w_k_final = W_k_raw·(rho_prev·0,5 + 0,5)`.
  - **Osservato**: errore relativo massimo **0** per la prima identità e **4,0·10⁻¹⁶** per la
    ricorsione (255 righe, epoca 1 compresa, dove `w_final = W_raw`). Il peso pubblicato è
    `w_final × 100` entro l'arrotondamento all'intero in 255 righe su 255.
  - **Giudizio**: **conforme**.
- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [phase1/esg_events.csv](phase1/esg_events.csv) (ESG statici)
  - **Osservato**: `miner_esg_score` costante in tutte le 51 epoche per ogni cluster
    (75/56/55/49/29), senza ri-certificazioni.
  - **Giudizio**: **conforme**.
- **File**: [plots/weights_over_time.png](plots/weights_over_time.png),
  [plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png)
  - **Cosa misura**: i pesi per miner nei tre stadi (grezzo, dopo malus, dopo smorzamento).
  - **Osservato**: i tre pannelli sono **identici** (Psi = 1, `g` = identità). Dopo l'epoca 1 di
    bootstrap (81 525 per miner-2), miner-2 oscilla fra 1,52 e 1,95 M, miner-1 fra 0,14 e 0,31 M,
    miner-4 fra 0,10 e 0,25 M, miner-3 fra 0,10 e 0,18 M, miner-0 fra 0,05 e 0,11 M. Nessuna
    tendenza, e l'ordinamento della balena non cambia mai.
  - **Atteso**: pesi rumorosi (tau riestratto ogni epoca), senza tendenza sistematica.
  - **Giudizio**: **conforme**.
- **File**: [phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)
  - **Cosa misura**: la retroazione `rho(e)` → peso pubblicato in `e+1` (Spearman lag-1).
  - **Osservato**: `rho` **non è nullo**: media 0,0051, deviazione standard 0,0031, range
    [0; 0,0138], 10 zeri su 255. 2 612 restituzioni al treasury, tutte da miner. Spearman aggregato
    **−0,026** (p = 0,68, n = 250); per cluster fra −0,13 e +0,08, nessuno significativo. Lo scatter
    mostra due bande orizzontali (balena e piccoli) senza pendenza.
  - **Atteso**: con `lambda_w` = 0,5 il fattore vale 0,5·rho + 0,5. Con rho ≤ 0,014 il fattore sta
    fra 0,500 e 0,507: un effetto sotto l'1,4 %, sommerso dalla varianza di tau (±15–30 %).
  - **Giudizio**: **conforme**. La retroazione è attiva ma quantitativamente inerte in questo
    regime.
- **File**: [phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png)
  - **Cosa misura**: `Gini(pubblicato) − Gini(input)` nel tempo.
  - **Osservato**: pendenza −6·10⁻⁶ per epoca, intercetta 1,9·10⁻⁴, Spearman −0,19 (p = 0,19).
  - **Atteso**: pendenza ≈ 0.
  - **Giudizio**: **conforme**. Il motore non amplifica la disuguaglianza dei propri input.
- **File**: [plots/esg_scores.png](plots/esg_scores.png) (e `esg_scores/company.png`,
  `esg_scores/miner.png`)
  - **Osservato**: 35 score certificati; miner-2 ha l'ESG più alto fra i miner (75), come previsto
    dal profilo. `certified_scores_reflected_in_the_engine` = FAIL (non critico) per
    1XPy45GVqYWF… = **company-13** e 1PJZEA5mCczf… = **company-27**: certificati ma mai registrati
    nel cluster, perché i loro nodi non rispondevano.
  - **Giudizio**: **scostamento significativo da indagare**, ma **dell'harness, non del
    protocollo**: il motore ignora correttamente due aziende senza membership (§5).

### 3.8 Concentrazione

- **File**: [phase2/epoch_concentration.csv](phase2/epoch_concentration.csv),
  [phase3/report.md](phase3/report.md) §3,
  [plots/concentration_over_time.png](plots/concentration_over_time.png)
  - **Cosa misura**: HHI, N_eff, Gini e Nakamoto, teorici contro osservati nella stessa epoca.
  - **Osservato**: aggregato HHI teorico **0,5598** contro osservato **0,5674**; N_eff 1,79 contro
    1,76; Gini 0,578 contro 0,584. Nakamoto(1/2) = 1 in ogni epoca misurata, sia teorico sia
    osservato. Per epoca l'HHI osservato oscilla fra 0,442 (ep. 2) e 0,779 (ep. 25) attorno al
    teorico (0,518–0,615). Nelle ultime dieci epoche il Gini osservato (0,54–0,65) sta sopra il
    teorico (0,56–0,59) in 7 casi su 10.
  - **Atteso**: il confronto affidabile è l'aggregato. Per epoca, con 100 blocchi, la varianza
    multinomiale sposta l'HHI di ±0,05–0,1, e il Gini osservato su 5 validatori è distorto verso
    l'alto quando i piccoli vincono 0–3 blocchi. Nakamoto(1/2) = 1 è la conseguenza diretta di una
    balena con quota spettante 0,73.
  - **Giudizio**: **conforme** (HHI aggregato +1,3 %, Gini +1,0 %). La concentrazione è quella del
    **peso**, non un'amplificazione dell'elezione. L'eccesso aggregato di HHI è la stessa
    fluttuazione di +0,8 punti di miner-2 di §3.3. Il Gini osservato per epoca supera il teorico in
    34 epoche su 50, ma non è una deriva: una simulazione multinomiale (100 blocchi, `p_theoretical`
    di ogni epoca, 4 000 estrazioni) dà P(Gini osservato > teorico) = 0,61 e una distorsione media di
    +0,010 per costruzione, e 34/50 contro 0,61 ha p binomiale 0,18. Il dubbio sollevato nella run
    interrotta è quindi risolto.

### 3.9 Streak e ripetizioni

- **File**: [phase3/streak.md](phase3/streak.md),
  [phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv)
  - **Cosa misura**: la serie massima di vittorie consecutive e la probabilità di ripetizione,
    contro un Monte-Carlo sugli stessi pesi.
  - **Osservato**: `L_max` aggregato 20 contro 25,1 simulato (p = 0,95); per epoca **nessun**
    `L_max` con p < 0,05 (minimo 0,058, ep. 26). Ripetizione aggregata 0,578 contro 0,561
    (p = 0,029). Per epoca, 6 p < 0,05 su 50 (epoche 2, 6, 9, 20, 25, 26; binomiale P(X ≥ 6) =
    0,038), bilanciati da epoche in difetto (12: 0,424, p = 0,976; 15: 0,424, p = 0,964).
  - **Atteso**: nessun eccesso sistematico; 2,5 rigetti per epoca attesi.
  - **Giudizio**: **lieve scostamento**. Non è sistematico (44 epoche su 50 non rigettano, `L_max`
    mai), e l'epoca 2 è contaminata dal setup. §3.5 mostra che non viene da rumore di rete
    persistente né da un vantaggio dell'uscente: i ripetuti hanno score privato uniforme e le
    inversioni reali sono 3. Un seed non rinfrescato sarebbe visibile come correlazione fra `E_i`
    successivi, e il KS di `E_i` privato non rigetta. Resta una fluttuazione di +1,2 punti
    condizionata, da ricontrollare sulle run `sqrt` e `log`.

### 3.10 Malus

Caso **J.1**: nessuna violazione iniettata (`malicious.enabled = false`), meccanismo attivo
(`enable-wpoa-malus = true`).

- **File**: [phase2/malus_state.csv](phase2/malus_state.csv),
  [phase3/malus_invariants.csv](phase3/malus_invariants.csv),
  [plots/malus_invariant_audit.png](plots/malus_invariant_audit.png)
  - **Osservato**: M = 0 e Psi = 1 in **255 celle (epoca, validatore) su 255**; i tre invarianti
    valgono ovunque. Nel registro, 198 430 campioni di malus hanno tutti Psi in [0,1].
    `weight_effective == weight_raw` ovunque (i pannelli di `weights_over_time.png` coincidono).
  - **Atteso**: effetto esattamente nullo sul comportamento onesto.
  - **Giudizio**: **conforme**.
- **File**: [phase1/malus_detections.csv](phase1/malus_detections.csv), `phase1/malicious_*.csv`,
  [phase2/malus_actions.csv](phase2/malus_actions.csv),
  [phase2/malus_detection_events.csv](phase2/malus_detection_events.csv),
  [phase3/malus_detection.csv](phase3/malus_detection.csv),
  [phase3/malus_funnel.csv](phase3/malus_funnel.csv),
  [phase3/malus_latency.csv](phase3/malus_latency.csv),
  [phase3/malus_rate.csv](phase3/malus_rate.csv)
  - **Osservato**: 0 righe di dati in tutti i file (funnel a 0 per `all`, `selfwrite`, `badweight`;
    precision e recall non definiti; rate vuoto). `malus_effectiveness.md` **non è presente**:
    l'esperimento malicious non è stato eseguito.
  - **Giudizio**: **conforme**, perché è il risultato atteso per J.1.
- **File**: [plots/malus_action_funnel.png](plots/malus_action_funnel.png),
  [plots/malus_state_trajectory.png](plots/malus_state_trajectory.png),
  [plots/malus_detection_latency.png](plots/malus_detection_latency.png),
  [plots/malus_weight_effect.png](plots/malus_weight_effect.png)
  - **Osservato**: figure degeneri come atteso. La variazione del peso efficace in
    `malus_weight_effect.png` (solo gruppo onesto) è l'effetto dell'epoca 1 di bootstrap, non del
    malus (Psi = 1 ovunque).
  - **Giudizio**: **conforme**.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv)
  (calcolato qui, epoche 2–50, n = 245)
  - **Cosa misura**: se guadagno o volume di transazioni entrano nell'elezione per canali diversi
    dal peso.
  - **Osservato, punto 1** (Spearman con `n_blocks_won_epoch`): `w_k_published` 0,857, `W_k_raw`
    0,857, `companies_contribution_sum` 0,794, `earnings_g_k` 0,681, `income` 0,195,
    `miner_activity` 0,190.
  - **Osservato, punto 2** (residui `p_hat − p_theoretical`, Spearman fra validatori):
    `earnings_g_k` 0,061 (p 0,34), `income` 0,093 (p 0,15), `miner_activity` 0,096 (p 0,13),
    `companies_contribution_sum` 0,105 (p 0,10). **Entro validatore** (valori standardizzati per
    miner): con le grandezze del motore della stessa epoca, `W_k_raw` r = 0,10 (p 0,11),
    `companies_contribution_sum` 0,09 (p 0,18), `miner_activity` 0,07, `rho` 0,08. Con i guadagni
    registrati all'**epoca successiva** r = **0,80**.
  - **Atteso**: correlazione del punto 1 interamente mediata dal peso; nulla al punto 2.
  - **Giudizio**: **conforme**. L'unica correlazione forte (0,80) ha il verso causale opposto: il
    coinbase accredita al miner le fee dei blocchi che produce, e il motore le conta nell'epoca
    successiva, quindi chi vince più del dovuto **guadagna** di più. Nessuna grandezza che precede
    l'elezione ne spiega il residuo: nessun canale non documentato. Nota esplorativa: il residuo
    dell'epoca `e` è debolmente anti-correlato con la variazione della quota spettante da `e` a
    `e+1` (r = −0,20, p = 0,002). Nessuno degli input del motore la spiega (tutti con |r| ≤ 0,14),
    ed è fuori dal protocollo di §3.2(K). Va ricontrollata sulle run gemelle prima di darle un
    significato.

### 3.12 Integrità della run e controlli di consistenza

- **File**: [phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  - **Osservato**, critici (**7/7 PASS**): `registry_weights_finite_and_positive` (198 430
    campioni), `no_phantom_validator_in_registry`, `malus_finite_and_psi_in_unit_interval`,
    `delay_recompute_mismatch_rounds_is_zero`, `every_esg_publication_reached_the_stream` (35/35),
    `only_miners_pay_the_treasury` (2 612/2 612), `at_least_one_fully_measured_epoch` (50).
    Non critici: `phi_consistent` FAIL (atteso, §3.6); `certified_scores_reflected_in_the_engine`
    FAIL (company-13 e company-27, §3.7); `traffic_counts_within_configured_range` PASS (1 615 coppie
    complete, tutte nel range).
  - **Giudizio**: **conforme** sui critici.
- **File**: [phase1/verification.csv](phase1/verification.csv)
  - **Osservato**: 200 verifiche `weightverifyweights` (epoche 1–50), **200/200 `verdict = ok`**.
  - **Giudizio**: **conforme**. Nessun peso non ricalcolabile.
- **File**: [phase2/epoch_traffic.csv](phase2/epoch_traffic.csv),
  [plots/traffic_per_epoch.png](plots/traffic_per_epoch.png)
  - **Osservato**: 33 nodi per epoca (28 aziende e 5 miner). Per le aziende, pianificate = inviate =
    on-chain in tutte le epoche complete (fra 1 110 e 1 390 transazioni per epoca). Epoca 51
    parziale: ~1 250 pianificate, 330 inviate, 320 on-chain.
  - **Giudizio**: **conforme**; l'ultima epoca è parziale per costruzione.
- **File**: [phase1/rpc_errors.csv](phase1/rpc_errors.csv)
  - **Osservato**: 406 errori, **tutti fra le 17:03 e le 17:17Z** (bootstrap): 4 × 101 `wpoalist*`
    con "Round not evaluable" prima che il registro dei pesi fosse attivo, e 2
    `weightregistermembership` falliti verso company-13 e company-27. Nessun errore nelle ~11h
    successive.
  - **Giudizio**: **conforme**. Errori benigni di bootstrap, più il sintomo del difetto su due
    aziende.
- **File**: `manifest.json`, `shutdown.json`
  - **Osservato**: `status = ok`, `final_height` 5124 ≥ target 5120, snapshot di chiusura a 5125
    con 35 connessioni. `true_winner_mismatch` 0 su 4 901 righe: `blocks.csv` è raccolto dopo la
    correzione del blocco orfano.
  - **Giudizio**: **conforme**.
- **Ultima epoca (51)**: 21 blocchi, Wilson larghi fino a 0,30 (miner-4: [0,050; 0,346]), miner-0 a
  0 vittorie con quota spettante 0,034 (probabilità di 0 su 21: 48 %). **Esclusa da ogni conclusione
  di tendenza.**

## 4. Punti di forza

- **Proporzionalità con una balena, senza smorzamento, su 4 900 blocchi.** Miner-2 (1E5SXZumxwmJ…)
  vince il 74,31 % dei blocchi wPoA contro il 73,49 % spettante (z = 1,3), e i quattro piccoli
  restano entro ±0,6 punti. χ² aggregato p = 0,36, TV 0,0096; 1 rigetto per epoca su 50
  (artefatto di setup); 11/250 violazioni di Wilson contro 12,5 attese.
- **Randomness pulita su tutti i canali.** `E_i` pubblico 1,0001 (`√n·D` 0,61), privato 1,0045
  (`√n·D` 1,20); argmin di `score_norm` 0,5029 pubblico e 0,5036 privato; score del vincitore
  vero 0,504 (KS p 0,77); Prop. 5.17 fra 0,97 e 1,14.
- **Timer race quasi senza inversioni.** Q1 = 0,983, 3 inversioni reali su 4 900 (0,06 %), reorg
  al massimo di 1 blocco, 759/759 fork risolte verso lo score minimo. Il tie-break per score
  recupera le 384 inversioni istantanee (7,8 %) che la regola nativa avrebbe lasciato, e il
  modello simmetrico con σ ≈ 0,3–0,35 s ne riproduce sia il tasso sia la distribuzione.
- **Meccanica bit-esatta.** Delay mismatch 0 su 24 505 (≤ 3,6·10⁻¹⁵ s); `score_norm` mismatch
  ≤ 2,2·10⁻¹⁶; identità del weight engine ≤ 4·10⁻¹⁶; 200/200 pesi verificati.
- **Block time sul target per 11 ore.** Media 8,064 s (+0,8 %), stabile per terzi (8,03 / 8,08 /
  8,09); `Phi` mai oltre il 54 % del suo bound; rumore di scheduling costante (0,43 s).
- **Malus a effetto nullo sugli onesti.** M = 0, Psi = 1 e invarianti veri in 255/255 celle.
- **Nessun canale di influenza fuori dal peso.** I residui non dipendono da nessuna grandezza che
  precede l'elezione (|r| ≤ 0,10).

## 5. Punti critici / da approfondire

- **company-13 e company-27 mai attive** (nodi non raggiungibili alla registrazione della
  membership).
  - *Entità:* 2 aziende su 30. La balena lavora con 17 aziende e miner-1 con 2. Un check non
    critico fallisce per questo.
  - *Causa ipotizzata:* crash del daemon durante il join con 38 nodi avviati insieme. È lo stesso
    difetto già visto nella run interrotta (company-28/29), in `whale-sqrt` (3 aziende) e in
    `regional-d025` (3): non è legato al blackout.
  - *Serve:* un controllo di liveness nell'orchestratore dopo `launch_peers` e prima di
    `register_membership`, che fallisca subito o riavvii il nodo.
- **La prima epoca misurata (2) contiene blocchi di setup.**
  - *Entità:* 21 blocchi su 100 in round robin; ne derivano l'unico rigetto del GoF, 3 violazioni di
    Wilson su 11 e uno dei 6 rigetti di ripetizione.
  - *Causa:* la pipeline esclude solo le epoche *interamente* sotto `setup-first-blocks`.
  - *Serve:* filtrare i blocchi con `in_setup = True` anche dentro l'epoca a cavallo della soglia.
    Sui 79 blocchi wPoA il χ² dà p = 0,60.
- **Il GLM longitudinale continua a segnalare "NOT consistent" per costruzione.**
  - *Entità:* β1 = 1,536 contro H0 = 1, ma la nulla corretta è 1,511 [1,462; 1,560].
  - *Serve:* sostituire in `stat/longitudinal.py` l'H0 fissa con il β1 nullo simulato sulle
    `p_theoretical` della run.
- **Leggero eccesso di ripetizioni del vincitore** (0,578 contro 0,561, p = 0,029; 6/50 epoche).
  - *Entità:* +1,7 punti incondizionati, +1,2 punti (z ≈ 1,7) dato il vincitore precedente.
  - *Causa più probabile:* fluttuazione campionaria sommata al +0,8 punti di miner-2. Non viene
    dalla timer race: il designato privato coincide con l'uscente con la stessa frequenza, e i
    ripetuti hanno score uniforme.
  - *Serve:* confrontare con `whale-sqrt` (lì 0,282 contro 0,284) e con la futura `whale-log`. Se
    l'eccesso si ripetesse in più run, testare l'indipendenza seriale degli `E_i` privati fra round
    consecutivi dello stesso miner.
- **Anti-correlazione esplorativa residuo ↔ variazione successiva della quota spettante**
  (r = −0,20, p = 0,002).
  - *Causa:* non identificata; nessun input del motore la spiega.
  - *Serve:* rifare lo stesso calcolo su `whale-sqrt` e `regional-feedback`. Se compare in tutte, è
    probabilmente una proprietà della media per blocco di `p_theoretical` dentro l'epoca, non del
    protocollo.

## 6. Conclusione

Sulla run completa (50 epoche, 4 900 blocchi wPoA misurati) il meccanismo wPoA si comporta come
previsto dal modello su tutti e cinque gli assi. Questa run sostituisce quella interrotta dal
blackout e ne conferma le conclusioni con il triplo dei dati.

- **Affidabilità della sortition: conforme.** L'elezione segue il peso effettivo con una balena da
  0,73: quota osservata 0,7431 contro 0,7349 spettante, χ² aggregato p = 0,36, 11/250 violazioni di
  Wilson (12,5 attese), 1 rigetto per epoca su 50, spiegato dal setup. Log-rapporti con pendenza
  1,048; il GLM, ricalibrato, è dentro la sua nulla.
- **Qualità della randomness: conforme.** `E_i` 1,0001 pubblico e 1,0045 privato, argmin di
  `score_norm` 0,503–0,504, score del vincitore vero uniforme (KS p = 0,77), Prop. 5.17 entro il
  rumore dopo la correzione per confronti multipli.
- **Efficacia dello smorzamento:** non applicabile per costruzione (`dump-function = none`: i
  pannelli prima e dopo lo smorzamento coincidono). È il **riferimento non compresso** della terna
  `none`/`sqrt`/`log`: il 74,3 % osservato è la quota da cui `sqrt` (45,1 % spettante, 46,7 %
  osservato) scende preservando l'ordinamento.
- **Efficacia del malus: conforme.** Nessuna violazione iniettata e effetto esattamente nullo: M = 0
  e Psi = 1 in 255/255 celle.
- **Stabilità del block time: conforme.** Media 8,064 s contro 8, nessuna deriva per terzi, `Phi`
  mai saturato e non oscillante. In più, 0,06 % di inversioni reali e fork risolte sempre verso lo
  score migliore, con reorg di profondità 1.

I punti aperti riguardano **l'harness e gli strumenti di analisi, non il protocollo**: due aziende
cadute al bootstrap, blocchi di setup nell'epoca 2 e l'H0 del GLM mal specificata. L'eccesso di
ripetizioni (+1,2 punti condizionati) resta un rilievo minore da confrontare con le run gemelle.
