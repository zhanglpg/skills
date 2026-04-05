"""Tests for lint_checker.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from vault_index import PageInfo
from lint_checker import (
    check_orphans,
    check_broken_links,
    check_stale_entities,
    check_missing_entities,
    check_frontmatter,
    check_duplicate_entities,
    run_full_lint,
    format_lint_report,
)


class TestCheckOrphans(unittest.TestCase):
    def test_no_orphans(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
            PageInfo(path=Path("gen-notes/entities/B.md"), title="B", page_type="entity"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[B]].",
            Path("gen-notes/entities/B.md"): "Links to [[A]].",
        }
        issues = check_orphans(pages, content)
        self.assertEqual(len(issues), 0)

    def test_orphan_detected(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
            PageInfo(path=Path("gen-notes/entities/B.md"), title="B", page_type="entity"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "No links here.",
            Path("gen-notes/entities/B.md"): "No links here either.",
        }
        issues = check_orphans(pages, content)
        self.assertEqual(len(issues), 2)


class TestCheckBrokenLinks(unittest.TestCase):
    def test_no_broken(self):
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[B]].",
        }
        issues = check_broken_links(content, {"A", "B"}, {"A", "B"})
        self.assertEqual(len(issues), 0)

    def test_broken_detected(self):
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[Nonexistent]].",
        }
        issues = check_broken_links(content, {"A"}, {"A"})
        self.assertEqual(len(issues), 1)
        self.assertIn("Nonexistent", issues[0].message)


class TestCheckStaleEntities(unittest.TestCase):
    def test_fresh_entity(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/entities/T.md"),
                title="T",
                page_type="entity",
                date_updated="2026-04-01",
            ),
        ]
        issues = check_stale_entities(pages, max_age_days=90)
        self.assertEqual(len(issues), 0)

    def test_stale_entity(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/entities/T.md"),
                title="T",
                page_type="entity",
                date_updated="2020-01-01",
            ),
        ]
        issues = check_stale_entities(pages, max_age_days=90)
        self.assertEqual(len(issues), 1)


class TestCheckMissingEntities(unittest.TestCase):
    def test_no_missing(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[Transformer]].",
        }
        issues = check_missing_entities(pages, content, {"Transformer"}, min_mentions=2)
        self.assertEqual(len(issues), 0)

    def test_missing_detected(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
            PageInfo(path=Path("gen-notes/digests/B.md"), title="B", page_type="digest"),
            PageInfo(path=Path("gen-notes/digests/C.md"), title="C", page_type="digest"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "Uses [[RLHF]].",
            Path("gen-notes/digests/B.md"): "Also uses [[RLHF]].",
            Path("gen-notes/digests/C.md"): "RLHF again [[RLHF]].",
        }
        issues = check_missing_entities(pages, content, set(), min_mentions=3)
        self.assertEqual(len(issues), 1)
        self.assertIn("RLHF", issues[0].message)


class TestCheckFrontmatter(unittest.TestCase):
    def test_valid_digest(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/digests/A.md"),
                title="A",
                page_type="digest",
                tags=["ml"],
            ),
        ]
        issues = check_frontmatter(pages)
        self.assertEqual(len(issues), 0)

    def test_missing_tags(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/digests/A.md"),
                title="A",
                page_type="digest",
                tags=[],
            ),
        ]
        issues = check_frontmatter(pages)
        self.assertEqual(len(issues), 1)
        self.assertIn("tags", issues[0].message)


class TestCheckDuplicateEntities(unittest.TestCase):
    def test_no_duplicates(self):
        pages = [
            PageInfo(path=Path("e/A.md"), title="A", page_type="entity"),
            PageInfo(path=Path("e/B.md"), title="B", page_type="entity"),
        ]
        issues = check_duplicate_entities(pages)
        self.assertEqual(len(issues), 0)

    def test_duplicate_detected(self):
        pages = [
            PageInfo(path=Path("e/RLHF.md"), title="RLHF", page_type="entity"),
            PageInfo(path=Path("e/rlhf.md"), title="rlhf", page_type="entity"),
        ]
        issues = check_duplicate_entities(pages)
        self.assertEqual(len(issues), 1)


class TestRunFullLint(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        gen = Path(self.tmpdir) / "gen-notes" / "digests"
        gen.mkdir(parents=True)
        (gen / "Paper.md").write_text(
            '---\ntitle: "Paper"\ntags:\n  - ml\n---\n\nBody with [[Broken Link]].'
        )

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_finds_issues(self):
        issues = run_full_lint(self.tmpdir)
        # Should find at least broken link and orphan
        self.assertGreater(len(issues), 0)
        checks = {i.check for i in issues}
        self.assertIn("broken-links", checks)


class TestFormatLintReport(unittest.TestCase):
    def test_empty_report(self):
        report = format_lint_report([])
        self.assertIn("All checks passed", report)

    def test_report_with_issues(self):
        from lint_checker import LintIssue
        issues = [
            LintIssue("warning", "orphan-pages", "test.md", "No links"),
            LintIssue("error", "broken-links", "test.md", "[[Missing]]"),
        ]
        report = format_lint_report(issues)
        self.assertIn("2 issues found", report)
        self.assertIn("Errors", report)
        self.assertIn("Warnings", report)


if __name__ == "__main__":
    unittest.main()
