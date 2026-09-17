"""Validation of the ``malicious`` profile section, and its backward compatibility.

The most load-bearing test here is the last one: a profile with no ``malicious`` section
must resolve to exactly the disabled plan, because the whole feature rests on that clause —
an existing profile has to behave as though the feature did not exist.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "traffic"))

import malicious as M  # noqa: E402
from config_loader import load_profile  # noqa: E402

PROFILES = Path(__file__).resolve().parent.parent / "config" / "profiles"


class TestValidate(unittest.TestCase):
    def _valid(self, **overrides):
        cfg = {
            "enabled": True,
            "miner_count": 2,
            "target_action_rate": 0.15,
            "actions": {"selfwrite": 0.5, "badweight": 0.5},
            "start_epoch": 3,
        }
        cfg.update(overrides)
        return cfg

    def test_absent_section_is_disabled_plan(self):
        out = M.validate(None, miner_count=10, epoch_count=20, profile_seed=42)
        self.assertFalse(out["enabled"])
        self.assertEqual(out["seed"], 42)          # falls back to the run seed
        self.assertEqual(out["miner_count"], 0)

    def test_seed_defaults_to_profile_seed(self):
        out = M.validate(self._valid(seed=None), 10, 20, 777)
        self.assertEqual(out["seed"], 777)
        out2 = M.validate(self._valid(seed=1), 10, 20, 777)
        self.assertEqual(out2["seed"], 1)

    def test_actions_normalised(self):
        out = M.validate(self._valid(actions={"selfwrite": 3, "badweight": 1}), 10, 20, 1)
        self.assertAlmostEqual(sum(out["actions"].values()), 1.0)
        self.assertAlmostEqual(out["actions"]["selfwrite"], 0.75)
        self.assertAlmostEqual(out["actions"]["badweight"], 0.25)

    def test_count_out_of_range(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(miner_count=11), 10, 20, 1)
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(miner_count=-1), 10, 20, 1)

    def test_rate_out_of_range(self):
        for bad in (-0.01, 1.01, 2.0):
            with self.assertRaises(M.MaliciousConfigError):
                M.validate(self._valid(target_action_rate=bad), 10, 20, 1)

    def test_negative_action_weight(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(actions={"selfwrite": -1, "badweight": 1}), 10, 20, 1)

    def test_all_zero_action_weights(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(actions={"selfwrite": 0, "badweight": 0}), 10, 20, 1)

    def test_unknown_action(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(actions={"bogus": 1}), 10, 20, 1)

    def test_unimplementable_actions_rejected_with_reason(self):
        for kind in ("delay", "equiv"):
            with self.assertRaises(M.MaliciousConfigError) as ctx:
                M.validate(self._valid(actions={kind: 1}), 10, 20, 1)
            self.assertIn("consensus core", str(ctx.exception))

    def test_start_epoch_bounds(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(start_epoch=0), 10, 20, 1)
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(start_epoch=21), 10, 20, 1)

    def test_stop_before_start(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(start_epoch=5, stop_epoch=4), 10, 20, 1)

    def test_unknown_key(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(nonsense=1), 10, 20, 1)

    def test_enabled_but_inert_rejected(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(miner_count=0), 10, 20, 1)
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(target_action_rate=0.0), 10, 20, 1)

    def test_selfwrite_stream_must_be_self_attested(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.validate(self._valid(selfwrite_stream="supply-chain-events"), 10, 20, 1)
        out = M.validate(self._valid(selfwrite_stream="wpoa-weights"), 10, 20, 1)
        self.assertEqual(out["selfwrite_stream"], "wpoa-weights")


class TestProfilesLoad(unittest.TestCase):
    def test_honest_profiles_unchanged(self):
        for name in ("small", "medium", "large"):
            profile = load_profile(str(PROFILES / ("%s.yaml" % name)))
            self.assertFalse(profile.malicious_enabled, name)
            self.assertEqual(profile.malicious_miner_ids, [], name)
            # The disabled plan still lists every miner, so phase 1 has a constant shape.
            plan = profile.malicious_plan()
            self.assertEqual(len(plan["all_miner_ids"]), profile.miner_count)
            self.assertEqual(plan["malicious_miner_ids"], [])

    def test_malicious_profile_selects_deterministically(self):
        profile = load_profile(str(PROFILES / "malicious.yaml"))
        self.assertTrue(profile.malicious_enabled)
        first = profile.malicious_miner_ids
        second = load_profile(str(PROFILES / "malicious.yaml")).malicious_miner_ids
        self.assertEqual(first, second)
        self.assertEqual(len(first), 2)
        self.assertTrue(all(m.startswith("miner-") for m in first))


if __name__ == "__main__":
    unittest.main()
