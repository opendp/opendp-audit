---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Polars HStack column replacement and grouping-certificate lineage

## Invariant and threat model

For an HStack projection, the output domain and distance map must not retain a grouping certificate after a replacement changes a column on which the certificate depends. The frame's protected ID expression must not be overwritten. Incorrect retention could make a later group-wise sensitivity calibration too small. The review is limited to source-level lineage and public projection semantics; no end-to-end private release was used.

## Affected symbols and source audits

- [`make_h_stack` source audit](../source/rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs.md), [pinned upstream constructor](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/h_stack/mod.rs).
- [Shared lineage-helper source audit](../source/rust/src/transformations/make_stable_lazyframe/mod.rs.md), [pinned helper implementation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/mod.rs).
- [Projection options contract](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/polars/options.rs); [upstream HStack tests](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/make_stable_lazyframe/h_stack/test.rs).

## Reasoning and executed evidence

1. **Writes and names.** All HStack expressions are stabilized against the same input domain in row-by-row context. Output domains are assembled in input order then write order, using a name-to-index lookup; an existing name gets the new column domain and a new name appends. The constructor rejects projection options disabling broadcasting or duplicate checks.
2. **Identity and invalidation.** A write is ignored as a change only for a direct column reference to the output name or nested aliases of such a column. All other writes mark the **output name** changed. A certificate that depends explicitly on a changed output name is dropped; a wildcard/multiple-output selector is dropped on any change; by-empty frame certificates are retained. Adding `new = x + 1` does not change existing `k` groups, but dynamic selectors may gain `new` and are therefore dropped. Both `output_domain.margins` and `StabilityMap`-output `Bounds` use the identical pruning predicate.
3. **Protected identifiers.** When the intermediate metric has a `SymmetricIdDistance` identifier, the constructor compares *every* written output name (including identity writes) with the identifier expression's root column names and rejects any intersection. This is conservative for identities and sufficient for ordinary identifier expressions whose root names are complete. The source does not independently validate the dependency metadata of exotic expressions.
4. **Existing upstream runtime evidence.** The upstream HStack tests cover nonidentity overwrites, original grouping by a computed cast key, ordinary and selector grouping, contribution bounds, projection option rejection, and identities. They were **read but not run** in this session.

**Actually executed:** Standard-library Python [source-model tests](../tools/tests/test_hstack_lineage_model.py): **1,280** exhaustive output/source-name × dependency-mask × selector cases, **20,000** deterministic randomized cases, plus targeted identifier and new-column checks. All passed. This is an abstract reproduction of the source's set rules, **not compiled Rust or Polars**, and it relies on a declared dependency-root oracle rather than inferring one from real query plans.

## Findings

**No bug found within the declared source-level properties.** The implemented invalidation is conservative given accurate Polars metadata. The audit remains **Partial** for privacy-relevant lineage because `root_names()` and `has_multiple_outputs()` correctness for all supported expression forms, actual optimizer execution, and ID-expression semantics were not independently verified. Existing audit and upstream open/closed issues and PRs were searched for HStack grouping/identifier lineage; no matching defect or claim was identified when this audit began. [Audit task #55](https://github.com/opendp/opendp-audit/issues/55) reserves and records this bounded review; it is not a defect report.

## Unresolved questions

Run native Polars experiments with computed or nested-alias grouping keys, selectors, and `SymmetricIdDistance` identifiers after optimizing the plan. Verify actual output membership and groupwise differences, and revisit this property after any changes to Polars projection metadata.
