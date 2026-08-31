# Confronto fra aree — run1-tbt-15s

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
| peso identico fra i livelli | 12 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 33 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 2 | m1 | tau diverso | 4980 / 2 | 4980 / 2 | 8637 / 4 | 4980 / 2 |
| 2 | m2 | tau diverso | 4390 / 2 | 4390 / 2 | 7572 / 4 | 4390 / 2 |
| 2 | m3 | tau diverso | 2418 / 1 | 2418 / 1 | 3961 / 2 | 2418 / 1 |
| 3 | m1 | tau diverso | 47146 / 38 | 47146 / 38 | 86978 / 36 | 47146 / 38 |
| 3 | m2 | tau diverso | 24749 / 21 | 24749 / 21 | 43134 / 19 | 24749 / 21 |
| 3 | m3 | tau diverso | 7967 / 8 | 7967 / 8 | 12849 / 7 | 7967 / 8 |
| 4 | m1 | tau diverso | 94273 / 39 | 89605 / 37 | 89605 / 37 | 89605 / 37 |
| 4 | m2 | tau diverso | 46543 / 21 | 44838 / 20 | 42596 / 19 | 44838 / 20 |
| 5 | m1 | tau diverso | 86978 / 36 | — / 37 | — / 37 | 96314 / 40 |
| 5 | m2 | tau diverso | 43134 / 19 | — / 20 | 47081 / 21 | 48785 / 22 |
| 6 | m1 | tau diverso | 100982 / 42 | 89000 / 38 | 95710 / 41 | — / 40 |
| 6 | m2 | tau diverso | 52732 / 24 | 42421 / 20 | 48785 / 22 | — / 22 |
| 6 | m3 | tau diverso | 12435 / 8 | 11099 / 7 | 14185 / 8 | 12435 / 8 |
| 7 | m1 | tau diverso | 96314 / 40 | 94273 / 39 | 76185 / 31 | 98336 / 42 |
| 7 | m2 | tau diverso | 47081 / 21 | 48785 / 22 | 36945 / 16 | 44664 / 21 |
| 7 | m3 | tau diverso | 14185 / 8 | 14185 / 8 | 11514 / 6 | 14185 / 8 |
| 8 | m1 | tau diverso | 89605 / 37 | 98356 / 41 | 86978 / 36 | 98356 / 41 |
| 8 | m2 | tau diverso | 44838 / 20 | 47081 / 21 | 44838 / 20 | 51027 / 23 |
| 9 | m1 | tau diverso | 100982 / 42 | 94273 / 39 | 91646 / 38 | 98941 / 41 |
| 9 | m2 | tau diverso | 48785 / 22 | 48785 / 22 | 47081 / 21 | 48785 / 22 |
| 9 | m3 | tau diverso | 14185 / 8 | 14185 / 8 | — / 7 | 12435 / 8 |
| 10 | m1 | tau diverso | 103024 / 43 | 103024 / 43 | 94273 / 39 | 93688 / 39 |
| 10 | m2 | tau diverso | 51027 / 23 | 51027 / 23 | 44838 / 20 | — / 22 |
| 10 | m3 | tau diverso | — / 8 | — / 8 | 11099 / 7 | 12849 / 7 |
| 11 | m1 | tau diverso | 96314 / 40 | 86978 / 36 | 96314 / 40 | 82895 / 34 |
| 11 | m2 | tau diverso | 48785 / 22 | 44838 / 20 | 48785 / 22 | 38475 / 18 |
| 11 | m3 | tau diverso | 12435 / 8 | 11099 / 7 | 14185 / 8 | — / 7 |
| 12 | m1 | tau diverso | 91646 / 38 | 87563 / 36 | — / 40 | 103024 / 43 |
| 12 | m2 | tau diverso | 47081 / 21 | 40892 / 18 | — / 22 | 51027 / 23 |
| 12 | m3 | tau diverso | 12849 / 7 | 12849 / 7 | — / 8 | 12435 / 8 |
| 13 | m1 | tau diverso | 84937 / 35 | 91646 / 38 | 91627 / 39 | 91646 / 38 |
| 13 | m2 | tau diverso | 42596 / 19 | 47081 / 21 | 44664 / 21 | 44838 / 20 |
| 13 | m3 | tau diverso | — / 7 | — / 7 | 11099 / 7 | 12849 / 7 |

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 6 | m1 | 0.636 | 0.727 | 0.545 | 0.727 | 0.182 |
| 6 | m2 | 0.273 | 0.182 | 0.273 | 0.273 | 0.091 |
| 6 | m3 | 0.091 | 0.091 | 0.182 | 0.000 | 0.182 |
| 7 | m1 | 0.667 | 0.750 | 0.833 | 1.000 | 0.333 |
| 7 | m2 | 0.333 | 0.250 | 0.167 | 0.000 | 0.333 |
| 7 | m3 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| 8 | m1 | 0.417 | 0.500 | 0.667 | 0.583 | 0.250 |
| 8 | m2 | 0.583 | 0.167 | 0.333 | 0.333 | 0.417 |
| 8 | m3 | 0.000 | 0.333 | 0.000 | 0.083 | 0.333 |
| 9 | m1 | 0.667 | 0.583 | 0.750 | 0.833 | 0.250 |
| 9 | m2 | 0.250 | 0.167 | 0.083 | 0.083 | 0.167 |
| 9 | m3 | 0.083 | 0.250 | 0.167 | 0.083 | 0.167 |
| 10 | m1 | 1.000 | 0.667 | 0.667 | 0.500 | 0.500 |
| 10 | m2 | 0.000 | 0.167 | 0.333 | 0.500 | 0.500 |
| 10 | m3 | 0.000 | 0.167 | 0.000 | 0.000 | 0.167 |
| 11 | m1 | 0.667 | 0.583 | 0.583 | 0.417 | 0.250 |
| 11 | m2 | 0.333 | 0.333 | 0.250 | 0.417 | 0.167 |
| 11 | m3 | 0.000 | 0.083 | 0.167 | 0.167 | 0.167 |
| 12 | m1 | 0.500 | 0.750 | 0.667 | 0.583 | 0.250 |
| 12 | m2 | 0.250 | 0.083 | 0.333 | 0.333 | 0.250 |
| 12 | m3 | 0.250 | 0.167 | 0.000 | 0.083 | 0.250 |
| 13 | m1 | 0.500 | 0.333 | 0.500 | 0.583 | 0.250 |
| 13 | m2 | 0.333 | 0.667 | 0.333 | 0.250 | 0.417 |
| 13 | m3 | 0.167 | 0.000 | 0.167 | 0.167 | 0.167 |
| 14 | m1 | 0.833 | 0.750 | 0.500 | 0.917 | 0.417 |
| 14 | m2 | 0.167 | 0.167 | 0.417 | 0.000 | 0.417 |
| 14 | m3 | 0.000 | 0.083 | 0.083 | 0.083 | 0.083 |
| 15 | m1 | 1.000 | 0.600 | 0.833 | — | 0.400 |
| 15 | m2 | 0.000 | 0.400 | 0.167 | — | 0.400 |
| 15 | m3 | 0.000 | 0.000 | 0.000 | — | 0.000 |
