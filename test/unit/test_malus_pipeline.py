"""End-to-end of the analysis join, on a fabricated run directory.

Exercises the parsing of the ground-truth logs (phase 1) and the funnel / detection /
rate join (phase 2) without a chain: a handful of hand-written ``events.jsonl`` lines and a
manifest carrying an enabled plan. This is the test that would catch an event-type name
drifting between the writer and the reader.
"""

import datetime
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "bootstrap"))
sys.path.insert(0, str(_ROOT / "analysis"))

from pipeline import phase1_collect  # noqa: E402
from pipeline.phase2_aggregate import Aggregator  # noqa: E402

PROFILE = str(_ROOT / "config" / "profiles" / "native" / "small.yaml")
ADMIN = "1AdminAddr"
ATTACKER = "1AttackerAddr"
VICTIM = "1VictimAddr"


def _line(role, nid, addr, height, etype, payload, epoch_len=20):
    return json.dumps({
        "timestamp_utc": datetime.datetime(2026, 1, 1).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
        "node_role": role, "node_id": nid, "node_address": addr,
        "block_height": height,
        "epoch_index": None if height is None else height // epoch_len,
        "event_type": etype, "payload": payload,
    }) + "\n"


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.dir = Path(tempfile.mkdtemp())
        (self.dir / "logs" / "miner-0").mkdir(parents=True)
        (self.dir / "logs" / "malus-detector").mkdir(parents=True)

        plan = {
            "schema_version": "malicious/1", "enabled": True, "seed": 12345,
            "target_action_rate": 0.5, "miner_count": 1,
            "actions": {"selfwrite": 0.5, "badweight": 0.5},
            "start_epoch": 3, "stop_epoch": None,
            "selfwrite_stream": "weight-engine-membership", "opportunities_per_epoch": 1,
            "all_miner_ids": ["miner-0", "miner-1", "miner-2"],
            "malicious_miner_ids": ["miner-0"],
            "malicious_miner_addresses": {"miner-0": ATTACKER},
            "honest_miner_ids": ["miner-1", "miner-2"],
            "quota_shares": {"miner-0": 1.0}, "quota_share_source": "uniform",
            "per_miner_target_rate": {"miner-0": 0.5},
        }
        manifest = {
            "profile_path": PROFILE, "seed": 20260905, "chain_name": "t",
            "status": "ok", "final_height": 200,
            "effective_setup_first_blocks": 40,
            "epochs": {"length_blocks": 20},
            "addresses": {"miner-0": ATTACKER, "miner-1": "1M1", "miner-2": "1M2",
                          "admin": ADMIN, "company-0": VICTIM},
            "clusters": {}, "treasury_address": "1Treasury",
            "malicious_plan": plan,
        }
        (self.dir / "manifest.json").write_text(json.dumps(manifest))

        # miner-0: two attempts (badweight epoch 3, selfwrite epoch 5), both confirmed;
        # one epoch offered with no action (epoch 4).
        miner = []
        miner.append(_line("miner", "miner-0", ATTACKER, 62, "malicious_opportunity", {
            "epoch": 3, "miner": "miner-0", "is_malicious": True, "opportunity_index": 1,
            "opportunities_denominator": 1, "target_rate": 0.5, "act": True,
            "action": "badweight", "action_id": "aid3", "attempted_so_far": 1}))
        miner.append(_line("miner", "miner-0", ATTACKER, 62, "malicious_action_sent", {
            "epoch": 3, "miner": "miner-0", "opportunity_index": 1, "action": "badweight",
            "action_id": "aid3", "stream": "wpoa-weights", "txid": "bwtx",
            "declared_address": ATTACKER, "declared_weight": 999, "true_weight": 500,
            "target_epoch": 2}))
        miner.append(_line("miner", "miner-0", ATTACKER, 64, "malicious_action_confirmed", {
            "epoch": 3, "miner": "miner-0", "action": "badweight", "action_id": "aid3",
            "stream": "wpoa-weights", "txid": "bwtx", "confirm_height": 64,
            "declared_address": ATTACKER, "target_epoch": 2}))
        miner.append(_line("miner", "miner-0", ATTACKER, 82, "malicious_opportunity", {
            "epoch": 4, "miner": "miner-0", "is_malicious": True, "opportunity_index": 2,
            "opportunities_denominator": 2, "target_rate": 0.5, "act": False,
            "action": None, "action_id": None, "attempted_so_far": 1}))
        miner.append(_line("miner", "miner-0", ATTACKER, 102, "malicious_opportunity", {
            "epoch": 5, "miner": "miner-0", "is_malicious": True, "opportunity_index": 3,
            "opportunities_denominator": 3, "target_rate": 0.5, "act": True,
            "action": "selfwrite", "action_id": "aid5", "attempted_so_far": 2}))
        miner.append(_line("miner", "miner-0", ATTACKER, 102, "malicious_action_sent", {
            "epoch": 5, "miner": "miner-0", "opportunity_index": 3, "action": "selfwrite",
            "action_id": "aid5", "stream": "weight-engine-membership", "txid": "swtx",
            "declared_address": VICTIM, "target_epoch": 4}))
        miner.append(_line("miner", "miner-0", ATTACKER, 104, "malicious_action_confirmed", {
            "epoch": 5, "miner": "miner-0", "action": "selfwrite", "action_id": "aid5",
            "stream": "weight-engine-membership", "txid": "swtx", "confirm_height": 104,
            "declared_address": VICTIM, "target_epoch": 4}))
        (self.dir / "logs" / "miner-0" / "events.jsonl").write_text("".join(miner))

        # detector: reports the badweight (true positive), refuses an honest record.
        det = []
        det.append(_line("admin", "malus-detector", ADMIN, 70, "malus_detection", {
            "verdict": "reported", "kind": "badweight", "accused_address": ATTACKER,
            "offence_height": 64, "offence_epoch": 3, "evidence_txid": "bwtx",
            "stream": "wpoa-weights", "report_txid": "rep-bw", "detect_height": 70,
            "detect_epoch": 3, "reason": None}))
        det.append(_line("admin", "malus-detector", ADMIN, 110, "malus_detection", {
            "verdict": "reported", "kind": "selfwrite", "accused_address": ATTACKER,
            "offence_height": 104, "offence_epoch": 5, "evidence_txid": "swtx",
            "stream": "weight-engine-membership", "report_txid": "rep-sw", "detect_height": 110,
            "detect_epoch": 5, "reason": None}))
        det.append(_line("admin", "malus-detector", ADMIN, 90, "malus_detection", {
            "verdict": "refused", "kind": "badweight", "accused_address": "1M1",
            "offence_height": 80, "offence_epoch": 4, "evidence_txid": "honesttx",
            "stream": "wpoa-weights", "report_txid": None, "detect_height": 90,
            "detect_epoch": 4, "reason": "the published weight is CORRECT"}))
        (self.dir / "logs" / "malus-detector" / "events.jsonl").write_text("".join(det))

    def tearDown(self):
        shutil.rmtree(self.dir, ignore_errors=True)

    def test_phase1_parses_ground_truth(self):
        phase1_collect.collect(self.dir, Path(PROFILE))
        p1 = self.dir / "analysis" / "phase1"

        def rows(name):
            import csv
            with open(p1 / ("%s.csv" % name), newline="") as h:
                return list(csv.DictReader(h))

        self.assertEqual(len(rows("malicious_opportunities")), 3)
        self.assertEqual(len(rows("malicious_actions")), 2)
        self.assertEqual(len(rows("malicious_confirmations")), 2)
        self.assertEqual(len(rows("malus_detections")), 3)
        miners = rows("malicious_miners")
        self.assertEqual(len(miners), 3)
        self.assertEqual(sum(1 for r in miners if r["is_malicious"] == "True"), 1)

    def test_phase2_funnel_and_detection(self):
        phase1_collect.collect(self.dir, Path(PROFILE))
        agg = Aggregator(self.dir)
        agg.build_malicious()

        funnel = {r["scope"]: r for r in agg.tables["malus_funnel"]}
        self.assertEqual(funnel["all"]["opportunities"], 3)
        self.assertEqual(funnel["all"]["attempts"], 2)
        self.assertEqual(funnel["all"]["confirmed"], 2)
        self.assertEqual(funnel["all"]["valid_malus"], 2)

        actions = {r["action_id"]: r for r in agg.tables["malus_actions"]}
        self.assertTrue(actions["aid3"]["reported"])
        self.assertEqual(actions["aid3"]["detection_latency_blocks"], 70 - 64)
        self.assertEqual(actions["aid3"]["activation_latency_epochs"], 1)

        # The detector's refusal of an honest record is a NON-true-positive report? No:
        # a refusal is not a report. There must be zero false positives.
        events = agg.tables["malus_detection_events"]
        false_positives = [e for e in events
                           if e["verdict"] == "reported" and e["is_true_positive"] is not True]
        self.assertEqual(false_positives, [])

        rate = {r["miner"]: r for r in agg.tables["malus_rate_by_miner"]}
        self.assertEqual(rate["miner-0"]["opportunities"], 3)
        self.assertEqual(rate["miner-0"]["attempts"], 2)
        self.assertAlmostEqual(rate["miner-0"]["attempted_rate"], 2 / 3)


if __name__ == "__main__":
    unittest.main()
