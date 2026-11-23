#!/usr/bin/env python3
"""Validate the deliberately small, dependency-free audit Markdown schema.

Audit frontmatter is a restricted YAML subset: one unquoted `key: value` scalar
per line. This is intentional; nested YAML is not part of schema version 1.
"""

from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path
import re
import sys

SHA = re.compile(r"[0-9a-f]{40}\Z")
PROPERTY = re.compile(r"[a-z][a-z0-9-]*(?:/[a-z][a-z0-9-]*)+\Z")
FIELD = re.compile(r"([a-z_]+): ([^:#\n][^\n]*)\Z")
STATUSES = {"Not reviewed", "Partial", "Audited", "Inconclusive", "Stale"}
HEADER = ["Symbol", "Property", "Status", "Reviewed commit", "Evidence / findings"]
LINK = re.compile(r"(?<!!)\[[^\]]+\]\(([^)]+)\)")


def parse_metadata(path: Path, errors: list[str]) -> tuple[dict[str, str], str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if not lines or lines[0] != "---":
        errors.append(f"{path}: missing opening --- frontmatter delimiter")
        return {}, ""
    try:
        end = lines.index("---", 1)
    except ValueError:
        errors.append(f"{path}: missing closing --- frontmatter delimiter")
        return {}, ""
    metadata: dict[str, str] = {}
    for num, line in enumerate(lines[1:end], 2):
        match = FIELD.fullmatch(line)
        if not match:
            errors.append(f"{path}:{num}: expected plain `key: value` metadata")
            continue
        key, value = match.groups()
        if key in metadata:
            errors.append(f"{path}:{num}: duplicate metadata field {key}")
        metadata[key] = value.strip()
    return metadata, "\n".join(lines[end + 1 :])


def check_metadata(path: Path, metadata: dict[str, str], kind: str, errors: list[str]) -> None:
    required = ({"schema_version", "updated", "source"} if kind == "source"
                else {"schema_version", "updated", "upstream_commit", "status"})
    for key in sorted(required - metadata.keys()):
        errors.append(f"{path}: missing metadata field {key}")
    for key in sorted(metadata.keys() - required):
        errors.append(f"{path}: unsupported metadata field {key}")
    if metadata.get("schema_version") != "1":
        errors.append(f"{path}: schema_version must be 1")
    updated = metadata.get("updated", "")
    try:
        if date.fromisoformat(updated).isoformat() != updated:
            raise ValueError
    except ValueError:
        errors.append(f"{path}: updated must be an ISO date (YYYY-MM-DD)")
    if kind == "investigation":
        if not SHA.fullmatch(metadata.get("upstream_commit", "")):
            errors.append(f"{path}: upstream_commit must be a full lowercase 40-character SHA")
        if metadata.get("status") not in (STATUSES - {"Not reviewed"}):
            errors.append(f"{path}: invalid investigation status")


def cells(line: str) -> list[str]:
    if not line.startswith("|") or not line.endswith("|"):
        return []
    # Markdown table cells may contain escaped pipes, e.g. a Rust trait bound.
    return [v.replace(r"\|", "|").strip() for v in re.split(r"(?<!\\)\|", line[1:-1])]


def check_coverage(path: Path, body: str, errors: list[str]) -> None:
    lines = body.splitlines()
    try:
        idx = lines.index("## Symbol coverage") + 1
    except ValueError:
        errors.append(f"{path}: missing ## Symbol coverage")
        return
    while idx < len(lines) and not lines[idx].strip():
        idx += 1
    if idx + 1 >= len(lines) or cells(lines[idx]) != HEADER:
        errors.append(f"{path}: coverage table header must be {HEADER}")
        return
    separator = cells(lines[idx + 1])
    if len(separator) != len(HEADER) or not all(re.fullmatch(r":?-{3,}:?", x) for x in separator):
        errors.append(f"{path}: invalid coverage table separator")
        return
    seen: set[tuple[str, str]] = set()
    rows = 0
    for lineno in range(idx + 2, len(lines)):
        line = lines[lineno]
        if not line.strip() or line.startswith("## "):
            break
        row = cells(line)
        if len(row) != len(HEADER):
            errors.append(f"{path}:{lineno + 1}: expected {len(HEADER)} coverage columns")
            continue
        rows += 1
        symbol, prop, status, commit, evidence = [v.strip("`") for v in row]
        if not symbol or "<" in symbol and ">" in symbol and symbol.startswith("<"):
            errors.append(f"{path}:{lineno + 1}: missing/placeholder symbol")
        if not PROPERTY.fullmatch(prop):
            errors.append(f"{path}:{lineno + 1}: property must be a scoped slug (e.g. privacy/stability)")
        if status not in STATUSES:
            errors.append(f"{path}:{lineno + 1}: invalid status {status!r}")
        if status == "Not reviewed":
            if commit != "-":
                errors.append(f"{path}:{lineno + 1}: unreviewed symbol must use - for commit")
        elif not SHA.fullmatch(commit):
            errors.append(f"{path}:{lineno + 1}: reviewed commit must be a full lowercase 40-character SHA")
        if not evidence or evidence == "-":
            errors.append(f"{path}:{lineno + 1}: evidence/findings cannot be empty")
        key = (symbol, prop)
        if key in seen:
            errors.append(f"{path}:{lineno + 1}: duplicate symbol/property {key}")
        seen.add(key)
    if not rows:
        errors.append(f"{path}: no symbol coverage rows; create files after reviewing code")


def check_links(path: Path, body: str, root: Path, errors: list[str]) -> None:
    for target in LINK.findall(body):
        target = target.split("#", 1)[0]
        if not target or ":" in target or target.startswith("/"):
            continue
        resolved = (path.parent / target).resolve()
        if not resolved.is_relative_to(root.resolve()) or not resolved.is_file():
            errors.append(f"{path}: broken local link {target}")


def validate_repository(root: Path) -> list[str]:
    errors: list[str] = []
    for kind, directory in (("source", root / "source"), ("investigation", root / "investigations")):
        if not directory.is_dir():
            errors.append(f"{directory}: directory is missing")
            continue
        for path in sorted(directory.rglob("*.md")):
            metadata, body = parse_metadata(path, errors)
            check_metadata(path, metadata, kind, errors)
            if kind == "source":
                expected = path.relative_to(directory).as_posix()[:-3]
                if metadata.get("source") != expected:
                    errors.append(f"{path}: source must equal {expected!r}")
                check_coverage(path, body, errors)
            check_links(path, body, root, errors)
    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args()
    issues = validate_repository(args.root.resolve())
    if issues:
        for issue in issues:
            print(f"ERROR: {issue}", file=sys.stderr)
        return 1
    print("Audit records valid.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
