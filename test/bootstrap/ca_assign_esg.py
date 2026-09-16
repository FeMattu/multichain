#!/usr/bin/env python3
"""The Certification Authorities: publish a certified ESG score for every node.

A separate process per run, connected to the CA nodes. It is the only actor that may
write ``weight-engine-esg``: the score is an attestation of *trust*, and no peer can
verify it cryptographically, so the only defence is to restrict who may assert it. The
node enforces that with the custom permission ``high1``, which the global administrator
confers and may revoke — **being an administrator is not itself sufficient**.

Why this step is load-bearing rather than decorative: the raw cluster weight is

    W_k = ESG_Mk * ( tau_Mk + sum_{i in C_k} c_i )

so a miner with no certified score computes ``W_k = 0``, and ``ToIntegerWeight`` then
publishes the positivity floor of exactly ``1``. Without this step *every* cluster
publishes 1, the sortition is uniform, and the weight-versus-election comparison — the
headline result of the whole experiment — would be measuring nothing at all.

Scores come from the master seed, so a rerun of the same profile certifies the same
nodes with the same numbers.

    python3 test/bootstrap/ca_assign_esg.py --config <profile> --run-dir <run>
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Dict, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))

from config_loader import Profile, load_profile  # noqa: E402
from event_log import EVENT_ESG_SET, EventLog  # noqa: E402
from rpc_client import RpcClient, RpcError, RpcTransportError  # noqa: E402


def plan_scores(profile: Profile, addresses: Dict[str, str]) -> List[dict]:
    """Which CA certifies which node, with which score.

    Miners **and** companies are certified. A company's score enters its contribution
    ``c_i = ESG_i * tau_i / kappa`` and so reaches the cluster weight through the sum; a
    miner's multiplies the whole bracket. Leaving either uncertified zeroes a term that
    the analysis would then read as an absence of activity.

    Targets are certified round-robin across the CAs, so with more than one CA the load
    is spread and a single CA's failure does not take the whole certification with it.
    """
    cas = profile.by_role("ca")
    targets = profile.by_role("miner") + profile.by_role("company")
    low, high = profile.traffic["esg_score_range"]
    rng = profile.rng("esg-scores")
    plan = []
    for i, node in enumerate(targets):
        ca = cas[i % len(cas)]
        plan.append(
            {
                "ca_node_id": ca.node_id,
                "target_node_id": node.node_id,
                "target_role": node.role,
                "target_address": addresses.get(node.node_id, ""),
                "score": rng.randint(low, high),
            }
        )
    return plan


def assign(
    profile: Profile,
    run_dir: Path,
    chain_home: Path,
    addresses: Dict[str, str],
    log: Optional[EventLog] = None,
) -> Dict[str, object]:
    """Publish every planned score. Returns a summary for the orchestrator."""
    owns_log = log is None
    if log is None:
        first_ca = profile.by_role("ca")[0]
        log = EventLog(run_dir, first_ca.node_id, "ca", epoch_length=profile.epoch_length)

    clients: Dict[str, RpcClient] = {}
    for ca in profile.by_role("ca"):
        clients[ca.node_id] = RpcClient.from_datadir(
            chain_home / ca.node_id,
            profile.chain_name,
            profile.host,
            ca.rpc_port,
            node_id=ca.node_id,
            timeout=profile.runtime["rpc_timeout_s"],
        )

    plan = plan_scores(profile, addresses)
    published, failed = 0, 0
    tip = 0
    try:
        tip = clients[plan[0]["ca_node_id"]].block_height()
    except (RpcError, RpcTransportError, IndexError, KeyError):
        tip = 0

    for item in plan:
        rpc = clients[item["ca_node_id"]]
        address = item["target_address"]
        if not address:
            log.rpc_error(
                "weightsetesg",
                RuntimeError("no address known for %s" % item["target_node_id"]),
                tip,
                target=item["target_node_id"],
            )
            failed += 1
            continue
        try:
            txid = rpc.call("weightsetesg", address, item["score"])
        except (RpcError, RpcTransportError) as exc:
            log.rpc_error(
                "weightsetesg",
                exc,
                tip,
                ca=item["ca_node_id"],
                target=item["target_node_id"],
                target_address=address,
                score=item["score"],
            )
            failed += 1
            continue
        published += 1
        log.emit(
            EVENT_ESG_SET,
            tip,
            {
                "txid": txid,
                "ca_node_id": item["ca_node_id"],
                "target_node_id": item["target_node_id"],
                "target_role": item["target_role"],
                "target_address": address,
                "esg_score": item["score"],
            },
            node_address=address,
        )

    summary = {
        "planned": len(plan),
        "published": published,
        "failed": failed,
        "scores": {i["target_node_id"]: i["score"] for i in plan},
        "by_ca": {
            ca.node_id: sum(1 for i in plan if i["ca_node_id"] == ca.node_id)
            for ca in profile.by_role("ca")
        },
    }
    log.note("ESG certification complete", tip, **summary)
    if owns_log:
        log.close()
    return summary


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--config", required=True)
    parser.add_argument("--run-dir", required=True)
    parser.add_argument("--chain-home", default=None)
    parser.add_argument(
        "--addresses",
        default=None,
        help="JSON map node_id -> address; defaults to <run-dir>/addresses.json",
    )
    args = parser.parse_args(argv)

    profile = load_profile(args.config)
    run_dir = Path(args.run_dir)
    chain_home = Path(args.chain_home) if args.chain_home else run_dir / "chains"
    addresses_path = Path(args.addresses) if args.addresses else run_dir / "addresses.json"
    addresses = json.loads(addresses_path.read_text(encoding="utf-8"))

    summary = assign(profile, run_dir, chain_home, addresses)
    print(
        "ESG: %d/%d published (%d failed)"
        % (summary["published"], summary["planned"], summary["failed"])
    )
    return 0 if summary["failed"] == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
