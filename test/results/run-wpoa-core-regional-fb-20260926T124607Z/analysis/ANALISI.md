# Analisi della run run-wpoa-core-regional-fb-20260926T124607Z

Run: `test/results/run-wpoa-core-regional-fb-20260926T124607Z`
Timestamp UTC della run: 2026-09-26T12:46:07Z
Catena: `wpoa-core-regional-fb` — profilo: `test/config/profiles/core/regional-long23h-feedback.yaml` — regime: core
Analisi prodotta il: 2026-09-27

Legenda validatori (da [addresses.json](addresses.json)):
miner-0 (1Aq6DsGTu8oM…), miner-1 (1TfKWWNoCoR6…), miner-2 (17kNqikg3HNj…), miner-3 (1267AwvLrhT4…), miner-4 (1MGq3mjRuCmm…).

> **Premessa.** Il sistema è stocastico su più livelli indipendenti: score ESG estratti a caso
> in `[1,100]`, traffico per azienda estratto in `[30,60]` tx/epoca, restituzioni in `[0,20]`
> per epoca, VRF a ogni round e, in regime `core`, la rete emulata. I pesi sono quindi un
> *campione*, non una configurazione. Nessun giudizio è dato su singoli round o singole epoche:
> solo su aggregati, con intervalli di confidenza e correzione per confronti multipli
> (100 epoche misurate ⇒ ~5 rigetti attesi per puro caso a `alpha = 0.05`).

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| Nome catena | `wpoa-core-regional-fb` | [manifest.json](manifest.json) `chain_name` |
| Seed esperimento / seed analisi | 20260905 / 20260905 | `manifest.json` `seed`; [analysis/phase3/report.md](analysis/phase3/report.md) |
| Profilo | `test/config/profiles/core/regional-long23h-feedback.yaml` | `manifest.json` `profile_path` |
| Regime | `core` (CORE, mappa emulata) | `manifest.json` `fabric.backend` |
| Topologia | `regional`: 20 siti, 7 hub, 34 link | `manifest.json` `fabric.topology.*` |
| Latenza peggiore sul percorso | 5,137 ms (RTT 10,3 ms) | `derived.worst_path_delay_ms`, `derived.worst_round_trip_s` |
| Nodi per ruolo | 1 admin, 2 CA, 5 miner, 30 aziende (38 totali) | `manifest.json` `nodes.*` |
| Cluster | 6 aziende per miner (company-k → miner-(k mod 5)) | [clusters.json](clusters.json) |
| Epoche | 100 × 100 blocchi (misurate 2–101; la 1 è in setup) | `epochs.*`; `report.md` |
| Altezza finale / target / esito | 10 122 (manifest), 10 120 (report) / 10 120 / `ok`, nessun errore | `final_height`, `derived.target_height`, `status`, `error` |
| `dump-function` | `none` (g(w) = w) | `wpoa_params`; [analysis/phase1/config.csv](analysis/phase1/config.csv) |
| `target-block-time` T_block | 8 s | `chain_params`, `config.csv` |
| `wpoa-sortition-delta` δ | 0,5 ⇒ Δ_max = 4 s, banda base [4 s, 12 s] | `wpoa_params` |
| `wpoa-sortition-lambda` λ | 0,3 | `wpoa_params` |
| Bound del feedback M | min(0,5·8 ; 8·(1−0,5)/0,3) = min(4 ; 13,33) = **4 s** | ricavato |
| Parametri malus | μ = 0,5; M_max = 3; p(Equiv)=4, p(BadWeight)=2, p(SelfWrite)=1, p(Delay)=0,25 | `wpoa_params`, `effective_chain_params` |
| Stato malus | meccanismo **attivo** (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`, 0 miner malicious) | `effective_chain_params`; [malicious_manifest.json](malicious_manifest.json) |
| Weight engine | κ = 100; λ_w = **0,99**; `weight-alpha` = 0,2 (**inerte**, validato e mai letto) | `weight_engine_params` |
| `setup-first-blocks` | 220 effettivi (220 richiesti; floor di protocollo 109) | `effective_chain_params`, `derived.*` |
| `mining-diversity` | 0,0 (non vincolante) | `chain_params` |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | `chain_params` |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10¹⁴ (premine 3,5 M) | `chain_params`, `derived.premine` |
| Seed GAS iniziale per miner | 600 200 | `derived.miner_seed_gas` |
| Traffico | stream `supply-chain-events`; aziende [30,60] tx/epoca; restituzioni [0,20]/epoca di importo [50,250]; ESG in [1,100] | `manifest.json` `traffic.*` |
| Lookback RANDAO | 101 | `wpoa-randao-lookback` |
| Piano malicious | `enabled = false`, `target_action_rate = 0`, `actions` {selfwrite 0,5; badweight 0,5}, `start_epoch = 1`, `malicious_miner_ids = []` | `malicious_manifest.json` |
| Log debug | `-debug=wpoa -debug=wpoafork` attivi; `debug.log` dei 5 miner leggibile (via container, file `root` 0600) | `chains/miner-*/wpoa-core-regional-fb/debug.log` |

**Divergenze manifest ↔ catena.** `config.csv` e `effective_chain_params` concordano su tutti i
parametri elencati; l'unica differenza è `setup-first-blocks = null` nel profilo, risolto a 220 dal
launcher (atteso). Altezza finale 10 122 nel manifest contro 10 120 nel report: la pipeline chiude
all'ultima altezza assestata, differenza di 2 blocchi, irrilevante.

**Pesi effettivi alla prima epoca misurata (epoca 2).** Non sono una configurazione ma l'esito
stocastico di ESG × τ ([analysis/phase1/esg_events.csv](analysis/phase1/esg_events.csv),
[analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv)):

| Validatore | ESG miner | τ miner | Σ contributi aziende | W_k grezzo | ρ_prev | w pubblicato = w_eff | p teorica |
|---|---:|---:|---:|---:|---:|---:|---:|
| miner-0 (1Aq6DsGTu8oM…) | 29 | 16 | 104,43 | 3 492 | 0 | 3 492 | 0,103 |
| miner-1 (1TfKWWNoCoR6…) | 56 | 21 | 74,01 | 5 321 | 0 | 5 321 | 0,158 |
| miner-2 (17kNqikg3HNj…) | 75 | 5 | 97,07 | 7 655 | 0 | 7 655 | 0,230 |
| miner-3 (1267AwvLrhT4…) | 55 | 6 | 140,13 | 8 037 | 0 | 8 037 | 0,238 |
| miner-4 (1MGq3mjRuCmm…) | 49 | 4 | 183,37 | 9 181 | 0 | 9 181 | 0,271 |

Sull'intera run il rapporto max/min dei pesi per epoca vale in media 3,07 (range 2,08–5,24):
**nessuna balena**, due gruppi (miner-0/miner-1 ≈ 10–14 % contro miner-2/3/4 ≈ 23–27 %).

## 2. Executive summary

- **Randomness pulita.** Sugli score **privati** VRF ricostruiti dai `debug.log` (49 375 coppie round×miner), `E_i` ha media 0,9974 (banda 1 ± 0,0088) e KS `√n·D = 0,64` < 1,36; lo `score_norm` dell'argmin privato ha media 0,502 e `√n·D = 1,23` < 1,36. Prop. 5.17: gap standardizzato medio 0,978–1,006 per tutti e 5 i vincitori, KS mai rigettato.
- **Meccanica del delay esatta:** 0 mismatch su 49 940 coppie candidato-round (massimo 4·10⁻¹⁴ s contro tolleranza 1,5 ms).
- **Sortition proporzionale al peso:** GoF aggregato su 9 916 blocchi χ² = 1,10, p = 0,894, TV = 0,42 %; 5/100 epoche rigettate (5,0 attese); 26/500 intervalli di Wilson violati (25 attesi); p-value per epoca uniformi (KS p = 0,465).
- **Il GLM logit che "rigetta" (β₁ = 1,146, IC [1,089; 1,203]) è un falso allarme della specificazione**: con 5 validatori `logit(w/W)` non ha pendenza 1 in `log w`. Simulando la sortition esatta sui pesi reali, β₁ sotto H0 vale 1,163 [1,10; 1,23]: l'osservato ci sta dentro. Il test dei log-rapporti (pendenza 1,025, intercetta −0,004) conferma la proporzionalità.
- **Inversioni reali quasi assenti:** 31 round su 9 874 (0,31 %) vinti da chi non era l'argmin privato; tutte con margine < 0,53 s. Il fork-choice per score sceglie il blocco a score migliore nel 99,95 % dei 2 096 round con più di un blocco (la regola nativa first-seen avrebbe preso il blocco finale solo nel 57 % delle valutazioni contese).
- **Block time sul target:** media 8,072 s (sd 2,41) contro 8 s; Φ mai saturato (|Φ| ≤ 2,17 s contro M = 4 s), media −0,05 s.
- **Retroazione ρ → peso attiva:** Spearman lag-1 0,61–0,81 per cluster (tutti p < 10⁻⁴), 0,336 aggregato; identità del motore esatte (errore relativo ≤ 9·10⁻¹⁵).
- **Malus a effetto esattamente nullo** (nessuna violazione iniettata): M = 0, Ψ = 1 su 505 celle, invarianti tutti veri.
- **Da approfondire (nessuno invalida il meccanismo):** (i) `stream_items.csv` troncato a 100 000 record ⇒ il check di traffico fallisce dall'epoca 78 per un artefatto di raccolta; (ii) il rumore dello scheduler cresce nell'ultimo terzo (sd del residuo vero 0,44 → 0,78 s); (iii) le 31 inversioni residue favoriscono il miner uscente (11/22 contro 25 % atteso, p = 0,010 su un campione piccolo).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [analysis/phase2/candidate_long.csv](analysis/phase2/candidate_long.csv) (score pubblico HMAC) — test A.1
  - **Cosa misura**: `E_i = score_public · weight_effective`, che deve essere Exp(1).
  - **Osservato**: n = 49 385 (9 877 round × 5 candidati, tutti eleggibili), media 0,9931, `√n·D = 1,08`.
  - **Atteso**: media in 1 ± 1,96/√n = [0,9912; 1,0088]; `√n·D ≤ 1,358`.
  - **Giudizio**: **conforme** — scarto −0,69 %, dentro la banda (0,78 della semiampiezza); KS non rigettato. Nota: questo score è la forma pubblica `HMAC-SHA256(seed, indirizzo)`, statisticamente indipendente dallo score VRF con cui gira l'elezione. Il test verifica la normalizzazione e la pipeline, non la VRF: la VRF è testata sotto su fonte privata.
- **File**: `analysis/phase2/candidate_long.csv` — test A.2 (minimo per round)
  - **Cosa misura**: `min_i score_norm_public` per round, che deve essere U(0,1).
  - **Osservato**: n = 9 877, media 0,4994, `√n·D = 0,64`. Sulle righe `is_winner` la media sale a 0,818, come atteso: lo score pubblico del minatore reale non ha nulla a che fare con l'argmin pubblico (vedi §3.5).
  - **Atteso**: media 0,5, `√n·D ≤ 1,358`.
  - **Giudizio**: **conforme** (scarto −0,06 %).
- **File**: `analysis/phase2/candidate_long.csv` — test A.3
  - **Cosa misura**: `score_norm_mismatch_public`, loggato contro ricalcolato.
  - **Osservato**: 0 righe non nulle; massimo 5,2·10⁻¹⁵.
  - **Atteso**: 0.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/timer_race.md](analysis/phase3/timer_race.md), [analysis/phase3/wpoa_timer_race.csv](analysis/phase3/wpoa_timer_race.csv) — score **vero** del vincitore (test Q2)
  - **Cosa misura**: lo `score_norm` ricalcolato dal reveal VRF del blocco vincitore: è U(0,1) se vince l'argmin.
  - **Osservato**: 9 876 round, media 0,5023, KS p = 0,094. Separando gli 80 round vinti in cima alla banda (0,81 %), sui 9 796 round in corsa la media è 0,4982 e KS p = 0,579. Q1: corr(dt_prev, delay_true) = 0,971.
  - **Atteso**: media 0,5, KS non rigettato; ≈ 1 − 1/(n+1) = 0,83 se il vincitore fosse casuale.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/wpoa_prop517.csv](analysis/phase3/wpoa_prop517.csv), [analysis/plots/prop517_gap_by_validator.png](analysis/plots/prop517_gap_by_validator.png)
  - **Cosa misura**: gap standardizzato `(score₍₂₎ − score₍₁₎)(W_tot − w_eff,i*)`, che deve essere Exp(1).
  - **Osservato**: medie 1,0057 (miner-0, n = 991), 0,9782 (miner-1, n = 1 343), 0,9803 (miner-2, n = 2 635), 1,0012 (miner-3, n = 2 278), 1,0015 (miner-4, n = 2 629); KS p fra 0,199 e 0,848; nella figura tutte le barre sono blu, nessun rigetto.
  - **Atteso**: media 1, KS non significativo.
  - **Giudizio**: **conforme** — scarto massimo −2,2 % (miner-1), compatibile con l'errore standard 1/√1343 ≈ 2,7 %.
- **File**: `chains/miner-{0..4}/wpoa-core-regional-fb/debug.log` (righe `mchn-miner: wPoA-sortition`) — VRF privata
  - Riportato in §3.5.1(a): `E_i` media 0,9974, `√n·D = 0,64`; argmin `score_norm` media 0,502, `√n·D = 1,23`. **Conforme.**

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv) (`delay_recompute_mismatch_rounds_is_zero`), `wpoa_epoch_tests.csv` (`delay_recompute_mismatch_rounds`), [analysis/plots/delay_recompute_mismatch.png](analysis/plots/delay_recompute_mismatch.png)
  - **Cosa misura**: |D_i ricalcolato dalla pipeline − D_i loggato dal nodo|.
  - **Osservato**: 0 round in mismatch su 100 epoche; 0/49 940 coppie oltre la tolleranza; nella figura tutti i punti stanno fra 10⁻¹⁸ e 4·10⁻¹⁴ s, cioè 11 ordini di grandezza sotto la soglia di 1,5 ms.
  - **Atteso**: 0 con tolleranza 1,5 ms.
  - **Giudizio**: **conforme**. Harness e nodo concordano sulla formula D_i = T_block + Δ_max(2·score_norm − 1) + λΦ.

### 3.3 Quota di blocchi contro peso

`dump-function = none`, quindi la quota attesa è `w_eff/Σw_eff`, con w_eff pari al peso pubblicato (Ψ = 1 ovunque).

- **File**: [analysis/phase3/weight_vs_election.md](analysis/phase3/weight_vs_election.md) (tabella aggregata)
  - **Cosa misura**: quota osservata contro quota spettante sull'intera run.
  - **Osservato** (p_teorica / p_hat, 9 921 blocchi): miner-0 0,0998 / 0,1009; miner-1 0,1340 / 0,1358; miner-2 0,2710 / 0,2666; miner-3 0,2306 / 0,2305; miner-4 0,2646 / 0,2657. Tutte le quote spettanti cadono nell'intervallo di Wilson (larghezza ≈ 0,012–0,017).
  - **Atteso**: p_hat ≈ p_teorica.
  - **Giudizio**: **conforme** — scarto assoluto massimo 0,0044 (miner-2), MAE aggregato 0,0017, TV 0,42 %.
- **File**: [analysis/phase3/weight_election_wilson_coverage.csv](analysis/phase3/weight_election_wilson_coverage.csv), [analysis/plots/wilson_violation_heatmap.png](analysis/plots/wilson_violation_heatmap.png)
  - **Cosa misura**: copertura dei 500 intervalli di Wilson al 95 % per (epoca, validatore).
  - **Osservato**: 26 violazioni (miner-3 6, miner-4 7, miner-1 7, miner-0 4, miner-2 2), sparse, senza blocchi contigui nella heatmap tranne nell'epoca 2 (3 celle). Risoluzione: larghezza media 0,149.
  - **Atteso**: 0,05 · 500 = 25.
  - **Giudizio**: **conforme** (26 contro 25).
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](analysis/phase3/wpoa_epoch_tests.csv), [analysis/phase3/weight_election_pvalue_uniformity.csv](analysis/phase3/weight_election_pvalue_uniformity.csv), [analysis/plots/p_value_uniformity.png](analysis/plots/p_value_uniformity.png)
  - **Cosa misura**: GoF congiunto per epoca e uniformità dei p-value.
  - **Osservato**: 5 rigetti su 100 epoche (2, 62, 77, 78, 86; le ultime tre con p ≈ 0,048–0,049). Binomiale sul conteggio p = 0,564; KS dei p-value contro U(0,1) D = 0,084, p = 0,465. L'istogramma non ha un picco vicino a 0 (7 epoche nel primo decile contro 10 attese). In ogni epoca `share_changes_within_epoch = True`, quindi il test da leggere è `gof_mc_round_by_round_p`: 3/100 sotto 0,05. L'epoca 2 (p = 0,0007) è la prima dopo il setup: ha 95 blocchi e un salto di pesi dall'epoca 1 (ρ inizializzato). Un rigetto isolato su 100 test resta nell'atteso.
  - **Atteso**: ~5 rigetti; p-value uniformi.
  - **Giudizio**: **conforme**.
- **File**: `wpoa_epoch_tests.csv` riga `all`
  - **Osservato**: χ² = 1,104 (df 4), p = 0,894; round-by-round p = 0,892; MAE_p = 0,0017; MaxAE_p = 0,0044.
  - **Giudizio**: **conforme**: il test più potente della run non vede alcun effetto sistematico.
- **File**: [analysis/plots/weight_vs_election.png](analysis/plots/weight_vs_election.png)
  - **Osservato**: nello scatter i 500 punti si dispongono lungo la diagonale in due nuvole (≈ 0,07–0,17 e ≈ 0,18–0,37), con dispersione verticale ≈ ±0,1, coerente con Wilson a B = 100.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/weight_election_residuals.csv](analysis/phase3/weight_election_residuals.csv), [analysis/plots/residual_boxplot_by_validator.png](analysis/plots/residual_boxplot_by_validator.png)
  - **Osservato**: le mediane dei residui per validatore stanno in [−0,004; +0,006] e le medie (triangoli) su 0; IQR ≈ ±0,025.
  - **Atteso**: box centrati su 0.
  - **Giudizio**: **conforme**; nessuna sovra- o sotto-rappresentazione sistematica.
- **File**: [analysis/plots/election_share_distribution.png](analysis/plots/election_share_distribution.png)
  - **Osservato**: quote cumulative miner-2 26,7 %, miner-4 26,6 %, miner-3 23,1 %, miner-1 13,6 %, miner-0 10,1 %.
  - **Giudizio**: **conforme**: coincidono con le quote teoriche al decimo di punto.
- **Terzi di run** (calcolato da `round_level.csv`): quote osservate contro teoriche, per terzo, entro 0,007 in tutti e tre i terzi (es. miner-2 0,291/0,287, 0,255/0,254, 0,254/0,272 — lo scarto maggiore è −0,018 nell'ultimo terzo, ~1,7 σ binomiali su 3 290 blocchi). **Conforme.**

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](analysis/phase3/longitudinal.md), [analysis/phase3/wpoa_longitudinal_fits.csv](analysis/phase3/wpoa_longitudinal_fits.csv) — GLM logit
  - **Cosa misura**: `logit(p_i) = β₀ + β₁ log(w_eff,i)` sulle 500 celle (epoca, validatore); la pipeline assume H0: β₁ = 1.
  - **Osservato**: β₁ = 1,1464, IC 95 % [1,0894; 1,2033], `converged = True`, marcato "NOT consistent".
  - **Atteso**: β₁ = 1 **secondo la pipeline**. Ma sotto la sortition pesata `p = w/W`, quindi `logit p = log w − log(W − w)`, e la pendenza locale in `log w` vale `1/(1 − p)` (media 1,26 su questa run), non 1. Inoltre il regressore è il peso assoluto e non la quota, e W cambia da un'epoca all'altra. Ho quindi simulato la distribuzione di β₁ sotto la H0 **esatta**: 300 repliche multinomiali con le `p_theoretical_blockweighted` reali di ogni epoca, stesso stimatore IRLS della pipeline. Risultato: β₁ medio 1,163, intervallo 2,5–97,5 % **[1,102; 1,227]**.
  - **Giudizio**: **conforme**. L'osservato (1,146) cade al centro della distribuzione nulla corretta. Il "NOT consistent" è un **difetto del test** (H0 mal specificata per n piccolo), non del meccanismo; vedi §5.
- **File**: `wpoa_longitudinal_fits.csv`, [analysis/phase3/wpoa_longitudinal_logratios.csv](analysis/phase3/wpoa_longitudinal_logratios.csv), [analysis/plots/longitudinal_logratio.png](analysis/plots/longitudinal_logratio.png) — log-rapporti
  - **Osservato**: 1 000 coppie, pendenza 1,0249, intercetta −0,0039, Pearson r = 0,859 (p ≈ 0), Spearman 0,872. Nella figura la retta stimata e la diagonale quasi coincidono.
  - **Atteso**: pendenza 1, intercetta 0.
  - **Giudizio**: **conforme** — pendenza +2,5 %, intercetta ≈ 0; r = 0,86 indica che resta rumore campionario (100 blocchi/epoca), non una distorsione.
- **File**: `wpoa_longitudinal_fits.csv` (monotonicity), [analysis/plots/sign_test_by_validator.png](analysis/plots/sign_test_by_validator.png)
  - **Osservato**: concordanza peso↔quota fra epoche 0,54 (miner-3, p = 0,235), 0,62 (miner-0, p = 0,014), 0,68 (miner-2, p = 2·10⁻⁴), 0,69 (miner-1, p = 1·10⁻⁴), 0,73 (miner-4, p = 3·10⁻⁶).
  - **Atteso**: concordanza > 0,5, tanto più netta quanto più il peso varia fra epoche.
  - **Giudizio**: **conforme** — 4/5 significativi; miner-3 (p = 0,235) è compatibile con il caso con 5 test e ha comunque concordanza > 0,5.
- **File**: [analysis/phase3/wpoa_longitudinal_validators.csv](analysis/phase3/wpoa_longitudinal_validators.csv)
  - **Osservato**: prima contro ultima epoca, `intervals_overlap = True` per tutti e 5. L'ultima epoca ha però solo 21 blocchi (Wilson larghi ~0,3).
  - **Giudizio**: **conforme ma poco informativo** (ultima epoca parziale).

### 3.5 Timer race, margine e inversioni

- **File**: `wpoa_timer_race.csv`, [analysis/plots/margin_distribution.png](analysis/plots/margin_distribution.png) — margine G
  - **Cosa misura**: distanza fra i due delay più veloci (sulla forma pubblica).
  - **Osservato**: G medio 2,239 s, mediana 1,773 s; distribuzione decrescente da 0 a 8 s = 2Δ_max. KS contro la simulazione esatta: D = 0,012, p = 0,240 (media simulata 2,268 s). KS contro Beta(1,5): p = 0 (media attesa 1,333 s).
  - **Atteso**: il test di riferimento è il KS simulato; Beta(1,n) è lo **straw man** dichiarato e ci si aspetta che rigetti con pesi non uniformi.
  - **Giudizio**: **conforme**. Il rigetto Beta(1,n) non è un rilievo.
- **File**: [analysis/phase3/wpoa_sigma.csv](analysis/phase3/wpoa_sigma.csv), [analysis/plots/sigma_decomposition.png](analysis/plots/sigma_decomposition.png)
  - **Osservato**: S1_topology = 0,000377 s (rete emulata, *misurata*, non assente); S2_scheduler_residual_sd = 3,175 s; S2b_inversion_gap = 1,870 s.
  - **Atteso/lettura**: S2 e S2b sono calcolati sul delay **pubblico**, che non è quello da cui partono i timer, quindi misurano la distanza fra due variabili indipendenti e non il jitter reale. Il residuo sul delay **vero** (`timer_race.md`) ha sd 0,574 s e media +0,070 s.
  - **Giudizio**: **conforme** come audit. Il jitter reale è ~0,57 s; il valore 3,2 s è un artefatto della forma pubblica.
- **File**: [analysis/plots/inversion_bound_vs_observed.png](analysis/plots/inversion_bound_vs_observed.png), `wpoa_timer_race.csv`
  - **Osservato**: bound di Prop. 5.18 (pubblico) = 1,0; MC con σ_S2 = 0,505; tasso "osservato" pubblico 0,772 (7 620/9 877).
  - **Atteso**: il bound **saturato a 1,0 è vacuo**. Il tasso pubblico vale ≈ 1 − Σp² ≈ 0,78 per costruzione, perché lo score pubblico è indipendente da quello privato.
  - **Giudizio**: **non informativo**, e non è un rilievo: il tasso di inversione vero è in §3.5.1(b) (0,31 %).
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](analysis/phase3/wpoa_epoch_tests.csv) (`inversion_public_*`)
  - Stesso artefatto per epoca: tasso pubblico ≈ 0,77 costante. **Non informativo.**
- **Vantaggio del miner uscente** (da `debug.log`, campo `lag` = ritardo con cui il nodo arma il timer rispetto al timestamp del parent):
  - **Osservato**: il miner uscente vede il proprio blocco con lag medio 0,625 s, gli altri 1,652 s: ~1,03 s di anticipo. Per terzi di run: 0,605/1,604, 0,622/1,648, 0,646/1,702 s, quindi l'anticipo cresce da 1,00 a 1,06 s. Tuttavia tutti i timer sono ancorati al parent (`anchor=parent` in 54 042/54 042 righe): `start in = delay − lag`, quindi il lag **non** sposta l'istante assoluto di proposta, finché lag < delay (delay minimo 4 s). Il vincitore designato coincide con il miner uscente nel 22,66 % dei round, contro il 22,85 % atteso (Σ p_prev).
  - **Giudizio**: **conforme** sul piano del timer. L'anticipo di ricezione esiste (~1 s, dovuto a validazione e relay dei 38 daemon sullo stesso host più il timestamp a secondo intero, non ai 5 ms della rete), ma l'ancoraggio al parent lo neutralizza. Resta un segnale piccolo sulle inversioni finali, vedi §3.5.1(b).

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Copertura: **score privati di 5 miner su 5**, dai `debug.log` letti tramite il container `mcsim`
(file `root` 0600). 54 042 righe di scheduling; il 91,6 % è riferito al parent poi rimasto sulla
catena finale (il resto era su un tip poi orfano). Round con score di tutti e 5 i miner sul parent
finale: **9 874 su 9 876** misurati (uno con 4, uno con 1, esclusi).

- **(a) Sortition privata.**
  - `E_i = score_privato · w_eff,i` (w_eff da `round_final_weights.csv` all'altezza del round): n = 49 375, media 0,9974 (banda [0,9912; 1,0088]), `√n·D = 0,64`. **Conforme.**
  - `score_norm` dell'argmin privato: n = 9 874, media 0,5022, `√n·D = 1,23` < 1,358. **Conforme** (p ≈ 0,10).
  - Designato = miner del round precedente: 22,66 % contro 22,85 % atteso. **Nessuna correlazione fra round.**
  - Quote dei designati: miner-2 26,71 %, miner-4 26,63 %, miner-3 22,99 %, miner-1 13,60 %, miner-0 10,08 %, contro teoriche 27,11 / 26,46 / 23,06 / 13,39 / 9,98 %. Scarto massimo −0,40 pp (miner-2, ≈ 0,9 σ). **Conforme**, nessun disallineamento del registro pesi.
- **(b) Inversioni reali** (designato privato ≠ minatore del blocco finale in `blocks.csv`; `true_winner_mismatch = 0` in `round_level.csv`, fase 1 già corretta):
  - Tasso complessivo **0,314 % (31/9 874)**; per terzo di run 0,03 % (1), 0,46 % (15), 0,46 % (15).
  - Margine fra i due delay privati nei round invertiti: media 0,212 s, mediana 0,166 s, massimo 0,526 s (contro 2,24 s medi su tutti i round). Il vincitore effettivo aveva sempre il secondo timer, a meno di 0,53 s dal primo.
  - Beneficiari: miner-3 10, miner-4 9, miner-2 8, miner-1 3, miner-0 1 (proporzionali al peso). Designati "scavalcati": miner-2 10, miner-4 9, miner-0 5, miner-3 4, miner-1 3.
  - **Miner uscente:** 11/31 inversioni (35 %) sono andate al miner del round precedente. Nei 22 casi in cui il designato non era già l'uscente, l'uscente ha vinto 11 volte (50 % contro 25 % atteso se il beneficiario fosse uno qualunque degli altri 4): binomiale unilaterale p = 0,010.
  - **Giudizio**: **conforme** sul tasso (0,3 %, irrilevante per le quote: vedi §3.3). **Lieve scostamento da indagare** sul beneficiario: il campione è di 22 eventi e il test è uno solo, ma il segnale va nella direzione del vantaggio di ricezione di ~1 s dell'uscente.
- **(c) Fork** (righe `[wpoa-fork]`):
  - Round con più di un blocco proposto alla stessa altezza: **2 096 su 9 900 (21,2 %)**, fino a 5 blocchi per altezza; 3 471 blocchi orfani distinti.
  - Il blocco finale è quello a score migliore fra i contendenti nel **99,95 %** dei round con fork (2 095/2 096).
  - Tie-break per score contro regola nativa: sull'ultima valutazione per nodo e altezza con almeno 2 candidati (10 376), il blocco scelto per score è quello finale nel 95,4 % dei casi, quello first-seen nativo solo nel 57,3 %. Nelle 4 174 valutazioni in cui le due regole divergono (1 939 altezze distinte), la regola per score ha preso il blocco finale nel 94,9 % dei casi, quella nativa **mai** (0 %). Con la regola nativa, circa 1 939 altezze (≈ 20 % dei round) sarebbero state potenzialmente invertite.
  - 6 442 eventi `displace` (tip sostituito da un blocco a score migliore, su 2 093 altezze; 100 % verso score migliore); 1 090 `defer`, **0 `defer-release`** (ogni blocco trattenuto è stato poi scalzato dall'argmin); 614 `retarget-abort`.
  - Tempo massimo di un nodo su un tip poi orfano: **11 s** (mediana 1 s, p95 2 s; 4 452 episodi, 8,3 % delle valutazioni di scheduling). La profondità di riorganizzazione non è ricostruibile esattamente dai log (mancano righe `UpdateTip`/`REORGANIZE`). Tutti i `displace` sono alla stessa altezza e la permanenza massima è di ~1 intervallo di blocco, il che è coerente con riorganizzazioni di profondità 1.
  - **Giudizio**: **conforme**. I fork sono frequenti (21 %) perché la banda [4, 12] s lascia partire più timer prima che il blocco dell'argmin si propaghi (~1 s). Il fork-choice per score li risolve quasi sempre (99,95 %) a favore dell'argmin: è il componente che porta le inversioni dal ~10 % grezzo allo 0,3 % finale.
- **(d) Prop. 5.18 sui delay reali.** Simulazione sui delay privati di ciascuno dei 9 874 round: tempo di proposta = delay + N(0, σ²), con o senza un vantaggio `a` sottratto all'uscente; 20 repliche.
  - Il bersaglio corretto per un modello di *rumore sul timer* è il tasso di inversione **al primo arrivo** (prima del fork-choice): il primo blocco ricevuto non era dell'argmin in 1 044 round (**10,6 %** di tutti i round; 49,9 % dei round con fork), per terzo 51,5 / 49,8 / 48,4 % dei round con fork.
  - Modello simmetrico: σ = 0,3 s → 9,3 %, σ = 0,5 s → 14,1 %, quindi σ ≈ 0,35 s riproduce il 10,6 %. Quota dell'uscente fra i vincitori al primo arrivo: simulata 21 % (27 % se il designato non era l'uscente), osservata **22,8 % (29,4 %)**.
  - Modello con vantaggio (σ = 0,5, a = 0,3 s): quota dell'uscente 37,5 % (43 %), **peggiore** dell'osservato.
  - Sul tasso finale (0,31 %) nessuno dei due modelli di rumore sul timer è applicabile: le inversioni finali sono i rari casi in cui il fork-choice non recupera. Lì la quota dell'uscente (50 % su 22) sarebbe riprodotta da a ≈ 0,05 s con σ ≈ 0,05 s, ma su 22 eventi il fit non è identificabile.
  - Crescita nel tempo: il tasso grezzo al primo arrivo **non** cresce (51,5 → 48,4 %); il tasso finale sale da 1 a 15 eventi fra primo e secondo terzo e resta a 15 nel terzo.
  - **Giudizio**: **conforme**: al primo arrivo il modello simmetrico con σ ≈ 0,35 s spiega sia il tasso sia chi ne beneficia, e non serve alcun vantaggio sistematico. Il bound di Prop. 5.18 con n = 5, Δ_max = 4 s e σ = 0,35 s vale O((5·0,35/4)^{2/3}) ≈ 0,58: corretto ma lasco rispetto al 10,6 % grezzo.

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/phase2/round_level.csv](analysis/phase2/round_level.csv) (`dt_prev_s`)
  - **Cosa misura**: spaziatura realizzata fra blocchi.
  - **Osservato**: 9 876 round, media **8,072 s**, sd 2,414, mediana 8,0, min 3, max 24 s. Media per epoca in [7,60; 8,68] s; per terzi 8,050 / 8,079 / 8,087 s. Nessuna deriva: la variazione per terzo, +0,04 s, sta dentro l'errore standard per terzo (≈ 0,042 s).
  - **Atteso**: media → T_block = 8 s.
  - **Giudizio**: **conforme** — +0,9 % sopra il target.
- **File**: `round_level.csv` (`delay_true_s`, `residual_true_s`), `candidate_long.csv` (`delay_logged_public_s`)
  - **Osservato**: delay vero del vincitore medio 8,002 s (il minimo di 5 timer nella banda [4, 12]). Residuo spaziatura − delay vero: media +0,070 s, sd 0,574 s; per terzo sd 0,438 / 0,441 / **0,776 s**. La media del delay **pubblico** di tutti i candidati (10,67 s) non va confrontata col target, perché include i perdenti.
  - **Giudizio**: **lieve scostamento**: il rumore dello scheduler aumenta nell'ultimo terzo, con epoche a sd > 1 s (90, 91, 96, 98, 99, 100: 1,09–1,56 s) contro 0,45 s medi nelle epoche 2–77. Non è legato al traffico: il `txcount` medio per blocco resta 14,6 prima e dopo. La causa candidata è la contesa di CPU/I/O sull'host verso fine run (i `debug.log` dei miner arrivano a 167–305 MB). La media resta sul target e corr(dt, delay_true) scende solo da 0,983 a 0,949.
- **File**: [analysis/plots/phi_over_time.png](analysis/plots/phi_over_time.png), `round_level.csv` (`phi_s`)
  - **Osservato**: 51 valori distinti (multipli di 1/12 s), media −0,051 s, sd 0,591, range [−2,17; +2,00] s; |Φ| < 0,5 s nel 56 % dei round, |Φ| > 1 s in 836 round (8,5 %). **0 round saturati** a ±M = ±4 s. Il cambio di segno round su round avviene nel 21 % dei casi, con autocorrelazione lag-1 0,887 (finestra mobile di 12 blocchi). La mediana mobile nella figura resta in [−0,17; +0,08] s su tutta la run.
  - **Atteso**: Φ piccolo e non saturato se il controllo funziona.
  - **Giudizio**: **conforme**. Nessuna saturazione e nessuna oscillazione aggressiva: l'autocorrelazione alta indica una correzione lenta, non invertente.
- **File**: `consistency_checks.csv` (`phi_consistent`)
  - **Osservato**: FAIL, "51 distinct Phi values", non critico.
  - **Giudizio**: **atteso, non è un difetto**: il check è una sonda di non-regressione tarata su run con feedback spento, mentre qui λ = 0,3 e Φ varia per design.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv), [analysis/phase3/weight_engine_epoch.csv](analysis/phase3/weight_engine_epoch.csv) — identità
  - **Osservato**: `W_k_raw = ESG·(τ_miner + Σc_i)` con errore relativo massimo 3,9·10⁻¹⁶; `w_k_final = W_k_raw·(ρ_prev·λ_w + 1 − λ_w)` con errore 9,0·10⁻¹⁵ (epoca 1: w = W). `w_k_published / w_k_final` ∈ [99,987; 100,010], cioè un fattore di scala fisso ×100 con arrotondamento all'intero.
  - **Giudizio**: **conforme**, esatto.
- **File**: `epoch_engine.csv`, [analysis/phase1/esg_events.csv](analysis/phase1/esg_events.csv), [analysis/plots/esg_scores.png](analysis/plots/esg_scores.png) — ESG statici
  - **Osservato**: 35 certificazioni (30 aziende + 5 miner), una per soggetto, nessuna ri-certificazione. `miner_esg_score` ha un solo valore per miner in tutte le 101 epoche (miner-0 29, miner-1 56, miner-2 75, miner-3 55, miner-4 49). ESG delle aziende fra 4 e 99.
  - **Giudizio**: **conforme**.
- **ρ non nullo** (§1.5): ρ medio 0,0025, sd 0,0016, max 0,0069, nullo nel 3,4 % delle celle. È piccolo perché il saldo parte dal seed di 600 200 GAS per miner, mentre le restituzioni sono dell'ordine di 10³ per epoca. Con λ_w = 0,99 il fattore `0,99ρ + 0,01` va da 0,010 a 0,0168: la retroazione sposta il peso fino a **×1,68**, un effetto non trascurabile rispetto a `W_raw`.
- **File**: [analysis/phase3/weight_engine_correlations.csv](analysis/phase3/weight_engine_correlations.csv), [analysis/plots/rho_vs_next_weight.png](analysis/plots/rho_vs_next_weight.png), [analysis/plots/rho_feedback_by_validator.png](analysis/plots/rho_feedback_by_validator.png)
  - **Osservato**: Spearman lag-1 ρ(e) → w(e+1): miner-4 0,812, miner-3 0,799, miner-2 0,779, miner-0 0,737, miner-1 0,608 (tutti p < 10⁻⁴, n = 100); aggregato 0,336 (n = 500). L'aggregato è più basso perché mescola due gruppi di peso diversi: nello scatter compaiono due bande, 4–8 k e 8–19 k, ciascuna crescente in ρ.
  - **Atteso**: correlazione positiva se ρ ha varianza.
  - **Giudizio**: **conforme**: il canale endogeno è attivo e ben visibile.
- **File**: [analysis/plots/weights_over_time.png](analysis/plots/weights_over_time.png), [analysis/plots/weights_boxplot_per_epoch.png](analysis/plots/weights_boxplot_per_epoch.png)
  - **Osservato**: i tre pannelli (grezzo, dopo malus, finale) sono **identici**, come deve essere con Ψ = 1 e `none`. Il salto fra l'epoca 1 (pesi 10–28 k) e l'epoca 2 (3,5–9 k) è la convenzione `w⁽¹⁾ = W⁽¹⁾`, poi il fattore `(0,99ρ + 0,01)` a partire dall'epoca 2; l'epoca 1 è in setup. Dall'epoca 2 in poi i pesi sono stazionari e rumorosi: medie miner-2 12 949, miner-4 12 656, miner-3 10 981, miner-1 6 355, miner-0 4 739. Spearman epoca→peso fra −0,14 e +0,12: nessun trend. Mediana mobile del boxplot stabile fra 8,8 k e 10,4 k.
  - **Atteso**: pesi rumorosi (τ riestratto ogni epoca), ordine guidato da ESG × attività aziendale.
  - **Giudizio**: **conforme**. Nessun cluster cresce sistematicamente, coerente con τ e restituzioni i.i.d. per epoca: in questa run non esiste un "validatore sempre più attivo".
- **File**: [analysis/phase3/weight_engine_gini.csv](analysis/phase3/weight_engine_gini.csv), [analysis/phase3/weight_engine_gini_summary.csv](analysis/phase3/weight_engine_gini_summary.csv), [analysis/plots/gini_delta_trajectory.png](analysis/plots/gini_delta_trajectory.png)
  - **Osservato**: Gini(pubblicato) − Gini(input) oscilla in [−0,06; +0,07] con livello medio ≈ +0,009. Pendenza 1,9·10⁻⁵ per epoca, Spearman −0,019 (p = 0,849).
  - **Atteso**: pendenza ≈ 0.
  - **Giudizio**: **conforme**. Il motore non amplifica la disuguaglianza nel tempo; lo scarto medio positivo di ~0,01 è l'effetto moltiplicativo di ρ.

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](analysis/phase2/epoch_concentration.csv), `wpoa_epoch_tests.csv`, sezione 3 di `report.md`, [analysis/plots/concentration_over_time.png](analysis/plots/concentration_over_time.png)
  - **Osservato**: aggregato HHI teorico 0,2245 contro osservato 0,2237 (N_eff 4,45 contro 4,47); Gini osservato 0,185. Per epoca, HHI osservato − teorico ha media +0,0068 ed è positivo nel 61 % delle epoche; Gini osservato − teorico +0,019 in media. Nakamoto 1/2: 2 in 97/99 epoche teoriche e 96/99 osservate (3 negli altri casi).
  - **Atteso**: con B = 100 l'HHI osservato per epoca è gonfiato dalla varianza multinomiale, di circa (1 − HHI)/B ≈ +0,0078; l'aggregato deve coincidere.
  - **Giudizio**: **conforme**. L'eccesso per epoca (+0,0068) è la varianza di campione attesa (+0,0078), e sull'aggregato l'osservato è persino leggermente sotto il teorico.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](analysis/phase3/streak.md), `wpoa_epoch_tests.csv` (`L_max_*`, `repeat_prob_*`)
  - **Osservato**: L_max per epoca con p < 0,05 in 3/100 epoche (es. epoca 99: 7 contro 3,93 medio MC, p = 0,019). Ripetizione con p < 0,05 (coda superiore) in 5/100. Aggregato: L_max 9 contro 7,69 MC (p = 0,188); probabilità di ripetizione 0,2265 contro 0,2289 MC (p = 0,705). Dai log privati il designato ripete il miner precedente nel 22,66 % dei round contro il 22,85 % atteso.
  - **Atteso**: ~5 rigetti per famiglia; nessun eccesso sistematico.
  - **Giudizio**: **conforme**. Nessuna dipendenza fra round, coerente col tasso di inversione dello 0,3 %.

### 3.10 Malus

Caso **J.1**: meccanismo attivo, nessuna violazione iniettata.

- **File**: [analysis/phase1/malus_detections.csv](analysis/phase1/malus_detections.csv), `analysis/phase1/malicious_*.csv`, [analysis/phase2/malus_actions.csv](analysis/phase2/malus_actions.csv), `analysis/phase2/malus_detection_events.csv`, [analysis/phase3/malus_rate.csv](analysis/phase3/malus_rate.csv), `analysis/phase3/malus_funnel.csv`, `analysis/phase3/malus_detection.csv`, `analysis/phase3/malus_latency.csv`
  - **Osservato**: 0 righe di dati in tutti; funnel 0/0/0/0/0; precision/recall non definiti (n = 0); latenze n = 0.
  - **Giudizio**: **conforme** — vuoti come atteso.
- **File**: [analysis/phase2/malus_state.csv](analysis/phase2/malus_state.csv), [analysis/phase3/malus_invariants.csv](analysis/phase3/malus_invariants.csv), [analysis/plots/malus_invariant_audit.png](analysis/plots/malus_invariant_audit.png)
  - **Osservato**: 505 celle (101 epoche × 5): M_max = 0, Ψ_min = 1; `invariant_psi_in_unit`, `invariant_weff_matches`, `invariant_clean_psi_one` tutti veri, heatmap tutta verde. Check critico `malus_finite_and_psi_in_unit_interval`: 387 465 campioni, PASS.
  - **Giudizio**: **conforme**: effetto del malus sul comportamento onesto **esattamente nullo** (w_eff = w).
- **File**: [analysis/plots/malus_action_funnel.png](analysis/plots/malus_action_funnel.png), [analysis/plots/malus_state_trajectory.png](analysis/plots/malus_state_trajectory.png) ("no malicious miner had a malus trajectory to plot"), [analysis/plots/malus_detection_latency.png](analysis/plots/malus_detection_latency.png) — figure degeneri, come atteso.
- **File**: [analysis/phase3/malus_weight_effect.csv](analysis/phase3/malus_weight_effect.csv), [analysis/phase3/malus_weight_effect_matched.csv](analysis/phase3/malus_weight_effect_matched.csv), [analysis/plots/malus_weight_effect.png](analysis/plots/malus_weight_effect.png)
  - **Osservato**: variazione relativa del peso efficace per gli onesti fra −35 % e −64 % (mediana −56 %).
  - **Giudizio**: **conforme, non attribuibile al malus** (Ψ = 1 ovunque). Il calo è l'artefatto della convenzione di epoca 1 (w = W senza fattore ρ) confrontata con l'ultima epoca (fattore ≈ 0,01 + 0,99ρ), vedi §3.7. La figura non va letta come effetto del malus.
- `analysis/phase3/malus_effectiveness.md` **non è presente**: l'esperimento malicious non è stato eseguito in questa run.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: `epoch_engine.csv` (punto K.1, epoche 2–101, n = 500)
  - **Osservato**: Spearman di `n_blocks_won_epoch` con `w_k_published` 0,846, `W_k_raw` 0,804, `earnings_g_k` 0,673, `companies_contribution_sum` 0,601, `income` 0,084, `miner_activity` 0,082.
  - **Atteso**: correlazione positiva mediata dal peso.
  - **Giudizio**: **conforme**. La correlazione è massima col peso; quella col guadagno segue il fatto che le fee sono incassate da chi mina. `miner_activity` pesa poco su W, perché τ_miner (1–28) è piccolo rispetto a Σc_i (≈ 132).
- **File**: [analysis/phase3/weight_election_residuals.csv](analysis/phase3/weight_election_residuals.csv) × `epoch_engine.csv` (punto K.2, n = 495, epoche 2–100)
  - **Osservato**: Spearman del residuo `p_hat − p_theoretical` con `earnings_g_k` −0,035 (p = 0,43), `income` −0,015 (p = 0,73), `miner_activity` −0,011 (p = 0,81), `companies_contribution_sum` −0,019 (p = 0,67), `R_k` −0,003 (p = 0,96), ρ −0,003 (p = 0,95), `W_k_raw` −0,030 (p = 0,51).
  - **Atteso**: nessuna correlazione residua.
  - **Giudizio**: **conforme**. A peso fissato, guadagno e volume non spiegano nulla: nessun canale di influenza non documentato.

### 3.12 Integrità della run e controlli di consistenza

- **File**: [analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv)

  | check | critico | esito |
  |---|---|---|
  | `registry_weights_finite_and_positive` | sì | PASS (387 465 campioni) |
  | `no_phantom_validator_in_registry` | sì | PASS |
  | `malus_finite_and_psi_in_unit_interval` | sì | PASS |
  | `delay_recompute_mismatch_rounds_is_zero` | sì | PASS |
  | `every_esg_publication_reached_the_stream` | sì | PASS (35/35) |
  | `only_miners_pay_the_treasury` | sì | PASS (5 069 pagamenti) |
  | `at_least_one_fully_measured_epoch` | sì | PASS (100 epoche) |
  | `phi_consistent` | no | FAIL, atteso (§3.6) |
  | `certified_scores_reflected_in_the_engine` | no | PASS |
  | `traffic_counts_within_configured_range` | no | FAIL: 666/3 360 coppie fuori range, **artefatto di raccolta** (sotto) |

  **Giudizio**: **conforme**: 7/7 critici superati.
- **File**: [analysis/phase1/verification.csv](analysis/phase1/verification.csv)
  - **Osservato**: 435 verifiche (epoche 2–100), `verdict = ok` in tutte, `invalid = 0`: ogni peso pubblicato è ricalcolabile.
  - **Giudizio**: **conforme**, nessun BadWeight.
- **File**: [analysis/phase2/epoch_traffic.csv](analysis/phase2/epoch_traffic.csv), [analysis/plots/traffic_per_epoch.png](analysis/plots/traffic_per_epoch.png), [analysis/phase1/stream_items.csv](analysis/phase1/stream_items.csv)
  - **Osservato**: tutte le 666 coppie fuori range sono **sotto** il minimo (nessuna sopra) e stanno tutte fra l'epoca 78 e la 100 (29 nodi per epoca). Le aziende pianificano e inviano sempre nel range (100 %; inviate = pianificate nel 100 %), ma le transazioni "on chain" crollano a 184 nell'epoca 78 e a 0 dalla 79. `stream_items.csv` contiene **esattamente 100 000** record di `supply-chain-events`, cioè il tetto della raccolta. Il `txcount` per blocco in `blocks.csv` resta 14,6 in media prima e dopo l'epoca 78, e la `verification.csv` (che ricalcola dal nodo) è `ok` fino all'epoca 100.
  - **Atteso**: conteggi on-chain nel range [30, 60].
  - **Giudizio**: **scostamento da indagare, ma della pipeline e non del protocollo**: `stream_items` è troncato a 100 000 record, quindi dall'epoca 78 la pipeline non vede più il traffico on-chain. La didascalia della figura ("a gap ... is the number of publishes the chain rejected") qui è fuorviante: la catena non ha rifiutato nulla. La τ del motore non ne risente (verifica dei pesi ok).
- **File**: [analysis/phase1/rpc_errors.csv](analysis/phase1/rpc_errors.csv)
  - **Osservato**: 408 errori, tutti `-1 Round not evaluable on this node` sui 4 metodi `wpoalist*` (102 ciascuno), tutti ad altezza < 1 000 (bootstrap, prima che il registro pesi fosse disponibile).
  - **Giudizio**: **conforme**, errori benigni di avvio.
- **Blocco orfano in `blocks.csv`**: `true_winner_mismatch = 0` su 9 877 round; `verdict_true = ok` in 9 876 (1 `not-sortition` al confine). Fase 1 già corretta. **Conforme.**
- **Ultima epoca (101)**: 21 blocchi, Wilson larghi, GoF via Monte Carlo (p = 0,694). Esclusa dalle conclusioni di tendenza.
- **Esito**: `status = ok`, altezza target raggiunta (10 120). Il file `STOP` nella radice della run è il segnale di arresto dell'harness; lo `shutdown.json` non riporta errori che tocchino l'analisi.

## 4. Punti di forza

- **VRF privata corretta**: `E_i` medio 0,9974 su 49 375 campioni, KS `√n·D = 0,64`; argmin `score_norm` medio 0,502, `√n·D = 1,23`; score vero del vincitore medio 0,498 sui round in corsa (KS p = 0,58).
- **Nucleo della sortition esatto**: Prop. 5.17 con gap medio in [0,978; 1,006] per tutti e 5 i vincitori, KS p ≥ 0,20.
- **Delay ricalcolato identico** al loggato su 49 940 coppie (errore ≤ 4·10⁻¹⁴ s).
- **Proporzionalità al peso sull'intera run**: χ² aggregato p = 0,894, TV 0,42 %, scarto massimo di quota 0,44 pp; Wilson 26/500 (25 attese); GoF 5/100 (5 attese); p-value uniformi (KS p = 0,47); log-rapporti con pendenza 1,025 e intercetta −0,004.
- **Fork-choice per score efficace**: sceglie l'argmin nel 99,95 % dei 2 096 round con fork; porta l'inversione dal ~10,6 % al primo arrivo allo **0,31 %** finale. Nessun `defer-release`.
- **Block time sul target**: 8,072 s contro 8 s, senza deriva per terzo; Φ mai saturato (|Φ|max 2,17 s < M = 4 s).
- **Weight engine esatto e con retroazione viva**: identità esatte (≤ 10⁻¹⁴), ESG statici, Spearman ρ → w(e+1) fra 0,61 e 0,81 per cluster, nessuna amplificazione di Gini (pendenza 2·10⁻⁵, p = 0,85).
- **Nessun canale occulto**: residui di quota scorrelati da guadagno, volume, ρ e peso (|Spearman| ≤ 0,035, p ≥ 0,43).
- **Malus a effetto nullo**: M = 0, Ψ = 1, invarianti veri su 505/505 celle; 435/435 pesi verificati.

## 5. Punti critici / da approfondire

- **GLM logit con H0 mal specificata (pipeline).** `longitudinal.md` dichiara β₁ = 1,146 "NOT consistent" con 1.
  - *Entità*: sotto la sortition esatta, simulata sui pesi reali, β₁ vale 1,163 [1,102; 1,227], quindi il rigetto è un falso positivo sistematico con pochi validatori.
  - *Causa*: `logit(w/W) = log w − log(W−w)`, la cui pendenza in `log w` è 1/(1−p) > 1; in più il regressore è il peso assoluto, non normalizzato per epoca.
  - *Serve*: correggere `stat/longitudinal.py`/`phase3_analyze.py`, regredendo su `log(p_theoretical)` con offset `log(1−p)` (oppure usando un GLM multinomiale/condizionale), o calibrare l'H0 via Monte Carlo come fatto qui. Da ricontrollare su tutte le run già analizzate.
- **`stream_items.csv` troncato a 100 000 record (pipeline).**
  - *Entità*: traffico aziendale "on chain" a 0 dalle epoche 78–100, 666 coppie fuori range, `traffic_per_epoch.png` fuorviante.
  - *Causa*: tetto della raccolta di fase 1 sullo stream `supply-chain-events`; la catena ha continuato a includere ~14,6 tx/blocco.
  - *Serve*: paginare `liststreamitems` in `phase1_collect.py` senza cap e rigenerare le fasi 1–3. Le conclusioni su sortition e motore restano valide, perché la τ del motore è verificata dal nodo (`verification.csv` ok).
- **Rumore dello scheduler in crescita nell'ultimo terzo.**
  - *Entità*: sd del residuo vero 0,44 → 0,78 s; 6 epoche finali con sd > 1 s. Il block time medio non ne risente (8,09 s).
  - *Causa ipotizzata*: contesa di CPU/I/O fra 38 daemon sullo stesso host, con `debug.log` fino a 305 MB e compattazioni di LevelDB, non la rete (S1 = 0,4 ms) né il traffico (costante).
  - *Serve*: metriche di carico dell'host (CPU steal, iowait) allineate per altezza, oppure una ripetizione con `-debug` ridotto per vedere se l'aumento sparisce.
- **Inversioni residue sbilanciate verso il miner uscente.**
  - *Entità*: 11 delle 22 inversioni "eleggibili" vanno all'uscente (50 % contro 25 %, p = 0,010). In assoluto sono 11 blocchi su 9 874 (0,11 %), irrilevanti per le quote.
  - *Causa ipotizzata*: l'uscente riceve e valida il proprio blocco ~1,03 s prima degli altri; nei rari casi in cui il blocco dell'argmin arriva tardi, chi ha già il parent in locale estende la catena per primo e il fork-choice (che lavora alla stessa altezza) non recupera. Al primo arrivo, invece, non c'è vantaggio (22,8 % osservato contro 21 % simmetrico).
  - *Serve*: più run o run più lunghe per portare il campione oltre ~100 inversioni; log `UpdateTip`/reorg per misurare la profondità delle riorganizzazioni.
- **Profondità di riorganizzazione non misurata esattamente.** I log non contengono righe `UpdateTip`/`REORGANIZE`: la profondità 1 è solo inferita (permanenza massima su un orfano 11 s). *Serve*: attivare il logging di tip/reorg o raccogliere `getchaintips` a fine run.
- **Figure di audit pubbliche da non leggere come esiti**: `inversion_bound_vs_observed.png` (bound vacuo 1,0; tasso pubblico 0,77 per costruzione), `sigma_decomposition.png` (S2 = 3,18 s dalla forma pubblica) e `malus_weight_effect.png` (−56 % dovuto alla convenzione di epoca 1). Non sono difetti del protocollo, ma la loro didascalia dovrebbe dirlo per evitare letture errate.

## 6. Conclusione

Il meccanismo wPoA in questa run (5 miner, regime `core` regionale, `none`, λ_w = 0,99, 100 epoche) è **in buona salute** su tutti e cinque gli assi:

| Asse | Giudizio | Evidenza |
|---|---|---|
| Affidabilità della sortition | **conforme** | χ² aggregato p = 0,894, TV 0,42 %; Wilson 26/500 contro 25; GoF 5/100 contro 5; log-rapporti pendenza 1,025. Il rigetto del GLM è un artefatto della sua H0 (β₁ nullo simulato 1,163 [1,10; 1,23]). Inversioni reali 0,31 %. |
| Qualità della randomness (VRF) | **conforme** | `E_i` privato 0,9974, `√n·D = 0,64`; argmin `score_norm` 0,502, `√n·D = 1,23`; Prop. 5.17 in [0,978; 1,006]. |
| Efficacia dello smorzamento | **non applicabile** (`dump-function = none`) | Pesi grezzo = finale in ogni epoca; la quota segue linearmente il peso (scarto ≤ 0,44 pp). |
| Efficacia del malus | **conforme, effetto esattamente nullo** | Nessuna violazione iniettata: M = 0, Ψ = 1, invarianti veri su 505/505 celle, 435/435 pesi verificati. |
| Stabilità del block time | **conforme** | Media 8,072 s contro 8 s, nessuna deriva; Φ mai saturato (max 2,17 s < 4 s); rumore dello scheduler in lieve crescita a fine run senza effetto sulla media. |

I due unici "fallimenti" riportati dalla pipeline (GLM β₁ e range del traffico) sono difetti
dell'analisi, non del protocollo: il primo è una H0 mal specificata, il secondo un troncamento della
raccolta a 100 000 record. Vanno corretti in `test/analysis/pipeline/` prima di confrontare questa
run con altre.
