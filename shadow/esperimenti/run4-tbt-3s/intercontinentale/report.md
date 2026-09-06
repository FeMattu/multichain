[run] setup-first-blocks non specificato: uso 144 (minimo calcolato: 144)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: intercontinentale
  target-block-time=3s  setup=144  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] intercontinentale -> /home/mattu/multichain/shadow/intercontinentale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 1972s simulati (144 blocchi di setup + 200 misurati a 3s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 866s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello intercontinentale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 535
  fase di setup (PoA)  : 144 blocchi (height 1..144)
  finestra wPoA misurata: 391 blocchi (height 145..535)

  intervallo fra blocchi (finestra wPoA), target = 3 s:
    media       3.58 s     scarto vs target +0.58 s (+19.5%)
    mediana     4.00 s
    dev.std     1.00 s
    min/max     2.00 / 6.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e6                 1         1         1
  e8             12606      5186      3269
  e9              4278      1323      1209
  e10            21453      7727      4122
  e11            42907     15454      6539
  e12            44404     18080      8243
  e13            52503                6539
  e14            44404     12808      8243
  e15            51006     18080          
  e16            45901                5826
  e17            52503     17889      6539
  e18            51006     15454      8243
  e19            44404     18080          
  e20            51006     15454      4122
  e21            45901     18080      8243
  e22            51006                    
  e23            52503     15434      5826
  e24            42907     15454      6539
  e25            44404                8243
  e26                      15434      6539
  e27            43947     18080      8243
  e28            52503     20535          
  e29            51006     18080      5826
  e30            45901     15454      6539
  e31            51006     18080      8243
  e32            44404     15454          
  e33            52503     20535      5826
  e34            42907     12999      6539
  e35            52503     20535      8243
  e36                      18080          
  e37            35848                4122
  e38            52503     15434      8243
  e39            51006     17908          
  e40            44404     18080      5826
  e41            52503                6539
  e42            44404     12808      8243
  e43            52503     18080          
  e44            51006     20535      5826
  record totali: 98

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA       323    82.6%     51006    65.9%
  m2     1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5        54    13.8%     20535    26.5%
  m3     1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm        14     3.6%      5826     7.5%

  blocchi consecutivi dello stesso proposer: 340 osservati, 274.1 attesi

  chi-quadro = 48.482  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [1.50, 4.50] s   (T=3 s, delta=0.5, Dmax=1.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          425     1.374     3.140     4.469         54.7%
  m2          424     1.343     3.852     4.517         78.4%
  m3          424     1.403     4.101     4.533         86.7%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 425 round):
    media      1.055 s
    mediana    0.836 s
    minimo     0.001 s
    5o perc.   0.064 s
    round con G < 100 ms: 32 su 425 (7.5%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         535       9  999304.5347  001423f99ed65365   00d67d00353c5c1d
  m1            535       9     107.9925  001423f99ed65365   00d67d00353c5c1d
  m2            535       9      20.6326  001423f99ed65365   00d67d00353c5c1d
  m3            535       9      48.7922  001423f99ed65365   00d67d00353c5c1d
  c1            536       9       89.183  00b53ffca4a382e4   00d67d00353c5c1d
  c2            536       9      92.7218  00b53ffca4a382e4   00d67d00353c5c1d
  c3            536       9      94.5176  00b53ffca4a382e4   00d67d00353c5c1d
  c4            536       9      95.5806  00b53ffca4a382e4   00d67d00353c5c1d
  c5            536       9      96.4194  00b53ffca4a382e4   00d67d00353c5c1d
  ca            536       9       49.356  00b53ffca4a382e4   00d67d00353c5c1d
  -> teste diverse ma altezze a 1 blocco di distanza e stesso hash sepolto:
     e' il normale ritardo di propagazione fra i nodi, non un fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA,85.56
  m2,1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5,26.46
  m3,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm,24.17
  c1,1MZ34BZBycanzV6MQpn4kGo3igKxDeCFHrm4ys,17.50
  c2,1LB6qUDEtPSL1cXPypZpfPq4jGZRpZVJ3UzARx,77.16
  c3,14pmjhAXKHStX1ymPpwvt7n9i412fia61DZFdB,99.26
  c4,1TFFyiBbp1YeJiDAG9heTHahno55ikaZcom68e,92.76
  c5,1Zf6vhjhrZjDD8A5EitQbbxXVqtZKz5YEQ5i7C,70.53

── Adesioni ai cluster (membership.csv) ──
  m3,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm
  c1,1MZ34BZBycanzV6MQpn4kGo3igKxDeCFHrm4ys,1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA
  c3,14pmjhAXKHStX1ymPpwvt7n9i412fia61DZFdB,1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5
  c2,1LB6qUDEtPSL1cXPypZpfPq4jGZRpZVJ3UzARx,1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA
  m2,1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5,1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5
  m1,1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA,1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA
  c5,1Zf6vhjhrZjDD8A5EitQbbxXVqtZKz5YEQ5i7C,1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm
  c4,1TFFyiBbp1YeJiDAG9heTHahno55ikaZcom68e,1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  110,10,m1,49.6786,45.2947
  110,10,m3,49.9942,9.5988
  110,10,m2,49.9952,28.7971
  122,11,m1,105.0405,97.8885
  122,11,m2,21.0769,11.4461
  122,11,m3,40.2744,7.6549
  132,12,m1,107.076,99.8222
  132,12,m3,32.7001,6.1400
  132,12,m2,109.5096,64.5058
  144,13,m1,107.1586,99.9007
  144,13,m2,45.2816,25.9690
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
  ... (68 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 4598
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             148782
  fold di fallback RANDAO          0
  score di sortition calcolati     1276
  attese per mappa pesi vuota      426
  pesi registrati sullo stream     104
  letture della mappa dei pesi     13201
  epoche calcolate dal motore      441
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 43, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "1EjTSBbBL4yFpTtoME9NpC8UpK1PLnzA3NnRS5", "published": 18080, "published_epoch": 43, "recomputed": 18080, "verdict": "ok"}, {"address": "1QgfFWVY65u3QeYVETh4jPoFqBBL2MwgpBFZvm", "published": 8243, "published_epoch": 42, "recomputed": 0, "verdict": "other-epoch"}, {"address": "1X6UMfyYAa2CneQRWw6ESrCuLmu9JzSVF142bA", "published": 52503, "published_epoch": 43, "recomputed": 52503, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/intercontinentale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/intercontinentale/run