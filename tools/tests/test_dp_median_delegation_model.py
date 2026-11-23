"""Independent finite source-model for OpenDP median-to-quantile wiring.

Pinned upstream: opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
This does not execute OpenDP's Rust or the Polars plugin runtime.
"""
from bisect import bisect_left
from itertools import product
import unittest


ALPHABET = (-2, -1, 0, 1, 2)


def rust_histogram_model(data, candidates, alpha_num=1, alpha_den=2):
    """Translate the histogram logic in score_candidates (ordered candidates)."""
    hist_ro = [0] * (len(candidates) + 1)
    hist_lo = [0] * (len(candidates) + 1)
    for value in data:
        idx_lt = bisect_left(candidates, value)
        hist_lo[idx_lt] += 1
        idx_eq = idx_lt + int(idx_lt < len(candidates) and candidates[idx_lt] == value)
        hist_ro[idx_eq] += 1
    total = sum(hist_lo)
    lt = le = 0
    out = []
    for ro, lo in zip(hist_ro[:-1], hist_lo[:-1]):
        lt += ro
        le += lo
        gt = total - le
        out.append(abs((alpha_den - alpha_num) * lt - alpha_num * gt))
    return out


def median_score_direct(data, candidates):
    return [abs(sum(x < c for x in data) - sum(x > c for x in data))
            for c in candidates]


class MedianDelegationReferenceTests(unittest.TestCase):
    def test_median_alias_matches_half_quantile_score(self):
        checked = 0
        for mask in range(1, 1 << len(ALPHABET)):
            candidates = tuple(value for i, value in enumerate(ALPHABET) if mask & (1 << i))
            for n in range(5):
                for data in product(ALPHABET, repeat=n):
                    self.assertEqual(
                        rust_histogram_model(data, candidates, 1, 2),
                        median_score_direct(data, candidates),
                    )
                    checked += 1
        self.assertEqual(checked, 31 * sum(5 ** n for n in range(5)))

    def test_one_insertion_changes_any_score_by_at_most_one(self):
        checked = 0
        for mask in range(1, 1 << len(ALPHABET)):
            candidates = tuple(value for i, value in enumerate(ALPHABET) if mask & (1 << i))
            for n in range(4):
                for data in product(ALPHABET, repeat=n):
                    old = median_score_direct(data, candidates)
                    for new_value in ALPHABET:
                        new = median_score_direct(data + (new_value,), candidates)
                        self.assertLessEqual(max(abs(a - b) for a, b in zip(new, old)), 1)
                        checked += 1
        self.assertEqual(checked, 31 * sum(5 ** n for n in range(4)) * len(ALPHABET))

    def test_fixed_size_one_replacement_changes_any_score_by_at_most_two(self):
        checked = 0
        for mask in range(1, 1 << len(ALPHABET)):
            candidates = tuple(value for i, value in enumerate(ALPHABET) if mask & (1 << i))
            for n in range(1, 4):
                for data in product(ALPHABET, repeat=n):
                    old = median_score_direct(data, candidates)
                    for idx in range(n):
                        for new_value in ALPHABET:
                            other = data[:idx] + (new_value,) + data[idx + 1:]
                            new = median_score_direct(other, candidates)
                            self.assertLessEqual(max(abs(a - b) for a, b in zip(new, old)), 2)
                            checked += 1
        self.assertEqual(checked, 31 * sum(n * 5 ** n for n in range(1, 4)) * len(ALPHABET))

    def test_ties_are_not_counted_above_or_below(self):
        self.assertEqual(median_score_direct((1, 1, 1), (0, 1, 2)), [3, 0, 3])
        self.assertEqual(rust_histogram_model((1, 1, 1), (0, 1, 2)), [3, 0, 3])


if __name__ == "__main__":
    unittest.main()
