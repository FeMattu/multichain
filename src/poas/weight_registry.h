// src/poas/weight_registry.h
// Registro pesi per PoAS (Proof of Authority with Stake)
// Implementazione semi-statica: i pesi vengono letti da weights.json
// nella datadir del nodo (es. ~/.multichain/<chain-name>/weights.json).
//
// Formato weights.json atteso:
//   {"1AdrXXX...": 3.0, "1AdrYYY...": 1.5}
//
// Include corretti per questa fork di MultiChain:
//   utils/util.h  → GetDataDir(), LogPrintf()
//   (NON "util.h" — in questo codebase gli header stanno in sottocartelle)

#ifndef POAS_WEIGHT_REGISTRY_H
#define POAS_WEIGHT_REGISTRY_H

#include <string>
#include <map>
#include <fstream>
#include <sstream>

#include <boost/filesystem.hpp>
#include <boost/thread/mutex.hpp>
#include <boost/thread/lock_guard.hpp>

#include "utils/util.h"   // GetDataDir(), LogPrintf()

class WeightRegistry {
public:
    // Singleton thread-safe (costruito alla prima chiamata)
    static WeightRegistry& getInstance() {
        static WeightRegistry instance;
        return instance;
    }

    // Carica i pesi da <datadir>/weights.json.
    // Chiamare una volta all'avvio, in AppInit2() dentro core/init.cpp.
    // Ritorna true se il file esiste ed è stato letto.
    bool loadFromFile() {
        boost::lock_guard<boost::mutex> lock(mtx_);
        boost::filesystem::path path = GetDataDir() / "weights.json";

        if (!boost::filesystem::exists(path)) {
            LogPrintf("wPoA: weights.json non trovato in %s — tutti i pesi = 1.0\n",
                      path.string());
            return false;
        }

        std::ifstream file(path.string());
        if (!file.is_open()) {
            LogPrintf("wPoA: impossibile aprire weights.json\n");
            return false;
        }

        std::string content((std::istreambuf_iterator<char>(file)),
                             std::istreambuf_iterator<char>());

        // Parser JSON minimale senza dipendenze esterne.
        // MultiChain include già univalue (src/univalue/), ma per semplicità
        // usiamo parsing manuale sul formato { "addr": num, ... }
        weights_.clear();
        std::string::size_type pos = 0;
        while ((pos = content.find('"', pos)) != std::string::npos) {
            std::string::size_type addr_start = pos + 1;
            std::string::size_type addr_end   = content.find('"', addr_start);
            if (addr_end == std::string::npos) break;

            std::string addr = content.substr(addr_start, addr_end - addr_start);
            if (addr.empty()) { pos = addr_end + 1; continue; }

            std::string::size_type colon    = content.find(':', addr_end);
            if (colon == std::string::npos) break;
            std::string::size_type val_start = content.find_first_not_of(" \t\r\n", colon + 1);
            if (val_start == std::string::npos) break;
            std::string::size_type val_end   = content.find_first_of(",}", val_start);
            if (val_end == std::string::npos) break;

            double w = 1.0;
            try {
                w = std::stod(content.substr(val_start, val_end - val_start));
            } catch (...) {
                LogPrintf("wPoA: peso non valido per %s — uso 1.0\n", addr);
            }

            weights_[addr] = (w > 0.0) ? w : 1.0;
            LogPrintf("wPoA: caricato peso %.2f per %s\n", w, addr);
            pos = val_end;
        }

        LogPrintf("wPoA: caricati %u pesi da %s\n",
                  (unsigned)weights_.size(), path.string());
        return true;
    }

    // Restituisce il peso di un indirizzo Base58 (default 1.0 se assente).
    double getWeight(const std::string& address) const {
        boost::lock_guard<boost::mutex> lock(mtx_);
        std::map<std::string, double>::const_iterator it = weights_.find(address);
        return (it != weights_.end()) ? it->second : 1.0;
    }

    // Imposta un peso a runtime (utile per test senza riavviare il nodo).
    void setWeight(const std::string& address, double weight) {
        boost::lock_guard<boost::mutex> lock(mtx_);
        weights_[address] = (weight > 0.0) ? weight : 1.0;
        LogPrintf("wPoA: impostato peso runtime %.2f per %s\n", weight, address);
    }

private:
    WeightRegistry() {}
    WeightRegistry(const WeightRegistry&);
    WeightRegistry& operator=(const WeightRegistry&);

    mutable boost::mutex mtx_;
    std::map<std::string, double> weights_;
};

#endif // POAS_WEIGHT_REGISTRY_H
