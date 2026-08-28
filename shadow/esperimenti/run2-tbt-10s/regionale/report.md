[run] setup-first-blocks non specificato: uso 64 (minimo calcolato: 64)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: regionale
  target-block-time=10s  setup=64  misura=200 blocchi  epoca=12
════════════════════════════════════════════════════════════════════
[treasury] gia' presente: /home/mattu/multichain/shadow/config/treasury.json (FORCE=1 per rigenerarlo)
[gen_topology] regionale -> /home/mattu/multichain/shadow/regionale/topologia_myledger_regionale.gml (10 nodi, 10 archi)

  arco                                  D (km)   one-way ms     RTT ms
  --------------------------------------------------------------------
  Firenze-Genova                         197.5        1.883       3.77
  Firenze-Bologna                         80.9        1.067       2.13
  Genova-Bologna                         190.5        1.833       3.67
  Pisa-Firenze                            68.8        1.482       2.96
  Siena-Firenze                           50.5        1.353       2.71
  La_Spezia-Genova                        77.6        1.543       3.09
  Savona-Genova                           38.8        1.272       2.54
  Modena-Bologna                          37.1        1.260       2.52
  Parma-Bologna                           87.2        1.610       3.22
  Ravenna-Bologna                         68.9        1.482       2.96

  RTT end-to-end (ms), cammino minimo andata+ritorno:
             0       1       2       3       4       5       6       7       8       9
    0     0.00    3.77    2.13    2.96    2.71    6.85    6.31    4.65    5.35    5.10  HUB_TOSCANA_Firenze
    1     3.77    0.00    3.67    6.73    6.47    3.09    2.54    6.19    6.89    6.63  HUB_LIGURIA_Genova
    2     2.13    3.67    0.00    5.10    4.84    6.75    6.21    2.52    3.22    2.96  HUB_EMILIAROMAGNA_Bologna
    3     2.96    6.73    5.10    0.00    5.67    9.82    9.27    7.62    8.32    8.06  Pisa
    4     2.71    6.47    4.84    5.67    0.00    9.56    9.02    7.36    8.06    7.80  Siena
    5     6.85    3.09    6.75    9.82    9.56    0.00    5.63    9.27    9.97    9.72  La_Spezia
    6     6.31    2.54    6.21    9.27    9.02    5.63    0.00    8.73    9.43    9.17  Savona
    7     4.65    6.19    2.52    7.62    7.36    9.27    8.73    0.00    5.74    5.48  Modena
    8     5.35    6.89    3.22    8.32    8.06    9.97    9.43    5.74    0.00    6.18  Parma
    9     5.10    6.63    2.96    8.06    7.80    9.72    9.17    5.48    6.18    0.00  Ravenna

  RTT massimo: 9.97 ms  (La_Spezia <-> Parma)
OK: /home/mattu/multichain/shadow/regionale/topologia_myledger_regionale.gml — 10 nodi, 20 archi, connesso
[prepare_params] catena 'poesiaregionale' pronta
[prepare_params]   target-block-time = 10 s, setup-first-blocks = 64, epoca = 12 blocchi
[prepare_params]   treasury          = 18QrmhtdHAfw8gknT5hxBStfGY63AhuQZCSDcg
[prepare_params]   target-block-time = 10                  # Target time between blocks (transaction confirmation delay), seconds. (2 - 86400)
[prepare_params]   enable-wpoa = true                      # Master switch: enable the whole wPoA protocol (weights stream + weighted selection + VRF + RANDAO + sortition). More specific enable-wpoa-* flags override it per phase. Default 0 (native MultiChain mining).
[prepare_params]   wpoa-sortition-delta = 0.5              # wPoA sortition delay band half-width as a fraction of target-block-time, delta in (0,1). Small: narrower band, more forks; large: more latency. Consensus-critical: identical on all nodes. Default 0.5.
[prepare_params]   wpoa-sortition-lambda = 0.2             # wPoA sortition feedback gain lambda in [0,1]: weight of the global correction Phi recentring the mean block time on target. 0 disables it. Consensus-critical: identical on all nodes. Default 0.
[prepare_params]   enable-weight-engine = true             # Weight engine: derive each cluster's wpoa-weights value from on-chain inputs (membership/ESG/activity/reconciliation) per epoch, instead of a static -weight. Requires enable-wpoa-weights. Consensus-critical: identical on all nodes. Default 0.
[prepare_params]   weight-epoch-length = 12                # Weight engine epoch length in blocks: epoch(height) = height / this. Consensus-critical: must be identical on all nodes. Default 100. (1 - 1000000)
[prepare_params]   weight-treasury-address = 18QrmhtdHAfw8gknT5hxBStfGY63AhuQZCSDcg # Weight engine treasury address. R_k = value paid to THIS address by transactions the miner signed, derived from the epoch's confirmed blocks, never declared. Empty means R_k = 0 for all clusters. Consensus-critical: identical on all nodes.
[prepare_params]   first-block-reward = 100000000000000                 # Different mining reward for first block only, ignored if negative. (-1 - 1000000000000000000)
[prepare_params]   minimum-relay-fee = 20000000                   # Minimum transaction fee, per 1000 bytes, in raw units of native currency. (0 - 1000000000)
[gen_shadow_yaml] regionale -> /home/mattu/multichain/shadow/regionale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 3580s simulati (64 blocchi di setup + 200 misurati a 10s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 551s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello regionale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 325
  fase di setup (PoA)  : 64 blocchi (height 1..64)
  finestra wPoA misurata: 261 blocchi (height 65..325)

  intervallo fra blocchi (finestra wPoA), target = 10 s:
    media      10.78 s     scarto vs target +0.78 s (+7.8%)
    mediana    11.00 s
    dev.std     2.84 s
    min/max     5.00 / 16.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e1                 1         1         1
  e3             21682      9050      5330
  e4            104092     38404     13358
  e5            105590     41030     11653
  e6            123285     46111     15062
  e7            105590     38404     13358
  e8            115186     46111          
  e9            105590     38404     10941
  e10           123285     46111     15062
  e11           105590     41030     13358
  e12           121788     43484          
  e13           115186     46111     12645
  e14           105590     38404     11653
  e15                      38576     13358
  e16            97034     40858          
  e17           115186     43656     10941
  e18           113689     43484     13358
  e19           107087     41030     15062
  e20           113689     43484     13358
  e21           105590     38404          
  e22                      38576      9236
  e23           113232     43484     15062
  e24           123285     48565          
  e25           107087     41030     10941
  e26           113689               13358
  record totali: 67

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv       195    74.7%    113689    67.6%
  m2     1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq        60    23.0%     41030    24.4%
  m3     1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM          6     2.3%     13358     7.9%

  blocchi consecutivi dello stesso proposer: 175 osservati, 159.0 attesi

  chi-quadro = 12.625  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [5.00, 15.00] s   (T=10 s, delta=0.5, Dmax=5.00 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          273     4.565    10.805    15.009         58.0%
  m2          273     4.841    12.660    15.083         76.6%
  m3          273     5.185    14.271    15.183         92.7%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 273 round):
    media      3.351 s
    mediana    2.860 s
    minimo     0.011 s
    5o perc.   0.140 s
    round con G < 100 ms: 12 su 273 (4.4%)

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         325       9  999436.4469  006cf36804c6a402   004fe5103513d0b1
  m1            325       9       7.3695  006cf36804c6a402   004fe5103513d0b1
  m2            325       9       9.0827  006cf36804c6a402   004fe5103513d0b1
  m3            325       9      60.7073  006cf36804c6a402   004fe5103513d0b1
  c1            325       9       77.971  006cf36804c6a402   004fe5103513d0b1
  c2            325       9       85.266  006cf36804c6a402   004fe5103513d0b1
  c3            325       9        88.91  006cf36804c6a402   004fe5103513d0b1
  c4            325       9      91.0446  006cf36804c6a402   004fe5103513d0b1
  c5            325       9      92.8388  006cf36804c6a402   004fe5103513d0b1
  ca            325       9      49.3572  006cf36804c6a402   004fe5103513d0b1
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv,85.56
  m2,1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq,26.46
  m3,1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM,24.17
  c1,1C53cY45GLP1jCtGZ3jjRxK41xDpogMscxLoET,17.50
  c2,1KwDQh1YXp8Gjcm5PUTzw4oojyETr76SR6K5g4,77.16
  c3,1akYxtSrcSsAR7FUMwZr2RAjBZeS9pefqhTGii,99.26
  c4,1RNinnWHk18yFwNrDviXwK4oyJtZRTHU6YR4MW,92.76
  c5,1HW1Y78Q8DyPU8YKdN6gzrGyAC2HS8qt346Gcd,70.53

── Adesioni ai cluster (membership.csv) ──
  m1,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv
  m2,1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq,1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq
  c1,1C53cY45GLP1jCtGZ3jjRxK41xDpogMscxLoET,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv
  c3,1akYxtSrcSsAR7FUMwZr2RAjBZeS9pefqhTGii,1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq
  c2,1KwDQh1YXp8Gjcm5PUTzw4oojyETr76SR6K5g4,1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv
  m3,1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM,1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM
  c5,1HW1Y78Q8DyPU8YKdN6gzrGyAC2HS8qt346Gcd,1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM
  c4,1RNinnWHk18yFwNrDviXwK4oyJtZRTHU6YR4MW,1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  34,3,m1,49.7844,45.3952
  34,3,m3,51.6272,9.9254
  34,3,m2,49.784,28.6704
  37,4,m2,21.0684,11.4410
  37,4,m3,42.6582,8.1316
  37,4,m1,104.344,97.2268
  48,5,m3,34.5432,6.5086
  48,5,m2,109.6994,64.6196
  48,5,m1,108.1722,100.8636
  60,6,m2,45.7362,26.2417
  60,6,m3,27.9138,5.1828
  ... (79 righe totali)

── Movimenti GAS (init + rifornimenti) (gas_transfers.csv) ──
  6,init,c1,100
  6,init,c2,100
  6,init,c3,100
  6,init,c4,100
  6,init,c5,100
  6,init,m1,50
  6,init,m2,50
  6,init,m3,50
  6,init,ca,50
  34,refill,m1,100
  37,refill,m1,100
  37,refill,m2,100
  ... (48 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 2436
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             86960
  fold di fallback RANDAO          0
  score di sortition calcolati     822
  attese per mappa pesi vuota      274
  pesi registrati sullo stream     69
  letture della mappa dei pesi     7186
  epoche calcolate dal motore      260
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 25, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1KzW2ShtUjCJuvMCFeYJrHKrcGfjEj2t77aQAv", "published": 107087, "published_epoch": 25, "recomputed": 107087, "verdict": "ok"}, {"address": "1S5cgrFXRwv4CuTTTJy8S9h42X7UwwZUUN52kq", "published": 41030, "published_epoch": 25, "recomputed": 41030, "verdict": "ok"}, {"address": "1ddHuTA1GMyEmio87QhyJBkR7WPUSwnavqqzM", "published": 10941, "published_epoch": 25, "recomputed": 10941, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/regionale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/regionale/run