# Fase 0 — Ricognizione della repository e checkpoint di design

Pipeline sperimentale Shadow per wPoA + Weight Engine (prompt v6).
Branch di lavoro: `tests/shadow-simulator` (HEAD `b7def7d`; `fix/shadow-harness-coherence` è avanti di un solo commit, `512e40b`, che tocca soltanto i test di harness).
Data: 2026-09-05. Stato: **nessun file di pipeline scritto**; questo documento è il primo output richiesto dal prompt (§0.1 e §0.3) e attende approvazione.

Ogni affermazione qui sotto è stata verificata leggendo i file reali della repository (path indicati). Dove tesi, codice C++ e pipeline esistente non coincidono, la divergenza è **segnalata in §4 e non risolta**.

---

## 1. Esito in una pagina

1. **Campagna reale**: 24 run archiviate = 6 configurazioni (`run1`…`run6`) × 4 aree. Nessuna replica: seme fisso `20260827` ovunque. La gerarchia è `esperimenti/<run>/<area>/run/`, cioè **run → area**, non area → tbt → replica come ipotizzato dal prompt (§3.1). `run6` ha `weight-epoch-length = 100` (le altre 12) e il nome cartella non lo dice. `run7-tbt7s` è vuota.
2. **Modello implementato**: `argmin_i E_i / g(w_i)` con `E_i = −ln u_i`, `u_i` da HMAC (selezione pubblica) o da VRF (sortition privata), tie-break lessicografico (`src/wpoa/wpoa_selector.h:150-240`, `src/wpoa/private_sortition.h`). **Nessuna traccia di `argmax` su hash×peso**: la verifica critica del prompt §2 è superata.
3. **I log contengono lo score e il delay di TUTTI e tre i candidati a ogni altezza** (ogni miner logga il proprio: copertura 3/3 su 438/438 altezze misurate in `run6/regionale`). Quindi il vincitore teorico (argmin dei delay) è ricostruibile e confrontabile con il proposer osservato. Misurato in ricognizione: **inversioni 8.7 % (run6/regionale, tbt 10), 11.2 % (run1/regionale, tbt 15), 27–28 % (run5, tbt 2)**.
4. **Scoperta rilevante per la Prop. 5.18**: sui round invertiti lo scarto `D_osservato − D_min` va da 0.01 s a **1.6 s** (mediana 0.3–0.6 s) anche a tbt 15 s con RTT massimo 10 ms. Il rumore che inverte il vincitore **non è la latenza di rete** ma la quantizzazione al secondo (barra temporale `floor(D)`, timestamp dei blocchi interi, granularità del loop del miner). La stima di σ va fatta da questa sorgente, e dichiarata (§5.6).
5. **Pipeline esistente**: `tools/analizza_esperimenti.py` (2963 righe) fa raccolta, ricostruzione **e** test in un solo script (viola la regola 4 del prompt), ma la sua ricostruzione della catena del peso è verificata: coincide con `weightverifyweights` su ~2100 righe (epoca × miner) delle 20 run analizzate, con 2 scarti classificati [P]. Va **riusata**, non riscritta, separandola in fasi. Mancano del tutto: Wilson, test esatto/Monte Carlo quando `E_i < 5`, KS del margine vs `Beta(1,n)`, verifica di Prop. 5.17, tasso di inversione vs bound, HHI/Nakamoto, streak Monte Carlo, regressione longitudinale. Esistono già: correlazione ritardata `ρ(e) → w(e+1)`, Gini con baseline da input, validatore Monte Carlo standalone (`tools/valida_sortition_montecarlo.py`, il "test algoritmico" di §6.4).
6. **Non calcolabile sulla campagna attuale** (da dichiarare, non da stimare): effetto di `dumpfunction` (è `none` in tutte le 24 run), traiettoria del malus e verifica degli eventi `Delay` (registro vuoto in tutte le 24 run), latenza/jitter per evento (log a risoluzione 1 s, jitter Shadow `0 us`), `y_i` della VRF (non loggato).

---

## 2. Ricognizione

### 2.1 Gerarchia reale delle directory

```
shadow/
├── run.sh                          dispatcher: area= tbt= blocks= setup= epochlen= seed= …
├── config/
│   ├── params.overrides            parametri di catena comuni (unica fonte dei default)
│   ├── treasury.json               chiave del treasury (R_k)
│   └── levels/<area>.json          10 nodi, ruoli, cluster, coordinate, archi
├── tools/                          harness + script di raccolta/analisi (vedi §2.5)
├── tools/analisi/                  DUPLICATO STALE dell'output (differisce da shadow/analisi/)
├── <area>/                         ultima run "viva" del livello (shadow.yaml, .gml, run/)
├── esperimenti/                    campagna archiviata
│   └── runN-tbt-Ts/                ← livello 1: la RUN (tbt e altri parametri sigillati)
│       └── <area>/                 ← livello 2: AREA ∈ {regionale, nazionale, continentale, intercontinentale}
│           ├── shadow.yaml
│           ├── [report.md]         stdout di run.sh (run2–run4)
│           └── run/
│               ├── data/<host>/    params.dat, debug.log, txs.log, permissions.log, chunks.log, <chain>/
│               ├── metrics/        snapshot JSON-RPC + CSV dell'harness + summary*.txt
│               ├── shadow.data/    stdout/stderr per processo
│               └── shared/         VUOTO nelle run archiviate (host↔addr va ricostruito)
└── analisi/                        output della pipeline precedente (run1–run5) + PROMPT_ANALISI.md, GUIDA_LETTURA.md, report_*.md
```

Host: `m1 m2 m3` (miner, capi cluster), `c1 c2` → m1, `c3 c4` → m2, `c5` → m3, `admin` (Apuana SB, mina solo nel setup), `ca` (Certification Authority). Identici su tutte le aree; cambia solo la latenza.

### 2.2 Inventario delle run

| run | area | tbt | L | setup | blocchi tot | misurati | debug.log MB |
|---|---|---|---|---|---|---|---|
| run1-tbt-15s | regionale | 15 | 12 | 60 | 167 | 107 | 13 |
| run1-tbt-15s | nazionale | 15 | 12 | 60 | 173 | 113 | 16 |
| run1-tbt-15s | continentale | 15 | 12 | 60 | 169 | 109 | 13 |
| run1-tbt-15s | intercontinentale | 15 | 12 | 60 | 172 | 112 | 14 |
| run2-tbt-10s | regionale | 10 | 12 | 64 | 325 | 261 | 30 |
| run2-tbt-10s | nazionale | 10 | 12 | 64 | 329 | 265 | 26 |
| run2-tbt-10s | continentale | 10 | 12 | 64 | 324 | 260 | 29 |
| run2-tbt-10s | intercontinentale | 10 | 12 | 64 | 327 | 263 | 30 |
| run3-tbt-5s | regionale | 5 | 12 | 98 | 416 | 318 | 36 |
| run3-tbt-5s | nazionale | 5 | 12 | 98 | 415 | 317 | 34 |
| run3-tbt-5s | continentale | 5 | 12 | 98 | 420 | 322 | 38 |
| run3-tbt-5s | intercontinentale | 5 | 12 | 98 | 421 | 323 | 38 |
| run4-tbt-3s | regionale | 3 | 12 | 144 | 531 | 387 | 51 |
| run4-tbt-3s | nazionale | 3 | 12 | 144 | 529 | 385 | 53 |
| run4-tbt-3s | continentale | 3 | 12 | 144 | 537 | 393 | 47 |
| run4-tbt-3s | intercontinentale | 3 | 12 | 144 | 535 | 391 | 50 |
| run5-tbt-2s | regionale | 2 | 12 | 200 | 658 | 458 | 58 |
| run5-tbt-2s | nazionale | 2 | 12 | 200 | 659 | 459 | 60 |
| run5-tbt-2s | continentale | 2 | 12 | 200 | 651 | 451 | 56 |
| run5-tbt-2s | intercontinentale | 2 | 12 | 200 | 655 | 455 | 58 |
| run6-tbt-10s | regionale | 10 | **100** | 152 | 590 | 438 | 50 |
| run6-tbt-10s | nazionale | 10 | **100** | 152 | 598 | 446 | 49 |
| run6-tbt-10s | continentale | 10 | **100** | 152 | 597 | 445 | 48 |
| run6-tbt-10s | intercontinentale | 10 | **100** | 152 | 602 | 450 | 46 |
| run7-tbt7s | (tutte) | — | — | — | — | — | vuota |

Tutti i valori sono letti da `params.dat` e `blocks.json`, non dal nome cartella. Costanti su tutte le 24 run: `mining-diversity = 0`, `mining-turnover = 0.5`, `wpoa-sortition-delta = 0.5`, `wpoa-sortition-lambda = 0.2`, `wpoa-randao-lookback = 1`, `dump-function = none`, `enable-wpoa-malus = true` (registro vuoto), `weight-kappa = 100`, `weight-alpha = 0.2`, `weight-lambda = 0.5`, `wpoa-malus-mu = 0.5`, `wpoa-malus-max = 4`, `p(equiv) = 4`, `p(delay) = 0.25`, treasury `18Qrmh…Dcg`, protocollo `20014`. La pipeline esistente copre run1–run5 (20 run); **run6 non è mai stata analizzata** ed è l'unica in cui il chi-quadro per singola epoca ha attesa minima ≥ 5.

### 2.3 Dove stanno i parametri di configurazione

| simbolo (tesi/prompt) | chiave in `params.dat` (per host, hash-enforced) | flag CLI di `multichain-util create` | template | valore in campagna |
|---|---|---|---|---|
| T_block | `target-block-time` | `set_param` in `prepare_params.sh` | `TARGET_BLOCK_TIME` | 15/10/5/3/2 |
| δ | `wpoa-sortition-delta` | `-wpoasortitiondelta` | `WPOA_SORTITION_DELTA` | 0.5 |
| λ (delay) | `wpoa-sortition-lambda` | `-wpoasortitionlambda` | `WPOA_SORTITION_LAMBDA` | 0.2 |
| k | `wpoa-randao-lookback` | `-wpoarandaolookback` | `WPOA_RANDAO_LOOKBACK` | 1 |
| g(·) | `dump-function` ∈ {none,sqrt,log} | `-dumpfunction` | `WPOA_DUMPFUNCTION` | none |
| malus on/off | `enable-wpoa-malus` | `-enablewpoamalus` | `ENABLE_WPOA_MALUS` | true |
| μ, M_max | `wpoa-malus-mu`, `wpoa-malus-max` | `-wpoamalusmu`, `-wpoamalusmax` | (default) | 0.5, 4 |
| p(κ) | `wpoa-malus-{equiv,delay,selfwrite,badweight}-points` | idem | (default) | 4, 0.25, **`[null]`**, **`[null]`** (nodo: 1, 2 — vedi D4) |
| L | `weight-epoch-length` | `-weightepochlength` | `WEIGHT_EPOCH_LENGTH` / `epochlen=` | 12 (run1–5), 100 (run6) |
| κ, α, λ_w | `weight-kappa`, `weight-alpha`, `weight-lambda` | `-weightkappa` … | `WEIGHT_*` | 100, 0.2, 0.5 |
| treasury | `weight-treasury-address` | `-weighttreasuryaddress` | `config/treasury.json` | 18Qrmh… |
| setup | `setup-first-blocks` | `set_param` | calcolato da `run.sh` | 60…200 |
| spacing | `mining-diversity` | `set_param` | `MINING_DIVERSITY` | 0.0 |
| topologia | `shadow.yaml` → `network.graph.file.path` (.gml generato da `config/levels/<area>.json` via `gen_topology.py`) | — | — | 10 nodi, jitter `0 us` |
| seme | `shadow.yaml` → `general.seed` (60827) e env `POESIA_RNG_SEED` (20260827) | — | `seed=` | 20260827 |
| margine di stabilità | costante C++ `MC_WEIGHT_DEFAULT_STABILITY_MARGIN = 6` (`src/weight_engine/weight_streams.h:147`) | — | — | 6 |

Fonte secondaria di conferma: la riga di avvio nei `debug.log`: `[wPoA] weights-stream ON; … sortition ON (delta=0.5, lambda=0.2); dumping=none`, `[wPoA-malus] ON; mu=0.5; Mmax=4; p(equiv)=4; p(delay)=0.25; p(selfwrite)=1; p(badweight)=2`, `[WeightEngine] ON; epoch-length=100 blocks; kappa=100; alpha=0.2; lambda=0.5; treasury=…`.

### 2.4 Script esistenti

| script | cosa fa | stato rispetto al prompt |
|---|---|---|
| `tools/collect_metrics.py` (429 r.) | a fine run: blocchi, proposer vs ultimo peso, chi-quadro asintotico (rifiuta se E<5), traiettoria pesi, delay/margine G, consistenza, contatori log → `summary.txt` | riepilogo di harness; mescola raccolta e test; usa l'ULTIMO peso |
| `tools/summary_per_epoca.py` (~800 r.) | stesse analisi **per epoca** con peso **vigente**, catena del peso anello per anello, verifica per epoca dai log → `summary_epoche.txt` | importa `analizza_esperimenti`; resa testuale |
| `tools/analizza_esperimenti.py` (2963 r.) | scopre le run, legge `params.dat`, indicizza `txs.log` (altezza di conferma per txid), estrae eventi (ESG, membership, traffico, GAS, riconciliazione), **ricostruisce la catena del peso Cap. 6 e la confronta con lo stream**, quota attesa **per vigenza**, chi² epoca e finestra, account ledger, Gini, integrità, Spearman, ordinamento delay, fit Prop. 5.18, famiglie di confronto → `analisi/` (CSV) | **le tre fasi in un file solo** (D6). Le parti di raccolta/ricostruzione sono verificate e vanno riusate; le parti statistiche vanno spostate in Fase 3 |
| `tools/valida_sortition_montecarlo.py` (288 r.) | reimplementa `ComputeScore` in Python, N estrazioni su scenari + un'epoca reale, chi² | **è il validatore algoritmico standalone di §6.4**: esiste, va riusato (default 10 000 estrazioni, `--estrazioni 100000`) |
| `tools/compare_levels.py` | tabella di confronto fra i 4 livelli dalla run "viva" | riepilogo di harness |
| `tools/role_*.sh`, `sim_common.sh` | ruoli dentro Shadow via curl; `role_admin.sh snapshot` produce `metrics/*.json`; `epoch_watch` (campionamento per epoca) esiste ma **nessuna run archiviata lo ha** | fonte dei dati grezzi |
| `src/wpoa/test/analyze_distribution.py` | chi² per il test funzionale multi-nodo (α=0.001) | non pertinente alla campagna Shadow |
| `shadow/analisi/PROMPT_ANALISI.md` | prompt di analisi della campagna precedente (schema colonne, [M]/[I], checklist) | è l'unico "prompt" trovato: **`prompt_claude_code_v5_dati.md` e `PROMPT_ANALISI_v3_unificato.md` non esistono** nella repo |

Nessuno script implementa: intervalli di Wilson, test multinomiale esatto o Monte Carlo per E_i < 5, KS, Beta(1,n), HHI, coefficiente di Nakamoto, streak Monte Carlo, regressione logit, confronto vincitore osservato vs argmin teorico, verifica di Prop. 5.17.

### 2.5 Formato dei log (`debug.log`, `-debug=wpoa` attivo su tutti i 10 host, timestamp a 1 s)

| riga (tipo) | esempio reale | campi utili | copre |
|---|---|---|---|
| score locale del miner | `mchn-miner: wPoA-sortition height=152 score=4.91116788e-06 delay=14.786s -> start in 14.786s (local=1FFo…)` | altezza, score grezzo, delay a 3 decimali, indirizzo | `score_raw`, `delay_effective` di **ogni** candidato (1 riga/altezza/miner, nessun ricalcolo osservato) |
| retroazione Φ | `[wpoa-sortition] feedback height=151 window=12 mean_spacing=9.833s Tblock=10.000s -> Phi=+0.167s (\|Phi\| <= 5.000s)` | n, finestra, Φ, bound M | `phi_n` |
| verifica del blocco | `[wpoa-sortition] verify OK height=152 signer=1FFo… score=4.91e-06 delay=14s nTime=946686329 parent=946686314` | score del firmatario, `floor(D)`, nTime, nTime del padre | **ricalcolo della barra temporale** `nTime ≥ parent + floor(D)` (prompt §1.2) |
| accettazione | `VerifyBlockMinerWPoA: sortition OK block <hash> (height 152) proposer 1LC9…` | hash, altezza, proposer | blocchi **concorrenti** alla stessa altezza (hash diversi) → `fork_detected` |
| rifiuto (nel codice, **0 occorrenze** nelle run) | `VerifyBlockMinerWPoA: REJECT block <hash> (height N): <motivo>` | motivo ∈ {no signer, invalid signer pubkey, missing VRF reveal, *block mined too early for its sortition score*, invalid VRF reveal, miner X is not the elected proposer Y} | tassonomia reale di `rejection_reason` |
| RANDAO | `[wPoA-RANDAO] seed for height=152 k=1 R_tot[150]=… h[151]=… -> seed=…` | seed | **93 % delle righe** (95 220/102 178 in m1); da saltare in streaming |
| weight engine | `[WeightEngine] epoch 1 (height 105): w_k = 502990 for 1FFo…`; `[WeightEngine] epoch 1: 3 of 3 published weight(s) checked … all matching (0 about another epoch …)`; `… FAILED independent verification`; `… published weights NOT verified` | epoca, peso, esito per nodo | pubblicazione e verifica **per epoca e per nodo** (il RPC `weightverifyweights` conserva solo l'ultima epoca) |
| malus (nel codice, 0 occorrenze) | `[wpoa-malus] height=… epoch=… M=… Psi=… w=… -> w_eff=…` | M, Ψ | correzione per validatore |
| avvio | `[wPoA] … ON …`, `[wPoA-malus] ON; …`, `[WeightEngine] ON; …` | parametri effettivi | conferma di `params.dat` (D4) |

Sorgenti non-log in `metrics/`: `blocks.json` (`listblocks 1-h`: hash, height, miner, time=nTime, txcount), `weights.json` (record `{timestamp,node_address,weight,epoch,height}` + txid), `esg.json`, `membership.json`, `malus.json` (vuoto), `verify.json`, `admin_getinfo.json`, `permissions_mine.json`, `treasury_balance.json`, e CSV senza header `esg_scores`, `membership`, `reconciliation(height,epoch,miner,balance,sent)`, `gas_transfers(height,tipo,host,importo)`, `gas_balances(height,host,balance ~ogni 30 s)`, `traffic(height,host,seq,txid)`, `node_state`. `txs.log` di ogni host dà l'**altezza di conferma** di ogni txid (indice già costruito da `build_tx_index`).

### 2.6 Copertura dei campi richiesti dal prompt (§4.1–§4.3)

Legenda: **P** presente nei grezzi · **D** derivabile senza ambiguità · **A** assente (richiederebbe modifica al nodo o all'harness, fuori scope).

| campo §4.1 (per round × candidato) | stato | fonte / nota |
|---|---|---|
| `experiment_id`, `area`, `target_block_time`, `dumpfunction`, `malus_enabled` | P | `params.dat` (+ `admin_getinfo.json` per controllo) |
| `replication_id` | P | sempre 1: nessuna replica in campagna (D5) |
| `height`, `epoch` (provvisoria/sepolta) | D | `epoch = h // L + 1`; sepolta se `e·L − 1 + 6 ≤ final_height` |
| `candidate_address` | D | `local=` nella riga score; host↔addr da `esg_scores.csv`/`membership.csv` (`shared/` è vuoto, D10) |
| `weight_raw` (vigente) | P | `weights.json` + altezza di conferma da `txs.log`; vale per `h > height_conferma` |
| `weight_effective` = g(w·Ψ) | D | Ψ = 1 e g = identità in tutta la campagna: coincide con `weight_raw` (da mostrare, non assumere) |
| `vrf_output_y_i` | **A** | non loggato. `E_i = score·g(w_eff)` e `u_i = e^{−E_i}` sono derivabili; `y_i` in sé richiederebbe una riga di log aggiuntiva nel nodo |
| `score_raw` | P | riga score (tutti i candidati) |
| `score_norm_i` | D | `1 − e^{−W_tot·score}` con `W_tot = Σ g(w_eff)` sulla mappa vigente (`private_sortition.cpp:160-180`) |
| `delay_base_i`, `phi_n`, `delay_effective_i` | P/D | delay e Φ loggati; base per differenza; il delay ricalcolato dalla pipeline va **confrontato** con quello loggato (controllo di coerenza del modello) |
| `is_winner`, `actual_proposer_address` | P | `blocks.json` |
| `network_latency_ms`, `jitter_ms` | **A** | log a 1 s, nessun `-logtimemicros` nel fork, `dTimeReceived` non loggato; jitter GML `0 us`. Disponibile solo la matrice RTT deterministica dal `.gml` (§5.6) |
| `block_accepted`, `rejection_reason` | D | REJECT (6 motivi, 0 osservati) + "blocco concorrente non canonico" (hash `sortition OK` non in `blocks.json`) |
| `fork_detected`, `fork_group_id` | D | run6/regionale: 29 altezze con blocchi concorrenti su 438 misurate; 16 delle 38 inversioni coincidono con un fork |
| `balance_snapshot` | P (campionato) | `gas_balances.csv` ~ogni 30 s simulati: si prende il campione più recente ≤ height, con l'altezza del campione dichiarata |
| `consecutive_wins_streak_position` | D | dalla sequenza canonica |

| campo §4.2 (per epoca × cluster) | stato | fonte / nota |
|---|---|---|
| `epoch`, `epoch_start_height`, `epoch_end_height`, `epoch_buried` | D | mappa unica §5.5 |
| `cluster_id`, `esg_score_miner`, lista `{company_id, esg, tau_i}` | P/D | `esg.json`, `membership.json`, `traffic.csv` + `txs.log` (già in `peso_riconciliazione.csv`) |
| `tau_miner`, `theta_epoch` | D | **Θ secondo il codice** = Σ τ delle sole aziende in cluster (D1) |
| `W_k`, `A_k`, `R_k`, `B_k`, `rho_k`, `w_k`, `w_k_prev` | D | `compute_weight_reconciliation` (verificato vs `verify.json` e vs `[WeightEngine] epoch N` per nodo) |
| blocchi del miner nell'epoca con incremento di saldo | parziale | `initial-block-reward = 0` → nessun premio; la fee è attribuibile solo all'**intervallo** fra due campioni di saldo (`account_ledger.csv`), non al singolo blocco |
| `malus_accumulator_M`, `psi`, eventi | P (vuoti) | `malus.json = []` in tutte le run: colonne presenti, valori M = 0, Ψ = 1, lista vuota |

| campo §4.3 (per esperimento) | stato |
|---|---|
| tutti i parametri di catena | P (`params.dat`), tranne `p_selfwrite`, `p_badweight` = `[null]` → dal log di avvio (D4) |
| topologia (area, n nodi, seed), durata (altezza finale) | P (`config/levels`, `shadow.yaml`, `final_height.txt`) |

### 2.7 Volume dei dati

2.2 GB in `shadow/`, di cui **904 MB di `debug.log`** su 24 run (54–283 MB per run; il miner più pesante 28 MB / 102 k righe). Il 93 % delle righe è RANDAO e si scarta al primo confronto di sottostringa. `metrics/` pesa < 0.5 MB per run. L'output di Fase 1 stimato: ~1 400 righe candidato-round per run (≈ 35 k in totale), quindi **nessun problema di memoria**: basta il parsing in streaming riga per riga (già così negli script esistenti). Ambiente Python 3.10: `pandas 1.3.5`, `numpy 1.21.5`, `scipy 1.8.0`, `openpyxl 3.1.5`, `matplotlib 3.5.1`, `networkx 2.4`; **`pyarrow` assente** (niente Parquet senza installazione).

---

## 3. Verifica del modello implementato (prompt §2)

* `WPoASelector::ComputeScore` (`wpoa_selector.h:187`): `u = (top64(HMAC-SHA256(seed, addr)) + 1)/2^64`, `E = −ln u`, `score = E / ApplyDumping(w)`; `SelectProposer` = argmin con tie-break sull'indirizzo minore. `ApplyDumping`: `none → w`, `sqrt → √w`, `log → ln(1+w)`.
* Sortition privata (`private_sortition.h:284`): `norm = 1 − e^{−W·score}`, `D = T + δT(2·norm − 1) + λΦ`, clamp `[0, 100000]`; `W = Σ_j g(w_j·Ψ_j)` sommata in ordine di indirizzo; verifica lato validatore `nTime ≥ parent.nTime + ⌊D⌋`.
* Φ (`private_sortition.cpp:~90-120`): media mobile su 12 blocchi dei **timestamp di header**, clippata a `±min(T/2, T(1−δ)/λ)`. Identica su tutti i nodi per costruzione (verificabile in Fase 2 confrontando i log dei tre miner alla stessa altezza).
* Peso: `w_eff = w·Ψ` **poi** `g(w_eff)` (`wpoa_selector.cpp:100`, `private_sortition.cpp:172`), coerente con la tesi §5.11.3 e con la pipeline.

Conclusione: **l'implementazione è quella di §1.1 del prompt**. Il chi-quadro misura la deviazione indotta dal canale, non la proporzionalità in astratto.

---

## 4. Discrepanze e gap trovati (segnalati, non risolti)

| # | tema | tesi / prompt | codice C++ | pipeline esistente | proposta (da confermare) |
|---|---|---|---|---|---|
| **D1** | definizione di Θ^(e) | Def. 6.6: numero **totale** di transazioni confermate nell'epoca, ognuna contata una volta (prompt §1.3 idem) | `WeightEngine::NetworkActivity` (`weight_engine.h:283-299`): `Σ_k Σ_{i∈C_k} τ_i` — solo aziende in cluster; esclusi τ dei miner, tx di admin/ca, riconciliazioni | segue il codice | ricalcolare con la formula del **codice** (è l'unica che riproduce i pesi pubblicati) e riportare **anche** Θ_tesi in colonna separata, con nota |
| **D2** | valore pubblicato | Def. 6.9: si pubblica `w_k^(e)`; §7.2: "arrotonda per eccesso" | `ToIntegerWeight(w, scale)` = `round-half-away(w·κ)` clamp `[1, 2^32−1]` (`weight_engine.h:264`); il fattore `scale` è κ | `floor(w·κ + 0.5)` (equivalente per w > 0) | trattare il codice come riferimento; annotare che il peso on-chain è `w_k·κ` arrotondato |
| **D3** | mappa altezza→epoca | `⌊n/L⌋ + 1` | `height / L + 1` (`weight_engine.h:465`); ma il testo di aiuto in `params.dat` dice `height / this` | `h // L + 1` | codice = tesi; solo il testo di aiuto è sbagliato. Una sola funzione in `comune.py` (§5.5) |
| **D4** | `p(selfwrite)`, `p(badweight)` | prompt §4.3 li chiede da configurazione | `params.dat` li scrive `[null]` (parametri STRING senza default in `paramlist.h:224-231`); il nodo applica 1 e 2 e lo logga in `[wPoA-malus] ON; …` | `run_index.csv` riporta `[null]` | leggere `params.dat`, **sovrascrivere dal log di avvio** e riportare entrambe le fonti in `config` |
| **D5** | gerarchia e repliche | area → tbt → replica | — | `runN-tbt-Ts/<area>`; regex `^run(\d+)-tbt-(\d+)s$` | gerarchia reale run → area; `replication_id = 1`; il manifest porta L, setup e tutti i parametri; `run7-tbt7s` (vuota, nome fuori pattern) va rinominata o ignorata esplicitamente |
| **D6** | separazione delle fasi (regola 4) | fasi separate | — | `analizza_esperimenti.py` fa raccolta + ricostruzione + test | estrarre le funzioni pure in `pipeline/comune.py`, lasciare lo script legacy intatto (§5.9) |
| **D7** | dimensioni `dumpfunction` e malus | trattate come variabili per esperimento | — | tutte le 24 run: `none` e registro vuoto | §6.1.9, §6.3.4, §6.3.5 → "non calcolabile: …". La pipeline resta pronta per run future con `WPOA_DUMPFUNCTION=sqrt\|log` |
| **D8** | rumore di rete σ | latenza/jitter additivi a media nulla | Shadow: jitter `0 us` su ogni arco; log a 1 s; barra temporale a secondi interi | `frazione_G_sotto_100ms` vs `1/Δmax` | il rumore osservato (scarti 0.01–1.6 s) è quantizzazione, non rete: σ va stimato da quello (§5.6) |
| **D9** | duplicato | — | — | `shadow/tools/analisi/` copia stale di `shadow/analisi/` | rimuovere o ignorare (decisione utente) |
| **D10** | `shared/*.addr` | — | — | vuoto nelle run archiviate; `extract_host_maps` già ricostruisce da ESG/membership | riusare |
| **D11** | ipotesi iid-uniforme di Prop. 5.18 | la tesi stessa (§5.10.5) la dichiara valida solo per pesi non concentrati | — | — | eseguire il KS vs `Beta(1,n)` come richiesto **e** il confronto con la predizione esatta via Monte Carlo sui pesi reali (§5.4) |
| **D12** | `weightverifyweights` per epoca | — | il RPC riporta solo l'ultima epoca; `epoch_watch` esiste nell'harness | nessuna run archiviata ha `metrics/epoche/` | usare le righe `[WeightEngine] epoch N: … checked …` dei log (già fatto da `summary_per_epoca`) |
| **D13** | verifica eventi `Delay` (prompt §1.2) | ricalcolare D dai grezzi per ogni evento | nessun evento in campagna | — | applicare il ricalcolo della barra temporale a **tutti** i blocchi (dati presenti nelle righe `verify OK`): 0 violazioni su 4 run controllate in ricognizione |
| **D14** | scala Wilson/α | prompt: Wilson 95 %, chi² con E_i ≥ 5 | — | soglia 5 e critici al 5 % tabulati | confermare α = 0.05, MC N = 20 000, multinomiale **esatto per enumerazione** con 3 classi (fattibile fino a B ≈ 1000) |

---

## 5. Checkpoint di design

### 5.1 Struttura dei file proposta

```
shadow/tools/pipeline/
├── __init__.py
├── comune.py              lettura parametri (params.dat + admin_getinfo + righe ON dei log), mappa altezza→epoca e
│                          vigenza (UNICA), g(), Ψ, regex dei log, lettura streaming, mappa host↔indirizzo, indice txs.log
├── fase1_raccolta.py      grezzi → risultati/<run>/<area>/fase1/*.csv + manifest.json   (solo estrazione)
├── fase2_aggregazione.py  fase1 → fase2/*.csv   (ranking, margini, vigenza, flag di coerenza; nessun test)
├── fase3_analisi.py       fase2 → fase3/<run>__<area>.xlsx (+ csv per foglio)   (test statistici)
├── stat/                  wilson.py, gof.py (chi² / multinomiale esatto / MC), timer_race.py (KS, Beta(1,n), MC esatto,
│                          bound 5.18, Prop. 5.17), concentrazione.py (HHI, N_eff, Nakamoto, Gini), streak.py, longitudinale.py
└── run_pipeline.py        orchestratore: --fase 1|2|3|tutte, --root, --out; ogni fase rieseguibile da sola

shadow/tools/valida_sortition_montecarlo.py   riusato com'è (test algoritmico di §6.4), invocato da fase3 solo per
                                              riportarne l'output nel foglio "note", non reimplementato
shadow/risultati/                             nuova radice di output (nome da confermare, Q1)
├── manifest_campagna.json                    gerarchia run → area → epoche → parametri (prompt §4.4)
├── campagna.xlsx                             confronti fra esperimenti (famiglie a un solo parametro variato)
└── <run>/<area>/{fase1,fase2,fase3}/
```

`analizza_esperimenti.py`, `summary_per_epoca.py`, `collect_metrics.py` restano **intatti** (continuano a servire `run.sh`). Le funzioni pure oggi dentro `analizza_esperimenti.py` che servono alla nuova pipeline (`parse_params_dat`, `build_tx_index`, `extract_host_maps`, `extract_event_tables`, `_weight_records`, `_inforce_shares`, il fold di `compute_weight_reconciliation` **senza** le colonne chi²) vengono importate da `comune.py`; se si preferisce la separazione fisica, vengono spostate e lo script legacy le reimporta (Q2).

### 5.2 Fase 1 — file grezzi (un set per `<run>/<area>`, colonne in inglese snake_case come nel prompt §4)

* `config.csv` — 1 riga: tutti i parametri di §4.3 + colonna `source` per ciascuno (`params.dat` / `admin_getinfo` / `debug.log:[wPoA-malus] ON` / `shadow.yaml` / `config/levels`) + `final_height`, `n_nodes`, `rng_seed`, `shadow_seed`, `rtt_max_ms`.
* `candidates_round.csv` — 1 riga per (height, candidato con peso): `experiment_id, replication_id, area, target_block_time, dumpfunction, malus_enabled, height, epoch, epoch_buried, candidate_host, candidate_address, weight_raw_inforce, weight_record_epoch, weight_record_confirm_height, psi, weight_effective, W_tot_effective, score_raw, E_i, u_i, score_norm, phi_n, delay_logged, delay_recomputed, delay_mismatch_s, is_winner, actual_proposer_address, actual_proposer_host, block_hash, block_time, parent_time, verify_delay_floor, verify_score, time_bar_ok, fork_detected, n_competing_blocks, competing_hashes, rejection_reason, balance_gas_sample, balance_sample_height, streak_position`.
* `blocks.csv` — 1 riga per blocco canonico: `height, hash, miner_address, miner_host, time, txcount, dt_prev_s, epoch, in_setup, n_competing_blocks`.
* `competing_blocks.csv` — hash non canonici visti da ogni nodo con altezza e proposer (da `sortition OK`).
* `phi.csv` — Φ per altezza e per nodo che l'ha calcolato (per il controllo di identità fra nodi).
* `rejects.csv` — righe REJECT (attese 0) con motivo.
* `weights_stream.csv`, `esg.csv`, `membership.csv`, `traffic_events.csv`, `gas_transfers.csv`, `gas_balances.csv`, `reconciliation.csv`, `malus_events.csv` (header solo), `verify_per_epoch_log.csv`, `weight_engine_publications_log.csv`.
* `topology_latency.csv` — matrice RTT/one-way fra host dal `.gml` (per S1 di §5.6).
* `manifest.json` — gerarchia e parametri dell'esperimento (§4.4).

Nessuna aggregazione, nessuna statistica. Ogni riga è riconducibile a una riga di log o a un record on-chain (colonna `source_file`/`source_line` dove il costo è trascurabile).

### 5.3 Fase 2 — dataset analizzabili

* `round_level.csv` — 1 riga per round misurato: `height, epoch, n_candidates, winner_observed, winner_theoretical_argmin, winner_matches_theoretical_argmin, observed_winner_rank, margin_G_logged, margin_G_recomputed, inversion_gap_s (D_obs − D_min), score_gap_2_1 (score(2)−score(1), per Prop. 5.17), W_tot_minus_winner, fork_detected, dt_prev_s, phi_n, phi_identical_across_nodes, streak_length_so_far`.
* `candidates_long.csv` — Fase 1 arricchita con `candidate_rank_by_score`, `candidate_rank_by_delay`, `p_theoretical_inforce = w_eff/W_tot`.
* `epoch_level_wpoa.csv` — 1 riga per (epoca, validatore): `epoch, epoch_buried, n_blocks_epoch, O_i, p_theoretical_blockweighted (media sui blocchi dell'epoca della quota vigente), w_eff_start, w_eff_end, delay_mean/min/max/pos_in_band, n_rounds_theoretical_argmin, n_rounds_theoretical_argmin_lost (base del MissedTurnRate), n_forks, n_rejects`.
* `epoch_level_weight_engine.csv` — 1 riga per (epoca, cluster): tutte le colonne della catena del peso (ESG, τ, c_i, Θ_code, Θ_thesis, W_k, A_k, R_k, B_k, ρ_k, ρ_k(e−1), w_k published, w_k recomputed, recompute_match, w_k_prev, M, Ψ) **senza** colonne di test.
* `balance_by_height.csv` — traiettoria del saldo per miner (campioni + movimenti noti).
* `malus_epoch.csv` — header con M, Ψ, eventi (vuoto in campagna).

Solo derivazioni deterministiche.

### 5.4 Fase 3 — fogli per esperimento (`<run>__<area>.xlsx`, un tab per foglio + CSV gemello)

Ogni tab ha in testa la riga dei parametri (§6.4). Ogni metrica non calcolabile riporta la stringa `non calcolabile: <motivo>`.

**Tab `wPoA_epoca`** (una sezione per epoca, come da §6.1):
1. tabella `w_eff`, `p_i`; 2. GoF: chi² asintotico se `min E_i ≥ 5`, altrimenti **multinomiale esatto per enumerazione** (3 classi, `C(B+2,2)` composizioni) o Monte Carlo (N = 20 000) se le classi sono > 3; colonna `gof_method` sempre presente; 3. Wilson 95 % per ogni `p̂_i`; 4. `MAE_p`, `MaxAE_p`, `TV`; 5. **timer race**: KS di `G` vs `2Δmax·Beta(1,n)` (n = candidati) **e** KS vs distribuzione di `G` simulata esattamente con i pesi vigenti (E_i ∼ Exp(1), stesso W_tot, stesso ψ) per superare D11; verifica di Prop. 5.17: `score(2)−score(1) | vincitore ~ Exp(W − w_i*)` (KS per classe di vincitore, sfrutta gli score di tutti i candidati); `p̂_inv = Pr[vincitore osservato ≠ argmin]` con Wilson, confrontata col bound `(3/2)(nσ/Δmax)^{2/3}` per **ciascuna** stima di σ dichiarata (§5.6), e con la frazione di inversioni coincidenti con un fork; 6. HHI, `1/HHI`, coefficiente di Nakamoto (1/3, 1/2, 2/3) su `p̂` e su `p`; 7. `L_max`, `Pr[w_t = w_{t−1}]` osservati vs Monte Carlo della sola sortition con i pesi vigenti round per round (N = 10 000); 8. liveness: `BlockSuccessRate = canonici/(canonici + concorrenti non canonici)`, percentili di `InterBlockTime` (mediana, p95, p99), `MissedTurnRate_i` (definizione in Q7), conteggio dei REJECT per motivo e dei blocchi concorrenti; 9. malus: `non calcolabile: nessun evento nel registro`; in sostituzione la **verifica universale della barra temporale** (D13) con conteggio delle violazioni.

**Tab `wPoA_longitudinale`** (§6.2): per validatore `p(e_0)`, `p(e_fin)`, `p̂(e_0)`, `p̂(e_fin)` con Wilson, `Gain_i`, test di monotonicità (peso cresciuto ⇒ `p̂` cresciuta?), regressione `logit(p̂_i) ~ β0 + β1·log(w_eff_i)` sui punti (epoca × validatore) con IC di β1, e confronto `log(p̂_i/p̂_j)` vs `log(w_i/w_j)` per coppia ed epoca.

**Tab `WeightEngine_epoca`** (§6.3): tabella per cluster; Spearman **ritardata** `ρ_k(e)` vs `w_k(e+1)` (con nota: il fattore `[ρλ_w + 1 − λ_w]` è deterministico, quindi si riporta anche `ρ_k(e)` vs `w_k(e+1)/W_k(e+1)` come controllo tautologico) e la dichiarazione che il traffico è **esogeno** (verificato in `role_company.sh:52-65`); Gini su `w_k` vs `gini_atteso_da_input` (su `W_k`) e `Δ`; effetto smorzamento: `non calcolabile: dumpfunction=none in tutta la campagna`; traiettoria malus: `non calcolabile: registro vuoto`.

**Tab `config`**, **tab `manifest`**, **tab `note_metodologiche`** (caveat su jitter Shadow, sorgente di σ, E_i < 5, elenco dei "non calcolabile", riferimento all'output di `valida_sortition_montecarlo.py` come test di livello algoritmico separato).

**`campagna.xlsx`**: le stesse metriche per esperimento affiancate lungo le famiglie a un solo parametro variato (tbt a area fissa; area a tbt fisso; L a tbt fisso per run2 vs run6), riusando la logica di `build_families`.

### 5.5 Mappa altezza→epoca e vigenza (unica per i due moduli)

In `comune.py`:
* `epoch_of(h) = h // L + 1` (= `weight_engine.h:465` = tesi); l'epoca `e` copre `[(e−1)L, eL−1]`;
* `epoch_buried(e, tip) = tip ≥ eL − 1 + 6`;
* vigenza del peso: il record con altezza di conferma `h_c` vale per i blocchi `h > h_c` (come `_inforce_shares`); la quota attesa per epoca è la **media sui blocchi** delle quote vigenti blocco per blocco, mai il peso marcato `e`;
* Ψ dell'epoca `e−1` si applica ai blocchi dell'epoca `e` (Def. 5.24), stessa mappa.

### 5.6 Stima di σ per il test di Prop. 5.18 (tutte e tre riportate, ciascuna con la sua fonte)

| stima | fonte | cosa misura | atteso in campagna |
|---|---|---|---|
| **S1 topologia** | matrice one-way/RTT dal `.gml` (deterministica; jitter `0 us`) fra le coppie di miner | la latenza di propagazione; **non** una varianza (nessun jitter modellato) | 1–56 ms one-way |
| **S2 scheduler (empirica)** | distribuzione di `block_time − parent_time − D_logged(vincitore)` su tutti i round, e di `inversion_gap_s` sui round invertiti | il rumore effettivo che decide la corsa: quantizzazione a 1 s della barra temporale e dei timestamp, granularità del loop del miner | 0.3–0.6 s mediana, coda a 1.6 s |
| **S3 packet loss** | non osservabile dai grezzi | — | `non calcolabile` |

Proposta: **S2 come stima primaria** per il bound (è quella che spiega le inversioni osservate: a tbt 15 s con RTT 10 ms si osservano 12 inversioni su 107 round), S1 riportata accanto per mostrare che la geografia è due ordini di grandezza sotto. Ogni foglio dichiara quale σ ha usato.

### 5.7 Formato di output

Excel (`openpyxl` presente) **un file per esperimento** con i tab di §5.4 e, accanto, un CSV per tab (diff-abile, leggibile da script); più `campagna.xlsx` e `manifest_campagna.json`. Parquet escluso (`pyarrow` assente e volume di ~35 k righe non lo richiede).

### 5.8 Cosa richiederebbe modifiche al nodo o all'harness (fuori scope, segnalato)

* `y_i` della VRF nel log dello score; * timestamp di log sub-secondo (`-logtimemicros` non esiste nel fork) e tempo di ricezione del blocco (`dTimeReceived`) per una latenza per evento; * `weightverifyweights` per epoca in run archiviate (l'harness `epoch_watch` lo fa già per le run future); * run con `dumpfunction ∈ {sqrt, log}` e run con violazioni di malus indotte, per rendere calcolabili §6.3.4, §6.3.5, §6.1.9; * repliche a seme diverso.

### 5.9 Riuso vs riscrittura

Riusati: indice `txs.log`, estrazione eventi, ricostruzione della catena del peso, quota per vigenza, mappa host↔indirizzo, `valida_sortition_montecarlo.py`, logica delle famiglie di confronto. Nuovi: parsing di **tutti** i candidati per round (oggi solo il margine), verify-line e blocchi concorrenti, Φ per nodo, e l'intero strato statistico di Fase 3. Gli script legacy non vengono toccati.

---

## 6. Domande aperte (da chiudere prima di scrivere codice)

1. **Radice di output**: `shadow/risultati/` (proposta) o dentro `shadow/analisi/`? E `shadow/tools/analisi/` (duplicato stale, D9): rimuoverla?
2. **Riuso di `analizza_esperimenti.py`** (D6): (a) importarlo come libreria da `comune.py` senza toccarlo; (b) spostare le funzioni pure in `comune.py` e farle reimportare dallo script legacy; (c) duplicare il minimo indispensabile. Raccomando (b).
3. **Θ** (D1): la Fase 2 ricalcola con la formula del codice (unica che riproduce i pesi pubblicati) e affianca Θ_tesi in colonna separata. Va bene, o la tesi va allineata al codice?
4. **Peso intero ×κ** (D2): trattare il codice come riferimento e annotarlo nel foglio?
5. **Punteggi malus `[null]`** (D4): accettare il valore dal log di avvio come fonte, dichiarandolo?
6. **σ** (D8, §5.6): S2 primaria, S1 accanto?
7. **Definizioni di liveness**: `MissedTurnRate_i = (round in cui i era argmin teorico ma non ha proposto) / (round in cui i era argmin teorico)`; `BlockSuccessRate = canonici / (canonici + concorrenti non canonici)`. Confermate?
8. **run6** (L = 100) entra nella campagna? **run7-tbt7s** vuota: la ignoro con avviso, o va rimossa/rinominata?
9. **Test Beta(1,n)** (D11): KS vs `Beta(1,n)` **più** KS vs Monte Carlo esatto sui pesi reali?
10. **Costanti statistiche** (D14): α = 0.05, Wilson 95 %, MC N = 20 000 (GoF) e 10 000 (streak), multinomiale esatto per enumerazione con 3 classi?
11. **Nomi colonna** in inglese snake_case (come §4 del prompt) nella nuova pipeline, documentazione in italiano?
12. **Repliche**: `replication_id = 1` ovunque (D5). Pianificare run a seme diverso è fuori da questo prompt: solo predisporre il campo?
13. Il prompt cita `prompt_claude_code_v5_dati.md` e `PROMPT_ANALISI_v3_unificato.md`: non esistono nella repo. Esistono altrove?

---

## 7. Criteri di accettazione del checkpoint (prompt §8)

| criterio | dove risposto |
|---|---|
| campi §4.1–4.3 già raccolti / mancanti / richiedono ricompilazione | §2.6, §5.8 |
| mappa altezza→epoca coerente fra i moduli | §5.5 (una sola funzione, D3) |
| stima di σ dato il caveat sul jitter | §5.6 (S1/S2/S3, tutte dichiarate) |
| formato di output e motivazione | §5.7 |
| domande aperte non risolvibili dalla sola ricognizione | §6 |
