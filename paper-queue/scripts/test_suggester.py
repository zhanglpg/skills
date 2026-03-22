#!/usr/bin/env python3
"""Unit tests for paper queue suggester."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from suggester import _extract_topics_from_digests, _build_arxiv_query, suggest_related
from storage import QueueDB


SAMPLE_SUGGEST_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2405.11111v1</id>
    <title>Suggested Paper One</title>
    <summary>A suggested paper about transformers.</summary>
    <author><name>Carol</name></author>
    <published>2024-05-01T00:00:00Z</published>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
  </entry>
  <entry>
    <id>http://arxiv.org/abs/2405.22222v1</id>
    <title>Suggested Paper Two</title>
    <summary>Another suggested paper.</summary>
    <author><name>Dave</name></author>
    <published>2024-05-02T00:00:00Z</published>
    <arxiv:primary_category term="cs.AI"/>
    <category term="cs.AI"/>
  </entry>
</feed>"""

SAMPLE_SUGGEST_XML_SINGLE = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2405.33333v1</id>
    <title>Only Suggestion</title>
    <summary>The only result.</summary>
    <author><name>Eve</name></author>
    <published>2024-05-03T00:00:00Z</published>
    <arxiv:primary_category term="cs.CL"/>
    <category term="cs.CL"/>
  </entry>
</feed>"""


class TestExtractTopicsFromDigests(unittest.TestCase):
    def test_empty_dir(self):
        with tempfile.TemporaryDirectory() as tmp:
            topics = _extract_topics_from_digests(tmp)
            self.assertEqual(topics, [])

    def test_none_dir(self):
        topics = _extract_topics_from_digests(None)
        self.assertEqual(topics, [])

    def test_nonexistent_dir(self):
        topics = _extract_topics_from_digests("/nonexistent/path")
        self.assertEqual(topics, [])

    def test_extracts_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            md_path = os.path.join(tmp, "digest1.md")
            with open(md_path, "w") as f:
                f.write("# Paper Digest\nCategories: cs.LG, cs.AI\nAlso mentions stat.ML\n")
            topics = _extract_topics_from_digests(tmp)
            self.assertIn("cs.LG", topics)
            self.assertIn("cs.AI", topics)
            self.assertIn("stat.ML", topics)

    def test_multiple_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "d1.md"), "w") as f:
                f.write("Category: cs.LG\n")
            with open(os.path.join(tmp, "d2.md"), "w") as f:
                f.write("Category: cs.CV\n")
            topics = _extract_topics_from_digests(tmp)
            self.assertIn("cs.LG", topics)
            self.assertIn("cs.CV", topics)

    def test_ignores_non_md_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "notes.txt"), "w") as f:
                f.write("cs.LG is great\n")
            topics = _extract_topics_from_digests(tmp)
            self.assertEqual(topics, [])

    def test_handles_eess_and_math_categories(self):
        with tempfile.TemporaryDirectory() as tmp:
            with open(os.path.join(tmp, "digest.md"), "w") as f:
                f.write("Topics: eess.SP, math.OC\n")
            topics = _extract_topics_from_digests(tmp)
            self.assertIn("eess.SP", topics)
            self.assertIn("math.OC", topics)


class TestBuildArxivQuery(unittest.TestCase):
    def test_empty_topics(self):
        self.assertEqual(_build_arxiv_query([]), "")

    def test_single_topic(self):
        query = _build_arxiv_query(["cs.LG"])
        self.assertEqual(query, "cat:cs.lg")

    def test_multiple_topics(self):
        query = _build_arxiv_query(["cs.LG", "cs.AI"])
        self.assertIn("cat:cs.lg", query)
        self.assertIn("cat:cs.ai", query)
        self.assertIn(" OR ", query)

    def test_frequency_ordering(self):
        # cs.LG appears 3 times, cs.AI once — cs.LG should come first
        query = _build_arxiv_query(["cs.LG", "cs.LG", "cs.LG", "cs.AI"])
        parts = query.split(" OR ")
        self.assertEqual(parts[0], "cat:cs.lg")

    def test_max_terms_limit(self):
        topics = [f"cs.T{i}" for i in range(20)]
        query = _build_arxiv_query(topics, max_terms=3)
        self.assertEqual(query.count("cat:"), 3)

    def test_case_insensitive_dedup(self):
        query = _build_arxiv_query(["cs.LG", "CS.LG", "cs.lg"])
        self.assertEqual(query.count("cat:"), 1)


class TestSuggestRelated(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "queue.db")
        self.db = QueueDB.init_db(self.db_path)

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_empty_queue_no_suggestions(self):
        suggestions = suggest_related(self.db)
        self.assertEqual(suggestions, [])

    @patch("suggester._fetch_text")
    def test_returns_suggestions(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML
        self.db.add_paper(title="Existing", arxiv_id="2401.00001", topics=["cs.LG"])
        suggestions = suggest_related(self.db, max_results=10)
        self.assertGreater(len(suggestions), 0)
        self.assertEqual(suggestions[0]["title"], "Suggested Paper One")

    @patch("suggester._fetch_text")
    def test_deduplicates_existing_papers(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML
        # Add one of the suggested papers to the queue already
        self.db.add_paper(title="Already There", arxiv_id="2405.11111v1", topics=["cs.LG"])
        suggestions = suggest_related(self.db, max_results=10)
        arxiv_ids = [s.get("arxiv_id") for s in suggestions]
        self.assertNotIn("2405.11111v1", arxiv_ids)

    @patch("suggester._fetch_text")
    def test_max_results_limit(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML
        self.db.add_paper(title="P", topics=["cs.LG"])
        suggestions = suggest_related(self.db, max_results=1)
        self.assertEqual(len(suggestions), 1)

    @patch("suggester._fetch_text")
    def test_with_paper_id_focus(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML_SINGLE
        pid = self.db.add_paper(
            title="Focus Paper", arxiv_id="2401.00001",
            topics=["cs.CL", "cs.AI"],
        )
        suggestions = suggest_related(self.db, paper_id=pid, max_results=5)
        # Should work without error; paper's topics get prioritized
        self.assertIsInstance(suggestions, list)

    @patch("suggester._fetch_text")
    def test_with_digest_dir(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML
        self.db.add_paper(title="P", topics=["cs.LG"])
        digest_dir = os.path.join(self.tmp.name, "digests")
        os.makedirs(digest_dir)
        with open(os.path.join(digest_dir, "d.md"), "w") as f:
            f.write("Topics: cs.AI\n")
        suggestions = suggest_related(self.db, digest_dir=digest_dir, max_results=5)
        self.assertIsInstance(suggestions, list)

    @patch("suggester._fetch_text")
    def test_api_failure_returns_empty(self, mock_fetch):
        mock_fetch.side_effect = Exception("Connection refused")
        self.db.add_paper(title="P", topics=["cs.LG"])
        suggestions = suggest_related(self.db, max_results=5)
        self.assertEqual(suggestions, [])

    @patch("suggester._fetch_text")
    def test_paper_id_with_string_topics(self, mock_fetch):
        """Test when paper topics are stored as JSON string in DB."""
        mock_fetch.return_value = SAMPLE_SUGGEST_XML_SINGLE
        import json
        pid = self.db.add_paper(title="P", topics=["cs.LG", "cs.AI"])
        # Topics are stored as JSON string internally — this tests the json.loads path
        suggestions = suggest_related(self.db, paper_id=pid, max_results=5)
        self.assertIsInstance(suggestions, list)

    @patch("suggester._fetch_text")
    def test_paper_id_nonexistent(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_SUGGEST_XML_SINGLE
        self.db.add_paper(title="P", topics=["cs.LG"])
        # paper_id=999 doesn't exist — should still work, just without focus
        suggestions = suggest_related(self.db, paper_id=999, max_results=5)
        self.assertIsInstance(suggestions, list)


if __name__ == "__main__":
    unittest.main()
