# Schema reale di `metrics/`

Generato da `tools/analizza_esperimenti.py`: elenca i file effettivamente presenti in ogni run e lo schema dedotto, cosi' si sa da quale campo viene ogni numero delle tabelle.

## File per run (24 run esaminate)

| file | presente in | schema osservato |
|---|---|---|
| `admin_getinfo.json` | 24/24 | `JSON-RPC, result = oggetto{balance, blocks, burnaddress, chainname, chainrewards, connections, description, difficulty, edition, errors, incomingpaused, keypoololdest}` (24 run) |
| `blocks.json` | 24/24 | `JSON-RPC, result = lista[169] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[172] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[173] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[167] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[324] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[327] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[329] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[325] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[420] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[421] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[415] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[416] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[537] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[535] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[529] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[531] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[651] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[655] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[659] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[658] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[597] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[602] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[598] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run)<br>`JSON-RPC, result = lista[590] di oggetti{confirmations, hash, height, miner, time, txcount}` (1 run) |
| `esg.json` | 24/24 | `JSON-RPC, result = lista[8] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (24 run) |
| `esg_scores.csv` | 24/24 | `senza header, 3 colonne (es. host,address,esg)` (24 run) |
| `final_height.txt` | 24/24 | `testo` (24 run) |
| `gas_balances.csv` | 24/24 | `senza header, 3 colonne (es. height,host,balance)` (24 run) |
| `gas_transfers.csv` | 24/24 | `senza header, 4 colonne (es. 6,init,c1,100)` (8 run)<br>`senza header, 4 colonne (es. 5,init,c1,100)` (4 run)<br>`senza header, 4 colonne (es. 11,init,c1,100)` (4 run)<br>`senza header, 4 colonne (es. 19,init,c1,100)` (4 run)<br>`senza header, 4 colonne (es. 28,init,c1,100)` (4 run) |
| `malus.json` | 24/24 | `JSON-RPC, result = lista vuota` (24 run) |
| `membership.csv` | 24/24 | `senza header, 3 colonne (es. m3,1DVAYRLwA57d87NS9TFhcyQtj8C9mS32fKGiy9,1DVAYRLwA57d87NS9TFhcyQtj8C9mS32fKGiy9)` (1 run)<br>`senza header, 3 colonne (es. m1,1BCbQWmgd57VhPC3P556KkGd4Y4x8a8CV1bddD,1BCbQWmgd57VhPC3P556KkGd4Y4x8a8CV1bddD)` (1 run)<br>`senza header, 3 colonne (es. m2,17Sjr3aPX8Bmfo7avGvib3ZJUxrz8u9aL8S8fU,17Sjr3aPX8Bmfo7avGvib3ZJUxrz8u9aL8S8fU)` (1 run)<br>`senza header, 3 colonne (es. m2,1QfNfpZhwfH6CM4ixrSJgDoDJhiRFdtubEjpYo,1QfNfpZhwfH6CM4ixrSJgDoDJhiRFdtubEjpYo)` (1 run)<br>`senza header, 3 colonne (es. m3,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58)` (1 run)<br>`senza header, 3 colonne (es. m3,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2)` (1 run)<br>`senza header, 3 colonne (es. m2,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe)` (1 run)<br>`senza header, 3 colonne (es. m1,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv)` (1 run)<br>`senza header, 3 colonne (es. m2,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS)` (1 run)<br>`senza header, 3 colonne (es. m2,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm)` (1 run)<br>`senza header, 3 colonne (es. m2,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx)` (1 run)<br>`senza header, 3 colonne (es. m2,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u)` (1 run)<br>`senza header, 3 colonne (es. m1,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi)` (1 run)<br>`senza header, 3 colonne (es. m3,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm)` (1 run)<br>`senza header, 3 colonne (es. m3,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8)` (1 run)<br>`senza header, 3 colonne (es. m2,1ZizoV8be5qn4x2Uk4tmToQ9Usx1nqZaxZUHs,1ZizoV8be5qn4x2Uk4tmToQ9Usx1nqZaxZUHs)` (1 run)<br>`senza header, 3 colonne (es. m2,18GGauDrTeEJnuo5WxTDKBoNSryjXMhQvGRPjC,18GGauDrTeEJnuo5WxTDKBoNSryjXMhQvGRPjC)` (1 run)<br>`senza header, 3 colonne (es. m1,1CMdrBmxo2wcbEWHTtRHXuKRi6pGt4zPLLdt25,1CMdrBmxo2wcbEWHTtRHXuKRi6pGt4zPLLdt25)` (1 run)<br>`senza header, 3 colonne (es. m2,1Qfy23H5N3KcwZ4CW25K68hY7T9BMNCYG9n3d8,1Qfy23H5N3KcwZ4CW25K68hY7T9BMNCYG9n3d8)` (1 run)<br>`senza header, 3 colonne (es. m1,1akrbuSTPkRMU7ztM65jGiNHd5t7DPrqV7pB8G,1akrbuSTPkRMU7ztM65jGiNHd5t7DPrqV7pB8G)` (1 run)<br>`senza header, 3 colonne (es. m1,18JDemQBu6Vrxd4WjEuSr62wjZLUFXv5vbjJqL,18JDemQBu6Vrxd4WjEuSr62wjZLUFXv5vbjJqL)` (1 run)<br>`senza header, 3 colonne (es. m3,12FC8Zks2JqRt2BTkbvcKztQFVkCRaMjVC9Tu7,12FC8Zks2JqRt2BTkbvcKztQFVkCRaMjVC9Tu7)` (1 run)<br>`senza header, 3 colonne (es. m3,1CsyzTjErfmoC3PFDMJbGZZqJu6EUYCh2wKkBq,1CsyzTjErfmoC3PFDMJbGZZqJu6EUYCh2wKkBq)` (1 run)<br>`senza header, 3 colonne (es. m1,1FFo3ah8sAKS4svacrTuQgQBUPEKrjop9rucCp,1FFo3ah8sAKS4svacrTuQgQBUPEKrjop9rucCp)` (1 run) |
| `membership.json` | 24/24 | `JSON-RPC, result = lista[8] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (24 run) |
| `node_state.csv` | 24/24 | `senza header, 6 colonne (es. host,height,besthash,hash_h_meno_6)` (3 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_161)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_318)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_321)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_323)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_319)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_414)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_415)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_409)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_410)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_531)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_529)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_523)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_525)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_645)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_649)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_653)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_652)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_591)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_596)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_592)` (1 run)<br>`senza header, 6 colonne (es. host,height,besthash,hash_a_584)` (1 run) |
| `permissions_mine.json` | 24/24 | `JSON-RPC, result = lista[4] di oggetti{address, endblock, for, startblock, type}` (24 run) |
| `reconciliation.csv` | 24/24 | `senza header, 5 colonne (es. height,epoch,miner,balance)` (24 run) |
| `summary.txt` | 24/24 | `testo` (24 run) |
| `traffic.csv` | 24/24 | `senza header, 4 colonne (es. height,host,seq,txid_or_error)` (24 run) |
| `treasury_balance.json` | 24/24 | `JSON-RPC, result = lista[1] di oggetti{assetref, qty, raw}` (24 run) |
| `verify.json` | 24/24 | `JSON-RPC, result = oggetto{entries, epoch, invalid, records, verified}` (24 run) |
| `weights.json` | 24/24 | `JSON-RPC, result = lista[14] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (3 run)<br>`JSON-RPC, result = lista[36] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (2 run)<br>`JSON-RPC, result = lista[65] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (2 run)<br>`JSON-RPC, result = lista[98] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (2 run)<br>`JSON-RPC, result = lista[113] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (2 run)<br>`JSON-RPC, result = lista[34] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[33] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[66] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[67] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[82] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[80] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[79] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[76] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[92] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[96] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[109] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[108] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run)<br>`JSON-RPC, result = lista[15] di oggetti{available, blocktime, confirmations, data, keys, offchain, publishers, txid}` (1 run) |

## Note sullo schema, verificate sul campo

* `membership.csv` e `gas_transfers.csv` sono scritti **senza riga di intestazione**: le colonne sono rispettivamente `host,address,miner_address` e `height,tipo,host,importo`.
* `node_state.csv` ha una colonna dal nome **variabile** (`hash_a_<N>`, con N = altezza di riferimento della run): il parser la individua per posizione, non per nome.
* i file `*:Zone.Identifier` sono artefatti di WSL/NTFS e vengono ignorati.
* i `debug.log` stanno in `data/<host>/debug.log` nelle run archiviate e in `data/<host>/<chain>/debug.log` in quelle appena eseguite: si cercano entrambe le forme.
* il chi-quadro **non** e' in un file dati: esiste solo come testo in `summary.txt`, da cui viene estratto con regex (`--recompute-chisq` lo ricalcola come controprova).
* `weights.json` porta gia' `epoch` in ogni record, quindi la traiettoria per epoca non richiede di rimappare le altezze.
* `admin_getinfo.json` espone `setupblocks` e `chainname`: e' la fonte piu' autorevole per la lunghezza del setup, incrociata con `params.dat`.

## Conversione GAS, run per run (Sez. 2.3)

Le RPC di MultiChain restituiscono la valuta nativa gia' in unita' di
**visualizzazione**: `getbalance`, l'importo di `send`, `qty` di
`listassets`. Ogni CSV scritto dall'harness ne e' una copia diretta —
`gas_balances.csv`, `gas_transfers.csv`, `reconciliation.csv`, la colonna
`balance` di `node_state.csv`, `treasury_balance.json` — quindi e' **gia' in
GAS** e non va convertito: convertirlo una seconda volta sarebbe l'errore.

A essere in unita' **grezze** sono i soli parametri di catena in
`params.dat`: `first-block-reward`, `initial-block-reward`,
`minimum-relay-fee`, `maximum-per-output`. La pipeline li divide per
`native-currency-multiple`, letto run per run e mai assunto:

| run | native-currency-multiple | fonte | first-block-reward (GAS) | initial-block-reward (GAS) | minimum-relay-fee (GAS/1000B) |
|---|---|---|---|---|---|
| `run1-tbt-15s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run1-tbt-15s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run1-tbt-15s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run1-tbt-15s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run2-tbt-10s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run2-tbt-10s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run2-tbt-10s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run2-tbt-10s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run3-tbt-5s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run3-tbt-5s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run3-tbt-5s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run3-tbt-5s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run4-tbt-3s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run4-tbt-3s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run4-tbt-3s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run4-tbt-3s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run5-tbt-2s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run5-tbt-2s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run5-tbt-2s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run5-tbt-2s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run6-tbt-10s/continentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run6-tbt-10s/intercontinentale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run6-tbt-10s/nazionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |
| `run6-tbt-10s/regionale` | 100000000.0 | params.dat di admin (native-currency-multiple) | 1000000 | 0 | 0.2 |

## Il generatore di traffico e' esogeno (Sez. 2.4)

Determinato leggendo l'harness, non assunto. `tools/role_company.sh`, fase
`traffic`: un ciclo `while true` che pubblica un item sullo stream applicativo
e poi `sleep $POESIA_TX_INTERVAL`. L'intervallo e' fisso per azienda e
dichiarato nello `shadow.yaml`; il ciclo non legge ne' chi ha vinto il blocco,
ne' il proprio saldo, ne' il peso pubblicato. Anche `tools/role_miner.sh` fase
`reconcile` e' a tasso fisso (`POESIA_RECONCILE_RATE` per miner), applicato al
saldo del momento.

Conseguenza per l'analisi: **non esiste un anello di retroazione dal risultato
delle elezioni al traffico**. Il canale selezione -> fee incassate ->
riconciliazione -> rho -> peso dell'epoca successiva esiste (le fee dipendono
da quanti blocchi il miner include), ma il traffico che alimenta `tau` no. Un
eventuale ciclo osservato nei dati non puo' quindi passare per `tau`.

## Nota sulle dipendenze Python

`pandas`, `scipy` e `numpy` sono presenti in questo ambiente e vengono usati
dove servono (Spearman via `scipy.stats.spearmanr`); la pipeline resta pero'
corretta senza, con il coefficiente calcolato sui ranghi e il p-value
dichiarato mancante invece che stimato. Lo stato effettivo di ogni giro e' la
riga `pandas=... scipy=...` in testa a `estrazione.log`.

