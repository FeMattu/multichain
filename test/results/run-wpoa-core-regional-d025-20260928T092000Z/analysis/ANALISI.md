# Analisi della run run-wpoa-core-regional-d025-20260928T092000Z

Run: `test/results/run-wpoa-core-regional-d025-20260928T092000Z`
Timestamp UTC della run: 2026-09-28T09:20:00Z
Catena: `wpoa-core-regional-d025` — profilo: `test/config/profiles/core/regional-d025.yaml` — regime: core
Analisi prodotta il: 2026-09-28

Legenda validatori (da [addresses.json](addresses.json)):
miner-0 (17rqappxadKR…), miner-1 (1aRd3erLH9tq…), miner-2 (1PY32fgWCYNV…), miner-3 (18TjG2hGRrKD…), miner-4 (1V1vDmRerh7D…).

> **Premessa.** Il sistema è stocastico su più livelli indipendenti: score ESG estratti a caso
> in `[1,100]`, traffico per azienda estratto in `[30,60]` tx/epoca, restituzioni in `[0,20]`
> per epoca, VRF a ogni round e, in regime `core`, la rete emulata. I pesi sono quindi un
> *campione*, non una configurazione. Nessun giudizio è dato su singoli round o singole epoche:
> solo su aggregati, con intervalli di confidenza e correzione per confronti multipli
> (30 epoche misurate ⇒ ~1,5 rigetti attesi per puro caso a `alpha = 0.05`).
>
> **Scopo della run.** È un punto dello sweep sulla semiampiezza della banda dei delay:
> identica a `regional-long23h-feedback` (run `run-wpoa-core-regional-fb-20260926T124607Z`,
> δ = 0,5) per seed, mappa, nodi, traffico e parametri del weight engine, ma con
> **δ = 0,25 ⇒ Δ_max = 2 s** e 30 epoche invece di 100. La domanda specifica è la legge di scala
> della Proposizione 5.18: a parità di rumore σ, le inversioni istantanee dovrebbero crescere
> circa come 1/Δ_max, e il tie-break per score dovrebbe tenere basse quelle finali. Per questo
> il confronto con la run δ = 0,5 compare in più sezioni; i numeri di riferimento di quella run
> sono ricalcolati **con lo stesso script** (vedi §3.5.1).

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| Nome catena | `wpoa-core-regional-d025` | [manifest.json](manifest.json) `chain_name` |
| Seed esperimento / seed analisi | 20260905 / 20260905 | `manifest.json` `seed`; [analysis/phase3/report.md](analysis/phase3/report.md) |
| Profilo | `test/config/profiles/core/regional-d025.yaml` | `manifest.json` `profile_path` |
| Regime | `core` (CORE, mappa emulata) | `manifest.json` `fabric.backend` |
| Topologia | `regional`: 20 siti, 7 hub, 34 link | `fabric.topology.*` |
| Latenza peggiore sul percorso | 5,137 ms (RTT 10,3 ms) | `derived.worst_path_delay_ms`, `derived.worst_round_trip_s` |
| Nodi per ruolo | 1 admin, 2 CA, 5 miner, 30 aziende (38 totali) | `manifest.json` `nodes.*` |
| Cluster | 6 aziende per miner (company-k → miner-(k mod 5)); **effettivi: miner-1 4 aziende, miner-4 5** (3 aziende morte al bootstrap, §3.12) | [clusters.json](clusters.json); [analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv) `n_companies` |
| Epoche | 30 × 100 blocchi pianificate; misurate 2–31 (la 1 è in setup, la 31 è parziale con 21 blocchi) | `epochs.*`; `report.md` |
| Altezza finale / target / esito | 3 124 (manifest), 3 120 (report) / 3 120 / `ok`, nessun errore | `final_height`, `derived.target_height`, `status`, `error` |
| `dump-function` | `none` (g(w) = w) | `wpoa_params`; [analysis/phase1/config.csv](analysis/phase1/config.csv) |
| `target-block-time` T_block | 8 s | `chain_params`, `config.csv` |
| `wpoa-sortition-delta` δ | **0,25** ⇒ Δ_max = 2 s, banda base **[6 s, 10 s]** | `wpoa_params`, `config.csv` |
| `wpoa-sortition-lambda` λ | 0,3 | `wpoa_params` |
| Bound del feedback M | min(0,5·8 ; 8·(1−0,25)/0,3) = min(4 ; 20) = **4 s** | ricavato |
| Ammissibilità del timer | Δ_max = 2 ≤ T_block − λM = 6,8 s: soddisfatta | ricavato |
| Parametri malus | μ = 0,5; M_max = 3; p(Equiv) = 4, p(BadWeight) = 2, p(SelfWrite) = 1, p(Delay) = 0,25 | `wpoa_params`, `config.csv` |
| Stato malus | meccanismo **attivo** (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`, 0 miner malicious) | `config.csv`; [malicious_manifest.json](malicious_manifest.json) |
| Weight engine | κ = 100; λ_w = **0,99**; `weight-alpha` = 0,2 (**inerte**, validato e mai letto) | `weight_engine_params`, `config.csv` |
| `setup-first-blocks` | 220 effettivi (220 richiesti; floor di protocollo 109) | `effective_setup_first_blocks`, `derived.*` |
| `mining-diversity` | 0,0 (non vincolante) | `chain_params` |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | `chain_params` |
| `initial-block-reward` / `first-block-reward` | 0 / 3,5·10¹⁴ (premine 3,5 M) | `chain_params`, `derived.premine` |
| Seed GAS iniziale per miner | 180 200 (contro 600 200 della run δ = 0,5: la run è più corta) | `derived.miner_seed_gas` |
| Traffico | stream `supply-chain-events`; aziende [30,60] tx/epoca; restituzioni [0,20]/epoca di importo [50,250]; ESG in [1,100] | `traffic.*` |
| Lookback RANDAO | 101 | `wpoa-randao-lookback` |
| Piano malicious | `enabled = false`, `target_action_rate = 0`, `actions` {selfwrite 0,5; badweight 0,5}, `start_epoch = 1`, `malicious_miner_ids = []` | `malicious_manifest.json` |
| Log debug | `-debug=wpoa -debug=wpoafork`, log `UpdateTip` presenti; `debug.log` dei 5 miner e dell'admin leggibili via container (file `root` 0600), righe wPoA estratte in [analysis/private/](analysis/private/) | `chains/<nodo>/wpoa-core-regional-d025/debug.log` |

**Divergenze manifest ↔ catena.** `config.csv` e `effective_chain_params` concordano su tutti i
parametri elencati; l'unica differenza è `setup-first-blocks = null` nel profilo, risolto a 220 dal
launcher (atteso). Altezza finale 3 124 nel manifest contro 3 120 nel report: la pipeline chiude
all'ultima altezza assestata; differenza irrilevante.

**Pesi effettivi alla prima epoca misurata (epoca 2).** Non sono una configurazione ma l'esito
stocastico di ESG × τ ([analysis/phase1/esg_events.csv](analysis/phase1/esg_events.csv),
[analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv), [analysis/phase2/epoch_level.csv](analysis/phase2/epoch_level.csv)):

| Validatore | ESG miner | τ miner | aziende | Σ contributi aziende | W_k grezzo | ρ_prev | w pubblicato (ep. 2) | w_eff a inizio ep. 2 | p teorica a inizio ep. 2 |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| miner-0 (17rqappxadKR…) | 29 | 16 | 6 | 105,10 | 3 512 | 0 | 3 512 | 10 585 | 0,105 |
| miner-1 (1aRd3erLH9tq…) | 56 | 21 | 4 | 67,01 | 4 929 | 0 | 4 929 | 14 504 | 0,145 |
| miner-2 (1PY32fgWCYNV…) | 75 | 5 | 6 | 97,07 | 7 655 | 0 | 7 655 | 28 425 | 0,283 |
| miner-3 (18TjG2hGRrKD…) | 55 | 6 | 6 | 141,16 | 8 094 | 0 | 8 094 | 24 035 | 0,240 |
| miner-4 (1V1vDmRerh7D…) | 49 | 4 | 5 | 148,37 | 7 466 | 0 | 7 466 | 22 785 | 0,227 |

(`w_eff` a inizio epoca 2 è ancora il peso dell'epoca 1, `w = W` senza fattore ρ; il nuovo peso
entra dopo il margine di stabilità.) Sull'intera run il rapporto max/min dei pesi pubblicati per
epoca vale in media **3,85** (range 1,77–7,69), più disperso della run δ = 0,5 (3,07) perché con
30 epoche e un seed GAS più piccolo ρ è circa 3,5 volte più grande (§3.7). Nessuna balena; pesi
medi: miner-2 20 974, miner-3 15 717, miner-4 15 165, miner-1 8 340, miner-0 6 898.

## 2. Executive summary

- **Randomness pulita** (nessun test di randomness fallito): sugli score **privati** VRF (14 500 coppie round × miner) `E_i` ha media 0,9989 (banda 1 ± 0,0163) e `√n·D = 0,62`; lo `score_norm` dell'argmin privato ha media 0,4929 e `√n·D = 0,93`, entrambi sotto il critico 1,358.
- **Meccanica del delay esatta:** 0 mismatch su 14 505 coppie candidato-round (massimo 2·10⁻¹⁴ s contro tolleranza 1,5 ms).
- **Sortition proporzionale al peso, con una fluttuazione di campionamento visibile:** GoF aggregato χ² = 6,76 (df 4), p = 0,149, TV = 2,2 %; 2/30 epoche rigettate (1,5 attese); 11/150 intervalli di Wilson violati (7,5 attesi, binomiale p = 0,13); p-value per epoca uniformi (KS p = 0,79). Lo scarto maggiore (miner-4 +1,6 pp, miner-2 −1,5 pp) è **già presente nei vincitori designati dagli score privati**, quindi è nell'estrazione e non nella timer race.
- **Legge di scala di Prop. 5.18 confermata:** dimezzando Δ_max (4 → 2 s) le inversioni istantanee (primo blocco ricevuto ≠ argmin) passano dal 10,6 % al **16,3 %** (472/2 900) e le fork dal 21,2 % al **32,1 %**; il margine medio fra i due timer privati scende da 2,24 a **1,19 s**. Un rumore simmetrico con **σ ≈ 0,32 s** (contro 0,35 s a δ = 0,5) riproduce il tasso e chi ne beneficia (26,7 % all'uscente osservato, 27,7 % simulato): lo stesso rumore, non un meccanismo nuovo.
- **Il tie-break per score assorbe l'aumento:** inversioni **finali 6/2 900 (0,21 %)**, contro 0,31 % a δ = 0,5 (differenza non significativa, p = 0,35); la catena finale tiene il blocco di score minimo in **930/930** round con fork; 666 blocchi trattenuti, 0 `defer-release`; tutte le riorganizzazioni hanno profondità 1.
- **Block time sul target e meno disperso:** media 8,014 s (sd 1,24 s contro 2,41 s a δ = 0,5), nessuna deriva; Φ mai saturato (|Φ| ≤ 1,17 s contro M = 4 s).
- **Weight engine esatto, retroazione più forte:** identità con errore ≤ 10⁻¹⁴; ρ medio 0,0087 (max 0,023) sposta il peso fino a ×3,3 fra miner; Spearman lag-1 ρ(e) → w(e+1) fra 0,87 e 0,94 per cluster.
- **Malus a effetto esattamente nullo** (nessuna violazione iniettata): M = 0, Ψ = 1 su 155 celle, invarianti veri, 115/115 pesi verificati.
- **Da segnalare (nessuno invalida il meccanismo):** (i) 3 aziende (company-16, -26, -29) morte al bootstrap senza che l'orchestratore se ne accorgesse; (ii) gap standardizzato di Prop. 5.17 sugli score privati con media 1,035 (z = 1,87, KS non rigettato), da ricontrollare su una run più lunga.

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: [analysis/phase2/candidate_long.csv](analysis/phase2/candidate_long.csv) (score pubblico HMAC) — test A.1
  - **Cosa misura**: `E_i = score_public · weight_effective`, che deve essere Exp(1).
  - **Osservato**: n = 14 505 (2 901 round × 5 candidati, tutti eleggibili), media 1,0041, `√n·D = 0,57`.
  - **Atteso**: media in 1 ± 1,96/√n = [0,9837; 1,0163]; `√n·D ≤ 1,358`.
  - **Giudizio**: **conforme** — scarto +0,41 %, un quarto della semiampiezza. Questo score è la forma pubblica `HMAC-SHA256(seed, indirizzo)`, indipendente da quella VRF con cui gira l'elezione: verifica la normalizzazione e la pipeline. La VRF è testata sotto, sulla fonte privata.
- **File**: `phase2/candidate_long.csv` — test A.2 (minimo per round)
  - **Cosa misura**: `min_i score_norm_public` per round, che deve essere U(0,1).
  - **Osservato**: n = 2 901, media 0,4985, `√n·D = 0,59`. Sulle righe `is_winner` la media sale a 0,815: lo score pubblico del minatore reale non è legato all'argmin pubblico (vedi §3.5), come atteso.
  - **Atteso**: media 0,5, `√n·D ≤ 1,358`.
  - **Giudizio**: **conforme** (scarto −0,3 %).
- **File**: `phase2/candidate_long.csv` — test A.3
  - **Cosa misura**: `score_norm_mismatch_public`, loggato contro ricalcolato.
  - **Osservato**: 0 righe non nulle; massimo 4,9·10⁻¹⁵.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/timer_race.md](analysis/phase3/timer_race.md), [analysis/phase3/wpoa_timer_race.csv](analysis/phase3/wpoa_timer_race.csv) — score **vero** del vincitore (test Q1/Q2)
  - **Cosa misura**: lo `score_norm` ricalcolato dal reveal VRF del blocco vincitore (U(0,1) se vince l'argmin), e la correlazione fra spaziatura e delay vero.
  - **Osservato**: 2 900 round, media 0,4929, KS p = 0,344. Separando i 30 round vinti in cima alla banda (1,03 %), sui 2 870 round in corsa media 0,4877, KS p = 0,141. Q1: corr(dt_prev, delay_true) = 0,939 (0,971 a δ = 0,5).
  - **Atteso**: media 0,5, KS non rigettato; ≈ 1 − 1/(n+1) = 0,83 se il vincitore fosse casuale. Q1 ≈ 1.
  - **Giudizio**: **conforme**. Q1 è più bassa che a δ = 0,5 per costruzione: la banda è larga la metà, quindi a parità di residuo (sd 0,43 s) la varianza del delay spiegata è minore.
- **File**: [analysis/phase3/wpoa_prop517.csv](analysis/phase3/wpoa_prop517.csv), [analysis/plots/prop517_gap_by_validator.png](analysis/plots/prop517_gap_by_validator.png) (forma pubblica)
  - **Cosa misura**: gap standardizzato `(score₍₂₎ − score₍₁₎)(W_tot − w_eff,i*)`, che deve essere Exp(1).
  - **Osservato**: medie 1,096 (miner-0, n = 300, KS p = 0,17), 0,943 (miner-1, n = 384, p = 0,86), 0,953 (miner-2, n = 858, p = 0,19), 1,096 (miner-3, n = 657, **p = 0,029**), 1,074 (miner-4, n = 701, p = 0,38).
  - **Atteso**: media 1, KS non significativo.
  - **Giudizio**: **lieve scostamento**: 1 rigetto su 5 test (p = 0,029, Bonferroni 0,15); gli scarti (−5,7 % … +9,6 %) sono fra 1,1 e 2,5 errori standard.
- **File**: `chains/miner-{0..4}/wpoa-core-regional-d025/debug.log` (righe `wPoA-sortition`) — VRF privata e Prop. 5.17 privata
  - `E_i` media 0,9989, `√n·D = 0,62`; argmin `score_norm` media 0,4929, `√n·D = 0,93` (§3.5.1(a)). **Conforme.**
  - Prop. 5.17 sugli score privati, per designato: medie 0,889 (miner-0, n = 302), 1,064 (miner-1, 383), 1,058 (miner-2, 858), 1,069 (miner-3, 655), 1,021 (miner-4, 702); aggregata 1,035 su 2 900 round (z = 1,87, p ≈ 0,06), KS aggregato `√n·D = 1,11` < 1,358. **Lieve scostamento**: il test congiunto non rigetta e `E_i` e `score_norm` dell'argmin, che dipendono dagli stessi score, sono puliti; nessun effetto di bordo d'epoca (media di `E_i` per posizione nell'epoca sempre entro la banda). A δ = 0,5 lo stesso test dava 0,978–1,006: va ricontrollato sulla run δ = 0,75 o su una ripetizione.

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv) (`delay_recompute_mismatch_rounds_is_zero`), [analysis/phase3/wpoa_epoch_tests.csv](analysis/phase3/wpoa_epoch_tests.csv) (`delay_recompute_mismatch_rounds`), [analysis/plots/delay_recompute_mismatch.png](analysis/plots/delay_recompute_mismatch.png)
  - **Cosa misura**: |D_i ricalcolato dalla pipeline − D_i loggato dal nodo|.
  - **Osservato**: 0 round in mismatch su 31 epoche; 0/14 505 coppie oltre la tolleranza; massimo 1,95·10⁻¹⁴ s.
  - **Atteso**: 0 con tolleranza 1,5 ms.
  - **Giudizio**: **conforme**: harness e nodo concordano sulla formula D_i = T_block + Δ_max(2·score_norm − 1) + λΦ anche con δ = 0,25.

### 3.3 Quota di blocchi contro peso

`dump-function = none`, quindi la quota attesa è `w_eff/Σw_eff`, con w_eff pari al peso pubblicato (Ψ = 1 ovunque; `weight_effective = weight_raw` in 14 505/14 505 righe).

- **File**: [analysis/phase3/weight_vs_election.md](analysis/phase3/weight_vs_election.md), [analysis/phase3/wpoa_epoch_validators.csv](analysis/phase3/wpoa_epoch_validators.csv) (riga `all`)
  - **Cosa misura**: quota osservata contro quota spettante sull'intera run.
  - **Osservato** (p_teorica / p_hat, 2 921 blocchi, Wilson 95 %): miner-0 0,1030 / 0,1027 [0,092; 0,114]; miner-1 0,1282 / 0,1339 [0,122; 0,147]; miner-2 0,3102 / 0,2958 [0,280; 0,313]; miner-3 0,2326 / 0,2253 [0,210; 0,241]; miner-4 0,2262 / 0,2424 [0,227; 0,258]. La quota spettante di miner-4 cade appena fuori dal proprio intervallo (0,2262 contro limite inferiore 0,2272).
  - **Atteso**: p_hat ≈ p_teorica.
  - **Giudizio**: **lieve scostamento**: scarto massimo +1,6 pp (miner-4, z ≈ 2,1), MAE 0,0088, TV 2,2 % (0,42 % a δ = 0,5 su un campione 3,4 volte più grande). La causa non è la timer race: i **vincitori designati** dagli score privati hanno già miner-4 al 24,21 % e miner-2 al 29,59 % contro 22,61 % e 31,06 % teorici (§3.5.1(a)), quindi lo scarto è nell'estrazione VRF ed è una fluttuazione di campione (χ² dei designati 6,24, df 4, p = 0,18). Sui soli 2 900 blocchi wPoA (escludendo i 21 di round robin dell'epoca 2) χ² = 6,03, p = 0,20.
- **File**: [analysis/phase3/weight_election_wilson_coverage.csv](analysis/phase3/weight_election_wilson_coverage.csv), [analysis/plots/wilson_violation_heatmap.png](analysis/plots/wilson_violation_heatmap.png)
  - **Cosa misura**: copertura dei 150 intervalli di Wilson al 95 % per (epoca, validatore).
  - **Osservato**: 11 violazioni (miner-4 4, miner-3 3, miner-2 2, miner-1 2, miner-0 0) in 9 epoche (2, 3, 11, 13, 17, 18, 23, 27, 29); nessun blocco contiguo. Risoluzione: larghezza media 0,154.
  - **Atteso**: 0,05 · 150 = 7,5; binomiale sul conteggio p = 0,13.
  - **Giudizio**: **conforme** (11 contro 7,5, compatibile). Una delle violazioni (epoca 2, miner-4 33/100) cade nell'epoca a cavallo di `setup-first-blocks` (altezze 200–299, 21 blocchi di round robin): sui 79 blocchi wPoA l'epoca ha χ² = 5,34, p = 0,25.
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](analysis/phase3/wpoa_epoch_tests.csv), [analysis/phase3/weight_election_pvalue_uniformity.csv](analysis/phase3/weight_election_pvalue_uniformity.csv), [analysis/plots/p_value_uniformity.png](analysis/plots/p_value_uniformity.png)
  - **Cosa misura**: GoF congiunto per epoca e uniformità dei p-value.
  - **Osservato**: 2 rigetti su 30 epoche (23: p = 0,049; 27: p = 0,034). Binomiale sul conteggio p = 0,45; KS dei p-value contro U(0,1) D = 0,116, p = 0,79. In ogni epoca `share_changes_within_epoch = True`, quindi il test da leggere è `gof_mc_round_by_round_p`: anch'esso 2/30 sotto 0,05.
  - **Atteso**: ~1,5 rigetti; p-value uniformi.
  - **Giudizio**: **conforme**.
- **File**: `wpoa_epoch_tests.csv` riga `all`
  - **Osservato**: χ² = 6,757 (df 4), p = 0,149; round-by-round p = 0,196; MAE_p 0,0088; MaxAE_p 0,0162.
  - **Giudizio**: **conforme**: nessun rigetto sul test più potente; l'effetto residuo è lo scarto di estrazione descritto sopra.
- **File**: [analysis/plots/weight_vs_election.png](analysis/plots/weight_vs_election.png)
  - **Osservato**: nello scatter le 150 coppie stanno lungo la diagonale fra 0,03 e 0,49, con dispersione verticale ≈ ±0,1 (Wilson a B = 100). miner-2 occupa la regione alta (0,2–0,48), miner-0 e miner-1 quella bassa.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase3/weight_election_residuals.csv](analysis/phase3/weight_election_residuals.csv), [analysis/plots/residual_boxplot_by_validator.png](analysis/plots/residual_boxplot_by_validator.png)
  - **Osservato**: residuo standardizzato `z_i = (O_i − B p)/√(B p(1−p))` sulle epoche 2–30: deviazione standard complessiva **1,058**; per validatore 0,99 (miner-0), 0,89 (miner-1), 1,06 (miner-2), 1,00 (miner-3), 1,25 (miner-4); medie fra −0,33 (miner-2) e +0,37 (miner-4).
  - **Atteso**: media 0, sd 1.
  - **Giudizio**: **conforme**: nessuna sovradispersione sistematica (a δ = 0,5: 1,00; nella baseline prima delle correzioni: 1,10). La sd di miner-4 (1,25 su 29 epoche) e le medie opposte di miner-2/miner-4 sono la stessa fluttuazione dell'aggregato.
- **Terzi di run**, sui designati privati: miner-4 0,266/0,251, 0,257/0,240, 0,204/0,188 (designato/teorico), miner-2 0,286/0,303, 0,271/0,277, 0,331/0,352. Lo scarto ha lo stesso segno nei tre terzi ma resta fra 0,6 e 2,1 punti, entro ~1,3 σ binomiali per terzo. **Lieve scostamento**, compatibile col caso.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](analysis/phase3/longitudinal.md), [analysis/phase3/wpoa_longitudinal_fits.csv](analysis/phase3/wpoa_longitudinal_fits.csv) — GLM logit
  - **Cosa misura**: `logit(p_i) = β₀ + β₁ log(w_eff,i)` sulle 150 celle; la pipeline assume H0: β₁ = 1.
  - **Osservato**: β₁ = 1,048, IC 95 % [0,963; 1,133], `converged = True`, marcato "consistent".
  - **Atteso**: β₁ = 1 secondo la pipeline, ma la H0 esatta non è 1 (con `p = w/W` la pendenza locale è `1/(1−p)`, e il regressore è il peso assoluto, non normalizzato per epoca). Simulazione della sortition esatta sui `p_theoretical_blockweighted` reali, stesso stimatore IRLS, 1 000 repliche: β₁ nullo medio **1,068**, intervallo 2,5–97,5 % [0,985; 1,157]; P(β₁ ≤ 1,048) = 0,35.
  - **Giudizio**: **conforme** sotto entrambe le H0. Qui il nullo simulato è più vicino a 1 che a δ = 0,5 (1,163): i pesi assoluti variano molto più fra le epoche (fattore ρ fino a ×3,3), e questa variazione, che non cambia le quote, attenua la pendenza. È un'ulteriore conferma che il GLM sul peso assoluto non ha una H0 fissa.
- **File**: `wpoa_longitudinal_fits.csv`, [analysis/phase3/wpoa_longitudinal_logratios.csv](analysis/phase3/wpoa_longitudinal_logratios.csv), [analysis/plots/longitudinal_logratio.png](analysis/plots/longitudinal_logratio.png) — log-rapporti
  - **Osservato**: 300 coppie, pendenza 0,974, intercetta −0,045, Pearson r = 0,897, Spearman 0,896.
  - **Atteso**: pendenza 1, intercetta 0.
  - **Giudizio**: **conforme** — pendenza −2,6 %, intercetta piccola (è la stessa asimmetria miner-2/miner-4 dell'aggregato); r = 0,90, più alto che a δ = 0,5 (0,86) perché i pesi sono più dispersi.
- **File**: `wpoa_longitudinal_fits.csv` (monotonicity), [analysis/plots/sign_test_by_validator.png](analysis/plots/sign_test_by_validator.png)
  - **Osservato**: concordanza peso↔quota fra epoche 0,89 (miner-1, p = 1,4·10⁻⁵), 0,82 (miner-3, p = 5·10⁻⁴), 0,68 (miner-2, p = 0,044), 0,59 (miner-0, p = 0,23), 0,55 (miner-4, p = 0,36).
  - **Atteso**: concordanza > 0,5.
  - **Giudizio**: **conforme** — tutte > 0,5, 3/5 significative con 29 coppie ciascuna.
- **File**: [analysis/phase3/wpoa_longitudinal_validators.csv](analysis/phase3/wpoa_longitudinal_validators.csv)
  - **Osservato**: prima contro ultima epoca, `intervals_overlap = True` per tutti e 5; l'ultima epoca ha 21 blocchi.
  - **Giudizio**: **conforme ma poco informativo**.

### 3.5 Timer race, margine e inversioni

- **File**: [analysis/phase3/wpoa_timer_race.csv](analysis/phase3/wpoa_timer_race.csv), [analysis/plots/margin_distribution.png](analysis/plots/margin_distribution.png) — margine G (forma pubblica)
  - **Cosa misura**: distanza fra i due delay più veloci.
  - **Osservato**: G medio 1,163 s, mediana 0,919 s; densità decrescente da 0 a 4 s = 2Δ_max. KS contro la simulazione esatta: D = 0,014, p = 0,70 (media simulata 1,142 s). KS contro Beta(1,5): p = 0 (media attesa 0,667 s).
  - **Atteso**: KS simulato non rigettato; Beta(1,n) è lo **straw man** e rigetta con pesi non uniformi.
  - **Giudizio**: **conforme**. Il margine medio è la metà di quello a δ = 0,5 (2,24 s), come vuole G ∝ Δ_max.
- **File**: [analysis/phase3/wpoa_sigma.csv](analysis/phase3/wpoa_sigma.csv), [analysis/plots/sigma_decomposition.png](analysis/plots/sigma_decomposition.png)
  - **Osservato**: S1_topology = 0,000377 s (misurata); S2_scheduler_residual_sd = 1,628 s; S2b_inversion_gap = 0,961 s.
  - **Lettura**: S2 e S2b sono calcolati sul delay **pubblico**, indipendente da quello da cui partono i timer, e misurano quindi la distanza fra due variabili indipendenti (qui minore che a δ = 0,5, 3,18 s, perché la banda è più stretta). Il residuo sul delay **vero** ha sd 0,427 s e media +0,047 s.
  - **Giudizio**: **conforme come audit**; il jitter reale è ~0,43 s.
- **File**: [analysis/plots/inversion_bound_vs_observed.png](analysis/plots/inversion_bound_vs_observed.png), `wpoa_timer_race.csv`, `wpoa_epoch_tests.csv` (`inversion_*`)
  - **Osservato**: bound di Prop. 5.18 (pubblico) = 1,0; MC con σ_S2 = 0,515; tasso "osservato" pubblico 0,772 (2 238/2 901).
  - **Giudizio**: **non informativo**, non un rilievo: il bound saturato a 1 è vacuo e il tasso pubblico vale ≈ 1 − Σp² per costruzione. Il tasso vero è in §3.5.1(b).
- **Vantaggio del miner uscente** (campo `lag` delle righe `wPoA-sortition`, ritardo con cui il nodo arma il timer rispetto al timestamp del padre):
  - **Osservato**: lag medio dell'uscente 0,593 s, degli altri 1,574 s: ~0,98 s di anticipo, stabile per terzi (0,590/1,567, 0,596/1,571, 0,593/1,582 s). Tutti i timer sono ancorati al padre (`anchor=parent` in 16 595/16 595 righe), quindi il lag non sposta l'istante di proposta finché lag < delay (delay minimo 6 s). Il designato coincide con l'uscente nel 24,31 % dei round contro il 24,16 % atteso.
  - **Giudizio**: **conforme**: l'anticipo di ricezione esiste (elaborazione locale del blocco con 35 daemon attivi sullo stesso host, non la rete a 5 ms) ma è neutralizzato dall'ancoraggio al padre.

#### 3.5.1 Vincitore designato, inversioni reali e fork (score privati)

Copertura: **score privati di 5 miner su 5**, dai `debug.log` letti tramite il container `mcsim`
(file `root` 0600); le righe wPoA sono estratte in [analysis/private/miner-*.log](analysis/private/), lo script è
[analysis/private/priv.py](analysis/private/priv.py) e l'output [analysis/private/priv_d025.json](analysis/private/priv_d025.json). 16 595
righe di scheduling, l'87,4 % riferito al padre poi rimasto sulla catena finale. Round con score di
tutti e 5 i miner sul padre finale: **2 900 su 2 900** misurati. Per il confronto, lo stesso script
è stato eseguito sui log della run δ = 0,5 ([analysis/private/priv_ref_fb.json](analysis/private/priv_ref_fb.json)):
riproduce i numeri già pubblicati di quella run (31 inversioni finali, 21,2 % di fork, 1 045 primi
arrivi invertiti).

- **(a) Sortition privata.**
  - `E_i = score_privato · w_eff,i` (w_eff da `round_final_weights.csv` all'altezza del round): n = 14 500, media 0,9989 (banda [0,9837; 1,0163]), `√n·D = 0,62`. Per miner: 0,980 / 1,009 / 0,999 / 1,032 / 0,974 (miner-0…4), tutte entro ±0,036. **Conforme**, e nessun indizio di un peso letto dal nodo diverso da quello della pipeline.
  - `score_norm` dell'argmin privato: n = 2 900, media 0,4929, `√n·D = 0,93`. **Conforme.**
  - Designato = miner del round precedente: 24,31 % contro 24,16 % atteso. **Nessuna correlazione fra round.**
  - Quote dei designati: miner-2 29,59 %, miner-4 24,21 %, miner-3 22,59 %, miner-1 13,21 %, miner-0 10,41 %, contro teoriche 31,06 / 22,61 / 23,24 / 12,80 / 10,29 %; χ² = 6,24, df 4, p = 0,18. **Lieve scostamento**, compatibile con il campione (2 900 estrazioni); è l'origine dello scarto di quota di §3.3.
- **(b) Inversioni reali** (designato privato ≠ minatore del blocco finale; `true_winner_mismatch = 0` in `round_level.csv`, fase 1 già corretta):
  - Tasso complessivo **0,21 % (6/2 900)**, Wilson [0,09; 0,45] %; per terzo 2, 1, 3 round. A δ = 0,5: 0,31 % (31/9 874); differenza non significativa (z = −0,94, p = 0,35).
  - Margine fra i due delay privati nei round invertiti: media 0,096 s, massimo 0,177 s (contro 1,19 s medi su tutti i round).
  - Miner uscente: 2/6 inversioni; nei 5 casi in cui il designato non era l'uscente, l'uscente vince 2 volte (40 % contro 25 %, p = 0,37).
  - **Giudizio**: **conforme**: il tasso finale non cresce dimezzando Δ_max. Il segnale sull'uscente di δ = 0,5 (11/22) qui non si vede, ma 5 eventi non bastano per dire nulla.
- **(c) Fork** (righe `[wpoa-fork]` e `UpdateTip`):
  - Round con più di un blocco proposto alla stessa altezza: **930 su 2 900 (32,1 %)**, Wilson [30,4; 33,8] %, fino a 5 blocchi per altezza, 1 586 blocchi orfani; per terzo 33,2 / 31,4 / 31,6 %. A δ = 0,5: 21,2 %.
  - Il blocco finale è quello di score minimo fra i contendenti in **930/930** round con fork (100 %).
  - Regola nativa contro regola per score: il primo blocco ricevuto dalla rete non è quello rimasto sulla catena in **470 round (16,2 %)**; con la regola nativa "primo ricevuto" sarebbero rimasti invertiti. Sull'ultima valutazione per nodo e altezza con almeno 2 candidati (4 707), il blocco scelto per score è quello finale nel 100 % dei casi, quello first-seen nel 63,0 %; nelle 1 743 valutazioni in cui le due regole divergono (765 altezze), la regola per score ha preso il blocco finale nel 100 %, quella nativa mai.
  - 2 986 `displace` su 934 altezze, tutti verso score migliore; **666 `defer`** (23,0 % dei round, contro 11,0 % a δ = 0,5), **0 `defer-release`**; 238 `retarget-abort`.
  - Riorganizzazioni (da `UpdateTip`): tutte di profondità 1 (665, 672, 536, 553, 560 per miner-0…4), nessuna più profonda dopo il setup. Tempo su un tip poi orfano: mediana ≈ 0 s, p95 0,57 s, massimo 1,23 s (tempi di log a risoluzione di 1 s).
  - **Giudizio**: **conforme**: le fork crescono come previsto (banda più stretta ⇒ più timer che scadono prima che il blocco dell'argmin si propaghi), e il tie-break le chiude tutte a favore dell'argmin.
- **(d) Prop. 5.18 sui delay reali.** Tempo di proposta = delay privato + N(0, σ²), con o senza un vantaggio `a` sottratto all'uscente; 20 repliche sui 2 900 round.
  - Bersaglio: tasso di inversione **al primo arrivo**, 472/2 900 = **16,3 %** (Wilson [15,0; 17,7] %); per terzo 16,9 / 15,1 / 16,8 %, nessuna crescita. A δ = 0,5: 10,6 % (1 045/9 874); rapporto 1,54.
  - Modello simmetrico: σ = 0,30 s → 15,5 %, σ = 0,35 s → 17,5 %, quindi σ ≈ 0,32 s. Quota dell'uscente fra i primi arrivi invertiti: simulata 21,3 % (27,7 % se il designato non era l'uscente), osservata **20,6 % (26,7 %, 97/363)**.
  - Modello con vantaggio (σ = 0,35, a = 0,1 s): uscente 28,8 % (35,4 %); con a = 0,3 s 45,7 % (51,5 %): **peggiori** dell'osservato.
  - Stesso σ, due bande: con σ = 0,35 s la simulazione sui delay reali dà 17,5 % a Δ_max = 2 s e 10,6 % a Δ_max = 4 s (rapporto 1,66). La legge lineare del primo ordine prevederebbe 2: la differenza viene dai termini di ordine superiore (mσ/Δ_max = 0,875 non è piccolo) e dalla forma della distribuzione dei margini.
  - Bound (m = 5, Δ_max = 2 s, σ = 0,35 s): maggiorazione di Chebyshev 1,37 (**vacua**), primi due termini 0,386, primo termine 0,309, gaussiano completo 0,340, MC con score uniformi 0,206. Tutti sopra il 16,3 % osservato. Sui margini veri `Pr[G < t]` resta sotto `m t/(2Δ_max)` per ogni soglia (t = 0,1/0,25/0,5/1 s: 0,099/0,204/0,329/0,525 contro 0,125/0,31/0,63/1,25).
  - **Confronto a parità di finestra.** Ristretta alle stesse altezze 221–3 120 ([private/priv_win.py](analysis/private/priv_win.py), output [private/priv_ref_fb_h221-3120.json](analysis/private/priv_ref_fb_h221-3120.json); 2 898 round valutabili), la run δ = 0,5 dà: margine medio 2,27 s, fork 21,5 %, inversioni al primo arrivo 11,2 % (σ ≈ 0,34 s), blocchi trattenuti 12,1 %, fork chiuse sull'argmin 622/623, inversioni finali 1 (0,03 %), block time 8,06 s (sd 2,44). Rapporto delle inversioni istantanee d025/fb 1,45 contro 1,54 simulato con σ = 0,35 s; inversioni finali 6 contro 1 (Fisher p = 0,12, non significativo). È la versione usata nella Tabella tab:exp-banda del capitolo 8.
  - **Giudizio**: **conforme**: il modello simmetrico con lo stesso σ della run δ = 0,5 spiega sia il tasso sia la composizione, e il bound resta un maggiorante valido (fattore 2,1 per la forma gaussiana, contro 1,4 a δ = 0,5).

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/phase2/round_level.csv](analysis/phase2/round_level.csv) (`dt_prev_s`)
  - **Cosa misura**: spaziatura realizzata fra blocchi.
  - **Osservato**: 2 900 round, media **8,014 s**, sd 1,242, mediana 8, min 6, max 11 s. Media per epoca in [7,77; 8,23] s; per terzi 8,004 / 8,017 / 8,022 s. I primi dieci blocchi di ogni epoca non sono più lenti degli altri (7,90 contro 8,03 s).
  - **Atteso**: media → T_block = 8 s.
  - **Giudizio**: **conforme** — +0,18 % sopra il target, nessuna deriva. La sd è la metà di quella a δ = 0,5 (2,41 s): la varianza del block time scala con la banda.
- **File**: `round_level.csv` (`delay_true_s`, `residual_true_s`)
  - **Osservato**: delay vero del vincitore medio 7,968 s. Residuo spaziatura − delay vero: media +0,047 s, sd 0,427 s; per terzo 0,427 / 0,410 / 0,443 s.
  - **Giudizio**: **conforme**: nessuna crescita del rumore dello scheduler (a δ = 0,5 cresceva a 0,78 s nell'ultimo terzo di una run di 23 h; questa dura 6,7 h e i `debug.log` dei miner restano sotto i 105 MB).
- **File**: [analysis/plots/phi_over_time.png](analysis/plots/phi_over_time.png), `round_level.csv` (`phi_s`)
  - **Osservato**: 26 valori distinti (multipli di 1/12 s), media −0,012 s, sd 0,328, range [−1,17; +0,92] s; |Φ| < 0,5 s nell'83 % dei round, |Φ| > 1 s in 3 round. **0 round saturati** a ±M = ±4 s. Cambio di segno fra round consecutivi nel 6,4 % dei casi, autocorrelazione lag-1 0,897. La mediana mobile resta in [−0,08; +0,17] s.
  - **Atteso**: Φ piccolo e non saturato.
  - **Giudizio**: **conforme**: nessuna saturazione né oscillazione.
- **File**: `consistency_checks.csv` (`phi_consistent`)
  - **Osservato**: FAIL, "26 distinct Phi values", non critico.
  - **Giudizio**: **atteso, non è un difetto**: il check è tarato su run con feedback spento.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv), [analysis/phase3/weight_engine_epoch.csv](analysis/phase3/weight_engine_epoch.csv) — identità
  - **Osservato**: `W_k_raw = ESG·(τ_miner + Σc_i)` con errore relativo massimo 0; `w_k_final = W_k_raw·(ρ_prev·λ_w + 1 − λ_w)` con errore 9,9·10⁻¹⁵; `w_k_published` = 100 · `w_k_final` arrotondato.
  - **Giudizio**: **conforme**, esatto.
- **File**: `epoch_engine.csv`, [analysis/phase1/esg_events.csv](analysis/phase1/esg_events.csv), [analysis/plots/esg_scores.png](analysis/plots/esg_scores.png) — ESG statici
  - **Osservato**: 35 certificazioni, una per soggetto; `miner_esg_score` ha un solo valore per miner in tutte le 31 epoche (29, 56, 75, 55, 49 per miner-0…4).
  - **Giudizio**: **conforme**.
- **ρ non nullo** (§1.5): ρ medio 0,0087, sd 0,0054, max 0,0228, nullo nel 3,3 % delle celle. È circa 3,5 volte quello della run δ = 0,5 (0,0025) perché il seed GAS per miner è 180 200 invece di 600 200. Con λ_w = 0,99 il fattore `0,99ρ + 0,01` va da 0,010 a 0,033: la retroazione sposta il peso fino a **×3,3** fra miner.
- **File**: [analysis/phase3/weight_engine_correlations.csv](analysis/phase3/weight_engine_correlations.csv), [analysis/plots/rho_vs_next_weight.png](analysis/plots/rho_vs_next_weight.png), [analysis/plots/rho_feedback_by_validator.png](analysis/plots/rho_feedback_by_validator.png)
  - **Osservato**: Spearman lag-1 ρ(e) → w(e+1): miner-0 0,944, miner-3 0,942, miner-1 0,922, miner-4 0,919, miner-2 0,871 (tutti p < 10⁻⁴, n = 30); aggregato 0,573 (n = 150). Nello scatter il peso a e+1 cresce con ρ(e) da ~4 k (ρ = 0) a ~20–32 k (ρ ≈ 0,015), in bande diverse per cluster.
  - **Atteso**: correlazione positiva se ρ ha varianza.
  - **Giudizio**: **conforme**: il canale endogeno è attivo, più forte che a δ = 0,5 (0,61–0,81).
- **File**: [analysis/plots/weights_over_time.png](analysis/plots/weights_over_time.png), [analysis/plots/weights_boxplot_per_epoch.png](analysis/plots/weights_boxplot_per_epoch.png)
  - **Osservato**: i tre pannelli (grezzo, dopo malus, finale) sono identici, come deve essere con Ψ = 1 e `none`. Salto fra epoca 1 (10–28 k) ed epoca 2 (3,5–8 k), poi pesi rumorosi fra 3,5 k e 32 k; miner-2 in testa in 20 epoche su 30. Spearman epoca → peso fra −0,22 e +0,36: nessun trend netto.
  - **Giudizio**: **conforme**: pesi stazionari e rumorosi, come atteso con τ e restituzioni i.i.d. per epoca.
- **File**: [analysis/phase3/weight_engine_gini.csv](analysis/phase3/weight_engine_gini.csv), [analysis/phase3/weight_engine_gini_summary.csv](analysis/phase3/weight_engine_gini_summary.csv), [analysis/plots/gini_delta_trajectory.png](analysis/plots/gini_delta_trajectory.png)
  - **Osservato**: Gini(pubblicato) − Gini(input) in [−0,13; +0,11], media +0,032; pendenza 3,8·10⁻⁴ per epoca, Spearman 0,013 (p = 0,95).
  - **Atteso**: pendenza ≈ 0.
  - **Giudizio**: **conforme**: nessuna amplificazione nel tempo; lo scarto medio positivo è l'effetto moltiplicativo di ρ, maggiore che a δ = 0,5 (+0,009) perché ρ è più grande.

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](analysis/phase2/epoch_concentration.csv), `wpoa_epoch_tests.csv`, sezione 3 di [analysis/phase3/report.md](analysis/phase3/report.md), [analysis/plots/concentration_over_time.png](analysis/plots/concentration_over_time.png)
  - **Osservato**: aggregato HHI teorico 0,2285 contro osservato 0,2255 (N_eff 4,44); Gini osservato 0,198. Per epoca, HHI osservato − teorico ha media +0,0074 ed è positivo in 18/30 epoche. Nakamoto 1/2: 2 in 27/30 epoche teoriche e 28/30 osservate (3 negli altri).
  - **Atteso**: con B = 100 l'HHI osservato per epoca è gonfiato di circa (1 − HHI)/B ≈ +0,0076; l'aggregato deve coincidere.
  - **Giudizio**: **conforme**: l'eccesso per epoca è la varianza multinomiale attesa e l'aggregato osservato è persino sotto il teorico.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](analysis/phase3/streak.md), `wpoa_epoch_tests.csv` (`L_max_*`, `repeat_prob_*`)
  - **Osservato**: L_max con p < 0,05 in 1/30 epoche (11: 7 contro 4,36, p = 0,048); ripetizione con p < 0,05 in 0/30. Aggregato: L_max 7 contro 7,66 (p = 0,80); probabilità di ripetizione **0,2435 contro 0,2431** (p = 0,49). Dai log privati il designato ripete il miner precedente nel 24,3 % dei round contro il 24,2 % atteso.
  - **Atteso**: ~1,5 rigetti per famiglia; nessun eccesso sistematico.
  - **Giudizio**: **conforme**: round indipendenti, coerente col tasso di inversione finale dello 0,2 %.

### 3.10 Malus

Caso **J.1**: meccanismo attivo, nessuna violazione iniettata.

- **File**: [analysis/phase1/malus_detections.csv](analysis/phase1/malus_detections.csv), `phase1/malicious_{actions,opportunities,confirmations}.csv`, [analysis/phase2/malus_actions.csv](analysis/phase2/malus_actions.csv), `phase2/malus_detection_events.csv`, [analysis/phase3/malus_rate.csv](analysis/phase3/malus_rate.csv)
  - **Osservato**: 0 righe di dati in tutti; `malus_funnel`, `malus_detection` e `malus_latency` hanno solo le righe di riepilogo a zero.
  - **Giudizio**: **conforme** — vuoti come atteso.
- **File**: [analysis/phase2/malus_state.csv](analysis/phase2/malus_state.csv), [analysis/phase3/malus_invariants.csv](analysis/phase3/malus_invariants.csv), [analysis/plots/malus_invariant_audit.png](analysis/plots/malus_invariant_audit.png)
  - **Osservato**: 155 celle (31 epoche × 5): M massimo 0, Ψ minimo 1; i tre invarianti veri in 155/155. Check critico `malus_finite_and_psi_in_unit_interval`: 119 235 campioni, PASS.
  - **Giudizio**: **conforme**: effetto del malus sul comportamento onesto **esattamente nullo** (w_eff = w in 14 505/14 505 righe).
- **File**: [analysis/plots/malus_action_funnel.png](analysis/plots/malus_action_funnel.png), [analysis/plots/malus_state_trajectory.png](analysis/plots/malus_state_trajectory.png), [analysis/plots/malus_detection_latency.png](analysis/plots/malus_detection_latency.png) — figure degeneri, come atteso.
- **File**: [analysis/phase3/malus_weight_effect.csv](analysis/phase3/malus_weight_effect.csv), [analysis/phase3/malus_weight_effect_matched.csv](analysis/phase3/malus_weight_effect_matched.csv), [analysis/plots/malus_weight_effect.png](analysis/plots/malus_weight_effect.png)
  - **Osservato**: variazione relativa del peso efficace per gli onesti fra −19 % e −58 %.
  - **Giudizio**: **conforme, non attribuibile al malus** (Ψ = 1 ovunque): è il confronto fra la convenzione dell'epoca 1 (w = W) e l'ultima epoca (fattore 0,01 + 0,99ρ).
- `analysis/phase3/malus_effectiveness.md` **non è presente**: l'esperimento malicious non è stato eseguito in questa run.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: `epoch_engine.csv` (punto K.1, epoche 2–31, n = 150)
  - **Osservato**: Spearman di `n_blocks_won_epoch` con `w_k_published` 0,814, `W_k_raw` 0,684, `earnings_g_k` 0,515, `companies_contribution_sum` 0,470, `income` 0,072, `miner_activity` 0,062.
  - **Giudizio**: **conforme**: la correlazione è massima col peso che l'elezione usa.
- **File**: [analysis/phase3/weight_election_residuals.csv](analysis/phase3/weight_election_residuals.csv) × `epoch_engine.csv` (punto K.2, n = 150)
  - **Osservato**: Spearman del residuo `p_hat − p_theoretical` con `earnings_g_k` −0,089 (p = 0,27), `income` −0,066 (p = 0,42), `miner_activity` −0,041 (p = 0,61), `companies_contribution_sum` −0,025 (p = 0,76), `R_k` −0,001 (p = 0,99), ρ −0,001 (p = 0,99), `W_k_raw` −0,087 (p = 0,29), `w_k_published` −0,055 (p = 0,50).
  - **Giudizio**: **conforme**: a peso fissato guadagno e volume non spiegano nulla; nessun canale di influenza non documentato.

### 3.12 Integrità della run e controlli di consistenza

- **File**: [analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv)

  | check | critico | esito |
  |---|---|---|
  | `registry_weights_finite_and_positive` | sì | PASS (119 235 campioni) |
  | `no_phantom_validator_in_registry` | sì | PASS |
  | `malus_finite_and_psi_in_unit_interval` | sì | PASS |
  | `delay_recompute_mismatch_rounds_is_zero` | sì | PASS |
  | `every_esg_publication_reached_the_stream` | sì | PASS (35/35) |
  | `only_miners_pay_the_treasury` | sì | PASS (1 563 pagamenti) |
  | `at_least_one_fully_measured_epoch` | sì | PASS (30 epoche) |
  | `phi_consistent` | no | FAIL, atteso (§3.6) |
  | `certified_scores_reflected_in_the_engine` | no | **FAIL**: 3 indirizzi certificati senza ESG in alcuna epoca (sotto) |
  | `traffic_counts_within_configured_range` | no | PASS (927/927 coppie) |

  **Giudizio**: **conforme**: 7/7 critici superati.
- **Aziende morte al bootstrap.** I tre indirizzi del check fallito sono company-16 e company-26 (cluster di miner-1) e company-29 (cluster di miner-4). Nei rispettivi [logs/company-*/stdout.log](logs/) compare `did not serve RPC within 120s ... Connection refused`; l'admin ha 34 connessioni invece di 37; `epoch_engine.csv` riporta 4 aziende per miner-1 e 5 per miner-4 in tutte le epoche; 3 dei 411 errori RPC sono le `weightregistermembership` fallite. **Lieve scostamento dal profilo, non dal protocollo**: il motore ha pesato correttamente i cluster con le aziende effettivamente attive, e le quote spettanti sono calcolate sui pesi pubblicati. È la terza run consecutiva con aziende cadute al bootstrap (dopo `regional-whale-none` e `regional-whale-sqrt`): l'orchestratore non ha un controllo di liveness fra l'avvio dei nodi e la registrazione delle appartenenze.
- **File**: [analysis/phase1/verification.csv](analysis/phase1/verification.csv)
  - **Osservato**: 115 verifiche (epoche 1–30), `verdict = ok` in tutte.
  - **Giudizio**: **conforme**, nessun BadWeight.
- **File**: [analysis/phase2/epoch_traffic.csv](analysis/phase2/epoch_traffic.csv), [analysis/plots/traffic_per_epoch.png](analysis/plots/traffic_per_epoch.png), [analysis/phase1/stream_items.csv](analysis/phase1/stream_items.csv)
  - **Osservato**: 927 coppie (epoca, nodo) complete, tutte nel range; pianificate = inviate = on chain in ogni epoca (1 100–1 310 tx/epoca, l'ultima parziale). `stream_items.csv` ha 36 667 record, lontano dal tetto di 100 000 della raccolta.
  - **Giudizio**: **conforme**.
- **File**: [analysis/phase1/rpc_errors.csv](analysis/phase1/rpc_errors.csv)
  - **Osservato**: 411 errori: 408 `-1` sui 4 metodi `wpoalist*` (102 ciascuno) durante il bootstrap, più le 3 registrazioni di appartenenza delle aziende morte.
  - **Giudizio**: **conforme**, errori benigni di avvio (i 3 restanti sono il sintomo del punto precedente).
- **Blocco orfano in `blocks.csv`**: `true_winner_mismatch = 0` su 2 900 round; `verdict_true = ok` in 2 900. **Conforme.**
- **Epoca a cavallo del setup (2)**: comprende le altezze 200–220 in round robin; non rigetta il GoF (p = 0,20), e sui soli 79 blocchi wPoA χ² = 5,34 (p = 0,25).
- **Ultima epoca (31)**: 21 blocchi, GoF p = 0,80. Esclusa dalle conclusioni di tendenza.
- **Esito**: `status = ok`, altezza target raggiunta (3 120); lo `shutdown.json` non riporta errori.

## 4. Punti di forza

- **VRF privata corretta**: `E_i` medio 0,9989 su 14 500 campioni (`√n·D = 0,62`), argmin `score_norm` medio 0,493 (`√n·D = 0,93`), score vero del vincitore 0,488 sui round in corsa (KS p = 0,14).
- **Delay ricalcolato identico** al loggato su 14 505 coppie (errore ≤ 2·10⁻¹⁴ s).
- **Proporzionalità al peso**: χ² aggregato p = 0,149; GoF 2/30 (1,5 attese); Wilson 11/150 (7,5 attese, p = 0,13); p-value uniformi (KS p = 0,79); log-rapporti con pendenza 0,974; residuo standardizzato con sd 1,06.
- **Legge di scala della timer race verificata**: dimezzando Δ_max il margine medio si dimezza (2,24 → 1,19 s), le inversioni istantanee passano dal 10,6 al 16,3 % e le fork dal 21,2 al 32,1 %, riprodotti da uno stesso rumore simmetrico (σ ≈ 0,32–0,35 s).
- **Tie-break per score robusto a una banda stretta**: sceglie l'argmin in 930/930 fork; inversioni finali 0,21 % (0,31 % a δ = 0,5); riorganizzazioni solo di profondità 1; nessun `defer-release`.
- **Block time sul target** (8,014 s, sd 1,24 s) senza deriva, Φ mai saturato (|Φ| ≤ 1,17 s < 4 s).
- **Weight engine esatto e con retroazione viva**: identità ≤ 10⁻¹⁴, ESG statici, Spearman ρ → w(e+1) 0,87–0,94 per cluster, nessuna amplificazione di Gini (p = 0,95).
- **Nessun canale occulto** (|Spearman| ≤ 0,09 sui residui) e **malus a effetto nullo** (155/155 celle, 115/115 pesi verificati).

## 5. Punti critici / da approfondire

- **Scarto di quota miner-4/miner-2 (+1,6 / −1,5 pp).**
  - *Entità*: TV 2,2 %, quota spettante di miner-4 appena fuori dal suo Wilson aggregato; χ² aggregato p = 0,15.
  - *Causa*: già presente nei vincitori designati dagli score privati (χ² = 6,24, p = 0,18), stesso segno in tutti e tre i terzi ma entro ~1,3 σ per terzo; `E_i` per miner entro la banda, quindi nessun peso sbagliato letto dal nodo. È una fluttuazione di estrazione su 2 900 round.
  - *Serve*: la run δ = 0,75 (stesso seed) o una ripetizione con seed diverso; se lo stesso segno ricomparisse con p piccolo, controllare la derivazione di `u_i` dalla VRF per miner-4.
- **Gap standardizzato di Prop. 5.17 sugli score privati sopra 1.**
  - *Entità*: media 1,035 su 2 900 round (z = 1,87, p ≈ 0,06); per designato fra 0,89 e 1,07; KS aggregato non rigettato (`√n·D = 1,11`). A δ = 0,5 era 0,98–1,01.
  - *Causa*: probabilmente campionaria; la banda del delay non entra nella statistica, che dipende solo dai due score minimi e dai pesi.
  - *Serve*: ripetere il test sulla run δ = 0,75 e su una run con seed diverso.
- **Aziende morte al bootstrap (harness).**
  - *Entità*: 3 aziende su 30, nei cluster di miner-1 e miner-4, per tutta la run.
  - *Causa*: daemon non avviati entro 120 s, senza controllo di liveness nell'orchestratore; terza run consecutiva con lo stesso difetto.
  - *Serve*: un controllo di liveness fra l'avvio dei nodi e `register_membership`, con riavvio o interruzione della run.
- **Figure di audit pubbliche da non leggere come esiti**: `inversion_bound_vs_observed.png` (bound 1,0 vacuo, tasso pubblico 0,77 per costruzione), `sigma_decomposition.png` (S2 = 1,63 s dalla forma pubblica), `malus_weight_effect.png` (−19…−58 % dovuto alla convenzione di epoca 1).

## 6. Conclusione

Il meccanismo wPoA in questa run (5 miner, regime `core` regionale, `none`, λ_w = 0,99, δ = 0,25, 30 epoche) è **in buona salute** su tutti e cinque gli assi, e la banda dimezzata produce esattamente gli effetti che la teoria prevede: più fork e più inversioni istantanee, nessun aumento delle inversioni finali.

| Asse | Giudizio | Evidenza |
|---|---|---|
| Affidabilità della sortition | **conforme** (lieve scostamento di campione) | χ² aggregato p = 0,149, TV 2,2 %; Wilson 11/150 contro 7,5; GoF 2/30 contro 1,5; log-rapporti 0,974; GLM β₁ = 1,048 contro nullo simulato 1,068 [0,99; 1,16]. Inversioni reali 0,21 %. Lo scarto miner-4/miner-2 è già nei designati. |
| Qualità della randomness (VRF) | **conforme** | `E_i` privato 0,9989, `√n·D = 0,62`; argmin `score_norm` 0,493, `√n·D = 0,93`; Prop. 5.17 aggregata 1,035 (KS non rigettato). |
| Efficacia dello smorzamento | **non applicabile** (`dump-function = none`) | Pesi grezzo = finale in ogni epoca; la quota segue linearmente il peso. |
| Efficacia del malus | **conforme, effetto esattamente nullo** | M = 0, Ψ = 1, invarianti veri su 155/155 celle; 115/115 pesi verificati. |
| Stabilità del block time | **conforme** | Media 8,014 s contro 8 s, sd 1,24 s, nessuna deriva; Φ mai saturato (max 1,17 s < 4 s). |

Rispetto a δ = 0,5, dimezzare Δ_max dimezza la varianza del block time e il margine della timer race,
alza le inversioni istantanee di un fattore 1,54 (16,3 % contro 10,6 %) e le fork di un fattore 1,5,
lasciando invariato il tasso finale grazie al tie-break per score. Il vincolo di dimensionamento della
Prop. 5.18 vale quindi per le inversioni *istantanee*; sul tasso finale, con il tie-break attivo,
Δ_max = 2 s è sufficiente su questa mappa.
