Confronto fra livelli — target-block-time 15 s, finestra oltre il blocco 60

livello              RTT max  blocchi  dt medio    sd dt         quote proposer G mediano  G<100ms  teste
------------------------------------------------------------------------------------------------------------
regionale              10.0m      107    15.90s    4.52s         68% / 24% / 7%     3.39s    3.4%      1
nazionale              22.0m      113    15.25s    4.61s         65% / 27% / 8%     3.82s    3.3%      1
continentale           44.7m      109    15.77s    4.47s         66% / 28% / 6%     4.50s    3.4%      1
intercontinentale     112.0m      112    15.44s    3.98s        62% / 25% / 12%     4.26s    0.8%      1

Blocchi consecutivi dello stesso proposer (osservati vs attesi):
regionale             64 vs   56.2
nazionale             64 vs   55.9
continentale          72 vs   55.7
intercontinentale     55 vs   52.0

Nota: 'RTT max' e' in millisecondi (cammino minimo peggiore fra due host).
    'G' e' il margine della timer race D(2)-D(1) (Def. 5.15).
    'teste' e' il numero di best-hash distinti a fine run: 1 = nessun fork.