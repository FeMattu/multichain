"""The two profile mistakes that cost a run without ever printing an error of their own.

Both were found the expensive way. A premine above ``maximum-per-output`` leaves the node
mining block 1 and rejecting its own block for ``txout.nValue too high``, once a second,
forever: the chain stays at height 0 and the bootstrap simply stops after the admin
starts. A premine below the funding round gets through the whole fabric, chain and daemon
bring-up and then fails on ``sendtoaddress`` with ``-704``. Neither is visible in the
profile, and both are pure arithmetic — so they belong in the loader.

The third guard is ``runtime.wpoa_debug``, whose cost is quadratic in the epoch count and
which is therefore safe on the smoke profiles it was written for and ruinous on a campaign.
"""

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "bootstrap"))

import yaml  # noqa: E402

from config_loader import (  # noqa: E402
    WPOA_DEBUG_BUDGET_BYTES,
    ConfigError,
    load_profile,
)

ROOT = Path(__file__).resolve().parent.parent
PROFILES = ROOT / "config" / "profiles"
BASE = PROFILES / "native" / "small.yaml"


class _Harness(unittest.TestCase):
    def profile(self, **sections):
        """``native/small.yaml`` with sections merged in, loaded from a temp file."""
        import tempfile

        raw = yaml.safe_load(BASE.read_text(encoding="utf-8"))
        for name, patch in sections.items():
            raw.setdefault(name, {}).update(patch)
        tmp = Path(tempfile.mkdtemp()) / "profile.yaml"
        tmp.write_text(yaml.safe_dump(raw), encoding="utf-8")
        return load_profile(str(tmp))


class TestPremineCeiling(_Harness):
    def test_premine_above_max_per_output_is_refused(self):
        with self.assertRaises(ConfigError) as ctx:
            self.profile(chain={"first-block-reward": 350_000_000_000_000})
        message = str(ctx.exception)
        self.assertIn("maximum-per-output", message)
        self.assertIn("txout.nValue too high", message)

    def test_raising_the_ceiling_with_it_is_accepted(self):
        profile = self.profile(
            chain={
                "maximum-per-output": 400_000_000_000_000,
                "first-block-reward": 350_000_000_000_000,
            }
        )
        self.assertEqual(profile.premine, 3_500_000)
        self.assertEqual(profile.max_per_output, 4_000_000)

    def test_exactly_at_the_ceiling_is_accepted(self):
        # The node's own check is "too high", not "too high or equal".
        profile = self.profile(
            chain={
                "maximum-per-output": 350_000_000_000_000,
                "first-block-reward": 350_000_000_000_000,
            }
        )
        self.assertEqual(profile.premine, profile.max_per_output)

    def test_maximum_per_output_reaches_params_dat(self):
        profile = self.profile(
            chain={
                "maximum-per-output": 400_000_000_000_000,
                "first-block-reward": 350_000_000_000_000,
            }
        )
        overrides = profile.params_overrides()
        self.assertEqual(overrides["maximum-per-output"], "400000000000000")


class TestFundingRound(_Harness):
    def test_demand_above_the_premine_is_refused(self):
        # The regional-long28h shape: three maxima multiplied together.
        with self.assertRaises(ConfigError) as ctx:
            self.profile(
                epochs={"count": 100},
                traffic={
                    "miner_gas_returns_per_epoch_range": [0, 20],
                    "restitution_amount_range": [50.0, 250.0],
                },
            )
        message = str(ctx.exception)
        self.assertIn("-704", message)
        self.assertIn("miner_seed_gas", message)

    def test_gas_demand_matches_what_seed_gas_would_send(self):
        profile = self.profile()
        others = profile.node_count - 1 - profile.miner_count
        self.assertAlmostEqual(
            profile.gas_demand,
            profile.miner_count * profile.miner_seed_gas + others * profile.gas_seed,
            places=4,
        )


class TestWpoaDebugBudget(_Harness):
    def test_off_costs_nothing(self):
        self.assertEqual(self.profile().wpoa_debug_projected_bytes, 0.0)

    def test_on_is_fine_on_a_short_profile(self):
        profile = self.profile(runtime={"wpoa_debug": True})
        self.assertGreater(profile.wpoa_debug_projected_bytes, 0.0)
        self.assertLess(profile.wpoa_debug_projected_bytes, WPOA_DEBUG_BUDGET_BYTES)

    def test_on_is_refused_on_a_campaign_profile(self):
        with self.assertRaises(ConfigError) as ctx:
            self.profile(
                epochs={"count": 100, "length_blocks": 100},
                chain={"target-block-time": 10},
                runtime={"wpoa_debug": True},
            )
        self.assertIn("wpoa_debug", str(ctx.exception))

    def test_cost_is_quadratic_in_the_epoch_count(self):
        """Doubling the epochs quadruples the per-epoch total, which is the whole point:
        a flag that is free at 5 epochs is not merely twice as expensive at 10."""
        short = self.profile(epochs={"count": 10}, runtime={"wpoa_debug": True})
        long = self.profile(epochs={"count": 20}, runtime={"wpoa_debug": True})
        ratio = long.wpoa_debug_projected_bytes / short.wpoa_debug_projected_bytes
        self.assertAlmostEqual(ratio, 4.0, places=6)


class TestShippedProfiles(unittest.TestCase):
    def test_every_shipped_profile_still_loads(self):
        paths = sorted(PROFILES.glob("*/*.yaml"))
        self.assertGreater(len(paths), 20)
        for path in paths:
            with self.subTest(profile=path.name):
                profile = load_profile(str(path))
                self.assertLessEqual(profile.gas_demand, profile.premine)
                self.assertLessEqual(profile.premine, profile.max_per_output)
                self.assertLessEqual(
                    profile.wpoa_debug_projected_bytes, WPOA_DEBUG_BUDGET_BYTES
                )


if __name__ == "__main__":
    unittest.main()
