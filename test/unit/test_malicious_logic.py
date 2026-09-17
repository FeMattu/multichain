"""The deterministic core: selection, quota split, the rate controller, ids and payloads.

These are the decisions a malicious daemon makes with no chain and no coordination, so they
are exactly the ones that must be reproducible and provably correct in isolation.
"""

import random
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import malicious as M  # noqa: E402


class TestSelection(unittest.TestCase):
    MINERS = ["miner-%d" % i for i in range(10)]

    def test_deterministic(self):
        a = M.select_miners(12345, self.MINERS, 3)
        b = M.select_miners(12345, self.MINERS, 3)
        self.assertEqual(a, b)

    def test_seed_changes_selection(self):
        a = set(M.select_miners(1, self.MINERS, 3))
        b = set(M.select_miners(2, self.MINERS, 3))
        self.assertNotEqual(a, b)  # overwhelmingly likely with 10 choose 3

    def test_count_bounds(self):
        self.assertEqual(M.select_miners(1, self.MINERS, 0), [])
        self.assertEqual(set(M.select_miners(1, self.MINERS, 10)), set(self.MINERS))

    def test_returned_in_profile_order(self):
        chosen = M.select_miners(999, self.MINERS, 4)
        self.assertEqual(chosen, [m for m in self.MINERS if m in set(chosen)])

    def test_only_miners_selected(self):
        chosen = M.select_miners(7, self.MINERS, 5)
        self.assertTrue(set(chosen).issubset(set(self.MINERS)))


class TestQuota(unittest.TestCase):
    def test_uniform_when_no_weights(self):
        shares = M.quota_shares(["a", "b", "c", "d"])
        self.assertTrue(all(abs(s - 0.25) < 1e-12 for s in shares.values()))

    def test_proportional_to_weight(self):
        shares = M.quota_shares(["a", "b"], {"a": 30.0, "b": 10.0})
        self.assertAlmostEqual(shares["a"], 0.75)
        self.assertAlmostEqual(shares["b"], 0.25)

    def test_fallback_when_all_zero(self):
        shares = M.quota_shares(["a", "b"], {"a": 0.0, "b": 0.0})
        self.assertAlmostEqual(shares["a"], 0.5)
        self.assertAlmostEqual(shares["b"], 0.5)

    def test_per_miner_rate_uniform_collapses_to_target(self):
        # Uniform split of n miners: each gets exactly the aggregate target.
        self.assertAlmostEqual(M.per_miner_rate(0.15, 2, 0.5), 0.15)
        self.assertAlmostEqual(M.per_miner_rate(0.2, 5, 0.2), 0.2)

    def test_per_miner_rate_clamped(self):
        # A miner with a large share cannot be asked for more than one action per chance:
        # 0.5 * 3 * 0.8 = 1.2 would exceed one action per opportunity, so it clamps to 1.
        self.assertEqual(M.per_miner_rate(0.5, 3, 0.8), 1.0)
        # Just below the clamp it passes through unchanged.
        self.assertAlmostEqual(M.per_miner_rate(0.5, 2, 0.9), 0.9)

    def test_aggregate_rate_preserved(self):
        # Sum of per-miner attempts / total opportunities == target, when each miner sees
        # the same number of opportunities.
        shares = M.quota_shares(["a", "b", "c"], {"a": 50.0, "b": 30.0, "c": 20.0})
        target, n, opps_each = 0.3, 3, 100
        total_attempts = sum(
            M.per_miner_rate(target, n, shares[m]) * opps_each for m in shares
        )
        total_opps = n * opps_each
        self.assertAlmostEqual(total_attempts / total_opps, target, places=6)


class TestRateController(unittest.TestCase):
    def test_converges_to_target(self):
        ctrl = M.RateController(0.15)
        rng = random.Random(0)
        for _ in range(2000):
            ctrl.offer(rng.random())
        self.assertAlmostEqual(ctrl.realised_rate, 0.15, delta=0.02)

    def test_never_systematically_overshoots(self):
        # With draws that always act when allowed, the realised rate tracks the target
        # from below or exactly, never runs away above it.
        ctrl = M.RateController(0.2)
        for _ in range(500):
            ctrl.offer(0.0)  # act whenever probability > 0
        self.assertLessEqual(ctrl.realised_rate, 0.2 + 1e-9)

    def test_catches_up_after_a_gap(self):
        # A miner that declined early (deficit grows) then acts at every chance.
        ctrl = M.RateController(0.5)
        for _ in range(10):
            ctrl.offer(0.99)  # decline (probability stays < 0.99 for a while)
        # Now the deficit is large; a moderate draw should act.
        result = ctrl.offer(0.4)
        self.assertTrue(result["act"])

    def test_resume_from_state(self):
        ctrl = M.RateController(0.3, opportunities=10, attempted=3)
        self.assertEqual(ctrl.opportunities, 10)
        self.assertEqual(ctrl.attempted, 3)


class TestActionId(unittest.TestCase):
    def test_deterministic_and_stable(self):
        a = M.action_id("run-1", "miner-2", 5, 3, "badweight")
        b = M.action_id("run-1", "miner-2", 5, 3, "badweight")
        self.assertEqual(a, b)
        self.assertEqual(len(a), 24)

    def test_distinct_on_any_field(self):
        base = M.action_id("run-1", "miner-2", 5, 3, "badweight")
        self.assertNotEqual(base, M.action_id("run-2", "miner-2", 5, 3, "badweight"))
        self.assertNotEqual(base, M.action_id("run-1", "miner-3", 5, 3, "badweight"))
        self.assertNotEqual(base, M.action_id("run-1", "miner-2", 6, 3, "badweight"))
        self.assertNotEqual(base, M.action_id("run-1", "miner-2", 5, 4, "badweight"))
        self.assertNotEqual(base, M.action_id("run-1", "miner-2", 5, 3, "selfwrite"))


class TestChooseAction(unittest.TestCase):
    def test_split_matches_weights(self):
        actions = M.normalise_actions({"selfwrite": 0.5, "badweight": 0.5})
        rng = random.Random(1)
        counts = {"selfwrite": 0, "badweight": 0}
        for _ in range(10000):
            counts[M.choose_action(actions, rng.random())] += 1
        self.assertAlmostEqual(counts["selfwrite"] / 10000, 0.5, delta=0.03)

    def test_boundary_draw(self):
        actions = M.normalise_actions({"selfwrite": 1.0})
        self.assertEqual(M.choose_action(actions, 0.999999), "selfwrite")

    def test_single_action_always_chosen(self):
        actions = M.normalise_actions({"badweight": 1.0})
        for d in (0.0, 0.3, 0.99):
            self.assertEqual(M.choose_action(actions, d), "badweight")


class TestPayloads(unittest.TestCase):
    def test_selfwrite_membership_names_other_address(self):
        body = M.selfwrite_membership_payload("VICTIM", "ATTACKER", 123)
        self.assertEqual(body["json"]["node_address"], "VICTIM")
        self.assertEqual(body["json"]["miner_address"], "ATTACKER")
        self.assertNotEqual(body["json"]["node_address"], "ATTACKER")

    def test_selfwrite_weights_positive_weight(self):
        body = M.selfwrite_weights_payload("VICTIM", 100, 4)
        self.assertEqual(body["json"]["node_address"], "VICTIM")
        self.assertGreater(body["json"]["weight"], 0)

    def test_badweight_about_self_with_epoch(self):
        body = M.badweight_payload("SELF", 999, 5)
        self.assertEqual(body["json"]["node_address"], "SELF")
        self.assertEqual(body["json"]["epoch"], 5)
        self.assertGreater(body["json"]["weight"], 0)

    def test_badweight_rejects_zero_epoch(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.badweight_payload("SELF", 999, 0)

    def test_falsify_weight_always_differs_and_positive(self):
        rng = random.Random(3)
        for true in (1, 50, 100, 6670, 100000):
            for _ in range(20):
                v = M.falsify_weight(true, rng)
                self.assertNotEqual(v, true)
                self.assertGreater(v, 0)

    def test_pick_victim_excludes_self(self):
        rng = random.Random(4)
        for _ in range(20):
            v = M.pick_victim("SELF", ["SELF", "A", "B", "C"], rng)
            self.assertNotEqual(v, "SELF")
            self.assertIn(v, ("A", "B", "C"))

    def test_pick_victim_none_available(self):
        with self.assertRaises(M.MaliciousConfigError):
            M.pick_victim("SELF", ["SELF"], random.Random(0))


class TestWindow(unittest.TestCase):
    def test_active_window(self):
        plan = {"enabled": True, "start_epoch": 3, "stop_epoch": 6}
        self.assertFalse(M.active_window(plan, 2))
        self.assertTrue(M.active_window(plan, 3))
        self.assertTrue(M.active_window(plan, 6))
        self.assertFalse(M.active_window(plan, 7))

    def test_open_ended_window(self):
        plan = {"enabled": True, "start_epoch": 3, "stop_epoch": None}
        self.assertTrue(M.active_window(plan, 99))

    def test_disabled_never_active(self):
        self.assertFalse(M.active_window({"enabled": False, "start_epoch": 1}, 5))


if __name__ == "__main__":
    unittest.main()
