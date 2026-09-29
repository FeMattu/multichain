# Analisi della run run-wpoa-core-regional-malus-20260924T222732Z

Run: `test/results/run-wpoa-core-regional-malus-20260924T222732Z`
Timestamp UTC della run: 2026-09-24T22:27:32Z
Catena: `wpoa-core-regional-malus` — profilo: `test/config/profiles/core/regional-long23h-malus.yaml` — regime: core
Analisi prodotta il: 2026-09-26

Legenda validatori (da `addresses.json`):
miner-0 (15zsBvdzvXq5…), miner-1 (1GZPygyFoqJf…), miner-2 (1M2Z3c6Q3rkh…, **malicious**),
miner-3 (1GFDvF9QCMYD…, **malicious**), miner-4 (1AAGMioT948a…).

> **Premessa metodologica.** Il sistema è stocastico su più livelli indipendenti: score ESG
> estratti a caso in [1,100], traffico aziendale in [30,60] tx/epoca, restituzioni in [0,20]
> per epoca, VRF per ogni candidato e round, e (regime `core`) la rete emulata. Nessun giudizio
> è dato su singoli blocchi o round: solo su tendenze aggregate, con intervalli di confidenza e
> tenendo conto dei confronti multipli (con N test ad α = 0,05 sono attesi 0,05·N rigetti).

---

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| Nome catena | `wpoa-core-regional-malus` | [manifest.json](../manifest.json) `chain_name`; [analysis/phase1/config.csv](phase1/config.csv) |
| Seed esperimento | 20260905 | manifest.json `seed` |
| Profilo | `test/config/profiles/core/regional-long23h-malus.yaml` | manifest.json `profile_path` |
| Regime | `core` (CORE, rete emulata) | manifest.json `fabric.backend` |
| Topologia | `regional`: 20 siti, 7 hub, 34 link | manifest.json `fabric.topology` |
| Latenza peggiore sul percorso | 5,137 ms (RTT peggiore 10,3 ms) | manifest.json `derived.worst_path_delay_ms`, `worst_round_trip_s` |
| Nodi per ruolo | 1 admin, 2 CA, 5 miner, 30 aziende (38 totali) | manifest.json `nodes` |
| Cluster | 6 aziende per miner (company-k → miner-(k mod 5)) | [clusters.json](../clusters.json) |
| Epoche | 100 pianificate × 100 blocchi; 101 misurate (epoca 101 parziale, 21 blocchi) | manifest.json `epochs`, `measured_epochs` |
| Altezza finale / target | 10123 (manifest) / 10120 (target); 10120 in `blocks.csv` | manifest.json `final_height`, `derived.target_height` |
| Esito | `status = ok`, `error` vuoto | manifest.json |
| `dump-function` | `none` (g(w) = w) | config.csv |
| `target-block-time` T_block | 8 s | config.csv |
| `wpoa-sortition-delta` δ | 0,5 ⇒ Δ_max = 4 s; banda d_i ∈ (−4, +4) s | config.csv |
| `wpoa-sortition-lambda` λ | 0,3 | config.csv |
| Bound del feedback M | min(0,5·8, 8·0,5/0,3) = min(4; 13,3) = **4 s** | derivato |
| Parametri malus | μ = 0,5; M_max = 3; p(Equiv) = 4; p(BadWeight) = 2; p(SelfWrite) = 1; p(Delay) = 0,25 | config.csv |
| `enable-wpoa-malus` | `true` (meccanismo sempre attivo) | config.csv |
| Violazioni iniettate | **sì**: `malicious.enabled = true` | manifest.json `malicious`, [malicious_manifest.json](../malicious_manifest.json) |
| Piano malicious | miner-2 e miner-3; `target_action_rate` = 0,4; azioni selfwrite 0,4 / badweight 0,6; finestra epoche 20–60; 1 opportunità/epoca/miner | malicious_manifest.json |
| `weight-kappa` κ | 100 | config.csv |
| `weight-lambda` λ_w | 0,99 | config.csv |
| `weight-alpha` | 0,2 (**parametro inerte**, validato e mai letto) | config.csv |
| `weight-epoch-length` | 100 | config.csv |
| `setup-first-blocks` | 220 (richiesti 220; floor di protocollo 109) | config.csv; manifest.json `derived` |
| `mining-diversity` | 0,0 (non vincolante) | config.csv |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | config.csv |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10^14 (premine 3 500 000 unità) | config.csv; manifest.json `derived.premine` |
| `wpoa-randao-lookback` | 101 | config.csv |
| Traffico | `company_tx_per_epoch_range` [30,60]; `miner_gas_returns_per_epoch_range` [0,20]; `esg_score_range` [1,100]; `restitution_amount_range` [50,250]; stream `supply-chain-events` | manifest.json `traffic` |
| Treasury | 1DBWsUn58PHw… (`weight-treasury-address` in params.dat = `[null]`, il treasury è configurato lato harness) | [treasury.txt](../treasury.txt); config.csv |
| Divergenze manifest ↔ config.csv | nessuna sui parametri di protocollo | confronto diretto |

**Pesi effettivi alla prima epoca misurata.** Non sono una configurazione: sono l'esito
stocastico di ESG × attività (seed 20260905). Fonti:
[phase1/esg_events.csv](phase1/esg_events.csv), [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
[phase2/epoch_level.csv](phase2/epoch_level.csv).

| Validatore | ESG miner | W_k grezzo ep. 1 | w pubblicato ep. 1 (in vigore a inizio ep. 2) | p teorica inizio ep. 2 | w pubblicato ep. 2 |
|---|---:|---:|---:|---:|---:|
| miner-0 (15zsBvdzvXq5…) | 29 | 105,85 | 10 585 | 0,099 | 3 512 |
| miner-1 (1GZPygyFoqJf…) | 56 | 174,16 | 17 416 | 0,163 | 6 324 |
| miner-2 (1M2Z3c6Q3rkh…) | 75 | 284,25 | 28 425 | 0,266 | 7 699 |
| miner-3 (1GFDvF9QCMYD…) | 55 | 240,35 | 24 035 | 0,225 | 8 094 |
| miner-4 (1AAGMioT948a…) | 49 | 262,15 | 26 215 | 0,246 | 9 181 |

Il rapporto max/min è ≈ 2,7: **non c'è una balena**, come tipico di queste run. Il crollo di
scala fra epoca 1 e 2 (×≈0,01) è la retroazione con λ_w = 0,99 e ρ ≈ 0 (§3.7).

---

## 2. Executive summary

- **La randomness è pulita su entrambe le fonti.** Score privati VRF (dai `debug.log`, 49 295
  campioni): media di E_i = 0,9982 contro 1 (banda ±0,0088), √n·D = 0,58 < 1,36; minimo dello
  score_norm per round ~ U(0,1) con media 0,5029, KS p = 0,17. Prop. 5.17: gap standardizzato
  medio fra 0,961 e 1,031 per i 5 vincitori, nessun KS significativo.
- **Il meccanismo è deterministico e ricalcolabile:** 0 mismatch di delay su 49 295 righe
  (max 5,7·10⁻¹⁴ s); le identità del weight engine tornano con errore relativo ≤ 1,6·10⁻¹⁴.
- **La sortition privata è esattamente pesata** (vincitore designato vs quota teorica: χ² = 7,16,
  df = 4, p = 0,13), **ma la catena non la rispetta del tutto:** il 13,2 % dei round (1307/9879)
  è vinto da un candidato diverso dal designato, e l'**87,5 %** di queste inversioni va al
  **miner uscente**. Il tasso cresce nel tempo (11,4 % → 12,7 % → 15,6 % per terzo di run).
- **Conseguenze visibili sulle metriche di quota:** ripetizioni 0,361 contro 0,243 attese
  (repeat p < 0,05 in 80/100 epoche), 53 violazioni di Wilson contro 25 attese, 10/100 rigetti
  GoF contro 5 attesi (binomiale p = 0,028), GLM β₁ = 1,163 (IC 95 % [1,113; 1,213]). Sulla
  run intera la quota consegnata resta però vicina a quella spettante (TV = 0,015, MAE = 0,006).
- **Il block time non converge al target:** 9,39 s medi contro 8 s, in deriva (9,11 → 9,32 →
  9,74 s). Φ non è saturato (a −M in 0,01 % dei round) ma è negativo nel 98 % dei round:
  errore a regime di un controllo proporzionale troppo debole (λ = 0,3), a fronte di un ritardo
  di elaborazione che cresce (residuo 1,35 → 2,12 s).
- **Il malus funziona end-to-end:** 33/33 azioni confermate rilevate (precision = recall = 1),
  0 falsi positivi su 505 record onesti esaminati, latenza di attivazione esattamente 1 epoca,
  invarianti rispettati ovunque, decadimento μ^k esatto, miner-3 escluso (Ψ = 0) nell'epoca 48
  e 0 blocchi vinti su 100 round. Il BadWeight resta in vigore per il 92 % dell'epoca in cui è
  pubblicato, ma il bilancio netto dell'attacco è negativo (−19 % blocchi attesi per miner-2,
  −16 % per miner-3 rispetto al controfattuale onesto).
- **Nessun canale di influenza non documentato:** a quota spettante fissata, i residui non
  dipendono da guadagno, volume o attività (|ρ parziale| ≤ 0,062, p ≥ 0,17).

---

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (score pubblico HMAC)
  - **Cosa misura**: E_i = score_public · weight_effective, sulle 49 295 righe non-setup con peso > 0.
  - **Osservato**: media 1,0074; √n·D = 0,884.
  - **Atteso**: media 1 ± 1,96/√n = 1 ± 0,0088; √n·D ≤ 1,358.
  - **Giudizio**: **conforme** — media entro la banda (scarto 0,74 % < 0,88 %), KS ben sotto la
    soglia. Nota: è lo score *pubblico* (regola 10 della GUIDA), verifica la formula, non l'elezione.
- **File**: `candidate_long.csv` — minimo di `score_norm_public` per round (A.2)
  - **Osservato**: 9 879 round, media 0,4973, √n·D = 0,889.
  - **Atteso**: U(0,1), media 0,5, √n·D ≤ 1,358.
  - **Giudizio**: **conforme** (scarto sulla media 0,003).
- **File**: `candidate_long.csv` — coerenza della normalizzazione (A.3)
  - **Osservato**: max |score_norm_mismatch_public| = 7,0·10⁻¹⁵.
  - **Atteso**: 0 entro tolleranza.
  - **Giudizio**: **conforme**.
- **File**: `chains/miner-*/wpoa-core-regional-malus/debug.log` (score **privati**, estratti
  come root tramite il container `./docker/mcsim`)
  - **Cosa misura**: E_i = score privato · w_eff, per ogni miner e ogni round valutato sul tip finale.
  - **Osservato**: n = 49 295, media 0,9982, √n·D = 0,58 (p = 0,89). Per miner: medie 1,0051
    (miner-0), 1,0028 (miner-1), 1,0013 (miner-2), 0,9844 (miner-3), 0,9975 (miner-4); nessun
    KS per miner sotto 0,05 (minimo p = 0,081 per miner-3).
  - **Atteso**: Exp(1).
  - **Giudizio**: **conforme** — test primario della VRF superato sulla fonte che conta.
- **File**: [analysis/phase3/timer_race.md](phase3/timer_race.md), `phase2/round_level.csv`
  (`score_norm_true`, test Q2)
  - **Osservato**: media dello score_norm vero del *vincitore effettivo* 0,5115 (round in gara:
    0,4878), KS p ≈ 0; 459 round (4,6 %) vinti in cima alla banda; score_true·W_tot del
    vincitore ha media 1,356 invece di 1.
  - **Atteso**: U(0,1) solo se vince sempre l'argmin.
  - **Giudizio**: **lieve scostamento**, spiegato: il test Q2 fallisce perché il 13,2 % dei
    blocchi non è prodotto dall'argmin (§3.5.1). Sul minimo privato del round (argmin vero) la
    distribuzione è U(0,1) con p = 0,17: il difetto non è nella VRF.

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  (`delay_recompute_mismatch_rounds_is_zero`), [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [analysis/plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
  - **Cosa misura**: |D ricalcolato − D loggato| per ogni round e candidato.
  - **Osservato**: 0 round in mismatch su 101 epoche; max |Δ| = 5,7·10⁻¹⁴ s su 49 295 righe;
    `delay_recompute_ok_public` vero ovunque.
  - **Atteso**: 0 con tolleranza 1,5 ms.
  - **Giudizio**: **conforme**. Inoltre lo score privato loggato dal miner vincente coincide con
    `score_true` ricalcolato dal reveal VRF del blocco (errore relativo mediano 7·10⁻¹⁰ su 9 878 round).

### 3.3 Quota di blocchi contro peso

`dump-function = none`: la quota attesa è w_eff / Σ w_eff (dopo malus), senza compressione.

- **File**: [analysis/phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [analysis/phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [analysis/plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png)
  - **Cosa misura**: copertura dell'intervallo di Wilson 95 % sulla quota spettante, per (epoca, validatore).
  - **Osservato**: 53 violazioni su 500 (10,6 %); larghezza media dell'intervallo 0,148.
    Distribuzione: miner-0 2, miner-1 12, miner-2 14, miner-3 16, miner-4 9; per finestra:
    10/90 (ep. 2–19), 22/210 (ep. 20–61, malus attivo), 21/200 (ep. 62–101). La heatmap mostra
    violazioni sparse, non blocchi contigui su un validatore. La varianza degli scarti
    standardizzati (O − E)/√(Bp(1−p)) è 1,32 invece di 1.
  - **Atteso**: 0,05 · 500 = 25 violazioni.
  - **Giudizio**: **scostamento significativo da indagare** — 2,1× l'atteso. La sovradispersione
    del 32 % è quella prodotta da esiti non indipendenti fra round consecutivi (ripetizioni in
    eccesso, §3.9): con autocorrelazione positiva la varianza di O_i è più grande di quella
    binomiale su cui è costruito Wilson. La causa è il vantaggio del miner uscente (§3.5.1),
    non la sortition.
- **File**: [analysis/phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [analysis/plots/p_value_uniformity.png](plots/p_value_uniformity.png), `wpoa_epoch_tests.csv`
  - **Cosa misura**: GoF congiunto per epoca e uniformità dei p-value.
  - **Osservato**: 10 rigetti su 100 epoche (epoche 19, 36, 41, 46, 54, 67, 86, 87, 88, 98);
    KS dei p-value contro U(0,1): D = 0,188, p = 0,0014; binomiale sul conteggio p = 0,028.
    L'istogramma ha 20 epoche nel primo decile e 2 nell'ultimo. `share_changes_within_epoch` è
    vero in 100/100 epoche: la colonna di riferimento è quindi `gof_mc_round_by_round_p`, che dà
    gli stessi rigetti (es. ep. 87: 0,0006). Il report dice "11 di 101" includendo la riga `all`.
  - **Atteso**: 5 rigetti, p-value uniformi.
  - **Giudizio**: **scostamento significativo da indagare**, della stessa natura della riga
    sopra: eccesso di p-value piccoli coerente con esiti correlati. TV medio per epoca 0,091.
- **File**: `weight_vs_election.md`, riga "Pooled" e riga `all` del test congiunto
  - **Osservato**: quote pooled (teorica → osservata): miner-0 0,1048 → 0,0995; miner-1 0,1626
    → 0,1527 (fuori Wilson [0,1458; 0,1599]); miner-2 0,2444 → 0,2516; miner-3 0,2109 →
    0,2163; miner-4 0,2774 → 0,2794. χ² aggregato = 12,18, p = 0,016 (round-by-round p =
    0,008); TV = 0,0149, MAE = 0,0060.
  - **Atteso**: aderenza; un rigetto sull'aggregato con MAE piccolo indica un effetto sistematico
    piccolo ma reale.
  - **Giudizio**: **lieve scostamento** — effetto reale ma di 1 punto percentuale al massimo: i due
    miner più leggeri perdono quota (−0,5 e −1,0 p.p.) a favore dei più pesanti. È la firma
    dell'amplificazione dovuta al vantaggio del miner uscente (chi vince più spesso è più spesso
    uscente).
- **File**: [analysis/plots/weight_vs_election.png](plots/weight_vs_election.png)
  - **Osservato**: lo scatter spettante/osservato è allineato alla diagonale fra 0 e 0,55; i
    punti estremi (0,54–0,60) sono le epoche con BadWeight gonfiato di miner-2 (21, 26).
  - **Giudizio**: **conforme** a livello visivo, coerente con i numeri sopra.
- **File**: [analysis/plots/election_share_distribution.png](plots/election_share_distribution.png),
  [analysis/plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png),
  [analysis/phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv)
  - **Osservato**: residui p̂ − p per validatore centrati vicino a 0; i residui correlano con la
    quota spettante stessa (Spearman 0,139, p = 0,002).
  - **Atteso**: residui indipendenti dal peso.
  - **Giudizio**: **lieve scostamento**, stessa causa (super-proporzionalità, §3.4).
- **Smorzamento**: `none`, quindi nessuna compressione attesa né osservata.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](phase3/longitudinal.md),
  [analysis/phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv),
  [analysis/plots/longitudinal_logratio.png](plots/longitudinal_logratio.png),
  [analysis/plots/sign_test_by_validator.png](plots/sign_test_by_validator.png)
  - **Cosa misura**: risposta della quota al peso fra epoche.
  - **Osservato**: GLM logit β₁ = 1,163, IC 95 % [1,113; 1,213], n = 499, converged = True,
    **non consistente con 1**. Log-rapporti: pendenza 1,082, intercetta 0,003, Pearson r =
    0,876 su 996 coppie. Sign test: p = 0,0004 (miner-4), 2,7·10⁻⁵ (miner-3), 5,5·10⁻⁵
    (miner-1), < 10⁻⁵ (miner-2); miner-0 p = 0,67 (concordanza 0,48 su 85 coppie
    informative: il suo peso varia poco, 3 400–6 200).
  - **Atteso**: β₁ = 1, pendenza 1, intercetta 0.
  - **Giudizio**: **scostamento significativo da indagare** su β₁ (+16 %), di segno opposto alla
    compressione da latenza descritta nel prompt: qui la quota risponde al peso **più** che
    proporzionalmente. Spiegazione coerente con §3.5.1: il vantaggio del miner uscente premia
    chi vince spesso, e chi vince spesso è chi pesa di più. La monotonia peso → quota è
    confermata per 4 miner su 5.

### 3.5 Timer race, margine e inversioni

- **File**: [analysis/phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [analysis/plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
  - **Cosa misura**: gap standardizzato (score₍₂₎ − score₍₁₎)·(W_tot − w_eff,i*) ~ Exp(1).
  - **Osservato**: media 0,961 (miner-0, n = 981), 1,004 (miner-1), 1,002 (miner-2), 1,000
    (miner-3), 1,031 (miner-4); KS p fra 0,054 e 0,82.
  - **Atteso**: media 1, KS non significativo.
  - **Giudizio**: **conforme** — scarti ≤ 3,9 %, nessun p < 0,05.
- **File**: [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv),
  [analysis/plots/margin_distribution.png](plots/margin_distribution.png)
  - **Osservato**: G medio 2,285 s (mediana 1,776 s) contro 2,280 s della simulazione esatta,
    KS p = 0,905. KS contro Beta(1,n): p ≈ 0 (media attesa 1,333 s).
  - **Atteso**: KS di riferimento non rigettato; il Beta(1,n) è uno **straw man** e ci si aspetta
    che rigetti con pesi non uniformi.
  - **Giudizio**: **conforme**. Il rigetto del Beta(1,n) non è un rilievo.
- **File**: [analysis/phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [analysis/plots/sigma_decomposition.png](plots/sigma_decomposition.png)
  - **Osservato**: σ_S1 (topologia) = 0,38 ms (misurato, regime core); σ_S2 (residuo di
    scheduling, pubblico) = 3,15 s; σ_S2b = 1,92 s su 7 554 inversioni pubbliche.
  - **Giudizio**: **conforme** come decomposizione: la rete emulata è irrilevante (0,38 ms contro
    Δ_max = 4 s); la fonte di rumore è interna ai nodi. σ_S2 è calcolato sui delay pubblici e
    sovrastima il rumore vero (residuo vero: media 1,71 s, sd 1,10 s).
- **File**: `wpoa_timer_race.csv`, [analysis/plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
  - **Osservato**: bound Prop. 5.18 = 1,000; MC con σ_S2 = 0,506; tasso di inversione pubblico
    0,765 (7 554/9 879); per epoca media 0,765.
  - **Atteso**: il tasso pubblico vale ≈ 1 − 1/n = 0,8 per costruzione, perché lo score pubblico
    HMAC è indipendente da quello privato con cui si è votato.
  - **Giudizio**: **non informativo**: bound saturato a 1 (vacuo) e tasso pubblico artefatto. Il
    tasso di inversione vero è in §3.5.1.
- **Vantaggio del miner uscente** (da `round_level.csv` e dai timestamp dei `debug.log`)
  - **Osservato**: il miner che ha prodotto il blocco h−1 arma il timer per h in media **0,28 s**
    dopo il timestamp del blocco padre; gli altri candidati dopo **1,73 s** (9 901 e 39 504
    osservazioni, risoluzione 1 s). Il vantaggio cresce per terzo di run: 1,12 s → 1,42 s →
    1,81 s (uscente 0,11/0,27/0,45 s; altri 1,23/1,69/2,25 s). Il residuo vero
    `residual_true_s` cresce in parallelo: 1,35 → 1,65 → 2,12 s. La latenza di rete è 5 ms e
    `txcount` per blocco è stabile (15,0–15,1), quindi il ritardo è elaborazione locale del
    blocco ricevuto, non propagazione né carico transazionale (Spearman residuo↔txcount 0,003).
  - **Giudizio**: **scostamento significativo da indagare** — è la causa delle inversioni reali
    misurate sotto.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Copertura: **score privati di 5 miner su 5, 9 879 round su 9 879 misurati**, tutti completi.
I `chains/<node>/…/debug.log` sono di proprietà di root; sono stati letti eseguendo `grep`
dentro il container `./docker/mcsim` e tenendo solo le valutazioni fatte sul tip finale (91,8 %
delle righe `wPoA-sortition`; le altre riguardano tip poi orfani).

- **(a) Sortition privata.**
  - E_i privato: media 0,9982, KS p = 0,89 (§3.1). Minimo per round: score_norm medio 0,5029,
    KS p = 0,17.
  - Designato uguale al vincitore del round precedente: 24,5 % contro 24,3 % atteso dalle quote:
    **nessuna correlazione nella sortition stessa**.
  - Quote dei designati contro quote teoriche: miner-0 0,0997/0,1048; miner-1 0,1579/0,1626;
    miner-2 0,2484/0,2444; miner-3 0,2183/0,2108; miner-4 0,2756/0,2774; χ² = 7,16, df = 4,
    p = 0,13.
  - **Giudizio: conforme** — l'elezione privata è esattamente la sortition pesata del Teorema 5.3.
- **(b) Inversioni reali.**
  - Tasso complessivo: **13,23 %** (1 307/9 879). Per terzo: 11,4 % → 12,7 % → 15,6 %.
  - L'**87,5 %** delle inversioni (1 143/1 307) va al miner uscente (85,9 % / 88,3 % / 87,9 %
    per terzo). Il designato non è mai l'uscente nei round invertiti (0 %).
  - Il vincitore effettivo aveva in media un delay 0,52 s peggiore del designato (mediana
    0,36 s; fino a 5,4 s quando vince l'uscente, max 2,05 s negli altri casi).
  - Le quote *consegnate* (0,0993/0,1522/0,2519/0,2164/0,2800) si discostano dai designati
    esattamente nella direzione vista in §3.3 (i pesanti guadagnano).
  - **Giudizio: scostamento significativo da indagare.**
- **(c) Fork** (eventi `[wpoa-fork]` e `UpdateTip`).
  - Altezze con più di un blocco proposto: 2 125 su 9 900 (**21,5 %**); candidati per round: 2
    (9 987 righe), 3 (540), 4 (30).
  - Profondità massima di riorganizzazione: **1 blocco** (5 462 riorganizzazioni, tutte di 1).
  - Tie-break per score: sulle altezze contese il blocco finale è quello di score migliore fra i
    contendenti nel **99,8 %** dei casi. La regola nativa (primo ricevuto) avrebbe scelto il blocco
    finale solo nel 48,9 %: il tie-break per score cambia la scelta in 2 119 altezze, cioè
    evita ≈ 2 100 inversioni che altrimenti si sommerebbero alle 1 307 residue. Le 1 307
    inversioni restanti sono quindi round in cui il designato **non ha mai proposto** (timer
    annullato dall'arrivo del blocco dell'uscente: 240 `retarget-abort` solo su miner-0).
  - Tempo massimo su un tip poi orfano: 13 s (media 1,06 s, p99 6 s, 5 535 episodi).
  - **Giudizio: conforme** per la safety (reorg ≤ 1, convergenza rapida) e per l'efficacia del
    tie-break.
- **(d) Prop. 5.18 sui delay reali.** Simulazione su tutti i round con i delay privati reali:
  - Rumore simmetrico gaussiano: σ = 0,40 / 0,45 / 0,55 s per terzo riproduce il tasso
    (11,5 / 13,0 / 15,3 %), ma solo il **20–22 %** delle inversioni andrebbe all'uscente.
  - Vantaggio sistematico all'uscente a + jitter σ = 0,2 s: a = **0,60 / 0,70 / 0,80 s** per
    terzo riproduce tasso (11,3 / 12,6 / 14,3 %) **e** beneficiario (86,5 / 88,1 / 89,1 % contro
    85,9 / 88,3 / 87,9 % osservati).
  - Il bound analitico con σ ≈ 0,45 s, n = 5, Δ_max = 4 s vale ≈ 1,02: **vacuo**.
  - **Giudizio: scostamento significativo da indagare.** Il modello con vantaggio all'uscente
    vince nettamente, e il vantaggio stimato cresce nel tempo, parallelo al ritardo di
    elaborazione (§3.5).

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`, `phi_s`),
  [analysis/plots/phi_over_time.png](plots/phi_over_time.png)
  - **Cosa misura**: convergenza della spaziatura realizzata a T_block e comportamento di Φ.
  - **Osservato**:
    - dt medio 9,388 s (sd 2,376, mediana 9 s, n = 9 878), **+17 %** sul target.
    - Per terzo 9,11 / 9,32 / 9,74 s; media per epoca fra 8,75 s (ep. 12) e 10,55 s
      (ep. 101, parziale); 87 epoche su 100 sopra 9 s, nessuna sotto 7 s.
    - Delay vero del vincitore medio 7,68 s (7,75 → 7,62), residuo medio 1,71 s (1,35 → 2,12).
    - Φ: media −1,36 s, mediana −1,33 s, range [−4,0; +0,92], 57 valori distinti. Φ < 0 nel
      98,1 % dei round; Φ = −M solo nello 0,01 % dei round; |Φ| ≥ 0,9·M nello 0,05 %; cambi di
      segno nel 2,2 % dei round. La mediana mobile scende da ≈ −1,1 a ≈ −1,8 s (figura).
    - λ·Φ medio ≈ −0,41 s.
  - **Atteso**: media → 8 s; Φ piccolo, né saturato né oscillante.
  - **Giudizio**: **scostamento significativo da indagare.** Non è saturazione (M = 4 s quasi mai
    raggiunto) né oscillazione (segno quasi costante): è l'**errore a regime** di un controllo
    proporzionale. Con λ = 0,3 una correzione di −1,36 s su Φ sposta i timer di soli −0,41 s,
    mentre il ritardo di elaborazione aggiunge 1,7–2,1 s crescenti. Cause plausibili: λ troppo
    basso rispetto al disturbo, disturbo non stazionario (crescita del costo di elaborazione con
    la lunghezza della catena, contesa di CPU fra 38 daemon sullo stesso host). La rete emulata
    (5 ms) è esclusa.
- **File**: `consistency_checks.csv`, `phi_consistent`
  - **Osservato**: FAIL, 57 valori distinti di Φ.
  - **Giudizio**: **conforme** — atteso, il check è una sonda di non-regressione tarata su run con
    feedback spento; Φ varia per costruzione.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [analysis/phase3/weight_engine_epoch.csv](phase3/weight_engine_epoch.csv)
  - **Identità W_k = ESG_Mk·(τ_Mk + Σ c_i)**: errore relativo max 3,9·10⁻¹⁶ su 505 righe.
    **Conforme.**
  - **Ricorsione w_k = W_k·(ρ_prev·λ_w + 1 − λ_w)** per e ≥ 2: errore relativo max 1,6·10⁻¹⁴;
    epoca 1: w_k = W_k esatto. **Conforme.** Il peso pubblicato è 100 × w_k_final arrotondato
    all'intero (rapporto 99,988–100,014): è una convenzione di scala, non uno scostamento.
  - **ESG statici**: 1 valore distinto per miner su 101 epoche (29, 56, 75, 55, 49), 35
    pubblicazioni ESG tutte presenti sullo stream. **Conforme.**
- **File**: [analysis/phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [analysis/plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [analysis/plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)
  - **Osservato**: ρ **non** identicamente nullo: media 0,0025, sd 0,0016, range [0; 0,0060],
    simile fra miner (0,0024–0,0027). Con λ_w = 0,99 il fattore 0,99·ρ + 0,01 va da 0,010 a
    0,016: ρ sposta il peso fino a ×1,59. Spearman lag-1 ρ(e) → w(e+1): 0,75 / 0,65 / 0,78 /
    0,83 / 0,84 per miner-0/1/2/3/4, pooled 0,345 (p ≈ 0, n = 500).
  - **Atteso**: retroazione visibile se ρ ha varianza apprezzabile.
  - **Giudizio**: **conforme** — il canale endogeno è attivo e domina la variazione del peso
    *entro* ciascun miner. Il pooled è più basso perché fra miner il livello è fissato da ESG ×
    attività. ρ è piccolo in assoluto perché il saldo iniziale dei miner è ≈ 600 200 unità di premine.
- **File**: [analysis/plots/weights_over_time.png](plots/weights_over_time.png),
  [analysis/plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png)
  - **Osservato**: pesi grezzi stazionari e rumorosi; Spearman epoca → peso pubblicato fra −0,135
    e +0,085, tutti p > 0,17. Ordinamento stabile: miner-0 il più leggero (media 4 799), miner-1
    7 460, poi miner-3 11 153, miner-4 12 798, miner-2 13 173. I picchi del pannello "raw" nelle
    epoche 20–60 (fino a 53 317) sono i record BadWeight dei miner malicious; i pannelli "after
    malus" e "final" coincidono (smorzamento `none`).
  - **Atteso**: peso che segue l'attività, rumoroso perché τ è riestratto ogni epoca.
  - **Giudizio**: **conforme** — nessuna tendenza spuria; i miner "più attivi" non crescono nel
    tempo perché l'attività è estratta i.i.d. per epoca.
- **File**: [analysis/phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [analysis/plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png)
  - **Osservato**: pendenza di Gini(pubblicato) − Gini(input) = 2,4·10⁻⁵ per epoca, intercetta
    0,0089, Spearman 0,016 (p = 0,87).
  - **Atteso**: pendenza non positiva.
  - **Giudizio**: **conforme** — il motore non amplifica la disuguaglianza dei propri input.
- **File**: [analysis/plots/esg_scores.png](plots/esg_scores.png) e `plots/esg_scores/`
  - **Osservato**: ESG miner 29–75; aziende uniformi in [1,100] come da configurazione.
  - **Giudizio**: **conforme**.

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](phase2/epoch_concentration.csv),
  [analysis/phase3/report.md](phase3/report.md) §3,
  [analysis/plots/concentration_over_time.png](plots/concentration_over_time.png)
  - **Osservato**: sull'intera run HHI teorico 0,2185 contro osservato 0,2216 (N_eff 4,58 contro
    4,51), Gini osservato 0,184, Nakamoto 1/2 = 2. Per epoca l'HHI osservato supera spesso il
    teorico (es. ep. 13: 0,272 contro 0,224); i picchi teorici (0,35 in ep. 21, 0,35 in ep. 26,
    0,31 in ep. 46) coincidono con i BadWeight gonfiati in vigore.
  - **Atteso**: HHI osservato per epoca più alto del teorico per pura varianza multinomiale con
    100 blocchi; confronto affidabile sulla riga aggregata.
  - **Giudizio**: **conforme** sull'aggregato (+1,4 % di HHI). L'eccesso per epoca è in parte
    artefatto di campione, in parte gonfiato dalle ripetizioni (§3.9). Nessuna soglia di Nakamoto
    peggiore del teorico sull'aggregato.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](phase3/streak.md), `wpoa_epoch_tests.csv`
  - **Cosa misura**: vittorie consecutive e probabilità di ripetizione contro un Monte-Carlo sugli
    stessi pesi.
  - **Osservato**: probabilità di ripetizione media 0,361 contro 0,239 del MC; p < 0,05 in
    **80/100 epoche**. Sui dati di round: 0,361 contro 0,243 attesa; eccesso presente per ogni
    miner (miner-0 0,227/0,110; miner-1 0,266/0,172; miner-2 0,399/0,285; miner-3 0,377/0,241;
    miner-4 0,412/0,292) e stabile per terzo (0,347 / 0,377 / 0,357). L_max: p < 0,05 in 10/100
    epoche (es. streak di 13 in ep. 37, 12 in ep. 7).
  - **Atteso**: 5 epoche con p < 0,05.
  - **Giudizio**: **scostamento significativo da indagare** — l'esito dei round non è
    indipendente. Il seed si rinfresca correttamente (designato = uscente nel 24,5 % contro 24,3 %
    atteso, §3.5.1(a)), quindi la dipendenza nasce nella timer race: è il vantaggio del miner
    uscente. +0,118 di ripetizioni ≈ 13,2 % di inversioni × 87,5 % a favore dell'uscente ≈ 0,116.
    I conti tornano.

### 3.10 Malus

Caso **J.2**: violazioni iniettate.

- **File**: [analysis/phase3/malus_effectiveness.md](phase3/malus_effectiveness.md),
  [analysis/phase3/malus_funnel.csv](phase3/malus_funnel.csv),
  [analysis/phase3/malus_rate.csv](phase3/malus_rate.csv),
  [analysis/plots/malus_action_funnel.png](plots/malus_action_funnel.png)
  - **Osservato**: 82 opportunità → 33 tentativi → 33 inviate → 33 confermate → 33 malus validi
    (13 selfwrite, 20 badweight). Tasso realizzato 0,402 contro 0,400 (IC 95 % [0,303; 0,511]);
    per miner 0,439 contro 0,433 (miner-2) e 0,366 contro 0,367 (miner-3). Delay/equiv non
    iniettabili (rifiutati dal loader), come da piano.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/malus_detection.csv](phase3/malus_detection.csv),
  [analysis/phase1/malus_detections.csv](phase1/malus_detections.csv)
  - **Osservato**: TP = 33, FP = 0, FN = 0; precision = recall = F1 = 1,000 per entrambi i
    kind. Il detector ha inoltre esaminato e **rifiutato** 505 record badweight corretti ("the
    published weight is CORRECT").
  - **Giudizio**: **conforme** — la proprietà di safety (nessuna penalità senza evidenza) regge
    su 505 casi negativi.
- **File**: [analysis/phase3/malus_latency.csv](phase3/malus_latency.csv),
  [analysis/plots/malus_detection_latency.png](plots/malus_detection_latency.png)
  - **Osservato**: latenza di rilevazione 0 blocchi per tutte le 33; attivazione esattamente 1
    epoca per tutte.
  - **Atteso**: attivazione ≥ 1 epoca (record dell'epoca e agisce da e+1).
  - **Giudizio**: **conforme**, al minimo di protocollo.
- **File**: [analysis/phase2/malus_state.csv](phase2/malus_state.csv),
  [analysis/plots/malus_state_trajectory.png](plots/malus_state_trajectory.png)
  - **Osservato**: M > 0 solo per miner-2 e miner-3 e solo dall'epoca 21. Esempi: miner-3 M =
    1,0 (ep. 21) → 0,5 → 0,25 → 0,125 nelle epoche pulite, cioè μ^k esatto. Dopo l'ultima
    azione (ep. 59–60) M decade da 2,64 (miner-2, ep. 60) a 1,2·10⁻¹² (ep. 101), con Ψ ≥ 0,99
    dall'epoca 67. `epochs_to_clear` vale 0 ovunque tranne miner-3 in ep. 48 (M = 3,069 ≥ 3):
    ⌈ln(3,069/3)/ln 2⌉ = ⌈0,033⌉ = 1, coerente.
  - **Giudizio**: **conforme** — reversibilità e decadimento esatti, nessun ban permanente.
- **Esclusione a peso nullo** (`candidate_long.csv`)
  - **Osservato**: miner-3 in epoca 48: Ψ = 0 in tutti i 100 round, w_eff = 0, **0 blocchi
    vinti** (senza malus ne avrebbe attesi 24).
  - **Giudizio**: **conforme**.
- **Effetto sulla quota** (`candidate_long.csv`; [analysis/phase3/malus_weight_effect_matched.csv](phase3/malus_weight_effect_matched.csv),
  [analysis/plots/malus_weight_effect.png](plots/malus_weight_effect.png))
  - **Osservato**: nei round con Ψ < 1 la quota osservata segue quella corretta da Ψ, non quella
    grezza. miner-2: 7 900 round, Ψ medio 0,764, osservata 0,244 contro 0,235 attesa con Ψ e
    0,280 senza Ψ. miner-3: 8 000 round, Ψ medio 0,792, osservata 0,210 contro 0,207 con Ψ e
    0,235 senza. Il confronto appaiato per banda ha una sola coppia per banda (n = 1): differenza
    malicious − onesti = −0,32 nella banda media, **non conclusivo** per numerosità.
  - **Atteso**: riduzione della quota proporzionale a Ψ.
  - **Giudizio**: **conforme** — la riduzione osservata segue Ψ entro 1 p.p.
- **BadWeight in vigore** (`phase1/malicious_actions.csv`, `candidate_long.csv`,
  [analysis/phase1/verification.csv](phase1/verification.csv))
  - **Osservato**: ogni record BadWeight (gonfiato ×1,5–×2,95) resta il peso grezzo usato
    dall'elezione per il **92 %** dei round dell'epoca di pubblicazione (54 % e 75 % nei due casi
    pubblicati a metà epoca). Esempio: miner-2, epoca 21, 43 410 contro 16 670 veri → quota
    spettante 0,544, 60 blocchi vinti. `weightverifyweights` segnala 12 `mismatch` (tutti su
    record malicious) e 5 `other-epoch` all'epoca 76 (campione preso a cavallo di epoca, non un
    difetto).
  - **Controfattuale** (epoche 20–61, stessi round, pesi veri e Ψ = 1): blocchi attesi miner-2
    911,8 reali contro 1 132,2 onesti (**−19,5 %**); miner-3 792,4 contro 944,2 (**−16,1 %**).
    Osservati 958 e 773.
  - **Giudizio**: **lieve scostamento** rispetto a un'idea di malus "preventivo", ma è il
    comportamento documentato ("ha effetto finché nessuno lo confuta"): il guadagno dell'epoca
    gonfiata è più che compensato dalla penalità successiva (p(BadWeight) = 2 su M_max = 3 ⇒ Ψ =
    1/3). Con questi parametri l'attacco è in perdita netta.
- **File**: [analysis/phase3/malus_invariants.csv](phase3/malus_invariants.csv),
  [analysis/plots/malus_invariant_audit.png](plots/malus_invariant_audit.png)
  - **Osservato**: Ψ ∉ [0,1]: 0; w_eff ≠ round(w·Ψ): 0; validatore pulito con Ψ ≠ 1: 0 (su 409 590
    campioni di registro).
  - **Giudizio**: **conforme** — nessun rosso. I 3 miner onesti hanno M = 0 e Ψ = 1 in tutte le 101 epoche.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: `phase2/epoch_engine.csv`, `phase3/weight_election_residuals.csv`
  - **Osservato (punto 1)**, Spearman con `n_blocks_won_epoch` su 500 (epoca, miner):
    w_k_published 0,692; W_k_raw 0,663; companies_contribution_sum 0,507; earnings_g_k 0,440;
    income 0,091; miner_activity 0,080 (p = 0,07); R_k 0,084 (p = 0,06).
  - **Osservato (punto 2)**, residui p̂ − p: correlazione grezza con earnings_g_k 0,120 (p =
    0,007) e con companies_contribution_sum 0,126 (p = 0,005). Queste correlazioni passano per
    la quota spettante (residuo ↔ p_theoretical 0,139, p = 0,002, cioè la super-proporzionalità
    di §3.4). **A p_theoretical fissata** la correlazione parziale svanisce: earnings 0,062 (p =
    0,17), contribution 0,057 (p = 0,20), income −0,007 (p = 0,88), attività −0,008 (p = 0,86).
  - **Atteso**: correlazione al punto 1 mediata dal peso, nulla al punto 2.
  - **Giudizio**: **conforme** — nessun canale di influenza non documentato. La correlazione
    guadagno ↔ blocchi è anche in parte inversa (i blocchi portano fee: Spearman 0,425 nella
    stessa epoca).

### 3.12 Integrità della run e controlli di consistenza

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)

| check | critico | esito |
|---|---|---|
| `registry_weights_finite_and_positive` | sì | PASS (409 590 campioni) |
| `no_phantom_validator_in_registry` | sì | PASS |
| `malus_finite_and_psi_in_unit_interval` | sì | PASS |
| `delay_recompute_mismatch_rounds_is_zero` | sì | PASS |
| `phi_consistent` | no | FAIL, atteso (§3.6) |
| `every_esg_publication_reached_the_stream` | sì | PASS (35/35) |
| `certified_scores_reflected_in_the_engine` | no | PASS |
| `traffic_counts_within_configured_range` | no | FAIL: 763/3465 coppie fuori range, vedi sotto |
| `only_miners_pay_the_treasury` | sì | PASS (5 097 pagamenti) |
| `malus_psi_in_unit_interval` | sì | PASS |
| `malus_effective_weight_matches_recompute` | sì | PASS |
| `malus_clean_validator_has_psi_one` | sì | PASS |
| `malus_detector_no_false_positives` | sì | PASS |
| `malus_confirmed_actions_were_detected` | no | PASS (33/33) |
| `at_least_one_fully_measured_epoch` | sì | PASS (100 epoche) |

  - **Giudizio**: **conforme** — tutti i 12 check critici passano.
- **File**: [analysis/phase2/epoch_traffic.csv](phase2/epoch_traffic.csv),
  [analysis/plots/traffic_per_epoch.png](plots/traffic_per_epoch.png)
  - **Osservato**: fino all'epoca 74 `onchain_stream_items` = `planned` = `sent` per tutte le
    aziende (rapporto 1,000). All'epoca 75 il rapporto scende a 0,63; dall'epoca 76 è 0 per
    tutte le 30 aziende. Le 763 coppie fuori range sono tutte aziende e tutte da ep. 75 in poi.
    Però `txcount` per epoca resta 1 470–1 620 (ep. 74: 1 469; 76: 1 574; 100: 1 544),
    `traffic_tx.csv` registra 1 383–1 432 tx per epoca fino a h = 10 120, e il motore vede
    attività piena (Σ contributi aziendali 654–740 per epoca, prima e dopo).
    `stream_items.csv` contiene **esattamente 100 000** righe di `supply-chain-events`, la
    prima dell'epoca 0 e l'ultima dell'epoca 75.
  - **Causa**: `test/bootstrap/rpc_client.py:303` legge `liststreamitems(stream, True, 100000, 0)`,
    cioè i primi 100 000 elementi. Lo stream ha superato quel numero durante l'epoca 75.
  - **Giudizio**: **lieve scostamento** — **difetto di raccolta dell'harness**, non del
    protocollo. Colpisce solo il check di traffico e la figura, non pesi né elezioni.
- **File**: `phase1/verification.csv`
  - **Osservato**: 413 `ok`, 12 `mismatch` (tutti record BadWeight di miner-2/miner-3,
    atteso), 5 `other-epoch` (ep. 76, campione a cavallo di epoca).
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase1/rpc_errors.csv](phase1/rpc_errors.csv)
  - **Osservato**: 408 errori, tutti "Round not evaluable" su `wpoalist*` (102 per metodo), tutti
    ad altezze ≤ 220 (setup, registro pesi non ancora disponibile), 0 dopo il setup.
  - **Giudizio**: **conforme**.
- **Esito e completezza**: `status = ok`, altezza 10 120 su 10 120. L'epoca 101 è parziale (21
  blocchi, Wilson larghi, GoF MC p = 0,12) ed è stata **trattata a parte**: nessuna tendenza è
  dedotta da essa. Epoca 1 esclusa (setup); l'epoca 2 contiene ancora i round 200–220 sotto
  round robin nativo (il test congiunto ne usa 95 blocchi).
- **Blocco orfano in `blocks.csv`**: `true_winner_mismatch` = 0 su 9 878 round con verdict
  `ok`. La fase 1 è quella corretta e `winner_address` è affidabile.

---

## 4. Punti di forza

- **VRF e sortition privata esatte:** E_i privato medio 0,9982 (KS p = 0,89, 49 295 campioni);
  argmin del round U(0,1) (p = 0,17); designati proporzionali al peso (χ² p = 0,13); Prop.
  5.17 con media 0,96–1,03 per tutti i vincitori.
- **Meccanismo ricalcolabile:** 0 mismatch di delay (max 5,7·10⁻¹⁴ s), score privato del
  vincitore uguale al reveal VRF (errore 7·10⁻¹⁰), identità del weight engine esatte (≤ 1,6·10⁻¹⁴).
- **Distribuzione del margine G esatta:** 2,285 s osservati contro 2,280 s simulati, KS p = 0,90.
- **Safety dei fork:** riorganizzazioni di profondità massima 1 blocco; il tie-break per score
  sceglie il contendente migliore nel 99,8 % delle 2 125 altezze contese (la regola nativa lo
  farebbe nel 49 %).
- **Malus completo e sicuro:** precision = recall = 1 su 33 azioni, 0 falsi positivi su 505
  record onesti, attivazione a 1 epoca, esclusione a Ψ = 0 con 0 blocchi vinti, decadimento μ^k
  esatto, 0 violazioni di invariante; quota dei penalizzati entro 1 p.p. dal valore corretto da
  Ψ; attacco BadWeight in perdita netta (−16/−20 % di blocchi attesi).
- **Retroazione del motore attiva e non concentrante:** Spearman ρ → peso successivo 0,65–0,84
  per miner; pendenza del Gini-delta 2,4·10⁻⁵ (p = 0,87); ESG statici.
- **Aggregato di run vicino al pesato:** TV = 0,015, MAE = 0,006, HHI 0,2216 contro 0,2185.
- **Nessun canale nascosto:** a quota spettante fissata, residui indipendenti da guadagno,
  volume e attività (|ρ| ≤ 0,062).

## 5. Punti critici / da approfondire

- **Vantaggio del miner uscente → inversioni reali (priorità alta).**
  - *Entità*: 13,2 % dei round invertiti, 87,5 % a favore dell'uscente; ripetizioni 0,361
    contro 0,243; tasso in crescita 11,4 → 15,6 %.
  - *Causa ipotizzata*: il miner uscente arma il timer ≈ 0,28 s dopo il blocco, gli altri dopo
    ≈ 1,73 s, perché devono ricevere ed elaborare il blocco. Il vantaggio effettivo stimato è
    0,6 → 0,8 s. Il ritardo di elaborazione cresce con la run (1,2 → 2,3 s), mentre la rete
    pesa 5 ms.
  - *Per confermare*: timestamp sub-secondo di ricezione del blocco e di armamento del timer
    per nodo (i `debug.log` hanno risoluzione 1 s); profilo di CPU dei daemon nella seconda
    metà della run; una run di controllo con meno aziende (meno contesa di CPU) o con il timer
    ancorato al timestamp del padre invece che alla ricezione.
- **Metriche di quota sovradisperse (conseguenza del punto sopra).**
  - *Entità*: 53 violazioni di Wilson contro 25 attese, varianza degli scarti 1,32; 10 rigetti
    GoF contro 5 (p = 0,028); β₁ = 1,163 [1,113; 1,213]; χ² aggregato p = 0,016 con TV = 0,015.
  - *Causa ipotizzata*: esiti correlati fra round consecutivi e amplificazione dei pesi alti.
  - *Per confermare*: rifare Wilson/GoF con varianza corretta per autocorrelazione (block
    bootstrap per epoca), oppure calcolarli sul **designato privato** invece che sul vincitore
    effettivo. Qui il designato dà già χ² p = 0,13 sull'intera run.
- **Block time sopra il target, in deriva (priorità media).**
  - *Entità*: 9,39 s contro 8 s (+17 %), da 9,11 a 9,74 s; Φ negativo nel 98 % dei round, mai
    saturato.
  - *Causa ipotizzata*: errore a regime di un controllo proporzionale con λ = 0,3 contro un
    ritardo di elaborazione di 1,7–2,1 s crescente.
  - *Per confermare*: run con λ più alto (vincolo Δ_max ≤ T − λM: con δ = 0,5 e M = 4 s è
    ammissibile fino a λ = 1) oppure con un termine integrale; misurare se il ritardo di
    elaborazione dipende dall'altezza (dimensione del registro, stream, wallet).
- **BadWeight efficace per un'epoca intera (priorità bassa, comportamento documentato).**
  - *Entità*: il peso gonfiato (fino a ×2,95) governa il 92 % dei round dell'epoca;
    miner-2 raggiunge una quota spettante di 0,544 all'epoca 21.
  - *Nota*: con p(BadWeight) = 2 e M_max = 3 l'attacco è in perdita netta. Con penalità più
    basse, o con violazioni a epoche alterne, potrebbe non esserlo: serve uno sweep dei parametri.
- **Troncamento della raccolta degli stream (harness).**
  - *Entità*: `stream_items.csv` si ferma a 100 000 righe (epoca 75), quindi 763 falsi "fuori
    range" e barre "on chain" nulle da ep. 76 in `traffic_per_epoch.png`.
  - *Correzione*: paginare `liststreamitems` in `test/bootstrap/rpc_client.py:303` (ciclo su
    `start`) e rigenerare la fase 1.
- **Confronto appaiato del malus non conclusivo**: una sola coppia per banda di peso. Servirebbe
  una run con più miner malicious e onesti per banda.

## 6. Conclusione

- **Affidabilità della sortition — buona nel nucleo, degradata in esecuzione.** L'elezione
  privata è esattamente proporzionale al peso effettivo (designati: χ² p = 0,13). La catena
  consegna però il 13,2 % dei blocchi a un candidato non designato, quasi sempre il miner
  uscente. Ne derivano ripetizioni in eccesso (0,36 contro 0,24), β₁ = 1,16 e 2× le violazioni
  di Wilson attese. Sull'intera run lo scarto resta piccolo (TV = 0,015).
- **Qualità della randomness — pienamente conforme.** E_i ~ Exp(1) sulle fonti pubblica
  (media 1,007) e privata (0,998); argmin ~ U(0,1); Prop. 5.17 con media ≈ 1 per ogni vincitore.
- **Efficacia dello smorzamento — non applicabile.** `dump-function = none`; con pesi entro un
  fattore ≈ 3 la proporzionalità lineare è quella attesa e osservata.
- **Efficacia del malus — pienamente conforme.** Rilevazione perfetta senza falsi positivi,
  latenza di 1 epoca, penalità proporzionale a Ψ, esclusione a Ψ = 0 rispettata, decadimento
  reversibile esatto, attacco non conveniente. Unico limite, documentato: il BadWeight vale per
  l'epoca in cui è pubblicato.
- **Stabilità del block time — non conforme.** 9,39 s contro 8 s, in deriva. Φ corregge nella
  direzione giusta senza saturare, ma λ = 0,3 non basta contro un ritardo di elaborazione che
  cresce. Lo stesso ritardo è all'origine del vantaggio del miner uscente: è il fenomeno da
  indagare per primo in questa run.
