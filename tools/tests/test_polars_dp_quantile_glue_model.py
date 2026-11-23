"""Independent model of the Polars DP-quantile constructor's public glue.

This is NOT an implementation of a differential privacy mechanism, nor does
it execute OpenDP or Polars. It checks only the public-median imputation,
score-vector length and shape, and deterministic index postprocessing at
the selected constructor boundary (upstream ef1a238634d6196b01a1a1e77d3d5ad2340e3094).

The known upstream singleton-NaN candidate validator defect (#3243 PR)
is outside this model's admitted public-candidate precondition.
"""

from fractions import Fraction
from itertools import product
from math import isnan
import random
import unittest


def public_candidate_median(candidates):
    if not candidates:
        raise ValueError("candidate list must be nonempty")
    if any(c is None or isinstance(c, float) and isnan(c) for c in candidates):
        raise ValueError("invalid candidate")
    if any(a >= b for a, b in zip(candidates, candidates[1:])):
        raise ValueError("candidate list must be strictly increasing")
    mid = len(candidates) // 2
    if len(candidates) % 2:
        return Fraction(candidates[mid])
    return (Fraction(candidates[mid - 1]) + Fraction(candidates[mid])) / 2


def public_impute(values, candidates, *, float_data):
    filler = public_candidate_median(candidates)
    return tuple(
        filler if value is None or float_data and isinstance(value, float)
        and isnan(value) else Fraction(value)
        for value in values
    )


def score_half(values, candidates):
    """Current discrete-score formula for alpha=1/2, ignoring common scaling."""
    return tuple(
        abs(sum(value < c for value in values) -
            sum(value > c for value in values))
        for c in candidates
    )


def candidate_from_index(candidates, index):
    return candidates[index]


class TestDPQuantileGlueReference(unittest.TestCase):
    CANDS = (0, 10, 20, 30)

    def test_even_candidate_median_is_public_and_not_always_candidate(self):
        self.assertEqual(public_candidate_median(self.CANDS), Fraction(15))
        self.assertNotIn(public_candidate_median(self.CANDS), self.CANDS)
        self.assertEqual(public_candidate_median((0,)), Fraction(0))

    def test_optional_float_input_uses_same_public_filler(self):
        a = public_impute((None, 20, float("nan"), 5), self.CANDS, float_data=True)
        b = public_impute((3, None), self.CANDS, float_data=True)
        self.assertEqual(a, (15, 20, 15, 5))
        self.assertEqual(b, (3, 15))
        self.assertEqual(len(a), 4)
        self.assertEqual(len(b), 2)

    def test_scores_are_permutation_invariant_and_fixed_length(self):
        values = (None, 3, 22, 10)
        filled = public_impute(values, self.CANDS, float_data=False)
        expected = score_half(filled, self.CANDS)
        self.assertEqual(len(expected), len(self.CANDS))
        for rotated in ((3, 22, 10, None), (10, 3, None, 22)):
            got = score_half(
                public_impute(rotated, self.CANDS, float_data=False),
                self.CANDS,
            )
            self.assertEqual(expected, got)

    def test_score_linf_bounds_on_single_row_insert_or_replacement(self):
        # For alpha 1/2 (numerator=1, denominator=2), inserting one
        # record changes each integer score coordinate by at most one.
        # Replacing one record is two insert/delete edits.
        values = (None, 0, 5, 15, 20, 30)
        for length in range(4):
            for data in product(values, repeat=length):
                base = score_half(
                    public_impute(data, self.CANDS, float_data=False),
                    self.CANDS,
                )
                for val in values:
                    extension = score_half(
                        public_impute(data + (val,), self.CANDS, float_data=False),
                        self.CANDS,
                    )
                    self.assertLessEqual(
                        max(abs(a - b) for a, b in zip(base, extension)), 1
                    )
                if length:
                    for replacement in values:
                        changed = score_half(
                            public_impute(data[:-1] + (replacement,), self.CANDS,
                                          float_data=False),
                            self.CANDS,
                        )
                        self.assertLessEqual(
                            max(abs(a - b) for a, b in zip(base, changed)), 2
                        )

    def test_selected_noisy_index_is_only_a_public_candidate(self):
        rng = random.Random(20261123)
        # The noise and its privacy proof are explicitly NOT modeled.
        # A real NoisyMax index is required to be in [0, len(candidates)).
        for _ in range(300):
            index = rng.randrange(len(self.CANDS))
            self.assertIn(candidate_from_index(self.CANDS, index), self.CANDS)

    def test_public_preconditions_for_empty_duplicate_unsorted_candidates(self):
        for invalid in ((), (1, 1), (2, 1), (None, 2), (float("nan"), 2)):
            with self.assertRaises(ValueError):
                public_candidate_median(invalid)


if __name__ == "__main__":
    unittest.main()
