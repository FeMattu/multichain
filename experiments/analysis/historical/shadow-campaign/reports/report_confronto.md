# Valutazione sperimentale della wPoA — campagna Shadow a 20 run

Analisi delle tabelle in `analisi/`, prodotte da
`tools/analizza_esperimenti.py --root esperimenti --recompute-chisq` sulle 20 run
Shadow (5 valori di `target-block-time` × 4 livelli geografici). Materiale
destinato al Capitolo 8 della tesi.

**Nota sugli strumenti.** `matplotlib` 3.5.1 e `scipy` 1.8.0 non erano presenti e
sono stati installati in `~/.local` (`pip install --user`); i grafici in
`plots/` sono generati e reali. Tutti i p-value vengono da `scipy.stats`.

**Convenzione.** Ogni affermazione e' marcata **[M]** se misurata direttamente
dalle tabelle, **[I]** se inferita da un ragionamento sui dati.

---

## 1. Sintesi

Le 20 run sono tutte `stato = completa`, con `mining-diversity = 0`,
`dump-function = none`, `δ = 0.5`, `λ = 0.2`, epoca da 12 blocchi, e campione
statisticamente sufficiente (`campione_sufficiente = 1` in 20/20).

| run | tbt | blocchi | dt medio | scarto | χ² | p | G/Δmax | G<100ms | teste | fork |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 15s / regionale | 15 | 107 | 15.90 s | +5.97 % | 2.15 | 0.34 | 0.45 | 3.5 % | 1 | — |
| 15s / nazionale | 15 | 113 | 15.25 s | +1.67 % | 0.50 | 0.78 | 0.51 | 3.3 % | 1 | — |
| 15s / continentale | 15 | 109 | 15.77 s | +5.12 % | 1.73 | 0.42 | 0.60 | 3.4 % | 1 | — |
| 15s / intercontinentale | 15 | 112 | 15.44 s | +2.94 % | 3.54 | 0.17 | 0.57 | 0.8 % | 1 | — |
| 10s / regionale | 10 | 261 | 10.78 s | +7.81 % | **12.63** | 0.0018 | 0.57 | 4.4 % | 1 | — |
| 10s / nazionale | 10 | 265 | 10.65 s | +6.48 % | 2.76 | 0.25 | 0.60 | 3.6 % | 1 | — |
| 10s / continentale | 10 | 260 | 10.81 s | +8.11 % | 0.21 | 0.90 | 0.55 | 2.6 % | 1 | — |
| 10s / intercontinentale | 10 | 263 | 10.70 s | +7.02 % | 5.51 | 0.064 | 0.59 | 3.3 % | 1 | — |
| 5s / regionale | 5 | 318 | 5.69 s | +13.88 % | **22.35** | 1.4e-05 | 0.55 | 5.9 % | 1 | — |
| 5s / nazionale | 5 | 317 | 5.70 s | +13.99 % | **11.31** | 0.0035 | 0.58 | 6.8 % | 1 | — |
| 5s / continentale | 5 | 322 | 5.64 s | +12.77 % | **6.56** | 0.038 | 0.61 | 6.1 % | 2 | propagazione |
| 5s / intercontinentale | 5 | 323 | 5.61 s | +12.17 % | **20.31** | 3.9e-05 | 0.64 | 5.5 % | 1 | — |
| 3s / regionale | 3 | 387 | 3.63 s | +20.90 % | **10.94** | 0.0042 | 0.53 | 9.7 % | 1 | — |
| 3s / nazionale | 3 | 385 | 3.64 s | +21.27 % | **21.19** | 2.5e-05 | 0.59 | 8.5 % | 2 | propagazione |
| 3s / continentale | 3 | 393 | 3.57 s | +19.13 % | **13.52** | 0.0012 | 0.63 | 8.2 % | 2 | propagazione |
| 3s / intercontinentale | 3 | 391 | 3.59 s | +19.49 % | **48.48** | 3e-11 | 0.56 | 7.5 % | 2 | propagazione |
| 2s / regionale | 2 | 458 | 2.60 s | +30.20 % | **24.76** | 4e-06 | 0.62 | 13.8 % | 1 | — |
| 2s / nazionale | 2 | 459 | 2.60 s | +29.91 % | **35.29** | 2e-08 | 0.59 | 13.1 % | 1 | — |
| 2s / continentale | 2 | 451 | 2.65 s | +32.33 % | **16.50** | 2.6e-04 | 0.55 | 12.9 % | 2 | propagazione |
| 2s / intercontinentale | 2 | 455 | 2.63 s | +31.28 % | **50.77** | 9e-12 | 0.55 | 13.3 % | 3 | corsa al tip |

(χ² in grassetto = sopra la soglia 5.991, df = 2. "teste" = best-hash distinti a
fine run.)

**Dove sta il confine.** La selezione pesata regge fino a `tbt = 10 s`
(7 run su 8 compatibili) e **non regge da `tbt = 5 s` in giu'** (0 su 12,
p ≤ 0.04 ovunque). **[M]** La transizione e' governata da `tbt`, non dalla
geografia: a `tbt` fissato i quattro livelli danno esiti mescolati, mentre a
livello fissato l'ordinamento in `tbt` e' netto. **[M]** La *safety* non e' mai
stata compromessa: in tutte e 20 le run l'hash sepolto a −6 blocchi e' unico, e
i sei casi di teste multiple sono differenze di un blocco al tip che si
risolvono da sole. **[M]**

---

## 2. Asse 1 — fra epoche, dentro lo stesso esperimento

Fonti: `epoch_shares.csv`, `weights_trajectory.csv`. Grafici
`plots/01_traiettoria_pesi.png` e `plots/02_quota_per_epoca.png`, che mostrano
`run1-tbt-15s/regionale` (poche epoche lunghe) e `run5-tbt-2s/intercontinentale`
(molte epoche corte).

**I pesi si stabilizzano subito e poi restano fermi.** Nell'epoca 1 tutti i 24
record pubblicati valgono esattamente 1 **[M]**: nessuna attivita' e' ancora
stata osservata, quindi la selezione e' uniforme per costruzione e quell'epoca
va esclusa da ogni media — cosa fatta in tutte le analisi che seguono. Dalla
prima epoca misurata in poi la ripartizione del peso e' notevolmente stabile:
in `run1-tbt-15s/regionale` la quota di peso resta **61 / 30 / 8 %** per
m1 / m2 / m3 lungo tutte e nove le epoche della finestra, con oscillazioni di
±1 punto. **[M]**

Il rapporto `W_tot/w_i`, che governa la saturazione dello score, e' quindi anche
lui stabile: per m3 oscilla fra **10.4 e 13.4** in tutta la run. **[M]** Un
rapporto di quell'ordine porta `score_norm = 1 − exp(−11·E)` a saturare verso 1
per quasi ogni estrazione, ed e' coerente con la posizione in banda misurata
(vedi §5, Def. 5.10–5.13).

**La quota osservata per epoca non converge — ma non e' un segnale.** Lo scarto
medio `|quota_osservata − quota_peso|` per epoca vale 16.2 / 13.4 / 13.9 / 14.2 /
14.6 punti nei cinque quinti della run **[M]**: piatto, non decrescente. La
lettura corretta e' che **un'epoca e' un campione troppo piccolo**: 12 blocchi
divisi fra 3 miner danno una deviazione standard binomiale di ~13 punti sulla
quota, che e' esattamente la grandezza osservata. **[I]** Le quote per epoca
sono quindi rumore attorno al valore giusto, e la domanda sulla proporzionalita'
va posta sull'aggregato, non per epoca.

**Conseguenza metodologica, e un controllo importante.** Poiche' i pesi sono
stabili, usare l'**ultimo** peso pubblicato (come fa `chi2_summary`) o la media
per epoca pesata sui blocchi deve dare lo stesso risultato. Ho rifatto il test
nella seconda forma, escludendo la prima epoca: **7 run su 20 compatibili in
entrambi i modi**, con valori quasi coincidenti (es. 2s/intercontinentale:
50.77 contro 45.23; 5s/nazionale: 11.31 contro 6.05). **[M]** Questo
**esclude la causa n. 3** dell'elenco delle anomalie: lo scostamento dai pesi
osservato nel §4 non e' un artefatto del confronto con un peso non
rappresentativo.

---

## 3. Asse 2 — fra livelli geografici, a `tbt` costante

**La geografia non discrimina, a nessun `tbt`.** E' il risultato piu' netto di
questo asse, ed e' in parte atteso, in parte no.

| tbt | χ² regio / nazio / conti / inter | compatibili | G<100 ms: spread fra livelli |
|---|---|---:|---|
| 15 s | 2.15 / 0.50 / 1.73 / 3.54 | 4/4 | 1.11 pt attorno a 2.75 % |
| 10 s | 12.63 / 2.76 / 0.21 / 5.51 | 3/4 | 0.66 pt attorno a 3.46 % |
| 5 s | 22.35 / 11.31 / 6.56 / 20.31 | 0/4 | 0.48 pt attorno a 6.08 % |
| 3 s | 10.94 / 21.19 / 13.52 / 48.48 | 0/4 | 0.80 pt attorno a 8.50 % |
| 2 s | 24.76 / 35.29 / 16.50 / 50.77 | 0/4 | 0.36 pt attorno a 13.28 % |

A `tbt = 15 s` la mancanza di effetto e' **prevista dal README**: `Δmax = 7.5 s`
e' ~67 volte l'RTT peggiore, e la latenza non puo' spostare l'esito. **[M]**

Ma **anche a `tbt = 2 s` la geografia non discrimina**: la frazione di round con
margine sotto i 100 ms varia di **0.36 punti** fra i quattro livelli mentre
l'RTT varia di **11 volte** (10 → 112 ms). **[M]** Nessuna tendenza monotona in
RTT compare in nessuna riga della tabella.

**Spiegazione, ed e' un limite della campagna, non del protocollo.** Il campo
`jitter` vale 0 su ogni arco di tutti i `.gml`, perche' **Shadow non lo
implementa** (issue `shadow/shadow#3601`, documentato nel README). La geografia
introduce quindi una **latenza deterministica**, non una varianza. La σ che
compare nella Prop. 5.18 e' la deviazione standard del ritardo di propagazione:
nella simulazione essa nasce da contesa su CPU e `packet_loss`, che sono
sostanzialmente identici sui quattro livelli, **non** dall'RTT. **[I]**

Ne segue che **questa campagna non e' in grado di testare la dipendenza da σ
della Prop. 5.18**, e nessun confronto fra livelli lo potra' fare finche' il
jitter non e' modellabile. Non e' un esito negativo del protocollo: e' una
limitazione dello strumento, che va dichiarata nel capitolo invece di essere
letta come "la latenza non conta".

Restano due tracce deboli e coerenti fra loro, entrambe nel verso atteso:
i sei casi di teste multiple si concentrano ai `tbt` bassi e ai livelli piu'
larghi (l'unico caso a 3 teste e' `2s/intercontinentale`) **[M]**; e
l'eccesso del miner pesante (§4) e' massimo sull'intercontinentale a `tbt` 3 e
2 s (+16.7 e +15.0 punti). **[M]** Sono indizi, non prove: con quattro livelli e
una σ che non varia per costruzione non c'e' potenza statistica per separarli
dal rumore.

---

## 4. Asse 3 — fra classi di `tbt`, a livello costante

E' l'asse su cui la campagna ha potere discriminante, e produce i due risultati
quantitativi del capitolo.

### 4.1 Il margine della timer race segue la Prop. 5.18 senza parametri liberi

Il punto 2 della Prop. 5.18 prevede, per `n` candidati uniformemente distribuiti
su una banda di ampiezza `2Δmax`,

```
Pr[G < t] = 1 − (1 − t / (2·Δmax))^n
```

Con `n = 3` e `t = 100 ms` questa e' una **previsione numerica assoluta**: non
c'e' nulla da calibrare. Confronto con la misura (media sui quattro livelli):

| Δmax | previsto | osservato | scarto |
|---:|---:|---:|---:|
| 7.50 s | 1.99 % | 2.75 % | +0.76 pt |
| 5.00 s | 2.97 % | 3.46 % | +0.49 pt |
| 2.50 s | 5.88 % | 6.08 % | +0.20 pt |
| 1.50 s | 9.67 % | 8.50 % | −1.17 pt |
| 1.00 s | 14.26 % | 13.28 % | −0.98 pt |

**[M]** Su un intervallo in cui la grandezza prevista varia di 7 volte, la
previsione e' centrata entro ~1 punto percentuale. Il fit affine
`frazione = a/Δmax + c` da'

```
a = 0.1192   (previsto n·t/2 = 0.1500)      c = 0.0109      R² = 0.959
```

**[M]** Il coefficiente del termine `1/Δmax` e' entro il 21 % del valore
teorico, e compare un **pavimento di ~1.1 punti percentuali** che la teoria non
prevede. Il fit in legge di potenza pura da' esponente **0.772 contro 1.000
atteso** (r = 0.996) **[M]**: la differenza e' interamente attribuibile a quel
pavimento, che gonfia i valori ai Δmax grandi dove il termine principale e'
piccolo.

**Origine del pavimento.** Il modello assume i tre `score_norm` iid uniformi
sulla banda. Non lo sono: m2 e m3 sono compressi nella parte alta (posizione in
banda 73–79 % e 84–93 %, §5), quindi la loro spaziatura reciproca e'
sistematicamente piu' stretta di quella uniforme e produce un eccesso di margini
minuscoli indipendente da Δmax. **[I]** E' precisamente la saturazione dello
`score_norm` descritta nel README, qui **misurata come termine additivo**.

Grafico: `plots/04_margine_prop518.png`.

### 4.2 L'esponente 2/3 non e' verificabile su questi dati

Il punto 3 della Prop. 5.18 prevede
`Pr[inversione] = O((n·σ/Δmax)^{2/3})`. Non esiste in queste tabelle una misura
diretta dell'inversione: servirebbe confrontare, round per round, il vincitore
designato dallo score con quello osservato, cosa che richiede di correlare i
`debug.log` dei tre miner sullo stesso `height` — un dato ricavabile ma **non
presente** nelle tabelle attuali (estensione naturale di
`tools/analizza_esperimenti.py`).

Usando come proxy la distanza totale fra distribuzione osservata e attesa:

* contro `(n·σ/Δmax)` con σ ∝ RTT: esponente **0.206**, r = 0.41 — fit pessimo **[M]**;
* contro il solo `1/Δmax`: esponente **0.481**, r = 0.892 — fit buono **[M]**.

La lettura e' quella del §3: **σ non varia nella campagna**, quindi la forma
`(n·σ/Δmax)^{2/3}` non e' distinguibile da una qualunque `Δmax^{-b}`. Verdetto:
**non testabile con questi dati**, con l'esponente misurato rispetto al solo
Δmax (0.48) riportato per completezza — piu' vicino a 2/3 che a 1, ma con un
proxy che non e' la quantita' della proposizione.

### 4.3 Lo scarto del block time e' un ritardo fisso, non una deriva

Letto in percentuale, lo scarto dal target sembra esplodere: da +4 % a `tbt = 15 s`
fino a +31 % a `tbt = 2 s`. Letto **in secondi** e' un'altra storia:

| tbt | 15 s | 10 s | 5 s | 3 s | 2 s |
|---|---:|---:|---:|---:|---:|
| scarto assoluto medio | 0.589 s | 0.736 s | 0.660 s | 0.606 s | 0.619 s |

**[M]** Lo scarto e' **costante**: 0.642 s di media sulle 20 run (sd 0.13 s), e 0.59–0.74 s
mediando per classe di `tbt`, mentre `tbt` varia di un
fattore 7.5. La crescita percentuale e' solo il rapporto `0.64 / tbt`.

Questo **esclude la retroazione `λΦ`** come causa: un guadagno troppo aggressivo
(Sez. 5.10.4) produrrebbe un'oscillazione che **cambia segno**, mentre qui il
segno e' positivo in 20 run su 20 e la grandezza e' invariante. **[M]** Si
tratta di un costo fisso per blocco — latenza vDSO addebitata da Shadow,
assemblaggio, firma, propagazione e validazione — cioe' l'artefatto di
simulazione gia' previsto nel README, qui **quantificato in 0.64 s per blocco**.
**[I]**

Grafico: `plots/05_block_time.png`.

---

## 5. Verifica dei risultati formali della tesi

| risultato | previsione | dato osservato | verdetto |
|---|---|---|---|
| **Teor. 5.3** — selezione pesata | `Pr[i eletto] = w_i/W` | compatibile in 7/20 run (χ² ≤ 5.991); tutte e 7 hanno `tbt ≥ 10 s`. Stesso esito col peso per epoca | **parzialmente confermato**: vale per `Δmax` ampio, decade sistematicamente al restringersi della banda |
| **Cor. 5.4** — peso nullo | `admin` e `ca` eletti con probabilita' 0 | in 20/20 run i soli proposer sono m1, m2, m3. `admin` e `ca` non compaiono **mai**, su 6 149 blocchi misurati | **confermato** |
| **Def. 5.9 / Cor. 5.8** — pesi smorzati | `g(w)` comprime il vantaggio dei pesi grandi | `dump_function = none` in 20/20 run: il confronto quota-vs-peso usa i pesi **grezzi**, ed e' corretto cosi' | **non testabile**: l'anti-whale non e' stato esercitato |
| **Def. 5.10–5.13** — delay monotono nello score | delay ordinato per peso decrescente | `delay_medio_s` ordinato m1 < m2 < m3 in **20/20 run**, senza eccezioni | **confermato** |
| — posizione in banda | i pesi piccoli saturano verso il tetto | m1 54–62 %, m2 73–79 %, m3 **84–93 %** della banda, in ogni run | **confermato**: la saturazione e' reale e misurata |
| — retroazione `λΦ` | ricentra la media su `T` senza alterare l'ordine | scarto positivo in 20/20 e **costante in secondi** (0.64 s) → non e' `λΦ`. `λΦ` non ha ricentrato la media, ma nemmeno l'ha destabilizzata | **parzialmente confermato**: nessuna oscillazione (l'ordine e' preservato), ma il ricentramento non e' osservabile sotto un offset fisso maggiore |
| **Prop. 5.17** — margine esatto | `E[G] = 1/(W_tot − w_i*)` | `G` e' misurato sui **delay**, non sugli score grezzi: le due grandezze non sono confrontabili senza propagare `Δmax`, `ψ` e la non linearita' di `score_norm` | **non testabile con questi dati**. Il punto qualitativo regge: `G_mediano_su_Dmax` e' stabile (0.45–0.64) perche' il peso residuo e' stabile |
| **Prop. 5.18 pt. 2** — distribuzione del margine | `Pr[G<t] = 1−(1−t/2Δmax)^n` | previsione centrata entro ~1 pt su un intervallo di 7×; fit `a = 0.119` contro 0.150, R² = 0.96 | **confermato**, con un pavimento additivo di 1.1 pt dovuto alla saturazione |
| **Prop. 5.18 pt. 3** — impatto della latenza | `O((n·σ/Δmax)^{2/3})` | σ non varia nella campagna (jitter non implementato da Shadow); il proxy scala come `Δmax^{-0.48}` | **non testabile**: manca la variabile indipendente σ |
| **Cap. 6** — retroazione `ρ_k` | `ρ_k` diverso fra cluster → peso diverso | i tre miner riconciliano quote nettamente diverse e stabili (m1 ≈ 66–67 %, m3 ≈ 7 % del totale riconciliato, in tutte e 5 le classi di `tbt`) | **parzialmente confermato**: `ρ_k` e' differenziato e stabile, ma separare `W_k` da `ρ_k` nel peso pubblicato richiede l'attivita' `τ_i`, non presente nelle tabelle |
| **Cap. 5.11.3 / 7.8** — registro dei malus | il malus riduce il peso effettivo | `malus_events_found = 0` in **20/20** run | **non testabile**: nessun comportamento bizantino e' stato simulato |
| **Sez. 3.3.1** — Spacing | con `d = 0` il vincolo e' inerte | `mining_diversity = 0.0` ovunque; alternanze osservate **sempre > 0** e sempre **sopra** le attese | **confermato**: il vincolo e' inerte |
| **Verifica indipendente** (5.11.1) | ogni nodo ricalcola e conferma i pesi | 20/20 run `verificato = 1`, 60 record controllati, **0 non validi** | **confermato** |

---

## 6. Anomalie

### 6.1 La distribuzione si acuisce invece di appiattirsi

**Il fatto.** Dove la selezione devia dai pesi, **il miner piu' pesante prende
piu' di quanto gli spetti e i due leggeri meno**, e l'eccesso cresce al
restringersi della banda: **[M]**

| tbt | eccesso medio di m1 (punti) | caso peggiore |
|---:|---:|---|
| 15 s | +4.4 | regionale +6.9 |
| 10 s | +3.3 | regionale +7.1 |
| 5 s | +9.4 | intercontinentale +11.8 |
| 3 s | +11.1 | **intercontinentale +16.7** (82.6 % osservato contro 65.9 % atteso) |
| 2 s | +10.5 | intercontinentale +15.0 |

Questo e' il **verso opposto** a quello che ci si aspetterebbe da un rumore che
"confonde" la corsa: il rumore appiattirebbe verso l'uniforme.

**Le cinque cause documentate, verificate una per una:**

1. **offset da vDSO** — riguarda il block time, non la ripartizione dei blocchi.
   Non applicabile. **[M]**
2. **campione insufficiente** — `campione_sufficiente = 1` in 20/20, con
   `min_attesa` sempre ≥ 5. **Escluso.** **[M]**
3. **pesi mobili** — test rifatto per epoca (§2): stesso esito, 7/20.
   **Escluso.** **[M]**
4. **saturazione dello `score_norm`** — presente e misurata (m3 all'84–93 %
   della banda), ma la saturazione **comprime** i delay dei leggeri verso il
   tetto rendendoli piu' simili fra loro: appiattirebbe o al piu' penalizzerebbe
   uniformemente, non produrrebbe questa monotonia. Non spiega il verso.
   **[I]**
5. **Spacing residuo** — la firma sarebbe `consecutivi_osservati = 0`. Qui sono
   sempre **superiori** alle attese. **Escluso, e anzi rovesciato.** **[M]**

**Effetto reale, con una firma indipendente.** Le coppie di blocchi consecutivi
dello stesso proposer superano sistematicamente il valore atteso sotto
indipendenza **calcolata sulle quote osservate** — cioe' c'e' autocorrelazione
oltre a quanto le quote marginali gia' spiegano:

| tbt | osservate | attese | lift | p (binomiale, unilaterale) |
|---:|---:|---:|---:|---:|
| 15 s | 255 | 219.8 | 1.16× | 4.5e-04 |
| 10 s | 676 | 586.4 | 1.15× | 1.0e-08 |
| 5 s | 914 | 773.1 | 1.18× | 1.1e-16 |
| 3 s | 1274 | 970.3 | 1.31× | 1.2e-63 |
| 2 s | 1554 | 1133.5 | 1.37× | 9.7e-106 |
| **tutte** | **4673** | **3683.1** | **1.27×** | **1.8e-157** |

**[M]** Il lift cresce monotonamente al restringersi della banda, esattamente
come l'eccesso del miner pesante.

**Ipotesi meccanica [I].** I due fatti si spiegano con un unico meccanismo: il
proposer uscente ha un vantaggio nel round successivo. Chi ha appena costruito
il blocco riparte dal proprio orologio locale nell'istante in cui lo ha
prodotto, mentre gli altri devono prima riceverlo e validarlo. Il vantaggio vale
una frazione fissa di secondo — dello stesso ordine dei 0.64 s di overhead
misurati al §4.3 — e pesa quindi in proporzione a `1/Δmax`. Il vantaggio si
autoalimenta: chi vince piu' spesso e' piu' spesso uscente, e il miner piu'
pesante vince piu' spesso per costruzione. Questo produce insieme
l'autocorrelazione e l'amplificazione della quota del piu' pesante.

**L'ipotesi non e' dimostrata da questi dati** e ha un test diretto: estrarre da
`debug.log` la matrice di transizione proposer→proposer e verificare che
`Pr(i vince | i ha vinto il round precedente) > Pr(i vince)` per **ogni** miner,
non solo in aggregato. Se il vantaggio e' di incumbency deve valere anche per m3.
Serve una colonna nuova in `tools/analizza_esperimenti.py`.

Se confermato e' un **risultato di protocollo, non di simulatore**: la timer
race ancorata a `parent.nTime` con un costo di propagazione non nullo introduce
una deriva verso il proposer uscente, che la Prop. 5.12 (invarianza
dell'ordinamento) non cattura perche' assume che tutti i candidati partano
simultaneamente.

### 6.2 `run2-tbt-10s/regionale` rompe la monotonia

Con χ² = 12.63 e p = 0.0018 e' l'unica run non compatibile a `tbt ≥ 10 s`, ed e'
il livello a **latenza minima**. **[M]** L'eccesso di m1 e' +7.1 punti, il piu'
alto della sua classe. Non c'e' nulla di anomalo negli altri indicatori
(campione 261 blocchi, nessun fork, verify ok). Coerente con il §6.1, dove
l'effetto e' guidato da `1/Δmax` e non dall'RTT, e con una fluttuazione
campionaria su una singola run. **Non e' un'anomalia separata**; per risolverla
servirebbero repliche con seed diversi a `tbt = 10 s`, che questa campagna non
ha.

---

## 7. Conclusioni

**Dove il protocollo funziona.** Con `Δmax ≥ 5 s` (cioe' `tbt ≥ 10 s` a
`δ = 0.5`) la wPoA fa quello che la tesi dice: i delay sono ordinati per peso in
ogni run, i nodi a peso nullo non vengono mai eletti, i pesi pubblicati sono
ricalcolati e confermati indipendentemente da ogni nodo, e la distribuzione dei
proposer e' compatibile con i pesi in 7 casi su 8. La safety non e' mai stata
violata in nessuna delle 20 run. **[M]**

**Dove degrada.** Sotto `Δmax = 2.5 s` la proporzionalita' si perde in modo
sistematico e monotono. La causa dominante **non e' la latenza di rete** —
la geografia non discrimina a nessun `tbt` — ma la compressione della banda
rispetto a un costo fisso per blocco di **0.64 s**, che erode il margine della
timer race. Il rapporto `Δmax / costo fisso` scende da 11.7 (`tbt = 15 s`) a
7.8 (10 s), 3.9 (5 s), 2.3 (3 s), 1.6 (2 s): **il confine osservato cade fra 7.8
e 3.9**. **[M]**

**Raccomandazione operativa [I].** Dimensionare `Δmax` su almeno **8 volte il
costo fisso per blocco** della rete reale (assemblaggio + firma + propagazione +
validazione), non su un multiplo dell'RTT. Su un deployment reale quel costo va
misurato, non assunto: e' la grandezza che questa campagna indica come vincolante.

Poiche' `Δmax = δ·T` con `δ < 1` (Prop. 5.14, e in pratica `δ ≤ 1 − λM/T`),
**su una catena veloce non e' possibile ottenere un `Δmax` ampio alzando `δ`**:
il vincolo di ammissibilita' del timer lo impedisce. Le due leve rimaste sono
alzare `T` — che e' quello che questi dati raccomandano — oppure attivare
`dumpfunction = sqrt` o `log`, che comprimendo i rapporti fra i pesi riporta i
candidati leggeri fuori dalla zona satura e allarga i margini a parita' di
banda. **Questa seconda leva non e' stata esercitata da nessuna delle 20 run** ed
e' l'esperimento piu' ovvio da fare dopo.

**Cosa questa campagna non ha potuto dire.** Tre meccanismi restano non testati,
e vanno dichiarati come tali nel capitolo: il **registro dei malus** (nessun
nodo bizantino simulato), lo **smorzamento anti-whale** (`dump-function = none`
ovunque), e la **dipendenza da σ della Prop. 5.18** — quest'ultima non per una
svista, ma perche' Shadow non implementa il jitter e i quattro livelli
geografici variano una latenza deterministica anziche' una varianza. Finche'
quel campo non e' modellabile, l'asse geografico misura la sensibilita' del
protocollo alla latenza **media**, non al rumore, e la Prop. 5.18 resta
verificata solo nella sua meta' `Δmax`.

---

## Grafici

| file | cosa mostra |
|---|---|
| `plots/01_traiettoria_pesi.png` | peso pubblicato per epoca, per host, a `tbt` 15 s e 2 s |
| `plots/02_quota_per_epoca.png` | quota osservata (punti) contro quota di peso (linea), per epoca |
| `plots/03_chi2_vs_tbt.png` | χ² contro `tbt`, una linea per livello, con la soglia 5.991 |
| `plots/04_margine_prop518.png` | `Pr[G<100 ms]` contro `1/Δmax` con la curva teorica senza parametri liberi |
| `plots/05_block_time.png` | scarto dal target in secondi (costante) e in percentuale (crescente) |
| `plots/06_eccesso_miner_pesante.png` | eccesso di m1 sulla quota attesa, contro `tbt` |
