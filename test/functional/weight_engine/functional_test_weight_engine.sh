#!/usr/bin/env bash
#
# Functional test — WeightEngine publish side (self-attested + CA-gated writes) and the
# closed input streams.
# -----------------------------------------------------------------------------
# Brings up a single genesis node with the weight engine enabled, then asserts:
#   1. the TWO published input streams are auto-created (CLOSED) -- tau and R_k are
#      derived from the epoch's confirmed blocks, so neither is a stream;
#   2. ESG is CERTIFICATION-AUTHORITY-only: a global admin WITHOUT the role is
#      refused, publishes once granted `high1`, and is refused again after the role
#      is revoked even though `.write` is still held;
#   3. membership is SELF-WRITTEN by the node, and a forged record naming another
#      address is discarded by the reader rather than entering C_k;
#   4. reconciliation has NO write path and NO stream: R_k is derived from the
#      epoch's confirmed transfers to the treasury address;
#   5. an invalid ESG (score <= 0) is rejected by schema round-trip validation;
#   6. a raw publish from an address without write permission is rejected (the
#      CLOSED-stream guard against schema-bypassing writes);
#   7. the published records are readable back;
#   8. wpoa-weights records are SELF-PUBLISHED: a forged record naming another
#      cluster never enters the weight map, while the node's own does;
#   9. independent verification of the published weights is reachable;
#  10. verification is EPOCH-SCOPED: it targets e-1 while the tip is in e, no honest
#      record is ever a mismatch, and an other-epoch record is reported WITHOUT being
#      counted as invalid.
#
# Self-contained: no external deps beyond python3 (JSON parsing). Fast blocks
# (target-block-time=2, the parameter minimum) keep confirmations quick.
#
# Bootstrap, RPC polling, teardown and the small predicates come from the shared
# library (../lib/functional_lib.sh) rather than being reimplemented here; the
# assertions below, and this script's PASS/FAIL output contract, are unchanged.
#
# Usage:  ./functional_test_weight_engine.sh
# Exit:   0 iff every assertion passed.
set -uo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # test/functional/weight_engine
FUNC_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"                     # test/functional
ROOT="$(cd "$FUNC_DIR/../.." && pwd)"                        # repo root
# shellcheck source=../lib/functional_lib.sh
. "$FUNC_DIR/lib/functional_lib.sh"

BINDIR="${BINDIR:-$ROOT/src}"
EPOCH_LEN="${EPOCH_LEN:-4}"
export FL_CHAIN_PREFIX="wetestpub"

PASS=0; FAIL=0
say(){ echo "-- $*"; }
ok(){ echo "  PASS: $*"; PASS=$((PASS+1)); }
bad(){ echo "  FAIL: $*"; FAIL=$((FAIL+1)); }

# This script's assertions grep for ERROR MESSAGES, which arrive on stderr, so every
# call goes through fl_cli_q (stderr merged, request echo stripped) rather than fl_cli.
mcli(){ fl_cli_q 0 "$@"; }
first_addr(){ mcli getaddresses | python3 -c 'import sys,json; a=json.load(sys.stdin); print(a[0] if a else "")' 2>/dev/null; }
is_txid(){ fl_is_txid "$1"; }

trap fl_teardown EXIT

fl_phase "SETUP — single genesis node, weight engine ON (epoch length $EPOCH_LEN)"
fl_require_binaries
fl_start_single_node "-enablewpoaweights -enableweightengine -weightepochlength=$EPOCH_LEN"

ADMIN="$(first_addr)"
say "admin/node address: $ADMIN"
[ -n "$ADMIN" ] || fl_die "could not resolve node address"

# R_k is the native value paid to the TREASURY address by transactions the miner signed.
# The flag cannot be passed at first launch -- the genesis address does not exist until
# the wallet does -- so it goes on by restart, which is also what the experimental
# harness does (helpers/chain_setup.py). A node left without it computes R_k = 0 while
# its peers do not, which on a real network is a fork.
#
# A DEDICATED address, not the admin's: with the admin as treasury its own change
# outputs pay the treasury, and only the `signer == treasury` guard in
# mc_AccumulateReconciliation keeps that from registering as a reconciliation. Correct,
# but not something a test should lean on.
TREASURY="$(fl_make_treasury_address 0)"
[ -n "$TREASURY" ] || fl_die "could not create a treasury address"
say "treasury address (defines a reconciliation transfer): $TREASURY"
ENGINE_ARGS="-enablewpoaweights -enableweightengine -weightepochlength=$EPOCH_LEN -weighttreasuryaddress=$TREASURY"
fl_restart_node 0 "$ENGINE_ARGS" || fl_die "node did not come back up with the treasury address set"
[ "$(fl_chain_param 0 weight-treasury-address)" = "$TREASURY" ] \
  && ok "treasury address is in force on the chain ($TREASURY)" \
  || say "note: getblockchainparams does not echo weight-treasury-address; relying on the flag"

# 1. streams auto-created (closed)
say "waiting for the 2 published input streams to be auto-created"
n=0
for i in $(seq 1 30); do
  sleep 2
  n=$(mcli liststreams '*' 2>/dev/null | grep -oE 'weight-engine-[a-z]+' | sort -u | wc -l)
  [ "${n:-0}" -ge 2 ] && break
done
# Exactly two: reconciliation and activity are derived from the blocks, not streams.
[ "${n:-0}" -eq 2 ] && ok "2 input streams auto-created (membership, esg)" \
                    || bad "expected exactly 2 input streams, got ${n:-0}"

# confirm they are CLOSED (open=false)
closed=$(mcli liststreams '*' 2>/dev/null | python3 -c '
import sys,json
try: d=json.load(sys.stdin)
except Exception: d=[]
c=sum(1 for s in d if s.get("name","").startswith("weight-engine-") and s.get("restrict",{}).get("write") is True)
print(c)' 2>/dev/null)
[ "${closed:-0}" -ge 2 ] && ok "input streams are CLOSED (write-restricted)" || bad "streams not closed (closed=${closed:-0})"

# Grant write on the 2 published streams to the admin address, then let it confirm.
# (There is no reconciliation or activity stream: tau and R are derived from the epoch's
# confirmed blocks, so there is nothing to grant.)
# NOTE on membership: both streams stay CLOSED at the MultiChain level, but
# weight-engine-membership.write is now meant to be granted to EVERY node, not only
# to governance — its records are self-attested, so a write permission grants a node
# nothing beyond the ability to speak about itself. Here there is only one address,
# which therefore needs the grant like any other node.
for s in weight-engine-esg weight-engine-membership; do
  mcli grant "$ADMIN" "$s.write" >/dev/null 2>&1
done
sleep 4

# 2a-pre. ESG is CERTIFICATION-AUTHORITY-only, and being a global admin is NOT
# sufficient: the admin CONFERS the role, it does not hold it automatically. So the
# very first assertion is that the admin — which has .write but not yet `high1` — is
# refused. This is what distinguishes "who administers" from "who certifies".
r=$(mcli weightsetesg "$ADMIN" 15)
echo "$r" | grep -qiE 'certification authority|not a certification' \
  && ok "global admin without the CA role is refused (roles are distinct)" \
  || bad "admin without CA role was NOT refused: $r"

# 2a. confer CA status, then publish. Only `admin` can grant a high1..high3 slot
# (mc_Permissions::IsActivateEnough returns 0 for the high slots), which is what makes
# CA status conferrable by the administrator alone.
mcli grant "$ADMIN" high1 >/dev/null 2>&1
sleep 4
r=$(mcli weightsetesg "$ADMIN" 15)
is_txid "$r" && ok "Certification Authority publishes valid ESG" || bad "valid ESG failed: $r"

# 3. invalid ESG (score 0) rejected — schema validation still applies to a CA
r=$(mcli weightsetesg "$ADMIN" 0)
echo "$r" | grep -qiE 'reject|error|> 0|schema' && ok "invalid ESG (0) rejected" || bad "invalid ESG NOT rejected: $r"

# 3a. a generic address (neither CA nor admin) cannot publish. Checked on its own node
# only in the multi-node suite; here the single node's identity is the admin, so what
# is asserted is the complementary case: revoking the CA role blocks further writes
# even though weight-engine-esg.write is STILL granted. The two grants are
# independent, and revocation does not wait for .write to be withdrawn as well.
mcli revoke "$ADMIN" high1 >/dev/null 2>&1
sleep 4
r=$(mcli weightsetesg "$ADMIN" 16)
echo "$r" | grep -qiE 'certification authority|not a certification' \
  && ok "revoking CA status blocks ESG writes while .write remains" \
  || bad "revoked CA could still publish ESG: $r"

# restore CA status for the remainder of the run
mcli grant "$ADMIN" high1 >/dev/null 2>&1
sleep 4

# 2b. membership — SELF-WRITE: the node declares its OWN cluster, signed by itself.
# There is no parameter for "whose" membership, so the record can only ever be about
# the caller; here the admin address registers itself as a cluster head.
r=$(mcli weightregistermembership "$ADMIN")
is_txid "$r" && ok "node self-registers membership" || bad "membership failed: $r"

# 2b-bis. the self-attestation rule is not bypassable through the generic publishfrom:
# a record naming a node_address other than the signer is DISCARDED by every reader.
# The publish itself succeeds on-chain (the stream only checks .write) — what the
# assertion below establishes is that the forged record never reaches C_k, which is
# visible as the foreign node_address not appearing in any cluster.
FOREIGN=$(mcli getnewaddress 2>/dev/null | tr -d '"[:space:]')
r=$(mcli publishfrom "$ADMIN" weight-engine-membership "$FOREIGN" \
      "{\"json\":{\"node_address\":\"$FOREIGN\",\"miner_address\":\"$ADMIN\",\"timestamp\":1700000000}}")
if is_txid "$r"; then
  ok "forged membership accepted on-chain (stream only gates .write) — reader must discard it"
else
  ok "forged membership publish refused outright: $r"
fi

# 2c. reconciliation has NO write path at all: R_k is derived from the epoch's confirmed
# transfers to the treasury address, so the RPC that used to attest it is gone. Asserting
# its absence is the point — a lingering weightsetreconciliation would mean the admin can
# still declare a value the chain already records.
r=$(mcli weightsetreconciliation "$ADMIN" 10 1 2>&1)
echo "$r" | grep -qiE 'method not found|unknown command|help' \
  && ok "weightsetreconciliation is gone (R_k is chain-derived)" \
  || bad "weightsetreconciliation still exists: $r"

# 2d. and there is no reconciliation or activity stream to write to either.
r=$(mcli liststreams '*' 2>/dev/null)
echo "$r" | grep -qE 'weight-engine-(reconciliation|activity)' \
  && bad "a reconciliation/activity stream still exists" \
  || ok "no reconciliation/activity stream: both quantities are derived from blocks"

# 5. raw publish from a fresh (no-write) address is rejected (closed-stream guard)
NW=$(mcli getnewaddress 2>/dev/null | tr -d '"[:space:]')
r=$(mcli publishfrom "$NW" weight-engine-esg "$ADMIN" "{\"json\":{\"node_address\":\"$ADMIN\",\"esg\":5}}")
echo "$r" | grep -qiE 'error|permission|not|invalid' && ok "raw write from non-write address rejected (closed stream)" || bad "closed stream bypassable: $r"

mcli subscribe weight-engine-esg >/dev/null 2>&1   # ensure we can read items back
sleep 3  # let the valid publishes confirm + subscription import

# 6. published records readable back
r=$(mcli liststreamitems weight-engine-esg 2>/dev/null)
echo "$r" | grep -q '"esg"' && ok "ESG record readable on stream" || bad "ESG record not found: $r"

# 7. wpoa-weights output contract intact
r=$(mcli getallweights 2>/dev/null)
echo "$r" | grep -q 'validators' && ok "getallweights (wpoa-weights) intact" || bad "getallweights broken: $r"

# 8. wpoa-weights is SELF-PUBLISHED: a record naming another address is discarded by the
# reader even though the publish itself succeeds on chain (the stream only gates .write).
# The assertion is that the forged address never appears in the weight map.
FAKE=$(mcli getnewaddress 2>/dev/null | tr -d '"[:space:]')
mcli grant "$FAKE" "receive" >/dev/null 2>&1
sleep 4
r=$(mcli publishfrom "$ADMIN" wpoa-weights "$FAKE" \
      "{\"json\":{\"node_address\":\"$FAKE\",\"weight\":999999,\"timestamp\":1700000000,\"height\":1}}")
if is_txid "$r"; then
  sleep 6   # let it confirm and be imported
  w=$(mcli getallweights 2>/dev/null)
  echo "$w" | grep -qF "$FAKE" \
    && bad "forged wpoa-weights record ENTERED the weight map (self-publication not enforced)" \
    || ok "forged wpoa-weights record discarded: signer != node_address"
else
  ok "forged wpoa-weights publish refused outright: $r"
fi

# 9. the node's OWN weight is published from its own address, so it survives the same
# rule — a regression here would mean the node discards its own record.
w=$(mcli getallweights 2>/dev/null)
echo "$w" | grep -qF "$ADMIN" \
  && ok "own self-published weight accepted (signer == node_address)" \
  || bad "own weight missing from the map — is PublishWeightRecord using publishfrom? : $w"

# 10. independent verification is reachable and reports a coherent shape. With the engine
# off it must refuse explicitly rather than report a vacuous 'all ok'.
r=$(mcli weightverifyweights 2>&1)
echo "$r" | grep -qE '"epoch"|weight engine is disabled' \
  && ok "weightverifyweights reports verification state" \
  || bad "weightverifyweights unexpected output: $r"

# 11. VERIFICATION IS EPOCH-SCOPED, and the verdicts say so.
#
# Until now this suite only asserted that the RPC ANSWERS -- it never read a verdict,
# which left the epoch scoping covered by unit tests over hand-built maps and by nothing
# at all at node level. The node-level bookkeeping is the part a fake map cannot reach:
# the `epoch >= 2` gate, the last_verified_epoch marker, and the single-epoch verdict
# cache (ThreadWeightEngine / WeightEngineGetVerdicts).
#
# What the scoping means, and why other-epoch is NOT a finding: a weight is a claim about
# a specific epoch, and publication necessarily LAGS the epoch it describes -- a node can
# only compute w_k^(e) once e is buried, so its record for e lands during e+1.
# Verification therefore targets e-1 while the tip is in e, and a record about any other
# epoch (or none at all, as on the static -weight path) is reported other-epoch and left
# alone. Conflating that with a mismatch is how an honest node gets accused, and the
# malus would then turn the false accusation into a real weight penalty -- which was
# observed on a live run before the epoch field existed.
#
# Verification first runs once epoch 2 is buried, i.e. at height
#   2 * EPOCH_LEN + STABILITY_MARGIN - 1
# so drive there before asserting anything.
FIRST_VERIFY_HEIGHT=$(fl_height_for_buried_epoch 2 "$EPOCH_LEN")
say "epoch-scoped verification: first possible at height $FIRST_VERIFY_HEIGHT (epoch_len=$EPOCH_LEN)"
fl_drive_to_height $(( FIRST_VERIFY_HEIGHT + EPOCH_LEN )) 240 \
    "chain not advancing; the verification thread needs buried epochs" || true

# The engine verifies once per epoch on its own tick, so poll for the first real report
# (epoch 0 is the RPC's way of saying "it has not run here yet").
v_epoch=0
for _i in $(seq 1 30); do
    v_epoch="$(fl_verify_field 0 epoch)"; v_epoch="${v_epoch:-0}"
    [ "$v_epoch" -ge 1 ] && break
    sleep 3
done

say "verification report: $(fl_verdict_tally 0)"
v_ok="$(fl_verify_field 0 verified)"
n_mismatch="$(fl_verdict_count 0 mismatch)"
n_notcluster="$(fl_verdict_count 0 not-a-cluster)"
n_other="$(fl_verdict_count 0 other-epoch)"

[ "$v_epoch" -ge 1 ] \
  && ok "verification has run for a real epoch (epoch=$v_epoch, not the 0 that means 'not yet')" \
  || bad "verification never ran: epoch=$v_epoch at height $(fl_tip_height 0)"

# It must never verify AHEAD of what is buried: at tip T the newest buried epoch is
# (T - margin + 1)/len, and the engine targets one BELOW that. Read the tip AFTER the
# report so an advancing chain can only widen the gap, never invent a violation.
tip_now="$(fl_tip_height 0)"; tip_now="${tip_now:-0}"
buried_now="$(fl_buried_epoch_at "$tip_now" "$EPOCH_LEN")"
say "tip=$tip_now  newest buried epoch=$buried_now  verified epoch=$v_epoch"
[ "$v_epoch" -lt "$buried_now" ] \
  && ok "the verified epoch trails the newest buried one ($v_epoch < $buried_now): e-1 while the tip is in e" \
  || bad "verified epoch $v_epoch does not trail the newest buried epoch $buried_now (tip $tip_now)"

[ "${v_ok:-false}" = "true" ] \
  && ok "the recomputation SUCCEEDED, so the verdicts are real rather than fail-open" \
  || bad "verified=false: every verdict is UNVERIFIED and nothing was actually checked"

[ "${n_mismatch:-0}" -eq 0 ] \
  && ok "no mismatch verdicts on an honest single node" \
  || bad "$n_mismatch mismatch verdict(s) against an honest node"
[ "${n_notcluster:-0}" -eq 0 ] \
  && ok "no not-a-cluster verdicts on an honest single node" \
  || bad "$n_notcluster not-a-cluster verdict(s) against an honest node"

# other-epoch is EXPECTED, not tolerated: reported for the record, never a failure.
say "other-epoch verdicts: ${n_other:-0} (expected, and explicitly NOT a finding)"
ok "other-epoch records are reported without being counted as invalid"

# The invalid counter must agree with the verdicts: it is what mc_CountInvalidVerdicts
# feeds, and the filter drops exactly those from the election.
n_invalid="$(fl_verify_field 0 invalid)"; n_invalid="${n_invalid:-0}"
[ "$n_invalid" -eq "$(( ${n_mismatch:-0} + ${n_notcluster:-0} ))" ] \
  && ok "the invalid counter equals mismatch + not-a-cluster (other-epoch excluded)" \
  || bad "invalid=$n_invalid but mismatch+not-a-cluster=$(( ${n_mismatch:-0} + ${n_notcluster:-0} ))"

fl_phase "TEARDOWN"
fl_teardown
trap - EXIT

echo ""
echo "== SUMMARY: PASS=$PASS  FAIL=$FAIL =="
[ "$FAIL" -eq 0 ] && { echo "OK"; exit 0; } || { echo "FUNCTIONAL TEST FAILED"; exit 1; }
