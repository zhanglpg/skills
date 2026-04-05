"""Tests for wiki_manager.py — focused on cmd_ingest concept and name sourcing."""

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch, call

sys.path.insert(0, os.path.dirname(__file__))

import wiki_manager


def _make_digest(frontmatter_body: str, body: str = "## 1. Main Idea\nContent") -> str:
    """Helper to build a digest markdown string."""
    return f"---\n{frontmatter_body}\n---\n\n{body}"


class TestCmdIngestConceptSourcing(unittest.TestCase):
    """Test that cmd_ingest reads concepts from frontmatter or falls back to LLM."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_root = self.tmpdir
        self.concept_dir = os.path.join(self.tmpdir, "gen-notes", "concepts")
        self.names_dir = os.path.join(self.tmpdir, "gen-notes", "names")
        os.makedirs(self.concept_dir, exist_ok=True)
        os.makedirs(self.names_dir, exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "gen-notes"), exist_ok=True)

        self.config = {
            "vault_root": self.tmpdir,
            "concept_dir": "gen-notes/concepts",
            "names_dir": "gen-notes/names",
            "gen_notes_dir": "gen-notes",
            "log_path": "gen-notes/log.md",
            "max_concepts_per_ingest": 3,
            "max_names_per_ingest": 5,
        }
        self.logger = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_digest(self, content: str) -> str:
        digest_path = os.path.join(self.tmpdir, "test-digest.md")
        Path(digest_path).write_text(content, encoding="utf-8")
        return digest_path

    @patch("wiki_manager.append_log")
    @patch("wiki_manager.update_index")
    @patch("wiki_manager.create_name_page")
    @patch("wiki_manager.find_name_page", return_value=None)
    @patch("wiki_manager.extract_names_from_digest", return_value=[])
    @patch("wiki_manager.create_concept_page")
    @patch("wiki_manager.find_concept_page", return_value=None)
    @patch("wiki_manager.extract_concepts_from_digest")
    @patch("wiki_manager._make_llm_fn")
    def test_reads_concepts_from_frontmatter(
        self, mock_llm_fn, mock_extract, mock_find, mock_create,
        mock_name_extract, mock_name_find, mock_name_create, mock_index, mock_log
    ):
        """When digest has concepts in frontmatter, skip LLM extraction."""
        mock_llm_fn.return_value = MagicMock()
        mock_index.return_value = Path(self.tmpdir) / "gen-notes" / "index.md"

        digest = _make_digest(
            'title: "Test Paper"\n'
            'concepts:\n  - "Transformer"\n  - "BERT"'
        )
        digest_path = self._write_digest(digest)

        args = MagicMock()
        args.digest_path = digest_path

        wiki_manager.cmd_ingest(args, self.config, self.logger)

        # Should NOT call LLM extraction for concepts
        mock_extract.assert_not_called()

        # Should create concept pages for the two frontmatter concepts
        self.assertEqual(mock_create.call_count, 2)
        created_names = [c[0][0] for c in mock_create.call_args_list]
        self.assertIn("Transformer", created_names)
        self.assertIn("BERT", created_names)

    @patch("wiki_manager.append_log")
    @patch("wiki_manager.update_index")
    @patch("wiki_manager.create_name_page")
    @patch("wiki_manager.find_name_page", return_value=None)
    @patch("wiki_manager.extract_names_from_digest", return_value=[])
    @patch("wiki_manager.create_concept_page")
    @patch("wiki_manager.find_concept_page", return_value=None)
    @patch("wiki_manager.extract_concepts_from_digest", return_value=["GPT", "Scaling Laws"])
    @patch("wiki_manager.list_concepts", return_value=[])
    @patch("wiki_manager._make_llm_fn")
    def test_falls_back_to_llm_without_concepts(
        self, mock_llm_fn, mock_list, mock_extract, mock_find, mock_create,
        mock_name_extract, mock_name_find, mock_name_create, mock_index, mock_log
    ):
        """When digest lacks concepts in frontmatter, fall back to LLM extraction."""
        mock_llm_fn.return_value = MagicMock()
        mock_index.return_value = Path(self.tmpdir) / "gen-notes" / "index.md"

        digest = _make_digest('title: "Old Paper"')
        digest_path = self._write_digest(digest)

        args = MagicMock()
        args.digest_path = digest_path

        wiki_manager.cmd_ingest(args, self.config, self.logger)

        # SHOULD call LLM extraction
        mock_extract.assert_called_once()

        # Should create concept pages for the LLM-extracted concepts
        self.assertEqual(mock_create.call_count, 2)
        created_names = [c[0][0] for c in mock_create.call_args_list]
        self.assertIn("GPT", created_names)
        self.assertIn("Scaling Laws", created_names)

    @patch("wiki_manager.append_log")
    @patch("wiki_manager.update_index")
    @patch("wiki_manager.create_name_page")
    @patch("wiki_manager.find_name_page", return_value=None)
    @patch("wiki_manager.extract_names_from_digest", return_value=[])
    @patch("wiki_manager.create_concept_page")
    @patch("wiki_manager.find_concept_page", return_value=None)
    @patch("wiki_manager._make_llm_fn")
    def test_caps_frontmatter_concepts_to_max(
        self, mock_llm_fn, mock_find, mock_create,
        mock_name_extract, mock_name_find, mock_name_create, mock_index, mock_log
    ):
        """Frontmatter concepts should be capped by max_concepts_per_ingest."""
        mock_llm_fn.return_value = MagicMock()
        mock_index.return_value = Path(self.tmpdir) / "gen-notes" / "index.md"

        digest = _make_digest(
            'title: "Many Concepts Paper"\n'
            'concepts:\n  - "A"\n  - "B"\n  - "C"\n  - "D"\n  - "E"'
        )
        digest_path = self._write_digest(digest)

        args = MagicMock()
        args.digest_path = digest_path

        # max_concepts_per_ingest is 3 in self.config
        wiki_manager.cmd_ingest(args, self.config, self.logger)

        # Should only process 3 concepts (the cap)
        self.assertEqual(mock_create.call_count, 3)

    @patch("wiki_manager.append_log")
    @patch("wiki_manager.update_index")
    @patch("wiki_manager.create_name_page")
    @patch("wiki_manager.find_name_page", return_value=None)
    @patch("wiki_manager.extract_names_from_digest", return_value=[])
    @patch("wiki_manager.create_concept_page")
    @patch("wiki_manager.find_concept_page", return_value=None)
    @patch("wiki_manager.extract_concepts_from_digest")
    @patch("wiki_manager._make_llm_fn")
    def test_handles_single_concept_string(
        self, mock_llm_fn, mock_extract, mock_find, mock_create,
        mock_name_extract, mock_name_find, mock_name_create, mock_index, mock_log
    ):
        """A single concept value (string, not list) should be normalized to a list."""
        mock_llm_fn.return_value = MagicMock()
        mock_index.return_value = Path(self.tmpdir) / "gen-notes" / "index.md"

        # parse_frontmatter returns a string when there's an inline value
        digest = _make_digest('title: "Single Concept"\nconcepts: Transformer')
        digest_path = self._write_digest(digest)

        args = MagicMock()
        args.digest_path = digest_path

        wiki_manager.cmd_ingest(args, self.config, self.logger)

        # Should NOT fall back to LLM
        mock_extract.assert_not_called()

        # Should create one concept page
        self.assertEqual(mock_create.call_count, 1)
        self.assertEqual(mock_create.call_args_list[0][0][0], "Transformer")


class TestCmdIngestNameSourcing(unittest.TestCase):
    """Test that cmd_ingest reads names from frontmatter or falls back to LLM."""

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.vault_root = self.tmpdir
        self.concept_dir = os.path.join(self.tmpdir, "gen-notes", "concepts")
        self.names_dir = os.path.join(self.tmpdir, "gen-notes", "names")
        os.makedirs(self.concept_dir, exist_ok=True)
        os.makedirs(self.names_dir, exist_ok=True)
        os.makedirs(os.path.join(self.tmpdir, "gen-notes"), exist_ok=True)

        self.config = {
            "vault_root": self.tmpdir,
            "concept_dir": "gen-notes/concepts",
            "names_dir": "gen-notes/names",
            "gen_notes_dir": "gen-notes",
            "log_path": "gen-notes/log.md",
            "max_concepts_per_ingest": 3,
            "max_names_per_ingest": 5,
        }
        self.logger = MagicMock()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_digest(self, content: str) -> str:
        digest_path = os.path.join(self.tmpdir, "test-digest.md")
        Path(digest_path).write_text(content, encoding="utf-8")
        return digest_path

    @patch("wiki_manager.append_log")
    @patch("wiki_manager.update_index")
    @patch("wiki_manager.create_name_page")
    @patch("wiki_manager.find_name_page", return_value=None)
    @patch("wiki_manager.extract_names_from_digest")
    @patch("wiki_manager.create_concept_page")
    @patch("wiki_manager.find_concept_page", return_value=None)
    @patch("wiki_manager.extract_concepts_from_digest", return_value=[])
    @patch("wiki_manager.list_concepts", return_value=[])
    @patch("wiki_manager._make_llm_fn")
    def test_reads_names_from_frontmatter(
        self, mock_llm_fn, mock_list_concepts, mock_extract_concepts,
        mock_find_concept, mock_create_concept,
        mock_name_extract, mock_name_find, mock_name_create, mock_index, mock_log
    ):
        """When digest has names in frontmatter, skip LLM extraction."""
        mock_llm_fn.return_value = MagicMock()
        mock_index.return_value = Path(self.tmpdir) / "gen-notes" / "index.md"

        digest = _make_digest(
            'title: "Test Paper"\n'
            'names:\n  - "Geoffrey Hinton"\n  - "ImageNet"'
        )
        digest_path = self._write_digest(digest)

        args = MagicMock()
        args.digest_path = digest_path

        wiki_manager.cmd_ingest(args, self.config, self.logger)

        # Should NOT call LLM extraction for names
        mock_name_extract.assert_not_called()

        # Should create name pages
        self.assertEqual(mock_name_create.call_count, 2)
        created = [c[0][0] for c in mock_name_create.call_args_list]
        self.assertIn("Geoffrey Hinton", created)
        self.assertIn("ImageNet", created)


if __name__ == "__main__":
    unittest.main()
