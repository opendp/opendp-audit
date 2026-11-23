//! Actual OpenDP source-level regression for audit issue #92.
//!
//! Run against pinned upstream ef1a238634d6196b01a1a1e77d3d5ad2340e3094
//! in debug and release. These tests record the unfixed behavior, not the
//! intended post-remediation contract.

use opendp::domains::{AtomDomain, LazyFrameDomain, Margin, SeriesDomain};
use opendp::error::Fallible;
use opendp::metrics::{Bound, Bounds};
use polars::prelude::*;
use std::collections::HashSet;
use std::panic::{catch_unwind, AssertUnwindSafe};

const HALF_U32: u32 = 1 << 31;

fn one_column_domain() -> Fallible<LazyFrameDomain> {
    LazyFrameDomain::new(vec![SeriesDomain::new("A", AtomDomain::<i32>::default())])?
        .with_margin(Margin::by(["A"]).with_max_groups(HALF_U32))
}

fn assert_current_overflow(res: std::thread::Result<Option<u32>>) {
    if cfg!(debug_assertions) {
        assert!(res.is_err(), "expected existing checked i32::MIN negation panic");
    } else {
        assert_eq!(res.expect("unchecked negation must not panic"), Some(HALF_U32));
    }
}

#[test]
fn frame_domain_margin_large_u32_checked_panic() -> Fallible<()> {
    let domain = one_column_domain()?;
    let by = HashSet::from([col("A")]);
    let result = catch_unwind(AssertUnwindSafe(|| domain.get_margin(&by).max_groups));
    assert_current_overflow(result);
    Ok(())
}

#[test]
fn frame_distance_bound_large_u32_checked_panic() {
    let bounds = Bounds(vec![Bound::by(["A"]).with_num_groups(HALF_U32)]);
    let by = HashSet::from([col("A")]);
    let result = catch_unwind(AssertUnwindSafe(|| bounds.get_bound(&by).num_groups));
    assert_current_overflow(result);
}

#[test]
fn frame_domain_margin_tie_selects_larger_weight() -> Fallible<()> {
    let domain = LazyFrameDomain::new(vec![
        SeriesDomain::new("A", AtomDomain::<i32>::default()),
        SeriesDomain::new("B", AtomDomain::<i32>::default()),
        SeriesDomain::new("C", AtomDomain::<i32>::default()),
    ])?
    .with_margin(Margin::by(["A", "B"]).with_max_groups(1))?
    .with_margin(Margin::by(["A", "C"]).with_max_groups(HALF_U32 + 1))?;
    assert_eq!(
        domain.get_margin(&HashSet::from([col("A")])).max_groups,
        Some(HALF_U32 + 1),
        "pinned source should reproduce inverted large-weight priority"
    );
    Ok(())
}

#[test]
fn frame_distance_bound_tie_selects_larger_weight() {
    let bounds = Bounds(vec![
        Bound::by(["A", "B"]).with_num_groups(1),
        Bound::by(["A", "C"]).with_num_groups(HALF_U32 + 1),
    ]);
    assert_eq!(
        bounds.get_bound(&HashSet::from([col("A")])).num_groups,
        Some(HALF_U32 + 1),
        "pinned source should reproduce inverted large-weight priority"
    );
}
