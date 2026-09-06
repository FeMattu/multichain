# Confronto fra aree — run4-tbt-3s

Livelli confrontati: continentale, intercontinentale, nazionale, regionale.

## Traiettoria del peso

L'attesa di partenza e' che il peso **non** dipenda dall'area: a parita' di
run gli ESG certificati e le adesioni ai cluster sono identici per
costruzione, e cambia solo la latenza. La misura la smentisce, e il motivo
e' strutturale: `tau` conta le transazioni confermate in una finestra di
dodici **blocchi**, mentre il traffico e' generato a **tempo reale**. Dove i
blocchi sono piu' lenti l'epoca dura piu' secondi e ci cadono dentro piu'
transazioni: cambia `tau`, cambia `W_k`, cambia il peso pubblicato. La
latenza entra quindi nel peso, ma per la via del throughput, non del
protocollo di selezione.

Le divergenze vanno percio' separate in due famiglie:

| famiglia | coppie (epoca, host) | lettura |
|---|---|---|
| peso identico fra i livelli | 55 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 80 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 11 | m1 | tau diverso | 44404 / 8 | 42907 / 7 | 42907 / 7 | 44404 / 8 |
| 11 | m2 | tau diverso | 18080 / 5 | 15454 / 4 | 15454 / 4 | 18080 / 5 |
| 12 | m1 | tau diverso | 42907 / 7 | 44404 / 8 | 44404 / 8 | 42907 / 7 |
| 12 | m2 | tau diverso | 15454 / 4 | 18080 / 5 | 18080 / 5 | 15454 / 4 |
| 13 | m1 | tau diverso | 52503 / 10 | 52503 / 10 | 52503 / 10 | 44404 / 8 |
| 14 | m1 | tau diverso | 44404 / 8 | 44404 / 8 | — / 10 | 52503 / 10 |
| 14 | m2 | tau diverso | 15454 / 4 | 12808 / 4 | 15434 / 5 | 15434 / 5 |
| 14 | m3 | tau diverso | 8243 / 2 | 8243 / 2 | 4122 / 1 | 8243 / 2 |
| 15 | m1 | tau diverso | 52503 / 10 | 51006 / 9 | 43947 / 10 | 51006 / 9 |
| 15 | m2 | tau diverso | 18080 / 5 | 18080 / 5 | 20535 / 6 | 18080 / 5 |
| 16 | m1 | tau diverso | 51006 / 9 | 45901 / 9 | 44404 / 8 | 52503 / 10 |
| 17 | m1 | tau diverso | 52503 / 10 | 52503 / 10 | 51006 / 9 | 45901 / 9 |
| 17 | m2 | tau diverso | 17889 / 6 | 17889 / 6 | 18080 / 5 | 17889 / 6 |
| 17 | m3 | tau diverso | 8243 / 2 | 6539 / 1 | 5826 / 2 | 6539 / 1 |
| 18 | m1 | tau diverso | 44404 / 8 | 51006 / 9 | 45901 / 9 | 51006 / 9 |
| 18 | m3 | tau diverso | 6539 / 1 | 8243 / 2 | 6539 / 1 | 8243 / 2 |
| 19 | m1 | tau diverso | — / 8 | 44404 / 8 | 52503 / 10 | 52503 / 10 |
| 19 | m2 | tau diverso | 18080 / 5 | 18080 / 5 | 15434 / 5 | 18080 / 5 |
| 20 | m1 | tau diverso | 42450 / 9 | 51006 / 9 | 51006 / 9 | 44404 / 8 |
| 20 | m2 | tau diverso | 15454 / 4 | 15454 / 4 | 17908 / 5 | — / 5 |
| 20 | m3 | tau diverso | 6539 / 1 | 4122 / 1 | — / 2 | 5826 / 2 |
| 21 | m1 | tau diverso | 52503 / 10 | 45901 / 9 | 52503 / 10 | 52503 / 10 |
| 21 | m2 | tau diverso | 18080 / 5 | 18080 / 5 | 18080 / 5 | 15434 / 5 |
| 21 | m3 | tau diverso | 8243 / 2 | 8243 / 2 | 5826 / 2 | 6539 / 1 |
| 22 | m1 | tau diverso | 44404 / 8 | 51006 / 9 | 44404 / 8 | 44404 / 8 |
| 22 | m3 | tau diverso | — / 2 | — / 2 | 6539 / 1 | 8243 / 2 |
| 23 | m1 | tau diverso | — / 8 | 52503 / 10 | 51006 / 9 | 51006 / 9 |
| 23 | m2 | tau diverso | 12808 / 4 | 15434 / 5 | 12808 / 4 | 20535 / 6 |
| 23 | m3 | tau diverso | 4122 / 1 | 5826 / 2 | 8243 / 2 | — / 2 |
| 24 | m1 | tau diverso | 35848 / 8 | 42907 / 7 | 52503 / 10 | 52503 / 10 |
| 24 | m2 | tau diverso | 18080 / 5 | 15454 / 4 | 18080 / 5 | 18080 / 5 |
| 24 | m3 | tau diverso | 8243 / 2 | 6539 / 1 | — / 2 | 5826 / 2 |
| 25 | m1 | tau diverso | 51006 / 9 | 44404 / 8 | — / 10 | 44404 / 8 |
| 25 | m2 | tau diverso | 15454 / 4 | — / 4 | 20535 / 6 | 15454 / 4 |
| 25 | m3 | tau diverso | — / 2 | 8243 / 2 | 5826 / 2 | 6539 / 1 |
| 26 | m1 | tau diverso | 44404 / 8 | — / 8 | 37345 / 9 | — / 8 |
| 26 | m2 | tau diverso | 18080 / 5 | 15434 / 5 | 18080 / 5 | 18080 / 5 |
| 26 | m3 | tau diverso | 4122 / 1 | 6539 / 1 | 8243 / 2 | 8243 / 2 |
| 27 | m1 | tau diverso | 51006 / 9 | 43947 / 10 | 51006 / 9 | 42450 / 9 |
| 27 | m2 | tau diverso | 15454 / 4 | 18080 / 5 | — / 5 | 15454 / 4 |

(40 righe non elencate: il dettaglio e' in `confronto_aree_peso.csv`)

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 13 | m1 | 0.545 | 0.818 | 1.000 | 0.909 | 0.455 |
| 13 | m2 | 0.455 | 0.091 | 0.000 | 0.091 | 0.455 |
| 13 | m3 | 0.000 | 0.091 | 0.000 | 0.000 | 0.091 |
| 14 | m1 | 0.750 | 0.917 | 0.417 | 0.917 | 0.500 |
| 14 | m2 | 0.250 | 0.000 | 0.167 | 0.083 | 0.250 |
| 14 | m3 | 0.000 | 0.083 | 0.417 | 0.000 | 0.417 |
| 15 | m1 | 0.250 | 0.750 | 0.000 | 0.917 | 0.917 |
| 15 | m2 | 0.750 | 0.000 | 0.917 | 0.083 | 0.917 |
| 15 | m3 | 0.000 | 0.250 | 0.083 | 0.000 | 0.250 |
| 16 | m1 | 1.000 | 0.250 | 0.750 | 0.417 | 0.750 |
| 16 | m2 | 0.000 | 0.750 | 0.167 | 0.500 | 0.750 |
| 16 | m3 | 0.000 | 0.000 | 0.083 | 0.083 | 0.083 |
| 17 | m1 | 1.000 | 0.583 | 1.000 | 0.750 | 0.417 |
| 17 | m2 | 0.000 | 0.417 | 0.000 | 0.250 | 0.417 |
| 17 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 18 | m1 | 0.917 | 1.000 | 0.917 | 0.417 | 0.583 |
| 18 | m2 | 0.083 | 0.000 | 0.083 | 0.333 | 0.333 |
| 18 | m3 | 0.000 | 0.000 | 0.000 | 0.250 | 0.250 |
| 19 | m1 | 0.750 | 0.833 | 0.583 | 0.500 | 0.333 |
| 19 | m2 | 0.250 | 0.167 | 0.417 | 0.500 | 0.333 |
| 19 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 20 | m1 | 1.000 | 0.750 | 0.917 | 0.750 | 0.250 |
| 20 | m2 | 0.000 | 0.250 | 0.083 | 0.167 | 0.250 |
| 20 | m3 | 0.000 | 0.000 | 0.000 | 0.083 | 0.083 |
| 21 | m1 | 0.333 | 0.833 | 0.083 | 1.000 | 0.917 |
| 21 | m2 | 0.500 | 0.000 | 0.917 | 0.000 | 0.917 |
| 21 | m3 | 0.167 | 0.167 | 0.000 | 0.000 | 0.167 |
| 22 | m1 | 0.917 | 0.667 | 0.833 | 0.667 | 0.250 |
| 22 | m2 | 0.083 | 0.250 | 0.167 | 0.333 | 0.250 |
| 22 | m3 | 0.000 | 0.083 | 0.000 | 0.000 | 0.083 |
| 23 | m1 | 1.000 | 0.917 | 0.917 | 0.583 | 0.417 |
| 23 | m2 | 0.000 | 0.083 | 0.083 | 0.250 | 0.250 |
| 23 | m3 | 0.000 | 0.000 | 0.000 | 0.167 | 0.167 |
| 24 | m1 | 0.917 | 1.000 | 0.750 | 0.667 | 0.333 |
| 24 | m2 | 0.000 | 0.000 | 0.167 | 0.167 | 0.167 |
| 24 | m3 | 0.083 | 0.000 | 0.083 | 0.167 | 0.167 |
| 25 | m1 | 0.833 | 1.000 | 1.000 | 0.833 | 0.167 |
| 25 | m2 | 0.000 | 0.000 | 0.000 | 0.167 | 0.167 |
| 25 | m3 | 0.167 | 0.000 | 0.000 | 0.000 | 0.167 |
| 26 | m1 | 0.917 | 0.917 | 0.583 | 0.917 | 0.333 |
| 26 | m2 | 0.083 | 0.000 | 0.167 | 0.000 | 0.167 |
| 26 | m3 | 0.000 | 0.083 | 0.250 | 0.083 | 0.250 |
| 27 | m1 | 0.583 | 0.917 | 0.833 | 0.833 | 0.333 |
| 27 | m2 | 0.333 | 0.083 | 0.083 | 0.167 | 0.250 |
| 27 | m3 | 0.083 | 0.000 | 0.083 | 0.000 | 0.083 |
| 28 | m1 | 0.500 | 0.750 | 1.000 | 0.917 | 0.500 |
| 28 | m2 | 0.500 | 0.250 | 0.000 | 0.083 | 0.500 |
| 28 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 29 | m1 | 0.750 | 0.583 | 0.667 | 0.917 | 0.333 |
| 29 | m2 | 0.250 | 0.083 | 0.250 | 0.083 | 0.167 |
| 29 | m3 | 0.000 | 0.333 | 0.083 | 0.000 | 0.333 |
| 30 | m1 | 0.583 | 1.000 | 0.917 | 1.000 | 0.417 |
| 30 | m2 | 0.417 | 0.000 | 0.000 | 0.000 | 0.417 |
| 30 | m3 | 0.000 | 0.000 | 0.083 | 0.000 | 0.083 |
| 31 | m1 | 0.917 | 1.000 | 0.917 | 0.583 | 0.417 |
| 31 | m2 | 0.083 | 0.000 | 0.083 | 0.250 | 0.250 |
| 31 | m3 | 0.000 | 0.000 | 0.000 | 0.167 | 0.167 |
| 32 | m1 | 0.667 | 0.917 | 0.500 | 0.250 | 0.667 |
| 32 | m2 | 0.250 | 0.083 | 0.333 | 0.750 | 0.667 |
| 32 | m3 | 0.083 | 0.000 | 0.167 | 0.000 | 0.167 |

(39 righe non elencate: il dettaglio completo e' in `confronto_aree_peso.csv`)
