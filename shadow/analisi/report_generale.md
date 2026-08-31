# Capitolo 8 — Experimental Evaluation: report generale

Campagna wPoA su MultiChain 2.3 (progetto POESIA), 20 run Shadow:
5 `target-block-time` (15, 10, 5, 3, 2 s) x 4 livelli geografici.
Tutti i numeri di questo documento sono ricavati dalle tabelle sotto
`analisi/fogli-di-analisi/` e `analisi/esperimenti/`, lette in sola lettura.

Legenda: **[M]** misurato da un evento nativo della catena, **[I]** inferito o
ricostruito dalla pipeline.

Dettaglio nei report per famiglia:
[report_asse_tbt.md](report_asse_tbt.md) e
[report_asse_livello.md](report_asse_livello.md). Grafici in [plots/](plots/).

---

## 1. Errori bloccanti

**Nessuna riga `[H]` in tutta la campagna.** Verificato sui 20 file
`esperimenti/<run>/<livello>/errori_integrita.csv`: 82 righe complessive, di cui
**0 `[H]`**, **2 `[P]`**, **80 `[I]`**. Nessuna run e' invalidata all'origine.

Le 2 righe `[P]` sono discusse in §5 (risultato Sez. 5.11.1).

---

## 2. Due scostamenti dalle premesse del protocollo di analisi

Vanno prima di tutto il resto perche' cambiano il modo in cui vanno letti i
confronti, non perche' invalidino dei dati.

### 2.1 `setup-first-blocks` non e' 60 in tutte le run — varia con il `tbt`

| tbt | 15 | 10 | 5 | 3 | 2 |
|---|---|---|---|---|---|
| `setup_first_blocks` [M] | 60 | 64 | 98 | 144 | 200 |

Il valore sigillato in `params.dat` coincide sempre con `setupblocks` di
`getinfo` (`setup_mismatch = 0` su 20 run): il dato e' internamente coerente, e
la fase di setup e' tagliata correttamente in ogni run
(`altezza_max - setup_first_blocks - blocchi_misurati` = 0, a meno dello
`spread_altezze` di `forks.csv`). Non c'e' nessun errore nei dati: e' la
Sezione 2 del protocollo di analisi a riportare `60` per tutte le run.

**Conseguenza:** lungo l'asse `tbt` non varia solo il `tbt`. Varia anche la
lunghezza della fase di setup, e con essa il numero di epoche gia' consumate
prima che inizi la misura.

### 2.2 `run1-tbt-15s` ha un'assegnazione ESG diversa dalle altre quattro run

Gli score ESG [M] sono **identici fra le quattro aree di ogni run** — la
condizione di anomalia della §4.4 del protocollo di analisi **non** si verifica: 40 coppie
(run, host) su 40 concordi. Ma **non** sono identici fra le run:

| run | m1 | m2 | m3 | ESG m1/m3 |
|---|---|---|---|---|
| `run1-tbt-15s` | 26.46 | 24.17 | 17.50 | **1.51** |
| `run2` … `run5` | 85.56 | 26.46 | 24.17 | **3.54** |

Il multinsieme dei valori e' lo stesso, ruotato di una posizione: il seed di
configurazione non e' stato riprodotto identico per `run1`. L'effetto non e'
marginale — l'ESG del miner capofila cambia di un fattore 3.2, e con esso lo
sbilanciamento dei pesi che tutta l'analisi delle quote misura.

`famiglie_confronto.csv` dichiara la famiglia `target_block_time` come
variazione di **un solo** parametro, ma la colonna `costanti` elenca solo gli
scalari di `params.dat`: non traccia ne' l'ESG ne' `setup_first_blocks`.

**Conseguenza operativa, applicata in tutto il seguito:** ogni trend lungo
l'asse `tbt` e' stato ricalcolato **anche** sul solo sottoinsieme
omogeneo `run2`–`run5` (16 run, ESG identico). I trend principali sopravvivono,
e dove il numero cambia lo si dichiara.

---

## 3. Quadro di sintesi — quali configurazioni reggono

Una riga per run. `verify` = record dichiarati non validi dal verificatore
interno del nodo; `inv.` = inversioni peso→delay; `χ² fin.` = finestre
scorrevoli incompatibili al 5% su finestre ammissibili; `χ² run` = chi-quadro di
sintesi contro l'ultimo peso; `consec.` = eccesso di blocchi consecutivi
sull'atteso multinomiale; `bias m1` = scostamento medio della quota di m1 dalla
`quota_attesa_vigenza`.

| run | tbt | stato | fork | blocchi [M] | verify | inv. | χ² fin. | χ² run | scarto bt | consec. | bias m1 |
|---|---|---|---|---|---|---|---|---|---|---|---|
| `run1-tbt-15s/continentale` | 15 | completa | nessun fork | 109 | 0 | 0 | 0/5 | 1.73 si | +0.77 (5.1%) | +29% | +0.079 |
| `run1-tbt-15s/nazionale` | 15 | completa | nessun fork | 113 | 0 | 0 | 0/5 | 0.50 si | +0.25 (1.7%) | +15% | +0.044 |
| `run1-tbt-15s/regionale` | 15 | completa | nessun fork | 107 | 0 | 0 | 0/3 | 2.15 si | +0.90 (6.0%) | +14% | +0.070 |
| `run1-tbt-15s/intercontinentale` | 15 | completa | nessun fork | 112 | 0 | 0 | 3/5 | 3.54 si | +0.44 (2.9%) | +6% | +0.014 |
| `run2-tbt-10s/continentale` | 10 | completa | nessun fork | 260 | 0 | 0 | n.d. | 0.21 si | +0.81 (8.1%) | +19% | −0.039 |
| `run2-tbt-10s/nazionale` | 10 | completa | nessun fork | 265 | 0 | 0 | n.d. | 2.76 si | +0.65 (6.5%) | +14% | +0.058 |
| `run2-tbt-10s/regionale` | 10 | completa | nessun fork | 261 | 0 | 0 | n.d. | 12.62 **NO** | +0.78 (7.8%) | +10% | +0.092 |
| `run2-tbt-10s/intercontinentale` | 10 | completa | nessun fork | 263 | 0 | 0 | n.d. | 5.51 si | +0.70 (7.0%) | +19% | +0.033 |
| `run3-tbt-5s/continentale` | 5 | completa | ritardo di propag. | 322 | 0 | 0 | 3/21 | 6.56 **NO** | +0.64 (12.8%) | +23% | +0.068 |
| `run3-tbt-5s/nazionale` | 5 | completa | nessun fork | 317 | 0 | 0 | 4/22 | 11.31 **NO** | +0.70 (14.0%) | +23% | +0.069 |
| `run3-tbt-5s/regionale` | 5 | completa | nessun fork | 318 | 0 | 0 | 3/23 | 22.35 **NO** | +0.69 (13.9%) | +21% | +0.096 |
| `run3-tbt-5s/intercontinentale` | 5 | completa | nessun fork | 323 | 0 | 0 | 9/22 | 20.30 **NO** | +0.61 (12.2%) | +7% | +0.124 |
| `run4-tbt-3s/continentale` | 3 | completa | ritardo di propag. | 393 | 0 | 0 | 14/30 | 13.52 **NO** | +0.57 (19.1%) | +36% | +0.072 |
| `run4-tbt-3s/nazionale` | 3 | completa | ritardo di propag. | 385 | 0 | 0 | 10/28 | 21.19 **NO** | +0.64 (21.3%) | +36% | +0.060 |
| `run4-tbt-3s/regionale` | 3 | completa | nessun fork | 387 | 0 | 0 | 13/30 | 10.94 **NO** | +0.63 (20.9%) | +31% | +0.097 |
| `run4-tbt-3s/intercontinentale` | 3 | completa | ritardo di propag. | 391 | 0 | 0 | 23/30 | 48.48 **NO** | +0.58 (19.5%) | +24% | +0.164 |
| `run5-tbt-2s/continentale` | 2 | completa | ritardo di propag. | 451 | 0 | 0 | 10/35 | 16.50 **NO** | +0.65 (32.3%) | +48% | +0.061 |
| `run5-tbt-2s/nazionale` | 2 | completa | nessun fork | 459 | 0 | 0 | 22/35 | 35.29 **NO** | +0.60 (29.9%) | +35% | +0.126 |
| `run5-tbt-2s/regionale` | 2 | completa | nessun fork | 458 | 0 | 0 | 16/35 | 24.76 **NO** | +0.60 (30.2%) | +36% | +0.112 |
| `run5-tbt-2s/intercontinentale` | 2 | completa | **corsa al tip** | 455 | 0 | 0 | 26/35 | 50.77 **NO** | +0.63 (31.3%) | +31% | +0.149 |

**Come si legge in dieci secondi.** Le colonne di integrita' — stato, fork,
`verify`, inversioni — sono pulite su tutte e 20 le run: nessun fork
persistente, nessun record di peso invalido, nessuna inversione peso→delay.
Le colonne statistiche si degradano monotonamente scendendo di `tbt`: a 15 s la
selezione e' compatibile con la teoria quasi ovunque, da 5 s in giu' non lo e'
piu' in nessuna run.

`n.d.` per `run2-tbt-10s`: nessuna delle 28 finestre raggiunge attesa ≥ 5 nella
classe piu' piccola (`attesa_minima_finestra` mediana 4.67). Non e' un
fallimento del test, e' un test che **non si e' potuto fare**.

---

## 4. Le due famiglie di confronto

`famiglie_confronto.csv` costruisce due sole famiglie: `target_block_time` (4
famiglie, una per livello) e `livello` (5 famiglie, una per run).

### 4.1 Asse `target-block-time` → [report_asse_tbt.md](report_asse_tbt.md)

E' l'asse che discrimina. Scendendo da 15 s a 2 s, tre grandezze indipendenti
peggiorano insieme e in modo monotono: la quota osservata del miner piu' pesante
si stacca dalla quota attesa in vigenza (da +0.05 a +0.11 in media, Spearman
`tbt` vs bias ρ = −0.58, p = 0.008; ρ = −0.58, p = 0.018 sul solo sottoinsieme
omogeneo `run2`–`run5`); le ripetizioni dello stesso proposer superano l'atteso
multinomiale di una frazione crescente (+16% a 15 s → +37% a 2 s, ρ = −0.79,
p = 3·10⁻⁵; ρ = −0.87 su `run2`–`run5`); e il tasso di rifiuto del chi-quadro a
finestra passa da 3/18 finestre a 74/140. La causa comune candidata e' il
restringimento della banda `Dmax = delta·tbt`, che a 2 s vale 1 s: i tre delay si
affollano e il margine mediano fra primo e secondo scende a 0.55 s.

### 4.2 Asse `livello` → [report_asse_livello.md](report_asse_livello.md)

E' l'asse che **non** tocca la catena del peso. A parita' di run, l'attivita'
per epoca `theta_epoca` e' statisticamente indistinguibile fra le quattro aree
(Kruskal-Wallis p ≥ 0.61 in tutte e 5 le run) e l'ESG e' identico: gli input del
peso non dipendono dalla geografia. La latenza agisce solo sulla corsa dei
timer, e li' l'effetto e' reale ma non monotono nell'RTT: l'`intercontinentale`
e' il livello con il bias piu' alto a `tbt` basso (+0.16 a 3 s, +0.15 a 2 s) ed e'
l'unica run con verdetto `corsa al tip`.

Da notare che il canale "ESG identico, `tau` diverso" che il protocollo di
analisi si aspettava fra le aree **non si manifesta**: e' invece fortissimo
lungo l'asse `tbt` (Θ medio per epoca 58.1 a 15 s contro 8.6 a 2 s), perche' li'
cambia davvero la durata in secondi dell'epoca. Il tasso di generazione
ricostruito, Θ/(12·tbt), e' costante a 0.32–0.36 tx/s su tutte le run: conferma
[I] che il generatore di traffico e' esogeno e a tempo reale.

---

## 5. Verifica dei risultati formali

| risultato | cosa prevede | esito | dove |
|---|---|---|---|
| **Teor. 5.3** | `Pr[i eletto] = w_i^n / W^n` | **Confermato a `tbt` ≥ 10 s, respinto sotto.** A 15 s: 3/18 finestre incompatibili, χ² di run compatibile in 4/4. A 2 s: 74/140 finestre incompatibili, χ² di run incompatibile in 4/4. Lo scostamento e' **direzionale**, non dispersivo: m1 +0.086, m2 −0.045, m3 −0.041 in media (t = +9.5 / −5.4 / −10.1; p < 10⁻⁷) | `peso_riconciliazione.csv`; `chisq.csv`; [report_asse_tbt.md](report_asse_tbt.md) |
| **Cor. 5.4** | peso effettivo nullo → eletto con probabilita' 0 | **Confermato.** In `proposers.csv` compaiono solo m1, m2, m3 in tutte e 20 le run; `admin` — che **ha** il permesso di mining — e `ca` non propongono mai fuori dal setup. 6149 blocchi attribuiti, nessuno a un nodo senza peso. Monte Carlo: `selezioni_candidati_nulli` = 0 in 2 scenari su 2, `cor_5_4_rispettato` = 1 | `proposers.csv`; `validazione_sortition.csv`; `errori_integrita.csv` |
| **Lemma 6.1 / Prop. 6.2** | `w_k = 0` mai per la sola riconciliazione mancata | **Confermato.** 369 righe con `rho_epoca = 0`; di queste 131 hanno peso pubblicato e **tutte** con valore > 0. Nessun peso azzerato da una riconciliazione mancata. *Precisazione:* nell'epoca 1 `peso_grezzo = 0` e il peso pubblicato vale 1 — e' il troncamento a intero ≥ 1 della Def. 5.16, quindi l'equivalenza `w = 0 ⟺ W = 0` vale sul `w` reale, non sull'intero pubblicato | `peso_riconciliazione.csv` |
| **Def. 5.9 / Cor. 5.8** | `g(w)` comprime i pesi grandi | **Non esercitato.** `dump_function = none` in 20/20 run: `peso_dopo_malus`, `peso_efficace_epoca` e `peso_effettivo_epoca` coincidono riga per riga in tutte le 2139 righe. Limite dichiarato, §6 | `run_index.csv` |
| **Def. 5.10-5.13, Prop. 5.12** | delay monotono nello score; `λ·Φ_n` non altera l'ordinamento | **Confermato.** `inversioni = 0` in 20/20 run. La precondizione del test regge: l'ordine `m1 > m2 > m3` e' identico in **tutte** le 372 epoche con i tre pesi pubblicati insieme, quindi il confronto delay medio ↔ peso finale e' legittimo su questa campagna. I delay medi restano ben separati (`delay_pos_in_banda` 0.57 / 0.76 / 0.89): nessuna saturazione dello score | `ordinamento_delay.csv`; `weights_trajectory.csv`; `proposers.csv` |
| **Prop. 5.17** | `E[score(2) − score(1)] = 1/(W_tot − w_i*)` | **Non verificabile con le tabelle disponibili.** Serve il margine `G` **per round** affiancato al vincitore di quel round e alla mappa dei pesi in vigore; `sortition_margins.csv` aggrega `G` sull'intera run e non porta l'identita' del vincitore. Campo mancante: `vincitore` (e `w_vincitore`) in `sortition_margins.csv`, o una tabella `margini_per_round.csv` che non esiste | — |
| **Prop. 5.18** | `Pr[G < t] = 1 − (1 − t/(2·Dmax))^n`; `Pr[inv.] = O((n·σ/Dmax)^(2/3))` | **Confermato nella forma, esponente qualificato.** Il fit lineare di `frazione_G_sotto_100ms` contro `1/Dmax` ha r² = 0.96 sull'intera campagna e 0.97–0.99 per livello. L'esponente log-log e' −0.83 (atteso −1), per livello da −0.68 a −1.20. Il rapporto `G_mediano/Dmax` e' **0.571 ± 0.044** su tutte e 20 le run: l'invarianza di scala prevista. Vedi §6 sul limite del jitter | `sortition_margins.csv`; `fit_prop518.csv`; `plots/04_fit_prop518.png` |
| **Cap. 6.4** | `rho_k` unico canale fra epoca ed epoca successiva | **Confermato ma quasi inerte.** `spearman_rho_vs_peso_successivo` e' positivo in 60/60 righe (media 0.53 / 0.54 / 0.56 per m1/m2/m3): la formula implementata e' quella dichiarata. Ma `rho` e' **binaria** in questa campagna (§6): il canale esiste e non e' graduato | `correlazioni.csv`; `peso_riconciliazione.csv` |
| **Def. 5.17-5.24** | quattro tipi di violazione riducono il peso, decadimento reversibile | **Non esercitato.** `malus_events_found = 0` in 20/20 run, `fattore_correzione_malus` = 1 in tutte le 2139 righe. Limite dichiarato, §6 | `run_index.csv`; `peso_riconciliazione.csv` |
| **Sez. 3.3.1** | con `mining-diversity = 0` lo Spacing e' inerte | **Confermato, e il dato va oltre.** `mining_diversity = 0.0` in 20/20. Non solo non c'e' Spacing residuo: i blocchi consecutivi sono **piu'** dell'atteso in 20/20 run (+22% in media, 16/20 significative al 5%). Il vincolo che sopprime le ripetizioni e' assente; al suo posto c'e' una persistenza positiva. Vedi [report_asse_tbt.md](report_asse_tbt.md) §3 | `alternanze.csv`; `run_index.csv` |
| **Sez. 5.11.1** | ogni peso ricalcolabile dai soli input pubblici | **Confermato: 1544 pesi su 1546 riprodotti esattamente.** I 2 scarti sono entrambi in `run5-tbt-2s/nazionale`, host m1, epoche 38–39, e sono **diagnosticati**: il peso pubblicato corrisponde a `rho^(e−1)` = 0.6012 e 0.0000 contro 1.0 ricalcolata (verificato ricostruendo il fattore `w/(κ·W)`). `verifica_riconciliazione.log` registra per quella run **una** transazione vista e mai confermata, vista da `admin` e **m1**: la riconciliazione di m1 e' stata contata dall'harness e non dalla catena. Il verificatore interno dichiara `non_validi = 0` in 20/20 run: a divergere e' il modello di attribuzione dell'altezza della pipeline, non il peso sulla catena | `peso_riconciliazione.csv`; `verify.csv`; `verifica_riconciliazione.log` |

---

## 6. Limiti dichiarati

**Meccanismi non esercitati dalla campagna.**

1. **Malus (Def. 5.17-5.24) mai attivati.** `malus_events_found = 0` ovunque,
   `Psi = 1` in ogni riga. La reversibilita' dell'esclusione (Prop. 5.20) e
   l'ordine `w → w·Ψ → g(w·Ψ)` restano non misurati. L'ordine e' comunque
   ininfluente qui, perche' anche `g` e' l'identita'.
2. **Smorzamento anti-whale (Def. 5.9) mai attivato.** `dump_function = none`
   ovunque. Con un peso che nelle run arriva a 7:1 fra m1 e m3, e' proprio il
   regime in cui `g_sqrt` o `g_log` cambierebbero i numeri.
3. **La retroazione `rho` non e' graduata — risultato nuovo.** `rho_epoca` e'
   **esattamente 0 (17.2%) o esattamente 1 (82.8%)**, mai un valore intermedio,
   su 2139 righe. La ragione e' misurabile: la riconciliazione `R_k` supera il
   tetto `A_k + B_k^(e−1)` della Def. 6.7 nel **95.6%** delle righe con
   allocazione positiva, con un rapporto mediano di **30×** (`A_k` mediana 0.73
   GAS, `R_k` mediana 23.2 GAS). L'harness riconcilia a tasso fisso per miner
   senza guardare `A_k`, quindi `rho` satura. Conseguenze: il saldo residuo
   `B_k^e` e' esattamente 0 in 2058 righe su 2139 e non e' **mai** negativo — il
   riporto della Def. 6.7 e' anch'esso inerte; e il fattore
   `[rho·λ_w + (1 − λ_w)]` della Def. 6.9 assume solo i due valori 1 e 0.5.
   Non e' un difetto del protocollo: e' una calibrazione fra il generatore di
   traffico esogeno e la formula di allocazione (`alpha` = 0.2, Θ ≈ 21). Ma
   significa che il regime intermedio di `rho`, quello che da' senso alla
   gradualita' della Def. 6.9, **non e' testato**.
   Vedi `plots/08_rho_e_riconciliazione.png`.

**Limiti del campione e della misura.**

4. **Chi-quadro per epoca mai concludente.** `campione_sufficiente_epoca` = 0 in
   **tutte** le 1587 righe in cui e' definito. Con `weight-epoch-length` = 12 e
   tre miner sbilanciati l'attesa della classe piu' piccola non arriva a 5.
   Il test a finestra di 5 epoche e' ammissibile in 364 finestre su 713 — e in
   `run2-tbt-10s` in **nessuna**.
   *Raccomandazione metodologica:* per rendere conclusivo il test per epoca
   servono epoche piu' lunghe o run piu' lunghe, tali che l'attesa minima per
   classe superi 5. Con i rapporti di peso osservati (≈ 0.66/0.19/0.15) servono
   almeno ~35 blocchi per epoca contro i 12 attuali.
5. **I chi-quadro assumono blocchi indipendenti, e non lo sono.** L'eccesso di
   ripetizioni documentato in §5 (riga Sez. 3.3.1) e' una correlazione positiva
   nella sequenza dei proposer. Un test multinomiale su osservazioni
   autocorrelate e' anti-conservativo: parte dei rifiuti a `tbt` basso e'
   attribuibile alla non-indipendenza piu' che a un errore di selezione. La
   direzione dello scostamento (§5, Teor. 5.3) e' l'evidenza piu' solida,
   perche' non dipende da quell'assunzione.
6. **Shadow non implementa il jitter di rete.** Le latenze sono deterministiche
   per coppia di nodi, quindi il `sigma` della Prop. 5.18 non e' isolabile: fra i
   livelli varia la latenza **media**, non la sua varianza. L'esponente empirico
   −0.83 va letto con questa qualificazione, e la sua dispersione per livello
   (−0.68 … −1.20) non e' interpretabile come effetto della geografia sulla
   varianza.
7. **Offset vdso del simulatore.** Lo scarto del block time e' positivo in
   **20/20** run, con media 0.642 s e deviazione 0.135 s, e **non** scala col
   target (Spearman `tbt` vs `scarto_s` ρ = +0.36, p = 0.12). E' la firma
   dell'offset di scheduling descritto in §7 del protocollo di analisi, non la
   retroazione `λ·Φ_n` — che avrebbe prodotto scarti di segno alternato. In
   percentuale l'offset passa da 5% a 32% del target proprio perche' e' costante
   in secondi. Vedi `plots/05_scarto_block_time.png`.
8. **Timestamp a granularita' di 1 s.** `dt_mediana_s` e' intero in 20/20 run.
   A `tbt` = 2 s la quantizzazione e' meta' del target: le statistiche di block
   time a 2 e 3 s vanno lette come grane grosse.
9. **Monte Carlo: testa la formula, non il binario.**
   `validazione_sortition.csv` reimplementa in Python la trasformazione
   Efraimidis-Spirakis e la trova compatibile in 5 scenari su 5 (χ² da 0.006 a
   1.71, sempre sotto il critico). Non dimostra che il C++ compilato la
   implementi cosi': serve esporre `ComputeScore` a un harness dedicato.
10. **Copertura di pubblicazione incompleta, crescente al calare del `tbt`.**
    La quota di righe (epoca × host) senza record di peso pubblicato in quella
    epoca passa dal 20–24% a `tbt` = 15 s al 31–35% a `tbt` = 2 s, e non e'
    uniforme fra host (m3: 249 assenze, m1: 167). In 113 epoche su 713 **nessun**
    miner pubblica. Ne discende l'avvertenza del punto successivo.
11. **`delta_gini_pubblicato_input` va letto solo a parita' di host.** Aggregata
    cosi' com'e', la colonna vale in media −0.07 e suggerisce che la retroazione
    **comprima** la disuguaglianza. E' un artefatto della copertura incompleta:
    ristretta alle 372 epoche in cui tutti e tre i miner hanno pubblicato, la
    colonna vale **0.0000** (a quattro decimali, per ogni `tbt`), che e' il
    valore atteso — con `rho` = 1 per tutti si ha `w_k ∝ W_k` e il Gini e'
    invariante di scala. **Non c'e' ne' amplificazione ne' compressione da
    retroazione.** Sulle epoche con meno di tre publisher la stessa colonna vale
    da −0.11 a −0.24, perche' il Gini e' calcolato su un insieme piu' piccolo.

---

## 7. I grafici

Tutti generati dalle tabelle citate, nessuno riprodotto da analisi precedenti.

| grafico | cosa mostra |
|---|---|
| [`01_traiettoria_peso.png`](plots/01_traiettoria_peso.png) | traiettoria del peso pubblicato [M] per epoca, 5 run × 4 livelli × 3 host, scala log. I buchi nelle serie sono le epoche senza record pubblicato (§6.10) |
| [`02_quota_osservata_vs_attesa.png`](plots/02_quota_osservata_vs_attesa.png) | quota osservata (punti) contro `quota_attesa_vigenza` (linea) per epoca. Il distacco dei punti blu di m1 sopra la propria linea si legge a occhio scendendo verso `tbt` = 2 s |
| [`03_chi2_finestra_vs_tbt.png`](plots/03_chi2_finestra_vs_tbt.png) | χ² a finestra contro `tbt` con la soglia 5.991, e tasso di rifiuto per livello |
| [`04_fit_prop518.png`](plots/04_fit_prop518.png) | Prop. 5.18: fit lineare contro `1/Dmax` e log-log, con l'esponente atteso −1 |
| [`05_scarto_block_time.png`](plots/05_scarto_block_time.png) | scarto del block time in secondi (costante) e in percento (crescente) |
| [`06_gini_entropia.png`](plots/06_gini_entropia.png) | Gini ed entropia normalizzata del peso nel tempo, **ristretti alle epoche con tutti e tre i miner** per la ragione del §6.11 |
| [`07_bias_e_persistenza.png`](plots/07_bias_e_persistenza.png) | scostamento di quota per host contro `tbt`, ed eccesso di blocchi consecutivi |
| [`08_rho_e_riconciliazione.png`](plots/08_rho_e_riconciliazione.png) | distribuzione di `rho` (binaria) e rapporto `R_k/(A_k+B)` contro il tetto della Def. 6.7 |

Sulla concentrazione del peso il grafico dice una cosa netta, e va letto sulle
sole epoche con tutti e tre i publisher (§6.11): **il Gini sale e poi si ferma.**
Parte da 0 nell'epoca 1 — dove tutti i pesi valgono 1, il troncamento della
Def. 5.16 — sale nelle prime ~10 epoche e da li' in avanti resta su un plateau di
**0.374 ± 0.032**, identico in tutte e 20 le run e in tutti e quattro i livelli.
La pendenza stimata oltre l'epoca 10 e' **−0.00005 per epoca** (sd 0.0007, su 16
run con almeno 4 punti): piatta. L'entropia normalizzata si assesta specularmente
a 0.766 ± 0.040. `host_dominante` e' m1 in 533 epoche su 600 con almeno un
publisher.

E' il comportamento che il vincolo `lambda_w < 1` (Oss. 6.2) prevede: la
retroazione non diverge, la disuguaglianza si stabilizza entro la durata della
run. Unito al §6.11 — Gini del peso pubblicato uguale a quello del peso grezzo di
input, a parita' di host — il quadro e' che **non c'e' amplificazione da
retroazione in questa campagna**. In base alla §1.3 del protocollo di analisi la concentrazione che resta
e' la wPoA che fa il suo mestiere: m1 ha l'ESG piu' alto e il cluster piu'
attivo.

---

## 8. Test aggiuntivi, per run

* **Correlazioni (`correlazioni.csv`, Cap. 6.4).** Canale economico
  fee → `rho`: Spearman positivo in **60/60** righe (run × host), media 0.60
  (m1), 0.51 (m2), 0.37 (m3) — decrescente col peso, coerente col fatto che il
  miner che vince meno blocchi incassa meno fee. Canale formale
  `rho` → peso successivo: positivo in 60/60, media 0.53–0.56.
  Da segnalare come conferma metodologica: `spearman_entrate_vs_rho`, che somma
  ai fee i rifornimenti dell'admin, e' **piu' basso** del solo fee per m2 (0.41
  contro 0.51) e m3 (0.15 contro 0.37), e diventa negativo in alcune run.
  Confondere un trasferimento con un guadagno degrada davvero il segnale.
* **Ordinamento dei delay (`ordinamento_delay.csv`, Prop. 5.12).**
  `inversioni = 0` in 20/20, `ordinamento_rispettato = 1` in 20/20.
  Osservazione collaterale: `delay_max_s` supera il bordo alto nominale della
  banda `tbt + Dmax` in 39 righe (host × run) su 60 — di poco (23.03 s contro
  22.5 s a `tbt` = 15). E' coerente con la Def. 5.10-5.13: la correzione comune
  `λ·Φ_n` tras­la l'intera banda e non altera l'ordinamento, che infatti resta
  esatto.
* **Fit Prop. 5.18 (`fit_prop518.csv`).** r² lineare 0.959 sull'intera campagna;
  per livello 0.973 (continentale), 0.971 (intercontinentale), 0.985
  (nazionale), 0.993 (regionale). Esponente log-log −0.828 (campagna); per
  livello −0.739, −1.203, −0.695, −0.676, con r² 0.81–0.98.
* **Controprova indipendente del chi-quadro.** `scarto_ricalcolo` fra il χ²
  scritto dall'harness in `summary.txt` e quello ricalcolato dalla pipeline e'
  ≤ 0.0004 in 20/20 run: le due implementazioni concordano.

---

## 9. Risposta alla domanda della tesi

> **Il protocollo si comporta come la tesi prevede? E in quali condizioni?**

**Le proprieta' strutturali reggono senza eccezioni, su tutte e 20 le run.**
Nessun fork persistente; nessun record di peso invalido per il verificatore
interno; nessun nodo senza peso eletto, nemmeno `admin` che ne avrebbe il
permesso (Cor. 5.4); nessuna inversione fra ordine dei pesi e ordine dei delay
(Prop. 5.12); 1544 pesi su 1546 ricalcolabili bit per bit dai soli input
pubblici, e i 2 scarti spiegati da una transazione mai confermata (Sez. 5.11.1);
nessun peso azzerato da una riconciliazione mancata (Prop. 6.2).

**La proprieta' statistica — il Teor. 5.3 — regge solo sopra una soglia di
`target-block-time`.** A 15 s la selezione e' compatibile con la distribuzione
attesa; a 10 s il quadro e' ancora buono ma il test a finestra non e'
applicabile per insufficienza di campione; da 5 s in giu' il chi-quadro rifiuta
in tutte le run, e lo scostamento e' direzionale: **il miner piu' pesante vince
sistematicamente oltre la sua quota**, da +5 punti percentuali a 15 s fino a
+11 a 2 s, a spese di entrambi gli altri.

Questo scostamento **non** e' la deriva legittima del peso descritta nella §1.3
del protocollo di analisi: e' misurato contro `quota_attesa_vigenza`, cioe'
contro il peso davvero leggibile all'altezza di ciascun blocco, che gia'
incorpora ogni crescita virtuosa del peso. E non e' nessuno degli artefatti noti
da escludere: non e' Spacing residuo (le ripetizioni sono in eccesso, non in
difetto); non e' saturazione dello score (i tre delay medi restano separati a
0.57 / 0.76 / 0.89 nella banda); non e' l'offset vdso (che tocca il block time,
non le quote); non e' campione insufficiente (il bias e' una media su 529 righe
per host, con p < 10⁻⁷).

La spiegazione compatibile con i dati e' il **restringimento della banda**
`Dmax = delta·tbt`: il margine fra il primo e il secondo timer scala con `Dmax`
(rapporto costante 0.571 ± 0.044) mentre l'RTT resta fissato dalla geografia.
A 2 s il margine mediano e' 0.55 s e la frazione di round decisi entro 100 ms
quadruplica rispetto a 15 s. Il bias di m1 correla con quella frazione
(ρ = +0.66, p = 0.0015) e non con l'RTT da solo (ρ = −0.09, p = 0.70): conta il
margine assoluto, non la latenza in se'. Nello stesso regime cresce la
persistenza del vincitore, coerente con un vantaggio di chi e' gia' sul tip
quando parte il round successivo.

**In quali condizioni, allora.** Con questa configurazione — `delta` = 0.5,
`wpoa-sortition-lambda` = 0.2, tre miner in rapporto di peso ≈ 0.66/0.19/0.15 —
la wPoA si comporta come previsto per `target-block-time` ≥ 10 s a qualunque
livello geografico fino a 112 ms di RTT. Sotto i 5 s la fedelta' della selezione
si degrada in modo misurabile e sistematico, e il degrado peggiora con la
latenza. La leva indicata dai dati non e' il `tbt` in se' ma il prodotto
`delta·tbt`: una campagna che alzi `delta` al calare del `tbt`, a banda assoluta
costante, e' il primo esperimento da fare per confermare questa lettura — ed e'
esattamente l'esperimento che questa campagna, avendo tenuto `delta` fisso a
0.5, non contiene.

Restano fuori dalla portata di questa campagna, e vanno dichiarati come tali nel
capitolo: i malus, lo smorzamento anti-whale, e il regime intermedio di `rho`.
