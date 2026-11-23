"""Reference model for the identifier projection guards in Polars make_select.

Only evaluates set membership, identity expression lineage, and metric-space
checks from pinned opendp/opendp@ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
Not a compiled OpenDP or Polars execution.
"""

from itertools import product
import unittest


IDENTIFIERS = frozenset({"ID"})
INPUT_COLUMNS = frozenset({"ID", "x"})


def original_select_guard(projected):
    """Current make_select guard: reject any output with identifier name."""
    output_names = {name for _source, name, _identity in projected}
    return output_names.isdisjoint(IDENTIFIERS)


def output_metric_space_valid(projected):
    """FrameDomain check_space requires identifier root columns in output."""
    output_names = {name for _source, name, _identity in projected}
    return IDENTIFIERS <= output_names


def changed_columns(projected):
    """Source make_select's lineage logic for this direct-column subset."""
    retained = {
        name for source, name, identity in projected
        if identity and source == name
    }
    output_names = {name for _source, name, _identity in projected}
    return (INPUT_COLUMNS | output_names) - retained


def desired_id_preservation(projected):
    return (
        changed_columns(projected).isdisjoint(IDENTIFIERS)
        and output_metric_space_valid(projected)
    )


def id_distance_if_shared_rows_equal(rows_a, rows_b):
    """Finite symmetric-ID distance in the domain where shared IDs' data agree."""
    by_id_a = {row[0]: row for row in rows_a}
    by_id_b = {row[0]: row for row in rows_b}
    for common in by_id_a.keys() & by_id_b.keys():
        if by_id_a[common] != by_id_b[common]:
            return float("inf")
    return len(by_id_a.keys() ^ by_id_b.keys())


class TestPolarsSelectIdentifierModel(unittest.TestCase):
    def test_unchanged_identifier_projection_is_rejected_by_name_guard(self):
        projected = (("ID", "ID", True), ("x", "x", True))
        self.assertFalse(original_select_guard(projected))
        self.assertTrue(output_metric_space_valid(projected))
        self.assertTrue(desired_id_preservation(projected))

    def test_dropping_or_renaming_identifier_fails_output_metric_space(self):
        for projected in [
            (("x", "x", True),),
            (("ID", "renamed", False), ("x", "x", True)),
        ]:
            self.assertTrue(original_select_guard(projected))
            self.assertFalse(output_metric_space_valid(projected))
            self.assertFalse(desired_id_preservation(projected))

    def test_overwriting_identifier_is_correctly_rejected(self):
        projected = (("x", "ID", False), ("x", "x", True))
        self.assertFalse(original_select_guard(projected))
        self.assertTrue(output_metric_space_valid(projected))
        self.assertFalse(desired_id_preservation(projected))

    def test_no_direct_two_column_projection_can_pass_both_current_checks(self):
        # Any output containing ID fails the first guard; any other output
        # fails check_space, independently of its input lineage.
        projections = []
        outputs = ("ID", "x", "renamed")
        for left, right in product(outputs, repeat=2):
            if left == right:
                continue
            projections.append((("ID", left, left == "ID"), ("x", right, right == "x")))
        self.assertEqual(len(projections), 6)
        self.assertFalse(any(original_select_guard(p) and output_metric_space_valid(p) for p in projections))

    def test_preserving_projection_is_nonvacuously_one_stable(self):
        left = ((1, 4), (2, 5))
        right = ((2, 5), (3, 6))
        # Project ID and x without altering values or row membership.
        self.assertEqual(id_distance_if_shared_rows_equal(left, right), 2)
        out_left = tuple((id_, x) for id_, x in left)
        out_right = tuple((id_, x) for id_, x in right)
        self.assertEqual(id_distance_if_shared_rows_equal(out_left, out_right), 2)


if __name__ == "__main__":
    unittest.main()
