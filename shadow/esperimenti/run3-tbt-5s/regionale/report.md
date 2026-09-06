[run] setup-first-blocks non specificato: uso 98 (minimo calcolato: 98)
════════════════════════════════════════════════════════════════════
  POESIA / wPoA — livello: regionale
  target-block-time=5s  setup=98  misura=200 blocchi  epoca=12
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
[gen_shadow_yaml] regionale -> /home/mattu/multichain/shadow/regionale/shadow.yaml
[gen_shadow_yaml]   host: m1, m2, m3, c1, c2, c3, c4, admin, ca, c5
[gen_shadow_yaml]   cluster: m1<-c1+c2, m2<-c3+c4, m3<-c5
[gen_shadow_yaml]   stop_time = 2430s simulati (98 blocchi di setup + 200 misurati a 5s)
[run] avvio Shadow (--unblocked-vdso-latency 20us)...
[run] Shadow terminato (rc=0) in 523s di wall clock.

══════════════════════════════════════════════════════════════════
  POESIA / wPoA — riepilogo run: livello regionale
══════════════════════════════════════════════════════════════════

── Blocchi ────────────────────────────────────────────────────
  totale prodotti      : 416
  fase di setup (PoA)  : 98 blocchi (height 1..98)
  finestra wPoA misurata: 318 blocchi (height 99..416)

  intervallo fra blocchi (finestra wPoA), target = 5 s:
    media       5.69 s     scarto vs target +0.69 s (+13.9%)
    mediana     6.00 s
    dev.std     1.55 s
    min/max     3.00 / 8.00 s

── Traiettoria dei pesi (stream wpoa-weights) ─────────────────
  epoca             m1        m2        m3
  e3                 1         1         1
  e5             12606      5186      3269
  e6             17404      6500          
  e7             62099     25615      7531
  e8             60602     20535      8243
  e9                       20707          
  e10            61643     25615      7531
  e11            60602     23161      9948
  e12            62099                8243
  e13                      20515      9948
  e14            69742     28242          
  e15            62099     23161      5826
  e16            68701     25615      9948
  e17            62099     23161          
  e18            68701                5826
  e19            62099     20515      9948
  e20                      23161      8243
  e21            61643     25615      9948
  e22            70199     28242          
  e23            78298                7531
  e24            62099     20515      9948
  e25                      23161      8243
  e26            61643     25615      9948
  e27            70199     25787          
  e28                      25615      7531
  e29            60145     23161      9948
  e30            70199     28242      8243
  e31                      23161      9948
  e32            61643     28242          
  e33            70199     23161      7531
  e34                      28242      9948
  record totali: 76

── Distribuzione dei proposer vs peso pubblicato ──────────────
  host   indirizzo                                blocchi     quota      peso    attesa
  m1     12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg       242    76.1%     70199    64.8%
  m2     1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u        66    20.8%     28242    26.1%
  m3     1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA        10     3.1%      9948     9.2%

  blocchi consecutivi dello stesso proposer: 240 osservati, 197.6 attesi

  chi-quadro = 22.351  (df=2, critico 5% = 5.991)  -> NON compatibile con la selezione pesata
  NB: il peso usato e' l'ULTIMO pubblicato; se e' cambiato fra
      le epoche il test e' solo indicativo: va letto insieme alla
      traiettoria per epoca riportata sopra.

── Delay di sortition per miner ───────────────────────────────
  banda: [2.50, 7.50] s   (T=5 s, delta=0.5, Dmax=2.50 s)
  host   campioni     min s   media s     max s  pos. in banda
  m1          340     2.374     5.351     7.483         57.0%
  m2          340     2.302     6.239     7.560         74.8%
  m3          340     2.428     7.090     7.550         91.8%
  (pos. in banda: 0% = sempre il primo a proporre, 100% = sempre l'ultimo)

  margine della timer race G = D(2) - D(1)   (Def. 5.15, su 340 round):
    media      1.705 s
    mediana    1.383 s
    minimo     0.003 s
    5o perc.   0.094 s
    round con G < 100 ms: 20 su 340 (5.9%)

  In questi round il margine e' dell'ordine della latenza di rete:
  il vincitore osservato puo' differire da quello designato dallo
  score (Prop. 5.18), e la distribuzione dei proposer si appiattisce
  rispetto ai pesi. Per allargare il margine: alzare target-block-time
  (Dmax = delta*T cresce in valore assoluto) o attivare dumpfunction
  sqrt/log, che comprime i rapporti fra i pesi (Def. 5.9).

── Consistenza fra nodi a fine run ────────────────────────────
  host       height   peers          GAS  best hash          hash a -6
  admin         416       9  999307.9883  0010f499416f5675   009115fc96c8879d
  m1            416       9     108.5616  0010f499416f5675   009115fc96c8879d
  m2            416       9      48.9976  0010f499416f5675   009115fc96c8879d
  m3            416       9      25.7475  0010f499416f5675   009115fc96c8879d
  c1            416       9      85.9886  0010f499416f5675   009115fc96c8879d
  c2            416       9      90.5892  0010f499416f5675   009115fc96c8879d
  c3            416       9      92.8918  0010f499416f5675   009115fc96c8879d
  c4            416       9      94.2956  0010f499416f5675   009115fc96c8879d
  c5            416       9       95.415  0010f499416f5675   009115fc96c8879d
  ca            416       9      49.3562  0010f499416f5675   009115fc96c8879d
  -> tutti i nodi sulla stessa testa: nessun fork.

── ESG certificati dal CA (esg_scores.csv) ──
  host,address,esg
  m1,12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg,85.56
  m2,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u,26.46
  m3,1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA,24.17
  c1,1SQMyZsYBPsB6Z3JdtVvK5Z4nzaQ7kisunM2wk,17.50
  c2,1A4CrFTvpKkWiGKyfcWKP3P5Ds6KMtYA11iE14,77.16
  c3,1b1ZDAStzMbTZrRLLYn6FkR3gJu28HRKRSfWAa,99.26
  c4,1CyRAtgWZSyPLhC773ckjxce1q6dYoQKSyNrqt,92.76
  c5,1XZvMfDDwwKtNGuGmjcDCiMPgHW9iyKB5AV7kN,70.53

── Adesioni ai cluster (membership.csv) ──
  m2,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u
  m3,1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA,1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA
  c3,1b1ZDAStzMbTZrRLLYn6FkR3gJu28HRKRSfWAa,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u
  c5,1XZvMfDDwwKtNGuGmjcDCiMPgHW9iyKB5AV7kN,1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA
  m1,12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg,12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg
  c2,1A4CrFTvpKkWiGKyfcWKP3P5Ds6KMtYA11iE14,12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg
  c1,1SQMyZsYBPsB6Z3JdtVvK5Z4nzaQ7kisunM2wk,12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg
  c4,1CyRAtgWZSyPLhC773ckjxce1q6dYoQKSyNrqt,1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u

── Riconciliazione verso il treasury (reconciliation.csv) ──
  height,epoch,miner,balance,sent
  67,6,m1,49.6782,45.2943
  67,6,m3,51.208,9.8416
  67,6,m2,49.9952,28.7971
  73,7,m2,20.8363,11.3018
  73,7,m1,104.5087,97.3833
  73,7,m3,41.3212,7.8642
  85,8,m2,109.8027,64.6816
  85,8,m3,33.6634,6.3327
  85,8,m1,108.0492,100.7467
  97,9,m2,44.9705,25.7823
  97,9,m3,27.9265,5.1853
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
  blocchi validati dalla sortition 3196
  blocchi RIFIUTATI dalla sortition 0
  seed RANDAO derivati             104577
  fold di fallback RANDAO          0
  score di sortition calcolati     1023
  attese per mappa pesi vuota      341
  pesi registrati sullo stream     81
  letture della mappa dei pesi     9354
  epoche calcolate dal motore      350
  report di malus valutati         31

── weightverifyweights (ricomputazione indipendente) ──────────
  {"epoch": 33, "verified": true, "records": 3, "invalid": 0, "entries": [{"address": "12zTjgCumTMomJBYYnuKAixmrhW7dXX12NKDwg", "published": 70199, "published_epoch": 33, "recomputed": 70199, "verdict": "ok"}, {"address": "1B6r6YPpfhSzpSvUo39JkyfYERxVrLyDC1ai7u", "published": 23161, "published_epoch": 33, "recomputed": 23161, "verdict": "ok"}, {"address": "1CL4LiiNpuWSxPGYkh8WN8g7EnEjU4EK3kDWCA", "published": 7531, "published_epoch": 33, "recomputed": 7531, "verdict": "ok"}]}

[collect_metrics] riepilogo scritto in /home/mattu/multichain/shadow/regionale/run/metrics/summary.txt
[run] output: /home/mattu/multichain/shadow/regionale/run