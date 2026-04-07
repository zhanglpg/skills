"""Tests for link_fixer.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from link_fixer import (
    build_vault_alias_map,
    scan_broken_links,
    apply_link_fixes,
)


def _create_page(directory: Path, filename: str, content: str) -> Path:
    """Helper to create a markdown page."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / filename
    path.write_text(content, encoding="utf-8")
    return path


class TestBuildVaultAliasMap(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_concept_aliases(self):
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\n'
            'type: concept\naliases:\n  - "Transformer Architecture"\n---\n\nBody'
        ))
        alias_map, ambiguous = build_vault_alias_map(self.tmpdir)
        self.assertIn("transformer", alias_map)
        self.assertIn("transformerarchitecture", alias_map)
        self.assertEqual(alias_map["transformer"], "Transformer")
        self.assertEqual(len(ambiguous), 0)

    def test_name_aliases(self):
        _create_page(self.gen / "names", "Geoffrey Hinton.md", (
            '---\ntitle: "Geoffrey Hinton"\n'
            'type: name\naliases:\n  - "Geoff Hinton"\n---\n\nBody'
        ))
        alias_map, _ = build_vault_alias_map(self.tmpdir)
        self.assertIn("geoffreyhinton", alias_map)
        self.assertIn("geoffhinton", alias_map)
        self.assertEqual(alias_map["geoffhinton"], "Geoffrey Hinton")

    def test_digest_stem_and_title(self):
        _create_page(self.gen / "digests", "attention-is-all-you-need.md", (
            '---\ntitle: "Attention Is All You Need"\ntype: digest\ntags:\n  - ml\n---\n\nBody'
        ))
        alias_map, _ = build_vault_alias_map(self.tmpdir)
        self.assertIn("attentionisallyouneed", alias_map)

    def test_ambiguous_keys(self):
        """Same normalized alias pointing to different pages → ambiguous."""
        _create_page(self.gen / "concepts", "BERT.md", (
            '---\ntitle: "BERT"\ntype: concept\n---\n\nBody'
        ))
        _create_page(self.gen / "names", "bert.md", (
            '---\ntitle: "BERT"\ntype: name\n---\n\nBody'
        ))
        alias_map, ambiguous = build_vault_alias_map(self.tmpdir)
        self.assertIn("bert", ambiguous)
        self.assertNotIn("bert", alias_map)


class TestScanBrokenLinks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_finds_broken_links_with_hints(self):
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: concept\n'
            'aliases:\n  - "Transformer Architecture"\n---\n\nBody'
        ))
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[Transformer Architecture]] and [[Nonexistent]].'
        ))

        result = scan_broken_links(self.tmpdir)
        broken = result["broken_links"]
        self.assertEqual(len(broken), 2)  # both broken: alias hint ≠ auto-fix
        broken_links_map = {b["link"]: b for b in broken}
        self.assertIn("Transformer Architecture", broken_links_map)
        self.assertEqual(broken_links_map["Transformer Architecture"]["alias_hint"], "Transformer")
        self.assertIn("Nonexistent", broken_links_map)
        self.assertIsNone(broken_links_map["Nonexistent"]["alias_hint"])

    def test_existing_pages_include_aliases(self):
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: concept\n'
            'aliases:\n  - "Transformer Architecture"\n---\n\nBody'
        ))

        result = scan_broken_links(self.tmpdir)
        pages = result["existing_pages"]
        self.assertEqual(len(pages), 1)
        self.assertEqual(pages[0]["stem"], "Transformer")
        self.assertIn("Transformer Architecture", pages[0]["aliases"])

    def test_reports_total_files(self):
        _create_page(self.gen / "digests", "A.md", (
            '---\ntitle: "A"\ntype: digest\ntags:\n  - ml\n---\n\nBody'
        ))
        _create_page(self.gen / "digests", "B.md", (
            '---\ntitle: "B"\ntype: digest\ntags:\n  - ml\n---\n\nBody'
        ))
        result = scan_broken_links(self.tmpdir)
        self.assertEqual(result["total_files"], 2)


class TestApplyLinkFixes(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_replaces_broken_link(self):
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[Transformer Architecture]] in detail.'
        ))

        fixes = {"Transformer Architecture": "Transformer"}
        result = apply_link_fixes(self.tmpdir, "gen-notes", fixes)

        self.assertEqual(len(result["applied"]), 1)
        self.assertEqual(result["files_modified"], 1)

        content = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[Transformer]]", content)
        self.assertNotIn("[[Transformer Architecture]]", content)

    def test_preserves_display_text(self):
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'See [[Transformer Architecture|the architecture]].'
        ))

        fixes = {"Transformer Architecture": "Transformer"}
        apply_link_fixes(self.tmpdir, "gen-notes", fixes)

        content = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[Transformer|the architecture]]", content)

    def test_dry_run_does_not_write(self):
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[Transformer Architecture]].'
        ))

        fixes = {"Transformer Architecture": "Transformer"}
        result = apply_link_fixes(self.tmpdir, "gen-notes", fixes, dry_run=True)

        self.assertEqual(len(result["applied"]), 1)
        # File should NOT be modified
        content = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[Transformer Architecture]]", content)

    def test_multiple_fixes_across_files(self):
        _create_page(self.gen / "digests", "A.md", (
            '---\ntitle: "A"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Uses [[Geoff Hinton]] and [[transformer model]].'
        ))
        _create_page(self.gen / "digests", "B.md", (
            '---\ntitle: "B"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Also [[Geoff Hinton]].'
        ))

        fixes = {
            "Geoff Hinton": "Geoffrey Hinton",
            "transformer model": "Transformer",
        }
        result = apply_link_fixes(self.tmpdir, "gen-notes", fixes)

        self.assertEqual(result["files_modified"], 2)
        a = (self.gen / "digests" / "A.md").read_text(encoding="utf-8")
        b = (self.gen / "digests" / "B.md").read_text(encoding="utf-8")
        self.assertIn("[[Geoffrey Hinton]]", a)
        self.assertIn("[[Transformer]]", a)
        self.assertIn("[[Geoffrey Hinton]]", b)

    def test_no_match_no_change(self):
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Links to [[Transformer]].'
        ))

        fixes = {"Nonexistent": "Something"}
        result = apply_link_fixes(self.tmpdir, "gen-notes", fixes)

        self.assertEqual(len(result["applied"]), 0)
        self.assertEqual(result["files_modified"], 0)


class TestEndToEnd(unittest.TestCase):
    """Test the full scan → apply workflow."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_scan_then_apply(self):
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: concept\n'
            'aliases:\n  - "Transformer Architecture"\n---\n\nBody'
        ))
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[Transformer Architecture]] and [[Nonexistent]].'
        ))

        # Step 1: Scan
        scan = scan_broken_links(self.tmpdir)
        self.assertEqual(len(scan["broken_links"]), 2)

        # Step 2: Build fix mapping from alias hints (simulating agent decision)
        fixes = {}
        for bl in scan["broken_links"]:
            if bl["alias_hint"]:
                fixes[bl["link"]] = bl["alias_hint"]
        self.assertEqual(fixes, {"Transformer Architecture": "Transformer"})

        # Step 3: Apply
        result = apply_link_fixes(self.tmpdir, "gen-notes", fixes)
        self.assertEqual(len(result["applied"]), 1)

        # Verify
        content = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[Transformer]]", content)
        self.assertIn("[[Nonexistent]]", content)  # still broken, no fix provided


if __name__ == "__main__":
    unittest.main()
