---
schema_version: 1
source: python/src/opendp/extras/_ibis/__init__.py
updated: 2026-11-23
---

# `python/src/opendp/extras/_ibis/__init__.py`

## Scope and assumptions

- **Audit scope:** `run_on_database` handling of the scalar result of a translated bounded integer DP `SUM` when the underlying private SQL table has zero or one row. Trace `split_polars_on_ffi`, raw SQL result materialization, scalar extraction, parameter decoding, and noise construction/invocation. Inspect pending upstream replacements.
- **Invariants:** The privacy guarantee for valid adjacent datasets must include all observable outcomes of executing the query, including errors before noise. The result of a translated supported numeric aggregate must meet the noise input carrier, independently of whether the private table is empty.
- **Assumptions:** A SQLite source table with public schema `ints INTEGER`, no public positive minimum row count, contribution cap at least 1, public sum clipping bounds 0 through 10, and a supported `dp.sum` query; empty and one-row datasets are adjacent. The `polars-to-ibis` lowering is pinned at `ce0296a0f7a4cc7546521db7a5fa9fad39d11331`, and the OpenDP source is pinned at `a010591f55b1713c926f8e355091471634480307`.
- **Execution boundary:** Standard-library `sqlite3` and source-equivalent Python extraction were executed. The local environment lacks the compiled `opendp` library and the `polars`, `ibis`, `polars_to_ibis` packages. No native Context/Ibis/noise call was executed.
- **Pinned sources:** [OpenDP Ibis adapter](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/_ibis/__init__.py), [translator SQL sum handler](https://github.com/opendp/polars-to-ibis/blob/ce0296a0f7a4cc7546521db7a5fa9fad39d11331/src/polars_to_ibis/_parse/value_handlers.py), [translator expected bounded-sum SQL](https://github.com/opendp/polars-to-ibis/blob/ce0296a0f7a4cc7546521db7a5fa9fad39d11331/tests/config_split.py), [cross-file investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/ibis-empty-sql-sum-pre-noise-null.md).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `opendp.extras._ibis.run_on_database` | privacy/pre-noise-sql-null | Partial | `a010591f55b1713c926f8e355091471634480307` | [SQL empty-sum result and error boundary](#sql-empty-sum-result-and-error-boundary); standalone adjacent-dataset carrier mismatch established; actual native error propagation unverified. |
| `opendp.extras._ibis.run_on_database` | correctness/sql-scalar-carrier | Audited | `a010591f55b1713c926f8e355091471634480307` | [SQL empty-sum result and error boundary](#sql-empty-sum-result-and-error-boundary): passes potentially `None` aggregate to integer noise input with no normalization. |
| `opendp.extras._ibis.run_on_database` | correctness/plugin-parameter-alignment | Partial | `a010591f55b1713c926f8e355091471634480307` | [Existing independent problems and replacements](#existing-independent-problems-and-replacements): positional zip already tracked by upstream #3148; not reaudited exhaustively. |
| `opendp.extras._ibis.run_on_database` | security/pickle-parameter-decoding | Partial | `a010591f55b1713c926f8e355091471634480307` | [Existing independent problems and replacements](#existing-independent-problems-and-replacements): current `pickle.loads` and pending typed decoder PR #3072 inspected only for impact on this path. |
| `opendp.extras._ibis.scan_database` | correctness/public-schema-only | Partial | `a010591f55b1713c926f8e355091471634480307` | [Schema binding](#schema-binding): delegates schema acquisition to translator, does not by itself fetch or certify private rows. |

## Analysis

### SQL empty-sum result and error boundary

The public query contains a bounded integer `dp.sum`. The translator's `handle_sum` calls `.sum()` directly. Its test fixture expects SQL `SELECT SUM(CASE ... END) AS ints FROM ...` with row-wise null replacement and clipping, but no outer `COALESCE(SUM(...),0)`. Standard SQLite SQL `SUM` returns `NULL` for an empty input relation. For one integer record `1`, it returns `1`.

The adapter gets the exact SQL result with `connection.to_polars(ibis_table).to_dict(as_series=False)`, extracts the first value of each column using `private_items = [v[0] for v in private_result.values()]`, and invokes `measurement(private_item)`. It constructs a `dp.atom_domain(T=int, nan=False)` and `dp.absolute_distance(T=int)` when the decoded plugin declares `Integer` support. There is no post-SQL null normalization before invoking the mechanism.

**Observed:** A standalone `sqlite3` test reproduces `None` for an empty dataset and `1` for a one-row neighbor, and mirrors the adapter's `private_items` extraction. A strict integer-input stub rejects the `None` case before any simulated noise and accepts the integer case. This validates the source-level null-carrier mismatch. The stub is not the real OpenDP `make_laplace` FFI, so the exact host-visible exception and complete privacy implication remain **Partial**.

**Threat:** If native OpenDP raises a visible carrier-conversion error for SQL `None` and successfully samples for integer `1`, the event "query failed" distinguishes an empty private table from a one-row neighbor before noise. This is a conditional privacy concern, **not a verified native differential-privacy exploit**.

**Evidence:** [Investigation](https://github.com/opendp/opendp-audit/blob/main/investigations/ibis-empty-sql-sum-pre-noise-null.md) and [standard-library SQLite model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_ibis_empty_sum_source_model.py).

### Existing independent problems and replacements

- [Open upstream issue #3148](https://github.com/opendp/opendp/issues/3148) separately identifies privacy-relevant **noise-scale swaps** due to positional alignment of SQL columns and plugin parameters. This review does not duplicate that defect.
- [Open upstream PR #3072](https://github.com/opendp/opendp/pull/3072) replaces Python unpickling of plugin parameters with native typed decoding, but not the empty `SUM` semantics.
- [Open upstream PR #3073](https://github.com/opendp/opendp/pull/3073) rewrites the scalar postprocessing executor with typed validation and retains a legacy fallback. The inspected diff does not add an empty SQL sum normalization; a pre-noise null rejection can still be observable.
- **Open upstream PR #3146** ([new Ibis Context integration](https://github.com/opendp/opendp/pull/3146)) removes `run_on_database` entirely and introduces a bound-table/OnceFrame collector. It eliminates the *precise legacy entrypoint* if merged, although the replacement's handling of empty SQL aggregates is **not audited**. This is a **pending removal**, not fixed on current `main`, nor a verified repair for every SQL release semantics issue.

Because a pending upstream PR removes the old entrypoint, this audit records the risk in source coverage and investigation rather than filing another candidate-defect issue. Reassess if that PR is abandoned or if its replacement exposes the same event.

### Schema binding

`scan_database` delegates to `polars_to_ibis.scan_database`, which obtains a public table schema. It does not inspect row count or values while scanning. Neither `scan_database` nor the adapter's construction checks enforce a positive minimum number of rows. The empty-vs-one-row witness therefore does not violate a stated public size precondition.

## Next checks

1. Run a native pinned OpenDP + Ibis + SQLite integration regression for `context.query().select(pl.col("ints").dp.sum(bounds=(0,10)))` on empty and one-row tables, checking both output events and privacy budget handling. Confirm Polars `connection.to_polars` null conversion and OpenDP's integer carrier rejection directly.
2. Compare native Polars `sum` of an empty input (zero) with SQL `SUM` (null), and either normalize to a public zero **before** noise or enforce an equivalent, provably safe postprocessing contract.
3. If PR #3146 merges, test the `OnceFrame` replacement on the same adjacent datasets, including typed carrier conversion, SQL Arrow nulls, and error propagation; do not treat entrypoint deletion alone as a proof of the replacement's safety.
4. Review SQL integer overflow, zero-row count, nullable SQL schemas and backend-dependent numeric output types separately.
