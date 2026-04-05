"""Tests for vault_index.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from vault_index import parse_frontmatter, scan_vault, build_index, update_index, PageInfo


class TestParseFrontmatter(unittest.TestCase):
    """Tests for YAML frontmatter parsing."""

    def test_basic_frontmatter(self):
        text = '---\ntitle: "Test Paper"\nyear: 2024\n---\n\nBody text.'
        fm = parse_frontmatter(text)
        self.assertEqual(fm["title"], "Test Paper")
        self.assertEqual(fm["year"], "2024")

    def test_list_frontmatter(self):
        text = (
            "---\n"
            'title: "Test"\n'
            "tags:\n"
            "  - ml\n"
            "  - nlp\n"
            "---\n"
            "\nBody."
        )
        fm = parse_frontmatter(text)
        self.assertEqual(fm["tags"], ["ml", "nlp"])

    def test_inline_list(self):
        text = '---\ntags: [ml, nlp, "deep learning"]\n---\n\nBody.'
        fm = parse_frontmatter(text)
        self.assertEqual(fm["tags"], ["ml", "nlp", "deep learning"])

    def test_no_frontmatter(self):
        text = "# Just a heading\n\nBody text."
        fm = parse_frontmatter(text)
        self.assertEqual(fm, {})

    def test_empty_values(self):
        text = "---\ntitle:\n---\n\nBody."
        fm = parse_frontmatter(text)
        # Empty value without list continuation — key may or may not be present
        # but should not raise an error
        self.assertIsInstance(fm, dict)


class TestScanVault(unittest.TestCase):
    """Tests for vault scanning."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"
        self.gen.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_page(self, subdir: str, filename: str, content: str):
        d = self.gen / subdir
        d.mkdir(parents=True, exist_ok=True)
        (d / filename).write_text(content)

    def test_scan_empty(self):
        pages = scan_vault(self.tmpdir)
        self.assertEqual(pages, [])

    def test_scan_digests(self):
        self._write_page("digests", "Paper-A.md", (
            '---\ntitle: "Paper A"\ncategories:\n  - paper-digest\ntags:\n  - ml\n---\n\n'
            '## TL;DR\nA cool paper.\n'
        ))
        pages = scan_vault(self.tmpdir)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].title, "Paper A")
        self.assertEqual(pages[0].page_type, "digest")
        self.assertEqual(pages[0].tags, ["ml"])

    def test_scan_entities(self):
        self._write_page("entities", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: entity\ndate-created: 2024-01-01\n---\n\n'
            '## Overview\nA neural architecture.\n'
        ))
        pages = scan_vault(self.tmpdir)
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0].page_type, "entity")

    def test_skips_index_and_log(self):
        (self.gen / "index.md").write_text("# Index")
        (self.gen / "log.md").write_text("# Log")
        self._write_page("digests", "Paper.md", '---\ntitle: "P"\n---\n\nBody.')
        pages = scan_vault(self.tmpdir)
        self.assertEqual(len(pages), 1)

    def test_summary_from_tldr(self):
        self._write_page("digests", "Paper.md", (
            '---\ntitle: "Paper"\n---\n\n'
            '## TL;DR\nThis paper introduces X.\n\n## Key Ideas\n- Idea 1\n'
        ))
        pages = scan_vault(self.tmpdir)
        self.assertIn("introduces X", pages[0].summary)

    def test_type_inference_from_directory(self):
        self._write_page("concepts", "Scaling.md", '---\ntitle: "Scaling"\n---\n\nBody.')
        self._write_page("syntheses", "Query.md", '---\ntitle: "Query"\n---\n\nBody.')
        pages = scan_vault(self.tmpdir)
        types = {p.title: p.page_type for p in pages}
        self.assertEqual(types["Scaling"], "concept")
        self.assertEqual(types["Query"], "synthesis")


class TestBuildIndex(unittest.TestCase):
    """Tests for index generation."""

    def test_empty_index(self):
        content = build_index([])
        self.assertIn("Knowledge Wiki Index", content)
        self.assertIn("No digests yet", content)

    def test_index_with_pages(self):
        pages = [
            PageInfo(
                path=Path("gen-notes/digests/Paper-A.md"),
                title="Paper A",
                page_type="digest",
                tags=["ml"],
                date_created="2024-01-01",
                summary="A cool paper",
            ),
            PageInfo(
                path=Path("gen-notes/entities/Transformer.md"),
                title="Transformer",
                page_type="entity",
                tags=["ml"],
                summary="A neural architecture",
            ),
        ]
        content = build_index(pages)
        self.assertIn("[[Paper-A]]", content)
        self.assertIn("[[Transformer]]", content)
        self.assertIn("Digests | 1", content)
        self.assertIn("Entities | 1", content)

    def test_index_sections_present(self):
        pages = [
            PageInfo(path=Path("gen-notes/digests/P.md"), title="P", page_type="digest"),
        ]
        content = build_index(pages)
        self.assertIn("## Recent Digests", content)
        self.assertIn("## Entities", content)
        self.assertIn("## Concepts", content)
        self.assertIn("## Stats", content)


class TestUpdateIndex(unittest.TestCase):
    """Tests for index file writing."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        gen = Path(self.tmpdir) / "gen-notes" / "digests"
        gen.mkdir(parents=True)
        (gen / "P.md").write_text('---\ntitle: "P"\n---\n\nBody.')

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_writes_index_file(self):
        path = update_index(self.tmpdir)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("Knowledge Wiki Index", content)


if __name__ == "__main__":
    unittest.main()
