#!/usr/bin/env python3
"""Unit tests for paper queue source handlers."""

import unittest
from unittest.mock import patch, MagicMock
from xml.etree.ElementTree import Element, SubElement, tostring

from sources import (
    _extract_arxiv_id,
    _parse_arxiv_entry,
    fetch_arxiv_metadata,
    resolve_arxiv,
    resolve_twitter,
    resolve_manual,
    ATOM_NS,
    ARXIV_NS,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

SAMPLE_ARXIV_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom"
      xmlns:arxiv="http://arxiv.org/schemas/atom">
  <entry>
    <id>http://arxiv.org/abs/2401.12345v1</id>
    <title>Test Paper: A Novel Approach</title>
    <summary>This paper proposes a novel approach to testing.</summary>
    <author><name>Alice Smith</name></author>
    <author><name>Bob Jones</name></author>
    <published>2024-01-15T00:00:00Z</published>
    <arxiv:primary_category term="cs.LG"/>
    <category term="cs.LG"/>
    <category term="cs.AI"/>
  </entry>
</feed>"""

SAMPLE_ARXIV_ERROR_XML = """<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <id>http://arxiv.org/api/errors#incorrect_id</id>
    <title>Error</title>
    <summary>incorrect id format</summary>
  </entry>
</feed>"""

SAMPLE_TWEET_HTML = """
<html><body>
<p>Check out this great paper on transformers!
https://arxiv.org/abs/2401.12345
Really interesting work on scaling.</p>
</body></html>
"""

SAMPLE_TWEET_MULTI_URLS = """
<html><body>
<p>Two great papers today:
https://arxiv.org/abs/2401.12345
https://arxiv.org/pdf/2402.67890
</p>
</body></html>
"""


class TestExtractArxivId(unittest.TestCase):
    def test_bare_id(self):
        self.assertEqual(_extract_arxiv_id("2401.12345"), "2401.12345")

    def test_bare_id_with_version(self):
        self.assertEqual(_extract_arxiv_id("2401.12345v2"), "2401.12345v2")

    def test_abs_url(self):
        self.assertEqual(
            _extract_arxiv_id("https://arxiv.org/abs/2401.12345"),
            "2401.12345",
        )

    def test_pdf_url(self):
        self.assertEqual(
            _extract_arxiv_id("https://arxiv.org/pdf/2401.12345v1"),
            "2401.12345v1",
        )

    def test_not_arxiv(self):
        self.assertIsNone(_extract_arxiv_id("https://example.com/paper"))
        self.assertIsNone(_extract_arxiv_id("random text"))

    def test_whitespace_stripped(self):
        self.assertEqual(_extract_arxiv_id("  2401.12345  "), "2401.12345")


class TestParseArxivEntry(unittest.TestCase):
    def setUp(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring(SAMPLE_ARXIV_XML)
        self.entry = root.findall(f"{ATOM_NS}entry")[0]

    def test_parse_title(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertEqual(result["title"], "Test Paper: A Novel Approach")

    def test_parse_authors(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertEqual(result["authors"], "Alice Smith, Bob Jones")

    def test_parse_abstract(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertEqual(result["abstract"], "This paper proposes a novel approach to testing.")

    def test_parse_arxiv_id(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertEqual(result["arxiv_id"], "2401.12345v1")

    def test_parse_topics(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertIn("cs.LG", result["topics"])
        self.assertIn("cs.AI", result["topics"])

    def test_parse_source(self):
        result = _parse_arxiv_entry(self.entry)
        self.assertEqual(result["source"], "arxiv")


class TestFetchArxivMetadata(unittest.TestCase):
    @patch("sources._fetch_text")
    def test_success(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_ARXIV_XML
        result = fetch_arxiv_metadata("2401.12345")
        self.assertEqual(result["title"], "Test Paper: A Novel Approach")
        self.assertEqual(result["authors"], "Alice Smith, Bob Jones")
        mock_fetch.assert_called_once()

    @patch("sources._fetch_text")
    def test_error_response(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_ARXIV_ERROR_XML
        with self.assertRaises(ValueError):
            fetch_arxiv_metadata("9999.99999")

    @patch("sources._fetch_text")
    def test_strips_version_for_api_call(self, mock_fetch):
        mock_fetch.return_value = SAMPLE_ARXIV_XML
        fetch_arxiv_metadata("2401.12345v2")
        call_url = mock_fetch.call_args[0][0]
        self.assertIn("id_list=2401.12345", call_url)
        self.assertNotIn("v2", call_url)


class TestResolveArxiv(unittest.TestCase):
    @patch("sources.fetch_arxiv_metadata")
    def test_bare_id(self, mock_fetch):
        mock_fetch.return_value = {"title": "Paper", "arxiv_id": "2401.12345"}
        result = resolve_arxiv("2401.12345")
        mock_fetch.assert_called_once_with("2401.12345")

    @patch("sources.fetch_arxiv_metadata")
    def test_url(self, mock_fetch):
        mock_fetch.return_value = {"title": "Paper", "arxiv_id": "2401.12345"}
        resolve_arxiv("https://arxiv.org/abs/2401.12345")
        mock_fetch.assert_called_once_with("2401.12345")

    def test_invalid_input(self):
        with self.assertRaises(ValueError):
            resolve_arxiv("not-an-arxiv-thing")


class TestResolveTwitter(unittest.TestCase):
    @patch("sources.fetch_arxiv_metadata")
    @patch("sources._fetch_text")
    def test_extracts_arxiv_from_tweet(self, mock_fetch_text, mock_arxiv):
        mock_fetch_text.return_value = SAMPLE_TWEET_HTML
        mock_arxiv.return_value = {
            "title": "Test Paper",
            "arxiv_id": "2401.12345",
            "authors": "Alice",
            "abstract": "...",
            "url": "https://arxiv.org/abs/2401.12345",
            "source": "arxiv",
            "topics": ["cs.LG"],
        }
        papers = resolve_twitter("https://x.com/karpathy/status/123456")
        self.assertEqual(len(papers), 1)
        self.assertEqual(papers[0]["source"], "twitter")
        self.assertEqual(papers[0]["source_meta"]["tweet_author"], "karpathy")

    @patch("sources.fetch_arxiv_metadata")
    @patch("sources._fetch_text")
    def test_multiple_papers_in_tweet(self, mock_fetch_text, mock_arxiv):
        mock_fetch_text.return_value = SAMPLE_TWEET_MULTI_URLS
        mock_arxiv.side_effect = [
            {"title": "Paper 1", "arxiv_id": "2401.12345", "authors": "", "abstract": "", "url": "", "source": "arxiv", "topics": []},
            {"title": "Paper 2", "arxiv_id": "2402.67890", "authors": "", "abstract": "", "url": "", "source": "arxiv", "topics": []},
        ]
        papers = resolve_twitter("https://x.com/user/status/123")
        self.assertEqual(len(papers), 2)

    @patch("sources._fetch_text")
    def test_no_papers_found(self, mock_fetch_text):
        mock_fetch_text.return_value = "<html><body>Just a normal tweet</body></html>"
        papers = resolve_twitter("https://x.com/user/status/123")
        self.assertEqual(len(papers), 0)

    @patch("sources._fetch_text")
    def test_fetch_failure_returns_empty(self, mock_fetch_text):
        from urllib.error import URLError
        mock_fetch_text.side_effect = URLError("Connection refused")
        papers = resolve_twitter("https://x.com/user/status/123")
        self.assertEqual(len(papers), 0)


class TestResolveManual(unittest.TestCase):
    def test_basic(self):
        result = resolve_manual(title="My Paper")
        self.assertEqual(result["title"], "My Paper")
        self.assertEqual(result["source"], "manual")
        self.assertIsNone(result["arxiv_id"])

    def test_full(self):
        result = resolve_manual(
            title="Paper",
            url="https://example.com/paper.pdf",
            authors="Alice, Bob",
            notes="Found on HN",
        )
        self.assertEqual(result["url"], "https://example.com/paper.pdf")
        self.assertEqual(result["authors"], "Alice, Bob")
        self.assertEqual(result["notes"], "Found on HN")


if __name__ == "__main__":
    unittest.main()
