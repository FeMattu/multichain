# Analisi della run `run-wpoa-long24h-large-log-20260918T235047Z`

Run: `test/results/run-wpoa-long24h-large-log-20260918T235047Z`
Timestamp UTC della run: **2026-09-18T23:50:47Z**
Catena: `wpoa-long24h-large-log` — profilo: `test/config/profiles/native/long24h-large-log.yaml` — regime: **native**
Analisi prodotta il: 2026-09-20

---

## 1. Configurazione della run

| Parametro | Valore | Fonte |
|---|---|---|
| chain_name | `wpoa-long24h-large-log` | [manifest.json](../manifest.json) |
| seed dell'esperimento | `20260905` | manifest.json |
| regime / fabric | **native** (nessuna emulazione di rete, tutti i nodi su loopback) | manifest.json `fabric.backend` |
| worst path delay | `0.0 ms` (non applicabile in native) | manifest.json `derived.worst_path_delay_ms` |
| nodi | 1 admin, 3 CA, **10 miner**, 20 company (34 totali) | manifest.json `nodes` |
| epoche | **100 epoche × 100 blocchi** | manifest.json `epochs` |
| `setup-first-blocks` | **210** → epoca 1 esclusa (round robin nativo) | [phase1/config.csv](phase1/config.csv) |
| altezza finale | `10122` (target derivato `10120`) — run **completata**, `status = ok` | manifest.json |
| **`dump-function`** | **`log`** → `g(w) = ln(1+w)` (smorzamento aggressivo) | phase1/config.csv |
| `target-block-time` | **10 s** | phase1/config.csv |
| `wpoa-sortition-delta` (δ) | **0.5** → `Δ_max = δ·T = 5.0 s` | phase1/config.csv |
| `wpoa-sortition-lambda` (λ) | **0.3** | phase1/config.csv |
| bound del feedback `M` | **5.0 s** = `min(0.5·T, T(1−δ)/λ) = min(5.0, 16.67)` | ricavato |
| malus: `mu`, `M_max` | `0.5`, `4.0` | phase1/config.csv |
| malus: punti per kind | equiv `4.0`, badweight `2.0`, selfwrite `1.0`, delay `0.25` | phase1/config.csv |
| `enable-wpoa-malus` | `true` (il meccanismo è **sempre attivo**) | phase1/config.csv |
| **violazioni iniettate** | **NO** — `malicious.enabled = false`, 0 miner malicious | [malicious_manifest.json](../malicious_manifest.json) |
| `weight-kappa` (κ) | `100.0` | phase1/config.csv |
| `weight-lambda` (λ_w) | `0.5` | phase1/config.csv |
| `weight-alpha` | `0.2` — **parametro inerte**, validato e mai letto dal binario | phase1/config.csv |
| `weight-epoch-length` | `100` | phase1/config.csv |
| `wpoa-randao-lookback` | `101` | phase1/config.csv |
| `mining-diversity` | **`0.0`** → la regola di spacing nativa non è vincolante | phase1/config.csv |
| `mining-turnover` | `0.5` (euristica locale nativa, senza effetto su wPoA) | phase1/config.csv |
| `initial-block-reward` | **`0`** → nessuna ricompensa da mining | phase1/config.csv |
| `first-block-reward` | `100000000000000` (premine dell'admin) | phase1/config.csv |
| traffico: tx per azienda/epoca | `[30, 60]` | manifest.json `traffic` |
| traffico: restituzioni per miner/epoca | `[0, 5]`, importi in `[1.0, 9.0]` | manifest.json `traffic` |
| traffico: range score ESG | `[1, 100]` | manifest.json `traffic` |
| stream informativo | `supply-chain-events` | manifest.json `traffic` |

**Pesi "iniziali" per validatore.** Non esiste un campo di configurazione che li fissi: emergono
dalla pipeline `ESG × τ`. Gli score ESG certificati dei 10 miner ([phase1/esg_events.csv](phase1/esg_events.csv),
[plots/esg_scores.png](plots/esg_scores.png)) sono, in ordine: **29, 43, 49, 55, 56, 67, 75, 76, 81, 95**
(rapporto max/min = 3,28×). I pesi grezzi pubblicati a fine run spaziano da **42 028 a 295 832**
(rapporto **7,04×**), in unità fixed-point ×100 del registro. Sono un **esito stocastico del seed**,
non una configurazione.

> **Verifica di scala.** `w_k_published = 100 × w_k_final` su tutte le 1010 righe di
> [phase2/epoch_engine.csv](phase2/epoch_engine.csv), con deviazione relativa `2,8·10⁻⁸`. È la
> rappresentazione fixed-point a 2 decimali del registro, non una discrepanza.

---

## 2. Executive summary

1. **La randomness è impeccabile.** `E_i ~ Exp(1)` su 99 020 campioni: media **0,99452** (IC95
   [0,99377 – 1,00623]), varianza 0,981, KS `√n·D = 0,842` contro un critico di 1,358 (p = 0,477).
   Lo score normalizzato dell'argmin è `U(0,1)`: media **0,50113**, KS p = 0,468.
2. **Il calcolo del delay è esatto.** Il ricalcolo indipendente coincide con il valore loggato dal
   nodo entro **6,2·10⁻¹⁵ s** su tutte le 99 020 coppie candidato-round: 12 ordini di grandezza
   sotto la tolleranza di 1,5 ms.
3. **Il difetto principale: la timer race non elegge il vincitore della sortition.** Il tasso di
   inversione è **0,899**, cioè esattamente `1 − 1/n = 0,900` per n = 10 candidati, e il rank di
   sortition del produttore effettivo è **uniforme** (10,10 % a rank 1 contro il 10,00 % del caso).
   Il block time è **scorrelato** dai delay calcolati (Pearson +0,031). Il meccanismo di selezione
   è corretto in ogni sua componente, ma **non governa chi produce il blocco**.
4. **Il block time non converge ed è in deriva monotona.** Media **11,376 s** contro un target di
   10 s (**+13,8 %**), in crescita da 11,12 s a 12,35 s lungo la run (Spearman epoca↔block time
   = **+0,715**, p ≈ 1·10⁻¹²). `Φ` misura correttamente l'errore ed è **lontano dalla saturazione**
   (|Φ|max = 4,42 s contro M = 5,0 s): l'anello di retroazione è **aperto**, non mal tarato.
5. **La run non ha la potenza per testare la proporzionalità al peso.** Con `dump-function = log`
   i pesi grezzi che spaziano 7,04× si comprimono a **1,18×** sui pesi efficaci, e le quote
   spettanti coprono solo l'intervallo **0,0911 – 0,1075** (ampiezza 0,0164) contro una larghezza
   media dell'intervallo di Wilson di **0,1185**: la risoluzione è **7,2× più grossolana** del
   segnale da misurare.
6. **I round non sono indipendenti.** La probabilità di ripetizione consecutiva è **0,2133** contro
   **0,1004** atteso (**+112 %**), uniformemente su tutti e 10 i validatori, e decade entro il lag 3.
7. **Questa dipendenza spiega quasi interamente l'eccesso di rigetti.** Correggendo per il fattore
   di inflazione della varianza (VIF = 1,287) i rigetti GoF per epoca passano da **14/100 a 6/100**
   (attesi 5) e il chi-quadro aggregato da p = 0,024 a **p = 0,095**.
8. **Ciò che si può misurare, torna.** Sull'aggregato dei 9 921 blocchi l'ordinamento è preservato
   (Spearman quota attesa↔osservata = **+0,733**, critico 0,648 per n = 10), la concentrazione
   coincide con la teoria (HHI **0,1004** contro 0,1002 atteso; N_eff 9,956 contro 9,984) e lo
   scarto massimo per validatore è di **0,82 punti percentuali**.
9. **Il malus si comporta come deve in assenza di violazioni:** `M = 0` e `Ψ = 1` su tutte le 1010
   coppie (epoca, validatore), tutti e tre gli invarianti verificati, nessuna penalità senza evidenza.
10. **Il canale di retroazione inter-epoca è inerte in questa run**, per costruzione del modello di
    traffico: `ρ ∈ [0, 0,0080]` contro un range possibile `[0, 1]`.

---

## 3. Analisi per metrica

### 3.1 Qualità della randomness (VRF)

#### `E_i ~ Exp(1)` — test primario

- **File**: derivato da [phase2/candidate_long.csv](phase2/candidate_long.csv) come
  `E_i = score × weight_effective`, righe con `in_setup = False` (99 020 su 99 020 utilizzabili).
- **Cosa misura**: lo score grezzo della VRF, prima della divisione per il peso. È l'unica quantità
  la cui distribuzione è indipendente da pesi, smorzamento, malus, traffico e topologia.
- **Osservato**: media **0,994519**, varianza **0,98132**, KS `D = 0,002676`, `√n·D = 0,8421`, p = **0,477**.
  L'istogramma segue la densità teorica bin per bin: `[0; 0,25)` 22,271 % contro 22,120 % teorico;
  `[1; 1,5)` 14,545 % contro 14,475 %; `[4; 6)` 1,516 % contro 1,584 %.
- **Atteso**: media 1 (IC95 [0,99377 – 1,00623] per n = 99 020), varianza 1, `√n·D ≤ 1,358` al 5 %.
- **Giudizio**: **conforme**. La media è entro lo **0,55 %** dal valore teorico e dentro l'IC95; il KS
  è al 62 % del valore critico. La VRF e la sua normalizzazione sono corrette.

#### `score_norm` dell'argmin `~ U(0,1)` — Proposizione 5.11

- **File**: minimo di `score_norm` per `height` in [phase2/candidate_long.csv](phase2/candidate_long.csv),
  9 902 round non-setup.
- **Osservato**: media **0,501134**, KS `D = 0,008517`, `√n·D = 0,8475`, p = **0,468**.
- **Atteso**: media 0,5 (IC95 [0,49431 – 0,50569]), `√n·D ≤ 1,358`.
- **Giudizio**: **conforme**. Media entro lo **0,23 %** dal valore teorico.

> **Nota metodologica.** Lo `score_norm` delle righe con `is_winner = True` ha media **0,9083**, che
> a prima vista sembrerebbe una violazione clamorosa di Prop. 5.11. Non lo è, per due ragioni
> concorrenti: (a) `is_winner` marca chi ha *minato* il blocco, non l'argmin della sortition; (b) con
> 10 validatori a peso quasi uguale si ha `W_tot·score_i ≈ 10·E_i`, quindi
> `E[score_norm] = 1 − 1/11 = 0,909` su un candidato qualsiasi. Il valore 0,9083 è esattamente la
> media di un candidato estratto a caso — che è precisamente ciò che il produttore effettivo è in
> questa run (§3.5).

#### `score_norm_mismatch`

- **File**: colonna `score_norm_mismatch` di [phase2/candidate_long.csv](phase2/candidate_long.csv).
- **Osservato**: massimo **6,63·10⁻¹⁶**, media 2,58·10⁻¹⁷ su 99 020 righe.
- **Giudizio**: **conforme**. Errore di arrotondamento in doppia precisione.

#### Prop. 5.17 — gap standardizzato fra vincitore e secondo

- **File**: [phase3/wpoa_prop517.csv](phase3/wpoa_prop517.csv), [plots/prop517_gap_by_validator.png](plots/prop517_gap_by_validator.png).
- **Cosa misura**: `(score_(2) − score_(1))·(W_tot − w_eff_i*)`, che deve essere `Exp(1)`.
- **Osservato**: media dei gap standardizzati sulle 10 classi = **0,9909**; valori individuali da
  0,9211 (miner-1) a 1,1013 (miner-4). Il KS rigetta a 0,05 in **2 classi su 10** (miner-4 p = 0,0038,
  miner-1 p = 0,0051).
- **Atteso**: media 1,0 per ogni classe; ~0,5 rigetti attesi su 10 test ad α = 0,05.
- **Giudizio**: **lieve scostamento**. La media aggregata è entro lo 0,9 % da 1. I 2 rigetti su 10
  sono sopra lo 0,5 atteso ma con n ≈ 1000 per classe il KS è molto potente e coglie deviazioni
  dell'ordine dell'8–10 % sulla media; nessun validatore mostra un gap patologico. Non è un difetto
  del nucleo di sortition, la cui correttezza è già stabilita dai due test precedenti.

### 3.2 Correttezza meccanica del delay

- **File**: [phase2/candidate_long.csv](phase2/candidate_long.csv) (`delay_mismatch_s`,
  `delay_recompute_ok`), [phase3/consistency_checks.csv](phase3/consistency_checks.csv),
  [plots/delay_recompute_mismatch.png](plots/delay_recompute_mismatch.png).
- **Cosa misura**: il confronto fra il delay loggato dal nodo e quello ricalcolato indipendentemente
  dalla pipeline con `D_i = T + Δ_max(2·score_norm − 1) + λΦ`.
- **Osservato**: `delay_recompute_ok = True` su **99 020/99 020** coppie candidato-round; scarto
  massimo **6,22·10⁻¹⁵ s**, medio 2,61·10⁻¹⁶ s. La figura mostra tutti i punti fra 10⁻¹⁸ e 10⁻¹⁴ s
  contro una linea di tolleranza a 1,5·10⁻³ s. Il check critico
  `delay_recompute_mismatch_rounds_is_zero` è **PASS**.
- **Atteso**: mismatch nullo entro 1,5 ms.
- **Giudizio**: **conforme**, con margine di **12 ordini di grandezza**.

> **Attenzione all'interpretazione.** Questo test dimostra che harness e nodo **calcolano** la stessa
> formula. Non dimostra che lo scheduler **onori** il delay calcolato — ed è esattamente lì che
> questa run fallisce (§3.5).

### 3.3 Quota di blocchi contro peso

- **File**: [phase3/weight_vs_election.md](phase3/weight_vs_election.md),
  [phase3/wpoa_epoch_validators.csv](phase3/wpoa_epoch_validators.csv),
  [phase3/weight_election_wilson_coverage.csv](phase3/weight_election_wilson_coverage.csv),
  [phase3/weight_election_pvalue_uniformity.csv](phase3/weight_election_pvalue_uniformity.csv),
  [plots/weight_vs_election.png](plots/weight_vs_election.png),
  [plots/wilson_violation_heatmap.png](plots/wilson_violation_heatmap.png),
  [plots/p_value_uniformity.png](plots/p_value_uniformity.png),
  [plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png),
  [plots/election_share_distribution.png](plots/election_share_distribution.png).

#### Il problema di potenza statistica, da leggere prima di tutto il resto

Con `dump-function = log` le quote spettanti coprono un intervallo minuscolo:

| Quantità | Valore |
|---|---|
| pesi grezzi, rapporto max/min | **7,04×** (42 028 → 295 832) |
| pesi efficaci `ln(1+w)`, rapporto max/min | **1,183×** (10,646 → 12,598) |
| `p_theoretical`, intervallo su tutta la run | **0,0911 – 0,1075** (ampiezza **0,0164**) |
| spread intra-epoca medio di `p_theoretical` | **0,0124** |
| larghezza media dell'intervallo di Wilson | **0,1185** |
| **rapporto segnale / risoluzione** | **0,139** — la risoluzione è **7,2× più grossolana** |
| blocchi per epoca necessari per separare gli estremi | **≈ 5 100** (la run ne ha 100) |

Lo scatter di [plots/weight_vs_election.png](plots/weight_vs_election.png) lo rende evidente: i punti
formano una **striscia verticale** attorno a x ≈ 0,10, con la quota osservata che spazia 0,00–0,23 e
la quota spettante che non spazia affatto. La stessa cosa si vede in
[plots/longitudinal_logratio.png](plots/longitudinal_logratio.png), dove la nuvola copre ±0,15 in
ascissa contro ±2,5 in ordinata.

Ricalcolando le quote attese sugli stessi pesi grezzi con le altre funzioni di smorzamento:

| `dump-function` | spread medio delle quote | quota massima media | rapporto max/min |
|---|---:|---:|---:|
| `none` — `g(w)=w` | 0,1317 | 0,1720 | **4,35×** |
| `sqrt` — `g(w)=√w` | 0,0695 | 0,1345 | **2,08×** |
| **`log` — `g(w)=ln(1+w)` (questa run)** | **0,0124** | **0,1055** | **1,13×** |

Il comportamento è **quello atteso e corretto** per lo smorzamento logaritmico, ed è coerente per
direzione e ordine di grandezza con la tabella di riferimento (caso a balena: 10× → 1,9×). Qui la
compressione porta 4,35× a 1,13×. Ma la conseguenza sperimentale è che **questa run non può
verificare la proporzionalità**: non c'è dinamica da misurare.

#### Copertura degli intervalli di Wilson

- **Osservato**: **920/1000** intervalli contengono la quota spettante, **80 violazioni** contro le
  **50** attese ad α = 0,05. Test binomiale: `p(≥80 su 1000 | p=0,05) = 3,5·10⁻⁵`. Le violazioni
  sono distribuite su tutti i validatori (da 3 per miner-5 a 16 per miner-7) e su tutte le epoche,
  senza struttura a blocchi evidente nella heatmap.
- **Giudizio**: **scostamento significativo** al valore nominale, ma vedi §3.3 ultimo paragrafo:
  dopo la correzione per la dipendenza fra round l'attesa sale a ~64 violazioni e il p passa a
  **0,025**, due ordini di grandezza più debole.

#### Goodness of fit per epoca

- **Osservato**: **14 rigetti su 100** epoche misurate contro 5 attesi; test binomiale sul conteggio
  p = 4,6·10⁻⁴; KS dei p-value contro l'uniforme `D = 0,2804`, p ≈ 0. `MAE_p` medio **0,0279**,
  massimo 0,0631; `TV` medio 0,1395. Tutte e 100 le epoche hanno
  `share_changes_within_epoch = True`, e il metodo usato è `chi2_asymptotic` in 99 epoche su 100.
- **La forma dell'istogramma è informativa**: in [plots/p_value_uniformity.png](plots/p_value_uniformity.png)
  i p-value non mostrano un *picco* a 0 (che indicherebbe poche epoche gravemente sbagliate) ma una
  **inclinazione uniforme verso sinistra** (22, 15, 15, 16 nei primi quattro decili contro 10 attesi;
  4, 4, 5, 3 negli ultimi quattro). Questa è la firma di una **varianza sottostimata su tutte le
  epoche**, non di una media sbagliata su alcune.
- **Giudizio**: **scostamento significativo al nominale, riconducibile alla violazione
  dell'indipendenza** (vedi sotto).

#### Il test aggregato su tutta la run

Aggregando i 9 921 blocchi misurati:

| miner | quota attesa | quota osservata | O_i | atteso | scarto (p.p.) | z |
|---|---:|---:|---:|---:|---:|---:|
| miner-1 | 0,1049 | 0,1090 | 1081 | 1040,4 | +0,409 | +1,33 |
| miner-9 | 0,1044 | 0,0980 | 972 | 1036,0 | −0,645 | −2,10 |
| miner-6 | 0,1033 | 0,1009 | 1001 | 1025,2 | −0,244 | −0,80 |
| miner-4 | 0,1020 | 0,1102 | 1093 | 1011,5 | **+0,821** | **+2,70** |
| miner-3 | 0,1018 | 0,1069 | 1061 | 1010,1 | +0,513 | +1,69 |
| miner-5 | 0,1010 | 0,0997 | 989 | 1001,7 | −0,128 | −0,42 |
| miner-7 | 0,0992 | 0,0986 | 978 | 984,4 | −0,064 | −0,21 |
| miner-0 | 0,0953 | 0,0959 | 951 | 945,5 | +0,056 | +0,19 |
| miner-8 | 0,0942 | 0,0885 | 878 | 934,7 | −0,571 | −1,95 |
| miner-2 | 0,0939 | 0,0924 | 917 | 931,6 | −0,148 | −0,50 |

- **Ordinamento preservato**: Spearman fra quota attesa e quota osservata = **+0,733**, sopra il
  valore critico 0,648 per n = 10 a due code. Lo smorzamento logaritmico non inverte l'ordinamento,
  come richiesto.
- **Scarto massimo**: **0,82 punti percentuali** (miner-4), su quote spettanti che coprono
  complessivamente 1,1 p.p. `MAE_p` aggregato = **0,0036**, `MaxAE_p` = 0,0082, `TV` = 0,0180.
- Chi-quadro aggregato **19,135** su 9 gdl, p nominale **0,0241** → rigetto.
- I residui per validatore ([plots/residual_boxplot_by_validator.png](plots/residual_boxplot_by_validator.png))
  sono tutti centrati su zero (medie da −0,007 a +0,008): **nessun validatore ha un offset
  sistematico**.
- **Giudizio**: **conforme nella sostanza**. Un errore medio di 0,36 punti percentuali su quote del
  10 % è un'aderenza dello **0,36 %** in valore assoluto. Il rigetto del chi-quadro è una questione
  di potenza (n = 9 921), non di ampiezza.

#### La correzione che riconcilia i rigetti: i round non sono indipendenti

Il chi-quadro multinomiale e l'intervallo di Wilson assumono entrambi round **indipendenti**. In
questa run non lo sono (§3.9). Calcolando l'autocorrelazione lag-1 dell'indicatore "il validatore i
vince" e il conseguente fattore di inflazione della varianza `VIF = (1+r₁)/(1−r₁)`:

| miner | autocorr. lag-1 | VIF |
|---|---:|---:|
| miner-1 | +0,1444 | 1,3375 |
| miner-3 | +0,1354 | 1,3133 |
| miner-7 | +0,1351 | 1,3124 |
| miner-9 | +0,1319 | 1,3039 |
| miner-0 | +0,1288 | 1,2957 |
| miner-2 | +0,1287 | 1,2956 |
| miner-8 | +0,1152 | 1,2605 |
| miner-4 | +0,1135 | 1,2560 |
| miner-6 | +0,1112 | 1,2503 |
| miner-5 | +0,1093 | 1,2454 |
| **medio** | **+0,1254** | **1,2871** |

Applicando `VIF = 1,2871`:

| Test | Nominale | Corretto | Atteso |
|---|---|---|---|
| chi-quadro aggregato | χ² = 19,135, **p = 0,0241** | χ² = 14,868, **p = 0,0946** | — |
| rigetti GoF per epoca | **14/100** | **6/100** | 5,0 |
| violazioni di Wilson | 80/1000, p = 3,5·10⁻⁵ | attese ≈ 64, **p = 0,025** | 50 |

- **Giudizio**: l'eccesso di rigetti **non è evidenza di un'elezione distorta**: è quasi interamente
  spiegato dalla dipendenza lag-1 introdotta dallo scheduler. Dopo la correzione, i rigetti GoF per
  epoca sono **6 contro 5 attesi**, cioè indistinguibili dal caso. Resta un residuo marginale sulla
  copertura di Wilson (80 contro 64), coerente con un VIF stimato per media anziché per epoca.

### 3.4 Comportamento longitudinale

- **File**: [phase3/longitudinal.md](phase3/longitudinal.md),
  [phase3/wpoa_longitudinal_fits.csv](phase3/wpoa_longitudinal_fits.csv),
  [plots/longitudinal_logratio.png](plots/longitudinal_logratio.png),
  [plots/sign_test_by_validator.png](plots/sign_test_by_validator.png).

| Test | Osservato | Atteso | Giudizio |
|---|---|---|---|
| GLM logit su `log(peso)` | `β₁ = 1,3661`, IC95 **[0,8674 – 1,8649]**, n = 1000, converged | `β₁ = 1` | **compatibile con H0** (l'IC contiene 1), ma l'IC è largo **1,0 unità**: il test non discrimina |
| Regressione dei log-rapporti | pendenza **1,1907**, intercetta **−0,0170**, Pearson r = **0,1235**, n = 4483 | pendenza 1, intercetta 0 | pendenza compatibile in ordine di grandezza; `r` bassissimo |
| Sign test per validatore | 2/10 significativi: miner-1 (59/93 = 0,634, p = 0,0062) e miner-5 (56/88 = 0,636, p = 0,0069); gli altri fra 0,409 e 0,564 | concordanza > 0,5 | concordanza aggregata **479/913 = 0,5246**, z = +1,49, **p = 0,068** |

- **Giudizio**: **non conclusivo, per mancanza di dinamica, non per un difetto**. L'ampiezza dell'IC
  su `β₁` (±0,50) e il Pearson `r = 0,12` sono la conseguenza diretta del problema di potenza
  documentato in §3.3: la pendenza è stimata su un intervallo di ascisse che copre ±0,15 in
  log-rapporto. La concordanza aggregata è nella direzione giusta (0,5246 contro 0,5) ma appena
  fuori soglia. **Nulla qui contraddice la proporzionalità; nulla qui la conferma.**

### 3.5 Timer race, margine e inversioni — **il punto critico principale**

- **File**: [phase3/timer_race.md](phase3/timer_race.md),
  [phase3/wpoa_timer_race.csv](phase3/wpoa_timer_race.csv), [phase3/wpoa_sigma.csv](phase3/wpoa_sigma.csv),
  [phase2/round_level.csv](phase2/round_level.csv),
  [plots/margin_distribution.png](plots/margin_distribution.png),
  [plots/sigma_decomposition.png](plots/sigma_decomposition.png),
  [plots/inversion_bound_vs_observed.png](plots/inversion_bound_vs_observed.png).

#### Il margine è corretto

- `G_mean` osservato **2,6145 s**, `G_median` 2,0016 s su 9 902 round.
- KS contro la distribuzione **esatta simulata** della sortition implementata: `D = 0,0102`,
  **p = 0,4206** — il test di riferimento **non rigetta**. La media simulata (2,6513 s) e quella
  osservata (2,6145 s) differiscono dell'**1,4 %**.
- Il KS contro `Beta(1,n)` dà p = 0, ma è un **straw man dichiarato** dalla pipeline stessa: assume
  pesi uniformi e la sua media attesa (0,909 s) non è pertinente. **Non è un rilievo.**
- **Giudizio**: **conforme**. La distribuzione dei delay calcolati è quella che il modello prevede.

#### Ma il produttore del blocco è indipendente dai delay

| Quantità | Osservato | Riferimento |
|---|---:|---|
| tasso di inversione | **0,89900** | `1 − 1/n = 0,900` se il produttore fosse **uniforme fra i 10 candidati** |
| inversione simulata MC con `σ_S2` | 0,57978 | ciò che il rumore gaussiano da solo produrrebbe |
| bound di Prop. 5.18 | **1,00000** | **vacuo** — un maggiorante saturato non è una conferma |
| rank di sortition del produttore, quota a rank 1 | **10,10 %** | 10,00 % (caso puro) |
| Pearson(block time, delay del produttore) | **+0,0306** | 1 se il delay governasse la produzione |
| Pearson(block time, delay dell'argmin) | **+0,0126** | — |

La distribuzione del `rank_by_score` del produttore effettivo è piatta su tutti e 10 i ranghi
(1000, 965, 982, 1024, 1014, 968, 1037, 966, 969, 976 — scarto massimo dal valore uniforme: 3,7 %).
Il tasso di inversione non ha deriva nel tempo (Spearman epoca↔inversione = +0,046; intervallo per
epoca 0,820–0,970).

- **Atteso**: il vincitore della timer race deve coincidere con l'`argmin` della sortition
  (Prop. 5.10). Sotto rumore additivo, l'inversione cresce con `n·σ/Δ_max` ma resta **sbilanciata a
  favore del rank 1**.
- **Osservato**: nessuno sbilanciamento. Il rank è uniforme e il tasso di inversione coincide con il
  valore di **totale indipendenza**, non con il valore che il rumore gaussiano stimato (0,580)
  produrrebbe.
- **Giudizio**: **scostamento significativo da indagare — è il difetto principale di questa run.**
  La differenza fra 0,580 (rumore) e 0,899 (indipendenza) è decisiva: non si tratta di un delay
  "disturbato", si tratta di un delay **che non viene usato**.

#### Da dove viene il rumore

| Sorgente | σ | n | Nota |
|---|---:|---:|---|
| `S1_topology` | **0,000000 s** | 0 | **assente**, non piccolo: regime `native`, nessuna mappa |
| `S2_scheduler_residual_sd` | **3,482237 s** | 9 901 | sorgente primaria |
| `S2b_inversion_gap` | 2,257063 s | 8 901 | dispersione del margine sui round invertiti |

Il residuo dello scheduler (`dt_prev − delay_winner`) ha media **−2,298 s** e sd **3,482 s**: i
blocchi arrivano in media 2,3 s **prima** del delay del nodo che li produce. Con un margine medio di
2,61 s, il rumore (σ = 3,48 s) è **1,33× il margine stesso**. In regime `native` — 34 daemon sulla
stessa macchina, nessuna latenza di rete — questo rumore non può essere propagazione: le cause
candidate sono la granularità/periodo di poll del ciclo di mining di MultiChain, la contesa di CPU
fra i 34 processi, o un disallineamento fra l'istante di riferimento del timer wPoA e quello usato
dal miner nativo.

- **Giudizio**: **scostamento significativo**. `σ_S2 = 3,48 s` su una banda di ±5,0 s rende la barra
  temporale inefficace per costruzione. Anche ammesso rumore gaussiano, il modello ne predirebbe il
  58 % di inversioni; l'osservato 89,9 % indica che il legame è rotto, non solo degradato.

### 3.6 Stabilità del block time e correzione globale `Φ`

- **File**: [phase2/round_level.csv](phase2/round_level.csv) (`dt_prev_s`, `phi_s`,
  `scheduler_residual_s`), [phase1/round_delays.csv](phase1/round_delays.csv) (`feedback_phi`),
  [plots/phi_over_time.png](plots/phi_over_time.png).

| Quantità | Osservato | Atteso |
|---|---:|---|
| block time medio | **11,376 s** | 10 s (`target-block-time`) |
| scostamento | **+13,76 %** | ~0 % |
| mediana | 11,000 s | 10 s |
| sd | 2,904 s | — |
| minimo / massimo | 4 s / 24 s | banda dei delay `(4,6 – 14,6) s` |
| delay medio del produttore | 13,674 s (p25 13,96, p50 14,43, p75 14,65) | — |
| delay medio dell'argmin | 9,602 s | — |

**Deriva.** Il block time medio cresce monotonamente lungo la run:

| epoche | `Φ` medio | block time medio |
|---|---:|---:|
| 2–11 | −1,1855 s | 11,196 s |
| 22–31 | −1,1511 s | 11,139 s |
| 42–51 | −1,2388 s | 11,233 s |
| 62–71 | −1,3636 s | 11,351 s |
| 82–91 | −1,7216 s | 11,746 s |
| 92–101 | −1,9472 s | 12,002 s |

Spearman(epoca, block time medio) = **+0,7146** su 100 epoche (z ≈ +7,1, p ≈ 1,2·10⁻¹²); pendenza
**+0,0091 s per epoca**, cioè **+0,91 s su 100 epoche** (da 11,124 s a 12,354 s).

**Diagnosi di `Φ`.** Il controllore **funziona correttamente e non è il colpevole**:

- `Φ` medio = **−1,364 s**, che è esattamente `T − mean_spacing = 10 − 11,376 = −1,376 s`: la misura
  dell'errore è giusta.
- **Non è saturato**: `|Φ|max = 4,4167 s` contro `M = 5,0 s`; **0 round su 9 902** in saturazione.
  Ha ancora il 12 % di autorità inutilizzata.
- **Non oscilla**: `Φ < 0` nel **95,0 %** dei round, con solo **243/9 901 cambi di segno**
  consecutivi (2,5 %). Non è un anello a guadagno eccessivo.
- Il rolling median in [plots/phi_over_time.png](plots/phi_over_time.png) scende regolarmente da
  −1,2 a −1,9 senza discontinuità: **deriva lenta, non salto**.
- Il termine di correzione effettivo vale `λ·Φ = 0,3 × (−1,364) = **−0,41 s** in media, contro un
  errore da compensare di **+1,38 s**.

- **Giudizio**: **scostamento significativo**, ma la causa **non** è `Φ`. La catena causale è:
  il delay non governa il block time (§3.5, Pearson +0,031) → l'anello di retroazione è **aperto**
  → `Φ` misura l'errore ma il suo attuatore non ha autorità → l'errore non si chiude e, anzi, deriva.
  Alzare `λ` non risolverebbe: con un attuatore scorrelato dall'uscita, qualunque guadagno produce
  la stessa correzione inefficace. **Il dato da guardare è §3.5, non questo.**

### 3.7 Evoluzione dei pesi e retroazione inter-epoca

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv),
  [phase3/weight_engine_correlations.csv](phase3/weight_engine_correlations.csv),
  [phase3/weight_engine_gini_summary.csv](phase3/weight_engine_gini_summary.csv),
  [plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png),
  [plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png),
  [plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png),
  [plots/gini_delta_trajectory.png](plots/gini_delta_trajectory.png),
  [plots/esg_scores.png](plots/esg_scores.png).

#### Identità del motore di peso — verificate esattamente

| Identità | n | Errore relativo massimo |
|---|---:|---:|
| `W_k_raw = ESG_Mk · (τ_Mk + Σ c_i)` | 1010 | **0,0** (esatto) |
| `w_k_final = W_k_raw · (ρ_prev·λ_w + 1 − λ_w)`, e ≥ 2 | 1000 | **3,3·10⁻¹⁶** |
| `w_k_final = W_k_raw` per e = 1 | 10 | **0,0** (esatto) |
| `w_k_published = 100 · w_k_final` | 1010 | 2,8·10⁻⁸ |

- **Giudizio**: **conforme**. Il motore di peso implementa esattamente la definizione ricorsiva.

#### Il canale di retroazione è inerte in questa run

| Quantità | Osservato | Range possibile |
|---|---:|---|
| `ρ` (tasso di restituzione) | media **0,0021**, sd 0,0016, **max 0,0080**, 166/1010 esattamente 0 | `[0, 1]` |
| `R_k` per epoca | media 12,39 GAS, totale 12 517 GAS | — |
| `saldo_k` | media 5 860 GAS (5 600 – 6 195) | — |
| fattore `ρ·λ_w + (1−λ_w)` | media **0,5011**, min 0,5000, **max 0,5040** | `[0,5 – 1,0]` |

Il fattore moltiplicativo che dovrebbe modulare il peso occupa lo **0,8 %** del suo intervallo utile.
La causa è il modello di traffico: i miner sono finanziati con 5 600 GAS di seed e restituiscono al
massimo 5 × 9 = 45 GAS per epoca, quindi `ρ = R_k/saldo_k` non può superare ~0,008.

- Spearman lag-1 `ρ(e) → peso pubblicato in e+1`: **−0,0317**, p = 0,317, n = 1000. Per validatore
  ([plots/rho_feedback_by_validator.png](plots/rho_feedback_by_validator.png)) i valori si
  distribuiscono fra −0,13 e +0,17 e **nessuno è significativo**.
- Lo scatter [plots/rho_vs_next_weight.png](plots/rho_vs_next_weight.png) conferma visivamente:
  l'asse x copre `[0; 0,008]` e non c'è struttura.
- **Giudizio**: **non testabile in questa run, e non è un difetto del codice**. L'assenza di
  correlazione era prevedibile prima di guardare i dati, dato che `ρ` non ha varianza utile.
  L'identità algebrica del peso (sopra) è verificata esattamente, quindi il meccanismo **è
  implementato**; semplicemente non è stato **esercitato**.

#### Traiettoria dei pesi e amplificazione

- Il boxplot per epoca ([plots/weights_boxplot_per_epoch.png](plots/weights_boxplot_per_epoch.png))
  mostra i pesi efficaci (dopo malus e smorzamento) stabili fra **10,65 e 12,60** per tutte le 100
  epoche misurate, con mediana piatta a ≈ 11,75 e nessun allargamento né deriva. L'epoca 1 (setup)
  sta più in basso (≈ 9,2–9,8), coerentemente con la minore attività accumulata.
- I pesi **grezzi** crescono invece di un fattore **6,5× – 14,3×** dalla prima all'ultima epoca
  ([phase3/malus_weight_effect.csv](phase3/malus_weight_effect.csv)): è l'accumulo di `τ`. Lo
  smorzamento logaritmico assorbe quasi interamente questa crescita — `ln` di un fattore 10 aggiunge
  solo 2,3 — ed è esattamente il comportamento previsto.
- **Amplificazione della disuguaglianza**: `gini_delta = Gini(pubblicato) − Gini(input ESG×τ)` ha
  media **−2,6·10⁻⁵**, oscilla in `[−6,6·10⁻⁴; +8,3·10⁻⁴]`, pendenza della traiettoria
  **−1·10⁻⁶** (Spearman −0,0695, p = 0,490).
- **Giudizio**: **conforme**. Il motore **non concentra** il peso oltre la disuguaglianza dei propri
  input: la differenza di Gini è nulla entro il decimillesimo e non ha trend.

#### Staticità degli score ESG

- **Osservato**: **0 cluster head su 10** mostrano un ESG variabile fra epoche; 30 pubblicazioni ESG,
  tutte presenti sullo stream `weight-engine-esg` (check critico **PASS**).
- **Giudizio**: **conforme**.

### 3.8 Concentrazione

- **File**: [phase2/epoch_concentration.csv](phase2/epoch_concentration.csv), sezione 3 di
  [phase3/report.md](phase3/report.md), [plots/concentration_over_time.png](plots/concentration_over_time.png).

| Indice | Teorico medio (per epoca) | Osservato medio (per epoca) | **Aggregato teorico** | **Aggregato osservato** |
|---|---:|---:|---:|---:|
| HHI | 0,1002 | 0,1126 | **0,100156** | **0,100446** |
| N_eff | 9,983 | 8,912 | **9,9844** | **9,9556** |
| Gini | 0,0227 | 0,1887 | **0,021935** | **0,037607** |
| Entropia norm. | 0,9996 | 0,9718 | — | — |
| Nakamoto 1/2 | 5 (in 100/100 epoche) | 4 (82), 5 (14), 3 (4) | **5** | **5** |

- **Osservato**: per epoca il divario appare grande (Gini 0,189 contro 0,023). **Sull'aggregato il
  divario quasi scompare**: HHI 0,100446 contro 0,100156 (**+0,29 %**), N_eff 9,956 contro 9,984
  (**−0,29 %**), Nakamoto 1/2 identico a 5. La quota cumulativa per miner
  ([plots/election_share_distribution.png](plots/election_share_distribution.png)) spazia
  **8,8 % – 11,0 %**.
- **Atteso**: con 100 blocchi per epoca e 10 validatori, l'HHI e il Gini **osservati** sono
  sistematicamente sopra il teorico per pura varianza multinomiale. Il confronto affidabile è
  l'aggregato.
- **Giudizio**: **conforme**. Il divario per epoca è un artefatto di campione, non concentrazione
  reale: segnalarlo come tale sarebbe un falso allarme. La figura non mostra alcun trend crescente
  (l'unico picco, epoca 101 con HHI 0,152, è l'epoca parziale da 21 blocchi).

### 3.9 Streak e ripetizioni — **secondo punto critico**

- **File**: [phase3/streak.md](phase3/streak.md), colonne `L_max_*` e `repeat_prob_*` di
  [phase3/wpoa_epoch_tests.csv](phase3/wpoa_epoch_tests.csv), più calcolo diretto su
  [phase1/blocks.csv](phase1/blocks.csv).

| Quantità | Osservato | Riferimento Monte-Carlo | Eccesso |
|---|---:|---:|---:|
| prob. di ripetizione, per epoca (media) | **0,2151** | 0,1009 | **+113,2 %** |
| prob. di ripetizione, aggregata | **0,213232** | 0,100193 | **+112,8 %** (p = 1·10⁻⁴) |
| rigetti `repeat_prob` a 0,05 | **88/100 epoche** | 5 attesi | — |
| `L_max` medio per epoca | 3,750 | 2,690 | +39,4 % |
| rigetti `L_max` a 0,05 | **16/100 epoche** | 5 attesi | — |
| `L_max` aggregato | 6 | 4,700 (p = 0,092) | — |

Calcolo diretto sulla sequenza dei 9 910 blocchi non-setup:

- ripetizioni consecutive **2114/9909 = 0,2133** contro `Σpᵢ² = 0,1004` atteso sotto indipendenza;
- lunghezza media dei run **1,271** contro 1,112 attesa; distribuzione dei run:
  `{1: 6161, 2: 1262, 3: 289, 4: 66, 5: 15, 6: 2, 7: 1}`, massimo 7;
- **l'eccesso è uniforme su tutti i validatori**: da 0,1936 (miner-8) a 0,2377 (miner-1), sempre
  circa il doppio della rispettiva quota;
- **la memoria è corta**: lag-2 = 0,1162, lag-3 = 0,1063, lag-5 = 0,1092, lag-10 = 0,0979 — già al
  lag 3 si è quasi tornati al valore di indipendenza (0,1004).

- **Atteso**: sotto sortition pesata i round sono indipendenti e la probabilità di ripetizione è
  `Σpᵢ² ≈ 0,100`.
- **Giudizio**: **scostamento significativo**. Non è imputabile a un singolo nodo "più veloce"
  (l'eccesso è uniforme) né a un seed che non si rinfresca (in quel caso la dipendenza persisterebbe
  oltre il lag 1, e invece decade subito). È coerente con lo stesso meccanismo di §3.5: il produttore
  è scelto da una corsa locale con memoria di un round, non dalla sortition. **Questa dipendenza è
  anche la causa dell'eccesso apparente di rigetti in §3.3.**

### 3.10 Malus

Il meccanismo è **attivo** (`enable-wpoa-malus = true`, non configurabile), ma **nessuna violazione
è stata iniettata**: `malicious.enabled = false`, 0 miner malicious, 10 miner onesti.

| Verifica | Risultato |
|---|---|
| `M = 0` su ogni (epoca, validatore) | **sì**, 1010/1010 righe |
| `Ψ = 1` su ogni (epoca, validatore) | **sì**, min = max = 1,0 |
| `w_effective == w_raw · Ψ` | scarto massimo **0,0** (esatto) |
| `invariant_psi_in_unit` | 0 violazioni / 1010 |
| `invariant_weff_matches` | 0 violazioni / 1010 |
| `invariant_clean_psi_one` | 0 violazioni / 1010 |
| validatori esclusi (`Ψ = 0`) | **0** |
| check critico `malus_finite_and_psi_in_unit_interval` | **PASS** (1 035 430 campioni) |

[plots/malus_invariant_audit.png](plots/malus_invariant_audit.png) è **interamente verde** su tutte
le 1010 celle.

**File vuoti, come atteso e da dichiarare esplicitamente:**

- [phase1/malus_detections.csv](phase1/malus_detections.csv), [phase1/malicious_actions.csv](phase1/malicious_actions.csv),
  [phase1/malicious_opportunities.csv](phase1/malicious_opportunities.csv),
  [phase1/malicious_confirmations.csv](phase1/malicious_confirmations.csv),
  [phase2/malus_actions.csv](phase2/malus_actions.csv),
  [phase2/malus_detection_events.csv](phase2/malus_detection_events.csv),
  [phase2/malus_rate_by_miner.csv](phase2/malus_rate_by_miner.csv),
  [phase3/malus_rate.csv](phase3/malus_rate.csv): **0 righe dati**.
- [phase3/malus_detection.csv](phase3/malus_detection.csv) e [phase3/malus_funnel.csv](phase3/malus_funnel.csv):
  presenti ma tutti a zero; `precision`, `recall`, `f1` **non calcolabili** (nessun positivo).
- [phase3/malus_latency.csv](phase3/malus_latency.csv): `n = 0` per tutte e 4 le misure.
- [plots/malus_state_trajectory.png](plots/malus_state_trajectory.png),
  [plots/malus_action_funnel.png](plots/malus_action_funnel.png),
  [plots/malus_detection_latency.png](plots/malus_detection_latency.png): segnaposto vuoti.
- [plots/malus_weight_effect.png](plots/malus_weight_effect.png) mostra `malicious (n=0)` contro
  `honest (n=10)`: la colonna onesta riporta solo la crescita del peso pubblicato (6,5× – 14,3×
  dalla prima all'ultima epoca), che è accumulo di `τ` e **non porta alcun segnale di malus**.
- **`phase3/malus_effectiveness.md` NON esiste**: viene generato solo quando l'esperimento malicious
  è stato eseguito.

- **Giudizio**: **conforme**. Il malus ha **effetto esattamente nullo sul comportamento onesto**, che
  è la garanzia che il protocollo offre. Nessun peso è stato penalizzato senza evidenza.
- **Limite**: questa run **non dice nulla** sull'efficacia del malus — non su rilevazione, non su
  latenza, non su proporzionalità della penalità, non su reversibilità. Per misurarla serve un
  profilo con la sezione `malicious`.

### 3.11 Correlazione guadagno/transazioni e rielezione

- **File**: [phase2/epoch_engine.csv](phase2/epoch_engine.csv) appaiato con
  [phase3/weight_election_residuals.csv](phase3/weight_election_residuals.csv), 1000 coppie.

**Passo 1 — correlazione grezza con i blocchi vinti** (l'effetto *deve* essere presente, mediato dal peso):

| Variabile | Spearman | p |
|---|---:|---:|
| `companies_contribution_sum` | **+0,1484** | 2,1·10⁻⁶ |
| `w_k_published` | **+0,1340** | 1,9·10⁻⁵ |
| `miner_activity` | +0,0082 | 0,796 |
| `earnings_g_k` | +0,0063 | 0,841 |
| `income` | −0,0069 | 0,827 |
| `return_rate_rho` | −0,0005 | 0,987 |

**Passo 2 — correlazione dei residui `p_hat − p_theoretical`** (qui l'effetto **deve sparire**):

| Variabile | Spearman | p |
|---|---:|---:|
| `companies_contribution_sum` | +0,0712 | **0,0241** |
| `w_k_published` | +0,0212 | 0,504 |
| `income` | −0,0158 | 0,619 |
| `return_rate_rho` | −0,0109 | 0,730 |
| `earnings_g_k` | +0,0067 | 0,833 |
| `miner_activity` | −0,0066 | 0,834 |

- **Atteso**: al passo 1 una correlazione positiva con le variabili che *producono* il peso e
  nessuna con guadagno e reddito; al passo 2 nessuna correlazione residua.
- **Osservato**: il passo 1 si comporta esattamente così — correlano solo i contributi delle aziende
  e il peso pubblicato (che ne è funzione), **non** guadagno né reddito. Al passo 2 resta un solo
  valore sotto 0,05, `companies_contribution_sum` con ρ = +0,071. Con **6 test simultanei** la
  soglia di Bonferroni è 0,05/6 = **0,0083**, e 0,0241 non la supera.
- **Giudizio**: **conforme**. Nessun canale di influenza non documentato: il traffico entra
  nell'elezione **solo** attraverso il peso. Il residuo su `companies_contribution_sum` (ρ = 0,071,
  cioè lo 0,5 % di varianza spiegata) non sopravvive alla correzione per confronti multipli; vale la
  pena ricontrollarlo su una run con dinamica di peso più ampia, ma allo stato non è un rilievo.

### 3.12 Integrità della run e controlli di consistenza

| Check | Critico | Esito | Dettaglio |
|---|---|---|---|
| `registry_weights_finite_and_positive` | sì | **PASS** | 1 035 430 campioni, tutti finiti e ≥ 0 |
| `no_phantom_validator_in_registry` | sì | **PASS** | ogni indirizzo pesato è un miner noto |
| `malus_finite_and_psi_in_unit_interval` | sì | **PASS** | 1 035 430 campioni, ogni Ψ in [0,1] |
| `delay_recompute_mismatch_rounds_is_zero` | sì | **PASS** | coincidenza in ogni round (toll. 1,5 ms) |
| `every_esg_publication_reached_the_stream` | sì | **PASS** | 30 pubblicazioni ESG, tutte sullo stream |
| `only_miners_pay_the_treasury` | sì | **PASS** | 2 498 pagamenti, tutti da miner |
| `at_least_one_fully_measured_epoch` | sì | **PASS** | 100 epoche oltre `setup-first-blocks` |
| `certified_scores_reflected_in_the_engine` | no | **PASS** | ogni indirizzo certificato ha ESG non nullo |
| `traffic_counts_within_configured_range` | no | **PASS** | 2 969 coppie complete, tutte in range |
| `phi_consistent` | no | **FAIL** | 68 valori distinti di `Φ` |

**Su `phi_consistent`**: **non è un difetto**. `Φ` è per costruzione una funzione dello stato della
catena (§3.6) e deve variare; il check è una sonda di non-regressione tarata su run con feedback
spento, ed è marcato non critico proprio per questo. La nota di
[plots/phi_over_time.png](plots/phi_over_time.png) lo dice esplicitamente.

Altri controlli:

- **[phase1/verification.csv](phase1/verification.csv)**: 960 righe, verdetto `ok` su **tutte**,
  0 record `invalid`. Nessun peso pubblicato non ricalcolabile → **nessun `BadWeight` latente**.
- **[phase1/rpc_errors.csv](phase1/rpc_errors.csv)**: 420 errori, di cui **416 ad altezza ≤ 210**,
  cioè dentro la fase di setup, tutti sulle quattro RPC di audit (`wpoalistscores`,
  `wpoalistdelays`, `wpoalisteffectiveweights`, `wpoalistfinalweights`, 104 ciascuna) con il
  messaggio *"Round not evaluable on this node: the beacon seed or the weight registry is
  unavailable"*. È il comportamento atteso prima dell'attivazione della sortition. I 4 restanti
  sono su `weightgetlocalreturns` da miner-1. **Benigno.**
- **[phase2/epoch_traffic.csv](phase2/epoch_traffic.csv)**: 2 969 coppie (epoca, nodo) complete,
  **0 fuori range**. [plots/traffic_per_epoch.png](plots/traffic_per_epoch.png) mostra pianificato,
  inviato e on-chain sovrapposti su ~840–990 transazioni per epoca.
- **Epoca 101 parziale**: 21 blocchi invece di 100. Le sue metriche hanno intervalli molto larghi e
  concentrazione apparente più alta (HHI 0,152, Gini 0,43): **esclusa da ogni conclusione di
  tendenza** in questa analisi.
- **Run completata**: `status = ok`, altezza finale 10 122 contro un target derivato di 10 120.

---

## 4. Punti di forza

- **La VRF è di qualità eccellente.** `E_i` ha media **0,994519** contro 1 atteso (scarto
  **0,55 %**, dentro l'IC95) e KS `√n·D = 0,842` contro un critico di 1,358 su **99 020 campioni**
  (p = 0,477). L'istogramma aderisce alla densità teorica entro **0,15 punti percentuali** in ogni
  bin.
- **La Proposizione 5.11 è verificata con precisione.** Lo score normalizzato dell'argmin ha media
  **0,501134** contro 0,5 (scarto **0,23 %**) e KS p = 0,468 su 9 902 round.
- **Il calcolo del delay è esatto.** Ricalcolo indipendente coincidente entro **6,2·10⁻¹⁵ s** su
  **99 020** coppie candidato-round: un margine di **12 ordini di grandezza** sotto la tolleranza.
- **Il motore di peso implementa esattamente la definizione ricorsiva.** `W_k = ESG·(τ + Σc)` è
  verificata **esattamente** (errore 0,0) su 1010 righe, e
  `w_k = W_k·(ρ·λ_w + 1 − λ_w)` entro **3,3·10⁻¹⁶**.
- **Lo smorzamento logaritmico comprime come previsto senza invertire l'ordinamento.** Un rapporto
  di pesi grezzi di **7,04×** diventa **1,18×** sui pesi efficaci (quote da 4,35× a 1,13×), e
  l'ordinamento aggregato è preservato: Spearman quota attesa↔osservata = **+0,733**, sopra il
  critico 0,648 per n = 10.
- **La distribuzione dei delay calcolati è quella prevista dal modello.** KS del margine contro la
  distribuzione esatta simulata: **p = 0,4206**; media osservata 2,6145 s contro 2,6513 s simulata
  (scarto **1,4 %**).
- **Sull'aggregato l'elezione consegna ciò che il peso prevede.** `MAE_p = 0,0036` e
  `MaxAE_p = 0,0082` su quote di ≈ 0,10, cioè un errore medio di **0,36 punti percentuali**; nessun
  validatore ha un offset sistematico (residui tutti centrati fra −0,007 e +0,008).
- **La concentrazione osservata coincide con quella teorica.** HHI aggregato **0,100446** contro
  0,100156 (**+0,29 %**), N_eff 9,956 contro 9,984, Nakamoto 1/2 pari a 5 in entrambi i casi.
- **Il motore non amplifica la disuguaglianza dei propri input.** `Gini(pubblicato) − Gini(input)`
  ha media **−2,6·10⁻⁵** e pendenza **−1·10⁻⁶** su 101 epoche (Spearman −0,069, p = 0,490).
- **Il malus è a effetto rigorosamente nullo sul comportamento onesto.** `M = 0` e `Ψ = 1` su tutte
  le **1010** coppie (epoca, validatore); i tre invarianti valgono su **1010/1010** celle;
  `w_eff = w_raw·Ψ` è esatto.
- **Il traffico entra nell'elezione solo attraverso il peso.** I residui rispetto alla quota attesa
  non correlano con guadagno (ρ = +0,007), reddito (ρ = −0,016) né attività del miner (ρ = −0,007);
  l'unico valore sotto 0,05 non sopravvive alla correzione di Bonferroni su 6 test.
- **Tutti e 7 i controlli critici di consistenza passano**, su una run completata alla sua altezza
  target con 0 record di peso non ricalcolabili su 960 verifiche.

---

## 5. Punti critici / da approfondire

### 5.1 La timer race non seleziona il vincitore della sortition *(priorità massima)*

- **Entità**: tasso di inversione **0,899**, che coincide con `1 − 1/n = 0,900` per 10 candidati,
  cioè con il valore di **totale indipendenza**. Il rank di sortition del produttore effettivo è
  **uniforme** (10,10 % a rank 1 contro 10,00 % del caso; scarto massimo fra i 10 ranghi: 3,7 %). La
  correlazione fra block time e delay del produttore è **+0,031**; con il delay dell'argmin,
  **+0,013**.
- **Perché non è rumore**: il modello Monte-Carlo con il rumore misurato (`σ_S2 = 3,48 s`) predice il
  **58,0 %** di inversioni. L'osservato è **89,9 %**. La differenza fra "disturbato" e "indipendente"
  è di 32 punti percentuali, e il dato cade esattamente sul secondo.
- **Perché non è la rete**: regime **`native`**, `σ_S1 = 0` per assenza di mappa. Tutti i nodi sono
  processi locali sulla stessa macchina.
- **Ipotesi sulla causa**, in ordine di plausibilità:
  1. **Disallineamento dell'istante di riferimento** fra il timer wPoA e il ciclo di mining nativo di
     MultiChain. Il residuo `dt_prev − delay_winner` ha media **−2,298 s**: i blocchi arrivano
     sistematicamente *prima* del delay del loro stesso produttore, il che è compatibile con due
     origini temporali diverse.
  2. **Granularità del ciclo di poll del miner**: se il miner rivaluta la schedulazione a intervalli
     grossolani rispetto alla banda di ±5 s, l'ordinamento fine indotto dai delay viene perso.
  3. **Contesa di CPU fra i 34 daemon** sulla stessa macchina, che introduce ritardi di esecuzione
     non modellati; spiegherebbe `σ_S2 = 3,48 s` ma **non** spiegherebbe da sola un rank uniforme.
- **Cosa servirebbe per confermare**: (a) i log `-debug=wpoa` con l'istante di armamento del timer e
  l'istante effettivo di proposta per ogni round, da confrontare con `B_n.Time + D_i`; (b) una run
  `native` con **2–3 miner soltanto**, dove `1 − 1/n` vale 0,50–0,67 e si distingue nettamente dal
  58 % predetto dal rumore; (c) una run con `wpoa-sortition-delta` più grande (banda più ampia) per
  vedere se il tasso di inversione scende, come Prop. 5.18 prevede — se resta a `1 − 1/n`, la causa
  non è il rapporto rumore/banda ma il disallineamento.
- **Nota**: il bound di Prop. 5.18 vale **1,00000**, cioè è **vacuo**. Non va citato come conferma.

### 5.2 Dipendenza fra round consecutivi

- **Entità**: probabilità di ripetizione **0,2133** contro **0,1004** atteso (**+112,8 %**,
  p = 1·10⁻⁴ aggregato; 88/100 epoche rigettano). Lunghezza media dei run 1,271 contro 1,112.
- **Struttura**: l'eccesso è **uniforme su tutti i validatori** (0,194–0,238, sempre ≈ 2× la quota) e
  **decade entro il lag 3** (lag-2 0,1162, lag-3 0,1063, lag-10 0,0979 contro 0,1004 atteso).
- **Ipotesi sulla causa**: la stessa di 5.1. Una corsa locale con memoria di un round — il nodo che
  ha appena minato è ancora "avanti" nel proprio ciclo quando parte il round successivo — produce
  esattamente una dipendenza lag-1 uniforme e senza coda lunga. Uno squilibrio permanente fra nodi
  (un nodo più veloce degli altri) darebbe invece un eccesso **concentrato** su quel nodo e
  persistente a lag alti, che non si osserva.
- **Cosa servirebbe**: i timestamp di armamento del timer per round e per nodo; oppure una run in cui
  si introduce artificialmente un ritardo fisso su un nodo, per verificare se l'eccesso si sposta su
  di esso.

### 5.3 Il block time non converge e deriva

- **Entità**: media **11,376 s** contro 10 s (**+13,76 %**), in crescita monotona da **11,124 s** a
  **12,354 s** (Spearman epoca↔block time **+0,715**, p ≈ 1,2·10⁻¹²; pendenza **+0,91 s su 100
  epoche**).
- **`Φ` non è il colpevole, ed è importante dirlo**: misura l'errore correttamente (media −1,364 s
  contro un errore di +1,376 s), **non è saturato** (|Φ|max = 4,417 s contro M = 5,0 s, **0 round**
  in saturazione) e **non oscilla** (95,0 % dei round con `Φ < 0`, solo 2,5 % di cambi di segno
  consecutivi). Il termine effettivo `λΦ = −0,41 s` è però applicato a un attuatore — il delay — che
  non governa l'uscita (5.1): **l'anello è aperto**.
- **Implicazione pratica**: **non alzare `λ`**. Con un attuatore scorrelato dall'uscita qualunque
  guadagno produce la stessa correzione inefficace, e un `λ` alto introdurrebbe solo oscillazione. La
  correzione va fatta su 5.1.
- **Cosa servirebbe**: risolto 5.1, rimisurare. Se il block time convergesse a 10 s senza toccare
  `λ`, la diagnosi sarebbe confermata.

### 5.4 La run non ha la potenza statistica per testare la proporzionalità al peso

- **Entità**: le quote spettanti coprono **0,0911 – 0,1075** (ampiezza **0,0164**) contro una
  larghezza media dell'intervallo di Wilson di **0,1185**: la risoluzione è **7,2× più grossolana**
  del segnale. Servirebbero **≈ 5 100 blocchi per epoca** per separare gli estremi; la run ne ha 100.
  Ne conseguono l'IC su `β₁` largo 1,0 unità ([0,867 – 1,865]) e il Pearson `r = 0,1235` della
  regressione dei log-rapporti.
- **Causa**: **non è un difetto del codice**. È l'effetto combinato di (a) `dump-function = log`, la
  più aggressiva delle tre, e (b) pesi grezzi già relativamente omogenei (7,04×), prodotti da ESG
  uniformi in `[1,100]` e `τ` in un range stretto.
- **Cosa servirebbe**: per testare la proporzionalità, una run gemella con `dump-function = none`
  (spread delle quote **0,1317**, cioè **10,6×** quello attuale, sopra la risoluzione di Wilson) o
  `sqrt` (0,0695, **5,6×**). Le altre due varianti del profilo esistono già:
  `test/config/profiles/native/long24h-large-none.yaml` e `…-sqrt.yaml`. In alternativa, un profilo
  con ESG deliberatamente sbilanciati (una "balena") per ricreare il caso della tabella di
  riferimento.

### 5.5 La scala fixed-point ×100 interagisce con lo smorzamento logaritmico

- **Entità**: lo smorzamento è applicato al peso **intero del registro**, che è `100 × w_k_final`.
  Poiché `ln(1+100w) ≠ ln(1+w) + costante`, la scala **non si elide**: lo spread delle quote passa da
  **0,0204** (smorzamento sul peso non scalato) a **0,0124** (come in questa run), cioè si perde un
  ulteriore **39 %** della dinamica residua. Verificato numericamente su una coppia di pesi reali: la
  quota del più pesante passa da 0,5694 a 0,5420 (**−0,0275**) per effetto della sola scala.
- **`none` e `sqrt` sono immuni**, perché omogenee: la differenza misurata è **esattamente 0,0000**
  per entrambe.
- **Ipotesi**: probabile scelta implementativa non intenzionale, dato che l'effetto è invisibile per
  due delle tre funzioni di smorzamento.
- **Cosa servirebbe**: leggere `WPoASelector::ApplyDumping` in
  `src/wpoa/wpoa_selector.h` (riga ~103) e verificare su quale unità il peso arriva alla funzione;
  poi decidere se `log` debba operare sul peso in unità naturali. Non è un bug di correttezza — il
  risultato resta deterministico e concorde fra i nodi — ma è un fattore di taratura non documentato.

### 5.6 Il canale di retroazione inter-epoca non è stato esercitato

- **Entità**: `ρ ∈ [0; 0,0080]` contro un range possibile `[0; 1]`; il fattore moltiplicativo
  `ρ·λ_w + (1−λ_w)` resta in **[0,5000; 0,5040]**, cioè occupa lo **0,8 %** del suo intervallo utile
  `[0,5; 1,0]`. Spearman lag-1 = −0,0317 (p = 0,317); nessun cluster head significativo.
- **Causa**: il modello di traffico. Con `miner_seed_gas = 5600`, `miner_gas_returns_per_epoch_range
  = [0,5]` e `restitution_amount_range = [1.0, 9.0]`, la restituzione massima per epoca (45 GAS) è
  lo **0,8 %** del saldo tipico (≈ 5 860 GAS). **L'assenza di correlazione era prevedibile prima di
  guardare i dati** e non va letta come un difetto: l'identità algebrica del peso è verificata
  esattamente, quindi il meccanismo è implementato ma non sollecitato.
- **Cosa servirebbe**: alzare `miner_gas_returns_per_epoch_range` e `restitution_amount_range` di
  due ordini di grandezza, oppure abbassare `miner_seed_gas`, così che `ρ` copra almeno `[0; 0,5]`.
  Solo allora la Spearman lag-1 diventa un test e non una formalità.

### 5.7 Efficacia del malus: non misurata

- **Entità**: nessuna violazione iniettata, quindi **nessun dato** su rilevazione, precisione,
  richiamo, latenza, proporzionalità della penalità e reversibilità. `phase3/malus_effectiveness.md`
  non esiste.
- **Cosa servirebbe**: una run con la sezione `malicious` (il profilo di esempio è
  `test/config/profiles/native/malicious.yaml`). Si noti il limite strutturale già noto: solo
  `selfwrite` e `badweight` sono iniettabili dall'esterno; `delay` ed `equiv` nascono dentro il core
  di consenso e il loader li rifiuta.

### 5.8 Prop. 5.17: due classi su dieci rigettano

- **Entità**: media dei gap standardizzati **0,9909** (corretta), ma il KS rigetta a 0,05 per
  **miner-4** (gap 1,1013, p = 0,0038) e **miner-1** (gap 0,9211, p = 0,0051), contro ~0,5 rigetti
  attesi su 10 test.
- **Ipotesi**: con n ≈ 1000 per classe il KS coglie scostamenti dell'8–10 % sulla media; miner-4 è
  anche il validatore con il maggiore scarto di quota (+0,82 p.p., z = +2,70), il che suggerisce una
  fluttuazione campionaria comune ai due indicatori più che un difetto di scoring. La correttezza del
  nucleo è comunque già stabilita in modo indipendente da §3.1.
- **Cosa servirebbe**: ripetere su una seconda run con seed diverso; se gli stessi due validatori
  rigettassero di nuovo, allora sarebbe strutturale.

---

## 6. Conclusione

| Asse | Giudizio | Evidenza |
|---|---|---|
| **Qualità della randomness (VRF)** | **Eccellente** | `E_i` media 0,994519 (KS p = 0,477, n = 99 020); `score_norm` dell'argmin media 0,501134 (KS p = 0,468); Prop. 5.17 media 0,9909 |
| **Affidabilità della sortition (calcolo)** | **Eccellente** | delay ricalcolato entro 6,2·10⁻¹⁵ s su 99 020 casi; margine `G` conforme alla simulazione esatta (p = 0,421); identità del peso esatte |
| **Affidabilità della sortition (attuazione)** | **Compromessa** | inversione 0,899 ≈ `1 − 1/n`; rank del produttore uniforme; corr(block time, delay) = +0,031 |
| **Efficacia dello smorzamento** | **Corretta ma non discriminante** | 7,04× → 1,18×, ordinamento preservato (Spearman +0,733); spread delle quote 7,2× sotto la risoluzione |
| **Efficacia del malus** | **Non misurata** (effetto nullo corretto in assenza di violazioni) | `M = 0`, `Ψ = 1`, 3/3 invarianti su 1010 celle; nessuna violazione iniettata |
| **Stabilità del block time** | **Non raggiunta** | media 11,376 s contro 10 s (+13,76 %), deriva +0,91 s su 100 epoche, Spearman +0,715 |

**Stato di salute complessivo.** Il protocollo wPoA, **come oggetto matematico e come
implementazione di calcolo, è sano in questa run**: la VRF produce randomness di qualità
verificabile su quasi 100 000 campioni, la trasformazione di Efraimidis–Spirakis e la normalizzazione
dello score si comportano esattamente come i teoremi prevedono, il delay è calcolato in modo
riproducibile alla precisione della macchina, il motore di peso soddisfa le proprie identità
algebriche esattamente, e il registro dei malus non penalizza nessuno senza evidenza. Sull'aggregato
dei 9 921 blocchi misurati l'elezione consegna le quote che il peso prevede entro **0,36 punti
percentuali** e ne preserva l'ordinamento.

**Il difetto è a valle, nel punto di giunzione fra la sortition e lo scheduler di MultiChain.** Il
produttore effettivo del blocco risulta statisticamente indipendente dall'ordinamento di sortition —
inversione al **89,9 %**, cioè il valore di scelta uniforme fra 10 candidati, contro il **58,0 %**
che il rumore misurato spiegherebbe. Da questo discendono, come conseguenze e non come difetti
autonomi, la dipendenza lag-1 fra round (**+112,8 %** di ripetizioni) e il mancato aggancio del block
time al target (**+13,76 %**, in deriva), perché la retroazione `Φ` — che misura il proprio errore
correttamente, non è saturata e non oscilla — agisce su un attuatore privo di autorità.

Un rilievo importante sul piano metodologico: **l'eccesso apparente di rigetti statistici non è
evidenza di un'elezione distorta.** Correggendo per il fattore di inflazione della varianza indotto
dalla dipendenza fra round (VIF = 1,287), i rigetti del goodness-of-fit per epoca scendono da
**14/100 a 6/100** contro 5 attesi, e il chi-quadro aggregato da p = 0,024 a **p = 0,095**. Ciò che
resta è coerente con il caso.

Infine, **questa run non è in grado di verificare la proprietà centrale che intende misurare**: con
`dump-function = log` su pesi già omogenei, le quote spettanti coprono 1,6 punti percentuali contro
una risoluzione sperimentale di 11,9. La verifica della proporzionalità va portata sulle varianti
`none` e `sqrt` dello stesso profilo, che esistono già nel repository, prima che qualunque
affermazione su `β₁` o sulla pendenza dei log-rapporti possa essere sostenuta.

**Priorità di intervento**: (1) chiarire il disallineamento fra timer wPoA e scheduler di mining
(§5.1); (2) rimisurare block time e ripetizioni una volta risolto, senza toccare `λ`; (3) ripetere
l'esperimento su `long24h-large-none.yaml` per ottenere la dinamica di peso necessaria a testare la
proporzionalità; (4) verificare se lo smorzamento logaritmico debba operare sul peso in unità
naturali anziché sull'intero fixed-point (§5.5).
