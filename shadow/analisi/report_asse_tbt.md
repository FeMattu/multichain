# Famiglia `target_block_time` — report di dettaglio

Famiglia costruita da `famiglie_confronto.csv`: `parametro_variato =
target_block_time`, valori 15 | 10 | 5 | 3 | 2, quattro famiglie parallele (una
per livello, tenuto costante). 20 run in tutto.

> **Avvertenza sulla famiglia.** La colonna `costanti` di
> `famiglie_confronto.csv` elenca solo gli scalari di `params.dat`. Lungo questo
> asse variano anche due cose che non traccia: `setup_first_blocks` (60, 64, 98,
> 144, 200 al calare del `tbt`) e l'assegnazione ESG di `run1-tbt-15s`, diversa
> da quella di `run2`–`run5`. Vedi [report_generale.md](report_generale.md) §2.
> Ogni trend qui sotto e' stato ricontrollato sul solo sottoinsieme omogeneo
> `run2`–`run5`, e il valore per quel sottoinsieme e' riportato accanto.

---

## 1. Il quadro per `tbt` (medie sui 4 livelli)

`Dmax = delta·tbt` con `delta` = 0.5 [M]. `G` = margine fra il secondo e il
primo delay dello stesso round [M]. Quote medie per epoca, misurate contro
`quota_attesa_vigenza` [I].

| tbt [s] | Dmax [s] | G mediano [s] | G med./Dmax | frazione G<100ms | quota m1 oss./att. | scost. m1 | scost. m2 | scost. m3 | finestre χ² incomp. | eccesso consecutivi |
|---|---|---|---|---|---|---|---|---|---|---|
| 15 | 7.5 | 3.99 | 0.532 | 0.027 | 0.662 / 0.611 | **+0.051** | −0.049 | −0.003 | 3/18 | +16% |
| 10 | 5.0 | 2.89 | 0.579 | 0.035 | 0.706 / 0.670 | **+0.036** | −0.009 | −0.027 | 0/0 (n.d.) | +15% |
| 5 | 2.5 | 1.49 | 0.596 | 0.061 | 0.754 / 0.665 | **+0.089** | −0.053 | −0.037 | 19/88 | +18% |
| 3 | 1.5 | 0.86 | 0.576 | 0.085 | 0.762 / 0.663 | **+0.098** | −0.057 | −0.041 | 60/118 | +31% |
| 2 | 1.0 | 0.57 | 0.574 | 0.133 | 0.767 / 0.654 | **+0.112** | −0.050 | −0.062 | 74/140 | +37% |

Il rapporto `G mediano / Dmax` e' costante — 0.571 ± 0.044 sulle 20 run — mentre
`G` in secondi scala col `tbt`: la struttura relativa della corsa dei timer non
cambia, cambia solo la sua ampiezza assoluta contro un RTT fissato dalla
geografia. E' l'invarianza di scala prevista dalla Prop. 5.18, ed e' la
grandezza che governa tutto il resto della tabella. A `tbt` = 10 s il test a
finestra non e' applicabile: `attesa_minima_finestra` mediana 4.67 < 5 in tutte
le 28 finestre delle 4 run, quindi `0/0` va letto come "non misurato", non come
"nessun rifiuto".

---

## 2. Il bias di selezione

![scostamento di quota e persistenza](plots/07_bias_e_persistenza.png)

Le serie per epoca stanno in
[`02_quota_osservata_vs_attesa.png`](plots/02_quota_osservata_vs_attesa.png), e
la traiettoria dei pesi che le genera in
[`01_traiettoria_peso.png`](plots/01_traiettoria_peso.png).

Lo scostamento della quota di m1 dalla `quota_attesa_vigenza` cresce
monotonamente al calare del `tbt`, e i due miner leggeri lo pagano entrambi.
Spearman `tbt` vs bias di m1 sulle 20 run: ρ = **−0.576**, p = 0.008; sul solo
sottoinsieme omogeneo `run2`–`run5`: ρ = **−0.582**, p = 0.018. Il bias e'
direzionale e non dispersivo: sull'insieme delle 529 righe per host,
m1 = +0.086 (t = +9.45, p = 1.1·10⁻¹⁹), m2 = −0.045 (t = −5.45, p = 7.9·10⁻⁸),
m3 = −0.041 (t = −10.08, p = 5.7·10⁻²²). Il confronto e' contro il peso
**davvero leggibile all'altezza di ogni blocco**, quindi la deriva legittima del
peso (§1.3 del protocollo di analisi) e' gia' scontata: quello che resta e'
errore di selezione. Il bias correla con `frazione_G_sotto_100ms` (ρ = +0.662,
p = 0.0015) e **non** con l'RTT da solo (ρ = −0.093, p = 0.70): a decidere e' il
margine assoluto fra i timer, non la latenza in se'.

---

## 3. La persistenza del vincitore — segno opposto a quello atteso

| tbt | consecutivi osservati [M] | attesi [I] | eccesso | run significative al 5% |
|---|---|---|---|---|
| 15 | 255 | 219.8 | **+16%** | 1/4 |
| 10 | 676 | 586.4 | **+15%** | 4/4 |
| 5 | 914 | 773.1 | **+18%** | 3/4 |
| 3 | 1274 | 970.3 | **+31%** | 4/4 |
| 2 | 1554 | 1133.5 | **+37%** | 4/4 |

`consecutivi_attesi` = Σp_i²·(n−1) sulle quote **osservate**, quindi lo
sbilanciamento delle quote e' gia' scontato. L'eccesso e' positivo in **20/20**
run e significativo al 5% in 16/20 (test binomiale normale). Spearman `tbt` vs
eccesso: ρ = −0.791, p = 3.3·10⁻⁵ sulle 20 run; ρ = −0.873, p = 1.0·10⁻⁵ su
`run2`–`run5`. Il protocollo di analisi (§7) prevedeva il rischio opposto —
ripetizioni **piu' rare** dell'atteso per Spacing residuo di MultiChain: con
`mining_diversity = 0.0` in 20/20 run lo Spacing e' effettivamente inerte, e al
suo posto emerge una correlazione positiva nella sequenza dei proposer. La
lettura compatibile con l'andamento in `tbt` e' un vantaggio di chi e' gia' sul
tip quando parte il round successivo: piu' l'intervallo si accorcia, piu' pesa
il tempo di propagazione rispetto al margine `G`. **Conseguenza metodologica:**
i blocchi non sono estrazioni indipendenti, e ogni chi-quadro multinomiale e'
percio' anti-conservativo — parte dei rifiuti a `tbt` basso e' attribuibile alla
non-indipendenza. La direzione del bias (§2) non dipende da questa assunzione.

---

## 4. Chi-quadro a finestra scorrevole

![chi2 a finestra](plots/03_chi2_finestra_vs_tbt.png)

Solo le finestre con attesa ≥ 5 in ogni classe (364 su 713). Il tasso di
rifiuto al 5% passa da 3/18 a `tbt` = 15 s a 74/140 a `tbt` = 2 s. Il chi-quadro
di sintesi contro l'ultimo peso (`chisq.csv`) — l'indicatore grossolano, che
confonde deriva del peso ed errore di selezione — d'accordo con quello a
finestra: compatibile in 4/4 run a 15 s, in 3/4 a 10 s, in **0/4** a 5, 3 e 2 s.
Che i due indicatori concordino e' l'argomento piu' forte contro l'ipotesi che
il rifiuto sia un artefatto della scelta del peso di confronto. La controprova
indipendente della pipeline riproduce il χ² scritto dall'harness in `summary.txt`
con scarto ≤ 0.0004 in 20/20 run.

---

## 5. Attivita' per epoca e block time

| tbt [s] | Θ medio per epoca [I] | Θ/(12·tbt) [tx/s] | dt medio [s] [M] | scarto [s] | scarto [%] |
|---|---|---|---|---|---|
| 15 | 58.05 | 0.322 | 15.59 | +0.589 | 3.9 |
| 10 | 41.62 | 0.347 | 10.74 | +0.736 | 7.4 |
| 5 | 20.61 | 0.343 | 5.66 | +0.660 | 13.2 |
| 3 | 12.42 | 0.345 | 3.61 | +0.606 | 20.2 |
| 2 | 8.58 | 0.357 | 2.62 | +0.619 | 30.9 |

![scarto del block time](plots/05_scarto_block_time.png)

Il tasso di generazione ricostruito Θ/(12·`tbt`) e' costante a 0.32–0.36 tx/s
su tutta la campagna: conferma quantitativa [I] che il generatore di traffico e'
esogeno e gira a tempo reale, come letto nell'harness. Ne discende che il numero
di transazioni per epoca — e quindi `tau`, `W_k` e l'allocazione `A_k` — scala
col `tbt` di un fattore ~7 fra 15 s e 2 s: e' il canale **throughput**, atteso, e
non riguarda la selezione. Lo scarto del block time e' invece **sempre positivo**
(20/20 run), quasi costante in secondi (0.642 ± 0.135) e non correlato al target
(ρ = +0.356, p = 0.12): e' la firma dell'offset vdso del simulatore, non la
retroazione `λ·Φ_n`, che avrebbe prodotto scarti di segno alternato. In
percentuale esplode da 3.9% a 30.9% solo perche' il denominatore si riduce.

---

## 6. Cosa questa famiglia non puo' dire

`delta` e' fissato a 0.5 in tutte e 20 le run, quindi `Dmax` e `tbt` variano
**insieme** e la campagna non li separa. L'ipotesi che governa §2 e §3 — e' la
banda assoluta `Dmax` a contare, non il `tbt` — e' compatibile con tutti i dati
ma non e' isolata da essi. L'esperimento che la deciderebbe non e' in questa
campagna: variare `delta` al calare del `tbt` tenendo `Dmax` costante (per
esempio `delta` = 3.75 a `tbt` = 2 s, per riprodurre i 7.5 s di banda del caso a
15 s) e verificare se il bias sparisce. Va aggiunto che a `tbt` = 2 e 3 s i
timestamp dei blocchi hanno granularita' di 1 s (`dt_mediana_s` intera in 20/20
run), quindi le statistiche di block time in quel regime sono a grana grossa.
