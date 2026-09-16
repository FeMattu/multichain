#!/usr/bin/env python3
"""Check the hand-written special functions against a reference implementation.

``stat/`` deliberately imports no ``scipy`` and no ``statsmodels``: a thesis result whose
p-value depends on which version of a library happened to be installed is harder to defend
than one whose arithmetic is visible in the file. The cost of that choice is that the
closed forms have to be *shown* to be right rather than assumed, and this script is where
that happens.

It is the **only** file in the harness that imports ``scipy``, and it imports it as an
oracle, never as a dependency: nothing in the pipeline calls this, and a machine without
scipy runs every analysis perfectly well and simply cannot run this check.

    python3 test/analysis/pipeline/tools/verify_stat_closed_forms.py

Exit code 0 when every value agrees within tolerance, 1 otherwise. Run it after touching
anything in ``stat/__init__.py``.
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path
from typing import Any, List, Optional

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from pipeline.stat import (  # noqa: E402
    Z95,
    betainc,
    binom_sf_inclusive,
    chi2_sf,
    kolmogorov_sf,
    pearson,
    spearman,
    t_sf_two_sided,
)
from pipeline.stat.concentration import (  # noqa: E402
    gini,
    hhi,
    n_eff,
    nakamoto,
    normalized_entropy,
)
from pipeline.stat.wilson import wilson_interval  # noqa: E402


class Checker:
    def __init__(self, tolerance: float) -> None:
        self.tolerance = tolerance
        self.failures: List[str] = []
        self.checked = 0

    def close(self, ours: Optional[float], reference: float, label: str) -> None:
        self.checked += 1
        if ours is None or not math.isfinite(float(ours)):
            self.failures.append("%s: ours is %r" % (label, ours))
            status = "MISSING"
        else:
            scale = max(1.0, abs(reference))
            ok = abs(float(ours) - reference) <= self.tolerance * scale
            status = "ok" if ok else "MISMATCH"
            if not ok:
                self.failures.append(
                    "%s: ours=%.17g reference=%.17g" % (label, float(ours), reference)
                )
        print("  %-40s %-24.15g %-24.15g %s"
              % (label, float(ours) if ours is not None else float("nan"), reference, status))

    def equal(self, ours: Any, reference: Any, label: str) -> None:
        self.checked += 1
        ok = ours == reference
        if not ok:
            self.failures.append("%s: ours=%r reference=%r" % (label, ours, reference))
        print("  %-40s %-24s %-24s %s" % (label, ours, reference, "ok" if ok else "MISMATCH"))


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--tolerance", type=float, default=1e-9)
    args = parser.parse_args(argv)

    try:
        from scipy import stats
    except ImportError:
        print(
            "scipy is not installed, so this cross-check cannot run.\n"
            "That is not a problem for the harness: nothing in the analysis pipeline "
            "imports scipy, and every phase runs without it. This script exists only to "
            "demonstrate that the closed forms in stat/ agree with a reference.",
            file=sys.stderr,
        )
        return 0

    checker = Checker(args.tolerance)
    header = "  %-40s %-24s %-24s %s" % ("quantity", "stat/", "scipy", "")

    print("chi-square survival function")
    print(header)
    for x, df in [(3.84, 1), (0.5, 1), (17.566, 2), (10.0, 5), (1.0, 10), (50.0, 3), (1e-3, 1)]:
        checker.close(chi2_sf(x, df), stats.chi2.sf(x, df), "chi2_sf(%g, %d)" % (x, df))

    print("\nStudent's t, two-sided tail")
    print(header)
    for t, df in [(2.0, 10), (0.5, 3), (4.5, 25), (1.96, 1000)]:
        checker.close(
            t_sf_two_sided(t, df), 2 * stats.t.sf(abs(t), df), "t_sf_two_sided(%g, %d)" % (t, df)
        )

    print("\nexact binomial upper tail")
    print(header)
    for k, n, p in [(7, 10, 0.5), (0, 5, 0.3), (12, 12, 0.9), (3, 20, 0.1)]:
        checker.close(
            binom_sf_inclusive(k, n, p),
            stats.binom.sf(k - 1, n, p),
            "P(X>=%d | %d, %g)" % (k, n, p),
        )

    print("\nKolmogorov limit distribution")
    print(header)
    for lam in [0.5, 1.0, 1.5, 2.0]:
        checker.close(kolmogorov_sf(lam), stats.kstwobign.sf(lam), "Q(%g)" % lam)

    print("\nregularised incomplete beta")
    print(header)
    for a, b, x in [(2, 3, 0.4), (0.5, 0.5, 0.7), (5, 1, 0.9)]:
        checker.close(betainc(a, b, x), stats.beta.cdf(x, a, b), "I_%g(%g, %g)" % (x, a, b))

    print("\ncorrelation")
    print(header)
    xs = [1, 2, 3, 4, 5, 6, 7]
    ys = [2, 1, 4, 3, 7, 5, 8]
    r, p_value, _ = pearson(xs, ys)
    reference_r = stats.pearsonr(xs, ys)
    checker.close(r, reference_r[0], "pearson r")
    checker.close(p_value, reference_r[1], "pearson p")
    rho, p_rho, _ = spearman(xs, ys)
    reference_rho = stats.spearmanr(xs, ys)
    checker.close(rho, reference_rho.correlation, "spearman rho")
    checker.close(p_rho, reference_rho.pvalue, "spearman p")

    print("\nWilson score interval (against its own closed form)")
    print(header)
    for k, n in [(0, 10), (9, 10), (1, 12), (5, 5)]:
        low, high = wilson_interval(k, n)
        p_hat = k / n
        z2 = Z95 * Z95
        denominator = 1 + z2 / n
        centre = (p_hat + z2 / (2 * n)) / denominator
        half = Z95 * math.sqrt(p_hat * (1 - p_hat) / n + z2 / (4 * n * n)) / denominator
        checker.close(low, max(0.0, centre - half), "wilson low %d/%d" % (k, n))
        checker.close(high, min(1.0, centre + half), "wilson high %d/%d" % (k, n))

    print("\nconcentration indices (against their definitions)")
    print(header)
    checker.close(hhi([1, 1, 1, 1]), 0.25, "HHI, four equal")
    checker.close(n_eff([1, 1, 1, 1]), 4.0, "N_eff, four equal")
    checker.close(hhi([0.7, 0.1, 0.1, 0.1]), 0.52, "HHI, one dominant")
    checker.close(n_eff([0.7, 0.1, 0.1, 0.1]), 1.0 / 0.52, "N_eff, one dominant")
    checker.close(gini([1, 1, 1, 1]), 0.0, "Gini, four equal")
    checker.close(normalized_entropy([1, 1, 1, 1]), 1.0, "normalised entropy, four equal")
    checker.equal(nakamoto([0.7, 0.1, 0.1, 0.1], 0.5), 1, "Nakamoto 1/2, one dominant")
    checker.equal(nakamoto([1, 1, 1, 1], 2.0 / 3.0), 3, "Nakamoto 2/3, four equal")

    print()
    if checker.failures:
        print("%d of %d checks FAILED:" % (len(checker.failures), checker.checked))
        for failure in checker.failures:
            print("  - %s" % failure)
        return 1
    print("all %d checks agree within %g relative tolerance" % (checker.checked, args.tolerance))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
