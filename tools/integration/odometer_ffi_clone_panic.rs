//! Pinned OpenDP FFI regression: unsupported opaque input types are cloned
//! before odometer query validation. The child process is expected to abort,
//! rather than merely return FfiResult::Err.
//!
//! This is a witness for a BUG in the pinned revision, not desired behavior.
use std::process::Command;

use opendp::combinators::make_fully_adaptive_composition;
use opendp::core::{
    FfiResult, opendp_core__odometer_queryable_invoke,
    opendp_core__odometer_queryable_privacy_loss,
};
use opendp::domains::AtomDomain;
use opendp::ffi::any::{AnyDomain, AnyMeasure, AnyMetric, AnyObject, AnyOdometer};
use opendp::measures::MaxDivergence;
use opendp::metrics::AbsoluteDistance;

fn fresh_queryable() -> AnyObject {
    let typed_odometer = make_fully_adaptive_composition::<
        AnyDomain,
        AnyMetric,
        AnyMeasure,
        AnyObject,
    >(
        AnyDomain::new(AtomDomain::<i32>::default()),
        AnyMetric::new(AbsoluteDistance::<i32>::default()),
        AnyMeasure::new(MaxDivergence),
        None,
    )
    .expect("construct typed odometer");
    // The FFI constructor erases Q = AnyMeasurement into Q = AnyObject.
    // Without this conversion, the downcast in the FFI function fails before cloning.
    let odometer: AnyOdometer = typed_odometer.into();
    AnyObject::new(
        odometer
            .invoke(&AnyObject::new(0_i32))
            .expect("spawn odometer queryable"),
    )
}

#[test]
fn cloneable_wrong_invoke_type_is_a_fallible_error() {
    let mut queryable = fresh_queryable();
    let wrong_type = AnyObject::new(1_i32);
    assert!(matches!(
        opendp_core__odometer_queryable_invoke(&mut queryable, &wrong_type),
        FfiResult::Err(_)
    ));
}

#[test]
fn uncloneable_wrong_query_aborts_across_ffi() {
    if let Ok(case) = std::env::var("OPENDP_AUDIT_ABORT_CASE") {
        let mut queryable = fresh_queryable();
        // Unit is a valid AnyObject payload but is not in AnyObject::clone's
        // dispatch table. In both entry points, cloning precedes validation.
        let wrong_type = AnyObject::new(());
        match case.as_str() {
            "invoke" => {
                let _ = opendp_core__odometer_queryable_invoke(&mut queryable, &wrong_type);
            }
            "privacy_loss" => {
                let _ = opendp_core__odometer_queryable_privacy_loss(&mut queryable, &wrong_type);
            }
            _ => panic!("unrecognized child case"),
        }
        panic!("expected FFI abort, but call returned");
    }

    for case in ["invoke", "privacy_loss"] {
        let output = Command::new(std::env::current_exe().expect("test exe"))
            .args(["--exact", "uncloneable_wrong_query_aborts_across_ffi", "--nocapture"])
            .env("OPENDP_AUDIT_ABORT_CASE", case)
            .output()
            .expect("run abort witness in child process");
        let stderr = String::from_utf8_lossy(&output.stderr);
        assert!(
            !output.status.success(),
            "{case}: unsupported query unexpectedly completed without process termination"
        );
        assert!(
            stderr.contains("Clone is not implemented")
                && stderr.contains("panic in a function that cannot unwind"),
            "{case}: expected AnyObject::clone panic across extern C, got stderr: {stderr}"
        );
    }
}
