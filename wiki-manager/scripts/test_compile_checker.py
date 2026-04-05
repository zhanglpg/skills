"""Tests for compile_checker.py — deterministic logic only."""

import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from vault_index import PageInfo
from compile_checker import (
    CompileFinding,
    build_page_batches,
    build_batch_prompt,
    build_gap_prompt,
    parse_llm_findings,
    format_compile_report,
)


def _make_page(stem: str, title: str = "", ptype: str = "digest",
               tags: list | None = None, summary: str = "") -> PageInfo:
    """Helper to create PageInfo objects for tests."""
    return PageInfo(
        path=Path(f"gen-notes/{ptype}s/{stem}.md"),
        title=title or stem,
        page_type=ptype,
        tags=tags or [],
        summary=summary,
    )


class TestBuildPageBatches(unittest.TestCase):
    def test_single_tag_group(self):
        pages = [
            _make_page("A", tags=["ml"]),
            _make_page("B", tags=["ml"]),
            _make_page("C", tags=["ml"]),
        ]
        content = {p.path: f"Content of {p.title}" for p in pages}
        batches = build_page_batches(pages, content)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["label"], "ml")
        self.assertEqual(len(batches[0]["pages"]), 3)

    def test_multiple_tag_groups(self):
        pages = [
            _make_page("A", tags=["ml"]),
            _make_page("B", tags=["ml"]),
            _make_page("C", tags=["ml"]),
            _make_page("D", tags=["nlp"]),
            _make_page("E", tags=["nlp"]),
            _make_page("F", tags=["nlp"]),
        ]
        content = {p.path: f"Content of {p.title}" for p in pages}
        batches = build_page_batches(pages, content)
        labels = {b["label"] for b in batches}
        self.assertEqual(labels, {"ml", "nlp"})

    def test_large_group_split(self):
        pages = [_make_page(f"P{i}", tags=["ml"]) for i in range(10)]
        content = {p.path: f"Content of {p.title}" for p in pages}
        batches = build_page_batches(pages, content, max_batch_size=4)
        # 10 pages / 4 per batch = 3 batches
        self.assertEqual(len(batches), 3)
        total_pages = sum(len(b["pages"]) for b in batches)
        self.assertEqual(total_pages, 10)
        # Should have part labels
        self.assertTrue(any("part" in b["label"] for b in batches))

    def test_small_groups_merged(self):
        pages = [
            _make_page("A", tags=["ml"]),
            _make_page("B", tags=["nlp"]),
            _make_page("C", tags=["vision"]),
        ]
        content = {p.path: f"Content of {p.title}" for p in pages}
        batches = build_page_batches(pages, content)
        # All groups have < 3 pages, so they get merged into "assorted"
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["label"], "assorted")
        self.assertEqual(len(batches[0]["pages"]), 3)

    def test_content_truncation(self):
        pages = [
            _make_page("A", tags=["ml"]),
            _make_page("B", tags=["ml"]),
            _make_page("C", tags=["ml"]),
        ]
        content = {p.path: "x" * 10000 for p in pages}
        batches = build_page_batches(pages, content, max_chars_per_page=100)
        for _stem, text in batches[0]["contents"].items():
            self.assertLessEqual(len(text), 130)  # 100 + truncation marker
            self.assertIn("[... truncated ...]", text)

    def test_untagged_pages(self):
        pages = [
            _make_page("A", tags=[]),
            _make_page("B", tags=[]),
            _make_page("C", tags=[]),
        ]
        content = {p.path: "text" for p in pages}
        batches = build_page_batches(pages, content)
        self.assertEqual(len(batches), 1)
        self.assertEqual(batches[0]["label"], "untagged")

    def test_empty_vault(self):
        batches = build_page_batches([], {})
        self.assertEqual(batches, [])


class TestBuildBatchPrompt(unittest.TestCase):
    def test_formats_pages_into_template(self):
        pages = [_make_page("Alpha", title="Alpha Paper", tags=["ml"])]
        batch = {
            "label": "ml",
            "pages": pages,
            "contents": {"Alpha": "Some content about Alpha."},
        }
        template = "Analyze these:\n\n{pages_content}\n\nDone."
        result = build_batch_prompt(batch, template)
        self.assertIn("Alpha Paper", result)
        self.assertIn("Some content about Alpha.", result)
        self.assertIn("Analyze these:", result)
        self.assertNotIn("{pages_content}", result)

    def test_includes_all_batch_pages(self):
        pages = [
            _make_page("A", title="Page A", tags=["ml"]),
            _make_page("B", title="Page B", tags=["ml"]),
        ]
        batch = {
            "label": "ml",
            "pages": pages,
            "contents": {"A": "Content A", "B": "Content B"},
        }
        result = build_batch_prompt(batch, "{pages_content}")
        self.assertIn("Page A", result)
        self.assertIn("Page B", result)
        self.assertIn("Content A", result)
        self.assertIn("Content B", result)


class TestBuildGapPrompt(unittest.TestCase):
    def test_compact_summary_format(self):
        pages = [
            _make_page("T", title="Transformer", ptype="entity",
                       tags=["ml", "attention"], summary="Core architecture"),
        ]
        result = build_gap_prompt(pages, "{wiki_summary}", "schema here")
        self.assertIn("Transformer (entity) [ml, attention]", result)
        self.assertIn("Core architecture", result)

    def test_schema_injection(self):
        result = build_gap_prompt([], "{wiki_summary}\n{schema_excerpt}", "## Schema\nRules here")
        self.assertIn("## Schema", result)
        self.assertIn("Rules here", result)


class TestParseLlmFindings(unittest.TestCase):
    def test_valid_json_array(self):
        response = json.dumps([
            {
                "category": "contradiction",
                "pages": ["A", "B"],
                "description": "A says X, B says Y",
            },
            {
                "category": "missing-xref",
                "pages": ["C"],
                "description": "C should link to D",
            },
        ])
        findings = parse_llm_findings(response)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "contradiction")
        self.assertEqual(findings[0].severity, "warning")
        self.assertEqual(findings[0].pages, ["A", "B"])
        self.assertEqual(findings[1].category, "missing-xref")
        self.assertEqual(findings[1].severity, "info")

    def test_json_with_surrounding_text(self):
        response = 'Here are my findings:\n\n[{"category": "data-gap", "pages": [], "description": "Missing benchmarks"}]\n\nHope that helps!'
        findings = parse_llm_findings(response)
        self.assertEqual(len(findings), 1)
        self.assertEqual(findings[0].category, "data-gap")

    def test_empty_array(self):
        findings = parse_llm_findings("[]")
        self.assertEqual(findings, [])

    def test_malformed_fallback(self):
        findings = parse_llm_findings("This is not JSON at all.")
        self.assertEqual(findings, [])

    def test_empty_input(self):
        self.assertEqual(parse_llm_findings(""), [])
        self.assertEqual(parse_llm_findings("   "), [])

    def test_missing_fields_handled(self):
        response = json.dumps([
            {"category": "contradiction"},  # missing pages and description
            {"pages": ["A"]},  # missing category — should be skipped
            {"category": "data-gap", "description": "gaps exist"},
        ])
        findings = parse_llm_findings(response)
        self.assertEqual(len(findings), 2)
        self.assertEqual(findings[0].category, "contradiction")
        self.assertEqual(findings[0].pages, [])
        self.assertEqual(findings[1].category, "data-gap")

    def test_pages_as_string(self):
        response = json.dumps([
            {"category": "missing-xref", "pages": "SinglePage", "description": "test"},
        ])
        findings = parse_llm_findings(response)
        self.assertEqual(findings[0].pages, ["SinglePage"])


class TestFormatCompileReport(unittest.TestCase):
    def test_empty_report(self):
        report = format_compile_report([], [])
        self.assertIn("0 structural issues, 0 semantic findings", report)
        self.assertIn("All structural checks passed", report)
        self.assertIn("No semantic issues found", report)

    def test_lint_only(self):
        from lint_checker import LintIssue
        lint_issues = [
            LintIssue("warning", "orphan-pages", "test.md", "No links"),
        ]
        report = format_compile_report([], lint_issues)
        self.assertIn("1 structural issues", report)
        self.assertIn("No semantic issues found", report)
        self.assertIn("test.md", report)

    def test_findings_only(self):
        findings = [
            CompileFinding("contradiction", "warning", ["A", "B"], "A contradicts B"),
        ]
        report = format_compile_report(findings, [])
        self.assertIn("1 semantic findings", report)
        self.assertIn("Contradictions Between Pages", report)
        self.assertIn("[[A]]", report)
        self.assertIn("A contradicts B", report)

    def test_merged_report(self):
        from lint_checker import LintIssue
        lint_issues = [
            LintIssue("error", "broken-links", "x.md", "[[Missing]]"),
        ]
        findings = [
            CompileFinding("data-gap", "info", [], "Need more benchmarks"),
        ]
        report = format_compile_report(findings, lint_issues)
        self.assertIn("1 structural issues, 1 semantic findings", report)
        self.assertIn("Structural Issues", report)
        self.assertIn("Semantic Findings", report)

    def test_frontmatter_present(self):
        report = format_compile_report([], [])
        self.assertTrue(report.startswith("---"))
        self.assertIn("type: compile-report", report)

    def test_findings_grouped_by_category(self):
        findings = [
            CompileFinding("contradiction", "warning", ["A"], "issue 1"),
            CompileFinding("data-gap", "info", [], "issue 2"),
            CompileFinding("contradiction", "warning", ["B"], "issue 3"),
        ]
        report = format_compile_report(findings)
        # Both contradictions should be under the same heading
        contradiction_pos = report.index("Contradictions Between Pages")
        data_gap_pos = report.index("Data Gaps")
        self.assertLess(contradiction_pos, data_gap_pos)


if __name__ == "__main__":
    unittest.main()
