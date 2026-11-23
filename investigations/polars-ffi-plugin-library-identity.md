---
schema_version: 1
upstream_commit: a010591f55b1713c926f8e355091471634480307
updated: 2026-11-23
status: Partial
---

# Polars FFI plugin identity: privacy accounting versus executable library

## Invariant and scope

A Polars DP expression must execute a plugin implementation whose noise distribution and semantics agree with the attached `Measurement.privacy_map`. The **trusted-library identity** used to recognize an OpenDP placeholder must not disagree with the **executable-library path** retained in the rewritten private plan.

This investigation covers:

- [`match_plugin`, `match_trusted_plugin` and `apply_plugin`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/polars/mod.rs), which recognize FFI shims and rewrite them to executable plugins.
- [`make_expr_noise`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/measurements/make_private_expr/expr_noise/mod.rs), which accepts a matched `noise` shim, creates a noise privacy map and asks `apply_plugin` to rewrite its AST.
- [`sanitize_serialized_dslplan` / `rebind_plugin`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/rust/src/polars/preflight/mod.rs), which rebind accepted serialized placeholders before Polars deserialization in **untrusted** plans and selectively rebinds library filenames in **trusted** plans.
- [`LazyFrameQuery.deserialize`](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/src/opendp/extras/polars/__init__.py), which defaults to `trusted=False`.
- [Native/Python preflight regression source](https://github.com/opendp/opendp/blob/a010591f55b1713c926f8e355091471634480307/python/test/test_serialization_polars.py), especially trusted-preflight preservation of third-party plugin paths.

The concern is with **locally authored** or explicitly trusted native-plugin plans. It is **not** a demonstration that remotely submitted serialized plans can bypass OpenDP's default untrusted-plan preflight.

## Code-level mismatch

Under FFI, `match_plugin::<KW>` recognizes a plugin expression when `lib.contains("opendp")`, `symbol == KW::NAME` and the `kwargs` byte string is short. The check neither identifies the canonical OpenDP library nor distinguishes an unrelated shared library whose path or filename happens to contain the string. `match_trusted_plugin` applies the same test before parsing trusted plugin kwargs.

After that match, `make_expr_noise` constructs a measurement based on `NoiseExprMeasure` and `map_function` for OpenDP's underlying Laplace/Gaussian mechanisms. Its release function calls `apply_plugin(vec![input_expr], expr, NoisePlugin { ... })`.

For an FFI plugin, `apply_plugin` discards/replaces the original **input expressions**, plugin flags and symbol name, but captures and **reuses the original `lib`**:

```rust
FunctionExpr::FfiPlugin { lib, .. } => Expr::Function {
    input: input_exprs,
    function: FunctionExpr::FfiPlugin {
        flags: KW::function_options(),
        lib,
        symbol: KW::NAME.into(),
        kwargs: /* serialized trusted plugin arguments */,
    },
},
```

Thus an unrelated native plugin library originally referenced by an expression named `noise` may still be referenced by its rewritten executable expression named `noise_plugin`, while the privacy map was derived under the assumption that OpenDP's `NoisePlugin` implementation will execute. A name collision is sufficient for this **source-level association mismatch**; realizing an actual privacy violation would additionally require a compatible alternate native plugin implementation and successful Polars execution.

## Preflight boundary: important limiting evidence

`preflight::sanitize_serialized_dslplan(raw, trusted_lib, false)` checks an allowlisted syntax and symbol vocabulary, forbids untrusted pickled kwargs and unsupported executable plugins, and **rebinds every allowed FFI shim to `trusted_lib`** before Polars deserializes the plan. `LazyFrameQuery.deserialize(serialized_plan, trusted=False)` calls this sanitization with the locally loaded canonical OpenDP library. In this path, remote library-name spoofing cannot survive to the matcher. This safeguard is already present on the reviewed `main`.

For `trusted=true`, the source intentionally permits third-party native plugin paths and rebinds only if a plugin basename starts with `libopendp.` or `opendp.` **and** the symbol is in the recognized DP shim vocabulary. Its existing Python regression specifically expects libraries named `libother.so` and `libopendp_other.so` to remain unchanged under trusted preflight. The latter still matches the **much looser** substring `lib.contains("opendp")` in `match_plugin`.

A locally authored `pl.Expr` passed directly to the ordinary `make_private_lazyframe` API is not necessarily passed through `LazyFrameQuery.deserialize` at all; the original FFI plugin library field is therefore relevant at the constructor boundary.

## Minimal source-equivalent trace

Use these public path strings only as a *model of the predicates*, not an executed proof of a malicious shared library:

| Condition | Canonical OpenDP path | Noncanonical colliding path |
| --- | --- | --- |
| `match_plugin(lib, symbol="noise")` | Accepted | **Accepted** |
| `trusted=true` preflight rebinds | Yes | **No** |
| `trusted=false` preflight rebinds | Yes | **Yes** |
| `apply_plugin` rewrites to `noise_plugin` | Preserves trusted path | **Preserves different original path** |

For the noncanonical case, take a third-party basename containing `opendp` without the canonical filename prefix. The path passes the FFI shim recognition test, is retained by trusted preflight, and still occurs in the rewritten executable plugin expression. The original input `noise` shim is never required to execute before the rewrite, provided the Polars builder accepts the planned FFI plugin expression; this last condition is **not natively tested**.

The accompanying [Python standard-library source-equivalent regression](../tools/tests/test_polars_ffi_plugin_identity_model.py) checks five scenarios: noncanonical library acceptance, exact library retention, trusted/untrusted preflight differences, canonical rebinding, and substring matches in directory names. No OpenDP or Polars runtime was available, so this does not show successful dynamic loading or a private release.

## Threat model, impact and disclosure

**Conditional impact:** A system whose users can author or submit *explicitly trusted* Polars plans referencing third-party shared libraries can construct a query accepted as OpenDP private noise while the generated AST references a different implementation. If that implementation does not supply the noise charged by `privacy_map`, then the claimed DP guarantee is invalid. More generally, a DP API should bind the semantics it certifies to a uniquely trusted executable, not an arbitrary path string.

**Limitations:**
- The default `trusted=False` serialized-plan pathway is not vulnerable to this specific library-path retention because preflight replaces the path before interpretation.
- Allowing an untrusted user to supply and execute arbitrary native code is **already** a privileged operation. This finding does not assert that OpenDP alone creates arbitrary-code execution capability, nor that the matcher crosses an isolation boundary that otherwise forbids native code.
- A crafted native library exporting the expected executable symbol was **not built or run**. No empirical privacy loss or production exploit is claimed.
- If the threat model excludes all untrusted local/third-party native plugins and trusted serialized plans, the issue is a **defense-in-depth trust predicate inconsistency**, not a demonstrated privacy bug in normal use.

**Verification:** Source-level mismatch reproduced by tracing pinned code and the standalone model. **Defect issue:** [#159](https://github.com/opendp/opendp-audit/issues/159), tracked as `Candidate`/`Unreported`. **Coordination task:** [#157](https://github.com/opendp/opendp-audit/issues/157). This is distinct from the existing upstream preflight security mitigations, which correctly handle the default remote/untrusted serialized-plan path.

## Recommended remediation and decisive tests

Unify the trust predicate for `match_plugin`, `match_trusted_plugin`, preflight and `apply_plugin`. Bind rewritten OpenDP executable plugins to a verified canonical shared library identity/path (or reject a noncanonical path before assigning an OpenDP privacy map), while preserving third-party plugin support in contexts that do **not** claim OpenDP privacy. Avoid name-only library checks.

Compile a targeted native regression creating an FFI shim whose library basename contains `opendp` but is not the canonical OpenDP binary; verify the DP constructor rejects its identity or rewrites to the canonical OpenDP library, and verify that trusted third-party plugins not claiming OpenDP DP remain permitted. Re-run the existing untrusted serialized-plan preflight tests to ensure this strong boundary remains intact.
