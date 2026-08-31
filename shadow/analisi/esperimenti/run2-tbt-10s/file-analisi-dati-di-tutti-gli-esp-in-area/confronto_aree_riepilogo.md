# Confronto fra aree — run2-tbt-10s

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
| peso identico fra i livelli | 19 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 65 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 3 | m1 | tau diverso | 20933 / 4 | 20933 / 4 | 20933 / 4 | 21682 / 5 |
| 4 | m1 | tau diverso | 107087 / 26 | 107087 / 26 | 107087 / 26 | 104092 / 24 |
| 4 | m2 | tau diverso | 41030 / 14 | 41030 / 14 | 41030 / 14 | 38404 / 13 |
| 5 | m1 | tau diverso | 112191 / 26 | 105590 / 25 | 104092 / 24 | 105590 / 25 |
| 5 | m2 | tau diverso | 38404 / 13 | 38404 / 13 | 38404 / 13 | 41030 / 14 |
| 6 | m1 | tau diverso | 105590 / 25 | 113689 / 27 | 105590 / 25 | 123285 / 30 |
| 6 | m2 | tau diverso | 41030 / 14 | 41030 / 14 | — / 13 | 46111 / 16 |
| 6 | m3 | tau diverso | 9236 / 4 | 10941 / 5 | 13358 / 5 | 15062 / 6 |
| 7 | m1 | tau diverso | 116683 / 29 | 105590 / 25 | 115186 / 28 | 105590 / 25 |
| 7 | m2 | tau diverso | 46111 / 16 | 43484 / 15 | 41010 / 15 | 38404 / 13 |
| 7 | m3 | tau diverso | 15062 / 6 | 13358 / 5 | — / 5 | 13358 / 5 |
| 8 | m1 | tau diverso | 113689 / 27 | 113689 / 27 | 105590 / 25 | 115186 / 28 |
| 8 | m2 | tau diverso | 43484 / 15 | 41030 / 14 | 38404 / 13 | 46111 / 16 |
| 8 | m3 | tau diverso | 13358 / 5 | — / 5 | 10941 / 5 | — / 5 |
| 9 | m1 | tau diverso | 105590 / 25 | 107087 / 26 | 115186 / 28 | 105590 / 25 |
| 9 | m2 | tau diverso | 38404 / 13 | — / 14 | 46111 / 16 | 38404 / 13 |
| 9 | m3 | tau diverso | — / 5 | 10941 / 5 | 15062 / 6 | 10941 / 5 |
| 10 | m1 | tau diverso | — / 25 | 112191 / 26 | 112191 / 26 | 123285 / 30 |
| 10 | m2 | tau diverso | 41030 / 14 | 35758 / 13 | 38404 / 13 | 46111 / 16 |
| 10 | m3 | tau diverso | 10941 / 5 | 13358 / 5 | 13358 / 5 | 15062 / 6 |
| 11 | m1 | tau diverso | 105133 / 27 | 107087 / 26 | 107087 / 26 | 105590 / 25 |
| 11 | m2 | tau diverso | — / 14 | 43484 / 15 | 43484 / 15 | 41030 / 14 |
| 12 | m1 | tau diverso | 97490 / 23 | 105590 / 25 | 121788 / 29 | 121788 / 29 |
| 12 | m2 | tau diverso | 35758 / 13 | 41030 / 14 | 46111 / 16 | 43484 / 15 |
| 13 | m1 | tau diverso | 123285 / 30 | 115186 / 28 | 115186 / 28 | 115186 / 28 |
| 13 | m2 | tau diverso | 46111 / 16 | — / 14 | 41030 / 14 | 46111 / 16 |
| 13 | m3 | tau diverso | 10941 / 5 | 13358 / 5 | 15062 / 6 | 12645 / 6 |
| 14 | m1 | tau diverso | 105590 / 25 | 112191 / 26 | — / 28 | 105590 / 25 |
| 14 | m2 | tau diverso | 38404 / 13 | 40838 / 15 | 46111 / 16 | 38404 / 13 |
| 14 | m3 | tau diverso | 13358 / 5 | — / 5 | 13358 / 5 | 11653 / 4 |
| 15 | m1 | tau diverso | 123285 / 30 | 116683 / 29 | 105133 / 27 | — / 25 |
| 15 | m2 | tau diverso | 46111 / 16 | 46111 / 16 | 43484 / 15 | 38576 / 13 |
| 15 | m3 | tau diverso | 15062 / 6 | 10941 / 5 | — / 5 | 13358 / 5 |
| 16 | m1 | tau diverso | 105590 / 25 | 112191 / 26 | 107087 / 26 | 97034 / 25 |
| 16 | m2 | tau diverso | 41030 / 14 | 41030 / 14 | 41030 / 14 | 40858 / 14 |
| 16 | m3 | tau diverso | 13358 / 5 | 13358 / 5 | 10941 / 5 | — / 5 |
| 17 | m1 | tau diverso | 123285 / 30 | 107087 / 26 | 113689 / 27 | 115186 / 28 |
| 17 | m2 | tau diverso | 46111 / 16 | 38404 / 13 | — / 14 | 43656 / 15 |
| 17 | m3 | tau diverso | — / 5 | — / 5 | 13358 / 5 | 10941 / 5 |
| 18 | m1 | tau diverso | 115186 / 28 | 115186 / 28 | 105590 / 25 | 113689 / 27 |

(25 righe non elencate: il dettaglio e' in `confronto_aree_peso.csv`)

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 6 | m1 | 0.429 | 1.000 | 0.857 | 1.000 | 0.571 |
| 6 | m2 | 0.571 | 0.000 | 0.000 | 0.000 | 0.571 |
| 6 | m3 | 0.000 | 0.000 | 0.143 | 0.000 | 0.143 |
| 7 | m1 | 0.750 | 0.500 | 0.917 | 0.750 | 0.417 |
| 7 | m2 | 0.167 | 0.500 | 0.083 | 0.250 | 0.417 |
| 7 | m3 | 0.083 | 0.000 | 0.000 | 0.000 | 0.083 |
| 8 | m1 | 0.833 | 0.833 | 0.417 | 0.750 | 0.417 |
| 8 | m2 | 0.167 | 0.167 | 0.583 | 0.083 | 0.500 |
| 8 | m3 | 0.000 | 0.000 | 0.000 | 0.167 | 0.167 |
| 9 | m1 | 0.833 | 0.583 | 0.583 | 0.917 | 0.333 |
| 9 | m2 | 0.167 | 0.417 | 0.333 | 0.000 | 0.417 |
| 9 | m3 | 0.000 | 0.000 | 0.083 | 0.083 | 0.083 |
| 10 | m1 | 0.667 | 0.750 | 0.833 | 0.833 | 0.167 |
| 10 | m2 | 0.250 | 0.250 | 0.083 | 0.167 | 0.167 |
| 10 | m3 | 0.083 | 0.000 | 0.083 | 0.000 | 0.083 |
| 11 | m1 | 0.583 | 0.583 | 0.750 | 0.750 | 0.167 |
| 11 | m2 | 0.250 | 0.333 | 0.083 | 0.167 | 0.250 |
| 11 | m3 | 0.167 | 0.083 | 0.167 | 0.083 | 0.083 |
| 12 | m1 | 0.750 | 1.000 | 0.833 | 1.000 | 0.250 |
| 12 | m2 | 0.250 | 0.000 | 0.167 | 0.000 | 0.250 |
| 12 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 13 | m1 | 0.750 | 0.583 | 0.833 | 0.750 | 0.250 |
| 13 | m2 | 0.250 | 0.417 | 0.167 | 0.250 | 0.250 |
| 13 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 14 | m1 | 0.500 | 0.750 | 0.750 | 0.917 | 0.417 |
| 14 | m2 | 0.417 | 0.167 | 0.083 | 0.083 | 0.333 |
| 14 | m3 | 0.083 | 0.083 | 0.167 | 0.000 | 0.167 |
| 15 | m1 | 0.750 | 0.750 | 0.500 | 0.583 | 0.250 |
| 15 | m2 | 0.167 | 0.167 | 0.167 | 0.417 | 0.250 |
| 15 | m3 | 0.083 | 0.083 | 0.333 | 0.000 | 0.333 |
| 16 | m1 | 0.833 | 0.667 | 0.583 | 0.750 | 0.250 |
| 16 | m2 | 0.083 | 0.333 | 0.333 | 0.250 | 0.250 |
| 16 | m3 | 0.083 | 0.000 | 0.083 | 0.000 | 0.083 |
| 17 | m1 | 0.500 | 0.667 | 0.917 | 0.750 | 0.417 |
| 17 | m2 | 0.250 | 0.333 | 0.083 | 0.167 | 0.250 |
| 17 | m3 | 0.250 | 0.000 | 0.000 | 0.083 | 0.250 |
| 18 | m1 | 0.583 | 0.667 | 0.833 | 0.833 | 0.250 |
| 18 | m2 | 0.250 | 0.333 | 0.083 | 0.167 | 0.250 |
| 18 | m3 | 0.167 | 0.000 | 0.083 | 0.000 | 0.167 |
| 19 | m1 | 0.500 | 0.667 | 0.750 | 0.333 | 0.417 |
| 19 | m2 | 0.500 | 0.167 | 0.250 | 0.583 | 0.417 |
| 19 | m3 | 0.000 | 0.167 | 0.000 | 0.083 | 0.167 |
| 20 | m1 | 0.333 | 0.833 | 0.667 | 0.583 | 0.500 |
| 20 | m2 | 0.667 | 0.167 | 0.250 | 0.417 | 0.500 |
| 20 | m3 | 0.000 | 0.000 | 0.083 | 0.000 | 0.083 |
| 21 | m1 | 0.667 | 0.583 | 0.583 | 0.667 | 0.083 |
| 21 | m2 | 0.333 | 0.250 | 0.417 | 0.333 | 0.167 |
| 21 | m3 | 0.000 | 0.167 | 0.000 | 0.000 | 0.167 |
| 22 | m1 | 0.750 | 0.583 | 0.833 | 0.667 | 0.250 |
| 22 | m2 | 0.250 | 0.417 | 0.167 | 0.333 | 0.250 |
| 22 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 23 | m1 | 0.917 | 0.583 | 0.833 | 0.833 | 0.333 |
| 23 | m2 | 0.083 | 0.250 | 0.167 | 0.167 | 0.167 |
| 23 | m3 | 0.000 | 0.167 | 0.000 | 0.000 | 0.167 |
| 24 | m1 | 0.750 | 0.583 | 0.583 | 0.750 | 0.167 |
| 24 | m2 | 0.167 | 0.417 | 0.250 | 0.250 | 0.250 |
| 24 | m3 | 0.083 | 0.000 | 0.167 | 0.000 | 0.167 |
| 25 | m1 | 0.583 | 0.750 | 0.667 | 0.583 | 0.167 |
| 25 | m2 | 0.250 | 0.167 | 0.250 | 0.417 | 0.250 |
| 25 | m3 | 0.167 | 0.083 | 0.083 | 0.000 | 0.167 |

(9 righe non elencate: il dettaglio completo e' in `confronto_aree_peso.csv`)
