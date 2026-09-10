#!/usr/bin/env bash
# Minimal JSON-RPC client, for poking at a node by hand.
#
#   sudo ip netns exec poesia-h-m1 env POESIA_RUN=<run> POESIA_CHAIN=<chain> \
#       experiments/runtime/roles/rpc.sh 11.0.0.21 getinfo
#   ... rpc.sh 11.0.0.10 liststreamitems '["wpoa-weights",false,10]'
#
# The address is the peer's EMULATED one, so the call travels the same
# impaired path a node's own RPC would - which is usually what you want when
# you are debugging why a node cannot see another.
set -Euo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/_common.sh"
rpc "$@"
echo
