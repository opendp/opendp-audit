---
schema_version: 1
upstream_commit: ef1a238634d6196b01a1a1e77d3d5ad2340e3094
updated: 2026-11-23
status: Partial
---

# Finite floating-point decision boundaries omitted by automatic binary-search probes

## Invariant and threat model

For the non-deprecated Rust, Python, and R binary-search utilities, missing bounds are inferred by probing away from a known point. For an everywhere-defined monotone predicate with a decision boundary at a finite representable floating-point value, the search must not report that no boundary exists solely because its finite probes do not cover the available floating range.

The failure is **availability/correctness** in parameter calibration, not a demonstrated differential-privacy violation. A rejected automatic calibration does not by itself emit private data.

## Affected symbols and source audits

- [Rust search source audit](../source/rust/src/utilities/search/mod.rs.md) and [pinned `Bands::bands`, `fallible_exponential_bounds_search`, `resolve_bounds`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/utilities/search/mod.rs).
- [FFI `opendp_internal___binary_search`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/internal/mod.rs) dispatches both `f32` and `f64`.
- [Python `binary_search`, `binary_search_param`, `binary_search_chain`](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/python/src/opendp/mod.py) use the Rust search when bounds are missing; automated calibration may require large finite scale parameters.
- [Rust unit tests inspected](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/utilities/search/test.rs): present positive/negative thresholds near zero, explicit full integer ranges, and a float midpoint extreme test, but not large *inferred* float boundaries.

## Reasoning and evidence

The `impl_bands_float!` macro makes probes at `center ± 0.5`, followed by `center ± 2^(k^2)` for `k = 0..size_of::<Self>()-1`. Both f32 and f64 are finite IEEE floats, but their *byte widths* bound the number of probes to four and eight. From zero:

| Float | Last positive probe | Witness predicate | True value available in type |
| --- | --- | --- | --- |
| `f32` | `2^9 = 512` | `x >= 1024` | `1024` |
| `f64` | `2^49` | `x >= 2^50` | `2^50` |

Every generated probe is below the positive threshold (or negative), so neither direction sees a Boolean change. `fallible_exponential_bounds_search` returns `Ok(None)`, and `resolve_bounds` produces a `Search` error. With `Above(0)`, `fallible_signed_band_search` independently returns `None`, producing the one-sided inference error. By contrast, providing explicit brackets `(0, 2048)` or `(0, 2^51)` yields opposite endpoint results.

The five tests in [the pinned-source probe model](../tools/tests/test_float_search_band_horizon_model.py) were executed locally through `python -m unittest discover` and passed. They check both float widths, both directions, one-sided search, exactly-last-probe boundary, and successful explicit brackets. The model independently recomputes the exact candidate list but **does not import or execute OpenDP**; native regression remains to be run.

Duplicate check: searched open/closed audit issues and upstream OpenDP issues/PRs using `binary_search`, `bands_float`, `band search`, `exponential_bounds_search`, and related terms. Old closed [OpenDP issue #443](https://github.com/opendp/opendp/issues/443) is a different 2022 exception in Python at an extreme scale; no current matching upstream issue/PR found.

## Findings

Confirmed source-level availability/correctness counterexample, filed as [audit issue #102](https://github.com/opendp/opendp-audit/issues/102). The fix should replace the byte-width-limited probe horizon with a finite-range-covering strategy, guarding against overflow and non-progress; tests should cover the f32/f64 examples via native Rust and language bindings.

## Unresolved questions

- Does the proposed expanded float search handle predicates that reject extreme finite candidates, instead of merely changing the error mode?
- Can a nonzero starting point or a one-sided upper bound leave a large interval undiscovered even if the closest finite extremum is reachable?
- Review parameterized privacy-map monotonicity and callback exceptions separately; this audit does not certify all binary-search output postconditions.
