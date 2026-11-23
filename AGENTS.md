# Audit agent protocol

This repository is an **audit knowledge base**, not a mirror of OpenDP's code and not a license to modify upstream.

## Start of an audit

1. Identify the specific OpenDP repository/ref and record its full commit SHA.
2. Read the relevant existing source audits, investigations, and candidate issues before analyzing code. Do not repeat resolved work without a reason.
3. State the exact properties under review (for example: privacy accounting, domain membership, numerical behavior, resource safety, API correctness). An unspecified "reviewed" assertion is not sufficient.
4. Inspect relevant callers, callees, constructors, traits, and assumptions. A function-by-function read is not enough for cross-cutting guarantees.

## Recording coverage

- Mirror upstream paths under `source/` and append `.md`. Create a file only once meaningful examination has happened.
- Maintain a coverage row for each relevant symbol and assessed scope; record the reviewed commit. Use symbol names as they appear in upstream code; include enough qualification to disambiguate methods and trait impls.
- Valid coverage statuses: `Not reviewed`, `Partial`, `Audited`, `Inconclusive`, `Stale`. Explain limitations and unexamined branches. Never claim a proof from inspection or passing tests alone.
- Place concise conclusions and evidence in the source audit. Use a detailed section only if substantive analysis merits it.
- Use `investigations/` for properties spanning files or languages; cross-link both ways where useful.
- Update records even when no bug is found. Negative results and remaining questions are valuable.

## Handling a suspected defect

1. Establish a concrete suspected invariant violation and relevant source revision.
2. Seek a minimal reproduction, test, or reasoning trace. If unavailable, clearly label the hypothesis as unverified.
3. Check existing audit issues (open and closed), upstream OpenDP issues (open and closed), and upstream PRs (open and merged), including the current `main` implementation.
4. If the issue already has an equivalent audit record, update or link that record; do not create a duplicate.
5. If an unmerged PR contains a plausible fix, track it as **pending upstream fix**; do not say it is fixed on `main`.
6. Candidate bugs belong in this repository's issues, with affected symbols, impact, evidence, confidence, and links. Do **not** open issues or PRs upstream unless explicitly requested in a separate task.
7. Revisit candidate issues when upstream changes; close as resolved only with an explicit disposition (fixed, duplicate, invalid, not applicable, or superseded).

Issue lifecycle terms: `Candidate`, `Reproduced`, `Confirmed`, `Upstream-ready`, `Resolved`. Treat these as descriptive states, not assertions that labels have already been configured.

## Freshness and change impact

- Compare the current upstream commit with the commit(s) recorded for affected symbols.
- Review semantic dependencies and shared assumptions, not only textual diffs.
- Mark a symbol/scope `Stale` only if relevant changes could invalidate its previous assessment. Keep unaffected audit rows intact.
- Preserve the reasoning behind disposition changes. Prefer amending existing reports/issues rather than creating another version of the same investigation.

## Safety and boundaries

- Do not invent test outcomes, source references, issue IDs, or audit coverage.
- Do not treat AI-generated hypotheses as confirmed defects without evidence.
- Do not disclose potentially exploitable vulnerabilities publicly; follow [OpenDP's security policy](https://github.com/opendp/opendp/security/policy).
- Do not modify the upstream OpenDP repository, create upstream issues, or create/open/undraft PRs as part of routine audit recording.
- Favor small, maintainable Markdown records over transcripts or automatically generated boilerplate.
