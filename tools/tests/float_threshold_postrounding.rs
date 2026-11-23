//! Standalone native Rust rounding reproducer for audit issue #44.
//!
//! Mirrors the accepted integer value and its nearest-float reconversion
//! after the source-level threshold filter. This does NOT link to OpenDP,
//! Dashu, or the actual noise sampler.
#![forbid(unsafe_code)]

#[test]
fn binary64_accepted_integer_rounds_to_threshold() {
    let count = 1u128 << 54;
    let noisy = count + 1;
    let threshold = 1.0f64;
    let grid = 2.0f64.powi(-54);
    assert!(noisy > count);
    let returned = (noisy as f64) * grid;
    assert_eq!(returned, threshold);
    assert!(threshold + grid == threshold);
}

#[test]
fn binary32_accepted_integer_rounds_to_threshold() {
    let count = 1u128 << 26;
    let noisy = count + 1;
    let threshold = 1.0f32;
    let grid = 2.0f32.powi(-26);
    assert!(noisy > count);
    let returned = (noisy as f32) * grid;
    assert_eq!(returned, threshold);
    assert!(threshold + grid == threshold);
}

#[test]
fn binary64_integer_grid_rounds_to_large_threshold() {
    let count = 1u128 << 54;
    let noisy = count + 1;
    assert!(noisy > count);
    assert_eq!(noisy as f64, count as f64);
}

#[test]
fn sufficiently_large_increment_stays_visible() {
    let count = 1u128 << 52;
    let noisy = count + 1;
    let threshold = 1.0f64;
    let returned = (noisy as f64) * 2.0f64.powi(-52);
    assert!(returned > threshold);
}
