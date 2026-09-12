# DIAGNOSI — raccolta dati, summary, grafici, modello temporale

Diagnosi dei tre run "puliti" presenti sul filesystem locale, con causa radice
per ogni lacuna e indicazione di che cosa è stato recuperato rigenerando il
post-processing e che cosa richiede un nuovo run.

- Branch: `feature/real-network-emulation`
- Data della diagnosi: 2026-09-12
- Run esaminati: `run-intercontinental-20260910T201338Z`,
  `run-national-20260910T220231Z`, `run-regional-20260911T212321Z`

> I risultati non sono in git (`experiments/results/` è in `.gitignore`): tutto
> quanto segue è misurato sui file locali. I run sono di proprietà `root`
> perché prodotti dentro il container `poesia-emu:22.04`; il post-processing è
> stato rieseguito nello stesso container.

---

## 0. Sintesi

I tre run **non sono confrontabili fra loro**, e non per un file rotto: sono
stati eseguiti da **tre versioni diverse della pipeline**, e due dei tre hanno
avuto un guasto di esecuzione distinto. La combinazione produce esattamente il
sintomo osservato — artefatti diversi in ogni run, senza un errore visibile.

| | intercontinental | national | regional |
|---|---|---|---|
| esito reale | misurazione riuscita | **daemon admin morto a fine run** | **fabric non funzionante** |
| `manifest.status` scritto | `completed` | `completed` ← falso | `completed` ← falso |
| errori nel manifest | 0 | 3465 | 1 |
| fasi completate | 8/8 | 5/8 (`join`,`weights`,`final` degraded) | 1 (`validate`) |
| blocchi prodotti | 304 | 0 misurati | 0 |
| campioni sampler | 7 020 obs / 5 470 sightings | 36 940 obs / 29 130 sightings | 0 |
| `raw/metrics/` (snapshot finale) | 20 file | **5 file** | **0 file** |
| versione pipeline al momento del run | pre-`a5abc8a` | pre-`a5abc8a` | ~HEAD |

Le tre cause sono indipendenti e vanno tenute separate:

1. **Deriva di versione** (intercontinental, national): i due run sono
   anteriori ai commit `a5abc8a` (summary + 12 fogli storici), `f527222`
   (figure) e `c073c9a` (summary per epoca). Nessun dato è andato perso — è il
   post-processing che non esisteva ancora. **Interamente recuperabile.**
2. **Snapshot finale mai preso** (national): il daemon `admin` è morto con
   `SIGABRT` e la fonte primaria delle metriche non è stata scritta.
   **Non recuperabile senza rieseguire il run.**
3. **Rete emulata non funzionante** (regional): nessun daemon è mai partito.
   **Non recuperabile senza rieseguire il run.**

A queste si aggiungono **cinque difetti della pipeline** che hanno reso ognuna
di queste situazioni silenziosa invece che evidente (§3), il bug di formato dei
summary (§4) e il bug delle figure (§5).

---

## 1. Task 1 — Inventario: atteso vs presente

### 1.1 Schema atteso

Ricavato da `plan.py`, `analysis/reporting.py`, `analysis/summaries.py`,
`analysis/summary_per_epoca.py`, `analysis/plots.py`, `analysis/layout.py`,
`analysis/pipeline/`, `metrics/catalogue.py`, `metrics/diagnostics.py` e dagli
script in `scripts/`.

```
<run>/
  manifest.json                     stato, fasi, errori, temporal_model
  run.log                           log della sessione, wall-clock
  config/                           experiment.yaml, chain-params.dat, topology.*
  runtime/
    shared/<node>.addr              indirizzo per nodo
    data/<node>/<chain>/            datadir reale di multichaind
    topology-realized.json          impairment EFFETTIVAMENTE installato
    node-status.json                stato per nodo a fine run
  logs/<node>/                      debug.log, role_controller.log, rpc.log,
                                    process.log, events.jsonl
  raw/observations/                 node_observations, block_sightings,
                                    process_samples          (sampler, live)
  raw/metrics/                      snapshot finale dell'admin:
                                    blocks.json, weights.json, esg.json,
                                    membership.json, malus.json, verify.json,
                                    admin_getinfo.json, permissions_mine.json,
                                    treasury_balance.json, final_height.txt,
                                    node_state.csv, esg_scores.csv,
                                    membership.csv, reconciliation.csv,
                                    traffic.csv, gas_transfers.csv,
                                    gas_balances.csv
                                    + summary.txt, summary_epoche.txt
  metrics/                          6 tabelle native + 12 fogli storici
                                    + epoch_summary.csv, epoch_validators.csv
                                    + per-run/
  analysis/<run>/<livello>/phase1|2|3/
  reports/                          summary.md, summary_per_epoca.md,
                                    summary_per_epoca_emulation.md,
                                    report_generale.md, report_confronto.md,
                                    report_asse_livello.md, report_asse_tbt.md,
                                    metrics_schema_report.md
  plots/                            01..06 (storiche) + 10..12 (emulazione)
```

### 1.2 Presenza per run — stato **prima** dell'intervento

| artefatto | intercontinental | national | regional |
|---|---|---|---|
| `run.log` | 113 righe | 3 577 righe | 105 righe |
| `manifest.json` | 78 KB | 531 KB | 126 KB |
| `raw/observations/*.csv` | 3 file, pieni | 3 file, pieni | **assenti** |
| `raw/metrics/` | 20 file | **5 file** (solo CSV di stream) | **vuota** |
| `metrics/` — native | 6, piene | 6, piene | 6, **vuote/header** |
| `metrics/` — 12 fogli storici | **assenti** | **assenti** | presenti ma **vuoti** |
| `metrics/epoch_summary.csv` | **assente** | **assente** | presente, 0 righe |
| `metrics/per-run/` | **assente** | **assente** | presente, vuoto |
| `analysis/phase1\|2\|3` | completo (304 blocchi) | completo ma **0 blocchi** | completo ma **0 di tutto** |
| `reports/summary.md` | **assente** | **assente** | **assente** |
| `reports/summary_per_epoca.md` | **assente** | **assente** | **assente** |
| `reports/summary_per_epoca_emulation.md` | **assente** | **assente** | presente (vuoto di dati) |
| `reports/report_*.md` (4) | presenti | presenti | presenti |
| `plots/*.png` | 3 (famiglia emulazione) | 3 (famiglia emulazione) | **0** |

### 1.3 A quale fase è riconducibile ogni lacuna

| lacuna | fase | causa |
|---|---|---|
| 12 fogli storici assenti (inter, nat) | post-processing | lo stadio non esisteva alla data del run (`a5abc8a`) |
| `summary.md` / `summary_per_epoca.md` assenti (inter) | post-processing | idem — recuperabile |
| `summary*.md` assenti (nat, reg) | **raccolta live** | manca `blocks.json`: snapshot mai preso |
| `raw/metrics/` con 5 file (nat) | **raccolta live** | `AdminRole.teardown()` non ha potuto girare |
| `raw/metrics/` vuota (reg) | **raccolta live** | nessun daemon avviato |
| `raw/observations/` assente (reg) | **raccolta live** | sampler senza nodi da interrogare |
| `netem_conditions.csv` vuoto (reg) | **raccolta live** | `topology-realized.json` mai scritto |
| 0 grafici (reg) | post-processing | dati a monte assenti **+** bug §5 |
| solo 3 grafici (inter, nat) | post-processing | **bug §5**: 6 figure mai tentate |

---

## 2. Task 2 — Causa radice della raccolta parziale

Le ipotesi tipiche indicate nel brief sono state verificate una per una.

### 2.1 Race condition / raccolta anticipata — **ESCLUSA come causa dei 3 run**

`run_experiment.sh:95` esegue la sessione con una sostituzione di comando
bloccante (`OUTPUT="$(cli "${ARGS[@]}" ...)"`) e ne raccoglie il codice di
uscita in `RUN_RC` **prima** di lanciare l'analisi (riga 118 originale). Non
c'è quindi sovrapposizione fra `experiment run` e `analysis run`, e nessuno
`sleep` fisso al posto di un'attesa. Lato Python, il barrier esiste già ed è
reale: `session.py:409` chiama `scheduler.stop_all(timeout_s=90)`, che manda
`SIGTERM` e **attende la morte effettiva dei processi**
(`scheduler.py:205-208`, ciclo su `time.monotonic()` finché
`any(h.alive())`), e lo fa *mentre i daemon sono ancora su*, come richiede lo
snapshot dell'admin.

**Difetto residuo comunque corretto**: `collect_results.sh` e
`analyze_results.sh` possono essere invocati **a mano** su un run i cui daemon
sono ancora vivi (è il caso d'uso documentato di quegli script). In quel caso
leggevano `raw/`, `runtime/` e i `debug.log` senza alcuna verifica. Aggiunta
`wait_for_daemons_to_exit()` in `scripts/_common.sh`: un barrier su **stato di
processo reale** (`pgrep` sul nome della catena, polling ogni 2 s, timeout
esplicito con avviso), non su un ritardo fisso.

### 2.2 Path/nomi non deterministici — **ESCLUSA**

`analysis/layout.py:46` risolve il layout **per ispezione** (`raw/metrics` +
`manifest.json` ⇒ nativo, altrimenti legacy) e tutti gli analizzatori migrati
lo usano: `collect_metrics.py:32,378`, `summary_per_epoca.py:43,744`,
`analizza_esperimenti.py` via `make_run`. `summaries.py` cerca i file esattamente
dove il writer li scrive (`layout.metrics`). Nessun disallineamento.

Un solo punto è confermato: `run_campaign_sheets()` fa girare
`analizza_esperimenti` in una `tempfile.mkdtemp()` e ne copia fuori i risultati
(`extractors.py:230-269`). Il path è corretto, ma la `shutil.rmtree` finale
**non era in un `finally`**: qualsiasi eccezione durante la copia lasciava
l'albero temporaneo in `/tmp` e — a causa di §2.3 — non lo segnalava.
Corretto.

### 2.3 Eccezioni silenziate — **CONFERMATA**, causa principale dell'invisibilità

`metrics/extractors.py:312-330` (prima della patch) avvolgeva i tre stadi
pesanti — summary, pipeline storica, fogli di campagna — in tre
`try/except Exception` che loggavano e **restituivano un dict di aspetto
normale**:

```python
except Exception as exc:      # noqa: BLE001
    LOG.error("the summaries could not be produced: %s", exc)
    produced["summaries"] = {"error": str(exc)}
```

`analysis/cli.py:83-87` poi restituiva `SUCCESS` purché `produced["tables"]`
non fosse vuoto — e `tables` contiene le sei tabelle native, che si scrivono
sempre, anche con zero righe. **Un run poteva perdere i 12 fogli storici e
tutti i summary e uscire con codice 0.** Nessuno stack trace, perché
`LOG.error` non è `LOG.exception`.

*Correzione*: i fallimenti sono ora **raccolti** in `produced["stage_failures"]`
e non solo loggati; `LOG.exception` stampa il traceback; `cmd_analysis_run`
esce con `AnalysisFailed` se un qualsiasi stadio è fallito; e un run in cui
**tutte** le tabelle sono vuote solleva `IncompleteData` invece di uscire 0
(era il caso di regional, che usciva 0).

### 2.4 Timeout troppo aggressivi — **NON è la causa dei 3 run**

Nessuna raccolta è stata abbandonata per timeout. `national` non ha perso lo
snapshot per lentezza ma perché il processo era **morto**: `run.log:3524-3564`
registra `daemon on admin exited with -6` (SIGABRT) ogni 5 s dalle 03:06:57,
e `admin:snapshot` viene avviato alle 03:08:17 — 80 secondi *dopo* la prima
morte, contro un daemon che non c'era più.

### 2.5 Ordine bash/Python — **ESCLUSO** (vedi §2.1)

**Difetto residuo comunque corretto**: in `run_experiment.sh` sia
`cli analysis run` sia `cli report generate` erano `|| warn`, e lo script
usciva con `RUN_RC`. Un'analisi fallita su un run riuscito **usciva 0**. Ora i
codici sono catturati e propagati.

### 2.6 Difetto aggiuntivo — snapshot fallito senza traccia — **CONFERMATO**

`runtime/roles/admin.py:241` (prima della patch):

```python
height = self.block_count()
if height < 0:
    self.log.error("no RPC at teardown: the final snapshot was not taken")
    return                      # <- e basta
```

Un `return` silenzioso. La sessione registra poi `phase final: ok` e
`status: completed`. È il motivo per cui `national` — che ha perso la fonte
primaria di ogni metrica — risulta a manifesto un run **completato**.

*Correzione*: `teardown()` scrive `raw/metrics/snapshot_failed.json` con
motivo, timestamp wall-clock, elenco dei file che mancheranno e
`recoverable_by_reanalysis: false`; il log elenca esplicitamente i file persi.
`analysis/summaries.snapshot_verdict()` legge quel file e trasforma
«no blocks.json» in «lo snapshot non è stato preso, alle 03:08:17, per questo
motivo, e nessuna rianalisi lo recupera».

### 2.7 Difetto aggiuntivo — deriva fra catalogo e collector — **CONFERMATO**

La validazione di schema segnala su entrambi i run vecchi:

```
node_observations.csv: declared columns absent from the file:
pending_transaction_count, process_alive, controller_alive
```

`metrics/catalogue.py` dichiara tre colonne che il sampler di allora non
scriveva. Non è un dato perso — è il catalogo che è avanzato. È però la ragione
per cui l'analisi di quei due run esce ora con codice 5: il comportamento è
corretto e voluto (l'incoerenza va vista), ma va saputo.

---

## 3. Riepilogo delle correzioni alla pipeline di raccolta

| # | difetto | file | correzione |
|---|---|---|---|
| 1 | snapshot fallito → `return` muto | `runtime/roles/admin.py:241` | artefatto `snapshot_failed.json` + log esplicito |
| 2 | eccezioni di stadio ingoiate | `metrics/extractors.py:312` | `stage_failures` + `LOG.exception` |
| 3 | exit 0 con output parziale | `analysis/cli.py:83` | exit `AnalysisFailed`; `IncompleteData` se tutto vuoto |
| 4 | analisi fallita → warning | `scripts/run_experiment.sh:118` | codici catturati e propagati |
| 5 | nessun barrier per uso manuale | `scripts/_common.sh` | `wait_for_daemons_to_exit()` su PID reali |
| 6 | tempdir non ripulita su errore | `metrics/extractors.py:246` | `finally` |
| 7 | `summary.md` fuori dagli attesi | `metrics/diagnostics.py:38` | aggiunto; `REQUIRED_PLOTS` derivato dal catalogo figure |

---

## 4. Task 3 — `summary.md` / `summary_epoches.md` in formato CSV

### 4.1 Riscontro

Il difetto è **reale e confermato**, con una precisazione sui nomi: la
pipeline non scrive `summary_epoches.md` ma `reports/summary_per_epoca.md`
(reso da `metrics/summary_epoche.txt`). Il nome è un contratto —
`docs/migration-from-shadow.md:332`,
`docs/pipeline/PROMPT_ANALISI_ESPERIMENTO.md:154` e
`tests/golden/test_prompt_schema.py:67` lo referenziano — quindi **non è stato
rinominato**; è lo stesso artefatto di cui parla la segnalazione.

L'ipotesi (b) del brief — un flag `format="csv"` con default sbagliato — è
**esclusa**: non esiste alcun parametro di formato in `cli.py`,
`analysis/cli.py` o nelle funzioni di scrittura.

L'ipotesi (a) è **confermata, in forma più grave**. `summaries.publish_to_reports()`
non passava da alcun formatter Markdown: prendeva l'output a larghezza fissa e
lo incollava **intero dentro un solo blocco ```text**:

```python
"```text\n%s\n```\n" % body.rstrip("\n")
```

Il file risultante era Markdown solo nell'estensione: **un** heading e 148
righe di testo preformattato. E dentro quel blocco, quattro sezioni sono
**CSV letterale** — è la segnalazione, alla lettera. In
`raw/metrics/summary.txt` del run intercontinental, righe 86-144:

```
── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,13DWP2zKBTDGazKQLbKux3BGtvDoQ98DucGphs,53.52
  ...
── Adesioni ai cluster (membership.csv) ──
── Riconciliazione verso il treasury (reconciliation.csv) ──
── Movimenti GAS (init + rifornimenti) (gas_transfers.csv) ──
```

Più, in coda, un blob JSON **troncato a metà token** da
`collect_metrics.py:419` (`json.dumps(verify)[:600]`), quindi non
interpretabile e non segnalato come parziale.

### 4.2 Correzione

Nuovo modulo `analysis/markdown.py`: un renderer del testo a larghezza fissa
verso Markdown reale. `summary.txt` e `summary_epoche.txt` **restano invariati
byte per byte** (li leggono `analizza_esperimenti.py:334` per il chi-quadro
autorevole e i tool di campagna) e vengono copiati accanto al `.md`.

| costrutto sorgente | resa |
|---|---|
| cornice `══` | `# Titolo` |
| `── Sezione ──` | `## Sezione` |
| blocco `chiave : valore` | tabella a 2 colonne |
| tabella allineata a spazi | tabella pipe, colonne per posizione |
| **blocco CSV incollato** | **tabella pipe** + file in `reports/tables/*.csv` |
| blob JSON troncato | fence ```text **con avviso esplicito** di troncamento |
| tutto il resto | fence per-blocco, mai perso |

Lo split delle tabelle allineate è **per posizione di colonna** (posizioni
bianche in *tutte* le righe del blocco), non per run di spazi: la traiettoria
dei pesi ha celle vuote, e uno split ingenuo sposta i valori a sinistra
falsando l'attribuzione dei pesi ai validatori. `_peel()` stacca inoltre le
righe di prosa che incorniciano una tabella (`record totali: 139`), che
altrimenti distruggono la rilevazione delle colonne.

### 4.3 Risultato misurato (run intercontinental)

| | prima | dopo |
|---|---|---|
| `summary.md` | 154 righe, 1 heading, **148 dentro un fence** | 184 righe, **9 heading H2, 119 righe di tabella, 5 righe in fence** |
| `summary_per_epoca.md` | 2 469 righe, 1 heading, tutto in fence | 2 870 righe, **25 heading, 1 146 righe di tabella** |
| righe CSV grezze nel `.md` | 40 | **0** |
| CSV estratti come file | 0 | 4 in `reports/tables/` |

### 4.4 Test

`tests/unit/test_summary_format.py`, 16 test: apertura con heading Markdown,
presenza della sintassi `|---|---|`, ogni `──` diventato `##`, nessuna riga
CSV grezza fuori dai fence, **meno di metà del file dentro un fence** (la
regressione esatta), celle vuote conservate nella colonna giusta, marker di
troncamento preservato, JSON troncato etichettato, e — il più importante —
**nessun token del sorgente perso nella conversione**.

---

## 5. Task 4 — Generazione grafici incostante

### 5.1 Riscontro: non è solo "dati mancanti a monte", c'è un bug indipendente

La causa radice è un **bug di codice**, non un problema di dati.

Il commit `f527222` ha sostituito, in `analysis/reporting.py:117`, la chiamata

```python
produced["plots"] = _plots(run_root, context)          # prima
```

con

```python
figures = generate_plots(run_root, plan)               # dopo
```

lasciando però `_plots()` nel file — 71 righe, **mai più chiamate da nessuno**
(verificato: nessun riferimento in tutto il repository). Quella funzione era
l'unica a disegnare le tre figure native dell'emulazione:
`01_height_per_node.png`, `02_block_propagation.png`, `03_link_delays.png`.

Conseguenza esatta, e coincide con l'osservato:

- **intercontinental e national** sono precedenti a `f527222`: hanno le 3
  figure dell'emulazione e **nessuna** delle 6 storiche;
- **regional** è successivo: tenta le 6 storiche, le salta tutte per mancanza
  di dati, e **non prova nemmeno** le 3 dell'emulazione → `plots/` vuota;
- da `f527222` in poi, **nessun run avrebbe mai più prodotto quelle 3 figure**,
  neanche con dati perfetti.

Difetti secondari confermati in `analysis/plots.py`:

- un drawer che **solleva** e una tabella legittimamente vuota finivano
  entrambi in `skipped`, indistinguibili: un crash si leggeva come "non
  c'erano dati";
- i motivi degli skip erano loggati a `LOG.info`, **sotto la soglia di
  default**: esistevano ma nessuno li vedeva;
- su eccezione la figura non veniva chiusa (`plt.close`), con leak di figure.

Non sono invece difetti: gli accessi alle colonne sono già tutti difensivi
(`row.get(...)` + `_number()` che assorbe `TypeError`/`ValueError`), e
`plots.mkdir(parents=True, exist_ok=True)` precede ogni `savefig`.

### 5.2 Correzione

- Le 3 figure dell'emulazione sono **restituite a `plots.py`** come
  `10_altezza_per_nodo.png`, `11_propagazione_blocchi.png`,
  `12_ritardi_link.png`. Numerate da 10 perché i prefissi `01/02/03`
  collidevano fra le due famiglie: nei run vecchi `01_` significava una cosa,
  in quelli nuovi un'altra.
- `_plots()` **rimossa** da `reporting.py`.
- `generate()` distingue ora tre esiti: `produced`, `skipped` (dato assente,
  con motivo), `failed` (drawer che ha sollevato → `LOG.error` con tipo
  dell'eccezione e nome del drawer, e riga dedicata nel report che dice
  esplicitamente «questo è un bug in `analysis/plots.py`, non un dato
  mancante»).
- Gli skip passano da `LOG.info` a `LOG.warning`.
- `metrics/diagnostics.REQUIRED_PLOTS` è ora **derivato** da `plots.FIGURES`
  invece di essere una seconda lista: era la ragione per cui la sparizione
  delle 3 figure non veniva rilevata dall'inventario.

### 5.3 Risultato misurato

| run | figure prima | figure dopo | saltate, con motivo |
|---|---|---|---|
| intercontinental | 3 | **8** | 1 (`03_chi2_vs_tbt`: serve una campagna multi-tbt) |
| national | 3 | **4** | 5 (tutte derivate dallo snapshot mancante) |
| regional | 0 | 0 | 9, **ognuna con la propria ragione** |

I tre file con i vecchi nomi (`01_height_per_node.png`,
`02_block_propagation.png`, `03_link_delays.png`) sono stati rimossi dai run:
erano gli stessi grafici sotto il nome anteriore alla rinumerazione.

### 5.4 Test

`tests/unit/test_plots_robustness.py`, 14 test. Il decisivo è
`test_every_catalogued_figure_has_a_drawer`: `FIGURES` e `DRAWERS` devono
coincidere, il che rende impossibile ripetere la regressione. Poi: nessuna
tabella, tabella con solo header, colonne con `dato non disponibile`/`-`,
colonna mancante, dati parziali che devono comunque produrre le figure
dell'emulazione, drawer che solleva → `failed` e non `skipped`, log a livello
`ERROR`, un fallimento non ferma gli altri.

---

## 6. Task 5 — Assenza di simulazione del tempo

**Verifica superata. Nessun residuo concettuale di Shadow nella gestione del
tempo.**

| controllo | esito |
|---|---|
| `time_scale`, `speedup`, `virtual_time`, `sim_clock`, `scale_factor`, `tick_rate`, `time_dilation`… in `.py`/`.sh`/`.yaml` | **0 occorrenze** (unica: una frase di prosa in `reporting.py:9` che *contrasta* il modello a eventi discreti) |
| durate calcolate con `time.time()` | **0** — tutte da `time.monotonic()` |
| timestamp assoluti | tutti `datetime.now(timezone.utc)`; nessun `utcnow()`, nessun `now()` naive |
| fine epoca sintetizzata come `start + durata_configurata` | **0 occorrenze** |
| `runtime/` che importa `analysis/legacy/` | **0** |
| import di `shadow.*` | **0** |
| scheduler a eventi discreti copiato | **assente** |

Dettaglio dei punti sensibili verificati a mano:

- `session.run_schedule()` (`session.py:303-314`): le tappe sono offset in
  secondi confrontati con `time.monotonic() - started`. È una **scaletta
  wall-clock**, non una timeline simulata: se la macchina è lenta, il run dura
  di più: non "recupera".
- `session._sleep()` (`session.py:446-452`): attesa interrompibile contro una
  deadline `time.monotonic()`, con `time.sleep(min(1.0, ...))` come intervallo
  di polling — non come avanzamento del tempo.
- Tutti i 14 `time.sleep()` del pacchetto sono intervalli di polling o backoff
  (max 5 s); nessuno sostituisce l'attesa di un evento.
- `runtime/events.py:37-39` registra ogni evento con **entrambi** gli orologi:
  `wall_clock_time` (UTC) e `monotonic_time`.
- `metrics/extractors.extract_propagation()` calcola la propagazione da
  `first_seen_monotonic` reali dei sightings, e la dichiara come **limite
  superiore** perché è quantizzata dall'intervallo di campionamento (10 s).
- `analysis/summary_per_epoca.py` prende i timestamp da `observed_wallclock`
  degli osservati; le durate dai timestamp di header dei blocchi (orologio
  reale del miner). Il campo si chiama `duration_wallclock_seconds`: **nome
  leggermente impreciso** (è derivato dagli header, non dall'osservazione
  diretta) — segnalato, non corretto, perché il valore è comunque un tempo
  macchina reale e il nome è già nello schema.

**Test**: `tests/unit/test_no_time_simulation.py`, 13 test, come guardia
statica permanente. Include un visitor AST che intercetta
`time.time() - x` (durata su orologio a muro, che un salto NTP falsa), un
controllo che `manifest.py` dichiari `temporal_model` con un valore
wall-clock, e una guardia sulla guardia (`test_the_monotonic_clock_is_actually_used`)
perché se il codice smettesse di misurare il tempo tutti gli altri test
passerebbero a vuoto. `analysis/legacy/` è escluso, e solo da queste regole:
è l'analizzatore Shadow migrato, tenuto compatibile di proposito, che legge
timestamp da file archiviati senza prenderne di propri.

> Nota sui manifesti: i due run vecchi **non hanno** la chiave
> `temporal_model` (né `started_at_wallclock`, `network_backend_used`,
> `fallback_confirmed`…). È una lacuna **di documentazione dell'artefatto**,
> non della logica: quei manifesti sono anteriori all'introduzione delle
> chiavi. Solo `regional` porta `temporal_model: wall_clock_emulation`.

---

## 7. Task 6 — Confronto con la pipeline Shadow archiviata

Riferimento: commit `62782748d902a31001f3a06302b2c4baea1a9ad6` (tip di
`feature/docker`, prima di `15009a6`), e la copia già presente in repository in
`experiments/analysis/historical/shadow-campaign/` — che è lo stesso materiale,
già estratto, e rende superfluo il `git show`.

Confronto fra i 17 fogli di `shadow-campaign/sheets/` e ciò che produce oggi
`metrics/`:

| foglio Shadow | prodotto oggi | note |
|---|---|---|
| `alternanze`, `block_times`, `chisq`, `epoch_shares`, `esg`, `forks`, `gas`, `proposers`, `run_index`, `sortition_margins`, `verify`, `weights_trajectory` | **sì**, stessi nomi e stesso codice migrato | 12/12 |
| `correlazioni`, `disuguaglianza_pesi`, `famiglie_confronto`, `fit_prop518`, `ordinamento_delay` | **sì** | 5/5 |
| `validazione_sortition` | script a sé (`legacy/valida_sortition_montecarlo.py`) | invariato |

La nuova pipeline è quindi un **superset**: oltre ai 17 fogli storici aggiunge
`node_observations`, `block_sightings`, `process_samples`,
`block_propagation`, `fork_events`, `netem_conditions`, `epoch_summary`,
`epoch_validators` — tutte serie temporali che **un simulatore con un solo
snapshot finale non poteva produrre**. Le definizioni storiche non sono state
riscritte: sono calcolate dalle stesse righe di codice migrate, così non
possono divergere dall'archivio.

Le 8 figure di `shadow-campaign/plots/` sono coperte dalle 6 storiche di
`plots.py` più le 3 dell'emulazione; `03_chi2_finestra_vs_tbt` resta una figura
**di campagna** e va costruita con `analysis campaign` su run a tbt diversi —
è dichiarata come skip con quella motivazione, non omessa.

---

## 8. Task 7 — Stato dopo la rigenerazione

Rigenerato con `analysis run` + `report generate` dentro `poesia-emu:22.04`.

### `run-intercontinental-20260910T201338Z` — **RECUPERATO INTEGRALMENTE**

| | prima | dopo |
|---|---|---|
| tabelle `metrics/` con righe | 6 / 6 | **22 / 25** |
| fogli storici | 0 | **17** (354 righe) |
| `summary.md` | assente | **presente, Markdown reale** |
| `summary_per_epoca.md` | assente | **presente** (2 870 righe, 25 sezioni) |
| `epoch_summary.csv` / `epoch_validators.csv` | assenti | presenti |
| `metrics/per-run/` | assente | presente |
| grafici | 3 | **8** |
| report `.md` | 5 | **8** |

Le 3 tabelle ancora vuote sono `famiglie_confronto` (serve più di un run),
`alternanze` e simili a riga singola: assenze legittime, dichiarate.

Uscita `analysis run`: **codice 5**, per la deriva di catalogo di §2.7
(`node_observations.csv` non ha le tre colonne dichiarate). È il comportamento
nuovo e corretto: l'incoerenza è reale e ora si vede.

### `run-national-20260910T220231Z` — **PARZIALMENTE RECUPERATO**

Recuperato tutto ciò che deriva dal sampler:

| | prima | dopo |
|---|---|---|
| tabelle con righe | 6 | **12 / 25** |
| grafici | 3 | **4** |
| osservazioni | 36 940 obs, 29 130 sightings, 142 439 campioni di processo | intatte |

**IRRECUPERABILE — richiede nuovo run** (dati grezzi mai scritti, non
ricostruibili né interpolabili):

- `raw/metrics/blocks.json`, `weights.json`, `esg.json`, `membership.json`,
  `malus.json`, `verify.json`, `admin_getinfo.json`, `permissions_mine.json`,
  `treasury_balance.json`, `final_height.txt`, `node_state.csv`,
  `gas_balances.csv`;
- di conseguenza: `summary.md`, `summary_per_epoca.md`, e i fogli
  `weights_trajectory`, `epoch_shares`, `block_times`, `proposers`, `chisq`,
  `forks`, `alternanze`, `esg`, `verify`, `disuguaglianza_pesi`;
- di conseguenza: le figure `01`, `02`, `05`, `06`.

*Causa*: `run.log:3524-3564` — `daemon on admin exited with -6` (SIGABRT) in
loop dalle 03:06:57; `admin:snapshot` avviato alle 03:08:17 contro un daemon
morto. Da indagare a parte, prima di rieseguire, il motivo dell'abort:
`logs/admin/multichaind.stdout.log`.

### `run-regional-20260911T212321Z` — **IRRECUPERABILE, richiede nuovo run**

Non c'è nulla da recuperare: nessun daemon è mai stato avviato.

```
2026-09-11T22:03:58 ERROR experiments.cli the fabric was built but does not
carry traffic: 380 of 380 node pairs cannot reach each other
(m1->m2, m1->m3, ...). No daemon was started, because on this network none
of them could join the chain.
```

*Causa*: backend `core` selezionato in automatico; la sessione CORE è stata
creata (20 namespace registrati alle 21:33, management plane alle 21:36) ma il
piano dati non instrada. Il messaggio d'errore indica già le verifiche:
`ip netns exec hm1 ip route` (la rotta verso la subnet dell'esperimento deve
portare `src <ip del nodo>`), `rp_filter` e `ip_forward` sui router. Nessun
dato è stato interpolato o inventato: le tabelle restano vuote con header, e
`analysis run` ora esce con **codice 4 (`IncompleteData`)** invece di 0.

---

## 9. Questione aperta, fuori dallo scope richiesto

`plan.setup_first_blocks` vale **152** mentre `summary_epoche.txt` legge
**64** da `params.dat` (che contiene `SETUP_FIRST_BLOCKS=auto`). I due summary
dello stesso run **non concordano su dove inizia la finestra wPoA**:
`summary.txt` misura le altezze 153-304, `summary_epoche.txt` parte
dall'epoca 6 (altezza 65). Il run-level summary scarta quindi metà della
finestra misurabile.

È lo stesso disallineamento che fa fallire 4 test **preesistenti** a questa
sessione (`tests/unit/test_chain_params.py` ×3,
`tests/unit/test_plan.py::test_setup_first_blocks_matches_the_documented_worked_example`,
che attende 64 e ottiene 152; verificato con `git stash` che falliscono anche
senza le modifiche di questa sessione, e presenti in
`.pytest_cache/v/cache/lastfailed`).

**Non corretto**: decidere quale dei due valori sia quello giusto cambia la
semantica dell'analisi e la finestra di misura di ogni run, ed è una scelta di
merito sulla tesi, non un bug di pipeline.

---

## 10. Verifica

```
294 passed, 8 failed, 5 skipped, 7 errors
```

I fallimenti e gli errori **preesistono** a questa sessione (verificato con
`git stash`; coincidono con `.pytest_cache/v/cache/lastfailed`):

- 4 unit: `test_chain_params` ×3 + `test_plan` ×1 → §9;
- 4 falliti + 7 errori di integrazione: `test_fabric_real.py`,
  `test_smoke_real.py` → richiedono root, `ip netns` e i binari MultiChain,
  non disponibili in questo contesto di esecuzione.

Nuovi test aggiunti, tutti verdi: **43**
(16 formato summary + 14 robustezza grafici + 13 assenza di simulazione).
