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

from paper_queue import (
    build_parser, cmd_add, cmd_list, cmd_status, cmd_score, cmd_stats,
    cmd_suggest, load_config, resolve_db_path, setup_logger, main,
)
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
        self.parser.parse_args(["list", "--status", "reading"])
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


class TestCmdAddFallbackManualUrl(CLITestBase):
    """Test that a non-arXiv, non-Twitter URL falls back to manual entry."""

    @patch("paper_queue.score_paper")
    def test_add_generic_url(self, mock_score):
        mock_score.return_value = (2.0, [])
        args = self.parser.parse_args(["add", "https://example.com/my-paper.pdf"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)
        papers = self.db.list_papers()
        self.assertEqual(len(papers), 1)
        self.assertIn("example.com", papers[0]["title"])

    def test_add_no_paper_arg(self):
        args = self.parser.parse_args(["add"])
        ret = cmd_add(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)



class TestCmdSuggest(CLITestBase):
    @patch("suggester.suggest_related")
    def test_suggest_empty(self, mock_suggest):
        mock_suggest.return_value = []
        args = self.parser.parse_args(["suggest"])
        ret = cmd_suggest(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)

    @patch("suggester.suggest_related")
    def test_suggest_with_results(self, mock_suggest):
        mock_suggest.return_value = [
            {"title": "Suggested Paper", "arxiv_id": "2405.11111"},
            {"title": "Another Suggestion That Has A Very Long Title That Should Be Truncated By Display", "arxiv_id": "2405.22222"},
        ]
        args = self.parser.parse_args(["suggest"])
        ret = cmd_suggest(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)

    @patch("suggester.suggest_related")
    def test_suggest_with_paper_id(self, mock_suggest):
        mock_suggest.return_value = [{"title": "S", "arxiv_id": "2405.33333"}]
        self.db.add_paper(title="Focus", arxiv_id="2401.00001", topics=["cs.LG"])
        args = self.parser.parse_args(["suggest", "1"])
        ret = cmd_suggest(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)


class TestCmdScoreEdgeCases(CLITestBase):
    def test_score_nonexistent_paper(self):
        args = self.parser.parse_args(["score", "999"])
        ret = cmd_score(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 1)

    @patch("paper_queue.score_paper")
    def test_score_empty_queue(self, mock_score):
        args = self.parser.parse_args(["score"])
        ret = cmd_score(args, self.config, self.db, self.logger)
        self.assertEqual(ret, 0)  # "No to-read papers to score"


class TestResolveDbPath(unittest.TestCase):
    def test_default_path(self):
        path = resolve_db_path({})
        self.assertIn("paper-queue", path)
        self.assertIn("queue.db", path)

    def test_override(self):
        path = resolve_db_path({}, db_override="/tmp/custom.db")
        self.assertEqual(path, "/tmp/custom.db")

    def test_config_path(self):
        path = resolve_db_path({"db_path": "/data/my-queue.db"})
        self.assertEqual(path, "/data/my-queue.db")

    def test_expandvars(self):
        os.environ["TEST_PQ_DIR"] = "/test/dir"
        path = resolve_db_path({"db_path": "$TEST_PQ_DIR/queue.db"})
        self.assertEqual(path, "/test/dir/queue.db")
        del os.environ["TEST_PQ_DIR"]


class TestSetupLogger(unittest.TestCase):
    def test_setup_logger_no_log_file(self):
        logger = setup_logger({})
        self.assertIsNotNone(logger)

    def test_setup_logger_with_log_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = os.path.join(tmp, "test.log")
            logger = setup_logger({"log_file": log_path})
            self.assertIsNotNone(logger)


class TestMainNoCommand(unittest.TestCase):
    def test_no_command_shows_help(self):
        ret = main([])
        self.assertEqual(ret, 1)


class TestMainExceptionHandling(unittest.TestCase):
    @patch("paper_queue.cmd_list", side_effect=RuntimeError("boom"))
    def test_command_exception_returns_1(self, mock_cmd):
        with tempfile.TemporaryDirectory() as tmp:
            db_path = os.path.join(tmp, "queue.db")
            main(["--db", db_path, "init"])
            ret = main(["--db", db_path, "list"])
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
