"""Independent finite reference checks for quantile candidate scoring.

This reproduces the integer histogram implementation in OpenDP at pinned
upstream commit ef1a238634d6196b01a1a1e77d3d5ad2340e3094, not native Rust.
The checks cover a bounded finite model and do not establish a general proof.
"""

from bisect import bisect_left, bisect_right
from collections import Counter
from itertools import product
import unittest


CANDIDATES = (-1, 0, 1)
ALPHAS = ((0, 1), (1, 3), (1, 2), (2, 3), (1, 1))
LIMITS = (1, 2, 3)
DATASETS = tuple(t for n in range(4) for t in product(CANDIDATES, repeat=n))


def rust_histogram_model(data, candidates, numerator, denominator, limit):
    """Translate score_candidates' histograms and cumulative-score arithmetic."""
    hist_ro = [0] * (len(candidates) + 1)
    hist_lo = [0] * (len(candidates) + 1)
    for value in data:
        hist_lo[bisect_left(candidates, value)] += 1
        hist_ro[bisect_right(candidates, value)] += 1
    n = sum(hist_lo)
    hist_ro.pop()
    hist_lo.pop()
    lt = le = 0
    result = []
    for ro, lo in zip(hist_ro, hist_lo):
        lt += ro
        le += lo
        gt = n - le
        result.append(abs((denominator - numerator) * min(lt, limit)
                          - numerator * min(gt, limit)))
    return tuple(result)


def specification(data, candidates, numerator, denominator, limit):
    """Reference formula derived from the scorer's rank-distance definition."""
    return tuple(abs((denominator - numerator) * min(sum(v < c for v in data), limit)
                     - numerator * min(sum(v > c for v in data), limit))
                 for c in candidates)


def symmetric_distance(a, b):
    """Small multiset symmetric difference: insertions plus deletions."""
    ca, cb = Counter(a), Counter(b)
    return sum((ca - cb).values()) + sum((cb - ca).values())


class TestQuantileScoreModel(unittest.TestCase):
    def test_histogram_matches_independent_rank_formula(self):
        for numerator, denominator in ALPHAS:
            for limit in LIMITS:
                for data in DATASETS:
                    self.assertEqual(
                        rust_histogram_model(data, CANDIDATES, numerator, denominator, limit),
                        specification(data, CANDIDATES, numerator, denominator, limit),
                    )

    def test_bounded_exhaustive_stability(self):
        """24,000 ordered pairs; fixed-size pairs test the tighter bound."""
        checked = 0
        for numerator, denominator in ALPHAS:
            for limit in LIMITS:
                scored = {data: rust_histogram_model(
                    data, CANDIDATES, numerator, denominator, limit)
                    for data in DATASETS}
                for a in DATASETS:
                    for b in DATASETS:
                        sym = symmetric_distance(a, b)
                        linf = max(abs(x - y) for x, y in zip(scored[a], scored[b]))
                        self.assertLessEqual(linf, sym * max(numerator, denominator - numerator))
                        if len(a) == len(b):
                            self.assertLessEqual(linf, sym // 2 * denominator)
                        checked += 1
        self.assertEqual(checked, 24_000)

    def test_published_proof_postcondition_has_wrong_coefficient(self):
        """At alpha=1/2, x=[0], c=1, code returns 1; proof states 2."""
        result = rust_histogram_model((0,), (1,), 1, 2, 1)
        proof_formula = abs(2 * 1 - 1 * 0)
        self.assertEqual(result, (1,))
        self.assertEqual(proof_formula, 2)
        self.assertNotEqual(result[0], proof_formula)


if __name__ == "__main__":
    unittest.main()
