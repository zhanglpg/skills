#!/usr/bin/env python3
"""Unit tests for paper queue storage layer."""

import json
import os
import sqlite3
import tempfile
import unittest

from storage import QueueDB


class TestQueueDBInit(unittest.TestCase):
    def test_init_db_creates_tables(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "sub", "queue.db")
            db = QueueDB.init_db(db_path)
            self.assertTrue(os.path.exists(db_path))
            conn = sqlite3.connect(db_path)
            tables = [r[0] for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()]
            self.assertIn("papers", tables)
            self.assertIn("score_components", tables)
            conn.close()
            db.close()

    def test_open_existing_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "queue.db")
            db = QueueDB.init_db(db_path)
            db.add_paper(title="Test")
            db.close()
            # Re-open existing DB
            db2 = QueueDB(db_path)
            self.assertEqual(len(db2.list_papers()), 1)
            db2.close()

    def test_fail_fast_when_db_missing(self):
        with self.assertRaises(FileNotFoundError) as ctx:
            QueueDB("/nonexistent/path/queue.db")
        self.assertIn("--init", str(ctx.exception))

    def test_init_db_rejects_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "queue.db")
            db = QueueDB.init_db(db_path)
            db.close()
            with self.assertRaises(FileExistsError):
                QueueDB.init_db(db_path)


class TestAddPaper(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_add_basic_paper(self):
        pid = self.db.add_paper(title="Attention Is All You Need", arxiv_id="1706.03762")
        self.assertEqual(pid, 1)
        paper = self.db.get_paper(pid)
        self.assertEqual(paper["title"], "Attention Is All You Need")
        self.assertEqual(paper["arxiv_id"], "1706.03762")
        self.assertEqual(paper["status"], "to-read")
        self.assertEqual(paper["priority_score"], 0)

    def test_add_full_paper(self):
        pid = self.db.add_paper(
            title="Test Paper",
            arxiv_id="2401.12345",
            authors="Alice, Bob",
            abstract="A test abstract.",
            url="https://arxiv.org/abs/2401.12345",
            source="arxiv",
            source_meta={"category": "cs.LG"},
            topics=["transformers", "attention"],
            notes="Recommended by Karpathy",
        )
        paper = self.db.get_paper(pid)
        self.assertEqual(paper["authors"], "Alice, Bob")
        self.assertEqual(paper["topics"], ["transformers", "attention"])
        self.assertEqual(paper["source_meta"], {"category": "cs.LG"})
        self.assertIsNotNone(paper["added_at"])

    def test_duplicate_arxiv_id_raises(self):
        self.db.add_paper(title="Paper A", arxiv_id="2401.12345")
        with self.assertRaises(sqlite3.IntegrityError):
            self.db.add_paper(title="Paper B", arxiv_id="2401.12345")

    def test_null_arxiv_id_allowed_multiple(self):
        id1 = self.db.add_paper(title="Manual Paper 1")
        id2 = self.db.add_paper(title="Manual Paper 2")
        self.assertNotEqual(id1, id2)


class TestGetByArxivId(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_found(self):
        self.db.add_paper(title="Paper", arxiv_id="2401.12345")
        paper = self.db.get_by_arxiv_id("2401.12345")
        self.assertIsNotNone(paper)
        self.assertEqual(paper["title"], "Paper")

    def test_not_found(self):
        self.assertIsNone(self.db.get_by_arxiv_id("9999.99999"))


class TestListPapers(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="Low Priority", arxiv_id="0001.00001")
        self.db.add_paper(title="High Priority", arxiv_id="0002.00002")
        self.db.update_score(2, 9.5, [{"component": "citations", "value": 9.5}])
        self.db.update_status(1, "reading")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_list_all_sorted_by_priority(self):
        papers = self.db.list_papers()
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0]["title"], "High Priority")

    def test_filter_by_status(self):
        papers = self.db.list_papers(status="reading")
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Low Priority")

    def test_limit(self):
        papers = self.db.list_papers(limit=1)
        self.assertEqual(len(papers), 1)

    def test_filter_by_topic(self):
        self.db.add_paper(title="Topic Paper", topics=["transformers", "RAG"])
        papers = self.db.list_papers(topic="transformers")
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Topic Paper")


class TestUpdateStatus(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="Paper", arxiv_id="2401.12345")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_valid_status_transition(self):
        self.db.update_status(1, "reading")
        self.assertEqual(self.db.get_paper(1)["status"], "reading")
        self.db.update_status(1, "digested")
        self.assertEqual(self.db.get_paper(1)["status"], "digested")

    def test_invalid_status_raises(self):
        with self.assertRaises(ValueError):
            self.db.update_status(1, "invalid")


class TestUpdateScore(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="Paper", arxiv_id="2401.12345")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_score_and_components(self):
        components = [
            {"component": "citations", "value": 7.0, "detail": "150 citations"},
            {"component": "recency", "value": 9.0, "detail": "Published 3 days ago"},
        ]
        self.db.update_score(1, 8.0, components)
        paper = self.db.get_paper(1)
        self.assertEqual(paper["priority_score"], 8.0)
        sc = self.db.get_score_components(1)
        self.assertEqual(len(sc), 2)

    def test_rescore_replaces_components(self):
        self.db.update_score(1, 5.0, [{"component": "citations", "value": 5.0}])
        self.db.update_score(1, 8.0, [{"component": "citations", "value": 8.0}])
        sc = self.db.get_score_components(1)
        self.assertEqual(len(sc), 1)
        self.assertEqual(sc[0]["value"], 8.0)


class TestDigestPath(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="Paper", arxiv_id="2401.12345")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_update_digest_path_sets_digested(self):
        self.db.update_digest_path(1, "/path/to/digest.md")
        paper = self.db.get_paper(1)
        self.assertEqual(paper["digest_path"], "/path/to/digest.md")
        self.assertEqual(paper["status"], "digested")


class TestSearch(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="Attention Is All You Need", abstract="Transformer architecture")
        self.db.add_paper(title="BERT", abstract="Bidirectional encoders")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_search_title(self):
        results = self.db.search("Attention")
        self.assertEqual(len(results), 1)

    def test_search_abstract(self):
        results = self.db.search("Bidirectional")
        self.assertEqual(len(results), 1)

    def test_search_no_results(self):
        results = self.db.search("nonexistent")
        self.assertEqual(len(results), 0)


class TestStats(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = QueueDB.init_db(os.path.join(self.tmp.name, "queue.db"))
        self.db.add_paper(title="P1", topics=["transformers"])
        self.db.add_paper(title="P2", topics=["RAG"])
        self.db.update_status(2, "reading")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_stats(self):
        stats = self.db.get_stats()
        self.assertEqual(stats["total"], 2)
        self.assertEqual(stats["by_status"]["to-read"], 1)
        self.assertEqual(stats["by_status"]["reading"], 1)
        self.assertIn("transformers", stats["topics"])
        self.assertIn("rag", stats["topics"])


if __name__ == "__main__":
    unittest.main()
