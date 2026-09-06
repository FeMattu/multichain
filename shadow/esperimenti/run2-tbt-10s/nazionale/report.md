[run] setup-first-blocks non specificato: uso 64 (minimo calcolato: 64)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: nazionale
  target-block-time=10s  setup=64  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] nazionale -> /home/mattu/multichain/shadow/nazionale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 3580s simulati (64 blocchi di setup + 200 misurati a 10s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 571s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello nazionale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 329
  fase di setup (PoA)  : 64 blocchi (height 1..64)
  finestra wPoA misurata: 265 blocchi (height 65..329)

  intervallo fra blocchi (finestra wPoA), target = 10 s:
    media      10.65 s     scarto vs target +0.65 s (+6.5%)
    mediana    11.00 s
    dev.std     2.74 s
    min/max     5.00 / 16.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e1                 1         1         1
  e3             20933      9050      5330
  e4            107087     41030     13358
  e5            104092     38404     11653
  e6            105590               13358
  e7            115186     41010          
  e8            105590     38404     10941
  e9            115186     46111     15062
  e10           112191     38404     13358
  e11           107087     43484          
  e12           121788     46111     10941
  e13           115186     41030     15062
  e14                      46111     13358
  e15           105133     43484          
  e16           107087     41030     10941
  e17           113689               13358
  e18           105590     35758          
  e19           115186     46111     12645
  e20           104092     38404     11653
  e21           123285     46111     15062
  e22           105590     38404     13358
  e23           107087     41030          
  e24           112191               10941
  e25           105590     40838     13358
  e26           115186     41030          
  record totali: 65

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt       192    72.5%    115186    67.9%
  m2     19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe        53    20.0%     41030    24.2%
  m3     1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa        20     7.5%     13358     7.9%

  blocchi consecutivi dello stesso proposer: 171 osservati, 150.6 attesi

  chi-quadro = 2.764  (df=2, critico 5% = 5.991)  -> compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [5.00, 15.00] s   (T=10 s, delta=0.5, Dmax=5.00 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          276     4.853    10.708    15.061         57.1%
  m2          277     5.075    12.905    15.160         79.0%
  m3          276     5.682    14.157    15.217         91.6%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 276 round):
    media      3.576 s
    mediana    3.008 s
    minimo     0.005 s
    5o perc.   0.159 s
    round con G < 100 ms: 10 su 276 (3.6%)

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         329       9  999323.3477  005b86712ffd0fb5   0035ad2241a0b5f6
  m1            329       9     108.4157  005b86712ffd0fb5   0035ad2241a0b5f6
  m2            329       9      20.7966  005b86712ffd0fb5   0035ad2241a0b5f6
  m3            329       9      61.4566  005b86712ffd0fb5   0035ad2241a0b5f6
  c1            329       9      77.9716  005b86712ffd0fb5   0035ad2241a0b5f6
  c2            329       9      85.2638  005b86712ffd0fb5   0035ad2241a0b5f6
  c3            329       9      88.8532  005b86712ffd0fb5   0035ad2241a0b5f6
  c4            329       9      91.0456  005b86712ffd0fb5   0035ad2241a0b5f6
  c5            329       9       92.838  005b86712ffd0fb5   0035ad2241a0b5f6
  ca            329       9      49.3566  005b86712ffd0fb5   0035ad2241a0b5f6
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt,85.56
  m2,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe,26.46
  m3,1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa,24.17
  c1,15fYhE3iZ4bpB7ugDAYGojPMeX2Spatt4cYUa3,17.50
  c2,17qTRawo67UbxQwDkqqHxGDpdvyfvfQdxpNybm,77.16
  c3,19CJJciQqbHBXRfwnZNpmfyWwq2CS5ExqyeWti,99.26
  c4,1ZGQepCG9n73v7nznTU4z3FWSu2Y5ZaTSRPy6v,92.76
  c5,1Sr73nub1pmsBWR9zQQ4Swj6AKw4syyoYts52e,70.53

── Adesioni ai cluster (membership.csv) ──
  m2,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe
  m3,1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa,1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa
  m1,1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt,1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt
  c1,15fYhE3iZ4bpB7ugDAYGojPMeX2Spatt4cYUa3,1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt
  c2,17qTRawo67UbxQwDkqqHxGDpdvyfvfQdxpNybm,1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt
  c3,19CJJciQqbHBXRfwnZNpmfyWwq2CS5ExqyeWti,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe
  c4,1ZGQepCG9n73v7nznTU4z3FWSu2Y5ZaTSRPy6v,19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe
  c5,1Sr73nub1pmsBWR9zQQ4Swj6AKw4syyoYts52e,1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  34,3,m1,51.6284,47.1470
  34,3,m3,49.7838,9.5568
  34,3,m2,49.7842,28.6705
  36,4,m3,40.1818,7.6364
  36,4,m2,21.0685,11.4411
  36,4,m1,105.042,97.8899
  49,5,m2,110.3498,65.0099
  49,5,m3,32.8394,6.1679
  49,5,m1,108.5079,101.1825
  60,6,m3,27.2191,5.0438
  60,6,m2,46.7525,26.8515
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
  36,refill,m1,100
  36,refill,m2,100
  ... (50 righe totali)

── Contatori diagnostici (somma sui 10 debug.log) ─────────────
  blocchi validati dalla sortition 2414
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             74063
  fold di fallback RANDAO          0
  score di sortition calcolati     832
  attese per mappa pesi vuota      277
  pesi registrati sullo stream     68
  letture della mappa dei pesi     7141
  epoche calcolate dal motore      260
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 26, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "19kvdJGdyLyMu8NcGpqistnByR71TSqfptkRQe", "published": 41030, "published_epoch": 26, "recomputed": 41030, "verdict": "ok"}, {"address": "1PZ3gzLZ6RaKq1ZtUUs5657xvQwtwxQH2tMqJa", "published": 13358, "published_epoch": 25, "recomputed": 0, "verdict": "other-epoch"}, {"address": "1adtRPUq4ybX3pziYy2xMkFSGwepw299oQivBt", "published": 115186, "published_epoch": 26, "recomputed": 115186, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/nazionale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/nazionale/run