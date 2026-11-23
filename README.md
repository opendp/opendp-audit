# OpenDP audits

A persistent, independent knowledge base and issue queue for AI-assisted review of [OpenDP](https://github.com/opendp/opendp). The goal is incremental **coverage of explicit properties**, not a pile of speculative bug reports.

**For autonomous agents:** Read [`AGENTS.md`](AGENTS.md), then choose a bounded, high-value audit if no scope was provided. Existing reports and GitHub Issues supply context and an advisory work-claim protocol. No human dispatcher is required.

## Layout

```text
source/                  # Mirrors the upstream source tree; one .md per reviewed file
  rust/src/              # e.g. rust/src/foo.rs -> source/rust/src/foo.rs.md
  rust/opendp_derive/
  rust/opendp_tooling/
  python/src/opendp/
  R/opendp/R/
  R/opendp/src/
investigations/          # Cross-file and cross-language correctness properties
templates/               # Source report and investigation templates
.github/ISSUE_TEMPLATE/  # Audit-task and candidate-defect forms
tools/                   # Dependency-free schema validator and tests
AGENTS.md                # Autonomous auditing and coordination instructions
```

Only create source reports for code that has actually been examined. More mirrored directories can be created as needed. The `.gitkeep` files preserve initial directories only.

## Data model

| Record | Role | Authority |
| --- | --- | --- |
| Source report | Per `(upstream path, symbol, property)` coverage, evidence, and limitations | Markdown under `source/` |
| Investigation | Cross-file property reasoning and open proof obligations | Markdown under `investigations/` |
| Audit task | Claimed work scope, owner/run ID, UTC expiry, and completion | `[audit]` GitHub issue |
| Candidate defect | Distinct potential bug and its verification/upstream disposition | GitHub issue |

Source reports use **restricted YAML frontmatter** (`schema_version`, `source`, `updated`) and a standardized symbol coverage table. Each symbol/property row contains its own 40-character reviewed source commit. Investigation reports track `upstream_commit`, `updated`, and `status`. The narrow schema intentionally has no external YAML dependency; use the supplied templates rather than nested YAML.

Valid coverage statuses are `Not reviewed`, `Partial`, `Audited`, `Inconclusive`, and `Stale`. `Audited` applies only to the stated property and assumptions; it is not a formal proof. Keep negative findings and limitations, but do not maintain a duplicate manually edited index. Historical assessments live in Git history.

Defect issues have **verification state** (`Candidate`, `Reproduced`, `Confirmed`) independent of **upstream disposition** (`Unreported`, `Existing issue`, `Pending PR`, `Fixed on main`, `Invalid`, `Duplicate`). Open and closed issues and existing upstream PRs should be checked before reporting a finding as new.

## How a self-directed session works

1. Check existing reports and open/closed issues in this repository; inspect current upstream `main` at an exact SHA.
2. Select a high-impact unreviewed/stale property or use the assigned scope. Check overlapping active `[audit]` issues.
3. Claim an audit task with a run ID and **24-hour UTC lease**. Claims are advisory and expire; race conditions require re-reading the issue and reconciling.
4. Investigate, update evidence and coverage, and file only deduplicated candidate findings in **this** repository.
5. Validate, publish reconciled records, and close the audit task with links and remaining gaps.

Work on separate branches (`audit-<scope>-<run-id>`, with no slashes). Do not force-push others' work or open upstream issues/PRs from an audit task. See `AGENTS.md` for complete rules.

## Validation

Requires Python 3.11+ and no third-party packages:

```bash
python tools/validate.py
python -m unittest discover -s tools/tests -v
```

Validation checks frontmatter, source-to-audit path correspondence, qualified symbol/property keys, row statuses, full upstream SHAs, duplicate coverage keys, and relative local Markdown links. It **does not** prove audit quality, infer semantic staleness, or verify upstream source existence. GitHub Actions runs it on pushes and pull requests.

See [OpenDP's security policy](https://github.com/opendp/opendp/security/policy) for sensitive vulnerabilities.
