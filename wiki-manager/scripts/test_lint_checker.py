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
    check_stale_concepts,
    check_missing_concepts,
    check_frontmatter,
    check_duplicate_concepts,
    check_stale_names,
    check_duplicate_names,
    run_full_lint,
    format_lint_report,
)


class TestCheckOrphans(unittest.TestCase):
    def test_no_orphans(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
            PageInfo(path=Path("gen-notes/concepts/B.md"), title="B", page_type="concept"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[B]].",
            Path("gen-notes/concepts/B.md"): "Links to [[A]].",
        }
        issues = check_orphans(pages, content)
        self.assertEqual(len(issues), 0)

    def test_orphan_detected(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
            PageInfo(path=Path("gen-notes/concepts/B.md"), title="B", page_type="concept"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "No links here.",
            Path("gen-notes/concepts/B.md"): "No links here either.",
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

    def test_broken_with_suggested_fix(self):
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[transformer architecture]].",
        }
        alias_map = {"transformerarchitecture": "Transformer"}
        issues = check_broken_links(content, {"A", "Transformer"}, {"A", "Transformer"}, alias_map=alias_map)
        self.assertEqual(len(issues), 1)
        self.assertEqual(issues[0].suggested_fix, "Transformer")
        self.assertIn("did you mean", issues[0].message)

    def test_broken_without_alias_no_suggested_fix(self):
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[Unknown Thing]].",
        }
        alias_map = {"transformer": "Transformer"}
        issues = check_broken_links(content, {"A"}, {"A"}, alias_map=alias_map)
        self.assertEqual(len(issues), 1)
        self.assertIsNone(issues[0].suggested_fix)
        self.assertNotIn("did you mean", issues[0].message)


class TestCheckStaleConcepts(unittest.TestCase):
    def test_fresh_concept(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/concepts/T.md"),
                title="T",
                page_type="concept",
                date_updated="2026-04-01",
            ),
        ]
        issues = check_stale_concepts(pages, max_age_days=90)
        self.assertEqual(len(issues), 0)

    def test_stale_concept(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/concepts/T.md"),
                title="T",
                page_type="concept",
                date_updated="2020-01-01",
            ),
        ]
        issues = check_stale_concepts(pages, max_age_days=90)
        self.assertEqual(len(issues), 1)


class TestCheckMissingConcepts(unittest.TestCase):
    def test_no_missing(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/A.md"), title="A", page_type="digest"),
        ]
        content = {
            Path("gen-notes/digests/A.md"): "Links to [[Transformer]].",
        }
        issues = check_missing_concepts(pages, content, {"Transformer"}, min_mentions=2)
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
        issues = check_missing_concepts(pages, content, set(), min_mentions=3)
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


class TestCheckDuplicateConcepts(unittest.TestCase):
    def test_no_duplicates(self):
        pages = [
            PageInfo(path=Path("c/A.md"), title="A", page_type="concept"),
            PageInfo(path=Path("c/B.md"), title="B", page_type="concept"),
        ]
        issues = check_duplicate_concepts(pages)
        self.assertEqual(len(issues), 0)

    def test_duplicate_detected(self):
        pages = [
            PageInfo(path=Path("c/RLHF.md"), title="RLHF", page_type="concept"),
            PageInfo(path=Path("c/rlhf.md"), title="rlhf", page_type="concept"),
        ]
        issues = check_duplicate_concepts(pages)
        self.assertEqual(len(issues), 1)


class TestCheckStaleNames(unittest.TestCase):
    def test_fresh_name(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/names/Hinton.md"),
                title="Geoffrey Hinton",
                page_type="name",
                date_updated="2026-04-01",
            ),
        ]
        issues = check_stale_names(pages, max_age_days=90)
        self.assertEqual(len(issues), 0)

    def test_stale_name(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/names/Hinton.md"),
                title="Geoffrey Hinton",
                page_type="name",
                date_updated="2020-01-01",
            ),
        ]
        issues = check_stale_names(pages, max_age_days=90)
        self.assertEqual(len(issues), 1)


class TestCheckDuplicateNames(unittest.TestCase):
    def test_no_duplicates(self):
        pages = [
            PageInfo(path=Path("n/A.md"), title="A", page_type="name"),
            PageInfo(path=Path("n/B.md"), title="B", page_type="name"),
        ]
        issues = check_duplicate_names(pages)
        self.assertEqual(len(issues), 0)

    def test_duplicate_detected(self):
        pages = [
            PageInfo(path=Path("n/GPT4.md"), title="GPT-4", page_type="name"),
            PageInfo(path=Path("n/gpt4.md"), title="gpt-4", page_type="name"),
        ]
        issues = check_duplicate_names(pages)
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
