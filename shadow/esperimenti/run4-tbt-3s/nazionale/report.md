[run] setup-first-blocks non specificato: uso 144 (minimo calcolato: 144)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: nazionale
  target-block-time=3s  setup=144  misura=200 blocchi  epoca=12
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
[prepare_params]   target-block-time = 3 s, setup-first-blocks = 144, epoca = 12 blocchi
[prepare_params]   treasury          = 18QrmhtdHAfw8gknT5hxBStfGY63AhuQZCSDcg
[prepare_params]   target-block-time = 3                  # Target time between blocks (transaction confirmation delay), seconds. (2 - 86400)
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
[gen_shadow_yaml]   stop_time = 1972s simulati (144 blocchi di setup + 200 misurati a 3s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 752s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello nazionale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 529
  fase di setup (PoA)  : 144 blocchi (height 1..144)
  finestra wPoA misurata: 385 blocchi (height 145..529)

  intervallo fra blocchi (finestra wPoA), target = 3 s:
    media       3.64 s     scarto vs target +0.64 s (+21.3%)
    mediana     4.00 s
    dev.std     0.99 s
    min/max     2.00 / 6.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e6                 1         1         1
  e8             12606      5186      3269
  e9              4278      1323      1209
  e10            21453      7727      4122
  e11            42907     15454      6539
  e12            44404     18080      8243
  e13            52503                    
  e14                      15434      4122
  e15            43947     20535      8243
  e16            44404     15454          
  e17            51006     18080      5826
  e18            45901                6539
  e19            52503     15434      8243
  e20            51006     17908          
  e21            52503     18080      5826
  e22            44404                6539
  e23            51006     12808      8243
  e24            52503     18080          
  e25                      20535      5826
  e26            37345     18080      8243
  e27            51006                6539
  e28            44404     12808      8243
  e29            52503     18080          
  e30            42907     15454      4122
  e31            52503     18080      8243
  e32            44404     20535          
  e33            52503     18080      5826
  e34            51006     15454      6539
  e35            44404     18080      8243
  e36            52503                    
  e37                      17889      5826
  e38            35848     15454      6539
  e39            52503     18080      8243
  e40            44404                    
  e41            51006     12808      4122
  e42            52503     18080      8243
  e43            44404                    
  record totali: 92

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2       285    74.0%     44404    62.8%
  m2     1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr        72    18.7%     18080    25.6%
  m3     1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8        28     7.3%      8243    11.7%

  blocchi consecutivi dello stesso proposer: 308 osservati, 225.9 attesi

  chi-quadro = 21.187  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [1.50, 4.50] s   (T=3 s, delta=0.5, Dmax=1.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          423     1.328     3.207     4.448         56.9%
  m2          422     1.390     3.768     4.555         75.6%
  m3          423     1.435     4.131     4.566         87.7%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 423 round):
    media      1.081 s
    mediana    0.885 s
    minimo     0.002 s
    5o perc.   0.051 s
    round con G < 100 ms: 36 su 423 (8.5%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         529       9  999263.5639  0081e988dd0e01fd   00246b61d3cb8f74
  m1            529       9       7.0735  0081e988dd0e01fd   00246b61d3cb8f74
  m2            529       9      20.8334  0081e988dd0e01fd   00246b61d3cb8f74
  m3            529       9      49.5021  0081e988dd0e01fd   00246b61d3cb8f74
  c1            529       9      89.2376  0081e988dd0e01fd   00246b61d3cb8f74
  c2            529       9      92.7216  0081e988dd0e01fd   00246b61d3cb8f74
  c3            529       9      94.5162  00b7a3cb155500e6   00246b61d3cb8f74
  c4            530       9      95.5794  00b7a3cb155500e6   00246b61d3cb8f74
  c5            530       9      96.4204  00b7a3cb155500e6   00246b61d3cb8f74
  ca            530       9      49.3566  00b7a3cb155500e6   00246b61d3cb8f74
  -> teste diverse ma altezze a 1 blocco di distanza e stesso hash sepolto:
     e' il normale ritardo di propagazione fra i nodi, non un fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2,85.56
  m2,1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr,26.46
  m3,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8,24.17
  c1,1BcH8Y9BYTZ1h8V5EJMmu29g3F1Cpz8QDQ3z3E,17.50
  c2,14bxQXRV6SLyVcpEDK9CZu4fSG2bJt37eEJ8ep,77.16
  c3,1UgRUwEYvbGLKGifyd6iEiLqu4LMKjACEYfj4v,99.26
  c4,1Wn3ZhubfkcfqefJg2RhQ781sLSPMdg2wMjLKL,92.76
  c5,149xLWRgHiqgcszXwC6GDsrpvc8WsKbzGfDiPu,70.53

── Adesioni ai cluster (membership.csv) ──
  m3,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8
  m2,1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr,1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr
  c1,1BcH8Y9BYTZ1h8V5EJMmu29g3F1Cpz8QDQ3z3E,1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2
  c4,1Wn3ZhubfkcfqefJg2RhQ781sLSPMdg2wMjLKL,1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr
  c3,1UgRUwEYvbGLKGifyd6iEiLqu4LMKjACEYfj4v,1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr
  c5,149xLWRgHiqgcszXwC6GDsrpvc8WsKbzGfDiPu,1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8
  m1,1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2,1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2
  c2,14bxQXRV6SLyVcpEDK9CZu4fSG2bJt37eEJ8ep,1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  110,10,m3,49.6786,9.5357
  110,10,m2,49.6786,28.6072
  110,10,m1,49.6788,45.2949
  122,11,m3,40.0217,7.6043
  122,11,m2,21.9798,11.9879
  122,11,m1,104.2629,97.1498
  132,12,m3,32.2964,6.0593
  132,12,m1,106.9919,99.7423
  132,12,m2,109.9265,64.7559
  144,13,m3,26.1159,4.8232
  144,13,m2,45.0198,25.8119
  ... (118 righe totali)

── Movimenti GAS (init + rifornimenti) (gas_transfers.csv) ──
  19,init,c1,100
  19,init,c2,100
  19,init,c3,100
  19,init,c4,100
  19,init,c5,100
  19,init,m1,50
  19,init,m2,50
  19,init,m3,50
  19,init,ca,50
  110,refill,m1,100
  129,refill,m1,100
  129,refill,m2,100
  ... (66 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 4728
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             156630
  fold di fallback RANDAO          0
  score di sortition calcolati     1271
  attese per mappa pesi vuota      424
  pesi registrati sullo stream     100
  letture della mappa dei pesi     13516
  epoche calcolate dal motore      441
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 42, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1ETD6u7wdHS6P9D1mxb1Qx3Aapa2DwAyyZutL2", "published": 44404, "published_epoch": 43, "recomputed": 0, "verdict": "other-epoch"}, {"address": "1LtuCHDRfFnaxMXGm2gmsN7NoezE7zExV3Cet8", "published": 8243, "published_epoch": 42, "recomputed": 8243, "verdict": "ok"}, {"address": "1WKxQntNgmP3dtjbv3UL3DHV2JEciQTnQ4K3sr", "published": 18080, "published_epoch": 42, "recomputed": 18080, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/nazionale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/nazionale/run