---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Privacy measure casts: pure DP, zCDP and fixed approximate DP

## Scope and invariant

Audit the non-deprecated public conversion combinators at OpenDP commit `ef1a238634d6196b01a1a1e77d3d5ad2340e3094`: `make_pureDP_to_zCDP`, `make_fixed_approxDP_to_approxDP`, `make_approximate`, and the wrapper of `make_zCDP_to_approxDP`. Output distributions must be unchanged; the new privacy parameters must be no more optimistic than those justified by the original parameters, for valid input measurement contracts. Numerical implementation of `cdp_delta` and custom user-defined measures are external to this bounded review.

Source reports: [pure DP to zCDP](../source/rust/src/combinators/measure_cast/pureDP_to_zCDP/mod.rs.md), [fixed approximate DP](../source/rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/mod.rs.md), [zero-slack lifting](../source/rust/src/combinators/measure_cast/approximate/mod.rs.md), and [zCDP profile wrapper](../source/rust/src/combinators/measure_cast/zCDP_to_approxDP/mod.rs.md).

## Mathematical arguments

**Pure DP to zCDP:** If both directional max divergences are bounded by `ε`, then at every Rényi order `α>1`, `D_α(P||Q)≤α ε²/2` (BS16 theorem). The constructor invokes the source privacy map and computes a directed-upward `eps²/2`. Positive infinity is preserved exactly. In native Rust, successful rounding must be upward all the way through `InfPowI` and `InfDiv`. Source: [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/pureDP_to_zCDP/mod.rs).

**Fixed approximate DP to profile:** For any valid `(ε₀,δ₀)`, the profile `δ(ε)=1` below `ε₀` and `δ(ε)=δ₀` at/above `ε₀` is sound. The `δ=1` branch is trivial; above `ε₀` the event inequality becomes only weaker. The input measurement's function is unchanged. This is a conservative profile, not the tightest possible. Source: [constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/measure_cast/fixed_approxDP_to_approxDP/mod.rs).

**Zero-slack and zCDP profile wrappers:** `make_approximate` lifts a valid `d` to `(d,0)` without changing the release. `make_zCDP_to_approxDP` wraps `ρ` in `cdp_delta(ρ, ε)`; if the original source measure also carries `δ`, it returns `(profile,δ)`. The wrapper preserves the input function and metadata, but `cdp_delta` correctness is not established by this argument.

## Executed independent finite reference tests

On 2026-11-22 an independently authored Python idealized model ran with standard-library `math`:

- All 21 strictly positive ternary distributions with probabilities in eighths, plus all 15 strictly positive binary distributions with probabilities in sixteenths.
- Every ordered same-alphabet pair (21² + 15² = **666**), with symmetric `ε=max(log(P_i/Q_i), log(Q_i/P_i))`.
- For `α ∈ {1.5,2,3,5,10}`, computed `D_α(P||Q)` using log-sum-exp and compared to `α ε²/2`. **3,330 passing ordered-pair/order checks**.
- For fixed `ε₀∈{0,0.1,0.5,1,2}`, computed the optimal symmetric approximate-DP event residual `δ₀=max(Σ_i max(0,P_i-exp(ε₀)Q_i), Σ_i max(0,Q_i-exp(ε₀)P_i))`; for nine query `ε` values, checked that its actual event residual was within the fixed-to-profile step curve. **29,970 passing pair/threshold/query comparisons**.

The retained [reference model](../tools/tests/test_measure_cast_reference_model.py) is idealized: finite full-support distributions; Python binary64 log/exp; no native Rust code execution. It does not verify the directed rounding backend, all `α`, all distributions or validity of arbitrary source maps. Tolerance `1e-11` covers modeled floating-point arithmetic.

## Findings and disposition

No counterexamples in the finite reference checks; no source-level metadata miswiring, omitted slack or wrong branch boundary identified. The privacy casts' mathematical formulas are consistent with the documented source guarantees. Overall review is **Partial** pending native execution and numerical proofs. The zCDP `cdp_delta` arithmetic is not duplicated here. No newly confirmed defect warranting a distinct issue was discovered. Existing [audit issue #19](https://github.com/opendp/opendp-audit/issues/19) tracks inversion failure for extremely large finite `ε`, which should not be conflated with the correctness of a forward privacy profile.

## Next checks

- Execute Rust conversion tests with finite subnormal and near-overflow `ε`, source-map failures, and fixed-profile threshold neighbors.
- Reconfirm directed `InfPowI`/ `InfDiv` rounding and numerical behavior in `cdp_delta`.
- Add negative and invalid-parameter tests to ensure failing source measurements do not produce plausible, optimistic output guarantees.
