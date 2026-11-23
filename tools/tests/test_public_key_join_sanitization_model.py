"""Finite reference checks for pinned OpenDP public-key join admission guards.

OpenDP ef1a238634d6196b01a1a1e77d3d5ad2340e3094;
does not run Rust or Polars.
"""
import itertools
import random
import unittest


def accept_join(group_keys, private_join_keys, public_join_keys,
                public_schema, private_aggs, *,
                column_only=True, coalesced=True, ordinary_options=True,
                public_keys_exist=True):
    # Mirrors match_group_by's set matching and public-output collision checks.
    return (
        column_only
        and coalesced
        and ordinary_options
        and set(private_join_keys) == set(group_keys)
        and len(private_join_keys) == len(public_join_keys)
        and set(public_join_keys).issubset(set(public_schema))
        and set(public_schema).isdisjoint(set(private_aggs))
        and public_keys_exist
    )


class PublicKeyJoinSourceModel(unittest.TestCase):
    def test_all_key_subsets_and_collision_masks(self):
        names = ("k0", "k1", "k2")
        checked = 0
        subsets = [
            set(n for n, flag in zip(names, mask) if flag)
            for mask in itertools.product((False, True), repeat=len(names))
        ]
        for group, joined, schema, aggregates in itertools.product(subsets, repeat=4):
            accepted = accept_join(
                group, sorted(joined), sorted(joined),
                schema, aggregates
            )
            expected = group == joined and joined <= schema and not (schema & aggregates)
            self.assertEqual(accepted, expected)
            checked += 1
        self.assertEqual(checked, 4096)

    def test_guarded_options_and_columns(self):
        for flags in itertools.product((False, True), repeat=4):
            column_only, coalesced, ordinary, exist = flags
            self.assertEqual(
                accept_join(["k"], ["k"], ["pub"], ["pub"], ["out"],
                            column_only=column_only, coalesced=coalesced,
                            ordinary_options=ordinary, public_keys_exist=exist),
                all(flags)
            )

    def test_join_on_must_cover_all_private_keys(self):
        self.assertFalse(accept_join(["k", "p"], ["k"], ["k"], ["k"], ["out"]))
        self.assertTrue(accept_join(["k", "p"], ["p", "k"], ["P", "K"],
                                    ["P", "K", "meta"], ["out"]))
        self.assertFalse(accept_join(["k"], ["k"], ["pub"], ["pub", "out"], ["out"]))

    def test_randomized_reference(self):
        rng = random.Random(20261123)
        names = [f"key{i}" for i in range(9)]
        for _ in range(20000):
            group = [x for x in names if rng.random() < .5]
            private = [x for x in names if rng.random() < .5]
            public = [x for x in names if rng.random() < .5]
            schema = [x for x in names if rng.random() < .5]
            aggs = [x for x in names if rng.random() < .5]
            got = accept_join(group, private, public, schema, aggs)
            want = (set(private) == set(group) and len(private) == len(public)
                    and set(public) <= set(schema) and not (set(schema) & set(aggs)))
            self.assertEqual(got, want)


if __name__ == "__main__":
    unittest.main()
