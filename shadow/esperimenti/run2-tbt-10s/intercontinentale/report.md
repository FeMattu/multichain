[run] setup-first-blocks non specificato: uso 64 (minimo calcolato: 64)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: intercontinentale
  target-block-time=10s  setup=64  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] intercontinentale -> /home/mattu/multichain/shadow/intercontinentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 3580s simulati (64 blocchi di setup + 200 misurati a 10s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 658s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello intercontinentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 327
  fase di setup (PoA)  : 64 blocchi (height 1..64)
  finestra wPoA misurata: 263 blocchi (height 65..327)

  intervallo fra blocchi (finestra wPoA), target = 10 s:
    media      10.70 s     scarto vs target +0.70 s (+7.0%)
    mediana    11.00 s
    dev.std     2.88 s
    min/max     5.00 / 16.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e1                 1         1         1
  e3             20933      9050      5330
  e4            107087     41030     13358
  e5            105590     38404          
  e6            113689     41030     10941
  e7            105590     43484     13358
  e8            113689     41030          
  e9            107087               10941
  e10           112191     35758     13358
  e11           107087     43484          
  e12           105590     41030     10941
  e13           115186               13358
  e14           112191     40838          
  e15           116683     46111     10941
  e16           112191     41030     13358
  e17           107087     38404          
  e18           115186     46111     12645
  e19           104092     38404     11653
  e20           115186     41030     15062
  e21           104092     38404     11653
  e22           115186     46111     15062
  e23                      43484     13358
  e24           114729     46111     15062
  e25           113689     41030     13358
  e26           115186     46111          
  record totali: 66

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx       181    68.8%    115186    66.0%
  m2     1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc        72    27.4%     46111    26.4%
  m3     1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2        10     3.8%     13358     7.6%

  blocchi consecutivi dello stesso proposer: 172 osservati, 144.1 attesi

  chi-quadro = 5.510  (df=2, critico 5% = 5.991)  -> compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [5.00, 15.00] s   (T=10 s, delta=0.5, Dmax=5.00 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          276     4.652    10.831    15.046         58.3%
  m2          276     4.603    12.519    15.166         75.2%
  m3          276     5.355    14.234    15.183         92.3%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 276 round):
    media      3.355 s
    mediana    2.964 s
    minimo     0.001 s
    5o perc.   0.173 s
    round con G < 100 ms: 9 su 276 (3.3%)

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         327       9  999295.8497  009d8bb6af03e00c   0082a4630b2c485a
  m1            327       9     108.2425  009d8bb6af03e00c   0082a4630b2c485a
  m2            327       9      49.3645  009d8bb6af03e00c   0082a4630b2c485a
  m3            327       9      60.9837  009d8bb6af03e00c   0082a4630b2c485a
  c1            327       9      77.9156  009d8bb6af03e00c   0082a4630b2c485a
  c2            327       9      85.2094  009d8bb6af03e00c   0082a4630b2c485a
  c3            327       9      88.8566  009d8bb6af03e00c   0082a4630b2c485a
  c4            327       9      91.0444  009d8bb6af03e00c   0082a4630b2c485a
  c5            327       9      92.8402  009d8bb6af03e00c   0082a4630b2c485a
  ca            327       9      49.3566  009d8bb6af03e00c   0082a4630b2c485a
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx,85.56
  m2,1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc,26.46
  m3,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2,24.17
  c1,19tmz4FYx6edh324hq22R7cbnZPZwPsSoFgkUu,17.50
  c2,1NKfxpBVQ6Dwj42rabdPqSsTtiJPeXSLgSkZR5,77.16
  c3,1UVoePQHSbTtPqNpKfAzFf22zUiV3RVT1NyYzU,99.26
  c4,14Z543WVJLihcUGSe1gDjPviSg2SGY2R4ypgoj,92.76
  c5,1CyZ6VYS93ZAFmXbPhQK61zNeinNVbWCzNybqU,70.53

── Adesioni ai cluster (membership.csv) ──
  m3,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2
  m2,1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc,1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc
  c2,1NKfxpBVQ6Dwj42rabdPqSsTtiJPeXSLgSkZR5,1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx
  c1,19tmz4FYx6edh324hq22R7cbnZPZwPsSoFgkUu,1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx
  m1,1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx,1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx
  c3,1UVoePQHSbTtPqNpKfAzFf22zUiV3RVT1NyYzU,1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc
  c4,14Z543WVJLihcUGSe1gDjPviSg2SGY2R4ypgoj,1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc
  c5,1CyZ6VYS93ZAFmXbPhQK61zNeinNVbWCzNybqU,1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  34,3,m2,49.784,28.6704
  34,3,m1,51.3122,46.8466
  34,3,m3,50.1002,9.6200
  37,4,m3,40.831,7.7662
  37,4,m2,21.0686,11.4412
  37,4,m1,104.4206,97.2996
  49,5,m3,33.1358,6.2272
  49,5,m1,106.9704,99.7219
  49,5,m2,110.8682,65.3209
  60,6,m2,45.3963,26.0378
  60,6,m3,27.8816,5.1763
  ... (82 righe totali)

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
  ... (49 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 2520
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             86567
  fold di fallback RANDAO          0
  score di sortition calcolati     831
  attese per mappa pesi vuota      277
  pesi registrati sullo stream     69
  letture della mappa dei pesi     7408
  epoche calcolate dal motore      260
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 25, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1CoWuY4gZW7xVpsTregiYWuhnsmgnnBimpbDjx", "published": 113689, "published_epoch": 25, "recomputed": 113689, "verdict": "ok"}, {"address": "1H2ZSPhnLnBw6i2ghJ5DcHXH7AafiDkSkFdiq2", "published": 13358, "published_epoch": 25, "recomputed": 13358, "verdict": "ok"}, {"address": "1U9k1edYTa5QzLkoar9sYbaRncvZGQCJ33agpc", "published": 41030, "published_epoch": 25, "recomputed": 41030, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/intercontinentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/intercontinentale/run