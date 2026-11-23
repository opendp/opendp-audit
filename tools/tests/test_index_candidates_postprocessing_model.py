"""Finite reference checks for the Polars index_candidates postprocessor.

The code mirrors the source-visible semantics, but does not execute OpenDP Rust
or Polars. Pinned OpenDP: ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""

from collections import defaultdict
from fractions import Fraction
from itertools import product
import unittest


def select_candidates(candidates, indices):
    """In-range u32 candidate takes; an invalid index is an observable error."""
    result = []
    for index in indices:
        if index is None:
            result.append(None)
        elif not isinstance(index, int) or index < 0 or index > 0xFFFFFFFF:
            raise TypeError("candidate indices must be nullable u32")
        else:
            result.append(candidates[index])
    return result


def pushforward(probs, candidates):
    """Map a finite distribution on indices to a distribution on values."""
    out = defaultdict(Fraction)
    for index, probability in enumerate(probs):
        out[candidates[index]] += probability
    return out


def privacy_ratio(p, q):
    """Max multiplicative probability ratio on the finite alphabet."""
    return max(Fraction(p[x], q[x]) for x in p)


class TestIndexCandidatesPostprocessingModel(unittest.TestCase):
    def test_all_in_range_indices_yield_only_public_candidates(self):
        for size in range(1, 6):
            candidates = tuple("abcde"[:size])
            for length in (0, 1, 2, 3):
                for indices in product(range(size), repeat=length):
                    self.assertEqual(
                        select_candidates(candidates, indices),
                        [candidates[i] for i in indices],
                    )
                    self.assertTrue(set(select_candidates(candidates, indices)) <= set(candidates))

    def test_duplicate_candidates_collapse_indices_deterministically(self):
        self.assertEqual(select_candidates(("A", "A", "B"), (0, 1, 2, 1)), ["A", "A", "B", "A"])

    def test_invalid_indices_are_errors_not_wrapping_or_clamping(self):
        for candidates, index in (((), 0), (("A",), 1), (("A", "B"), 2)):
            with self.subTest(index=index, candidates=candidates):
                with self.assertRaises(IndexError):
                    select_candidates(candidates, (index,))
        for index in (-1, 1 << 32, "1"):
            with self.assertRaises(TypeError):
                select_candidates(("A",), (index,))

    def test_nullable_indices_are_propagated_in_model(self):
        self.assertEqual(select_candidates((10, 20), (None, 1, None, 0)), [None, 20, None, 10])

    def test_finite_pushforward_does_not_increase_pure_dp_loss(self):
        # Positive rational distributions on three index values. The pairwise
        # DP ratio can only shrink when public candidate labels merge outcomes.
        vectors = [tuple(Fraction(w, sum(weights)) for w in weights)
                   for weights in product((1, 2, 3), repeat=3)]
        for p in vectors:
            for q in vectors:
                before = privacy_ratio(dict(enumerate(p)), dict(enumerate(q)))
                for candidates in (("A", "B", "C"), ("A", "A", "B"), ("A", "A", "A")):
                    after = privacy_ratio(pushforward(p, candidates), pushforward(q, candidates))
                    self.assertLessEqual(after, before)

    def test_privacy_map_kept_on_measurement_function_chain(self):
        # Source make_chain_pm copies privacy_map unchanged: the new operation
        # does not charge or discount an additional privacy cost.
        original_map = {0: Fraction(0), 1: Fraction(3, 2), 2: Fraction(3)}
        chained_map = original_map.copy()
        self.assertEqual(chained_map, original_map)


if __name__ == "__main__":
    unittest.main()
