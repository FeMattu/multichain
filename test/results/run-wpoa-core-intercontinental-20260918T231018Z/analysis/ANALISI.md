# Analisi della run `run-wpoa-core-intercontinental-20260918T231018Z`

Run: `test/results/run-wpoa-core-intercontinental-20260918T231018Z`
Timestamp UTC della run: **2026-09-18T23:10:18Z**
Catena: `wpoa-core-intercontinental` — profilo: `test/config/profiles/core/intercontinental-long20h.yaml` — regime: **core** (rete emulata)
Analisi prodotta il: 2026-09-20

---

## 1. Configurazione della run

| Parametro | Valore | Fonte |
|---|---|---|
| chain_name | `wpoa-core-intercontinental` | [manifest.json](../manifest.json) |
| seed dell'esperimento | `20260905` | manifest.json |
| regime / fabric | **core** — una namespace per sito, netem sui cavi | manifest.json `fabric.backend` |
| topologia | `intercontinental`: **20 siti, 7 hub, 34 link** | manifest.json `fabric.topology` |
| percorso peggiore fra due siti | **181,522 ms** (round trip peggiore 0,363 s) | manifest.json `derived` |
| nodi | 1 admin, 2 CA, **10 miner**, 20 company (33 totali) | manifest.json `nodes` |
| epoche | **60 epoche × 120 blocchi** | manifest.json `epochs` |
| `setup-first-blocks` | **240** → epoca 1 esclusa (round robin nativo) | [phase1/config.csv](phase1/config.csv) |
| altezza finale | `7343` (target derivato `7340`) — run **completata**, `status = ok` | manifest.json |
| **`dump-function`** | **`sqrt`** → `g(w) = √w` (compressione moderata) | phase1/config.csv |
| `target-block-time` | **10 s** | phase1/config.csv |
| `wpoa-sortition-delta` (δ) | **0.5** → `Δ_max = 5,0 s` | phase1/config.csv |
| `wpoa-sortition-lambda` (λ) | **0.3** | phase1/config.csv |
| bound del feedback `M` | **5,0 s** = `min(0,5·T, T(1−δ)/λ) = min(5,0; 16,67)` | ricavato |
| malus: `mu`, `M_max` | `0.5`, `4.0` | phase1/config.csv |
| malus: punti per kind | equiv `4.0`, badweight `2.0`, selfwrite `1.0`, delay `0.25` | phase1/config.csv |
| `enable-wpoa-malus` | `true` (meccanismo **sempre attivo**) | phase1/config.csv |
| **violazioni iniettate** | **NO** — `malicious.enabled = false`, 0 miner malicious | [malicious_manifest.json](../malicious_manifest.json) |
| `weight-kappa` (κ) | `100.0` | phase1/config.csv |
| `weight-lambda` (λ_w) | `0.5` | phase1/config.csv |
| `weight-alpha` | `0.2` — **parametro inerte**, validato e mai letto | phase1/config.csv |
| `weight-epoch-length` | `120` | phase1/config.csv |
| `wpoa-randao-lookback` | `121` | phase1/config.csv |
| `mining-diversity` | **`0.0`** → spacing nativo non vincolante | phase1/config.csv |
| `mining-turnover` | `0.5` (euristica locale nativa, senza effetto su wPoA) | phase1/config.csv |
| `initial-block-reward` | **`0`** → nessuna ricompensa da mining | phase1/config.csv |
| traffico: tx per azienda/epoca | `[40, 80]` | manifest.json `traffic` |
| traffico: restituzioni per miner/epoca | `[0, 7]`, importi in `[1.0, 100.0]` | manifest.json `traffic` |
| traffico: range score ESG | `[1, 100]` | manifest.json `traffic` |
| `miner_seed_gas` | `50 600` | manifest.json `derived` |

**Pesi "iniziali" e geografia.** I pesi non sono configurati: emergono da `ESG × τ`. Gli score
ESG certificati dei 10 miner sono **29, 43, 49, 55, 56, 67, 75, 76, 81, 95**; quelli delle 20
aziende vanno da 4 a 99. I pesi grezzi pubblicati a fine run spaziano da **67 845 a 515 385**
(rapporto **7,60×**), in unità fixed-point ×100 del registro (verificato:
`w_k_published = 100 × w_k_final` su 610 righe, deviazione relativa 1,8·10⁻⁸). Sono un **esito
stocastico del seed**, non una configurazione.

**Collocazione geografica dei validatori** (da `manifest.json` e
[phase1/topology_paths.csv](phase1/topology_paths.csv)), con il ritardo medio di percorso verso
gli altri 9 validatori — la variabile che risulterà decisiva in §3.5:

| miner | sito | ritardo medio verso gli altri validatori |
|---|---|---:|
| miner-1 | frankfurt-i | **60,69 ms** |
| miner-0 | milano-i | **60,83 ms** |
| miner-2 | new-york | 66,64 ms |
| miner-6 | johannesburg | 78,55 ms |
| miner-4 | sao-paulo | 80,09 ms |
| miner-5 | tokyo | 81,22 ms |
| miner-3 | singapore | 85,77 ms |
| miner-8 | seoul | 89,26 ms |
| miner-9 | buenos-aires | 91,40 ms |
| miner-7 | los-angeles | **92,01 ms** |

---

## 2. Executive summary

1. **La randomness è impeccabile.** `E_i ~ Exp(1)` su 71 010 campioni: media **0,999159**
   (IC95 [0,99264 – 1,00736]), varianza 1,004, KS `√n·D = 0,788` contro un critico di 1,358
   (p = 0,564). Lo score normalizzato dell'argmin è `U(0,1)`: media **0,496258**, KS p = 0,507.
2. **Il calcolo del delay è esatto** su tutte le 71 010 coppie candidato-round, entro
   **1,4·10⁻¹³ s** contro una tolleranza di 1,5 ms.
3. **La timer race non elegge il vincitore della sortition**, esattamente come nella run
   `native`: inversione **0,9103**, rank del produttore quasi piatto (rank 1 al **8,97 %**
   contro il 10 % del caso), correlazione fra block time e delay **+0,014**.
4. **Il rumore non viene dalla rete.** `σ_S1` (topologia) = **0,035 s**, `σ_S2` (residuo dello
   scheduler) = **3,469 s**: la propagazione pesa l'**1 %**. Il valore di `σ_S2` è
   indistinguibile da quello della run `native` (3,482 s), che gira su loopback senza alcuna
   rete: **la sorgente è locale al nodo, non la geografia**.
5. **Ma la geografia sposta le quote.** Sulla finestra pulita (epoche 2–53) la correlazione fra
   ritardo medio di percorso e scarto di quota è **Pearson −0,889**: i tre validatori più
   centrali sono tutti sovra-rappresentati (z = **+4,92**, **+3,60**, **+2,82**), i periferici
   sotto-rappresentati. Controllando per la quota attesa, la correlazione parziale resta
   **−0,670** (t = −2,39 su 7 gdl, **p = 0,048**).
6. **Questa volta lo scostamento dalle quote attese è reale.** A differenza della run `log`, non
   si spiega con la dipendenza fra round: dopo la correzione per il VIF (1,370) il chi-quadro
   aggregato sulle epoche 2–53 resta **53,67 su 9 gdl, p = 2,2·10⁻⁸**, e l'istogramma dei p-value
   mostra un **picco** in `[0; 0,1]` (28 epoche su 60 contro 6 attese) — firma di una media
   sbagliata, non di una varianza sottostimata.
7. **L'ordinamento è però preservato e la monotonia è dimostrata.** Spearman quota attesa ↔
   osservata sui 10 validatori = **+0,879**; sign test aggregato **312/532 = 0,5865**,
   z = +3,99, **p = 3·10⁻⁵**, con 5 validatori su 10 significativi singolarmente.
8. **La selezione è compressa verso l'uniforme di circa il 30 %**: regressione della quota
   osservata sulla quota attesa con pendenza **0,700**; GLM logit `β₁ = 0,8418`, IC95
   **[0,7340 – 0,9496]**, che **esclude 1**; regressione dei log-rapporti con pendenza 0,8603.
9. **Due validatori si sono fermati durante la run.** **miner-5** non produce blocchi
   dall'epoca 54 (0 blocchi in 861 round con quota attesa 11,75 %: `P = 10⁻⁴⁶,⁷`) e **miner-2**
   dall'epoca 59. Entrambi restano **connessi, sincronizzati, autorizzati ed eleggibili con peso
   pieno**: il peso del cluster è retto dall'attività delle sue aziende, che non si è fermata.
10. **Il block time non converge**: media **11,425 s** contro 10 s (**+14,25 %**), con deriva
    lieve (Spearman epoca↔block time +0,262, p = 0,044). `Φ` misura l'errore correttamente, non
    è saturato (|Φ|max = 3,67 s contro M = 5,0 s) e non oscilla: l'anello è **aperto**, come
    nella run `native`.
11. **Il malus si comporta come deve in assenza di violazioni**: `M = 0`, `Ψ = 1` su tutte le
    610 coppie, 3/3 invarianti verificati.

---

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

#### `E_i ~ Exp(1)`

- **File**: derivato da [phase2/candidate_long.csv](phase2/candidate_long.csv) come
  `E_i = score × weight_effective`, righe `in_setup = False` (71 010 su 7 101 round).
- **Osservato**: media **0,999159**, varianza **1,00366**, KS `D = 0,002955`,
  `√n·D = 0,7875`, **p = 0,564**. Istogramma contro la densità teorica:

  | bin | osservato | teorico |
  |---|---:|---:|
  | [0; 0,25) | 22,221 % | 22,120 % |
  | [0,25; 0,5) | 17,360 % | 17,227 % |
  | [0,5; 0,75) | 13,333 % | 13,416 % |
  | [1; 1,5) | 14,422 % | 14,475 % |
  | [2; 3) | 8,469 % | 8,555 % |
  | [4; 6) | 1,674 % | 1,584 % |

- **Atteso**: media 1 (IC95 [0,99264 – 1,00736]), varianza 1, `√n·D ≤ 1,358`.
- **Giudizio**: **conforme**. La media è entro lo **0,08 %** dal valore teorico; il KS è al 58 %
  del critico.

#### `score_norm` dell'argmin `~ U(0,1)` (Prop. 5.11)

- **Osservato**: minimo di `score_norm` per round, 7 101 valori: media **0,496258**,
  KS `D = 0,009753`, `√n·D = 0,8219`, **p = 0,507**.
- **Atteso**: media 0,5 (IC95 [0,49329 – 0,50671]).
- **Giudizio**: **conforme**, entro lo **0,75 %**.

> **Trappola confermata anche qui**: lo `score_norm` delle righe con `is_winner = True` ha media
> **0,9099**, che è il valore atteso per un candidato *qualsiasi* (con 10 pesi vicini,
> `E[score_norm] ≈ 1 − 1/11 = 0,909`), non una violazione di Prop. 5.11. Il test corretto è sul
> minimo per round.

#### Coerenza della normalizzazione

- `score_norm_mismatch`: massimo **1,40·10⁻¹⁴**, media 6,1·10⁻¹⁶ su 71 010 righe.
- **Giudizio**: **conforme** (arrotondamento in doppia precisione).

#### Prop. 5.17 — gap standardizzato

- **File**: [phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv),
  [plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png).
- **Osservato**: media dei gap sulle 10 classi **1,0054**; valori da 0,9503 (miner-6) a 1,1046
  (miner-8). Il KS rigetta in **1 classe su 10** (miner-2, p = 0,0056).
- **Atteso**: media 1,0 per classe, ~0,5 rigetti su 10 test ad α = 0,05.
- **Giudizio**: **conforme**. La media aggregata è entro lo **0,54 %** da 1 e il conteggio di
  rigetti è compatibile con il caso.

### 3.2 Correttezza meccanica del delay

- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv),
  [phase3/consistency_checks.csv](phase3/consistency_checks.csv),
  [plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png).
- **Osservato**: `delay_recompute_ok = True` su **71 010/71 010**; scarto massimo
  **1,40·10⁻¹³ s**, medio 6,1·10⁻¹⁵ s. La figura mostra tutti i punti fra 10⁻¹⁸ e 10⁻¹³ s contro
  la tolleranza a 1,5·10⁻³ s; la didascalia riporta *"0 of 72150 candidate-rounds disagree"*. Il
  check critico `delay_recompute_mismatch_rounds_is_zero` è **PASS**.
- **Giudizio**: **conforme**, con **10 ordini di grandezza** di margine.

> Come nella run `native`: questo prova che harness e nodo **calcolano** la stessa formula, non
> che lo scheduler la **onori**.

### 3.3 Quota di blocchi contro peso — **scostamento reale**

- **File**: [phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [phase3/wpoa_epoch_validators.csv](phase3/wpoa_epoch_validators.csv),
  [phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [plots/weight_vs_election.png](plots/weight_vs_election.png),
  [plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png),
  [plots/p_value_uniformity.png](plots/p_value_uniformity.png),
  [plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png),
  [plots/election_share_distribution.png](plots/election_share_distribution.png).

#### Questa volta la run ha potenza statistica

| Quantità | Valore |
|---|---|
| pesi grezzi, rapporto max/min | **7,60×** (67 845 → 515 385) |
| pesi efficaci `√w`, rapporto max/min | **2,76×** (260,47 → 717,90) — esattamente `√7,60` |
| `p_theoretical`, intervallo | **0,0601 – 0,1617** (ampiezza **0,1016**) |
| spread intra-epoca medio | **0,0736** |
| larghezza media dell'intervallo di Wilson | **0,1081** |
| **rapporto segnale / risoluzione** | **0,940** |

Ricalcolando le quote attese sugli stessi pesi grezzi:

| `dump-function` | spread medio delle quote | quota massima media | rapporto max/min |
|---|---:|---:|---:|
| `none` — `g(w)=w` | 0,1504 | 0,1973 | **4,31×** |
| **`sqrt` — `g(w)=√w` (questa run)** | **0,0739** | **0,1439** | **2,07×** |
| `log` — `g(w)=ln(1+w)` | 0,0119 | 0,1064 | 1,13× |

Lo smorzamento a radice comprime il vantaggio da 4,31× a **2,07×**, coerentemente in direzione e
ordine di grandezza con il riferimento teorico (caso a balena: 10× → 3,2×). A differenza della
run `long24h-large-log`, dove il segnale era **7,2× più piccolo** della risoluzione, qui i due
sono dello stesso ordine: **la proporzionalità è testabile**. Lo scatter di
[plots/weight_vs_election.png](plots/weight_vs_election.png) mostra infatti una nuvola con
ascissa reale (0,06–0,17) e struttura diagonale visibile.

#### Copertura di Wilson e goodness of fit

| Test | Tutte le epoche 2–61 | Epoche 2–53 (prima del guasto di miner-5) |
|---|---|---|
| blocchi | 7 101 | 6 240 |
| Wilson: violazioni | **81/600** (attese 30,0), p = 1,1·10⁻¹⁵ | **60/520** (attese 26,0), p = 2,6·10⁻⁹ |
| GoF per epoca | **22/60** rigetti (attesi 3,0) | **15/52** (attesi 2,6) |
| chi-quadro aggregato | 109,264 su 9 gdl, **p = 2,1·10⁻¹⁹** | 73,539 su 9 gdl, **p = 3,1·10⁻¹²** |
| MAE delle quote | 0,00904 | 0,00926 |
| MaxAE | 0,02709 | 0,01967 |
| uniformità dei p-value | KS `D = 0,4521`, p ≈ 0 | — |

Le violazioni di Wilson non sono uniformi sui validatori: **miner-5 ne ha 16**, seguito da
miner-2 (9), miner-1, miner-9, miner-6, miner-4 (8 ciascuno), fino a miner-3 (5).

#### La correzione per la dipendenza fra round **non** basta a spiegarlo

Come nella run `native`, i round non sono indipendenti (§3.9) e i test lo assumono. Calcolando il
fattore di inflazione della varianza dall'autocorrelazione lag-1:

| | Tutte 2–61 | Epoche 2–53 |
|---|---|---|
| VIF medio | **1,3992** | **1,3702** |
| chi-quadro aggregato corretto | 78,088, **p = 3,9·10⁻¹³** | 53,671, **p = 2,2·10⁻⁸** |
| GoF per epoca corretti | **12/60** (attesi 3,0) | **6/52** (attesi 2,6) |
| Wilson attese col VIF / osservate | 42 / **81**, p = 1,5·10⁻⁸ | 36 / **60**, p = 6,4·10⁻⁵ |

- **Confronto decisivo con la run `long24h-large-log`**: là la stessa correzione portava i
  rigetti GoF da 14/100 a 6/100 contro 5 attesi e il chi-quadro aggregato a p = 0,095, cioè
  **riconciliava tutto**. Qui, sulla finestra pulita, restano **6 rigetti contro 2,6 attesi** e
  un chi-quadro a **p = 2,2·10⁻⁸**: lo scostamento sopravvive.
- **La forma dell'istogramma conferma la diagnosi**. In
  [plots/p_value_uniformity.png](plots/p_value_uniformity.png) i p-value mostrano un **picco
  netto** nel primo decile (**28 epoche su 60** contro 6 attese) seguito da un profilo quasi
  piatto — la firma di una **media mal specificata**. Nella run `log` lo stesso istogramma
  mostrava un'inclinazione graduale, firma di una sola **varianza** sottostimata. Le due run si
  distinguono qui, non nei conteggi di rigetto.
- **Giudizio**: **scostamento significativo da indagare**. La causa è identificata in §3.5.

#### Il quadro aggregato

| miner | quota attesa | quota osservata | O_i | atteso | scarto (p.p.) | z |
|---|---:|---:|---:|---:|---:|---:|
| miner-9 | 0,1431 | 0,1366 | 970 | 1016,4 | −0,653 | −1,57 |
| miner-5 | 0,1276 | 0,1005 | 714 | 906,4 | **−2,709** | **−6,84** |
| miner-2 | 0,1166 | 0,1203 | 854 | 828,2 | +0,363 | +0,95 |
| miner-6 | 0,1070 | 0,1062 | 754 | 759,7 | −0,080 | −0,22 |
| miner-1 | 0,0926 | 0,1139 | 809 | 657,3 | **+2,136** | **+6,21** |
| miner-4 | 0,0890 | 0,0934 | 663 | 632,0 | +0,437 | +1,29 |
| miner-8 | 0,0886 | 0,0893 | 634 | 629,0 | +0,070 | +0,21 |
| miner-3 | 0,0863 | 0,0828 | 588 | 612,6 | −0,347 | −1,04 |
| miner-7 | 0,0786 | 0,0713 | 506 | 557,9 | −0,731 | −2,29 |
| miner-0 | 0,0706 | 0,0858 | 609 | 501,5 | **+1,514** | **+4,98** |

- **Ordinamento preservato**: Spearman quota attesa ↔ osservata = **+0,879**, ben sopra il
  critico 0,648 per n = 10.
- **Compressione verso l'uniforme**: la regressione della quota osservata sulla quota attesa dà
  `osservata = +0,0300 + 0,700 × attesa`. Pendenza 1 significherebbe proporzionalità, pendenza 0
  indipendenza totale: **il 30 % del segnale è perso**. Il modello di pura compressione uniforme
  non basta però a spiegare i dati (chi-quadro residuo 80,08 su 8 gdl), perché sopra di esso si
  sovrappone l'effetto geografico di §3.5.
- **Il boxplot dei residui** ([plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png))
  mostra, a differenza della run `native`, **offset persistenti per validatore**: miner-1 con box
  interamente sopra lo zero (media **+0,022**), miner-0 sopra (**+0,016**), miner-5 sotto
  (**−0,029**). Non sono fluttuazioni: sono sovra- e sotto-rappresentazioni sistematiche.
- **Quote cumulative** ([plots/election_share_distribution.png](plots/election_share_distribution.png)):
  da 7,1 % (miner-7) a 13,7 % (miner-9).

### 3.4 Comportamento longitudinale

- **File**: [phase3/longitudinal.md](phase3/longitudinal.md),
  [phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv),
  [plots/longitudinal_logratio.png](plots/longitudinal_logratio.png),
  [plots/sign_test_by_validator.png](plots/sign_test_by_validator.png).

| Test | Osservato | Atteso | Giudizio |
|---|---|---|---|
| GLM logit su `log(peso)` | `β₁ = 0,8418`, IC95 **[0,7340 – 0,9496]**, se = 0,055, n = 600, converged | `β₁ = 1` | **H0 rigettata**: l'IC **non contiene 1** |
| Regressione dei log-rapporti | pendenza **0,8603**, intercetta **+0,0146**, Pearson r = **0,4464** (p ≈ 0), n = 2588 | pendenza 1, intercetta 0 | pendenza sotto 1, coerente col GLM |
| Sign test per validatore | 5/10 significativi: miner-1 (0,691, p = 0,0032), miner-2 (0,673, p = 0,0088), miner-5 (0,653, p = 0,0222), miner-4 (0,636, p = 0,0290), miner-6 (0,630, p = 0,0380) | concordanza > 0,5 | **concordanza aggregata 312/532 = 0,5865, z = +3,99, p = 3·10⁻⁵** |

- **Osservato**: la nuvola in [plots/longitudinal_logratio.png](plots/longitudinal_logratio.png)
  ha un'ascissa reale (±0,8) e una retta stimata leggermente sotto la diagonale.
- **Giudizio**: **la monotonia è confermata in modo robusto** (sign test p = 3·10⁻⁵), **la
  proporzionalità no**: `β₁ = 0,84` e pendenza 0,86 dicono entrambe che la quota risponde al peso
  **meno che proporzionalmente**. È il medesimo 30 % di compressione misurato in §3.3 su un'altra
  scala.
- **Confronto con la run `native`/`log`**: là `β₁ = 1,3661` con IC95 largo 1,0 unità (test senza
  potere) e sign test aggregato p = 0,068. Qui l'IC è largo 0,22 e il test discrimina.

### 3.5 Timer race, margine e inversioni — **la causa dello scostamento**

- **File**: [phase3/timer_race.md](phase3/timer_race.md),
  [phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv), [phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [phase1/topology_paths.csv](phase1/topology_paths.csv),
  [phase2/round_level.csv](phase2/round_level.csv),
  [plots/margin_distribution.png](plots/margin_distribution.png),
  [plots/sigma_decomposition.png](plots/sigma_decomposition.png),
  [plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png).

#### Il margine calcolato è corretto

- `G_mean` osservato **2,6718 s**, mediana 2,0628 s su 7 101 round.
- KS contro la **simulazione esatta** della sortition implementata: `D = 0,00826`,
  **p = 0,859** — il test di riferimento non rigetta; media simulata 2,6640 s contro osservata
  2,6718 s (**0,3 %** di scarto).
- Il KS contro `Beta(1,n)` dà p = 0 ma è uno **straw man dichiarato**: **non è un rilievo**.
- **Giudizio**: **conforme**.

#### Il produttore è quasi indipendente dai delay

| Quantità | Osservato | Riferimento |
|---|---:|---|
| tasso di inversione | **0,91028** | `1 − 1/n = 0,900` se il produttore fosse uniforme fra i 10 |
| inversione simulata MC con `σ_S2` | 0,58259 | ciò che il rumore gaussiano predirebbe |
| bound di Prop. 5.18 | **1,00000** | **vacuo** |
| rank di sortition del produttore, a rank 1 | **8,97 %** | 10,00 % |
| Pearson(block time, delay del produttore) | **+0,0136** | 1 se il delay governasse |
| Pearson(block time, delay dell'argmin) | **+0,0309** | — |

La distribuzione dei rank del produttore è quasi piatta (637, 775, 753, 700, 682, 758, 707, 642,
731, 715) ma **non esattamente uniforme**: chi-quadro **27,73 su 9 gdl, p = 0,0011**, con il
rank 1 a z = **−2,89**. Non c'è alcuna struttura monotona nei ranghi: il vincitore designato
vince, se mai, **meno** del caso, non di più.

#### Il rumore non è la rete

| Sorgente | σ | n |
|---|---:|---:|
| `S1_topology` | **0,034991 s** | 45 |
| `S2_scheduler_residual_sd` | **3,469049 s** | 7 100 |
| `S2b_inversion_gap` | 2,270859 s | 6 463 |

**La propagazione pesa l'1 %** del rumore totale. E il valore di `σ_S2` qui (3,469 s) è
indistinguibile da quello della run `native` (3,482 s), che gira su loopback **senza alcuna
rete**: la differenza è dello **0,4 %**. Il residuo dello scheduler (`dt_prev − delay_winner`) ha
media **−2,249 s** e sd 3,469 s, contro −2,298 s e 3,482 s in `native`. **La sorgente del rumore
è locale al nodo e identica nei due regimi.**

#### Eppure la posizione in rete sposta le quote

Correlando il ritardo medio di percorso verso gli altri validatori con lo scarto di quota
aggregato, **sulla finestra pulita 2–53** (esclusi gli 8 epoch di guasto di miner-5, §3.10):

| miner | sito | ritardo medio | scarto (p.p.) | z |
|---|---|---:|---:|---:|
| miner-1 | frankfurt-i | 60,69 ms | **+1,834** | **+4,92** |
| miner-0 | milano-i | 60,82 ms | **+1,187** | **+3,60** |
| miner-2 | new-york | 66,64 ms | **+1,169** | **+2,82** |
| miner-6 | johannesburg | 78,55 ms | −0,359 | −0,90 |
| miner-4 | sao-paulo | 80,09 ms | +0,016 | +0,04 |
| miner-5 | tokyo | 81,22 ms | −1,282 | −2,97 |
| miner-3 | singapore | 85,77 ms | −0,665 | −1,83 |
| miner-8 | seoul | 89,26 ms | −0,202 | −0,55 |
| miner-9 | buenos-aires | 91,40 ms | −0,888 | −1,97 |
| miner-7 | los-angeles | 92,01 ms | −0,810 | −2,34 |

- **Pearson = −0,8885**, **Spearman = −0,7939** (critico 0,648 per n = 10). I **tre validatori
  più centrali sono gli unici tre con scarto positivo**, tutti con z fra +2,8 e +4,9; **tutti i
  quattro più periferici hanno scarto negativo**.
- Su tutte le epoche 2–61 la correlazione resta Pearson −0,674 / Spearman −0,782; escludendo
  miner-5 (che ha il guasto) sale a Pearson **−0,898** / Spearman **−0,883**.
- **La latenza non è confusa con il peso**: `corr(latenza, quota attesa) = +0,224`. La
  correlazione **parziale** fra latenza e scarto, controllando per la quota attesa, vale
  **−0,670** (t = −2,39 su 7 gdl, **p = 0,048**); quella fra quota attesa e scarto controllando
  per la latenza vale −0,519 (t = −1,61, p = 0,152, **non significativa**).
- Regressione a due variabili: `scarto(pp) = +7,304 − 0,0642·latenza(ms) − 0,225·quota_attesa(pp)`,
  **R² = 0,601**. Da sola la latenza spiega R² = 0,454; da sola la quota attesa R² = 0,275.
- **Entità**: **−0,64 punti percentuali ogni 10 ms** di ritardo medio. Sull'escursione osservata
  (60,7 → 92,0 ms) fanno **circa 2,0 punti percentuali**, cioè un **±20 % relativo** su quote
  dell'ordine del 10 %.

- **Atteso**: la probabilità di elezione deve valere `g(w_i)/Σg(w_k)`, **indipendentemente dalla
  posizione in rete**.
- **Giudizio**: **scostamento significativo da indagare — è il risultato principale di questa
  run.** La geografia compra blocchi.
- **Ipotesi sul meccanismo**: la Proposizione 5.18 modella la latenza come rumore additivo **a
  media nulla**, che non favorisce sistematicamente nessuno. Su una mappa reale la latenza ha
  invece una **media per nodo diversa da zero**: un validatore centrale riceve il blocco `n`
  prima degli altri e **arma il proprio timer prima**, ottenendo un vantaggio costante pari al
  proprio anticipo di propagazione. Un offset sistematico non si media a zero: si somma round
  dopo round. Questo è coerente con il fatto che `σ_S1` sia irrilevante nel bound (0,035 s) ma la
  *media* di percorso sia fortemente predittiva, e con il fatto che i blocchi arrivino 2,25 s
  **prima** del delay del loro produttore — la corsa reale non si decide al confine della banda
  `Δ_max`, ma in una finestra molto più stretta dove 30 ms contano.
- **Cosa servirebbe per confermare**: gli istanti di armamento del timer e di ricezione del
  blocco `n` per nodo e per round (`-debug=wpoa`), da confrontare con `B_n.Time`. E un confronto
  fra i quattro profili `core` (`regional` 5,1 ms, `national` 11,9 ms, `continental` 27,8 ms,
  `intercontinental` 181,5 ms), che differiscono **solo** per la geografia: se la pendenza
  in punti percentuali per ms è stabile fra i quattro, l'ipotesi è confermata.

### 3.6 Stabilità del block time e correzione globale `Φ`

- **File**: [phase2/round_level.csv](phase2/round_level.csv),
  [phase1/round_delays.csv](phase1/round_delays.csv),
  [plots/phi_over_time.png](plots/phi_over_time.png).

| Quantità | Osservato | Atteso |
|---|---:|---|
| block time medio | **11,425 s** | 10 s |
| scostamento | **+14,25 %** | ~0 % |
| mediana | 12,000 s | 10 s |
| sd | 2,871 s | — |
| min / max | 5 s / 16 s | — |
| delay medio del produttore | 13,673 s (p50 14,43) | — |
| delay medio dell'argmin | 9,537 s | — |
| residuo dello scheduler | −2,249 s (sd 3,469 s) | ~0 |

**Deriva** (molto più lieve che nella run `native`):

| epoche | `Φ` medio | block time medio |
|---|---:|---:|
| 2–11 | −1,372 s | 11,383 s |
| 22–31 | −1,383 s | 11,379 s |
| 32–41 | −1,318 s | 11,324 s |
| 42–51 | −1,409 s | 11,406 s |
| 52–61 | −1,626 s | 11,634 s |

Spearman(epoca, block time medio) = **+0,262** su 60 epoche (z = +2,02, **p = 0,044**); pendenza
**+0,0035 s per epoca**, cioè +0,21 s sull'intera run (11,294 → 11,792 s). Contro la run
`native`, dove la stessa Spearman valeva +0,715 e la pendenza +0,91 s su 100 epoche.

**Diagnosi di `Φ`** — identica a quella della run `native`, e ancora una volta **`Φ` non è il
colpevole**:

- `Φ` medio = **−1,420 s**, contro un errore da compensare di `10 − 11,425 = −1,425 s`: la misura
  è giusta.
- **Non è saturato**: |Φ|max = **3,667 s** contro `M = 5,0 s`; **0 round su 7 101** in saturazione.
- **Non oscilla**: `Φ < 0` nel **97,30 %** dei round, con **106/7 100** cambi di segno consecutivi
  (1,5 %). Il rolling median in [plots/phi_over_time.png](plots/phi_over_time.png) resta piatto
  fra −1,4 e −1,6 senza discontinuità.
- Termine effettivo `λ·Φ = −0,426 s` in media, contro un errore di +1,425 s.

- **Giudizio**: **scostamento significativo**, con causa in §3.5. Il delay non governa il block
  time (Pearson +0,014), quindi l'anello di retroazione è **aperto**: `Φ` misura l'errore ma il
  suo attuatore non ha autorità. **Alzare `λ` non risolverebbe.**

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png),
  [plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png),
  [plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png),
  [plots/esg_scores.png](plots/esg_scores.png).

#### Identità del motore — verificate esattamente

| Identità | n | Errore relativo massimo |
|---|---:|---:|
| `W_k_raw = ESG_Mk · (τ_Mk + Σ c_i)` | 610 | **0,0** (esatto) |
| `w_k_final = W_k_raw · (ρ_prev·λ_w + 1 − λ_w)`, e ≥ 2 | 600 | **4,2·10⁻¹⁶** |
| `w_k_published = 100 · w_k_final` | 610 | 1,8·10⁻⁸ |

#### Il canale di retroazione resta quasi inerte

| Quantità | Osservato | Range possibile |
|---|---:|---|
| `ρ` (tasso di restituzione) | media **0,0035**, sd 0,0026, **max 0,0146**, 82/610 a zero | `[0, 1]` |
| `R_k` per epoca | media 177,24 GAS, totale 108 114 GAS | — |
| `saldo_k` | media ≈ 50 813 GAS | — |
| fattore `ρ·λ_w + (1−λ_w)` | media **0,5017**, min 0,5000, **max 0,5073** | `[0,5 – 1,0]` |

Il fattore moltiplicativo occupa l'**1,5 %** del suo intervallo utile — poco, ma quasi **il doppio**
della run `log` (0,8 %), grazie a `restitution_amount_range = [1, 100]` invece di `[1, 9]`. Resta
comunque insufficiente: `miner_seed_gas = 50 600` contro restituzioni di al massimo 7 × 100 = 700
GAS per epoca.

- Spearman lag-1 `ρ(e) → peso pubblicato in e+1`: **−0,0124**, p = 0,762, n = 600. Per validatore
  ([plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)) nessuno è
  significativo.
- **Giudizio**: **non testabile in questa run, e non è un difetto del codice**. L'assenza di
  correlazione era prevedibile data la varianza di `ρ`. L'identità algebrica del peso è verificata
  esattamente: il meccanismo **è implementato**, non è stato **esercitato**.

#### Traiettoria dei pesi e amplificazione

- Il boxplot ([plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png)) mostra
  i pesi efficaci fra **260 e 718**, con box ≈ 350–530 e mediana stabile a ≈ 430 su tutte le 60
  epoche misurate; l'epoca 1 (setup) sta molto più in basso (≈ 75–150). Nessuna deriva, nessun
  allargamento progressivo.
- `gini_delta = Gini(pubblicato) − Gini(input ESG×τ)`: media **+6·10⁻⁶**, intervallo
  `[−7,5·10⁻⁴; +1,3·10⁻³]`, pendenza della traiettoria **−1·10⁻⁶** (Spearman −0,0925, p = 0,478).
- **Giudizio**: **conforme**. Il motore **non concentra** il peso oltre la disuguaglianza dei
  propri input.

#### Staticità degli score ESG

- **Osservato**: **0 cluster head su 10** con ESG variabile fra epoche; 30 pubblicazioni ESG,
  tutte presenti sullo stream (check critico **PASS**).
- **Giudizio**: **conforme**.

### 3.8 Concentrazione

- **File**: [phase2/epoch_concentration.csv](phase2/epoch_concentration.csv), sezione 3 di
  [phase3/report.md](phase3/report.md),
  [plots/concentration_over_time.png](plots/concentration_over_time.png).

| Indice | Teorico medio (per epoca) | Osservato medio (per epoca) | **Aggregato teorico** | **Aggregato osservato** |
|---|---:|---:|---:|---:|
| HHI | 0,1052 | 0,1182 | **0,104767** | **0,103466** |
| N_eff | 9,505 | 8,507 | **9,545** | **9,665** |
| Gini | 0,1245 | 0,2261 | **0,120667** | **0,104901** |
| Entropia norm. | 0,9890 | 0,9563 | — | — |
| Nakamoto 1/2 | 4 (20 epoche), 5 (40) | 4 (54), 3 (5), 5 (1) | **5** | **5** |

- **Osservato**: per epoca l'osservato è **sopra** il teorico (HHI 0,118 contro 0,105) — varianza
  multinomiale con 120 blocchi. **Sull'aggregato il segno si inverte**: HHI osservato
  **0,1035 < 0,1048** teorico, Gini **0,1049 < 0,1207**, N_eff **9,665 > 9,545**. Cioè la
  distribuzione consegnata è **più egualitaria** di quella cui i pesi darebbero diritto.
- **Atteso**: aggregato ≈ teorico.
- **Giudizio**: **lieve scostamento, coerente con §3.3**. La maggiore uguaglianza aggregata è
  esattamente la compressione verso l'uniforme misurata dalla pendenza 0,700. Il divario *per
  epoca* resta invece un artefatto di campione e non va segnalato come concentrazione reale.

### 3.9 Streak e ripetizioni

- **File**: [phase3/streak.md](phase3/streak.md), colonne `L_max_*` e `repeat_prob_*` di
  [phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv), più calcolo diretto su
  [phase1/blocks.csv](phase1/blocks.csv).

| Quantità | Osservato | Monte-Carlo | Eccesso |
|---|---:|---:|---:|
| prob. di ripetizione, aggregata | **0,251585** | 0,105267 | **+139 %** (p = 1·10⁻⁴) |
| prob. di ripetizione, media per epoca | 0,2530 | 0,1054 | +140 % |
| rigetti `repeat_prob` | **60/60 epoche** | 3 attesi | — |
| `L_max` aggregato | 7 | 4,779 (p = 0,0153) | — |
| rigetti `L_max` | **23/60** | 3 attesi | — |

Calcolo diretto sulla sequenza dei blocchi non-setup:

- ripetizioni **1786/7099 = 0,2516** contro `Σpᵢ² = 0,1035` atteso → **+143,2 %**;
- lunghezza media dei run **1,336** contro 1,115 attesa; distribuzione
  `{1: 3996, 2: 984, 3: 242, 4: 59, 5: 25, 6: 7, 7: 1}`;
- **l'eccesso è presente in tutti i validatori** (da 0,2194 per miner-3 a 0,2835 per miner-9),
  sempre circa 2–2,5× la rispettiva quota;
- decadimento: lag-2 **0,1386**, lag-3 0,1177, lag-5 0,1004, lag-10 0,1096.

- **Giudizio**: **scostamento significativo**. L'eccesso (+143 %) è maggiore di quello della run
  `native` (+113 %) e la memoria decade più lentamente (in `native` il lag-3 era già a 0,1063
  contro 0,1004 atteso; qui il lag-2 è ancora a 0,1386). La componente aggiuntiva è plausibilmente
  la rete: chi ha appena propagato un blocco parte avvantaggiato anche sul round seguente.
- **Nota**: la ripetizione **non** correla con la latenza media
  (Pearson +0,147, Spearman +0,261): la dipendenza lag-1 di base è lo stesso artefatto di
  scheduler osservato in regime `native`, non un effetto geografico.

### 3.10 Due guasti di nodo durante la run — **da tenere fuori dalle conclusioni**

#### miner-5 (tokyo): fermo dall'epoca 54

- Ultimo blocco prodotto: **altezza 6460** (epoca 54). Dopo di allora **0 blocchi in 861 round**
  con una quota attesa media di **0,1175**: `P[0 blocchi] = (1 − 0,1175)^861 = 10⁻⁴⁶,⁷`.
- Il crollo è visibile a occhio nella
  [heatmap di Wilson](plots/wilson_violation_heatmap.png), dove la riga di miner-5 è un blocco
  rosso continuo dall'epoca ~52 alla fine.

| epoche | quota attesa | quota osservata | scarto |
|---|---:|---:|---:|
| 2–11 | 0,1244 | 0,1200 | −0,0044 |
| 12–21 | 0,1282 | 0,0983 | −0,0299 |
| 22–31 | 0,1273 | 0,1075 | −0,0198 |
| 32–41 | 0,1330 | 0,1217 | −0,0113 |
| 42–51 | 0,1304 | 0,1317 | +0,0013 |
| **52–61** | **0,1215** | **0,0158** | **−0,1057** |

**Cosa NON è la causa** — tutto verificato nei dati della run:

| Verifica | Esito |
|---|---|
| presenza fra i peer dell'admin | presente in **62/62** altezze campionate |
| sincronizzazione | `synced_blocks` segue il tip fino alla fine (7338 su 7340) |
| permessi | `connect, mine, receive, send` **per tutta la run**, senza revoche |
| `permitted` in `miners.csv` | `True` in **63/63** campioni; `diversitywaitblocks = 0` |
| eleggibilità nella sortition | eleggibile e con score calcolato in **862/862** round delle epoche 54–61 |
| peso efficace consumato dall'elezione | ≈ **507,7**, quota attesa ≈ **0,1178** |
| errori RPC del nodo | **0** |
| chiusura | `shutdown.json` → `"rpc"` (arresto normale a fine run) |

**Cosa si osserva invece**: dall'epoca 56 la sua attività diretta `τ_M` va a **0**, l'`income` a
**0** e `R_k` a **0**, mentre il suo daemon **continua a tentare restituzioni** (5, 6, 1, 4 nelle
epoche 56–59, per 660 GAS complessivi) che **non confermano mai**. Il suo saldo resta congelato a
51 038,67 GAS. Le due aziende del suo cluster (`company-5`, `company-12`) continuano invece a
trasmettere regolarmente (105–140 tx per epoca fino alla fine).

#### miner-2 (new-york): fermo dall'epoca 59

Stesso quadro, più tardi e più breve: **0 blocchi dalle epoche 59 in poi**, `τ_M = 0` e
`income = 0` dall'epoca 60. Il conteggio di connessioni visto dall'admin
([phase1/node_state.csv](phase1/node_state.csv)) scende da **30 a 29** intorno all'altezza 6365 e
a **25** dall'altezza 6845, coerentemente con i due eventi.

#### La conseguenza di protocollo, che è il vero rilievo

Il peso di un cluster è retto da `ESG_Mk · (τ_Mk + Σ c_i)`: la somma dei contributi delle aziende
domina. Per miner-5 nelle epoche 56–61, `τ_M = 0` ma `companies_contribution_sum` resta fra 81,8
e 110,3, quindi `W_k_raw` resta fra 5 481 e 7 415 e il peso pubblicato fra **274 571 e 372 815**.

> **Un cluster head che smette di produrre blocchi conserva indefinitamente la propria quota
> spettante** (qui ≈ 11,8 %), perché il peso misura l'operosità del *cluster* e non la
> partecipazione del *validatore*. Quella quota viene sottratta a tutti gli altri nel denominatore
> `W_tot` e i blocchi corrispondenti sono redistribuiti da chi vince la timer race. Il meccanismo
> di malus non interviene, correttamente: non esiste un'evidenza provabile on-chain per
> "il validatore non propone più".

- **Giudizio**: **scostamento significativo**. Il guasto in sé è un problema di infrastruttura
  della run, non del protocollo, e **contamina le epoche 54–61**: per questo tutta l'analisi
  principale è stata ripetuta sulla finestra **2–53**, dove le conclusioni reggono (§3.3, §3.5).
  La **mancanza di decadimento del peso di un validatore inattivo** è invece una proprietà del
  progetto, che questa run ha reso visibile.

### 3.11 Malus

Il meccanismo è **attivo** (`enable-wpoa-malus = true`), ma **nessuna violazione è stata
iniettata**: `malicious.enabled = false`, 0 miner malicious.

| Verifica | Risultato |
|---|---|
| `M = 0` su ogni (epoca, validatore) | **sì**, 610/610 |
| `Ψ = 1` su ogni (epoca, validatore) | **sì**, min = max = 1,0 |
| `w_effective == w_raw · Ψ` | scarto massimo **0,0** |
| `invariant_psi_in_unit` | 0 violazioni / 610 |
| `invariant_weff_matches` | 0 violazioni / 610 |
| `invariant_clean_psi_one` | 0 violazioni / 610 |
| validatori esclusi (`Ψ = 0`) | **0** |
| check critico `malus_finite_and_psi_in_unit_interval` | **PASS** (793 390 campioni) |

**File vuoti, da dichiarare esplicitamente**: [phase1/malus_detections.csv](phase1/malus_detections.csv),
[phase1/malicious_actions.csv](phase1/malicious_actions.csv),
[phase1/malicious_opportunities.csv](phase1/malicious_opportunities.csv),
[phase2/malus_actions.csv](phase2/malus_actions.csv),
[phase2/malus_detection_events.csv](phase2/malus_detection_events.csv),
[phase3/malus_rate.csv](phase3/malus_rate.csv) hanno **0 righe dati**;
[phase3/malus_detection.csv](phase3/malus_detection.csv) e
[phase3/malus_funnel.csv](phase3/malus_funnel.csv) sono tutti a zero con `precision`/`recall`/`f1`
**non calcolabili**; [phase3/malus_latency.csv](phase3/malus_latency.csv) ha `n = 0` su tutte e 4
le misure. **`phase3/malus_effectiveness.md` NON esiste.**

- **Giudizio**: **conforme**. Effetto **esattamente nullo sul comportamento onesto**, che è la
  garanzia che il protocollo offre. Nessun peso penalizzato senza evidenza — **incluso miner-5**,
  che pur avendo smesso di produrre blocchi non ha subito alcuna riduzione, coerentemente con il
  fatto che l'inattività non è una violazione provabile (§3.10).
- **Limite**: questa run **non dice nulla** sull'efficacia del malus.

### 3.12 Correlazione guadagno/transazioni e rielezione

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv) appaiato con
  [phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv), 600 coppie.

**Passo 1 — correlazione grezza con i blocchi vinti** (l'effetto *deve* esserci, mediato dal peso):

| Variabile | Spearman | p |
|---|---:|---:|
| `w_k_published` | **+0,3985** | ≈ 0 |
| `companies_contribution_sum` | **+0,2844** | 4,1·10⁻¹³ |
| `earnings_g_k` | +0,2328 | 4,8·10⁻⁹ |
| `miner_activity` | +0,0794 | 0,051 |
| `income` | +0,0664 | 0,104 |
| `return_rate_rho` | +0,0632 | 0,122 |

**Passo 2 — correlazione dei residui `p_hat − p_theoretical`** (qui l'effetto **deve sparire**):

| Variabile | Spearman | p |
|---|---:|---:|
| `w_k_published` | **−0,1206** | **0,0030** |
| `earnings_g_k` | +0,0676 | 0,098 |
| `miner_activity` | +0,0574 | 0,160 |
| `income` | +0,0446 | 0,275 |
| `companies_contribution_sum` | −0,0436 | 0,286 |
| `return_rate_rho` | +0,0375 | 0,358 |

- **Osservato**: al passo 1 la correlazione più forte è con il **peso pubblicato**, seguito dai
  contributi delle aziende che lo generano; il guadagno correla anch'esso (+0,233) ma è a sua
  volta funzione dell'attività. Al passo 2 **nessuna variabile di traffico o guadagno sopravvive**
  alla soglia di Bonferroni su 6 test (0,0083); sopravvive invece, con segno **negativo**,
  `w_k_published` (ρ = −0,121, p = 0,0030).
- **Giudizio**: **duplice.**
  1. **Nessun canale di influenza non documentato dalle transazioni**: il traffico entra
     nell'elezione solo attraverso il peso, come il modello prescrive. Su questo la risposta è
     **conforme**.
  2. **Il residuo correla negativamente con il peso**: i validatori più pesanti ricevono
     sistematicamente **meno** di quanto spetti loro. Non è un canale occulto del traffico, è la
     firma della compressione verso l'uniforme già misurata in §3.3 (pendenza 0,700) e §3.4
     (`β₁ = 0,842`), vista a grana (epoca, validatore).

### 3.13 Integrità della run e controlli di consistenza

| Check | Critico | Esito | Dettaglio |
|---|---|---|---|
| `registry_weights_finite_and_positive` | sì | **PASS** | 793 390 campioni, tutti finiti e ≥ 0 |
| `no_phantom_validator_in_registry` | sì | **PASS** | ogni indirizzo pesato è un miner noto |
| `malus_finite_and_psi_in_unit_interval` | sì | **PASS** | 793 390 campioni, ogni Ψ in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | sì | **PASS** | coincidenza in ogni round (toll. 1,5 ms) |
| `every_esg_publication_reached_the_stream` | sì | **PASS** | 30 pubblicazioni ESG, tutte sullo stream |
| `only_miners_pay_the_treasury` | sì | **PASS** | 2 207 pagamenti, tutti da miner |
| `at_least_one_fully_measured_epoch` | sì | **PASS** | 60 epoche oltre `setup-first-blocks` |
| `certified_scores_reflected_in_the_engine` | no | **PASS** | ogni indirizzo certificato ha ESG non nullo |
| `traffic_counts_within_configured_range` | no | **PASS** | 1 766 coppie complete, tutte in range |
| `phi_consistent` | no | **FAIL** | 57 valori distinti di `Φ` |

**Su `phi_consistent`**: **non è un difetto**. `Φ` è per costruzione una funzione dello stato
della catena e deve variare; il check è una sonda non critica tarata su run con feedback spento.

Altri controlli:

- **[phase1/verification.csv](phase1/verification.csv)**: 440 righe, **432 `ok` + 8 `other-epoch`**,
  **0 record `invalid`**. Nessun peso pubblicato non ricalcolabile → nessun `BadWeight` latente.
- **[phase1/rpc_errors.csv](phase1/rpc_errors.csv)**: 492 errori, di cui **488 ad altezza ≤ 240**
  (fase di setup), tutti sulle quattro RPC di audit (`wpoalistscores`, `wpoalistdelays`,
  `wpoalisteffectiveweights`, `wpoalistfinalweights`, 122 ciascuna) con
  *"Round not evaluable on this node: the beacon seed or the weight registry is unavailable"*.
  **Benigno**. I 4 restanti sono su `weightgetlocalreturns` da miner-3.
- **[phase2/epoch_traffic.csv](phase2/epoch_traffic.csv)**: 1 766 coppie (epoca, nodo) complete,
  **0 fuori range**.
- **Epoca 61 parziale**: **21 blocchi** invece di 120 — esclusa da ogni conclusione di tendenza.
- **Run completata**: `status = ok`, altezza finale 7 343 contro un target derivato di 7 340.

> **Nota sulle figure.** Sono state aperte e lette visivamente 12 figure aggregate:
> `weight_vs_election`, `residual_boxplot_by_validator`, `concentration_over_time`,
> `phi_over_time`, `wilson_violation_heatmap`, `longitudinal_logratio`, `sigma_decomposition`,
> `election_share_distribution`, `p_value_uniformity`, `margin_distribution`,
> `weights_boxplot_per_epoch`, `delay_recompute_mismatch`. Le restanti
> (`esg_scores`, `gini_delta_trajectory`, `traffic_per_epoch`, `rho_vs_next_weight`,
> `rho_feedback_by_validator`, `sign_test_by_validator`, `prop517_gap_by_validator`,
> `inversion_bound_vs_observed`, `weights_over_time`, `malus_*`) sono state verificate
> numericamente attraverso le rispettive tabelle di origine in `phase2/` e `phase3/`, citate in
> ciascuna sezione.

---

## 4. Punti di forza

- **La VRF è di qualità eccellente.** `E_i` ha media **0,999159** contro 1 atteso (scarto
  **0,08 %**) e KS `√n·D = 0,788` contro un critico di 1,358 su **71 010 campioni** (p = 0,564);
  l'istogramma aderisce alla densità teorica entro **0,14 punti percentuali** in ogni bin.
- **La Proposizione 5.11 è verificata**: score normalizzato dell'argmin con media **0,496258**
  contro 0,5 (scarto **0,75 %**), KS p = 0,507 su 7 101 round.
- **La Proposizione 5.17 è verificata**: gap standardizzato medio **1,0054** contro 1, con un solo
  rigetto KS su 10 classi (atteso ~0,5).
- **Il calcolo del delay è esatto** entro **1,4·10⁻¹³ s** su **71 010** coppie candidato-round:
  10 ordini di grandezza sotto la tolleranza.
- **La distribuzione del margine coincide con la simulazione esatta**: KS **p = 0,859**, media
  osservata 2,6718 s contro 2,6640 s simulata (**0,3 %** di scarto).
- **L'ordinamento è preservato con margine ampio**: Spearman quota attesa ↔ osservata sui 10
  validatori = **+0,879**, contro un critico di 0,648.
- **La monotonia peso ↔ quota è dimostrata statisticamente**: sign test aggregato
  **312/532 = 0,5865**, z = +3,99, **p = 3·10⁻⁵**, con 5 validatori su 10 significativi
  individualmente. Nella run gemella con `log` lo stesso test non arrivava alla soglia (p = 0,068).
- **Lo smorzamento a radice comprime esattamente come previsto**: `√7,60 = 2,76` verificato sui
  pesi efficaci, con quote che passano da 4,31× a **2,07×** — coerente con il riferimento teorico
  per `sqrt` e, soprattutto, con una **dinamica sufficiente a testare la proporzionalità**
  (rapporto segnale/risoluzione 0,94 contro 0,14 nella run `log`).
- **Il motore di peso implementa esattamente la definizione ricorsiva**: `W_k = ESG·(τ + Σc)`
  esatta su 610 righe, `w_k = W_k·(ρ·λ_w + 1 − λ_w)` entro **4,2·10⁻¹⁶**.
- **Il motore non amplifica la disuguaglianza dei propri input**: `gini_delta` medio **+6·10⁻⁶**,
  pendenza −1·10⁻⁶ su 61 epoche (Spearman −0,092, p = 0,478).
- **Il malus è a effetto rigorosamente nullo sul comportamento onesto**: `M = 0`, `Ψ = 1`,
  3/3 invarianti su **610** celle — e nessuna penalità è stata applicata nemmeno ai due nodi che
  si sono fermati, correttamente, perché l'inattività non è un'evidenza provabile.
- **Il traffico non ha canali occulti verso l'elezione**: nessuna variabile di guadagno o volume
  correla con i residui dopo la correzione per confronti multipli.
- **Tutti e 7 i controlli critici passano**, su una run completata alla sua altezza target con
  0 pesi non ricalcolabili su 440 verifiche.

---

## 5. Punti critici / da approfondire

### 5.1 La posizione in rete determina la quota di blocchi *(priorità massima, risultato specifico di questa run)*

- **Entità**: sulla finestra pulita (epoche 2–53), Pearson fra ritardo medio di percorso e scarto
  di quota = **−0,8885**, Spearman **−0,7939** (critico 0,648). I tre validatori più centrali
  (frankfurt 60,7 ms, milano 60,8 ms, new-york 66,6 ms) sono gli **unici tre** con scarto positivo,
  a z = **+4,92**, **+3,60**, **+2,82**; tutti e quattro i più periferici hanno scarto negativo.
  Pendenza **−0,64 punti percentuali ogni 10 ms**, cioè **≈ 2,0 p.p.** sull'escursione osservata —
  un **±20 % relativo** su quote del 10 %.
- **Non è confuso con il peso**: `corr(latenza, quota attesa) = +0,224`; la correlazione parziale
  latenza↔scarto controllando per la quota attesa vale **−0,670** (t = −2,39 su 7 gdl, **p = 0,048**),
  mentre quella quota attesa↔scarto controllando per la latenza non è significativa (p = 0,152).
  Regressione a due variabili: R² = 0,601, di cui 0,454 dalla sola latenza.
- **Non si spiega col rumore del bound**: `σ_S1` (propagazione) vale **0,035 s**, cioè l'**1 %**
  del rumore totale, e il bound di Prop. 5.18 è **vacuo** (1,0).
- **Ipotesi sul meccanismo**: Prop. 5.18 modella la latenza come rumore **a media nulla**. Su una
  mappa reale la latenza ha una **media per nodo diversa da zero**: un validatore centrale riceve
  il blocco `n` prima e **arma il proprio timer prima**, con un vantaggio costante round dopo
  round. Un offset sistematico non si media a zero. Che i blocchi arrivino **2,25 s prima** del
  delay del loro produttore (§3.6) rafforza l'ipotesi: la corsa reale non si decide al confine
  della banda `Δ_max` ma in una finestra molto più stretta, dove 30 ms pesano.
- **Cosa servirebbe per confermare**: (a) gli istanti di ricezione del blocco `n` e di armamento
  del timer per nodo e per round, da `-debug=wpoa`; (b) **il confronto fra i quattro profili
  `core`** — `regional.yaml` (5,1 ms), `national.yaml` (11,9 ms), `continental.yaml` (27,8 ms),
  `intercontinental.yaml` (181,5 ms) — che per costruzione differiscono **solo** per la geografia:
  se la pendenza in p.p./ms è stabile, l'ipotesi è confermata; se l'effetto scompare sulle mappe
  strette, è quantificata la soglia oltre cui la geografia diventa rilevante.
- **Perché conta**: è una violazione della garanzia centrale del protocollo, che promette
  `Pr[i eletto] = g(w_i)/Σg(w_k)` **indipendentemente dalla posizione in rete**.

### 5.2 La timer race non seleziona il vincitore della sortition *(difetto comune alle due run)*

- **Entità**: inversione **0,9103** contro il **0,5826** che il rumore misurato predirebbe e
  il **0,900** dell'indipendenza totale; rank del produttore quasi piatto (rank 1 all'**8,97 %**);
  Pearson(block time, delay) = **+0,014**.
- **Il rank non è esattamente uniforme**: chi-quadro **27,73 su 9 gdl, p = 0,0011**, con il
  rank 1 a z = −2,89. Ma non c'è struttura monotona: il vincitore designato vince, se mai, **meno**
  del caso. Va registrato come deviazione dall'uniforme senza sovra-interpretarla.
- **La sorgente del rumore è locale, non la rete**: `σ_S2 = 3,469 s` qui contro **3,482 s** nella
  run `native` su loopback — **0,4 % di differenza**. `σ_S1 = 0,035 s` è 99× più piccolo.
- **Ipotesi**: le stesse della run `native` — disallineamento dell'istante di riferimento fra
  timer wPoA e ciclo di mining nativo (il residuo `dt_prev − delay_winner` ha media **−2,249 s**),
  granularità del poll del miner, contesa di CPU fra i 33 daemon.
- **Cosa servirebbe**: i log `-debug=wpoa` con armamento e proposta effettiva; una run `core` con
  2–3 miner, dove `1 − 1/n` vale 0,50–0,67 e si separa nettamente dal 58 % del modello di rumore.

### 5.3 Lo scostamento dalle quote attese è reale e sopravvive a ogni correzione

- **Entità**: sulla finestra pulita 2–53, chi-quadro aggregato **73,54** su 9 gdl (p = 3,1·10⁻¹²),
  che **corretto per il VIF (1,370) resta 53,67, p = 2,2·10⁻⁸**; 60/520 violazioni di Wilson
  contro 36 attese col VIF (p = 6,4·10⁻⁵); 6/52 rigetti GoF corretti contro 2,6 attesi.
  `MaxAE` delle quote **0,0197**, cioè ~2 punti percentuali.
- **Come si distingue dalla run `long24h-large-log`**: là la stessa correzione riportava tutto nel
  caso (6/100 rigetti contro 5 attesi, chi-quadro p = 0,095). **La differenza non è nei conteggi ma
  nella forma dell'istogramma dei p-value**: qui un **picco** in `[0; 0,1]` (28/60 contro 6 attese),
  là un'inclinazione graduale. Picco = media sbagliata; inclinazione = varianza sottostimata.
- **Compressione verso l'uniforme del ~30 %**: regressione quota osservata su quota attesa con
  pendenza **0,700**; GLM `β₁ = 0,8418` con IC95 **[0,734 – 0,950]** che **esclude 1**; pendenza
  dei log-rapporti 0,8603; residui che correlano negativamente col peso pubblicato (ρ = −0,121,
  p = 0,0030). Coerente in tutte e quattro le misure.
- **Causa**: 5.1 (bias geografico) più 5.2 (mescolamento dell'esito). Il modello di sola
  compressione uniforme non basta da solo (chi-quadro residuo 80,08 su 8 gdl), il che è atteso:
  sopra la compressione si sovrappone il gradiente geografico.

### 5.4 Due validatori si sono fermati durante la run

- **Entità**: **miner-5** non produce blocchi dall'epoca 54 — 0 su 861 round con quota attesa
  0,1175, `P = 10⁻⁴⁶,⁷`; **miner-2** dall'epoca 59. Le connessioni viste dall'admin scendono da
  30 a 29 (h≈6365) e poi a 25 (h≈6845).
- **Nessuna causa osservabile nei dati raccolti**: entrambi restano presenti fra i peer in tutte
  le altezze campionate, sincronizzati al tip (7338 su 7340), con i quattro permessi
  (`connect, mine, receive, send`) mai revocati, `permitted = True` in 63/63 campioni,
  `diversitywaitblocks = 0`, eleggibili e con score calcolato in 862/862 round, 0 errori RPC. Il
  daemon di miner-5 continua a **tentare** restituzioni (660 GAS nelle epoche 56–59) che **non
  confermano mai**, e il suo `shutdown.json` riporta un arresto normale via `rpc`.
- **Cosa servirebbe**: il `daemon.out` di `chains/miner-5/` e `chains/miner-2/`, che questa
  analisi non ha potuto leggere (i data directory sono di proprietà `root`), più il log del
  proprio ciclo di mining. È l'unico posto in cui la causa può essere ancora scritta.
- **Impatto sull'analisi**: le epoche 54–61 sono contaminate. Tutte le conclusioni principali sono
  state ricalcolate sulla finestra 2–53 e reggono.

### 5.5 Un validatore inattivo conserva la propria quota spettante *(proprietà del progetto)*

- **Entità**: per miner-5 nelle epoche 56–61 `τ_M = 0`, ma
  `companies_contribution_sum` resta fra **81,8 e 110,3** perché le sue due aziende continuano a
  trasmettere (105–140 tx per epoca). Di conseguenza `W_k_raw` resta fra 5 481 e 7 415 e il peso
  pubblicato fra **274 571 e 372 815**, con una quota spettante di **≈ 11,8 %** mantenuta per 8
  epoche senza produrre un solo blocco.
- **Perché accade**: il peso misura l'operosità del **cluster**, non la partecipazione del
  **validatore**. Il termine `τ_Mk` (attività diretta del miner) esiste, ma è di un ordine di
  grandezza inferiore al contributo aggregato delle aziende (valori tipici 1–9 contro 70–110).
- **Perché il malus non interviene, correttamente**: le quattro categorie di violazione richiedono
  un'evidenza crittografica provabile (doppio blocco, timestamp anticipato, firma altrui, peso non
  ricalcolabile). "Non propone più" non è dimostrabile localmente e non deve esserlo.
- **Cosa servirebbe per decidere se è un problema**: è una scelta di progetto da discutere, non un
  bug. Se si volesse un decadimento, la leva naturale è dare più peso a `τ_Mk` rispetto a
  `Σ c_i` nella definizione del peso grezzo, oppure introdurre un fattore di liveness osservabile
  (blocchi prodotti nell'epoca) distinto dal registro dei malus. **Va però notato che legare il
  peso ai blocchi prodotti introdurrebbe una retroazione positiva diretta fra elezione e peso, che
  il progetto attuale evita deliberatamente.**

### 5.6 Il block time non converge

- **Entità**: media **11,425 s** contro 10 s (**+14,25 %**), con deriva lieve ma significativa
  (Spearman +0,262, p = 0,044; +0,21 s sull'intera run).
- **`Φ` non è il colpevole**: misura l'errore correttamente (media −1,420 s contro un errore di
  −1,425 s), **non è saturato** (|Φ|max = 3,667 s contro M = 5,0 s, **0 round** saturati) e **non
  oscilla** (97,3 % dei round con `Φ < 0`, 1,5 % di cambi di segno). L'attuatore — il delay — non
  governa l'uscita (5.2): **l'anello è aperto**.
- **Implicazione**: **non alzare `λ`**. La correzione va fatta su 5.2.
- **Nota di confronto**: lo scostamento (+14,25 %) è quasi identico a quello della run `native`
  (+13,76 %), il che conferma che non dipende dalla rete.

### 5.7 Il canale di retroazione inter-epoca non è stato esercitato

- **Entità**: `ρ ∈ [0; 0,0146]`, fattore moltiplicativo in **[0,5000; 0,5073]**, cioè l'**1,5 %**
  dell'intervallo utile `[0,5; 1,0]`. Spearman lag-1 = −0,0124 (p = 0,762); nessun cluster head
  significativo.
- **Causa**: il modello di traffico. `miner_seed_gas = 50 600` contro restituzioni massime di
  7 × 100 = 700 GAS per epoca (1,4 % del saldo). È il doppio della run `log` (0,8 %) ma resta
  insufficiente.
- **Cosa servirebbe**: abbassare `miner_seed_gas` di uno-due ordini di grandezza, o alzare
  `restitution_amount_range` in proporzione, così che `ρ` copra almeno `[0; 0,5]`.

### 5.8 Efficacia del malus: non misurata

- Nessuna violazione iniettata: nessun dato su rilevazione, precisione, richiamo, latenza,
  proporzionalità della penalità e reversibilità.
- **Cosa servirebbe**: una run con la sezione `malicious` (esempio:
  `test/config/profiles/native/malicious.yaml`). Limite noto: solo `selfwrite` e `badweight` sono
  iniettabili dall'esterno.

---

## 6. Conclusione

| Asse | Giudizio | Evidenza |
|---|---|---|
| **Qualità della randomness (VRF)** | **Eccellente** | `E_i` media 0,999159 (KS p = 0,564, n = 71 010); `score_norm` dell'argmin media 0,496258 (p = 0,507); Prop. 5.17 media 1,0054 |
| **Affidabilità della sortition (calcolo)** | **Eccellente** | delay ricalcolato entro 1,4·10⁻¹³ s su 71 010 casi; margine conforme alla simulazione esatta (p = 0,859); identità del peso esatte |
| **Affidabilità della sortition (attuazione)** | **Compromessa, e per due cause distinte** | inversione 0,910 con rank quasi piatto (difetto locale, identico in `native`); **più** un bias geografico: Pearson −0,889 fra latenza e scarto di quota |
| **Efficacia dello smorzamento** | **Corretta e, qui, misurabile** | 7,60× → 2,76× sui pesi efficaci (`√7,60` esatto), quote da 4,31× a 2,07×, ordinamento preservato (Spearman +0,879), rapporto segnale/risoluzione 0,94 |
| **Efficacia del malus** | **Non misurata** (effetto nullo corretto in assenza di violazioni) | `M = 0`, `Ψ = 1`, 3/3 invarianti su 610 celle |
| **Stabilità del block time** | **Non raggiunta** | media 11,425 s contro 10 s (+14,25 %), deriva +0,21 s, `Φ` corretto e non saturo |

**Stato di salute complessivo.** Il nucleo crittografico e matematico del wPoA è **sano e
verificato con margini ampi**: la VRF produce randomness indistinguibile dall'ideale su 71 010
campioni, la trasformazione di Efraimidis–Spirakis e la normalizzazione dello score si comportano
come i teoremi prevedono, il margine fra i due candidati più veloci segue la distribuzione esatta
della sortition implementata, il delay è calcolato in modo riproducibile alla precisione della
macchina e il motore di peso soddisfa esattamente le proprie identità algebriche. Lo smorzamento a
radice fa esattamente quello che deve, comprimendo il vantaggio da 4,31× a 2,07× senza mai invertire
l'ordinamento, e — a differenza della variante `log` — lascia dinamica sufficiente perché
l'esperimento sia informativo.

**Su questo nucleo sano si innestano però due difetti di attuazione, che questa run separa
nettamente.** Il primo è **locale al nodo e non dipende dalla rete**: il produttore effettivo del
blocco è quasi indipendente dall'ordinamento di sortition (inversione 91,0 %, rank quasi piatto,
correlazione fra block time e delay +0,014), e il rumore che lo causa — `σ_S2 = 3,469 s` — è
indistinguibile da quello misurato su loopback nella run `native` (3,482 s), mentre la propagazione
contribuisce appena `σ_S1 = 0,035 s`. Il secondo è invece **specifico della geografia** ed è il
risultato che solo il regime `core` poteva produrre: la posizione in rete sposta la quota di
blocchi di circa **0,64 punti percentuali ogni 10 ms** di ritardo medio verso gli altri validatori,
con i tre validatori più centrali sovra-rappresentati a 2,8–4,9 deviazioni standard e i periferici
sotto-rappresentati. La correlazione parziale, controllando per la quota attesa, resta **−0,670**
(p = 0,048). È una violazione della garanzia centrale del protocollo, e la spiegazione più
plausibile è che la Proposizione 5.18 modelli la latenza come rumore a media nulla mentre su una
mappa reale essa ha una media **per nodo** diversa da zero, che non si compensa nel tempo.

**Un rilievo metodologico che vale per entrambe le run.** L'eccesso di rigetti statistici va sempre
corretto per la dipendenza fra round (qui VIF = 1,370, ripetizioni a +143 % del valore atteso). Su
questa run la correzione **non** riconcilia i dati: il chi-quadro aggregato resta a p = 2,2·10⁻⁸
sulla finestra pulita, e l'istogramma dei p-value mostra un **picco** in zero anziché
un'inclinazione — media sbagliata, non varianza sottostimata. È esattamente l'opposto della run
`long24h-large-log`, dove la stessa correzione riportava tutto nel caso. **Le due run vanno lette
insieme**: la prima isola il difetto di scheduler, la seconda vi aggiunge — e misura — l'effetto
della geografia.

**Due avvertenze sulla validità.** Le epoche 54–61 sono contaminate dall'arresto di due validatori
(miner-5 e miner-2) che restano connessi, sincronizzati, autorizzati ed eleggibili senza produrre
blocchi; tutte le conclusioni sono state ricalcolate sulla finestra 2–53 e reggono. Quell'incidente
ha però reso visibile una proprietà del progetto che merita una decisione esplicita: **un cluster
head inattivo conserva indefinitamente la propria quota spettante** — qui l'11,8 % per otto epoche
— perché il peso misura l'operosità del cluster e non la partecipazione del validatore.

**Priorità di intervento**: (1) misurare gli istanti di ricezione del blocco e di armamento del
timer per nodo, che è l'unico dato che separa definitivamente le ipotesi su 5.1 e 5.2; (2)
ripetere l'esperimento sui quattro profili `core` (`regional`, `national`, `continental`,
`intercontinental`), che differiscono solo per la geografia, per quantificare la pendenza
latenza→quota e trovare la soglia oltre cui diventa rilevante; (3) chiarire l'arresto di miner-5 e
miner-2 leggendo i rispettivi `daemon.out`; (4) decidere se il peso debba decadere per un
validatore che smette di proporre, sapendo che legarlo ai blocchi prodotti introdurrebbe una
retroazione positiva che il progetto attuale evita.
