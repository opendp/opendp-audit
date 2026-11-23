---
schema_version: 1
source: rust/src/combinators/chain/shr/partials.rs
updated: 2026-11-22
---

# `rust/src/combinators/chain/shr/partials.rs`

## Scope and assumptions

- **Scoped property:** Under the `partials` Cargo feature, each of the twelve `Shr` overloads for deferred transformation and measurement constructors must `fix` its upstream partial using the correct public `(Domain, Metric)` pair, compose in left-to-right order, and propagate construction errors before evaluating downstream constructors.
- **Contract assumptions:** Each `PartialTransformation` or `PartialMeasurement` constructor obeys the `fix` input-space contract; each returned concrete transformation/measurement satisfies its component stability/privacy invariants and has no privacy-relevant side effects during construction. Inputs to the partial factory are public domain/metric descriptions. A postprocessing transformation reads only the released value and public state.
- **Revision:** [Partial-chain overloads](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/shr/partials.rs), [core `PartialTransformation` / `PartialMeasurement` definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs), [ordinary typed chaining](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/mod.rs), and [operator module](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/shr/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `PartialTransformation >> Transformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `Transformation >> PartialTransformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `Fallible<Transformation> >> PartialTransformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `PartialTransformation >> PartialTransformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `(DI, MI) >> PartialTransformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `PartialTransformation >> Measurement` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `Transformation >> PartialMeasurement` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `Fallible<Transformation> >> PartialMeasurement` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `PartialTransformation >> PartialMeasurement` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `(DI, MI) >> PartialMeasurement` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `PartialMeasurement >> Function` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |
| `PartialMeasurement >> Transformation` | correctness/partial-fix-order | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Construction and error trace](../../../../../../investigations/partial-chain-fix-propagation.md) |

## Analysis

### Deferred constructor ordering — `correctness/partial-fix-order`

**Conclusion:** No violation identified in the twelve overloads under the stated component contracts. Every overload with a left partial fixes the left operand from the requested input space. Where the right operand is partial, it is fixed using the *resolved left output domain and metric*, rather than the original input space. Fixed right operands remain fixed, and concrete composition then delegates to `make_chain_tt`, `make_chain_mt`, or `make_chain_pm`. Two `(DI, MI) >> Partial*` overloads just call `fix` on the supplied public space. Both `Fallible<Transformation> >> Partial*` overloads unwrap the left result with `?` before fixing the right. A left-partial failure likewise short-circuits, and errors in the concrete chaining constructors remain fallible.

**Postprocessing:** The `PartialMeasurement >> Function` and `PartialMeasurement >> Transformation` overloads delegate to `make_chain_pm`; the latter intentionally passes only the transformation's function, not its input domain or stability map. Under the postprocessing premise, this preserves the original DP map. It does *not* certify that every measurement output lies in an arbitrary transformation's input domain: the measurement's output type is known, but no output domain is stored.

**Source-level test evidence:** A standalone Python 3 model of the twelve overload traces passed all twelve expected constructor sequences, error short-circuit cases for each stage (including two `Fallible`-input errors), and 5,000 algebraic composition instances. The test **models** the source order; it does not run the compiled OpenDP Rust code. The upstream `test_shr` checks one generated chain using `then_clamp`, `then_sum`, and `then_laplace`; it was read but not executed.

**Limitations:** Rust's `FnOnce` partial closure is arbitrary; the code does not independently prove that a user-defined closure returns a transformation whose input metadata equals the supplied `fix` arguments, nor that such a constructor is pure. The returned typed constructors are checked by the ordinary `make_chain_*` functions where an intermediate comparison exists. We did not audit all generated `then_*` constructors, user callbacks, non-default feature combinations, generic `Domain::PartialEq` implementations, or native debug/release execution. See [investigation](../../../../../../investigations/partial-chain-fix-propagation.md).

## Next checks

Run native Rust tests with `partials` enabled, including mismatch and error callbacks for both deferred operands and stage-specific failure. Add a test for `PartialTransformation >> PartialMeasurement` that verifies the right constructor receives the resolved left output domain/metric. No new defect or issue is justified for this bounded property.
