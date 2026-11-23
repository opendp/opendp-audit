---
schema_version: 1
source: rust/src/measurements/noise_threshold/mod.rs
updated: 2026-11-23
---

# `rust/src/measurements/noise_threshold/mod.rs`

## Scope and assumptions

- **Audit scope:** The core `ZExpFamily<P>::make_noise_threshold` implementation over `HashMap<TK, IBig>`: explicit-zero handling, strict signed threshold filtering, and the ordering of retained pairs. Includes the corresponding Laplace/Gaussian wrapper and regression-test paths.
- **Invariants:** (1) Adding or deleting explicit `(key, 0)` entries cannot affect the release distribution over nonzero keys. (2) A successful release retains an eligible sampled pair only when the noisy count is **strictly** beyond the threshold in its signed direction. (3) Released hash-map order must not preserve input insertion ordering as a deterministic side channel.
- **Assumptions:** `ZExpFamily<P>` is a valid distribution, individual `Sample::sample` calls implement the specified independent additive-noise law, and `Vec::shuffle` implements an input-order-independent random permutation when it succeeds. This audit does **not** verify those sampler contracts or the complete privacy map.
- **Pinned source:** [Core threshold mechanism](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/mod.rs#L69-L131), [sample contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/mod.rs), [shuffle implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/mod.rs), [Laplace tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/laplace/test.rs), and [Gaussian tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise_threshold/distribution/gaussian/test.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `measurements::noise_threshold::MakeNoiseThreshold::make_noise_threshold_for_ZExpFamily` | correctness/zero-key-equivalence | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Zero-key analysis](#zero-key-equivalence) |
| `measurements::noise_threshold::MakeNoiseThreshold::make_noise_threshold_for_ZExpFamily` | correctness/strict-threshold | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Threshold comparison](#strict-threshold-comparison) |
| `measurements::noise_threshold::MakeNoiseThreshold::make_noise_threshold_for_ZExpFamily` | privacy/output-order-independence | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Output ordering](#output-ordering) |

## Analysis

### Zero-key equivalence

The input is a hash map, under `L0PInfDistance`, which treats absent keys as zero. At the start of the release closure, `.filter(|(_, v)| *v != &IBig::ZERO)` removes all explicitly zero-valued entries *before* sampling noise. Consequently, the list of nonzero key/value pairs forwarded to the noise sampler is the same whether additional explicit zero entries are present or absent. Under the stated iid sampling and unbiased shuffle assumptions, the release distribution of the nonzero keys is identical. This is not a guarantee of identical outputs for two independent invocations.

The type-specific integer adapter preserves zero on conversion to `IBig`. The float adapter quantizes values before the core measurement; values rounded to integer-grid zero are likewise suppressed, with quantization error accounted for by a separate stability map not audited here.

Existing upstream tests cover explicit zeros for both Laplace and Gaussian mechanisms at thresholds `-1` and `1`, opposite-sign nonzero keys, and the float-to-grid zero case. These tests were **read, not executed** during this session.

**Conclusion:** No discrepancy found in the scoped zero-key handling. Previously addressed in [upstream PR #3058](https://github.com/opendp/opendp/pull/3058) (merged 2026-10-23). The `Audited` status is limited to the stated representation-invariance behavior and sampler assumptions, not an end-to-end privacy proof.

### Strict threshold comparison

For a positive threshold, `keep_ordering = Ordering::Greater`; for a negative threshold, `keep_ordering = Ordering::Less`. After adding noise, each successful sample is retained only when `noisy_value.cmp(&threshold) == keep_ordering`, so equality is excluded in either direction. The map predicate passes `Err` values through to `collect::<Fallible<_>>()`, which propagates a sampling failure instead of silently dropping it. This prevents error values from being confused with ineligible noisy counts.

The existing zero-scale Laplace and Gaussian tests verify equality exclusion and the strict greater-than / less-than behavior in both threshold directions. The float adapter explicitly rejects negative thresholds; the signed-negative case here applies to supported integer-based inputs.

**Conclusion:** The source-level comparison and error forwarding implement the stated strict signed threshold condition. No defect identified within this invariant.

**Scope qualification:** This statement applies to the **integer-stage** output, before any float reconversion. The non-deprecated float Laplace/Gaussian adapters can round a retained value back to the public threshold; see [float threshold post-rounding audit](nature/float/mod.rs.md) and [issue #44](https://github.com/opendp/opendp-audit/issues/44). This does not change the correctness of the integer comparison or establish a privacy-accounting violation.

**Integer adapter qualification:** The integer threshold adapter can likewise return the public threshold **after** its saturating cast: an `IBig` value of `256` passes a `u8` threshold of `255`, but saturates to `255u8` in the final map. The negative `i8::MIN` boundary behaves analogously. See the [integer post-saturation source audit](nature/integer/mod.rs.md), [investigation](../../../../../investigations/integer-threshold-postsaturation.md), and [issue #58](https://github.com/opendp/opendp-audit/issues/58). The core `IBig` comparison remains correct, and no privacy-accounting failure is implied.

### Output ordering

The core closure collects eligible `(key, noisy_count)` pairs into a vector, calls `pairs.shuffle()?`, and only then builds a new `HashMap`. This avoids deterministically forwarding the input iteration order to the result, including when keys collide. The shuffle implementation uses `SliceRandom::shuffle` with `GeneratorOpenDP`. The upstream `test_noise_threshold_shuffles_colliding_keys` regression uses colliding hashes and checks that an output permutation outside the original cyclic orders is observed across trials.

**Conclusion:** The implementation includes the expected shuffle, resolving the earlier issue of missing output randomization. [Upstream issue #3228](https://github.com/opendp/opendp/issues/3228) was addressed by [merged PR #3232](https://github.com/opendp/opendp/pull/3232) (2026-11-18).

**Limitations:** This review did not execute a distributional test, formally establish `GeneratorOpenDP` properties, or analyze error/timing side channels from sampling and shuffling. For this reason, the broader `privacy/output-order-independence` status is `Partial`.

### Verification

**Performed:** Pinned-source inspection of the core closure, the Laplace and Gaussian wrappers, the `Sample` contract, the shuffle implementation, and existing upstream regression tests; review of upstream issue/PR disposition. **Not performed:** A compiled Rust test run, an entropy-failure experiment, or a full proof check of the Laplace/Gaussian threshold privacy maps.

## Next checks

- Run the compiled regression tests from `rust/src/measurements/noise_threshold/{test.rs,distribution/laplace/test.rs,distribution/gaussian/test.rs}` on the reviewed upstream revision.
- Verify distribution-level coupling and permutation independence under hash collisions, and separately assess data-dependent entropy failures or timing channels.
- Review the `L01InfDistance`/`L02InfDistance` privacy-map tail bounds and the float quantization stability map; neither is covered by this source report.
