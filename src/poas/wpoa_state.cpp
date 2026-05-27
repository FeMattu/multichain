// src/poas/wpoa_state.cpp
// Variabili globali condivise tra miner/miner.cpp e protocol/multichainblock.cpp
// per il meccanismo wPoA.
//
// miner.cpp  → scrive g_wPoAEligibleMiners e g_wPoAPrevHash
//              prima di proporre ogni blocco.
// multichainblock.cpp → legge le stesse variabili in CheckBlockPermissions
//              per verificare che il blocco ricevuto venga dal vincitore atteso.

#include "poas/wpoa_state.h"

std::vector<std::string> g_wPoAEligibleMiners;
uint256                  g_wPoAPrevHash;
