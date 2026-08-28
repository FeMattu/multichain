mattu@DESKTOP-ACCC0JT:~/multichain/shadow$ ./run.sh area=continentale tbt=10
[run] setup-first-blocks non specificato: uso 64 (minimo calcolato: 64)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: continentale
  target-block-time=10s  setup=64  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] continentale -> /home/mattu/multichain/shadow/continentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 3580s simulati (64 blocchi di setup + 200 misurati a 10s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 637s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello continentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 324
  fase di setup (PoA)  : 64 blocchi (height 1..64)
  finestra wPoA misurata: 260 blocchi (height 65..324)

  intervallo fra blocchi (finestra wPoA), target = 10 s:
    media      10.81 s     scarto vs target +0.81 s (+8.1%)
    mediana    11.00 s
    dev.std     2.96 s
    min/max     5.00 / 16.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e1                 1         1         1
  e3             20933      9050      5330
  e4            107087     41030     13358
  e5            112191     38404          
  e6            105590     41030      9236
  e7            116683     46111     15062
  e8            113689     43484     13358
  e9            105590     38404          
  e10                      41030     10941
  e11           105133               13358
  e12            97490     35758          
  e13           123285     46111     10941
  e14           105590     38404     13358
  e15           123285     46111     15062
  e16           105590     41030     13358
  e17           123285     46111          
  e18           115186     43484     12645
  e19           113689               13358
  e20                      38384          
  e21            98531     41030     10941
  e22           121788     46111     15062
  e23           105590     38404     11653
  e24           115186     46111     15062
  e25           105590     38404     13358
  e26           123285     46111          
  record totali: 65

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb       172    66.2%    123285    67.5%
  m2     1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3        68    26.2%     46111    25.2%
  m3     1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58        20     7.7%     13358     7.3%

  blocchi consecutivi dello stesso proposer: 158 osservati, 132.6 attesi

  chi-quadro = 0.206  (df=2, critico 5% = 5.991)  -> compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [5.00, 15.00] s   (T=10 s, delta=0.5, Dmax=5.00 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          272     4.801    10.885    15.050         58.8%
  m2          272     4.826    12.751    15.149         77.5%
  m3          272     4.808    13.891    15.148         88.9%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 272 round):
    media      3.238 s
    mediana    2.744 s
    minimo     0.005 s
    5o perc.   0.177 s
    round con G < 100 ms: 7 su 272 (2.6%)

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         324       9  999208.9012  00de015e83d1fb7d   003c9d0aa53af9f8
  m1            324       9     108.4974  00de015e83d1fb7d   003c9d0aa53af9f8
  m2            324       9     120.0958  00de015e83d1fb7d   003c9d0aa53af9f8
  m3            324       9      61.8241  00de015e83d1fb7d   003c9d0aa53af9f8
  c1            324       9      77.9706  00de015e83d1fb7d   003c9d0aa53af9f8
  c2            324       9      85.2104  00de015e83d1fb7d   003c9d0aa53af9f8
  c3            324       9      88.8576  00de015e83d1fb7d   003c9d0aa53af9f8
  c4            324       9      91.0432  00de015e83d1fb7d   003c9d0aa53af9f8
  c5            324       9       92.838  00de015e83d1fb7d   003c9d0aa53af9f8
  ca            324       9      49.3564  00de015e83d1fb7d   003c9d0aa53af9f8
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb,85.56
  m2,1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3,26.46
  m3,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58,24.17
  c1,17hkibG1jwCnYcoHqegVXJYK56Qp9MuiibepCQ,17.50
  c2,1LAyr99FkAc6rNx8EPyfMJnfdyq1yRZvLnzsaV,77.16
  c3,1Sx4KDRxVxbKGMMAtLjERQ8XUJJmcCaR7XGoKW,99.26
  c4,1a9oy7P2bVVwFWV6oZe2Xf33UNnvLQVQc8yERj,92.76
  c5,1XD1hpXTN6rBVW9uQD8sue46yKsy7BcPUxfApz,70.53

── Adesioni ai cluster (membership.csv) ──
  m3,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58
  m2,1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3,1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3
  c3,1Sx4KDRxVxbKGMMAtLjERQ8XUJJmcCaR7XGoKW,1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3
  m1,1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb,1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb
  c1,17hkibG1jwCnYcoHqegVXJYK56Qp9MuiibepCQ,1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb
  c2,1LAyr99FkAc6rNx8EPyfMJnfdyq1yRZvLnzsaV,1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb
  c5,1XD1hpXTN6rBVW9uQD8sue46yKsy7BcPUxfApz,1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58
  c4,1a9oy7P2bVVwFWV6oZe2Xf33UNnvLQVQc8yERj,1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  34,3,m1,49.7838,45.3946
  34,3,m2,49.7838,28.6703
  34,3,m3,49.784,9.5568
  36,4,m2,21.6747,11.8048
  36,4,m3,40.182,7.6364
  36,4,m1,104.9504,97.8029
  48,5,m3,32.729,6.1458
  48,5,m2,111.2593,65.5556
  48,5,m1,106.8913,99.6467
  60,6,m3,27.2662,5.0532
  60,6,m2,47.3605,27.2163
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
  36,refill,m1,100
  36,refill,m2,100
  ... (48 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 2456
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             84122
  fold di fallback RANDAO          0
  score di sortition calcolati     819
  attese per mappa pesi vuota      273
  pesi registrati sullo stream     68
  letture della mappa dei pesi     7232
  epoche calcolate dal motore      260
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 25, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1KxWxQCw8B6cfbPkjPqbyQ6co3qCuicxpv4P58", "published": 13358, "published_epoch": 25, "recomputed": 13358, "verdict": "ok"}, {"address": "1M1uMpgaw82fhzH6tz99Eybn5ydKoNaFrwXUvb", "published": 105590, "published_epoch": 25, "recomputed": 105590, "verdict": "ok"}, {"address": "1ZMv2Lqqkcy5zY6fAyGy1Dn6KT3fBVb7GxkCd3", "published": 38404, "published_epoch": 25, "recomputed": 38404, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/continentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/continentale/run
mattu@DESKTOP-ACCC0JT:~/multichain/shadow$ 