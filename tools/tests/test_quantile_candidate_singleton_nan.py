"""Abstract model of OpenDP check_candidates; not a compiled Rust test.

Pinned upstream: ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""
import math
import random
import unittest


def source_check_candidates(candidates):
    """Model `!empty && !windows(2).any(left.partial_cmp(right) != Less)`."""
    return bool(candidates) and all(
        left < right for left, right in zip(candidates, candidates[1:])
    )


def total_order_contract(candidates):
    return bool(candidates) and all(not math.isnan(c) for c in candidates) and all(
        left < right for left, right in zip(candidates, candidates[1:])
    )


class CheckCandidatesModel(unittest.TestCase):
    def test_source_accepts_singleton_nan_against_contract(self):
        self.assertTrue(source_check_candidates([float('nan')]))
        self.assertFalse(total_order_contract([float('nan')]))

    def test_ordinary_valid_and_invalid_cases(self):
        for case in [[-math.inf], [math.inf], [0.0], [-1.0, 0.0, 1.0],
                     [0.0, 1.0], [-math.inf, math.inf]]:
            self.assertTrue(source_check_candidates(case), case)
            self.assertTrue(total_order_contract(case), case)
        for case in [[], [1.0, 1.0], [2.0, 1.0], [1.0, math.nan],
                     [math.nan, 1.0], [0.0, math.nan, 1.0],
                     [math.nan, math.nan]]:
            self.assertFalse(source_check_candidates(case), case)
            self.assertFalse(total_order_contract(case), case)

    def test_10k_random_sequences_characterize_only_exception(self):
        rng = random.Random(20261123)
        mismatch = 0
        for _ in range(10000):
            n = rng.randrange(5)
            candidates = [float('nan') if rng.randrange(10) == 0
                          else float(rng.randrange(-3, 4)) for _ in range(n)]
            actual = source_check_candidates(candidates)
            desired = total_order_contract(candidates)
            if actual != desired:
                mismatch += 1
                self.assertEqual(len(candidates), 1)
                self.assertTrue(math.isnan(candidates[0]))
        self.assertGreater(mismatch, 0)


if __name__ == '__main__':
    unittest.main()
