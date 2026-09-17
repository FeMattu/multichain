"""The malus-specific statistics and the effective-weight recomputation.

The recomputation matters most: the invariant audit compares the node's reported ``w_eff``
against ``_effective_weight`` here, so this must match ``MalusAccumulator::EffectiveWeight``
in the C++ branch for branch — a divergence would make the audit test the test, not the node.
"""

import sys
import unittest
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_ROOT / "analysis"))

from pipeline.stat import malus as MAL  # noqa: E402
from pipeline.phase2_aggregate import _effective_weight  # noqa: E402


class TestEffectiveWeight(unittest.TestCase):
    def test_psi_one_returns_raw(self):
        self.assertEqual(_effective_weight(100, 1.0), 100.0)

    def test_psi_zero_excludes(self):
        self.assertEqual(_effective_weight(100, 0.0), 0.0)

    def test_zero_weight(self):
        self.assertEqual(_effective_weight(0, 0.5), 0.0)

    def test_rounds_half_up(self):
        self.assertEqual(_effective_weight(100, 0.5), 50.0)
        self.assertEqual(_effective_weight(101, 0.5), 51.0)   # 50.5 -> 51

    def test_positive_psi_never_zeroes(self):
        # A tiny positive product must round to at least 1, mirroring the C++ guard.
        self.assertEqual(_effective_weight(1, 0.001), 1.0)

    def test_missing_inputs(self):
        self.assertIsNone(_effective_weight(None, 0.5))
        self.assertIsNone(_effective_weight(100, None))


class TestDetectionMetrics(unittest.TestCase):
    def test_perfect(self):
        m = MAL.detection_metrics(true_positive=5, false_positive=0, false_negative=0)
        self.assertEqual(m["precision"], 1.0)
        self.assertEqual(m["recall"], 1.0)
        self.assertEqual(m["f1"], 1.0)

    def test_with_misses_and_false_alarms(self):
        m = MAL.detection_metrics(true_positive=3, false_positive=1, false_negative=2)
        self.assertAlmostEqual(m["precision"], 0.75)
        self.assertAlmostEqual(m["recall"], 0.6)
        self.assertAlmostEqual(m["f1"], 2 * 0.75 * 0.6 / (0.75 + 0.6))

    def test_no_reports_precision_none(self):
        m = MAL.detection_metrics(0, 0, 4)
        self.assertIsNone(m["precision"])   # no reports at all
        self.assertEqual(m["recall"], 0.0)
        self.assertIsNone(m["f1"])

    def test_nothing_to_detect(self):
        m = MAL.detection_metrics(0, 0, 0)
        self.assertIsNone(m["precision"])
        self.assertIsNone(m["recall"])
        self.assertIsNone(m["f1"])


class TestLatency(unittest.TestCase):
    def test_summary(self):
        s = MAL.latency_summary([1, 2, 3, 4])
        self.assertEqual(s["n"], 4)
        self.assertEqual(s["min"], 1)
        self.assertEqual(s["max"], 4)
        self.assertEqual(s["median"], 2.5)

    def test_empty(self):
        s = MAL.latency_summary([])
        self.assertEqual(s["n"], 0)
        self.assertIsNone(s["median"])

    def test_ignores_none(self):
        s = MAL.latency_summary([1, None, 3])
        self.assertEqual(s["n"], 2)

    def test_ecdf_monotone(self):
        steps = MAL.ecdf([3, 1, 2])
        self.assertEqual([p["x"] for p in steps], [1, 2, 3])
        self.assertEqual(steps[-1]["f"], 1.0)


class TestRateConvergence(unittest.TestCase):
    def test_on_target_inside_ci(self):
        r = MAL.rate_convergence(0.15, 0.15, 100)
        self.assertTrue(r["target_inside"])
        self.assertEqual(r["abs_error"], 0.0)

    def test_far_off_outside_ci(self):
        r = MAL.rate_convergence(0.15, 0.9, 100)
        self.assertFalse(r["target_inside"])

    def test_no_opportunities(self):
        r = MAL.rate_convergence(0.15, None, 0)
        self.assertIsNone(r["target_inside"])


class TestRelativeChange(unittest.TestCase):
    def test_basic(self):
        self.assertAlmostEqual(MAL.relative_change(100, 50), -0.5)

    def test_zero_base_none(self):
        self.assertIsNone(MAL.relative_change(0, 50))
        self.assertIsNone(MAL.relative_change(None, 50))


if __name__ == "__main__":
    unittest.main()
