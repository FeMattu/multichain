# Confronto fra aree — run3-tbt-5s

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
| peso identico fra i livelli | 31 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 77 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 5 | m1 | tau diverso | 12606 / 2 | 16884 / 2 | 12606 / 2 | 12606 / 2 |
| 5 | m2 | tau diverso | 5186 / 2 | 6509 / 2 | 5186 / 2 | 5186 / 2 |
| 7 | m1 | tau diverso | 60602 / 12 | 62099 / 13 | 60602 / 12 | 62099 / 13 |
| 7 | m2 | tau diverso | 20535 / 6 | 25615 / 8 | 20535 / 6 | 25615 / 8 |
| 8 | m1 | tau diverso | 62099 / 13 | 60602 / 12 | 62099 / 13 | 60602 / 12 |
| 8 | m2 | tau diverso | 23161 / 7 | 20535 / 6 | 25615 / 8 | 20535 / 6 |
| 9 | m1 | tau diverso | 68701 / 14 | 62099 / 13 | 70199 / 15 | — / 12 |
| 9 | m2 | tau diverso | 25615 / 8 | 23161 / 7 | 25787 / 8 | 20707 / 6 |
| 10 | m1 | tau diverso | 63597 / 14 | 68701 / 14 | — / 15 | 61643 / 15 |
| 10 | m2 | tau diverso | 25787 / 8 | — / 7 | 25615 / 8 | 25615 / 8 |
| 10 | m3 | tau diverso | — / 3 | 8243 / 2 | — / 3 | 7531 / 3 |
| 11 | m1 | tau diverso | 70199 / 15 | 62099 / 13 | 53543 / 13 | 60602 / 12 |
| 11 | m2 | tau diverso | 25615 / 8 | 20515 / 7 | 23161 / 7 | 23161 / 7 |
| 11 | m3 | tau diverso | 5826 / 2 | 9948 / 3 | 5826 / 2 | 9948 / 3 |
| 12 | m1 | tau diverso | 68701 / 14 | 70199 / 15 | 68701 / 14 | 62099 / 13 |
| 12 | m2 | tau diverso | 23161 / 7 | 28242 / 9 | — / 7 | — / 7 |
| 12 | m3 | tau diverso | 9948 / 3 | — / 3 | 9948 / 3 | 8243 / 2 |
| 13 | m1 | tau diverso | 70199 / 15 | — / 15 | 62099 / 13 | — / 13 |
| 13 | m2 | tau diverso | 28242 / 9 | 23161 / 7 | 20515 / 7 | 20515 / 7 |
| 13 | m3 | tau diverso | — / 3 | 5826 / 2 | — / 3 | 9948 / 3 |
| 14 | m1 | tau diverso | 60602 / 12 | 60145 / 14 | 78298 / 17 | 69742 / 17 |
| 14 | m2 | tau diverso | 20535 / 6 | 25615 / 8 | 28242 / 9 | 28242 / 9 |
| 14 | m3 | tau diverso | 5826 / 2 | 9948 / 3 | 7531 / 3 | — / 3 |
| 15 | m1 | tau diverso | 62099 / 13 | 63597 / 14 | 62099 / 13 | 62099 / 13 |
| 15 | m2 | tau diverso | 23161 / 7 | 25787 / 8 | 25615 / 8 | 23161 / 7 |
| 15 | m3 | tau diverso | 9948 / 3 | — / 3 | 8243 / 2 | 5826 / 2 |
| 16 | m1 | tau diverso | 70199 / 15 | 68701 / 14 | 70199 / 15 | 68701 / 14 |
| 16 | m2 | tau diverso | 25787 / 8 | 23161 / 7 | 25787 / 8 | 25615 / 8 |
| 16 | m3 | tau diverso | — / 3 | 5826 / 2 | 9948 / 3 | 9948 / 3 |
| 17 | m1 | tau diverso | 62099 / 13 | 62099 / 13 | 68701 / 14 | 62099 / 13 |
| 17 | m2 | tau diverso | 25615 / 8 | — / 7 | 23161 / 7 | 23161 / 7 |
| 17 | m3 | tau diverso | 5826 / 2 | 9948 / 3 | — / 3 | — / 3 |
| 18 | m1 | tau diverso | 70199 / 15 | — / 13 | 63597 / 14 | 68701 / 14 |
| 18 | m2 | tau diverso | 23161 / 7 | 22969 / 8 | 25615 / 8 | — / 7 |
| 18 | m3 | tau diverso | 9948 / 3 | — / 3 | 7531 / 3 | 5826 / 2 |
| 19 | m1 | tau diverso | — / 15 | 68244 / 16 | 60602 / 12 | 62099 / 13 |
| 19 | m2 | tau diverso | 28242 / 9 | 23161 / 7 | 23161 / 7 | 20515 / 7 |
| 19 | m3 | tau diverso | — / 3 | 7531 / 3 | 8243 / 2 | 9948 / 3 |
| 20 | m1 | tau diverso | 61643 / 15 | 62099 / 13 | 70199 / 15 | — / 13 |
| 20 | m3 | tau diverso | 7531 / 3 | 8243 / 2 | 9948 / 3 | 8243 / 2 |

(37 righe non elencate: il dettaglio e' in `confronto_aree_peso.csv`)

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 9 | m1 | 0.333 | 1.000 | 1.000 | 0.556 | 0.667 |
| 9 | m2 | 0.444 | 0.000 | 0.000 | 0.333 | 0.444 |
| 9 | m3 | 0.222 | 0.000 | 0.000 | 0.111 | 0.222 |
| 10 | m1 | 0.833 | 0.833 | 0.667 | 1.000 | 0.333 |
| 10 | m2 | 0.000 | 0.000 | 0.333 | 0.000 | 0.333 |
| 10 | m3 | 0.167 | 0.167 | 0.000 | 0.000 | 0.167 |
| 11 | m1 | 0.583 | 0.583 | 0.917 | 0.917 | 0.333 |
| 11 | m2 | 0.167 | 0.333 | 0.083 | 0.000 | 0.333 |
| 11 | m3 | 0.250 | 0.083 | 0.000 | 0.083 | 0.250 |
| 12 | m1 | 0.833 | 0.667 | 0.500 | 0.917 | 0.417 |
| 12 | m2 | 0.083 | 0.167 | 0.083 | 0.083 | 0.083 |
| 12 | m3 | 0.083 | 0.167 | 0.417 | 0.000 | 0.417 |
| 13 | m1 | 0.583 | 0.833 | 0.667 | 0.333 | 0.500 |
| 13 | m2 | 0.167 | 0.167 | 0.250 | 0.667 | 0.500 |
| 13 | m3 | 0.250 | 0.000 | 0.083 | 0.000 | 0.250 |
| 14 | m1 | 1.000 | 0.917 | 0.917 | 0.750 | 0.250 |
| 14 | m2 | 0.000 | 0.083 | 0.083 | 0.250 | 0.250 |
| 14 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 15 | m1 | 0.917 | 0.750 | 1.000 | 0.833 | 0.250 |
| 15 | m2 | 0.083 | 0.167 | 0.000 | 0.083 | 0.167 |
| 15 | m3 | 0.000 | 0.083 | 0.000 | 0.083 | 0.083 |
| 16 | m1 | 0.833 | 0.583 | 0.917 | 0.667 | 0.333 |
| 16 | m2 | 0.083 | 0.417 | 0.083 | 0.167 | 0.333 |
| 16 | m3 | 0.083 | 0.000 | 0.000 | 0.167 | 0.167 |
| 17 | m1 | 0.667 | 0.667 | 0.500 | 0.833 | 0.333 |
| 17 | m2 | 0.250 | 0.333 | 0.417 | 0.167 | 0.250 |
| 17 | m3 | 0.083 | 0.000 | 0.083 | 0.000 | 0.083 |
| 18 | m1 | 0.667 | 0.583 | 0.750 | 0.667 | 0.167 |
| 18 | m2 | 0.250 | 0.417 | 0.250 | 0.333 | 0.167 |
| 18 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 19 | m1 | 0.500 | 0.667 | 0.917 | 0.500 | 0.417 |
| 19 | m2 | 0.500 | 0.167 | 0.083 | 0.417 | 0.417 |
| 19 | m3 | 0.000 | 0.167 | 0.000 | 0.083 | 0.167 |
| 20 | m1 | 0.500 | 0.667 | 0.750 | 0.917 | 0.417 |
| 20 | m2 | 0.417 | 0.167 | 0.167 | 0.083 | 0.333 |
| 20 | m3 | 0.083 | 0.167 | 0.083 | 0.000 | 0.167 |
| 21 | m1 | 0.833 | 0.833 | 0.500 | 0.917 | 0.417 |
| 21 | m2 | 0.167 | 0.167 | 0.500 | 0.083 | 0.417 |
| 21 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 22 | m1 | 0.750 | 0.750 | 0.750 | 1.000 | 0.250 |
| 22 | m2 | 0.167 | 0.250 | 0.167 | 0.000 | 0.250 |
| 22 | m3 | 0.083 | 0.000 | 0.083 | 0.000 | 0.083 |
| 23 | m1 | 0.833 | 0.583 | 0.833 | 0.333 | 0.500 |
| 23 | m2 | 0.000 | 0.417 | 0.167 | 0.500 | 0.500 |
| 23 | m3 | 0.167 | 0.000 | 0.000 | 0.167 | 0.167 |
| 24 | m1 | 0.583 | 0.917 | 0.917 | 0.833 | 0.333 |
| 24 | m2 | 0.417 | 0.083 | 0.083 | 0.167 | 0.333 |
| 24 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 25 | m1 | 0.917 | 0.917 | 0.833 | 0.833 | 0.083 |
| 25 | m2 | 0.083 | 0.000 | 0.167 | 0.167 | 0.167 |
| 25 | m3 | 0.000 | 0.083 | 0.000 | 0.000 | 0.083 |
| 26 | m1 | 0.667 | 0.833 | 0.083 | 0.917 | 0.833 |
| 26 | m2 | 0.250 | 0.167 | 0.917 | 0.083 | 0.833 |
| 26 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 27 | m1 | 0.833 | 0.750 | 0.500 | 0.833 | 0.333 |
| 27 | m2 | 0.167 | 0.167 | 0.333 | 0.167 | 0.167 |
| 27 | m3 | 0.000 | 0.083 | 0.167 | 0.000 | 0.167 |
| 28 | m1 | 0.750 | 1.000 | 1.000 | 0.583 | 0.417 |
| 28 | m2 | 0.250 | 0.000 | 0.000 | 0.417 | 0.417 |
| 28 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |

(24 righe non elencate: il dettaglio completo e' in `confronto_aree_peso.csv`)
