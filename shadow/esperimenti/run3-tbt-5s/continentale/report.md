[run] setup-first-blocks non specificato: uso 98 (minimo calcolato: 98)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: continentale
  target-block-time=5s  setup=98  misura=200 blocchi  epoca=12
════════════════════════════════════════════════════════════════════
[treasury] gia' presente: /home/mattu/multichain/shadow/config/treasury.json (FORCE=1 per rigenerarlo)
[gen_topology] continentale -> /home/mattu/multichain/shadow/continentale/topologia_myledger_continentale.gml (10 nodi, 10 archi)

  arco                                  D (km)   one-way ms     RTT ms
  --------------------------------------------------------------------
  Milano-Frankfurt                       518.1        4.127       8.25
  Milano-Madrid                         1188.2        8.818      17.64
  Frankfurt-Madrid                      1445.9       10.621      21.24
  Zurich-Milano                          218.4        2.529       5.06
  Marseille-Milano                       387.6        3.713       7.43
  Amsterdam-Frankfurt                    363.4        3.544       7.09
  Warszawa-Frankfurt                     890.1        7.231      14.46
  Paris-Frankfurt                        477.9        4.345       8.69
  London-Frankfurt                       637.8        5.464      10.93
  Lisboa-Madrid                          502.4        4.517       9.03

  RTT end-to-end (ms), cammino minimo andata+ritorno:
             0       1       2       3       4       5       6       7       8       9
    0     0.00    8.25   17.64    5.06    7.43   15.34   22.72   16.94   19.18   26.67  HUB_IT_Milano
    1     8.25    0.00   21.24   13.31   15.68    7.09   14.46    8.69   10.93   30.28  HUB_DE_Frankfurt
    2    17.64   21.24    0.00   22.69   25.06   28.33   35.70   29.93   32.17    9.03  HUB_ES_Madrid
    3     5.06   13.31   22.69    0.00   12.48   20.40   27.77   22.00   24.24   31.73  Zurich
    4     7.43   15.68   25.06   12.48    0.00   22.77   30.14   24.37   26.61   34.10  Marseille
    5    15.34    7.09   28.33   20.40   22.77    0.00   21.55   15.78   18.02   37.36  Amsterdam
    6    22.72   14.46   35.70   27.77   30.14   21.55    0.00   23.15   25.39   44.74  Warszawa
    7    16.94    8.69   29.93   22.00   24.37   15.78   23.15    0.00   19.62   38.97  Paris
    8    19.18   10.93   32.17   24.24   26.61   18.02   25.39   19.62    0.00   41.20  London
    9    26.67   30.28    9.03   31.73   34.10   37.36   44.74   38.97   41.20    0.00  Lisboa

  RTT massimo: 44.74 ms  (Warszawa <-> Lisboa)
OK: /home/mattu/multichain/shadow/continentale/topologia_myledger_continentale.gml — 10 nodi, 20 archi, connesso
[prepare_params] catena 'poesiacontinentale' pronta
[prepare_params]   target-block-time = 5 s, setup-first-blocks = 98, epoca = 12 blocchi
[prepare_params]   treasury          = 18QrmhtdHAfw8gknT5hxBStfGY63AhuQZCSDcg
[prepare_params]   target-block-time = 5                  # Target time between blocks (transaction confirmation delay), seconds. (2 - 86400)
[prepare_params]   enable-wpoa = true                      # Master switch: enable the whole wPoA protocol (weights stream + weighted selection + VRF + RANDAO + sortition). More specific enable-wpoa-* flags override it per phase. Default 0 (native MultiChain mining).
[prepare_params]   wpoa-sortition-delta = 0.5              # wPoA sortition delay band half-width as a fraction of target-block-time, delta in (0,1). Small: narrower band, more forks; large: more latency. Consensus-critical: identical on all nodes. Default 0.5.
[prepare_params]   wpoa-sortition-lambda = 0.2             # wPoA sortition feedback gain lambda in [0,1]: weight of the global correction Phi recentring the mean block time on target. 0 disables it. Consensus-critical: identical on all nodes. Default 0.
[prepare_params]   enable-weight-engine = true             # Weight engine: derive each cluster's wpoa-weights value from on-chain inputs (membership/ESG/activity/reconciliation) per epoch, instead of a static -weight. Requires enable-wpoa-weights. Consensus-critical: identical on all nodes. Default 0.
[prepare_params]   weight-epoch-length = 12                # Weight engine epoch length in blocks: epoch(height) = height / this. Consensus-critical: must be identical on all nodes. Default 100. (1 - 1000000)
[prepare_params]   weight-treasury-address = 18QrmhtdHAfw8gknT5hxBStfGY63AhuQZCSDcg # Weight engine treasury address. R_k = value paid to THIS address by transactions the miner signed, derived from the epoch's confirmed blocks, never declared. Empty means R_k = 0 for all clusters. Consensus-critical: identical on all nodes.
[prepare_params]   first-block-reward = 100000000000000                 # Different mining reward for first block only, ignored if negative. (-1 - 1000000000000000000)
[prepare_params]   minimum-relay-fee = 20000000                   # Minimum transaction fee, per 1000 bytes, in raw units of native currency. (0 - 1000000000)
[gen_shadow_yaml] continentale -> /home/mattu/multichain/shadow/continentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 2430s simulati (98 blocchi di setup + 200 misurati a 5s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 534s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello continentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 420
  fase di setup (PoA)  : 98 blocchi (height 1..98)
  finestra wPoA misurata: 322 blocchi (height 99..420)

  intervallo fra blocchi (finestra wPoA), target = 5 s:
    media       5.64 s     scarto vs target +0.64 s (+12.8%)
    mediana     6.00 s
    dev.std     1.46 s
    min/max     3.00 / 8.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e3                 1         1         1
  e5             12606      5186      3269
  e6             17404      6500          
  e7             60602     20535      7531
  e8             62099     23161      8243
  e9             68701     25615      9948
  e10            63597     25787          
  e11            70199     25615      5826
  e12            68701     23161      9948
  e13            70199     28242          
  e14            60602     20535      5826
  e15            62099     23161      9948
  e16            70199     25787          
  e17            62099     25615      5826
  e18            70199     23161      9948
  e19                      28242          
  e20            61643     23161      7531
  e21            60602                8243
  e22            62099     20515          
  e23            68701     25615      7531
  e24            70199     23161      9948
  e25            62099                    
  e26            70199     25596      7531
  e27            71696     28242      8243
  e28            68701     23161      9948
  e29            70199     25615          
  e30            62099     23161      7531
  e31            70199     25787      8243
  e32            60602     20535      9948
  e33            62099     25615      8243
  e34            70199     25787      9948
  record totali: 82

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs       235    73.0%     70199    66.3%
  m2     19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS        64    19.9%     25787    24.3%
  m3     16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj        23     7.1%      9948     9.4%

  blocchi consecutivi dello stesso proposer: 227 osservati, 185.3 attesi

  chi-quadro = 6.563  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [2.50, 7.50] s   (T=5 s, delta=0.5, Dmax=2.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          343     2.330     5.266     7.482         55.3%
  m2          343     2.412     6.316     7.533         76.3%
  m3          343     2.550     6.912     7.548         88.2%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 343 round):
    media      1.735 s
    mediana    1.527 s
    minimo     0.001 s
    5o perc.   0.078 s
    round con G < 100 ms: 21 su 343 (6.1%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         420       9  999246.6591  00f2a6d2fb111dc6   007cccaf984afa64
  m1            420       9     109.1154  00f2a6d2fb111dc6   007cccaf984afa64
  m2            420       9     109.7137  00f2a6d2fb111dc6   007cccaf984afa64
  m3            420       9      21.0017  00f2a6d2fb111dc6   007cccaf984afa64
  c1            420       9      85.9884  00f2a6d2fb111dc6   007cccaf984afa64
  c2            420       9      90.5896  00f2a6d2fb111dc6   007cccaf984afa64
  c3            420       9      92.8916  00f2a6d2fb111dc6   007cccaf984afa64
  c4            420       9      94.2952  00f2a6d2fb111dc6   007cccaf984afa64
  c5            421       9      95.4128  00e8b52fa79ed4a8   007cccaf984afa64
  ca            421       9      49.3572  00e8b52fa79ed4a8   007cccaf984afa64
  -> teste diverse ma altezze a 1 blocco di distanza e stesso hash sepolto:
     e' il normale ritardo di propagazione fra i nodi, non un fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs,85.56
  m2,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS,26.46
  m3,16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj,24.17
  c1,1SSC2XrW9PNniKVfAx3JCNZpVNFW1DAQfiFm4j,17.50
  c2,1bgdBC45cJoHQt1vDh2YdLX2naj9s5n42n8Q5,77.16
  c3,1GMNEQPW8JDLYbPsyfnKhv4RKdRhpiGNa3P9Zo,99.26
  c4,18pe3itSBY7SpsRAvT1vdKtLA2jcrWRfPTNLku,92.76
  c5,1ZPKsqPFkrpVzhBzVbQPBbTxSQqwDgsWSSaFew,70.53

── Adesioni ai cluster (membership.csv) ──
  m2,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS
  c5,1ZPKsqPFkrpVzhBzVbQPBbTxSQqwDgsWSSaFew,16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj
  c4,18pe3itSBY7SpsRAvT1vdKtLA2jcrWRfPTNLku,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS
  c2,1bgdBC45cJoHQt1vDh2YdLX2naj9s5n42n8Q5,1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs
  c3,1GMNEQPW8JDLYbPsyfnKhv4RKdRhpiGNa3P9Zo,19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS
  m3,16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj,16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj
  m1,1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs,1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs
  c1,1SSC2XrW9PNniKVfAx3JCNZpVNFW1DAQfiFm4j,1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  67,6,m3,49.6786,9.5357
  67,6,m2,51.5216,29.7130
  67,6,m1,49.679,45.2951
  73,7,m3,40.8735,7.7747
  73,7,m2,21.7634,11.8580
  73,7,m1,104.5647,97.4365
  85,8,m3,33.3906,6.2781
  85,8,m2,110.2142,64.9285
  85,8,m1,107.648,100.3656
  97,9,m3,27.6031,5.1206
  97,9,m2,45.1349,25.8809
  ... (97 righe totali)

── Movimenti GAS (init + rifornimenti) (gas_transfers.csv) ──
  11,init,c1,100
  11,init,c2,100
  11,init,c3,100
  11,init,c4,100
  11,init,c5,100
  11,init,m1,50
  11,init,m2,50
  11,init,m3,50
  11,init,ca,50
  67,refill,m1,100
  73,refill,m1,100
  73,refill,m2,100
  ... (58 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 3404
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             112438
  fold di fallback RANDAO          0
  score di sortition calcolati     1032
  attese per mappa pesi vuota      344
  pesi registrati sullo stream     86
  letture della mappa dei pesi     9886
  epoche calcolate dal motore      350
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 33, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "16DXgBMMssAC9UUE4fZDpJUNaRG6wpVbEBV2Lj", "published": 8243, "published_epoch": 33, "recomputed": 8243, "verdict": "ok"}, {"address": "19EEeSY2KeYEN5fm97hBm6Egx4Qu8ShLcWD9iS", "published": 25615, "published_epoch": 33, "recomputed": 25615, "verdict": "ok"}, {"address": "1Z3VEAVVVNdushdAEx1zY2ufwRC6JUZYLedtDs", "published": 62099, "published_epoch": 33, "recomputed": 62099, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/continentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/continentale/run