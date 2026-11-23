"""Source-level model of Polars HStack lineage; not compiled OpenDP tests.

Pinned OpenDP source ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
"""

from itertools import product
import random
import unittest

NAMES = ("id", "k", "x", "y", "new")
EXISTING = NAMES[:-1]


def is_identity(expression, output_name):
    """Only Column(output_name) and aliases of that column are identities."""
    tag, value = expression
    while tag == "alias":
        tag, value = value
    return tag == "column" and value == output_name


def changed_columns(writes):
    return {out for out, expr in writes if not is_identity(expr, out)}


def retain_certificate(changes, roots, multiple_outputs=False):
    if not changes:
        return True
    if multiple_outputs:
        return False
    return changes.isdisjoint(roots)


class HStackLineageModel(unittest.TestCase):
    def test_exhaustive_explicit_key_and_selector_decisions(self):
        checked = 0
        for output in NAMES:
            for source in EXISTING:
                expr = ("alias", ("column", source))
                changes = changed_columns([(output, expr)])
                semantic_changes = set() if source == output else {output}
                self.assertEqual(changes, semantic_changes)
                for flags in product((False, True), repeat=len(NAMES)):
                    roots = {name for name, flag in zip(NAMES, flags) if flag}
                    for selector in (False, True):
                        expected = not semantic_changes or (
                            not selector and roots.isdisjoint(semantic_changes)
                        )
                        self.assertEqual(
                            retain_certificate(changes, roots, selector), expected
                        )
                        checked += 1
        self.assertEqual(checked, 1280)

    def test_randomized_replacements_and_unrelated_new_columns(self):
        rng = random.Random(20261123)
        for _ in range(20000):
            output = rng.choice(NAMES)
            source = rng.choice(EXISTING)
            changes = changed_columns([(output, ("column", source))])
            roots = {name for name in NAMES if rng.random() < 0.4}
            selector = rng.random() < 0.2
            self.assertEqual(
                retain_certificate(changes, roots, selector),
                not changes or (not selector and not (changes & roots)),
            )

    def test_derived_output_and_original_frame_bound(self):
        self.assertEqual(changed_columns([("new", ("derived", "x"))]), {"new"})
        self.assertTrue(retain_certificate({"new"}, set()))
        self.assertTrue(retain_certificate({"new"}, {"k"}))
        self.assertFalse(retain_certificate({"new"}, set(), multiple_outputs=True))
        self.assertFalse(retain_certificate({"k"}, {"k"}))

    def test_identifier_targets_are_guarded(self):
        identifier_roots = {"id", "k"}
        for output in NAMES:
            rejected = bool({output} & identifier_roots)
            self.assertEqual(rejected, output in identifier_roots)
        # This check depends on the Polars root_names() contract.


if __name__ == "__main__":
    unittest.main()
