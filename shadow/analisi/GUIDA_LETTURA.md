# Guida di lettura delle tabelle di `analisi/`

Riferimento rapido per chi conosce il progetto POESIA / wPoA e vuole leggere i
risultati senza tornare alla tesi. Le tabelle sono prodotte da
`tools/analizza_esperimenti.py`; la semantica completa di ogni meccanismo sta in
`shadow/README.md`.

---

## Glossario

| termine | in una riga |
|---|---|
| **epoca** | blocco di `weight-epoch-length` altezze (qui 12): `epoca(h) = h/12 + 1`. I pesi si ricalcolano una volta per epoca, non a ogni blocco |
| **peso grezzo** `W_k` | quanto vale il cluster del miner `k` in una data epoca: ESG del miner × (sua attivita' + contributi delle sue aziende) |
| **peso** `w_k` | il peso grezzo dopo la retroazione inter-epoca: `w_k = W_k·[ρ·λ_w + (1−λ_w)]`. E' il valore **pubblicato** su `wpoa-weights`, ed e' quello nelle tabelle |
| **peso efficace** `g(w)` | il peso dopo la funzione di smorzamento anti-whale (`sqrt`, `log`). Con `dump_function = none` coincide col peso |
| **peso effettivo** `w_eff` | il peso dopo il malus comportamentale: `w_eff = w·Ψ`. Senza malus registrati, `Ψ = 1` e coincide col peso |
| **score** | `E_i / w_i` con `E_i ~ Exp(1)` derivata dalla VRF del validatore. Vince chi ha lo score **piu' basso** |
| **score normalizzato** | `1 − exp(−W_tot·score)` ∈ (0,1). Dipende solo dal **rapporto** `W_tot/w_i`, non dalla scala assoluta dei pesi |
| **delay** `D_i` | `T + Δmax·(2·score_norm − 1) + λΦ`. Il timer che ogni candidato avvia: chi lo fa scadere per primo propone |
| **Δmax** | mezza ampiezza della banda dei delay, `δ·T`. Con `δ = 0.5` e `T = 15 s` vale 7.5 s, e i delay cadono in [7.5, 22.5] s |
| **margine** `G` | `D(2) − D(1)`: di quanto il vincitore batte il secondo. Se scende sotto la varianza di rete, vince la latenza e non lo score |
| **`ρ_k`** | tasso di conformita': quanta parte della propria allocazione il cluster ha riconciliato al treasury. E' l'unico canale con cui il comportamento di un'epoca influenza il peso della successiva |
| **Spacing** | vincolo nativo di MultiChain: `ceil(d·(N−1))` blocchi obbligatori fra due blocchi dello stesso firmatario. Con `mining-diversity = 0` vale 0 ed e' inerte |
| **malus** | riduzione del peso per violazioni provate on-chain (doppia proposta, delay violato, auto-attestazione falsificata, peso non ricalcolabile) |
| **finestra misurata** | i blocchi oltre `setup_blocks`: solo li' la wPoA governa la selezione. Prima e' PoA nativa e non va misurata |

---

## Le colonne, tabella per tabella

### `run_index.csv` — l'anagrafica

Una riga per run. Le colonne `chain_name … first_block_reward` sono lette
**dal `params.dat` sigillato alla genesi**, non dal nome della cartella.

* `tbt_dirname` vs `tbt_params` — il primo viene dal nome `runN-tbt-Ts`, il
  secondo da `params.dat`. **`tbt_mismatch = 1` significa che la run e'
  etichettata male** e ogni confronto per `tbt` che la include e' falsato.
* `setup_blocks` / `setup_mismatch` — analogo, incrociando `params.dat` con
  `setupblocks` di `getinfo`.
* `mining_diversity_val` — deve essere `0.0`. Se non lo e', lo Spacing nativo e'
  attivo e la distribuzione dei proposer **non** e' quella della wPoA (vedi
  sotto, *alternanze*).
* `stato` — `completa` / `parziale` / `incompleta` / `errore`; `note` dice
  perche'.
* `malus_events_found` — record trovati sul registro dei malus. Zero ovunque
  significa che il meccanismo esiste ma **non e' stato esercitato**: e' un
  limite dichiarato della campagna, non un successo.

### `block_times.csv` — il ritmo della catena

`dt_medio_s` contro `target_s`, con `scarto_s` e `scarto_pct`. `dt_sd_s` e' la
deviazione standard (popolazione) degli intervalli.

Uno scarto **positivo e costante** su tutte le run e' l'artefatto `vdso` del
simulatore (vedi *Come distinguere simulatore e protocollo*). Uno scarto che
**oscilla di segno** fra run vicine e' la retroazione `λΦ` con un guadagno
troppo aggressivo.

### `proposers.csv` — chi ha proposto, e quanto avrebbe dovuto

`quota_osservata` = `blocchi / totale misurati`; `quota_attesa` =
`peso_ultimo / Σ pesi`, cioe' la previsione del Teor. 5.3.

Le colonne `delay_*` vengono dai `debug.log` dei miner. **`delay_medio_s` deve
risultare ordinato per peso decrescente**: il miner piu' pesante ha il delay piu'
corto. Se non lo e', c'e' un problema nella catena score → delay, non nella
statistica.

`delay_pos_in_banda` dice dove cade il delay medio dentro [T−Δmax, T+Δmax]:
0 % = sempre il primo a proporre, 100 % = sempre l'ultimo.

### `chisq.csv` — il test

`chi2_summary` e' il valore prodotto dalla run; `chi2_ricalcolato` esiste solo
se hai passato `--recompute-chisq`, ed e' una **controprova indipendente**:
`scarto_ricalcolo` deve essere nell'ordine dell'arrotondamento (10⁻⁴).

`compatibile_summary = 1` significa `chi-quadro ≤ 5.991` (df = 2, soglia al 5 %).

**`campione_sufficiente` va guardato per primo.** Vale 1 solo se ogni miner ha
almeno 5 blocchi attesi. Se vale 0, il test **non e' applicabile** e il suo
esito non e' un risultato ne' in un senso ne' nell'altro: serve una run piu'
lunga.

### `alternanze.csv` — la firma dello Spacing

`consecutivi_osservati` contro `consecutivi_attesi` (= `Σ p_i²·(n−1)`).

**Zero osservati con attesi ben sopra zero non e' un esito statistico**: e' un
vincolo di alternanza attivo. E' precisamente cosi' che nel progetto e' stato
scoperto che lo Spacing di `mining-diversity` resta vincolante sotto wPoA:
con `d = 0.3` si osservavano 0 alternanze su 380 blocchi contro ~34 attese per
livello, e la distribuzione collassava su un round robin qualunque fossero i
pesi. Con `mining-diversity = 0` il vincolo e' inerte e i due numeri tornano
confrontabili.

### `sortition_margins.csv` — quanto e' stretta la corsa

`G_mediano_s` e' il distacco tipico fra vincitore e secondo. **In secondi non e'
confrontabile fra `tbt` diversi** (la banda cambia): per il confronto usa
`G_mediano_su_Dmax`, che e' adimensionale.

`frazione_G_sotto_100ms` e' la frazione di round in cui il margine e'
dell'ordine della latenza di rete. E' l'indicatore diretto del regime della
Prop. 5.18: quando cresce, il vincitore osservato inizia a differire da quello
designato dallo score.

### `weights_trajectory.csv` e `epoch_shares.csv` — l'evoluzione

`weights_trajectory` e' un record per pubblicazione (`epoca`, `peso`, `height`).
Una **casella mancante per un'epoca significa "invariato"**: il registro non
ripubblica un peso uguale al precedente.

`epoch_shares` incrocia, per ogni epoca, la quota di blocchi effettivamente
minati (`quota_osservata_epoca`) con la quota di peso in vigore in
quell'epoca (`quota_peso_epoca`). **E' la tabella corretta quando i pesi si
muovono**, perche' `quota_attesa` in `proposers.csv` usa l'ultimo peso e
schiaccia tutta la storia su un solo valore.

`rapporto_Wtot_su_wi` e' il numero che governa la saturazione: quando e' grande,
lo `score_norm` di quel candidato satura verso 1.

**L'epoca 1 va sempre trattata a parte**: i pesi partono tutti a 1 perche' non
c'e' ancora attivita' osservata, e la distribuzione e' uniforme per costruzione.

### `forks.csv` — la catena ha tenuto?

`teste_distinte` = best-hash diversi a fine run. Il `verdetto` distingue quattro
casi, in ordine di gravita':

* `nessun fork` — una sola testa;
* `ritardo di propagazione` — teste diverse ma altezze a ≤ 1 blocco di distanza
  e stesso hash sepolto: normale, non e' un fork;
* `corsa al tip` — teste diverse, stesso hash sepolto: si risolve da sola;
* `fork persistente` — teste **e** hash sepolti diversi: e' un problema vero.

### `gas.csv`, `esg.csv`, `verify.csv`

`gas.csv` traccia distribuzione, rifornimenti automatici e riconciliazione per
miner: `riconciliato_m1/m2/m3` sono l'input osservabile di `ρ_k` (per costruzione
i tre miner riconciliano al 95 / 60 / 20 %).

`verify.csv` riporta l'esito di `weightverifyweights`: `verificato = 1` e
`non_validi = 0` significa che ogni nodo ha ricalcolato indipendentemente i pesi
pubblicati e li ha confermati. **E' la verifica della Sez. 5.11.1**, ed e' un
risultato a se' stante: senza di essa il registro sarebbe una dichiarazione.

---

## Come interpretare il chi-quadro in questo contesto

Il test confronta la distribuzione osservata dei blocchi con quella prevista dai
pesi (`Pr[i eletto] = w_i/W`, Teor. 5.3). Tre avvertenze, in ordine di
importanza:

1. **serve un campione minimo.** Con 3 miner servono ≥ 5 blocchi attesi
   ciascuno. Con quote molto sbilanciate (un miner al 70 %, uno al 7 %) il
   vincolo lo detta il piu' debole: possono servire diverse centinaia di blocchi.
   `campione_sufficiente` risponde a questa domanda.
2. **usa l'ULTIMO peso pubblicato.** Se la traiettoria mostra pesi che si
   muovono molto, il test misura la distribuzione di tutta la finestra contro un
   peso valido solo alla fine. Va letto **insieme** a `epoch_shares.csv`, non al
   posto di essa. Se i due danno risposte diverse, la risposta buona e' quella
   per epoca.
3. **"non compatibile" non significa "il protocollo e' rotto".** Significa che i
   dati sono improbabili sotto l'ipotesi che la selezione segua i pesi. Le cause
   candidate sono, in ordine: Spacing residuo, saturazione dello score, margine
   `G` sotto la varianza di rete, campione insufficiente. Solo dopo averle
   escluse si parla di difetto del protocollo.

---

## Come distinguere un artefatto del simulatore da un effetto del protocollo

| sintomo | simulatore | protocollo |
|---|---|---|
| block time medio sopra il target | offset **costante e sempre positivo**, presente in tutte le run allo stesso modo: e' la latenza `vdso` che Shadow addebita alle chiamate di orologio | oscillazione che **cambia segno** fra run vicine: e' `λΦ` con guadagno troppo alto (Sez. 5.10.4) |
| verifica | ripeti la stessa run con `vdso=5us` e `vdso=50us`: se la media si sposta, e' il simulatore | ripeti con `wpoasortitionlambda=0`: se l'oscillazione sparisce, era la retroazione |
| fork alla stessa altezza | contesa reale su CPU fra processi simulati | `Δmax` troppo stretto per la latenza (Prop. 5.18) — deve crescere al calare di `tbt` |

Il `jitter` degli archi e' **0 in tutti i `.gml`**: il campo non e' implementato
da Shadow. La variabilita' osservata viene dai percorsi, dal `packet_loss`
stocastico e dalla contesa sulle risorse, non da un jitter modellato.

---

## Checklist: leggere una run nuova

Nell'ordine. Ogni passo puo' invalidare quelli successivi.

1. **`run_index.csv`** — `stato = completa`? `tbt_mismatch = 0`?
   `mining_diversity_val = 0.0`? Se no, fermati: la run non e' confrontabile
   con le altre.
2. **`forks.csv`** — verdetto `fork persistente`? Se si', la catena non ha
   tenuto e le statistiche sui proposer sono calcolate su una storia che non
   tutti i nodi condividono.
3. **`verify.csv`** — `verificato = 1`, `non_validi = 0`? Se no, i pesi
   pubblicati non sono quelli che il motore avrebbe calcolato, e ogni confronto
   quota-vs-peso perde significato.
4. **`alternanze.csv`** — `consecutivi_osservati = 0` con attesi > 3? Allora
   c'e' un vincolo di alternanza attivo e la distribuzione non e' quella della
   wPoA. Non serve guardare il chi-quadro.
5. **`chisq.csv` → `campione_sufficiente`** — se e' 0, il test non e'
   applicabile: passa direttamente a `epoch_shares.csv`.
6. **`proposers.csv` → `delay_medio_s`** — ordinato per peso decrescente? E
   `delay_pos_in_banda`: se il miner leggero e' oltre l'85–90 %, il suo score e'
   saturo e la distribuzione si appiattira' comunque.
7. **`sortition_margins.csv` → `frazione_G_sotto_100ms`** — se supera qualche
   punto percentuale, parte dei round e' decisa dalla rete e non dallo score.
8. **solo ora** il chi-quadro e le quote osservate vs attese.
9. **`block_times.csv`** — scarto dal target, letto con la tabella qui sopra per
   attribuirlo al simulatore o alla retroazione.
10. **`epoch_shares.csv`** — se il chi-quadro globale e quello per epoca
    divergono, fidati di quello per epoca e riporta entrambi.
