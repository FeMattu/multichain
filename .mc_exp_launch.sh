#!/usr/bin/env bash
# Stage 3 launcher: run the 15h regional profile inside the emulation container,
# line-buffered into output.log at the repo root so it can be tailed live over SSH.
cd /home/fede/Desktop/thesis/multichain || exit 1
exec ./docker/mcsim run bash -c \
  'stdbuf -oL -eL python3 -u test/bootstrap/bootstrap_network.py --config test/config/profiles/core/regional-medium15h.yaml > output.log 2>&1'
