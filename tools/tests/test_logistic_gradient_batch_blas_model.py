"""Source-equivalent OpenDP logistic-regression rowwise-gradient stability model.

Pinned upstream: a010591f55b1713c926f8e355091471634480307.
Observed on NumPy 2.3.5, SciPy 1.17.0, OpenBLAS 0.3.30, x86-64 SkylakeX.

This does not invoke native OpenDP. The failing numerical property is
platform-dependent because NumPy/BLAS selects different reduction strategies
depending on the number and position of rows. The regression *skips* if the
current NumPy/BLAS does not reproduce the particular cancellation witness.
"""
import math
import unittest

try:
    import numpy as np
    from scipy.special import expit
except ImportError:
    np = None
    expit = None

THETA = [1e16, -1e16, -10.0, 3.0, -3.0, 0.0, -1.0, 10.0]


def per_example_gradients_model(X, y, theta, fit_intercept=False):
    """Copy the relevant arithmetic from upstream per_example_gradients."""
    y = np.asarray(y)
    if y.dtype.kind == "O":
        y = y.astype(float)
    X = np.nan_to_num(X, nan=0.0, posinf=0.0, neginf=0.0)
    d = X.shape[1]
    gradients = np.empty((X.shape[0], d + (1 if fit_intercept else 0)))
    with np.errstate(all="ignore"):
        z = np.nan_to_num(
            X @ theta[:d] + (theta[-1] if fit_intercept else 0.0),
            nan=0.0,
        )
        residual = expit(z) - y
        np.multiply(residual[:, None], X, out=gradients[:, :d])
        if fit_intercept:
            gradients[:, -1] = residual
    gradients[~np.isfinite(y)] = 0.0
    return np.nan_to_num(gradients, copy=False), z


def within_l2_clamp_domain(x, norm):
    """Source-equivalent _rows_within_norm(centered, norm, 2), origin=0."""
    with np.errstate(all="ignore"):
        scale = np.max(np.abs(x), axis=1, keepdims=True, initial=0.0)
        scale = np.where(scale == 0.0, 1.0, scale)
        row_norm = np.linalg.norm(x / scale, ord=2, axis=1, keepdims=True)
        return np.isfinite(x).all(axis=1, keepdims=True) & (
            row_norm <= norm / scale
        )


@unittest.skipUnless(np is not None and expit is not None,
                     "NumPy and SciPy optional in audit CI")
class TestLogisticGradientBLASRowStability(unittest.TestCase):
    def inputs(self):
        theta = np.asarray(THETA, dtype=np.float64)
        X0 = np.ones((3, 8), dtype=np.float64)
        X1 = np.vstack([X0, np.zeros((1, 8))])
        y0 = np.zeros(3, dtype=np.float64)
        y1 = np.zeros(4, dtype=np.float64)
        return theta, X0, X1, y0, y1

    def test_unbounded_size_adjacent_inputs(self):
        theta, X0, X1, y0, y1 = self.inputs()
        np.testing.assert_array_equal(X0, X1[:3])
        np.testing.assert_array_equal(y0, y1[:3])
        np.testing.assert_array_equal(X1[-1], np.zeros(8))
        self.assertTrue(np.isfinite(theta).all())
        self.assertEqual(X0.shape, (3, 8))
        self.assertEqual(X1.shape, (4, 8))

    def test_cancellation_changes_existing_rows_and_exceeds_map(self):
        theta, X0, X1, y0, y1 = self.inputs()
        G0, z0 = per_example_gradients_model(X0, y0, theta)
        G1, z1 = per_example_gradients_model(X1, y1, theta)

        if np.array_equal(z0, z1[:3]):
            self.skipTest(
                "This BLAS/NumPy implementation preserves logits for the "
                "platform-dependent cancellation witness"
            )

        # Specific numerical witness observed on the pinned OpenBLAS build.
        # If another kernel changes the logits differently, still check the
        # generic rowwise contract against the actual computed scores.
        if not (np.allclose(z0, [2.0, 2.0, -4.0], atol=0, rtol=0)
                and np.allclose(z1, [-4.0, -4.0, -4.0, 0.0],
                                atol=0, rtol=0)):
            self.skipTest(
                "Different shape-dependent BLAS kernel; this particular "
                "privacy-calibration witness has not been verified here"
            )

        # Under unsized add/remove adjacency the gradient transformation
        # advertises SymmetricDistance stability 1 for a single inserted row.
        self.assertFalse(np.array_equal(G0[:2], G1[:2]))
        self.assertFalse(np.array_equal(G0[0], G0[2]))
        self.assertTrue(np.array_equal(G1[-1], np.zeros(8)))

        # All gradient rows fall strictly within the clamp output domain.
        # Therefore source make_np_clamp preserves them unchanged.
        radius = math.sqrt(8.0)
        self.assertTrue(within_l2_clamp_domain(G0, radius).all())
        self.assertTrue(within_l2_clamp_domain(G1, radius).all())
        self.assertLess(np.linalg.norm(G0, axis=1).max(), radius)
        self.assertLess(np.linalg.norm(G1, axis=1).max(), radius)

        # make_np_sum on a zero-origin unsized L2-bounded domain reports
        # stability map(1) = 1 * radius, but actual L2 sum distance is larger.
        dist = float(np.linalg.norm(G0.sum(axis=0) - G1.sum(axis=0)))
        self.assertAlmostEqual(dist, 4.880795325243335, places=12)
        self.assertGreater(dist, radius)
        self.assertGreater(dist / radius, 1.72)

        # Conditional ideal Gaussian accounting when sigma=radius.
        self.assertEqual((radius / radius) ** 2 / 2, 0.5)
        self.assertGreater((dist / radius) ** 2 / 2, 1.48)

    def test_rowwise_computation_independent_of_batch_shape(self):
        theta, X0, X1, y0, y1 = self.inputs()
        batched0, _ = per_example_gradients_model(X0, y0, theta)
        individual = np.vstack([
            per_example_gradients_model(X0[i:i+1], y0[i:i+1], theta)[0]
            for i in range(len(X0))
        ])
        if np.array_equal(batched0, individual):
            self.skipTest("Current BLAS shows no rowwise difference here")
        # This is the property violation, not a pass/fail condition on all BLAS.
        self.assertTrue(np.any(batched0 != individual))


if __name__ == "__main__":
    unittest.main()
