#!/usr/bin/env bash
# Genera UNA VOLTA la coppia di chiavi del treasury (il "conto di
# riconciliazione" di Apuana SB) e la salva in config/treasury.json.
#
# PERCHE' SERVE QUESTA MACCHINERIA
# --------------------------------
# `weight-treasury-address` e' un parametro di catena hash-enforced: va scritto
# in params.dat PRIMA della genesi. Ma l'indirizzo dell'admin nasce CON la
# genesi -> dipendenza circolare.
#
# La si rompe fissando lo spazio degli indirizzi: address-pubkeyhash-version,
# address-scripthash-version, private-key-version e address-checksum-value sono
# normalmente generati a caso per ogni catena, ma sono editabili in params.dat.
# Pinnandoli a costanti, un indirizzo generato su una catena qualsiasi resta
# valido su ogni altra catena con gli stessi valori. Generiamo quindi la coppia
# su una catena usa-e-getta e la riusiamo su tutti e quattro i livelli.
#
# La chiave privata viene poi importata come WATCH-ONLY nel wallet dell'admin
# (importaddress, non importprivkey): l'admin vede il saldo riconciliato senza
# che quei fondi finiscano nel suo saldo spendibile, che serve al refill GAS.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
. "$ROOT/config/params.overrides"

BINDIR="${BINDIR:-$(cd "$ROOT/../src" && pwd)}"
OUT="$ROOT/config/treasury.json"

if [ -f "$OUT" ] && [ "${FORCE:-0}" != "1" ]; then
    echo "[treasury] gia' presente: $OUT (FORCE=1 per rigenerarlo)"
    exit 0
fi

TMP="$(mktemp -d "${TMPDIR:-/tmp}/wpoa_treasury.XXXXXX")"
trap 'rm -rf "$TMP"' EXIT
CHAIN="tsygen"
PORT=$(( 30000 + RANDOM % 20000 )); RPC=$(( PORT + 1 ))

"$BINDIR/multichain-util" create "$CHAIN" -datadir="$TMP" >/dev/null
P="$TMP/$CHAIN/params.dat"
sed -i -E \
  -e "s/^(address-pubkeyhash-version[[:space:]]*=[[:space:]]*)[0-9a-f]+/\1$ADDRESS_PUBKEYHASH_VERSION/" \
  -e "s/^(address-scripthash-version[[:space:]]*=[[:space:]]*)[0-9a-f]+/\1$ADDRESS_SCRIPTHASH_VERSION/" \
  -e "s/^(private-key-version[[:space:]]*=[[:space:]]*)[0-9a-f]+/\1$PRIVATE_KEY_VERSION/" \
  -e "s/^(address-checksum-value[[:space:]]*=[[:space:]]*)[0-9a-f]+/\1$ADDRESS_CHECKSUM_VALUE/" \
  "$P"

"$BINDIR/multichaind" "$CHAIN" -datadir="$TMP" -port=$PORT -rpcport=$RPC -daemon >/dev/null 2>&1
for _ in $(seq 1 30); do
    "$BINDIR/multichain-cli" "$CHAIN" -datadir="$TMP" -rpcport=$RPC getinfo >/dev/null 2>&1 && break
    sleep 1
done

"$BINDIR/multichain-cli" "$CHAIN" -datadir="$TMP" -rpcport=$RPC createkeypairs 1 2>/dev/null \
    | sed -n '/^\[/,$p' > "$TMP/kp.json"
"$BINDIR/multichain-cli" "$CHAIN" -datadir="$TMP" -rpcport=$RPC stop >/dev/null 2>&1 || true
sleep 2

python3 - "$OUT" "$TMP/kp.json" "$ADDRESS_PUBKEYHASH_VERSION" "$ADDRESS_CHECKSUM_VALUE" <<'PY'
import json, sys
out, kpfile, pkh, cks = sys.argv[1:5]
kp = json.load(open(kpfile))[0]
json.dump({
    "address": kp["address"],
    "privkey": kp["privkey"],
    "pubkey":  kp["pubkey"],
    "address_pubkeyhash_version": pkh,
    "address_checksum_value": cks,
    "note": "indirizzo di treasury (riconciliazione R_k). Valido su ogni catena "
            "che pinna le stesse versioni di indirizzo. Rigenerare con FORCE=1.",
}, open(out, "w"), indent=2)
print("[treasury] indirizzo: " + kp["address"])
PY
echo "[treasury] scritto in $OUT"
