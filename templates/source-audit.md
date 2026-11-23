---
schema_version: 1
source: rust/src/path/to/file.rs
updated: YYYY-MM-DD
---

# `rust/src/path/to/file.rs`

## Scope and assumptions

- **Audit scope:** Which properties and behavior were examined?
- **Invariants:** What specifically must hold?
- **Assumptions:** Public parameters, domains, supported backends, relevant dependencies.
- **Source links:** Use commit-pinned GitHub URLs, not moving line references.

## Symbol coverage

| Symbol | Property | Status | Reviewed commit | Evidence / findings |
| --- | --- | --- | --- | --- |
| `qualified::symbol` | privacy/stability | Partial | `aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa` | [Analysis](#analysis) |

Use one row per qualified symbol **and scoped property**. The commit above is an illustrative placeholder; replace it with the actual full upstream SHA. Valid statuses: Not reviewed, Partial, Audited, Inconclusive, Stale. For Not reviewed, use `-` for the commit. Property identifiers are stable lowercase slugs with at least one slash (e.g. `privacy/stability`, `memory/ownership`). Escape literal pipes in table cells as `\|`.

## Analysis

### `qualified::symbol` — `privacy/stability`

**Conclusion:** Scoped assessment, not a blanket proof.

**Evidence:** Concrete reasoning and/or test results, including what was *actually run*.

**Limitations:** Unexamined paths, cross-file dependencies, assumptions, and why status is appropriate.

**Related:** Candidate issues and investigations, if any.

## Next checks

Specific remaining work, or none identified within scope.
