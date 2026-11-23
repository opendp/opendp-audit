//! Pinned OpenDP regression for audit defect #100.
//! Current buggy behavior is intentionally asserted. Invert on upstream repair.
use opendp::core::Domain;
use opendp::domains::AtomDomain;
use opendp::error::Fallible;

#[test]
fn bounded_simple_scalar_domains_error_on_member() -> Fallible<()> {
    let strings = AtomDomain::<String>::new_closed(("a".into(), "z".into()))?;
    assert!(strings.member(&"m".to_string()).is_err());

    let bools = AtomDomain::<bool>::new_closed((false, true))?;
    assert!(bools.member(&false).is_err());
    assert!(bools.member(&true).is_err());

    let chars = AtomDomain::<char>::new_closed(('a', 'z'))?;
    assert!(chars.member(&'m').is_err());

    let slices = AtomDomain::<&str>::new_closed(("a", "z"))?;
    assert!(slices.member(&"m").is_err());
    Ok(())
}

#[test]
fn numeric_unbounded_and_invalid_bound_controls() -> Fallible<()> {
    let integers = AtomDomain::<i32>::new_closed((1, 3))?;
    assert!(integers.member(&2)?);
    assert!(!integers.member(&4)?);

    let floats = AtomDomain::<f64>::new_closed((0., 1.))?;
    assert!(floats.member(&0.5)?);
    assert!(!floats.member(&1.5)?);
    assert!(!floats.member(&f64::NAN)?);

    assert!(AtomDomain::<String>::default().member(&"m".to_string())?);
    assert!(AtomDomain::<i32>::new_closed((3, 1)).is_err());
    assert!(AtomDomain::<f64>::new_closed((f64::NAN, 1.)).is_err());
    Ok(())
}
