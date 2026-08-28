# Prompt di analisi approfondita — campagna Shadow wPoA

> Da incollare in una nuova sessione di Claude Code **dopo** aver eseguito
> `python3 tools/analizza_esperimenti.py --root esperimenti --out analisi --recompute-chisq`.
> Tutto quello che serve per capire lo schema delle tabelle e' descritto qui
> sotto: non serve rileggere lo script di estrazione.

---

## Contesto

Sto scrivendo il **Capitolo 8 ("Experimental Evaluation") della mia tesi**, che
al momento e' vuoto. Gli esperimenti Shadow descritti da queste tabelle sono il
materiale che deve riempirlo. L'analisi non deve quindi limitarsi a descrivere i
numeri: deve **verificare esplicitamente, uno per uno, i risultati formali
enunciati nei Capitoli 5 e 6 della tesi**, dicendo per ciascuno se i dati lo
confermano, lo confermano parzialmente, non sono in grado di testarlo, o lo
contraddicono — e in quest'ultimo caso se per un artefatto del simulatore o per
un effetto reale non previsto dal modello.

Il sistema e' **POESIA / wPoA**: una Weighted Proof-of-Authority implementata
come fork di MultiChain 2.3, in cui la probabilita' di essere eletti proposer e'
proporzionale a un peso `w_i` pubblicato on-chain. Il file `shadow/README.md`
e' la fonte di verita' per la semantica di ogni metrica, il modello di latenza,
i vincoli del simulatore e i limiti noti: **leggilo prima di interpretare
qualunque numero**.

### La rete, identica in tutte le run

10 nodi: `m1 m2 m3` miner e capi cluster; `c1 c2` aziende nel cluster di `m1`,
`c3 c4` in quello di `m2`, `c5` in quello di `m3`; `admin` (Apuana SB) e `ca`
(Certification Authority). `admin` e `ca` **non hanno peso** e sono
strutturalmente ineleggibili.

### Le due variabili indipendenti

* **geografia** — 4 livelli, RTT massimo end-to-end 10 / 22 / 44.7 / 112 ms per
  `regionale` / `nazionale` / `continentale` / `intercontinentale`;
* **`target-block-time`** — 5 valori: 15, 10, 5, 3, 2 s.

20 run = 5 × 4, tutte con `mining-diversity = 0`, `delta = 0.5`,
`wpoa-sortition-lambda = 0.2`, `weight-epoch-length = 12`, `dump-function = none`.

---

## Cosa contiene `analisi/`

Tutti i file sono CSV con intestazione. La chiave di join fra tabelle e'
sempre `run_id` (formato `runN-tbt-Ts/<livello>`); `livello` e `tbt` sono
ripetuti in ogni tabella per comodita'.

| file | granularita' | colonne |
|---|---|---|
| `run_index.csv` | una riga per run | `run_id, run_dir, run_index, livello, tbt_dirname, params_da_host, params_trovato, chain_name, target_block_time, setup_first_blocks, mining_diversity, mining_turnover, weight_epoch_length, weight_kappa, weight_alpha, weight_lambda, wpoa_sortition_delta, wpoa_sortition_lambda, wpoa_randao_lookback, dump_function, enable_wpoa, enable_wpoa_selection, enable_wpoa_sortition, enable_wpoa_malus, enable_weight_engine, minimum_relay_fee, first_block_reward, setupblocks_getinfo, chainname_getinfo, protocolversion, tbt, tbt_params, tbt_mismatch, setup_blocks, setup_mismatch, epoch_len, mining_diversity_val, delta, lambda_sortition, rtt_max_ms, stato, note, malus_events_found, blocchi_misurati, fork_verdetto, path` |
| `block_times.csv` | una riga per run | `run_id, livello, tbt, blocchi_totali, setup_blocks, blocchi_misurati, dt_medio_s, dt_mediana_s, dt_sd_s, dt_min_s, dt_max_s, target_s, scarto_s, scarto_pct` |
| `proposers.csv` | una riga per (run, host con peso) | `run_id, livello, tbt, host, address, blocchi, quota_osservata, peso_ultimo, quota_attesa, delay_campioni, delay_medio_s, delay_min_s, delay_max_s, delay_pos_in_banda` |
| `chisq.csv` | una riga per run | `run_id, livello, tbt, chi2_summary, df_summary, critico_summary, compatibile_summary, verdetto_summary, chi2_ricalcolato, df, critico_5pct, compatibile_ricalcolato, min_attesa, campione_sufficiente, scarto_ricalcolo` |
| `alternanze.csv` | una riga per run | `run_id, livello, tbt, blocchi_misurati, consecutivi_osservati, consecutivi_attesi` |
| `sortition_margins.csv` | una riga per run | `run_id, livello, tbt, rtt_max_ms, banda_dmax_s, round, G_medio_s, G_mediano_s, G_min_s, G_p05_s, round_G_sotto_100ms, frazione_G_sotto_100ms, G_mediano_su_Dmax` |
| `weights_trajectory.csv` | una riga per record pubblicato | `run_id, livello, tbt, host, address, epoca, peso, height` |
| `epoch_shares.csv` | una riga per (run, epoca, host) | `run_id, livello, tbt, epoca, host, address, blocchi_epoca, quota_osservata_epoca, peso_epoca, quota_peso_epoca, W_tot_epoca, rapporto_Wtot_su_wi` |
| `forks.csv` | una riga per run | `run_id, livello, tbt, nodi, teste_distinte, hash_sepolti_distinti, altezza_min, altezza_max, spread_altezze, host_divergenti, verdetto` |
| `gas.csv` | una riga per run | `run_id, livello, tbt, gas_distribuito_init, movimenti_init, gas_rifornito, rifornimenti, gas_riconciliato_totale, epoche_con_riconciliazione, saldo_treasury, riconciliato_m1, riconciliato_m2, riconciliato_m3` |
| `esg.csv` | una riga per (run, host) | `run_id, livello, tbt, host, address, esg, cluster` |
| `verify.csv` | una riga per run | `run_id, livello, tbt, epoca, verificato, record, non_validi, verdetti` |
| `metrics_schema_report.md` | — | schema reale dei file sorgente, e le stranezze note |
| `estrazione.log` | — | log dell'estrazione, run per run |

Note sulle colonne che si prestano a fraintendimenti:

* `quota_attesa` e' `peso_ultimo / somma dei pesi`, cioe' la probabilita' di
  elezione prevista dal **Teor. 5.3** usando l'**ultimo** peso pubblicato.
* `quota_peso_epoca` e' la stessa cosa ma calcolata **epoca per epoca**, con il
  peso in vigore in quell'epoca: e' la versione corretta quando i pesi si
  muovono, e va preferita a `quota_attesa` per l'asse 1.
* `delay_pos_in_banda` e' `(delay medio − (T − Δmax)) / (2·Δmax)`: 0 % = sempre
  il primo a proporre, 100 % = sempre l'ultimo.
* `G_mediano_su_Dmax` normalizza il margine sulla banda, e rende i `tbt`
  confrontabili fra loro (`G` in secondi non lo e').
* `compatibile_summary` = 1 significa `chi-quadro ≤ critico al 5 %`.
* `malus_events_found` = numero di record trovati sul registro dei malus.

---

## Cosa devi produrre

Un report Markdown in **`analisi/report_confronto.md`**, piu' i grafici in
`analisi/plots/`. Il report deve avere queste sezioni.

### 1. Sintesi

Una tabella unica con tutte le run: `run_id`, `tbt`, `livello`, `dt_medio_s` vs
target, esito del chi-quadro, `G_mediano_su_Dmax`, `frazione_G_sotto_100ms`,
`teste_distinte`, `verdetto` dei fork. Deve permettere di vedere a colpo
d'occhio **quali configurazioni funzionano e quali no**. Chiudi con due o tre
frasi che dicano dove sta il confine.

### 2. Asse 1 — fra epoche, dentro lo stesso esperimento

Usa `epoch_shares.csv` e `weights_trajectory.csv`. Per ogni run (o per un
sottoinsieme rappresentativo, dichiarandolo):

* come evolvono i pesi `w_i` per host e il rapporto `W_tot/w_i`;
* se `quota_osservata_epoca` converge verso `quota_peso_epoca` man mano che i
  pesi si stabilizzano, o se se ne allontana;
* **attenzione all'epoca 1**: i pesi partono tutti a 1 (nessuna attivita'
  ancora osservata) e la distribuzione e' per costruzione uniforme. Le prime
  epoche vanno escluse o trattate a parte, non mediate con le altre.

### 3. Asse 2 — fra livelli geografici, a `tbt` costante

Per ciascuno dei 5 valori di `tbt`, confronta i 4 livelli: block time medio e σ
vs target, esito del chi-quadro, quote osservate vs attese, alternanze
osservate vs attese, `teste_distinte`, delay medio per host, `G` mediano e
frazione di round sotto i 100 ms. La domanda e': **a parita' di `tbt`, la
latenza discrimina?** Attesa teorica dal README: a `tbt = 15 s` no
(`Δmax = 7.5 s` e' ~67× l'RTT peggiore), a `tbt` piccolo si'.

### 4. Asse 3 — fra classi di `tbt`, a livello costante

Per ciascuno dei 4 livelli, confronta i 5 `tbt`. E' qui che si vede dove la
timer race smette di girare sullo score e comincia a girare sul rumore.
Confronta l'andamento osservato con la legge di scala della **Prop. 5.18**:

```
Pr[inversione del vincitore] = O( (n·σ / Δmax)^{2/3} )
```

con `n = 3` candidati e `Δmax = δ·T = 0.5·tbt`. Verifica se la degradazione del
chi-quadro (o della frazione di round con `G < 100 ms`) segue l'esponente 2/3
rispetto a `1/Δmax`: fai il fit, riporta l'esponente misurato e di' se e'
compatibile con 2/3. **Questo e' il test quantitativo piu' importante del
capitolo**: e' l'unico punto in cui una previsione numerica della tesi puo'
essere confrontata con un numero misurato.

### 5. Verifica dei risultati formali della tesi

Una tabella con una riga per risultato, nel formato
**risultato teorico → previsione quantitativa → dato osservato → verdetto**,
dove il verdetto e' uno fra *confermato*, *parzialmente confermato*, *non
testabile con questi dati*, *anomalia*. Copri almeno:

| risultato | cosa prevede | dove guardare |
|---|---|---|
| **Teor. 5.3** (selezione pesata) | `Pr[i eletto] = w_i / W` | `chisq.csv`, `proposers.csv`, `epoch_shares.csv` |
| **Cor. 5.4** (peso nullo) | `admin` e `ca` eletti con probabilita' 0 | `proposers.csv`: verifica che **non compaiano mai** come proposer. Se compaiono e' un'anomalia grave, non un dettaglio |
| **Def. 5.9 / Cor. 5.8** (pesi smorzati) | `g(w)` comprime il vantaggio dei pesi grandi | `run_index.csv → dump_function`. Se e' `none` in tutte le run, il confronto quota-vs-peso usa i pesi **grezzi** ed e' corretto cosi': dichiaralo, e segnala che l'anti-whale non e' testato |
| **Def. 5.10–5.13** (score normalizzato, delay, `λΦ`) | il delay e' immagine monotona dello score; `λΦ` ricentra la media su `T` senza alterare l'ordine | `proposers.csv → delay_medio_s` deve essere **ordinato per peso decrescente**; `block_times.csv → scarto_pct`. Se lo scarto oscilla di segno fra run vicine e' un guadagno `λ` troppo aggressivo (Sez. 5.10.4); se e' un offset costante e sempre dello stesso segno e' l'artefatto `vdso` del simulatore |
| **Prop. 5.17** (margine esatto) | `E[score(2) − score(1) | i*] = 1/(W_tot − w_i*)` | `sortition_margins.csv` + `proposers.csv`. Attenzione: `G` e' misurato sui **delay**, non sugli score grezzi, quindi il confronto e' indicativo — dichiaralo. Il punto qualitativo verificabile e': il margine si comprime quando il peso residuo e' alto |
| **Prop. 5.18** (impatto della latenza) | `O((n·σ/Δmax)^{2/3})` | asse 3, sopra |
| **Cap. 6** (retroazione inter-epoca `ρ_k`) | se `ρ_k` cambia molto fra epoche, il peso pubblicato si muove in modo coerente | `gas.csv → riconciliato_m1/m2/m3` (i tre miner riconciliano al 95 / 60 / 20 %) incrociato con `weights_trajectory.csv` |
| **Cap. 5.11.3 / 7.8** (registro dei malus) | quattro tipi di violazione riducono il peso effettivo | `run_index.csv → malus_events_found` |
| **Sez. 3.3.1** (Spacing / `mining-diversity`) | con `d = 0` il vincolo e' inerte | `run_index.csv → mining_diversity_val` incrociato con `alternanze.csv` |
| **Verifica indipendente dei pesi** (5.11.1) | ogni nodo ricalcola e conferma i pesi pubblicati | `verify.csv` |

### 6. Anomalie

Per ogni anomalia, prima di concludere che il protocollo si comporta in modo
imprevisto, **verifica nell'ordine** le spiegazioni gia' documentate nel
README (sezione *Fedelta' e limiti noti*):

1. **offset da `vdso`** — il block time medio e' sistematicamente sopra il
   target per la latenza che Shadow addebita alle chiamate vDSO. E' un
   artefatto del simulatore. Distinguilo da `λΦ` guardando **il segno**: un
   offset costante e sempre positivo e' il simulatore, un'oscillazione che si
   inverte e' la retroazione;
2. **campione insufficiente per il chi-quadro** — servono ≥ 5 blocchi attesi
   per miner; `chisq.csv → campione_sufficiente` e `min_attesa` te lo dicono
   gia'. Un test su un campione insufficiente non e' un risultato;
3. **pesi che cambiano molto fra epoche** — `chi2_summary` usa l'**ultimo**
   peso: se la traiettoria e' mossa, il test e' indicativo e va rifatto per
   epoca con `epoch_shares.csv`;
4. **saturazione dello `score_norm`** — per un candidato con quota di peso
   piccola `W_tot/w_i` e' grande, l'esponenziale satura e il suo delay si
   schiaccia contro il tetto della banda. E' la prima cosa da controllare
   prima di leggere una distribuzione appiattita come "il protocollo non
   funziona": guarda `delay_pos_in_banda` e `rapporto_Wtot_su_wi`;
5. **Spacing residuo** — `consecutivi_osservati = 0` con `consecutivi_attesi`
   ben sopra zero e' la firma di un vincolo di alternanza attivo. Con
   `mining_diversity_val = 0` non dovrebbe accadere: se accade, e' una scoperta.

Solo dopo aver escluso queste cinque, concludi che si tratta di un effetto reale
del protocollo — e in quel caso dillo chiaramente, perche' e' un risultato.

### 7. Conclusioni

In quali condizioni il protocollo funziona bene, dove degrada, e quale
raccomandazione operativa ne deriva per il dimensionamento di `tbt` e `δ` su una
rete reale con una data latenza.

---

## Grafici

In `analisi/plots/`, PNG, solo se aggiungono qualcosa a una tabella:

* traiettoria dei pesi per epoca (una linea per host), per almeno un livello;
* `quota_osservata_epoca` vs `quota_peso_epoca` per epoca, stessa run;
* `chi2` vs `tbt`, una linea per livello (asse y logaritmico) con la soglia 5.991;
* `frazione_G_sotto_100ms` vs `1/Δmax`, con la retta di pendenza 2/3 attesa
  dalla Prop. 5.18 in scala log-log;
* `dt_medio_s − target` vs `tbt`, una linea per livello.

Etichetta sempre gli assi con l'unita' di misura.

---

## Vincoli

* Python 3, `pathlib`, compatibile Windows.
* **`pandas`, `scipy` e `matplotlib` non sono installati** su questa macchina:
  o li installi in un virtualenv locale dichiarandolo nel report, o fai i
  calcoli con la libreria standard e i grafici con SVG scritto a mano. Non
  fingere di aver prodotto grafici che non hai prodotto.
* Sola lettura su `esperimenti/`; scrivi solo dentro `analisi/`.
* Se un dato che ti serve non e' in queste tabelle, **dillo** invece di
  stimarlo: le tabelle si rigenerano estendendo
  `tools/analizza_esperimenti.py`.
* Distingui sempre, nel testo, cosa e' **misurato** da cosa e' **inferito**.
