# OpenDP autonomous audit protocol

This repository is a **persistent audit record and coordination space**, not a fork of OpenDP. When asked to audit without a specific target, **choose and complete a bounded, high-value audit autonomously**. Do not ask for a file list or a coordinator. Do not assume prior AI reasoning remains true; read the evidence.

## 1. Orient yourself

1. Read this file and `README.md`, then scan existing source reports, investigations, and **open and closed** audit issues.
2. Inspect the current [`opendp/opendp`](https://github.com/opendp/opendp) `main` at an exact commit SHA. Inspect relevant upstream issues and PRs, including merged and open PRs.
3. If a scope was supplied, use it. Otherwise, choose one **bounded unit** (a source file or a cross-file invariant) from insufficiently reviewed areas, prioritizing privacy/correctness, FFI safety, numerical behavior, and high-impact usability. Favor recent changes, data-dependent behavior, construction/execution boundaries, and dependency chains over trivial code. Do not repeat coverage merely to generate activity.
4. Define a concrete invariant and review scope before starting. An audit is **not** a general impression of the file.

## 2. Coordinate with other agents

The audit repository's GitHub Issues are the shared work queue. **Audit-task issues** (title prefix `[audit]`) reserve work; **candidate-defect issues** describe findings. They are different records.

1. Search open audit-task issues for your proposed paths, symbols, properties, and overlapping investigations. Check source-report coverage as well as issues. Prefer unclaimed work.
2. For substantive new work, create an **audit-task** issue using the issue form, or reuse an existing matching unclaimed task. Specify: upstream SHA, exact scope, property, unique run identity, claim start (UTC), and claim expiry (UTC, normally 24 hours later). This is a *lease*, not permanent ownership.
3. Check the issue **again after claiming** and before publishing. If another live claim overlaps, choose a nonoverlapping unit or coordinate through that issue. Expired claims may be taken over, retaining previous work and links. Never erase another agent's results.
4. Issue edits are not atomic locks. In a race, re-read the latest record, stop duplicate work, and reconcile rather than silently overwriting. If you cannot access or write GitHub issues, record the limitation and avoid claiming exclusive ownership.
5. Do not create an audit-task issue for a tiny clarification of an existing record. Do not create a new task when an existing task sufficiently covers the same work.

The user may delegate bug discovery in this **audit repository**. You may create and maintain audit-task and candidate-defect issues **here** when authorized for the audit run. Never create issues or PRs in upstream OpenDP as part of an audit. Do not open or undraft PRs, reply to review comments, or change PR descriptions in either repository unless specifically and separately authorized. Do not rewrite other agents' branches.

## 3. Conduct the audit

- Inspect relevant constructors, callers, callees, trait implementations, and assumptions. Trace the property across files when necessary.
- Separate soundness/privacy failures from utility, performance, numerical, and usability failures. State severity and uncertainty, not just suspicious code.
- Seek minimal counterexamples, tests, and proof obligations. Record what you actually executed versus what you only reasoned about.
- Check whether the suspected defect exists on **current `main`**, and whether an existing upstream PR already fixes it. A fix in an open PR is **pending**, not fixed on `main`.
- If the property spans files, write an `investigations/` record and cross-link relevant source audits; do not duplicate the full argument in each file.

## 4. Record coverage precisely

Source reports mirror OpenDP's upstream path under `source/`, with `.md` appended; create them **only after meaningful review**. Start from `templates/source-audit.md`. Investigations use `templates/investigation.md`.

- Each coverage key is `(upstream path, qualified symbol, property slug)`. Use a stable, precise property identifier such as `privacy/stability`, `memory/ownership`, or `correctness/domain-membership`. Keep property identifiers consistent across reports.
- Each coverage row records its **own full 40-character upstream commit SHA** because different symbols can be reviewed at different revisions. The report's `updated` date is *not* a source revision. Link to commit-pinned source and supporting analysis.
- Status is one of `Not reviewed`, `Partial`, `Audited`, `Inconclusive`, `Stale`. `Audited` means only the **declared property and assumptions** were examined; it never means proven correct. Prefer `Partial` if plausible branches or prerequisites remain unchecked.
- Include negative results and open questions. A coverage row can reference a concise analysis section; do not create verbose empty sections for trivial symbols.
- Treat a code change as a **freshness signal**, not automatic invalidation. Mark only property/symbol records whose code, dependency, or assumption changed materially as `Stale`, with an explanation. Record the newer commit when re-reviewed.
- Do not maintain a hand-edited global coverage index. Reports are the source of truth; Git history preserves earlier versions.

## 5. Track a suspected defect

Before filing, search both **open and closed** audit issues, upstream OpenDP issues, and upstream PRs (open and merged). Check the current code, not only titles. Reuse an equivalent issue rather than creating a duplicate.

Use the candidate-defect issue form. Keep these dimensions separate:

- **Verification:** `Candidate`, `Reproduced`, or `Confirmed`.
- **Upstream disposition:** `Unreported`, `Existing issue`, `Pending PR`, `Fixed on main`, `Invalid`, or `Duplicate`.

Describe the invariant, affected SHA and symbols, evidence or missing proof, impact, known issues/PRs, and next decisive check. A candidate is not a confirmed bug; an open fix PR is not a merged fix. Do not file a newly discovered defect already fixed on `main`. If a previously tracked defect is fixed, update the existing audit issue with evidence and close it with a clear disposition. Follow [OpenDP's security policy](https://github.com/opendp/opendp/security/policy) for exploitable security or privacy findings, rather than publishing attack details to inappropriate channels.

## 6. Publish and release your claim

1. Update the relevant source report(s) and/or investigation(s). Amend the *current assessment*, not a chronological transcript; Git already stores history.
2. Run `python tools/validate.py` and `python -m unittest discover -s tools/tests`. Do not invent a successful test result.
3. Use a distinct work branch named `audit-<scope>-<run-id>` (**no `/` in branch names**). Before integration, fetch current audit `main`, reconcile changes, and revalidate. Publish only on authorized branches; fast-forward to audit `main` when allowed, **without opening a PR by default**. Never force-push another agent's work. If publication is blocked, leave a descriptive branch/commit and report the limitation.
4. Re-check for an overlapping new finding or a newly merged upstream fix immediately before publishing issue changes.
5. Update and close the audit-task issue with the covered properties, reviewed revision, files, findings, and remaining work. Release the lease even when the audit was inconclusive; file a follow-up task if necessary.
6. Finish with a short factual summary and links. If no bugs were found, say so **within the reviewed scope**, not as a blanket correctness claim.

**No unattended infinite loops.** When given no further scope, finish one bounded audit unit and then report. Subsequent sessions can choose the next unit using the shared records.

## Boundaries

Do not modify `opendp/opendp` from this workflow. Do not fabricate evidence, tests, source revisions, or audit conclusions. If a required connector permission or tool is unavailable, record the limitation; don't pretend a claim or published record exists.
