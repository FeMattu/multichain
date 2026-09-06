# Topologie di rete

I file `.gml` di questa cartella sono gli **artefatti versionati** referenziati
da `topology_file` nei descrittori di `config/simulations/`. Shadow li legge
tramite `network.graph.type: gml` e `network.graph.file.path`.

Definiscono **solo** latenze, banda e packet loss fra i `network_node_id`. Non
dicono nulla su quali host ci stiano sopra: quello lo decide la sezione `nodes`
del descrittore di simulazione, e piu' host possono condividere lo stesso
`network_node_id`.

## Provenienza

Sono prodotti da `tools/gen_topology.py`, che applica a tutte le topologie lo
stesso modello di latenza — `0.005 · D_km · 1.4 + overhead`, con `D_km`
distanza great-circle. E' questo a renderle confrontabili fra loro: un `.gml`
scritto a mano con latenze arbitrarie non lo sarebbe.

| file | sorgente | rigenerazione |
|---|---|---|
| `continental-10n.gml` | `config/levels/continentale.json` | `python3 tools/gen_topology.py config/levels/continentale.json -o config/topologies/continental-10n.gml` |
| `intercontinental-global-10n.gml` | `intercontinental-global.json` (qui accanto) | `python3 tools/gen_topology.py config/topologies/intercontinental-global.json -o config/topologies/intercontinental-global-10n.gml` |

`continental-10n.gml` e' **byte-identico** a
`continentale/topologia_myledger_continentale.gml`: nasce dalla stessa
definizione di livello, non e' una copia riscritta a mano. Le due topologie
storiche restano dove sono per le run del modo livelli deprecato.

`intercontinental-global-10n.gml` e' nuovo. Quello storico
(`intercontinentale/topologia_myledger_intercontinentale.gml`) si ferma
all'Atlantico settentrionale: la tratta piu' lunga e' Milano-New York, ~90 ms
di RTT. Questo attraversa anche Pacifico e Atlantico meridionale e arriva a
407 ms fra Tokyo e Johannesburg, che e' un regime di latenza qualitativamente
diverso — abbastanza da rendere visibile l'effetto della banda di sortition
`Delta_max = delta · target-block-time`.

## Verifica

```bash
python3 tools/check_topology.py config/topologies/<file>.gml --matrix
```

Controlla che il grafo sia valido e connesso e stampa la matrice degli RTT
end-to-end sul cammino minimo.

## Vincoli del parser GML di Shadow 3.3

Verificati sul campo, non documentati nel manuale. `gen_topology.py` li
rispetta tutti; un `.gml` scritto a mano li viola facilmente.

1. **Niente commenti.** Una riga che inizia con `#` fa fallire il parse con
   *"Failed to parse the network graph ... in Verify"*.
2. **Blocchi `node`/`edge` in forma canonica multi-riga.** La forma compatta
   `node [ id 0 label "x" ]` fallisce con *"... in MultiSpace"*.
3. **Le stringhe con unita' vogliono una magnitudine intera.** `latency "0.2 ms"`
   produce *"Edge 'latency' is not a valid unit: invalid digit found in string"*.
   Per questo le latenze sono emesse in microsecondi interi.

L'attributo `jitter` resta 0 su ogni arco: il campo **non e' implementato** da
Shadow (issue shadow/shadow#3601).
