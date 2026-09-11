#!/usr/bin/env bash
# Run an experiment WITHOUT root, inside an unprivileged user namespace.
#
#   experiments/scripts/run_unprivileged.sh \
#       --experiment experiments/configs/experiments/smoke-3n.yaml
#
# `unshare -Urnm` gives this process a user namespace in which it is uid 0,
# plus its own network and mount namespaces. Inside them the harness has real
# CAP_NET_ADMIN over its own network namespace, so `ip netns`, veth and
# tc/netem all work — verified, not assumed — while on the host nothing is
# privileged and every file is created as the invoking user.
#
# WHAT THIS IS GOOD FOR
#   - a smoke test, CI, or development on a machine where you cannot or would
#     rather not use sudo
#   - it produces the same artefacts as a privileged run, and the manifest
#     records that it was unprivileged
#
# WHAT IT IS NOT
#   - it cannot talk to a CORE daemon (that runs as root, outside), so the
#     backend is always netns and the fallback is authorised implicitly by
#     your choosing this script
#   - it needs unprivileged user namespaces enabled (Ubuntu: on by default;
#     some hardened kernels and Docker's default seccomp profile block them)
. "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/_common.sh"
trap 'on_error $LINENO' ERR

if [ "${POESIA_IN_USERNS:-0}" != "1" ]; then
    command -v unshare >/dev/null || \
        die "$EXIT_ENVIRONMENT_UNAVAILABLE" "unshare is not installed (util-linux)"
    if ! unshare -Urn true 2>/dev/null; then
        die "$EXIT_ENVIRONMENT_UNAVAILABLE" \
            "unprivileged user namespaces are not available on this kernel. \
Use sudo -E experiments/scripts/run_experiment.sh instead."
    fi
    say "entering an unprivileged user namespace"
    exec unshare -Urnm --propagation private \
        env POESIA_IN_USERNS=1 "$0" "$@"
fi

# Inside: /run must be writable for `ip netns`, and lo must be up.
mount -t tmpfs none /run 2>/dev/null || true
ip link set lo up 2>/dev/null || true

say "uid=$(id -u) (mapped), netns available: $(ip netns list >/dev/null 2>&1 && echo yes || echo no)"

# The backend can only be netns here, and choosing this script IS the consent:
# there is no CORE daemon reachable from inside a user namespace.
exec "$SCRIPTS_DIR/run_experiment.sh" --backend netns "$@"
