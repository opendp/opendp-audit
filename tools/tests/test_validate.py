"""Regression tests for the audit record validator."""

from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from validate import validate_repository  # noqa: E402

SHA = "a" * 40


def record(rows: str | None = None, **metadata: str) -> str:
    keys = {"schema_version": "1", "source": "rust/src/foo.rs", "updated": "2026-11-22"}
    keys.update(metadata)
    frontmatter = "\n".join(f"{k}: {v}" for k, v in keys.items())
    default_row = f"| `Foo::bar` | privacy/stability | Audited | `{SHA}` | [Analysis](#analysis) |"
    return (f"---\n{frontmatter}\n---\n\n## Symbol coverage\n\n"
            "| Symbol | Property | Status | Reviewed commit | Evidence / findings |\n"
            "| --- | --- | --- | --- | --- |\n"
            f"{rows if rows is not None else default_row}\n\n## Analysis\n\nExamined.\n")


class ValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "investigations").mkdir()
        self.path = self.root / "source/rust/src/foo.rs.md"
        self.path.parent.mkdir(parents=True)
        self.path.write_text(record(), encoding="utf-8")

    def errors(self) -> str:
        return "\n".join(validate_repository(self.root))

    def test_valid_audit(self) -> None:
        self.assertEqual(self.errors(), "")

    def test_source_path_mismatch(self) -> None:
        self.path.write_text(record(source="rust/src/other.rs"), encoding="utf-8")
        self.assertIn("source must equal", self.errors())

    def test_reject_duplicate_symbol_property(self) -> None:
        row = f"| Foo::bar | privacy/stability | Audited | {SHA} | None found |"
        self.path.write_text(record(rows=row + "\n" + row), encoding="utf-8")
        self.assertIn("duplicate symbol/property", self.errors())

    def test_reject_invalid_status_and_commit(self) -> None:
        row = "| Foo::bar | privacy/stability | Verified | deadbeef | None found |"
        self.path.write_text(record(rows=row), encoding="utf-8")
        errors = self.errors()
        self.assertIn("invalid status", errors)
        self.assertIn("reviewed commit must", errors)

    def test_unreviewed_can_omit_commit(self) -> None:
        row = "| Foo::bar | privacy/stability | Not reviewed | - | Not yet examined |"
        self.path.write_text(record(rows=row), encoding="utf-8")
        self.assertEqual(self.errors(), "")

    def test_reject_broken_local_link(self) -> None:
        self.path.write_text(record() + "\n[missing](missing.md)\n", encoding="utf-8")
        self.assertIn("broken local link", self.errors())

    def test_valid_investigation(self) -> None:
        (self.root / "investigations/test.md").write_text(
            f"---\nschema_version: 1\nupstream_commit: {SHA}\nupdated: 2026-11-22\nstatus: Partial\n---\n\n# Test\n",
            encoding="utf-8",
        )
        self.assertEqual(self.errors(), "")

    def test_investigation_requires_source_revision(self) -> None:
        (self.root / "investigations/test.md").write_text(
            "---\nschema_version: 1\nupstream_commit: deadbeef\nupdated: 2026-11-22\nstatus: Partial\n---\n\n# Test\n",
            encoding="utf-8",
        )
        self.assertIn("upstream_commit must", self.errors())


if __name__ == "__main__":
    unittest.main()
