# Analisi della run run-wpoa-core-intercontinental-20260922T195913Z

Run: `test/results/run-wpoa-core-intercontinental-20260922T195913Z`
Timestamp UTC della run: 2026-09-22T19:59:13Z
Catena: `wpoa-core-intercontinental` — profilo: `test/config/profiles/core/intercontinental-long28h.yaml` — regime: core
Analisi prodotta il: 2026-09-24

> Premessa. Il sistema è **intrinsecamente stocastico** su più livelli indipendenti: score ESG
> estratti a caso in `[1,100]`, traffico per azienda e restituzioni per miner estratti a ogni
> epoca, score VRF a ogni round, e in regime `core` delay/jitter della rete emulata. Nessun
> giudizio qui è dato su singoli blocchi o round: solo su aggregati, con bande di confidenza e
> correzione per confronti multipli (attesa `0,05·N` rigetti su `N` test).
>
> Oltre ai file di `analysis/`, per due punti decisivi (§3.5 e §3.6) sono stati letti i
> `debug.log` dei nodi (`chains/<nodo>/wpoa-core-intercontinental/debug.log`): le righe
> `mchn-miner: wPoA-sortition` (attive perché `runtime.sortition_miner_log = True`) danno lo
> score **vero** di ogni miner per ogni round, e le righe `UpdateTip` / `[StreamWeightRegistry]`
> danno i tempi di elaborazione. Le colonne `_public` della pipeline non possono misurare
> l'inversione (vedi §3.5).
>
> **Nota di revisione (2026-09-24).** La ricostruzione di §3.5.1 ha mostrato un problema nei
> dati della pipeline. In 756 altezze post-setup (11,7 %), `phase1/blocks.csv`, e quindi
> `phase2/round_level.csv`, registra il **primo blocco visto**, poi rimpiazzato da una fork,
> invece del blocco della catena finale. La catena finale corretta è in
> `phase1/block_sortition.csv`. I test di quota della pipeline (Wilson, GoF, streak,
> longitudinale) sono stati quindi ricalcolati sulla catena finale in §3.3, §3.4 e §3.9. Anche le
> cifre sull'inversione vera sono state rifatte sulla catena finale e sostituiscono quelle della
> prima versione (in quella versione erano 25,9 % e 14,1 % → 47,7 %).

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-intercontinental` | `manifest.json` → `chain_name`; `analysis/phase1/config.csv` |
| seed | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/intercontinental-long28h.yaml` | `manifest.json` → `profile_path` |
| regime | `core` (rete emulata) | `manifest.json` → `fabric.backend` |
| topologia | `intercontinental`: 20 siti, 7 hub, 34 link | `manifest.json` → `fabric.topology.*` |
| latenza peggiore sulla mappa | 181,5 ms (round trip 0,363 s) | `manifest.json` → `derived.worst_path_delay_ms` |
| siti dei miner | miner-0 Milano, miner-1 Francoforte, miner-2 New York, miner-3 Singapore, miner-4 San Paolo; percorsi fra miner 4,1–112,4 ms | `analysis/phase1/topology_paths.csv` |
| nodi per ruolo | 1 admin, 2 CA, 5 miner, 20 aziende (28 totali) | `manifest.json` → `nodes.*` |
| cluster | 4 aziende per miner (company-k → miner-(k mod 5)) | `clusters.json` |
| epoche | 100 pianificate × 100 blocchi | `manifest.json` → `epochs.*` |
| altezza obiettivo / raggiunta | 10120 / **6660** | `manifest.json` → `derived.target_height`, `final_height` |
| esito | **`interrupted` — "interrupted by the operator"** (file `STOP` presente) | `manifest.json` → `status`, `error` |
| epoche misurate | 65 (2–66); epoca 1 esclusa (setup); epoca 66 parziale (60 blocchi) | `analysis/phase3/report.md`; `phase3/wpoa_epoch_tests.csv` |
| **funzione di smorzamento** | `sqrt` | `config.csv` → `dump-function` |
| `target-block-time` `T_block` | 10 s | `config.csv` |
| banda `delta` | 0,5 ⇒ `Delta_max = 5 s` | `config.csv` → `wpoa-sortition-delta` |
| guadagno correzione globale `lambda` | 0,3 | `config.csv` → `wpoa-sortition-lambda` |
| bound `M` del feedback | `min(0,5·10 ; 10·0,5/0,3) = min(5 ; 16,7) = 5 s` | ricavato |
| banda effettiva del delay | `(5 + 0,3·Phi ; 15 + 0,3·Phi)` s, cioè da (3,5 ; 13,5) a (5,3 ; 15,3) | ricavato |
| parametri malus | `mu = 0,5`, `M_max = 4`, equiv 4, badweight 2, selfwrite 1, delay 0,25 | `config.csv` |
| stato malus | meccanismo attivo (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`, 0 miner malicious) | `config.csv`; `malicious_manifest.json` |
| weight engine | `weight-kappa = 100`, `weight-lambda` (`lambda_w`) = 0,5, `weight-alpha = 0,2` (**inerte**) | `config.csv` |
| `setup-first-blocks` | 207 (richiesto 207, floor di protocollo 109) | `config.csv`; `manifest.json` → `derived.*` |
| `mining-diversity` | 0,0 (non vincolante) | `config.csv` |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | `config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 1·10^14 (premine dell'admin) | `config.csv` |
| traffico | aziende 30–60 tx/epoca; miner 0–7 restituzioni/epoca, importo 1–100; ESG in `[1,100]`; stream `supply-chain-events` | `manifest.json` → `traffic.*` |
| lookback RANDAO | 101 | `config.csv` |
| fork choice | `runtime.fork_score = True` (tie-break a score attivo) | `manifest.json` → `runtime` |
| piano malicious | `enabled = false`, `miner_count = 0`, `target_action_rate = 0`, azioni selfwrite/badweight 0,5/0,5 non usate | `malicious_manifest.json` |

**Pesi effettivi alla prima epoca misurata.** Non sono una configurazione: sono un **esito
stocastico** della pipeline `ESG × tau` con il seed della run.

| Validatore | ESG miner | `W_k_raw` ep. 1 (parziale) | `w_k_published` ep. 1 | `w_k_published` ep. 2 | `w_eff = sqrt` ep. 2 | `p_theoretical` ep. 2 |
|---|---:|---:|---:|---:|---:|---:|
| miner-0 (1DGxG7N5LTyW…) | 29 | 95,99 | 9 599 | 137 997 | 371 | 0,151 |
| miner-1 (1NhmufUWxrfs…) | 56 | 129,36 | 12 936 | 155 484 | 394 | 0,162 |
| miner-2 (1NJxjU3vKSMJ…) | 75 | 246,00 | 24 600 | 313 575 | 559 | 0,229 |
| miner-3 (1UhH3MJqKnc3…) | 55 | 183,70 | 18 370 | 300 658 | 548 | 0,222 |
| miner-4 (1S526n9WV1u7…) | 49 | 208,74 | 20 874 | 339 742 | 582 | 0,236 |

Fonti: `analysis/phase1/esg_events.csv`, `analysis/phase2/epoch_engine.csv`,
`analysis/phase3/weight_vs_election.md`. Il peso pubblicato è `100 × w_k_final` (rapporto
medio 100,0000, min 99,9997, max 100,0004: arrotondamento a intero). Rapporto max/min dei pesi
grezzi per round: 2,77 in media, compresso a 1,66 dallo smorzamento `sqrt`. Non c'è balena.

## 2. Executive summary

- **La randomness è pulita.** Sul punteggio pubblico `E_i` ha media 0,9849 (n = 32 220) e
  `sqrt(n)·D = 1,14` contro un critico di 1,36; il minimo di `score_norm` per round ha media
  0,4978 e `sqrt(n)·D = 0,74`. Sul punteggio **vero** (log dei miner), l'argmin coincide col
  vincitore del round precedente nel 20,97 % dei round, contro circa il 20,7 % atteso: la
  sortition non ha memoria. `E_i` privato ha media 1,0005 (`√n·D = 0,51`).
- **Il meccanismo del delay è corretto.** 0 disaccordi su 32 725 coppie (round, candidato), con
  scarto massimo 1·10⁻¹³ s. Prop. 5.17 torna con media 0,95–1,02 per ogni vincitore, e il KS non
  rigetta per nessuno (p ≥ 0,36).
- **La run ha però un difetto di liveness grave e progressivo, che la invalida nella seconda
  metà.** Il block time medio è 18,36 s contro 10 s di target. Parte da 11,05 s (epoca 2), resta
  sotto 12,5 s fino all'epoca 32, poi sale fino a 60,7 s (epoca 66): Spearman epoca→block time
  0,985, p ≈ 1·10⁻⁴⁹. `Phi` è saturato a −5 s nell'88 % dei round sopra l'altezza 5000. La causa
  è lentezza locale dei nodi e non la rete: a fine run i miner integrano nel proprio tip **i
  loro stessi blocchi** con 14–38 s di ritardo (mediana). La fase che termina con la lettura
  del registro dei pesi (`ReadAllRecords`) passa da ≈0 s a 2,5 s in media, con picchi di 7–9 s.
- **La pipeline conta anche blocchi orfani.** In 756 altezze post-setup (11,7 %) `blocks.csv`
  e `round_level.csv` registrano un blocco poi scartato da una fork. Sui dati della pipeline le
  quote rigettano nettamente: GoF aggregato p = 3,5·10⁻⁵, pendenza dei log-rapporti 0,81, 31
  violazioni di Wilson. **Sulla catena finale** (`block_sortition.csv`) l'aderenza aggregata è
  buona: χ² = 8,82, p = 0,066, MAE 0,63 pp, pendenza 1,09. Restano un eccesso di rigetti per
  epoca, 9/65 contro 3,25 (p = 0,005), e 28/325 violazioni di Wilson contro 16,25 (p = 0,004).
- **Resta l'inversione della timer race, che non è un difetto della sortition.** Sulla catena
  finale il designato (argmin privato) vince l'80,8 % dei round; le inversioni sono il 19,2 % e
  salgono dall'8,9 % (epoche 2–22) al 15,9 % e al 36,4 %. Il 67,5 % va al miner del blocco
  precedente (l'incumbent), il che spiega la probabilità di ripetizione di 0,340 contro 0,208.
  Le fork sono il 38 % dei round e vengono tutte risolte a profondità 1. Il tie-break per score
  sceglie l'argmin in 2 272 fork su 2 273 e dimezza le inversioni (il valore stimato con la
  regola nativa è 36,6 %).
- **Lo smorzamento `sqrt` funziona come previsto.** La quota spettante di miner-2 scende da 0,290
  (`none`) a 0,245 (`sqrt`) e quella di miner-0 sale da 0,111 a 0,151. L'ordinamento è
  preservato: miner-2 > miner-4 > miner-3 > miner-1 > miner-0 sia nelle quote teoriche sia in
  quelle osservate.
- **Malus: effetto esattamente nullo, come atteso senza violazioni.** `M = 0` e `Psi = 1` su
  330/330 celle (epoca, validatore), i tre invarianti valgono ovunque, e 300/300 verifiche
  `weightverifyweights` danno `ok`.
- **La retroazione inter-epoca è di fatto inerte.** `rho` resta ≤ 0,0070 (media 0,0021) perché
  il saldo è dominato dal seed di 84 200 GAS per miner, quindi il fattore `0,5·rho + 0,5` sta in
  [0,500; 0,504]. La Spearman lag-1 vale 0,078 (p = 0,16).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

**A.1 — `E_i ~ Exp(1)`**
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (ricalcolo:
  `E = score_public × weight_effective`, righe `in_setup = False`)
- **Cosa misura**: la variabile esponenziale grezza, prima della divisione per il peso.
- **Osservato**: n = 32 220 (6444 round × 5 candidati); media 0,98490. KS contro `1 − e^(−x)`:
  D = 0,00638, `sqrt(n)·D = 1,145`.
- **Atteso**: media nella banda `1 ± 1,96/sqrt(n) = 1 ± 0,0109`; `sqrt(n)·D ≤ 1,358`.
- **Giudizio**: **lieve scostamento**. La media è 1,5 % sotto 1, cioè 1,38 bande di Monte Carlo
  sotto (appena fuori dalla banda a 1,96/√n, che vale 1,09 %). Il KS invece non rigetta (1,145 <
  1,358). Le 32 220 osservazioni non sono indipendenti (5 candidati per round condividono il
  seed), quindi la banda nominale è ottimistica. Nessun segno di difetto nella forma della
  distribuzione.
- **Nota importante**: questo è lo score **pubblico** `HMAC-SHA256(seed, indirizzo)`, che
  verifica la *formula* e non la VRF privata con cui l'elezione è davvero girata. La VRF privata
  si testa sotto (Q2 e ricostruzione dell'argmin).

**A.2 — `score_norm` dell'argmin `~ U(0,1)` (Prop. 5.11)**
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (minimo di
  `score_norm_public` per `height`)
- **Osservato**: n = 6444, media 0,4978; D = 0,00917, `sqrt(n)·D = 0,736`.
- **Atteso**: media 0,5; `sqrt(n)·D ≤ 1,358`.
- **Giudizio**: **conforme**. La media è entro 0,45 % da 0,5 e il KS è a metà del valore
  critico.

**A.2-bis — Q2 sul punteggio vero del vincitore**
- **File**: [analysis/phase3/timer_race.md](phase3/timer_race.md),
  [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv)
- **Osservato**: su 5687 round con punteggio vero, `score_norm_true` del vincitore ha media
  0,5418, KS p ≈ 0. Sui 5293 round "in gara" la media è 0,5078 con D = 0,0377
  (`sqrt(n)·D = 2,74`), p = 1·10⁻⁶. I 394 round vinti in cima alla banda (6,1 %) hanno
  `score_norm ≈ 1` per costruzione.
- **Atteso**: 0,5 se vince sempre l'argmin.
- **Giudizio**: **scostamento significativo, ma è la firma dell'inversione (§3.5), non della
  VRF.** Sulla catena finale la quota di vincitori con `score_norm > 0,99` sale dal 3,6 % (epoche
  2–22) al 6,0 % e al 14,7 %, insieme alle ripetizioni (§3.5). Il test decisivo è
  l'indipendenza dell'argmin privato, ricostruito dagli score di tutti i 5 miner (§3.5.1), dal
  round precedente: P(argmin = miner precedente) = 0,2097 contro Σp² ≈ 0,207 atteso. La VRF
  non trasmette vantaggio da un round al successivo.

**A.3 — coerenza della normalizzazione**
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv)
- **Osservato**: `|score_norm_mismatch_public|` massimo 1,0·10⁻¹⁴; `weight_effective −
  sqrt(weight_after_malus)` massimo 5,7·10⁻¹⁴.
- **Giudizio**: **conforme** (errore di macchina).

**Prop. 5.17 — gap standardizzato**
- **File**: [analysis/phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [analysis/plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
- **Osservato**: media del gap standardizzato miner-0 0,996, miner-1 0,996, miner-2 0,979,
  miner-3 1,018, miner-4 0,955; KS p fra 0,364 e 0,999. La figura mostra le cinque barre tutte
  blu (nessun rigetto) attorno alla linea 1.
- **Atteso**: media 1, KS non significativo.
- **Giudizio**: **conforme**. Tutte le medie sono entro il 4,5 % da 1 e nessun KS rigetta.

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)
  (`delay_recompute_mismatch_rounds_is_zero`),
  [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [analysis/plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png)
- **Cosa misura**: il ricalcolo indipendente di `D_i = T + d_i + lambda·Phi` dagli input
  loggati, contro il delay loggato dal nodo.
- **Osservato**: 0 round fuori tolleranza su 65 epoche; scarto massimo 1,0·10⁻¹³ s. La figura
  mostra tutti i punti fra 10⁻¹⁸ e 10⁻¹³ s, dieci ordini di grandezza sotto la tolleranza di
  1,5·10⁻³ s, con didascalia "0 of 32725 candidate-rounds disagree".
- **Atteso**: 0 mismatch.
- **Giudizio**: **conforme**. Harness e nodo concordano esattamente sul meccanismo.

### 3.3 Quota di blocchi contro peso

**Smorzamento `sqrt` sui pesi reali**
- **File**: [analysis/phase2/candidate_long.csv](phase2/candidate_long.csv) (ricalcolo delle quote
  `none` = `w/Σw` contro `sqrt` = `p_theoretical`, media sui round)
- **Osservato**:

| Validatore | quota `none` | quota `sqrt` (spettante) | quota osservata | quota dell'argmin vero (log) |
|---|---:|---:|---:|---:|
| miner-2 (1NJxjU3vKSMJ…) | 0,290 | 0,245 | 0,242 | 0,248 |
| miner-4 (1S526n9WV1u7…) | 0,260 | 0,232 | 0,223 | 0,241 |
| miner-3 (1UhH3MJqKnc3…) | 0,210 | 0,209 | 0,194 | 0,214 |
| miner-1 (1NhmufUWxrfs…) | 0,129 | 0,163 | 0,181 | 0,160 |
| miner-0 (1DGxG7N5LTyW…) | 0,111 | 0,151 | 0,161 | 0,138 |

  La "quota osservata" è quella della pipeline (`blocks.csv`, con blocchi orfani). Sulla
  **catena finale** le quote sono 0,243 (miner-2), 0,241 (miner-4), 0,215 (miner-3), 0,160
  (miner-1) e 0,141 (miner-0), contro spettanti di 0,245, 0,232, 0,209, 0,163 e 0,151.
- **Atteso**: compressione del più pesante rispetto a `none`, a ordinamento preservato.
- **Giudizio**: **conforme**. `sqrt` porta la quota del più pesante da 29,0 % a 24,5 % e il
  rapporto più pesante/più leggero da 2,62 a 1,62. L'ordinamento resta identico in tutte le
  colonne. Sulla catena finale ogni quota è entro 1,0 pp dalla spettante. La compressione verso
  0,2 che si vede nella colonna della pipeline (i leggeri +1,0/+1,8 pp) è un artefatto dei
  blocchi orfani, che tendono a essere dei miner che hanno perso la fork.

**Intervalli di Wilson**
- **File**: [analysis/phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [analysis/phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [analysis/plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png),
  [analysis/plots/weight_vs_election.png](plots/weight_vs_election.png)
- **Osservato**: 294/325 intervalli contengono la quota spettante, quindi **31 violazioni**
  contro 16,25 attese; binomiale P(≥31 | 325; 0,05) = 5,1·10⁻⁴. La larghezza media è
  **0,154**: la risoluzione per singola cella è di circa ±7,7 pp. Violazioni per validatore:
  miner-0 8, miner-4 8, miner-1 7, miner-2 5, miner-3 3. Per terzi di run: 8, 12 e 11. La
  heatmap mostra celle rosse sparse, senza colonne piene né righe dominanti. Lo scatter
  "entitled vs observed" è una nube attorno alla diagonale fra 0,14 e 0,27 di quota spettante.
- **Atteso**: circa il 5 % di violazioni (16).
- **Giudizio**: **scostamento significativo da indagare**. L'eccesso è ×1,9 e non è attribuito
  a un validatore specifico. Sulla catena finale le violazioni scendono a 28 (×1,7, p = 0,004;
  vedi il ricalcolo sotto).

**Goodness of fit per epoca e aggregata**
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv),
  [analysis/phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [analysis/plots/p_value_uniformity.png](plots/p_value_uniformity.png)
- **Osservato**: `share_changes_within_epoch = True` in **tutte** le 65 epoche, quindi la
  colonna di riferimento è `gof_mc_round_by_round_p`. Rigetta in 12/65 epoche (11, 12, 27, 37,
  38, 39, 45, 46, 48, 57, 58, 64), le stesse del chi-quadro asintotico. L'attesa è 3,25; la
  binomiale sul conteggio dà p = 8,2·10⁻⁵ e il KS dei p-value contro U(0,1) dà D = 0,248, p =
  5,1·10⁻⁴. Per terzi: 2, 4 e 6 rigetti, in aumento. L'istogramma ha 19 epoche nel bin [0; 0,1]
  contro 6,5 attese. L'aggregato `all` su 6456 blocchi dà χ² = 25,8 (df 4), p = 3,5·10⁻⁵ (MC
  round-by-round p = 5·10⁻⁵), MAE 0,0109, MaxAE 0,0178, TV 0,027. Le medie per epoca sono
  MAE 0,039 e TV 0,098.
- **Atteso**: 3,25 rigetti, p-value uniformi; aggregato non rigettato.
- **Ricalcolo sulla catena finale** (`block_sortition.csv`, stesse `p_theoretical_blockweighted`,
  chi-quadro per epoca e Wilson 95 %):
  - GoF: **9/65 rigetti** (epoche 11, 12, 17, 38, 40, 46, 58, 60, 64) contro 3,25 attesi,
    binomiale p = 0,005, KS dei p-value p = 9·10⁻⁵. Per terzi: 3, 2 e 4.
  - Wilson: **28/325 violazioni** contro 16,25, p = 0,004. Per terzi: 6, 8 e 14.
  - Aggregato su 6 443 blocchi: **χ² = 8,82, p = 0,066**, MAE **0,63 pp**.
- **Atteso**: 3,25 rigetti, p-value uniformi; aggregato non rigettato.
- **Giudizio**: **lieve scostamento** sull'aggregato, **scostamento significativo da indagare**
  per epoca.
  - Il rigetto aggregato della pipeline (p = 3,5·10⁻⁵) è in larga parte un **artefatto** dei
    756 blocchi orfani contati come vinti. Sulla catena finale l'aggregato non rigetta.
  - Resta un eccesso di rigetti per epoca, ×2,8 sul GoF e ×1,7 su Wilson. È coerente con il
    vantaggio dell'incumbent, che introduce dipendenza fra round consecutivi (§3.5, §3.9) e
    rende il chi-quadro multinomiale troppo ottimista sulla varianza.

**Residui**
- **File**: [analysis/phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv),
  [analysis/plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png),
  [analysis/plots/election_share_distribution.png](plots/election_share_distribution.png)
- **Osservato**: residuo medio `p_hat − p_theoretical` +0,018 per miner-1, +0,009 per miner-0,
  −0,004 per miner-2, −0,009 per miner-4, −0,014 per miner-3. I box sono tutti a cavallo di 0
  (IQR circa ±0,04). La torta cumulativa dà 24,2 / 22,3 / 19,4 / 18,1 / 16,1 %.
- **Giudizio**: **lieve scostamento**. Gli offset (≤ 1,8 pp) sono dentro l'IQR per epoca. Sulla
  catena finale si riducono a ≤ 1,0 pp e cambiano segno per miner-3 (+0,6 pp) e miner-4
  (+0,9 pp): il pattern "leggeri sovra-rappresentati" della pipeline viene dai blocchi orfani.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](phase3/longitudinal.md),
  [analysis/phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv),
  [analysis/phase3/wpoa_longitudinal_logratios.csv](phase3/wpoa_longitudinal_logratios.csv),
  [analysis/phase3/wpoa_longitudinal_validators.csv](phase3/wpoa_longitudinal_validators.csv),
  [analysis/plots/longitudinal_logratio.png](plots/longitudinal_logratio.png),
  [analysis/plots/sign_test_by_validator.png](plots/sign_test_by_validator.png)
- **Osservato**:
  - GLM logit: `beta1 = 0,921`, IC 95 % [0,781; 1,060], `converged = True`, n = 325;
    `beta1_consistent_with_1 = True`.
  - Log-rapporti a coppie (650): pendenza 0,806, intercetta 0,029, Pearson r = 0,50
    (Spearman 0,50). La figura mostra la retta arancione più piatta della diagonale su una nube
    larga ±0,6.
  - Sign test: p = 0,020 (miner-3), 0,078 (miner-1), 0,078 (miner-2), 0,221 (miner-4) e 0,922
    (miner-0), con concordanze 0,64 / 0,60 / 0,60 / 0,56 / 0,42.
  - Prima contro ultima epoca: gli intervalli si sovrappongono per 5/5 validatori.
- **Atteso**: `beta1 = 1`, pendenza 1, intercetta 0.
- **Ricalcolo sulla catena finale**: la regressione dei log-rapporti (650 coppie) dà **pendenza
  1,089**, intercetta −0,047, r = **0,62**.
- **Giudizio**: **conforme** sulla catena finale.
  - La pendenza 0,81 e il `beta1` 0,92 della pipeline sono un artefatto dei blocchi orfani, che
    mescolano all'esito un rumore indipendente dal peso.
  - Sulla catena finale la pendenza è 1,09, leggermente sopra 1 come nella run regionale
    (1,057). Anche r sale da 0,50 a 0,62.
  - Un eccesso sopra 1 è atteso dal vantaggio dell'incumbent: chi vince più spesso è più spesso
    incumbent, e quindi rivince.
  - Sui sign test, un p < 0,05 su 5 è compatibile con il caso (attesa 0,25; con Bonferroni la
    soglia è 0,01).

### 3.5 Timer race, margine e inversioni

**Margine G**
- **File**: [analysis/phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv), [analysis/plots/margin_distribution.png](plots/margin_distribution.png)
- **Osservato**: `G` pubblico medio 2,803 s (mediana 2,207 s, n = 6 444) contro 2,795 s simulati; KS contro la distribuzione esatta simulata **p = 0,701**. Il KS contro `Beta(1,n)` dà p = 0 con media attesa 1,667 s, ma è lo straw man dichiarato dalla pipeline. La densità decresce in modo monotono da 0 a 10 s (= `2·Delta_max`). Il margine vero (timer privati, §3.5.1) ha media 2,770 s e mediana 2,148 s: stessa forma.
- **Atteso**: aderenza alla simulazione esatta; il `Beta(1,n)` deve rigettare con pesi non uniformi.
- **Giudizio**: **conforme** (scarto della media +0,3 %, KS p = 0,70). Il rigetto `Beta(1,n)` **non è un rilievo**.

**Prop. 5.17**
- **File**: [analysis/phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv), [analysis/plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png)
- **Osservato**: gap standardizzato medio 0,955 (miner-4, n = 1 437), 0,979 (miner-2, n = 1 560), 0,996 (miner-1, n = 1 168), 0,996 (miner-0, n = 1 030), 1,018 (miner-3, n = 1 248). KS p = 0,36 / 0,80 / 0,80 / 1,00 / 0,41. Nessuna barra arancione nella figura.
- **Atteso**: media 1, KS non significativo.
- **Giudizio**: **conforme**. Scarti ≤ 4,5 % e nessun rigetto su 5 test.

**Decomposizione del rumore**
- **File**: [analysis/phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv), [analysis/plots/sigma_decomposition.png](plots/sigma_decomposition.png), [analysis/phase1/block_sortition.csv](phase1/block_sortition.csv)
- **Osservato**:
  - `S1_topology` = **0,0314 s**, misurato sulla mappa (10 coppie di miner, percorsi 4,1–112,4 ms). `S2_scheduler_residual_sd` (pubblico) = 15,13 s; `S2b_inversion_gap` = 2,36 s.
  - Sul punteggio vero, calcolato sulla catena finale, il residuo `dt_prev − delay_true` cambia natura lungo la run. Nelle epoche 2–22 ha sd **1,03 s** e `corr(dt_prev, delay_true)` = **0,940**, valori confrontabili con la run regionale (0,82 s e 0,938). Nelle epoche 23–44 ha sd 3,27 s e correlazione 0,63. Nelle epoche 45–66 ha sd **19,6 s** e correlazione **0,26**. Sull'intera run: sd 14,2 s, correlazione 0,27.
- **Atteso**: la sorgente primaria è lo scheduler, non la rete.
- **Giudizio**: **conforme sulla gerarchia delle sorgenti, non conforme sulla stabilità**. La rete vale 31 ms, circa 1/30 del residuo vero anche nel tratto sano. Nell'ultimo terzo il residuo di scheduling cresce di un fattore 19 fino a sommergere il timer: il block time non è più governato dalla sortition (§3.6). L'S2 pubblico va letto come audit del modello, non come misura del rumore vero.

**Inversione e bound di Prop. 5.18**
- **File**: `wpoa_timer_race.csv`, `wpoa_epoch_tests.csv` (`inversion_public_*`), [analysis/plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png)
- **Osservato**: tasso di inversione pubblico 0,799 (5 145 round su 6 444). Bound = **1,0**. MC con `sigma_S2` = 0,731.
- **Atteso**: lo score pubblico è indipendente da quello VRF, quindi l'inversione pubblica ha valore atteso `1 − Σp²` ≈ 1 − 0,207 = **0,793** qualunque cosa faccia il protocollo.
- **Giudizio**: il tasso osservato coincide con il valore di pura indipendenza (scarto 0,6 pp), quindi **non è informativo**. Il bound saturato a 1,0 è **vacuo**, non una conferma. L'inversione *vera*, misurata dagli score privati di tutti i validatori, è in §3.5.1: **19,2 %**. Sale dall'8,9 % al 15,9 % e al 36,4 % per terzi di run.

**Vantaggio del miner uscente (diagnosi)**
- **File**: [analysis/phase1/block_sortition.csv](phase1/block_sortition.csv) (`dt_prev_s`, `delay_s`, `score_norm` del vincitore sulla catena finale), `chains/miner-*/wpoa-core-intercontinental/debug.log`
- **Osservato**:
  - Residuo `dt_prev − delay_true` quando vince di nuovo il miner uscente, contro gli altri round:

    | epoche | miner uscente (media / mediana, n) | altri round (media / mediana, n) | anticipo del miner uscente | ripetizioni | vincitori con `score_norm > 0,99` |
    |---|---|---|---:|---:|---:|
    | 2–22 | 0,84 / 0,78 s (583) | 2,20 / 2,12 s (1 509) | **1,4 s** | 0,279 | 3,6 % |
    | 23–44 | 2,41 / 1,53 s (744) | 4,40 / 3,51 s (1 456) | 2,0 s | 0,338 | 6,0 % |
    | 45–66 | 16,05 / 7,83 s (868) | 23,36 / 14,28 s (1 292) | 6–7 s | 0,402 | 14,7 % |

  - Esempio dai `debug.log`, altezza 224 (epoca 2).
    - miner-1 crea il blocco 223 alle 20:36:41 e nello stesso secondo arma il timer per il 224 (14,796 s).
    - miner-3, designato con un delay più breve (14,375 s), riceve e integra il 223 solo alle 20:36:42 e arma il timer da lì.
    - Il timer di miner-1 scade alle 20:36:55,8, quello di miner-3 alle 20:36:56,4. Alle 20:36:57 miner-3 entra in `build`, ma il blocco di miner-1 (`00f42d8b…`) è già arrivato e viene integrato nello stesso secondo.
    - Il designato perde per 0,42 s pur avendo lo score migliore.
  - Il Monte-Carlo sui delay privati reali di ogni round (sotto, §3.5.1(d), modello M2) riproduce il primo terzo con un vantaggio `h = 0,5 s` e un jitter di 0,2 s. Il secondo terzo richiede `h = 1,0 s` e il terzo `h = 2 s`, con jitter di 2 s.
- **Giudizio**: **scostamento significativo da indagare** (vedi §5). È la stessa firma della run regionale `run-wpoa-core-regional-20260922T202430Z`: lì le ripetizioni sono 0,326 e il vantaggio 0,6–0,8 s. Qui il meccanismo è identico nel tratto sano e poi si amplifica con il ritardo di elaborazione crescente (§3.6).

#### 3.5.1 Vincitore designato dalla sortition privata, inversioni reali e fork

> **Perché questa sezione.** Tutte le colonne `_public` della pipeline usano lo score pubblico
> HMAC, che è indipendente da quello VRF con cui si è votato. Il Q2 (§3.1) usa lo score vero,
> ma solo quello del vincitore. Qui invece l'argmin **vero** è ricostruito per ogni round
> dagli score privati di **tutti e 5** i validatori.
>
> - **Score privati.** Con `sortition_miner_log = True` ogni miner scrive nel proprio
>   `debug.log`, per ogni altezza, la riga `mchn-miner: wPoA-sortition height=… tip=… score=… delay=…`
>   con il proprio score VRF privato e il timer armato. Per ogni altezza `h` si tiene l'ultima
>   riga il cui `tip` coincide con il blocco canonico `h−1`.
> - **Fork.** Sono ricostruite dalle righe `[wpoa-fork] cand` e `UpdateTip` dei `debug.log` di
>   **tutti i 28 nodi**. Fonti: `chains/*/wpoa-core-intercontinental/debug.log` (leggibili
>   direttamente), e [analysis/phase1/block_sortition.csv](phase1/block_sortition.csv) come
>   catena canonica. Questa coincide con la catena finale di tutti i 28 nodi a 6 658 altezze su
>   6 660: le eccezioni sono la 148, sotto il setup, e la 6 660, l'ultimo blocco, non ancora
>   propagato allo stop.
> - **Round analizzati.** Sono **5 952** (altezze 208–6 659, con tutti e 5 gli score sul padre
>   canonico).
>
> ⚠ **Attenzione a `blocks.csv`.** In **756 altezze post-setup (11,7 %)** `phase1/blocks.csv`
> registra un blocco che **non** è nella catena finale: è il primo blocco visto a
> quell'altezza, poi rimpiazzato da una fork, e ogni volta è di un miner diverso. Per terzi di
> run sono 109, 187 e 460 altezze. `phase2/round_level.csv` (`winner_address`) coincide con
> `blocks.csv` al 100 % e con la catena finale solo all'86,9 %. Tutti i test di quota della
> pipeline (Wilson, GoF, streak, longitudinale) contano quindi anche blocchi orfani.
> L'effetto è quantificato in §3.3/§3.4 e in §3.12. Qui si usa la catena finale.

**(a) La sortition privata, da sola, è esatta**
- **Cosa misura**: A.1, A.2 e Teorema 5.3 ripetuti sugli score VRF privati, cioè quelli che hanno davvero armato i timer, invece che sullo score pubblico.
- **Osservato**:
  - `E_i = score_privato × w_eff`: n = 29 760, media **1,0005** (banda ±0,0114), KS `√n·D = 0,514`. Per miner le medie vanno da 0,9838 (miner-3) a 1,0118 (miner-4), con `√n·D` fra 0,46 e 1,16: tutti sotto 1,36.
  - `score_norm` dell'argmin privato: media **0,5020**, KS `√n·D = 0,924`.
  - L'argmin privato coincide con il miner del blocco precedente nel **20,97 %** dei round (1 248 su 5 952), contro Σp² ≈ 20,7 % atteso: nessuna memoria fra round.
  - Delay loggato dal miner contro `T + Delta_max·(2·score_norm − 1) + lambda·Phi` ricalcolato:
    - nel 96,6 % delle 29 760 righe lo scarto è ≤ 0,5 ms, pari all'arrotondamento a 3 decimali del log;
    - nel restante 3,4 % (202 round) arriva fino a 0,20 s. Tutti e 202 sono round il cui padre in `blocks.csv` è un orfano, per cui il `phi_s` preso da `round_level.csv` è quello calcolato sul tip sbagliato. È un artefatto della pipeline (vedi l'avvertenza sopra), non del nodo.
  - Quote dei vincitori **designati** contro la quota spettante: chi-quadro **9,16** (df 4, p = 0,057). Quote realizzate sulla catena finale: chi-quadro 10,23 (p = 0,037).

  | validatore | `p_theoretical` | quota designata (argmin) | quota realizzata (catena finale) |
  |---|---:|---:|---:|
  | miner-0 (1DGxG7N5LTyW…) | 0,1511 | 0,1393 | 0,1405 |
  | miner-1 (1NhmufUWxrfs…) | 0,1631 | 0,1581 | 0,1569 |
  | miner-2 (1NJxjU3vKSMJ…) | 0,2454 | 0,2487 | 0,2455 |
  | miner-3 (1UhH3MJqKnc3…) | 0,2083 | 0,2144 | 0,2130 |
  | miner-4 (1S526n9WV1u7…) | 0,2320 | 0,2396 | 0,2441 |

- **Atteso**: `Exp(1)` con media 1; `U(0,1)`; quote designate uguali a `w_i/W_tot` (Teorema 5.3).
- **Giudizio**: **conforme** per la VRF (KS a 0,51 e 0,92 contro un critico di 1,36), **al limite** per le quote designate (p = 0,057). Lo scarto più ampio è miner-0: −1,2 pp, circa 2,6 errori standard su 5 952 round.
  - Sulle quote designate l'argmin è esatto per costruzione, dato il peso con cui il nodo ha calcolato lo score. La `p_theoretical` della pipeline usa invece il peso campionato dall'harness. Uno scarto sistematico fra i due indicherebbe che nodo e pipeline leggono il registro a prefissi diversi (la lettura "as of block", §3.6), non un difetto della VRF.
  - Da verificare confrontando il campo `weff=` e `validators=` delle righe `verify OK` con `candidate_long.csv`.
  - Sulla catena finale le quote realizzate stanno tutte entro 1,2 pp dalla spettante (MAE 0,63 pp, §3.3).

**(b) Quanto spesso vince il designato**
- **Osservato**: il designato (argmin privato) ha prodotto il blocco canonico in **4 808 round su 5 952 (80,8 %)**. Nei restanti **1 144 (19,2 %)** ha vinto un altro validatore. Il tasso **cresce** nel tempo: per epoca la media è 21,3 %, il range va dal 3 % al 62 % e la pendenza è +0,69 pp per epoca. La run regionale, invece, era piatta all'11 %.
- **Scomposizione dei 5 952 round**:

  | caso | round | quota | esito |
  |---|---:|---:|---|
  | nessuna fork, vince l'argmin | 2 882 | 48,4 % | corretto |
  | fork con l'argmin fra i candidati, vince l'argmin | 1 926 | 32,4 % | corretto, grazie al tie-break |
  | nessuna fork, vince un non-argmin | 797 | 13,4 % | **inversione**: l'argmin non ha mai pubblicato |
  | fork **senza** l'argmin fra i candidati | 346 | 5,8 % | **inversione**: la fork è fra due non-argmin |
  | fork con l'argmin presente, vince un non-argmin | **1** | 0,02 % | — |

- **Per terzi di run**:

  | epoche | round | inversioni | round con fork | quota vinta dall'incumbent | inversioni se l'argmin è l'incumbent | inversioni se non lo è | gap vincitore−designato (mediana / p99 / max) |
  |---|---:|---:|---:|---:|---:|---:|---|
  | 2–22 | 2 092 | **8,9 %** | 25,2 % | 81,3 % | **0 / 431** | 11,3 % | 0,32 / 2,15 / 2,64 s |
  | 23–44 | 2 180 | 15,9 % | 37,3 % | 77,5 % | 8 / 472 | 19,8 % | 0,97 / 7,99 / 9,94 s |
  | 45–66 | 1 680 | **36,4 %** | 55,5 % | 57,6 % | 45 / 345 | 42,4 % | 2,36 / 9,48 / 9,94 s |
  | **totale** | 5 952 | 19,2 % | 38,2 % | 67,5 % | 53 / 1 248 (4,2 %) | 23,2 % | 1,24 / 9,18 / 9,94 s |

- **Chi vince al posto del designato**: nel **67,5 %** dei casi (772 su 1 144) il **miner del blocco precedente**. Le 372 inversioni vinte da un non-incumbent cadono per il 67 % (248) in round con fork.
- **Inversione in funzione del margine vero** `G = D_(2) − D_(1)` (timer privati):

  | `G` (s) | < 0,25 | [0,25; 0,5) | [0,5; 1) | [1; 1,5) | [1,5; 2) | [2; 3) | [3; 5) | [5; 7) | ≥ 7 |
  |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
  | inversioni | 41,6 % | 36,5 % | 29,3 % | 17,5 % | 19,8 % | 15,1 % | 10,1 % | 6,7 % | 7,8 % |

  Nella run regionale l'inversione era **0** per `G ≥ 3 s`. Qui resta al 7–10 % anche con margini di 5–10 s, cioè metà-banda o più: nessuna latenza di rete (≤ 112 ms fra miner) può spiegarlo, lo spiega solo il ritardo di elaborazione di decine di secondi della seconda metà (§3.6).
- **Chi ci perde**: il tasso di "argmin non eletto" è 20,0 % per miner-0, 20,3 % per miner-1, 19,1 % per miner-2, **20,6 % per miner-3** (Singapore, il sito più lontano) e 17,0 % per miner-4. Le differenze sono piccole: il fattore dominante è il ruolo di incumbent, non il sito.
- **Giudizio**: **scostamento significativo da indagare**. Nel tratto sano (epoche 2–22) la firma è quella della run regionale, inequivocabile: le inversioni sono **nulle** quando il designato è l'incumbent (0 su 431), vanno all'incumbent nell'81 % dei casi, e il gap è sempre ≤ 2,64 s. Si tratta del vantaggio locale del miner uscente, non di un errore della sortition, che al punto (a) è esatta. Nella seconda metà a questo si somma una componente indipendente dal ruolo, che cresce fino a portare l'inversione al 36 %.

**(c) Fork: frequenza, finestra e risoluzione**
- **Osservato**:
  - **Frequenza.** Round con fork (≥ 2 blocchi validi alla stessa altezza visti da almeno un nodo): **2 273 su 5 952 (38,2 %)**; 1 352 con 2 blocchi, 539 con 3, 226 con 4, 156 con 5. Per epoca fra il 18 % e il 68 %, **in crescita** (+0,72 pp per epoca). Nella run regionale erano il 16,3 %, senza trend.
  - **Risoluzione.** Al termine della run tutti i 28 nodi hanno lo stesso blocco a 6 658 altezze su 6 660. In **2 272 fork su 2 273** il blocco canonico è quello di **score minimo fra i candidati**. Ogni riorganizzazione dopo il setup è di profondità **1**: 45 473 scambi di un blocco alla stessa altezza, sommati sui nodi, e **0** riorganizzazioni di profondità ≥ 2.
  - **Permanenza su un tip orfano.** Un nodo è restato su un tip orfano per una mediana di **1 s**, un p90 di 7 s e un massimo di **23 s**. Nella run regionale il massimo era 2 s.
  - **Inversioni evitate dal tie-break**: in **1 034** fork (17,4 % dei round) il blocco dell'argmin **non** era il primo arrivato in rete, eppure ha vinto grazie allo score. Con la regola nativa (primo arrivato) le inversioni sarebbero state circa **2 178 (36,6 %)** invece di 1 144 (19,2 %). La stima prende come vincitore nativo il candidato con ricezione più precoce sull'insieme dei nodi. In 620 di queste fork il primo arrivato era il blocco dell'incumbent.
  - **Finestra di fork** (3 468 round in cui nessuno dei due timer più rapidi è dell'incumbent):

    | `G` (s) | < 0,5 | [0,5; 1) | [1; 1,25) | [1,25; 1,5) | [1,5; 1,75) | [1,75; 2) | [2; 3) | [3; 5) | ≥ 5 |
    |---|---:|---:|---:|---:|---:|---:|---:|---:|---:|
    | P(fork) | 0,64 | 0,61 | 0,64 | 0,56 | 0,42 | 0,39 | 0,40 | 0,29 | 0,21 |

    Quando l'incumbent ha il timer più rapido (1 247 round), le fork sono il 18,1 % e le inversioni il 4,3 %.
- **Lettura**: il secondo validatore pubblica un blocco concorrente se il suo timer scade prima di aver ricevuto **e processato** il blocco del primo.
  - Nella run regionale la finestra si chiudeva a circa 1,5–2 s. Qui la probabilità di fork scende solo lentamente e vale ancora il 21 % con margini ≥ 5 s.
  - La finestra efficace è quindi dell'ordine del ritardo di elaborazione locale del blocco, che in questa run passa da circa 1 s a decine di secondi (§3.6), e non della latenza di rete (≤ 112 ms fra miner, `S1` = 31 ms).
  - È lo stesso ritardo che, per asimmetria, dà all'incumbent il suo vantaggio: lui il proprio blocco non deve riceverlo.
- **Giudizio**: **conforme sulla safety**, **scostamento significativo sulla liveness**.
  - Safety: nessuna fork irrisolta, nessuna riorganizzazione profonda, convergenza finale su tutti i nodi.
  - Tie-break: la regola per score fa esattamente ciò per cui è progettata. Vince sempre l'argmin *fra i blocchi prodotti* (2 272/2 273), e le inversioni scendono da circa il 37 % a circa il 19 %: è **più efficace qui che nella run regionale** (−17 pp contro −7 pp), perché le fork sono più frequenti.
  - Limite: **non può** correggere le 1 143 inversioni restanti, perché in quei round il blocco del designato non esiste fra i candidati. È il limite già noto della regola: agisce solo sui candidati osservati, sotto `nChainWork`.
  - Liveness: il 38 % di round con fork, in crescita, e tip orfani fino a 23 s sono un costo reale del rallentamento di §3.6.

**(d) Confronto con la Proposizione 5.18**

La tesi dà, per latenza modellata come rumore additivo **indipendente a media nulla** `L_i` con
deviazione standard `sigma`:

```
Pr[ î != i* ]  <=  2*sigma^2/t^2 + n*t/(2*Delta_max)          per ogni t > 0
```

Minimizzando in `t` (`t* = (8·sigma²·Delta_max/n)^(1/3)`) si ottiene la forma chiusa

```
Pr[ î != i* ]  <=  (3/2) * ( n*sigma / Delta_max )^(2/3)
```

qui con `n = 5` e `Delta_max = 5 s`.

| `sigma` usata | valore | bound Prop. 5.18 | osservato (tutta la run / epoche 2–22) | esito |
|---|---:|---:|---:|---|
| `S1_topology` (propagazione sulla mappa) | 0,0314 s | **0,149** (`t*` = 0,20 s) | **0,192** / **0,089** | **violato** sulla run (1,3×), valido nel tratto sano |
| `sigma` che rende il bound = osservato (run) | 0,0458 s | 0,192 | 0,192 | — |
| `sigma` che rende il bound = osservato (ep. 2–22) | 0,0145 s | 0,089 | 0,089 | — |
| `sigma` del rumore simmetrico che riproduce il tasso, ep. 2–22 (MC, sotto) | 0,30 s | 0,672 | 0,089 | valido, ma largo 7,6× |
| `sigma` del rumore simmetrico che riproduce il tasso, run (MC) | 1,0 s | 1,50 | 0,192 | vacuo (> 1) |
| residuo vero `dt_prev − delay_true` (sd), ep. 2–22 | 1,03 s | 1,53 | 0,089 | vacuo |
| `S2b_inversion_gap` | 2,36 s | 2,66 | 0,192 | vacuo |
| residuo vero (sd), run | 14,2 s | 8,81 | 0,192 | vacuo |
| `S2_scheduler_residual_sd` (pubblico) | 15,13 s | 9,18 | 0,192 | vacuo |

- **Il termine di margine regge.** Il secondo addendo `n·t/(2·Delta_max)` maggiora `Pr[G < t]` con un'unione di eventi. Sui margini veri (5 952 round):

  | `t` (s) | 0,1 | 0,25 | 0,5 | 1 | 1,5 | 2 | 3 |
  |---|---:|---:|---:|---:|---:|---:|---:|
  | `Pr[G < t]` osservato | 0,048 | 0,102 | 0,174 | 0,295 | 0,393 | 0,476 | 0,619 |
  | termine di margine `n·t/(2·Delta_max)` | 0,050 | 0,125 | 0,250 | 0,500 | 0,750 | 1,000 | 1,500 |
  | approssimazione `Beta(1,n)` | 0,049 | 0,119 | 0,226 | 0,410 | 0,556 | 0,672 | 0,832 |

  La maggiorazione vale a ogni `t` ed è conservativa di 1,0–2,4×: con pesi non uniformi il margine è più largo che nel caso uniforme. Il margine medio vero è 2,77 s, la mediana 2,15 s.
- **È l'ipotesi sul rumore a cadere.** Nel tratto sano il bound con il rumore di rete (`S1`) promette il 14,9 %, e se ne osserva l'8,9 %: il numero torna, ma per la ragione sbagliata, come mostra la composizione. Su tutta la run il bound è violato (19,2 % contro 14,9 %). Non è una contraddizione della proposizione: la sua ipotesi, rumore indipendente a media nulla, non vale. Due modelli simulati sui **delay privati reali di ogni round** (5 952 round, 3–10 repliche; parametri scelti per minimizzare lo scarto sulle tre grandezze osservate):

  | tratto | modello | parametri | inversioni | quota vinta dall'incumbent | inversioni quando l'argmin è l'incumbent |
  |---|---|---|---:|---:|---:|
  | epoche 2–22 | **osservato** | — | **0,089** | **0,813** | **0,000** (su 431) |
  | | M1: rumore gaussiano i.i.d. a media nulla (ipotesi di Prop. 5.18) | `sigma = 0,3 s` | 0,083 | 0,201 | 0,079 |
  | | M2: vantaggio `h` all'incumbent + rumore | `h = 0,5 s`, `sigma = 0,2 s` | 0,086 | 0,760 | 0,000 |
  | epoche 23–44 | **osservato** | — | **0,159** | **0,775** | **0,017** |
  | | M1 | `sigma = 0,8 s` | 0,172 | 0,204 | 0,187 |
  | | M2 | `h = 1,0 s`, `sigma = 0,5 s` | 0,161 | 0,753 | 0,020 |
  | epoche 45–66 | **osservato** | — | **0,364** | **0,576** | **0,130** |
  | | M1 | `sigma = 2,5 s` | 0,383 | 0,205 | 0,389 |
  | | M2 | `h = 2 s`, `sigma = 2 s` | 0,355 | 0,504 | 0,149 |
  | tutta la run | **osservato** | — | **0,192** | **0,675** | **0,042** |
  | | M1 | `sigma = 1,0 s` | 0,204 | 0,193 | 0,212 |
  | | M2 | `h = 1,5 s`, `sigma = 1 s` | 0,240 | 0,643 | 0,053 |

  - **M1** riproduce il tasso in ogni tratto, ma sbaglia sempre la composizione. Dà all'incumbent il 20 % delle inversioni invece del 58–81 %, e prevede l'8–39 % di inversioni anche quando l'argmin è l'incumbent, dove se ne osservano 0–13 %.
  - **M2** riproduce tutte e tre le grandezze insieme, ma con parametri che **crescono nel tempo**: da `h` = 0,5 s con jitter 0,2 s nel primo terzo, a `h` = 2 s con jitter 2 s nell'ultimo.
  - Il primo terzo coincide con la run regionale (`h` = 0,6–0,7 s, jitter 0,1–0,2 s): lì il bias è la componente dominante.
  - Nell'ultimo terzo compare anche un rumore simmetrico di secondi: ritardi di elaborazione casuali, per nodo e per blocco, che colpiscono chiunque, non solo i non-incumbent.
- **Giudizio**: **scostamento significativo da indagare**, nel modello e nella run.
  - La Prop. 5.18 resta corretta nel suo dominio, e il suo termine di margine è verificato empiricamente.
  - Il rumore che guida le inversioni in questa implementazione **non è simmetrico e non è stazionario**. È un bias deterministico legato al ruolo di incumbent, di circa 0,5 s nel tratto sano e fino a 2 s alla fine, più un jitter che cresce da 0,2 a 2 s. Entrambi sono generati dal tempo di elaborazione locale del blocco, non dalla rete (31 ms).
  - Per usare la proposizione come dimensionamento, `sigma` dovrebbe includere questa componente, e il bias dovrebbe comparire esplicitamente, per esempio come termine `Pr[G < h]`.
  - Anche solo con `sigma = 0,3 s` (tratto sano), il vincolo `Delta_max ≳ n·sigma·eps^(−3/2)` per `eps = 0,05` richiederebbe `Delta_max ≈ 134 s`, incompatibile con `Delta_max ≤ T_block − lambda·M = 8,5 s`.
  - Le leve praticabili sono due. La prima è eliminare il bias alla fonte, ancorando i timer al tempo di catena e non all'istante locale di ricezione del tip. La seconda è rimuovere il rallentamento di §3.6, che è ciò che fa crescere entrambi i parametri.

### 3.6 Stabilità del block time e correzione globale

**Block time realizzato**
- **File**: [analysis/phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`),
  [analysis/phase1/blocks.csv](phase1/blocks.csv)
- **Osservato**: sui 6444 round non-setup `dt` ha media **18,36 s**, deviazione standard 14,65 s,
  mediana 14 s, p95 52 s, p99 75 s e massimo 142 s. Il 13,7 % dei round supera 30 s. Media per
  epoca: 11,05 (ep. 2), 11,3 (ep. 10), 11,7 (ep. 20), 12,3 (ep. 30), 15,8 (ep. 40), 21,2
  (ep. 50), 29,7 (ep. 60), **60,7 (ep. 66)**. Regressione lineare: +0,48 s per epoca, Spearman
  0,985, p ≈ 1·10⁻⁴⁹. La media del delay vero del vincitore è 9,54 s (9,51 s nelle epoche
  2–20): il timer punta correttamente sotto T, ma il residuo `block_time − earliest_time` cresce
  da 1,75 s (h < 2000) a 2,96 s, 6,0 s e 22,2 s (h ≥ 5000).
- **Confronto con run comparabili** in `test/results/`:
  - `run-wpoa-core-intercontinental-20260918T231018Z` (stessa mappa, T = 10, δ = 0,5, λ = 0,3,
    `sqrt`, 10 miner, senza fork_score): stabile fra 11,2 e 11,8 s per 58 epoche.
  - `run-wpoa-core-regional-20260922T202430Z` (T = 8, fork_score attivo), **in esecuzione in
    parallelo sullo stesso host** fino al 2026-09-23 21:49: stabile fra 8,6 e 9,4 s per 98
    epoche.

  Nel frattempo questa run è passata da 11 a 42 s, e ha continuato a peggiorare anche dopo la
  fine della run parallela. Il carico dell'host non basta quindi a spiegare il degrado.
- **Atteso**: media che converge a 10 s grazie a `Phi`.
- **Giudizio**: **scostamento significativo da indagare, di gravità alta.** Anche nella parte
  sana (epoche 2–30, circa 11,3 s) la media resta 1,3 s sopra il target. Il sovrappiù è
  coerente con un ritardo di ricezione/validazione di circa 1 s per blocco, che il controllo
  con `lambda = 0,3` non recupera del tutto. Dall'epoca 33 in poi la divergenza è
  progressiva e non si stabilizza.

**Correzione `Phi`**
- **File**: [analysis/phase2/round_level.csv](phase2/round_level.csv) (`phi_s`),
  [analysis/plots/phi_over_time.png](plots/phi_over_time.png)
- **Osservato**: `M = 5 s`. Media di `Phi` −3,03 s, deviazione standard 1,65 s, 71 valori
  distinti; `Phi < 0` nel 98,7 % dei round. Il segno cambia solo nell'1,1 % dei passaggi fra
  round consecutivi, quindi non c'è oscillazione. Saturazione a −M per tratto: 0 % (h < 2000),
  4,7 % (2000–4000), 42,3 % (4000–5000), **88,3 %** (h ≥ 5000). La figura mostra la mediana
  mobile scendere da −1,25 a −5 fra le altezze 1000 e 5000, e poi restare incollata a −5 con
  rare escursioni.
- **Atteso**: `Phi` piccolo e di segno alterno, media sul target.
- **Giudizio**: **scostamento significativo da indagare**. Il feedback non oscilla (`lambda` non
  è troppo aggressivo), ma è **saturato**: `lambda·M = 1,5 s` è l'accorciamento massimo del
  timer, mentre il ritardo esterno al modello raggiunge i 20–50 s. Nessun `lambda` ammissibile
  (vincolo `Delta_max ≤ T − lambda·M`) potrebbe compensarlo. Il check `phi_consistent = FAIL`
  (71 valori) di per sé **non è un difetto**: è atteso, perché `Phi` varia per design.

**Causa del ritardo: elaborazione locale lenta e crescente** (analisi aggiuntiva)
- **File**: `chains/<nodo>/wpoa-core-intercontinental/debug.log`. Ritardo fra `date=` di
  `UpdateTip` (timestamp del blocco) e l'ora di log di `UpdateTip`, per blocchi di 13 epoche.
- **Osservato**:
  - **Ritardo di ricezione** (mediana, blocchi altrui), uguale per tutti e 6 i nodi misurati:
    1, 1, 1, 2, **15, 29–35 s**; p90 1–2, 2, 4, 11, 36–38, 44–57 s.
  - **Blocchi propri**, cioè dalla creazione del blocco al suo ingresso nel tip dello stesso
    nodo: mediana 0, 0, 1, 2, **12–15, 23–38 s**. Il ritardo quindi **non è di rete**. Un
    esempio a h = 6500 (miner-3): `build` 03:00:43, `Block Found` 03:00:48, prima `verify OK`
    03:00:57, `UpdateTip` 03:01:08, cioè 25 s per un blocco con una sola transazione.
  - **Letture del registro.** Ogni riga `[StreamWeightRegistry] All nodes weights as of block…`
    è preceduta da un intervallo che cresce con l'altezza: su miner-3 da 0,0 s (h < 2000) a 0,1,
    0,3, 0,5, 1,5 e **2,5 s in media** (h ≥ 6500), con singoli casi di 7–9 s; sull'admin resta
    ≤ 0,2 s. Il codice di `StreamWeightRegistry::ReadAllRecords`
    (`src/wpoa/stream_weight_registry.cpp`, righe 533 e seguenti) rilegge a **ogni** chiamata
    tutti i record confermati di `wpoa-weights` con un `GetWalletTx` ciascuno (330 record a fine
    run). La lettura "as of block" è stata introdotta dal commit `4cefac9d` (2026-09-22) e viene
    invocata più volte per blocco (verifica di ogni candidato, loop del miner, RPC della
    pipeline).
  - Nel `debug.log` di miner-0 le valutazioni del seed RANDAO per altezza passano da 52 a 187.
  - Sono presenti **2485–2634 altezze con più di un `UpdateTip`** per nodo (riorganizzazioni)
    e 586 righe `generated block is stale` su miner-0.
- **Giudizio**: la sorgente del ritardo è **locale e cresce con la lunghezza della catena**. È
  compatibile con un costo O(record) per lettura del registro, ripetuto molte volte per round,
  su un wallet di miner che cresce. Blocchi più lenti comportano più polling per altezza e
  quindi più letture: questo retroaziona positivamente. Resta un'ipotesi da confermare con un
  profilo: il costo è misurato sull'intervallo che termina con la riga di log, non strumentato
  dentro la funzione. Resta anche aperta la domanda sul perché la run regionale parallela non
  degradi (il suo debug.log non è leggibile, permessi `root`).

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [analysis/phase3/weight_engine_epoch.csv](phase3/weight_engine_epoch.csv),
  [analysis/phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [analysis/phase3/weight_engine_gini.csv](phase3/weight_engine_gini.csv),
  [analysis/phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [analysis/plots/weights_over_time.png](plots/weights_over_time.png),
  [analysis/plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png),
  [analysis/plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [analysis/plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png),
  [analysis/plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png),
  [analysis/plots/esg_scores.png](plots/esg_scores.png)

**Identità del peso grezzo**
- **Osservato**: `W_k_raw = ESG_Mk·(miner_activity + companies_contribution_sum)` torna con
  errore relativo massimo 2,4·10⁻¹⁶ su 330 righe.
- **Giudizio**: **conforme**.

**Formula ricorsiva**
- **Osservato**: `w_k_final = W_k_raw·(0,5·rho_prev + 0,5)` per e ≥ 2 torna con errore
  massimo 6,2·10⁻¹⁶; per l'epoca 1 `w_k_final = W_k_raw` esattamente.
- **Giudizio**: **conforme**.

**Retroazione `rho → peso`**
- **Osservato**: `rho` ha media 0,0021, deviazione standard 0,0015, massimo 0,0070, ed è zero
  nell'11,8 % dei casi. Il fattore moltiplicativo resta quindi in [0,500; 0,5035]. La Spearman
  lag-1 aggregata vale 0,078 (p = 0,162, n = 325); per cluster head vale 0,05–0,06
  (p ≈ 0,63–0,70), con l'eccezione di miner-2 a 0,339 (p = 0,006). Nello scatter la nube è
  piatta in `rho`, con i pesi raggruppati su due livelli (≈150 k e ≈300–450 k) che riflettono
  i cluster e non `rho`.
- **Atteso**: effetto al massimo ×2, spesso sommerso da `tau`.
- **Giudizio**: **conforme ma inerte**. `rho` non è identicamente nullo, ma è compresso di tre
  ordini di grandezza perché il `saldo` a denominatore include il seed di 84 200 GAS
  (`epoch_engine.csv`, epoca 1: `balance_saldo = 84 205`) contro restituzioni di decine di GAS
  per epoca. La retroazione è di fatto spenta: la variazione massima di peso che può indurre è
  dello 0,35 %. La correlazione di miner-2 da sola, su 5 test, non supera Bonferroni con
  margine e non è interpretabile come canale reale. È un limite di configurazione del
  funding, non un difetto del motore.

**Traiettoria dei pesi**
- **Osservato**: la Spearman epoca→peso pubblicato per validatore vale 0,14, 0,005, −0,23,
  0,13 e 0,002, tutte con p ≥ 0,07. Dalla prima all'ultima epoca: miner-0 138 k→143 k, miner-1
  155 k→190 k, miner-2 314 k→364 k, miner-3 301 k→274 k, miner-4 340 k→348 k. Il boxplot del
  peso finale ha mediana mobile piatta a ≈510–530. L'epoca 1 ha pesi 10–25 k perché
  `miner_activity = 1` e le aziende sono ancora quasi inattive (epoca parziale di setup).
- **Giudizio**: **conforme**. Il peso è rumoroso ma stazionario, com'è atteso con `tau`
  riestratto a ogni epoca e retroazione inerte.

**Concentrazione del motore**
- **Osservato**: `gini_delta` medio 6·10⁻⁵ (min −6·10⁻⁴, max 7·10⁻⁴); pendenza 1·10⁻⁶,
  Spearman 0,032, p = 0,80.
- **Giudizio**: **conforme**. Il motore non amplifica la disuguaglianza dei propri input.

**ESG statici**
- **Osservato**: un solo valore di `miner_esg_score` per miner su 66 epoche (29, 56, 75, 55,
  49), coerente con i 25 eventi di `esg_events.csv`. Il grafico ESG mostra le aziende fra 4
  (company-6) e 99 (company-17).
- **Giudizio**: **conforme**.

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](phase2/epoch_concentration.csv),
  [analysis/phase3/report.md](phase3/report.md) §3,
  [analysis/plots/concentration_over_time.png](plots/concentration_over_time.png)
- **Osservato**:
  - **Aggregato**: HHI teorico 0,2069 contro osservato **0,2042**; N_eff osservato 4,90;
    Gini teorico 0,103 contro osservato 0,082; entropia normalizzata 0,989 contro 0,993;
    Nakamoto 1/3, 1/2 e 2/3 = 2, 3, 3 teorici contro 2, 3, 4 osservati.
  - **Per epoca**: HHI osservato − teorico in media +0,009; N_eff medio 4,82 teorico contro
    4,63 osservato. Il Nakamoto 1/2 oscilla fra 2 e 3 in figura, contro 3 teorico quasi
    sempre.
- **Atteso**: HHI teorico ≈ 1/5 con pesi omogenei. L'HHI osservato per epoca è gonfiato dalla
  varianza multinomiale (100 blocchi), mentre l'aggregato è affidabile.
- **Giudizio**: **conforme**. L'eccesso per epoca (+0,009) è un artefatto di campione.
  Sull'aggregato il potere osservato è persino **meno** concentrato del teorico (HHI −0,003,
  Gini −0,021): è la compressione da inversione, e sposta verso la decentralizzazione, non il
  contrario.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](phase3/streak.md),
  [analysis/phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv)
- **Osservato**:
  - Probabilità di ripetizione aggregata **0,354** contro 0,207 del Monte Carlo (+71 %),
    p = 1·10⁻⁴.
  - Per epoca il p del Monte Carlo è < 0,05 in **55/65** epoche (attese 3,25), e la ripetizione
    cresce: 0,301 (ep. 2–22), 0,351 (23–44), 0,413 (45–66), fino a 0,54 all'epoca 66.
  - `L_max` è significativo in 24/65 epoche; il massimo è 9 contro 6,52 in media sul run
    (p = 0,030).
  - Sulla catena finale la ripetizione vale **0,340** (per terzi 0,281 / 0,338 / 0,403) contro
    0,208 del Monte Carlo.
  - Dai log (§3.5.1): l'argmin vero ripete il miner precedente nel 20,97 % dei round, cioè
    l'atteso.
- **Atteso**: ripetizione ≈ Σp² ≈ 0,207.
- **Giudizio**: **scostamento significativo da indagare**. L'eccesso è sistematico (85 % delle
  epoche) e quindi i round **non** sono indipendenti a livello di esito, ma **lo sono a livello
  di sortition**. L'eccesso sta tutto nelle inversioni a favore dell'incumbent (772 delle 1 144
  inversioni vere sulla catena finale). La causa è il vantaggio locale del produttore del blocco precedente
  (§3.5), amplificato dalla lentezza di validazione. Il seed si rinfresca correttamente.

### 3.10 Malus

Caso **J.1**: nessuna violazione iniettata.
- **File**: [analysis/phase2/malus_state.csv](phase2/malus_state.csv),
  [analysis/phase3/malus_invariants.csv](phase3/malus_invariants.csv),
  [analysis/phase1/malus_detections.csv](phase1/malus_detections.csv),
  [analysis/phase3/malus_detection.csv](phase3/malus_detection.csv),
  [analysis/phase3/malus_funnel.csv](phase3/malus_funnel.csv),
  [analysis/phase3/malus_latency.csv](phase3/malus_latency.csv),
  [analysis/phase3/malus_rate.csv](phase3/malus_rate.csv),
  [analysis/phase3/malus_weight_effect.csv](phase3/malus_weight_effect.csv),
  [analysis/phase3/malus_weight_effect_matched.csv](phase3/malus_weight_effect_matched.csv),
  [analysis/plots/malus_invariant_audit.png](plots/malus_invariant_audit.png),
  [analysis/plots/malus_state_trajectory.png](plots/malus_state_trajectory.png),
  [analysis/plots/malus_weight_effect.png](plots/malus_weight_effect.png),
  [analysis/plots/malus_action_funnel.png](plots/malus_action_funnel.png),
  [analysis/plots/malus_detection_latency.png](plots/malus_detection_latency.png)
- **Osservato**:
  - `M = 0`, `Psi = 1` e `excluded = False` su 330/330 celle (epoca, validatore); i tre
    invarianti sono veri ovunque e la heatmap degli invarianti è tutta verde ("0 violation(s)
    across 330 cells").
  - Nei round di `candidate_long.csv`, `malus` massimo 0 e `malus_factor` minimo 1.
  - `malus_detections.csv`, `malicious_actions/opportunities/confirmations.csv`,
    `phase2/malus_actions.csv` e `malus_detection_events.csv` sono vuoti. Il funnel è a zero,
    la latenza ha n = 0 e `malus_rate.csv` è "empty".
  - `malus_state_trajectory.png` riporta "no malicious miner had a malus trajectory to plot".
  - `malus_weight_effect.png` mostra solo il gruppo onesto (n = 5, variazione relativa ≈ 13,9 ×
    dalla prima all'ultima epoca). È la crescita da epoca 1 (setup, pesi ≈10–25 k) a regime, non
    un effetto del malus.
- **Atteso**: effetto esattamente nullo.
- **Giudizio**: **conforme**. [analysis/phase3/malus_effectiveness.md](phase3/malus_effectiveness.md)
  **non è presente**: l'esperimento malicious non è stato eseguito in questa run. Nessuna
  riduzione di peso o di elezioni è attribuibile al malus.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [analysis/phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [analysis/phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv)
  (Spearman calcolate qui, epoche 2–66, n = 325)
- **Osservato — (K1) blocchi vinti contro**:
  - `w_k_published`: 0,526 (p ≈ 1·10⁻²⁴)
  - `W_k_raw`: 0,526
  - `companies_contribution_sum`: 0,315 (p = 6·10⁻⁹)
  - `earnings_g_k`: 0,304 (p = 2·10⁻⁸)
  - `income`: 0,047 (p = 0,40)
  - `miner_activity`: 0,031 (p = 0,57)
- **Osservato — (K2) residui `p_hat − p_theoretical` contro**:
  - `earnings_g_k`: −0,076 (p = 0,17)
  - `income`: −0,018 (p = 0,74)
  - `miner_activity`: −0,001 (p = 0,98)
  - `R_k`: 0,018 (p = 0,74)
  - `rho`: 0,018 (p = 0,74)
  - `companies_contribution_sum`: −0,131 (p = 0,018)
- **Atteso**: correlazione positiva in K1, interamente mediata dal peso; nulla in K2.
- **Giudizio**: **conforme**. A peso fissato guadagno, entrate, restituzioni e attività non
  spiegano i residui. L'unico p < 0,05 (contributo aziendale, −0,13) non supera Bonferroni su
  6 test (soglia 0,0083) e ha **segno negativo**: i cluster con più contributo (quindi più
  pesanti) sono leggermente sotto-rappresentati. È di nuovo la compressione da inversione, non
  un canale di vantaggio non documentato.

### 3.12 Integrità della run e controlli di consistenza

**Controlli di consistenza**
- **File**: [analysis/phase3/consistency_checks.csv](phase3/consistency_checks.csv)
- **Osservato**:

| check | critico | esito |
|---|---|---|
| `registry_weights_finite_and_positive` (545 580 campioni) | sì | PASS |
| `no_phantom_validator_in_registry` | sì | PASS |
| `malus_finite_and_psi_in_unit_interval` | sì | PASS |
| `delay_recompute_mismatch_rounds_is_zero` | sì | PASS |
| `every_esg_publication_reached_the_stream` (25/25) | sì | PASS |
| `only_miners_pay_the_treasury` (1194 pagamenti) | sì | PASS |
| `at_least_one_fully_measured_epoch` (65) | sì | PASS |
| `certified_scores_reflected_in_the_engine` | no | PASS |
| `phi_consistent` (71 valori) | no | FAIL — atteso, `Phi` varia per design |
| `traffic_counts_within_configured_range` (60/1600 fuori range) | no | FAIL — vedi sotto |

- **Giudizio**: **conforme** su tutti e 7 i check critici.

**Verifica dei pesi pubblicati**
- **File**: [analysis/phase1/verification.csv](phase1/verification.csv)
- **Osservato**: 300/300 record con verdetto `ok` (epoche 1–65) e `published = recomputed` su
  tutti.
- **Giudizio**: **conforme**. Nessun `BadWeight` di fatto.

**Traffico**
- **File**: [analysis/phase2/epoch_traffic.csv](phase2/epoch_traffic.csv),
  [analysis/plots/traffic_per_epoch.png](plots/traffic_per_epoch.png)
- **Osservato**:
  - Le 60 coppie fuori range sono tutte aziende nelle epoche 63, 64 e 65 (20 per epoca). Per le
    aziende, le tx on-chain lette dallo stream valgono 97 all'epoca 63 e 0 alle epoche 64–66,
    mentre le tx inviate sono circa 880 per epoca e la figura mostra le barre verdi che
    spariscono dall'epoca 63.
  - Nello stesso periodo i blocchi portano ancora in media 9,3–10,5 tx.
  - `rpc_errors.csv` contiene 6 timeout di `liststreamitems` sull'admin (`admin is
    unreachable: timed out`, rpc timeout 30 s) alle altezze 5805–6605.
- **Giudizio**: **lieve scostamento, di raccolta e non di protocollo**. Lo snapshot dello stream
  non è stato raccolto a fine run perché l'admin, rallentato come gli altri nodi, ha superato il
  timeout RPC. Fino all'epoca 62 inviate e on-chain coincidono. Collegato al degrado di §3.6:
  la frazione di blocchi con la sola coinbase passa dal 4 % (ep. 2) al 60–73 % (ep. 57–66), con
  le transazioni incluse a raffiche (massimo 93 tx).

**Errori RPC**
- **File**: [analysis/phase1/rpc_errors.csv](phase1/rpc_errors.csv)
- **Osservato**: 414 righe. 408 sono `wpoalist*` "Round not evaluable" alle altezze 4–105
  (bootstrap, registro non ancora popolato: benigni); le altre 6 sono i timeout sopra.
- **Giudizio**: **conforme** per la parte di bootstrap; i 6 timeout sono un indicatore del
  degrado.

**Catena registrata dalla pipeline contro catena finale**
- **File**: [analysis/phase1/blocks.csv](phase1/blocks.csv),
  [analysis/phase1/block_sortition.csv](phase1/block_sortition.csv),
  [analysis/phase2/round_level.csv](phase2/round_level.csv), `UpdateTip` dei `debug.log` di
  tutti i 28 nodi
- **Osservato**:
  - `blocks.csv` e `block_sortition.csv` differiscono in **766 altezze** (756 dopo il setup);
    in tutte il miner è diverso. Per terzi di run sono 109, 187 e 460 altezze.
  - `block_sortition.csv` coincide con la catena finale dei 28 nodi a 6 658/6 660 altezze.
  - `round_level.csv` segue `blocks.csv` al 100 %.
- **Atteso**: una sola catena, quella finale, in tutte le tabelle.
- **Giudizio**: **scostamento significativo (difetto della pipeline)**. `blocks.csv` registra
  il primo blocco visto a ogni altezza, non quello rimasto dopo la risoluzione delle fork (38 %
  dei round, §3.5.1). Tutte le metriche di quota, streak e concentrazione di phase2/phase3
  includono quindi l'11,7 % di blocchi orfani. I ricalcoli sulla catena finale sono in §3.3,
  §3.4, §3.5.1 e §3.9. Ne resta invariato il giudizio sulla randomness e sul delay, e cambia
  quello sull'aderenza aggregata (da rigetto a non rigetto).

**Esito della run**
- **File**: `manifest.json`
- **Osservato**: `status = interrupted`, altezza 6660 su 10120 obiettivo (65,8 %). La run doveva
  durare circa 28 h a 10 s e ne è durata circa 34 (fermata dall'operatore alle 05:27 UTC del
  24/09). L'epoca 66 è parziale (60 blocchi) e le sue metriche (HHI 0,211, repeat 0,54) vanno
  lette a parte.
- **Giudizio**: **scostamento significativo**. La run è incompleta e le ultime ~15 epoche sono
  misurate in un regime di liveness degradata.

## 4. Punti di forza

- **VRF e sortition corrette.** Sugli score privati di tutti i 5 miner (5 952 round), `E_i` ha
  media 1,0005 (`√n·D = 0,51`) e `score_norm` dell'argmin ha media 0,502 (`√n·D = 0,92`).
  L'argmin ripete il miner precedente nel 20,97 % dei round (atteso ≈ 20,7 %).
- **Fork sempre risolte correttamente.** Il 38 % dei round ha una fork. Sono tutte risolte a
  profondità 1, con 0 riorganizzazioni profonde e convergenza finale su tutti i 28 nodi. Il
  tie-break per score sceglie il candidato di score minimo in 2 272 fork su 2 273 e porta le
  inversioni dal 36,6 % stimato con la regola nativa al 19,2 %.
- **Aderenza aggregata sulla catena finale**: χ² = 8,82 (p = 0,066), MAE 0,63 pp, pendenza dei
  log-rapporti 1,09.
- **Formula del punteggio pubblica pulita.** Sul minimo per round di `score_norm_public`, media
  0,4978 e `sqrt(n)·D = 0,74` (critico 1,36). Su `E_i`, KS `sqrt(n)·D = 1,14`.
- **Prop. 5.17 verificata per tutti e 5 i vincitori**: medie del gap standardizzato 0,955–1,018,
  KS p ≥ 0,36.
- **Meccanismo del delay esatto**: 0/32 725 mismatch, scarto massimo 1·10⁻¹³ s.
- **Margine della timer race conforme alla sortition simulata**: KS p = 0,70, media osservata
  2,803 s contro 2,795 s simulata.
- **Smorzamento `sqrt` efficace e monotono**: quota del più pesante 29,0 % → 24,5 %, rapporto
  estremi 2,62 → 1,62, ordinamento identico fra spettante, argmin e osservato.
- **Weight engine numericamente esatto**: identità di `W_k_raw` e formula ricorsiva con errore
  ≤ 6·10⁻¹⁶; ESG statici; 300/300 pesi pubblicati ricalcolabili; `gini_delta` con pendenza nulla
  (p = 0,80).
- **Malus a effetto nullo sul comportamento onesto**: `Psi = 1` su 330/330 celle e invarianti
  tutti veri.
- **Nessun canale di influenza nascosto**: i residui di quota non dipendono da guadagno, entrate,
  restituzioni o attività (|Spearman| ≤ 0,08, p ≥ 0,17).
- **Concentrazione aggregata allineata al teorico**: HHI 0,204 contro 0,207, N_eff 4,90, Nakamoto
  1/2 = 3 in entrambi.

## 5. Punti critici / da approfondire

- **Degrado progressivo della liveness (priorità massima).**
  - **Entità**: il block time passa da 11,05 s (ep. 2) a 60,7 s (ep. 66), con media 18,36 s
    contro 10 s; `Phi` è saturato all'88 % sopra h = 5000; i blocchi propri entrano nel tip del
    produttore con 23–38 s di ritardo mediano a fine run.
  - **Ipotesi**: un costo di elaborazione locale che cresce con la catena, candidato principale
    la rilettura completa del registro `wpoa-weights` (`ReadAllRecords`, un `GetWalletTx` per
    record) ripetuta molte volte per round sulla lettura "as of block" introdotta in `4cefac9d`.
    Il polling RPC della pipeline (`wpoalist*`, malus e registro campionati circa 16 volte per
    altezza per nodo: 545 580 campioni) moltiplica le chiamate, e con blocchi più lenti ce ne
    sono di più per altezza. Carico dell'host e rete sono esclusi come causa principale: la run
    regionale parallela resta stabile a 9 s e `S1` vale 31 ms.
  - **Per confermare**: cronometrare dentro `ReadAllRecords` (durata e numero di chiamate per
    altezza, con `-wpoadebug` o un contatore); ripetere 1000–2000 blocchi con il polling della
    pipeline disattivato o diradato; confrontare con un binario precedente a `4cefac9d`, oppure
    con una cache per `(max_block, tip)`; rendere leggibile il `debug.log` della run regionale
    per capire perché lì non si manifesti.
- **La pipeline conta blocchi orfani come vinti (bug di raccolta, priorità alta).**
  - **Entità**: 756 altezze post-setup (11,7 %; 109, 187 e 460 per terzi), dove `blocks.csv` e
    `round_level.csv` hanno il primo blocco visto invece di quello finale, sempre di un miner
    diverso.
  - **Effetto**: il GoF aggregato passa da p = 3,5·10⁻⁵ a p = 0,066 sulla catena finale, e la
    pendenza dei log-rapporti da 0,81 a 1,09. Il ricalcolo del delay sui log privati ha 202
    round con `phi_s` preso dal tip sbagliato.
  - **Da fare**: far leggere a phase1 la catena finale (per esempio con `getblockhash` a fine run,
    o usando `block_sortition.csv`) e rigenerare phase2/phase3. Verificare se lo stesso difetto
    tocca le altre run con fork frequenti, a partire da quella regionale 202430Z.
- **Inversioni della timer race elevate e crescenti.**
  - **Entità**: sulla catena finale sono l'8,9 %, il 15,9 % e il 36,4 % per terzi di run; il
    67,5 % va all'incumbent. Nelle epoche 2–22 le inversioni sono nulle quando il designato è
    l'incumbent (0/431).
  - **Ipotesi**: M2 (§3.5.1(d)) riproduce tutte le firme con un vantaggio che cresce nel tempo.
    (i) Un vantaggio di circa 0,5 s del produttore del blocco precedente, che arma il proprio
    timer prima degli altri, spiega il tratto sano, come nella run regionale. (ii) Il ritardo
    di elaborazione crescente porta il vantaggio fino a circa 2 s e aggiunge un jitter di circa
    2 s.
  - **Per confermare**: ripetere la ricostruzione dopo la correzione della liveness. Se il tasso
    resta a circa il 9 % con l'81 % all'incumbent, isolare (i) ancorando il timer al tempo di
    catena anche per il produttore.
- **Eccesso residuo di rigetti per epoca sulla catena finale (GoF 9/65 contro 3,25; Wilson 28
  contro 16).**
  - **Ipotesi**: la dipendenza fra round consecutivi indotta dall'incumbent (ripetizione 0,340
    contro 0,208) viola l'ipotesi multinomiale i.i.d. del test.
  - **Per confermare**: un GoF con riferimento Monte Carlo che includa il vantaggio `h`, oppure i
    test di quota rifatti usando l'argmin privato come vincitore. Quest'ultimo (§3.5.1(a)) dà
    χ² p = 0,057 sull'aggregato.
- **Ripetizioni in eccesso (0,340 sulla catena finale contro 0,208; nella pipeline 0,354,
  significative in 55/65 epoche).**
  - **Ipotesi**: la stessa del punto sulle inversioni (incumbent). Non è un difetto del seed:
    l'argmin vero non ha memoria.
  - **Per confermare**: una run di controllo dopo il fix del vantaggio dell'incumbent.
- **Offset residuo del block time anche nel tratto sano (circa 11,3 s contro 10 s).**
  - **Ipotesi**: circa 1 s di latenza di ricezione/validazione per blocco, oltre il margine di
    correzione di `lambda = 0,3`.
  - **Per confermare**: confronto con la run a 10 miner del 18/09 (11,2–11,8 s) a parità di
    parametri; eventualmente un `lambda` più alto entro il vincolo `Delta_max ≤ T − lambda·M`.
- **Retroazione inter-epoca inerte (`rho` ≤ 0,007).**
  - **Ipotesi**: il seed di 84 200 GAS per miner domina il `saldo`, per cui il fattore resta
    ≈ 0,5 costante.
  - **Per confermare**: una run con seed GAS proporzionato alle restituzioni (o con `saldo`
    misurato al netto del funding), per poter osservare il canale `rho → peso`.
- **Run incompleta e raccolta dello stream persa dall'epoca 63.**
  - **Entità**: 6660/10120 altezze; stream items a zero per le epoche 64–66 per timeout RPC.
  - **Per confermare/risolvere**: rilanciare dopo il fix della liveness. Con la run attuale,
    basare le conclusioni sulle epoche 2–40, dove il block time è ≤ 15,8 s e l'inversione vera è
    circa il 9–16 %.

## 6. Conclusione

La run conferma la **correttezza del nucleo crittografico e statistico** di wPoA e mette in
luce un **problema di prestazioni che ne compromette la seconda metà**.

- **Affidabilità della sortition — conforme nel meccanismo e nell'aggregato, degradata per
  epoca.**
  - L'argmin privato è indipendente dal round precedente (20,97 %).
  - Sulla **catena finale** le quote aggregate aderiscono al peso: χ² p = 0,066, MAE 0,63 pp,
    pendenza 1,09.
  - La compressione e il rigetto aggregato riportati dalla pipeline sono un artefatto dei 756
    blocchi orfani in `blocks.csv`.
  - Restano il 19,2 % di inversioni (36 % nell'ultimo terzo, 67 % a favore dell'incumbent) e un
    eccesso di rigetti per epoca: sono effetti della timer race, non della selezione.
- **Qualità della randomness — conforme.** Minimo di `score_norm` uniforme (`sqrt(n)·D = 0,74`),
  `E_i` a media 0,985 con KS non rigettato, Prop. 5.17 con medie 0,95–1,02. Sugli score privati di tutti i miner `E_i` ha media 1,0005 e
  l'argmin ha `score_norm` medio 0,502. Il rigetto di Q2 è interamente spiegato dalle inversioni
  a favore dell'incumbent.
- **Efficacia dello smorzamento — conforme.** `sqrt` comprime la quota del più pesante da 29,0 %
  a 24,5 % senza toccare l'ordinamento; con pesi entro un fattore 2,8 l'effetto è moderato, come
  atteso.
- **Efficacia del malus — conforme (caso senza violazioni).** Effetto esattamente nullo: `Psi = 1`
  ovunque, invarianti veri, 300/300 pesi verificati. L'efficacia sanzionatoria non è testata in
  questa run.
- **Stabilità del block time — non conforme.** 18,36 s medi contro 10 s, con deriva monotona fino
  a 60 s e `Phi` saturato. La causa è un rallentamento di elaborazione locale che cresce con la
  catena, non la rete né la sortition. Va risolto prima di usare run lunghe di questo profilo
  come evidenza quantitativa. Per la tesi, le epoche 2–40 di questa run sono utilizzabili con la
  cautela sulle inversioni; le epoche 45–66 no.
