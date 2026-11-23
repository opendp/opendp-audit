"""Experimental fix for public duplicate replacement keys in pinned OpenDP.

Apply *only* to the ephemeral checkout made by the audit GitHub Actions job.
This does not modify opendp/opendp and is not an upstream fix/PR.
The guard mirrors pinned Polars's validate_old() check for materialized
public Series replacement patterns, including null and NaN semantics.
"""

from pathlib import Path
import sys

if len(sys.argv) != 2:
    raise SystemExit("usage: patch_polars_replace_duplicate_keys.py PATH_TO_EXPR_REPLACE_MOD_RS")

path = Path(sys.argv[1])
source = path.read_text(encoding="utf-8")

anchor = """    let mut output_domain = middle_domain.clone();"""
replacement = """    // Public replacement keys must be unique in the same sense as Polars's
    // runtime validate_old() check. Scalar keys have length one, while
    // dynamic list and AnyValue::List literals were materialized to Series.
    // This precondition is data independent and should be checked before
    // the stable transformation can be constructed.
    if let LiteralValue::Series(old_series) = &old_lit {
        if old_series.n_unique()? != old_series.len() {
            return fallible!(
                MakeTransformation,
                "replace: public old literal keys must be unique"
            );
        }
    }

    let mut output_domain = middle_domain.clone();"""

if source.count(anchor) != 1:
    raise SystemExit("expected exactly one pinned make_expr_replace output-domain anchor")
if "replace: public old literal keys must be unique" in source:
    raise SystemExit("patch appears already applied")

path.write_text(source.replace(anchor, replacement, 1), encoding="utf-8")
print("Applied ephemeral public old-key uniqueness guard to pinned OpenDP")
