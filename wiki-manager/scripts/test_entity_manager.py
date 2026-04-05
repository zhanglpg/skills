"""Tests for entity_manager.py."""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, os.path.dirname(__file__))

from entity_manager import (
    _normalize_name,
    _sanitize_filename,
    _sanitize_llm_output,
    find_entity_page,
    list_entities,
    create_entity_page,
    update_entity_page,
    extract_entities_from_digest,
)


class TestNormalizeName(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_normalize_name("Transformer"), "transformer")

    def test_special_chars(self):
        self.assertEqual(_normalize_name("Chain-of-Thought"), "chainofthought")

    def test_case_insensitive(self):
        self.assertEqual(_normalize_name("RLHF"), _normalize_name("rlhf"))


class TestSanitizeFilename(unittest.TestCase):
    def test_basic(self):
        self.assertEqual(_sanitize_filename("Transformer"), "Transformer")

    def test_removes_special(self):
        self.assertEqual(_sanitize_filename('Test: A/B "C"'), "Test AB C")


class TestFindEntityPage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.entity_dir = Path(self.tmpdir) / "entities"
        self.entity_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_entity(self, name, aliases=None):
        aliases_yaml = ""
        if aliases:
            aliases_yaml = "aliases:\n" + "\n".join(f'  - "{a}"' for a in aliases)
        content = (
            f"---\n"
            f'title: "{name}"\n'
            f"type: entity\n"
            f"{aliases_yaml}\n"
            f"---\n\n"
            f"# {name}\n"
        )
        (self.entity_dir / f"{name}.md").write_text(content)

    def test_find_by_stem(self):
        self._write_entity("Transformer")
        result = find_entity_page("Transformer", self.entity_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result.stem, "Transformer")

    def test_find_by_alias(self):
        self._write_entity("RLHF", aliases=["Reinforcement Learning from Human Feedback"])
        result = find_entity_page("Reinforcement Learning from Human Feedback", self.entity_dir)
        self.assertIsNotNone(result)
        self.assertEqual(result.stem, "RLHF")

    def test_case_insensitive(self):
        self._write_entity("Transformer")
        result = find_entity_page("transformer", self.entity_dir)
        self.assertIsNotNone(result)

    def test_not_found(self):
        result = find_entity_page("Nonexistent", self.entity_dir)
        self.assertIsNone(result)


class TestListEntities(unittest.TestCase):
    def test_empty_dir(self):
        tmpdir = tempfile.mkdtemp()
        entity_dir = Path(tmpdir) / "entities"
        entity_dir.mkdir()
        result = list_entities(entity_dir)
        self.assertEqual(result, [])
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)

    def test_lists_entities(self):
        tmpdir = tempfile.mkdtemp()
        entity_dir = Path(tmpdir) / "entities"
        entity_dir.mkdir()
        (entity_dir / "Transformer.md").write_text(
            '---\ntitle: "Transformer"\ntype: entity\n---\n\n# Transformer\n'
        )
        (entity_dir / "RLHF.md").write_text(
            '---\ntitle: "RLHF"\ntype: entity\n---\n\n# RLHF\n'
        )
        result = list_entities(entity_dir)
        self.assertEqual(len(result), 2)
        titles = {e["title"] for e in result}
        self.assertIn("Transformer", titles)
        self.assertIn("RLHF", titles)
        import shutil
        shutil.rmtree(tmpdir, ignore_errors=True)


class TestCreateEntityPage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.entity_dir = Path(self.tmpdir) / "entities"
        self.entity_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_creates_file(self):
        def mock_llm(prompt):
            return (
                "---\n"
                'title: "Transformer"\n'
                "type: entity\n"
                "aliases:\n"
                '  - "Transformer"\n'
                "date-created: 2024-01-01\n"
                "date-updated: 2024-01-01\n"
                "source-digests: []\n"
                "tags: [ml]\n"
                "status: 🔗\n"
                "---\n\n"
                "# Transformer\n\n"
                "## Overview\nA neural architecture.\n"
            )

        path = create_entity_page("Transformer", "digest content", self.entity_dir, mock_llm)
        self.assertTrue(path.exists())
        self.assertEqual(path.stem, "Transformer")
        content = path.read_text()
        self.assertIn("Transformer", content)

    def test_wraps_output_without_frontmatter(self):
        def mock_llm(prompt):
            return "## Overview\nA neural architecture.\n"

        path = create_entity_page("Test", "digest content", self.entity_dir, mock_llm)
        content = path.read_text()
        self.assertTrue(content.startswith("---"))
        self.assertIn('title: "Test"', content)


class TestUpdateEntityPage(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.entity_dir = Path(self.tmpdir) / "entities"
        self.entity_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_update_with_valid_output(self):
        original = (
            '---\ntitle: "Transformer"\ntype: entity\n---\n\n'
            "# Transformer\n\n## Overview\nOriginal.\n"
        )
        entity_path = self.entity_dir / "Transformer.md"
        entity_path.write_text(original)

        def mock_llm(prompt):
            return (
                '---\ntitle: "Transformer"\ntype: entity\n'
                "date-updated: 2026-04-05\n---\n\n"
                "# Transformer\n\n## Overview\nUpdated.\n"
            )

        update_entity_page(entity_path, "New Paper", "digest content", mock_llm)
        content = entity_path.read_text()
        self.assertIn("Updated", content)

    def test_fallback_on_bad_output(self):
        original = (
            '---\ntitle: "Transformer"\ntype: entity\n---\n\n'
            "# Transformer\n\n## Overview\nOriginal.\n"
        )
        entity_path = self.entity_dir / "Transformer.md"
        entity_path.write_text(original)

        def mock_llm(prompt):
            return "Some malformed output without frontmatter"

        update_entity_page(entity_path, "New Paper", "digest content", mock_llm)
        content = entity_path.read_text()
        # Should append a fallback update
        self.assertIn("New Paper", content)
        self.assertIn("Original", content)  # original content preserved


class TestExtractEntities(unittest.TestCase):
    def test_json_array_response(self):
        def mock_llm(prompt):
            return '["Transformer", "Attention Mechanism", "BERT"]'

        result = extract_entities_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Transformer", "Attention Mechanism", "BERT"])

    def test_json_in_text(self):
        def mock_llm(prompt):
            return 'Here are the entities:\n["Transformer", "RLHF"]\n'

        result = extract_entities_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Transformer", "RLHF"])

    def test_fallback_parsing(self):
        def mock_llm(prompt):
            return "- Transformer\n- RLHF\n- Scaling Laws"

        result = extract_entities_from_digest("digest content", [], mock_llm)
        self.assertEqual(result, ["Transformer", "RLHF", "Scaling Laws"])

    def test_max_entities(self):
        def mock_llm(prompt):
            return '["A", "B", "C", "D", "E"]'

        result = extract_entities_from_digest("digest content", [], mock_llm, max_entities=3)
        self.assertEqual(len(result), 3)


class TestSanitizeLlmOutput(unittest.TestCase):
    CLEAN_OUTPUT = (
        '---\ntitle: "Transformer"\ntype: entity\n---\n\n'
        "# Transformer\n\n## Overview\nA neural architecture.\n"
    )

    def test_passthrough_clean_output(self):
        result = _sanitize_llm_output(self.CLEAN_OUTPUT)
        self.assertEqual(result, self.CLEAN_OUTPUT.strip())

    def test_strips_markdown_code_fence(self):
        wrapped = "```markdown\n" + self.CLEAN_OUTPUT + "```\n"
        result = _sanitize_llm_output(wrapped)
        self.assertEqual(result, self.CLEAN_OUTPUT.strip())

    def test_strips_yaml_code_fence(self):
        wrapped = "```yaml\n" + self.CLEAN_OUTPUT + "```\n"
        result = _sanitize_llm_output(wrapped)
        self.assertEqual(result, self.CLEAN_OUTPUT.strip())

    def test_removes_duplicated_frontmatter(self):
        duplicate_fm = (
            '---\ntitle: "Transformer"\ntype: entity\n---\n\n'
        )
        doubled = duplicate_fm + self.CLEAN_OUTPUT
        result = _sanitize_llm_output(doubled)
        self.assertEqual(result, self.CLEAN_OUTPUT.strip())

    def test_handles_both_issues(self):
        duplicate_fm = '---\ntitle: "Transformer"\ntype: entity\n---\n\n'
        inner = duplicate_fm + self.CLEAN_OUTPUT
        wrapped = "```markdown\n" + inner + "```\n"
        result = _sanitize_llm_output(wrapped)
        self.assertEqual(result, self.CLEAN_OUTPUT.strip())

    def test_preserves_internal_code_blocks(self):
        with_code = (
            '---\ntitle: "Test"\ntype: entity\n---\n\n'
            "# Test\n\n## Overview\nExample:\n\n"
            "```python\nprint('hello')\n```\n"
        )
        result = _sanitize_llm_output(with_code)
        self.assertIn("```python", result)
        self.assertIn("print('hello')", result)


class TestCreateEntityPageSanitization(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.entity_dir = Path(self.tmpdir) / "entities"
        self.entity_dir.mkdir()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_strips_fences_from_created_file(self):
        def mock_llm(prompt):
            return (
                "```markdown\n"
                "---\n"
                'title: "Transformer"\n'
                "type: entity\n"
                "aliases:\n"
                '  - "Transformer"\n'
                "date-created: 2024-01-01\n"
                "date-updated: 2024-01-01\n"
                "source-digests: []\n"
                "tags: [ml]\n"
                "status: 🔗\n"
                "---\n\n"
                "# Transformer\n\n"
                "## Overview\nA neural architecture.\n"
                "```\n"
            )

        path = create_entity_page("Transformer", "digest", self.entity_dir, mock_llm)
        content = path.read_text()
        self.assertTrue(content.startswith("---"))
        self.assertNotIn("```markdown", content)


if __name__ == "__main__":
    unittest.main()
