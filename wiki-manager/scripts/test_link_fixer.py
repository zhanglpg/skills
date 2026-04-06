"""Tests for link_fixer.py."""

import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from link_fixer import (
    build_vault_alias_map,
    resolve_broken_link,
    fix_links_in_file,
    fix_all_links,
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


class TestResolveBrokenLink(unittest.TestCase):
    def test_exact_match(self):
        alias_map = {"transformer": "Transformer"}
        self.assertEqual(resolve_broken_link("transformer", alias_map), "Transformer")

    def test_normalized_match(self):
        alias_map = {"reinforcementlearningfromhumanfeedback": "RLHF"}
        result = resolve_broken_link("Reinforcement Learning from Human Feedback", alias_map)
        self.assertEqual(result, "RLHF")

    def test_no_match(self):
        alias_map = {"transformer": "Transformer"}
        self.assertIsNone(resolve_broken_link("Nonexistent Concept", alias_map))


class TestFixLinksInFile(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_fixes_broken_link(self):
        file_path = Path(self.tmpdir) / "test.md"
        content = "Discusses [[transformer architecture]] in detail."
        file_path.write_text(content, encoding="utf-8")

        alias_map = {"transformerarchitecture": "Transformer"}
        page_stems = {"Transformer"}
        page_titles = {"Transformer"}

        new_content, replacements = fix_links_in_file(
            file_path, content, alias_map, page_stems, page_titles
        )
        self.assertEqual(len(replacements), 1)
        self.assertEqual(replacements[0], ("transformer architecture", "Transformer"))
        self.assertIn("[[Transformer]]", new_content)
        # File should be rewritten
        self.assertIn("[[Transformer]]", file_path.read_text(encoding="utf-8"))

    def test_preserves_display_text(self):
        file_path = Path(self.tmpdir) / "test.md"
        content = "See [[transformer architecture|the architecture]]."
        file_path.write_text(content, encoding="utf-8")

        alias_map = {"transformerarchitecture": "Transformer"}
        page_stems = {"Transformer"}
        page_titles = {"Transformer"}

        new_content, replacements = fix_links_in_file(
            file_path, content, alias_map, page_stems, page_titles
        )
        self.assertEqual(len(replacements), 1)
        self.assertIn("[[Transformer|the architecture]]", new_content)

    def test_skips_valid_links(self):
        file_path = Path(self.tmpdir) / "test.md"
        content = "Links to [[Transformer]] and [[BERT]]."
        file_path.write_text(content, encoding="utf-8")

        alias_map = {"transformer": "Transformer"}
        page_stems = {"Transformer", "BERT"}
        page_titles = {"Transformer", "BERT"}

        new_content, replacements = fix_links_in_file(
            file_path, content, alias_map, page_stems, page_titles
        )
        self.assertEqual(len(replacements), 0)
        self.assertEqual(new_content, content)

    def test_dry_run(self):
        file_path = Path(self.tmpdir) / "test.md"
        original = "Discusses [[transformer architecture]]."
        file_path.write_text(original, encoding="utf-8")

        alias_map = {"transformerarchitecture": "Transformer"}
        page_stems = {"Transformer"}
        page_titles = {"Transformer"}

        new_content, replacements = fix_links_in_file(
            file_path, original, alias_map, page_stems, page_titles, dry_run=True
        )
        self.assertEqual(len(replacements), 1)
        # File should NOT be rewritten
        self.assertEqual(file_path.read_text(encoding="utf-8"), original)


class TestFixAllLinks(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.gen = Path(self.tmpdir) / "gen-notes"

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_end_to_end(self):
        # Create a concept page with an alias
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: concept\n'
            'aliases:\n  - "Transformer Architecture"\n---\n\nBody'
        ))
        # Create a digest that references it by alias
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[Transformer Architecture]] and [[Nonexistent]].'
        ))

        result = fix_all_links(self.tmpdir)
        self.assertEqual(len(result["fixed"]), 1)
        self.assertEqual(result["fixed"][0][1], "Transformer Architecture")
        self.assertEqual(result["fixed"][0][2], "Transformer")
        self.assertEqual(len(result["unresolved"]), 1)
        self.assertIn("Nonexistent", result["unresolved"][0][1])

        # Verify the file was rewritten
        digest = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[Transformer]]", digest)
        self.assertIn("[[Nonexistent]]", digest)

    def test_dry_run(self):
        _create_page(self.gen / "concepts", "Transformer.md", (
            '---\ntitle: "Transformer"\ntype: concept\n---\n\nBody'
        ))
        _create_page(self.gen / "digests", "Paper.md", (
            '---\ntitle: "Paper"\ntype: digest\ntags:\n  - ml\n---\n\n'
            'Discusses [[transformer]].'
        ))

        result = fix_all_links(self.tmpdir, dry_run=True)
        self.assertEqual(len(result["fixed"]), 1)

        # File should NOT be rewritten
        digest = (self.gen / "digests" / "Paper.md").read_text(encoding="utf-8")
        self.assertIn("[[transformer]]", digest)


if __name__ == "__main__":
    unittest.main()
