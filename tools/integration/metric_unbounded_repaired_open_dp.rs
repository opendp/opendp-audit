//! Test the real OpenDP constructor after applying a CI-only checked-map patch.
//!
//! This test asserts the required stability-map contract. It is intentionally
//! separate from the pinned-upstream regression test in audit issue #27.

use opendp::domains::{AtomDomain, VectorDomain};
use opendp::metrics::{ChangeOneDistance, HammingDistance};
use opendp::transformations::make_metric_unbounded;
use std::panic::{catch_unwind, AssertUnwindSafe};

#[test]
fn checked_change_one_cast_preserves_conservative_bound() {
    let domain = VectorDomain::new(AtomDomain::<i32>::default()).with_size(1);
    let trans = make_metric_unbounded(domain, ChangeOneDistance).unwrap();
    assert_eq!(trans.invoke(&vec![0]).unwrap(), vec![0]);
    assert_eq!(trans.invoke(&vec![1]).unwrap(), vec![1]);
    assert_safe_bounds(|d| trans.map(&d));
}

#[test]
fn checked_hamming_cast_preserves_conservative_bound() {
    let domain = VectorDomain::new(AtomDomain::<i32>::default()).with_size(1);
    let trans = make_metric_unbounded(domain, HammingDistance).unwrap();
    assert_eq!(trans.invoke(&vec![0]).unwrap(), vec![0]);
    assert_eq!(trans.invoke(&vec![1]).unwrap(), vec![1]);
    assert_safe_bounds(|d| trans.map(&d));
}

fn assert_safe_bounds(map: impl Fn(u32) -> opendp::error::Fallible<u32>) {
    assert_eq!(map(0).unwrap(), 0);
    assert_eq!(map(1).unwrap(), 2);
    assert_eq!(map((1_u32 << 31) - 1).unwrap(), u32::MAX - 1);

    for invalid in [1_u32 << 31, (1_u32 << 31) + 1, u32::MAX] {
        let outcome = catch_unwind(AssertUnwindSafe(|| map(invalid)));
        assert!(outcome.is_ok(), "stability map must not panic for d_in={invalid}");
        assert!(
            outcome.unwrap().is_err(),
            "unrepresentable doubled u32 bound must yield Err, not a truncated Ok"
        );
    }
}
