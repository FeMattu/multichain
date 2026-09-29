# Analisi della run run-wpoa-core-regional-whale-sqrt-20260927T182156Z

Run: `test/results/run-wpoa-core-regional-whale-sqrt-20260927T182156Z`
Timestamp UTC della run: 2026-09-27T18:21:56Z
Catena: `wpoa-core-regional-whale-sqrt` — profilo: `test/config/profiles/core/regional-whale-sqrt.yaml` — regime: core
Analisi prodotta il: 2026-09-28

> **Premessa metodologica.** Il sistema è stocastico su più livelli indipendenti: score ESG
> estratti a caso in `[1,100]`, traffico aziendale e restituzioni estratti a ogni epoca, VRF a
> ogni round, rete emulata (CORE, mappa `regional`). Tutto ciò che deriva dal `seed`
> (20260905) resta comunque un campione. Nessun giudizio si basa su singoli blocchi, round o
> epoche, ma solo su aggregati, con bande di confidenza e correzione per confronti multipli
> (`alpha = 0.05`: con `N` test sono attesi `0.05·N` rigetti).
>
> **Convenzione di etichettatura:** miner-0 (1Sn6fJoKpnXx…), miner-1 (1cK5n9odGm9n…),
> miner-2 (1CdLcHePAtXZ…, **la balena**), miner-3 (1G5DNu4yhYJx…), miner-4 (1KQZhneKLcxf…).

> **⚠ Difetto dell'harness, non del protocollo: tre aziende non hanno mai partecipato.** I
> daemon MultiChain di **company-11** (1VhPXKJEjqNv…) e **company-13** (19phZk4ZHRrH…),
> entrambe nel cluster di miner-2, e di **company-28** (1Bo9jQwLbt1A…), nel cluster di miner-3,
> si sono chiusi durante il bootstrap. L'ultimo `UpdateTip` è all'altezza 9–10 nei rispettivi
> `debug.log` e non c'è alcun messaggio d'errore. L'orchestratore è andato avanti
> (`did not serve RPC within 120s` in `logs/company-{11,13,28}/stdout.log`) e la registrazione
> della membership è fallita, con 3 righe `weightregistermembership` in
> [analysis/phase1/rpc_errors.csv](phase1/rpc_errors.csv). Effetto:
> `n_companies` = **16** per miner-2 (invece di 18) e **2** per miner-3 (invece di 3) in
> [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv). È lo stesso difetto già
> osservato su `run-wpoa-core-regional-whale-none-20260927T140026Z` (lì company-28 e
> company-29). Lo scenario "balena contro quattro piccoli" resta intatto, perché miner-2 ha
> comunque il 45 % della quota spettante dopo lo smorzamento.

## 1. Configurazione della run

| parametro | valore | fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-regional-whale-sqrt` | `manifest.json` → `chain_name`; `analysis/phase1/config.csv` |
| seed esperimento | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/regional-whale-sqrt.yaml` | `manifest.json` → `profile_path` |
| regime | `core` (emulazione CORE) | `manifest.json` → `fabric.backend` |
| topologia | `regional`: 20 siti, 7 hub, 34 link; latenza peggiore 5,137 ms (RTT 10,3 ms) | `manifest.json` → `fabric.topology.*`, `derived.worst_path_delay_ms` |
| nodi per ruolo | 1 admin, 2 CA, 5 miner, 30 aziende (38); **27 aziende effettivamente attive** | `manifest.json` → `nodes.*`; `phase2/epoch_engine.csv` |
| composizione cluster | miner-2: 18 aziende da profilo, **16 attive**; miner-0, miner-1, miner-4: 3; miner-3: 3 da profilo, **2 attive** | `clusters.json`; `phase2/epoch_engine.csv` → `n_companies` |
| epoche | 50 × 100 blocchi; misurate 2–51 (la 1 è in setup, la 51 è parziale con 21 blocchi) | `manifest.json` → `epochs.*`, `measured_epochs` |
| altezza finale / target | 5 123 (5 120 raccolte = `derived.target_height`) | `manifest.json` → `final_height`; `shutdown.json` |
| esito | `status = ok`, `error = ""` | `manifest.json` |
| **funzione di smorzamento** | **`sqrt`**, cioè `g(w) = √w` | `config.csv` → `dump-function` |
| `target-block-time` `T_block` | 8 s | `config.csv` |
| banda del delay `delta` | 0,5 ⇒ `Delta_max = 4 s` | `config.csv` → `wpoa-sortition-delta` |
| guadagno correzione globale `lambda` | 0,3 | `config.csv` → `wpoa-sortition-lambda` |
| bound del feedback `M` | `min(0,5·8; 8·0,5/0,3) = min(4; 13,33) = 4 s` | ricavato |
| vincolo di ammissibilità | `Delta_max = 4 ≤ T_block − lambda·M = 6,8` ✓ | ricavato |
| parametri malus | `mu` 0,5; `M_max` 4; punti Equiv 4 / BadWeight 2 / SelfWrite 1 / Delay 0,25 | `config.csv` → `wpoa-malus-*` |
| stato malus | meccanismo **attivo** (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`, 0 miner malicious) | `config.csv`; `malicious_manifest.json` |
| weight engine | `weight-kappa` 100; `weight-lambda` (`lambda_w`) 0,5; `weight-alpha` 0,2 (**inerte**, non letto dal binario) | `config.csv` |
| `setup-first-blocks` | 220 (richiesto 220, floor di protocollo 109) | `config.csv`; `manifest.json` → `derived.*` |
| `mining-diversity` | 0,0 (non vincolante) | `config.csv` |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | `config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10¹⁴ (premine dell'admin) | `config.csv` |
| funding dei miner | `miner_seed_gas` = 300 200 | `manifest.json` → `derived.miner_seed_gas` |
| lookback RANDAO | 101 | `config.csv` → `wpoa-randao-lookback` |
| traffico | aziende 30–60 tx/epoca su `supply-chain-events`; miner 0–20 restituzioni/epoca da 50–250; ESG in `[1,100]` | `manifest.json` → `traffic.*` |
| runtime | `wpoa_debug = false`, `sortition_miner_log = true`, `fork_score_log = true` | `manifest.json` → `runtime` |
| piano malicious | `enabled = false`, `miner_count = 0`, `target_action_rate = 0` | `malicious_manifest.json` |

Nessuna divergenza fra `manifest.json → effective_chain_params` e `analysis/phase1/config.csv`.

**ESG certificati dei miner** ([analysis/phase1/esg_events.csv](phase1/esg_events.csv)):
miner-2 **75**, miner-1 56, miner-3 55, miner-4 49, miner-0 29.

**Pesi effettivi alla prima epoca misurata (epoca 2).** Non sono una configurazione ma un esito
stocastico di `ESG × tau`, con la composizione dei cluster fissata dal profilo. Fonti:
[analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
[analysis/phase3/wpoa_longitudinal_validators.csv](phase3/wpoa_longitudinal_validators.csv).

| validatore | `W_k_raw` | `w_k_final` | `w_k_published` (×100) | `p_theoretical` epoca 2 (`g = √w`) |
|---|---:|---:|---:|---:|
| miner-2 (1CdLcHePAtXZ…) | 29 617,5 | 14 808,8 | 1 480 875 | 0,4464 |
| miner-1 (1cK5n9odGm9n…) | 5 345,8 | 2 672,9 | 267 288 | 0,1907 |
| miner-4 (1KQZhneKLcxf…) | 3 321,2 | 1 660,6 | 166 061 | 0,1506 |
| miner-3 (1G5DNu4yhYJx…) | 1 686,3 | 843,2 | 84 315 | 0,1093 |
| miner-0 (1Sn6fJoKpnXx…) | 1 543,1 | 771,5 | 77 155 | 0,1030 |

Sull'intera run il rapporto medio fra il peso grezzo della balena e quello del validatore più
leggero è **21,4**; dopo `g = √w` scende a **4,6**. È la configurazione della tabella di
riferimento (una balena contro quattro piccoli).

## 2. Executive summary

- **La randomness è pulita.** Sugli score VRF **privati** dei 5 miner (24 500 valori, 4 900
  round, copertura completa) `E_i` ha media 1,0006 (banda ±0,013) e KS `√n·D = 0,79`; lo
  `score_norm` dell'argmin privato ha media 0,4999 e `√n·D = 0,64` (p = 0,81). Prop. 5.17 torna
  per ogni vincitore (media del gap 0,974–1,015, KS p ≥ 0,06).
- **Lo smorzamento `sqrt` comprime la balena come previsto e preserva l'ordinamento.** Sugli
  stessi pesi grezzi la quota spettante di miner-2 sarebbe 0,717 senza smorzamento; con `√w`
  è **0,451**, contro lo 0,442 della tabella di riferimento. Osservato **0,467** su 4 900 blocchi
  canonici. L'ordinamento osservato (miner-2 > miner-1 > miner-4 > miner-3 > miner-0) coincide
  con quello dei pesi smorzati.
- **La quota osservata segue quella smorzata.** χ² aggregato 7,55 (df 4, **p = 0,11**),
  TV = 0,019, round-by-round MC p = 0,11. La balena è a **+1,6 punti** (z = 2,2), ma l'eccesso è
  già nei **vincitori designati** dalla sortition privata (46,7 %), non nella timer race. La
  media di `E_i` della balena è 0,995: pesi del nodo e della pipeline coincidono, quindi
  l'eccesso è compatibile con il caso (χ² dei designati p ≈ 0,095) e non si ripete nel terzo
  finale della run (−0,1 punti).
- **La timer race funziona.** Solo **9 inversioni reali su 4 900 round (0,18 %)**, tutte con
  margine < 0,32 s. Q1 = 0,983, Q2 p = 0,81. Le fork riguardano il 19,2 % delle altezze e si
  risolvono **tutte (940/940)** verso lo score minimo, con riorganizzazioni di profondità 1.
- **Block time sul target:** media 8,046 s (+0,6 %), stabile per terzi; `Phi` mai saturato
  (|Phi| ≤ 1,92 s contro M = 4 s).
- **Weight engine esatto** (identità a ≤ 4·10⁻¹⁶, 200/200 verifiche `ok`). La retroazione `rho`
  è inerte per calibrazione (`rho` ≤ 0,014, Spearman −0,03).
- **Malus a effetto esattamente nullo** (nessuna violazione iniettata): M = 0 e Psi = 1 in
  255/255 celle.
- **Integrità:** 7/7 check critici PASS. Un FAIL non critico
  (`certified_scores_reflected_in_the_engine`) è il sintomo delle tre aziende cadute al
  bootstrap.

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (A.1, calcolato qui: `E_i = score_public × weight_effective`, righe non di setup)
  - **Cosa misura**: la variabile esponenziale prima della divisione per il peso, sulla forma **pubblica** HMAC (verifica la formula, non l'ordinamento).
  - **Osservato**: n = 24 505; media **0,9956**; mediana 0,6901 (teorica ln 2 = 0,6931); `√n·D` = **0,996**.
  - **Atteso**: media in 1 ± 0,0125; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme** (−0,44 %, entro la banda; KS al 73 % del critico).
- **File**: `candidate_long.csv` (A.2, minimo di `score_norm_public` per round)
  - **Osservato**: 4 901 round; media **0,4945**; `√n·D` = **1,22**. Sulle righe `is_winner = True` la media sale a 0,783, come atteso: lo score pubblico è indipendente da quello privato.
  - **Atteso**: `U(0,1)`, media 0,5; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme** (scarto −1,1 %, KS al 90 % del critico).
- **File**: [analysis/phase3/timer_race.md](phase3/timer_race.md), sezione "The winner's real score" (Q2 sullo score **privato** del vincitore)
  - **Osservato**: 4 900 round; media **0,4999**; KS p = **0,809**. Sui 4 870 round in corsa media 0,497, p = 0,32; solo **30 round (0,61 %)** vinti al bordo superiore della banda.
  - **Atteso**: `U(0,1)` se vince l'argmin; ≈ 0,83 se vincesse un validatore qualsiasi.
  - **Giudizio**: **conforme**. Il vincitore è l'argmin della VRF privata. I round vinti al bordo di banda restano allo 0,6 %, come in `whale-none` (0,57 %), contro il ~6 % delle run precedenti alle correzioni del 2026-09-26.
- **File**: [analysis/phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv), [analysis/plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
  - **Osservato**: gap standardizzato medio miner-2 1,004 (n = 2 289, KS p 0,87); miner-1 0,974 (871, p 0,78); miner-4 1,012 (690, p 0,76); miner-3 0,977 (586, p 0,06); miner-0 1,015 (464, p 0,93). Tutte le barre sulla linea a 1.
  - **Atteso**: media 1, KS non significativo.
  - **Giudizio**: **conforme** (scarti ≤ 2,6 %, nessun rigetto su 5).
- **File**: `candidate_long.csv` (A.3, `score_norm_mismatch_public`)
  - **Osservato**: 0 righe non nulle su 24 505; massimo 1,1·10⁻¹⁴.
  - **Giudizio**: **conforme** (alla precisione di macchina).

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv) (`delay_recompute_mismatch_rounds_is_zero`), [analysis/plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
  - **Osservato**: **0 su 25 075** coppie candidato-round oltre la tolleranza; massimo 8,5·10⁻¹⁴ s. Nella figura tutti i punti stanno fra 10⁻¹⁸ e 10⁻¹³ s, in tutte le epoche.
  - **Atteso**: 0 mismatch con tolleranza 1,5 ms.
  - **Giudizio**: **conforme**. Harness e nodo concordano esattamente sul meccanismo, anche con `g = √w`.

### 3.3 Quota di blocchi contro peso

Con `dump-function = sqrt` e `Psi ≡ 1` la quota spettante è `√w_i / Σ√w` sui pesi pubblicati.
Il controfattuale `none` (stessi pesi grezzi, `g(w) = w`) è calcolato qui da
`candidate_long.csv` → `weight_raw` per confronto.

**Confronto aggregato sulla catena canonica** ([analysis/phase1/block_sortition.csv](phase1/block_sortition.csv), 4 900 blocchi wPoA, altezze 221–5120; calcolato qui)

| validatore | quota senza smorzamento (controfattuale) | `p_theoretical` (`√w`) | `p_hat` | Wilson 95 % | z |
|---|---:|---:|---:|---|---:|
| miner-2 (1CdLcHePAtXZ…) | 0,7171 | **0,4513** | **0,4671** | [0,4532; 0,4811] | +2,23 |
| miner-1 (1cK5n9odGm9n…) | 0,1249 | 0,1879 | 0,1778 | [0,1673; 0,1887] | −1,82 |
| miner-4 (1KQZhneKLcxf…) | 0,0757 | 0,1462 | 0,1408 | [0,1314; 0,1508] | −1,06 |
| miner-3 (1G5DNu4yhYJx…) | 0,0480 | 0,1163 | 0,1196 | [0,1108; 0,1290] | +0,73 |
| miner-0 (1Sn6fJoKpnXx…) | 0,0343 | 0,0984 | 0,0947 | [0,0868; 0,1032] | −0,87 |

- **Osservato**: χ² = **7,55** (df 4), **p = 0,109**; TV = 0,019. La riga `all` di [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv), che conta anche i 21 blocchi di setup dell'epoca 2, dà χ² 7,19, p = 0,126, round-by-round MC p = 0,112, `MAE_p` 0,0075. In [analysis/phase3/weight_vs_election.md](phase3/weight_vs_election.md) ("Pooled") l'intervallo della balena [0,4527; 0,4805] esclude di poco la spettante 0,4512.
- **Atteso** (caso `sqrt`): la balena compressa rispetto al caso `none` ma ancora dominante, ordinamento preservato, quota vicina alla riga `sqrt` della tabella di riferimento (44,2 %).
- **Giudizio**: **conforme sullo smorzamento, lieve scostamento sulla balena**. La compressione è quella prevista: da 0,717 a 0,451, contro 0,714 → 0,442 della tabella. Il rapporto balena/più piccolo passa da 21,4 a 4,6. L'ordinamento è preservato in tutte e cinque le posizioni. Lo scarto di +1,6 punti della balena (z = 2,2) è uno solo fra cinque confronti e il test congiunto non rigetta (p = 0,11). Per il terzo della run: +2,0 / +2,8 / −0,1 punti (z = 1,6 / 2,3 / −0,1). L'eccesso non è sistematico, e §3.5.1(a) mostra che nasce nell'estrazione e non nella timer race.

**Intervalli di Wilson per (epoca, validatore)**
- **File**: [analysis/phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv), [analysis/plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png), [analysis/plots/weight_vs_election.png](plots/weight_vs_election.png)
  - **Osservato**: **13 violazioni su 250** contro 12,5 attese; larghezza media **0,146**. Per validatore: miner-1 5, miner-2 3, miner-3 3, miner-4 2, miner-0 0. Nella heatmap i rossi sono sparsi su 12 epoche diverse, senza righe continue. Nello scatter la nuvola della balena sta attorno a (0,45; 0,46) e quelle dei piccoli fra 0,05 e 0,25, sulla diagonale.
  - **Atteso**: 0,05·250 = 12,5.
  - **Giudizio**: **conforme** (13 contro 12,5).

**Goodness of fit per epoca**
- **File**: `wpoa_epoch_tests.csv`, [analysis/phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv), [analysis/plots/p_value_uniformity.png](plots/p_value_uniformity.png)
  - **Osservato**: **4 rigetti su 50** (epoche 5, 6, 16, 43; p fra 0,025 e 0,049) contro 2,5 attesi, binomiale p = 0,24. KS dei p-value contro `U(0,1)`: D = 0,071, **p = 0,95**. `share_changes_within_epoch = True` ovunque, ma `gof_mc_round_by_round_p` coincide col pooled entro 0,01. L'istogramma è piatto (3–7 epoche per decile).
  - **Atteso**: 2,5 rigetti; p-value uniformi.
  - **Giudizio**: **conforme**.

**Residuo standardizzato per validatore**
- **File**: [analysis/plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png); calcolato qui su `wpoa_epoch_validators.csv`, epoche 2–50
  - **Osservato**: `z = (p_hat − p)/√(p(1−p)/B)` con deviazione standard complessiva **0,999**; per validatore 0,79 (miner-0) – 1,10 (miner-1). Medie fra −0,26 (miner-1) e +0,31 (miner-2). Nel boxplot della pipeline, sui residui grezzi, la scatola di miner-2 è centrata a +0,015 e le altre sullo zero.
  - **Atteso**: deviazione standard 1 se le epoche sono estrazioni binomiali indipendenti.
  - **Giudizio**: **conforme** sulla dispersione (1,00: nessuna sovradispersione, a differenza della baseline `regional-23h` che dava 1,10). Lo spostamento di +0,31 della balena è lo stesso eccesso aggregato di cui sopra.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](phase3/longitudinal.md), [analysis/phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv) (GLM logit)
  - **Osservato**: `beta1` = **1,412** [1,356; 1,469], n = 250, `converged = True` → "NOT consistent" con 1.
  - **Atteso**: l'H0 `beta1 = 1` della pipeline è **mal specificata** con pochi validatori. Sotto `p = g(w)/Σg` la pendenza di `logit p` in `log w_eff` è ≈ 1/(1 − p), molto sopra 1 con una balena a p ≈ 0,45. Ricalibrata con 600 simulazioni multinomiali sulle `p_theoretical_blockweighted` di ogni epoca e lo stesso `binomial_logit_glm` della pipeline: `beta1` nullo = **1,351** [1,285; 1,417].
  - **Giudizio**: **lieve scostamento**. L'osservato (1,412) è al margine superiore della nulla corretta, coerente con il +1,6 punti della balena (§3.3). Il "NOT consistent" della pipeline resta un falso allarme dello strumento.
- **File**: [analysis/phase3/wpoa_longitudinal_logratios.csv](phase3/wpoa_longitudinal_logratios.csv), [analysis/plots/longitudinal_logratio.png](plots/longitudinal_logratio.png)
  - **Osservato**: pendenza **1,037**, intercetta 0,038, Pearson r = 0,896 (500 coppie). Nella figura la retta stimata è quasi sovrapposta alla diagonale.
  - **Atteso**: pendenza 1, intercetta 0.
  - **Giudizio**: **conforme** (pendenza +3,7 %, r alto).
- **File**: `wpoa_longitudinal_fits.csv` (monotonicity), [analysis/plots/sign_test_by_validator.png](plots/sign_test_by_validator.png)
  - **Osservato**: p del sign test 0,09 (miner-2), 0,19 (miner-3), 0,27 (miner-0), 0,38 (miner-4), 0,96 (miner-1); concordanza fra 0,38 e 0,61.
  - **Atteso**: con pesi quasi stazionari fra epoche (§3.7) il test ha pochissima potenza; con 5 test sono attesi 0,25 p < 0,05.
  - **Giudizio**: **conforme / non informativo** per bassa potenza (nessun p < 0,05).
- **File**: [analysis/phase3/wpoa_longitudinal_validators.csv](phase3/wpoa_longitudinal_validators.csv)
  - **Osservato**: prima contro ultima epoca, intervalli sovrapposti per 5 validatori su 5. L'ultima epoca (51) ha 21 blocchi e non è informativa.
  - **Giudizio**: **conforme**.

### 3.5 Timer race, margine e inversioni

- **File**: [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv), [analysis/plots/margin_distribution.png](plots/margin_distribution.png) — margine `G`
  - **Osservato**: `G` medio 2,382 s (mediana 1,876) contro 2,367 s simulati; KS contro la simulazione esatta **p = 0,98**. KS contro `Beta(1,5)`: p = 0 (media attesa 1,333 s). La densità decresce da 0 a 8 s.
  - **Atteso**: aderenza alla simulazione esatta; `Beta(1,n)` è lo **straw man** dichiarato e deve rigettare con pesi non uniformi.
  - **Giudizio**: **conforme** (+0,6 %, KS p = 0,98). Il rigetto `Beta(1,n)` **non è un rilievo**.
- **File**: `timer_race.md` (Q1)
  - **Osservato**: `corr(dt_prev, delay_true)` = **0,983** (4 900 round); residuo medio 0,060 s, deviazione standard 0,436 s. Per terzo di run la deviazione standard è 0,427 / 0,441 / 0,439 s.
  - **Atteso**: ≈ 1 se i timer governano la produzione.
  - **Giudizio**: **conforme**. Rumore di scheduling di circa 0,44 s, stabile nel tempo.
- **File**: [analysis/phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv), [analysis/plots/sigma_decomposition.png](plots/sigma_decomposition.png), [analysis/plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
  - **Osservato**: `S1_topology` = 0,000377 s (misurato). `S2_scheduler_residual_sd` = 3,29 s e `S2b` = 1,95 s, **sullo score pubblico**. Bound = 1,0; MC 0,512; "inversione" pubblica 0,714.
  - **Atteso**: sullo score pubblico l'inversione vale ≈ `1 − Σp²` = 1 − 0,283 = 0,717 per costruzione; il bound saturato a 1 è **vacuo**.
  - **Giudizio**: **conforme come audit del modello, non informativo sull'ordinamento**. L'inversione vera è in §3.5.1(b); il rumore vero è 0,44 s, non 3,3 s.
- **Vantaggio del miner uscente** (campo `lag` delle righe `wPoA-sortition` nei `debug.log` dei miner)
  - **Osservato**: il miner uscente arma il timer con `lag` medio 0,593 s, gli altri 1,574 s: circa 0,98 s di anticipo nella ricezione. Tutti i timer sono però ancorati al padre (`anchor=parent`), quindi il lag non sposta l'istante di proposta. La probabilità di ripetizione è 0,2823 contro 0,2840 del Monte-Carlo sugli stessi pesi (p = 0,59).
  - **Atteso**: nessun vantaggio sistematico dopo le correzioni del 2026-09-26; ripetizione ≈ Σp².
  - **Giudizio**: **conforme**. L'anticipo di ricezione esiste (elaborazione locale del blocco), ma non si traduce in vittorie.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Fonte: `chains/miner-{0..4}/wpoa-core-regional-whale-sqrt/debug.log`, letti come root dal
container. Righe `wPoA-sortition height=… score=… delay=…` (score VRF privato e timer di ogni
miner su ogni padre) e righe `[wpoa-fork] cand/round/displace/defer/retarget-abort`. **Copertura:
score privati di 5 miner su 5 in 4 900 round su 4 900** (altezze 221–5120, padre canonico).

- **(a) Sortition privata.**
  - `E_i = score_privato · w_eff`: n = 24 500, media **1,0006** (banda ±0,0125), `√n·D = 0,79`. Per miner: miner-0 1,012, miner-1 1,027, miner-2 **0,995**, miner-3 0,992, miner-4 0,976, tutte entro ±0,028 (n = 4 900 ciascuno).
  - `score_norm` dell'argmin privato: media **0,4999**, `√n·D = 0,64` (p = 0,81).
  - Quote dei **designati** (argmin privato): miner-2 **0,4671**, miner-1 0,1773, miner-4 0,1406, miner-3 0,1200, miner-0 0,0949, contro le spettanti 0,4513 / 0,1879 / 0,1462 / 0,1163 / 0,0984. χ² = 7,90 (df 4, p ≈ 0,095).
  - Il designato coincide con il miner del round precedente nel 28,3 % dei round, contro il 28,9 % atteso.
  - **Giudizio**: **conforme**. L'eccesso della balena è già presente fra i designati, cioè nell'estrazione VRF, e non nasce nella timer race. La media di `E_i` della balena (0,995) esclude un disallineamento fra il peso usato dal nodo e quello della pipeline: se il nodo usasse un peso più alto, `E_i` calcolato col peso della pipeline scenderebbe sotto 1 in proporzione. Lo scarto è quindi varianza di estrazione, compatibile col caso al livello congiunto.
- **(b) Inversioni reali.** In **9 round su 4 900 (0,18 %)** il blocco finale non è quello dell'argmin privato; per terzo 3 / 4 / 2. Tutti hanno margine fra i due timer privati inferiore a 0,32 s (mediana 0,055 s, contro 2,38 s medi). Beneficiari: miner-1 3, miner-2 3, miner-4 3. Al miner uscente ne va **1 su 9**. **Giudizio: conforme.** Tasso allineato a `regional-feedback` (0,31 %) e alla `race-check` corretta (0,2 %), nessun vantaggio all'uscente.
- **(c) Fork.**
  - Altezze con più di un blocco visto dai miner: **940 su 4 900 (19,2 %)**; 576 con 2 blocchi, 200 con 3, 113 con 4, 51 con 5.
  - **In 940 fork su 940 la catena finale tiene il blocco di score minimo fra i candidati.**
  - In **469** fork (9,6 % dei round) il primo blocco arrivato non era quello finale. Sulle 7 594 valutazioni `round` con almeno due candidati, la regola per score seleziona il blocco finale 6 468 volte, la regola nativa first-seen (`legacy`) 3 910. Nelle 3 111 valutazioni in cui le due regole divergono, la regola per score prende il blocco finale in 2 558 casi, quella nativa **mai**.
  - Eventi: 2 868 `displace`, tutti (2 868/2 868) verso uno score migliore; 566 `defer`; 0 rilasci per scadenza del margine; 242 `retarget-abort`.
  - Riorganizzazioni: 2 923 cambi di tip, tutti di profondità 1 (lo stesso blocco sostituito alla stessa altezza). Tempo massimo di un miner su un tip poi orfano: **2 s** (mediana 0, p95 1 s).
  - **Giudizio: conforme.** Il tie-break per score recupera circa 469 round che la regola nativa avrebbe invertito; l'attivazione consapevole dello score trattiene 566 blocchi peggiori e nessuno viene poi rilasciato.
- **(d) Prop. 5.18 sui delay reali.** Il bersaglio per un modello di rumore sul timer è l'inversione **al primo arrivo**, prima del fork-choice: 471 round (9,6 % di tutti i round; 50,1 % dei round con fork). Il 19,3 % di queste va al miner uscente, il 26 % (91/349) quando il designato non era l'uscente. Simulazione sui delay privati di ogni round (10 repliche), tempo di proposta = delay + N(0, σ²), con o senza un vantaggio `a` all'uscente:

  | modello | inversione al primo arrivo | quota all'uscente |
  |---|---:|---:|
  | osservato | **9,6 %** | **19,3 %** |
  | simmetrico σ = 0,30 s | 8,7 % | 19,4 % |
  | simmetrico σ = 0,35 s | 10,0 % | 19,6 % |
  | vantaggio a = 0,3 s, σ = 0,35 s | 10,3 % | 43,8 % |

  **Giudizio: conforme.** Un rumore **simmetrico** con σ ≈ 0,33 s riproduce sia il tasso sia la composizione; il modello con vantaggio all'uscente sbaglia la composizione (44 % contro 19 %). Il disturbo torna quello assunto dalla Prop. 5.18. Con n = 5, `Delta_max` = 4 s e σ = 0,33 s il bound vale (3/2)(5·0,33/4)^{2/3} ≈ 0,83: corretto ma largo rispetto al 9,6 %. Dopo il fork-choice restano 9 inversioni (0,18 %).

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`, `phi_s`, `delay_true_s`)
  - **Osservato**: `dt_prev` medio **8,046 s** (deviazione standard 2,35, mediana 8, range [3; 13], n = 4 900); per epoca fra 7,64 s (epoca 31) e 8,47 s (epoca 37); per terzo 8,03 / 8,06 / 8,04 s. Delay vero medio del vincitore 7,986 s.
  - **Atteso**: convergenza a `T_block = 8 s`.
  - **Giudizio**: **conforme** (+0,6 %, nessuna deriva).
- **File**: [analysis/plots/phi_over_time.png](plots/phi_over_time.png), `consistency_checks.csv` (`phi_consistent`)
  - **Osservato**: `Phi` medio −0,045 s, deviazione standard 0,59, range [−1,92; +1,83] s, 45 valori distinti. **0 round a ±M** (M = 4 s). Negativo nel 49 % dei round; 498 cambi di segno su 4 899 transizioni (10 %). La mediana mobile resta fra −0,2 e +0,2 s.
  - **Atteso**: `Phi` piccolo e centrato se il controllo funziona.
  - **Giudizio**: **conforme** (|Phi| massimo al 48 % di M; nessuna oscillazione round per round). `phi_consistent = FAIL` è **atteso e non è un difetto**.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv), [analysis/phase3/weight_engine_epoch.csv](phase3/weight_engine_epoch.csv)
  - **Osservato**: `W_k_raw = ESG·(tau_M + Σc_i)` con errore relativo massimo **0** su 255 righe; `w_k_final = W_k_raw·(rho_prev·0,5 + 0,5)` con errore massimo **4,2·10⁻¹⁶**. Peso pubblicato = 100 × `w_k_final` (rapporto 99,9992–100,0007, arrotondamento all'intero). [analysis/phase1/verification.csv](phase1/verification.csv): **200/200 `ok`** (epoche 1–50).
  - **Giudizio**: **conforme** (esatto).
- **File**: [analysis/phase1/esg_events.csv](phase1/esg_events.csv), [analysis/plots/esg_scores.png](plots/esg_scores.png)
  - **Osservato**: 35 certificazioni, ESG dei miner costanti in tutte le 51 epoche (75/56/55/49/29). `certified_scores_reflected_in_the_engine` = FAIL (non critico) per company-11, company-13 e company-28: certificate ma mai registrate, perché i loro nodi erano già morti.
  - **Giudizio**: **conforme** sul motore, che ignora correttamente aziende senza membership. Il FAIL è un difetto dell'harness (§5).
- **File**: [analysis/plots/weights_over_time.png](plots/weights_over_time.png), [analysis/plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png)
  - **Osservato**: dopo l'epoca 1 (bootstrap) i pesi sono stazionari e rumorosi. Pesi finali per epoca: miner-2 14 464–19 132, miner-1 1 922–3 892, miner-4 1 011–2 483, miner-3 789–1 604, miner-0 536–1 085. Nel pannello "after dumping" miner-2 sta a ≈ 1 250–1 350 contro 200–600 degli altri. I pannelli "raw" e "after malus" coincidono (Psi = 1); quello smorzato mostra la compressione.
  - **Atteso**: peso rumoroso guidato da `tau`, senza trend; ordinamento stabile.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv), [analysis/plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png), [analysis/plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)
  - **Osservato**: `rho` non nullo (media 0,0051, deviazione standard 0,0032, massimo 0,0138; 10 zeri su 255) ma minuscolo. Il fattore `0,5·rho + 0,5` sta in [0,500; 0,507]. Spearman lag-1 aggregato **−0,026** (p = 0,68, n = 250); per cluster fra −0,17 e +0,09, nessuno significativo. Lo scatter è una nuvola a due bande orizzontali (balena e piccoli) senza pendenza.
  - **Atteso**: con `lambda_w` = 0,5 e `rho` ≤ 0,014 l'effetto è ≤ 0,7 %, sommerso dalla varianza di `tau`.
  - **Giudizio**: **conforme / inerte per calibrazione**, come dichiarato dal profilo.
- **File**: [analysis/phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv), [analysis/plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png)
  - **Osservato**: `Gini(pubblicato) − Gini(input)` fra −0,0011 e +0,0013; pendenza −9·10⁻⁶ per epoca, Spearman −0,27 (p = 0,052).
  - **Atteso**: pendenza non positiva.
  - **Giudizio**: **conforme** (il motore non amplifica la disuguaglianza dei propri input).

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](phase2/epoch_concentration.csv), `wpoa_epoch_tests.csv` (riga `all`), [analysis/phase3/report.md](phase3/report.md) §3, [analysis/plots/concentration_over_time.png](plots/concentration_over_time.png)
  - **Osservato**: aggregato HHI teorico **0,2835** contro osservato **0,2926** (+3,2 %); `N_eff` 3,53 contro 3,42; Gini 0,311 contro 0,321; entropia normalizzata 0,890 contro 0,880; Nakamoto 1/3, 1/2, 2/3 = 1 / 2 / 3 in entrambi. Per epoca l'HHI osservato oscilla fra 0,236 e 0,368 attorno al teorico (0,27–0,30), e il Nakamoto(1/2) osservato scende a 1 in 15 epoche su 50 (quelle in cui la balena ha superato il 50 %), contro 2 del teorico.
  - **Atteso**: per epoca, con 100 blocchi, l'HHI osservato è più disperso del teorico per varianza multinomiale; il riferimento è l'aggregato. Senza smorzamento la stessa configurazione darebbe HHI ≈ 0,54 e Nakamoto(1/2) = 1 (cfr. `whale-none`: HHI 0,58).
  - **Giudizio**: **conforme**. Lo smorzamento porta la concentrazione teorica da circa 0,54 a 0,28 e il Nakamoto(1/2) da 1 a 2. Il +3,2 % osservato sull'HHI aggregato è il riflesso del +1,6 punti della balena (§3.3). Le 15 epoche con Nakamoto osservato = 1 sono varianza per epoca: con p = 0,45 e 100 blocchi, P(balena ≥ 50) ≈ 0,18, cioè ≈ 9 epoche attese su 50.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](phase3/streak.md), `wpoa_epoch_tests.csv` (`L_max_*`, `repeat_prob_*`)
  - **Osservato**: aggregato `L_max` 10 contro 10,18 del Monte-Carlo (p = 0,61); ripetizione **0,2823 contro 0,2840** (p = 0,59). Per epoca: 3 su 50 con p di ripetizione < 0,05 (epoche 12, 26, 43) e 3 con p di `L_max` < 0,05 (11, 26, 44), contro 2,5 attesi per famiglia.
  - **Atteso**: ripetizione ≈ Σp² = HHI; nessun eccesso sistematico.
  - **Giudizio**: **conforme**. I round sono indipendenti, coerente con lo 0,18 % di inversioni reali.

### 3.10 Malus

Caso **J.1**: meccanismo attivo (`enable-wpoa-malus = true`), nessuna violazione iniettata (`malicious.enabled = false`).

- **File vuoti come atteso**: [analysis/phase1/malus_detections.csv](phase1/malus_detections.csv), [analysis/phase1/malicious_actions.csv](phase1/malicious_actions.csv), [analysis/phase2/malus_actions.csv](phase2/malus_actions.csv), [analysis/phase3/malus_rate.csv](phase3/malus_rate.csv) (0 righe ciascuno). `malus_funnel.csv` e `malus_detection.csv` sono tutti a zero, e `malus_latency.csv` ha n = 0. **`malus_effectiveness.md` non è presente**: l'esperimento malicious non è stato eseguito in questa run.
- **Stato**: [analysis/phase2/malus_state.csv](phase2/malus_state.csv), [analysis/phase3/malus_invariants.csv](phase3/malus_invariants.csv): **M = 0 e Psi = 1 in 255 celle su 255**, con i tre invarianti veri ovunque. [analysis/plots/malus_invariant_audit.png](plots/malus_invariant_audit.png) è interamente verde. Il check critico sul malus passa su 198 085 campioni.
- **Figure**: `malus_action_funnel.png`, `malus_state_trajectory.png` e `malus_detection_latency.png` sono segnaposto ("no malicious experiment ran on this profile"). [analysis/plots/malus_weight_effect.png](plots/malus_weight_effect.png) mostra per i 5 onesti una variazione relativa fra +13 e +20: è il passaggio dall'epoca 1 di bootstrap al regime, **non** un effetto del malus.
- **Giudizio**: **conforme**, effetto esattamente nullo sul comportamento onesto.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv), [analysis/phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv) (calcolato qui, epoche 2–50, n = 245)
  - **Osservato, punto 1** (Spearman con `n_blocks_won_epoch`): `w_k_published` 0,831, `W_k_raw` 0,830, `companies_contribution_sum` 0,745, `earnings_g_k` 0,683, `income` 0,121, `miner_activity` 0,122.
  - **Osservato, punto 2** (residui `p_hat − p_theoretical`): `earnings_g_k` 0,085, `income` 0,102, `miner_activity` 0,104, `companies_contribution_sum` 0,047, `W_k_raw` 0,077, `w_k_published` 0,077. Tutti con |t| ≤ 1,62, quindi p > 0,1.
  - **Atteso**: correlazione del punto 1 mediata dal peso; nulla al punto 2.
  - **Giudizio**: **conforme**. La correlazione di 0,83 sul peso scende sotto 0,11 sui residui: nessun canale di influenza non documentato.

### 3.12 Integrità della run e controlli di consistenza

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)

| check | critico | esito | nota |
|---|---|---|---|
| `registry_weights_finite_and_positive` | sì | PASS | 198 085 campioni |
| `no_phantom_validator_in_registry` | sì | PASS | |
| `malus_finite_and_psi_in_unit_interval` | sì | PASS | 198 085 campioni |
| `delay_recompute_mismatch_rounds_is_zero` | sì | PASS | tolleranza 1,5 ms |
| `phi_consistent` | no | FAIL | 45 valori: **atteso** (§3.6) |
| `every_esg_publication_reached_the_stream` | sì | PASS | 35/35 |
| `certified_scores_reflected_in_the_engine` | no | FAIL | company-11, -13, -28 morte al bootstrap |
| `traffic_counts_within_configured_range` | no | PASS | 1 565 coppie complete |
| `only_miners_pay_the_treasury` | sì | PASS | 2 609 pagamenti |
| `at_least_one_fully_measured_epoch` | sì | PASS | 50 epoche |

  **7 critici su 7 passano.**
- **Traffico** ([analysis/phase2/epoch_traffic.csv](phase2/epoch_traffic.csv), [analysis/plots/traffic_per_epoch.png](plots/traffic_per_epoch.png)): 32 nodi per epoca (27 aziende attive e 5 miner). Pianificato = inviato = on-chain in ogni epoca completa (1 050–1 340 transazioni per epoca), e l'ultima epoca è parziale. Qui non si raggiunge il tetto di 100 000 elementi di `stream_items`. **Conforme.**
- **Errori RPC** ([analysis/phase1/rpc_errors.csv](phase1/rpc_errors.csv)): 403 righe, **tutte fra le 18:22 e le 18:36Z** (bootstrap). Sono 4 × 100 `wpoalist*` con "Round not evaluable", prima che il registro fosse attivo, più le 3 `weightregistermembership` fallite verso le aziende morte. **Conforme**, salvo il sintomo del difetto di bootstrap.
- **Catena finale**: `true_winner_mismatch` = 0 su 4 900 righe di `round_level.csv`, quindi `blocks.csv` coincide con `block_sortition.csv`.
- **Epoca 2**: contiene i 21 blocchi di setup delle altezze 200–220 (round robin nativo), inclusi nei conteggi di fase 3. Qui non produce rigetti (GoF p = 0,50), ma il conteggio aggregato in §3.3 è rifatto sulla sola catena wPoA.
- **Ultima epoca (51)**: 21 blocchi; trattata a parte e non usata per tendenze.

## 4. Punti di forza

- **Lo smorzamento `sqrt` fa ciò che promette su un caso reale a balena.** Quota spettante della balena da 0,717 (senza smorzamento) a 0,451, contro 0,714 → 0,442 della tabella di riferimento; rapporto balena/più piccolo da 21,4 a 4,6; ordinamento preservato in tutte e cinque le posizioni; HHI teorico da circa 0,54 a 0,28.
- **L'elezione segue il peso smorzato**: χ² aggregato p = 0,11, TV = 0,019, 13/250 violazioni di Wilson (12,5 attese), p-value per epoca uniformi (KS p = 0,95), residui standardizzati con deviazione standard 1,00.
- **Randomness pulita sugli score privati**: `E_i` 1,0006 (`√n·D` 0,79), argmin `U(0,1)` con media 0,4999 (`√n·D` 0,64); `E_i` entro la banda per ciascuno dei 5 miner.
- **Timer race quasi perfetta**: 9 inversioni reali su 4 900 (0,18 %), 940/940 fork risolte verso lo score minimo, riorganizzazioni di profondità 1, massimo 2 s su un tip orfano. Round indipendenti (ripetizione 0,282 contro 0,284).
- **Meccanica esatta**: 0/25 075 mismatch di delay (≤ 8,5·10⁻¹⁴ s), identità del weight engine ≤ 4·10⁻¹⁶, 200/200 pesi verificati.
- **Block time sul target**: 8,046 s (+0,6 %), stabile per terzi; `Phi` mai oltre il 48 % di M.
- **Rumore simmetrico**: al primo arrivo un rumore gaussiano con σ ≈ 0,33 s riproduce sia il 9,6 % di inversioni sia il 19 % destinato all'uscente, senza bisogno di alcun vantaggio sistematico.

## 5. Punti critici / da approfondire

- **Balena lievemente sovra-rappresentata (+1,6 punti, z = 2,2).**
  - *Entità*: 0,4671 contro 0,4513; l'intervallo di Wilson aggregato esclude di poco la spettante. `beta1` del GLM (1,412) è al margine superiore della nulla corretta [1,285; 1,417].
  - *Ipotesi*: varianza di estrazione. L'eccesso è già nei designati privati (χ² p ≈ 0,095), non nella timer race (9 inversioni); `E_i` della balena ha media 0,995, quindi il peso usato è quello giusto; l'effetto non è stabile nel tempo (+2,0 / +2,8 / −0,1 punti per terzo); il test congiunto non rigetta (p = 0,11).
  - *Dati per confermare*: `run-wpoa-core-regional-whale-log` con lo stesso seed e un seed diverso per `whale-sqrt`. Uno scarto sistematico della balena si ripresenterebbe; una fluttuazione no.
- **Tre aziende morte al bootstrap** (company-11, company-13, company-28), in modo silenzioso come in `whale-none`.
  - *Entità*: 3 su 30; il cluster della balena ha 16 aziende invece di 18 e quello di miner-3 2 invece di 3.
  - *Causa ipotizzata*: crash dei daemon durante il join, con 38 nodi avviati insieme; il `debug.log` si interrompe senza errore all'altezza 9–10.
  - *Serve*: un controllo di liveness nell'orchestratore dopo `launch_peers` e prima di `register_membership`, che fallisca o riavvii il nodo.
- **H0 del GLM mal specificata** (`beta1 = 1`): con una balena a p ≈ 0,45 la nulla corretta è 1,35. Va sostituita in `stat/longitudinal.py` con un valore calibrato per simulazione.
- **Epoca 2 con blocchi di setup**: la pipeline include i 21 blocchi in round robin della prima epoca misurata. Qui è innocuo, ma resta da correggere in fase 2/3.
- **Retroazione inerte per calibrazione** (`rho` ≤ 0,014, fattore in [0,500; 0,507]): la run non dice nulla sull'efficacia della retroazione, e non era il suo scopo.

## 6. Conclusione

- **Affidabilità della sortition: conforme.** L'elezione segue il peso **effettivo dopo lo smorzamento**: χ² aggregato p = 0,11, 13/250 violazioni di Wilson (12,5 attese), 4/50 rigetti per epoca (2,5 attesi, binomiale p = 0,24), p-value uniformi (p = 0,95), log-rapporti con pendenza 1,037. La balena a +1,6 punti è uno scarto marginale, già presente nell'estrazione VRF e non stabile nel tempo.
- **Qualità della randomness (VRF): conforme.** `E_i` privato 1,0006 (anche per singolo miner), argmin 0,4999, Q2 p = 0,81, Prop. 5.17 fra 0,974 e 1,015.
- **Efficacia dello smorzamento: conforme, ed è il risultato principale della run.** `g = √w` comprime la balena da 0,717 a 0,451 (tabella di riferimento: 0,714 → 0,442) preservando l'ordinamento. L'osservato 0,467 è a 1,6 punti dalla spettante smorzata e a 25 punti da quella non smorzata. Insieme a `whale-none` (osservato 0,756 contro 0,750) mostra che la quota consegnata segue la curva di `g`.
- **Efficacia del malus: conforme per il caso J.1.** Effetto esattamente nullo (M = 0, Psi = 1 in 255/255 celle, invarianti veri). Nessuna violazione iniettata, quindi nulla sull'efficacia contro violazioni reali.
- **Stabilità del block time: conforme.** 8,046 s contro 8, nessuna deriva, `Phi` mai saturato né oscillante. Timer race con 0,18 % di inversioni e fork risolte sempre verso lo score minimo.

I punti aperti riguardano **l'esecuzione e gli strumenti, non il protocollo**: aziende che muoiono
al bootstrap senza che l'orchestratore se ne accorga, l'H0 del GLM e i blocchi di setup nella
prima epoca misurata.
