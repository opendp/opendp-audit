---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Integer threshold mechanism: post-saturation strictness failure

## Invariant and threat model

The non-deprecated public `make_laplace_threshold` and `make_gaussian_threshold` APIs release only noisy values strictly beyond a public threshold. For integer-valued maps, the threshold is checked in an arbitrary-precision integer representation (`IBig`), and the output is later converted to a potentially narrower native integer type by saturation. The privacy question is distinct from the utility contract: the final cast is deterministic postprocessing of a DP mechanism, so it cannot alone invalidate the privacy accounting.

## Affected symbols and related findings

- [Integer adapter source audit](../source/rust/src/measurements/noise_threshold/nature/integer/mod.rs.md); [upstream integer adapter](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/nature/integer/mod.rs).
- [Core threshold source audit](../source/rust/src/measurements/noise_threshold/mod.rs.md); [pinned core implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs).
- [Saturating native integer conversions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/cast/mod.rs); [Laplace public contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/mod.rs); [Gaussian public contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/mod.rs).
- [Candidate defect #58](https://github.com/opendp/opendp-audit/issues/58) (this integer saturation path); [related float-only rounding defect #44](https://github.com/opendp/opendp-audit/issues/44).

## Reasoning and evidence

### Deterministic positive-probability witnesses

The exposed `IntExpFamily<P>::make_noise_threshold` implementation computes `t_int >> m_noise >> then_saturating_cast_hashmap`, with the following behavior for one key and a selected noise event:

| Native type | Public input / threshold | Noise event | Accepted `IBig` comparison | Returned native count |
| --- | --- | --- | --- | --- |
| `u8` | `255 / 255` | `+1` | `256 > 255` | `255` |
| `u16` | `65535 / 65535` | `+1` | `65536 > 65535` | `65535` |
| `i8` | `-128 / -128` | `-1` | `-129 < -128` | `-128` |
| `i16` | `-32768 / -32768` | `-1` | `-32769 < -32768` | `-32768` |

All native input values are in range and nonzero, so the core's explicit-zero suppression does not apply. For a finite positive scale such as `1`, each specified noise increment has positive probability in both discrete Laplace (`P=1`) and discrete Gaussian (`P=2`) mechanisms. The extra comparison error is caused solely by **post-filter saturation**, not an error in the core `IBig` strict inequality.

The Rust `SaturatingCast<IBig>` implementations explicitly invoke `T::try_from(value)` and fall back to `T::MAX` for out-of-range positive values and `T::MIN` for out-of-range negative values. That conversion is data-independent after the noise draw. Applying an additional strict filter over final native values is DP-preserving postprocessing; whether it matches the intended utility contract is a specification choice.

### Reproducible models and verification level

The standard-library [Python model](../tools/tests/test_integer_threshold_postsaturation.py) implements exact unbounded-integer addition, the strict signed threshold predicate, and a native integer saturation oracle. It checks both boundary directions for signed widths `8,16,32,64,128`, upper boundaries for unsigned widths `8,16,32,64,128`, as well as controls for non-extreme thresholds and rejected noise. The model does not execute the OpenDP sampler or guarantee that a real Rust invocation reaches every modeled state.

The [standalone Rust regression](../tools/tests/integer_threshold_postsaturation.rs) uses native `TryFrom` with the same positive/negative fallback semantics as `SaturatingCast<IBig>`, but computes the intermediate count in an available wider integer type. This independently exercises the actual native cast behavior for `u8`/`i8` and `u64`/`i64` boundaries. It **does not** import OpenDP or its arbitrary-precision Dashu types.

**Verdict:** Source-stage ordering plus exact integer saturation establish a **confirmed functional output-contract defect** on positive-probability noise outcomes. Full native OpenDP integration remains untested; the investigation is `Partial` for the full behavior, privacy-map correctness, and potential remediation.

## Findings

**Confirmed, unreported integer-specific bug:** A retained, strictly beyond-threshold `IBig` value can convert back into a native integer exactly equal to the public threshold. [Audit issue #58](https://github.com/opendp/opendp-audit/issues/58) is scoped to this integer saturation path. No upstream issue or PR fixing this integer-specific defect was found in targeted searches. The similar [float issue #44](https://github.com/opendp/opendp-audit/issues/44) concerns a distinct rounding operator and input class.

## Unresolved questions

- Add compiled OpenDP integration tests for `u8::MAX` and `i8::MIN` thresholds and the relevant `+1`/`-1` noise outcomes, for both Laplace and Gaussian releases.
- Enforce the output contract with an explicit final comparison in native type, or clarify that the threshold only constrains the pre-cast noisy `IBig` value.
- Check that the fix retains correct signed/unsigned behavior on all native integer widths and has no unintended privacy-map or runtime effects.
