"""The injector's decision replay, restart safety and on-chain idempotency.

Uses a real :class:`EventLog` in a temp directory (the log is the journal, so a test of
restart behaviour has to use the real one) and a fake RPC that records what it was asked to
publish, so the test never needs a chain.
"""

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "bootstrap"))
sys.path.insert(0, str(_ROOT / "traffic"))

import malicious as M  # noqa: E402
from config_loader import load_profile  # noqa: E402
from event_log import EventLog, replay  # noqa: E402
from malicious_injector import MaliciousInjector  # noqa: E402
from rpc_client import RpcError  # noqa: E402

PROFILES = _ROOT / "config" / "profiles" / "native"


class FakeRpc:
    """Records publishes; answers reads from an in-memory stream keyed by item key."""

    def __init__(self):
        self.published = []                 # (stream, key, payload)
        self.items = {}                     # (stream, key) -> [item, ...]
        self.calls = 0
        self.failures = 0
        self.fail_publish = False

    def own_address(self):
        return "ATTACKER"

    def call(self, method, *args):
        self.calls += 1
        if method == "publish":
            if self.fail_publish:
                self.failures += 1
                raise RpcError("publish", -6, "fee policy")
            stream, key, payload = args
            txid = "tx-%s-%d" % (key, len(self.published))
            self.published.append((stream, key, payload))
            self.items.setdefault((stream, key), []).append(
                {"txid": txid, "blockheight": 100 + len(self.published),
                 "confirmations": 1, "keys": [key]}
            )
            return txid
        if method == "weightgetnodeclusterweight":
            return {"final_cluster_weight": 500}
        if method == "getnodeweight":
            return {"address": args[0], "weight": 500}
        raise RpcError(method, -32601, "unexpected method in test")

    def stream_key_items(self, stream, key, count=100000):
        return list(self.items.get((stream, key), []))


def _plan():
    return {
        "schema_version": M.SCHEMA_VERSION,
        "enabled": True,
        "seed": 12345,
        "target_action_rate": 1.0,   # act at every opportunity, to make behaviour testable
        "miner_count": 1,
        "actions": {"badweight": 1.0},
        "start_epoch": 3,
        "stop_epoch": 6,
        "selfwrite_stream": "weight-engine-membership",
        "opportunities_per_epoch": 1,
        "all_miner_ids": ["miner-0", "miner-1", "miner-2"],
        "malicious_miner_ids": ["miner-0"],
        "per_miner_target_rate": {"miner-0": 1.0},
        "quota_shares": {"miner-0": 1.0},
    }


class InjectorTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        self.profile = load_profile(str(PROFILES / "small.yaml"))
        self.addr = {"miner-0": "ATTACKER", "company-0": "VICTIM", "miner-1": "OTHER"}

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def _injector(self, rpc=None):
        log = EventLog(self.dir, "miner-0", "miner", epoch_length=self.profile.epoch_length)
        return MaliciousInjector(
            self.profile, _plan(), "miner-0", "ATTACKER", rpc or FakeRpc(), log, "run-x",
            all_addresses=self.addr,
        ), log

    def test_decision_replay_is_deterministic(self):
        inj, log = self._injector()
        d1 = inj.decision_for_epoch(5)
        inj2, log2 = self._injector()
        d2 = inj2.decision_for_epoch(5)
        log.close()
        log2.close()
        self.assertEqual(d1["act"], d2["act"])
        self.assertEqual(d1["opportunity_index"], d2["opportunity_index"])
        self.assertEqual(d1["draw"], d2["draw"])

    def test_opportunity_index_tracks_epoch(self):
        inj, log = self._injector()
        self.assertEqual(inj.decision_for_epoch(3)["opportunity_index"], 1)
        self.assertEqual(inj.decision_for_epoch(4)["opportunity_index"], 2)
        self.assertEqual(inj.decision_for_epoch(6)["opportunity_index"], 4)
        log.close()

    def test_rate_one_acts_every_epoch(self):
        inj, log = self._injector()
        for e in range(3, 7):
            self.assertTrue(inj.decision_for_epoch(e)["act"], e)
        log.close()

    def test_opportunity_logged_once_per_epoch(self):
        rpc = FakeRpc()
        inj, log = self._injector(rpc)
        inj.run_opportunity(3, tip=70)
        inj.run_opportunity(3, tip=71)   # same epoch again: must not re-offer
        log.close()
        opps = list(replay(self.dir, "miner-0", ("malicious_opportunity",)))
        self.assertEqual(len(opps), 1)

    def test_action_published_and_logged(self):
        rpc = FakeRpc()
        inj, log = self._injector(rpc)
        inj.run_opportunity(3, tip=70)
        log.close()
        self.assertEqual(len(rpc.published), 1)
        stream, key, _ = rpc.published[0]
        self.assertEqual(stream, "wpoa-weights")          # badweight target
        sent = list(replay(self.dir, "miner-0", ("malicious_action_sent",)))
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["payload"]["action_id"], key)

    def test_idempotent_across_restart(self):
        # First incarnation publishes for epoch 3.
        rpc = FakeRpc()
        inj, log = self._injector(rpc)
        inj.run_opportunity(3, tip=70)
        log.close()
        published_before = len(rpc.published)
        # Second incarnation, SAME rpc (so the item is 'on chain') and same log dir:
        # it must neither re-offer the epoch nor re-publish the action.
        inj2, log2 = self._injector(rpc)
        inj2.run_opportunity(3, tip=72)
        log2.close()
        self.assertEqual(len(rpc.published), published_before)

    def test_confirmation_swept_once(self):
        rpc = FakeRpc()
        inj, log = self._injector(rpc)
        inj.run_opportunity(3, tip=70)   # publishes + sweeps (item confirmed immediately)
        inj.sweep_confirmations(3, tip=80)  # second sweep must not re-log
        log.close()
        confs = list(replay(self.dir, "miner-0", ("malicious_action_confirmed",)))
        self.assertEqual(len(confs), 1)

    def test_publish_failure_recorded_not_fatal(self):
        rpc = FakeRpc()
        rpc.fail_publish = True
        inj, log = self._injector(rpc)
        inj.run_opportunity(3, tip=70)   # should not raise
        log.close()
        self.assertEqual(len(rpc.published), 0)
        sent = list(replay(self.dir, "miner-0", ("malicious_action_sent",)))
        self.assertEqual(len(sent), 0)   # nothing was sent
        # but the opportunity was still recorded
        opps = list(replay(self.dir, "miner-0", ("malicious_opportunity",)))
        self.assertEqual(len(opps), 1)


if __name__ == "__main__":
    unittest.main()
