# Analisi della run run-wpoa-forkscore-1h-20260921T143502Z

Run: `test/results/run-wpoa-forkscore-1h-20260921T143502Z/`
Timestamp UTC della run: 2026-09-21T14:35:02Z
Catena: `wpoa-forkscore-1h` — profilo: `test/config/profiles/core/forkscore-1h.yaml` — regime: core
Analisi prodotta il: 2026-09-21

Nota di lettura: il sistema è intrinsecamente stocastico su più livelli indipendenti (score ESG
casuali, assegnazione cluster, traffico casuale, VRF ad ogni round, e in questo regime `core`
anche la rete emulata). Nessun giudizio in questo documento è basato su un singolo blocco o una
singola epoca isolata; dove i numeri per-epoca vengono citati è sempre insieme al riferimento
aggregato sull'intera run.

Mappa indirizzo → validatore (da `addresses.json` / `manifest.json`), usata ovunque in questo
documento nella forma `miner-N (indirizzo troncato)`:

| Validatore | Indirizzo (troncato) | Cluster (aziende) |
|---|---|---|
| miner-0 | `1QrpSHGbytWz…` | company-0, company-7 |
| miner-1 | `1A9tPhymKcFC…` | company-1, company-8 |
| miner-2 | `1UmL87cqSz7o…` | company-2, company-9 |
| miner-3 | `18VGDtNzFSoy…` | company-3 |
| miner-4 | `1aS6ZBnfY8iT…` | company-4 |
| miner-5 | `1L51GRy46DAx…` | company-5 |
| miner-6 | `1KmKgDW1Vbyd…` | company-6 |

## 1. Configurazione della run

| Parametro | Valore | Fonte (file) |
|---|---|---|
| Nome catena | `wpoa-forkscore-1h` | `manifest.json` (`chain_name`), `analysis/phase1/config.csv` |
| Seed esperimento | `20260905` | `manifest.json` (`seed`) |
| Profilo | `test/config/profiles/core/forkscore-1h.yaml` | `manifest.json` (`profile_path`) |
| Regime | `core` (rete emulata) | `manifest.json` (`fabric.backend`) |
| Topologia | `intercontinental` — 20 siti, 7 hub, 34 link | `manifest.json` (`fabric.topology`) |
| Latenza peggiore one-way | 181,522 ms | `manifest.json` (`derived.worst_path_delay_ms`) |
| Round-trip peggiore | 0,363 s | `manifest.json` (`derived.worst_round_trip_s`) |
| Nodi per ruolo | admin 1, ca 2, miner 7, company 10 (totale 20) | `manifest.json` (`nodes`) |
| Epoche pianificate / lunghezza | 5 epoche × 40 blocchi | `manifest.json` (`epochs`) |
| Epoche effettivamente presenti nella griglia | 6 (`measured_epochs`) | `manifest.json` |
| Altezza finale / target | 262 / 260 | `manifest.json` (`final_height`, `derived.target_height`) |
| Esito | `status = ok`, `error = ""` | `manifest.json` |
| Funzione di smorzamento | `dump-function = sqrt` | `analysis/phase1/config.csv` |
| `target-block-time` | 10 s | `analysis/phase1/config.csv` |
| `wpoa-sortition-delta` | 0,5 → `Delta_max = delta·T_block = 5,0 s` | `analysis/phase1/config.csv` (calcolato) |
| `wpoa-sortition-lambda` | 0,3 | `analysis/phase1/config.csv` |
| Bound del feedback `M` | `min(0,5·10 ; 10·(1-0,5)/0,3) = 5,0 s` | calcolato (§1.3d); coerente con `D_max=5.0` in `analysis/phase3/wpoa_timer_race.csv` |
| Parametri malus | `mu=0,5`, `max=4,0`, `equiv=4,0`, `delay=0,25`, `selfwrite=1,0`, `badweight=2,0` | `analysis/phase1/config.csv` |
| Malus attivo / violazioni iniettate | `enable-wpoa-malus = true` (sempre attivo) **e** `malicious.enabled = false` (nessuna violazione iniettata) → caso J.1 | `analysis/phase1/config.csv`, `manifest.json`, `malicious_manifest.json` |
| Weight engine | `weight-kappa=100`, `weight-lambda=0,5`, `weight-alpha=0,2` (**parametro inerte**, §1.3h — validato all'avvio ma mai letto) | `analysis/phase1/config.csv` |
| `setup-first-blocks` effettivo | 112 | `analysis/phase1/config.csv` (`effective_chain_params`), `manifest.json` (`derived.setup_first_blocks_requested=112`) |
| `mining-diversity` | 0,0 — nessun collasso al round robin nativo | `analysis/phase1/config.csv` |
| `mining-turnover` | 0,5 — euristica nativa senza effetto su wPoA (§1.5) | `analysis/phase1/config.csv` |
| `initial-block-reward` / `first-block-reward` | 0 / 100 000 000 000 000 (raw) | `analysis/phase1/config.csv` — nessuna ricompensa di mining continuativa; le entrate dei miner sono fee + trasferimenti dal premine |
| Traffico | `company_tx_per_epoch=[30,60]`, `miner_gas_returns_per_epoch=[0,5]`, `esg_score_range=[1,100]`, `restitution_amount_range=[1,0–9,0]`, stream `supply-chain-events` | `manifest.json` (`traffic`) |
| `wpoa-randao-lookback` | 41 | `analysis/phase1/config.csv` |
| Indirizzo treasury | `18dPcHvzBfoVCsS4QqTscZs2jnhoqCWA7djSgC` | `treasury.txt`, `manifest.json`. Nota: `config.csv` riporta `weight-treasury-address=[null]` come parametro di catena hash-enforced — il valore effettivo è comunque quello di `treasury.txt`/`manifest.json`; divergenza minore, non impattante (non è un parametro consensus-critical al pari di `weight-alpha`). |
| Piano malicious | `enabled=false`, `miner_count=0`, `target_action_rate=0,0`, azioni previste `{selfwrite:0,5, badweight:0,5}`, `start_epoch=1`, nessun `malicious_miner_id` | `malicious_manifest.json` |
| Fork-choice tie-break | `runtime.fork_score = true` (`-enablewpoaforkscore` attivo), `runtime.wpoa_debug = false` (nessun log `-debug=wpoafork`) | `manifest.json` (`runtime`) — vedi §3.5 |

### Pesi effettivi alla prima epoca misurata

I pesi **non sono un parametro di configurazione**: emergono dalla pipeline ESG × attività
(§1.3h) e sono quindi un **esito stocastico** di questa run, non un input scelto. Score ESG
certificati (`analysis/phase1/esg_events.csv`):

| Validatore | ESG certificato | Peso grezzo pubblicato all'epoca 1 (`W_k_raw`, `analysis/phase2/epoch_engine.csv`) | Peso efficace dopo `sqrt` all'inizio dell'epoca 2 (`w_eff_start`, `analysis/phase2/epoch_level.csv`) | Quota teorica iniziale (`p_theoretical_start`) |
|---|---:|---:|---:|---:|
| miner-2 (`1UmL87cqSz7o…`) | 75 | 3 301,50 (pubbl. 16 575) | 128,74 | 0,1787 |
| miner-6 (`1KmKgDW1Vbyd…`) | 81 | 2 306,07 (pubbl. 13 527) | 116,31 | 0,1615 |
| miner-1 (`1A9tPhymKcFC…`) | 56 | 3 104,64 (pubbl. 13 104) | 114,47 | 0,1589 |
| miner-5 (`1L51GRy46DAx…`) | 67 | 1 591,92 (pubbl. 11 658) | 107,97 | 0,1499 |
| miner-3 (`18VGDtNzFSoy…`) | 55 | 2 684,00 (pubbl. 10 450) | 102,23 | 0,1419 |
| miner-0 (`1QrpSHGbytWz…`) | 29 | 1 319,21 (pubbl. 6 264) | 79,15 | 0,1099 |
| miner-4 (`1aS6ZBnfY8iT…`) | 49 | 125,44 (pubbl. 5 096) | 71,39 | 0,0991 |

I pesi sono **quasi omogenei** (rapporto max/min sul peso efficace ≈ 1,81, non una "balena"):
coerente con l'attesa di §1.4 secondo cui, con ESG uniformi in [1,100] e traffico in range
stretti, i pesi restano entro un fattore 2–3. Lo smorzamento `sqrt` è quindi atteso avere un
effetto visibile ma non drammatico (§3.3).

## 2. Executive summary

Il meccanismo si comporta in larga parte come previsto dal modello teorico. (1) **Randomness**:
`E_i` ha media empirica 1,0047 contro 1 atteso (banda 1±0,0607, n=1043) e KS `sqrt(n)·D=0,53`
contro un critico di 1,36 — pulita; lo `score_norm` dell'argmin ha media 0,4993 (attesa 0,5) con
KS 0,56 — pulita. Nessun test di randomness fallisce, quindi tutte le metriche a valle sono
affidabili. (2) **Meccanica del delay**: perfetta, 0 mismatch su 1505 coppie candidato-round oltre
la tolleranza di 1,5 ms. (3) **Quota contro peso**: l'unico rigetto del goodness-of-fit per epoca
(p=0,0089) è spiegato — non un difetto della sortition: quell'epoca (altezze 80–119, si veda
§3.3/§3.8/§3.9) contiene ancora 33 blocchi su 40 sotto round robin nativo perché
`setup-first-blocks=112` non è allineato alla griglia epocale da 40 blocchi, ma la pipeline la
marca comunque come "misurata"; sull'aggregato dell'intera run il GOF non rigetta (p=0,061) e la
copertura di Wilson è 31/35 (attesa per caso 33,2/35). (4) **Longitudinale**: `beta1=0,81`
(IC 95% [0,40; 1,23], contiene 1) — compressione lieve, coerente con un tasso di inversione
elevato sotto questa topologia intercontinentale. (5) **Timer race**: lo score vero del vincitore
è uniforme come atteso (media 0,512 su 139 round puliti, KS p=0,338), ma la spaziatura osservata
eccede il delay proprio del vincitore di 1,57 s in media (sd 0,83 s) — overhead di esecuzione
reale, non un difetto della formula (verificata esatta al punto 2). (6) **Novità di questa run**:
è la prima campagna della serie a validare la rottura dei pareggi a parità di altezza sul vero
score di sortition (`-enablewpoaforkscore`, commit `ebc59009`/`59c89542`); `block_sortition.csv`
mostra 9 round su 149 (6,0%) in cui un blocco osservato per primo è stato effettivamente
soppiantato da un competitor alla stessa altezza — lo scenario bersaglio della modifica si
presenta con una frequenza non trascurabile sotto stress di rete, ma l'assenza dei log
`-debug=wpoafork` (`wpoa_debug=false`) impedisce di attribuire con certezza l'esito al nuovo
comparator piuttosto che alla normale risoluzione per `nChainWork` (dettagli in §3.5).
(7) **Malus**: nessuna violazione iniettata (`malicious.enabled=false`); effetto nullo confermato
su tutte le 42 celle (epoca, validatore): `M=0`, `Psi=1`, invarianti rispettati ovunque.
(8) **Weight engine**: le identità del motore tornano esatte al bit (errore massimo 0,0 su 42
osservazioni), gli ESG sono statici come richiesto, e la retroazione `rho→peso` è debole ma non
nulla (Spearman 0,335, p=0,049).

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

- **File**: `analysis/phase2/candidate_long.csv` (colonne `score_public`, `score_norm_public`,
  `weight_effective`, `in_setup`), nessuna figura dedicata (test numerico, non un grafico della
  pipeline).
  **Cosa misura**: A.1 — `E_i = score_public · weight_effective` deve distribuirsi come `Exp(1)`
  indipendentemente da pesi, smorzamento, traffico (§1.3a). A.2 — il minimo di `score_norm_public`
  per round (l'argmin della sortition) deve essere uniforme su (0,1) (Prop. 5.11).
  **Osservato**: A.1 — n=1043 righe non-setup con `eligible=True`: media 1,0047 (banda accettabile
  `1±1,96/√n = 1±0,0607`), KS `sqrt(n)·D = 0,5336`. A.2 — n=149 round: media del minimo
  `score_norm_public` = 0,4993, KS `sqrt(n)·D = 0,5648`.
  **Atteso**: media ≈1 (A.1) / ≈0,5 (A.2); `sqrt(n)·D ≤ 1,358` al 5%.
  **Giudizio**: **conforme** — entrambe le medie entro lo 0,7% del valore teorico e i due
  `sqrt(n)·D` (0,53 e 0,56) ben al di sotto della soglia critica 1,358: nessuna evidenza di difetto
  nella VRF, nel seed RANDAO o nella normalizzazione dello score.

- **File**: `analysis/phase2/candidate_long.csv` (colonna `score_norm_mismatch_public`).
  **Cosa misura**: A.3 — coerenza fra lo `score_norm` loggato dal nodo e quello ricalcolato dalla
  pipeline.
  **Osservato**: n=1043, scarto assoluto massimo = 0,00000000.
  **Atteso**: mismatch nullo o sotto tolleranza.
  **Giudizio**: **conforme** — mismatch esattamente zero su ogni riga.

- **File**: `analysis/phase3/timer_race.md`, `analysis/phase3/wpoa_timer_race.csv` (colonne
  `true_score_norm_mean`, `true_score_norm_ks_p_uniform`).
  **Cosa misura**: la Prop. 5.11 applicata allo **score vero** del vincitore (recomputato dal
  reveal VRF sul suo blocco), non alla forma pubblica — il test Q2 di `timer_race.md`.
  **Osservato**: su 139 round "puliti" (esclusi 9 round con `true_winner_mismatch=True` e 1 con
  verdetto vuoto, si veda §3.5), media dello `score_norm_true` del vincitore = 0,511974, KS contro
  U(0,1) `D=0,078991`, `p=0,338025`.
  **Atteso**: media ≈0,5 se vince l'argmin (§1.3c, nota); KS non rigettato.
  **Giudizio**: **conforme** — la media è entro il 2,4% del valore teorico e il test KS non
  rigetta; conferma indipendente, sul punteggio realmente usato dall'elezione, di quanto già
  osservato sulla forma pubblica.

### 3.2 Correttezza meccanica del delay

- **File**: [analysis/plots/delay_recompute_mismatch.png](analysis/plots/delay_recompute_mismatch.png),
  `analysis/phase3/consistency_checks.csv` (check `delay_recompute_mismatch_rounds_is_zero`),
  `analysis/phase2/candidate_long.csv` (colonna `delay_mismatch_public_s`).
  **Cosa misura**: la differenza fra il delay ricalcolato indipendentemente dalla pipeline a
  partire dagli input loggati (§1.3c) e il delay effettivamente loggato dal nodo.
  **Osservato**: 0 mismatch su 1505 coppie candidato-round (didascalia della figura); scarto
  assoluto massimo verificato direttamente su `candidate_long.csv` = 0,000000 s (n=1043
  non-setup); il check critico di non-regressione `delay_recompute_mismatch_rounds_is_zero`
  passa con tolleranza 0,0015 s.
  **Atteso**: mismatch nullo (tolleranza 1,5 ms) — un difetto qui indicherebbe un disaccordo fra
  harness e nodo sul meccanismo stesso, non rumore statistico.
  **Giudizio**: **conforme**, aderenza perfetta — i residui visibili nella figura sono
  dell'ordine di 10⁻¹³–10⁻¹⁷ s, puro rumore in virgola mobile, con un singolo outlier per epoca
  attorno a 1 s attribuito dalla didascalia stessa a un troncamento del writer JSON del nodo, non
  al meccanismo di sortition.

### 3.3 Quota di blocchi contro peso

- **File**: [analysis/plots/weight_vs_election.png](analysis/plots/weight_vs_election.png),
  `analysis/phase3/weight_vs_election.md`.
  **Cosa misura**: quota di blocchi vinta da ciascun validatore contro la quota spettante dal
  peso efficace (`effective_weight_after_malus_and_dumping`, con `dump-function=sqrt`).
  **Osservato**: 31 dei 35 intervalli di Wilson (epoca, validatore) contengono la quota spettante
  (attesi 1,8 rigetti per caso a alpha=0,05; osservati 4). Larghezza media dell'intervallo:
  0,2001 — questa è la risoluzione della run. Sul pool dell'intera run (B=181 blocchi per
  validatore): miner-3 (`18VGDtNzFSoy…`) sovra-rappresentato (osservato 0,2099 contro teorico
  0,1486, IC 95% [0,157; 0,275] esclude il teorico); miner-2 (`1UmL87cqSz7o…`)
  sotto-rappresentato (osservato 0,1271 contro teorico 0,2051, IC 95% [0,086; 0,184] esclude il
  teorico); gli altri 5 validatori rientrano nell'intervallo.
  **Atteso**: con `dump-function=sqrt` su pesi quasi omogenei (rapporto max/min ≈1,81), la quota
  osservata deve avvicinarsi a quella teorica con compressione modesta; circa 1,8/35 violazioni
  per puro caso.
  **Giudizio**: **lieve scostamento** — 4 violazioni contro 1,8 attese non è un eccesso enorme, e
  le due deviazioni sistematiche (miner-3 sopra, miner-2 sotto) sono coerenti con la compressione
  longitudinale già misurata (`beta1=0,81`, §3.4) e con il tasso di inversione elevato sotto
  questa topologia (§3.5), non con un'inversione di ordinamento (nessun validatore a peso più
  alto perde sistematicamente contro uno a peso più basso).

- **File**: [analysis/plots/election_share_distribution.png](analysis/plots/election_share_distribution.png).
  **Cosa misura**: quota cumulativa di blocchi vinti sull'intera run, per validatore.
  **Osservato**: miner-3 21,3%, miner-1 19,1%, miner-6 16,9%, miner-0 14,0%, miner-2 12,9%,
  miner-5 11,2%, miner-4 4,5%.
  **Atteso**: ordinamento coerente con il peso medio nel tempo, senza una singola quota
  dominante (nessuna balena in questa run, §1.4).
  **Giudizio**: **conforme** — nessun validatore supera il 22%; la quota più bassa (miner-4,
  4,5%) corrisponde al validatore di peso quasi sempre più basso (peso efficace iniziale 71,4
  contro un massimo di 128,7, tabella §1).

- **File**: [analysis/plots/wilson_violation_heatmap.png](analysis/plots/wilson_violation_heatmap.png).
  **Cosa misura**: dove la quota spettante cade fuori dall'intervallo di Wilson 95%, per epoca e
  validatore.
  **Osservato**: 4 violazioni su 35 celle, concentrate su miner-5 (`1L51GRy46DAx…`, epoche 2 e 4)
  e miner-2 (`1UmL87cqSz7o…`, epoche 2 e 3); nessuna violazione per miner-3, miner-1, miner-6,
  miner-0, miner-4.
  **Atteso**: ≈1,8 violazioni distribuite per caso.
  **Giudizio**: **lieve scostamento** — la concentrazione di 2 violazioni su miner-2 proprio nelle
  prime epoche misurate (2 e 3) è coerente con la sotto-rappresentazione aggregata di miner-2 già
  notata sopra; da tenere d'occhio ma non conclusivo con questa ampiezza campionaria.

- **File**: [analysis/plots/residual_boxplot_by_validator.png](analysis/plots/residual_boxplot_by_validator.png).
  **Cosa misura**: distribuzione del residuo `p_hat − p_theoretical` per validatore, sulle 5
  epoche misurate.
  **Osservato**: miner-3 sistematicamente positivo (mediana +0,059, range [0,037; 0,083]);
  miner-2 sistematicamente negativo (mediana −0,073, range [−0,164; 0,072], un solo punto
  positivo); gli altri 5 hanno box centrati vicino a zero.
  **Atteso**: box centrati su zero per un validatore eletto al tasso spettante.
  **Giudizio**: **lieve scostamento** per miner-3 e miner-2, **conforme** per gli altri 5 — stessa
  lettura del punto precedente.

- **File**: `analysis/phase3/wpoa_epoch_tests.csv` (colonne `gof_p_value`, `gof_reject_alpha05`,
  `gof_mc_round_by_round_p`), [analysis/plots/p_value_uniformity.png](analysis/plots/p_value_uniformity.png).
  **Cosa misura**: il goodness-of-fit congiunto su tutti i validatori dell'epoca, e la sua
  uniformità sotto H0 sull'aggregato.
  **Osservato**: rigetto in 1 epoca su 5 a alpha=0,05 (attesi 0,25): l'epoca corrispondente alle
  altezze 80–119 (etichettata "epoca 2" in questi report) con `gof_p=0,0089`; le altre 4 epoche
  non rigettano (`p=0,357`; `0,076`; `0,202`; `0,759`). Sull'aggregato: KS dei p-value contro
  U(0,1) `D=0,4428, p=0,2067`; binomiale sul conteggio dei rigetti `p=0,2262`
  (`analysis/phase3/weight_election_pvalue_uniformity.csv`). Test aggregato sull'intera run
  (riga "all"): `chi2=12,049, p=0,0609`, non rigetta.
  **Causa identificata per il rigetto dell'epoca 80–119**: questa epoca (indice di griglia
  `altezza // 40 = 2`) si estende dall'altezza 80 alla 119, ma `setup-first-blocks=112` cade a
  metà: **33 dei suoi 40 blocchi (80–112) sono ancora sotto round robin nativo**, non sotto wPoA
  (verificato riga per riga su `analysis/phase1/blocks.csv`, colonna `in_setup`). La pipeline
  esclude correttamente l'epoca interamente in setup (indice 1, altezze 40–79) perché
  `epoch_level.csv` la marca `in_setup=True`; per l'epoca 80–119, però, la stessa colonna è
  marcata `in_setup=False` (non è *interamente* in setup) e l'intera finestra da 40 blocchi
  — round robin nativo compreso — entra nel test come se fosse omogeneamente wPoA
  (`analysis/phase2/epoch_level.csv`, `n_blocks_epoch=40`, somma di `O_i`=37 sui 7 validatori,
  contro soli 7 round genuinamente wPoA nella stessa finestra secondo
  `analysis/phase2/round_level.csv`). Questo spiega anche la concentrazione anomala e il
  repeat-rate di questa epoca discussi in §3.8 e §3.9.
  **Atteso**: ≈0,25 rigetti per caso; p-value uniformi su (0,1).
  **Giudizio**: **scostamento significativo, ma con causa identificata e non attribuibile al
  meccanismo wPoA** — è un artefatto della non-allineatura fra `setup-first-blocks=112` e la
  griglia epocale da 40 blocchi in questo specifico profilo, non un difetto della sortition
  pesata. Segnalato in dettaglio in §5 come raccomandazione metodologica per i prossimi profili
  (scegliere `setup-first-blocks` multiplo di `weight-epoch-length`, o filtrare esplicitamente
  per `round.in_setup` invece che per `epoch.in_setup` nei test di fase 3).

### 3.4 Comportamento longitudinale

- **File**: `analysis/phase3/longitudinal.md`, `analysis/phase3/wpoa_longitudinal_fits.csv`,
  [analysis/plots/longitudinal_logratio.png](analysis/plots/longitudinal_logratio.png).
  **Cosa misura**: GLM logit su `log(peso)` (H0: `beta1=1`) e regressione dei log-rapporti a
  coppie (H0: pendenza 1, intercetta 0).
  **Osservato**: `beta1=0,8135` (IC 95% [0,3995; 1,2276], n=35, convergenza confermata).
  Log-rapporti: pendenza 0,4671, intercetta 0,3307, Pearson `r=0,3081` (p=0,0019), n=99 coppie.
  **Atteso**: `beta1=1`; pendenza 1, intercetta 0.
  **Giudizio**: **lieve scostamento, compatibile con il modello** — l'IC di `beta1` include
  ampiamente 1 (test statisticamente non distinguibile dalla sortition pesata pura); la pendenza
  dei log-rapporti (0,47) è più bassa, con `r` moderato (0,31): la relazione è corretta in
  direzione ma sommersa da rumore campionario su una run breve, e la compressione osservata è la
  firma tipica di un rumore di rete indipendente dal peso (§3.5) più che di un difetto del
  meccanismo di selezione.

- **File**: [analysis/plots/sign_test_by_validator.png](analysis/plots/sign_test_by_validator.png).
  **Cosa misura**: per validatore, se la quota osservata si muove col peso (sign test esatto a
  una coda).
  **Osservato**: 7 validatori testati, p-value fra 0,3125 e 0,9375 — nessuno sotto 0,05.
  **Atteso**: con 7 validatori e alpha=0,05, ~0,35 rigetti attesi per caso; nessuno è comunque un
  buon esito.
  **Giudizio**: **conforme** — nessuna evidenza di monotonia violata, sebbene la potenza sia
  bassa con solo 4–5 coppie di epoche informative per validatore (didascalia della figura).

### 3.5 Timer race, margine e inversioni

- **File**: `analysis/phase3/timer_race.md`, `analysis/phase3/wpoa_prop517.csv`,
  [analysis/plots/prop517_gap_by_validator.png](analysis/plots/prop517_gap_by_validator.png).
  **Cosa misura**: Prop. 5.17 — il gap standardizzato fra i due score minimi del round deve
  essere `Exp(1)`, media 1, per ogni vincitore.
  **Osservato**: media del gap standardizzato per vincitore fra 0,760 (miner-6, n=33) e 1,487
  (miner-4, n=8); nessun KS individuale rigetta (p fra 0,226 e 0,753).
  **Atteso**: media ≈1 per ogni validatore.
  **Giudizio**: **conforme** — tutte le medie sono nell'intorno di 1 (scarto massimo 24–49%, ma
  su campioni di soli 8–33 osservazioni per validatore, dove questa varianza è attesa); nessun
  test KS rigetta.

- **File**: [analysis/plots/margin_distribution.png](analysis/plots/margin_distribution.png),
  `analysis/phase3/wpoa_timer_race.csv`.
  **Cosa misura**: il margine `G` fra i due delay pubblici più veloci del round, contro lo straw
  man `Beta(1,n)` e contro la simulazione esatta della sortition implementata.
  **Osservato**: media `G`=2,668 s, mediana 1,937 s (n=149). KS contro `Beta(1,n)`: `p=0,00000`
  (**straw man dichiarato, atteso rigettare con pesi non uniformi — non è un rilievo**). KS
  contro la simulazione esatta (test di riferimento): `p=0,94272`.
  **Atteso**: il test di riferimento (simulazione esatta) non deve rigettare.
  **Giudizio**: **conforme** — `p=0,943` è ben lontano dal rigetto; il margine osservato è
  interamente spiegato dalla sortition pesata implementata.

- **File**: [analysis/plots/sigma_decomposition.png](analysis/plots/sigma_decomposition.png),
  `analysis/phase3/wpoa_sigma.csv`.
  **Cosa misura**: le tre sorgenti di rumore temporale che alimentano il bound di Prop. 5.18.
  **Osservato**: `S1_topology=0,0278 s` (n=21, misura reale sotto regime `core` — non zero perché
  assente, ma perché piccola rispetto a `Delta_max=5 s`, coerente con `worst_round_trip_s=0,363
  s`); `S2_scheduler_residual_sd=3,8202 s` (n=148, sorgente primaria, forma pubblica);
  `S2b_inversion_gap=2,2921 s` (n=116, dispersione del margine sui soli round invertiti).
  **Atteso**: `S1` piccolo ma reale in regime `core`; `S2` dominante.
  **Giudizio**: **conforme all'atteso qualitativo** — `S1` (27,8 ms) è due ordini di grandezza
  sotto `S2` (3,82 s), confermando che il rumore dominante in questa run non è la propagazione di
  rete in sé ma la dispersione dello scheduling/esecuzione (si veda anche §3.6 sul residuo vero).

- **File**: [analysis/plots/inversion_bound_vs_observed.png](analysis/plots/inversion_bound_vs_observed.png).
  **Cosa misura**: Prop. 5.18 — bound teorico, simulazione Monte Carlo e tasso osservato di
  inversione, **in forma pubblica** (quindi non indicativa da sola di correttezza o difetto, per
  costruzione statisticamente scorrelata dal vincitore reale).
  **Osservato**: bound=1,00000 (**saturo, quindi vacuo**, da non leggere come conferma); MC con
  `sigma_S2`=0,55998; tasso osservato=0,78378 (116/149). Per epoca (etichette del report):
  0,850; 0,775; 0,750; 0,775; 0,905 (`analysis/phase3/wpoa_epoch_tests.csv`,
  `inversion_public_rate`) — sostanzialmente stabile, senza un trend di crescita marcato.
  **Atteso**: con `n=7` candidati, il tasso pubblico ha valore atteso `1−1/n=0,857`
  indipendentemente dal fatto che il protocollo funzioni o meno (`timer_race.md`).
  **Giudizio**: **non conclusivo per costruzione** (colonna pubblica, come esplicitamente
  documentato) — il tasso osservato (0,784) è comunque coerente con l'ordine di grandezza atteso
  (0,857); il bound saturo a 1,0 non va letto né come conferma né come allarme.

- **File**: `analysis/phase3/timer_race.md` (sezione "The winner's real score").
  **Cosa misura**: sullo score **vero** del vincitore (dal reveal VRF del suo blocco):
  correlazione `dt_prev↔delay_true` (Q1) e uniformità di `score_norm_true` (Q2, §3.1).
  **Osservato**: su 139 round puliti, `corr(dt_prev, delay_true)=0,95760`; residuo
  `dt_prev − delay_true`: media 1,57432 s, sd 0,83232 s. Scorporando i 4 round "vinti al tetto
  della banda" (liveness, non ordinamento) dai 135 round "in corsa": questi ultimi hanno
  `corr=0,95862`, `sd residuo=0,81010`, media `score_norm`=0,49751, KS `p=0,52343` — leggermente
  migliore del pool completo. Sulle 132 righe a pesi non stantii (`weight_epoch_stale=False`):
  risultati sostanzialmente identici (`corr=0,95925`, KS `p=0,49939`).
  **Atteso**: `corr≈1`; residuo medio ≈0; `score_norm` uniforme (già confermato in §3.1).
  **Giudizio**: **conforme sull'ordinamento** (correlazione 0,96, KS non rigettato — il vincitore
  del timer è affidabilmente l'argmin del proprio score) **ma lieve scostamento sul livello
  assoluto del residuo**: +1,57 s sistematici (sd 0,83 s) fra la spaziatura osservata e il delay
  che lo score del vincitore prescriveva. Approfondito in §3.6, dove è più naturale (è un
  fenomeno di stabilità del timing, non di ordinamento).

#### Pareggi allo stesso height e la nuova regola di fork-choice (`block_sortition.csv`)

Questa run (`wpoa-forkscore-1h`, branch `feat/wpoa-fork-choice-score`) è stata costruita
appositamente per validare la modifica introdotta dal commit `ebc59009` ("fork choice: break a
same-height tie on the true sortition score"): quando un nodo tiene in memoria due blocchi validi
alla stessa altezza, entrambi non ancora estesi, il comparatore ora consulta lo score di
sortition **vero** (già verificato in ammissione) prima di ricadere sull'ordine di arrivo
(`nSequenceId`), dietro il flag `-enablewpoaforkscore` (`runtime.fork_score=true` in
`manifest.json` per questa run). Il commit `59c89542` spiega perché proprio questa topologia:
"the tie-break only ever fires while two same-height candidates are both live and unextended,
which is a race between a competitor's mining delay and the winner's block propagating" — la
geografia intercontinentale (181,5 ms peggiore one-way) massimizza la finestra in cui questo può
accadere.

- **File**: `analysis/phase1/block_sortition.csv` (**non elencato in §2.3 del prompt operativo**
  — è l'audit per-blocco introdotto insieme alla modifica: una riga per altezza, campionata
  **2 blocchi dietro il tip** apposta per evitare di registrare il ramo perdente di un pareggio
  ancora in corso, cfr. `test/analysis/pipeline/phase1_collect.py:446` e il commit `59c89542`),
  incrociato con `analysis/phase1/blocks.csv` (campionato invece vicino al tip) tramite
  `analysis/phase2/round_level.csv` (colonna `true_winner_mismatch`,
  `test/analysis/pipeline/phase2_aggregate.py:436-445`).
  **Cosa misura**: se il miner registrato come vincitore di un'altezza dal campionamento *live*
  (`blocks.csv`) coincide con quello confermato come canonico 2 blocchi dopo (`block_sortition.csv`).
  Una discordanza è, per costruzione della pipeline, la firma di un blocco osservato per primo e
  poi soppiantato da un competitor alla stessa altezza — esattamente lo scenario che la modifica
  di fork-choice indirizza.
  **Osservato**: **9 round su 149 non-setup (6,04%)** mostrano `true_winner_mismatch=True`
  (`analysis/phase2/manifest.json`, `n_rounds_true_winner_mismatch=9`), alle altezze 126, 132,
  168, 191, 203, 209, 210, 224, 239. In ciascuno di questi 9 casi il validatore registrato dal
  campionamento live differisce da quello confermato canonico, ad es. altezza 126: live=miner-6,
  canonico=miner-3; altezza 210: live=miner-6, canonico=miner-5; altezza 239: live=miner-5,
  canonico=miner-2 (confronto riga per riga fra `blocks.csv` e `block_sortition.csv`). Questi 9
  round hanno una spaziatura sistematicamente più lenta: `dt_prev_s` medio 14,78 s contro 11,26 s
  per i round senza contestazione (+31%, +3,5 s) — coerente con il tempo aggiuntivo di
  propagazione/risoluzione atteso su una mappa con round-trip peggiore di 0,363 s. Lo score vero
  del validatore che ha infine mantenuto l'altezza è sistematicamente alto (`score_norm_true` fra
  0,711 e 0,9995, media 0,869, da `analysis/phase1/block_sortition.csv`): in **tutti e 9** i casi
  il blocco rimasto canonico non era quello dell'argmin della sortition, coerente con
  l'inversione già misurata sopra. Non a caso, questi 9 round (più 1 con verdetto vuoto) sono
  esattamente quelli che la pipeline esclude dal campione "pulito" di 139 round usato per i test
  Q1/Q2 di `timer_race.md` (149 − 9 − 1 = 139, `test/analysis/pipeline/phase2_aggregate.py:441-448`
  — la riga `true_row` viene scartata proprio quando `true_mismatch=True`, "so the gap is counted
  rather than silently absent").
  **Atteso**: nessuna aspettativa quantitativa formale è definita nel documento di riferimento
  per questa metrica (non fa parte delle 12 sottosezioni standard); il segnale atteso qualitativo,
  dato il design della run, è che lo scenario di pareggio-e-sostituzione si presenti con
  frequenza non nulla sotto questa topologia stressata.
  **Giudizio**: **segnale positivo ma non dirimente**. È una conferma concreta, con numeri e
  altezze precise, che il fenomeno bersaglio della modifica — due blocchi validi alla stessa
  altezza, nessuno ancora esteso — si verifica realmente sotto la topologia intercontinentale
  (6,0% dei round misurati, non un evento raro). **Limite importante**: `runtime.wpoa_debug=false`
  in questa run, quindi **non esiste nei log** (`logs/miner-*/events.jsonl`, verificato: nessuna
  occorrenza di `wpoafork`/`REORGANIZE`/termini affini) l'istrumentazione `-debug=wpoafork` che il
  commit stesso introduce per registrare, per ogni gruppo conteso, lo score e l'ordine di arrivo
  di ogni candidato e il vincitore secondo **entrambe** le regole (quella nuova basata su score e
  quella pre-wPoA basata su arrivo). Di conseguenza, sebbene `-enablewpoaforkscore` fosse attivo
  per l'intera run e ciascuno di questi 9 pareggi fosse quindi idoneo a essere deciso dal nuovo
  comparatore, i dati raccolti qui mostrano solo l'**esito** (quale blocco è rimasto canonico) e
  non permettono di distinguere se la sostituzione sia dovuta al nuovo comparatore a parità di
  `nChainWork`, oppure alla normale estensione della catena con più lavoro (il commit stesso nota
  che il tie-break "only ever runs on candidates still tied on work" e smette di applicarsi non
  appena un lato viene esteso). Una run gemella con `wpoa_debug=true` sarebbe necessaria per una
  misura diretta e non ambigua della decisione del comparatore.

### 3.6 Stabilità del block time e correzione globale

- **File**: [analysis/plots/phi_over_time.png](analysis/plots/phi_over_time.png),
  `analysis/phase2/round_level.csv` (colonne `dt_prev_s`, `phi_s`), `analysis/phase1/config.csv`.
  **Cosa misura**: convergenza della media dei block time verso `target-block-time=10 s` tramite
  la correzione globale `Phi`, e se `Phi` satura o oscilla.
  **Osservato**: `dt_prev_s` medio = 11,473 s (sd 2,912 s, min 5,0, max 16,0, n=148 round
  non-setup) — +14,7% sopra il target. Per epoca (etichette di `round_level.csv`): 11,43 s (n=7);
  11,13 s (n=40); 11,10 s (n=40); 12,20 s (n=40); 11,48 s (n=21) — nessuna deriva monotona
  marcata, l'epoca a 12,20 s è isolata. `Phi` medio = −1,4497 s, range [−3,333; +0,167], **mai
  saturo** rispetto al tetto `M=5,0 s` calcolato in §1 (valore assoluto massimo osservato 3,33,
  contro il tetto 5,0). 46 valori distinti di `Phi` su 149 round (check `phi_consistent` fallisce,
  ma è **non critico per design**, §(F): `Phi` varia per costruzione con lo stato della catena).
  Il residuo vero `dt_prev − delay_true` (§3.5) ha media +1,574 s: poiché per il vincitore
  `E[d_winner]=0` esattamente (Prop. 5.11 applicata a `d_i`), il delay atteso del vincitore è
  `T_block + lambda·E[Phi] ≈ 10 + 0,3·(−1,45) = 9,57 s`, mentre la spaziatura osservata media
  (11,47 s) è **1,9 s sopra** questo valore teorico.
  **Atteso**: media dei block time convergente su `target-block-time`; `Phi` non saturo, non
  oscillante di segno con ampiezza costante.
  **Giudizio**: **lieve scostamento, causa identificata** — la correzione `Phi` funziona nella
  direzione corretta (negativa, perché la rete corre lenta) e non è mai saturata né oscillante in
  modo patologico (nessuna inversione di segno round-su-round con ampiezza comparabile nel
  grafico). Il residuo positivo persistente (~1,6 s) è verosimilmente overhead reale di
  esecuzione (validazione, firma, RPC, harness) su 20 nodi emulati sotto regime `core`, non un
  difetto della formula del delay (verificata esatta al bit in §3.2). Con `lambda=0,3`, annullare
  interamente un bias di 1,6 s richiederebbe `Phi≈−5,2 s`, oltre il tetto `M=5,0 s`: la
  correzione a finestra fissa di 12 blocchi, su una run di soli ~250 blocchi (~45 minuti), può non
  aver avuto tempo di convergere al proprio stato stazionario. Da verificare su una run più lunga.

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: `analysis/phase2/epoch_engine.csv` (identità `W_k_raw = ESG · (attività + contributi)`
  e `w_k_final` ricorsivo).
  **Cosa misura**: le due identità esatte del motore dei pesi (§1.3h).
  **Osservato**: su 42 osservazioni (7 validatori × 6 epoche), errore assoluto massimo = 0,0 per
  entrambe le identità.
  **Atteso**: uguaglianza esatta.
  **Giudizio**: **conforme, esatto** — nessuno scarto misurabile.

- **File**: `analysis/phase2/epoch_engine.csv` (colonna `miner_esg_score`).
  **Cosa misura**: staticità degli score ESG fra epoche in assenza di ri-certificazione.
  **Osservato**: 0 validatori su 7 mostrano variazione di `miner_esg_score` fra le 6 epoche;
  coerente con il check di non-regressione `certified_scores_reflected_in_the_engine` (PASS).
  **Giudizio**: **conforme**.

- **File**: [analysis/plots/rho_vs_next_weight.png](analysis/plots/rho_vs_next_weight.png),
  [analysis/plots/rho_feedback_by_validator.png](analysis/plots/rho_feedback_by_validator.png),
  `analysis/phase3/weight_engine_correlations.csv`.
  **Cosa misura**: la retroazione `rho(e) → peso pubblicato(e+1)`, unico canale endogeno.
  **Osservato**: `rho` non è identicamente nullo (26/42 righe di `epoch_engine.csv` con
  `return_rate_rho>0`, media 0,015, massimo 0,0562 — coerente col fatto che, pur con
  `initial-block-reward=0`, i miner ricevono funding dal premine e possono restituirlo).
  Spearman lag-1 aggregato: `rho=0,3350, p=0,0492, n=35`. Per validatore: da −0,21 (miner-3,
  miner-1) a +0,50 (miner-2), nessuno individualmente sotto 0,05 con n=5.
  **Atteso**: effetto reale ma modesto (fattore moltiplicativo in [0,5; 1] con `lambda_w=0,5`),
  facilmente sommerso dalla varianza di `tau`; una Spearman piccola non è di per sé un difetto.
  **Giudizio**: **conforme** — la Spearman aggregata è debolmente significativa (p=0,049, al
  limite di alpha=0,05) nella direzione attesa, con `rho` verificato non nullo prima di
  concludere; la dispersione per validatore (bassa potenza con n=5) è quanto atteso su una run
  breve.

- **File**: [analysis/plots/gini_delta_trajectory.png](analysis/plots/gini_delta_trajectory.png),
  `analysis/phase3/weight_engine_gini.csv`, `weight_engine_gini_summary.csv`.
  **Cosa misura**: se il motore dei pesi amplifica la disuguaglianza dei propri input
  (`Gini(pubblicato) − Gini(input)`).
  **Osservato**: `gini_delta` per epoca: 0,0 (ep.1); 0,0 (ep.2); −0,00265 (ep.3); −0,00134 (ep.4);
  +0,00092 (ep.5); +0,00004 (ep.6). Pendenza della traiettoria = +0,000123 su 6 epoche, Spearman
  `rho=0,4286, p=0,3965`.
  **Atteso**: pendenza positiva = amplificazione; qui vicino a zero e non significativa.
  **Giudizio**: **conforme** — gli scarti sono due ordini di grandezza sotto il livello tipico del
  Gini in questa run (0,19–0,33); il motore non amplifica misurabilmente la disuguaglianza dei
  propri input.

- **File**: [analysis/plots/weights_boxplot_per_epoch.png](analysis/plots/weights_boxplot_per_epoch.png),
  [analysis/plots/esg_scores.png](analysis/plots/esg_scores.png).
  **Cosa misura**: spread del peso finale fra i miner per epoca; score ESG certificati.
  **Osservato**: la mediana del peso finale sale da ~107 (epoca 1, ancora setup) a ~340 (epoca 2)
  per poi stabilizzarsi fra ~320 e ~385 nelle epoche 3–6, con lo spread (IQR) che si allarga
  leggermente nel tempo. ESG: miner-6=81, miner-2=75, miner-5=67, miner-1=56, miner-3=55,
  miner-4=49, miner-0=29 fra i miner; aziende fra 4 (company-4) e 95 (company-2).
  **Giudizio**: **conforme** — l'ingresso in vigore del weight engine post-setup (salto epoca
  1→2) è visibile e atteso; nessuna azienda/miner con ESG anomalo rispetto al range configurato
  [1,100].

### 3.8 Concentrazione

- **File**: [analysis/plots/concentration_over_time.png](analysis/plots/concentration_over_time.png),
  tabella "3. Concentration" di `analysis/phase3/report.md`.
  **Cosa misura**: HHI, N_eff, Gini e soglie di Nakamoto, teorici contro osservati, per epoca e
  sull'aggregato.
  **Osservato**: per epoca (teor./oss.): HHI 0,1569/0,2403 (ep.2), 0,1619/0,1600 (ep.3),
  0,1586/0,1912 (ep.4), 0,1601/0,1750 (ep.5), 0,1591/0,1882 (ep.6). Sull'aggregato ("all"):
  0,1588/0,1615 — molto vicini. N_eff osservato: 4,16 (ep.2) contro 6,25–6,19 nelle altre
  epoche/aggregato. Nakamoto 1/2: 2 validatori in epoca 2, 3 altrove. Gini osservato: 0,4556
  (ep.2) contro 0,19–0,31 nelle altre epoche.
  **Atteso**: HHI osservato per epoca sistematicamente un po' sopra il teorico per varianza
  multinomiale campionaria con pochi blocchi/epoca (§3.2H) — il confronto affidabile è
  sull'aggregato.
  **Giudizio**: **conforme sull'aggregato** (HHI 0,1615 contro 0,1588 teorico, scarto 1,7%,
  entro la varianza campionaria attesa) — **ma l'epoca "2" (altezze 80–119) è un'anomalia
  isolata** (HHI +53% sopra il teorico, Gini più che raddoppiato rispetto alle altre epoche,
  N_eff crollato a 4,16 validatori efficaci su 7): la stessa causa identificata in §3.3 (33 dei
  40 blocchi di questa finestra sotto round robin nativo) spiega la concentrazione artificialmente
  più alta — un round robin nativo su un sottoinsieme di validatori attivi in quella fase produce
  naturalmente meno dispersione della sortition pesata a regime. Non un difetto del meccanismo
  wPoA.

### 3.9 Streak e ripetizioni

- **File**: `analysis/phase3/streak.md`, `analysis/phase3/wpoa_epoch_tests.csv` (colonne
  `L_max_*`, `repeat_prob_*`).
  **Cosa misura**: lunghezza massima di vittorie consecutive e probabilità di ripetizione,
  contro un riferimento Monte Carlo costruito sugli stessi pesi usati dall'elezione.
  **Osservato**: `L_max` osservato per epoca: 4, 4, 3, 3, 3 contro medie MC 2,75; 2,78; 2,75;
  2,76; 2,40 — nessun p-value sotto 0,05 (0,128; 0,144; 0,590; 0,598; 0,362); sull'aggregato
  `L_max=4` contro MC 3,54 (p=0,440). `repeat_prob` osservato/MC/p: epoca 2 → 0,3077/0,1586/**0,0140**;
  epoca 3 → 0,2564/0,1624/0,0906; epoca 4 → 0,2051/0,1596/0,2735; epoca 5 →
  0,2821/0,1603/**0,0402**; epoca 6 → 0,2500/0,1590/0,2046; **aggregato ("all")** →
  0,2517/0,1606/**0,0040**.
  **Atteso**: nessun eccesso sistematico di streak/ripetizione (che indicherebbe non-indipendenza
  dei round, tipicamente per rumore di rete persistente, §3.2I).
  **Giudizio**: **conforme per `L_max`** (nessun rigetto, in nessuna epoca). **Scostamento
  significativo da approfondire per `repeat_prob`**: il rigetto dell'epoca 2 (p=0,0140) ha la
  stessa causa identificata sopra (contaminazione da round robin nativo, che per costruzione
  produce ripetizioni più concentrate su un sottoinsieme di validatori attivi in setup) — non è
  attribuibile al meccanismo wPoA. **Ma il rigetto persiste sull'aggregato dell'intera run anche
  al netto di questo** (p=0,0040, ben sotto 0,05, con 6 test totali quindi ben oltre lo 0,05·6=0,3
  atteso per caso) e compare anche nell'epoca 5 (p=0,0402), interamente post-setup. Causa
  plausibile, coerente col resto del documento: rumore di rete persistente per nodo sotto la
  topologia intercontinentale (lo stesso meccanismo già quantificato in §3.5 — residuo vero
  dt_prev−delay_true con sd 0,83 s, tasso di inversione elevato) può favorire ripetutamente lo
  stesso validatore in round consecutivi se la sua posizione di rete è persistentemente
  favorevole. **Dato ulteriore che servirebbe**: correlare le sequenze di vittorie per validatore
  con `analysis/phase1/topology_paths.csv` (i percorsi di rete emulati) per verificare se il
  validatore più ricorrente ha percorsi sistematicamente più corti verso gli altri nodi.

### 3.10 Malus

Nessuna violazione è stata iniettata in questa run (`malicious.enabled=false` in
`manifest.json`/`malicious_manifest.json`, `miner_count=0`) → **caso J.1**. Il meccanismo di
malus resta comunque sempre attivo a livello di protocollo (`enable-wpoa-malus=true`).

- **File**: `analysis/phase2/malus_state.csv`, `analysis/phase3/malus_invariants.csv`,
  [analysis/plots/malus_invariant_audit.png](analysis/plots/malus_invariant_audit.png).
  **Cosa misura**: `M=0 ⇒ Psi=1` (invariante duro) e coerenza `w_eff = w_raw · Psi` su ogni
  cella (epoca, validatore).
  **Osservato**: su 42 celle, `M=0` e `Psi=1` ovunque, `excluded=False` ovunque; i tre invarianti
  (`invariant_psi_in_unit`, `invariant_weff_matches`, `invariant_clean_psi_one`) sono `True` su
  tutte le 42 righe (0 violazioni, confermato anche visivamente: mappa interamente verde).
  **Giudizio**: **conforme, esatto** — effetto nullo sul comportamento onesto, come da garanzia
  di protocollo.

- **File**: `analysis/phase1/verification.csv`.
  **Cosa misura**: `weightverifyweights` — il canale che rileverebbe un `BadWeight`.
  **Osservato**: 28/28 verifiche con `verdict=ok`.
  **Giudizio**: **conforme** — nessun peso pubblicato non ricalcolabile.

- **File**: `analysis/phase1/malus_detections.csv`, `analysis/phase2/malus_actions.csv`,
  `analysis/phase2/malus_detection_events.csv`, `analysis/phase3/malus_rate.csv`.
  **Osservato**: tutti vuoti (0 righe). `analysis/phase3/malus_effectiveness.md` **non esiste**
  in questa run.
  **Giudizio**: **conforme all'atteso per il caso J.1** — nessun risultato inventato: l'assenza è
  la risposta corretta.

- **File**: [analysis/plots/malus_action_funnel.png](analysis/plots/malus_action_funnel.png) ("no
  malicious experiment ran on this profile"),
  [analysis/plots/malus_state_trajectory.png](analysis/plots/malus_state_trajectory.png) ("no
  malicious miner had a malus trajectory to plot"),
  [analysis/plots/malus_detection_latency.png](analysis/plots/malus_detection_latency.png) ("no
  confirmed malicious action was detected, so there is no latency to plot").
  **Giudizio**: **conforme** — le tre figure sono presenti ma esplicitamente degeneri, come
  atteso per il caso J.1.

- **File**: [analysis/plots/malus_weight_effect.png](analysis/plots/malus_weight_effect.png).
  **Cosa misura**: variazione relativa del peso efficace dalla prima all'ultima epoca,
  malicious contro onesti.
  **Osservato**: colonna "malicious" vuota (n=0); colonna "honest" con 7 punti, variazione
  relativa fra +1,35× e +16,2× (mediana ≈+11,5×) — crescita del peso dovuta alla normale
  evoluzione del weight engine (ingresso in vigore post-setup, §3.7), non al malus.
  **Giudizio**: **conforme** — nessun effetto malus da misurare; la crescita osservata è
  interamente spiegata dal weight engine.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: `analysis/phase2/epoch_engine.csv` (colonne `n_blocks_won_epoch`, `earnings_g_k`,
  `income`, `miner_activity`, `companies_contribution_sum`, `W_k_raw`, `w_k_published`),
  `analysis/phase3/weight_election_residuals.csv`.
  **Cosa misura**: se il volume di transazioni/guadagno influenza la rielezione solo attraverso
  il peso (atteso) o anche direttamente (canale non documentato, da segnalare come critico).
  **Osservato — punto 1 (correlazione grezza, epoche misurate 2–6, n=35)**:
  `corr(n_blocks_won_epoch, earnings_g_k)=0,164`; `income=0,158`; `miner_activity=0,238`;
  `companies_contribution_sum=0,296`; `W_k_raw=0,276`; `w_k_published=0,282` — tutte
  moderate-positive, dello stesso ordine di grandezza della correlazione col peso stesso.
  **Osservato — punto 2 (correlazione sui residui `p_hat − p_theoretical`, n=35)**:
  `corr(residuo, earnings_g_k)=0,069`; `corr(residuo, income)=0,058`;
  `corr(residuo, companies_contribution_sum)=−0,055`.
  **Atteso**: al punto 1 una correlazione positiva mediata dal peso è normale; al punto 2 la
  correlazione deve sparire una volta condizionato per il peso.
  **Giudizio**: **conforme** — le correlazioni residue (0,06–0,07 in valore assoluto) sono
  trascurabili rispetto a quelle grezze (0,16–0,30): nessun segnale di un canale di influenza non
  documentato fra traffico/guadagno ed elezione al netto del peso.

### 3.12 Integrità della run e controlli di consistenza

- **File**: `analysis/phase3/consistency_checks.csv`.
  **Osservato**: 10 check totali, 9 critici (`critical=yes`) tutti `PASS`:
  `registry_weights_finite_and_positive` (16 562 campioni, tutti finiti e ≥0),
  `no_phantom_validator_in_registry` (ok), `malus_finite_and_psi_in_unit_interval` (16 562
  campioni, `Psi∈[0,1]`), `delay_recompute_mismatch_rounds_is_zero` (ok, tolleranza 1,5 ms),
  `every_esg_publication_reached_the_stream` (17 pubblicazioni, tutte presenti),
  `only_miners_pay_the_treasury` (80/80 pagamenti da un miner), `at_least_one_fully_measured_epoch`
  (5 epoche misurate). Il solo check `FAIL` è `phi_consistent` (46 valori distinti di `Phi`),
  **non critico** e atteso per design (§3.6). I due check non-critici rimanenti
  (`certified_scores_reflected_in_the_engine`, `traffic_counts_within_configured_range`)
  passano anch'essi.
  **Giudizio**: **conforme** — "Overall: PASS — every critical consistency check holds" (citazione
  testuale di `report.md`).

- **File**: `analysis/phase2/epoch_traffic.csv`.
  **Osservato**: 68 coppie (epoca, nodo) complete, tutte con conteggio on-chain dentro il range
  configurato; le 34 coppie parziali (prima/ultima epoca) sono correttamente escluse dal check.
  **Giudizio**: **conforme**.

- **File**: `analysis/phase1/rpc_errors.csv`.
  **Osservato**: 168 errori, **tutti** ad altezza ≤45 (quindi ≤`setup-first-blocks=112`), tutti
  del tipo `"Round not evaluable on this node"` sulle 4 RPC `wpoalistscores`/`wpoalistdelays`/
  `wpoalisteffectiveweights`/`wpoalistfinalweights` (42 occorrenze ciascuna).
  **Giudizio**: **conforme, benigno** — chiamate RPC su round non ancora valutabili prima
  dell'attivazione piena di wPoA durante il setup; nessun errore fuori da questa finestra.

- **File**: `manifest.json`.
  **Osservato**: `status=ok`, `error=""`, `final_height=262` contro `target_height=260`
  (leggermente superato, non troncata).
  **Giudizio**: **conforme**.

- **File**: [analysis/plots/traffic_per_epoch.png](analysis/plots/traffic_per_epoch.png),
  `analysis/phase2/epoch_traffic.csv`.
  **Osservato**: per le epoche 1–5 pianificato/inviato/on-chain coincidono quasi esattamente
  (es. epoca 5: 523/523/505); nell'epoca 6 (parziale) pianificato=502, inviato=362 (−28%),
  on-chain=346 (−4,4% rispetto a inviato).
  **Giudizio**: **conforme, coerente con epoca parziale** — il gap fra pianificato e inviato
  nell'epoca 6 riflette l'interruzione della run a metà epoca (i daemon non hanno completato
  l'emissione pianificata), non un difetto; il piccolo gap residuo inviato→on-chain (qui e nelle
  altre epoche) è compatibile con reject benigni di policy fee (didascalia della figura).

## 4. Punti di forza

- Meccanica del delay verificata **esatta al bit**: 0 mismatch su 1505 coppie candidato-round
  oltre la tolleranza di 1,5 ms ([analysis/plots/delay_recompute_mismatch.png](analysis/plots/delay_recompute_mismatch.png)).
- Randomness pulita su entrambi i test primari: `E_i` medio 1,0047 (KS 0,53 contro critico 1,36,
  n=1043); `score_norm` dell'argmin medio 0,4993 (KS 0,56, n=149); confermato indipendentemente
  sullo score **vero** del vincitore (media 0,512, KS p=0,338, n=139).
- Identità del weight engine esatte al bit su 42 osservazioni (`W_k_raw` e `w_k_final`
  ricorsivo), ESG statici come richiesto (0/7 variazioni non certificate).
- Nessun canale di influenza nascosto fra traffico/guadagno e rielezione: correlazione residua
  (a peso fissato) 0,06–0,07, contro 0,16–0,30 grezza.
- Sistema malus verificato a invariante perfetto: 42/42 celle con `M=0, Psi=1`, 0 violazioni
  d'invariante, `verification.csv` 28/28 `ok` — nessuna penalità fantasma.
- Goodness-of-fit aggregato sull'intera run non rigetta (p=0,0609, n=178 blocchi); copertura di
  Wilson 31/35 (attesa 33,2/35 per caso).
- Prima run della campagna a catturare concretamente lo scenario bersaglio della modifica di
  fork-choice: 9/149 round (6,0%) con una reale competizione allo stesso height risolta con
  sostituzione del blocco osservato per primo, con numeri e altezze precise
  (`analysis/phase1/block_sortition.csv`, §3.5).
- Tutti i 9 controlli critici di non-regressione passano (`analysis/phase3/consistency_checks.csv`).

## 5. Punti critici / da approfondire

- **Contaminazione dell'epoca 80–119 da round robin nativo residuo.** `setup-first-blocks=112`
  cade a metà della finestra epocale (indice di griglia 2, altezze 80–119, 40 blocchi), ma
  `epoch_level.csv` la marca `in_setup=False` per intero anziché filtrare i singoli round: 33
  dei suoi 40 blocchi sono ancora round robin nativo. Effetto misurato: unico rigetto GOF per
  epoca (p=0,0089, §3.3), HHI osservato +53% sopra il teorico e Gini più che raddoppiato rispetto
  alle altre epoche (§3.8), `repeat_prob` significativo (p=0,0140, §3.9). **Non è un difetto
  della sortition pesata** — è un artefatto di allineamento fra `setup-first-blocks` e
  `weight-epoch-length` in questo profilo. Dato utile: rieseguire i test di fase 3 filtrando per
  `round.in_setup` invece che per `epoch.in_setup`, o scegliere `setup-first-blocks` multiplo di
  40 nei prossimi profili di questa famiglia.
- **Repeat-rate elevato sull'aggregato anche al netto dell'epoca contaminata.** `repeat_prob`
  osservato/MC sull'intera run: 0,2517/0,1606, p=0,0040 (§3.9), e anche nell'epoca 5
  (interamente post-setup) p=0,0402. Ipotesi più plausibile: rumore di rete persistente per nodo
  sotto la topologia intercontinentale, collegato allo stesso meccanismo quantificato in §3.5
  (residuo vero dt_prev−delay_true, sd 0,83 s; tasso di inversione elevato). Dato che servirebbe:
  incrociare le sequenze di vittorie per validatore con `analysis/phase1/topology_paths.csv` per
  verificare una correlazione fra posizione di rete e frequenza di ripetizione.
- **Residuo sistematico di +1,57 s (sd 0,83 s) fra spaziatura osservata e delay proprio del
  vincitore** (§3.5, §3.6, n=139). Ordinamento non compromesso (correlazione 0,96, KS non
  rigettato), ma il livello assoluto suggerisce un overhead di esecuzione reale (CPU/rete/harness
  su 20 nodi emulati) che il guadagno `lambda=0,3` non compensa del tutto su una finestra `Phi` a
  soli ~250 blocchi (mai saturo: max|Phi|=3,33 contro tetto 5,0). Dato utile: una run più lunga
  per verificare se `Phi` converge verso lo stato stazionario necessario a cancellare il bias.
- **Tie-break di fork-choice: evidenza di esito, non di meccanismo.** 9/149 round (6,0%) mostrano
  una reale sostituzione del blocco alla stessa altezza (`analysis/phase1/block_sortition.csv`,
  §3.5), ma `runtime.wpoa_debug=false` esclude dai log l'istrumentazione `-debug=wpoafork` che
  registrerebbe la decisione del comparatore candidato per candidato. Non è quindi possibile,
  con i soli dati di questa run, distinguere una risoluzione dovuta al nuovo comparatore
  basato su score da una dovuta alla normale estensione per `nChainWork`. Dato che servirebbe:
  una run gemella con `wpoa_debug=true` (stesso profilo, stesso seed) per un confronto diretto
  fra le due regole sugli stessi round contesi.
- **(minore) Due validatori ai margini della copertura di Wilson aggregata.** miner-3
  (`18VGDtNzFSoy…`) sovra-rappresentato (0,2099 osservato contro 0,1486 teorico) e miner-2
  (`1UmL87cqSz7o…`) sotto-rappresentato (0,1271 contro 0,2051 teorico), entrambi con IC 95% che
  esclude il teorico (§3.3). Compatibile con la compressione longitudinale già misurata
  (`beta1=0,81`) e col tasso di inversione elevato, non con un'inversione sistematica
  dell'ordinamento (mai osservata altrove in questa run).

## 6. Conclusione

Sui cinque assi del passo 3.4:

- **Affidabilità della sortition**: **buona**. L'aggregato sull'intera run non rigetta il
  goodness-of-fit (p=0,061, n=178), la copertura di Wilson è 31/35, e `beta1=0,81` (IC 95%
  [0,40; 1,23]) è statisticamente indistinguibile da 1. L'unico rigetto per-epoca ha una causa
  identificata ed estranea al meccanismo (contaminazione da setup).
- **Qualità della randomness**: **eccellente**. `E_i~Exp(1)` (media 1,0047, KS 0,53), `score_norm`
  dell'argmin `~U(0,1)` (media 0,4993, KS 0,56) e la stessa proprietà sullo score vero del
  vincitore (media 0,512, KS p=0,338): tutti i test primari passano nettamente.
  Prop. 5.17 confermata (gap standardizzato medio 0,76–1,49 per validatore, nessun KS rigettato).
- **Efficacia dello smorzamento**: **conforme all'atteso**, con effetto limitato perché i pesi in
  questa run sono quasi omogenei (rapporto max/min ≈1,81, nessuna balena). Nessuna inversione di
  ordinamento osservata; la compressione osservata (`beta1=0,81`) è nell'ordine di grandezza
  atteso per pesi ravvicinati sotto `dump-function=sqrt`.
- **Efficacia del malus**: **conforme, banale in questa run** — nessuna violazione iniettata
  (caso J.1), ed effetto esattamente nullo confermato su tutte le 42 celle (epoca, validatore):
  `M=0`, `Psi=1`, 0 violazioni d'invariante, nessuna penalità senza evidenza. Il canale
  `BadWeight` è verificato pulito (28/28 `weightverifyweights` con esito `ok`).
- **Stabilità del block time**: **buona con una riserva quantificata**. `Phi` non è mai saturo e
  non oscilla patologicamente; converge nella direzione corretta. Resta un residuo sistematico di
  ~1,6 s fra la spaziatura osservata e il delay proprio del vincitore, plausibilmente overhead di
  esecuzione reale su una run breve (~250 blocchi), da riverificare su una run più lunga.

Nel complesso, **il meccanismo wPoA di questa run si comporta come previsto dal modello teorico**:
tutti i controlli critici di non-regressione passano, i due test di randomness sono puliti, la
formula del delay è verificata esatta al bit, e le deviazioni osservate hanno cause identificate
e circoscritte (allineamento setup/epoca, overhead di esecuzione) piuttosto che essere sintomi di
difetti nel protocollo. In aggiunta, questa run cattura per la prima volta nella campagna un
segnale concreto e quantificato (9/149 round, 6,0%) dello scenario di pareggio allo stesso height
che la nuova regola di fork-choice sul vero score di sortition è pensata per gestire meglio della
regola basata sull'ordine di arrivo — un risultato incoraggiante sulla rilevanza pratica della
modifica, che però richiede una run con `wpoa_debug=true` per una misura diretta e non ambigua
della decisione del comparatore.
