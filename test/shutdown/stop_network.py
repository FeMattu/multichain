#!/usr/bin/env python3
"""Stop everything a run started, in the order that makes the teardown clean.

Called by ``bootstrap_network.py`` at the end of a run, and usable on its own to clean up
after an interrupted one::

    python3 test/shutdown/stop_network.py --config <profile> --run-dir <run>

Order matters in both halves:

1. **Daemons first.** The ``STOP`` sentinel goes down before any node does, so the
   company and miner daemons stop *deciding to send* rather than discovering mid-call
   that their node has gone. A daemon killed mid-publish leaves a transaction whose fate
   nothing recorded.
2. **Nodes last, seed last of all.** Every joined node talks to the seed; taking the seed
   down first makes each of the others spend its shutdown retrying a dead peer.

The sentinel is a file rather than a signal because the daemons may be children,
grandchildren or orphans of whoever is doing the stopping, and a file reaches all three.
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
sys.path.insert(0, str(REPO_ROOT / "test" / "bootstrap"))

from config_loader import ConfigError, Profile, load_profile  # noqa: E402
from event_log import EVENT_NODE_STOPPED, EventLog  # noqa: E402
from node_process import NodeRunner, write_json  # noqa: E402
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402


def final_snapshot(profile: Profile, chain_home: Path, log: EventLog) -> Dict[str, object]:
    """One last read of the chain, before the nodes are gone.

    A functional run is a one-shot experiment: once the daemons are down the evidence is
    whatever was written while they were up. This costs one round of RPC and is the
    cheapest possible insurance against a final epoch that turned out to be interesting.
    """
    admin = profile.admin
    try:
        rpc = RpcClient.from_datadir(
            chain_home / admin.node_id,
            profile.chain_name,
            profile.rpc_host(admin.node_id),
            admin.rpc_port,
            node_id=admin.node_id,
            timeout=profile.runtime["rpc_timeout_s"],
        )
        tip = rpc.block_height()
    except (RpcError, RpcTransportError, RuntimeError) as exc:
        log.note("final snapshot skipped: admin unreachable", None, error=str(exc))
        return {"final_height": None, "reachable": False}

    summary: Dict[str, object] = {"final_height": tip, "reachable": True}
    for method, args in (
        ("getinfo", ()),
        ("getallweights", ()),
        ("getallmalus", ()),
        ("listminers", (True,)),
        ("weightverifyweights", ()),
    ):
        try:
            data = rpc.call(method, *args)
        except (RpcError, RpcTransportError) as exc:
            log.rpc_error(method, exc, tip)
            continue
        log.snapshot(method, tip, data, final=True)
        summary[method] = data

    buried = profile.last_buried_epoch(tip)
    if buried >= 1:
        for method in (
            "weightlistclusterweights",
            "weightlistreturns",
            "weightlistearnings",
            "weightlistbalances",
            "weightlistcontributions",
        ):
            try:
                log.snapshot(method, tip, rpc.call(method, buried), epoch=buried, final=True)
            except (RpcError, RpcTransportError) as exc:
                log.rpc_error(method, exc, tip, epoch=buried)
    summary["last_buried_epoch"] = buried
    return summary


def stop_network(
    profile: Profile,
    run_dir: Path,
    chain_home: Path,
    snapshot: bool = True,
    fabric: Optional[object] = None,
) -> Dict[str, object]:
    """Bring the whole run down. Returns a report, and never raises past its own cleanup.

    ``fabric`` is the live one when the orchestrator is doing the stopping. Called on its
    own against a finished run there is none, and a node in an emulated regime cannot then
    be reached at all — its namespace went with the session. That is not a loss: the
    session is what held the nodes, and deleting it takes them with it.
    """
    log = EventLog(run_dir, "shutdown", "admin", epoch_length=profile.epoch_length)
    report: Dict[str, object] = {}
    try:
        # 1. Sentinel first: the daemons stop deciding to send.
        stop_flag = run_dir / "STOP"
        stop_flag.write_text("stop\n", encoding="utf-8")
        log.note("STOP sentinel written", None, path=str(stop_flag))
        print("[shutdown] STOP sentinel written; waiting for the daemons to notice", flush=True)
        time.sleep(min(10, profile.runtime["shutdown_grace_s"]))

        # 2. A last look at the chain, while it still answers.
        if snapshot:
            report["snapshot"] = final_snapshot(profile, chain_home, log)

        # 3. The nodes, seed last -- unless the emulated network is what holds them.
        if fabric is None and profile.fabric_backend != "native":
            report["nodes"] = _delete_emulated_session(run_dir, log)
            print("[shutdown] emulated session deleted; its nodes went with it", flush=True)
            return report
        runner = NodeRunner(profile, REPO_ROOT, chain_home, fabric)
        outcomes = runner.stop_all(profile.runtime["shutdown_grace_s"])
        report["nodes"] = outcomes
        forced = sorted(k for k, v in outcomes.items() if v in ("sigterm", "sigkill"))
        if forced:
            # Worth saying out loud: a node that had to be killed may have been wedged
            # for a while, and its last epoch's data deserves a second look.
            print("[shutdown] forced to signal: %s" % ", ".join(forced), flush=True)
        log.emit(EVENT_NODE_STOPPED, None, {"outcomes": outcomes, "forced": forced})
        print("[shutdown] %d node(s) stopped" % len(outcomes), flush=True)
    finally:
        log.close()

    write_json(run_dir / "shutdown.json", report)
    return report


def _delete_emulated_session(run_dir: Path, log: EventLog) -> Dict[str, str]:
    """Tear down an emulated run nobody is holding open any more.

    Stopping the nodes one at a time is not possible here and not wanted: reaching a node
    means entering the namespace its session owns, and the session is exactly what this is
    deleting. Deleting it takes the namespaces, the cables and every process inside them
    at once, which is the same outcome by a shorter path.

    The session id comes from ``<run>/fabric.json``, which the orchestrator wrote when it
    built the network.
    """
    manifest = run_dir / "fabric.json"
    if not manifest.is_file():
        log.note("no fabric.json: nothing to delete", None, path=str(manifest))
        return {"session": "absent"}
    try:
        described = json.loads(manifest.read_text(encoding="utf-8"))
        session_id = int(described.get("session_id"))
        address = str(described.get("grpc_address") or "127.0.0.1:50051")
    except (OSError, TypeError, ValueError) as exc:
        log.note("fabric.json unreadable", None, error=str(exc))
        return {"session": "unreadable: %s" % exc}

    try:
        from core.api.grpc import client as core_client

        handle = core_client.CoreGrpcClient(address)
        handle.connect()
        handle.stop_session(session_id)
        handle.delete_session(session_id)
        handle.close()
    except Exception as exc:  # the emulator may be gone, which is also a clean end
        log.note("could not delete the session", None, session=session_id, error=str(exc))
        return {"session": "%d: %s" % (session_id, exc)}
    log.note("emulated session deleted", None, session=session_id)
    return {"session": "%d: deleted" % session_id}


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    parser.add_argument(
        "--no-snapshot",
        action="store_true",
        help="skip the final read (use when the nodes are already gone)",
    )
    args = parser.parse_args(argv)

    try:
        profile = load_profile(args.config)
    except ConfigError as exc:
        print("[shutdown] configuration error: %s" % exc, file=sys.stderr)
        return 1

    run_dir = Path(args.run_dir)
    if not run_dir.is_dir():
        print("[shutdown] no such run directory: %s" % run_dir, file=sys.stderr)
        return 1
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"

    report = stop_network(profile, run_dir, chain_home, snapshot=not args.no_snapshot)
    print(json.dumps(report.get("nodes", {}), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
