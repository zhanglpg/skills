#!/usr/bin/env python3
"""Unit tests for paper_queue CLI."""

import os
import sys
import tempfile
import unittest
from unittest.mock import patch, MagicMock

# Ensure module imports work
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from paper_queue import build_parser, cmd_add, cmd_list, cmd_status, cmd_score, cmd_stats, load_config, resolve_db_path, main
from storage import QueueDB


class CLITestBase(unittest.TestCase):
    """Base class providing a temp DB and config."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db_path = os.path.join(self.tmp.name, "queue.db")
        self.db = QueueDB.init_db(self.db_path)
        self.config = {"scoring_weights": {"citations": 0.3, "recency": 0.3, "queue_affinity": 0.4}}
        self.logger = MagicMock()
        self.parser = build_parser()

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()


class TestCmdAddArxiv(CLITestBase):
    @patch("paper_queue.resolve_arxiv")
    @patch("paper_queue.score_paper")
    def test_add_arxiv_id(self, mock_score, mock_resolve):
        mock_resolve.return_value = {
            "title": "Test Paper",
            "arxiv_id": "2401.12345",
            "authors": "Alice",
            "abstract": "Abstract",
            "url": "https://arxiv.org/abs/2401.12345",
            "source": "arxiv",
            "source_meta": None,
            "topics": ["cs.LG"],
        }
        mock_score.return_value = (7.5, [{"component": "citations", "value": 7.5}])
        args = self.parser.parse_args(["add", "2401.12345"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)
        papers = self.db.list_papers()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "Test Paper")

    @patch("paper_queue.resolve_arxiv")
    @patch("paper_queue.score_paper")
    def test_add_duplicate_rejects(self, mock_score, mock_resolve):
        mock_resolve.return_value = {
            "title": "Paper", "arxiv_id": "2401.12345", "authors": "", "abstract": "",
            "url": "", "source": "arxiv", "source_meta": None, "topics": [],
        }
        mock_score.return_value = (5.0, [])
        args = self.parser.parse_args(["add", "2401.12345"])
        cmd_add(args, self.config, self.db, self.logger)
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)  # duplicate rejected
        self.assertEqual(len(self.db.list_papers()), 1)


class TestCmdAddManual(CLITestBase):
    @patch("paper_queue.score_paper")
    def test_add_manual(self, mock_score):
        mock_score.return_value = (3.0, [])
        args = self.parser.parse_args([
            "add", "--manual", "--title", "My Paper", "--url", "https://example.com/paper.pdf"
        ])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)
        papers = self.db.list_papers()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["title"], "My Paper")

    def test_add_manual_no_title(self):
        args = self.parser.parse_args(["add", "--manual"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)


class TestCmdAddTwitter(CLITestBase):
    @patch("paper_queue.score_paper")
    @patch("paper_queue.resolve_twitter")
    def test_add_from_tweet(self, mock_twitter, mock_score):
        mock_twitter.return_value = [{
            "title": "Tweet Paper",
            "arxiv_id": "2401.99999",
            "authors": "Bob",
            "abstract": "...",
            "url": "https://arxiv.org/abs/2401.99999",
            "source": "twitter",
            "source_meta": {"tweet_author": "karpathy"},
            "topics": ["cs.AI"],
        }]
        mock_score.return_value = (6.0, [])
        args = self.parser.parse_args(["add", "https://x.com/karpathy/status/123"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)
        papers = self.db.list_papers()
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["source"], "twitter")

    @patch("paper_queue.resolve_twitter")
    def test_add_tweet_no_papers(self, mock_twitter):
        mock_twitter.return_value = []
        args = self.parser.parse_args(["add", "https://x.com/user/status/456"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)


class TestCmdList(CLITestBase):
    def test_empty_queue(self):
        args = self.parser.parse_args(["list"])
        ret = cmd_list(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)

    def test_list_papers(self):
        self.db.add_paper(title="Paper A", arxiv_id="0001.00001")
        self.db.add_paper(title="Paper B", arxiv_id="0002.00002")
        self.db.update_score(2, 8.0, [])
        args = self.parser.parse_args(["list"])
        ret = cmd_list(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)

    def test_list_filter_status(self):
        self.db.add_paper(title="Paper A")
        self.db.add_paper(title="Paper B")
        self.db.update_status(1, "reading")
        args = self.parser.parse_args(["list", "--status", "reading"])
        papers = self.db.list_papers(status="reading")
        self.assertEqual(len(papers), 1)


class TestCmdStatus(CLITestBase):
    def test_update_status(self):
        self.db.add_paper(title="Paper", arxiv_id="2401.12345")
        args = self.parser.parse_args(["status", "1", "reading"])
        ret = cmd_status(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)
        self.assertEqual(self.db.get_paper(1)["status"], "reading")

    def test_update_nonexistent(self):
        args = self.parser.parse_args(["status", "999", "reading"])
        ret = cmd_status(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)


class TestCmdScore(CLITestBase):
    @patch("paper_queue.score_paper")
    def test_score_all(self, mock_score):
        mock_score.return_value = (7.0, [{"component": "citations", "value": 7.0}])
        self.db.add_paper(title="Paper A", arxiv_id="0001.00001", topics=["cs.LG"])
        self.db.add_paper(title="Paper B", arxiv_id="0002.00002", topics=["cs.AI"])
        args = self.parser.parse_args(["score"])
        ret = cmd_score(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)

    @patch("paper_queue.score_paper")
    def test_score_single(self, mock_score):
        mock_score.return_value = (5.0, [])
        self.db.add_paper(title="Paper", arxiv_id="0001.00001")
        args = self.parser.parse_args(["score", "1"])
        ret = cmd_score(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)


class TestCmdStats(CLITestBase):
    def test_stats(self):
        self.db.add_paper(title="P1", topics=["cs.LG"])
        self.db.add_paper(title="P2", topics=["cs.AI"])
        self.db.update_status(2, "reading")
        args = self.parser.parse_args(["stats"])
        ret = cmd_stats(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)


class TestLoadConfig(unittest.TestCase):
    def test_missing_file_returns_empty(self):
        config = load_config("/nonexistent/path.json")
        self.assertEqual(config, {})

    def test_valid_file(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            import json
            json.dump({"db_path": "/tmp/test.db"}, f)
            f.flush()
            config = load_config(f.name)
            self.assertEqual(config["db_path"], "/tmp/test.db")
            os.unlink(f.name)


class TestCmdInit(unittest.TestCase):
    def test_init_creates_db(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "queue.db")
            ret = main(["--db", db_path, "init"])
            self.assertEqual(ret, 0)
            self.assertTrue(os.path.isfile(db_path))

    def test_init_rejects_existing(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "queue.db")
            main(["--db", db_path, "init"])
            ret = main(["--db", db_path, "init"])
            self.assertEqual(ret, 1)


class TestFailFastNoDB(unittest.TestCase):
    def test_list_without_init_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "nonexistent.db")
            ret = main(["--db", db_path, "list"])
            self.assertEqual(ret, 1)

    def test_add_without_init_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "nonexistent.db")
            ret = main(["--db", db_path, "add", "--manual", "--title", "Test"])
            self.assertEqual(ret, 1)


if __name__ == "__main__":
    unittest.main()
