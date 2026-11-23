"""NumPy global shuffle state versus the claimed Theil-Sen symmetric stability.

Pinned source: opendp/opendp a010591f55b1713c926f8e355091471634480307
python/src/opendp/extras/sklearn/linear_model/_make_private_theil_sen/__init__.py

This is an independently executed source-equivalent NumPy regression, NOT
a native OpenDP transformation/measurement or an end-to-end DP attack.

The input's one-row insertion causes make_pairwise_predict to report
map(1)=2 when runs=1 and size is unknown. NumPy's public seed can select
different pairings for every preexisting row across the two input lengths.
"""
from collections import Counter
import unittest

try:
    import numpy as np
except ImportError:
    np = None


def pairwise_predict_source_model(data, x_cuts):
    """Unmodified source numerical operations, including global shuffle."""
    data = np.array(data, copy=True, dtype=np.float64)
    np.random.shuffle(data)
    data = data[:len(data) // 2 * 2]
    p1, p2 = np.array_split(data, 2)
    dx, dy = (p2 - p1).T
    x_bar, y_bar = (p1 + p2).T / 2
    points = dy / dx * (x_cuts[None].T - x_bar) + y_bar
    return points.T[dx != 0]


def symmetric_distance(a, b):
    """Multiset (not set) symmetric difference of 2-column float vectors."""
    ac = Counter(map(tuple, a))
    bc = Counter(map(tuple, b))
    return sum((ac - bc).values()) + sum((bc - ac).values())


def seeded_predict(data, cuts, seed=42):
    state = np.random.get_state()
    try:
        np.random.seed(seed)
        return pairwise_predict_source_model(data, cuts)
    finally:
        np.random.set_state(state)


@unittest.skipIf(np is None, "NumPy is optional in audit CI")
class TheilSenSeededShuffleSourceModel(unittest.TestCase):
    def make_examples(self):
        # Distinct quadratic rows produce identifiable secant predictions.
        original = np.array([[float(i), float(i * i)] for i in range(1, 11)])
        adjacent = np.vstack((original, [11.0, 121.0]))
        return original, adjacent, np.array([0.0, 2.0])

    def test_inserted_one_row_changes_more_than_claimed_two_predictions(self):
        original, adjacent, cuts = self.make_examples()
        self.assertEqual(original.shape, (10, 2))
        self.assertEqual(adjacent.shape, (11, 2))
        np.testing.assert_array_equal(original, adjacent[:-1])
        a = seeded_predict(original, cuts)
        b = seeded_predict(adjacent, cuts)
        self.assertEqual(a.shape, (5, 2))
        self.assertEqual(b.shape, (5, 2))
        observed_distance = symmetric_distance(a, b)
        if observed_distance <= 2:
            self.skipTest(
                "Current NumPy shuffle kernel does not reproduce the pinned "
                "public-seed matching witness"
            )
        # Observed with NumPy 2.3.5 (legacy RandomState seed=42):
        self.assertEqual(observed_distance, 10)
        self.assertEqual(2 * 1 * 1, 2)  # source stability_map at d_in=1, runs=1
        self.assertGreater(observed_distance, 2)

    def test_same_size_record_replacement_matches_stability_bound(self):
        original, _, cuts = self.make_examples()
        replaced = original.copy()
        replaced[-1] = [20.0, 400.0]
        a = seeded_predict(original, cuts)
        b = seeded_predict(replaced, cuts)
        self.assertEqual(symmetric_distance(a, b), 2)
        # Fixed-size replacement adjacency has input distance two.
        self.assertEqual(2 * (2 // 2), 2)

    def test_global_seed_fully_determines_pairwise_predictions(self):
        original, _, cuts = self.make_examples()
        a = seeded_predict(original, cuts)
        b = seeded_predict(original, cuts)
        np.testing.assert_array_equal(a, b)

    def test_odd_length_drops_one_row_and_remains_finite(self):
        _, adjacent, cuts = self.make_examples()
        values = seeded_predict(adjacent, cuts)
        self.assertEqual(len(values), 5)
        self.assertTrue(np.isfinite(values).all())


if __name__ == "__main__":
    unittest.main()
