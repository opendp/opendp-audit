"""Source-equivalent NumPy float32 sum overflow privacy counterexamples.

OpenDP main SHA a010591f55b1713c926f8e355091471634480307.
Not compiled OpenDP FFI or Rust noise execution; the float-to-bigint
intermediate is modeled from its pinned Rust code.
"""
import math
import unittest

try:
    import numpy as np
except ImportError:
    np = None


def scaled_rows_within_norm(x, norm, p):
    """Replicate opendp.extras.numpy._norm._rows_within_norm."""
    x = np.ascontiguousarray(x)
    with np.errstate(all="ignore"):
        scale = np.max(np.abs(x), axis=1, keepdims=True, initial=0.0)
        scale = np.where(scale == 0.0, 1.0, scale)
        row_norm = np.linalg.norm(x / scale, ord=p, axis=1, keepdims=True)
        return np.isfinite(x).all(axis=1, keepdims=True) & (
            row_norm <= norm / scale
        )


def rust_float_to_bigint_center_model(value):
    """Model clamp finite range + rational conversion fallback to zero.

    Models only the pre-rounding rational centers, not full Rust mechanism,
    noise sampling, integerization granularity, or FFI conversion.
    """
    if math.isnan(float(value)):
        return 0.0
    max_finite = float(np.finfo(np.float32).max)
    return float(np.clip(value, -max_finite, max_finite))


@unittest.skipIf(np is None, "NumPy optional in audit CI")
class TestNumpyFloat32SumOverflowModel(unittest.TestCase):
    def test_bounded_neighbors_exceed_certified_sensitivity(self):
        v = np.float32(1e38)
        a = np.array([v, v, v, -v, -v, -v, -v, -v], dtype=np.float32).reshape(-1, 1)
        b = a.copy()
        b[3, 0] = v
        norm = 1e38
        for array in (a, b):
            self.assertTrue(scaled_rows_within_norm(array, norm, p=2).all())
            self.assertEqual(array.shape, (8, 1))
            self.assertEqual(array.dtype, np.float32)

        # Same public size; replace exactly one row => d_in=2.
        self.assertEqual(np.count_nonzero(a != b), 1)
        with np.errstate(all="ignore"):
            y_a = a.sum(axis=0)[0]
            y_b = b.sum(axis=0)[0]

        self.assertTrue(np.isneginf(y_a))
        self.assertTrue(np.isnan(y_b))
        center_a = rust_float_to_bigint_center_model(y_a)
        center_b = rust_float_to_bigint_center_model(y_b)
        claimed = (2 // 2) * 2 * norm
        self.assertEqual(center_a, -float(np.finfo(np.float32).max))
        self.assertEqual(center_b, 0.0)
        self.assertGreater(abs(center_a - center_b), claimed)

        # Correct real (widened) sums do satisfy the stated bound.
        true_a = float(a.astype(np.float64).sum(axis=0)[0])
        true_b = float(b.astype(np.float64).sum(axis=0)[0])
        self.assertLessEqual(abs(true_a - true_b), claimed)

    def test_neighboring_bounded_datasets_raise_different_pre_noise_outcomes(self):
        v = np.float32(1e38)
        a = np.array([v, v, v, -v], dtype=np.float32).reshape(-1, 1)
        b = np.array([v, v, v, v], dtype=np.float32).reshape(-1, 1)
        self.assertEqual(np.count_nonzero(a != b), 1)
        for array in (a, b):
            self.assertTrue(scaled_rows_within_norm(array, 1e38, p=2).all())
        with np.errstate(over="raise", invalid="raise"):
            self.assertTrue(np.isfinite(a.sum(axis=0)).all())
            with self.assertRaises(FloatingPointError):
                b.sum(axis=0)


if __name__ == "__main__":
    unittest.main()
