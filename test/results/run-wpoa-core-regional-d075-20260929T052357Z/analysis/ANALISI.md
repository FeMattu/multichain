# Analisi della run run-wpoa-core-regional-d075-20260929T052357Z

Run: `test/results/run-wpoa-core-regional-d075-20260929T052357Z`
Timestamp UTC della run: 2026-09-29T05:23:57Z
Catena: `wpoa-core-regional-d075` — profilo: `test/config/profiles/core/regional-d075.yaml` — regime: core
Analisi prodotta il: 2026-09-29

> **Scopo della run.** È il terzo punto dello sweep su `wpoa-sortition-delta`. Ripete
> `regional-feedback` (δ = 0,5) e `regional-d025` (δ = 0,25) con **δ = 0,75**, cioè
> `Delta_max = 6 s` e timer fra 2 e 14 s. Mappa, nodi, seed, traffico e parametri del weight engine
> sono gli stessi (`lambda_w = 0,99`). La run è completa: 30 epoche misurate (2–31), 2 900 round
> wPoA, sulle stesse altezze 221–3 120 della run d025.

> **⚠ Difetto dell'harness, ripetuto:** `company-16` (cluster di miner-1) non rispondeva alla
> registrazione della membership (`company-16 is unreachable`, 1 riga in
> [phase1/rpc_errors.csv](phase1/rpc_errors.csv)). Miner-1 lavora quindi con **5 aziende invece di
> 6**; gli altri cluster ne hanno 6. Tutte le quote spettanti usano i pesi effettivamente pubblicati.

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-regional-d075` | `manifest.json` → `chain_name` |
| seed dell'esperimento | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/regional-d075.yaml` | `manifest.json` → `profile_path` |
| regime | `core`, mappa `regional` (20 siti, 7 hub); latenza peggiore sul percorso 5,137 ms | `manifest.json` → `fabric` |
| nodi | 1 admin, 2 CA, 5 miner, 30 aziende (38); **29 aziende attive** | `manifest.json` → `nodes`; `phase2/epoch_engine.csv` |
| composizione dei cluster | 6 aziende per miner da profilo; miner-1 con **5 effettive** | `clusters.json`, `phase2/epoch_engine.csv` |
| epoche | 30 da 100 blocchi; misurate 2–31 (epoca 1 in setup), la 31 parziale (21 blocchi) | `manifest.json` → `epochs`, `measured_epochs` |
| altezza finale / esito | 3124 contro un target di 3120; `status = ok` | `manifest.json`, `shutdown.json` |
| **funzione di smorzamento** | `none` → `g(w) = w` | `phase1/config.csv` |
| `target-block-time` | 8 s | `phase1/config.csv` |
| **banda del delay `delta`** | **0,75** → `Delta_max = 6,0 s` | `phase1/config.csv` → `wpoa-sortition-delta` |
| guadagno della correzione `lambda` | 0,3 | `phase1/config.csv` |
| bound del feedback `M` | `min(0,5·8; 8·0,25/0,3) = min(4; 6,67) = 4,0 s`; ammissibilità `Delta_max = 6 ≤ T − λM = 6,8` ✓ | derivato |
| parametri malus | `mu` 0,5; `M_max` 3; punti equiv 4, badweight 2, selfwrite 1, delay 0,25 | `phase1/config.csv` |
| stato del malus | meccanismo **attivo**; **nessuna violazione iniettata** (`malicious.enabled = false`) | `phase1/config.csv`; `malicious_manifest.json` |
| weight engine | `weight-kappa` 100; `weight-lambda` = **0,99**; `weight-alpha` 0,2 (**inerte**) | `phase1/config.csv` |
| `setup-first-blocks` | 220 | `phase1/config.csv` |
| `mining-diversity` / `mining-turnover` | 0,0 / 0,5 | `phase1/config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10¹⁴ (premine) | `phase1/config.csv` |
| traffico | aziende 30–60 tx/epoca; restituzioni 0–20/epoca da 50–250; ESG in [1,100] | `manifest.json` → `traffic` |
| lookback RANDAO | 101 | `phase1/config.csv` |
| log di runtime | `sortition_miner_log: true`, `fork_score_log: true`, `wpoa_debug: false` | `manifest.json` → `runtime` |

**ESG certificati** (35, tutti sullo stream): miner-2 75, miner-1 56, miner-3 55, miner-4 49,
miner-0 29.

**Pesi effettivi alla prima epoca misurata (epoca 2)**, esito stocastico di `ESG × tau`, non una
configurazione:

| validatore | peso | `p_theoretical` epoca 2 |
|---|---:|---:|
| miner-4 (15DYQJRiwguo…) | 9 181 | 0,267 |
| miner-3 (1MgyqAAoHga7…) | 8 037 | 0,234 |
| miner-2 (19jgv4CLCbqX…) | 7 591 | 0,225 |
| miner-1 (1p4ZFF6nSbR8…) | 5 905 | 0,171 |
| miner-0 (1K6qD6z4WnZh…) | 3 492 | 0,102 |

Con `lambda_w = 0,99` il peso è `W_k·(0,99·rho + 0,01)`, quindi segue `rho` quasi per intero. Il
rapporto fra il peso massimo e il minimo varia fra 1,9 e 6,2 da un'epoca all'altra (media 3,8).

## 2. Executive summary

- **Randomness pulita sugli score privati**, cioè su quelli con cui si vota. `E_i` ha media 1,0023
  (`√n·D` 1,09) e l'argmin di `score_norm` 0,502 (`√n·D` 0,57). Lo score del vincitore vero è
  uniforme (KS p = 0,90), e Prop. 5.17 privata dà 1,0005 (z = 0,03). Il punto aperto di d025 (1,035)
  si chiude qui. `E_i` sullo score **pubblico** HMAC ha media 0,978, fuori banda (z = −2,65), ma il
  KS non rigetta (p = 0,09) e quello score non partecipa all'elezione: lieve scostamento.
- **Sortition proporzionale al peso nell'aggregato:** χ² = 1,47 sui 2 900 blocchi wPoA (TV 0,0086),
  nessuna quota fuori Wilson.
- **Per epoca c'è una sovradispersione** che le run δ = 0,5 e δ = 0,25 non mostravano. Il GoF
  rigetta in **5 epoche su 30** (1,5 attese, binomiale p = 0,016), e la deviazione standard del
  residuo standardizzato è 1,12 (nulla 1,00, p = 0,03). Si concentra nelle epoche 5–8. Non viene
  dalla rete (le inversioni finali sono 0), né da pesi diversi fra nodo e pipeline, né da
  correlazioni seriali della VRF. È un **lieve scostamento da indagare** (§5).
- **Legge di scala di Prop. 5.18 confermata anche allargando la banda.** Da `Delta_max` 4 a 6 s le
  inversioni istantanee passano dall'11,2 % al **7,6 %** (fattore 1,47, contro 1,5 della legge
  lineare e 1,56 della simulazione). Le fork passano dal 21,5 % al **15,0 %** e il margine privato
  medio da 2,27 a **3,40 s**. Un rumore simmetrico con σ ≈ 0,37 s riproduce il tasso e chi ne
  beneficia.
- **Nessuna inversione finale** su 2 900 round. In tutte le 435 fork la catena tiene il blocco di
  score minimo.
- **Block time sul target ma più disperso:** media 8,057 s, deviazione standard **3,50 s** (2,44 a
  δ = 0,5, 1,24 a δ = 0,25). `Phi` arriva al massimo al 77 % di M, senza saturare.
- **Weight engine esatto; con `lambda_w = 0,99` la retroazione si vede.** La Spearman `rho → peso`
  vale 0,60 (p ≈ 0). Il malus non ha effetto (Psi = 1 in 155/155 celle).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (A.1, score pubblico)
  - **Cosa misura**: `E_i = score_public · weight_effective`, che deve essere `Exp(1)`.
  - **Osservato**: n = 14 505; media **0,9780** (z = −2,65); mediana 0,685 (ln 2 = 0,693); coda
    oltre 3 pari al 4,4 % (atteso 5,0 %); KS `√n·D` = **1,240** (p ≈ 0,09). Per (epoca, miner) la
    deviazione standard dello z della media è 0,99: lo scarto non è concentrato.
  - **Atteso**: media in [0,984; 1,016]; `√n·D` ≤ 1,358.
  - **Giudizio**: **lieve scostamento**. La media esce dalla banda (−2,2 %), ma il KS non rigetta.
    Lo score pubblico HMAC verifica la formula, non l'ordinamento: la sortition gira sullo score
    privato, che è pulito (sotto). Nelle altre run della campagna lo stesso test dava 1,000–1,005.
    Una sola deviazione a 2,6 σ su più run è compatibile col caso.
- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (A.2, score pubblico)
  - **Osservato**: minimo di `score_norm_public` per round su 2 901 round, media **0,4955**, `√n·D` =
    0,749. Sulle righe `is_winner` la media sale a 0,809, come atteso per uno score pubblico
    indipendente dal voto.
  - **Giudizio**: **conforme**.
- **File**: `analysis/private/priv_d075.json` (score **privati**, §3.5.1)
  - **Osservato**: `E_i` su 14 500 coppie: media **1,0023** (banda ±0,0163), `√n·D` = **1,092**.
    Per miner fra 0,997 e 1,012 (banda ±0,036). Argmin di `score_norm`: media **0,5018**,
    `√n·D` = 0,573. Autocorrelazione degli score uniformizzati a ritardo 1, 2, 5, 10, 50, 100 e 101
    fra −0,047 e +0,052 (errore standard 0,019), e correlazioni fra miner nello stesso round fra
    −0,039 e +0,026: nessuna struttura.
  - **Giudizio**: **conforme**.
- **File**: [phase3/timer_race.md](phase3/timer_race.md) (Q2, score vero del vincitore)
  - **Osservato**: 2 900 round; media **0,5018**; KS p = **0,896**.
  - **Atteso**: U(0,1) se vince l'argmin.
  - **Giudizio**: **conforme**.
- **File**: [phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
  - **Osservato** (pubblico): miner-4 (15DYQJRiwguo…) 0,938 (730, KS p 0,18); miner-2
    (19jgv4CLCbqX…) 0,952 (839, p 0,52); miner-0 (1K6qD6z4WnZh…) 0,981 (278, p 0,16); miner-3
    (1MgyqAAoHga7…) 1,031 (657, p 0,06); miner-1 (1p4ZFF6nSbR8…) 1,040 (396, p 0,10). Sugli score
    **privati**: media **1,0005** su 2 901 round (z = 0,03, `√n·D` 0,94), per designato fra 0,955 e
    1,061.
  - **Atteso**: media 1, KS non significativo.
  - **Giudizio**: **conforme**. Il gap privato di d025 (1,035, z = 1,87), segnalato come da
    ricontrollare, qui è 1,0005: era una fluttuazione.
- **A.3**: `score_norm_mismatch_public` massimo 5,4·10⁻¹⁵, 0 righe non nulle su 14 505. **Conforme.**

### 3.2 Correttezza meccanica del delay

- **File**: [phase3/consistency_checks.csv](phase3/consistency_checks.csv),
  [plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
  - **Osservato**: 0 righe su 14 505 oltre 1,5 ms; massimo 6,6·10⁻¹⁴ s. La formula del delay regge
    anche con δ = 0,75 e `Phi` fino a ±3 s.
  - **Giudizio**: **conforme**.

### 3.3 Quota di blocchi contro peso

- **File**: [phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [plots/weight_vs_election.png](plots/weight_vs_election.png)
  - **Osservato** (pooled della pipeline, 2 921 blocchi):

    | validatore | `p_theoretical` | `p_hat` | Wilson 95 % |
    |---|---:|---:|---|
    | miner-2 (19jgv4CLCbqX…) | 0,2918 | 0,2889 | [0,2728; 0,3056] |
    | miner-4 (15DYQJRiwguo…) | 0,2514 | 0,2516 | [0,2362; 0,2677] |
    | miner-3 (1MgyqAAoHga7…) | 0,2185 | 0,2253 | [0,2105; 0,2408] |
    | miner-1 (1p4ZFF6nSbR8…) | 0,1415 | 0,1356 | [0,1236; 0,1485] |
    | miner-0 (1K6qD6z4WnZh…) | 0,0968 | 0,0983 | [0,0880; 0,1096] |

    Riga `all`: χ² 1,49, p = 0,83. Sui soli 2 900 blocchi wPoA: χ² = 1,47, TV = 0,0086.
  - **Giudizio**: **conforme**. Scarto massimo 0,7 punti (miner-3), ogni quota dentro il proprio
    intervallo.
- **File**: [phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png)
  - **Osservato**: **10 violazioni su 150** (7,5 attese, binomiale p = 0,22), nelle epoche 5, 6, 7,
    8, 13, 16, 18 e 25; miner-4 in 4 di esse. Larghezza media dell'intervallo 0,150.
  - **Giudizio**: **conforme** come conteggio; il raggruppamento nelle epoche 5–8 è discusso sotto.
- **File**: [phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [plots/p_value_uniformity.png](plots/p_value_uniformity.png)
  - **Osservato**: **5 rigetti su 30**: epoche 6 (p = 0,004; miner-4 45 blocchi contro 27,9), 25
    (0,007; miner-0 20 contro 10,1), 8 (0,009; miner-2 43 contro 28,9 e miner-4 17 contro 27,7), 7
    (0,022; miner-2 16 contro 28,1) e 16 (0,025; miner-3 39 contro 27,3). Il round-by-round dà gli
    stessi p entro 0,002. KS dei p-value contro U(0,1): p = 0,44; binomiale sul numero di rigetti:
    **p = 0,016**. Deviazione standard del residuo standardizzato per (epoca, validatore) **1,126**
    (miner-0 1,26, miner-4 1,24, miner-1 0,90). Sui vincitori designati dagli score privati,
    epoche complete 3–30: 1,122, contro 0,997 della nulla simulata (2 000 repliche round per round,
    P(≥ osservato) = 0,03).
  - **Atteso**: 1,5 rigetti, sd del residuo ≈ 1.
  - **Giudizio**: **lieve scostamento da indagare**. Le cause ordinarie sono escluse una a una.
    (i) Non è la timer race: le inversioni finali sono 0, e i designati hanno la stessa
    sovradispersione dei vincitori. (ii) Non sono pesi diversi fra nodo e pipeline: la media di
    `E_i` privato per (epoca, miner), calcolata con i pesi della pipeline, ha z con deviazione
    standard 1,03 e nelle epoche rigettate resta entro ±2,5. (iii) Non è una correlazione seriale
    della VRF (§3.1). (iv) L'epoca 2 non è coinvolta: sui suoi 79 blocchi wPoA χ² = 1,02. Resta una
    sovradispersione a 2 σ, concentrata in quattro epoche consecutive, su una run di 30 epoche. Le
    run δ = 0,5 (sd 1,00 su 99 epoche) e δ = 0,25 (2 rigetti su 30) non la mostrano.

### 3.4 Comportamento longitudinale

- **File**: [phase3/longitudinal.md](phase3/longitudinal.md),
  [phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv)
  - **Osservato**: GLM β1 = **1,104** [1,016; 1,192], "NOT consistent" rispetto a 1. Nulla simulata
    (1 000 repliche multinomiali sulle `p_theoretical` reali, stessa IRLS): **1,061** [0,972; 1,149].
    Log-rapporti: pendenza **1,060**, intercetta −0,004, r = 0,877 (300 coppie). Sign test: p =
    0,0001 (miner-4), 0,0008 (miner-3), 0,003 (miner-0), 0,17 (miner-1), 0,42 (miner-2).
  - **Giudizio**: **conforme**. β1 sta dentro la sua nulla corretta: il "NOT consistent" è di nuovo
    l'H0 mal specificata. Il sign test, molto più potente che nelle run a `lambda_w = 0,5` perché
    i pesi variano fino a ×3, mostra la quota che segue il peso per 3 validatori su 5 a p < 0,01.

### 3.5 Timer race, margine e inversioni

- **File**: [phase3/timer_race.md](phase3/timer_race.md) (Q1)
  - **Osservato**: `corr(dt_prev, delay_true)` = **0,9926**, la più alta della campagna perché la
    banda (12 s) è larga rispetto al rumore; residuo medio 0,053 s, deviazione standard 0,426 s
    (per terzi 0,415 / 0,420 / 0,443 s).
  - **Giudizio**: **conforme**.
- **File**: [plots/margin_distribution.png](plots/margin_distribution.png),
  [phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv)
  - **Osservato**: margine pubblico medio 3,446 s; KS contro la simulazione esatta p = **0,875**;
    KS contro `Beta(1,n)` p = 0 (straw man). Margine privato medio 3,40 s (mediana 2,51 s), con il
    15,4 % dei round sotto 0,5 s.
  - **Giudizio**: **conforme**. Il margine cresce in proporzione alla banda: 1,19 → 2,27 → 3,40 s
    per δ = 0,25 → 0,5 → 0,75, con rapporti 1,91 e 1,50 contro 2 e 1,5.
- **File**: [phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
  - **Osservato**: `S1` = 0,000377 s; `S2` pubblico 4,69 s; bound pubblico 1,0 (**vacuo**);
    "inversioni" pubbliche 76,2 %.
  - **Giudizio**: **conforme come audit del modello, non informativo**: lo score pubblico è
    indipendente da quello del voto. Il tasso reale è in §3.5.1.
- **Vantaggio del miner uscente**
  - **Osservato**: ripetizione 0,2487 contro 0,2403 simulata (p = 0,16). Il designato privato
    coincide con l'uscente nel 24,9 % dei round, contro il 24,3 % atteso. Il lag dell'uscente
    (0,60 s contro 1,58 s degli altri) non diventa un vantaggio, perché il timer è ancorato al padre
    in 15 419 righe su 15 419.
  - **Giudizio**: **conforme**.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Fonte: `chains/miner-{0..4}/wpoa-core-regional-d075/debug.log`, letti come root dal container e
copiati in `analysis/private/`. Li analizza `analysis/private/priv.py`, lo stesso script di d025.
Copertura completa: **5 miner su 5, 2 900 round su 2 900**.

- **(a) Sortition privata.** Quote designate contro spettanti: miner-2 0,289/0,292, miner-4
  0,252/0,251, miner-3 0,227/0,218, miner-1 0,137/0,141, miner-0 0,096/0,097; χ² = 1,47 (p ≈ 0,83).
  **Conforme.**
- **(b) Inversioni reali.** **0 su 2 900** (Wilson 95 % [0; 0,13 %]), 0 / 0 / 0 per terzi.
  `true_winner_mismatch` = 0. **Conforme.**
- **(c) Fork.** Il **15,0 %** dei round (435/2 900) ha più di un blocco alla stessa altezza, fino a
  5, con 676 orfani; per terzi 15,0 / 15,4 / 14,6 %. In **435 fork su 435** la catena finale tiene
  il blocco di score minimo. Sulle 2 194 valutazioni contese la regola per score sceglie il blocco
  finale nel 100 % dei casi, quella nativa nel 61,3 %. Il **primo blocco arrivato non era
  l'argmin in 221 round (7,6 %)**. Le 1 300 `displace` vanno tutte verso lo score migliore.
  Ci sono 219 `defer` (7,6 % dei round) e nessun rilascio per scadenza. Le riorganizzazioni hanno
  tutte profondità 1. Un nodo resta al massimo 1,46 s su un blocco poi orfano. **Conforme.**
- **(d) Prop. 5.18 sui delay reali.** Monte-Carlo con rumore simmetrico sui delay privati:
  σ = 0,35 s → 7,3 %, σ = 0,4 s → 8,3 %; il 7,6 % osservato corrisponde a **σ ≈ 0,37 s**. La quota
  delle inversioni istantanee che va all'uscente è osservata al 21,7 % (26,8 % fra gli eleggibili,
  48/179), simulata al 22 % (28 %). Con un vantaggio di 0,1 s all'uscente la simulazione darebbe il
  30 % (36 %): il modello simmetrico spiega meglio i dati. Bound gaussiano completo (m = 5,
  σ = 0,35 s, `Delta_max` = 6 s): **0,091**, sopra il 7,6 % osservato; Chebyshev 0,66; primo
  termine 0,103. Per terzi 8,4 / 7,6 / 6,9 %: nessuna crescita. **Conforme.**

**Confronto dello sweep**, sulle stesse altezze 221–3 120:

| | δ = 0,25 (d025) | δ = 0,5 (feedback) | δ = 0,75 (d075) |
|---|---:|---:|---:|
| margine privato medio | 1,19 s | 2,27 s | 3,40 s |
| fork | 32,1 % | 21,5 % | 15,0 % |
| inversioni istantanee | 16,3 % | 11,2 % | 7,6 % |
| σ simmetrico implicito | 0,32 s | 0,34 s | 0,37 s |
| bound gaussiano (σ = 0,35 s) | 0,340 | 0,145 | 0,091 |
| blocchi trattenuti (`defer`) | 23,0 % | 12,1 % | 7,6 % |
| inversioni finali | 6 (0,21 %) | 1 (0,03 %) | 0 |
| block time (sd) | 8,01 s (1,24) | 8,06 s (2,44) | 8,06 s (3,50) |

Da δ = 0,5 a 0,75 il fattore sulle inversioni istantanee è 11,2/7,6 = 1,47, contro l'1,5 della
legge lineare `m·σ/Delta_max`, che qui vale 0,29 ed è nel regime in cui il primo ordine basta.

### 3.6 Stabilità del block time e correzione globale

- **File**: [phase2/round_level.csv](phase2/round_level.csv), [plots/phi_over_time.png](plots/phi_over_time.png)
  - **Osservato**: `dt_prev` medio **8,057 s**, mediana 8, deviazione standard **3,50 s**, fra 1 e
    15 s. Per terzi 8,12 / 8,11 / 7,94 s; per epoca fra 7,38 (la 31, parziale) e 8,59 s. `Phi`: 67
    valori distinti, media −0,058 s, deviazione standard 0,865 s, range [−3,08; +2,83] s, **0 round a
    ±M**, 12,5 % di cambi di segno, autocorrelazione a ritardo 1 pari a 0,88.
  - **Atteso**: media al target; con la banda più larga la spaziatura eredita la dispersione del
    timer vincente, che cresce con `Delta_max`.
  - **Giudizio**: **conforme** (+0,7 % sul target). Il prezzo della banda larga è la dispersione
    (3,50 s contro 2,44 e 1,24), e `Phi` lavora più forte (fino al 77 % di M) ma senza saturare.
    `phi_consistent = FAIL` non è un difetto.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv)
  - **Osservato**: errore massimo **1,2·10⁻¹⁶** su `W_k_raw` e **1,0·10⁻¹⁴** sulla ricorsione. ESG
    costanti (75/56/55/49/29). 115/115 verifiche `weightverifyweights` `ok`.
  - **Giudizio**: **conforme**.
- **File**: [phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png)
  - **Osservato**: `rho` media 0,0087, deviazione standard 0,0054, massimo 0,023, 3,3 % di zeri.
    Il fattore `0,99·rho + 0,01` varia fra 0,010 e 0,033 (×3,3). Spearman lag-1 `rho → peso`:
    **0,596** (p ≈ 0, n = 150). Gini(pubblicato) − Gini(input): pendenza 1,3·10⁻⁴ per epoca
    (p = 0,70).
  - **Atteso**: con `lambda_w = 0,99` il peso segue `rho`.
  - **Giudizio**: **conforme**. Unica run dello sweep in cui la retroazione domina il peso:
    medie per miner fra 6 890 (miner-0) e 20 951 (miner-2).
- **ESG / aziende**: `certified_scores_reflected_in_the_engine` FAIL (non critico) per 18Vk8VF65N7Q… =
  **company-16**, morta al bootstrap. **Difetto dell'harness**, non del protocollo.

### 3.8 Concentrazione

- **File**: [phase2/epoch_concentration.csv](phase2/epoch_concentration.csv),
  [plots/concentration_over_time.png](plots/concentration_over_time.png)
  - **Osservato**: aggregato HHI teorico 0,2255 contro osservato 0,2257; N_eff 4,43; Nakamoto(1/2) =
    2; Gini osservato 0,199.
  - **Giudizio**: **conforme** (scarto 0,1 %). Per epoca l'HHI osservato oscilla per la varianza
    multinomiale e, nelle epoche 5–8, per la sovradispersione di §3.3.

### 3.9 Streak e ripetizioni

- **File**: [phase3/streak.md](phase3/streak.md)
  - **Osservato**: `L_max` aggregato 9 contro 7,44 simulato (p = 0,18); ripetizione 0,2487 contro
    0,2403 (p = 0,16). Per epoca: `L_max` con p < 0,05 in 3 epoche su 30 (5: 0,007; 15: 0,021;
    20: 0,035), ripetizione in 1 (11: 0,042).
  - **Atteso**: 1,5 rigetti per test.
  - **Giudizio**: **conforme**. Il 5 è l'epoca in cui miner-4 vince 47 blocchi (sovradispersione
    di §3.3), non un effetto seriale: le autocorrelazioni della VRF sono nulle.

### 3.10 Malus

Caso **J.1** (nessuna violazione iniettata).

- **File**: [phase2/malus_state.csv](phase2/malus_state.csv),
  [phase3/malus_invariants.csv](phase3/malus_invariants.csv)
  - **Osservato**: M = 0 e Psi = 1 in **155/155** celle; invarianti veri ovunque; 119 945 campioni
    con Psi in [0,1]; `weight_effective == weight_raw` in 14 505/14 505 righe. Funnel, rilevazioni e
    tassi vuoti; `malus_effectiveness.md` non presente.
  - **Giudizio**: **conforme**.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv)
  - **Osservato**: punto 1 (Spearman con i blocchi vinti): `w_k_published` 0,80, `W_k_raw` 0,67,
    `earnings_g_k` 0,53, `companies_contribution_sum` 0,47, `income` 0,11, `miner_activity` 0,09.
    Punto 2 (residui): tutte fra −0,03 e +0,06 (p ≥ 0,48, n = 150), compresi `rho` e `R_k`.
  - **Giudizio**: **conforme**. Nessun canale fuori dal peso.

### 3.12 Integrità della run e controlli di consistenza

- **Critici 7/7 PASS** ([phase3/consistency_checks.csv](phase3/consistency_checks.csv)); non critici:
  `phi_consistent` FAIL (atteso), `certified_scores_reflected_in_the_engine` FAIL (company-16),
  traffico nel range (983 coppie).
- **RPC**: 405 errori, tutti fra 05:24 e 05:38Z (bootstrap): 4 × 101 "Round not evaluable" e la
  registrazione fallita di company-16.
- **Esito**: `status = ok`, altezza 3124 ≥ 3120, `true_winner_mismatch` 0.
- **Epoca 2**: contiene 21 blocchi di setup; sui 79 wPoA χ² = 1,02, nessun artefatto qui.
- **Ultima epoca (31)**: 21 blocchi, esclusa dalle tendenze.
- File `STOP` nella radice della run: segnale di arresto del launcher, a run già completata.

## 4. Punti di forza

- **Zero inversioni finali** su 2 900 round e 435/435 fork chiuse sul blocco di score minimo.
- **Legge di scala di Prop. 5.18 verificata su tre punti.** Inversioni istantanee 16,3 → 11,2 →
  7,6 % per `Delta_max` 2 → 4 → 6 s. Da 4 a 6 s il fattore è 1,47, contro 1,5 della legge lineare.
  Il rumore implicito resta σ ≈ 0,32–0,37 s, e il modello simmetrico riproduce anche chi beneficia
  delle inversioni.
- **Randomness privata pulita**: `E_i` 1,0023, argmin 0,502, Q2 p = 0,90, Prop. 5.17 1,0005.
- **Proporzionalità aggregata**: χ² 1,47, TV 0,86 %, log-rapporti con pendenza 1,06.
- **Retroazione del motore misurabile** (Spearman 0,60) con identità esatte a 10⁻¹⁴.

## 5. Punti critici / da approfondire

- **Sovradispersione per epoca** (5/30 rigetti del GoF, p = 0,016; sd del residuo 1,12, p = 0,03).
  - *Entità:* concentrata nelle epoche 5–8, fino a 17 blocchi di scarto su 100 (miner-4 nell'epoca 6).
  - *Escluso:* timer race (0 inversioni), pesi diversi fra nodo e pipeline (`E_i` privato per cella
    coerente), correlazione seriale o incrociata della VRF, contaminazione del setup.
  - *Causa più probabile:* fluttuazione a ~2 σ; l'aggregato non ne risente (χ² p = 0,83).
  - *Serve:* ripetere δ = 0,75 con un altro seed o più a lungo, e ricalcolare la stessa statistica
    sulla sovradispersione dei designati per d025 e feedback, per vedere se esiste una dipendenza
    da δ.
- **`E_i` pubblico a 0,978** (z = −2,65, KS non rigettato). Non tocca l'elezione; da ricontrollare
  sulla ripetizione.
- **company-16 caduta al bootstrap**: quinta run con lo stesso difetto; serve il controllo di
  liveness nell'orchestratore.
- **GLM "NOT consistent"**: H0 mal specificata (nulla simulata 1,061 [0,972; 1,149]).

## 6. Conclusione

- **Affidabilità della sortition: conforme nell'aggregato, lieve scostamento per epoca.** χ² 1,47
  su 2 900 blocchi, 0 inversioni finali; 5/30 epoche rigettate, non spiegate dalla rete né dai pesi.
- **Qualità della randomness: conforme** sugli score che eleggono (`E_i` privato 1,0023, Q2
  p = 0,90, Prop. 5.17 1,0005); lieve scostamento sulla forma pubblica (0,978).
- **Smorzamento:** non applicabile (`g(w) = w`).
- **Malus: conforme**, effetto nullo in 155/155 celle.
- **Block time: conforme**, 8,057 s, `Phi` mai saturato. La dispersione cresce con la banda (sd
  3,50 s): è il costo di `Delta_max` = 6 s, che in cambio dimezza quasi le fork rispetto a δ = 0,5
  e porta le inversioni istantanee al 7,6 %.

Lo sweep su δ è completo: allargare la banda riduce inversioni istantanee e fork secondo la legge
di Prop. 5.18, e aumenta la dispersione del block time. Il tasso finale resta sotto lo 0,3 % in tutti
e tre i punti grazie al tie-break per score.
