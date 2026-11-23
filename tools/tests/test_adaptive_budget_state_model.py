"""State-model regression for fixed-budget adaptive Rust composition.

Mirrors the budget reservation and permission-token logic at upstream
ef1a238634d6196b01a1a1e77d3d5ad2340e3094. It does NOT import OpenDP,
exercise the actual Rust Queryable, or prove an interactive privacy theorem.
"""
from dataclasses import dataclass
from itertools import product
import math
import unittest


@dataclass(frozen=True)
class Child:
    # The constructor takes the remaining length minus one, before pop.
    id: int


class AdaptiveBudgetModel:
    def __init__(self, budgets, sequential=True):
        if any(not math.isfinite(b) or b < 0 for b in budgets):
            raise ValueError("budgets must be finite nonnegative")
        self.original = tuple(budgets)
        self.remaining = list(reversed(budgets))
        self.sequential = sequential
        self.data_accesses = 0
        self.issued = []

    def query(self, cost, phase="ok", space_matches=True):
        """Return a child token on success; raise for rejected/failed queries.

        A failed invocation can expose a wrapped child before postprocessing
        fails. For that case the issued list retains the token, modeling the
        escaped Queryable referenced by the native upstream regression.
        """
        if not space_matches or not self.remaining:
            raise ValueError("pre-invocation rejection")
        if not math.isfinite(cost) or cost < 0:
            raise ValueError("invalid privacy map")
        if cost > self.remaining[-1]:
            raise ValueError("insufficient budget")
        child = Child(len(self.remaining) - 1)
        self.remaining.pop()  # Reserve BEFORE accessing data.
        self.data_accesses += 1
        if phase == "invoke_error":
            raise RuntimeError("invocation failed")
        self.issued.append(child)
        if phase == "postprocess_error":
            raise RuntimeError("postprocessing failed")
        return child

    def child_allowed(self, child):
        return not self.sequential or child.id == len(self.remaining)


class AdaptiveBudgetStateModelTests(unittest.TestCase):
    def test_allocation_order_is_original_query_order(self):
        root = AdaptiveBudgetModel([0.1, 0.3, 0.2])
        self.assertEqual([root.remaining[-1-i] for i in range(3)],
                         [0.1, 0.3, 0.2])
        tokens = [root.query(x) for x in (0.1, 0.3, 0.2)]
        self.assertEqual([t.id for t in tokens], [2, 1, 0])
        self.assertEqual(root.remaining, [])
        self.assertEqual(root.data_accesses, 3)
        self.assertFalse(root.child_allowed(tokens[0]))
        self.assertTrue(root.child_allowed(tokens[-1]))

    def test_pre_invocation_errors_preserve_entry(self):
        root = AdaptiveBudgetModel([0.5, 0.25])
        for cost, matches in ((0.6, True), (0.1, False),
                              (math.nan, True), (-1, True)):
            with self.assertRaises(ValueError):
                root.query(cost, space_matches=matches)
            self.assertEqual(len(root.remaining), 2)
            self.assertEqual(root.data_accesses, 0)
        child = root.query(0.5)
        self.assertEqual(len(root.remaining), 1)
        self.assertTrue(root.child_allowed(child))

    def test_each_failed_invocation_consumes_exactly_one_entry(self):
        for phase in ("invoke_error", "postprocess_error"):
            root = AdaptiveBudgetModel([0.1, 0.2])
            with self.assertRaises(RuntimeError):
                root.query(0.1, phase=phase)
            self.assertEqual(root.remaining, [0.2])
            self.assertEqual(root.data_accesses, 1)
            self.assertTrue(root.query(0.2))
            self.assertEqual(root.remaining, [])
            with self.assertRaises(ValueError):
                root.query(0.0)
            self.assertEqual(root.data_accesses, 2)

    def test_older_children_retire_after_failure_not_rejection(self):
        root = AdaptiveBudgetModel([0.2, 0.3, 0.4])
        old = root.query(0.2)
        self.assertTrue(root.child_allowed(old))
        with self.assertRaises(ValueError):
            root.query(0.9)
        self.assertTrue(root.child_allowed(old))  # Not yet charged.
        with self.assertRaises(RuntimeError):
            root.query(0.3, phase="postprocess_error")
        self.assertFalse(root.child_allowed(old))
        self.assertEqual(len(root.remaining), 1)
        self.assertEqual(root.data_accesses, 2)
        # Child leaked while postprocessing failed stays wrapped and is
        # retired after a later accepted invocation.
        leaked = root.issued[-1]
        self.assertTrue(root.child_allowed(leaked))
        newest = root.query(0.4)
        self.assertFalse(root.child_allowed(leaked))
        self.assertTrue(root.child_allowed(newest))

    def test_concurrent_composability_does_not_retire_old_children(self):
        root = AdaptiveBudgetModel([0.2, 0.3], sequential=False)
        old = root.query(0.2)
        with self.assertRaises(RuntimeError):
            root.query(0.3, phase="invoke_error")
        self.assertTrue(root.child_allowed(old))

    def test_exhaustive_short_query_transcripts(self):
        # Outcomes are successful, pre-rejected, over-budget, invoking
        # failure, or postprocessing failure. In each transcript the
        # accepted count equals the number of data accesses and entries
        # spent, while only the newest sequential child remains allowed.
        variants = ("ok", "space_reject", "budget_reject",
                    "invoke_error", "postprocess_error")
        checked = 0
        for actions in product(variants, repeat=5):
            root = AdaptiveBudgetModel([1] * 5)
            accepted = 0
            for action in actions:
                before = root.data_accesses
                if action == "space_reject":
                    with self.assertRaises(ValueError):
                        root.query(0, space_matches=False)
                elif action == "budget_reject":
                    with self.assertRaises(ValueError):
                        root.query(2)
                elif action.endswith("_error"):
                    with self.assertRaises(RuntimeError):
                        root.query(1, phase=action)
                    accepted += 1
                else:
                    root.query(1)
                    accepted += 1
                self.assertEqual(root.data_accesses, accepted)
                self.assertEqual(len(root.remaining), 5 - accepted)
                if action in ("space_reject", "budget_reject"):
                    self.assertEqual(root.data_accesses, before)
                for child in root.issued:
                    self.assertEqual(root.child_allowed(child),
                                     child.id == len(root.remaining))
            checked += 1
        self.assertEqual(checked, 3125)

    def test_each_root_invocation_restarts_budget_state(self):
        first = AdaptiveBudgetModel([0.1])
        first.query(0.1)
        self.assertEqual(first.remaining, [])
        second = AdaptiveBudgetModel(first.original)
        self.assertEqual(second.data_accesses, 0)
        self.assertEqual(second.remaining, [0.1])
        self.assertTrue(second.query(0.1))

    def test_constructor_nonnegative_and_empty_budget(self):
        for invalid in (-1, math.nan, -math.inf, math.inf):
            with self.assertRaises(ValueError):
                AdaptiveBudgetModel([0.1, invalid])
        root = AdaptiveBudgetModel([])
        self.assertEqual(root.remaining, [])
        with self.assertRaises(ValueError):
            root.query(0)


if __name__ == "__main__":
    unittest.main()
