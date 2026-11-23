//! Actual OpenDP constructor regression for audit issue #27.
//!
//! Run against pinned upstream ef1a238634d6196b01a1a1e77d3d5ad2340e3094 in both
//! debug and release. The tests deliberately record the *existing* broken
//! behavior instead of asserting that the unfixed upstream is correct.

use opendp::domains::{AtomDomain, VectorDomain};
use opendp::metrics::{ChangeOneDistance, HammingDistance};
use opendp::transformations::make_metric_unbounded;
use std::panic::{catch_unwind, AssertUnwindSafe};

#[test]
fn change_one_to_symmetric_is_unsound_at_u32_half_range() {
    let domain = VectorDomain::new(AtomDomain::<i32>::default()).with_size(1);
    let trans = make_metric_unbounded(domain, ChangeOneDistance).unwrap();
    assert_eq!(trans.invoke(&vec![0]).unwrap(), vec![0]);
    assert_eq!(trans.invoke(&vec![1]).unwrap(), vec![1]);
    assert_eq!(trans.map(&1).unwrap(), 2);

    // [0] and [1] are input-distance 1 apart but output-distance 2 apart.
    // Both are 2^31-close, so the claimed output bound must remain >= 2.
    assert_bad_map_result(catch_unwind(AssertUnwindSafe(|| trans.map(&(1_u32 << 31)))));
}

#[test]
fn hamming_to_insert_delete_has_the_same_underflow() {
    let domain = VectorDomain::new(AtomDomain::<i32>::default()).with_size(1);
    let trans = make_metric_unbounded(domain, HammingDistance).unwrap();
    assert_eq!(trans.invoke(&vec![0]).unwrap(), vec![0]);
    assert_eq!(trans.invoke(&vec![1]).unwrap(), vec![1]);
    assert_eq!(trans.map(&1).unwrap(), 2);

    assert_bad_map_result(catch_unwind(AssertUnwindSafe(|| trans.map(&(1_u32 << 31)))));
}

fn assert_bad_map_result(
    result: std::thread::Result<opendp::error::Fallible<u32>>,
) {
    if cfg!(debug_assertions) {
        // Debug checks turn the infallible closure's multiplication into a panic.
        assert!(result.is_err(), "expected checked u32 multiplication to panic");
    } else {
        // Release unchecked multiplication silently returns a false zero bound.
        assert_eq!(
            result.expect("unchecked map should not panic").expect("map should return Ok"),
            0,
            "release map must demonstrate the existing unsound zero bound"
        );
    }
}
