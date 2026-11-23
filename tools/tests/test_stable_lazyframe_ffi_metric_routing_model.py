"""Model the pinned make_stable_lazyframe FFI output-metric routing.

Upstream OpenDP main: a010591f55b1713c926f8e355091471634480307.
This test mirrors the FFI type-dispatch control flow; it does not run the
native OpenDP FFI, its Rust Type parser, or the Polars expression engine.

The witness is a deliberately *successful* bounded-metric branch with a
requested output type different from the constructor's actual output type.
"""
import unittest


FRAME_SYM = "FrameDistance<SymmetricDistance>"
FRAME_SYM_ID = "FrameDistance<SymmetricIdDistance>"
SYM = "SymmetricDistance"
SYM_ID = "SymmetricIdDistance"
CHANGE = "ChangeOneDistance"
CHANGE_ID = "ChangeOneIdDistance"


def source_equivalent_dispatch(mi, mo):
    """Only the metric type-selection branch, not a Polars runtime invocation.

    For bounded input metrics, Rust:
      fn monomorphize<MI: BoundedMetric>(...) {
          make_stable_lazyframe(input_domain, input_metric, lazyframe).into_any()
      }
    The inferred output type is FrameDistance<MI::UnboundedMetric> regardless
    of the parsed MO value.
    """
    if mo == "MI":
        mo = mi

    if mi in (FRAME_SYM, FRAME_SYM_ID):
        if mi == mo:
            return mi
        if mi == FRAME_SYM_ID and mo == FRAME_SYM:
            return FRAME_SYM
        raise ValueError("incompatible frame metric conversion")

    if mi in (SYM, SYM_ID):
        if (mi, mo) in ((SYM, FRAME_SYM), (SYM_ID, FRAME_SYM_ID)):
            return mo
        if (mi, mo) == (SYM_ID, FRAME_SYM):
            return FRAME_SYM
        raise ValueError("incompatible unbounded metric conversion")

    # Bounded branch: the *user-supplied* MO is ignored after parsing.
    return {CHANGE: FRAME_SYM, CHANGE_ID: FRAME_SYM_ID}[mi]


class TestBoundedStableLazyframeFfiMetricDispatch(unittest.TestCase):
    def test_mismatched_explicit_frame_metric_is_silently_accepted(self):
        for mi, wrong, actual in (
            (CHANGE, FRAME_SYM_ID, FRAME_SYM),
            (CHANGE_ID, FRAME_SYM, FRAME_SYM_ID),
            (CHANGE, SYM_ID, FRAME_SYM),
            (CHANGE_ID, SYM, FRAME_SYM_ID),
        ):
            with self.subTest(mi=mi, requested=wrong):
                returned = source_equivalent_dispatch(mi, wrong)
                self.assertNotEqual(returned, wrong)
                self.assertEqual(returned, actual)

    def test_bounded_default_suppresses_requested_equal_type(self):
        # MI as MO is the documented default token. The deliberate automatic
        # promotion is not the bug; *explicit conflicting choices* are.
        self.assertEqual(source_equivalent_dispatch(CHANGE, "MI"), FRAME_SYM)
        self.assertEqual(source_equivalent_dispatch(CHANGE_ID, "MI"), FRAME_SYM_ID)

    def test_unbounded_branches_do_check_explicit_mo(self):
        for mi, incompatible in (
            (SYM, FRAME_SYM_ID),
            (SYM_ID, FRAME_SYM_ID),  # SYM_ID->Frame<SYM_ID> is allowed, see below.
            (FRAME_SYM, FRAME_SYM_ID),
            (FRAME_SYM_ID, SYM),
        ):
            if mi == SYM_ID:
                self.assertEqual(source_equivalent_dispatch(mi, incompatible), FRAME_SYM_ID)
            else:
                with self.subTest(mi=mi, requested=incompatible):
                    with self.assertRaises(ValueError):
                        source_equivalent_dispatch(mi, incompatible)

    def test_explicit_supported_routes_still_match_actual(self):
        self.assertEqual(source_equivalent_dispatch(SYM, FRAME_SYM), FRAME_SYM)
        self.assertEqual(source_equivalent_dispatch(SYM_ID, FRAME_SYM_ID), FRAME_SYM_ID)
        self.assertEqual(source_equivalent_dispatch(SYM_ID, FRAME_SYM), FRAME_SYM)
        self.assertEqual(source_equivalent_dispatch(FRAME_SYM, FRAME_SYM), FRAME_SYM)
        self.assertEqual(source_equivalent_dispatch(FRAME_SYM_ID, FRAME_SYM), FRAME_SYM)


if __name__ == "__main__":
    unittest.main()
