//! Standalone native-Rust reproducer for opendp/opendp-audit#4.
//!
//! Models ONLY the built-in checked-subtraction semantics used by
//! OpenDP's AlertingSub in rust/src/traits/arithmetic/mod.rs at
//! ef1a238634d6196b01a1a1e77d3d5ad2340e3094.
//! This is not an OpenDP integration test and does not invoke the sampler.

#![forbid(unsafe_code)]

use std::convert::TryFrom;

// Mirrors:
// upper.alerting_sub(&lower)?.alerting_sub(&T::one())?
// after replacing AlertingSub with its checked_sub primitive.
macro_rules! original_trial_count {
    ($function:ident, $type:ty) => {
        fn $function(lower: $type, upper: $type) -> Option<usize> {
            let width = upper.checked_sub(lower)?;
            let trials = width.checked_sub(1)?;
            usize::try_from(trials).ok()
        }
    };
}

original_trial_count!(original_i8, i8);
original_trial_count!(original_i16, i16);
original_trial_count!(original_i32, i32);
original_trial_count!(original_u8, u8);

// An independent widened-arithmetic *oracle*, not a production patch.
// Inputs to this helper are the explicitly enumerated types above.
fn desired_trials(lower: i128, upper: i128) -> Option<usize> {
    let width = upper.checked_sub(lower)?;
    let trials = width.checked_sub(1)?;
    usize::try_from(trials).ok()
}

#[test]
fn signed_i8_width_is_representable_after_widening() {
    // Width 127: both the original computation and oracle succeed.
    assert_eq!(original_i8(-128, -1), Some(126));
    assert_eq!(desired_trials(-128, -1), Some(126));

    // Width 128: 127 trials fit in both i8 and usize, but the
    // *intermediate* i8 subtraction attempts to represent 128.
    assert_eq!(original_i8(-128, 0), None);
    assert_eq!(desired_trials(-128, 0), Some(127));
    assert_eq!(original_i8(-64, 64), None);
    assert_eq!(desired_trials(-64, 64), Some(127));

    // Width 255: the trial count is usize-representable.
    assert_eq!(original_i8(i8::MIN, i8::MAX), None);
    assert_eq!(desired_trials(i8::MIN as i128, i8::MAX as i128), Some(254));
}

#[test]
fn signed_i16_and_i32_repeat_the_overflow() {
    assert_eq!(original_i16(i16::MIN, 0), None);
    assert_eq!(desired_trials(i16::MIN as i128, 0), Some(32767));

    assert_eq!(original_i32(i32::MIN, 0), None);
    assert_eq!(
        desired_trials(i32::MIN as i128, 0),
        Some(2_147_483_647)
    );
}

#[test]
fn unsigned_full_range_has_no_intermediate_overflow() {
    assert_eq!(original_u8(0, u8::MAX), Some(254));
    assert_eq!(desired_trials(0, u8::MAX as i128), Some(254));
}

#[test]
fn widened_oracle_rejects_unrepresentable_cases() {
    // The original sampler bypasses these zero-width cases before
    // trial arithmetic, but the oracle itself must not invent a count.
    assert_eq!(desired_trials(0, 0), None);
    assert_eq!(desired_trials(1, 0), None);

    // i128 cannot hold this extreme mathematical difference.
    assert_eq!(desired_trials(i128::MIN, i128::MAX), None);
}
