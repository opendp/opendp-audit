"""Model the `ArrayFunction::Get(_)` branch and pinned Polars Get(false) behavior.

Source pins:
  OpenDP ef1a238634d6196b01a1a1e77d3d5ad2340e3094
  Polars 0.52.0, git tag py-1.36.1
This is an abstract source-control-flow regression, NOT compiled OpenDP or Polars.
"""
import random
import unittest


def opendp_accepts_array_get(null_on_oob: bool) -> bool:
    # In OpenDP `ArrayFunction::Get(_) | ArrayFunction::Join(_) ...`
    # always recurses into its operands, without examining null_on_oob.
    return True


def opendp_accepts_list_get(null_on_oob: bool) -> bool:
    # The corresponding `ListFunction::Get(null_on_oob)` rejects false.
    return null_on_oob


def polars_array_get(items, index: int, null_on_oob: bool):
    # Only models the index range and null-vs-error outcome of Polars' array_get.
    if -len(items) <= index < len(items):
        return items[index]
    if null_on_oob:
        return None
    raise IndexError("get index is out of bounds")


class ArrayGetOobWhitelistModel(unittest.TestCase):
    def test_open_dp_accepts_both_flags_although_backend_can_error(self):
        self.assertTrue(opendp_accepts_array_get(False))
        self.assertTrue(opendp_accepts_array_get(True))
        self.assertFalse(opendp_accepts_list_get(False))
        self.assertTrue(opendp_accepts_list_get(True))

    def test_public_width_private_index_changes_error_status(self):
        values = (5, 6)
        # Both indices are integer values admissible in a single-column domain.
        self.assertEqual(polars_array_get(values, 0, False), 5)
        with self.assertRaisesRegex(IndexError, "out of bounds"):
            polars_array_get(values, 2, False)
        self.assertIsNone(polars_array_get(values, 2, True))

    def test_complete_small_index_range_and_random_reference(self):
        checks = 0
        for width in range(1, 15):
            array = tuple(range(width))
            for index in range(-width - 4, width + 5):
                for null_on_oob in (False, True):
                    valid = -width <= index < width
                    if valid:
                        self.assertEqual(polars_array_get(array, index, null_on_oob), array[index])
                    elif null_on_oob:
                        self.assertIsNone(polars_array_get(array, index, null_on_oob))
                    else:
                        with self.assertRaises(IndexError):
                            polars_array_get(array, index, null_on_oob)
                    checks += 1
        rng = random.Random(20261123)
        for _ in range(20000):
            width = rng.randrange(1, 70)
            index = rng.randrange(-2 * width, 2 * width)
            null_on_oob = bool(rng.getrandbits(1))
            valid = -width <= index < width
            try:
                result = polars_array_get(tuple(range(width)), index, null_on_oob)
                self.assertTrue(valid or null_on_oob)
                self.assertEqual(result, index % width if valid else None)
            except IndexError:
                self.assertFalse(valid)
                self.assertFalse(null_on_oob)
            checks += 1
        self.assertEqual(checks, 20000 + sum(2 * (2 * w + 9) for w in range(1, 15)))


if __name__ == "__main__":
    unittest.main()
