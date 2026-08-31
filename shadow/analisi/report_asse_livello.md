# Famiglia `livello` — report di dettaglio

Famiglia costruita da `famiglie_confronto.csv`: `parametro_variato = livello`,
valori `regionale` | `nazionale` | `continentale` | `intercontinentale`, cinque
famiglie parallele (una per run, a `tbt` costante). Il livello cambia **solo** la
latenza della topologia simulata; ogni altro parametro di `params.dat` e'
identico dentro ciascuna famiglia.

---

## 1. Il quadro per livello (medie sulle 5 run)

| livello | RTT max [ms] [I] | scost. m1 | scost. m2 | scost. m3 | finestre χ² incomp. | eccesso consecutivi | frazione G<100ms | verdetti fork |
|---|---|---|---|---|---|---|---|---|
| `regionale` | 10.0 | +0.099 | −0.046 | −0.052 | 32/91 | +23% | 0.075 | 5 nessun fork |
| `nazionale` | 22.0 | +0.080 | −0.042 | −0.038 | 36/90 | +24% | 0.071 | 4 nessun fork, 1 ritardo |
| `continentale` | 44.7 | +0.049 | −0.020 | −0.029 | 27/91 | +31% | 0.066 | 2 nessun fork, 3 ritardo |
| `intercontinentale` | 112.0 | +0.117 | −0.072 | −0.045 | 61/92 | +17% | 0.061 | 3 nessun fork, 1 ritardo, **1 corsa al tip** |

**L'unica colonna che ordina monotonamente con l'RTT e' quella dei fork.** Il
`regionale` non produce mai divergenza; salendo di latenza compaiono i ritardi di
propagazione, e l'unico verdetto `corsa al tip` di tutta la campagna e'
`run5-tbt-2s/intercontinentale` — il caso di latenza massima e banda minima.
Le colonne statistiche non sono monotone: il `continentale` ha il bias piu' basso
(+0.049) pur avendo quattro volte l'RTT del `regionale`. Con cinque run per
livello, di cui una (`run1`) con ESG diverso, questa non-monotonia non e'
interpretabile come effetto: e' rumore campionario. La conferma e' in §3.

---

## 2. La geografia non tocca gli input del peso

| run | Θ medio per epoca — regionale / nazionale / continentale / intercontinentale | Kruskal-Wallis |
|---|---|---|
| `run1-tbt-15s` | 58.93 / 57.33 / 57.93 / 58.07 | H = 1.84, p = 0.61 |
| `run2-tbt-10s` | 41.79 / 41.36 / 41.96 / 41.36 | H = 0.37, p = 0.95 |
| `run3-tbt-5s` | 20.66 / 20.77 / 20.56 / 20.44 | H = 0.43, p = 0.94 |
| `run4-tbt-3s` | 12.44 / 12.53 / 12.31 / 12.38 | H = 0.47, p = 0.93 |
| `run5-tbt-2s` | 8.56 / 8.51 / 8.65 / 8.58 | H = 0.09 , p = 0.99 |

Gli score ESG [M] sono **identici** fra le quattro aree in tutte e 40 le coppie
(run, host): la condizione di anomalia della §4.4 del protocollo di analisi —
"ESG diverso a parita' di run" — **non si verifica**. E l'attivita' per epoca e'
statisticamente indistinguibile fra le aree in tutte e cinque le run
(p ≥ 0.61). Il peso grezzo medio di m1 varia fra aree di meno dell'1.5% in ogni
run (per esempio 296.6 / 301.0 / 301.1 / 305.6 in `run5`).

Questo e' un risultato in se': la divergenza "ESG identico, `tau` diverso" che il
protocollo di analisi si aspettava di trovare **fra le aree** non c'e'. Il canale
throughput esiste ma corre lungo l'asse `tbt`, non lungo la geografia — perche' a
cambiare la durata in secondi dell'epoca e' il block time, non la latenza. La
catena del peso della §1.2 e' quindi invariante per livello, e tutto l'effetto
della geografia si concentra sulla corsa dei timer.

---

## 3. Dove la latenza agisce davvero: il rapporto RTT / margine

| livello | RTT [ms] | G mediano a tbt=15 s | a tbt=2 s | RTT / G mediano a 15 s | a 2 s |
|---|---|---|---|---|---|
| `regionale` | 10.0 | 3.39 s | 0.62 s | 0.003 | 0.016 |
| `nazionale` | 22.0 | 3.82 s | 0.59 s | 0.006 | 0.037 |
| `continentale` | 44.7 | 4.50 s | 0.55 s | 0.010 | 0.082 |
| `intercontinentale` | 112.0 | 4.26 s | 0.55 s | 0.026 | **0.204** |

`G` non dipende dalla geografia — dipende da `Dmax`, ed e' identico fra i livelli
a parita' di `tbt` (rapporto `G mediano/Dmax` 0.571 ± 0.044 su tutte e 20 le
run). Quello che cambia fra i livelli e' il **denominatore del rischio**: a
`tbt` = 15 s l'RTT intercontinentale e' il 2.6% del margine mediano, a `tbt` = 2 s
ne e' il 20%. La geografia non altera la statistica della sortition: altera
quanto tempo ha il vincitore per propagare prima che il secondo agisca. Ed e'
esattamente nella cella con il rapporto piu' alto — intercontinentale a 2 s —
che compare l'unico `corsa al tip` della campagna, insieme al bias piu' alto
(+0.149) e al tasso di rifiuto piu' alto (26/35 finestre).

---

## 4. Il bias per cella (livello × tbt)

| livello | tbt=15 | tbt=10 | tbt=5 | tbt=3 | tbt=2 |
|---|---|---|---|---|---|
| `regionale` | +0.070 | +0.092 | +0.096 | +0.097 | +0.112 |
| `nazionale` | +0.044 | +0.058 | +0.069 | +0.060 | +0.126 |
| `continentale` | +0.079 | −0.039 | +0.068 | +0.072 | +0.061 |
| `intercontinentale` | +0.014 | +0.033 | +0.124 | **+0.164** | **+0.149** |

L'interazione e' piu' informativa dei margini. L'`intercontinentale` parte dal
bias **piu' basso** di tutti a `tbt` alto (+0.014 a 15 s, +0.033 a 10 s) e arriva
al **piu' alto** a `tbt` basso (+0.164 a 3 s): e' l'unico livello con un
andamento nettamente monotono, ed e' coerente con §3 — a banda larga la latenza
e' irrilevante, a banda stretta e' il fattore dominante. Gli altri tre livelli
crescono debolmente o restano piatti. L'unica cella negativa dell'intera
campagna, `continentale` a 10 s (−0.039), non ha una spiegazione nei dati
disponibili: e' anche una delle quattro celle in cui il test a finestra non e'
applicabile per campione insufficiente, quindi non e' sostenuta da un test.

---

## 5. Limiti di questa famiglia

Shadow **non implementa il jitter**: le latenze sono deterministiche per coppia
di nodi. Fra i livelli varia dunque la latenza **media**, mai la sua varianza, e
il `sigma` che compare nella Prop. 5.18 non e' isolabile su questo asse. La
dispersione dell'esponente empirico per livello riportata in `fit_prop518.csv`
(−0.676 regionale, −0.695 nazionale, −0.739 continentale, −1.203
intercontinentale, atteso −1) **non** e' quindi interpretabile come effetto della
geografia sulla varianza dei ritardi: sono quattro stime dello stesso esponente
su cinque punti ciascuna, con r² fra 0.81 e 0.98.
Va aggiunto che la famiglia contiene cinque run per livello, di cui `run1` con
un'assegnazione ESG diversa dalle altre quattro
([report_generale.md](report_generale.md) §2): i confronti *entro* una singola
run restano puliti — e' li' che il livello e' l'unica cosa che cambia — mentre le
medie per livello della §1 mescolano le due assegnazioni.
