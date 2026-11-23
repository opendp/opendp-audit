---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Privacy-free Polars expression leaves: public partition lengths and literal values

## Precise scope and invariant

The non-deprecated `make_private_expr` dispatch includes two zero-cost leaf constructors: `make_expr_private_len` for exact `Expr::Len` when **`Invariant::Lengths`** is provided, and `make_expr_private_lit` for public `Expr::Literal` values. A zero-privacy map is valid only when the observable being certified is identical on all neighboring inputs in the declared multiverse. In particular, the privacy of a leaf expression must not be conflated with the privacy of a complete grouped output that may also expose group keys.

- [Exact-length source report](../source/rust/src/measurements/make_private_expr/expr_len/mod.rs.md) and [pinned upstream Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_len/mod.rs).
- [Public-literal source report](../source/rust/src/measurements/make_private_expr/expr_literal/mod.rs.md) and [pinned upstream Rust](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_literal/mod.rs).
- [PrivateExpr leaf dispatch](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/mod.rs); [`Invariant` and `Margin` definitions](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/domains/polars/frame/mod.rs).
- Existing upstream native tests: [exact length](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_len/test.rs), [literal](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/make_private_expr/expr_literal/test.rs); inspected but not executed.
- [Independent reproducible Python model](../tools/tests/test_polars_privacy_free_expr_model.py), run locally with five passing unit tests.

## Proof: exact lengths under public group-length invariant

For a table `X` and grouping key `g`, define `n_X(g)=|{r in X: key(r)=g}|`. The multiverse assertion `Invariant::Lengths` means neighboring datasets `X,Y` share the same set of grouping keys and satisfy `n_X(g)=n_Y(g)` for each key. Consequently, the vector/map of grouped lengths is identical: `len(X)=len(Y)` groupwise. As a deterministic release this costs zero privacy loss.

The constructor checks `Expr::Len`, requires `Context::Aggregation`, and permits the zero map **only** under `Some(Invariant::Lengths)`. In particular `Some(Invariant::Keys)` is rejected, because fixed key presence does not fix the number of records in a group. For example, `[(a,1),(b,1)]` versus `[(a,1),(a,2),(b,1)]` has the same key set, but the exact length of group `a` changes from one to two. Public lengths are an explicit assumption about the neighboring domain family, not something inferred from checking one input dataset in isolation.

This is a private measurement constructor; it does **not** produce an `ExprDomain` of the sort constructed by the stable `make_expr_len` transformation. It is distinct from the incorrect grouped output `max_groups=1` reported in [audit defect #78](https://github.com/opendp/opendp-audit/issues/78).

## Proof: public literal expression and its limit

The literal constructor rejects nonliteral expression ASTs and wraps `Expr::Literal` into an `ExprPlan` with a zero privacy map. For fixed public literal value `c`, the value of the literal is `c` on any input. This is a valid zero-cost leaf claim.

**It is not a zero-cost grouped-frame claim.** The grouped query `group_by(private_key).agg(lit(c))` returns public constant values but may also reveal whether private groups exist. For instance a one-row table whose private key equals `a` yields a group keyed `a`, and substituting `b` changes that key. The higher-level mechanism must protect any keys and shape disclosed by the grouped result. The leaf's privacy map does not account for those separately.

Both functions return executable `ExprPlan` values under OpenDP's honest-but-curious/single-evaluation model. Neither the source trace nor the independent model establishes privacy for arbitrary plan introspection, serialization, reuse, or unvalidated downstream composition.

## Independent finite verification

Ran `python -m unittest -v /mnt/data/test_polars_privacy_free_expr_model.py` locally: **five tests passed**. The model uses two group keys (`a`, `b`) and three possible row values, giving six record types. All sequences of length zero through three form **259** datasets. It inspects all **67,081 ordered dataset pairs**:

- **15,085** pairs with equal per-group length signatures produce identical exact grouped lengths.
- **51,996** pairs do not share the public-length signature and are not eligible for the zero-cost length proof.
- Literal values `0, 17, -5, "public"` are constant across all datasets, but a separate test witnesses that grouped literal *output keys* can differ.
- Exact length is rejected in the model for `Keys` or no invariant; the empty/ungrouped count and grouped empty-output shapes are distinguished.

The model is a mathematical comparator, **not** a native Rust, Polars, FFI, or differential-privacy runtime test. It does not validate every Polars grouping, null handling, optimizer rewrite, or callback/tool interface.

## Disposition and remaining obligations

No counterexample to either narrowly scoped zero-cost leaf claim. Existing audit defect [#78](https://github.com/opendp/opendp-audit/issues/78) concerns the stable (not private) length expression and is **not** duplicated. Audit task [#47](https://github.com/opendp/opendp-audit/issues/47) covers signed `dp_frame_len`/count shims and is outside this study. No new defect issue was filed.

The privacy status is **Partial** for end-to-end composition: run native Rust/Polars tests with public length invariants and with grouped public literals, and verify higher-level `make_private_lazyframe` accounts for any newly revealed group presence when keys are not public. No upstream OpenDP code was modified.
