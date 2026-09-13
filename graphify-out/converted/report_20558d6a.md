<!-- converted from report.xlsx -->

## Sheet: Foglio di configurazione
| MyLedger / wPoA — Foglio di configurazione |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Parametro | Valore | Note |  |  |  |  |  |  |  |
| Score minimo ESG | 10 | intero, statico per tutta la run |  |  |  |  |  |  |  |
| Score massimo ESG | 20 | intero, statico per tutta la run |  |  |  |  |  |  |  |
| Numero minimo Tx | 8 | per azienda, per epoca |  |  |  |  |  |  |  |
| Numero massimo Tx | 18 | per azienda, per epoca |  |  |  |  |  |  |  |
| Numero min/max Tx miner | 10..20 | tau_Mk, il termine di attivita propria del miner in W_k |  |  |  |  |  |  |  |
| alpha (costo per Tx) | 0.2 | GAS per transazione — 1 GAS = 1 EUR |  |  |  |  |  |  |  |
| kappa | 100 | normalizzazione: Impatto utente = Tx * ESG / kappa |  |  |  |  |  |  |  |
| lambda | 0.5 | smorzamento del feedback di conformita |  |  |  |  |  |  |  |
| Peso % Reso | 50 | lambda in percentuale — il parametro del foglio Vers_2 |  |  |  |  |  |  |  |
| Base allocazione | raw | raw = A_k proporzionale a W_k (tesi/engine C++); final = A_k proporzionale a w_k (foglio Vers_2) |  |  |  |  |  |  |  |
| Modalita | wpoa | wpoa = selezione pesata; native = round-robin |  |  |  |  |  |  |  |
| Seed | 42 | ogni scelta casuale deriva da qui |  |  |  |  |  |  |  |
| Numero cluster | 5 | ClusterMiner |  |  |  |  |  |  |  |
| Aziende per cluster | 10 | trasmettono le transazioni |  |  |  |  |  |  |  |
| Epoche campionate | 9..28 | una scheda per epoca |  |  |  |  |  |  |  |
| Valuta | GAS | asset divisibile che modella il GAS nativo |  |  |  |  |  |  |  |
| Range di generazione (struttura del foglio Vers_2) |  |  |  |  |  |  |  |  |  |
|  | Score minimo ESG | Score massimo ESG | Numero minimo Tx | Numero massimo Tx |  |  |  |  |  |
| ClusterMinerA | 10 | 20 | 10 | 20 |  |  |  |  |  |
| ClusterMinerB | 10 | 20 | 10 | 20 |  |  |  |  |  |
| ClusterMinerC | 10 | 20 | 10 | 20 |  |  |  |  |  |
| ClusterMinerD | 10 | 20 | 10 | 20 |  |  |  |  |  |
| ClusterMinerE | 10 | 20 | 10 | 20 |  |  |  |  |  |
| AZIENDE ClusterMinerA | 10 | 20 | 8 | 18 |  |  |  |  |  |
| AZIENDE ClusterMinerB | 10 | 20 | 8 | 18 |  |  |  |  |  |
| AZIENDE ClusterMinerC | 10 | 20 | 8 | 18 |  |  |  |  |  |
| AZIENDE ClusterMinerD | 10 | 20 | 8 | 18 |  |  |  |  |  |
| AZIENDE ClusterMinerE | 10 | 20 | 8 | 18 |  |  |  |  |  |
| Peso % Reso | 50 |  |  |  |  |  |  |  |  |
| ClusterMiner — Score ESG, Certificato ISO, Peso %, Reso |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Peso % | Reso | Total GAIN (EUR) |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 24.8731 | 100 | 564.2354 |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 24.12347 | 90 | 570.6157 |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 16.20833 | 75 | 411.0118 |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 15.578605 | 60 | 432.9286 |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 19.21648 | 40 | 599.2080000000001 |  |  |  |  |
| AZIENDE per ogni Cluster (nome e Score ESG) |  |  |  |  |  |  |  |  |  |
| ClusterMinerA |  | ClusterMinerB |  | ClusterMinerC |  | ClusterMinerD |  | ClusterMinerE |  |
| Nome utente | Score ESG | Nome utente | Score ESG | Nome utente | Score ESG | Nome utente | Score ESG | Nome utente | Score ESG |
| Azienda_A1 | 11 | Azienda_B1 | 16 | Azienda_C1 | 20 | Azienda_D1 | 14 | Azienda_E1 | 14 |
| Azienda_A2 | 10 | Azienda_B2 | 10 | Azienda_C2 | 18 | Azienda_D2 | 12 | Azienda_E2 | 10 |
| Azienda_A3 | 14 | Azienda_B3 | 10 | Azienda_C3 | 16 | Azienda_D3 | 13 | Azienda_E3 | 17 |
| Azienda_A4 | 13 | Azienda_B4 | 11 | Azienda_C4 | 13 | Azienda_D4 | 15 | Azienda_E4 | 18 |
| Azienda_A5 | 13 | Azienda_B5 | 13 | Azienda_C5 | 17 | Azienda_D5 | 11 | Azienda_E5 | 11 |
| Azienda_A6 | 12 | Azienda_B6 | 13 | Azienda_C6 | 19 | Azienda_D6 | 11 | Azienda_E6 | 16 |
| Azienda_A7 | 11 | Azienda_B7 | 18 | Azienda_C7 | 14 | Azienda_D7 | 16 | Azienda_E7 | 11 |
| Azienda_A8 | 20 | Azienda_B8 | 19 | Azienda_C8 | 10 | Azienda_D8 | 11 | Azienda_E8 | 18 |
| Azienda_A9 | 18 | Azienda_B9 | 10 | Azienda_C9 | 12 | Azienda_D9 | 15 | Azienda_E9 | 14 |
| Azienda_A10 | 11 | Azienda_B10 | 18 | Azienda_C10 | 16 | Azienda_D10 | 15 | Azienda_E10 | 20 |
## Sheet: Epoch 9
| EPOCH 9  —  modalita wpoa  —  proposer ClusterMinerB (wpoa-weighted)  —  Theta (Tot Tx azienda) 666  —  monte premi alpha×Theta = 133.20 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 2.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 18 | 697.6 | 224.5968 | 29.9163 | 29.8403 | 0.076 | 99.746 | 29.9163 | 34880 | 0.224596 | 348.8 | 34880 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 18 | 1.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 0.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 17 | 3.23 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 8 | 1.44 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 20 | 706.8 | 227.5588 | 30.3108 | 26.0891 | 4.2217 | 86.072 | 30.3108 | 35340 | 0.227558 | 353.4 | 35340 | exact | SELECTED |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.7 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.8 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 15 | 456.3 | 146.9087 | 19.5682 | 14.8508 | 4.7174 | 75.8925 | 19.5682 | 22815 | 0.146908 | 228.15 | 22815 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 18 | 2.34 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.4 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 2.4 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 11 | 455.1 | 146.5224 | 19.5168 | 11.7093 | 7.8075 | 59.996 | 19.5168 | 22755 | 0.146522 | 227.55 | 22755 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.7 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 21 | 790.21 | 254.4132 | 33.8878 | 13.3263 | 20.5615 | 39.3248 | 33.8878 | 39511 | 0.254416 | 395.105 | 39511 | exact |  |
| TOTALI EPOCH 9 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 133.2 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 18 | 29.9163 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 20 | 30.3108 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 15 | 19.5682 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 11 | 19.5168 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 21 | 33.8878 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 10
| EPOCH 10  —  modalita wpoa  —  proposer ClusterMinerD (wpoa-weighted)  —  Theta (Tot Tx azienda) 483  —  monte premi alpha×Theta = 96.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 6 | 0.78 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 7 | 0.91 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 6 | 0.72 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 8 | 406.6 | 184.3698 | 17.8101 | 17.2692 | 0.6169 | 96.551 | 47.7264 | 40608 | 0.215178 | 406.083532 | 40608 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 7 | 0.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 0.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 6 | 0.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 7 | 1.26 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 14 | 505.02 | 228.9977 | 22.1212 | 22.8454 | 3.4975 | 86.7232 | 52.432 | 46985 | 0.248969 | 469.850309 | 46985 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 2.04 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 14 | 409.37 | 185.6259 | 17.9315 | 17.8159 | 4.833 | 78.6612 | 37.4997 | 36003 | 0.190777 | 360.025604 | 36003 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 6 | 0.72 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 7 | 1.05 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.35 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 10 | 340.2 | 154.2612 | 14.9016 | 13.4816 | 9.2275 | 59.3665 | 34.4184 | 27215 | 0.14421 | 272.153202 | 27215 | exact | SELECTED |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 7 | 0.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 7 | 0.77 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 14 | 544.16 | 246.7454 | 23.8356 | 18.4333 | 25.9638 | 41.5192 | 57.7234 | 37907 | 0.200866 | 379.074839 | 37907 | exact |  |
| TOTALI EPOCH 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 96.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 8 | 17.8101 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 14 | 22.1212 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 14 | 17.9315 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 10 | 14.9016 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 14 | 23.8356 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 11
| EPOCH 11  —  modalita wpoa  —  proposer ClusterMinerA (wpoa-weighted)  —  Theta (Tot Tx azienda) 488  —  monte premi alpha×Theta = 97.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 1.12 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 6 | 0.78 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 9 | 1.17 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 9 | 433.2 | 189.3721 | 18.4827 | 19.0996 | 0 | 100 | 66.2091 | 42573 | 0.216459 | 425.729364 | 42573 | exact | SELECTED |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.76 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 7 | 0.91 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 7 | 0.91 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 8 | 1.52 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 15 | 520.22 | 227.4126 | 22.1955 | 23.0681 | 2.6249 | 89.7836 | 74.6275 | 48569 | 0.246946 | 485.685658 | 48569 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 6 | 0.78 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.32 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 1.76 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 17 | 445.12 | 194.5829 | 18.9913 | 18.3113 | 5.513 | 76.8598 | 56.491 | 39763 | 0.202172 | 397.628401 | 39763 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 6 | 0.66 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 7 | 1.05 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 9 | 321.3 | 140.4553 | 13.7084 | 13.1467 | 9.7892 | 57.3193 | 48.1268 | 25602 | 0.130171 | 256.022297 | 25602 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.53 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 7 | 0.98 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 15 | 567.72 | 248.1771 | 24.2221 | 19.2844 | 30.9015 | 38.4259 | 81.9455 | 40172 | 0.204252 | 401.716268 | 40172 | exact |  |
| TOTALI EPOCH 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 97.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 9 | 18.4827 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 15 | 22.1955 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 17 | 18.9913 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 9 | 13.7084 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 15 | 24.2221 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 12
| EPOCH 12  —  modalita wpoa  —  proposer ClusterMinerA (wpoa-weighted)  —  Theta (Tot Tx azienda) 795  —  monte premi alpha×Theta = 159.00 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 21 | 2.52 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 21 | 807.6 | 222.3354 | 35.3513 | 33.6261 | 1.7252 | 95.1198 | 101.5604 | 80760 | 0.25649 | 807.6 | 80760 | exact | SELECTED |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 19 | 3.42 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 3.06 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 21 | 805.22 | 221.6802 | 35.2471 | 34.3411 | 3.5309 | 90.6768 | 109.8746 | 76409 | 0.242671 | 764.087747 | 76409 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 3.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 22 | 3.52 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 2.55 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 3.04 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 23 | 2.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.8 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 25 | 662.87 | 182.4907 | 29.016 | 24.9494 | 9.5796 | 72.2564 | 85.507 | 58618 | 0.186168 | 586.175148 | 58618 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.8 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 19 | 2.47 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 21 | 3.15 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 18 | 1.98 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.5 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 16 | 548.4 | 150.9766 | 24.0053 | 19.9916 | 13.8029 | 59.1564 | 72.1321 | 43137 | 0.137001 | 431.369553 | 43137 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 20 | 2.8 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.89 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 20 | 2.2 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 19 | 3.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 17 | 808.26 | 222.5171 | 35.3802 | 26.8969 | 39.3848 | 40.5797 | 117.3257 | 55942 | 0.177669 | 559.420721 | 55942 | exact |  |
| TOTALI EPOCH 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 159 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 21 | 35.3513 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 21 | 35.2471 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 25 | 29.016 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 16 | 24.0053 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 17 | 35.3802 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 13
| EPOCH 13  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 627  —  monte premi alpha×Theta = 125.40 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 20 | 702.6 | 228.4365 | 28.6459 | 29.643 | 0.7281 | 97.6027 | 130.2063 | 68546 | 0.259379 | 685.455998 | 68546 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 16 | 633.08 | 205.8335 | 25.8115 | 26.2644 | 3.078 | 89.5101 | 135.6861 | 60357 | 0.228391 | 603.568195 | 60357 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 16 | 2.56 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 2.38 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 17 | 3.23 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 18 | 487.63 | 158.5433 | 19.8813 | 21.0955 | 8.3654 | 71.6051 | 105.3883 | 41999 | 0.158925 | 419.986854 | 41999 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.56 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 2.25 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 8 | 1.2 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 20 | 574.65 | 186.8361 | 23.4293 | 22.1601 | 15.0721 | 59.5186 | 95.5614 | 45730 | 0.173043 | 457.296045 | 45730 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 2.04 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 3.06 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 17 | 677.73 | 220.3506 | 27.632 | 27.4375 | 39.5793 | 40.9412 | 144.9577 | 47638 | 0.180263 | 476.375324 | 47638 | exact | SELECTED |
| TOTALI EPOCH 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 125.4 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 20 | 28.6459 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 16 | 25.8115 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 18 | 19.8813 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 20 | 23.4293 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 17 | 27.632 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 14
| EPOCH 14  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 499  —  monte premi alpha×Theta = 99.80 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 8 | 1.12 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 7 | 0.77 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 8 | 1.44 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 14 | 537 | 223.8974 | 22.345 | 22.2952 | 0.7779 | 96.6285 | 152.5513 | 53056 | 0.257727 | 530.563129 | 53056 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 2.09 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 12 | 510.34 | 212.7817 | 21.2356 | 21.2122 | 3.1014 | 87.2442 | 156.9217 | 48357 | 0.234901 | 483.572821 | 48357 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 7 | 0.91 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 9 | 1.53 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 1.12 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 7 | 0.84 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 12 | 351.91 | 146.7258 | 14.6432 | 17.8617 | 5.1469 | 77.6305 | 120.0315 | 30195 | 0.146677 | 301.947712 | 30195 | exact |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.44 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.17 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 9 | 1.35 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 7 | 1.05 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 14 | 413.4 | 172.3635 | 17.2019 | 19.9464 | 12.3276 | 61.8033 | 112.7633 | 32973 | 0.160171 | 329.725034 | 32973 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 8 | 0.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.53 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 16 | 585.77 | 244.2316 | 24.3743 | 26.0123 | 37.9413 | 40.6737 | 169.332 | 41280 | 0.200524 | 412.795712 | 41280 | exact | SELECTED |
| TOTALI EPOCH 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 99.8 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 14 | 22.345 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 12 | 21.2356 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 12 | 14.6432 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 14 | 17.2019 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 16 | 24.3743 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 15
| EPOCH 15  —  modalita wpoa  —  proposer ClusterMinerC (wpoa-weighted)  —  Theta (Tot Tx azienda) 851  —  monte premi alpha×Theta = 170.20 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 19 | 2.09 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 20 | 2.6 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 19 | 2.28 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 18 | 775.6 | 206.5166 | 35.1491 | 34.9184 | 1.0086 | 97.1926 | 187.7004 | 76252 | 0.236278 | 762.525484 | 76253 | within-tol |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.88 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 19 | 1.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 19 | 2.09 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 21 | 3.78 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.85 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 22 | 3.96 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 17 | 791.54 | 210.7609 | 35.8715 | 33.5338 | 5.4391 | 86.0439 | 192.7932 | 74106 | 0.229629 | 741.056276 | 74106 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 21 | 3.78 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 19 | 3.04 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 2.89 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 22 | 4.18 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 22 | 2.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 18 | 2.16 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 21 | 3.36 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 19 | 618.28 | 164.6275 | 28.0196 | 25.4312 | 7.7353 | 76.6774 | 148.0511 | 54913 | 0.170156 | 549.127046 | 54913 | exact | SELECTED |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 21 | 2.52 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 19 | 2.85 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 20 | 2.2 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 21 | 3.36 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 20 | 3 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 18 | 2.7 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 21 | 663.15 | 176.5749 | 30.053 | 25.3774 | 17.0032 | 59.8798 | 142.8163 | 53650 | 0.166243 | 536.499322 | 53650 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 18 | 1.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 19 | 3.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 24 | 907.06 | 241.5201 | 41.1067 | 33.1907 | 45.8573 | 41.988 | 210.4387 | 63800 | 0.197694 | 637.997464 | 63800 | exact |  |
| TOTALI EPOCH 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 170.2 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 18 | 35.1491 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 17 | 35.8715 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 19 | 28.0196 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 21 | 30.053 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 24 | 41.1067 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 16
| EPOCH 16  —  modalita wpoa  —  proposer ClusterMinerC (wpoa-weighted)  —  Theta (Tot Tx azienda) 640  —  monte premi alpha×Theta = 128.00 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 12 | 568.2 | 200.3349 | 25.6429 | 26.6515 | 0 | 100 | 213.3433 | 56022 | 0.229755 | 560.224292 | 56022 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 17 | 669.56 | 236.0723 | 30.2173 | 31.1655 | 4.4909 | 87.4051 | 223.0105 | 62284 | 0.255436 | 622.837742 | 62284 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 17 | 3.23 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 14 | 444.47 | 156.7104 | 20.0589 | 19.9471 | 7.8471 | 71.7671 | 168.11 | 39264 | 0.161028 | 392.638954 | 39264 | exact | SELECTED |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.56 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.17 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.95 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 2.25 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 16 | 484.65 | 170.877 | 21.8723 | 24.4417 | 14.4338 | 62.8717 | 164.6886 | 38743 | 0.158891 | 387.428619 | 38743 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 2.56 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 3.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 15 | 669.37 | 236.0053 | 30.2087 | 31.6424 | 44.4236 | 41.5986 | 240.6474 | 47521 | 0.194891 | 475.212647 | 47521 | exact |  |
| TOTALI EPOCH 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 128 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 12 | 25.6429 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 17 | 30.2173 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 14 | 20.0589 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 16 | 21.8723 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 15 | 30.2087 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 17
| EPOCH 17  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 635  —  monte premi alpha×Theta = 127.00 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 1.92 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 17 | 677.2 | 232.9445 | 29.584 | 29.584 | 0 | 100 | 242.9273 | 67720 | 0.266166 | 677.2 | 67720 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 3.06 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.85 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 18 | 687.8 | 236.5907 | 30.047 | 29.9099 | 4.628 | 86.6002 | 253.0575 | 64449 | 0.253309 | 644.486022 | 64449 | exact |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 3.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 2.55 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.71 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 16 | 1.92 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 1.76 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 12 | 410.02 | 141.0394 | 17.912 | 19.3028 | 6.4563 | 74.9358 | 186.022 | 36509 | 0.143494 | 352.139796 | 35214 | off |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.25 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 1.95 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 19 | 526.2 | 181.0033 | 22.9874 | 23.1077 | 14.3135 | 61.7503 | 187.676 | 42852 | 0.168425 | 428.515526 | 42852 | exact |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 12 | 605.91 | 208.4221 | 26.4696 | 28.5858 | 42.3074 | 40.3223 | 267.117 | 42898 | 0.168606 | 428.980074 | 42898 | exact | SELECTED |
| TOTALI EPOCH 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 127 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 17 | 29.584 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 18 | 30.047 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 12 | 17.912 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 19 | 22.9874 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 12 | 26.4696 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 18
| EPOCH 18  —  modalita wpoa  —  proposer ClusterMinerD (wpoa-weighted)  —  Theta (Tot Tx azienda) 663  —  monte premi alpha×Theta = 132.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.44 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 17 | 3.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 15 | 649.6 | 218.7213 | 29.0024 | 27.9613 | 1.0411 | 96.4103 | 271.9297 | 64960 | 0.25203 | 649.6 | 64960 | exact |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 2.56 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 18 | 3.42 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 17 | 683.62 | 230.1759 | 30.5213 | 32.6235 | 2.5258 | 92.8141 | 283.5788 | 63875 | 0.247821 | 637.818238 | 63782 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 3.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 2.38 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.9 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 16 | 1.92 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 15 | 457.21 | 153.9433 | 20.4129 | 20.9199 | 5.9493 | 77.8583 | 206.4349 | 39606 | 0.153662 | 399.912095 | 39991 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 16 | 492.9 | 165.9602 | 22.0063 | 21.0825 | 15.2373 | 58.0469 | 209.6823 | 41111 | 0.159501 | 398.633593 | 39863 | off | SELECTED |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 16 | 2.72 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 3.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 15 | 686.66 | 231.1994 | 30.657 | 28.5485 | 44.4159 | 39.1266 | 297.774 | 48195 | 0.186986 | 481.768704 | 48177 | within-tol |  |
| TOTALI EPOCH 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 132.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 15 | 29.0024 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 17 | 30.5213 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 15 | 20.4129 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 16 | 22.0063 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 15 | 30.657 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 19
| EPOCH 19  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 662  —  monte premi alpha×Theta = 132.40 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.44 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 18 | 1.98 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 17 | 3.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 15 | 680.8 | 222.3601 | 29.4405 | 29.0891 | 1.3925 | 95.4317 | 301.3702 | 68993 | 0.257614 | 668.580651 | 66858 | off |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.76 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1.9 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 20 | 730.74 | 238.6713 | 31.6001 | 30.4661 | 3.6598 | 89.2756 | 315.1789 | 70886 | 0.264683 | 704.48481 | 70448 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 3.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.7 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 8 | 1.52 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.32 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 17 | 462.67 | 151.1154 | 20.0077 | 19.6677 | 6.2893 | 75.7703 | 226.4426 | 40823 | 0.15243 | 411.448478 | 41145 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 18 | 2.16 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 2.55 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 1.95 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 15 | 490.95 | 160.3521 | 21.2306 | 21.8095 | 14.6584 | 59.8047 | 230.9129 | 38613 | 0.144178 | 387.965506 | 38797 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 17 | 696.54 | 227.5011 | 30.1211 | 31.298 | 43.239 | 41.9899 | 327.8951 | 48500 | 0.181095 | 484.536263 | 48454 | within-tol | SELECTED |
| TOTALI EPOCH 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 132.4 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 15 | 29.4405 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 20 | 31.6001 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 17 | 20.0077 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 15 | 21.2306 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 17 | 30.1211 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 20
| EPOCH 20  —  modalita wpoa  —  proposer ClusterMinerB (wpoa-weighted)  —  Theta (Tot Tx azienda) 641  —  monte premi alpha×Theta = 128.20 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 18 | 714.4 | 228.3435 | 29.2736 | 29.3891 | 1.277 | 95.8358 | 330.6438 | 69476 | 0.255838 | 698.081926 | 69808 | within-tol |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 2.09 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 16 | 619.97 | 198.1609 | 25.4042 | 26.5404 | 2.5236 | 91.3171 | 340.5831 | 61007 | 0.224652 | 586.725951 | 58673 | off | SELECTED |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.9 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 19 | 486.59 | 155.5286 | 19.9388 | 20.2482 | 5.9799 | 77.2004 | 246.3814 | 42693 | 0.157213 | 427.640382 | 42764 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.17 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 2.25 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 18 | 2.7 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 2.4 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 19 | 544.05 | 173.8946 | 22.2933 | 22.8829 | 14.0688 | 61.9265 | 253.2062 | 43637 | 0.160689 | 434.708599 | 43471 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 1.6 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 3.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 19 | 763.61 | 244.0725 | 31.2901 | 29.5412 | 44.9879 | 39.6371 | 359.1852 | 54749 | 0.201608 | 542.124477 | 54212 | within-tol |  |
| TOTALI EPOCH 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 128.2 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 18 | 29.2736 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 16 | 25.4042 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 19 | 19.9388 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 19 | 22.2933 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 19 | 31.2901 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 21
| EPOCH 21  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 492  —  monte premi alpha×Theta = 98.40 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 6 | 0.72 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 6 | 0.66 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 14 | 533.8 | 216.9495 | 21.3478 | 22.5585 | 0.0663 | 99.707 | 351.9916 | 51746 | 0.244724 | 522.68573 | 52269 | off |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 1.04 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 14 | 536.56 | 218.0713 | 21.4582 | 21.7527 | 2.2291 | 90.705 | 362.0413 | 50911 | 0.240775 | 513.265498 | 51327 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 8 | 1.52 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 8 | 0.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 14 | 390.91 | 158.8755 | 15.6333 | 15.9737 | 5.6395 | 73.9071 | 262.0147 | 34562 | 0.163455 | 346.347056 | 34635 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 6 | 0.84 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 7 | 0.84 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.5 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 7 | 0.77 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 15 | 413.25 | 167.955 | 16.5268 | 18.9467 | 11.6489 | 61.9262 | 269.733 | 33287 | 0.157426 | 334.580661 | 33458 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.7 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 8 | 1.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 16 | 585.96 | 238.1487 | 23.4338 | 26.5432 | 41.8785 | 38.7935 | 382.619 | 40940 | 0.193619 | 409.108878 | 40911 | within-tol | SELECTED |
| TOTALI EPOCH 21 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 98.4 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 14 | 21.3478 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 14 | 21.4582 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 14 | 15.6333 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 15 | 16.5268 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 16 | 23.4338 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 22
| EPOCH 22  —  modalita wpoa  —  proposer ClusterMinerC (wpoa-weighted)  —  Theta (Tot Tx azienda) 650  —  monte premi alpha×Theta = 130.00 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 14 | 611.2 | 210.2757 | 27.3358 | 27.4021 | 0 | 100 | 379.3274 | 60160 | 0.239984 | 610.304466 | 61030 | off |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 2.47 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 14 | 606.67 | 208.7172 | 27.1332 | 26.7633 | 2.599 | 91.1485 | 389.1745 | 57597 | 0.22976 | 578.475117 | 57848 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 2.38 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 15 | 2.85 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 16 | 481 | 165.482 | 21.5127 | 20.2833 | 6.8689 | 74.7022 | 283.5274 | 41381 | 0.165073 | 418.246694 | 41825 | off | SELECTED |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.25 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 18 | 535.95 | 184.3869 | 23.9703 | 20.3474 | 15.2718 | 57.1248 | 293.7033 | 43295 | 0.172708 | 433.921801 | 43392 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 16 | 671.84 | 231.1381 | 30.048 | 30.0051 | 41.9214 | 41.7163 | 412.667 | 48250 | 0.192474 | 466.235262 | 46624 | off |  |
| TOTALI EPOCH 22 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 130 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 14 | 27.3358 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 14 | 27.1332 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 16 | 21.5127 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 18 | 23.9703 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 16 | 30.048 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 23
| EPOCH 23  —  modalita wpoa  —  proposer ClusterMinerA (wpoa-weighted)  —  Theta (Tot Tx azienda) 816  —  monte premi alpha×Theta = 163.20 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 19 | 2.66 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 18 | 2.16 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 18 | 1.98 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 15 | 734.6 | 203.4576 | 33.2043 | 33.2043 | 0 | 100 | 412.5317 | 73156 | 0.234722 | 734.6 | 73460 | within-tol | SELECTED |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.88 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 21 | 2.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 21 | 2.73 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 20 | 2.6 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.85 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 23 | 865.64 | 239.751 | 39.1274 | 36.4967 | 5.2297 | 87.4667 | 428.3019 | 82428 | 0.264471 | 827.328996 | 82733 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 18 | 2.88 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 19 | 3.23 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 19 | 3.61 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 20 | 2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.32 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 18 | 557.57 | 154.4267 | 25.2024 | 23.9828 | 8.0885 | 74.7796 | 308.7298 | 48348 | 0.155125 | 487.043623 | 48704 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 22 | 2.64 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 2.55 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 22 | 3.3 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 23 | 681.75 | 188.8201 | 30.8154 | 27.1516 | 18.9356 | 58.9135 | 324.5187 | 53273 | 0.170927 | 535.599193 | 53560 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 20 | 3.4 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 23 | 4.14 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 18 | 3.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 16 | 771.02 | 213.5446 | 34.8505 | 30.9027 | 45.8692 | 40.2526 | 447.5175 | 54466 | 0.174755 | 546.330645 | 54633 | within-tol |  |
| TOTALI EPOCH 23 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 163.2 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 15 | 33.2043 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 23 | 39.1274 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 18 | 25.2024 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 23 | 30.8154 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 16 | 34.8505 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 24
| EPOCH 24  —  modalita wpoa  —  proposer ClusterMinerE (wpoa-weighted)  —  Theta (Tot Tx azienda) 649  —  monte premi alpha×Theta = 129.80 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 17 | 686.4 | 221.9607 | 28.8105 | 28.3663 | 0.4442 | 98.4582 | 441.3422 | 68387 | 0.257885 | 686.4 | 68640 | within-tol |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 18 | 2.34 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 8 | 1.44 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 15 | 2.85 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 14 | 599.45 | 193.8437 | 25.1609 | 27.767 | 2.6236 | 91.3671 | 453.4628 | 56146 | 0.211725 | 561.88453 | 56188 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 15 | 3 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 2.89 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 2.66 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 20 | 530.79 | 171.6412 | 22.279 | 23.1091 | 7.2584 | 76.0981 | 331.0088 | 46198 | 0.174211 | 463.856403 | 46386 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 16 | 1.92 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 2.72 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 1.95 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 19 | 553.8 | 179.0819 | 23.2448 | 25.0565 | 17.1239 | 59.4032 | 347.7635 | 43792 | 0.165138 | 440.031586 | 44003 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.89 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.44 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 20 | 722 | 233.4726 | 30.3047 | 31.5429 | 44.631 | 41.4091 | 477.8222 | 50661 | 0.191041 | 506.311953 | 50631 | within-tol | SELECTED |
| TOTALI EPOCH 24 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 129.8 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 17 | 28.8105 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 14 | 25.1609 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 20 | 22.279 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 19 | 23.2448 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 20 | 30.3047 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 25
| EPOCH 25  —  modalita wpoa  —  proposer ClusterMinerA (wpoa-weighted)  —  Theta (Tot Tx azienda) 628  —  monte premi alpha×Theta = 125.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.95 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 2.08 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.08 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 20 | 726.8 | 256.926 | 32.2699 | 32.7141 | 0 | 100 | 473.6121 | 71065 | 0.289555 | 721.197102 | 72120 | off | SELECTED |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 15 | 1.5 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 18 | 2.34 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 2.52 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 2.66 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 2.34 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 13 | 616.36 | 217.8851 | 27.3664 | 26.7497 | 3.2403 | 89.1954 | 480.8292 | 58374 | 0.237846 | 589.755028 | 58976 | off |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 3.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 16 | 2.72 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 1.44 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 2.56 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 12 | 431.86 | 152.6638 | 19.1746 | 19.2926 | 7.1404 | 72.9868 | 350.1834 | 37660 | 0.153446 | 380.248695 | 38025 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 2.04 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.4 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 6 | 0.66 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 11 | 1.65 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.35 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 13 | 453.6 | 160.349 | 20.1398 | 22.2853 | 14.9784 | 59.8043 | 367.9033 | 36064 | 0.146943 | 361.526418 | 36153 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 11 | 1.54 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.7 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 9 | 1.26 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 11 | 2.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 17 | 600.21 | 212.1761 | 26.6493 | 28.5083 | 42.772 | 39.9946 | 504.4715 | 42265 | 0.172209 | 424.375675 | 42438 | within-tol |  |
| TOTALI EPOCH 25 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 125.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 20 | 32.2699 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 13 | 27.3664 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 12 | 19.1746 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 13 | 20.1398 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 17 | 26.6493 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 26
| EPOCH 26  —  modalita wpoa  —  proposer ClusterMinerA (wpoa-weighted)  —  Theta (Tot Tx azienda) 698  —  monte premi alpha×Theta = 139.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 17 | 2.21 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 9 | 1.8 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 20 | 753 | 224.8956 | 31.3954 | 31.3954 | 0 | 100 | 505.0075 | 73682 | 0.260771 | 753 | 75300 | off | SELECTED |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.08 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.4 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 1.87 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 18 | 2.34 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 2.66 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 12 | 1.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 17 | 659.87 | 197.0808 | 27.5125 | 27.0575 | 3.6953 | 87.9839 | 508.3417 | 60984 | 0.215831 | 624.221838 | 62422 | off |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 10 | 2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 9 | 1.44 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 18 | 3.06 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 2.66 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 14 | 1.96 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 9 | 0.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.56 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 17 | 474.24 | 141.6394 | 19.7729 | 19.2401 | 7.6732 | 71.4892 | 369.9563 | 40705 | 0.144061 | 410.186293 | 41019 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 16 | 2.24 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 1.8 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.69 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 12 | 1.8 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 16 | 2.56 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 19 | 2.85 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 21 | 3.15 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 17 | 560.7 | 167.4621 | 23.3777 | 22.6812 | 15.6749 | 59.1332 | 391.281 | 44439 | 0.157276 | 448.011393 | 44801 | within-tol |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 17 | 2.38 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 22 | 2.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 16 | 2.88 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 18 | 3.24 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 13 | 1.82 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 20 | 4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 24 | 900.41 | 268.922 | 37.5415 | 31.6538 | 48.6597 | 39.4128 | 542.013 | 62744 | 0.22206 | 630.262873 | 63026 | within-tol |  |
| TOTALI EPOCH 26 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 139.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 20 | 31.3954 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 17 | 27.5125 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 17 | 19.7729 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 17 | 23.3777 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 24 | 37.5415 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 27
| EPOCH 27  —  modalita wpoa  —  proposer ClusterMinerD (wpoa-weighted)  —  Theta (Tot Tx azienda) 483  —  monte premi alpha×Theta = 96.60 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 10 | 1.1 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 14 | 548 | 232.1444 | 22.4251 | 22.4251 | 0 | 100 | 527.4326 | 53553 | 0.262914 | 548 | 54800 | off |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 6 | 0.96 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 0.88 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 1.56 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 7 | 1.33 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 7 | 0.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 9 | 1.62 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 18 | 586.34 | 248.386 | 23.9941 | 23.7386 | 3.9508 | 85.7317 | 532.3358 | 55607 | 0.272998 | 551.112278 | 55111 | within-tol |  |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 8 | 1.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 11 | 1.98 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 10 | 1.6 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.3 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 13 | 2.21 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 1.71 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 7 | 0.98 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 10 | 1 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 8 | 0.96 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 8 | 1.28 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 15 | 385.06 | 163.1195 | 15.7573 | 17.5009 | 5.9296 | 74.6928 | 385.7136 | 32605 | 0.160072 | 330.168136 | 33017 | off |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 10 | 1.2 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.43 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 8 | 1.2 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 11 | 1.21 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 9 | 0.99 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 11 | 1.76 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 6 | 0.66 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 10 | 1.5 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 11 | 370.95 | 157.1423 | 15.1799 | 17.7852 | 13.0696 | 57.6416 | 406.4609 | 29279 | 0.143743 | 295.152354 | 29515 | within-tol | SELECTED |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 2 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 8 | 1.12 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 8 | 0.8 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 11 | 1.87 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 10 | 1.8 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 6 | 0.66 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 7 | 1.12 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 12 | 1.32 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 7 | 1.26 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 10 | 1.4 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 12 | 2.4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 11 | 470.25 | 199.2078 | 19.2435 | 26.1838 | 41.7194 | 38.5605 | 561.2565 | 32646 | 0.160273 | 327.794349 | 32779 | within-tol |  |
| TOTALI EPOCH 27 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 96.6 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 14 | 22.4251 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 18 | 23.9941 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 15 | 15.7573 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 11 | 15.1799 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 11 | 19.2435 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Epoch 28
| EPOCH 28  —  modalita wpoa  —  proposer ClusterMinerB (wpoa-weighted)  —  Theta (Tot Tx azienda) 824  —  monte premi alpha×Theta = 164.80 € |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Nome utente | Tx Utente | Impatto utente | Score ESG | Tx Miner | Impatto Cluster | Delay in msec | Guadagno Ex (€) | € Resi in Ex | Giacenza | % Reso | Total GAIN | Peso engine w_k | Prob. selezione | w_k atteso | w_k atteso (int) | Match | Proposer |
| ClusterMinerA   —   Score ESG 20   —   ISO 14001   —   blocchi proposti 0 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 1.98 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 21 | 2.73 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 19 | 2.47 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 18 | 2.16 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 18 | 1.98 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 20 | 4 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 16 | 1.76 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerA |  |  | 20 | 19 | 851.6 | 223.3178 | 36.8028 | 36.8028 | 0 | 100 | 564.2354 | 83010 | 0.256555 | 851.6 | 85160 | off |  |
| ClusterMinerB   —   Score ESG 19   —   ISO 14001 + ISO 50001   —   blocchi proposti 3 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.92 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 22 | 2.2 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 20 | 2.6 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 21 | 2.73 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 21 | 3.78 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 17 | 1.7 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 17 | 3.06 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerB |  |  | 19 | 23 | 885.78 | 232.2809 | 38.2799 | 37.9372 | 4.2935 | 89.8332 | 570.6157 | 79699 | 0.246322 | 822.587233 | 82259 | off | SELECTED |
| ClusterMinerC   —   Score ESG 13   —   ISO 9001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 13 | 2.6 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 19 | 3.04 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 19 | 2.47 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 22 | 3.74 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 12 | 2.28 | 19 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 2.1 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 19 | 1.9 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 15 | 1.8 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerC |  |  | 13 | 20 | 585.39 | 153.5087 | 25.2982 | 23.9007 | 7.3271 | 76.5366 | 411.0118 | 50673 | 0.156613 | 511.317135 | 51132 | within-tol |  |
| ClusterMinerD   —   Score ESG 15   —   ISO 14001   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 18 | 2.52 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 14 | 1.68 | 12 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 14 | 1.82 | 13 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 17 | 2.55 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 19 | 2.09 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 15 | 2.4 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 14 | 1.54 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 18 | 2.7 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 14 | 2.1 | 15 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerD |  |  | 15 | 20 | 612.45 | 160.6047 | 26.4677 | 24.1221 | 15.4152 | 61.011 | 432.9286 | 49347 | 0.152515 | 482.737986 | 48274 | off |  |
| ClusterMinerE   —   Score ESG 19   —   non certificato   —   blocchi proposti 1 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 1 | 12 | 1.68 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 2 | 13 | 1.3 | 10 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 3 | 18 | 3.06 | 17 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 4 | 15 | 2.7 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 5 | 15 | 1.65 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 6 | 14 | 2.24 | 16 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 7 | 13 | 1.43 | 11 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 8 | 12 | 2.16 | 18 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 9 | 20 | 2.8 | 14 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
|     Azienda 10 | 21 | 4.2 | 20 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| TOTALE ClusterMinerE |  |  | 19 | 23 | 878.18 | 230.2879 | 37.9515 | 31.2092 | 48.4617 | 39.1726 | 599.208 | 60827 | 0.187995 | 608.405213 | 60841 | within-tol |  |
| TOTALI EPOCH 28 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Tot Tx Epoch / Tot Impatto |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Total GAS distribuito (= alpha × Theta) | 164.8 | GAS = EUR ; somma Delay attesa = 1000 |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| Riepilogo Score ESG e Certificato ISO per cluster |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Score ESG | Certificato ISO | Tx Miner | Guadagno Ex (€) |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerA | 20 | ISO 14001 | 19 | 36.8028 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerB | 19 | ISO 14001 + ISO 50001 | 23 | 38.2799 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerC | 13 | ISO 9001 | 20 | 25.2982 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerD | 15 | ISO 14001 | 20 | 26.4677 |  |  |  |  |  |  |  |  |  |  |  |  |  |
| ClusterMinerE | 19 | non certificato | 23 | 37.9515 |  |  |  |  |  |  |  |  |  |  |  |  |  |
## Sheet: Riepilogo
| Riepilogo per epoca |  |  |  |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Epoch | Proposer | Theta (Tx azienda) | Tot Impatto (Σ W_k) | Σ tau_Mk | Somma Delay (=1000) | alpha×Theta (€) | Σ Guadagno (€) | Σ Resi (€) | % Reso media |
| 9 | ClusterMinerB | 666 | 3106.01 | 85 | 999.9999 | 133.2 | 133.1999 | 95.81580000000001 | 71.93383778816651 |
| 10 | ClusterMinerD | 483 | 2205.35 | 60 | 1000 | 96.60000000000001 | 96.6 | 89.84540000000001 | 67.05676270542551 |
| 11 | ClusterMinerA | 488 | 2287.56 | 65 | 1000 | 97.60000000000001 | 97.6 | 92.9101 | 65.55026961584946 |
| 12 | ClusterMinerA | 795 | 3632.35 | 100 | 1000 | 159 | 158.9999 | 139.8051 | 67.26945534419004 |
| 13 | ClusterMinerE | 627 | 3075.69 | 91 | 1000 | 125.4 | 125.4 | 126.6005 | 65.45252539248094 |
| 14 | ClusterMinerE | 499 | 2398.42 | 68 | 999.9999999999999 | 99.80000000000001 | 99.80000000000001 | 107.3278 | 64.41359501004963 |
| 15 | ClusterMinerC | 851 | 3755.63 | 99 | 1000 | 170.2 | 170.1999 | 152.4515 | 66.42911610274734 |
| 16 | ClusterMinerC | 640 | 2836.25 | 74 | 999.9999 | 128 | 128.0001 | 133.8482 | 65.27792137867263 |
| 17 | ClusterMinerE | 635 | 2907.13 | 78 | 1000 | 127 | 127 | 130.4902 | 65.83916680205495 |
| 18 | ClusterMinerD | 663 | 2969.99 | 78 | 1000.0001 | 132.6 | 132.5999 | 131.1357 | 65.46797859864775 |
| 19 | ClusterMinerE | 662 | 3061.7 | 84 | 1000 | 132.4 | 132.4 | 132.3304 | 65.65004410391656 |
| 20 | ClusterMinerB | 641 | 3128.62 | 91 | 1000.0001 | 128.2 | 128.2 | 128.6018 | 65.13495307411402 |
| 21 | ClusterMinerE | 492 | 2460.48 | 73 | 1000 | 98.4 | 98.3999 | 105.7748 | 63.24840600560522 |
| 22 | ClusterMinerC | 650 | 2906.66 | 78 | 999.9998999999999 | 130 | 130 | 124.8012 | 65.1831718306946 |
| 23 | ClusterMinerA | 816 | 3610.58 | 95 | 1000 | 163.2 | 163.2 | 151.7381 | 66.01295303990105 |
| 24 | ClusterMinerE | 649 | 3092.44 | 90 | 1000.0001 | 129.8 | 129.7999 | 135.8418 | 65.33277479296412 |
| 25 | ClusterMinerA | 628 | 2828.83 | 75 | 1000 | 125.6 | 125.6 | 129.55 | 65.5348437458108 |
| 26 | ClusterMinerA | 698 | 3348.22 | 95 | 999.9999 | 139.6 | 139.6 | 132.028 | 63.55716597081516 |
| 27 | ClusterMinerD | 483 | 2360.6 | 69 | 1000 | 96.60000000000001 | 96.5999 | 107.6336 | 62.46762969884448 |
| 28 | ClusterMinerB | 824 | 3813.4 | 105 | 1000 | 164.8 | 164.8001 | 153.972 | 67.0991133897969 |
| Totali della run per cluster |  |  |  |  |  |  |  |  |  |
| ClusterMiner | Σ tau_Mk | Guadagno (€) | Resi (€) | % Reso | Giacenza finale B_k | Total GAIN | Peso % medio | Blocchi proposti | Match w_k |
| ClusterMinerA | 318 | 564.2354 | 564.2354 | 98.40356253658074 | 0 | 564.2354 | 24.8731 | 28 | 13/20 |
| ClusterMinerB | 339 | 570.6157 | 566.3222 | 88.83414422880695 | 4.2935 | 570.6157 | 24.12347 | 21 | 16/20 |
| ClusterMinerC | 329 | 411.0118 | 403.6846999999999 | 75.03115109619888 | 7.3271 | 411.0118 | 16.20833 | 22 | 17/20 |
| ClusterMinerD | 322 | 432.9286 | 417.5133999999999 | 59.86941000769315 | 15.4152 | 432.9286 | 15.578605 | 21 | 18/20 |
| ClusterMinerE | 345 | 599.2080000000001 | 550.7462999999999 | 40.3116110296822 | 48.4617 | 599.208 | 19.21648 | 28 | 19/20 |
## Sheet: Pesi & Probabilita
| Peso pubblicato dall'engine (wpoa-weights) per epoca × cluster |  |  |  |  |  |  |
| --- | --- | --- | --- | --- | --- | --- |
| Epoch | ClusterMinerA | ClusterMinerB | ClusterMinerC | ClusterMinerD | ClusterMinerE | Proposer |
| 9 | 34880 | 35340 | 22815 | 22755 | 39511 | ClusterMinerB |
| 10 | 40608 | 46985 | 36003 | 27215 | 37907 | ClusterMinerD |
| 11 | 42573 | 48569 | 39763 | 25602 | 40172 | ClusterMinerA |
| 12 | 80760 | 76409 | 58618 | 43137 | 55942 | ClusterMinerA |
| 13 | 68546 | 60357 | 41999 | 45730 | 47638 | ClusterMinerE |
| 14 | 53056 | 48357 | 30195 | 32973 | 41280 | ClusterMinerE |
| 15 | 76252 | 74106 | 54913 | 53650 | 63800 | ClusterMinerC |
| 16 | 56022 | 62284 | 39264 | 38743 | 47521 | ClusterMinerC |
| 17 | 67720 | 64449 | 36509 | 42852 | 42898 | ClusterMinerE |
| 18 | 64960 | 63875 | 39606 | 41111 | 48195 | ClusterMinerD |
| 19 | 68993 | 70886 | 40823 | 38613 | 48500 | ClusterMinerE |
| 20 | 69476 | 61007 | 42693 | 43637 | 54749 | ClusterMinerB |
| 21 | 51746 | 50911 | 34562 | 33287 | 40940 | ClusterMinerE |
| 22 | 60160 | 57597 | 41381 | 43295 | 48250 | ClusterMinerC |
| 23 | 73156 | 82428 | 48348 | 53273 | 54466 | ClusterMinerA |
| 24 | 68387 | 56146 | 46198 | 43792 | 50661 | ClusterMinerE |
| 25 | 71065 | 58374 | 37660 | 36064 | 42265 | ClusterMinerA |
| 26 | 73682 | 60984 | 40705 | 44439 | 62744 | ClusterMinerA |
| 27 | 53553 | 55607 | 32605 | 29279 | 32646 | ClusterMinerD |
| 28 | 83010 | 79699 | 50673 | 49347 | 60827 | ClusterMinerB |
| Probabilita di selezione (peso / Σ pesi) |  |  |  |  |  |  |
| Epoch | ClusterMinerA | ClusterMinerB | ClusterMinerC | ClusterMinerD | ClusterMinerE |  |
| 9 | 0.224596 | 0.227558 | 0.146908 | 0.146522 | 0.254416 |  |
| 10 | 0.215178 | 0.248969 | 0.190777 | 0.14421 | 0.200866 |  |
| 11 | 0.216459 | 0.246946 | 0.202172 | 0.130171 | 0.204252 |  |
| 12 | 0.25649 | 0.242671 | 0.186168 | 0.137001 | 0.177669 |  |
| 13 | 0.259379 | 0.228391 | 0.158925 | 0.173043 | 0.180263 |  |
| 14 | 0.257727 | 0.234901 | 0.146677 | 0.160171 | 0.200524 |  |
| 15 | 0.236278 | 0.229629 | 0.170156 | 0.166243 | 0.197694 |  |
| 16 | 0.229755 | 0.255436 | 0.161028 | 0.158891 | 0.194891 |  |
| 17 | 0.266166 | 0.253309 | 0.143494 | 0.168425 | 0.168606 |  |
| 18 | 0.25203 | 0.247821 | 0.153662 | 0.159501 | 0.186986 |  |
| 19 | 0.257614 | 0.264683 | 0.15243 | 0.144178 | 0.181095 |  |
| 20 | 0.255838 | 0.224652 | 0.157213 | 0.160689 | 0.201608 |  |
| 21 | 0.244724 | 0.240775 | 0.163455 | 0.157426 | 0.193619 |  |
| 22 | 0.239984 | 0.22976 | 0.165073 | 0.172708 | 0.192474 |  |
| 23 | 0.234722 | 0.264471 | 0.155125 | 0.170927 | 0.174755 |  |
| 24 | 0.257885 | 0.211725 | 0.174211 | 0.165138 | 0.191041 |  |
| 25 | 0.289555 | 0.237846 | 0.153446 | 0.146943 | 0.172209 |  |
| 26 | 0.260771 | 0.215831 | 0.144061 | 0.157276 | 0.22206 |  |
| 27 | 0.262914 | 0.272998 | 0.160072 | 0.143743 | 0.160273 |  |
| 28 | 0.256555 | 0.246322 | 0.156613 | 0.152515 | 0.187995 |  |
## Sheet: Proposer log (wpoa)
| epoch | selected_proposer | selection_probability_at_time | theoretical_expected_proposer | match_expected | total_selections_ClusterMinerA | total_selections_ClusterMinerB | total_selections_ClusterMinerC | total_selections_ClusterMinerD | total_selections_ClusterMinerE | cumulative_deviation_from_expected |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 9 | ClusterMinerB | 0.2276 | ClusterMinerE | no | 1 | 2 | 1 | 1 | 1 | 0.2914 |
| 10 | ClusterMinerD | 0.1442 | ClusterMinerB | no | 1 | 3 | 2 | 3 | 3 | 0.3119 |
| 11 | ClusterMinerA | 0.2165 | ClusterMinerB | no | 4 | 5 | 2 | 4 | 3 | 0.2573 |
| 12 | ClusterMinerA | 0.2565 | ClusterMinerA | yes | 6 | 6 | 4 | 5 | 3 | 0.1573 |
| 13 | ClusterMinerE | 0.1803 | ClusterMinerA | no | 6 | 6 | 5 | 7 | 6 | 0.1755 |
| 14 | ClusterMinerE | 0.2005 | ClusterMinerA | no | 7 | 7 | 6 | 8 | 8 | 0.2075 |
| 15 | ClusterMinerC | 0.1702 | ClusterMinerA | no | 9 | 8 | 8 | 8 | 9 | 0.1223 |
| 16 | ClusterMinerC | 0.161 | ClusterMinerB | no | 11 | 9 | 10 | 8 | 10 | 0.137 |
| 17 | ClusterMinerE | 0.1686 | ClusterMinerA | no | 13 | 9 | 11 | 9 | 12 | 0.2277 |
| 18 | ClusterMinerD | 0.1595 | ClusterMinerA | no | 13 | 10 | 13 | 12 | 12 | 0.233 |
| 19 | ClusterMinerE | 0.1811 | ClusterMinerB | no | 14 | 11 | 15 | 12 | 14 | 0.287 |
| 20 | ClusterMinerB | 0.2247 | ClusterMinerA | no | 16 | 13 | 15 | 13 | 15 | 0.1554 |
| 21 | ClusterMinerE | 0.1936 | ClusterMinerA | no | 17 | 15 | 15 | 13 | 18 | 0.1505 |
| 22 | ClusterMinerC | 0.1651 | ClusterMinerA | no | 18 | 15 | 17 | 14 | 20 | 0.1659 |
| 23 | ClusterMinerA | 0.2347 | ClusterMinerB | no | 20 | 16 | 18 | 14 | 22 | 0.2291 |
| 24 | ClusterMinerE | 0.191 | ClusterMinerA | no | 21 | 17 | 19 | 15 | 24 | 0.1653 |
| 25 | ClusterMinerA | 0.2896 | ClusterMinerA | yes | 24 | 17 | 20 | 16 | 25 | 0.2509 |
| 26 | ClusterMinerA | 0.2608 | ClusterMinerA | yes | 27 | 18 | 21 | 17 | 25 | 0.1199 |
| 27 | ClusterMinerD | 0.1437 | ClusterMinerB | no | 28 | 18 | 21 | 20 | 27 | 0.2648 |
| 28 | ClusterMinerB | 0.2463 | ClusterMinerA | no | 28 | 21 | 22 | 21 | 28 | 0.1891 |
## Sheet: Verifiche
| Invarianti di fine run (output/assertions.csv) |  |  |  |
| --- | --- | --- | --- |
| Check | Ambito | Esito | Dettaglio |
| engine_matches_replay | published w_k vs harness replay | FAIL | 83/100 comparable cells agree (44 exact, 39 within 1.0%, 17 off, 0 unpublished) |
| reconciliation_visible_to_engine | weight-engine-reconciliation | PASS | every R_k record confirmed before the next epoch buried (mempool peak 0 tx) |
| settlement_confirmed | allocation + reconciliation transfers | PASS | every settlement transfer and governance publish confirmed |
| weight_ranking | ESG+NumTx composite | FAIL | mean pairwise concordance 0.7950 over 20 epochs (min 0.80) |
| tau_coverage | sampled epochs | FAIL | unattributed transactions in 12 epoch(s): [(17, 2), (18, 2), (19, 2), (20, 8), (21, 1)] |
| membership_from_chain | weight-engine-membership | PASS | on-chain cluster sets match the configured topology (5 clusters x 10) |
| alloc_sums_to_alpha_theta | per epoch | PASS | 20/20 epochs pass |
| delay_sums_to_1000 | per epoch | PASS | 20/20 epochs pass |
| rho_in_unit_interval | per epoch | PASS | 20/20 epochs pass |
| balance_non_negative | per epoch | PASS | 20/20 epochs pass |
| resi_within_available | per epoch | PASS | 20/20 epochs pass |
| conformity_rate_range | all epochs x clusters | PASS | all 100 rows in [0,100]% |
| total_gain_monotonic | per cluster | PASS | monotonic across 20 epochs for all 5 clusters |
| alloc_equals_alpha_theta | network | PASS | sum A_k 2577.9995 vs alpha*Theta 2578.0000 (Theta=12890) -- an EQUALITY under the weight-share model, unlike the per-block fee tally it replaced |
| gas_returned_to_admin | ADMIN address | PASS | ADMIN balance delta 2502.5020 vs sum Resi read off chain 2502.5020 |
| feepool_paid_out | FEEPOOL address | PASS | FEEPOOL balance delta -2577.9995 vs -sum A_k -2577.9995 |
| gas_supply_conserved | all addresses | PASS | balances 2000000.0000 (minconf 1) / 2000000.0000 (minconf 0) vs issued supply 2000000.0000 -- delta 0.0000 / 0.0000 |
| giacenza_matches_chain | per cluster miner | PASS | balance delta - miner trading = B_k for all 5 clusters (sum B_k 75.4975) |
| proposer_share_tracks_p_k | wpoa selection | PASS | total L1 deviation between observed block share and mean p_k: 0.0931 over 120 blocks. REPORTED, not thresholded: the selector applies its own whale-compression at election time (weight_engine.h), so exact agreement is not expected |
| Invarianti per epoca (output/epoch_checks.csv): 100 controlli, 0 fallimenti |  |  |  |
| Epoch | Check | Esito | Dettaglio |
| — | tutti i controlli superati | PASS | alpha×Theta, somma Delay = 1000, rho in [0,1], B_k >= 0, R_k <= A_k + B_prev |