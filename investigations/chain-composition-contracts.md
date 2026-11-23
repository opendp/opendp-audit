---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Chaining contracts: stability, privacy maps and postprocessing

## Property and scope

Verify the framework's **non-adaptive** composition paths (i) transformation then measurement, (ii) transformation then transformation, and (iii) measurement then postprocessing. Sources: [chain constructors](../source/rust/src/combinators/chain/mod.rs.md), [core function/map combinators](../source/rust/src/core/mod.rs.md), [upstream chain unit tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/test.rs), [FFI tests and entrypoints](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/ffi.rs), and [shift operator wiring](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/combinators/chain/shr/mod.rs).

## Cross-file argument

For a valid transformation `T0` from input metric `M0` to intermediate metric `MX`, let `s0(d)` be its stability map. For a valid measurement `M1` on `MX` with monotone conservative privacy map `p1`, any adjacent inputs with initial metric distance at most `d` yield intermediate distance at most `s0(d)`; the two releases are therefore `p1(s0(d))`-close. The constructor checks equality of the intermediate domain and metric, builds `M1.function ∘ T0.function`, and `PrivacyMap::make_chain(p1, s0)` computes precisely this order. Both component maps evaluate fallibly and propagate errors.

For transformations `T0`, `T1`, the corresponding composition uses `T1.function ∘ T0.function` and `s1(s0(d))` after the same intermediate checks. A monotone stability map `s1` propagates the outer bound. The input and output metadata selected for the chained transformation are the respective inner input and outer output.

For non-interactive postprocessing `F1`, the release is `F1(M0(input))` and the privacy map remains exactly `M0.privacy_map`. Under the data-processing theorem, deterministic or data-independent randomized postprocessing cannot worsen the divergence of the release distribution. A fallible result, including an error, may be treated as part of the postprocessed observable output as long as it is determined by the DP release and public state. An adversarial callback with access to original confidential data or side effects **violates the postprocessing premise** and is not covered by these combinators' contracts.

The underlying core helpers use `outer(&inner(input)?)`, establishing order and early return for an inner error. Each helper clones its `Arc` callback before embedding it in the composed callback. No transformed map incorrectly reverses its components. The FFI functions delegate to the same typed implementations; the shift-operator overloads call the corresponding constructors in inner-to-outer order.

## Executed checks and existing upstream coverage

**Actually executed:** A local Python 3 abstract model seeded with `20261122` ran **10,000** bounded nonnegative linear-map cases, verifying the direct function composition, composed privacy/stability map algebra, and retention of the original postprocessed privacy map. **Four** separate cases tested inner/outer failure short circuit for both function and map models. All passed. This is an **algebraic model of the source code, not an execution of compiled OpenDP**.

**Inspected but not executed:** Upstream Rust `test_make_chain_mt`, `test_make_chain_tt`, `test_make_chain_pm` and corresponding FFI tests exercise normal composition and map values. They do not explicitly cover all error propagation and mismatching metadata cases. No native Rust toolchain or upstream source checkout was available in the audit workspace.

## Conclusion and limitations

**No bug found in the declared bounded composition properties**, assuming component transformation/measurement contracts and appropriate domain/metric equality. The code correctly composes the functions and maps in the same order and preserves the original privacy map for postprocessing. The status `Audited` applies only to those algebraic properties, not to custom callback correctness or the mathematical proof obligations of every component.

The review did not examine `partials` feature-gated chaining, stateful adaptive composition, arbitrary custom domain equality implementations, or callbacks that directly access private inputs after measurement. Existing upstream historical [issue #134](https://github.com/opendp/opendp/issues/134) for the `make_chain_mt` proof is closed, as is [issue #48](https://github.com/opendp/opendp/issues/48) for FFI type validation. Open/closed upstream issues and PRs, as well as audit-repository issues, were searched; none justified a new candidate defect issue for this scope.

## Next checks

Run compiled Rust and FFI tests, plus negative tests for mismatched intermediate domains/metrics and errors raised by either map. Audit user-defined `Domain::PartialEq` and `partials` chaining separately if those are needed for a concrete claim.
