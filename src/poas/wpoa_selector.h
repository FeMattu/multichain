// src/poas/wpoa_selector.h
// Algoritmo di selezione pseudo-casuale pesata per wPoA.
//
// PROPRIETÀ FONDAMENTALE:
//   Dato lo stesso prevHash e la stessa tabella pesi, TUTTI i nodi
//   calcolano identicamente lo stesso vincitore — nessuna comunicazione
//   extra, nessun round di votazione, nessun fork accidentale.
//
// ALGORITMO:
//   Per ogni validatore i che soddisfa già il vincolo mining-diversity:
//     raw_i  = SHA256( prevHash || address_i )   // uint256, 32 byte
//     norm_i = low64(raw_i) / UINT64_MAX          // in [0, 1)
//     score_i = norm_i * weight_i
//   Vincitore = argmax(score_i)
//
// Include corretti per questa fork di MultiChain:
//   structs/hash.h    → CHash256   (NON "hash.h")
//   structs/uint256.h → uint256    (NON "uint256.h")
//   utils/util.h      → LogPrintf  (NON "util.h")

#ifndef POAS_WPOA_SELECTOR_H
#define POAS_WPOA_SELECTOR_H

#include <vector>
#include <string>
#include <algorithm>
#include <cmath>
#include <stdint.h>
#include <cstring>

#include "structs/uint256.h"      // uint256
#include "structs/hash.h"         // CHash256
#include "utils/util.h"           // LogPrintf
#include "poas/weight_registry.h" // WeightRegistry

struct ValidatorScore {
    std::string address;
    double      weight;
    double      score;     // norm(SHA256(prevHash||addr)) * weight

    // Operatore per std::max_element
    bool operator<(const ValidatorScore& o) const { return score < o.score; }
};

class WPoASelector {
public:
    // Calcola il validatore vincente per il blocco all'altezza corrente.
    //
    // @param validators  Lista di indirizzi Base58 che hanno il permesso
    //                    'mine' E soddisfano già il mining-diversity check
    //                    (calcolato a monte dal meccanismo nativo MultiChain).
    // @param prevHash    Hash del blocco precedente (noto e uguale per tutti).
    // @return            Indirizzo Base58 del vincitore; stringa vuota se
    //                    la lista è vuota (non dovrebbe mai accadere).
    static std::string selectWinner(
        const std::vector<std::string>& validators,
        const uint256& prevHash)
    {
        if (validators.empty()) return "";

        // Con un solo candidato idoneo non serve calcolare nulla
        if (validators.size() == 1) return validators[0];

        WeightRegistry& reg = WeightRegistry::getInstance();
        std::vector<ValidatorScore> scores;
        scores.reserve(validators.size());

        for (size_t i = 0; i < validators.size(); ++i) {
            const std::string& addr = validators[i];

            // SHA256( prevHash[32 byte] || addr[N byte] )
            // CHash256 è in structs/hash.h ed è SHA256d (double SHA256).
            // Usiamo SHA256 singolo via CSHA256 se vogliamo un giro solo,
            // ma CHash256 va benissimo per la selezione (è deterministico).
            unsigned char hashBuf[32];
            CHash256()
                .Write(prevHash.begin(), 32)
                .Write(reinterpret_cast<const unsigned char*>(addr.data()),
                       addr.size())
                .Finalize(hashBuf);

            // Prendiamo i primi 8 byte (little-endian) come uint64
            // per normalizzare in [0, 1) con buona precisione
            uint64_t low64 = 0;
            std::memcpy(&low64, hashBuf, sizeof(uint64_t));

            double norm  = static_cast<double>(low64) /
                           static_cast<double>(UINT64_MAX);
            double weight = reg.getWeight(addr);
            double score  = norm * weight;

            ValidatorScore vs;
            vs.address = addr;
            vs.weight  = weight;
            vs.score   = score;
            scores.push_back(vs);

            LogPrintf("wPoA: validator=%s weight=%.4f norm=%.8f score=%.8f\n",
                      addr, weight, norm, score);
        }

        // Seleziona il validatore con score massimo
        std::vector<ValidatorScore>::const_iterator winner =
            std::max_element(scores.begin(), scores.end());

        LogPrintf("wPoA: VINCITORE = %s (score=%.8f)\n",
                  winner->address, winner->score);
        return winner->address;
    }
};

#endif // POAS_WPOA_SELECTOR_H
