#!/usr/bin/env bash
# PHASE ONE OF THE PERMISSIONED JOIN (every node except the admin).
#
# On a permissioned chain a node's first start does not enter the network: it
# creates the data directory and the wallet, prints its own address and exits,
# waiting for the administrator to grant it permissions. This captures that
# address into runtime/shared/<host>.addr, from where admin.sh reads it to
# issue the grants. PHASE TWO - the real join - is a second multichaind
# process started later in the schedule.
#
# No 'set -e': a node that prints its address on stderr, or that exits
# non-zero after printing it, has still done its job. The address file is the
# contract, and it is checked explicitly below.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

: "${POESIA_DAEMON:?POESIA_DAEMON is not set}"
: "${POESIA_SEED:?POESIA_SEED is not set}"

DATADIR="$POESIA_RUN/runtime/data/$POESIA_HOST"
OUT="$SHARED/$POESIA_HOST.addr"
LOGDIR="$POESIA_RUN/logs/$POESIA_HOST"
mkdir -p "$DATADIR" "$LOGDIR"

log "first launch (address collection) towards $POESIA_SEED"
"$POESIA_DAEMON" "$POESIA_SEED" -datadir="$DATADIR" \
    -port="$POESIA_P2PPORT" -rpcport="$POESIA_RPCPORT" \
    -externalip="$POESIA_IP" -dnsseed=0 -discover=0 -shortoutput \
    > "$LOGDIR/first-launch.log" 2>&1

# -shortoutput prints the wallet address alone when permissions are needed.
grep -oE '[A-Za-z0-9]{30,40}' "$LOGDIR/first-launch.log" | tail -n1 > "$OUT"

if [ -s "$OUT" ]; then
    log "address published: $(cat "$OUT")"
else
    log "ERROR: no address extracted. Daemon output follows:"
    cat "$LOGDIR/first-launch.log"
    exit 1
fi
