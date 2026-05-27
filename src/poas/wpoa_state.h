// src/poas/wpoa_state.h
// Dichiarazioni extern per le variabili globali condivise wPoA.
// Includere in miner/miner.cpp e protocol/multichainblock.cpp.

#ifndef POAS_WPOA_STATE_H
#define POAS_WPOA_STATE_H

#include <vector>
#include <string>
#include "structs/uint256.h"

// Lista degli indirizzi Base58 eleggibili per il blocco corrente.
// Aggiornata da miner.cpp, letta da multichainblock.cpp.
extern std::vector<std::string> g_wPoAEligibleMiners;

// Hash del blocco precedente al momento in cui g_wPoAEligibleMiners
// è stato calcolato. Serve per invalidare la cache se la chain avanza.
extern uint256 g_wPoAPrevHash;

#endif // POAS_WPOA_STATE_H
