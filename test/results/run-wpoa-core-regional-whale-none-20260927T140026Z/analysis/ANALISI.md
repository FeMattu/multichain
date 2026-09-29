# Analisi della run run-wpoa-core-regional-whale-none-20260927T140026Z

Run: `test/results/run-wpoa-core-regional-whale-none-20260927T140026Z`
Timestamp UTC della run: 2026-09-27T14:00:26Z
Catena: `wpoa-core-regional-whale-none` — profilo: `test/config/profiles/core/regional-whale-none.yaml` — regime: core
Analisi prodotta il: 2026-09-27

> **⚠ RUN PARZIALE, INTERROTTA DA UN BLACKOUT.** L'host ha perso l'alimentazione intorno alle
> 17:39:17Z, dopo circa 3h39m delle ~11h35m previste. La run si è fermata all'altezza **1627**
> (ultimo evento loggato; `phase1` ricostruisce la catena fino a 1625) contro il `target_height`
> di **5120**: sono state misurate **15 epoche wPoA su 50** (2–16), l'ultima delle quali (16) ha
> solo 26 blocchi su 100. L'orchestratore non ha potuto eseguire la chiusura: **nessuno snapshot
> finale, nessuno `shutdown.json`, nessun `manifest.json`**. I dati sono stati recuperati così
> (script e report in [recovery/](../recovery/)):
>
> 1. copia intatta di tutti i `logs/*/events.jsonl` in `recovery/logs_raw/`;
> 2. rimozione dei **byte NUL in coda** a 18 log (pagine non scritte su disco al momento del
>    blackout: da 309 a 2 677 byte per file, **sempre e solo in coda**, mai in mezzo al file);
>    **nessuna riga JSON corrotta** è stata trovata o scartata. Il costo è la perdita degli ultimi
>    secondi di eventi di quei daemon (miner-2 e miner-3 si fermano a h≈1603–1605, gli altri a
>    h≈1618–1627);
> 3. `manifest.json` ricostruito offline con lo stesso `Orchestrator.write_manifest` della
>    pipeline, alimentato da `params.dat` dell'admin, `addresses.json`, `treasury.txt` e dalla nota
>    "registry usable" nel log dell'orchestratore; `status = "interrupted"`, con un blocco
>    `recovery` che elenca le lacune note;
> 4. pipeline completa rieseguita (phase1 → phase2 → phase3 → grafici), exit code 0.
>
> **Conseguenze sull'analisi:** potenza statistica circa ⅓ di quella progettata; epoca 16 parziale
> e trattata a parte; nessun dato post-teardown. **Nessuna delle metriche wPoA dipende dagli eventi
> persi:** blocchi, score e pesi sono raccolti dall'admin durante la run e sono integri fino a
> h 1625.

> **⚠ Difetto indipendente dal blackout: due aziende non hanno mai partecipato.** I nodi
> MultiChain `company-29` e `company-28` si sono chiusi durante il bootstrap (ultimo `UpdateTip` a
> h 9 e h 28 nei rispettivi `debug.log`, senza messaggio d'errore). La registrazione della loro
> membership è fallita (`weightregistermembership: Connection refused`, 2 righe in
> `rpc_errors.csv`), e i loro daemon di traffico sono morti 4 volte (14:14–14:22Z) prima di
> arrendersi. Il loro `events.jsonl` è vuoto. Effetto: i cluster di **miner-3 e miner-4 hanno 2
> aziende invece di 3** (`n_companies` = 2 in `epoch_engine.csv`). Il profilo resta una balena
> contro quattro piccoli, quindi lo scenario non è compromesso, ma i pesi di miner-3 e miner-4 sono
> più bassi di quanto il profilo prevedesse.

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-regional-whale-none` | `manifest.json` → `chain_name` |
| seed dell'esperimento | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/regional-whale-none.yaml` | `manifest.json` → `profile_path` |
| regime | `core` (rete emulata CORE) | `manifest.json` → `fabric.backend` |
| topologia | `regional`, 7 hub; latenza peggiore sul percorso 5,137 ms | `manifest.json` → `fabric.topology`, `derived.worst_path_delay_ms` |
| nodi | 1 admin, 2 CA, 5 miner, 30 aziende (38 in tutto); **28 aziende effettivamente attive** | `manifest.json` → `nodes`; `phase2/epoch_engine.csv` |
| composizione dei cluster | miner-2: 18 aziende; miner-0, miner-1: 3; miner-3, miner-4: 2 effettive (3 da profilo) | `clusters.json`, `phase2/epoch_engine.csv` |
| epoche | 50 da 100 blocchi da profilo; **16 raggiunte, 15 misurate (2–16), la 16 parziale (26 blocchi)** | `manifest.json` → `epochs`; `phase3/report.md` |
| altezza finale / esito | 1627 (ultimo evento) / 1625 (catena ricostruita); target 5120; `status = interrupted` (blackout) | `manifest.json` → `final_height`, `derived.target_height`, `status`, `error` |
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
| piano malicious | `enabled = false`, 0 miner, rate 0 | `malicious_manifest.json` |

**ESG certificati** (35 pubblicazioni, tutte arrivate sullo stream): miner-2 **75**, miner-1 56,
miner-3 55, miner-4 49, miner-0 29 ([analysis/phase1/esg_events.csv](phase1/esg_events.csv)).

**Pesi effettivi alla prima epoca misurata (epoca 2).** Non sono una configurazione ma un esito
stocastico di `ESG × tau` (ESG estratti dal seed, attività estratta ogni epoca, composizione dei
cluster fissata dal profilo):

| validatore | `w_final` epoca 2 | `p_theoretical` epoca 2 |
|---|---:|---:|
| miner-2 (1FeWA69kpmfJ…) | 1 582 800 | 0,7509 |
| miner-1 (1KbQn4HZLiab…) | 267 288 | 0,1284 |
| miner-3 (1HcbmswQDLfh…) | 84 315 | 0,0425 |
| miner-4 (1MikD1pDvprC…) | 81 487 | 0,0406 |
| miner-0 (1YszMjQTVpHe…) | 77 256 | 0,0376 |

Fonte: [analysis/phase3/weight_vs_election.md](phase3/weight_vs_election.md),
[analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv). All'attivazione del registro (h 106)
i pesi erano 84 000 / 17 080 / 8 965 / 7 742 / 5 713. È la configurazione "balena": **miner-2 pesa
circa 19 volte ciascuno dei tre piccoli**. Il profilo prevedeva una quota balena di ≈0,73,
contro lo 0,714 della tabella di riferimento.

## 2. Executive summary

- **La randomness è pulita**, sia sullo score pubblico sia su quello privato. `E_i` ha media 1,0049
  su 7 030 righe (accettazione 1 ± 0,023) e KS `√n·D` = 0,50 (critico 1,36). Il minimo di
  `score_norm` per round ha media 0,5014 e `√n·D` 1,05. Lo `score_norm` del vincitore vero
  (VRF privata) ha media 0,503, con KS p = 0,53 su 1 403 round.
- **La sortition è proporzionale al peso effettivo, anche con una balena.** Sull'intera run
  miner-2 vince il **74,54 %** dei blocchi contro il **74,96 %** spettante (Wilson [72,2; 76,7] %).
  Il GoF aggregato dà p = 0,62, con TV 0,0095. Gli intervalli di Wilson violati sono 4 su 75
  (3,8 attesi).
- I **rigetti del GoF per epoca sono 2 su 15** (0,75 attesi, binomiale p = 0,17). Quello
  dell'epoca 2 è un artefatto: mescola 21 blocchi di setup in round robin nativo (h 200–220).
- Il **"β1 NOT consistent" del GLM (1,49) è un falso allarme**: la nulla simulata con i pesi reali
  dà 1,504 [1,41; 1,60]. La regressione dei log-rapporti ha pendenza 1,044, intercetta −0,055 e
  r = 0,91.
- **Il timer race funziona.** `corr(dt_prev, delay_true)` vale 0,983, il delay mismatch è 0 su
  7 590 righe, e ci sono **0 inversioni reali** nei 207 round con fork. Il tie-break per score ha
  scelto il blocco finale in 119 fork dove il primo blocco arrivato era un altro.
- **Il block time converge**: media 8,075 s contro 8, `Phi` mai saturato (|Phi| ≤ 2,0 s contro
  M = 4).
- **Il weight engine è numericamente esatto** (identità ed errore della ricorsione < 2·10⁻¹⁶). La
  retroazione `rho → peso` è debole (Spearman 0,054), come atteso con `rho ≈ 0,005`.
- **Il malus non ha alcun effetto** in assenza di violazioni: M = 0 e Psi = 1 in 80 celle su 80.
- **Limiti**: ⅓ della potenza prevista per il blackout, e due aziende assenti per un difetto di
  bootstrap (§5).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (A.1, calcolato qui)
  - **Cosa misura**: `E_i = score_public · weight_effective` sui round non di setup; deve essere
    `Exp(1)`.
  - **Osservato**: n = 7 030; media **1,0049**; mediana 0,6922 (teorica ln 2 = 0,6931); KS contro
    `1 − e^{−x}`: `√n·D` = **0,502**.
  - **Atteso**: media in 1 ± 1,96/√n = [0,977; 1,023]; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme**. La media si scosta dello 0,49 %, entro la banda; il KS è al 37 %
    del valore critico. Nota: `candidate_long` porta lo score **pubblico** HMAC, che serve a
    verificare la formula e non l'ordinamento. Il test sullo score privato è la riga Q2 qui sotto.
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (A.2, calcolato qui)
  - **Cosa misura**: il minimo di `score_norm_public` fra i candidati di ogni round (Prop. 5.11).
  - **Osservato**: 1 406 round; media **0,5014**; KS contro U(0,1): D = 0,0280, `√n·D` = **1,051**.
  - **Atteso**: media 0,5; `√n·D` ≤ 1,358.
  - **Giudizio**: **conforme** (scarto 0,14 %, KS al 77 % del critico). Controprova della trappola
    di §1.3(c): sulle righe `is_winner` la media sale a 0,655. È l'effetto atteso, perché lo score
    pubblico è indipendente da quello privato con cui si è votato.
- **File**: [analysis/phase3/timer_race.md](phase3/timer_race.md), sezione "The winner's real
  score" (test Q2 sullo score **privato**)
  - **Cosa misura**: lo `score_norm_true` del vincitore, ricalcolato dal reveal VRF del suo blocco.
  - **Osservato**: 1 403 round; media **0,50305**; KS p = **0,529**. Sui 1 395 round in corsa: media
    0,50021, KS p = 0,680. Solo **8 round (0,57 %)** sono stati vinti al bordo superiore della banda.
  - **Atteso**: U(0,1) se vince l'argmin; ≈ 1 − 1/(n+1) = 0,83 se vincesse un validatore qualsiasi.
  - **Giudizio**: **conforme**. Il vincitore è l'argmin della VRF privata. I round al bordo di banda
    scendono allo 0,57 %, contro il ~6 % delle run precedenti alle correzioni del 2026-09-26.
- **File**: [analysis/phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [analysis/plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
  - **Cosa misura**: il gap standardizzato fra i due score minimi (Prop. 5.17), che deve essere
    `Exp(1)`.
  - **Osservato**: miner-2 (1FeWA69kpmfJ…) 0,966 (n = 1 061, KS p 0,67); miner-1 (1KbQn4HZLiab…)
    1,036 (168, p 0,85); miner-3 (1HcbmswQDLfh…) 0,928 (69, p 0,66); miner-4 (1MikD1pDvprC…)
    1,135 (66, p 0,18); miner-0 (1YszMjQTVpHe…) 1,352 (41, p 0,10).
  - **Atteso**: media 1 per ogni vincitore, KS non significativo.
  - **Giudizio**: **conforme**. Nessun KS rigetta al 5 %. Lo scarto di miner-0 (+35 %) poggia su 41
    osservazioni, dove l'errore standard della media di una `Exp(1)` vale 1/√41 = 0,156: siamo a
    2,3 σ, senza correzione per 5 confronti (Bonferroni: p ≈ 0,10 non rigetta).
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (A.3)
  - **Cosa misura**: `score_norm_mismatch_public` fra il valore loggato e quello ricalcolato.
  - **Osservato**: massimo 2,2·10⁻¹⁶; 0 righe non nulle su 7 590.
  - **Atteso**: 0 entro la tolleranza.
  - **Giudizio**: **conforme**, all'errore di macchina.

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  (`delay_recompute_mismatch_rounds_is_zero`),
  [analysis/plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
  - **Cosa misura**: `|D_i ricalcolato − D_i loggato|` per ogni coppia (candidato, round).
  - **Osservato**: **0 su 7 590** righe oltre la tolleranza; massimo 3,6·10⁻¹⁵ s. Il grafico mostra
    tutti i punti fra 10⁻¹⁸ e 10⁻¹⁴ s, dodici ordini di grandezza sotto la soglia di 1,5 ms, su
    tutte le 16 epoche.
  - **Atteso**: 0 mismatch.
  - **Giudizio**: **conforme**. Harness e nodo concordano esattamente sul meccanismo.

### 3.3 Quota di blocchi contro peso

- **File**: [analysis/phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [analysis/plots/weight_vs_election.png](plots/weight_vs_election.png),
  [analysis/plots/election_share_distribution.png](plots/election_share_distribution.png)
  - **Cosa misura**: la quota osservata `p_hat` contro la quota spettante
    `p_theoretical = w_eff/Σw_eff` (con `g(w) = w`).
  - **Osservato**, aggregato su 1 426 blocchi:

    | validatore | `p_theoretical` | `p_hat` | Wilson 95 % |
    |---|---:|---:|---|
    | miner-2 (1FeWA69kpmfJ…) | 0,7496 | **0,7454** | [0,7222; 0,7674] |
    | miner-1 (1KbQn4HZLiab…) | 0,1229 | 0,1234 | [0,1074; 0,1415] |
    | miner-3 (1HcbmswQDLfh…) | 0,0475 | 0,0540 | [0,0434; 0,0670] |
    | miner-4 (1MikD1pDvprC…) | 0,0452 | 0,0477 | [0,0378; 0,0600] |
    | miner-0 (1YszMjQTVpHe…) | 0,0348 | 0,0295 | [0,0219; 0,0396] |

    Lo scatter è allineato sulla diagonale, con i punti di miner-2 tutti fra 0,65 e 0,82. La torta
    cumulativa riporta 74,5 / 12,3 / 5,4 / 4,8 / 2,9 %.
  - **Atteso** (caso `none`): proporzionalità lineare non compressa. La balena deve dominare in
    proporzione al suo peso (profilo: ≈0,73; tabella di riferimento: 0,714).
  - **Giudizio**: **conforme**. La quota della balena si scosta di −0,42 punti percentuali dalla
    spettante, con MAE aggregato 0,0038 e TV 0,0095. Il dominio di miner-2 è
    **comportamento corretto, non un difetto**, perché è esattamente quanto il suo peso effettivo
    gli attribuisce.
- **File**: [analysis/phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [analysis/plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png),
  [analysis/phase3/wpoa_epoch_validators.csv](phase3/wpoa_epoch_validators.csv)
  - **Cosa misura**: la copertura degli intervalli di Wilson al 95 % per (epoca, validatore).
  - **Osservato**: **4 violazioni su 75**: epoca 2 per miner-2 e miner-3, epoca 7 per miner-3,
    epoca 13 per miner-1. Larghezza media dell'intervallo: **0,110**, che è la risoluzione di
    questa run.
  - **Atteso**: 0,05·75 = 3,75 violazioni.
  - **Giudizio**: **conforme** (4 contro 3,75). Due delle quattro cadono nell'epoca 2, contaminata
    dai blocchi di setup (vedi sotto).
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [analysis/phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [analysis/plots/p_value_uniformity.png](plots/p_value_uniformity.png)
  - **Cosa misura**: il GoF congiunto per epoca (multinomiale Monte-Carlo, 20 000 estrazioni) e
    l'uniformità dei suoi p-value.
  - **Osservato**: rigetti nell'**epoca 2** (p = 0,0012, TV 0,118) e nell'**epoca 7** (p = 0,014:
    miner-3 vince 13 blocchi contro 5,2 attesi). Le altre 13 epoche hanno p fra 0,20 e 0,84. KS dei
    p-value contro U(0,1): D = 0,239, p = 0,316; binomiale sul numero di rigetti p = 0,171.
    `share_changes_within_epoch = True` in tutte le epoche, ma `gof_mc_round_by_round_p` coincide
    col pooled entro 0,005 ovunque. Riga `all`: χ² = 2,64, p = 0,62 (round-by-round p = 0,82).
  - **Atteso**: 0,75 rigetti; p-value uniformi.
  - **Giudizio**: **conforme**, con una precisazione sull'epoca 2. La pipeline esclude solo l'epoca
    1, ma l'epoca 2 (h 200–299) contiene 21 blocchi **sotto `setup-first-blocks` = 220**, cioè in
    round robin nativo: in quei blocchi miner-3 ne vince 8 e miner-1 altri 8, contro 2 di miner-2.
    Sui soli 79 blocchi wPoA dell'epoca (miner-2 63, miner-1 7, miner-3 5, miner-4 3, miner-0 1) il
    χ² contro le quote spettanti vale ≈3,3 con 4 gdl (p ≈ 0,5). Il rigetto è quindi un
    **artefatto della pipeline**, che include nella prima epoca misurata i blocchi di setup. Resta
    un solo rigetto genuino (epoca 7) contro 0,75 attesi.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](phase3/longitudinal.md),
  [analysis/phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv)
  (GLM logit)
  - **Cosa misura**: `logit(p_hat) = β0 + β1·log(w_eff)`, con H0 della pipeline `β1 = 1`.
  - **Osservato**: β1 = **1,4898** [1,4239; 1,5556], `converged = True`, n = 75 → "NOT consistent".
  - **Atteso**: l'H0 `β1 = 1` è **mal specificata** con pochi validatori. Sotto `p = w/W` vale
    `logit p = log w − log(W − w)`, la cui pendenza è ≈ 1/(1 − p), molto maggiore di 1 quando c'è un
    validatore con p ≈ 0,75. Ho ricalibrato con 2 000 simulazioni multinomiali sulle
    `p_theoretical` reali di ogni epoca, rifittando con la stessa `binomial_logit_glm` della
    pipeline: β1 nullo = **1,504** [1,414; 1,597]; P(β1_sim ≥ 1,4898) = 0,62.
  - **Giudizio**: **conforme**. Il valore osservato sta al centro della sua distribuzione nulla
    corretta. Il "NOT consistent" è un falso allarme noto dello strumento, non del protocollo.
- **File**: [analysis/phase3/wpoa_longitudinal_logratios.csv](phase3/wpoa_longitudinal_logratios.csv),
  [analysis/plots/longitudinal_logratio.png](plots/longitudinal_logratio.png)
  - **Cosa misura**: la regressione dei log-rapporti delle quote osservate su quelli spettanti, a
    coppie.
  - **Osservato**: pendenza **1,044**, intercetta **−0,055**, Pearson r = 0,909 (135 coppie),
    Spearman 0,928. Nel grafico la retta stimata è praticamente sovrapposta alla diagonale.
  - **Atteso**: pendenza 1, intercetta 0.
  - **Giudizio**: **conforme**. Pendenza entro il 4,4 %, r alto: la proporzionalità regge anche sui
    rapporti fra i piccoli (log-rapporti fra −1,5 e 1).
- **File**: [analysis/phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv)
  (monotonicity), [analysis/plots/sign_test_by_validator.png](plots/sign_test_by_validator.png),
  [analysis/phase3/wpoa_longitudinal_validators.csv](phase3/wpoa_longitudinal_validators.csv)
  - **Cosa misura**: se, per ciascun validatore, la quota si muove col peso fra un'epoca e l'altra
    (sign test esatto a una coda).
  - **Osservato**: p = 0,046 per miner-3 (1HcbmswQDLfh…, 10/13 concordanti); 0,133 per miner-4;
    0,212 per miner-2; 0,254 per miner-0; 0,613 per miner-1. Prima contro ultima epoca: gli
    intervalli si sovrappongono per tutti e 5.
  - **Atteso**: con pesi quasi costanti fra epoche (miner-2 oscilla fra 1,58 e 1,91 M), il test ha
    pochissima potenza; con 5 test, 0,25 p < 0,05 attesi per caso.
  - **Giudizio**: **lieve scostamento**, compatibile col caso. È coerente (concordanza fra 0,50 e
    0,77 per tutti), ma non si può dire di più in 15 epoche con pesi che variano del ±10 %.

### 3.5 Timer race, margine e inversioni

- **File**: [analysis/phase3/timer_race.md](phase3/timer_race.md),
  [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv) (Q1)
  - **Cosa misura**: `corr(dt_prev, delay_true)`, cioè se la spaziatura dei blocchi segue il delay
    vero del vincitore.
  - **Osservato**: **0,983** (1 403 round); residuo medio 0,073 s, deviazione standard 0,429 s.
    Per terzo di run la deviazione standard del residuo è 0,421 / 0,432 / 0,435 s.
  - **Atteso**: ≈1 se il meccanismo funziona, ≈0 se è disaccoppiato.
  - **Giudizio**: **conforme**. Il rumore di scheduling è di ~0,43 s e **non cresce** nel tempo.
- **File**: [analysis/plots/margin_distribution.png](plots/margin_distribution.png),
  [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv)
  - **Cosa misura**: il margine `G` fra i due delay più rapidi (forma pubblica).
  - **Osservato**: media 2,910 s (mediana 2,529 s) contro 2,942 s della simulazione esatta. KS di
    riferimento: p = **0,363**. KS contro `Beta(1,n)`: p = 0,000.
  - **Atteso**: il KS contro la simulazione esatta non deve rigettare. Il `Beta(1,n)` è uno
    **straw man** (assume pesi uniformi, qui fortemente disomogenei).
  - **Giudizio**: **conforme** (scarto della media 1,1 %). Il rigetto `Beta(1,n)` **non è un
    rilievo**.
- **File**: [analysis/phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [analysis/plots/sigma_decomposition.png](plots/sigma_decomposition.png),
  [analysis/plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
  - **Cosa misura**: la decomposizione del rumore e il bound di Prop. 5.18.
  - **Osservato**: `S1_topology` = 0,000377 s (misurato: la mappa regionale ha percorsi di 0,75–1,9
    ms). `S2_scheduler_residual_sd` = 3,512 s e `S2b` = 2,070 s, **entrambi sullo score pubblico**.
    Bound = 1,0; probabilità MC 0,503; inversioni pubbliche osservate 585/1 406 = 0,416.
  - **Atteso**: sullo score pubblico il tasso di "inversione" è un artefatto di costruzione (score
    indipendente da quello privato con cui si vota). Il bound saturato a 1 è **vacuo**.
  - **Giudizio**: **conforme come audit del modello, non informativo sull'ordinamento**. Il 41,6 %
    **non** è un tasso di inversione reale, che si trova in §3.5.1. `S2` pubblico (3,5 s) va letto
    accanto al rumore vero di 0,43 s (Q1).
- **Vantaggio del miner uscente** (da [analysis/phase2/round_level.csv](phase2/round_level.csv) e
  [analysis/phase3/streak.md](phase3/streak.md))
  - **Osservato**: il tasso di ripetizione del vincitore è **0,585**, contro 0,583 della
    simulazione Monte-Carlo sugli stessi pesi (p = 0,46) e contro l'HHI teorico di 0,5825. Il
    residuo vero medio (+0,07 s) è lo stesso nei tre terzi della run.
  - **Atteso**: senza vantaggio dell'uscente, la probabilità di ripetizione è Σp² = HHI.
  - **Giudizio**: **conforme**. Nessun vantaggio dell'uscente misurabile (+0,2 punti percentuali
    contro il Monte-Carlo). È coerente con le correzioni "parent anchor" e "score-aware activation",
    già presenti nel binario di questa run.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Fonte: `chains/miner-{0..4}/wpoa-core-regional-whale-none/debug.log`, letti come root dal
container (5 miner su 5 leggibili; byte NUL in coda rimossi, da 0 a 3 755 per file). **Copertura
parziale, per configurazione:** la run ha `runtime.wpoa_debug: false`, quindi i log **non**
contengono lo score privato di ogni miner per ogni round. Contengono solo le righe
`[wpoa-fork] cand/round/displace/defer` (lo score privato di ogni blocco **proposto** e visto da un
nodo, e le decisioni di fork-choice) e `[wpoa-sortition] verify` (lo score del blocco accettato).
Il "vincitore designato" si può quindi stabilire **solo fra i candidati che hanno proposto**, cioè
sui **207 round con fork** (≥2 blocchi alla stessa altezza) su 1 405 misurati. Per i restanti
1 198 round a candidato singolo il test resta Q2 (§3.1), che conferma che il vincitore è l'argmin.

- **(a) Sortition privata.** Sui 207 round con fork il designato coincide con il vincitore del round
  precedente nel 57,5 % dei casi, contro un HHI di 0,58. Non c'è quindi correlazione anomala. I
  designati si distribuiscono così: miner-2 136, miner-1 37, miner-3 18, miner-4 10, miner-0 6. Il
  test di `E_i` sul sottoinsieme dei fork (media 2,40) **non** è un test della VRF: i round con fork
  sono selezionati proprio perché il minimo del campo era alto, cioè perché nessun timer è scattato
  presto. La qualità della VRF privata va letta in Q2 (media 0,503, KS p 0,53 su 1 403 round).
  **Giudizio: conforme.**
- **(b) Inversioni reali.** In **0 dei 207** round con fork il blocco rimasto sulla catena finale
  non è quello di score privato minimo fra i proposti: tasso 0/207, Wilson 95 % [0; 1,8 %]. Per
  terzo di run: 0 / 0 / 0, su 69 / 65 / 73 round con fork. Nessuna inversione va al miner uscente.
  `true_winner_mismatch` in `round_level.csv` è 0 su 1 518 righe, quindi `blocks.csv` è coerente
  con `block_sortition.csv` (fase 1 già corretta per il blocco orfano). **Giudizio: conforme.**
  Rispetto al 13,2 % (e poi 0,2 %) delle run precedenti alle correzioni del 2026-09-26, qui non se
  ne osserva nessuna.
- **(c) Fork.** Il 14,7 % dei round misurati (207/1 405) ha visto più di un blocco alla stessa
  altezza, con 347 blocchi candidati poi orfani. La distribuzione per terzo è stabile (69/65/73).
  La **profondità massima di riorganizzazione è 1 blocco** su tutti e sei i nodi analizzati:
  ricostruita dalle sequenze `UpdateTip`, da 68 (miner-2) a 164 (miner-0) reorg per nodo, tutte di
  profondità 1. Ci sono 636 eventi `displace`, **tutti verso il blocco di score migliore**
  (636/636). Il tie-break per score ha scelto il blocco finale in 1 475 valutazioni `round` su
  1 735; la regola nativa (first-seen, colonna `legacy`) solo in 908. **In 119 dei 207 fork il
  primo blocco ricevuto non era quello finale**: la regola nativa avrebbe prodotto fino a 119
  inversioni (8,5 % dei round), evitate dal tie-break per score. I 154 eventi `defer` (un nodo
  trattiene il proprio blocco perché il suo score è migliore di quello ricevuto) sono tutti
  coerenti (154/154). Tempo massimo passato da un nodo su un blocco poi orfano: **< 1 s** (0,97 s,
  con risoluzione del log di 1 s). **Giudizio: conforme.**
- **(d) Prop. 5.18 sui delay reali.** **Non eseguibile in modo significativo** su questa run, per
  due motivi. (i) Senza `wpoa_debug` mancano i delay privati dei candidati che non hanno proposto,
  quindi non si può simulare il rumore sui delay reali di **ogni** round. (ii) Il tasso di
  inversione reale osservato è 0, per cui entrambi i modelli (rumore simmetrico e vantaggio
  all'uscente) lo riproducono banalmente, e non c'è nessun beneficiario da discriminare. Il rumore
  vero di scheduling (0,43 s, stabile per terzi) contro un margine medio di 2,9 s è coerente con un
  bound piccolo. Per il test completo serve una run con `runtime.wpoa_debug: true`.

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`, `phi_s`,
  `delay_true_s`)
  - **Cosa misura**: lo spacing dei blocchi realizzato e il ritardo vero del vincitore.
  - **Osservato**: `dt_prev` medio **8,075 s** (deviazione standard 2,34, mediana 8,0, min 3,
    max 13; n = 1 405). Per epoca: fra 7,76 (ep. 9) e 8,45 s (ep. 5), senza deriva: per terzo 8,14 /
    7,97 / 8,12 s. Delay vero medio del vincitore 8,003 s.
  - **Atteso**: convergenza a `T_block` = 8 s, dentro la banda 8 ± 4 + 0,3·Phi.
  - **Giudizio**: **conforme** (+0,9 % sul target; epoca 16 parziale a 8,35 s su 26 blocchi).
- **File**: [analysis/plots/phi_over_time.png](plots/phi_over_time.png),
  [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv) (`phi_consistent`)
  - **Cosa misura**: la traiettoria del termine di feedback `Phi`.
  - **Osservato**: 44 valori distinti; media −0,071 s, deviazione standard 0,605 s, range
    [−2,0; +1,83] s. **0 round a ±M** (M = 4 s). 156 cambi di segno su 1 404 transizioni (11 %), 83
    round con Phi = 0. La mediana mobile resta fra −0,4 e +0,25 s.
  - **Atteso**: Phi piccolo e centrato se il controllo funziona; saturazione a ±M o oscillazione
    di segno round per round indicherebbero guadagno insufficiente o eccessivo.
  - **Giudizio**: **conforme**. Il massimo |Phi| è il 50 % di M e la variabilità è lenta, non
    un'alternanza round per round. `phi_consistent = FAIL` **non è un difetto**: il check (non
    critico) è una sonda tarata su run a feedback spento.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv) (identità del motore)
  - **Cosa misura**: `W_k_raw = ESG_Mk·(tau_Mk + Σc_i)` e
    `w_k_final = W_k_raw·(rho_prev·0,5 + 0,5)`.
  - **Osservato**: errore relativo massimo **0** per la prima identità e **1,8·10⁻¹⁶** per la
    ricorsione (80 righe, epoca 1 compresa, dove `w_final = W_raw`). Il peso pubblicato è
    `w_final × 100` in 75 righe su 80; le altre 5 differiscono di ±0,001 per arrotondamento
    all'intero.
  - **Atteso**: identità numeriche.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [analysis/phase1/esg_events.csv](phase1/esg_events.csv) (ESG statici)
  - **Osservato**: `miner_esg_score` costante in ogni epoca per tutti i cluster (75/56/55/49/29).
  - **Giudizio**: **conforme**.
- **File**: [analysis/plots/weights_over_time.png](plots/weights_over_time.png),
  [analysis/plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png)
  - **Cosa misura**: i pesi per miner nei tre stadi (grezzo, dopo malus, dopo smorzamento).
  - **Osservato**: i tre pannelli sono **identici** (Psi = 1, `g` = identità). Dopo l'epoca 1
    (attività parziale di bootstrap: 84 000 contro 1,58 M) miner-2 oscilla fra 1,58 e 1,91 M,
    miner-1 fra 0,23 e 0,39 M, gli altri tre fra 0,06 e 0,13 M. Spearman epoca → peso fra 0,32 e
    0,51 per tutti: nessuna tendenza forte.
  - **Atteso**: pesi rumorosi (tau riestratto ogni epoca), senza tendenza sistematica, e
    l'ordinamento della balena preservato.
  - **Giudizio**: **conforme**. Il salto 1 → 2 riflette solo l'epoca di bootstrap.
- **File**: [analysis/phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [analysis/plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [analysis/plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)
  - **Cosa misura**: la retroazione `rho(e)` → peso pubblicato in `e+1` (Spearman lag-1).
  - **Osservato**: `rho` **non è nullo**: media 0,0049, deviazione standard 0,0032, range
    [0; 0,0105], 8 zeri su 80 (l'epoca 1 e alcune epoche senza restituzioni), 807 restituzioni al
    treasury tutte da miner. Spearman aggregato **0,054** (p = 0,64, n = 75); per cluster fra −0,19
    (miner-1) e +0,22 (miner-2), nessuno significativo. Lo scatter mostra due bande orizzontali
    (balena e piccoli) senza pendenza.
  - **Atteso**: con `lambda_w` = 0,5 il fattore vale 0,5·rho + 0,5. Con rho ≤ 0,0105 il fattore sta
    fra 0,500 e 0,505, un effetto dell'1 % completamente sommerso dalla varianza di tau.
  - **Giudizio**: **conforme**. La retroazione è attiva ma quantitativamente inerte in questo
    regime (atteso, lo dichiara anche il profilo: "rho is ~0.003").
- **File**: [analysis/phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [analysis/plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png)
  - **Cosa misura**: `Gini(pubblicato) − Gini(input)` nel tempo.
  - **Osservato**: le differenze stanno fra −0,0007 e +0,0007; pendenza 9·10⁻⁶ per epoca;
    Spearman 0,17 (p = 0,53).
  - **Atteso**: pendenza ≈ 0 (il motore non amplifica la disuguaglianza).
  - **Giudizio**: **conforme**. L'ampiezza è di quattro ordini di grandezza sotto il Gini stesso
    (≈0,6).
- **File**: [analysis/plots/esg_scores.png](plots/esg_scores.png) (e `esg_scores/company.png`,
  `esg_scores/miner.png`)
  - **Osservato**: 35 score certificati. Miner-2 ha l'ESG più alto fra i miner (75), in linea con
    il profilo. `certified_scores_reflected_in_the_engine` = FAIL (non critico) per
    1EKW9gXoGtAK… = **company-29** e 1EWs2GdeMYzd… = **company-28**: certificati ma mai registrati
    nel cluster, perché i loro nodi erano già morti.
  - **Giudizio**: **scostamento significativo da indagare**, ma **dell'harness, non del
    protocollo**: il motore ignora correttamente due aziende senza membership (§5).

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](phase2/epoch_concentration.csv),
  [analysis/phase3/report.md](phase3/report.md) §3,
  [analysis/plots/concentration_over_time.png](plots/concentration_over_time.png)
  - **Cosa misura**: HHI, N_eff, Gini e Nakamoto, teorici contro osservati nella stessa epoca.
  - **Osservato**: aggregato HHI teorico **0,5825** contro osservato **0,5770**; N_eff 1,72 contro
    1,73; Gini osservato 0,603 contro circa 0,60 teorico. Nakamoto(1/2) = 1 in ogni epoca misurata,
    sia teorico sia osservato. Per epoca l'HHI osservato oscilla fra 0,465 e 0,683 attorno al
    teorico (0,556–0,612). Il Gini osservato delle ultime epoche (0,65–0,68) supera il teorico
    (≈0,60), ma nell'epoca 16 lo fa su soli 26 blocchi.
  - **Atteso**: il confronto affidabile è l'aggregato; per epoca, con 100 blocchi, la varianza
    multinomiale sposta l'HHI di ±0,05. Nakamoto(1/2) = 1 è la conseguenza diretta di una balena
    con quota spettante 0,75.
  - **Giudizio**: **conforme** (HHI aggregato −1 %). La concentrazione è quella del **peso**, non
    un'amplificazione dell'elezione: la linea teorica e quella osservata coincidono. Il Gini
    osservato per epoca più alto negli ultimi terzi è compatibile con la varianza (in 100 blocchi
    un piccolo con p = 0,035 vince 0 blocchi con probabilità 2,8 %, ed è successo nelle epoche
    14–15 per miner-0), ma è da ricontrollare su una run completa.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](phase3/streak.md),
  [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv)
  - **Cosa misura**: la serie massima di vittorie consecutive e la probabilità di ripetizione,
    contro un Monte-Carlo sugli stessi pesi.
  - **Osservato**: `L_max` aggregato 18 contro 22,1 simulato (p = 0,87). Ripetizione 0,5855 contro
    0,5832 (p = 0,46). Per epoca: **nessun** `L_max` con p < 0,05 (minimo 0,074 nell'epoca 15); per
    la ripetizione un solo p < 0,05 (epoca 15: 0,677 contro 0,555, p = 0,034). L'epoca 7 è
    all'estremo opposto (0,414, p = 0,9985: poche ripetizioni).
  - **Atteso**: nessun eccesso sistematico; con 15 epoche 0,75 p < 0,05 attesi.
  - **Giudizio**: **conforme**: 1 rigetto su 15, non sistematico, bilanciato da epoche con
    ripetizioni in difetto. Nessun indizio di rumore di rete persistente per nodo né di seed non
    rinfrescato, coerente con 0 inversioni reali.

### 3.10 Malus

Caso **J.1**: nessuna violazione iniettata (`malicious.enabled = false`), meccanismo attivo
(`enable-wpoa-malus = true`).

- **File**: [analysis/phase2/malus_state.csv](phase2/malus_state.csv),
  [analysis/phase3/malus_invariants.csv](phase3/malus_invariants.csv),
  [analysis/plots/malus_invariant_audit.png](plots/malus_invariant_audit.png)
  - **Osservato**: M = 0 e Psi = 1 in **80 celle (epoca, validatore) su 80**; i tre invarianti
    valgono ovunque (heatmap tutta verde, "0 violation(s) across 80 cells"). Nel registro, 60 875
    campioni di malus hanno tutti Psi in [0,1]. `weight_effective == weight_raw` ovunque (i pannelli
    di `weights_over_time.png` coincidono).
  - **Atteso**: effetto esattamente nullo sul comportamento onesto.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase1/malus_detections.csv](phase1/malus_detections.csv), `phase1/malicious_*.csv`,
  [analysis/phase2/malus_actions.csv](phase2/malus_actions.csv),
  [analysis/phase2/malus_detection_events.csv](phase2/malus_detection_events.csv),
  [analysis/phase3/malus_detection.csv](phase3/malus_detection.csv),
  [analysis/phase3/malus_funnel.csv](phase3/malus_funnel.csv),
  [analysis/phase3/malus_latency.csv](phase3/malus_latency.csv),
  [analysis/phase3/malus_rate.csv](phase3/malus_rate.csv)
  - **Osservato**: 0 righe in tutti i file (funnel tutto a 0, precision/recall non definiti, rate
    vuoto). `malus_effectiveness.md` **non è presente**: l'esperimento malicious non è stato
    eseguito.
  - **Giudizio**: **conforme**, perché è il risultato atteso per J.1.
- **File**: [analysis/plots/malus_action_funnel.png](plots/malus_action_funnel.png),
  [analysis/plots/malus_state_trajectory.png](plots/malus_state_trajectory.png),
  [analysis/plots/malus_detection_latency.png](plots/malus_detection_latency.png),
  [analysis/plots/malus_weight_effect.png](plots/malus_weight_effect.png)
  - **Osservato**: i primi tre sono segnaposto vuoti ("no malicious experiment ran on this
    profile"). `malus_weight_effect.png` mostra solo il gruppo onesto (n = 5) con una variazione del
    peso efficace dalla prima all'ultima epoca di +10,7 / +19,5 volte (mediana ≈12). Questo è
    l'effetto dell'epoca 1 di bootstrap, non del malus (Psi = 1 ovunque).
  - **Giudizio**: **conforme**. Figure degeneri come atteso; la variazione in `malus_weight_effect`
    non è attribuibile al malus.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [analysis/phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv)
  (calcolato qui, epoche 2–16, n = 75)
  - **Cosa misura**: se guadagno o volume di transazioni entrano nell'elezione per canali diversi
    dal peso.
  - **Osservato, punto 1** (Spearman con `n_blocks_won_epoch`): `w_k_published` 0,857,
    `W_k_raw` 0,856, `earnings_g_k` 0,727, `companies_contribution_sum` 0,704, `income` 0,19,
    `miner_activity` 0,19.
  - **Osservato, punto 2** (residui `p_hat − p_theoretical`): Spearman contro `earnings_g_k` 0,12
    (p 0,30), `income` 0,14 (p 0,23), `miner_activity` 0,13 (p 0,27), `companies_contribution_sum`
    0,02 (p 0,87). **Entro validatore** (valori centrati per miner), residuo contro guadagno **nella
    stessa epoca**: r = 0,35 (p ≈ 0,001). Residuo contro guadagno **dell'epoca precedente**:
    r = **0,000** (p = 1,0); contro l'attività delle aziende: r = −0,03.
  - **Atteso**: correlazione del punto 1 interamente mediata dal peso; nulla al punto 2.
  - **Giudizio**: **conforme**. L'unica correlazione residua (r = 0,35 nella stessa epoca) ha il
    verso causale opposto. In `weight_reader.cpp` il coinbase accredita al miner le fee dei blocchi
    che produce, quindi chi vince più del dovuto in un'epoca **guadagna** di più in quella stessa
    epoca. Con lag 1, che è il verso in cui un canale di influenza dovrebbe agire, la correlazione
    è esattamente nulla. Nessun canale non documentato.

### 3.12 Integrità della run e controlli di consistenza

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  - **Osservato**, critici (**7/7 PASS**): `registry_weights_finite_and_positive` (60 875
    campioni), `no_phantom_validator_in_registry`, `malus_finite_and_psi_in_unit_interval`,
    `delay_recompute_mismatch_rounds_is_zero`, `every_esg_publication_reached_the_stream` (35/35),
    `only_miners_pay_the_treasury` (807/807), `at_least_one_fully_measured_epoch` (15).
    Non critici: `phi_consistent` FAIL (atteso, §3.6); `certified_scores_reflected_in_the_engine`
    FAIL (company-28 e company-29, §3.7); `traffic_counts_within_configured_range` PASS (459 coppie
    complete, tutte nel range).
  - **Giudizio**: **conforme** sui critici. Dei due FAIL non critici, uno è atteso e l'altro è un
    difetto dell'harness (§5).
- **File**: [analysis/phase1/verification.csv](phase1/verification.csv)
  - **Osservato**: 60 verifiche `weightverifyweights` (epoche 1–14; le ultime epoche non erano
    ancora verificabili al blackout), **60/60 `verdict = ok`**, `published == recomputed`.
  - **Giudizio**: **conforme**. Nessun peso non ricalcolabile.
- **File**: [analysis/phase2/epoch_traffic.csv](phase2/epoch_traffic.csv),
  [analysis/plots/traffic_per_epoch.png](plots/traffic_per_epoch.png)
  - **Osservato**: 33 nodi per epoca (28 aziende attive e 5 miner; company-28 e company-29 assenti).
    Epoche 1–14: pianificate = inviate = on-chain (es. epoca 14: 1 272/1 272/1 272). Epoca 15:
    1 278 / 1 275 / 1 264. Epoca 16: 1 087 / 361 / 95.
  - **Atteso**: prima e ultima epoca parziali.
  - **Giudizio**: **lieve scostamento dovuto all'interruzione**. Nell'epoca 16 il crollo è il
    blackout a 26 blocchi dall'inizio. I 3 invii e gli 11 item on-chain mancanti nell'epoca 15 sono
    gli ultimi eventi finiti nella coda di log persa (byte NUL) e gli item che il collector
    dell'admin non ha fatto in tempo a registrare. Nessun effetto sui pesi dell'epoca 15, calcolati
    dalla catena e verificati.
- **File**: [analysis/phase1/rpc_errors.csv](phase1/rpc_errors.csv)
  - **Osservato**: 410 errori, **tutti fra le 14:00 e le 14:59Z** (bootstrap): 4 × 102
    `wpoalist*` con "Round not evaluable" prima che il registro dei pesi fosse attivo, e 2
    `weightregistermembership` falliti verso company-28 e company-29. Nessun errore nelle 2h40m
    successive.
  - **Giudizio**: **conforme**. Errori benigni di bootstrap, più il sintomo del difetto su
    company-28 e company-29.
- **File**: `manifest.json`, `recovery/recovery_report.json`
  - **Osservato**: `status = interrupted`, `final_height` 1627 contro `target_height` 5120 (31,8 %),
    manifest ricostruito (§ premessa), `shutdown.json` assente, nessuno snapshot finale.
    `true_winner_mismatch` 0 su 1 518 righe, quindi `blocks.csv` è raccolto dopo la correzione del
    blocco orfano.
  - **Giudizio**: **scostamento significativo da indagare** sul piano dell'**esecuzione**, non del
    protocollo. La run è troncata al 32 %, con la potenza statistica ridotta di conseguenza.
- **Ultima epoca (16)**: 26 blocchi, Wilson larghi fino a 0,31 (miner-1: [0,110; 0,421]),
  miner-0 e miner-4 a 0 vittorie con quota spettante 3–4 % (probabilità di 0 su 26: 41 % e 32 %).
  **Esclusa da ogni conclusione di tendenza.**

## 4. Punti di forza

- **Proporzionalità esatta con una balena, senza smorzamento.** Miner-2 (1FeWA69kpmfJ…) vince il
  74,54 % dei blocchi contro il 74,96 % spettante, e i quattro piccoli restano entro ±0,7 punti.
  GoF aggregato p = 0,62, TV 0,0095, MAE 0,0038. È lo scenario della tabella di riferimento
  (0,714), riprodotto sulla quota reale 0,75.
- **Randomness pulita su tutti i canali.** `E_i` media 1,0049 (`√n·D` 0,50); argmin di
  `score_norm` 0,5014 (`√n·D` 1,05); score privato del vincitore 0,503 (KS p 0,53); Prop. 5.17 fra
  0,93 e 1,35 per vincitore, nessun KS significativo.
- **Timer race senza inversioni.** Q1 = 0,983, 0 inversioni reali su 207 fork, reorg al massimo di
  1 blocco, 636/636 `displace` verso lo score migliore. Il tie-break per score recupera 119 fork
  che il first-seen nativo avrebbe perso, e i round vinti al bordo di banda scendono allo 0,57 %.
- **Meccanica bit-esatta.** Delay mismatch 0 su 7 590 (≤ 3,6·10⁻¹⁵ s); `score_norm` mismatch
  ≤ 2,2·10⁻¹⁶; identità del weight engine esatte (≤ 1,8·10⁻¹⁶); 60/60 pesi verificati.
- **Block time sul target.** Media 8,075 s (+0,9 %), stabile per terzi (8,14 / 7,97 / 8,12);
  `Phi` mai oltre il 50 % del suo bound.
- **Malus a effetto nullo sugli onesti.** M = 0, Psi = 1 e invarianti veri in 80/80 celle.
- **Nessun canale di influenza fuori dal peso.** Residui contro guadagno dell'epoca precedente:
  r = 0,000.
- **Il recupero dopo il blackout è stato pulito.** Nessuna riga JSON corrotta: i byte NUL erano
  solo in coda. La pipeline gira senza modifiche sui dati recuperati.

## 5. Punti critici / da approfondire

- **Run troncata dal blackout al 31,8 % dell'altezza target** (15 epoche misurate su 50, l'ultima
  parziale).
  - *Entità:* intervalli di Wilson larghi in media 0,110, e potenza circa ⅓ di quella progettata
    per il GoF per epoca e per i fit longitudinali.
  - *Causa:* perdita di alimentazione alle ~17:39Z, esterna al sistema.
  - *Serve:* rilanciare `regional-whale-none` da capo con lo stesso seed. Una ripresa in corso non è
    supportata dall'harness e sporcherebbe i timestamp. In alternativa, usare questa run come
    pilota per il confronto con `-sqrt` e `-log`, dichiarandone la lunghezza.
- **company-28 e company-29 mai attive** (nodi MultiChain chiusi al bootstrap, h 28 e h 9).
  - *Entità:* 2 aziende su 30. I cluster di miner-3 e miner-4 lavorano con 2 aziende invece di 3,
    quindi con un peso inferiore alle attese del profilo. Due check non critici falliscono per
    questo motivo.
  - *Causa ipotizzata:* crash o OOM del daemon durante la fase di join con 38 nodi avviati insieme.
    Il `debug.log` si interrompe senza errore, e con il riavvio dell'host il `dmesg` è perso.
  - *Serve:* un controllo di liveness nell'orchestratore dopo `launch_peers` e prima di
    `register_membership`, che fallisca subito o riavvii il nodo. Serve anche verificare se si è
    ripetuto in altre run del 2026-09-27 (`grep "did not serve RPC" logs/*/stdout.log`).
- **L'epoca 2 viene testata pur contenendo blocchi di setup.**
  - *Entità:* 21 blocchi su 100 (h 200–220) in round robin nativo. Ne derivano 1 rigetto del GoF su
    2 e 2 violazioni di Wilson su 4.
  - *Causa:* la pipeline esclude solo le epoche *interamente* sotto `setup-first-blocks`, ma i
    conteggi `O_i`/`B` dell'epoca 2 includono anche i blocchi di setup.
  - *Serve:* in `phase2`/`phase3`, filtrare i blocchi con `in_setup = True` anche dentro le epoche
    a cavallo della soglia. Sui 79 blocchi wPoA dell'epoca 2 il χ² ricalcolato dà p ≈ 0,5.
- **Il GLM longitudinale continua a segnalare "NOT consistent" per costruzione.**
  - *Entità:* β1 = 1,49 contro H0 = 1, ma la nulla corretta è 1,50 [1,41; 1,60].
  - *Causa:* H0 mal specificata (pendenza ≈ 1/(1−p) per validatori con p grande).
  - *Serve:* sostituire in `stat/longitudinal.py` l'H0 fissa con un β1 nullo calibrato col
    Monte-Carlo sulle `p_theoretical` della run, come fatto qui.
- **Copertura parziale degli score privati** (§3.5.1).
  - *Entità:* designato determinabile solo nei 207 round con fork su 1 405; il punto (d) non è
    eseguibile.
  - *Causa:* `runtime.wpoa_debug: false` nel profilo.
  - *Serve:* per le run destinate al §3.5.1 completo, `wpoa_debug: true` (costo stimato in
    `derived.wpoa_debug_projected_bytes`).
- **Gini osservato per epoca sopra il teorico nell'ultimo terzo** (0,65–0,68 contro ≈0,60).
  - *Entità:* +0,05/+0,07; nell'aggregato lo scarto sparisce (HHI −1 %).
  - *Causa più probabile:* varianza multinomiale (miner-0 a 0 vittorie in 2 epoche con p = 0,035).
  - *Serve:* verificarlo sulla run completa, dove una deriva reale si vedrebbe su 35 epoche in più.

## 6. Conclusione

Sulle 15 epoche recuperate (1 426 blocchi wPoA misurati) il meccanismo wPoA si comporta come
previsto dal modello su tutti e cinque gli assi. Il limite dichiarato è la potenza statistica
ridotta dal blackout.

- **Affidabilità della sortition: conforme.** L'elezione segue il peso effettivo anche con una
  balena da 0,75: quota osservata 0,7454 contro 0,7496 spettante, GoF aggregato p = 0,62, 4/75
  violazioni di Wilson (3,75 attese). Log-rapporti con pendenza 1,044 e intercetta −0,055. Il GLM,
  ricalibrato, è nel centro della sua nulla. L'unico rigetto per epoca non spiegato da un artefatto
  (epoca 7) è in linea con lo 0,75 atteso.
- **Qualità della randomness: conforme.** `E_i` media 1,0049, argmin di `score_norm` 0,5014,
  score privato del vincitore 0,503 (KS p = 0,53), Prop. 5.17 entro il rumore per tutti i
  vincitori.
- **Efficacia dello smorzamento:** non applicabile per costruzione (`dump-function = none`,
  g = identità: i pannelli prima e dopo lo smorzamento coincidono). Questa run è il **riferimento
  non compresso** della terna `none`/`sqrt`/`log`: il 74,5 % osservato è la quota da cui `sqrt` (atteso
  ≈0,46) e `log` (≈0,23) dovranno scendere preservando l'ordinamento.
- **Efficacia del malus: conforme.** Nessuna violazione iniettata e effetto esattamente nullo: M = 0
  e Psi = 1 in 80/80 celle, invarianti veri ovunque, nessuna segnalazione.
- **Stabilità del block time: conforme.** Media 8,075 s contro 8, nessuna deriva per terzi,
  `Phi` mai saturato (|Phi| ≤ 2,0 s contro M = 4 s) e non oscillante. In più, 0 inversioni reali e
  fork risolti sempre verso lo score migliore, con reorg di profondità 1.

I punti aperti riguardano **l'esecuzione e gli strumenti, non il protocollo**: la run è
troncata, due aziende sono cadute al bootstrap, la pipeline include i blocchi di setup
nell'epoca 2 e l'H0 del GLM è mal specificata. Per usare questa configurazione come risultato di
tesi serve la run completa a 50 epoche.
