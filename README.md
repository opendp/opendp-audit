# OpenDP audits

A persistent, independent record of AI-assisted reviews of [OpenDP](https://github.com/opendp/opendp). This repository tracks **what has been examined**, **what remains uncertain**, and **potential defects**. It does not replace the upstream issue tracker or OpenDP's security disclosure process.

## Layout

```text
source/                 # One Markdown audit per reviewed upstream source file
  rust/                 # Mirrors rust/... in opendp/opendp
  python/               # Mirrors python/... in opendp/opendp
  R/                    # Mirrors R/... in opendp/opendp
investigations/         # Cross-file or cross-language invariants
templates/              # Starting points for new records
.github/ISSUE_TEMPLATE/ # Candidate bug intake
AGENTS.md               # Required audit protocol
```

A source audit uses the *exact upstream-relative path*, with `.md` appended:

- `rust/src/foo.rs` → `source/rust/src/foo.rs.md`
- `python/src/opendp/foo.py` → `source/python/src/opendp/foo.py.md`
- `R/opendp/R/foo.R` → `source/R/opendp/R/foo.R.md`

These are path examples, not claims that those files exist. Create audit files **when actually reviewing code**, not as empty placeholders for the entire codebase. The tracked `.gitkeep` files only preserve the initial directory layout.

## Records

- **Source audits:** Coverage per function, method, or trait implementation, including reviewed commit, invariant/scope, limitations, and issue links. Small cohesive implementations may share a section; separate methods when their reasoning differs.
- **Investigations:** Properties spanning several symbols or files, such as permutation invariance or FFI ownership. Link affected source audits rather than duplicating analysis.
- **GitHub issues:** One issue per distinct suspected defect, including preliminary candidates. Link source audits and investigations. A finding may remain unverified; say so explicitly.

Use `templates/source-audit.md` and `templates/investigation.md` for new reports. Read `AGENTS.md` before starting or continuing an audit.

## Status and freshness

For every audited symbol **and scope**, use `Not reviewed`, `Partial`, `Audited`, `Inconclusive`, or `Stale`. `Audited` means examined for the *stated properties*, not proven correct. Record the exact OpenDP commit reviewed. A change to the symbol, relevant dependency, or assumption may invalidate the prior assessment; do not mark all symbols in a file stale solely because unrelated lines changed.

Record negative results, limitations, and open questions as well as bugs. Avoid inferring coverage from the presence of a file alone.

## Escalation

Search this repository's open **and closed** issues and upstream OpenDP issues/PRs before treating a finding as new. Distinguish fixes merged to `main` from fixes only present in an open PR or branch. Keep speculative work in this audit repository; do not automatically open upstream issues or PRs. Follow OpenDP's security reporting policy for sensitive vulnerabilities.
