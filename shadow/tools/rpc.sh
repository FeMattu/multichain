#!/usr/bin/env bash
# Client JSON-RPC minimale, usabile a mano dentro la simulazione o dai role script.
#   rpc.sh <ip> <metodo> [params-json]
set -uo pipefail
. "$(dirname "${BASH_SOURCE[0]}")/sim_common.sh"
rpc "$@"
echo
