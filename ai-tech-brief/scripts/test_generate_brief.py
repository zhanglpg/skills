#!/usr/bin/env python3
"""Unit tests for the AI Tech Brief Generator (modular architecture)."""

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, mock_open

# Ensure the script directory is importable
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import generate_brief as gb
import fetcher as ft
import summarizer as sm
import renderer as rd


# ── Sample XML Fixtures ──────────────────────────────────────────────────

RSS_20_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<rss version="2.0">
  <channel>
    <title>Test Feed</title>
    <item>
      <title>First Article</title>
      <link>https://example.com/1</link>
      <pubDate>Thu, 01 Jan 2026 00:00:00 GMT</pubDate>
      <description>Summary of article one</description>
    </item>
    <item>
      <title>Second Article</title>
      <link>https://example.com/2</link>
      <description>Summary of article two</description>
    </item>
  </channel>
</rss>
"""

ATOM_FEED = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Atom Feed</title>
  <entry>
    <title>Atom Entry One</title>
    <link rel="alternate" href="https://example.com/atom/1"/>
    <updated>2026-01-01T00:00:00Z</updated>
    <summary>Atom summary one</summary>
  </entry>
  <entry>
    <title>Atom Entry Two</title>
    <link href="https://example.com/atom/2"/>
    <published>2026-01-02T00:00:00Z</published>
    <content>Atom content two</content>
  </entry>
</feed>
"""

ARXIV_RESPONSE = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>Scaling Laws for Neural Nets</title>
    <summary>We study scaling properties of transformers.</summary>
    <published>2026-03-01T00:00:00Z</published>
    <link href="https://arxiv.org/abs/2603.01234v1" rel="alternate" type="text/html"/>
    <author><name>Alice</name></author>
    <author><name>Bob</name></author>
    <author><name>Carol</name></author>
    <author><name>Dave</name></author>
  </entry>
  <entry>
    <title>Efficient Attention</title>
    <summary>We propose a faster attention mechanism.</summary>
    <published>2026-03-02T00:00:00Z</published>
    <link href="https://arxiv.org/abs/2603.05678v2" rel="alternate" type="text/html"/>
    <author><name>Eve</name></author>
  </entry>
</feed>
"""

MALFORMED_XML = "<not valid xml><><>"


def _make_generator(config_overrides=None, skip_config_file=True):
    """Helper to create a BriefGenerator without touching the filesystem."""
    with patch.object(gb.BriefGenerator, '_setup_logger') as mock_log, \
         patch('os.makedirs'):
        mock_log.return_value = MagicMock()
        if skip_config_file:
            gen = gb.BriefGenerator(config_path='/nonexistent/config.json')
        else:
            gen = gb.BriefGenerator()
        if config_overrides:
            gen.config.update(config_overrides)
            # Also update sub-component configs so they see overrides
            gen.fetcher.config.update(config_overrides)
            gen.summarizer.config.update(config_overrides)
            gen.renderer.config.update(config_overrides)
        return gen


def _make_fetcher(config_overrides=None):
    """Helper to create a ContentFetcher with a mock logger."""
    config = gb.DEFAULT_CONFIG.copy()
    if config_overrides:
        config.update(config_overrides)
    logger = MagicMock()
    return ft.ContentFetcher(config, logger)


def _make_summarizer(config_overrides=None):
    """Helper to create a Summarizer with a mock logger."""
    config = gb.DEFAULT_CONFIG.copy()
    if config_overrides:
        config.update(config_overrides)
    logger = MagicMock()
    return sm.Summarizer(config, logger)


def _make_renderer(config_overrides=None):
    """Helper to create a BriefRenderer with a mock logger."""
    config = gb.DEFAULT_CONFIG.copy()
    if config_overrides:
        config.update(config_overrides)
    logger = MagicMock()
    return rd.BriefRenderer(config, logger)


# ── Test Classes ─────────────────────────────────────────────────────────

class TestHashAndDeduplication(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    def test_hash_article_deterministic(self):
        h1 = self.fetcher._hash_article("Title", "https://example.com")
        h2 = self.fetcher._hash_article("Title", "https://example.com")
        self.assertEqual(h1, h2)

    def test_hash_article_different_inputs(self):
        h1 = self.fetcher._hash_article("Title A", "https://a.com")
        h2 = self.fetcher._hash_article("Title B", "https://b.com")
        self.assertNotEqual(h1, h2)

    def test_hash_article_matches_md5(self):
        title, url = "Test", "https://test.com"
        expected = hashlib.md5(f"{title}:{url}".encode()).hexdigest()
        self.assertEqual(self.fetcher._hash_article(title, url), expected)

    def test_hash_article_empty_url(self):
        h = self.fetcher._hash_article("Title")
        expected = hashlib.md5("Title:".encode()).hexdigest()
        self.assertEqual(h, expected)

    def test_is_duplicate_first_seen(self):
        self.assertFalse(self.fetcher._is_duplicate("New Article", "https://new.com"))

    def test_is_duplicate_second_seen(self):
        self.fetcher._is_duplicate("Dupe", "https://dupe.com")
        self.assertTrue(self.fetcher._is_duplicate("Dupe", "https://dupe.com"))

    def test_is_duplicate_different_url_not_duplicate(self):
        self.fetcher._is_duplicate("Title", "https://a.com")
        self.assertFalse(self.fetcher._is_duplicate("Title", "https://b.com"))

    def test_seen_hashes_populated(self):
        self.fetcher._is_duplicate("Article", "https://example.com")
        self.assertEqual(len(self.fetcher.seen_hashes), 1)


class TestDateMethods(unittest.TestCase):
    def setUp(self):
        self.gen = _make_generator()

    @patch('generate_brief.datetime')
    def test_get_date_str_format(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 3, 5, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = self.gen.get_date_str()
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2}')

    @patch('generate_brief.datetime')
    def test_get_date_display_format(self, mock_dt):
        mock_dt.utcnow.return_value = datetime(2026, 3, 5, 10, 0, 0)
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        result = self.gen.get_date_display()
        self.assertIn('2026', result)

    def test_get_date_str_returns_string(self):
        result = self.gen.get_date_str()
        self.assertIsInstance(result, str)
        self.assertEqual(len(result), 10)  # YYYY-MM-DD

    def test_get_date_display_returns_string(self):
        result = self.gen.get_date_display()
        self.assertIsInstance(result, str)

    def test_custom_timezone_offset(self):
        gen = _make_generator({'timezone_offset': 0})
        result = gen.get_date_str()
        self.assertRegex(result, r'\d{4}-\d{2}-\d{2}')


class TestGetSourcesByCategory(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher({
            'rss_sources': [
                {'name': 'NL1', 'category': 'newsletter'},
                {'name': 'NL2', 'category': 'newsletter'},
                {'name': 'Lab1', 'category': 'ai_lab'},
                {'name': 'Res1', 'category': 'research_org'},
            ]
        })

    def test_filter_newsletter(self):
        result = self.fetcher._get_sources_by_category('newsletter')
        self.assertEqual(len(result), 2)
        self.assertEqual(result[0]['name'], 'NL1')

    def test_filter_ai_lab(self):
        result = self.fetcher._get_sources_by_category('ai_lab')
        self.assertEqual(len(result), 1)

    def test_filter_nonexistent_category(self):
        result = self.fetcher._get_sources_by_category('nonexistent')
        self.assertEqual(len(result), 0)


class TestXmlText(unittest.TestCase):
    def test_returns_text(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><child>Hello</child></root>')
        self.assertEqual(ft.ContentFetcher._xml_text(root, 'child'), 'Hello')

    def test_returns_none_for_missing(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><child>Hello</child></root>')
        self.assertIsNone(ft.ContentFetcher._xml_text(root, 'missing'))

    def test_returns_none_for_empty_text(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><child></child></root>')
        self.assertIsNone(ft.ContentFetcher._xml_text(root, 'child'))

    def test_strips_whitespace(self):
        import xml.etree.ElementTree as ET
        root = ET.fromstring('<root><child>  spaced  </child></root>')
        self.assertEqual(ft.ContentFetcher._xml_text(root, 'child'), 'spaced')


class TestParseFeedXml(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    def test_parse_rss20(self):
        articles = self.fetcher._parse_feed_xml(RSS_20_FEED, 'TestSource')
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]['title'], 'First Article')
        self.assertEqual(articles[0]['url'], 'https://example.com/1')
        self.assertEqual(articles[0]['source'], 'TestSource')
        self.assertIn('Summary of article one', articles[0]['summary'])

    def test_parse_rss20_pubdate(self):
        articles = self.fetcher._parse_feed_xml(RSS_20_FEED, 'Test')
        self.assertEqual(articles[0]['published'], 'Thu, 01 Jan 2026 00:00:00 GMT')
        self.assertEqual(articles[1]['published'], '')

    def test_parse_atom(self):
        articles = self.fetcher._parse_feed_xml(ATOM_FEED, 'AtomSource')
        self.assertEqual(len(articles), 2)
        self.assertEqual(articles[0]['title'], 'Atom Entry One')
        self.assertEqual(articles[0]['url'], 'https://example.com/atom/1')

    def test_atom_alternate_link(self):
        articles = self.fetcher._parse_feed_xml(ATOM_FEED, 'Test')
        self.assertEqual(articles[0]['url'], 'https://example.com/atom/1')

    def test_atom_fallback_link(self):
        articles = self.fetcher._parse_feed_xml(ATOM_FEED, 'Test')
        self.assertEqual(articles[1]['url'], 'https://example.com/atom/2')

    def test_atom_updated_vs_published(self):
        articles = self.fetcher._parse_feed_xml(ATOM_FEED, 'Test')
        self.assertEqual(articles[0]['published'], '2026-01-01T00:00:00Z')
        self.assertEqual(articles[1]['published'], '2026-01-02T00:00:00Z')

    def test_malformed_xml_returns_empty(self):
        articles = self.fetcher._parse_feed_xml(MALFORMED_XML, 'Bad')
        self.assertEqual(articles, [])

    def test_empty_feed_returns_empty(self):
        articles = self.fetcher._parse_feed_xml('<rss><channel></channel></rss>', 'Empty')
        self.assertEqual(articles, [])

    def test_caps_at_15_articles(self):
        items = ''.join(
            f'<item><title>Article {i}</title><link>https://example.com/{i}</link></item>'
            for i in range(20)
        )
        xml = f'<rss><channel>{items}</channel></rss>'
        articles = self.fetcher._parse_feed_xml(xml, 'Many')
        self.assertEqual(len(articles), 15)

    def test_summary_truncated_to_300(self):
        long_desc = 'x' * 500
        xml = f'<rss><channel><item><title>T</title><description>{long_desc}</description></item></channel></rss>'
        articles = self.fetcher._parse_feed_xml(xml, 'Trunc')
        self.assertLessEqual(len(articles[0]['summary']), 300)

    def test_item_without_title_skipped(self):
        xml = '<rss><channel><item><link>https://example.com</link></item></channel></rss>'
        articles = self.fetcher._parse_feed_xml(xml, 'NoTitle')
        self.assertEqual(len(articles), 0)


class TestHttpGet(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft, '_HAS_HTTPX', False)
    @patch('urllib.request.urlopen')
    def test_urllib_fallback_success(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'response body'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        result = self.fetcher._http_get('https://example.com')
        self.assertEqual(result, 'response body')

    @patch.object(ft, '_HAS_HTTPX', False)
    @patch('urllib.request.urlopen', side_effect=Exception('timeout'))
    def test_urllib_fallback_failure(self, mock_urlopen):
        result = self.fetcher._http_get('https://example.com')
        self.assertIsNone(result)

    @patch.object(ft, '_HAS_HTTPX', True)
    def test_httpx_success(self):
        mock_httpx = MagicMock()
        mock_resp = MagicMock()
        mock_resp.text = 'httpx body'
        mock_resp.raise_for_status = MagicMock()
        mock_httpx.get.return_value = mock_resp

        with patch.dict(sys.modules, {'httpx': mock_httpx}):
            original = getattr(ft, 'httpx', None)
            ft.httpx = mock_httpx
            try:
                result = self.fetcher._http_get('https://example.com')
                self.assertEqual(result, 'httpx body')
                mock_httpx.get.assert_called_once()
            finally:
                if original is None:
                    delattr(ft, 'httpx')
                else:
                    ft.httpx = original

    @patch.object(ft, '_HAS_HTTPX', True)
    def test_httpx_failure(self):
        mock_httpx = MagicMock()
        mock_httpx.get.side_effect = Exception('connection error')

        original = getattr(ft, 'httpx', None)
        ft.httpx = mock_httpx
        try:
            result = self.fetcher._http_get('https://example.com')
            self.assertIsNone(result)
        finally:
            if original is None:
                delattr(ft, 'httpx')
            else:
                ft.httpx = original

    @patch.object(ft, '_HAS_HTTPX', False)
    @patch('urllib.request.urlopen')
    def test_custom_timeout(self, mock_urlopen):
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'ok'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        self.fetcher._http_get('https://example.com', timeout=30)
        args, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs.get('timeout'), 30)


class TestCheckAndFetchRss(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher({
            'rss_sources': [
                {'name': 'Good Feed', 'rss': 'https://good.com/rss', 'category': 'newsletter'},
                {'name': 'Bad Feed', 'rss': 'https://bad.com/rss', 'category': 'newsletter'},
                {'name': 'No URL', 'category': 'newsletter'},
            ]
        })

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_ok_and_failed_sources(self, mock_get):
        def side_effect(url, **kwargs):
            if 'good.com' in url:
                return RSS_20_FEED
            return None
        mock_get.side_effect = side_effect

        ok, failed = self.fetcher.check_and_fetch_rss()
        ok_names = [s['name'] for s in ok]
        failed_names = [s['name'] for s in failed]
        self.assertIn('Good Feed', ok_names)
        self.assertIn('Bad Feed', failed_names)
        self.assertIn('No URL', failed_names)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_articles_stored_in_fetched_content(self, mock_get):
        mock_get.return_value = RSS_20_FEED
        self.fetcher.config['rss_sources'] = [
            {'name': 'Feed', 'rss': 'https://feed.com/rss', 'category': 'newsletter'}
        ]
        self.fetcher.check_and_fetch_rss()
        self.assertGreater(len(self.fetcher.fetched_content['rss']), 0)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_deduplication_across_feeds(self, mock_get):
        mock_get.return_value = RSS_20_FEED
        self.fetcher.config['rss_sources'] = [
            {'name': 'Feed A', 'rss': 'https://a.com/rss', 'category': 'newsletter'},
            {'name': 'Feed B', 'rss': 'https://b.com/rss', 'category': 'newsletter'},
        ]
        self.fetcher.check_and_fetch_rss()
        self.assertEqual(len(self.fetcher.fetched_content['rss']), 2)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_source_coverage_updated(self, mock_get):
        mock_get.return_value = RSS_20_FEED
        self.fetcher.config['rss_sources'] = [
            {'name': 'Tracked', 'rss': 'https://t.com/rss', 'category': 'newsletter'}
        ]
        self.fetcher.check_and_fetch_rss()
        self.assertIn('Tracked', self.fetcher.source_coverage)
        self.assertEqual(self.fetcher.source_coverage['Tracked'], 2)

    @patch.object(ft.ContentFetcher, '_http_get', return_value=None)
    def test_all_feeds_fail(self, mock_get):
        ok, failed = self.fetcher.check_and_fetch_rss()
        self.assertEqual(len(failed), 3)


class TestFetchArxivPapers(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher({'arxiv_categories': ['cs.LG', 'cs.AI']})

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_parses_arxiv_entries(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertEqual(len(papers), 2)
        self.assertEqual(papers[0]['title'], 'Scaling Laws for Neural Nets')
        self.assertEqual(papers[0]['arxiv_id'], '2603.01234')
        self.assertEqual(papers[0]['source'], 'arXiv')

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_authors_truncated(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertIn('...', papers[0]['authors'])
        self.assertNotIn('...', papers[1]['authors'])
        self.assertEqual(papers[1]['authors'], 'Eve')

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_stores_in_fetched_content(self, mock_get):
        self.fetcher.fetch_arxiv_papers()
        self.assertEqual(len(self.fetcher.fetched_content['arxiv']), 2)

    @patch.object(ft.ContentFetcher, '_http_get', return_value=None)
    def test_api_failure_returns_empty(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertEqual(papers, [])

    @patch.object(ft.ContentFetcher, '_http_get', return_value=MALFORMED_XML)
    def test_unparsable_xml_returns_empty(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertEqual(papers, [])

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_arxiv_id_strips_version(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertEqual(papers[0]['arxiv_id'], '2603.01234')
        self.assertEqual(papers[1]['arxiv_id'], '2603.05678')


class TestFetchHackerNews(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_fetches_and_filters_ai_stories(self, mock_get):
        def side_effect(url, **kwargs):
            if 'topstories' in url:
                return json.dumps([1, 2, 3])
            if '/1.json' in url:
                return json.dumps({'type': 'story', 'title': 'New LLM Released', 'score': 500, 'descendants': 100, 'url': 'https://llm.com'})
            if '/2.json' in url:
                return json.dumps({'type': 'story', 'title': 'Cooking Recipe', 'score': 300, 'descendants': 50, 'url': 'https://cook.com'})
            if '/3.json' in url:
                return json.dumps({'type': 'story', 'title': 'GPT-5 benchmark results', 'score': 400, 'descendants': 200, 'url': 'https://gpt5.com'})
            return None
        mock_get.side_effect = side_effect

        stories = self.fetcher.fetch_hackernews_top(limit=10)
        self.assertGreater(len(stories), 0)
        titles = [s['title'] for s in stories]
        self.assertIn('New LLM Released', titles)

    @patch.object(ft.ContentFetcher, '_http_get', return_value=None)
    def test_api_failure_returns_empty(self, mock_get):
        stories = self.fetcher.fetch_hackernews_top()
        self.assertEqual(stories, [])

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_unparsable_topstories(self, mock_get):
        mock_get.return_value = 'not json'
        stories = self.fetcher.fetch_hackernews_top()
        self.assertEqual(stories, [])

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_non_story_items_filtered(self, mock_get):
        def side_effect(url, **kwargs):
            if 'topstories' in url:
                return json.dumps([1])
            if '/1.json' in url:
                return json.dumps({'type': 'comment', 'title': 'AI Comment'})
            return None
        mock_get.side_effect = side_effect

        stories = self.fetcher.fetch_hackernews_top()
        self.assertEqual(len(stories), 0)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_fallback_when_few_ai_stories(self, mock_get):
        """When fewer than 3 AI stories are found, all stories are included."""
        def side_effect(url, **kwargs):
            if 'topstories' in url:
                return json.dumps([1, 2])
            if '/1.json' in url:
                return json.dumps({'type': 'story', 'title': 'Cooking Tips', 'score': 100, 'descendants': 10, 'url': 'https://cook.com'})
            if '/2.json' in url:
                return json.dumps({'type': 'story', 'title': 'Travel Guide', 'score': 50, 'descendants': 5, 'url': 'https://travel.com'})
            return None
        mock_get.side_effect = side_effect

        stories = self.fetcher.fetch_hackernews_top(limit=10)
        self.assertEqual(len(stories), 2)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_stories_sorted_by_score(self, mock_get):
        def side_effect(url, **kwargs):
            if 'topstories' in url:
                return json.dumps([1, 2])
            if '/1.json' in url:
                return json.dumps({'type': 'story', 'title': 'Low Score AI Model', 'score': 10, 'descendants': 1, 'url': 'https://low.com'})
            if '/2.json' in url:
                return json.dumps({'type': 'story', 'title': 'High Score AI Model', 'score': 999, 'descendants': 100, 'url': 'https://high.com'})
            return None
        mock_get.side_effect = side_effect

        stories = self.fetcher.fetch_hackernews_top(limit=10)
        self.assertEqual(stories[0]['title'], 'High Score AI Model')

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_hn_url_generated(self, mock_get):
        def side_effect(url, **kwargs):
            if 'topstories' in url:
                return json.dumps([42])
            if '/42.json' in url:
                return json.dumps({'type': 'story', 'title': 'AI News', 'score': 100, 'descendants': 10, 'url': 'https://ai.com'})
            return None
        mock_get.side_effect = side_effect

        stories = self.fetcher.fetch_hackernews_top()
        self.assertEqual(stories[0]['hn_url'], 'https://news.ycombinator.com/item?id=42')


class TestFetchGithubTrending(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_parses_github_response(self, mock_get):
        mock_get.return_value = json.dumps({
            'items': [
                {
                    'full_name': 'user/repo',
                    'html_url': 'https://github.com/user/repo',
                    'description': 'An AI library',
                    'stargazers_count': 1000,
                    'language': 'Python',
                }
            ]
        })
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(len(repos), 1)
        self.assertEqual(repos[0]['name'], 'user/repo')
        self.assertEqual(repos[0]['stars'], '1000')
        self.assertEqual(repos[0]['source'], 'GitHub')

    @patch.object(ft.ContentFetcher, '_http_get', return_value=None)
    def test_api_failure(self, mock_get):
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(repos, [])

    @patch.object(ft.ContentFetcher, '_http_get', return_value='invalid json')
    def test_unparsable_json(self, mock_get):
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(repos, [])

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_null_description_handled(self, mock_get):
        mock_get.return_value = json.dumps({
            'items': [{'full_name': 'x/y', 'html_url': 'https://github.com/x/y',
                        'description': None, 'stargazers_count': 5, 'language': None}]
        })
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(repos[0]['description'], '')
        self.assertEqual(repos[0]['language'], 'N/A')

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_caps_at_10_repos(self, mock_get):
        items = [
            {'full_name': f'u/r{i}', 'html_url': f'https://github.com/u/r{i}',
             'description': 'desc', 'stargazers_count': i, 'language': 'Python'}
            for i in range(20)
        ]
        mock_get.return_value = json.dumps({'items': items})
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(len(repos), 10)


class TestFetchWebSource(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft, '_HAS_TRAFILATURA', False)
    @patch.object(ft.ContentFetcher, '_http_get')
    def test_html_fallback_strips_tags(self, mock_get):
        mock_get.return_value = '<html><body><p>Hello world, this is a long enough text for extraction to work properly with at least fifty chars.</p></body></html>'
        result = self.fetcher.fetch_web_source('Test', 'https://test.com')
        self.assertIsNotNone(result)
        self.assertNotIn('<', result['content'])

    @patch.object(ft.ContentFetcher, '_http_get', return_value=None)
    def test_fetch_failure(self, mock_get):
        result = self.fetcher.fetch_web_source('Bad', 'https://bad.com')
        self.assertIsNone(result)

    @patch.object(ft, '_HAS_TRAFILATURA', False)
    @patch.object(ft.ContentFetcher, '_http_get', return_value='<html><body>short</body></html>')
    def test_short_content_returns_none(self, mock_get):
        result = self.fetcher.fetch_web_source('Short', 'https://short.com')
        self.assertIsNone(result)

    @patch.object(ft, '_HAS_TRAFILATURA', False)
    @patch.object(ft.ContentFetcher, '_http_get')
    def test_content_capped_at_2000(self, mock_get):
        long_text = 'a' * 5000
        mock_get.return_value = f'<html><body>{long_text}</body></html>'
        result = self.fetcher.fetch_web_source('Long', 'https://long.com')
        self.assertIsNotNone(result)
        self.assertLessEqual(len(result['content']), 2000)


class TestRunGemini(unittest.TestCase):
    def setUp(self):
        self.summarizer = _make_summarizer()

    @patch('subprocess.run')
    def test_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='Generated brief')
        result = self.summarizer.run_gemini('test prompt')
        self.assertEqual(result, 'Generated brief')

    @patch('subprocess.run')
    def test_failure_retries(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='error')
        with patch('time.sleep'):
            result = self.summarizer.run_gemini('prompt', retry=1)
        self.assertIn('Error', result)
        self.assertEqual(mock_run.call_count, 2)

    @patch('subprocess.run', side_effect=subprocess.TimeoutExpired(cmd='gemini', timeout=180))
    def test_timeout_retries(self, mock_run):
        with patch('time.sleep'):
            result = self.summarizer.run_gemini('prompt', retry=1)
        self.assertIn('Error', result)

    @patch('subprocess.run', side_effect=FileNotFoundError('gemini not found'))
    def test_missing_binary(self, mock_run):
        with patch('time.sleep'):
            result = self.summarizer.run_gemini('prompt', retry=0)
        self.assertIn('Error', result)

    @patch('subprocess.run')
    def test_zero_retries(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='fail')
        result = self.summarizer.run_gemini('prompt', retry=0)
        self.assertIn('Error', result)
        self.assertEqual(mock_run.call_count, 1)


class TestValidateBrief(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_valid_brief(self):
        brief = (
            "# Daily AI Tech Brief\n"
            "## Top Stories\n"
            "https://example.com\n"
            "Twitter updates from @test\n"
            "Newsletter highlights\n"
            "AI Lab Updates\n"
            "Research Papers\n"
            "arXiv papers\n"
            "Hacker News\n"
            "GitHub trending\n"
        )
        self.assertTrue(self.renderer.validate_brief(brief))

    def test_missing_heading(self):
        brief = "No headings here, just text https://example.com"
        self.assertFalse(self.renderer.validate_brief(brief))

    def test_missing_url(self):
        brief = "# Title\n## Section\nNo links here"
        self.assertFalse(self.renderer.validate_brief(brief))

    def test_low_source_coverage_still_valid(self):
        brief = "# Title\n## Section\nhttps://example.com\nTwitter only"
        self.assertTrue(self.renderer.validate_brief(brief))


class TestFormatMethods(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    def test_format_rss_empty(self):
        result = self.fetcher._format_rss_articles_for_prompt()
        self.assertEqual(result, "No RSS articles collected.")

    def test_format_rss_with_articles(self):
        self.fetcher.fetched_content['rss'] = [
            {'title': 'Test', 'source': 'Src', 'url': 'https://t.com', 'published': '2026-01-01', 'summary': 'Sum'}
        ]
        result = self.fetcher._format_rss_articles_for_prompt()
        self.assertIn('**Test**', result)
        self.assertIn('Src', result)
        self.assertIn('https://t.com', result)

    def test_format_arxiv_empty(self):
        result = self.fetcher._format_arxiv_for_prompt()
        self.assertEqual(result, "No arXiv papers collected.")

    def test_format_arxiv_with_papers(self):
        self.fetcher.fetched_content['arxiv'] = [
            {'title': 'Paper', 'arxiv_id': '2603.00001', 'url': 'https://arxiv.org/abs/2603.00001',
             'authors': 'Alice', 'summary': 'About scaling'}
        ]
        result = self.fetcher._format_arxiv_for_prompt()
        self.assertIn('**Paper**', result)
        self.assertIn('arXiv:2603.00001', result)

    def test_format_hackernews_empty(self):
        result = self.fetcher._format_hackernews_for_prompt()
        self.assertEqual(result, "No Hacker News stories collected.")

    def test_format_hackernews_with_stories(self):
        self.fetcher.fetched_content['hackernews'] = [
            {'title': 'HN Story', 'score': '100', 'comments': '50',
             'url': 'https://hn.com', 'hn_url': 'https://news.ycombinator.com/item?id=1'}
        ]
        result = self.fetcher._format_hackernews_for_prompt()
        self.assertIn('**HN Story**', result)
        self.assertIn('score: 100', result)

    def test_format_github_empty(self):
        result = self.fetcher._format_github_for_prompt()
        self.assertEqual(result, "No GitHub trending repos collected.")

    def test_format_github_with_repos(self):
        self.fetcher.fetched_content['github_trending'] = [
            {'name': 'org/repo', 'language': 'Python', 'stars': '500',
             'description': 'AI tool', 'url': 'https://github.com/org/repo'}
        ]
        result = self.fetcher._format_github_for_prompt()
        self.assertIn('**org/repo**', result)
        self.assertIn('Python', result)

    def test_format_web_content_empty(self):
        result = self.fetcher._format_web_content_for_prompt()
        self.assertEqual(result, "No web page content collected.")

    def test_format_web_content_with_pages(self):
        self.fetcher.fetched_content['web_pages'] = [
            {'source': 'Blog', 'url': 'https://blog.com', 'content': 'Blog content here'}
        ]
        result = self.fetcher._format_web_content_for_prompt()
        self.assertIn('### Blog', result)


class TestFormatFailedSourcesWarning(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_no_failed_sources(self):
        self.assertEqual(self.renderer._format_failed_sources_warning([]), "")

    def test_with_failed_sources(self):
        failed = [
            {'name': 'Source A', 'url': 'https://a.com', 'error': 'Timeout'},
            {'name': 'Source B', 'url': '', 'error': 'No URL'},
        ]
        result = self.renderer._format_failed_sources_warning(failed)
        self.assertIn('Source A', result)
        self.assertIn('Timeout', result)
        self.assertIn('Source B', result)
        self.assertIn('Source Access Issues', result)


class TestSourceCoverageReport(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer({
            'twitter_accounts': ['karpathy', 'AndrewYNg'],
            'rss_sources': [
                {'name': 'NL1', 'category': 'newsletter'},
                {'name': 'Lab1', 'category': 'ai_lab'},
            ],
            'web_only_sources': [
                {'name': 'WebSrc', 'url': 'https://web.com', 'category': 'newsletter'},
            ],
        })
        self.fetched_content = {
            'rss': [{'title': 'a'}],
            'arxiv': [{'title': 'b'}, {'title': 'c'}],
            'hackernews': [],
            'github_trending': [{'name': 'x'}],
            'web_pages': [{'source': 'WebSrc'}],
        }
        self.source_coverage = {}
        self.failed_sources = []

    def test_report_contains_data_counts(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, self.source_coverage, self.failed_sources)
        self.assertIn('1 articles', report)   # rss
        self.assertIn('2 papers', report)     # arxiv
        self.assertIn('0 stories', report)    # hn
        self.assertIn('1 repos', report)      # github

    def test_report_contains_twitter(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, self.source_coverage, self.failed_sources)
        self.assertIn('@karpathy', report)
        self.assertIn('@AndrewYNg', report)

    def test_report_contains_categories(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, self.source_coverage, self.failed_sources)
        self.assertIn('Newsletters', report)
        self.assertIn('AI Labs', report)

    def test_report_web_only(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, self.source_coverage, self.failed_sources)
        self.assertIn('Web-only Sources', report)
        self.assertIn('page fetched', report)


class TestLoadConfig(unittest.TestCase):
    def test_loads_valid_json(self):
        gen = _make_generator()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({'timezone_offset': 5, 'max_articles': 50}, f)
            f.flush()
            gen._load_config(f.name)
        os.unlink(f.name)
        self.assertEqual(gen.config['timezone_offset'], 5)
        self.assertEqual(gen.config['max_articles'], 50)

    def test_invalid_json_does_not_crash(self):
        gen = _make_generator()
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            f.write('not json at all {{{')
            f.flush()
            gen._load_config(f.name)  # Should not raise
        os.unlink(f.name)

    def test_nonexistent_file_does_not_crash(self):
        gen = _make_generator()
        gen._load_config('/nonexistent/path/config.json')  # Should not raise


class TestDefaultConfig(unittest.TestCase):
    def test_default_config_has_required_keys(self):
        required = ['arxiv_categories', 'twitter_accounts', 'rss_sources',
                     'web_only_sources', 'gemini_timeout', 'fetch_timeout',
                     'output_dir', 'log_file']
        for key in required:
            self.assertIn(key, gb.DEFAULT_CONFIG)

    def test_default_config_values(self):
        self.assertEqual(gb.DEFAULT_CONFIG['arxiv_categories'], ['cs.LG', 'cs.AI', 'cs.SE'])
        self.assertEqual(gb.DEFAULT_CONFIG['timezone_offset'], 8)

    def test_default_config_has_template_fields(self):
        self.assertIn('template', gb.DEFAULT_CONFIG)
        self.assertIn('brief_title', gb.DEFAULT_CONFIG)
        self.assertEqual(gb.DEFAULT_CONFIG['template'], 'templates/ai-tech-brief.md')
        self.assertEqual(gb.DEFAULT_CONFIG['brief_title'], 'Daily AI Tech Brief')


class TestGeneratorInit(unittest.TestCase):
    def test_init_creates_sub_components(self):
        gen = _make_generator()
        self.assertIsInstance(gen.fetcher, ft.ContentFetcher)
        self.assertIsInstance(gen.summarizer, sm.Summarizer)
        self.assertIsInstance(gen.renderer, rd.BriefRenderer)

    def test_init_creates_empty_fetched_content(self):
        gen = _make_generator()
        expected_keys = {'rss', 'arxiv', 'hackernews', 'github_trending', 'web_pages'}
        self.assertEqual(set(gen.fetcher.fetched_content.keys()), expected_keys)
        for v in gen.fetcher.fetched_content.values():
            self.assertEqual(v, [])

    def test_init_empty_seen_hashes(self):
        gen = _make_generator()
        self.assertEqual(len(gen.fetcher.seen_hashes), 0)

    def test_init_empty_source_coverage(self):
        gen = _make_generator()
        self.assertEqual(gen.fetcher.source_coverage, {})

    def test_init_empty_failed_sources(self):
        gen = _make_generator()
        self.assertEqual(gen.fetcher.failed_sources, [])


class TestFetchWebSourcesParallel(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher({
            'web_only_sources': [
                {'name': 'Blog', 'url': 'https://blog.com', 'category': 'newsletter'},
                {'name': 'Lab', 'url': 'https://lab.com', 'category': 'ai_lab'},
                {'name': 'YouTube', 'url': 'https://youtube.com/@test', 'category': 'youtube'},
                {'name': 'Podcast', 'url': 'https://pod.com', 'category': 'podcast'},
            ]
        })

    @patch.object(ft.ContentFetcher, 'fetch_web_source')
    def test_only_fetches_fetchable_categories(self, mock_fetch):
        mock_fetch.return_value = {'source': 'Test', 'url': 'https://t.com', 'content': 'text'}
        self.fetcher.fetch_web_sources_parallel()
        self.assertEqual(mock_fetch.call_count, 2)

    @patch.object(ft.ContentFetcher, 'fetch_web_source', return_value=None)
    def test_handles_all_failures(self, mock_fetch):
        results = self.fetcher.fetch_web_sources_parallel()
        self.assertEqual(len(results), 0)


class TestGenerateBriefContent(unittest.TestCase):
    def setUp(self):
        self.summarizer = _make_summarizer({
            'twitter_accounts': ['karpathy'],
            'web_only_sources': [],
            'rss_sources': [],
        })

    @patch.object(sm.Summarizer, 'run_gemini', return_value='# Brief\n## Section\nhttps://example.com')
    def test_calls_gemini_with_prompt(self, mock_gemini):
        content_sections = {
            'rss': 'No RSS articles collected.',
            'arxiv': 'No arXiv papers collected.',
            'hackernews': 'No Hacker News stories collected.',
            'github': 'No GitHub trending repos collected.',
            'web': 'No web page content collected.',
        }
        context = {
            'twitter_accounts': ['karpathy'],
            'unfetched_web': [],
            'failed_note': '',
        }
        result = self.summarizer.summarize(content_sections, 'template text', context)
        mock_gemini.assert_called_once()
        prompt = mock_gemini.call_args[0][0]
        self.assertIn('summarizer', prompt)
        self.assertIn('@karpathy', prompt)

    @patch.object(sm.Summarizer, 'run_gemini', return_value='brief content')
    def test_includes_failed_sources_note(self, mock_gemini):
        content_sections = {
            'rss': '', 'arxiv': '', 'hackernews': '', 'github': '', 'web': '',
        }
        context = {
            'twitter_accounts': [],
            'unfetched_web': [],
            'failed_note': '\n\nNOTE: The following RSS sources were UNREACHABLE: BadSource. You may still find their content via web search.',
        }
        self.summarizer.summarize(content_sections, 'template', context)
        prompt = mock_gemini.call_args[0][0]
        self.assertIn('BadSource', prompt)
        self.assertIn('UNREACHABLE', prompt)


# ── New Tests for Template/Renderer ──────────────────────────────────────

class TestLoadTemplate(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_loads_existing_template(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False) as f:
            f.write('# $brief_title - $date_display\nContent here')
            f.flush()
            content = self.renderer.load_template(f.name)
        os.unlink(f.name)
        self.assertIn('$brief_title', content)

    def test_missing_template_raises(self):
        with self.assertRaises(FileNotFoundError):
            self.renderer.load_template('/nonexistent/template.md')


class TestFillTemplate(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_substitutes_placeholders(self):
        template = '# $brief_title - $date_display\nSources: $rss_count articles'
        result = self.renderer.fill_template(template, {
            'brief_title': 'My Brief',
            'date_display': 'March 05, 2026',
            'rss_count': '10',
        })
        self.assertIn('My Brief', result)
        self.assertIn('March 05, 2026', result)
        self.assertIn('10 articles', result)

    def test_unknown_placeholders_preserved(self):
        template = '# $brief_title\n[Link]($unknown_var)'
        result = self.renderer.fill_template(template, {'brief_title': 'Test'})
        self.assertIn('$unknown_var', result)

    def test_literal_braces_preserved(self):
        template = '# $brief_title\n- **Source:** [Title](exact_url)'
        result = self.renderer.fill_template(template, {'brief_title': 'Test'})
        self.assertIn('(exact_url)', result)


class TestBuildPrompt(unittest.TestCase):
    def setUp(self):
        self.summarizer = _make_summarizer()

    def test_prompt_contains_all_sections(self):
        content_sections = {
            'rss': 'RSS content here',
            'arxiv': 'arXiv content here',
            'hackernews': 'HN content here',
            'github': 'GitHub content here',
            'web': 'Web content here',
        }
        context = {
            'twitter_accounts': ['testuser'],
            'unfetched_web': ['Some Blog'],
            'failed_note': '',
        }
        prompt = self.summarizer.build_prompt(content_sections, 'template output', context)
        self.assertIn('RSS content here', prompt)
        self.assertIn('arXiv content here', prompt)
        self.assertIn('HN content here', prompt)
        self.assertIn('GitHub content here', prompt)
        self.assertIn('Web content here', prompt)
        self.assertIn('@testuser', prompt)
        self.assertIn('Some Blog', prompt)
        self.assertIn('template output', prompt)
        self.assertIn('ACCURACY REQUIREMENTS', prompt)


class TestGetFormattedSections(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher()

    def test_returns_all_keys(self):
        sections = self.fetcher.get_formatted_sections()
        expected_keys = {'rss', 'arxiv', 'hackernews', 'github', 'web'}
        self.assertEqual(set(sections.keys()), expected_keys)

    def test_empty_fetcher_returns_defaults(self):
        sections = self.fetcher.get_formatted_sections()
        self.assertEqual(sections['rss'], 'No RSS articles collected.')
        self.assertEqual(sections['arxiv'], 'No arXiv papers collected.')


if __name__ == '__main__':
    unittest.main()
