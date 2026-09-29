# Analisi della run run-wpoa-core-regional-20260922T202430Z

Run: `test/results/run-wpoa-core-regional-20260922T202430Z`
Timestamp UTC della run: 2026-09-22T20:24:30Z
Catena: `wpoa-core-regional` — profilo: `test/config/profiles/core/regional-long23h.yaml` — regime: core
Analisi prodotta il: 2026-09-24

> **Premessa metodologica.** Il sistema è stocastico su più livelli indipendenti: score ESG
> estratti a caso in `[1,100]`, traffico aziendale e restituzioni estratti a caso a ogni epoca,
> VRF a ogni round, rete emulata (CORE, mappa `regional`). Tutto ciò che deriva dal `seed`
> (20260905) resta comunque un campione. Nessun giudizio si basa su singoli blocchi, round o
> epoche: solo su aggregati, con bande di confidenza e correzione per confronti multipli
> (`alpha = 0.05`; con `N` test sono attesi `0.05·N` rigetti).
>
> **Convenzione di etichettatura:** miner-0 (1F31QwpRoyGZ…), miner-1 (1XvxvAmi1h7V…),
> miner-2 (15rMLFBsfmJX…), miner-3 (1JRwbjzscU6V…), miner-4 (1NQkZTSTW2LX…).

## 1. Configurazione della run

| parametro | valore | fonte (file) |
|---|---|---|
| nome catena | `wpoa-core-regional` | `manifest.json` → `chain_name`; `analysis/phase1/config.csv` |
| seed esperimento | 20260905 | `manifest.json` → `seed` |
| profilo | `test/config/profiles/core/regional-long23h.yaml` | `manifest.json` → `profile_path` |
| regime | `core` (emulazione di rete CORE) | `manifest.json` → `fabric.backend` |
| topologia | `regional`: 20 siti, 7 hub, 34 link; latenza peggiore 5,137 ms (RTT 10,3 ms) | `manifest.json` → `fabric.topology.*`, `derived.worst_path_delay_ms` |
| nodi per ruolo | 1 admin, 2 CA, 5 miner, 30 aziende (38 in totale) | `manifest.json` → `nodes.*` |
| cluster | 6 aziende per miner, round-robin (`company-k → miner-(k mod 5)`) | `clusters.json` |
| epoche | 100 × 100 blocchi (misurate 2–101; la 1 è in setup) | `manifest.json` → `epochs.*`, `measured_epochs = 101` |
| altezza finale / target | 10 124 sulla catena (10 120 raccolte = `derived.target_height`) | `manifest.json` → `final_height`; `analysis/phase1/manifest.json` |
| esito | `status = ok`, `error = ""` | `manifest.json` |
| **funzione di smorzamento** | `none` (`g(w) = w`) | `config.csv` → `dump-function` |
| `target-block-time` `T_block` | 8 s | `config.csv` |
| banda del delay `delta` | 0,5 ⇒ `Delta_max = 4 s`, banda `[4, 12] s + lambda·Phi` | `config.csv` → `wpoa-sortition-delta` |
| guadagno correzione globale `lambda` | 0,3 | `config.csv` → `wpoa-sortition-lambda` |
| bound del feedback `M` | `min(0,5·8 ; 8·(1−0,5)/0,3) = min(4 ; 13,33) = 4 s` | ricavato |
| vincolo di ammissibilità | `Delta_max = 4 ≤ T_block − lambda·M = 6,8` ✓ | ricavato |
| parametri malus | `mu = 0,5`, `M_max = 4`, punti Equiv 4 / BadWeight 2 / SelfWrite 1 / Delay 0,25 | `config.csv` → `wpoa-malus-*` |
| stato malus | meccanismo **attivo** (`enable-wpoa-malus = true`); **nessuna violazione iniettata** (`malicious.enabled = false`, `malicious_miner_ids = []`) | `config.csv`; `malicious_manifest.json` |
| weight engine | `weight-kappa = 100`, `weight-lambda` (`lambda_w`) = 0,5, `weight-alpha = 0,2` (**inerte**, non letto dal binario) | `config.csv` |
| `setup-first-blocks` | 220 (richiesto 220, floor di protocollo 109) | `config.csv`; `manifest.json` → `derived.*` |
| `mining-diversity` | 0,0 (non vincolante) | `config.csv` |
| `mining-turnover` | 0,5 (euristica locale, senza effetto su wPoA) | `config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 3 500 000 GAS (premine dell'admin) | `config.csv` |
| funding dei miner | `miner_seed_gas = 600 200` GAS per miner | `manifest.json` → `derived.miner_seed_gas` |
| lookback RANDAO | 101 | `config.csv` → `wpoa-randao-lookback` |
| traffico | aziende `[30, 60]` tx/epoca sullo stream `supply-chain-events`; restituzioni miner `[0, 20]`/epoca da `[50, 250]` GAS; ESG in `[1, 100]` | `manifest.json` → `traffic.*` |
| opzioni runtime rilevanti | `fork_score = true`, `sortition_miner_log = true`, `wpoa_debug = false` | `manifest.json` → `runtime.*` |
| piano malicious | `enabled = false`, `miner_count = 0`, `target_action_rate = 0` | `malicious_manifest.json` |

Nessuna divergenza fra `manifest.json → effective_chain_params` e `analysis/phase1/config.csv`.
L'unica differenza è l'altezza: la catena è arrivata a 10 124 (`shutdown.json`), la pipeline
ha raccolto fino al target 10 120. I 4 blocchi in più sono stati prodotti durante lo shutdown
e non contano.

**Pesi alla prima epoca misurata (epoca 2).** Non sono una configurazione: vengono dalla
pipeline ESG × `tau` e dipendono dal campione di traffico estratto. Fonti:
`analysis/phase1/esg_events.csv`, `analysis/phase2/epoch_engine.csv`.

| validatore | ESG miner | `tau_M` | `Σ c_i` | `W_k_raw` | `rho_prev` | `w_k_final` | `w_k_published` (×100) |
|---|---:|---:|---:|---:|---:|---:|---:|
| miner-0 (1F31QwpRoyGZ…) | 29 | 16 | 105,10 | 3 511,90 | 0 | 1 755,95 | 175 595 |
| miner-1 (1XvxvAmi1h7V…) | 56 | 21 | 91,93 | 6 324,08 | 0 | 3 162,04 | 316 204 |
| miner-2 (15rMLFBsfmJX…) | 75 | 5 | 97,65 | 7 698,75 | 0 | 3 849,38 | 384 938 |
| miner-3 (1JRwbjzscU6V…) | 55 | 6 | 141,16 | 8 093,80 | 0 | 4 046,90 | 404 690 |
| miner-4 (1NQkZTSTW2LX…) | 49 | 4 | 183,37 | 9 181,13 | 0 | 4 590,57 | 459 057 |

Quote spettanti medie sull'intera run (ponderate per blocco): miner-2 0,2652, miner-4 0,2570,
miner-3 0,2277, miner-1 0,1537, miner-0 0,0965. Fra massimo e minimo c'è un fattore **2,75**:
non c'è una balena, e l'intervallo è quello tipico descritto per queste run.

## 2. Executive summary

- **I test di randomness sul punteggio pubblico passano.** `E_i` ha media 1,0042 (banda ±0,0088)
  con `√n·D = 0,94 < 1,36`. Il minimo di `score_norm` per round ha media 0,5036 con
  `√n·D = 0,75`. Normalizzazione e delay ricalcolati coincidono al 100 % (errore massimo
  3,6·10⁻¹⁵ s). Prop. 5.17 torna per ogni vincitore (media del gap 0,993–1,052, KS p ≥ 0,14).
- **Sull'intera run la sortition è proporzionale al peso effettivo.** Chi-quadro aggregato
  p = 0,755, TV = 0,006. Ogni quota aggregata cade dentro il proprio intervallo di Wilson, e lo
  scarto massimo è +0,47 punti percentuali (miner-4).
- **Punto critico principale: il miner del blocco precedente è avvantaggiato.** La probabilità
  di ripetizione è 0,326 contro 0,223 attesa (+46 %). Il test rigetta in 74 epoche su 100
  (MC p = 0,0001 sull'aggregato). I log mostrano che il miner uscente fa partire il timer del
  round successivo circa 1 s prima degli altri. Questo vantaggio spiega, con un solo meccanismo:
  il rigetto del KS sul punteggio vero del vincitore (5,1 % di vittorie con `score_norm > 0,99`
  contro 1 % atteso; il 96 % sono ripetizioni), `beta1 = 1,20` nel GLM, 35 violazioni di Wilson
  su 500 contro 25 attese (p = 0,03) e 9 rigetti GoF su 100 contro 5 attesi (p = 0,063).
- **Inversioni reali: il designato vince l'89,0 % dei round.** L'argmin è stato ricostruito dagli score VRF privati di tutti e 5 i validatori (§3.5.1). Nei restanti 1 088 round (11,0 %) vince un altro, nell'84 % dei casi il miner uscente, con timer più lento di al massimo 2,05 s. Tutte le 1 614 fork (16,3 %) si sono risolte verso il blocco di score minimo, senza riorganizzazioni di profondità ≥ 2 e senza fork irrisolte; il tie-break ha evitato circa 721 inversioni. La Prop. 5.18 con il rumore di rete dà un bound dello 0,9 % ed è **violata** di 12×, perché il rumore reale non è a media nulla: è un vantaggio sistematico di circa 0,65 s del miner uscente.
- **Il block time medio è 9,07 s contro 8 s (+13 %).** È stabile nel tempo (deriva di 0,0014 s
  per epoca). `Phi` non è né saturato (min −3,17 contro `M = 4`) né oscillante. Lo scarto è
  l'errore a regime atteso da una correzione solo proporzionale di fronte a un ritardo
  sistematico di 1,34 s: `8 + 1,34/(1 + 0,3) = 9,03 s`.
- **Malus: effetto esattamente nullo, come atteso senza violazioni iniettate.** `M = 0` e
  `Psi = 1` in tutte le 505 celle, `w_eff = w_raw` in 49 990 righe su 49 990, 3 invarianti su 3
  verdi.
- **Weight engine: aritmetica esatta** (identità verificate a 4·10⁻¹⁶). La **retroazione `rho`
  è però di fatto inerte**: `rho ≤ 0,006`, perché il saldo contiene i 600 200 GAS di funding.
- **Integrità:** tutti gli 8 check critici passano. Il FAIL non critico sul traffico
  (764/3 465) è un artefatto di raccolta: `stream_items` è troncato a 100 000 elementi.

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

> Le colonne `score_*_public` di `candidate_long.csv` sono lo score pubblico
> `HMAC-SHA256(seed, indirizzo)`. Verificano la *formula* (A.1–A.3), non chi ha vinto davvero.
> Il test sul punteggio **vero** è Q2 in [analysis/phase3/timer_race.md](analysis/phase3/timer_race.md).

**A.1 — `E_i ~ Exp(1)`**
- **File**: [analysis/phase2/candidate_long.csv](analysis/phase2/candidate_long.csv), `E_i = score_public × weight_effective`, righe con `in_setup = False`
- **Cosa misura**: la variabile esponenziale grezza, prima della divisione per il peso.
- **Osservato**: n = 49 425 (9 885 round × 5 candidati). Media 1,0042, sd 1,0050, KS `D = 0,00425`, `√n·D = 0,944`. Per validatore le medie vanno da 0,9983 (miner-1) a 1,0091 (miner-4), con `√n·D` fra 0,80 e 1,17 (n = 9 885 ciascuno).
- **Atteso**: media 1 ± 1,96/√n = 1 ± 0,0088; sd 1; `√n·D ≤ 1,358`.
- **Giudizio**: **conforme**. Scarto della media +0,42 %, dentro la banda al 95 %. Il KS è a 0,94 contro un critico di 1,36, e resta sotto il critico per ciascuno dei 5 validatori.

**A.2 — `score_norm` dell'argmin `~ U(0,1)` (Prop. 5.11), score pubblico**
- **File**: `candidate_long.csv`, minimo di `score_norm_public` per `height`
- **Cosa misura**: l'uniformità dello score normalizzato del vincitore *designato*.
- **Osservato**: n = 9 885, media 0,5036, `√n·D = 0,750`. Sulle righe `is_winner = True` la media è invece 0,822: lo score pubblico è indipendente da quello VRF con cui si è votato, quindi questo numero non va letto come un difetto.
- **Atteso**: media 0,5, `√n·D ≤ 1,358`.
- **Giudizio**: **conforme**. Scarto della media +0,7 %, KS a 0,75 contro 1,36.

**A.2-bis — Q2 sul punteggio vero del vincitore (reveal VRF del blocco)**
- **File**: [analysis/phase2/round_level.csv](analysis/phase2/round_level.csv) (`score_norm_true`), [analysis/phase3/timer_race.md](analysis/phase3/timer_race.md)
- **Cosa misura**: se il blocco sulla catena finale l'ha prodotto l'argmin della sortition. Se sì, `score_norm_true ~ U(0,1)`.
- **Osservato**: n = 9 685, media **0,5012**, ma KS `D = 0,0419`, `√n·D = 4,13`: rigetto. Lo scostamento è tutto in coda: ECDF(0,95) = 0,925 e ECDF(0,99) = 0,949, cioè il **5,1 %** dei vincitori ha `score_norm > 0,99` contro l'1 % atteso. Sotto 0,9 l'ECDF segue la diagonale entro 0,01 (ECDF(0,1) = 0,101; ECDF(0,5) = 0,5025; ECDF(0,7) = 0,701). Dei 505 blocchi con `score_norm > 0,99` ([analysis/phase1/block_sortition.csv](analysis/phase1/block_sortition.csv)), il **95,8 %** è una ripetizione del miner del blocco precedente. Fra le vittorie senza ripetizione, solo lo 0,31 % supera 0,99. La pipeline separa i round "vinti al top della banda" (439, 4,4 %) dai round in cui si è corsa la gara (media 0,478, KS rigettato). Quella separazione però è un **troncamento** della coda alta, e la media attesa di un'uniforme troncata a 0,956 è appunto 0,478: il rigetto sulla sotto-popolazione non aggiunge informazione.
- **Atteso**: `U(0,1)` esatta se vince sempre l'argmin.
- **Giudizio**: **scostamento significativo da indagare**, ma **non è un difetto della VRF**. A.1 e A.2 sono puliti e la media è 0,50. L'eccesso riguarda solo la coda `> 0,99`, cioè round in cui nessun altro candidato ha prodotto prima che scadesse il timer quasi massimo (≈ 11,7 s) del miner uscente. È la firma del vantaggio dell'incumbent (§3.5, §3.9).

**A.3 — coerenza della normalizzazione**
- **File**: `candidate_long.csv` → `score_norm_mismatch_public`
- **Osservato**: 0 righe non nulle su 49 425; massimo 2,2·10⁻¹⁶.
- **Atteso**: 0 entro tolleranza.
- **Giudizio**: **conforme** (esatto alla precisione di macchina).

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv) (`delay_recompute_mismatch_rounds_is_zero`), `wpoa_epoch_tests.csv` → `delay_recompute_mismatch_rounds`, [analysis/plots/delay_recompute_mismatch.png](analysis/plots/delay_recompute_mismatch.png)
- **Cosa misura**: `D_i` ricalcolato dalla pipeline con la formula di §1.3(c), confrontato con quello loggato dal nodo.
- **Osservato**: 0 round in disaccordo in tutte le 100 epoche; 0 su 49 990 righe candidato-round oltre la tolleranza. Scarto massimo 3,6·10⁻¹⁵ s. Nella figura tutti i punti stanno fra 10⁻¹⁸ e 10⁻¹⁴ s, dodici ordini di grandezza sotto la soglia di 1,5 ms.
- **Atteso**: 0 con tolleranza 1,5 ms.
- **Giudizio**: **conforme**. Harness e nodo concordano esattamente sul meccanismo.

### 3.3 Quota di blocchi contro peso

Con `dump-function = none` e `Psi ≡ 1`, `w_eff = w_raw`
([analysis/phase1/round_final_weights.csv](analysis/phase1/round_final_weights.csv): 49 990 righe
su 49 990 con `effective_weight_after_malus_and_dumping = raw_weight`). La quota attesa è
quindi `w_i / Σ w`, linearmente e senza compressione.

**Confronto aggregato**
- **File**: [analysis/phase3/weight_vs_election.md](analysis/phase3/weight_vs_election.md) (sezione "Pooled"), [analysis/plots/election_share_distribution.png](analysis/plots/election_share_distribution.png)
- **Osservato** (9 921 blocchi):

| validatore | `p_theoretical` | `p_hat` | Wilson 95 % | dentro? |
|---|---:|---:|---|---|
| miner-2 (15rMLFBsfmJX…) | 0,2652 | 0,2664 | [0,2578; 0,2752] | sì |
| miner-4 (1NQkZTSTW2LX…) | 0,2570 | 0,2617 | [0,2531; 0,2704] | sì |
| miner-3 (1JRwbjzscU6V…) | 0,2277 | 0,2263 | [0,2182; 0,2346] | sì |
| miner-1 (1XvxvAmi1h7V…) | 0,1537 | 0,1509 | [0,1440; 0,1581] | sì |
| miner-0 (1F31QwpRoyGZ…) | 0,0965 | 0,0944 | [0,0888; 0,1004] | sì |

  Chi-quadro aggregato 1,895 (df 4), **p = 0,755**; round-by-round MC p = 0,719; `MAE_p = 0,0024`, `TV = 0,0060`. La torta cumulativa (26,6 / 26,2 / 22,6 / 15,1 / 9,4 %) riproduce l'ordinamento dei pesi.
- **Atteso**: `p_hat ≈ w_i/W_tot`; ordinamento preservato.
- **Giudizio**: **conforme**. Aderenza entro 0,5 punti percentuali per ogni validatore, e ordinamento osservato identico a quello dei pesi. C'è una leggera inclinazione a favore dei pesanti (miner-4 +0,47 pp, miner-0 −0,21 pp): è quella prevista dal meccanismo di §3.5, ma sta dentro la banda.

**Intervalli di Wilson per (epoca, validatore)**
- **File**: [analysis/phase3/weight_election_wilson_coverage.csv](analysis/phase3/weight_election_wilson_coverage.csv), [analysis/phase3/wpoa_epoch_validators.csv](analysis/phase3/wpoa_epoch_validators.csv), [analysis/plots/wilson_violation_heatmap.png](analysis/plots/wilson_violation_heatmap.png), [analysis/plots/weight_vs_election.png](analysis/plots/weight_vs_election.png)
- **Osservato**: **35 violazioni su 500** contro 25 attese (binomiale esatta P(X ≥ 35) = 0,030). Larghezza media dell'intervallo **0,152**: è la risoluzione per epoca. Le violazioni sono sparse, senza cluster: 10 per miner-3, 9 per miner-4, 6 per miner-1 e miner-2, 4 per miner-0, in 28 epoche diverse, al massimo 2 per epoca. Nello scatter di `weight_vs_election.png` i punti si allineano sulla diagonale, raggruppati per validatore.
- **Atteso**: circa il 5 % (25) per caso.
- **Giudizio**: **lieve scostamento**. L'eccesso è di 10 violazioni (+40 %), al limite della significatività. È compatibile con la sovradispersione dei conteggi `O_i` causata dalle ripetizioni (§3.9): vittorie consecutive correlate aumentano la varianza di `O_i` rispetto alla binomiale su cui è costruito Wilson.

**Goodness of fit per epoca**
- **File**: [analysis/phase3/wpoa_epoch_tests.csv](analysis/phase3/wpoa_epoch_tests.csv), [analysis/phase3/weight_election_pvalue_uniformity.csv](analysis/phase3/weight_election_pvalue_uniformity.csv), [analysis/plots/p_value_uniformity.png](analysis/plots/p_value_uniformity.png)
- **Osservato**: 9 rigetti su 100 (epoche 15, 22, 41, 42, 49, 78, 88, 94, 99) contro 5 attesi; binomiale sul conteggio p = 0,063; KS dei p-value contro U(0,1) `D = 0,120`, p = 0,102. `share_changes_within_epoch = True` in tutte le 100 epoche, quindi la colonna da leggere è `gof_mc_round_by_round_p`: anche lì 9 epoche sotto 0,05, con valori quasi identici a quelli del test multinomiale. L'istogramma ha 16 epoche nel primo decile contro 10 attese, e il resto è piatto. `MAE_p` medio per epoca 0,035; `TV` medio 0,087.
- **Atteso**: circa 5 rigetti, p-value uniformi.
- **Giudizio**: **lieve scostamento**. L'uniformità dei p-value non è rigettata (p = 0,10) e il conteggio lo è solo marginalmente (p = 0,063). L'accumulo nel primo decile è coerente con la stessa sovradispersione.

### 3.4 Comportamento longitudinale

- **File**: [analysis/phase3/longitudinal.md](analysis/phase3/longitudinal.md), [analysis/phase3/wpoa_longitudinal_fits.csv](analysis/phase3/wpoa_longitudinal_fits.csv), [analysis/phase3/wpoa_longitudinal_validators.csv](analysis/phase3/wpoa_longitudinal_validators.csv), [analysis/plots/longitudinal_logratio.png](analysis/plots/longitudinal_logratio.png), [analysis/plots/sign_test_by_validator.png](analysis/plots/sign_test_by_validator.png)

**GLM logit su log(peso)**
- **Osservato**: `beta1 = 1,2045`, IC 95 % [1,140; 1,269], n = 500, `converged = True`, `beta1_consistent_with_1 = False`.
- **Atteso**: `beta1 = 1`.
- **Giudizio**: **scostamento significativo da indagare**, di entità moderata: la quota risponde al peso **più** che proporzionalmente, del 20 %. Non è una compressione (il caso tipico da latenza, `beta1 < 1`) ma un'amplificazione. È coerente con il vantaggio dell'incumbent: i validatori pesanti vincono più spesso e quindi partono più spesso avvantaggiati nel round successivo. Due cautele. (i) Il GLM assume osservazioni binomiali indipendenti: con le ripetizioni in eccesso l'IC è troppo stretto. (ii) Sull'aggregato l'amplificazione è piccola (+0,47 pp al massimo). Per confronto, la run regional precedente (`run-wpoa-core-regional-20260922T053033Z`, interrotta a 2 886 blocchi, 19 epoche, T = 12 s) dava `beta1 = 0,51` con n = 95: con meno epoche e pesi quasi statici il GLM è instabile, e il suo valore non va letto da solo.

**Regressione dei log-rapporti**
- **Osservato**: pendenza 1,057, intercetta 0,0055, Pearson r = 0,862 (p ≈ 0), n = 1 000 coppie. Nella figura la retta stimata è appena più ripida della diagonale.
- **Atteso**: pendenza 1, intercetta 0.
- **Giudizio**: **lieve scostamento**. Pendenza +5,7 %, intercetta praticamente nulla, r alto (relazione corretta e ben determinata). Il valore coincide con quello simulato per un vantaggio dell'incumbent fra 0,5 e 1 s (pendenza 1,03–1,06, §3.5).

**Sign test per validatore**
- **Osservato**: concordanza fra 0,50 e 0,60. p = 0,54 (miner-2), 0,11 (miner-0), 0,15 (miner-3), 0,11 (miner-4), 0,032 (miner-1).
- **Atteso**: con 5 test, 0,25 rigetti per caso.
- **Giudizio**: **lieve scostamento / conforme**. Un solo p sotto 0,05 (miner-1), non significativo dopo Bonferroni (0,032 > 0,01). Il potere è basso perché i pesi sono stazionari (§3.7): le variazioni epoca su epoca sono piccole rispetto al rumore di 100 blocchi.

**Prima contro ultima epoca**: `intervals_overlap = True` per 5 validatori su 5. L'ultima epoca (101) ha 21 blocchi e non è informativa.

### 3.5 Timer race, margine e inversioni

**Margine G**
- **File**: [analysis/phase3/wpoa_timer_race.csv](analysis/phase3/wpoa_timer_race.csv), [analysis/plots/margin_distribution.png](analysis/plots/margin_distribution.png)
- **Osservato**: `G` medio 2,260 s (mediana 1,767) contro 2,2715 s simulati; KS contro la distribuzione esatta simulata **p = 0,705**. Il KS contro `Beta(1,n)` dà p = 0 con media attesa 1,333 s, ma è lo straw man dichiarato dalla pipeline. La densità decresce in modo monotono da 0 a 8 s (= `2·Delta_max`).
- **Atteso**: aderenza alla simulazione esatta; il `Beta(1,n)` deve rigettare con pesi non uniformi.
- **Giudizio**: **conforme** (scarto della media −0,5 %, KS p = 0,71). Il rigetto `Beta(1,n)` **non è un rilievo**.

**Prop. 5.17**
- **File**: [analysis/phase3/wpoa_prop517.csv](analysis/phase3/wpoa_prop517.csv), [analysis/plots/prop517_gap_by_validator.png](analysis/plots/prop517_gap_by_validator.png)
- **Osservato**: gap standardizzato medio 0,993 (miner-3, n = 2 240), 0,998 (miner-1), 1,014 (miner-4), 1,023 (miner-2), 1,052 (miner-0, n = 932). KS p = 0,87 / 0,81 / 0,19 / 0,36 / 0,14. Nessuna barra arancione nella figura.
- **Atteso**: media 1, KS non significativo.
- **Giudizio**: **conforme**. Scarti ≤ 5,2 % e nessun rigetto su 5 test.

**Decomposizione del rumore**
- **File**: [analysis/phase3/wpoa_sigma.csv](analysis/phase3/wpoa_sigma.csv), [analysis/plots/sigma_decomposition.png](analysis/plots/sigma_decomposition.png)
- **Osservato**: `S1_topology = 0,000377 s`. Il valore è misurato, non assente: in regime core, con una latenza peggiore di 5,1 ms, la propagazione è trascurabile. `S2_scheduler_residual_sd` (pubblico) = 3,09 s; `S2b_inversion_gap` = 1,90 s. Sul punteggio vero, il residuo `dt_prev − delay_true` ha media **+1,341 s** e sd **0,825 s**, con `corr(dt_prev, delay_true) = 0,938`.
- **Atteso**: la sorgente primaria è lo scheduler, non la rete.
- **Giudizio**: **conforme** sulla gerarchia delle sorgenti. Il rumore di rete è 2 000 volte più piccolo del residuo di scheduling. L'S2 pubblico va letto come audit del modello, non come misura del rumore vero (la sd vera è 0,82 s).

**Inversione e bound di Prop. 5.18**
- **File**: `wpoa_timer_race.csv`, `wpoa_epoch_tests.csv` (`inversion_public_*`), [analysis/plots/inversion_bound_vs_observed.png](analysis/plots/inversion_bound_vs_observed.png)
- **Osservato**: tasso di inversione pubblico 0,777 (7 680 round su 9 885); per epoca fra 0,70 e 0,87, pendenza 7·10⁻⁵ per epoca, cioè nessuna crescita. Bound = **1,0**. MC con `sigma_S2` = 0,501.
- **Atteso**: lo score pubblico è indipendente da quello VRF, quindi l'inversione pubblica ha valore atteso `1 − Σp²` = 1 − 0,2226 = **0,777** qualunque cosa faccia il protocollo.
- **Giudizio**: il tasso osservato coincide esattamente con il valore di pura indipendenza, quindi **non è informativo**. Il bound saturato a 1,0 è **vacuo**, non una conferma. L'inversione *vera*, misurata direttamente dagli score privati di tutti i validatori, è in §3.5.1: **11,0 %**.

**Vantaggio del miner uscente (diagnosi)**
- **File**: `round_level.csv` (`residual_true_s`), `block_sortition.csv`, `chains/miner-*/wpoa-core-regional/debug.log` (letti via `./docker/mcsim`, i file sono di root)
- **Osservato**:
  - Residuo medio `dt_prev − delay_true` = **0,66 s** quando vince di nuovo il miner uscente (3 083 round) e **1,66 s** negli altri round (6 601). Il miner uscente produce quindi il blocco circa **1,0 s prima** rispetto al proprio timer. Nel `debug.log` di miner-2, per l'altezza 3027, il timer parte alle 03:55:35 dopo aver ricevuto il blocco 3026 alle 03:55:34, mentre miner-0 (autore del 3026, `nTime` 03:55:33) arma il proprio timer alla creazione del blocco. Il blocco di miner-0 arriva alle 03:55:46, con `score_norm = 0,99999957` e delay 11,92 s, prima che scada il timer di miner-2 (11,41 s).
  - Monte-Carlo (5 validatori con le quote aggregate, 200 000 round, script nello scratchpad della sessione). Con vantaggio `h = 0` le ripetizioni sono 0,220 e i vincitori con `score_norm > 0,99` l'1,0 %. Con `h = 0,5 s` e jitter 0,5 s: 0,282 e 5,7 %. Con `h = 1,0 s` e jitter 0,5 s: 0,358 e 7,2 %, e pendenza dei log-rapporti 1,03. Sui dati: **0,326** e **5,1 %**, pendenza 1,057. Un vantaggio di 0,6–0,8 s riproduce quindi tutte e tre le firme insieme.
- **Giudizio**: **scostamento significativo da indagare** (vedi §5).

#### 3.5.1 Vincitore designato dalla sortition privata, inversioni reali e fork

> **Perché questa sezione.** Tutte le colonne `_public` della pipeline usano lo score pubblico
> HMAC, che è indipendente da quello VRF con cui si è votato. Il Q2 (§3.1) usa lo score vero,
> ma solo quello del vincitore. Qui invece l'argmin **vero** è ricostruito per ogni round
> dagli score privati di **tutti e 5** i validatori. Con `sortition_miner_log = true` ogni miner
> scrive nel proprio `debug.log`, per ogni altezza, la riga
> `mchn-miner: wPoA-sortition height=… tip=… score=… delay=…` con il proprio score VRF privato
> e il timer armato. Per ogni altezza `h` si tiene l'ultima riga il cui `tip` coincide con il
> blocco canonico `h−1`. Le fork sono ricostruite dalle righe `[wpoa-fork] cand` e
> `UpdateTip` dei `debug.log` di **tutti i 38 nodi**. Fonti:
> `chains/*/wpoa-core-regional/debug.log`, letti via `./docker/mcsim` perché sono di root, e
> [analysis/phase1/block_sortition.csv](analysis/phase1/block_sortition.csv) come catena canonica
> (coincide con la catena finale di tutti i nodi a ogni altezza). Round analizzati: **9 884**
> (altezze 221–10 120 con tutti e 5 gli score sul padre canonico).

**(a) La sortition privata, da sola, è esatta**
- **Cosa misura**: A.1, A.2 e Teorema 5.3 ripetuti sugli score VRF privati, cioè quelli che hanno davvero armato i timer, invece che sullo score pubblico.
- **Osservato**:
  - `E_i = score_privato × w_eff`: n = 49 420, media **1,0010** (banda ±0,0088), KS `√n·D = 0,778`. Per miner le medie vanno da 0,9963 a 1,0079, con `√n·D` fra 0,55 e 0,84.
  - `score_norm` dell'argmin privato: media **0,5004**, KS `√n·D = 0,531`.
  - Delay loggato dal miner contro `T + Delta_max·(2·score_norm − 1) + lambda·Phi` ricalcolato: scarto massimo 0,0005 s su 49 420 righe, pari all'arrotondamento a 3 decimali del log.
  - Quote dei vincitori **designati** contro la quota spettante: chi-quadro **1,22** (df 4, p = 0,87).

  | validatore | `p_theoretical` | quota designata (argmin) | quota realizzata (catena) |
  |---|---:|---:|---:|
  | miner-0 (1F31QwpRoyGZ…) | 0,0965 | 0,0979 | 0,0953 |
  | miner-1 (1XvxvAmi1h7V…) | 0,1536 | 0,1550 | 0,1519 |
  | miner-2 (15rMLFBsfmJX…) | 0,2653 | 0,2668 | 0,2654 |
  | miner-3 (1JRwbjzscU6V…) | 0,2277 | 0,2234 | 0,2260 |
  | miner-4 (1NQkZTSTW2LX…) | 0,2570 | 0,2569 | 0,2614 |

- **Atteso**: `Exp(1)` con media 1; `U(0,1)`; quote designate uguali a `w_i/W_tot` (Teorema 5.3).
- **Giudizio**: **conforme**. È il test più diretto possibile della VRF e della trasformazione di Efraimidis–Spirakis: KS a 0,78 e 0,53 contro un critico di 1,36, e chi-quadro p = 0,87. Anche la quota realizzata ha chi-quadro 1,21 (p = 0,88), perché le inversioni tolgono blocchi ai miner leggeri e li danno ai pesanti in misura piccola: da −0,31 a +0,45 pp.

**(b) Quanto spesso vince il designato**
- **Osservato**: il designato (argmin privato) ha prodotto il blocco canonico in **8 796 round su 9 884 (89,0 %)**. Nei restanti **1 088 (11,0 %)** ha vinto un altro validatore. Per epoca il tasso è in media 10,9 %, con range 0–19 % e pendenza −3,9·10⁻⁵ per epoca: nessuna crescita nel tempo.
- **Scomposizione dei 9 884 round**:

  | caso | round | quota | esito |
  |---|---:|---:|---|
  | nessuna fork, vince l'argmin | 7 306 | 73,9 % | corretto |
  | fork con l'argmin fra i candidati, vince l'argmin | 1 490 | 15,1 % | corretto, grazie al tie-break |
  | nessuna fork, vince un non-argmin | 964 | 9,8 % | **inversione**: l'argmin non ha mai pubblicato |
  | fork **senza** l'argmin fra i candidati | 124 | 1,3 % | **inversione**: la fork è fra due non-argmin |
  | fork con l'argmin presente, vince un non-argmin | **0** | 0 % | — |

- **Chi vince al posto del designato**: nel **83,5 %** dei casi (909 su 1 088) il **miner del blocco precedente**. Quando il designato è proprio il miner uscente (2 192 round), le inversioni sono **0**. Quando non lo è (7 692 round), sono il 14,1 %. Le 179 inversioni vinte da un non-incumbent cadono per il 44 % (78) in round con fork.
- **Distanza temporale fra vincitore e designato** (timer del vincitore − timer del designato): media 0,40 s, mediana **0,33 s**, p90 0,83 s, p99 1,57 s, massimo **2,05 s**. Nessuna inversione con uno scarto superiore a 2,05 s.
- **Inversione in funzione del margine vero** `G = D_(2) − D_(1)` (timer privati): 48,5 % per `G < 0,25 s`, 34,2 % in [0,25; 0,5), 15,5 % in [0,5; 1), 3,2 % in [1; 1,5), 1,0 % in [1,5; 2), 0,1 % in [2; 3) e **0** per `G ≥ 3 s` (3 064 round).
- **Chi ci perde**: il tasso di "argmin non eletto" è 13,3 % per miner-0 (il più leggero) e 10,5–11,5 % per gli altri. Il miner leggero è raramente incumbent, quindi raramente è protetto dal vantaggio.
- **Giudizio**: **scostamento significativo da indagare**. Un round su nove non va al designato. La firma è inequivocabile: le inversioni sono nulle quando il designato è l'incumbent e vanno all'incumbent nell'84 % dei casi, entro una finestra di circa 2 s. È l'effetto del vantaggio locale del miner uscente descritto sopra, non un errore della sortition, che al punto (a) è esatta.

**(c) Fork: frequenza, finestra e risoluzione**
- **Osservato**:
  - Round con fork (≥ 2 blocchi validi alla stessa altezza visti da almeno un nodo): **1 614 su 9 884 (16,3 %)**; 1 421 con 2 blocchi, 180 con 3, 12 con 4, 1 con 5. Per epoca fra l'8 e il 27 %, senza trend (pendenza +1,9·10⁻⁵).
  - **Risoluzione**: al termine della run tutti i 38 nodi hanno lo stesso blocco a ognuna delle 10 125 altezze comuni. In tutte le fork il blocco canonico è quello di **score minimo fra i candidati**, e ci si arriva sempre con uno scambio alla **stessa altezza** (29 755 scambi di un blocco sommati sui nodi). Riorganizzazioni di profondità ≥ 2 dopo il setup: **0**; le 49 osservate cadono alle altezze 135, 190 e 206, sotto il round robin nativo. Un tip orfano è restato attivo al massimo **2 s** su un nodo (mediana 0 s).
  - **Inversioni evitate dal tie-break**: in **721** fork (7,3 % dei round) il blocco dell'argmin **non** era il primo arrivato in rete, eppure ha vinto grazie allo score. Con la regola nativa (primo arrivato) le inversioni sarebbero state circa **1 809 (18,3 %)** invece di 1 088 (11,0 %). La stima prende come vincitore nativo il candidato con ricezione più precoce sull'insieme dei nodi. In 679 fork il primo arrivato era il blocco dell'incumbent.
  - **Finestra di fork** (5 541 round in cui nessuno dei due timer più rapidi è dell'incumbent): P(fork) vale 0,44–0,49 per `G < 1 s`, 0,40 in [1; 1,25), 0,25 in [1,25; 1,5), 0,17 in [1,5; 1,75), 0,07 in [1,75; 2), 0,02 in [2; 3) e 0 per `G ≥ 3 s`. Quando l'incumbent ha il timer più rapido, le fork sono solo il 2,3 % e le inversioni lo 0 %.
- **Lettura**: il secondo validatore pubblica un blocco concorrente se il suo timer scade prima di aver ricevuto **e processato** il blocco del primo. La finestra efficace è di **circa 1,5 s**, cioè circa 300 volte la latenza di rete peggiore della mappa (5,1 ms). Il ritardo che conta è quindi quello di **elaborazione locale del blocco** (validazione, `UpdateTip`, riavvio del miner loop), non quello di propagazione. È lo stesso ritardo che, per asimmetria, dà all'incumbent il suo vantaggio: lui il proprio blocco non deve riceverlo.
- **Giudizio**: **conforme sulla safety** (nessuna fork irrisolta, nessuna riorganizzazione profonda, convergenza in ≤ 2 s). La regola di tie-break per score fa esattamente ciò per cui è progettata: vince sempre l'argmin *fra i blocchi prodotti*, e le inversioni scendono da circa il 18 % a circa l'11 %. **Non può** correggere le 1 088 inversioni restanti, perché in quei round il blocco del designato non esiste. È il limite già noto della regola: agisce solo sui candidati osservati, sotto `nChainWork`.

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

qui con `n = 5` e `Delta_max = 4 s`.

| `sigma` usata | valore | bound Prop. 5.18 | osservato | esito |
|---|---:|---:|---:|---|
| `S1_topology` (propagazione sulla mappa) | 0,000377 s | **0,0091** (`t*` = 9,7 ms) | **0,1101** | bound **violato** di 12× |
| `sigma` che rende il bound = osservato | 0,0159 s | 0,1101 | 0,1101 | — |
| `sigma` del rumore simmetrico che riproduce il tasso (MC, sotto) | 0,40 s | 0,945 | 0,1101 | valido, ma largo 8,6× |
| residuo vero `dt_prev − delay_true` (sd) | 0,825 s | 1,53 | 0,1101 | vacuo (> 1) |
| `S2b_inversion_gap` | 1,90 s | 2,67 | 0,1101 | vacuo |
| `S2_scheduler_residual_sd` (pubblico) | 3,09 s | 3,69 | 0,1101 | vacuo |

- **Il termine di margine regge.** Il secondo addendo `n·t/(2·Delta_max)` maggiora `Pr[G < t]` con un'unione di eventi. Sui margini veri: `Pr[G < t]` = 0,053 / 0,111 / 0,198 / 0,341 / 0,445 / 0,536 per `t` = 0,1 / 0,25 / 0,5 / 1 / 1,5 / 2 s. Il termine vale 0,063 / 0,156 / 0,313 / 0,625 / 0,938 / 1,25, e l'approssimazione `Beta(1,n)` `1 − (1 − t/(2·Delta_max))^n` vale 0,061 / 0,147 / 0,276 / 0,487 / 0,646 / 0,763. La maggiorazione vale a ogni `t` ed è conservativa di 1,2–2,8×, perché i pesi non uniformi allargano il margine rispetto al caso uniforme. Il margine medio vero è 2,27 s, mediana 1,80 s.
- **È l'ipotesi sul rumore a cadere.** Il bound calcolato con il rumore di rete (`S1`) promette meno dell'1 % di inversioni; se ne osservano l'11 %. Non è una contraddizione della proposizione: la sua ipotesi, rumore indipendente a media nulla, non vale. Due modelli simulati sui **delay privati reali di ogni round** (9 884 round, 5–20 repliche):

  | modello | parametri | inversioni | quota vinta dall'incumbent | inversioni quando l'argmin è l'incumbent |
  |---|---|---:|---:|---:|
  | **osservato** | — | **0,110** | **0,835** | **0,000** (su 2 192) |
  | M1: rumore gaussiano i.i.d. a media nulla (ipotesi di Prop. 5.18) | `sigma = 0,40 s` | 0,112 | 0,204 | 0,119 |
  | M2: vantaggio `h` all'incumbent + rumore | `h = 0,6 s`, `sigma = 0,2 s` | 0,108 | 0,851 | 0,002 |
  | M2 | `h = 0,7 s`, `sigma = 0,1 s` | 0,116 | 0,947 | 0,000 |
  | M2 | `h = 0,7 s`, `sigma = 0` | 0,110 | 1,000 | 0,000 |

  M1 può riprodurre il tasso, ma solo con una `sigma` di 0,40 s, 1 000 volte quella di rete. Inoltre sbaglia la composizione: dà all'incumbent il 20 % delle inversioni invece dell'84 %, e prevede il 12 % di inversioni anche quando l'argmin è l'incumbent, dove se ne osservano 0 su 2 192. M2, con un **vantaggio sistematico di circa 0,6–0,7 s al miner uscente** e un jitter residuo di 0,1–0,2 s, riproduce tutte e tre le grandezze insieme.
- **Giudizio**: **scostamento significativo da indagare**, nel modello più che nel codice. La Prop. 5.18 resta corretta nel suo dominio, e il suo termine di margine è verificato empiricamente. Ma il rumore che guida le inversioni in questa implementazione **non è simmetrico**: è un bias deterministico legato al ruolo di incumbent, generato dal tempo di elaborazione locale del blocco (circa 0,6–1,5 s) e non dalla rete (0,4 ms). Per usare la proposizione come dimensionamento, `sigma` dovrebbe includere questa componente e il bias dovrebbe comparire esplicitamente, per esempio come termine `Pr[G < h]`. Con `sigma` = 0,40 s il vincolo `Delta_max ≳ n·sigma·eps^(−3/2)` per `eps = 0,05` richiederebbe `Delta_max ≈ 179 s`, incompatibile con `Delta_max ≤ T_block − lambda·M = 6,8 s`. L'unica leva praticabile è quindi eliminare il bias alla fonte, ancorando i timer al tempo di catena e non all'istante locale di ricezione del tip.


### 3.6 Stabilità del block time e correzione globale

- **File**: `round_level.csv` (`dt_prev_s`, `phi_s`, `delay_true_s`, `residual_true_s`), [analysis/phase1/round_delays.csv](analysis/phase1/round_delays.csv), [analysis/plots/phi_over_time.png](analysis/plots/phi_over_time.png)
- **Osservato**:
  - `dt_prev` sui 9 885 round non-setup: media **9,074 s**, sd 2,33, mediana 9, range [4, 23]. Medie per epoca fra 8,63 e 9,52; pendenza 0,0014 s per epoca (+0,14 s sull'intera run), quindi niente deriva.
  - `delay_true` medio 7,692 s, che corrisponde a `8 + lambda·E[Phi] = 8 − 0,318 = 7,682`.
  - `Phi`: media −1,059, sd 0,578, range [−3,17; +1,17], 50 valori distinti. **Mai a ±M = ±4 s** (massimo `|Phi|` 3,17 = 79 % di M). 183 cambi di segno su 9 884 transizioni (1,9 %). La mediana mobile nella figura resta piatta intorno a −1,0/−1,2 per tutta la run.
  - Code: 18 round con `dt ≥ 14 s` (0,18 %), fino a 23 s: **15 su 18 ad altezze ≡ 8 (mod 100)**, cioè 8 blocchi dopo l'inizio dell'epoca, e 15 su 18 dopo l'altezza 7 500. Il `dt` medio a quelle altezze vale 9,14 / 10,08 / 9,56 / **13,93 s** nei quattro quarti della run, contro circa 9,05–9,08 s altrove.
- **Atteso**: media verso `T_block = 8 s`; `Phi` non saturato e non oscillante.
- **Giudizio**: **lieve scostamento**, spiegato quantitativamente e non patologico. `Phi` non è saturato (79 % di M al massimo) e non oscilla (1,9 % di cambi di segno, segno stabilmente negativo): il controllo lavora nel verso giusto. La media resta però +1,07 s sopra il target, perché la correzione è solo proporzionale e deve compensare un ritardo sistematico `r = 1,34 s` fra lo scadere del timer e il timestamp del blocco (latenza di assemblaggio/validazione più quantizzazione a 1 s di `nTime`). In condizione di regime, `dt = T + lambda·(T − dt) + r` dà `dt = T + r/(1 + lambda) = 8 + 1,34/1,3 = 9,03 s`, che si confronta con 9,07 osservati. Il controllo quindi funziona come progettato, e con un guadagno puramente proporzionale non può azzerare l'errore. Il FAIL di `phi_consistent` (50 valori distinti) è **atteso** e non è un difetto. Lo stallo a inizio epoca che peggiora nel tempo va segnalato a parte (§5).

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

**Identità del motore**
- **File**: [analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv), [analysis/phase3/weight_engine_epoch.csv](analysis/phase3/weight_engine_epoch.csv)
- **Osservato**: `W_k_raw = ESG·(tau_M + Σc_i)` con errore relativo massimo 2,4·10⁻¹⁶ su 505 righe. `w_k_final = W_k_raw·(rho_prev·0,5 + 0,5)` con errore massimo 4,3·10⁻¹⁶. `w_k_published = 100·w_k_final` in ogni riga (scala intera del registro). [analysis/phase1/verification.csv](analysis/phase1/verification.csv): 420 verifiche su 420 `ok`, `|published − recomputed| = 0`.
- **Giudizio**: **conforme** (esatto).

**ESG statici**
- **File**: [analysis/phase1/esg_events.csv](analysis/phase1/esg_events.csv), [analysis/plots/esg_scores.png](analysis/plots/esg_scores.png) (+ `esg_scores/miner.png`, `esg_scores/company.png`)
- **Osservato**: 35 certificazioni (30 aziende, 5 miner), nessuna ri-certificazione. Un solo valore ESG per miner in 101 epoche (miner-0 29, miner-1 56, miner-2 75, miner-3 55, miner-4 49). Gli ESG aziendali coprono 4–99.
- **Giudizio**: **conforme**.

**Traiettoria dei pesi**
- **File**: [analysis/plots/weights_over_time.png](analysis/plots/weights_over_time.png), [analysis/plots/weights_boxplot_per_epoch.png](analysis/plots/weights_boxplot_per_epoch.png)
- **Osservato**: dopo il salto dall'epoca 1 (setup, `W_k_raw` 106–284) i pesi sono **stazionari**. Spearman epoca→peso per miner fra −0,11 e +0,11. Medie pubblicate: miner-2 518 934, miner-4 503 036, miner-3 444 674, miner-1 300 116, miner-0 188 338; ogni serie oscilla di circa ±20 % per l'estrazione di `tau` a ogni epoca. La mediana del boxplot resta stabile a circa 390–400 k e l'IQR non si allarga. I tre pannelli di `weights_over_time.png` (grezzo / dopo malus / finale) sono identici, come deve essere con `Psi = 1` e `none`.
- **Atteso**: peso rumoroso, guidato da `tau` e ESG; senza trend, perché `tau` è i.i.d. fra epoche.
- **Giudizio**: **conforme**.

**Retroazione `rho → peso successivo`**
- **File**: [analysis/phase3/weight_engine_correlations.csv](analysis/phase3/weight_engine_correlations.csv), [analysis/plots/rho_vs_next_weight.png](analysis/plots/rho_vs_next_weight.png), [analysis/plots/rho_feedback_by_validator.png](analysis/plots/rho_feedback_by_validator.png), [analysis/phase1/epoch_earnings.csv](analysis/phase1/epoch_earnings.csv)
- **Osservato**: `rho` non è identicamente nullo (21 zeri su 505), ma è **minuscolo**: media 0,00253, sd 0,00158, massimo 0,00596. Il motivo è che `saldo_k` vale circa 600 998 GAS in media, per effetto dei 600 200 GAS di funding iniziale del miner, mentre `R_k` medio è 1 536 GAS per epoca. Il fattore `0,5·rho + 0,5` sta quindi in [0,5000; 0,5030]: la retroazione sposta il peso di **al più lo 0,6 %**, contro una variabilità di `tau` di circa ±20 %. Spearman aggregato 0,036 (p = 0,43, n = 500); per miner fra −0,19 (miner-1, p = 0,06) e +0,17 (miner-3, p = 0,09), nessuno significativo. Lo scatter è una nuvola senza struttura.
- **Atteso**: effetto al massimo di un fattore 2, visibile solo se `rho` ha varianza apprezzabile.
- **Giudizio**: **lieve scostamento** nel senso del prompt: non è un difetto del motore, perché l'aritmetica è esatta, ma in questa run il canale endogeno è **praticamente inerte** per calibrazione, e l'assenza di correlazione è quella attesa. La run non può quindi dire nulla sull'efficacia della retroazione.

**Il motore non concentra oltre i propri input**
- **File**: [analysis/phase3/weight_engine_gini_summary.csv](analysis/phase3/weight_engine_gini_summary.csv), [analysis/phase3/weight_engine_gini.csv](analysis/phase3/weight_engine_gini.csv), [analysis/plots/gini_delta_trajectory.png](analysis/plots/gini_delta_trajectory.png)
- **Osservato**: pendenza 0,000000, Spearman −0,005 (p = 0,96). `|Gini(pubblicato) − Gini(input)| < 0,0008` in ogni epoca.
- **Giudizio**: **conforme**. Come atteso con un fattore di retroazione quasi uguale per tutti.

### 3.8 Concentrazione

- **File**: [analysis/phase2/epoch_concentration.csv](analysis/phase2/epoch_concentration.csv), `wpoa_epoch_tests.csv` (`p_theoretical_*`, `p_hat_*`, `delta_*`), [analysis/phase3/report.md](analysis/phase3/report.md) §3, [analysis/plots/concentration_over_time.png](analysis/plots/concentration_over_time.png)
- **Osservato**:
  - Aggregato: HHI osservato 0,2225 contro teorico 0,2211 (+0,6 %); `N_eff` 4,49 contro 4,52; Gini 0,182 contro 0,176; entropia normalizzata 0,962 contro 0,964; Nakamoto 1/3, 1/2, 2/3 = 2 / 2 / 3, uguale al teorico.
  - Per epoca: HHI osservato medio 0,2331 contro teorico 0,2226. La distorsione multinomiale attesa è `(1 − HHI)/B ≈ 0,778/99 = 0,0079`, quindi l'atteso vale circa 0,2305: il residuo è +0,0026. `N_eff` osservato medio 4,31 contro 4,49; Nakamoto 1/2 fra 2 e 3, in linea con il teorico.
- **Atteso**: l'HHI per epoca è sistematicamente più alto per varianza campionaria; l'aggregato va letto come riferimento.
- **Giudizio**: **conforme** sull'aggregato (scarti ≤ 0,6 % su HHI). Sulle singole epoche lo scarto è quasi tutto l'artefatto di campione atteso. Il piccolo residuo (+0,003) è coerente con la sovradispersione da ripetizioni. Nessuna concentrazione reale oltre i pesi.

### 3.9 Streak e ripetizioni

- **File**: [analysis/phase3/streak.md](analysis/phase3/streak.md), `wpoa_epoch_tests.csv` (`L_max_*`, `repeat_prob_*`)
- **Osservato**:
  - **Probabilità di ripetizione**: 0,326 osservata contro 0,223 del Monte-Carlo sugli stessi pesi (+46 %, **MC p = 0,0001** sull'aggregato). Per epoca, media 0,324 contro 0,223; **74 epoche su 100 con p < 0,05** (5 attese) e 17 con p < 0,001. Per validatore, P(vince | ha vinto il precedente) vale 0,381 per miner-2 (quota 0,267), 0,364 per miner-4 (0,262), 0,334 per miner-3 (0,227), 0,236 per miner-1 (0,151), 0,193 per miner-0 (0,094). Ogni validatore ripete circa 1,4–2 volte la propria quota.
  - **Streak massimi**: `L_max` aggregato 9 contro 7,33 (p = 0,12); per epoca 10 su 100 con p < 0,05 (5 attesi); massimo 9 in epoca 13 (p = 0,0008).
  - **Riferimento esterno**: la run regional precedente (`run-wpoa-core-regional-20260922T053033Z`, T = 12 s, senza `fork_score`) dà 0,3266 contro 0,2265, p = 0,0001. L'effetto si riproduce identico con un `T_block` diverso e con il tie-break di fork-choice spento o acceso.
- **Atteso**: `repeat ≈ Σp²` se i round sono indipendenti.
- **Giudizio**: **scostamento significativo da indagare**. L'eccesso è sistematico (74 % delle epoche) e non episodico: gli esiti dei round **non sono indipendenti**. La causa che i dati supportano è una sorgente di vantaggio che persiste da un round al successivo, cioè il vantaggio di circa 1 s del miner uscente (§3.5). Un seed che non si rinfresca fra i round è escluso: A.1 e A.2 sono puliti per round e Prop. 5.17 torna.

### 3.10 Malus

Caso **J.1**: meccanismo attivo (`enable-wpoa-malus = true`), nessuna violazione iniettata (`malicious.enabled = false`).

- **File vuoti come atteso**: [analysis/phase1/malus_detections.csv](analysis/phase1/malus_detections.csv), `malicious_actions.csv`, `malicious_confirmations.csv`, `malicious_opportunities.csv` (0 righe ciascuno); [analysis/phase2/malus_actions.csv](analysis/phase2/malus_actions.csv), `malus_detection_events.csv`, `malus_rate_by_miner.csv` (0 righe); [analysis/phase3/malus_rate.csv](analysis/phase3/malus_rate.csv) vuoto. [analysis/phase3/malus_funnel.csv](analysis/phase3/malus_funnel.csv) e [analysis/phase3/malus_detection.csv](analysis/phase3/malus_detection.csv) sono tutti a zero, con precision/recall indefinite. [analysis/phase3/malus_latency.csv](analysis/phase3/malus_latency.csv) ha n = 0.
- **Stato**: [analysis/phase2/malus_state.csv](analysis/phase2/malus_state.csv) e [analysis/phase3/malus_invariants.csv](analysis/phase3/malus_invariants.csv) danno 505 celle su 505 con `M = 0` e `Psi = 1`, e i tre invarianti (`psi_in_unit`, `weff_matches`, `clean_psi_one`) veri in tutte e 505. [analysis/plots/malus_invariant_audit.png](analysis/plots/malus_invariant_audit.png) è interamente verde. Il check critico `malus_finite_and_psi_in_unit_interval` passa su 435 565 campioni.
- **Effetto sul comportamento onesto**: `w_eff = w_raw` in 49 990 righe su 49 990 ([analysis/phase1/round_final_weights.csv](analysis/phase1/round_final_weights.csv)).
- **Figure**: [analysis/plots/malus_action_funnel.png](analysis/plots/malus_action_funnel.png) ("no malicious experiment ran"), [analysis/plots/malus_state_trajectory.png](analysis/plots/malus_state_trajectory.png) e [analysis/plots/malus_detection_latency.png](analysis/plots/malus_detection_latency.png) sono degeneri, come atteso. [analysis/plots/malus_weight_effect.png](analysis/plots/malus_weight_effect.png) e [analysis/phase3/malus_weight_effect.csv](analysis/phase3/malus_weight_effect.csv) mostrano per i 5 onesti una variazione relativa di `w_eff` fra +15,4 e +21,4 (mediana circa 17). **Non è un effetto del malus**: confronta l'epoca 1 (setup, pesi 10 585–28 425) con l'ultima (190 929–587 105), cioè il passaggio dall'attività quasi nulla del setup al regime.
- **`malus_effectiveness.md` non è presente**: l'esperimento malicious non è stato eseguito in questa run. Non ci sono risultati di efficacia da riportare.
- **Giudizio**: **conforme**. Effetto esattamente nullo sul comportamento onesto: 0 celle con `Psi < 1`, 0 righe con `w_eff ≠ w_raw`.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [analysis/phase2/epoch_engine.csv](analysis/phase2/epoch_engine.csv), [analysis/phase3/weight_election_residuals.csv](analysis/phase3/weight_election_residuals.csv) / `wpoa_epoch_validators.csv` (`excess_p`), [analysis/plots/residual_boxplot_by_validator.png](analysis/plots/residual_boxplot_by_validator.png)
- **Osservato**:
  - **Correlazioni grezze** (Spearman, 495 coppie epoca-miner, epoche 2–100) fra `n_blocks_won_epoch` e: `W_k_raw` 0,80, `w_k_published` 0,80, `earnings_g_k` 0,62, `companies_contribution_sum` 0,57, `income` 0,06, `miner_activity` 0,06.
  - **A peso fissato** (Spearman fra il residuo `p_hat − p_theoretical` e le stesse variabili): `earnings_g_k` −0,001, `income` −0,026, `miner_activity` −0,029, `companies_contribution_sum` +0,030, `W_k_raw` +0,002, `w_k_published` +0,002, `R_k` −0,013, `rho` −0,013. `|t| ≤ 0,67` in tutti i casi.
  - Residui medi per validatore fra −0,0031 (miner-1) e +0,0042 (miner-4); nel boxplot tutte le scatole sono centrate sullo zero.
- **Atteso**: correlazione grezza positiva mediata dal peso, che sparisce sui residui.
- **Giudizio**: **conforme**. La correlazione grezza è interamente spiegata dal peso: il 0,80 su `W_k_raw` scende a |ρ| ≤ 0,03 sui residui. Nessun canale di influenza non documentato del traffico o del guadagno sull'elezione.

### 3.12 Integrità della run e controlli di consistenza

**Check di consistenza** ([analysis/phase3/consistency_checks.csv](analysis/phase3/consistency_checks.csv))

| check | critico | esito | nota |
|---|---|---|---|
| `registry_weights_finite_and_positive` | sì | PASS | 435 565 campioni |
| `no_phantom_validator_in_registry` | sì | PASS | |
| `malus_finite_and_psi_in_unit_interval` | sì | PASS | 435 565 campioni |
| `delay_recompute_mismatch_rounds_is_zero` | sì | PASS | tolleranza 1,5 ms |
| `phi_consistent` | no | FAIL | 50 valori distinti: **atteso**, `Phi` varia per design (§3.6) |
| `every_esg_publication_reached_the_stream` | sì | PASS | 35 su 35 |
| `certified_scores_reflected_in_the_engine` | no | PASS | |
| `traffic_counts_within_configured_range` | no | FAIL | 764 coppie su 3 465: **artefatto di raccolta**, vedi sotto |
| `only_miners_pay_the_treasury` | sì | PASS | 5 094 pagamenti |
| `at_least_one_fully_measured_epoch` | sì | PASS | 100 epoche |

**8 critici su 8 passano.**

**Traffico** ([analysis/phase2/epoch_traffic.csv](analysis/phase2/epoch_traffic.csv), [analysis/plots/traffic_per_epoch.png](analysis/plots/traffic_per_epoch.png))
- Le 764 coppie fuori range sono tutte aziende, e tutte a partire dall'**epoca 75**. Il rapporto on-chain/pianificato vale 1,000 dall'epoca 2 alla 74, 0,63 nella 75 e **0** dalla 76 in poi. La figura mostra le barre verdi che spariscono dopo l'epoca 75.
- Pianificato e inviato coincidono sempre, e il 100 % dei piani sta nel range `[30, 60]`.
- La causa è di raccolta, non di protocollo. [analysis/phase1/stream_items.csv](analysis/phase1/stream_items.csv) contiene **esattamente 100 000** righe di `supply-chain-events`, cioè il default `count=100000` di `stream_items()` in `test/bootstrap/rpc_client.py:303`. Ai circa 1 340 elementi per epoca il tetto si raggiunge proprio all'epoca 75. Nel frattempo `txcount` per blocco resta invariato (14,7–16,1 dalla 2 alla 100, [analysis/phase1/blocks.csv](analysis/phase1/blocks.csv)) e il motore, che legge la catena, ricalcola i pesi senza errori (420 verifiche su 420 `ok`).
- **Giudizio**: **lieve scostamento dell'harness**, nessun impatto su pesi ed elezione. Da correggere con una paginazione, altrimenti le metriche di traffico di ogni run con più di 100 000 eventi restano cieche.

**Altri controlli**
- **Verifica dei pesi** ([analysis/phase1/verification.csv](analysis/phase1/verification.csv)): 420 su 420 `ok`, nessun `BadWeight` possibile. **Conforme.**
- **Errori RPC** ([analysis/phase1/rpc_errors.csv](analysis/phase1/rpc_errors.csv)): 416 errori, tutti `Round not evaluable on this node` (104 per ciascuna di `wpoalistscores`, `wpoalistdelays`, `wpoalisteffectiveweights`, `wpoalistfinalweights`). Sono benigni: round non ancora valutabili al momento del campionamento, pari all'1 % dei round. **Conforme.**
- **Setup**: epoca 1 esclusa; nell'epoca 2 sono esclusi i 21 round ad altezza ≤ 220 (105 righe `in_setup`). Il primo round testato è all'altezza 221. **Conforme.**
- **Ultima epoca** (101): parziale, 21 blocchi (Wilson larghi fino a 0,38, HHI 0,256). È trattata a parte e non usata per le tendenze.
- **Fork e coerenza con la catena finale** (verificato sui `debug.log` di tutti i 38 nodi, letti via `./docker/mcsim`): alle 10 125 altezze comuni **tutti i nodi concordano** su ogni blocco, quindi non resta nessuna fork irrisolta. Dopo il setup ci sono state 1 618 altezze contese (1 424 con 2 blocchi, 180 con 3, 12 con 4, 1 con 5). Il **100 %** si è risolto verso il blocco di score minimo, sempre con uno scambio alla stessa altezza (tie-break per score). Le riorganizzazioni di profondità ≥ 2 sono **0**: le 49 osservate cadono tutte in setup, alle altezze 135, 190 e 206. Su ogni nodo un tip orfano è rimasto attivo al massimo 2 s (mediana 0 s). **Artefatto di raccolta**: in 199 altezze (2,0 %) [analysis/phase1/blocks.csv](analysis/phase1/blocks.csv) registra il blocco *orfano*, perché `_snap_getlastblockinfo` in `test/analysis/pipeline/phase1_collect.py` tiene il primo campione del tip (0 conferme). [analysis/phase1/block_sortition.csv](analysis/phase1/block_sortition.csv) coincide invece con la catena dei nodi a ogni altezza (`true_winner_mismatch = True` in `round_level.csv` segnala proprio questi casi). In 144 dei 199 casi l'orfano è un blocco del miner uscente, poi scalzato dal tie-break. Rifatti sulla catena finale, i numeri principali cambiano poco: ripetizioni 0,314 contro 0,222 attese (+41 % invece di +46 %), quote entro 0,1 pp da quelle riportate, Q2 con `√n·D = 4,20` e 5,1 % sopra 0,99. Le conclusioni non cambiano, ma `winner_address` e le tabelle per epoca vanno ricalcolate dopo aver corretto il collector.

## 4. Punti di forza

- **Randomness pulita sul meccanismo pubblico.** `E_i` ha media 1,0042 (banda ±0,0088) con `√n·D = 0,94` su 49 425 campioni, e resta sotto il critico per ciascun validatore (0,80–1,17). L'argmin di `score_norm` ha media 0,5036 con `√n·D = 0,75`.
- **Sortition privata esatta**: sugli score VRF reali `E_i` ha media 1,0010 con `√n·D = 0,78`, l'argmin ha `score_norm` medio 0,5004 con `√n·D = 0,53`, e le quote designate hanno chi-quadro 1,22 (p = 0,87).
- **Fork sempre risolte**: 1 614 fork, 100 % verso lo score minimo fra i candidati, 0 riorganizzazioni di profondità ≥ 2, convergenza in ≤ 2 s, nessuna fork irrisolta su 38 nodi.
- **Nucleo di sortition esatto.** Prop. 5.17 dà una media del gap di 0,993–1,052 per i 5 vincitori (KS p ≥ 0,14). Il margine `G` è di 2,260 s contro 2,272 s simulati (KS p = 0,705).
- **Meccanica del delay senza errori**: 0 disaccordi su 49 990 righe candidato-round, errore massimo 3,6·10⁻¹⁵ s.
- **Proporzionalità aggregata eccellente**: chi-quadro p = 0,755, `TV = 0,006`, 5 intervalli di Wilson aggregati su 5 contengono la quota spettante, scarto massimo 0,47 pp. Ordinamento osservato uguale a quello dei pesi.
- **Nessun canale nascosto traffico/guadagno → elezione**: sui residui a peso fissato `|ρ| ≤ 0,03` per 8 variabili, contro 0,80 sulle correlazioni grezze.
- **Weight engine aritmeticamente esatto** (identità a 4·10⁻¹⁶), 420 verifiche su 420 `ok`, ESG statici, nessuna amplificazione della disuguaglianza (pendenza del Gini delta 0,000, p = 0,96).
- **Malus neutro sul comportamento onesto**: 505 celle su 505 con `Psi = 1`, 3 invarianti su 3 veri ovunque, 49 990 righe su 49 990 con `w_eff = w_raw`.
- **Correzione globale stabile**: `Phi` mai saturato (massimo 79 % di `M`), mai oscillante (1,9 % di cambi di segno). Block time senza deriva su 100 epoche (+0,14 s sull'intera run).
- **Rete non limitante**: `S1 = 0,38 ms`, circa 2 000 volte sotto il residuo di scheduling.

## 5. Punti critici / da approfondire

1. **Vantaggio temporale del miner uscente (dipendenza fra round consecutivi).**
   - *Entità*: il designato non vince nell'**11,0 %** dei round (1 088 su 9 884), che diventa 0 % quando il designato è l'incumbent; la Prop. 5.18 con `sigma = S1` prevede lo 0,9 %; ripetizioni 0,326 contro 0,223 (+46 %), rigetto in 74 epoche su 100. Il 5,1 % dei vincitori ha `score_norm_true > 0,99` contro l'1 % atteso, e il 96 % di questi casi sono ripetizioni. Residuo di 0,66 s nelle ripetizioni contro 1,66 s negli altri round, cioè circa 1 s di anticipo. Conseguenze secondarie: `beta1 = 1,20` (IC [1,14; 1,27]), pendenza dei log-rapporti 1,057, Wilson 35 su 500 (p = 0,03), GoF 9 su 100 (p = 0,063). Sull'aggregato l'effetto sulle quote resta piccolo (≤ 0,5 pp).
   - *Ipotesi*: il miner che ha appena prodotto il blocco `h` arma il timer per `h+1` al momento della creazione. Gli altri lo armano solo dopo aver ricevuto e validato il blocco, e l'avvio del miner loop aggiunge un altro ritardo (circa 1–2 s nel caso dell'altezza 3027). La rete (5 ms) non c'entra: il ritardo è locale al nodo (validazione, CPU condivisa da 38 daemon, polling del miner). Il Monte-Carlo con un vantaggio di 0,6–0,8 s riproduce insieme ripetizioni, coda `> 0,99` e pendenza. L'effetto è identico nella run regional precedente con `T_block = 12 s` e senza `fork_score`, quindi non dipende né da `T_block` né dal tie-break.
   - *Dati che servirebbero*: (a) per ogni round e nodo, l'istante di armo del timer (`mchn-miner: wPoA-sortition … start in`) rispetto all'istante di creazione/ricezione del blocco padre, estratto da tutti i `debug.log`, per misurare `h` per nodo; (b) una run di controllo in cui i timer siano ancorati a `parent.nTime` (tempo di catena) invece che all'istante locale di arrivo del tip, per verificare che la ripetizione torni a `Σp²`; (c) l'andamento di `h` al variare del carico di CPU (cpuset o numero di aziende).
2. **Block time medio +13 % sul target (9,07 s contro 8 s).**
   - *Entità*: +1,07 s stabile, senza deriva; `Phi` medio −1,06, non saturato.
   - *Ipotesi*: errore a regime del controllo solo proporzionale di fronte a un ritardo sistematico di 1,34 s (latenza di produzione più quantizzazione di `nTime`), secondo `dt = T + r/(1 + lambda)`. Aumentare `lambda` riduce ma non azzera (con `lambda = 1` si arriverebbe a 8,67 s); servirebbe un termine integrale, oppure sottrarre `r` stimato.
   - *Dati*: una run con `lambda` diverso (ad esempio 0,6) per verificare la previsione `8 + 1,34/1,6 = 8,84 s`.
3. **Stallo a inizio epoca che cresce nel tempo.**
   - *Entità*: all'altezza ≡ 8 (mod 100) il `dt` medio passa da 9,1 s (primo quarto) a 13,9 s (ultimo quarto); 18 round ≥ 14 s, fino a 23 s, di cui 15 all'altezza ≡ 8 (mod 100) e 15 dopo la 7 500.
   - *Ipotesi*: un calcolo di confine d'epoca (weight engine, ricostruzione del registro, snapshot dell'harness `weightgetlocal*` sui 38 nodi) il cui costo cresce con la lunghezza della catena o con il numero di elementi negli stream.
   - *Dati*: i timestamp di `debug.log` intorno alle altezze `e·100 + 0…8` per le epoche 20, 50 e 95; il profilo di CPU del nodo in quelle finestre. Da verificare prima delle run da 24 h e oltre, dove lo stallo potrebbe crescere ancora.
4. **Retroazione `rho` inerte per calibrazione.**
   - *Entità*: `rho ≤ 0,006`, fattore di retroazione in [0,500; 0,503], effetto ≤ 0,6 % sul peso.
   - *Ipotesi*: il saldo include i 600 200 GAS di funding iniziale del miner (`derived.miner_seed_gas`), mentre le restituzioni valgono circa 1 500 GAS per epoca.
   - *Dati*: una run in cui il funding non entri in `saldo` (o sia comparabile alle restituzioni), per osservare una varianza di `rho` apprezzabile e testare davvero `rho → peso`.
5. **Raccolta degli stream troncata a 100 000 elementi** (`test/bootstrap/rpc_client.py:303`). Rende ciechi `epoch_traffic` e il check sul traffico dall'epoca 75 in poi. È un difetto dell'harness, senza effetto sul protocollo. Correzione: paginare `liststreamitems` con `start` crescente.
6. **`blocks.csv` registra 199 blocchi orfani (2 %)**: il collector tiene il primo campione del tip invece del blocco sepolto. `winner_address`, `O_i` e le statistiche di ripetizione ereditano l'errore (ripetizioni 0,326 contro 0,314 reali). Correzione: riempire `blocks` da una lettura a profondità ≥ `stability_margin`, oppure riconciliarlo a fine run con `block_sortition`.

## 6. Conclusione

- **Affidabilità della sortition: buona sull'aggregato, con una dipendenza fra round da
  correggere.** Proporzionalità al peso effettivo confermata (chi-quadro p = 0,755, scarti
  ≤ 0,5 pp, ordinamento preservato). A livello di singolo round c'è però un vantaggio di
  circa 1 s per il miner uscente: ripetizioni +46 %, `beta1 = 1,20`, e un eccesso lieve di
  violazioni di Wilson (35 su 500) e di rigetti GoF (9 su 100).
- **Aderenza del vincitore reale al designato: 89,0 %.** Le fork sono tutte risolte dal tie-break per score. Le inversioni residue (11,0 %) superano di 12× il bound di Prop. 5.18 calcolato con il rumore di rete, perché il rumore effettivo è un bias di circa 0,65 s a favore del miner uscente.
- **Qualità della randomness (VRF): conforme.** `E_i ~ Exp(1)` (media 1,0042,
  `√n·D = 0,94`), argmin `~ U(0,1)` (0,5036, `√n·D = 0,75`), Prop. 5.17 con media 0,99–1,05.
  Il rigetto del Q2 sul punteggio vero (`√n·D = 4,13`) sta tutto nella coda `> 0,99` ed è
  spiegato dal vantaggio dell'incumbent, non dalla VRF.
- **Efficacia dello smorzamento: non applicabile** (`dump-function = none`). Il comportamento
  lineare atteso è verificato: `w_eff = w_raw` in 49 990 righe su 49 990, quote lineari nel
  peso, con un rapporto di 2,75 fra massimo e minimo e nessuna balena.
- **Efficacia del malus: effetto esattamente nullo, come richiesto dal caso J.1.** `Psi = 1`
  in 505 celle su 505 e invarianti tutti veri. Sull'efficacia del malus contro violazioni
  reali la run non dice nulla, perché nessuna è stata iniettata.
- **Stabilità del block time: stabile ma fuori target.** 9,07 s contro 8 s (+13 %), senza
  deriva. `Phi` non è saturato (≤ 79 % di `M`) e non oscilla: l'errore residuo è quello
  previsto per una correzione proporzionale con `lambda = 0,3` di fronte a 1,34 s di ritardo
  sistematico. Da monitorare lo stallo di confine d'epoca, che nell'ultimo quarto porta il
  primo blocco dopo l'altezza `e·100 + 8` a 13,9 s in media.

Nel complesso il meccanismo wPoA è **corretto nella formula e nell'esito aggregato**. Le
deviazioni rilevate sono di esecuzione (tempi locali dei nodi), di calibrazione (funding che
annulla `rho`, `lambda` puramente proporzionale) e di raccolta (tetto di 100 000 stream item).
Nessuna di esse indica un difetto della VRF, della sortition pesata, del weight engine o del
malus.
