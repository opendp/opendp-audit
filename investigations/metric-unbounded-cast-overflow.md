---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-22
status: Audited
---

# Metric-unbounded cast: `u32` stability-map overflow

## Invariant and threat model

A transformation that changes its output metric from a bounded distance to an unbounded distance, while leaving datasets unchanged, must report a conservative upper bound on output distances for **all input pairs** that are within an advertised input bound. An erroneous intermediate distance can propagate through composed `PrivacyMap::make_chain` into insufficient reported privacy cost. Failure of this necessary precondition does not itself demonstrate an exploitable DP mechanism.

## Reviewed source paths and records

- [Metric cast report](../source/rust/src/transformations/cast_metric/mod.rs.md) and [reference-model regression](../tools/tests/test_metric_unbounded_cast_overflow.py).
- [Rust `make_metric_unbounded`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/cast_metric/mod.rs) and [bounded metric trait implementations](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/cast_metric/traits.rs).
- [Event-level metric definitions, including `IntDistance = u32`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs); [core `StabilityMap::new`, `Transformation::map`, and `PrivacyMap::make_chain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/core/mod.rs).

## Minimal counterexample and trace

1. Construct `make_metric_unbounded(VectorDomain::new(AtomDomain::<i32>::default()).with_size(1), ChangeOneDistance)`; `get_size()` succeeds, and the function is the identity. Alternatively use `HammingDistance` for an `InsertDeleteDistance` output.
2. The pair `[0]` and `[1]` lies in the domain; the input bounded distance is `1` and the output unbounded distance is `2`. Both pairs are `d_in`-close for `d_in = 2^31`, so the returned upper bound must be **at least 2**.
3. The actual map is `StabilityMap::new(|d_in| d_in * 2)`, where the input and output distances are both `u32`. For `d_in = 2_147_483_648u32`, its exact result is `2^32`, unrepresentable in `u32`. Under unchecked arithmetic the map returns `Ok(0)`; with overflow checks enabled it panics rather than reporting a fallible arithmetic error.
4. `Transformation::map` directly calls the map closure without adjusting the bound to the domain's size. `PrivacyMap::make_chain` evaluates the transformed intermediate distance before the downstream privacy map. Therefore a false zero can propagate into the reported privacy cost, conditional on the chosen downstream measurement. This is a soundness concern, even though no composed production mechanism has been run here.

## Independent verification

- **Executed:** Four Python 3 standard-library tests in [the local reference model](../tools/tests/test_metric_unbounded_cast_overflow.py), including exact `u32` wrapping at the cutoff and all ordered pairs of binary vectors up to size four. The smaller-pair checks establish that, absent overflow, doubling suffices for both bounded/unbounded metric pairs. A size-one witness demonstrates the failure when input bound `d_in` is large. All four passed.
- **Not executed:** Native Rust library or bindings; the audit runtime has no `rustc`/`cargo`. A compiled Rust debug/release regression remains the next decisive runtime check. The static Rust multiplication and `StabilityMap::new` contracts directly establish the failure modes given the standard arithmetic configurations.

## Finding and disposition

**Confirmed analytical/source-level stability-map underestimate for unchecked `u32` multiplication**, plus a checked-build panic path, at pinned upstream `main`. This is an **Unreported** upstream defect after duplicate and open-fix searches. It is tracked in [audit issue #27](https://github.com/opendp/opendp-audit/issues/27) and was audited under [task #25](https://github.com/opendp/opendp-audit/issues/25). Severity depends on whether callers request unusually large bounds; no default-size data computation, direct privacy exploit, or particular private mechanism has been demonstrated.

## Unresolved questions

- Execute the minimal code path in compiled OpenDP Rust with and without overflow checks and through the FFI constructor, verifying a structured error or a conservative value.
- Check any external callers that request large map distances, and the effect of the proposed fallible multiplication on their behavior.
- Replace `d_in * 2` with conservative checked multiplication; do not substitute a wrapping result, and add regression coverage at `2^31 - 1`, `2^31`, and `u32::MAX`.
