# Confronto fra aree — run5-tbt-2s

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
| peso identico fra i livelli | 74 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 91 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 16 | m2 | tau diverso | 15454 / 4 | 15454 / 4 | 15454 / 4 | 12827 / 3 |
| 17 | m1 | tau diverso | 34808 / 5 | 34808 / 5 | 34808 / 5 | 27749 / 6 |
| 17 | m2 | tau diverso | 10373 / 2 | 10373 / 2 | 10373 / 2 | 12999 / 3 |
| 18 | m1 | tau diverso | 42907 / 7 | 42907 / 7 | 44404 / 8 | 42907 / 7 |
| 18 | m2 | tau diverso | 15454 / 4 | 15454 / 4 | 18080 / 5 | 15454 / 4 |
| 18 | m3 | tau diverso | 6539 / 1 | 8243 / 2 | 8243 / 2 | 6539 / 1 |
| 19 | m1 | tau diverso | 36305 / 6 | 36305 / 6 | 41409 / 6 | — / 7 |
| 19 | m2 | tau diverso | 12999 / 3 | 12999 / 3 | 10373 / 2 | 12999 / 3 |
| 19 | m3 | tau diverso | 8243 / 2 | 6539 / 1 | 6539 / 1 | 8243 / 2 |
| 20 | m1 | tau diverso | 42907 / 7 | 42907 / 7 | 36305 / 6 | 27749 / 6 |
| 22 | m1 | tau diverso | 27749 / 6 | 34351 / 7 | — / 7 | — / 7 |
| 22 | m2 | tau diverso | 15454 / 4 | 10353 / 3 | 15454 / 4 | 10353 / 3 |
| 22 | m3 | tau diverso | 4122 / 1 | 8243 / 2 | 8243 / 2 | 5826 / 2 |
| 23 | m1 | tau diverso | 42907 / 7 | 36305 / 6 | 27749 / 6 | 35848 / 8 |
| 23 | m2 | tau diverso | — / 4 | 15454 / 4 | — / 4 | 18080 / 5 |
| 23 | m3 | tau diverso | 8243 / 2 | 6539 / 1 | 6539 / 1 | 6539 / 1 |
| 24 | m1 | tau diverso | — / 7 | 42907 / 7 | 42907 / 7 | 34808 / 5 |
| 24 | m2 | tau diverso | 10353 / 3 | 12999 / 3 | 10353 / 3 | 10373 / 2 |
| 25 | m1 | tau diverso | 27749 / 6 | 34808 / 5 | 36305 / 6 | 42907 / 7 |
| 26 | m1 | tau diverso | 42907 / 7 | 42907 / 7 | 41409 / 6 | 36305 / 6 |
| 26 | m3 | tau diverso | 5826 / 2 | 6539 / 1 | 8243 / 2 | 8243 / 2 |
| 27 | m1 | tau diverso | — / 7 | 44404 / 8 | 36305 / 6 | 42907 / 7 |
| 27 | m2 | tau diverso | 10353 / 3 | 15454 / 4 | 15454 / 4 | 10353 / 3 |
| 27 | m3 | tau diverso | 6539 / 1 | 8243 / 2 | 6539 / 1 | 6539 / 1 |
| 28 | m1 | tau diverso | 27749 / 6 | 36305 / 6 | 42907 / 7 | 34808 / 5 |
| 28 | m2 | tau diverso | 15454 / 4 | — / 4 | 12999 / 3 | 12999 / 3 |
| 29 | m1 | tau diverso | 41409 / 6 | 41409 / 6 | — / 7 | 42907 / 7 |
| 29 | m2 | tau diverso | 12999 / 3 | 10353 / 3 | 15454 / 4 | 15454 / 4 |
| 30 | m1 | tau diverso | 36305 / 6 | 36305 / 6 | 27749 / 6 | 36305 / 6 |
| 30 | m2 | tau diverso | 15454 / 4 | 15454 / 4 | 12999 / 3 | — / 4 |
| 30 | m3 | tau diverso | 8243 / 2 | 5826 / 2 | 6539 / 1 | 8243 / 2 |
| 31 | m2 | tau diverso | 12999 / 3 | 12999 / 3 | 15454 / 4 | 10353 / 3 |
| 31 | m3 | tau diverso | 6539 / 1 | 6539 / 1 | 8243 / 2 | 6539 / 1 |
| 33 | m1 | tau diverso | 42907 / 7 | 41409 / 6 | 42907 / 7 | 27749 / 6 |
| 33 | m2 | tau diverso | 12999 / 3 | 10373 / 2 | 10353 / 3 | 12999 / 3 |
| 34 | m1 | tau diverso | 34808 / 5 | 36305 / 6 | 34808 / 5 | 34808 / 5 |
| 34 | m2 | tau diverso | 12827 / 3 | 12999 / 3 | 12827 / 3 | 10373 / 2 |
| 34 | m3 | tau diverso | 6539 / 1 | 6539 / 1 | 4122 / 1 | 6539 / 1 |
| 35 | m2 | tau diverso | 12999 / 3 | 15454 / 4 | 12999 / 3 | 15454 / 4 |
| 36 | m1 | tau diverso | — / 7 | 36305 / 6 | 44404 / 8 | 34351 / 7 |

(51 righe non elencate: il dettaglio e' in `confronto_aree_peso.csv`)

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 17 | m1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| 17 | m2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 17 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 18 | m1 | 0.583 | 1.000 | 1.000 | 1.000 | 0.417 |
| 18 | m2 | 0.417 | 0.000 | 0.000 | 0.000 | 0.417 |
| 18 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 19 | m1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| 19 | m2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 19 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 20 | m1 | 0.917 | 0.667 | 1.000 | 0.167 | 0.833 |
| 20 | m2 | 0.000 | 0.333 | 0.000 | 0.833 | 0.833 |
| 20 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 21 | m1 | 1.000 | 1.000 | 1.000 | 1.000 | 0.000 |
| 21 | m2 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 21 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 22 | m1 | 0.583 | 0.917 | 1.000 | 0.750 | 0.417 |
| 22 | m2 | 0.417 | 0.083 | 0.000 | 0.250 | 0.417 |
| 22 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 23 | m1 | 0.667 | 0.500 | 1.000 | 0.333 | 0.667 |
| 23 | m2 | 0.333 | 0.167 | 0.000 | 0.167 | 0.333 |
| 23 | m3 | 0.000 | 0.333 | 0.000 | 0.500 | 0.500 |
| 24 | m1 | 0.500 | 1.000 | 1.000 | 0.833 | 0.500 |
| 24 | m2 | 0.417 | 0.000 | 0.000 | 0.167 | 0.417 |
| 24 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 25 | m1 | 0.083 | 1.000 | 0.667 | 1.000 | 0.917 |
| 25 | m2 | 0.917 | 0.000 | 0.000 | 0.000 | 0.917 |
| 25 | m3 | 0.000 | 0.000 | 0.333 | 0.000 | 0.333 |
| 26 | m1 | 0.667 | 0.667 | 1.000 | 0.750 | 0.333 |
| 26 | m2 | 0.333 | 0.333 | 0.000 | 0.250 | 0.333 |
| 26 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 27 | m1 | 1.000 | 1.000 | 0.750 | 0.750 | 0.250 |
| 27 | m2 | 0.000 | 0.000 | 0.250 | 0.083 | 0.250 |
| 27 | m3 | 0.000 | 0.000 | 0.000 | 0.167 | 0.167 |
| 28 | m1 | 0.750 | 1.000 | 0.417 | 0.500 | 0.583 |
| 28 | m2 | 0.083 | 0.000 | 0.583 | 0.500 | 0.583 |
| 28 | m3 | 0.167 | 0.000 | 0.000 | 0.000 | 0.167 |
| 29 | m1 | 0.583 | 0.667 | 0.583 | 0.667 | 0.083 |
| 29 | m2 | 0.000 | 0.167 | 0.250 | 0.333 | 0.333 |
| 29 | m3 | 0.417 | 0.167 | 0.167 | 0.000 | 0.417 |
| 30 | m1 | 0.667 | 0.500 | 1.000 | 0.917 | 0.500 |
| 30 | m2 | 0.250 | 0.250 | 0.000 | 0.000 | 0.250 |
| 30 | m3 | 0.083 | 0.250 | 0.000 | 0.083 | 0.250 |
| 31 | m1 | 0.583 | 1.000 | 0.417 | 0.917 | 0.583 |
| 31 | m2 | 0.333 | 0.000 | 0.583 | 0.083 | 0.583 |
| 31 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 32 | m1 | 0.750 | 0.417 | 0.583 | 0.833 | 0.417 |
| 32 | m2 | 0.250 | 0.417 | 0.333 | 0.167 | 0.250 |
| 32 | m3 | 0.000 | 0.167 | 0.083 | 0.000 | 0.167 |
| 33 | m1 | 1.000 | 0.833 | 0.667 | 0.750 | 0.333 |
| 33 | m2 | 0.000 | 0.000 | 0.333 | 0.250 | 0.333 |
| 33 | m3 | 0.000 | 0.167 | 0.000 | 0.000 | 0.167 |
| 34 | m1 | 0.667 | 1.000 | 1.000 | 1.000 | 0.333 |
| 34 | m2 | 0.333 | 0.000 | 0.000 | 0.000 | 0.333 |
| 34 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 35 | m1 | 0.583 | 1.000 | 1.000 | 1.000 | 0.417 |
| 35 | m2 | 0.167 | 0.000 | 0.000 | 0.000 | 0.167 |
| 35 | m3 | 0.250 | 0.000 | 0.000 | 0.000 | 0.250 |
| 36 | m1 | 0.417 | 1.000 | 0.500 | 0.917 | 0.583 |
| 36 | m2 | 0.333 | 0.000 | 0.500 | 0.083 | 0.500 |
| 36 | m3 | 0.250 | 0.000 | 0.000 | 0.000 | 0.250 |

(57 righe non elencate: il dettaglio completo e' in `confronto_aree_peso.csv`)
