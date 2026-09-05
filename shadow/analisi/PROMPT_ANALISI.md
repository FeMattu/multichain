# Prompt di analisi — Capitolo 8 della tesi wPoA

> **Come si usa.** Incolla questo file, per intero, all'inizio di una sessione
> nuova di Claude Code (o di un altro agente) aperta su `shadow/`. Basta a se
> stesso: non serve leggere il codice della pipeline, ne' il prompt che l'ha
> generata, ne' la tesi. Tutto quello che serve per interpretare i dati e' qui
> dentro. I dati sono gia' stati estratti: **non rilanciare la pipeline**, a meno
> che `analisi/fogli-di-analisi/run_index.csv` non esista.

---

## 0. Chi sei e cosa devi produrre

Sei l'analista che deve scrivere il **Capitolo 8 ("Experimental Evaluation")**
della tesi sul protocollo **wPoA (Weighted Proof-of-Authority)**, un fork di
MultiChain 2.3 sviluppato nel progetto POESIA. Quel capitolo e' oggi vuoto. Le
tabelle sotto `analisi/` sono il materiale che deve riempirlo.

La domanda a cui rispondi e' una sola, e va risposta con numeri:

> **Il protocollo si comporta come la tesi prevede? E in quali condizioni?**

Produci:

1. `analisi/report_generale.md` — sintetico, poche pagine, la risposta;
2. i report di dettaglio per famiglia di confronto, in `analisi/` (uno per
   famiglia, es. `report_asse_tbt.md`, `report_asse_livello.md`);
3. i grafici in `analisi/plots/`.

La struttura precisa e' nella Sezione 5 di questo documento.

**Vincoli operativi, non negoziabili:**

* **sola lettura** su `esperimenti/`, su `analisi/fogli-di-analisi/` e su
  `analisi/esperimenti/`. Non li rigeneri, non li modifichi, non li cancelli;
* **scrivi solo** `analisi/report_generale.md`, i report di dettaglio in
  `analisi/`, e `analisi/plots/`;
* **[M] / [I]**: ogni numero che citi e' o **misurato** direttamente da un evento
  nativo della catena, o **inferito/ricostruito** dalla pipeline. La Sezione 4
  dice quale e' quale, colonna per colonna. Mantieni la distinzione in ogni
  tabella e in ogni affermazione del report;
* **se un dato manca, dichiaralo**. Mai stimarlo, mai riempirlo con un'euristica
  non dichiarata, mai ometterlo in silenzio;
* **mai un grafico che non hai davvero generato**, mai una tabella copiata due
  volte in due file diversi (rimanda al file di dettaglio).

> **Materiale preesistente.** In `analisi/` possono trovarsi `GUIDA_LETTURA.md` e
> `report_confronto.md`, prodotti da un giro di analisi **precedente** su una
> struttura di cartelle superata. Non sono fonti: se li usi, riverifica ogni
> numero contro le tabelle attuali prima di riportarlo.

---

## 1. Il protocollo, in forma completa

Questa sezione e' il modello formale a cui i dati vanno confrontati. Non e' un
riassunto da integrare altrove: e' tutto quello che serve.

### 1.1 La rete, identica in tutte le run

Dieci nodi:

| nodo | ruolo | peso |
|---|---|---|
| `m1`, `m2`, `m3` | miner, capi cluster | **si'**, e sono gli unici |
| `c1`, `c2` | aziende nel cluster di `m1` | no (contribuiscono al peso di `m1`) |
| `c3`, `c4` | aziende nel cluster di `m2` | no |
| `c5` | azienda nel cluster di `m3` | no |
| `admin` | Apuana SB: genesi, permessi, distribuzione del GAS | **no, per costruzione** |
| `ca` | Certification Authority, ruolo `high1`, certifica gli ESG | **no, per costruzione** |

`admin` e `ca` sono strutturalmente ineleggibili (**Cor. 5.4**). Nota non
banale: `admin` **ha** il permesso di mining sulla catena (compare in
`permissions_mine.json`) e mina i blocchi della fase di setup. Fuori dal setup
non deve mai comparire come proposer, e questo rende il Cor. 5.4 verificabile su
un nodo che *potrebbe* minare e non lo fa perche' non ha peso, non perche' gli
sia vietato.

Quattro livelli geografici, che cambiano **solo la latenza** della topologia
simulata in Shadow: `regionale` (RTT max ~10 ms), `nazionale` (~22 ms),
`continentale` (~45 ms), `intercontinentale` (~112 ms).

### 1.2 La catena del peso, anello per anello

```
score ESG statico (Def. 6.1-6.2)
  ESG_i (azienda), ESG_Mk (miner) - certificati una tantum dalla CA, invariati
  fra epoche salvo ri-certificazione esplicita
        |
        v
attivita' dinamica per epoca (Def. 6.3)
  tau_i^e   contatore di transazioni CONFERMATE dell'azienda i nell'epoca e
  M_k^e     attivita' diretta del miner k nell'epoca e
        |
        v
contributo aziendale pesato (Def. 6.4)
  c_i^e = ESG_i * tau_i^e / kappa            kappa > 0, parametro di rete
        |
        v
peso grezzo del cluster (Def. 6.5)
  W_k^e = ESG_Mk * ( M_k^e + somma_{i in Ck} c_i^e )
        |
        v  allocazione proporzionale (Def. 6.6) - canale GAS, non peso diretto
  Theta^e = somma di TUTTI i tau delle AZIENDE (i tau dei miner non entrano)
  A_k^e   = alpha * Theta^e * W_k^e / W_tot^e       alpha in (0,1)
        |
        v  riconciliazione e saldo residuo (Def. 6.7)
  B_k^0 = 0
  R_k^e in [0, A_k^e + B_k^(e-1)]   GAS trasferiti dal miner k al treasury
                                    nell'epoca e, derivati dai blocchi confermati
  B_k^e = A_k^e + B_k^(e-1) - R_k^e
        |
        v  tasso di conformita' (Def. 6.8)
  rho_k^e = R_k^e / (A_k^e + B_k^(e-1))   in [0,1];  denominatore <= 0 -> rho = 0
        |
        v  IL PESO DEFINITIVO (Def. 6.9), ricorsivo
  w_k^1 = W_k^1                                        epoca 1: nessuna storia
  w_k^e = W_k^e * [ rho_k^(e-1) * lambda_w + (1 - lambda_w) ]      e >= 2
          lambda_w in [0,1)  - intervallo SEMIAPERTO: lambda_w = 1 e' escluso
          per costruzione (Oss. 6.2), perche' e' cio' che garantisce w_k > 0
          quando W_k > 0
        |
        v  w_k^e, scalato di kappa e arrotondato a intero >= 1, e' il valore
           PUBBLICATO sullo stream wpoa-weights (Def. 5.16)
        |
        v  CORREZIONE MALUS (Def. 5.23-5.24)
  M_i^e   = beta * M_i^(e-1) + somma dei punti p(kind) dei record validi in e
            beta in [0,1) persistenza; e' beta < 1 a rendere reversibile
            l'esclusione (Prop. 5.20)
  Psi_i^e = max(0, 1 - M_i^e / M_max)   in [0,1]
  w_dopo_malus = w_k^e * Psi_i^(e-1)    <- il malus si applica al peso ANCORA
            GREZZO, con la Psi dell'epoca PRECEDENTE (evita la circolarita')
        |
        v  SMORZAMENTO ANTI-WHALE (Def. 5.9), DOPO il malus
  peso_efficace = g( w_dopo_malus )
            g_none(w) = w,  g_sqrt(w) = sqrt(w),  g_log(w) = ln(1+w)
        |
        v
  peso_effettivo = peso_efficace   -> entra nello score della sortition
```

**L'ordine e' `w -> w*Psi -> g(w*Psi)`, non `w -> g(w) -> g(w)*Psi`.**
Verificato leggendo il sorgente C++ che ha generato questi dati, non solo la
tesi: `wpoa_selector.cpp:100` chiama `WPoAApplyMalus(weights, height)` su tutta
la mappa dei pesi, e solo dopo `WPoASelector::SelectProposer(..., g_dumping_function)`
applica `ApplyDumping`. Con `g` non lineare i due ordini danno numeri diversi.

**In questa campagna** `dump-function = none` in tutte le run e il registro dei
malus e' vuoto in tutte le run: `peso_pubblicato_epoca`, `peso_dopo_malus`,
`peso_efficace_epoca` e `peso_effettivo_epoca` **coincidono numericamente**. Le
quattro colonne esistono lo stesso, separate, riga per riga: e' un fatto da
mostrare, non da assumere, e la stessa pipeline resta valida il giorno che si
lancia una run con `dumpfunction = sqrt` o con malus attivi.

### 1.3 Il principio guida, non negoziabile

> **Un peso che cresce di epoca in epoca perche' il nodo e' virtuoso — ESG alto,
> cluster attivo, buona riconciliazione — e una quota di elezione che cresce di
> pari passo NON sono un'anomalia: sono la wPoA che fa esattamente quello per cui
> e' stata progettata (Cap. 4.3.2).**

Il tuo compito non e' giudicare "sbagliato" un sistema che premia la
virtuosita' mostrando pesi e quote crescenti. E' verificare che **la catena
causale sia coerente in ogni anello**: peso grezzo coerente con ESG e attivita'
osservate, peso pubblicato coerente con peso grezzo e rho, quota osservata
coerente col peso **in vigore in quella specifica epoca**.

Da qui discende una regola operativa che non ammette eccezioni:

> **Ogni chi-quadro va testato contro il peso in vigore nell'epoca dei blocchi
> contati. Mai contro un peso medio, finale, o dell'ultima pubblicazione.**

Confrontare tutti i blocchi di una run con l'ultimo peso pubblicato confonde una
deriva *legittima* del peso con un errore di selezione. E' il modo piu' rapido di
"scoprire" una violazione che non esiste.

### 1.4 La vigenza: il peso dell'epoca `e` vale nell'epoca `e+1`

Secondo punto cruciale, sbagliato quasi sempre al primo tentativo. Il motore
pubblica il peso di un'epoca **a epoca gia' finita**, dopo il margine di
stabilita' di 6 blocchi (Sez. 6.4). Quindi:

* il record marcato `epoch = e` entra in vigore **dentro l'epoca e+1**;
* una tabella che confronta i blocchi minati nell'epoca `e` col peso *marcato*
  `e` sta confrontando cose che non erano in vigore contemporaneamente.

Le tabelle riportano **entrambe** le versioni, con nomi diversi e inequivocabili:

| colonna | cosa e' | quando usarla |
|---|---|---|
| `quota_peso_epoca` | istantanea "per epoca marcata": quota del peso marcato `e` sul totale dei pesi marcati `e` | per descrivere la **traiettoria del peso**; **mai** per confrontare con le quote osservate |
| `quota_attesa_vigenza` | per ogni blocco dell'epoca, la quota calcolata sulla mappa dei pesi **davvero leggibile a quell'altezza** (solo i record confermati prima del blocco), poi mediata sui blocchi | e' la **sola** attesa legittima da confrontare con `quota_osservata_epoca` |

`scostamento_quota = quota_osservata_epoca - quota_attesa_vigenza`. E' lui la
misura dell'errore di selezione; la differenza rispetto a `quota_peso_epoca` non
lo e'.

### 1.5 I risultati formali da verificare esplicitamente

Questa tabella va riprodotta **per intero** in `report_generale.md`, con una
colonna "esito" riempita dai dati.

| risultato | cosa prevede esattamente | dove si verifica |
|---|---|---|
| **Teor. 5.3** | `Pr[i eletto al round n+1] = w_i^n / W^n` | `peso_riconciliazione.csv`: `quota_osservata_epoca` vs `quota_attesa_vigenza`, `chi2_finestra`; e `validazione_sortition.csv` per l'algoritmo isolato |
| **Cor. 5.4** | un candidato a peso effettivo nullo e' eletto con probabilita' 0, purche' resti almeno un candidato a peso positivo | `proposers.csv` (`admin`/`ca` non devono comparire); `validazione_sortition.csv`, colonne `candidati_peso_nullo` / `selezioni_candidati_nulli` / `cor_5_4_rispettato`; `errori_integrita.csv` tipo `altro` |
| **Lemma 6.1 / Prop. 6.2** | `W_k^e = 0 <=> M_k^e = 0 e tau_i^e = 0 per ogni i in Ck`; se `ESG_Mk > 0` e `lambda_w in [0,1)` allora `w_k^e = 0 <=> W_k^e = 0` — **mai** per la sola riconciliazione mancata | `peso_riconciliazione.csv`: cerca righe con `rho_epoca = 0` e verifica che `peso_pubblicato_epoca > 0` |
| **Def. 5.9 / Cor. 5.8** | `g(w)` comprime il vantaggio dei pesi grandi (anti-whale) | `run_index.csv` colonna `dump_function`. In questa campagna e' `none` ovunque: **il meccanismo non e' esercitato**, dichiaralo come limite |
| **Def. 5.10-5.13, Prop. 5.12** | il delay e' funzione monotona crescente dello score normalizzato; `lambda*Phi_n` e' comune a tutti i candidati del round e non altera l'ordinamento | `ordinamento_delay.csv`: `inversioni` deve essere 0 in ogni run |
| **Prop. 5.17** | `E[score(2) - score(1) | vincitore i*] = 1 / (W_tot - w_i*)`, esponenziale esatta — dipende dal peso RESIDUO, non da quello del vincitore | `sortition_margins.csv` (`G_medio_s`), incrociato coi pesi di `weights_trajectory.csv` |
| **Prop. 5.18** | `Pr[G < t] = 1 - (1 - t/(2*Dmax))^n` esatta; `Pr[inversione] = O((n*sigma/Dmax)^(2/3))` approssimata | `sortition_margins.csv` + `fit_prop518.csv` |
| **Cap. 6.4** | `rho_k` e' l'**unico** canale attraverso cui il comportamento di un'epoca si ripercuote sul peso della successiva | `correlazioni.csv`, colonne `spearman_rho_vs_peso_successivo` |
| **Def. 5.17-5.24** | quattro tipi di violazione (Equiv, Delay, SelfWrite, BadWeight) riducono il peso effettivo con decadimento esponenziale reversibile (Prop. 5.20) | `malus.json` e' vuoto in **tutte** le run: `run_index.csv` colonna `malus_events_found` = 0 ovunque. **Limite dichiarato**, non omettere |
| **Sez. 3.3.1** | con `mining-diversity = 0` lo Spacing nativo di MultiChain e' inerte (`ceil(0) = 0`) | `run_index.csv` colonna `mining_diversity`, incrociata con `alternanze.csv` |
| **Sez. 5.11.1** | ogni peso pubblicato dev'essere ricalcolabile bit per bit dai soli input pubblici della sua epoca | `peso_riconciliazione.csv`: `peso_pubblicato_epoca` vs `peso_pubblicato_ricalcolato`, `esito_ricalcolo`; incrociato con `verify.csv` |

---

## 2. La campagna: cosa contiene, davvero

20 run: 5 valori di `target-block-time` (15, 10, 5, 3, 2 s) x 4 livelli
geografici, stesso seed di configurazione. Parametri identici ovunque salvo il
`tbt` e la latenza:

`weight-epoch-length = 12`, `weight-kappa = 100`, `weight-alpha = 0.2`,
`weight-lambda (lambda_w) = 0.5`, `wpoa-sortition-delta (delta) = 0.5`,
`wpoa-sortition-lambda = 0.2`, `wpoa-randao-lookback = 1`,
`dump-function = none`, `mining-diversity = 0.0`, `mining-turnover = 0.5`,
`setup-first-blocks = 60`, `wpoa-malus-mu (beta) = 0.5`, `wpoa-malus-max = 4`.
Tutte le fasi wPoA sono attive (`enable-wpoa*` e `enable-weight-engine` a `true`).
Verificali comunque in `run_index.csv`: e' li' che vive il valore sigillato in
`params.dat`, non nel nome della cartella.

**Attenzione a due parametri che si somigliano e non c'entrano nulla l'uno con
l'altro**: `weight-lambda` (colonna `weight_lambda`) e' il `lambda_w` della
retroazione del PESO, Def. 6.9; `wpoa-sortition-lambda` (colonna
`wpoa_sortition_lambda`) e' il guadagno della retroazione del DELAY, che
ricentra il block time medio sul target. Confonderli fa dire sciocchezze.

**Unita' monetarie.** Ogni colonna monetaria di ogni tabella e' in **GAS**, cioe'
nell'unita' di visualizzazione della valuta nativa. Le RPC di MultiChain
restituiscono gia' l'unita' di visualizzazione, quindi i CSV dell'harness sono
gia' GAS; a essere in unita' grezze sono i soli parametri di `params.dat`
(`first-block-reward`, `initial-block-reward`, `minimum-relay-fee`), che la
pipeline converte dividendo per `native_currency_multiple` (= 100 000 000,
riportato con la sua fonte in `run_index.csv`). Non riconvertire nulla.

**Il generatore di traffico e' ESOGENO.** Determinato leggendo l'harness
(`tools/role_company.sh`, fase `traffic`): un ciclo che pubblica un item e poi
dorme un intervallo fisso per azienda, senza mai leggere chi ha vinto il blocco,
il proprio saldo o il peso pubblicato. Anche la riconciliazione dei miner e' a
tasso fisso per miner. **Conseguenza:** non esiste un anello di retroazione dal
risultato delle elezioni al traffico. Il canale selezione -> fee incassate ->
riconciliazione -> `rho` -> peso dell'epoca successiva esiste ed e' misurabile;
un ciclo che passasse per `tau` invece non puo' esistere, e se lo "trovi" nei
dati hai trovato una correlazione spuria.

---

## 3. Dove sono i dati

```
analisi/
  fogli-di-analisi/         tabelle globali: una riga per run o per run x dimensione
  esperimenti/<run>/<livello>/    dettaglio per esperimento
  esperimenti/<run>/file-analisi-dati-di-tutti-gli-esp-in-area/
                            confronto fra le quattro aree della stessa run
  plots/                    <- ci scrivi tu
  report_generale.md        <- lo scrivi tu
```

`<run>` e' una fra `run1-tbt-15s`, `run2-tbt-10s`, `run3-tbt-5s`,
`run4-tbt-3s`, `run5-tbt-2s`; `<livello>` una fra `regionale`, `nazionale`,
`continentale`, `intercontinentale`.

I dati grezzi stanno sotto `esperimenti/<run>/<livello>/run/metrics/` e
`.../run/data/`: **sola lettura**, e in linea di principio non ti servono — se
ti servono, e' perche' hai trovato qualcosa che le tabelle non spiegano, e in
quel caso dillo nel report.

---

## 4. Schema di ogni tabella

Legenda della colonna "fonte": **[M]** misurato da un evento nativo della
catena; **[I]** inferito o ricostruito dalla pipeline.

### 4.1 `fogli-di-analisi/` — le tabelle globali

#### `run_index.csv` — una riga per run. **Leggila per prima, sempre.**

Parametri sigillati in `params.dat` (tutti **[M]**): `chain_name`,
`target_block_time`, `setup_first_blocks`, `mining_diversity`,
`mining_turnover`, `weight_epoch_length`, `weight_kappa`, `weight_alpha`,
`weight_lambda`, `wpoa_sortition_delta`, `wpoa_sortition_lambda`,
`wpoa_randao_lookback`, `dump_function`, `enable_wpoa*`, `enable_weight_engine`,
`minimum_relay_fee`, `first_block_reward`, `initial_block_reward`,
`native_currency_multiple`, `weight_treasury_address`, `wpoa_malus_mu`,
`wpoa_malus_max`, `wpoa_malus_*_points`.

Controlli e sintesi:

| colonna | significato | fonte |
|---|---|---|
| `tbt_mismatch` | 1 se il `tbt` del nome cartella non coincide con `params.dat`. **1 invalida ogni confronto per tbt su quella run** | [I] |
| `setup_mismatch` | 1 se `setup-first-blocks` non coincide con `setupblocks` di `getinfo` | [I] |
| `stato` | `completa` / `parziale` / `incompleta` / `errore` | [I] |
| `note` | perche' non e' `completa` | [I] |
| `malus_events_found` | record sul registro dei malus | [M] |
| `blocchi_misurati` | blocchi oltre la fase di setup | [M] |
| `fork_verdetto` | vedi `forks.csv` | [I] |
| `righe_peso_riconciliazione`, `scarti_ricalcolo_peso` | righe prodotte e pesi non riprodotti dal ricalcolo | [I] |
| `righe_account_ledger`, `premi_mining_ricostruiti` | dimensione del registro dei conti | [I] |
| `errori_H`, `errori_P`, `errori_I` | righe di `errori_integrita.csv` per severita' | [I] |
| `fonte_conversione_gas` | da dove viene `native_currency_multiple` | [I] |
| `rtt_max_ms` | RTT massimo end-to-end del livello | [I] |

#### `block_times.csv` — una riga per run
`blocchi_totali`, `setup_blocks`, `blocchi_misurati`, `dt_medio_s`,
`dt_mediana_s`, `dt_sd_s`, `dt_min_s`, `dt_max_s`, `target_s`, `scarto_s`,
`scarto_pct`. I `dt` sono differenze fra i timestamp dei blocchi **[M]**; lo
scarto e' rispetto al `target-block-time`.

#### `proposers.csv` — una riga per (run, host con peso)
`blocchi` **[M]**, `quota_osservata` **[M]**, `peso_ultimo` **[M]**,
`quota_attesa` **[I]** (calcolata sull'**ultimo** peso: e' l'approssimazione
grossolana, vedi `chisq.csv`), `delay_campioni` / `delay_medio_s` /
`delay_min_s` / `delay_max_s` **[M]**, letti dalle righe `wPoA-sortition ...
delay=...s` dei `debug.log`, `delay_pos_in_banda` **[I]** (posizione del delay
medio dentro la banda `[tbt-Dmax, tbt+Dmax]`, 0 = bordo basso, 1 = bordo alto).

#### `chisq.csv` — chi-quadro di sintesi sull'intera run
Contro l'**ultimo** peso pubblicato. `chi2_summary` e' quello scritto
dall'harness in `summary.txt`; `chi2_ricalcolato` la controprova indipendente
della pipeline; `scarto_ricalcolo` la loro differenza; `p_value` il valore da
scipy. `min_attesa`, `campione_sufficiente` (1 sse attesa >= 5 in ogni classe).

> **Questo chi-quadro non va MAI presentato da solo.** Confronta blocchi di tutta
> la run con un peso che nella run e' cambiato: e' un indicatore di sintesi, e
> confonde deriva legittima del peso ed errore di selezione. Presentalo sempre
> accanto a `chi2_finestra` di `peso_riconciliazione.csv`.

#### `alternanze.csv`
`consecutivi_osservati` **[M]** (quante volte lo stesso miner ha proposto due
blocchi di fila) contro `consecutivi_attesi` **[I]** = `somma(p_i^2) * (n-1)`
sulle quote osservate. Se osservati << attesi, c'e' uno Spacing residuo che
impedisce le ripetizioni. Incrocialo con `mining_diversity` e con il numero di
indirizzi che hanno il permesso `mine`: lo spacing nativo vale
`min(floor(N*d) + 1, N)` ed e' inerte solo quando risulta 1. Con spacing >= 2 e
osservati == 0 la regola e' tornata vincolante (regressione del gate di
`IsBarredByDiversity`); con spacing 1 la run non discrimina, perche' la regola
sarebbe inerte comunque.

#### `sortition_margins.csv` — la corsa dei timer
`rtt_max_ms` **[I]**, `banda_dmax_s` = `delta * tbt` **[I]**, `round` **[M]**,
e le statistiche del margine `G` = differenza fra il secondo e il primo delay
piu' piccolo dello stesso round **[M]**: `G_medio_s`, `G_mediano_s`, `G_min_s`,
`G_p05_s`, `round_G_sotto_100ms`, `frazione_G_sotto_100ms`,
`G_mediano_su_Dmax`.

**Come si legge:** se `G` e' molto piu' grande dell'RTT del livello, il vincitore
ha tempo di propagare prima che il secondo agisca e non ci sono corse; quando
`G` scende sotto l'RTT, il fork diventa possibile. `frazione_G_sotto_100ms` e' la
misura sintetica del rischio.

#### `weights_trajectory.csv` — un record per pubblicazione su `wpoa-weights`
`host`, `address`, `epoca`, `peso`, `height` — tutto **[M]**, letto dallo stream.
`height` e' l'altezza che il publisher aveva in mano quando ha costruito il
record, **non** quella di conferma.

#### `epoch_shares.csv` — vista "per epoca marcata"
`blocchi_epoca`, `quota_osservata_epoca` **[M]**, `peso_epoca`,
`quota_peso_epoca`, `W_tot_epoca`, `rapporto_Wtot_su_wi` **[I]**.
**Non usarla per l'attesa:** e' la versione per epoca marcata, non per vigenza.
Serve a descrivere la traiettoria. L'attesa corretta e' in
`peso_riconciliazione.csv`.

#### `forks.csv`
`nodi`, `teste_distinte`, `hash_sepolti_distinti` (a 6 blocchi di profondita'),
`altezza_min`/`max`, `spread_altezze`, `host_divergenti`, `verdetto` in ordine di
gravita': `nessun fork` < `ritardo di propagazione` < `corsa al tip` <
`fork persistente`. **Un fork persistente invalida tutte le analisi successive
su quella run**: la sequenza dei proposer non e' piu' unica.

#### `gas.csv` — tutti gli importi in GAS
`gas_distribuito_init`, `movimenti_init`, `gas_rifornito`, `rifornimenti`,
`gas_riconciliato_totale`, `epoche_con_riconciliazione`, `saldo_treasury`,
`riconciliato_m1/m2/m3`. Tutto **[M]**.

#### `esg.csv`
`host`, `address`, `esg`, `cluster` — **[M]**, dalla certificazione della CA.

#### `verify.csv` — esito di `weightverifyweights`
`epoca`, `verificato`, `record`, `non_validi`, `verdetti`. E' il **verificatore
interno del nodo** (`weight_verifier.h`) che ricalcola i pesi dai blocchi veri:
la fonte piu' autorevole sulla ricalcolabilita'. **[M]**.

#### `disuguaglianza_pesi.csv` — aggregato di tutte le run
Vedi §4.3: stesso schema del file per-esperimento.

#### `correlazioni.csv` — Sez. 4.9.1, una riga per (run, host con peso)

| colonna | cosa correla | perche' |
|---|---|---|
| `spearman_fee_vs_rho`, `p_fee_vs_rho` | fee incassate nell'epoca vs `rho_epoca` | il canale **economico**: chi vince piu' blocchi incassa piu' fee e ha piu' GAS da riconciliare. Le fee sono l'unica entrata *guadagnata* |
| `spearman_entrate_vs_rho` | **tutte** le entrate (fee + rifornimenti dell'admin) vs `rho` | riportato a parte perche' i rifornimenti sono un trasferimento, non un guadagno: confonderli col canale economico e' l'errore da evitare |
| `spearman_rho_vs_peso_successivo` | `rho_epoca(e)` vs `peso_pubblicato_epoca(e+1)` | il canale **formale**, vero per costruzione dalla Def. 6.9. Va riportato lo stesso: e' la verifica diretta che la formula implementata sia quella dichiarata |

`p_*` viene da `scipy.stats.spearmanr`; vuoto significa che il campione non lo
consentiva (serie costante o meno di 3 punti), non che sia zero.

> **Non correlare blocchi minati con peso.** E' l'implicazione inversa, gia'
> garantita dal Teor. 5.3: un coefficiente alto li' non dimostrerebbe nulla.

#### `ordinamento_delay.csv` — Sez. 4.9.2, Prop. 5.12
`ordine_per_peso_decrescente` e `delay_nello_stesso_ordine` mostrano affiancate
le due sequenze; `inversioni` le conta; `ordinamento_rispettato` e' 1 sse zero.
**Deve essere zero ovunque.** Se non lo e' e' un'anomalia seria, non un dettaglio
statistico: la correzione globale `lambda*Phi_n` e' comune a tutti i candidati
del round e non puo' spiegarla.

*Limite del test, da dichiarare quando lo citi:* il confronto usa il **delay
medio** su tutta la run contro il **peso finale** (`peso_ultimo` di
`proposers.csv`), non il peso in vigore round per round. Regge su questa
campagna perche' l'ordine relativo dei tre miner non si inverte mai lungo la
run — verificalo su `weights_trajectory.csv` prima di darlo per scontato — ma
non sarebbe un test valido su una campagna in cui i ranghi si scambiano.

#### `fit_prop518.csv` — Sez. 4.9.3
Una riga per gruppo (`tutta la campagna` e un gruppo per livello).
`lin_pendenza` / `lin_intercetta` / `lin_r2`: fit di
`frazione_G_sotto_100ms` contro `1/Dmax`. `log_esponente` / `log_r2`: fit di
`ln(frazione)` contro `ln(Dmax)` — la pendenza e' l'esponente empirico, che il
modello vuole vicino a `-1` (`esponente_atteso`).

#### `famiglie_confronto.csv` — Sez. 4.9.5
Le famiglie di run che differiscono per **esattamente un** parametro, costruite
automaticamente dall'indice: `parametro_variato`, `valori`, `n_run`, `run_id`
(i membri), `costanti` (tutto cio' che non cambia). Gli "assi" classici della
campagna sono i due casi particolari che ne escono: `parametro_variato =
target_block_time` (a livello costante) e `parametro_variato = livello` (a tbt
costante). **Usa questo file per decidere di quali confronti scrivere**, invece
di deciderlo a priori.

#### `validazione_sortition.csv` — Sez. 4.8, Monte Carlo
Prodotto da `tools/valida_sortition_montecarlo.py`, che **non legge le run
Shadow** (salvo prendere in prestito i rapporti di peso di un'epoca reale per
uno scenario) e reimplementa in Python la trasformazione di score
Efraimidis-Spirakis del selettore: `u = (d+1)/2^64`, `E = -ln(u)`,
`score = E / g(w)`, vince l'argmin.

`scenario`, `pesi`, `dump_function`, `n_estrazioni`, `seed`, `chi2`, `df`,
`critico_5pct`, `compatibile`, `attesa_minima`, `campione_sufficiente`,
`candidati_peso_nullo`, `selezioni_candidati_nulli`, `cor_5_4_rispettato`,
`quote_osservate`, `quote_attese`, `nota`.

> **Cosa dimostra e cosa no.** Dimostra che la **formula** e' corretta, con il
> campione grande che le run Shadow non possono avere. **Non** dimostra che il
> binario C++ compilato la implementi cosi': quello resta lavoro futuro
> (esporre `ComputeScore` a un harness dedicato). Dichiaralo nel report ogni
> volta che lo citi.

#### `metrics_schema_report.md`
Lo schema reale di `metrics/` per ogni run, le sorprese trovate (file senza
header, colonne dal nome variabile, artefatti `*:Zone.Identifier` di WSL), la
tabella della conversione GAS run per run con la sua fonte, e la determinazione
esogena del generatore di traffico. **Leggilo prima di dubitare di un numero.**

#### `estrazione.log`
Ogni run processata, ogni file letto, ogni warning, ogni campo mancante, e in
testa la riga `pandas=... scipy=...` che dice quali dipendenze erano attive.

### 4.2 `esperimenti/<run>/<livello>/peso_riconciliazione.csv` — **la tabella centrale**

Una riga per (epoca, host con peso), con tutta la catena della §1.2 sulla stessa
riga. E' qui che si risponde alla domanda della tesi.

| gruppo | colonne | fonte |
|---|---|---|
| identita' | `run_id`, `livello`, `tbt`, `epoca`, `host`, `indirizzo` | [M] |
| ESG | `esg_miner`, `esg_cluster_medio`, `esg_cluster_lista` (`"c1:42.1,c2:57.3"`) | [M] |
| attivita' | `attivita_miner_tau` (`M_k^e`), `attivita_cluster_tau_somma`, `attivita_cluster_tau_lista`, `theta_epoca` (`Theta^e`) | [I] (conteggio per epoca di conferma) |
| contributi | `contributi_c_i_lista` (`c_i^e` gia' calcolati, `"c1:12.3,c2:8.9"`) | [I] |
| peso grezzo | `peso_grezzo_epoca` (`W_k^e`) | [I] |
| GAS | `allocazione_A_k`, `saldo_B_precedente`, `saldo_B_epoca`, `riconciliato_R_k` | [I] da [M] |
| conformita' | `rho_epoca` (`rho_k^e`), `rho_epoca_precedente` (`rho_k^(e-1)`, **quella che entra davvero in `w_k^e`**) | [I] |
| peso pubblicato | `peso_pubblicato_epoca` (`w_k^e` letto dallo stream) | **[M]** |
| ricalcolo | `peso_pubblicato_ricalcolato`, `scarto_ricalcolo`, `esito_ricalcolo` (`esatto` / `scostamento` / `non pubblicato in questa epoca`), `height_pubblicazione` | [I] |
| malus | `malus_accumulatore_epoca` (`M_i^e`), `fattore_correzione_malus` (`Psi_i^(e-1)`), `peso_dopo_malus` | [I] |
| smorzamento | `dump_function_usata`, `peso_efficace_epoca` (`g(peso_dopo_malus)`), `peso_effettivo_epoca` | [I] |
| quote | `W_tot_epoca`, `quota_peso_epoca`, `quota_attesa_vigenza`, `blocchi_minati_epoca`, `blocchi_totali_epoca`, `quota_osservata_epoca`, `scostamento_quota` | [M] i conteggi, [I] le quote |
| chi-quadro per epoca | `chi2_epoca`, `df_epoca`, `chi2_critico_5pct`, `compatibile_epoca`, `attesa_minima_epoca`, `campione_sufficiente_epoca` | [I] |
| chi-quadro a finestra | `finestra_epoche` (5), `blocchi_finestra`, `chi2_finestra`, `df_finestra`, `compatibile_finestra`, `attesa_minima_finestra`, `campione_sufficiente_finestra` | [I] |

**Tre chi-quadro concettualmente distinti — e' la confusione piu' comune:**

1. **algoritmo puro** — `validazione_sortition.csv`: isola la trasformazione
   statistica dal rumore di rete, campione grande a piacere;
2. **rete simulata, per epoca** — `chi2_epoca`: con `weight-epoch-length = 12` e
   tre miner a quote sbilanciate `campione_sufficiente_epoca` **e' quasi sempre
   0**. Non e' un bug, e' aritmetica: servirebbe attesa >= 5 per classe.
   Riportalo, ma non concludere mai da solo su un'epoca;
3. **rete simulata, a finestra scorrevole** di 5 epoche — `chi2_finestra`: il
   compromesso dichiarato, l'unico con campione utilizzabile su questa campagna.

Da qui esce una **raccomandazione metodologica** che va nel report: per rendere
il test per epoca conclusivo servono epoche piu' lunghe o run piu' lunghe, in
modo che l'attesa minima per classe superi 5.

### 4.3 Le altre tabelle per esperimento

#### `account_ledger.csv` — bilancio GAS per nodo
Una riga per movimento, per **ogni** nodo, `admin` e `ca` inclusi (movimentano
GAS pur senza peso). Ordinato per nodo e altezza crescente.

`height`, `epoca`, `nodo`, `indirizzo`, `tipo_movimento`, `importo_gas` (col
segno: `+` se il nodo riceve), `controparte`, `motivo`, `saldo_gas_dopo`,
`txid_o_riferimento`, `coerente_con_saldo`.

| `tipo_movimento` | fonte | nota |
|---|---|---|
| `init`, `refill` | **[M]** l'importo, **[I]** l'altezza | `gas_transfers.csv` porta l'altezza di **invio**, non di conferma: non c'e' txid |
| `reconcile` | **[M]** | e' la `R_k` dell'epoca; l'altezza e' modellata come invio+1 |
| `mining_reward` | **[I]** | ricostruito da `blocks.json` x il premio di catena di `params.dat`, convertito in GAS. In questa campagna `initial-block-reward = 0`: l'unica riga e' il premine del blocco 1 all'`admin` |
| `fee` | **[I]** | il **residuo** fra due saldi misurati consecutivi una volta tolti i movimenti noti. Nessuna metrica registra la fee di una singola transazione (dipende dai byte, non dal solo `minimum-relay-fee`): la fee e' attribuibile all'intervallo, non alla transazione, ed e' cosi' che viene riportata. Segno negativo = pagata (azienda che pubblica), positivo = incassata (miner che include il blocco) |

Il residuo **chiude il registro per costruzione**: `saldo_gas_dopo` coincide con
ogni saldo misurato, e l'ultima riga lo riporta sul saldo di fine run di
`node_state.csv`. Due avvertenze:

* per l'`admin` il residuo finale e' particolarmente grosso perche' l'`admin`
  importa il treasury come indirizzo **watch-only**: quel residuo conflagra fee
  e GAS riconciliato al treasury. Non leggerlo come "fee incassate dall'admin";
* `coerente_con_saldo = 0` significa che il registro **ricostruito** e' andato
  sotto zero. Prima di chiamarla anomalia leggi `errori_integrita.csv`, che la
  classifica gia'.

#### `gas_transfers.csv`
`height`, `height_conferma`, `epoca`, `tipo` (`init`/`refill`/`reconcile`),
`nodo_mittente`, `indirizzo_mittente`, `nodo_destinatario`,
`indirizzo_destinatario`, `importo_gas`, `saldo_mittente_prima`,
`saldo_mittente_dopo`, `fonte_saldo_mittente`, `saldo_destinatario_dopo`,
`fonte_saldo_destinatario`, `note`. Le colonne `fonte_*` dicono riga per riga se
il saldo e' misurato, calcolato o non disponibile: leggile.

#### `esg_publish.csv`
`height_conferma`, `epoca`, `nodo_certificato`, `indirizzo_certificato`,
`esg_score`, `publisher`, `publisher_indirizzo`, `txid`. Lo stream ESG e'
**chiuso**: scrive solo la CA delegata.

#### `membership_events.csv`
`height_conferma`, `epoca`, `azienda`, `indirizzo`, `miner_cluster`,
`miner_indirizzo`, `evento` (`adesione` / `auto-adesione del miner`), `txid`.
I record sono **auto-attestati**: il lettore li accetta solo perche' il
firmatario coincide con `node_address`, quindi nessuno puo' dichiarare
l'appartenenza altrui.

#### `traffic_events.csv` — la fonte diretta di `tau_i`
`height_invio`, `height_conferma`, `epoca`, `nodo_publisher`, `indirizzo`,
`miner_cluster`, `seq`, `esito` (`ok` / `errore` / `non_confermata`),
`dettaglio_errore`, `txid`.

`epoca` e' quella dell'altezza di **conferma**, non di invio: usare l'invio
sbaglierebbe sistematicamente al confine fra epoche, ed e' proprio li' che il
motore dei pesi cambia risultato.

> `tau_i` **non e' solo traffico**: comprende anche il record di adesione
> dell'azienda, che e' una transazione confermata come le altre. La pipeline lo
> verifica riga per riga e lo dichiara come riga `[I]` in
> `errori_integrita.csv`.

#### `tabellone_eventi.csv` — vista di comodo
Denormalizzata: `height`, `epoca`, `categoria_evento`, `nodo_mittente`,
`nodo_destinatario`, `importo`, `unita`, `note`. Comoda per filtrare su un
singolo host; **le tabelle separate restano la fonte di verita'**.

#### `errori_integrita.csv` — la tabella unica dei controlli
`height`, `epoca`, `host`, `tipo_controllo`, `severita`, `descrizione`,
`valore_atteso`, `valore_osservato`, `riferimento_riga_sorgente`.

`tipo_controllo` in: `saldo_negativo`, `peso_non_ricalcolabile`,
`tau_incoerente`, `autorizzazione_spesa_mancante`, `altro`.

| severita' | significato | cosa farne |
|---|---|---|
| **[H]** hard | il dato e' certamente sbagliato e invalida ogni lettura che vi si appoggi | **in cima a `report_generale.md`, prima di tutto il resto** |
| **[P]** probabile | lo scostamento esiste, ma un artefatto noto e **dichiarato nella riga stessa** lo spiega senza chiamare in causa il protocollo | riportalo con la sua spiegazione, non come scoperta |
| **[I]** informativo | nessun errore: un limite della campagna da non perdere di vista | va nella sezione dei limiti |

Su questa campagna: **0 righe [H]**, **2 righe [P]** (due pesi non riprodotti dal
ricalcolo, entrambi in `run5-tbt-2s/nazionale`, host `m1`, epoche 38 e 39),
**80 righe [I]**. Verificalo, non fidarti di questa riga.

#### `disuguaglianza_pesi.csv` — concentrazione del peso nel tempo
Una riga per epoca. `n_host_con_peso`, `gini_peso_pubblicato`,
`gini_peso_effettivo`, `entropia_normalizzata_peso` (`H/H_max`: 1 =
equidistribuzione, 0 = un solo host ha tutto), `host_dominante`,
`quota_host_dominante`, `gini_atteso_da_input`, `gini_contributi_c_i`,
`delta_gini_pubblicato_input`.

* `gini_atteso_da_input` e' il Gini sul **peso grezzo `W_k^e`**, cioe' sulla
  stessa quantita' *prima* che la retroazione `rho` la tocchi. E' il termine di
  paragone giusto perche' e' definito sulla stessa unita' (il cluster);
* `gini_contributi_c_i` e' la lettura letterale sui singoli `c_i^e`: dice quanto
  e' diseguale l'**attivita' di filiera**, non il potere di elezione;
* `delta_gini_pubblicato_input = gini_peso_pubblicato - gini_atteso_da_input`.
  Se e' positivo e crescente, c'e' **amplificazione da retroazione**; se il Gini
  si stabilizza entro la durata della run, e' coerente col vincolo
  `lambda_w < 1` (Oss. 6.2).

Questi sono **numeri**, non verdetti: l'interpretazione e' compito tuo, e resta
soggetta alla §1.3 — un peso che si concentra perche' un cluster e' piu' virtuoso
e' il protocollo che funziona.

#### `verifica_riconciliazione.log`
Per ogni riga in cui il peso ricalcolato non torna, la spiegazione piu'
probabile invece del solo numero; e l'elenco delle transazioni viste dai nodi e
mai finite in un blocco (causa piu' comune di uno scostamento). Leggilo prima di
scrivere che la Sez. 5.11.1 e' violata.

### 4.4 `esperimenti/<run>/file-analisi-dati-di-tutti-gli-esp-in-area/`

* `confronto_aree_peso.csv` — stesse colonne di `peso_riconciliazione.csv`, con
  `livello` come dimensione di confronto a parita' di run (stesso seed, stesso
  `tbt`);
* `confronto_aree_riepilogo.md` — separa **due famiglie di divergenza**:
  * **ESG identico, `tau` diverso**: *atteso*. L'epoca dura piu' **secondi** dove
    i blocchi sono piu' lenti, quindi ci cadono dentro piu' transazioni anche se
    il tasso di generazione e' identico. Il canale e' il **throughput**, non la
    selezione;
  * **ESG diverso a parita' di run**: *anomalia*. Indica un seed non riprodotto,
    e va segnalata **prima di ogni altra cosa**.

---

## 5. Il report che devi scrivere

### 5.1 `analisi/report_generale.md` — sintetico, poche pagine

Nell'ordine:

1. **Le righe `[H]` di `errori_integrita.csv`, se ce ne sono, in cima al
   documento, prima di qualunque altra cosa.** Se non ce ne sono, dillo in una
   riga e vai avanti.
2. **Tabella di sintesi**: una riga per run, colonne "quali configurazioni
   funzionano" — stato, fork, verify, ordinamento delay, chi-quadro a finestra,
   scarto di block time. Il lettore deve capire in dieci secondi quali run
   reggono.
3. **Un paragrafo per famiglia di confronto** di `famiglie_confronto.csv`
   (5-8 righe l'uno), con rimando al report di dettaglio.
4. **La tabella di verifica dei risultati formali** della §1.5 di questo
   documento, **per intero**, con una colonna `esito` e una colonna `dove`.
5. **L'esito dei test aggiuntivi**, una riga per run: correlazioni,
   ordinamento dei delay, fit Prop. 5.18.
6. **I limiti dichiarati**: malus mai esercitati, `dump-function = none` ovunque,
   campione per epoca insufficiente, jitter non implementato da Shadow, Monte
   Carlo che testa la formula e non il binario.
7. **Rimandi espliciti** ai file di dettaglio, per ogni sezione. **Mai
   duplicare una tabella.**

### 5.2 I report di dettaglio, uno per famiglia

Per ciascuno: **prima** la tabella o il grafico, **poi** al massimo 5-8 righe di
commento. Mai il contrario, mai piu' lungo.

Grafici da produrre in `analisi/plots/` (solo quelli che generi davvero):

* traiettoria del peso per epoca, per run e per host;
* quota osservata vs `quota_attesa_vigenza` per epoca;
* chi-quadro a finestra vs `tbt`, con la soglia 5.991 tracciata;
* fit della Prop. 5.18 (`frazione_G_sotto_100ms` vs `1/Dmax`, e log-log);
* scarto del block time vs `tbt`;
* Gini ed entropia nel tempo.

---

## 6. Checklist di lettura di una run — in quest'ordine

Ogni passo puo' invalidare tutti quelli successivi. Non saltarne nessuno e non
cambiare l'ordine.

1. **`run_index.csv`**: `stato`, `tbt_mismatch`, `setup_mismatch`, `note`. Una
   run `parziale` o con `tbt_mismatch = 1` non entra nei confronti per `tbt`.
2. **`forks.csv`**: un `fork persistente` invalida tutto il resto per quella run.
3. **`verify.csv`**: se il verificatore interno dichiara record non validi, i
   pesi su cui poggia ogni attesa non sono affidabili.
4. **`alternanze.csv`**: `consecutivi_osservati` molto sotto gli attesi = Spacing
   residuo, cioe' un vincolo che sopprime le ripetizioni e falsa ogni chi-quadro.
5. **`campione_sufficiente_epoca` / `_finestra`** in `peso_riconciliazione.csv`:
   se sono 0, il chi-quadro corrispondente non e' concludente. Dirlo e' parte
   della risposta, non una premessa da saltare.
6. **`ordinamento_delay.csv`**: `inversioni > 0` significa che la mappa
   peso -> delay non e' monotona, e allora nessuna quota attesa e' credibile.
7. **`sortition_margins.csv`**: se `G` e' dell'ordine dell'RTT, le corse al tip
   spiegano gli scostamenti meglio di qualunque ipotesi sul peso.
8. **Solo adesso** chi-quadro e quote: `chi2_finestra`, `scostamento_quota`.
9. **`block_times.csv`**: `scarto_s` e il suo segno (vedi §7).
10. **`peso_riconciliazione.csv` epoca per epoca**: la catena della §1.2, anello
    per anello, e `esito_ricalcolo`.

---

## 7. Come distinguere un artefatto del simulatore da un effetto di protocollo

Prima di presentare qualunque anomalia come scoperta, escludi **tutte** queste
spiegazioni note, e scrivi nel report che l'hai fatto.

| sintomo | spiegazione nota da escludere prima |
|---|---|
| block time medio **sistematicamente sopra** il target, offset **costante e positivo** a ogni `tbt` | e' l'**offset vdso** del simulatore: Shadow intercetta le chiamate di tempo e introduce un ritardo fisso di scheduling. Firma: lo scarto **non** cambia segno e scala poco col `tbt`. Non e' il protocollo |
| block time che **oscilla intorno** al target, con scarto che **cambia segno** fra le run | e' la retroazione `lambda*Phi_n` di `wpoa-sortition-lambda`: se il guadagno e' troppo alto sovracorregge. Firma: segno alternato, correlazione col valore di `wpoa_sortition_lambda` |
| margini `G` piccoli e fork "misteriosi" a `tbt` basso | `Dmax = delta * tbt`: a `tbt = 2 s` la banda e' 1 s e i delay si affollano. Guarda `banda_dmax_s` prima di ipotizzare altro |
| scostamento fra quota osservata e attesa in una singola epoca | quasi sempre **campione insufficiente** (`campione_sufficiente_epoca = 0`). Usa `chi2_finestra` |
| quote piatte nonostante pesi molto diversi | possibile **saturazione dello `score_norm`**: se i delay finiscono tutti al bordo della banda, l'ordinamento resta ma la separazione si perde. Guarda `delay_pos_in_banda` in `proposers.csv` |
| ripetizioni dello stesso proposer molto piu' rare dell'atteso | **Spacing residuo** di MultiChain, anche con `mining-diversity = 0`. Guarda `alternanze.csv` |
| peso diverso fra livelli a parita' di run | `tau` conta le transazioni di una finestra di **12 blocchi**, ma il traffico e' generato a **tempo reale**: dove i blocchi sono piu' lenti l'epoca dura piu' secondi e ci cadono dentro piu' transazioni. E' il canale **throughput**, atteso. Anomalia solo se cambia anche l'**ESG** |
| il peso ricalcolato non torna | leggi `verifica_riconciliazione.log` **prima**: una riconciliazione entrata in mempool e poi caduta come orfana viene contata dall'harness e non dalla catena. E incrocia con `verify.csv`: e' la **discordanza fra i due verificatori** a essere significativa, non lo scarto da solo |

**Un limite strutturale da dichiarare esplicitamente:** Shadow non implementa il
**jitter** di rete. Le latenze sono deterministiche per coppia di nodi. Quindi il
`sigma` che compare nella Prop. 5.18 (`Pr[inversione] = O((n*sigma/Dmax)^(2/3))`)
**non e' isolabile dalla sola geografia** in questa campagna: quello che vedi
variare fra i livelli e' la latenza media, non la sua varianza. Ogni conclusione
sull'esponente della legge di scala va qualificata di conseguenza.

---

## 8. Riepilogo dei dati gia' verificati dalla pipeline

Punti di partenza, tutti da riverificare sulle tabelle — non citarli sulla fiducia:

* 20 run su 20 in stato `completa`, nessun `tbt_mismatch`, nessun
  `setup_mismatch`;
* nessun fork persistente: 14 run `nessun fork`, 5 `ritardo di propagazione`,
  1 `corsa al tip`;
* `malus_events_found = 0` in tutte le run: il meccanismo dei malus non e'
  esercitato dalla campagna;
* `dump_function = none` in tutte le run: lo smorzamento anti-whale non e'
  esercitato;
* ricalcolo del peso: 2 scarti su ~2100 righe (epoca x host), entrambi nella
  stessa run (`run5-tbt-2s/nazionale`, `m1`, epoche 38-39), classificati `[P]`
  perche' `verify.csv` dichiara validi tutti i record in tutte le 20 run;
* `errori_integrita.csv`: 0 righe `[H]` su tutta la campagna;
* ordinamento delay-peso rispettato in tutte le 20 run;
* Monte Carlo: Cor. 5.4 confermato con **zero** selezioni esatte per il
  candidato a peso nullo, e chi-quadro compatibile in tutti gli scenari;
* in `proposers.csv` compaiono solo `m1`, `m2`, `m3`: `admin` — che pure ha il
  permesso di mining — e `ca` non propongono mai un blocco fuori dal setup
  (Cor. 5.4);
* ESG e adesioni identici fra le quattro aree di ogni run: ogni differenza di
  peso fra livelli viene dall'attivita' `tau`, cioe' dal throughput.

Buon lavoro. Se un dato che ti serve non esiste in nessuna di queste tabelle,
**dichiara esattamente quale campo manca e dove ti aspetteresti di trovarlo**,
invece di stimarlo.
