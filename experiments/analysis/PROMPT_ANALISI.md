# Prompt di analisi — esperimenti wPoA su rete emulata

> **Come si usa.** Apri una sessione nuova con un agente IA (Claude, ChatGPT,
> o altro), incolla **questo file per intero** e allega i file elencati nella
> Sezione 3. Basta a se stesso: non serve leggere il codice della pipeline,
> né la tesi, né altri prompt. Tutto quello che serve per interpretare i dati
> è qui dentro.
>
> **Non rilanciare nulla.** I dati sono già stati estratti. Il tuo compito è
> leggerli e giudicarli.

Derivato da `shadow/analisi/PROMPT_ANALISI.md` (commit `6278274`): stessa
struttura, stesso metodo di lettura, stessi criteri. Ciò che cambia è la
provenienza dei dati — RPC di nodi reali su rete emulata invece di log
intercettati da un simulatore — e le due conseguenze che ne derivano, in
Sezione 1.6.

---

## 0. Chi sei e cosa devi produrre

Sei un **analista di protocolli di consenso blockchain**. Devi giudicare se
un'implementazione di **wPoA (Weighted Proof-of-Authority)** — un fork di
MultiChain 2.3 del progetto POESIA — si comporta come il protocollo prevede.

La domanda è una sola, e si risponde con numeri:

> **Il protocollo si comporta come previsto? E in quali condizioni smette?**

Produci, in questo ordine:

1. **Sintesi** (max 1 pagina): la risposta, con i tre o quattro numeri che la
   sostengono.
2. **Tabella di conformità peso/blocchi**: per ogni validatore, quota di
   blocchi osservata contro quota di peso attesa, differenza assoluta e
   relativa, e il verdetto del test statistico.
3. **Criticità rilevate**, ordinate per gravità, ciascuna con l'evidenza
   numerica e il file da cui viene.
4. **Raccomandazioni**: cosa cambiare nella configurazione o nel protocollo, e
   quale esperimento lo dimostrerebbe.

### Vincoli non negoziabili

* **Non inventare dati.** Se una metrica manca, è vuota o è dichiarata non
  disponibile, **dillo esplicitamente** e vai avanti. Una tabella con un
  numero plausibile ma inventato è il modo peggiore di fallire questo
  compito. La formula da usare è: *"dato non disponibile: \<motivo\>"*.
* **Distingui osservato da derivato.** Ogni colonna ha uno stato dichiarato in
  `metrics_schema_report.md`: `observed` (letto da un nodo, dal kernel o dalla
  configurazione), `derived` (calcolato con una formula indicata),
  `unavailable` (assente, con la ragione). Mantieni la distinzione in ogni
  affermazione.
* **Un campione non è una tendenza.** Un solo run è un campione. Se il numero
  di blocchi misurati è basso, dichiara che il test non è concludente invece
  di leggerne il verdetto.
* **Leggi `run_index.csv` per prima, sempre.** Contiene la configurazione
  effettivamente sigillata nella catena. Se un parametro che citi non
  corrisponde a quella riga, è la riga ad avere ragione.

---

## 1. Il protocollo, in forma sufficiente a giudicarlo

### 1.1 La rete

Una rete permissioned con quattro ruoli:

| ruolo | cosa fa |
|---|---|
| `miner` | validatore e **capo cluster**. È l'unico che propone blocchi. Ha un peso. |
| `company` | cliente. Pubblica item di filiera su uno stream applicativo: paga una fee al miner che li include e incrementa il contatore di attività `tau_i`. Non ha peso e non mina. |
| `admin` | governance. Sigilla la genesi, concede i permessi, crea gli stream, distribuisce il GAS, e durante la fase di setup mina da solo. Peso nullo. |
| `ca` | Certification Authority. È l'**unico** autorizzato a scrivere i punteggi ESG (permesso custom `high1`). Peso nullo. |

Ogni company aderisce al cluster di un miner. Il peso di un miner dipende
dall'attività e dagli ESG del **proprio cluster**, non dai propri.

### 1.2 La catena del peso, anello per anello

```
ESG_i        punteggio certificato dal CA, in (0, 100)          [osservato]
tau_i        item pubblicati dal nodo i nell'epoca             [osservato]
c_i          = ESG_i * tau_i / kappa        contributo del nodo [derivato]
Theta        = somma dei tau sui nodi del cluster              [derivato]
W_k          = somma dei c_i sul cluster k                     [derivato]
A_k          = alpha * Theta * W_k / W_tot                     [derivato]
R_k          GAS riconciliato dal miner k verso il treasury    [osservato]
rho_k        tasso di conformità, da R_k                       [derivato]
w_k          = W_k * [rho_{k,e-1} * lambda + (1 - lambda)]     [derivato]
```

`w_k` è il peso pubblicato sullo stream **chiuso** `wpoa-weights`. È quello
che conta per l'elezione.

### 1.3 Il principio guida

> **La probabilità che un miner proponga un blocco deve essere proporzionale
> al suo peso**, dopo la funzione di smorzamento.

L'elezione è un'estrazione di Efraimidis–Spirakis su `f(w)`, dove `f` è la
*dump function* (`none`, `sqrt` o `log`). Con `sqrt`, un divario di peso 10×
compra circa 3.2× di probabilità. La dump function è **consenso-critica**: sta
in `params.dat` ed è uguale per tutti.

### 1.4 La vigenza: il peso dell'epoca `e` vale nell'epoca `e+1`

Il record marcato `epoch = e` viene pubblicato a epoca **già chiusa**, dopo un
margine di stabilità. Entra quindi in vigore dentro l'epoca `e+1`.

**Conseguenza diretta per la tua analisi:** confrontare i blocchi di tutta la
run con l'**ultimo** peso pubblicato è indicativo, non probante, se i pesi si
muovono fra le epoche — ed è precisamente ciò che il weight engine fa. Il
confronto corretto è per epoca, contro il peso **vigente in quell'epoca**. È
per questo che esistono sia `summary.md` sia `summary_per_epoca.md`: leggi il
secondo prima di concludere.

### 1.5 I risultati formali da verificare

| risultato | cosa dovresti osservare | dove guardare |
|---|---|---|
| **Teor. 5.3** (proporzionalità) | quota di blocchi ≈ quota di peso, entro il rumore | `proposers.csv`, `chisq.csv` |
| **Cor. 5.4** (ineleggibilità) | nessun blocco proposto da un nodo a peso nullo dopo il setup | `proposers.csv` |
| **Prop. 5.12** (ordinamento) | il delay medio di sortition cresce al calare del peso | `ordinamento_delay.csv` |
| **Prop. 5.18** (timer race) | la frazione di round con margine `G` piccolo cresce al calare di `Δmax` | `sortition_margins.csv`, `fit_prop518.csv` |
| **Spacing residuo** | zero blocchi consecutivi dello stesso proposer è **un allarme**, non un risultato | `alternanze.csv` |

**Lo Spacing merita attenzione particolare.** Sotto selezione pesata, la
probabilità che due blocchi consecutivi abbiano lo stesso proposer è la somma
dei quadrati delle quote, quindi *diversa da zero*. Se `consecutivi_osservati`
è **0** mentre `consecutivi_attesi` è sensibilmente positivo, non è un esito
statistico: è la firma del vincolo di alternanza nativo
(`mining-diversity`), che vale `ceil(d*(N-1))` blocchi. In quel caso la
distribuzione osservata è un round robin e **il confronto coi pesi non dice
nulla sul protocollo**. Verifica `mining_diversity` in `run_index.csv`: deve
essere `0`.

### 1.6 Emulazione, non simulazione — le due conseguenze

Questi dati vengono da processi `multichaind` **reali** su una rete emulata
(namespace Linux, veth, `tc`/netem), misurati sull'orologio di parete. La
campagna storica veniva invece da un simulatore a eventi discreti.

1. **Gli orologi non sono confrontabili.** Qui `timestamp_wallclock` e
   `timestamp_monotonic`; là tempo simulato. Non confrontare mai timestamp fra
   le due, e usa `monotonic` per le differenze.
2. **Il tempo di blocco porta un bias diverso.** La media storica era gonfiata
   dalla latenza che il simulatore addebitava a ogni chiamata di orologio;
   qui quel termine non c'è, ma c'è la **contesa sull'host**, perché venti
   demoni competono per CPU reale. Prima di attribuire uno scarto del tempo di
   blocco alla retroazione `λΦ` del protocollo, **controlla il carico**
   riportato in `report_generale.md`.

Quote, chi-quadro, Gini, traiettorie dei pesi e margine della timer race sono
invece confrontabili: sono adimensionali o in blocchi.

---

## 2. Cosa contiene un esperimento

Un *run* è una rete completa avviata, portata a regime e misurata. Ha due fasi:

* **setup** (`setup-first-blocks` blocchi): PoA nativa, l'admin mina da solo
  mentre i nodi entrano, il CA certifica gli ESG, i cluster si formano e i
  primi pesi vengono pubblicati;
* **finestra di misura**: da lì in poi governa la wPoA. **Solo questi blocchi
  contano** per la valutazione del protocollo.

`run_index.csv` riporta entrambi i numeri. Ogni statistica che citi deve
riferirsi alla finestra di misura, mai al totale.

---

## 3. I file da allegare

Allega tutto ciò che esiste; se qualcosa manca, dichiaralo e prosegui.

**Indispensabili**

```
manifest.json                      configurazione, commit, binario, stato del run
metrics/run_index.csv              la configurazione sigillata — LEGGI PER PRIMA
metrics/proposers.csv              quota osservata vs peso
metrics/chisq.csv                  il test di proporzionalità
metrics/block_times.csv            tempi di blocco contro il target
reports/summary.md                 il riepilogo di run, leggibile
reports/summary_per_epoca.md       lo stesso, epoca per epoca (vedi 1.4)
reports/metrics_schema_report.md   stato di OGNI colonna: observed/derived/unavailable
```

**Molto utili**

```
metrics/epoch_shares.csv           quote per epoca contro il peso vigente
metrics/weights_trajectory.csv     traiettoria dei pesi pubblicati
metrics/alternanze.csv             il controllo sullo Spacing (vedi 1.5)
metrics/sortition_margins.csv      il margine della timer race
metrics/forks.csv                  consistenza fra nodi
metrics/verify.csv                 ricomputazione indipendente dei pesi
metrics/esg.csv                    punteggi ESG certificati
metrics/gas.csv                    economia del GAS e riconciliazione
metrics/netem_conditions.csv       le condizioni di rete effettivamente imposte
metrics/block_propagation.csv      propagazione dei blocchi fra nodi
metrics/fork_events.csv            divergenze nel tempo
```

---

## 4. Schema delle tabelle

Le colonne marcate **[O]** sono osservate, **[D]** derivate. Dove una colonna
può essere assente, è detto.

### `run_index.csv` — una riga per run. **Leggila per prima.**

| colonna | | significato |
|---|---|---|
| `run_id`, `livello`, `tbt` | [O] | identificativo, scenario geografico, target-block-time in secondi |
| `chain_name`, `protocolversion` | [O] | nome catena e versione di protocollo (deve essere `20014`) |
| `setup_first_blocks` | [O] | fine della fase PoA nativa. **Tutto ciò che sta sotto non va analizzato.** |
| `blocchi_misurati` | [D] | blocchi nella finestra wPoA. **Sotto ~100, il chi-quadro non è concludente.** |
| `mining_diversity` | [O] | **deve essere 0**; altrimenti vedi 1.5 |
| `dump_function` | [O] | `none` \| `sqrt` \| `log` |
| `weight_epoch_length` | [O] | lunghezza dell'epoca in blocchi |
| `weight_kappa/alpha/lambda` | [O] | costanti della catena del peso (§1.2) |
| `wpoa_sortition_delta` | [O] | `Δmax = delta * tbt`, la banda di ritardo |
| `rtt_max_ms` | [D] | RTT peggiore della topologia |
| `errori_H/P/I` | [D] | controlli di integrità falliti, per severità |
| `stato`, `note` | [D] | `completa` o il motivo per cui non lo è |

### `proposers.csv` — una riga per (run, validatore)

`blocchi` [O] proposti · `quota_osservata` [D] · `peso_ultimo` [O] ultimo peso
pubblicato · `quota_attesa` [D] = `w_i / W_tot` · `delay_medio_s` [O] delay
medio di sortition · `delay_pos_in_banda` [D] posizione nella banda `Δmax`.

**Come si legge:** `quota_osservata` contro `quota_attesa`. Se
`delay_pos_in_banda` è vicino a 1 per i nodi leggeri, i loro delay sono
schiacciati contro il tetto della banda e il vincitore lo decide la latenza,
non lo score — è il regime della Prop. 5.18.

### `chisq.csv` — il test di proporzionalità

`chi2_summary` [D] · `df` · `critico_5pct` · `compatibile_ricalcolato` [D] 1/0
· `min_attesa` [D] · `campione_sufficiente` [D] · `p_value` [D] (vuoto se
scipy non era installato: **dichiaralo, non stimarlo**).

**Come si legge:** se `campione_sufficiente` è 0 (attesa minima sotto 5), il
test **non è applicabile** e il verdetto va ignorato. Dillo.

### `block_times.csv`

`dt_medio_s` · `dt_mediana_s` · `dt_sd_s` · `dt_min_s`/`dt_max_s` [tutti D] ·
`target_s` [O] · `scarto_s`, `scarto_pct` [D].

**Come si legge:** vedi §1.6, punto 2, prima di attribuire lo scarto al
protocollo.

### `epoch_shares.csv` — una riga per (epoca, validatore)

`epoca` [D] · `blocchi_epoca` [O] · `quota_osservata_epoca` [D] ·
`peso_epoca` [O] il peso **vigente** allora · `quota_peso_epoca` [D] ·
`rapporto_Wtot_su_wi` [D].

È la tabella su cui si giudica davvero la proporzionalità (§1.4).

### `weights_trajectory.csv`

`host` · `epoca` · `peso` [O] · `height` [O] altezza di conferma. Una casella
mancante significa **invariato**: il registro non ripubblica un peso uguale.

### `alternanze.csv`

`blocchi_misurati` · `consecutivi_osservati` [O] · `consecutivi_attesi` [D].
Vedi §1.5: osservato 0 con atteso positivo è un allarme.

### `sortition_margins.csv`

`banda_dmax_s` [D] · `G_medio_s`, `G_mediano_s`, `G_min_s` [D] ·
`round_G_sotto_100ms`, `frazione_G_sotto_100ms` [D].

`G` è la distanza fra i due delay migliori. Quando `G` scende sotto la
varianza di rete, l'elezione gira sul rumore.

### `forks.csv`

`teste_distinte` [O] · `hash_sepolti_distinti` [O] · `spread_altezze` [D] ·
`verdetto` [D]. Più di una testa a fine run è un fork persistente.

### `verify.csv`

`epoca` · `verificato` [O] · `record` [O] · `non_validi` [O]. Ricomputazione
indipendente dei pesi da parte di un nodo. `non_validi > 0` è grave.

### `esg.csv` / `gas.csv`

ESG: `host`, `esg` [O], `cluster`. GAS: importi **già in GAS**, mai in unità
grezze. `gas_riconciliato_totale` [O] e `saldo_treasury` [O] sono la base di
`R_k`.

### `netem_conditions.csv` — nuovo rispetto alla campagna storica

Una riga per **direzione** di ogni link: `netem_delay_ms`, `netem_jitter_ms`,
`netem_loss_percent`, `netem_bandwidth_mbps` [tutti O **come configurati**,
non misurati sul filo]. `measured_delay_ms` è dichiarato `unavailable`.

**Il jitter è nuovo:** la campagna storica aveva jitter 0 ovunque, perché il
simulatore non implementava il campo.

### `block_propagation.csv` — nuovo

`nodes_seen` [D] · `propagation_time` [D] = ultimo avvistamento meno primo,
fra i nodi. **È un limite superiore**: la risoluzione è l'intervallo di
campionamento. Un blocco arrivato a tutti entro un tick legge 0.

### `fork_events.csv` — nuovo

`fork_detected` [D] 1 quando i nodi divergono a un'altezza sepolta comune ·
`fork_depth` [D] in **tick consecutivi**, non in blocchi. Un fork risolto fra
due tick è invisibile qui.

---

## 5. Il report che devi scrivere

### 5.1 Sintesi (max 1 pagina)

Rispondi alla domanda di §0. Apri con il verdetto, poi i numeri che lo
sostengono. Se non è possibile rispondere, dì perché e cosa manca.

### 5.2 Tabella di conformità

| validatore | blocchi | quota oss. | peso | quota attesa | Δ assoluta | Δ relativa |
|---|---:|---:|---:|---:|---:|---:|

Sotto la tabella: il verdetto del chi-quadro, **con** `campione_sufficiente` e
`min_attesa`, e la stessa tabella per epoca se i pesi si sono mossi.

### 5.3 Criticità

Per ciascuna: **gravità** (alta / media / bassa), **evidenza** (numero e file),
**interpretazione**, **cosa la confermerebbe o la escluderebbe**.

Da controllare sempre, in quest'ordine:

1. `mining_diversity` è 0? Altrimenti nulla di ciò che segue è valido (§1.5).
2. `blocchi_misurati` è sufficiente? Altrimenti il test non è concludente.
3. `campione_sufficiente` è 1?
4. Ci sono fork persistenti (`teste_distinte > 1`)?
5. `non_validi > 0` in `verify.csv`?
6. `errori_H` / `errori_P` diversi da zero in `run_index.csv`?
7. Il carico dell'host è alto (vedi `report_generale.md`)? Se sì, il tempo di
   blocco non è attribuibile al protocollo.

### 5.4 Raccomandazioni

Per ciascuna: che cosa cambiare, perché, e **quale esperimento** la
verificherebbe (quale file di `configs/chain-params/`, quale topologia, quale
durata).

---

## 6. Errori da non commettere

* **Non confrontare i tempi con la campagna Shadow.** §1.6.
* **Non leggere il chi-quadro quando il campione non basta.** Dì che non basta.
* **Non concludere sulla proporzionalità senza guardare le epoche.** §1.4.
* **Non dedurre fork, sync lag o propagazione da un solo nodo**: sono
  relazioni *fra* nodi. Le tabelle che le contengono sono già aggregate; non
  ricavarle da `getinfo` di un nodo solo.
* **Non trattare i valori netem come misurati.** Sono configurati (§4).
* **Non riempire un buco.** "Dato non disponibile: \<motivo\>".
