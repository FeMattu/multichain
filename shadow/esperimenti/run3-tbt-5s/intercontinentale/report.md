[run] setup-first-blocks non specificato: uso 98 (minimo calcolato: 98)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: intercontinentale
  target-block-time=5s  setup=98  misura=200 blocchi  epoca=12
════════════════════════════════════════════════════════════════════
[treasury] gia' presente: /home/mattu/multichain/shadow/config/treasury.json (FORCE=1 per rigenerarlo)
[gen_topology] intercontinentale -> /home/mattu/multichain/shadow/intercontinentale/topologia_myledger_intercontinentale.gml (10 nodi, 10 archi)

  arco                                  D (km)   one-way ms     RTT ms
  --------------------------------------------------------------------
  Milano-Frankfurt                       518.1        4.127       8.25
  Milano-New_York                       6464.3       45.750      91.50
  Frankfurt-New_York                    6202.7       43.919      87.84
  Zurich-Milano                          218.4        2.529       5.06
  Marseille-Milano                       387.6        3.713       7.43
  Amsterdam-Frankfurt                    363.4        3.544       7.09
  Warszawa-Frankfurt                     890.1        7.231      14.46
  Paris-Frankfurt                        477.9        4.345       8.69
  London-Frankfurt                       637.8        5.464      10.93
  Toronto-New_York                       550.4        4.853       9.71

  RTT end-to-end (ms), cammino minimo andata+ritorno:
             0       1       2       3       4       5       6       7       8       9
    0     0.00    8.25   91.50    5.06    7.43   15.34   22.72   16.94   19.18  101.21  HUB_IT_Milano
    1     8.25    0.00   87.84   13.31   15.68    7.09   14.46    8.69   10.93   97.54  HUB_DE_Frankfurt
    2    91.50   87.84    0.00   96.56   98.93   94.93  102.30   96.53   98.77    9.71  HUB_US_New_York
    3     5.06   13.31   96.56    0.00   12.48   20.40   27.77   22.00   24.24  106.26  Zurich
    4     7.43   15.68   98.93   12.48    0.00   22.77   30.14   24.37   26.61  108.63  Marseille
    5    15.34    7.09   94.93   20.40   22.77    0.00   21.55   15.78   18.02  104.63  Amsterdam
    6    22.72   14.46  102.30   27.77   30.14   21.55    0.00   23.15   25.39  112.01  Warszawa
    7    16.94    8.69   96.53   22.00   24.37   15.78   23.15    0.00   19.62  106.23  Paris
    8    19.18   10.93   98.77   24.24   26.61   18.02   25.39   19.62    0.00  108.47  London
    9   101.21   97.54    9.71  106.26  108.63  104.63  112.01  106.23  108.47    0.00  Toronto

  RTT massimo: 112.01 ms  (Warszawa <-> Toronto)
OK: /home/mattu/multichain/shadow/intercontinentale/topologia_myledger_intercontinentale.gml — 10 nodi, 20 archi, connesso
[prepare_params] catena 'poesiaintercontinentale' pronta
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
[gen_shadow_yaml] intercontinentale -> /home/mattu/multichain/shadow/intercontinentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 2430s simulati (98 blocchi di setup + 200 misurati a 5s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 578s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello intercontinentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 421
  fase di setup (PoA)  : 98 blocchi (height 1..98)
  finestra wPoA misurata: 323 blocchi (height 99..421)

  intervallo fra blocchi (finestra wPoA), target = 5 s:
    media       5.61 s     scarto vs target +0.61 s (+12.2%)
    mediana     6.00 s
    dev.std     1.53 s
    min/max     3.00 / 8.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e3                 1         1         1
  e4                 1         1          
  e5             16884      6509      3269
  e6             17404      6500          
  e7             62099     25615      7531
  e8             60602     20535      8243
  e9             62099     23161      9948
  e10            68701                8243
  e11            62099     20515      9948
  e12            70199     28242          
  e13                      23161      5826
  e14            60145     25615      9948
  e15            63597     25787          
  e16            68701     23161      5826
  e17            62099                9948
  e18                      22969          
  e19            68244     23161      7531
  e20            62099                8243
  e21                      22969      9948
  e22            61643     25787      8243
  e23            70199     25615      9948
  e24                      25787          
  e25            61643     25615      7531
  e26            62099     23161      9948
  e27            68701                8243
  e28            60602     20515      9948
  e29            70199     25615          
  e30            63597     25787      5826
  e31            68701     25615      9948
  e32            70199     23161          
  e33            62099     25615      5826
  e34            70199     25787      9948
  record totali: 80

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q        252    78.0%     70199    66.3%
  m2     1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm        54    16.7%     25787    24.3%
  m3     1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR        17     5.3%      9948     9.4%

  blocchi consecutivi dello stesso proposer: 221 osservati, 205.9 attesi

  chi-quadro = 20.305  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [2.50, 7.50] s   (T=5 s, delta=0.5, Dmax=2.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          346     2.253     5.272     7.507         55.4%
  m2          346     2.392     6.422     7.550         78.4%
  m3          346     2.598     6.995     7.550         89.9%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 346 round):
    media      1.845 s
    mediana    1.596 s
    minimo     0.002 s
    5o perc.   0.095 s
    round con G < 100 ms: 19 su 346 (5.5%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         421       9  999307.2235  00e7782d2697d064   0070ca0aeb2e2ec9
  m1            421       9     108.0207  00e7782d2697d064   0070ca0aeb2e2ec9
  m2            421       9      49.8294  00e7782d2697d064   0070ca0aeb2e2ec9
  m3            421       9      21.3348  00e7782d2697d064   0070ca0aeb2e2ec9
  c1            421       9       85.986  00e7782d2697d064   0070ca0aeb2e2ec9
  c2            421       9      90.5896  00e7782d2697d064   0070ca0aeb2e2ec9
  c3            421       9      92.8918  00e7782d2697d064   0070ca0aeb2e2ec9
  c4            421       9      94.2948  00e7782d2697d064   0070ca0aeb2e2ec9
  c5            421       9      95.4136  00e7782d2697d064   0070ca0aeb2e2ec9
  ca            421       9      49.3572  00e7782d2697d064   0070ca0aeb2e2ec9
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q,85.56
  m2,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm,26.46
  m3,1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR,24.17
  c1,1ESxJuPreq5n4ajdCVe721fC6537dAAjkNv6JT,17.50
  c2,1HeU7vw9ZRKhJuJP3bGUDf7WC1thiW7MqxU5gL,77.16
  c3,1Atoq5b2CCV9JgRDWGbGbZE6tad9Ygdbkamw7L,99.26
  c4,1b7ke8bvGbq9gQxvE3o7PyUM6SQwo6a4xa8Kym,92.76
  c5,1DAhaHzyUhToVmbabUa4yPFCVCfvdsUZiEM56M,70.53

── Adesioni ai cluster (membership.csv) ──
  m2,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm
  m1,1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q,1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q
  c4,1b7ke8bvGbq9gQxvE3o7PyUM6SQwo6a4xa8Kym,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm
  c2,1HeU7vw9ZRKhJuJP3bGUDf7WC1thiW7MqxU5gL,1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q
  c1,1ESxJuPreq5n4ajdCVe721fC6537dAAjkNv6JT,1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q
  c3,1Atoq5b2CCV9JgRDWGbGbZE6tad9Ygdbkamw7L,1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm
  m3,1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR,1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR
  c5,1DAhaHzyUhToVmbabUa4yPFCVCfvdsUZiEM56M,1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  66,6,m1,49.6042,45.2240
  66,6,m3,51.3108,9.8622
  66,6,m2,49.6026,28.5616
  73,7,m3,41.5442,7.9088
  73,7,m2,21.081,11.4486
  73,7,m1,105.3684,98.2000
  84,8,m1,107.1852,99.9259
  84,8,m3,34.1754,6.4351
  84,8,m2,110.2514,64.9508
  96,9,m2,45.5392,26.1235
  96,9,m3,27.5897,5.1179
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
  66,refill,m1,100
  73,refill,m1,100
  73,refill,m2,100
  ... (58 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 3168
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             110536
  fold di fallback RANDAO          0
  score di sortition calcolati     1041
  attese per mappa pesi vuota      347
  pesi registrati sullo stream     84
  letture della mappa dei pesi     9308
  epoche calcolate dal motore      350
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 33, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1MHYudquDYbqcfKFeiPme4REV3zEevG9hz5JMm", "published": 25615, "published_epoch": 33, "recomputed": 25615, "verdict": "ok"}, {"address": "1azp6DNJXJxktRDqVLpMUDiVHKGQQTmFUsTbZR", "published": 5826, "published_epoch": 33, "recomputed": 5826, "verdict": "ok"}, {"address": "1ihctmEdJFVpXYNx7B1rbP9ALaeCCZpNVWv4q", "published": 62099, "published_epoch": 33, "recomputed": 62099, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/intercontinentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/intercontinentale/run