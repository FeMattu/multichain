"""Keep pytest out of the results tree.

`experiments/results/` holds run directories, not tests. Walking it is slow
once a campaign has accumulated, and it is worse than slow when a run was
made with sudo: MultiChain's data directory is mode 0700 and root-owned, so
collection dies with a PermissionError before a single test runs.

`testpaths` in pyproject.toml covers `pytest` with no argument; this covers
`pytest experiments`, which is what people actually type.
"""

from __future__ import annotations

collect_ignore_glob = [
    "results/*",
    "topology/generated/*",
    "analysis/historical/*",
]
