[run] setup-first-blocks non specificato: uso 98 (minimo calcolato: 98)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: nazionale
  target-block-time=5s  setup=98  misura=200 blocchi  epoca=12
════════════════════════════════════════════════════════════════════
[treasury] gia' presente: /home/mattu/multichain/shadow/config/treasury.json (FORCE=1 per rigenerarlo)
[gen_topology] nazionale -> /home/mattu/multichain/shadow/nazionale/topologia_myledger_nazionale.gml (10 nodi, 10 archi)

  arco                                  D (km)   one-way ms     RTT ms
  --------------------------------------------------------------------
  Milano-Roma                            476.9        3.838       7.68
  Milano-Napoli                          657.5        5.103      10.21
  Roma-Napoli                            188.4        1.819       3.64
  Torino-Milano                          125.5        1.879       3.76
  Venezia-Milano                         243.8        2.707       5.41
  Firenze-Roma                           230.9        2.616       5.23
  Perugia-Roma                           134.6        1.942       3.88
  Bologna-Milano                         200.7        2.405       4.81
  Bari-Napoli                            220.5        2.544       5.09
  Palermo-Napoli                         314.0        3.198       6.40

  RTT end-to-end (ms), cammino minimo andata+ritorno:
             0       1       2       3       4       5       6       7       8       9
    0     0.00    7.68   10.21    3.76    5.41   12.91   11.56    4.81   15.29   16.60  HUB_NORD_Milano
    1     7.68    0.00    3.64   11.43   13.09    5.23    3.88   12.49    8.73   10.03  HUB_CENTRO_Roma
    2    10.21    3.64    0.00   13.96   15.62    8.87    7.52   15.02    5.09    6.40  HUB_SUD_Napoli
    3     3.76   11.43   13.96    0.00    9.17   16.67   15.32    8.57   19.05   20.36  Torino
    4     5.41   13.09   15.62    9.17    0.00   18.32   16.97   10.22   20.71   22.02  Venezia
    5    12.91    5.23    8.87   16.67   18.32    0.00    9.12   17.72   13.96   15.27  Firenze
    6    11.56    3.88    7.52   15.32   16.97    9.12    0.00   16.37   12.61   13.92  Perugia
    7     4.81   12.49   15.02    8.57   10.22   17.72   16.37    0.00   20.10   21.41  Bologna
    8    15.29    8.73    5.09   19.05   20.71   13.96   12.61   20.10    0.00   11.48  Bari
    9    16.60   10.03    6.40   20.36   22.02   15.27   13.92   21.41   11.48    0.00  Palermo

  RTT massimo: 22.02 ms  (Venezia <-> Palermo)
OK: /home/mattu/multichain/shadow/nazionale/topologia_myledger_nazionale.gml — 10 nodi, 20 archi, connesso
[prepare_params] catena 'poesianazionale' pronta
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
[gen_shadow_yaml] nazionale -> /home/mattu/multichain/shadow/nazionale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 2430s simulati (98 blocchi di setup + 200 misurati a 5s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 512s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello nazionale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 415
  fase di setup (PoA)  : 98 blocchi (height 1..98)
  finestra wPoA misurata: 317 blocchi (height 99..415)

  intervallo fra blocchi (finestra wPoA), target = 5 s:
    media       5.70 s     scarto vs target +0.70 s (+14.0%)
    mediana     6.00 s
    dev.std     1.49 s
    min/max     3.00 / 8.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e3                 1         1         1
  e5             12606      5186      3269
  e6             17404      6500          
  e7             60602     20535      7531
  e8             62099     25615      8243
  e9             70199     25787      9948
  e10                      25615          
  e11            53543     23161      5826
  e12            68701                9948
  e13            62099     20515          
  e14            78298     28242      7531
  e15            62099     25615      8243
  e16            70199     25787      9948
  e17            68701     23161          
  e18            63597     25615      7531
  e19            60602     23161      8243
  e20            70199                9948
  e21            78298     25596          
  e22            62099     23161      5826
  e23            68701     25615      9948
  e24            70199     25787          
  e25            62099     25615      7531
  e26            71696     25787      9948
  e27            70199     25615      8243
  e28                      28242      9948
  e29            68244     23161          
  e30            62099     25615      7531
  e31                      23161      9948
  e32            60145                8243
  e33            70199     25596      9948
  e34            62099     23161          
  record totali: 79

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp       232    73.2%     62099    65.2%
  m2     1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx        67    21.1%     23161    24.3%
  m3     1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac        18     5.7%      9948    10.4%

  blocchi consecutivi dello stesso proposer: 226 osservati, 184.4 attesi

  chi-quadro = 11.312  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [2.50, 7.50] s   (T=5 s, delta=0.5, Dmax=2.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          337     2.329     5.406     7.473         58.1%
  m2          337     2.205     6.322     7.495         76.4%
  m3          337     2.272     6.946     7.533         88.9%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 337 round):
    media      1.684 s
    mediana    1.450 s
    minimo     0.002 s
    5o perc.   0.075 s
    round con G < 100 ms: 23 su 337 (6.8%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         415       9  999308.2377  00d8c35744ac0142   0027f9e9bd793997
  m1            415       9       7.6692  00d8c35744ac0142   0027f9e9bd793997
  m2            415       9      48.8128  00d8c35744ac0142   0027f9e9bd793997
  m3            415       9      26.4169  00d8c35744ac0142   0027f9e9bd793997
  c1            415       9      85.9902  00d8c35744ac0142   0027f9e9bd793997
  c2            415       9      90.5912  00d8c35744ac0142   0027f9e9bd793997
  c3            415       9      92.8912  00d8c35744ac0142   0027f9e9bd793997
  c4            415       9      94.2958  00d8c35744ac0142   0027f9e9bd793997
  c5            415       9      95.4126  00d8c35744ac0142   0027f9e9bd793997
  ca            415       9      49.3568  00d8c35744ac0142   0027f9e9bd793997
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp,85.56
  m2,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx,26.46
  m3,1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac,24.17
  c1,1X2L9fkqq9LAbwPDz1SqCJiNrmxKdikgue6yYZ,17.50
  c2,1UxnAi2fFtTDq4ueXQFEL4zi8MwtVHREpjHc6h,77.16
  c3,1ZeK9j4KbGp26TqiEj712Uy3dDSxEvoCgHx2pJ,99.26
  c4,1KJxpGjjCx4L4ui7yXDrVyjxijxMShNRXcS3XB,92.76
  c5,17V2VF5b1CmigfPVqujRoCWaiNfGZHdigz6HU7,70.53

── Adesioni ai cluster (membership.csv) ──
  m2,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx
  m3,1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac,1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac
  m1,1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp,1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp
  c5,17V2VF5b1CmigfPVqujRoCWaiNfGZHdigz6HU7,1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac
  c1,1X2L9fkqq9LAbwPDz1SqCJiNrmxKdikgue6yYZ,1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp
  c4,1KJxpGjjCx4L4ui7yXDrVyjxijxMShNRXcS3XB,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx
  c3,1ZeK9j4KbGp26TqiEj712Uy3dDSxEvoCgHx2pJ,1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx
  c2,1UxnAi2fFtTDq4ueXQFEL4zi8MwtVHREpjHc6h,1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  67,6,m3,49.9948,9.5990
  67,6,m1,49.6786,45.2947
  67,6,m2,49.9948,28.7969
  73,7,m1,104.3387,97.2218
  73,7,m3,40.3508,7.6702
  73,7,m2,21.9285,11.9571
  85,8,m3,32.9132,6.1826
  85,8,m2,109.8504,64.7102
  85,8,m1,108.0405,100.7385
  96,9,m3,26.58,4.9160
  96,9,m2,45.1862,25.9117
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
  ... (55 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 3200
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             98988
  fold di fallback RANDAO          0
  score di sortition calcolati     1014
  attese per mappa pesi vuota      338
  pesi registrati sullo stream     81
  letture della mappa dei pesi     9352
  epoche calcolate dal motore      340
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 33, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1CDYMG7QEtXPWnEVVWcYX1NBF1jKK4gz6vthcp", "published": 70199, "published_epoch": 33, "recomputed": 70199, "verdict": "ok"}, {"address": "1M2z5HwZUMH7221MNFHycGfwkoENnFENJm4KAx", "published": 25596, "published_epoch": 33, "recomputed": 25596, "verdict": "ok"}, {"address": "1Z8u3jdAAsLX6vgyujHKQGSGEEhYiELHoQV1ac", "published": 9948, "published_epoch": 33, "recomputed": 9948, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/nazionale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/nazionale/run