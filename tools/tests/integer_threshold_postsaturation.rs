//! Standalone native Rust saturation reproducer for audit issue #58.
//!
//! Models the strict IBig comparison followed by SaturatingCast<IBig>
//! using wider built-in integers. This does NOT import Dashu/OpenDP, call
//! the noise sampler or test the full DP measurement.
#![forbid(unsafe_code)]

fn saturating_u8(large: u16) -> u8 {
    u8::try_from(large).unwrap_or(u8::MAX)
}
fn saturating_i8(large: i16) -> i8 {
    i8::try_from(large).unwrap_or(if large > 0 { i8::MAX } else { i8::MIN })
}
fn saturating_u64(large: u128) -> u64 {
    u64::try_from(large).unwrap_or(u64::MAX)
}
fn saturating_i64(large: i128) -> i64 {
    i64::try_from(large).unwrap_or(if large > 0 { i64::MAX } else { i64::MIN })
}

#[test]
fn unsigned_u8_upper_boundary_aliases_public_threshold() {
    let threshold = u8::MAX as u16;
    let noisy = threshold + 1;
    assert!(noisy > threshold);
    assert_eq!(saturating_u8(noisy), u8::MAX);
}
#[test]
fn signed_i8_negative_boundary_aliases_public_threshold() {
    let threshold = i8::MIN as i16;
    let noisy = threshold - 1;
    assert!(noisy < threshold);
    assert_eq!(saturating_i8(noisy), i8::MIN);
}
#[test]
fn wide_unsigned_and_signed_aliases() {
    let upper = u64::MAX as u128;
    assert!(upper + 1 > upper);
    assert_eq!(saturating_u64(upper + 1), u64::MAX);

    let lower = i64::MIN as i128;
    assert!(lower - 1 < lower);
    assert_eq!(saturating_i64(lower - 1), i64::MIN);
}
#[test]
fn normal_in_range_values_remain_strict() {
    assert_eq!(saturating_u8(11), 11);
    assert_eq!(saturating_i8(-11), -11);
    assert_eq!(saturating_u64(11), 11);
    assert_eq!(saturating_i64(-11), -11);
}
