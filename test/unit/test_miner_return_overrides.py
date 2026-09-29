"""traffic.miner_return_overrides: per-miner restitution phases, and nothing else.

The option exists for the controlled experiment on rho (profile regional-rho-swap). Its
contract has two halves, and both are tested here:

* a profile WITHOUT the key resolves, funds and draws exactly as before — same traffic
  mapping (the key is absent, not defaulted), same miner_seed_gas, same RNG sequence;
* a profile WITH it gives each named miner its own ranges from each phase's from_epoch,
  funds every miner equally on the largest range, and rejects malformed phases.

The phase 3 side (the likelihood-ratio test) is checked on a synthetic election where the
answer is known.
"""

import copy
import random
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "bootstrap"))
sys.path.insert(0, str(ROOT / "traffic"))
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "analysis"))

import yaml  # noqa: E402

from config_loader import ConfigError, load_profile  # noqa: E402
from miner_gas_daemon import MinerGasDaemon  # noqa: E402
from pipeline.stat import rho_contrast as RHO  # noqa: E402

PROFILES = ROOT / "config" / "profiles"
SWAP = PROFILES / "core" / "regional-rho-swap.yaml"
PLAIN = PROFILES / "core" / "regional-d075.yaml"


def load_raw(raw):
    handle = tempfile.NamedTemporaryFile(
        "w", suffix=".yaml", dir=str(SWAP.parent), delete=False
    )
    yaml.safe_dump(raw, handle)
    handle.close()
    try:
        return load_profile(handle.name)
    finally:
        Path(handle.name).unlink()


def draws(profile, node_id, epochs=30):
    daemon = MinerGasDaemon.__new__(MinerGasDaemon)
    daemon.profile = profile
    daemon.node_id = node_id
    daemon.rng = profile.rng("miner-returns", node_id)
    out = []
    for epoch in range(1, epochs + 1):
        planned = daemon.plan_epoch(epoch)
        used = set()
        amounts = []
        for _ in range(planned):
            amount = daemon.distinct_amount(used, epoch)
            used.add(amount)
            amounts.append(amount)
        out.append(amounts)
    return out


class WithoutOverrides(unittest.TestCase):
    def test_key_absent_from_the_resolved_traffic(self):
        profile = load_profile(PLAIN)
        self.assertNotIn("miner_return_overrides", profile.traffic)
        self.assertNotIn("miner_return_overrides", profile.manifest()["traffic"])

    def test_every_miner_uses_the_shared_ranges(self):
        profile = load_profile(PLAIN)
        for epoch in (1, 15, 30):
            self.assertEqual(
                profile.miner_return_ranges("miner-1", epoch),
                (
                    profile.traffic["miner_gas_returns_per_epoch_range"],
                    profile.traffic["restitution_amount_range"],
                ),
            )

    def test_seed_is_the_historical_formula(self):
        profile = load_profile(PLAIN)
        ret_max = profile.traffic["miner_gas_returns_per_epoch_range"][1]
        hi = profile.traffic["restitution_amount_range"][1]
        self.assertEqual(
            profile.miner_seed_gas, round(ret_max * profile.epoch_count * hi * 1.2 + 200, 4)
        )

    def test_draws_match_the_pre_override_daemon(self):
        """The daemon before the option made exactly these calls on the same RNG."""
        profile = load_profile(PLAIN)
        low, high = profile.traffic["miner_gas_returns_per_epoch_range"]
        a_low, a_high = profile.traffic["restitution_amount_range"]
        rng = profile.rng("miner-returns", "miner-2")
        expected = []
        for _ in range(30):
            planned = rng.randint(low, high)
            used, amounts = set(), []
            for _ in range(planned):
                for _ in range(64):
                    amount = round(rng.uniform(a_low, a_high), 2)
                    if amount > 0 and amount not in used:
                        break
                used.add(amount)
                amounts.append(amount)
            expected.append(amounts)
        self.assertEqual(draws(profile, "miner-2"), expected)


class WithOverrides(unittest.TestCase):
    def setUp(self):
        self.profile = load_profile(SWAP)

    def test_phases_take_effect_at_from_epoch(self):
        self.assertEqual(self.profile.miner_return_ranges("miner-1", 14)[0], [16, 20])
        self.assertEqual(self.profile.miner_return_ranges("miner-1", 15)[0], [0, 2])
        self.assertEqual(self.profile.miner_return_ranges("miner-3", 14)[0], [0, 2])
        self.assertEqual(self.profile.miner_return_ranges("miner-3", 15)[0], [16, 20])

    def test_controls_keep_the_shared_ranges_and_their_draws(self):
        plain = load_profile(PLAIN)
        for miner in ("miner-0", "miner-2", "miner-4"):
            self.assertEqual(draws(self.profile, miner), draws(plain, miner))

    def test_treated_draws_stay_in_their_phase_ranges(self):
        for epoch, amounts in enumerate(draws(self.profile, "miner-1"), start=1):
            returns, (low, high) = self.profile.miner_return_ranges("miner-1", epoch)
            self.assertTrue(returns[0] <= len(amounts) <= returns[1])
            self.assertTrue(all(low <= a <= high for a in amounts))

    def test_seed_is_equal_for_all_and_covers_the_largest_range(self):
        # 20 returns x 30 epochs x 250 x 1.2 + 200, as in regional-d025/d075.
        self.assertEqual(self.profile.miner_seed_gas, 180200.0)
        raw = yaml.safe_load(SWAP.read_text(encoding="utf-8"))
        raw["traffic"]["miner_return_overrides"]["miner-1"][0][
            "restitution_amount_range"] = [200.0, 400.0]
        self.assertEqual(load_raw(raw).miner_seed_gas, round(20 * 30 * 400 * 1.2 + 200, 4))

    def test_omitted_range_inherits_the_shared_one(self):
        raw = yaml.safe_load(SWAP.read_text(encoding="utf-8"))
        raw["traffic"]["miner_return_overrides"] = {"miner-0": [{"from_epoch": 5}]}
        profile = load_raw(raw)
        self.assertEqual(
            profile.traffic["miner_return_overrides"]["miner-0"][0]["restitution_amount_range"],
            profile.traffic["restitution_amount_range"],
        )

    def test_malformed_phases_are_rejected(self):
        raw = yaml.safe_load(SWAP.read_text(encoding="utf-8"))
        cases = {
            "not a miner": {"company-1": [{"from_epoch": 1}]},
            "empty phases": {"miner-1": []},
            "epoch zero": {"miner-1": [{"from_epoch": 0}]},
            "epoch past the run": {"miner-1": [{"from_epoch": 31}]},
            "not increasing": {"miner-1": [{"from_epoch": 5}, {"from_epoch": 5}]},
            "unknown key": {"miner-1": [{"from_epoch": 1, "returns": [0, 1]}]},
            "low above high": {"miner-1": [{"from_epoch": 1,
                                            "miner_gas_returns_per_epoch_range": [5, 1]}]},
            "zero amount": {"miner-1": [{"from_epoch": 1,
                                         "restitution_amount_range": [0.0, 1.0]}]},
        }
        for label, overrides in cases.items():
            broken = copy.deepcopy(raw)
            broken["traffic"]["miner_return_overrides"] = overrides
            with self.subTest(label):
                with self.assertRaises(ConfigError):
                    load_raw(broken)


class LikelihoodRatio(unittest.TestCase):
    def shares(self, rounds, seed):
        rng = random.Random(seed)
        with_fb, without_fb = [], []
        for _ in range(rounds):
            base = [rng.uniform(1, 3) for _ in range(4)]
            factor = [rng.choice((0.01, 0.03)) for _ in range(4)]
            weighted = [b * f for b, f in zip(base, factor)]
            with_fb.append([w / sum(weighted) for w in weighted])
            without_fb.append([b / sum(base) for b in base])
        return with_fb, without_fb

    @staticmethod
    def elect(shares, seed):
        rng = random.Random(seed)
        return [rng.choices(range(len(row)), weights=row)[0] for row in shares]

    def test_detects_an_election_that_follows_the_feedback(self):
        with_fb, without_fb = self.shares(1500, 1)
        result = RHO.likelihood_ratio_test(with_fb, without_fb, self.elect(with_fb, 2), 2000, 3)
        self.assertLess(result["p_value_without_feedback"], 0.001)
        self.assertTrue(0.01 < result["quantile_under_feedback"] < 0.99)

    def test_does_not_detect_an_election_that_ignores_it(self):
        with_fb, without_fb = self.shares(1500, 1)
        result = RHO.likelihood_ratio_test(with_fb, without_fb, self.elect(without_fb, 2), 2000, 3)
        self.assertGreater(result["p_value_without_feedback"], 0.01)
        self.assertLess(result["quantile_under_feedback"], 0.001)

    def test_phase_index(self):
        phases = [{"from_epoch": 3}, {"from_epoch": 10}]
        self.assertEqual([RHO.phase_index(phases, e) for e in (1, 3, 9, 10, 30)],
                         [0, 1, 1, 2, 2])


if __name__ == "__main__":
    unittest.main()
