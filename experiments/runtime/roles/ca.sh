#!/usr/bin/env bash
# CERTIFICATION AUTHORITY NODE.
#
# Publishes each miner's and each company's certified ESG score on
# weight-engine-esg. Scores are drawn uniformly from (0, 100) by a generator
# seeded with POESIA_RNG_SEED, so the same run replayed with the same seed
# produces the same scores.
#
# The CA role is carried by the custom high1 permission, delegated by the admin
# and revocable: being an administrator is NOT enough to certify (see
# src/wpoa/docs/weight-engine.md 6.4). An ESG score is an attestation of trust,
# not something a third party can verify cryptographically - restricting who
# may assert it is the only defence there is.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"

IP="$POESIA_IP"
TARGETS="${POESIA_MINERS:-} ${POESIA_COMPANIES:-}"
RNG_SEED="${POESIA_RNG_SEED:-1}"

# SPLITTING THE WORK BETWEEN SEVERAL CAs. An experiment may declare more than
# one; without a split each would certify the whole list and write the same ESG
# score N times to the stream. Each CA takes a slice of the targets by rotation
# (target index modulo the number of CAs).
#
# The counter i stays GLOBAL and walks every target, including the ones this CA
# skips: it seeds the score (srand(s+k)), so keeping it global makes a given
# host's ESG independent of how many CAs there are. The same run with one, two
# or three CAs produces the same scores.
CA_INDEX="${POESIA_CA_INDEX:-1}"
CA_COUNT="${POESIA_CA_COUNT:-1}"

wait_rpc "$IP" 900 || exit 1
wait_stream "$IP" weight-engine-esg 900 || exit 1

csvh esg_scores.csv "host,address,esg"

i=0
for h in $TARGETS; do
    i=$((i + 1))
    [ $(( (i - 1) % CA_COUNT )) -eq $(( CA_INDEX - 1 )) ] || continue
    addr="$(addr_of "$h")"
    if [ -z "$addr" ]; then
        log "WARNING: no address for $h, ESG skipped"
        continue
    fi
    # Uniform on (0, 100), endpoints excluded: Def. 6.1 requires ESG_i > 0, and
    # the positivity of the weight depends on it.
    score="$(awk -v s="$RNG_SEED" -v k="$i" 'BEGIN{srand(s+k); v=rand(); if(v<0.001)v=0.001; if(v>0.999)v=0.999; printf "%.2f", v*100}')"
    for attempt in 1 2 3 4 5; do
        if rpc_ok "$IP" weightsetesg "[\"$addr\",$score]"; then
            log "ESG certified: $h ($addr) = $score"
            csv esg_scores.csv "$h,$addr,$score"
            break
        fi
        log "attempt $attempt failed for $h: $(rpc_err "$IP" weightsetesg "[\"$addr\",$score]")"
        sleep 10
    done
done
log "ESG certification complete (CA $CA_INDEX of $CA_COUNT)"
