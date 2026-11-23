"""Reference-model boundary checks for OpenDP count/CDF postprocessors.

These tests translate relevant Rust guards and index operations from
opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094; they do not
execute OpenDP's Rust library or prove any differential privacy claim.
"""

import math
import unittest


def accepted_bin_edges(edges):
    # Mirrors `len().is_zero()` and `windows(2).any(|w| w[0] >= w[1])`.
    return bool(edges) and not any(a >= b for a, b in zip(edges, edges[1:]))


def accepted_alphas(alphas):
    # Mirrors windows sortedness, first.is_sign_negative(), last > one.
    # A NaN in an interior position bypasses all four guards independent of sign.
    return (
        not any(a >= b for a, b in zip(alphas, alphas[1:]))
        and not (alphas and math.copysign(1.0, alphas[0]) < 0)
        and not (alphas and alphas[-1] > 1.0)
    )


def last_cumulative_count(values):
    """Python translation of the unguarded cumsum[cumsum.len() - 1]."""
    total = 0.0
    cumsum = []
    for value in values:
        total += value
        cumsum.append(total)
    return cumsum[len(cumsum) - 1]


def quantile_shape_is_accepted(bin_edges, raw_counts):
    return abs(len(bin_edges) - len(raw_counts)) == 1


def effective_counts(bin_edges, raw_counts):
    if len(bin_edges) + 1 == len(raw_counts):
        return raw_counts[1:-1]
    return raw_counts


class TestCountCdfBoundaryModel(unittest.TestCase):
    def test_cdf_empty_input_reaches_unguarded_index(self):
        with self.assertRaises(IndexError):
            last_cumulative_count([])
        self.assertEqual(last_cumulative_count([2.0, 3.0]), 5.0)

    def test_quantile_constructor_accepts_shape_without_central_bin(self):
        edges, counts = [5.0], [7.0, 9.0]
        self.assertTrue(accepted_bin_edges(edges))
        self.assertTrue(quantile_shape_is_accepted(edges, counts))
        trimmed = effective_counts(edges, counts)
        self.assertEqual(trimmed, [])
        with self.assertRaises(IndexError):
            last_cumulative_count(trimmed)

    def test_interior_nan_alpha_passes_all_guards(self):
        self.assertTrue(accepted_alphas([0.0, math.nan, 1.0]))
        self.assertFalse(accepted_alphas([0.0, 0.4, 0.4, 1.0]))
        self.assertFalse(accepted_alphas([-0.1, 0.5]))
        self.assertFalse(accepted_alphas([0.5, 1.1]))

    def test_nan_bin_edge_passes_sortedness_check(self):
        self.assertTrue(accepted_bin_edges([0.0, math.nan, 2.0]))
        self.assertFalse(accepted_bin_edges([0.0, 0.0, 2.0]))
        self.assertFalse(accepted_bin_edges([]))


if __name__ == "__main__":
    unittest.main()
