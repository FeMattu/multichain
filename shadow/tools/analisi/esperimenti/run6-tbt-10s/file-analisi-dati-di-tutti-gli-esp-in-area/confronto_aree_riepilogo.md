# Confronto fra aree — run6-tbt-10s

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
| peso identico fra i livelli | 7 | nessuna divergenza da spiegare |
| peso diverso, **ESG identico**, `tau` diverso | 14 | atteso: canale latenza -> throughput -> attivita' |
| peso diverso, **ESG diverso** | 0 | anomalia nei dati: seed o certificazione ESG non riprodotti |

**Nessuna coppia ha ESG diverso fra i livelli**: la certificazione e le adesioni sono state riprodotte identiche in tutte le aree, e ogni divergenza di peso e' riconducibile alla sola attivita' misurata.

## Divergenze di peso, con l'attivita' che le spiega

| epoca | host | causa | continentale (peso / tau cluster) | intercontinentale (peso / tau cluster) | nazionale (peso / tau cluster) | regionale (peso / tau cluster) |
|---|---|---|---|---|---|---|
| 1 | m1 | tau diverso | 502990 / 137 | 511089 / 139 | 501493 / 136 | 502990 / 137 |
| 1 | m2 | tau diverso | 199052 / 76 | 199052 / 76 | 193971 / 74 | 199052 / 76 |
| 2 | m1 | tau diverso | 785078 / 214 | 768423 / 212 | 796172 / 218 | 804271 / 220 |
| 2 | m2 | tau diverso | 298559 / 115 | 301205 / 115 | 308720 / 119 | 306266 / 118 |
| 2 | m3 | tau diverso | 74727 / 41 | 74727 / 41 | 76432 / 42 | 76432 / 42 |
| 3 | m1 | tau diverso | 823464 / 226 | 814324 / 221 | 805768 / 221 | — / 220 |
| 3 | m2 | tau diverso | 268877 / 122 | 265001 / 120 | 259890 / 119 | 256000 / 119 |
| 3 | m3 | tau diverso | 79841 / 44 | 78137 / 43 | — / 42 | 78137 / 43 |
| 4 | m1 | tau diverso | 820469 / 224 | 838621 / 227 | 830065 / 227 | 812370 / 222 |
| 4 | m2 | tau diverso | 313801 / 121 | 316256 / 122 | 316428 / 122 | 311175 / 120 |
| 4 | m3 | tau diverso | 78137 / 43 | — / 43 | 77424 / 44 | 76432 / 42 |
| 5 | m1 | tau diverso | 839662 / 230 | 813867 / 223 | 811330 / 219 | 866954 / 238 |
| 5 | m2 | tau diverso | 324155 / 124 | 313993 / 120 | 311366 / 119 | 334297 / 129 |
| 5 | m3 | tau diverso | 79841 / 44 | 75720 / 43 | 76432 / 42 | 83251 / 46 |

## Quota osservata per epoca

Qui la differenza fra livelli e' invece **legittima e attesa**: e' l'effetto della latenza sulla corsa dei timer, a parita' di peso vigente. Le epoche della fase di setup non hanno blocchi misurati e sono omesse.

| epoca | host | continentale | intercontinentale | nazionale | regionale | spread |
|---|---|---|---|---|---|---|
| 2 | m1 | 0.702 | 0.574 | 0.532 | 0.809 | 0.277 |
| 2 | m2 | 0.298 | 0.383 | 0.383 | 0.149 | 0.234 |
| 2 | m3 | 0.000 | 0.043 | 0.085 | 0.043 | 0.085 |
| 3 | m1 | 0.660 | 0.740 | 0.610 | 0.740 | 0.130 |
| 3 | m2 | 0.270 | 0.200 | 0.280 | 0.190 | 0.090 |
| 3 | m3 | 0.070 | 0.060 | 0.110 | 0.070 | 0.050 |
| 4 | m1 | 0.780 | 0.770 | 0.710 | 0.760 | 0.070 |
| 4 | m2 | 0.150 | 0.180 | 0.240 | 0.140 | 0.100 |
| 4 | m3 | 0.070 | 0.050 | 0.050 | 0.100 | 0.050 |
| 5 | m1 | 0.620 | 0.650 | 0.830 | 0.690 | 0.210 |
| 5 | m2 | 0.290 | 0.260 | 0.170 | 0.230 | 0.120 |
| 5 | m3 | 0.090 | 0.090 | 0.000 | 0.080 | 0.090 |
| 6 | m1 | 0.755 | 0.790 | 0.636 | 0.813 | 0.177 |
| 6 | m2 | 0.184 | 0.190 | 0.273 | 0.176 | 0.097 |
| 6 | m3 | 0.061 | 0.020 | 0.091 | 0.011 | 0.080 |
| 7 | m1 | — | 1.000 | — | — | 0.000 |
| 7 | m2 | — | 0.000 | — | — | 0.000 |
| 7 | m3 | — | 0.000 | — | — | 0.000 |
