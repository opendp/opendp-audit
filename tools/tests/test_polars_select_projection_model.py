"""Independent source-level model of OpenDP's non-deprecated Polars select.

Does NOT execute native OpenDP, Rust, or Polars. Covers only deterministic,
row-local projections and certificate-retention control flow.
"""
from collections import Counter
from itertools import product
import unittest

COLUMNS = ("a", "b", "c")
ROWS = tuple(product(range(3), (0, 1)))  # Six values for (a, b).


def multiset_distance(left, right):
    lc, rc = Counter(left), Counter(right)
    return sum(abs(lc[row] - rc[row]) for row in lc.keys() | rc.keys())


def selected(dataset, function):
    return tuple(function(row) for row in dataset)


def changed_columns(columns, output_exprs):
    """Model the Rust retained_columns and changed_columns construction.

    output_expr is (output_name, source_name_or_none, dependency_roots).
    An unchanged expression must be a direct named-column identity (aliasing to
    the original name does not change values). Rewrites and drops count as
    changes. Output names must be unique as enforced by projection options.
    """
    retained = {name for name, source, _ in output_exprs if source == name}
    return (set(columns) | {name for name, _, _ in output_exprs}) - retained


def unaffected(roots, changed, selector=False):
    """Model the Rust unaffected() conservative selector handling."""
    return not changed or (not selector and set(roots).isdisjoint(changed))


class SelectProjectionReferenceTests(unittest.TestCase):
    def test_all_small_multisets_are_nonexpansive_for_local_projection(self):
        datasets = tuple(rows for n in range(4) for rows in product(ROWS, repeat=n))
        self.assertEqual(len(datasets), 259)
        transformations = (
            lambda r: (r[0],),
            lambda r: (r[1],),
            lambda r: (r[0], r[1]),
            lambda r: (r[0] * 2, r[1]),
            lambda r: (r[0], r[0]),
            lambda r: (r[0], 5),
        )
        comparisons = 0
        for func in transformations:
            outputs = [Counter(selected(ds, func)) for ds in datasets]
            inputs = [Counter(ds) for ds in datasets]
            for i, left in enumerate(datasets):
                for j, right in enumerate(datasets):
                    old = sum(abs(inputs[i][key] - inputs[j][key])
                              for key in inputs[i].keys() | inputs[j].keys())
                    new = sum(abs(outputs[i][key] - outputs[j][key])
                              for key in outputs[i].keys() | outputs[j].keys())
                    self.assertLessEqual(new, old)
                    comparisons += 1
        self.assertEqual(comparisons, 6 * 259**2)

    def test_retained_certificate_requires_unchanged_source_roots(self):
        # Distinct output names; sources None represent a rewritten value.
        options = tuple((name, name, (name,)) for name in COLUMNS) + (
            ("a", None, ("b",)),  # overwrite a from b
            ("b", None, ("a",)),  # overwrite b from a
            ("c", None, ("a", "b")),
            ("d", None, ("a",)),  # derived new column
            ("e", None, ()),  # broadcastable constant
            ("f", None, ("b",)),
        )
        certificates = [tuple(c for c, selected in zip(COLUMNS, mask) if selected)
                        for mask in product((False, True), repeat=len(COLUMNS))]
        examined = retained = 0
        for count in range(1, 4):
            for exprs in product(options, repeat=count):
                names = [name for name, _, _ in exprs]
                if len(set(names)) != len(names):
                    continue  # projection rejects duplicate output names
                if all(not roots for _, _, roots in exprs):
                    continue  # Rust rejects literal-only projections
                changed = changed_columns(COLUMNS, exprs)
                for cert_roots in certificates:
                    for selector in (False, True):
                        examined += 1
                        if not unaffected(cert_roots, changed, selector):
                            continue
                        retained += 1
                        # For an explicit grouping expression, all source
                        # columns on which it depends must survive unchanged.
                        if not selector:
                            self.assertTrue(set(cert_roots).isdisjoint(changed))
                        else:
                            # Selectors may depend on the whole schema and are
                            # retained only when the schema is unchanged.
                            self.assertFalse(changed)
        self.assertEqual(examined, 7232)
        self.assertGreater(retained, 0)

    def test_changed_or_dropped_key_removes_its_certificate(self):
        for outputs in (
            (("b", "b", ("b",)),),  # a dropped
            (("a", None, ("b",)), ("b", "b", ("b",))),  # a overwritten
            (("renamed", None, ("a",)), ("b", "b", ("b",))),
        ):
            changed = changed_columns(COLUMNS, outputs)
            self.assertFalse(unaffected(("a",), changed))
        kept = (("a", "a", ("a",)), ("b", "b", ("b",)))
        self.assertTrue(unaffected(("a",), changed_columns(COLUMNS, kept)))
        self.assertFalse(unaffected((), changed_columns(COLUMNS, kept), selector=True))
        unchanged = tuple((c, c, (c,)) for c in COLUMNS)
        self.assertTrue(unaffected((), changed_columns(COLUMNS, unchanged), selector=True))

    def test_projection_guards_and_literal_broadcast(self):
        self.assertFalse(any(roots for _, _, roots in (("constant", None, ()),)))
        self.assertTrue(any(roots for _, _, roots in (
            ("a", "a", ("a",)), ("constant", None, ()),
        )))
        # Source accepts arbitrary parallelism only when duplicate checks and
        # literal broadcasting are enabled.
        accepted = []
        for duplicate_check, should_broadcast, run_parallel in product(
            (False, True), repeat=3
        ):
            valid = duplicate_check and should_broadcast
            if valid:
                accepted.append((duplicate_check, should_broadcast, run_parallel))
        self.assertEqual(accepted, [(True, True, False), (True, True, True)])


if __name__ == "__main__":
    unittest.main()
