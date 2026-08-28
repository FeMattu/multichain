[run] setup-first-blocks non specificato: uso 144 (minimo calcolato: 144)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: continentale
  target-block-time=3s  setup=144  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] continentale -> /home/mattu/multichain/shadow/continentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 1972s simulati (144 blocchi di setup + 200 misurati a 3s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 783s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello continentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 537
  fase di setup (PoA)  : 144 blocchi (height 1..144)
  finestra wPoA misurata: 393 blocchi (height 145..537)

  intervallo fra blocchi (finestra wPoA), target = 3 s:
    media       3.57 s     scarto vs target +0.57 s (+19.1%)
    mediana     4.00 s
    dev.std     0.95 s
    min/max     1.00 / 6.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e6                 1         1         1
  e8             12606      5186      3269
  e9              4278      1323      1209
  e10            21453      7727      4122
  e11            44404     18080      6539
  e12            42907     15454      8243
  e13            52503     18080      6539
  e14            44404     15454      8243
  e15            52503     18080          
  e16            51006                5826
  e17            52503     17889      8243
  e18            44404     15454      6539
  e19                      18080      8243
  e20            42450     15454      6539
  e21            52503     18080      8243
  e22            44404                    
  e23                      12808      4122
  e24            35848     18080      8243
  e25            51006     15454          
  e26            44404     18080      4122
  e27            51006     15454      8243
  e28            52503     20535          
  e29            45901     18080      5826
  e30            51006                6539
  e31            52503     15434      8243
  e32            44404     15454          
  e33            52503     20535      5826
  e34            51006     18080      6539
  e35            44404     15454      8243
  e36            52503     18080          
  e37            44404                4122
  e38            51006     12808      8243
  e39            45901     18080          
  e40            51006                4122
  e41            44404     12808      8243
  e42            52503     20535          
  e43            51006     18080      5826
  e44            45901                6539
  record totali: 98

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi       290    73.8%     45901    65.1%
  m2     1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6        79    20.1%     18080    25.6%
  m3     1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7        24     6.1%      6539     9.3%

  blocchi consecutivi dello stesso proposer: 313 osservati, 230.8 attesi

  chi-quadro = 13.518  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [1.50, 4.50] s   (T=3 s, delta=0.5, Dmax=1.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          425     1.369     3.204     4.475         56.8%
  m2          427     1.376     3.819     4.500         77.3%
  m3          426     1.424     4.147     4.500         88.2%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 426 round):
    media      1.095 s
    mediana    0.940 s
    minimo     0.000 s
    5o perc.   0.049 s
    round con G < 100 ms: 35 su 426 (8.2%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         537       9  999303.7507  000e16afafdf609a   00f8eef08f9c5fec
  m1            537       9     107.4496  000e16afafdf609a   00f8eef08f9c5fec
  m2            537       9      21.3363  000e16afafdf609a   00f8eef08f9c5fec
  m3            537       9      49.5738  000e16afafdf609a   00f8eef08f9c5fec
  c1            537       9      89.1842  000e16afafdf609a   00f8eef08f9c5fec
  c2            537       9      92.7208  000e16afafdf609a   00f8eef08f9c5fec
  c3            537       9       94.516  000e16afafdf609a   00f8eef08f9c5fec
  c4            537       9      95.5796  000e16afafdf609a   00f8eef08f9c5fec
  c5            537       9      96.4202  00827567f0a6ecd4   00f8eef08f9c5fec
  ca            538       9      49.3564  00827567f0a6ecd4   00f8eef08f9c5fec
  -> teste diverse ma altezze a 1 blocco di distanza e stesso hash sepolto:
     e' il normale ritardo di propagazione fra i nodi, non un fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi,85.56
  m2,1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6,26.46
  m3,1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7,24.17
  c1,1JYF2q1Sf8dBzUVspdhkifPGzhj1rwA12i1hPV,17.50
  c2,1C7XjpQytFpcBVJyEs8Gf1TvTTZJgYsbySAgGE,77.16
  c3,1FzwgcL8WrrmniBZoBvAR6MEp5DRgxqCGyjyx8,99.26
  c4,1Cy3ajnDFY64KmZnhC5S4Nd1d59WrLjgpqjbiz,92.76
  c5,1HqvoZqwoGg5a7XkWWXUdSerMcrtk3RppCHmib,70.53

── Adesioni ai cluster (membership.csv) ──
  m1,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi
  c2,1C7XjpQytFpcBVJyEs8Gf1TvTTZJgYsbySAgGE,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi
  c3,1FzwgcL8WrrmniBZoBvAR6MEp5DRgxqCGyjyx8,1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6
  m2,1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6,1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6
  c1,1JYF2q1Sf8dBzUVspdhkifPGzhj1rwA12i1hPV,1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi
  m3,1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7,1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7
  c5,1HqvoZqwoGg5a7XkWWXUdSerMcrtk3RppCHmib,1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7
  c4,1Cy3ajnDFY64KmZnhC5S4Nd1d59WrLjgpqjbiz,1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  109,10,m2,51.524,29.7144
  109,10,m3,49.6786,9.5357
  109,10,m1,49.6786,45.2947
  122,11,m2,21.6884,11.8130
  122,11,m1,105.1363,97.9795
  122,11,m3,40.0217,7.6043
  132,12,m3,33.0048,6.2010
  132,12,m2,109.7544,64.6526
  132,12,m1,107.0356,99.7838
  145,13,m3,27.1336,5.0267
  145,13,m2,45.2044,25.9226
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
  109,refill,m1,100
  130,refill,m1,100
  130,refill,m2,100
  ... (68 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 4020
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             141204
  fold di fallback RANDAO          0
  score di sortition calcolati     1281
  attese per mappa pesi vuota      428
  pesi registrati sullo stream     105
  letture della mappa dei pesi     11760
  epoche calcolate dal motore      451
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 43, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1PJJAyxet5ARk1XH3GjK9tVTPH3keFUewkjkfi", "published": 51006, "published_epoch": 43, "recomputed": 51006, "verdict": "ok"}, {"address": "1VAcJXZ4zmVYXXG3RSh25pvJNoJdBeVy9ChdT6", "published": 18080, "published_epoch": 43, "recomputed": 18080, "verdict": "ok"}, {"address": "1VuBTTQVFkVMQoHen4dKPJgUfqJY1ta899xaf7", "published": 5826, "published_epoch": 43, "recomputed": 5826, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/continentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/continentale/run