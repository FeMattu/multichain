#!/usr/bin/env python3
"""Start one ``company_daemon.py`` process per company, and supervise them.

Separate OS processes, not threads. Each company must stay individually killable, must
own its ``events.jsonl``, and must be diagnosable on its own — a thread pool would put
every company's failures in one log and one traceback, and would let one stuck RPC call
stall the others.

The supervisor restarts a daemon that dies before the run is over. A company that stops
publishing does not fail loudly: it simply contributes no ``tau``, and the epoch's weight
silently understates it, which is the kind of failure that reaches a conclusion rather
than an error message. Every restart is recorded.

    python3 test/traffic/run_company_daemons.py --config <profile> --run-dir <run>
"""

from __future__ import annotations

import argparse
import signal
import subprocess
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(HERE.parent / "bootstrap"))

from config_loader import load_profile  # noqa: E402
from event_log import EventLog  # noqa: E402

#: A daemon that dies this many times is left dead: restarting it again would only fill
#: the log, and the cause is upstream (no permission, no funds, a dead node).
MAX_RESTARTS = 3


class DaemonSupervisor:
    """Starts a set of per-node daemons and keeps them alive until the run ends."""

    def __init__(
        self,
        profile,
        run_dir: Path,
        chain_home: Path,
        role: str,
        script: Path,
        log_name: str,
    ) -> None:
        self.profile = profile
        self.run_dir = Path(run_dir)
        self.chain_home = Path(chain_home)
        self.role = role
        self.script = script
        self.stop_flag = self.run_dir / "STOP"
        self._running = True
        self.processes: Dict[str, subprocess.Popen] = {}
        self.restarts: Dict[str, int] = {}
        self.log = EventLog(
            run_dir, log_name, role, epoch_length=profile.epoch_length
        )

    def request_stop(self, *_: object) -> None:
        self._running = False

    def command(self, node_id: str) -> List[str]:
        return [
            sys.executable,
            str(self.script),
            "--config",
            str(self.profile.path),
            "--run-dir",
            str(self.run_dir),
            "--chain-home",
            str(self.chain_home),
            "--node-id",
            node_id,
        ]

    def start_one(self, node_id: str) -> None:
        out_dir = self.run_dir / "logs" / node_id
        out_dir.mkdir(parents=True, exist_ok=True)
        handle = open(out_dir / "stdout.log", "a", encoding="utf-8", buffering=1)
        command = self.command(node_id)
        handle.write("\n$ %s\n" % " ".join(command))
        self.processes[node_id] = subprocess.Popen(
            command,
            stdout=handle,
            stderr=subprocess.STDOUT,
            cwd=str(REPO_ROOT),
            start_new_session=True,
        )
        self.log.note(
            "daemon started",
            None,
            node_id=node_id,
            pid=self.processes[node_id].pid,
            restarts=self.restarts.get(node_id, 0),
        )

    def run(self) -> int:
        nodes = self.profile.by_role(self.role)
        self.log.note("supervisor starting", None, role=self.role, count=len(nodes))
        for node in nodes:
            self.start_one(node.node_id)

        while self._running and not self.stop_flag.exists():
            time.sleep(3.0)
            for node in nodes:
                process = self.processes.get(node.node_id)
                if process is None or process.poll() is None:
                    continue
                count = self.restarts.get(node.node_id, 0)
                self.log.note(
                    "daemon exited",
                    None,
                    node_id=node.node_id,
                    returncode=process.returncode,
                    restarts=count,
                )
                if self.stop_flag.exists() or not self._running:
                    break
                if count >= MAX_RESTARTS:
                    self.processes.pop(node.node_id, None)
                    continue
                self.restarts[node.node_id] = count + 1
                self.start_one(node.node_id)

        self.stop_all()
        self.log.note(
            "supervisor stopped", None, role=self.role, restarts=dict(self.restarts)
        )
        self.log.close()
        return 0

    def stop_all(self) -> None:
        for node_id, process in self.processes.items():
            if process.poll() is None:
                process.terminate()
        deadline = time.time() + self.profile.runtime["shutdown_grace_s"]
        for node_id, process in self.processes.items():
            try:
                process.wait(timeout=max(1, int(deadline - time.time())))
            except subprocess.TimeoutExpired:
                process.kill()


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
        role="company",
        script=HERE / "company_daemon.py",
        log_name="run_company_daemons",
    )
    signal.signal(signal.SIGTERM, supervisor.request_stop)
    signal.signal(signal.SIGINT, supervisor.request_stop)
    return supervisor.run()


if __name__ == "__main__":
    raise SystemExit(main())
