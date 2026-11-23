"""Reference model for nullable SeriesDomain bounds and Arrow validity bits.

This test does not call OpenDP or Polars. The pinned compiled regression is
tools/integration/polars_series_member_null_backing.rs (audit #83).
"""
import unittest


def buggy_membership(raw_values, is_valid, *, low, high, nullable):
    if not nullable and not all(is_valid):
        return False
    return all(low <= x <= high for x in raw_values)


def logical_membership(raw_values, is_valid, *, low, high, nullable):
    if len(raw_values) != len(is_valid):
        raise ValueError("validity and data buffer have different lengths")
    if not nullable and not all(is_valid):
        return False
    return all(
        low <= value <= high
        for value, valid in zip(raw_values, is_valid)
        if valid
    )


class TestSeriesNullableMemberReference(unittest.TestCase):
    def test_bounded_nullable_member_should_skip_null_backing(self):
        raw, validity = [0, 2], [False, True]
        kwargs = dict(low=1, high=3, nullable=True)
        self.assertFalse(buggy_membership(raw, validity, **kwargs))
        self.assertTrue(logical_membership(raw, validity, **kwargs))

    def test_membership_must_be_invariant_to_null_payload(self):
        kwargs = dict(low=1, high=3, nullable=True)
        validity = [False, True]
        for hidden in [0, 1, 2, 3, 999]:
            self.assertTrue(logical_membership([hidden, 2], validity, **kwargs))
        self.assertFalse(buggy_membership([0, 2], validity, **kwargs))
        self.assertTrue(buggy_membership([2, 2], validity, **kwargs))

    def test_actual_out_of_bounds_valid_values_are_rejected(self):
        raw, validity = [0, 4], [False, True]
        kwargs = dict(low=1, high=3, nullable=True)
        self.assertFalse(buggy_membership(raw, validity, **kwargs))
        self.assertFalse(logical_membership(raw, validity, **kwargs))

    def test_nonnullable_domain_rejects_nulls(self):
        raw, validity = [0, 2], [False, True]
        kwargs = dict(low=0, high=3, nullable=False)
        self.assertFalse(buggy_membership(raw, validity, **kwargs))
        self.assertFalse(logical_membership(raw, validity, **kwargs))


if __name__ == "__main__":
    unittest.main()
