"""Tests for name_manager.py."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from name_manager import (
    find_name_page,
    list_names,
    create_name_page,
    update_name_page,
    extract_names_from_digest,
)


class TestFindNamePage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.names_dir = Path(self.tmpdir) / "names"
        self.names_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_name(self, name, aliases=None):
        aliases_yaml = ""
        if aliases:
            aliases_yaml = "aliases:\n" + "\n".join(f'  - "{a}"' for a in aliases)
        content = (
            f"---\n"
            f'title: "{name}"\n'
            f"type: name\n"
            f"{aliases_yaml}\n"
            f"---\n\n"
            f"# {name}\n"
        )
        (self.names_dir / f"{name}.md").write_text(content)

    def test_find_by_stem(self):
        self._write_name("ImageNet")
        result = find_name_page("ImageNet", self.names_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result.stem, "ImageNet")

    def test_find_by_alias(self):
        self._write_name("Geoffrey Hinton", aliases=["Geoff Hinton"])
        result = find_name_page("Geoff Hinton", self.names_dir)
        self.assertIsNotNone(result)

    def test_case_insensitive(self):
        self._write_name("ImageNet")
        result = find_name_page("imagenet", self.names_dir)
        self.assertIsNotNone(result)

    def test_not_found(self):
        result = find_name_page("Nonexistent", self.names_dir)
        self.assertIsNone(result)


class TestListNames(unittest.TestCase):
    def test_empty_dir(self):
        tmpdir = tempfile.mkdtemp()
        names_dir = Path(tmpdir) / "names"
        names_dir.mkdir()
        result = list_names(names_dir)
        self.assertEqual(result, [])
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_lists_names(self):
        tmpdir = tempfile.mkdtemp()
        names_dir = Path(tmpdir) / "names"
        names_dir.mkdir()
        (names_dir / "ImageNet.md").write_text(
            '---\ntitle: "ImageNet"\ntype: name\n---\n\n# ImageNet\n'
        )
        (names_dir / "GPT-4.md").write_text(
            '---\ntitle: "GPT-4"\ntype: name\n---\n\n# GPT-4\n'
        )
        result = list_names(names_dir)
        self.assertEqual(len(result), 2)
        titles = {n["title"] for n in result}
        self.assertIn("ImageNet", titles)
        self.assertIn("GPT-4", titles)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestCreateNamePage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.names_dir = Path(self.tmpdir) / "names"
        self.names_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_file(self):
        def mock_llm(prompt):
            return (
                "---\n"
                'title: "Geoffrey Hinton"\n'
                "type: name\n"
                "name-type: person\n"
                "aliases:\n"
                '  - "Geoff Hinton"\n'
                "date-created: 2024-01-01\n"
                "date-updated: 2024-01-01\n"
                "source-digests: []\n"
                "tags: [AI]\n"
                "status: 🔗\n"
                "---\n\n"
                "# Geoffrey Hinton\n\n"
                "## Overview\nPioneer of deep learning.\n"
            )

        path = create_name_page("Geoffrey Hinton", "digest content", self.names_dir, mock_llm)
        self.assertTrue(path.exists())
        content = path.read_text()
        self.assertIn("Geoffrey Hinton", content)

    def test_wraps_output_without_frontmatter(self):
        def mock_llm(prompt):
            return "## Overview\nA major dataset.\n"

        path = create_name_page("ImageNet", "digest content", self.names_dir, mock_llm)
        content = path.read_text()
        self.assertTrue(content.startswith("---"))
        self.assertIn('title: "ImageNet"', content)


class TestUpdateNamePage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.names_dir = Path(self.tmpdir) / "names"
        self.names_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_with_valid_output(self):
        original = (
            '---\ntitle: "ImageNet"\ntype: name\n---\n\n'
            "# ImageNet\n\n## Overview\nOriginal.\n"
        )
        name_path = self.names_dir / "ImageNet.md"
        name_path.write_text(original)

        def mock_llm(prompt):
            return (
                '---\ntitle: "ImageNet"\ntype: name\n'
                "date-updated: 2026-04-05\n---\n\n"
                "# ImageNet\n\n## Overview\nUpdated.\n"
            )

        update_name_page(name_path, "New Paper", "digest content", mock_llm)
        content = name_path.read_text()
        self.assertIn("Updated", content)

    def test_fallback_on_bad_output(self):
        original = (
            '---\ntitle: "ImageNet"\ntype: name\n---\n\n'
            "# ImageNet\n\n## Overview\nOriginal.\n"
        )
        name_path = self.names_dir / "ImageNet.md"
        name_path.write_text(original)

        def mock_llm(prompt):
            return "Some malformed output"

        update_name_page(name_path, "New Paper", "digest content", mock_llm)
        content = name_path.read_text()
        self.assertIn("New Paper", content)
        self.assertIn("Original", content)


class TestExtractNames(unittest.TestCase):
    def test_json_array_response(self):
        def mock_llm(prompt):
            return '["Geoffrey Hinton", "ImageNet", "GPT-4"]'

        result = extract_names_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Geoffrey Hinton", "ImageNet", "GPT-4"])

    def test_json_in_text(self):
        def mock_llm(prompt):
            return 'Here are the names:\n["Geoffrey Hinton", "BERT"]\n'

        result = extract_names_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Geoffrey Hinton", "BERT"])

    def test_fallback_parsing(self):
        def mock_llm(prompt):
            return "- Geoffrey Hinton\n- ImageNet\n- Stanford"

        result = extract_names_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Geoffrey Hinton", "ImageNet", "Stanford"])

    def test_max_names(self):
        def mock_llm(prompt):
            return '["A", "B", "C", "D", "E", "F"]'

        result = extract_names_from_digest("digest content", [], mock_llm, max_names=3)
        self.assertEqual(len(result), 3)


if __name__ == "__main__":
    unittest.main()
