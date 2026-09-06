#!/usr/bin/env bash
# Preparazione NATIVA (fuori da Shadow) di params.dat e dei datadir.
#
# E' l'unico passo che gira sull'host reale, e per una ragione precisa:
# `multichain-util create` scrive solo params.dat, che non contiene alcun
# timestamp finche' la genesi non e' sigillata. Tutto il resto — genesi,
# permessi, stream, ESG, membership, GAS — avviene DENTRO la simulazione,
# perche' l'orologio di Shadow parte sempre dal 2000-01-01 e non e'
# configurabile: un datadir cotto nativamente porterebbe blocchi datati oggi,
# che il nodo rifiuterebbe con "block timestamp too far in the future".
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"

# --params-file sceglie l'ASSE dei parametri di catena: e' il file referenziato
# da blockchain_params_file nel descrittore di simulazione. Va risolto prima di
# ogni altra opzione, perche' i default di TBT/SETUP/EPOCHLEN vengono da li'.
# Senza l'opzione resta config/params.overrides, il default storico.
PARAMS_FILE="$ROOT/config/params.overrides"
for i in $(seq 1 $#); do
    if [ "${!i}" = "--params-file" ]; then
        j=$((i + 1)); PARAMS_FILE="${!j}"
    fi
done
[ -f "$PARAMS_FILE" ] || { echo "ERRORE: file di parametri non trovato: $PARAMS_FILE" >&2; exit 2; }
. "$PARAMS_FILE"

RUN=""; CHAIN=""; TBT="$TARGET_BLOCK_TIME"; SETUP="$SETUP_FIRST_BLOCKS"; HOSTS=""
EPOCHLEN="$WEIGHT_EPOCH_LENGTH"; ADMIN="admin"
while [ $# -gt 0 ]; do
    case "$1" in
        --run)    RUN="$2"; shift 2 ;;
        --chain)  CHAIN="$2"; shift 2 ;;
        --tbt)    TBT="$2"; shift 2 ;;
        --setup)  SETUP="$2"; shift 2 ;;
        --epochlen) EPOCHLEN="$2"; shift 2 ;;
        --hosts)  HOSTS="$2"; shift 2 ;;
        --admin)  ADMIN="$2"; shift 2 ;;
        --params-file) shift 2 ;;   # gia' consumato sopra
        *) echo "argomento sconosciuto: $1" >&2; exit 2 ;;
    esac
done
[ -n "$RUN" ] && [ -n "$CHAIN" ] && [ -n "$HOSTS" ] || { echo "uso: --run DIR --chain NAME --hosts 'h1 h2 ...' [--params-file FILE] [--admin HOST]" >&2; exit 2; }

# I file di config/blockchain/ possono lasciare SETUP_FIRST_BLOCKS='auto': il
# valore lo calcola gen_simulation.py e arriva qui via --setup. Se nessuno lo
# ha risolto, il sed piu' sotto scriverebbe la stringa 'auto' in params.dat.
case "$SETUP" in
    ''|*[!0-9]*)
        echo "ERRORE: setup-first-blocks non risolto ('$SETUP')." >&2
        echo "       Passare --setup <n>, oppure impostare SETUP_FIRST_BLOCKS a un intero in $PARAMS_FILE." >&2
        exit 2 ;;
esac

BINDIR="${BINDIR:-$(cd "$ROOT/../src" && pwd)}"
TREASURY=""
[ -f "$ROOT/config/treasury.json" ] && \
    TREASURY="$(grep -oP '"address"\s*:\s*"\K[^"]+' "$ROOT/config/treasury.json")"

ADMIN_DATADIR="$RUN/data/$ADMIN"
mkdir -p "$ADMIN_DATADIR"

# -enablewpoa e' il master: accende weights + selection + VRF + RANDAO +
# sortition in un colpo solo. I flag numerici e il weight engine si passano a
# parte. Finiscono tutti in params.dat, quindi sono ereditati dai nodi che si
# uniscono e concorrono all'hash del file: nessun nodo puo' divergere.
"$BINDIR/multichain-util" create "$CHAIN" -datadir="$ADMIN_DATADIR" \
    -enablewpoa=1 \
    -wpoasortitiondelta="$WPOA_SORTITION_DELTA" \
    -wpoasortitionlambda="$WPOA_SORTITION_LAMBDA" \
    -wpoarandaolookback="$WPOA_RANDAO_LOOKBACK" \
    -dumpfunction="$WPOA_DUMPFUNCTION" \
    -enablewpoamalus="$ENABLE_WPOA_MALUS" \
    -enableweightengine=1 \
    -weightepochlength="$EPOCHLEN" \
    -weightkappa="$WEIGHT_KAPPA" \
    -weightalpha="$WEIGHT_ALPHA" \
    -weightlambda="$WEIGHT_LAMBDA" \
    ${TREASURY:+-weighttreasuryaddress="$TREASURY"} \
    > "$RUN/prepare_params.log" 2>&1

P="$ADMIN_DATADIR/$CHAIN/params.dat"
[ -f "$P" ] || { echo "ERRORE: params.dat non generato (vedi $RUN/prepare_params.log)" >&2; exit 1; }

set_param() {   # set_param <nome> <valore>
    sed -i -E "s|^($1[[:space:]]*=[[:space:]]*)[^[:space:]#]+|\1$2|" "$P"
}

# --- catena ---
set_param "target-block-time"       "$TBT"
set_param "setup-first-blocks"      "$SETUP"
set_param "mine-empty-rounds"       "$MINE_EMPTY_ROUNDS"
set_param "mining-diversity"        "$MINING_DIVERSITY"
# --- spazio degli indirizzi pinnato (rende riusabile l'indirizzo di treasury) ---
set_param "address-pubkeyhash-version" "$ADDRESS_PUBKEYHASH_VERSION"
set_param "address-scripthash-version" "$ADDRESS_SCRIPTHASH_VERSION"
set_param "private-key-version"        "$PRIVATE_KEY_VERSION"
set_param "address-checksum-value"     "$ADDRESS_CHECKSUM_VALUE"
# --- economia del GAS ---
set_param "native-currency-multiple" "$NATIVE_CURRENCY_MULTIPLE"
set_param "first-block-reward"       "$FIRST_BLOCK_REWARD"
set_param "initial-block-reward"     "$INITIAL_BLOCK_REWARD"
set_param "minimum-relay-fee"        "$MINIMUM_RELAY_FEE"

# multichain.conf per ogni nodo: credenziali RPC fisse (i role script parlano
# JSON-RPC via curl) e RPC raggiungibile dagli altri host della simulazione.
for h in $HOSTS; do
    mkdir -p "$RUN/data/$h/$CHAIN"
    cat > "$RUN/data/$h/$CHAIN/multichain.conf" <<CONF
rpcuser=${POESIA_RPCUSER:-poesia}
rpcpassword=${POESIA_RPCPASS:-poesiarpc}
rpcallowip=0.0.0.0/0
# maxtxfee: il default del wallet e' 0.1 unita' di valuta nativa. Con
# minimum-relay-fee = 0.2 GAS/1000 byte, ogni transazione oltre i ~500 byte
# richiederebbe una fee superiore a quel tetto, e CreateTransaction la
# rifiuterebbe con "Transaction too large for fee policy" (wallet.cpp:3266,
# walletcoins.cpp:2465) — cosa che colpisce le publish su stream, non le send.
# Va alzato coerentemente con la fee scelta, o nessun record verrebbe pubblicato.
maxtxfee=${POESIA_MAXTXFEE:-10.0}
CONF
done

echo "[prepare_params] catena '$CHAIN' pronta"
echo "[prepare_params]   parametri         = $PARAMS_FILE (dumping $WPOA_DUMPFUNCTION)"
echo "[prepare_params]   target-block-time = $TBT s, setup-first-blocks = $SETUP, epoca = $EPOCHLEN blocchi"
echo "[prepare_params]   treasury          = ${TREASURY:-<non impostato: R_k = 0>}"
grep -E '^(enable-wpoa|enable-weight-engine|weight-epoch-length|wpoa-sortition-lambda|wpoa-sortition-delta|target-block-time|first-block-reward|minimum-relay-fee|weight-treasury-address) ' "$P" | sed 's/^/[prepare_params]   /'
