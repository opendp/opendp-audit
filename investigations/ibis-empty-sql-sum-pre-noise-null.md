---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Legacy Ibis empty SQL SUM and pre-noise NULL propagation

## Invariant and threat model

A DP query's observable success/error behavior must not reveal whether the private dataset contains zero or one row before random noise is applied. This bounded review concerns the legacy `opendp.extras._ibis.run_on_database` executor with a *single supported bounded integer DP sum*, translated to SQL by the pinned `polars-to-ibis` main. Both an empty dataset and a one-row dataset are valid under an insert/delete adjacency relation when no positive minimum size is declared. The public schema, query, clipping bounds, privacy unit, and privacy budget remain unchanged.

An observer can inspect whether `run_on_database` returns a noisy numeric answer or raises a carrier-conversion exception. The warning/error channel is **conditional** on the native OpenDP integer noise measurement rejecting SQL `None`, as expected for an integer atomic carrier, and has not been exercised in a compiled OpenDP/Ibis environment.

## Affected symbols and source audits

- [Source report: `run_on_database`](https://github.com/opendp/opendp-audit/blob/main/source/python/src/opendp/extras/_ibis/__init__.py.md), [pinned OpenDP implementation](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/_ibis/__init__.py).
- [Translator: `handle_sum`](https://github.com/opendp/polars-to-ibis/blob/ce0296a0f7a4cc7546521db7a5fa9fad39d11331/src/polars_to_ibis/_parse/value_handlers.py), which directly returns `polars_expr_to_ibis_value(payload).sum()`.
- [Translator aggregation lowering](https://github.com/opendp/polars-to-ibis/blob/ce0296a0f7a4cc7546521db7a5fa9fad39d11331/src/polars_to_ibis/_parse/table_handlers.py), `apply_select_expr` accumulates aggregate columns and invokes `input_table.aggregate(**agg_kwargs)`.
- [Translator's expected SQL for bounded integer DP sums](https://github.com/opendp/polars-to-ibis/blob/ce0296a0f7a4cc7546521db7a5fa9fad39d11331/tests/config_split.py): `SELECT SUM(CASE ... END) AS ints`, with row-wise `COALESCE` for null inputs but **no outer `COALESCE(SUM(...),0)`**.
- [Standalone SQLite + carrier model](https://github.com/opendp/opendp-audit/blob/main/tools/tests/test_ibis_empty_sum_source_model.py), [audit task #162](https://github.com/opendp/opendp-audit/issues/162).

## Reasoning and evidence

### Private-data-dependent aggregate carrier

The translator emits a scalar SQL aggregate `SUM(CASE WHEN ... END)`. Under standard SQLite aggregate semantics, the result is one row containing `NULL` when no rows reach the aggregate, even when every row expression contains null-filling logic. Row-wise `COALESCE` does not affect a zero-row aggregate. For a single valid integer record with value 1, the aggregate returns the integer 1.

This distinction was **executed with Python's standard-library `sqlite3`** using a source-equivalent bounded-sum `CASE` expression. The reproduced outcomes were:

| Private table | SQL `SUM` value | Python scalar |
| --- | --- | --- |
| Empty | `NULL` | `None` |
| One row: `ints=1` | `1` | `int(1)` |

These two tables are one insertion/removal apart under the standard event-level unbounded adjacency relation. A public row-size cap or contribution cap of at least one does not exclude either table.

The legacy OpenDP Ibis adapter obtains the *exact* SQL result by calling `connection.to_polars(ibis_table).to_dict(as_series=False)`, takes the first value of each result column using `private_items = [v[0] for v in private_result.values()]`, and builds an integer noise mechanism when the plugin's public `support` flag is `Integer`. It invokes `measurement(private_item)` with no explicit SQL-null normalization. The integer noise input domain is `dp.atom_domain(T=int, nan=False)`, so `None` does not meet that carrier contract.

The standalone model mirrors the scalar extraction and checks how a **type-strict stub** would reject `None` while accepting the integer from the one-row relation. The stub deliberately does not claim to implement native OpenDP's FFI carrier conversion. Even if the native mechanism instead converts `None` in a different way, SQL/Python result types are data-dependent and require a safety proof before treating the release as DP.

### Privacy implications and limitations

If the actual OpenDP integer noise measurement raises a visible type error on the empty SQL `None` while succeeding on the one-row integer, then the presence of an error becomes a deterministic distinguisher with success probabilities 1 versus 0 on adjacent datasets, before DP randomization. This would violate any nontrivial DP guarantee for that observer-visible execution. The SQL is executed before the integer noise call, and the adapter does not catch/suppress the error.

**Execution boundaries:** The standard-library SQLite SQL and Python scalar extraction were exercised. The audit runtime does not have the `opendp`, `polars`, `ibis`, or `polars_to_ibis` packages; no native OpenDP converter, real `Context` query, Ibis backend, or noise measurement was executed. In particular, it remains to be verified that the installed Ibis/Polars bridge returns `None` and that native OpenDP rejects it. This is a source-level candidate, **not** a confirmed end-to-end privacy exploit.

### Deduplication and pending upstream work

- [Open upstream issue #3148](https://github.com/opendp/opendp/issues/3148) describes **noise-scale swaps when SQL projection order differs from plugin order**. Its observed mismatch is distinct from SQL-null handling and does not establish an empty-sum repair.
- [Open upstream PR #3072](https://github.com/opendp/opendp/pull/3072) replaces unsafe Python `pickle.loads` with typed deserialization; its goal is unrelated to a zero-row `SUM` becoming NULL.
- [Open upstream PR #3073](https://github.com/opendp/opendp/pull/3073) builds typed noise measurements before SQL and adds scalar validation; its patch continues to extract raw `private_items` in the legacy path and validates/carrier-converts before noise in the optional new path. It does **not** demonstrate zero-row SQL sum normalization and would still reject a null scalar rather than release a DP result.
- **Open upstream PR #3146** ([refactor: Polars-to-Ibis splitter and Context integration](https://github.com/opendp/opendp/pull/3146)) replaces the legacy `run_on_database` function entirely with a **bound Ibis source and `OnceFrame` collection flow**. This eliminates the precise old user-facing entrypoint if merged. The new collector's empty-sum/null semantics remain **not audited**, so this is a pending replacement rather than proof that all SQL-based private releases are safe.

Because the legacy entrypoint is specifically removed by an existing pending upstream PR, **no duplicate audit candidate issue was filed** under the repository's deduplication policy. This investigation documents the untested property and how to validate that a replacement implementation actually handles zero-row SQL aggregates safely.

## Findings

**Observed in SQLite:** The exact translated category of bounded SQL SUM emits `NULL` on the empty table versus an integer on a neighboring one-row table, and the legacy adapter's source forwards this scalar to a noise mechanism without a null fallback. The execution bridge and native failure distinguishability are not yet established.

**Disposition:** Partial, pending native reproduction; the old API is scheduled for removal by open PR #3146. No claim of a verified native DP violation or a complete upstream fix is made.

## Unresolved questions

1. Under a pinned `opendp[ibis]`/SQLite installation, construct an empty and one-row database with identical public schema and `Context` settings, run `context.query().select(pl.col("ints").dp.sum(bounds=(0,10)))` through `run_on_database`, and record exact response/error and privacy-budget effects.
2. Verify that the Ibis/Polars `connection.to_polars` output preserves `None` for the empty aggregate and that the OpenDP integer mechanism rejects it before sampling, rather than silently normalizing it.
3. If PR #3146 merges, test `OnceFrame` collection of the **same** empty/nonempty private datasets; verify both successful noise application and absence of input-dependent warnings/errors. Do not assume removal of `run_on_database` alone proves the replacement's DP behavior.
4. Audit other scalar aggregates and SQL dialects for the analogous zero-row convention (`COUNT(*)` is typically zero, unlike `SUM`), plus overflow and undefined SQL numeric expressions.
