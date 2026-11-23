---
schema_version: 1
source: rust/src/transformations/scalar_to_vector/mod.rs
updated: 2026-11-22
---

# `rust/src/transformations/scalar_to_vector/mod.rs`

## Scope and assumptions

- **Scope:** The non-deprecated `make_vec<T, const P: usize, Q>` singleton wrapper and its 1-stability claim under `AbsoluteDistance<Q>` → `LpDistance<P,Q>`. Review `then_index_or_default` only for totality and scalar-noise caller usage. This is not an end-to-end noise-mechanism privacy audit.
- **Invariant:** For every supported norm exponent `P`, a singleton `[x]` must have Lp distance equal to scalar absolute distance `|x-x'|`, so the identity stability map is valid. The output has length one and meets `VectorDomain` membership. No constructor may successfully certify a metric without defined mathematical semantics.
- **Assumptions:** Atomic data support subtraction in the mathematical distance; `Q` represents a meaningful, ordered distance. The finite numerical model covers real-valued `T=Q=f64` semantics and positive integer `P`. It does not establish numerical trait validity for arbitrary `CheckAtom` and `Q` implementations.
- **Pinned upstream:** [Rust transformation](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/mod.rs), [proof](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/transformations/scalar_to_vector/make_vec.tex), [Lp metric definition and check](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/metrics/mod.rs), [scalar noise caller](https://github.com/opendp/opendp/blob/ef1a238634d6196b01a1a1e77d3d5ad2340e3094/rust/src/measurements/noise/nature/float/mod.rs).

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `make_vec<T,P,Q>` | privacy/stability-positive-p | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Positive exponents](#positive-exponents) |
| `make_vec<T,P,Q>` | correctness/lp-exponent-precondition | Partial | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Zero exponent](#zero-exponent) |
| `then_index_or_default` | correctness/index-totality | Audited | `ef1a238634d6196b01a1a1e77d3d5ad2340e3094` | [Index postprocessor](#index-postprocessor) |

## Analysis

### Positive exponents

`make_vec` wraps any valid atom `x` in a one-element vector and declares the output domain as `.with_size(1)`. Its map is `StabilityMap::new(Clone::clone)`, so it returns the original distance bound unchanged. For real atomic values, any positive real `p` satisfies `||[x]-[x']||_p = (|x-x'|^p)^(1/p) = |x-x'|`; equality of input and output distances establishes 1-stability for `P >= 1`. The output element also inherits the input element domain. The proof document uses this singleton identity, conditional on a nonzero exponent.

**Executed:** [An independent finite Python mathematical model](../../../../../tools/tests/test_scalar_to_vector_lp_model.py) enumerated 25 ordered pairs of rational scalar values at each exponent `P=1,2,3,4,8` (125 checks total), comparing the singleton norm to absolute distance. All checks passed. This validates the ordinary positive-exponent identity, **not** the compiled Rust generic instantiation or all numerical types.

### Zero exponent

The public Rust signature accepts any `const P: usize`, including zero. `LpDistance<0,Q>` implements `Metric`, and the vector `MetricSpace` implementation tests only whether the element domain permits NaN; it does not validate the exponent. Thus an instantiation such as `make_vec::<f64, 0, f64>((AtomDomain::new_non_nan(), AbsoluteDistance::default()))` is not rejected by the visible constructors or trait bounds. The Rust function still advertises the identity map. The documented Lp formula and `make_vec.tex` proof use an exponent `1/P`, which is undefined when `P=0`.

If an `LpDistance<0,Q>` is interpreted as conventional *L0* (number of nonzero coordinate differences), the map is not conservative: for `x=0`, `x'=1/2`, input distance is `1/2`, output L0 distance is `1`, and the advertised map returns `1/2`. OpenDP does **not** explicitly define `LpDistance<0,Q>` as L0 in the reviewed source, so this is a **conditional counterexample**, not an established mechanism-level privacy violation. The confirmed narrower defect is admission of a metric whose documented mathematical formula and proof have no valid `P=0` interpretation. See [cross-file investigation](../../../../../investigations/scalar-to-vector-zero-lp-exponent.md) and [audit candidate #37](https://github.com/opendp/opendp-audit/issues/37).

This requires a native constructor regression and a declared supported-exponent contract. It is not known to affect default scalar noise constructors, whose production branches may select only supported exponent values. **Status `Partial`** reflects those unresolved downstream questions.

### Index postprocessor

`then_index_or_default(i)` constructs `Function::new(move |vec: &Vec<T>| vec.get(i).cloned().unwrap_or_default())`. For an in-range index it clones the element; otherwise it returns `T::default()`. It never performs unchecked indexing and so is total under its `Clone + Default` constraints. Its effect is deterministic postprocessing when chained after a measurement, without adding privacy cost. A small Python model checked the integer `i=0` outcomes on empty, singleton, and length-two inputs; the result matches the implementation's branch structure. This is scoped correctness coverage; it does not assert that every user expects a silent default for missing data.

## Next checks

- Explicitly restrict the supported `LpDistance` exponents in the relevant `MetricSpace` implementations or specify a mathematically valid `P=0` interpretation and revise the `make_vec` proof and stability map accordingly.
- Compile `make_vec::<f64, 0, f64>` against pinned OpenDP, check constructor success, and test downstream mechanism instantiation and map behavior.
- Verify the generic `Q` and atom-distance assumptions in the proof for non-float types separately; this bounded report does not certify all such combinations.
- **Upstream disposition:** No matching upstream corrective issue or PR identified; [audit candidate #37](https://github.com/opendp/opendp-audit/issues/37) tracks the issue. No end-to-end privacy violation demonstrated.
