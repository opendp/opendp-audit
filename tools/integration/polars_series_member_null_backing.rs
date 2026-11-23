//! Native, pinned OpenDP/Polars regression for audit #83.
//!
//! Reproduces why SeriesDomain::member must check only valid Arrow slots.
//! The current buggy behavior is intentionally asserted; if it is fixed,
//! update this test to assert membership instead.
use opendp::core::Domain;
use opendp::domains::{AtomDomain, OptionDomain, SeriesDomain};
use opendp::error::Fallible;
use polars::prelude::*;

#[test]
fn nullable_bounded_integer_domain_rejects_valid_null_series() -> Fallible<()> {
    let domain = SeriesDomain::new(
        "x",
        OptionDomain::new(AtomDomain::<i32>::new_closed((1, 3))?),
    );
    assert!(domain.nullable);

    let series = Series::new("x".into(), &[None, Some(2_i32)]);
    assert_eq!(series.dtype(), &DataType::Int32);
    assert_eq!(series.null_count(), 1);
    assert_eq!(series.i32()?.get(0), None);
    assert_eq!(series.i32()?.get(1), Some(2));

    // Polars Arrow stores a data buffer and a separate validity bitmap.
    // values_iter() ignores validity. The null slot happens to contain zero,
    // which is outside the domain's allowed *nonnull* range [1,3].
    let chunked = series.i32()?;
    let chunks: Vec<_> = chunked.downcast_iter().collect();
    assert_eq!(chunks.len(), 1);
    assert_eq!(chunks[0].values_iter().next().copied(), Some(0));
    assert_eq!(chunks[0].non_null_values_iter().count(), 1);

    // This is a logically valid member: the only nonnull element is 2.
    // Pinned OpenDP incorrectly returns false by checking zero at the null slot.
    assert!(!domain.member(&series)?);

    // Controls: an all-valid in-bounds series is accepted and out-of-bounds
    // nonnull values are rejected by exactly the same constructor.
    let valid = Series::new("x".into(), &[Some(1_i32), Some(3)]);
    let invalid = Series::new("x".into(), &[Some(2_i32), Some(4)]);
    assert!(domain.member(&valid)?);
    assert!(!domain.member(&invalid)?);

    // If the domain also allows the hidden null-slot payload, the same
    // logical series is accepted. This demonstrates dependence on storage
    // that should be ignored by a nullable-domain membership predicate.
    let wide_domain = SeriesDomain::new(
        "x",
        OptionDomain::new(AtomDomain::<i32>::new_closed((0, 3))?),
    );
    assert!(wide_domain.member(&series)?);

    Ok(())
}

#[test]
fn nonnullable_domain_correctly_rejects_nulls() -> Fallible<()> {
    let domain = SeriesDomain::new("x", AtomDomain::<i32>::new_closed((0, 3))?);
    let series = Series::new("x".into(), &[None, Some(2_i32)]);
    assert!(!domain.member(&series)?);
    Ok(())
}
