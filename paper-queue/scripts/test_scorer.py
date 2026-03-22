#!/usr/bin/env python3
"""Unit tests for paper queue scoring."""

import json
import unittest
from unittest.mock import patch

from scorer import (
    fetch_citation_count,
    score_citations,
    score_recency,
    score_queue_affinity,
    score_paper,
)


class TestScoreCitations(unittest.TestCase):
    def test_zero(self):
        score, _ = score_citations(0)
        self.assertEqual(score, 0.0)

    def test_small(self):
        score, detail = score_citations(10)
        self.assertGreater(score, 0)
        self.assertLess(score, 5)
        self.assertIn("10", detail)

    def test_medium(self):
        score, _ = score_citations(100)
        self.assertGreater(score, 5)
        self.assertLess(score, 9)

    def test_high(self):
        score, _ = score_citations(500)
        self.assertAlmostEqual(score, 10.0)

    def test_very_high_capped(self):
        score, _ = score_citations(10000)
        self.assertEqual(score, 10.0)

    def test_negative(self):
        score, _ = score_citations(-5)
        self.assertEqual(score, 0.0)


class TestFetchCitationCount(unittest.TestCase):
    @patch("scorer.urlopen")
    def test_success(self, mock_urlopen):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"citationCount": 42}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        count = fetch_citation_count("2401.12345")
        self.assertEqual(count, 42)

    @patch("scorer.urlopen")
    def test_failure_returns_zero(self, mock_urlopen):
        from urllib.error import URLError
        mock_urlopen.side_effect = URLError("timeout")
        count = fetch_citation_count("2401.12345")
        self.assertEqual(count, 0)

    @patch("scorer.urlopen")
    def test_strips_version(self, mock_urlopen):
        mock_resp = unittest.mock.MagicMock()
        mock_resp.read.return_value = json.dumps({"citationCount": 5}).encode()
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = unittest.mock.MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp
        fetch_citation_count("2401.12345v2")
        call_args = mock_urlopen.call_args
        url = call_args[0][0].full_url if hasattr(call_args[0][0], 'full_url') else str(call_args[0][0])
        self.assertNotIn("v2", url)


class TestScoreRecency(unittest.TestCase):
    def test_recent(self):
        from datetime import datetime, timezone, timedelta
        recent = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()
        score, detail = score_recency(recent)
        self.assertEqual(score, 10.0)
        self.assertIn("this week", detail)

    def test_this_month(self):
        from datetime import datetime, timezone, timedelta
        date = (datetime.now(timezone.utc) - timedelta(days=15)).isoformat()
        score, _ = score_recency(date)
        self.assertEqual(score, 8.0)

    def test_old(self):
        score, detail = score_recency("2020-01-01T00:00:00Z")
        self.assertEqual(score, 1.0)
        self.assertIn("older than 1 year", detail)

    def test_none(self):
        score, _ = score_recency(None)
        self.assertEqual(score, 5.0)

    def test_bad_format(self):
        score, _ = score_recency("not-a-date")
        self.assertEqual(score, 5.0)


class TestScoreQueueAffinity(unittest.TestCase):
    def test_full_overlap(self):
        score, _ = score_queue_affinity(
            ["cs.LG", "cs.AI"],
            ["cs.LG", "cs.AI", "cs.LG", "cs.AI"],
        )
        self.assertGreater(score, 7)

    def test_partial_overlap(self):
        score, detail = score_queue_affinity(
            ["cs.LG", "cs.CL"],
            ["cs.LG", "cs.CV"],
        )
        self.assertGreater(score, 0)
        self.assertIn("cs.lg", detail)

    def test_no_overlap(self):
        score, _ = score_queue_affinity(
            ["cs.LG"],
            ["math.CO", "physics.QP"],
        )
        self.assertEqual(score, 1.0)

    def test_empty_paper_topics(self):
        score, _ = score_queue_affinity([], ["cs.LG"])
        self.assertEqual(score, 3.0)

    def test_empty_queue(self):
        score, _ = score_queue_affinity(["cs.LG"], [])
        self.assertEqual(score, 5.0)


class TestScorePaper(unittest.TestCase):
    @patch("scorer.fetch_citation_count")
    def test_combined_score(self, mock_cit):
        mock_cit.return_value = 50
        paper = {
            "arxiv_id": "2401.12345",
            "topics": ["cs.LG", "cs.AI"],
            "published": "2024-01-15T00:00:00Z",
        }
        queue_topics = ["cs.LG", "cs.CL"]
        total, components = score_paper(paper, queue_topics)
        self.assertGreater(total, 0)
        self.assertEqual(len(components), 3)
        comp_names = {c["component"] for c in components}
        self.assertEqual(comp_names, {"citations", "recency", "queue_affinity"})

    def test_with_precomputed_citations(self):
        paper = {"arxiv_id": "2401.12345", "topics": ["cs.LG"], "published": None}
        total, components = score_paper(paper, [], citation_count=100)
        cit = next(c for c in components if c["component"] == "citations")
        self.assertGreater(cit["value"], 5)

    def test_custom_weights(self):
        paper = {"topics": ["cs.LG"], "published": None}
        weights = {"citations": 0.0, "recency": 0.0, "queue_affinity": 1.0}
        total1, _ = score_paper(paper, ["cs.LG"], weights=weights, citation_count=0)
        total2, _ = score_paper(paper, [], weights=weights, citation_count=1000)
        # With affinity-only weight, queue match matters more
        self.assertGreater(total1, total2)


if __name__ == "__main__":
    unittest.main()
