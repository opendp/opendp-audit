---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Partial
---

# Bounded geometric mechanism: signed-interval trial-width overflow

## Invariant and threat model

The non-deprecated bounded `make_geometric` mechanism should support a signed integer interval when `upper - lower - 1` is nonnegative and representable as a `usize` trial count, subject to explicit resource limits. A computation that overflows a narrower temporary `T` even though the trial count fits `usize` is an avoidable **functional availability defect**, not a privacy breach. The scoped threat is valid positive-scale calls to the public bounded constructor followed by scalar or nonempty vector invocation.

**Issue state:** **Confirmed by pinned-source control flow and exact integer arithmetic**, strengthened by a **compiled standalone native Rust arithmetic reproducer** (four tests passed in audit CI). The full OpenDP Rust measurement has **not** been compiled or invoked for this reproduction. The investigation remains `Partial` pending that integration test and an upstream fix.

## Affected symbols and source audits

- [Sampler source audit](../source/rust/src/traits/samplers/geometric/mod.rs.md) — `sample_discrete_laplace_linear<T,P>` computes `upper.alerting_sub(lower)?.alerting_sub(1)?` before widening.
- [Measurement source audit](../source/rust/src/measurements/noise/distribution/geometric/mod.rs.md) — `make_geometric` and `ConstantTimeGeometric::make_noise` construct the measurement and defer width arithmetic until invoke.
- [Upstream sampler](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/samplers/geometric/mod.rs); [checked integer subtraction](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/traits/arithmetic/mod.rs); [bounded constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/distribution/geometric/mod.rs).
- **Candidate-defect issue:** [opendp-audit #4](https://github.com/opendp/opendp-audit/issues/4).

## Reasoning and evidence

### Minimal deterministic counterexample

Choose `T = i8`, `scale = 1.0`, `lower = i8::MIN (-128)`, `upper = 0_i8`, and scalar `input = 0_i8`. Bounds satisfy `lower <= upper`, the scale is finite and positive, and the intended number of Bernoulli trials for the bounded sampler is `upper - lower - 1 = 127`, which fits both `i8` and `usize`. However the implementation evaluates `upper.alerting_sub(&lower)?` first, in `i8`. Its mathematical result is `128`, which is outside `[-128,127]`, so the checked subtraction returns `Overflow` and short-circuits. No sampler entropy is consumed. The same error occurs for any nonempty vector using the same bounds; the scalar mechanism wraps the input in a singleton vector. Empty vector invocation does **not** call the sampler and thus can succeed.

The independent Python 3 check of the exact integer ranges demonstrated:

| Type | Bounds | Exact width | Trial count | First checked subtraction |
| --- | --- | ---: | ---: | --- |
| `i8` | `(-128,-1)` | 127 | 126 | Succeeds |
| `i8` | `(-128,0)` | 128 | 127 | **Overflow** |
| `i8` | `(-64,64)` | 128 | 127 | **Overflow** |
| `i8` | `(-128,127)` | 255 | 254 | **Overflow** |
| `i16` | `(-32768,0)` | 32768 | 32767 | **Overflow** |
| `i32` | `(-2147483648,0)` | 2147483648 | 2147483647 | **Overflow** |
| `u8` | `(0,255)` | 255 | 254 | Succeeds |

For each overflowing example, the exact trial count fits `usize` on both 32-bit and 64-bit platforms. The error stems from the order and width of intermediate arithmetic, not an inability to allocate the count type. This is conclusive for the source's arithmetic path; **OpenDP Rust itself was not run**.

### Compiled standalone Rust arithmetic reproduction

The audit repository now contains a dependency-free [Rust test harness](../tools/tests/geometric_trial_width.rs), executed by its GitHub Actions workflow at [run #45098886613](https://github.com/opendp/opendp-audit/actions/runs/45098886613) (commit [`458218e`](https://github.com/opendp/opendp-audit/commit/458218e348d6bf64b9e1f85f2f004d5e9b4c43f8)). The workflow compiled the harness with `rustc --edition=2021 --test` and reported **four tests passed, zero failed**, alongside passing Python tests and Markdown validation.

The harness reproduces the relevant **native Rust `checked_sub` primitives** used by OpenDP's `AlertingSub` implementation, confirms the failing signed `i8`, `i16`, and `i32` intervals, verifies the unsigned `u8` control case, and checks exact trial counts using a widened `i128` oracle. It does **not** import or invoke OpenDP's `sample_discrete_laplace_linear` or `make_geometric`; consequently, this is native Rust arithmetic evidence rather than a native OpenDP integration regression. The pinned OpenDP implementation is still required to establish its full runtime and constructor behavior experimentally.

### Bounded-noise distribution sanity check

An independent Python 3 `fractions.Fraction` model reconstructed the sampler's two signed proposals, `trials+1` Bernoulli draws, the single signed-zero rejection, conditioning on acceptance, type-bound saturation, and final application-bound clamping. For both `u8` and `i8` machine ranges, six small intervals for each type, six probabilities `p ∈ {1/16,1/4,1/2,3/4,15/16,1}`, and seven representative inputs per interval, it compared **504** full output PMFs to the exact clamped discrete Laplace law with `a=1-p`. All **504** matched at every output atom using rational arithmetic. It is evidence that the bounded proposal scheme is consistent on these small widths, not proof of actual floating-point Bernoulli correctness, constant-time execution, or broad distribution soundness. The native Rust tests were not run.

### Duplication and upstream disposition

A search of both audit and upstream issues, and upstream PRs for signed geometric bounds/interval overflow, found no matching open report or fix at the pinned revision. [Upstream issue #3012](https://github.com/opendp/opendp/issues/3012) and merged [PR #3089](https://github.com/opendp/opendp/pull/3089) address **biased probabilities near the minimum integer boundary**, a different defect. This width-overflow behavior remains in the reviewed upstream `main`. **Disposition: Unreported upstream, confirmed in audit issue #4; no upstream issue or PR opened.**

## Findings

**Confirmed functional availability defect:** bounded positive-scale geometric sampling uses signed-type intermediate subtraction and fails when the interval width exceeds `T::MAX` but its intended trial count fits `usize`. The constructor may succeed while scalar/nonempty-vector invocation fails. Not a confirmed privacy leak.

**Separate negative result:** The independent small-width distribution model found no discrepancy in 504 exact-rational PMF checks. That limited distribution coverage remains `Partial`.

## Unresolved questions

- Run a **compiled OpenDP integration regression** for successful bounded `make_geometric` construction and invocation failure at `i8` bounds `(-128,0)`; the existing standalone compiled Rust test covers only the checked-arithmetic primitive. After widening trial-count arithmetic upstream, require the integration test to pass.
- Decide whether and how to reject genuinely unaffordable or non-`usize`-representable widths in the constructor rather than delaying errors to invocation.
- Separately test the actual constant-time and directed-floating-point Bernoulli implementations, including extreme scales.
