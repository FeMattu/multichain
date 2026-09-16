#!/usr/bin/env python3
"""Start one ``miner_gas_daemon.py`` process per miner, and supervise them.

Same supervision contract as ``run_company_daemons.py``, whose ``DaemonSupervisor`` this
reuses: one OS process per miner, individually killable, each with its own
``events.jsonl``, restarted a bounded number of times if it dies before the run ends.

A miner daemon that dies is more consequential than a company one. Its restitutions are
the only source of ``R_k``, so its silence pins ``rho`` at 0 for its whole cluster and
the inter-epoch feedback simply stops moving — visible in the results as an unusually
well-behaved weight rather than as a failure.

Mining itself needs no daemon: with sortition on, a permitted node self-elects and
produces blocks without any RPC from the harness.

    python3 test/traffic/run_miner_daemons.py --config <profile> --run-dir <run>
"""

from __future__ import annotations

import argparse
import signal
import sys
from pathlib import Path
from typing import List, Optional

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "bootstrap"))
sys.path.insert(0, str(HERE))

from config_loader import load_profile  # noqa: E402
from run_company_daemons import DaemonSupervisor  # noqa: E402


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"

    supervisor = DaemonSupervisor(
        profile,
        run_dir,
        chain_home,
        role="miner",
        script=HERE / "miner_gas_daemon.py",
        log_name="run_miner_daemons",
    )
    signal.signal(signal.SIGTERM, supervisor.request_stop)
    signal.signal(signal.SIGINT, supervisor.request_stop)
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
