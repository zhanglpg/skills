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
        self.template = (
            "## Top Stories\n## Twitter Updates\n## Newsletter Highlights\n"
            "## AI Lab Updates\n## Research Papers\n## Hacker News\n## GitHub Trending\n"
        )

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
        self.assertTrue(self.renderer.validate_brief(brief, self.template))

    def test_missing_heading(self):
        brief = "No headings here, just text https://example.com"
        self.assertFalse(self.renderer.validate_brief(brief, self.template))

    def test_missing_url(self):
        brief = "# Title\n## Section\nNo links here"
        self.assertFalse(self.renderer.validate_brief(brief, self.template))

    def test_low_source_coverage_still_valid(self):
        brief = "# Title\n## Section\nhttps://example.com\nTwitter only"
        self.assertTrue(self.renderer.validate_brief(brief, self.template))


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
        self.assertIn('Newsletter', report)
        self.assertIn('Ai Lab', report)

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
        self.assertEqual(gb.DEFAULT_CONFIG['brief_title'], 'Daily Brief')


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
        template = "Summarize: {rss}\nTwitter: {twitter_block}"
        prompt_vars = {
            'rss': 'No RSS articles collected.',
            'twitter_block': '@karpathy',
        }
        self.summarizer.summarize(template, prompt_vars)
        mock_gemini.assert_called_once()
        prompt = mock_gemini.call_args[0][0]
        self.assertIn('Summarize:', prompt)
        self.assertIn('@karpathy', prompt)

    @patch.object(sm.Summarizer, 'run_gemini', return_value='brief content')
    def test_includes_failed_sources_note(self, mock_gemini):
        template = "Content: {rss}\nNote: {failed_note}"
        prompt_vars = {
            'rss': '',
            'failed_note': 'NOTE: The following RSS sources were UNREACHABLE: BadSource.',
        }
        self.summarizer.summarize(template, prompt_vars)
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
        template = (
            "{rss}\n{arxiv}\n{hackernews}\n{github}\n{web}\n"
            "{twitter_block}\n{unavailable_web_block}\n{output_format}"
        )
        prompt_vars = {
            'rss': 'RSS content here',
            'arxiv': 'arXiv content here',
            'hackernews': 'HN content here',
            'github': 'GitHub content here',
            'web': 'Web content here',
            'twitter_block': '@testuser',
            'unavailable_web_block': 'Some Blog',
            'output_format': 'template output',
        }
        prompt = self.summarizer.build_prompt(template, prompt_vars)
        self.assertIn('RSS content here', prompt)
        self.assertIn('arXiv content here', prompt)
        self.assertIn('HN content here', prompt)
        self.assertIn('GitHub content here', prompt)
        self.assertIn('Web content here', prompt)
        self.assertIn('@testuser', prompt)
        self.assertIn('Some Blog', prompt)
        self.assertIn('template output', prompt)


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


# ── Additional Tests for Renderer ────────────────────────────────────────

class TestExtractSections(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_extracts_h2_headings(self):
        template = "# Title\n## Top Stories\n## Twitter Updates\n## Research Papers\n"
        sections = self.renderer.extract_sections(template)
        self.assertEqual(sections, ['Top Stories', 'Twitter Updates', 'Research Papers'])

    def test_empty_template_returns_empty(self):
        sections = self.renderer.extract_sections("")
        self.assertEqual(sections, [])

    def test_no_h2_headings_returns_empty(self):
        template = "# H1 only\n### H3 only\nPlain text"
        sections = self.renderer.extract_sections(template)
        self.assertEqual(sections, [])

    def test_strips_trailing_whitespace(self):
        template = "## Section One  \n## Section Two\n"
        sections = self.renderer.extract_sections(template)
        self.assertEqual(sections[0], 'Section One')

    def test_does_not_include_h1_headings(self):
        template = "# Main Title\n## Sub Section\n"
        sections = self.renderer.extract_sections(template)
        self.assertNotIn('Main Title', sections)
        self.assertIn('Sub Section', sections)

    def test_multiple_sections_order_preserved(self):
        template = "## Alpha\n## Beta\n## Gamma\n"
        sections = self.renderer.extract_sections(template)
        self.assertEqual(sections, ['Alpha', 'Beta', 'Gamma'])


class TestValidateBriefWithTemplate(unittest.TestCase):
    """Tests for validate_brief using the correct two-argument signature."""

    def setUp(self):
        self.renderer = _make_renderer()
        self.template = (
            "# Brief Template\n"
            "## Top Stories\n"
            "## Twitter Updates\n"
            "## Newsletter Highlights\n"
            "## Research Papers\n"
            "## Hacker News\n"
            "## GitHub Trending\n"
        )

    def test_valid_brief_passes(self):
        brief = (
            "# Daily Brief\n"
            "## Top Stories\nhttps://example.com story one\n"
            "## Twitter Updates\nsome updates\n"
            "## Newsletter Highlights\ncontent\n"
            "## Research Papers\npapers here\n"
        )
        self.assertTrue(self.renderer.validate_brief(brief, self.template))

    def test_missing_heading_fails(self):
        brief = "No headings here just text https://example.com"
        self.assertFalse(self.renderer.validate_brief(brief, self.template))

    def test_missing_url_fails(self):
        brief = "# Title\n## Top Stories\nNo links here at all"
        self.assertFalse(self.renderer.validate_brief(brief, self.template))

    def test_low_section_coverage_still_validates(self):
        # Brief has a heading and URL even with few matching sections
        brief = "# Title\n## Top Stories\nhttps://example.com content"
        # validate_brief returns True even with low coverage (just logs a warning)
        self.assertTrue(self.renderer.validate_brief(brief, self.template))

    def test_template_with_no_sections(self):
        # When template has no ## headings, validation falls back to True
        brief = "# Title\nhttps://example.com"
        empty_template = "# Main Title\nNo sections here"
        self.assertTrue(self.renderer.validate_brief(brief, empty_template))

    def test_all_sections_present_passes(self):
        brief = (
            "# Brief\nhttps://start.com\n"
            "## Top Stories\ncontent\n"
            "## Twitter Updates\ncontent\n"
            "## Newsletter Highlights\ncontent\n"
            "## Research Papers\ncontent\n"
            "## Hacker News\ncontent\n"
            "## GitHub Trending\ncontent\n"
        )
        self.assertTrue(self.renderer.validate_brief(brief, self.template))


class TestRenderOutput(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer({
            'twitter_accounts': ['testuser'],
            'rss_sources': [],
            'web_only_sources': [],
        })
        self.fetched_content = {
            'rss': [], 'arxiv': [], 'hackernews': [],
            'github_trending': [], 'web_pages': [],
        }

    def test_output_contains_brief(self):
        brief = "# My Brief\nhttps://example.com\nContent here"
        result = self.renderer.render_output(brief, [], self.fetched_content, {})
        self.assertIn("# My Brief", result)

    def test_no_failed_sources_no_warning_block(self):
        brief = "# Brief\nhttps://example.com"
        result = self.renderer.render_output(brief, [], self.fetched_content, {})
        self.assertNotIn("Source Access Issues", result)

    def test_failed_sources_adds_warning(self):
        brief = "# Brief\nhttps://example.com"
        failed = [{'name': 'BadSrc', 'url': 'https://bad.com', 'error': 'Timeout'}]
        result = self.renderer.render_output(brief, failed, self.fetched_content, {})
        self.assertIn("Source Access Issues", result)
        self.assertIn("BadSrc", result)

    def test_coverage_report_always_appended(self):
        brief = "# Brief\nhttps://example.com"
        result = self.renderer.render_output(brief, [], self.fetched_content, {})
        self.assertIn("Source Coverage Report", result)

    def test_output_order_brief_then_coverage(self):
        brief = "# Brief\nhttps://example.com"
        result = self.renderer.render_output(brief, [], self.fetched_content, {})
        brief_pos = result.find("# Brief")
        coverage_pos = result.find("Source Coverage Report")
        self.assertLess(brief_pos, coverage_pos)


class TestSave(unittest.TestCase):
    def setUp(self):
        self.renderer = _make_renderer()

    def test_saves_content_to_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'brief.md')
            self.renderer.save("# Test Brief\nContent", path)
            with open(path) as f:
                content = f.read()
        self.assertEqual(content, "# Test Brief\nContent")

    def test_creates_parent_directory(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'subdir', 'nested', 'brief.md')
            self.renderer.save("content", path)
            self.assertTrue(os.path.exists(path))

    def test_overwrites_existing_file(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            path = os.path.join(tmpdir, 'brief.md')
            self.renderer.save("first content", path)
            self.renderer.save("second content", path)
            with open(path) as f:
                content = f.read()
        self.assertEqual(content, "second content")

    def test_empty_output_dir_uses_cwd(self):
        # When output_path has no directory component, it writes to current dir
        with tempfile.TemporaryDirectory() as tmpdir:
            orig_dir = os.getcwd()
            try:
                os.chdir(tmpdir)
                self.renderer.save("content", 'brief.md')
                self.assertTrue(os.path.exists(os.path.join(tmpdir, 'brief.md')))
            finally:
                os.chdir(orig_dir)
                if os.path.exists(os.path.join(tmpdir, 'brief.md')):
                    os.unlink(os.path.join(tmpdir, 'brief.md'))


class TestGenerateSourceCoverageReportFailedSources(unittest.TestCase):
    """Additional coverage report tests focusing on failed source status."""

    def setUp(self):
        self.renderer = _make_renderer({
            'twitter_accounts': [],
            'rss_sources': [
                {'name': 'GoodFeed', 'category': 'newsletter'},
                {'name': 'FailedFeed', 'category': 'newsletter'},
            ],
            'web_only_sources': [
                {'name': 'UnfetchedSrc', 'url': 'https://unfetched.com', 'category': 'podcast'},
            ],
        })
        self.fetched_content = {
            'rss': [{'title': 'a'}], 'arxiv': [], 'hackernews': [],
            'github_trending': [], 'web_pages': [],
        }

    def test_failed_source_shows_access_failed_status(self):
        failed = [{'name': 'FailedFeed', 'url': 'https://fail.com', 'error': 'Timeout'}]
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, {}, failed)
        self.assertIn('Access failed', report)
        self.assertIn('FailedFeed', report)

    def test_source_with_articles_shows_count(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, {'GoodFeed': 3}, [])
        self.assertIn('3 articles', report)

    def test_source_with_zero_articles_shows_no_articles(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, {}, [])
        self.assertIn('No articles found', report)

    def test_web_only_unfetched_shows_gemini_search(self):
        report = self.renderer.generate_source_coverage_report(
            self.fetched_content, {}, [])
        self.assertIn('via Gemini search', report)


# ── Additional Tests for Summarizer ──────────────────────────────────────

class TestBuildPromptCorrect(unittest.TestCase):
    """Tests using the actual build_prompt(prompt_template, prompt_vars) signature."""

    def setUp(self):
        self.summarizer = _make_summarizer()

    def test_substitutes_single_placeholder(self):
        result = self.summarizer.build_prompt("Hello {name}!", {'name': 'World'})
        self.assertEqual(result, "Hello World!")

    def test_unknown_placeholder_left_as_empty_string(self):
        # defaultdict(str) means unknown keys resolve to ''
        result = self.summarizer.build_prompt("Hello {unknown}!", {})
        self.assertEqual(result, "Hello !")

    def test_multiple_placeholders_all_substituted(self):
        template = "{rss}\n{arxiv}\n{hackernews}"
        vars_ = {'rss': 'RSS data', 'arxiv': 'arXiv data', 'hackernews': 'HN data'}
        result = self.summarizer.build_prompt(template, vars_)
        self.assertIn('RSS data', result)
        self.assertIn('arXiv data', result)
        self.assertIn('HN data', result)

    def test_empty_prompt_vars_leaves_template_blanks(self):
        result = self.summarizer.build_prompt("Content: {content}", {})
        self.assertEqual(result, "Content: ")

    def test_empty_template_returns_empty(self):
        result = self.summarizer.build_prompt("", {'key': 'value'})
        self.assertEqual(result, "")

    def test_template_without_placeholders_unchanged(self):
        template = "No placeholders here"
        result = self.summarizer.build_prompt(template, {'key': 'value'})
        self.assertEqual(result, template)


class TestSummarizeCorrect(unittest.TestCase):
    """Tests using the actual summarize(prompt_template, prompt_vars) signature."""

    def setUp(self):
        self.summarizer = _make_summarizer()

    @patch.object(sm.Summarizer, 'run_gemini', return_value='Summary output')
    def test_summarize_calls_run_gemini(self, mock_gemini):
        result = self.summarizer.summarize("Template {data}", {'data': 'some content'})
        mock_gemini.assert_called_once()
        self.assertEqual(result, 'Summary output')

    @patch.object(sm.Summarizer, 'run_gemini', return_value='Summary output')
    def test_summarize_builds_prompt_before_calling_gemini(self, mock_gemini):
        self.summarizer.summarize("Hello {name}", {'name': 'Test'})
        prompt_used = mock_gemini.call_args[0][0]
        self.assertEqual(prompt_used, "Hello Test")

    @patch.object(sm.Summarizer, 'run_gemini', return_value='Error: Gemini CLI failed after all retry attempts')
    def test_summarize_returns_gemini_output_on_failure(self, mock_gemini):
        result = self.summarizer.summarize("template", {})
        self.assertIn('Error', result)

    @patch.object(sm.Summarizer, 'run_gemini', return_value='ok')
    def test_summarize_logs_info(self, mock_gemini):
        self.summarizer.summarize("template {x}", {'x': 'y'})
        self.summarizer.logger.info.assert_called()


class TestRunGeminiEnvironment(unittest.TestCase):
    """Tests that run_gemini sets up the environment correctly."""

    def setUp(self):
        self.summarizer = _make_summarizer({'gemini_timeout': 60})

    @patch('subprocess.run')
    def test_path_env_contains_system_dirs(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ok')
        self.summarizer.run_gemini('prompt')
        call_kwargs = mock_run.call_args[1]
        env = call_kwargs.get('env', {})
        self.assertIn('/usr/bin', env.get('PATH', ''))

    @patch('subprocess.run')
    def test_uses_config_timeout(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='ok')
        self.summarizer.run_gemini('prompt')
        call_kwargs = mock_run.call_args[1]
        self.assertEqual(call_kwargs.get('timeout'), 60)

    @patch('subprocess.run')
    def test_captures_output(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='result')
        self.summarizer.run_gemini('prompt')
        call_kwargs = mock_run.call_args[1]
        self.assertTrue(call_kwargs.get('capture_output'))
        self.assertTrue(call_kwargs.get('text'))

    @patch('subprocess.run')
    def test_gemini_command_format(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0, stdout='result')
        self.summarizer.run_gemini('my prompt')
        call_args = mock_run.call_args[0][0]
        self.assertEqual(call_args[0], 'gemini')
        self.assertIn('-p', call_args)
        self.assertIn('my prompt', call_args)

    @patch('subprocess.run')
    @patch('time.sleep')
    def test_exponential_backoff_on_failure(self, mock_sleep, mock_run):
        mock_run.return_value = MagicMock(returncode=1, stderr='error')
        self.summarizer.run_gemini('prompt', retry=2)
        # With retry=2, we get 3 attempts and 2 sleeps (2^0=1s, 2^1=2s)
        sleep_calls = [c[0][0] for c in mock_sleep.call_args_list]
        self.assertEqual(len(sleep_calls), 2)
        self.assertEqual(sleep_calls[0], 1)
        self.assertEqual(sleep_calls[1], 2)


# ── Additional Tests for Fetcher ─────────────────────────────────────────

class TestFetchAll(unittest.TestCase):
    def setUp(self):
        self.fetcher = _make_fetcher({
            'rss_sources': [
                {'name': 'Feed', 'rss': 'https://feed.com/rss', 'category': 'newsletter'}
            ],
            'web_only_sources': [
                {'name': 'Blog', 'url': 'https://blog.com', 'category': 'newsletter'}
            ],
            'arxiv_categories': ['cs.LG'],
        })

    @patch.object(ft.ContentFetcher, 'fetch_web_sources_parallel', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_github_trending', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_hackernews_top', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_arxiv_papers', return_value=[])
    @patch.object(ft.ContentFetcher, 'check_and_fetch_rss', return_value=([], []))
    def test_fetch_all_calls_all_stages(self, mock_rss, mock_arxiv, mock_hn, mock_gh, mock_web):
        ok, failed = self.fetcher.fetch_all()
        mock_rss.assert_called_once()
        mock_arxiv.assert_called_once()
        mock_hn.assert_called_once()
        mock_gh.assert_called_once()
        mock_web.assert_called_once()

    @patch.object(ft.ContentFetcher, 'fetch_web_sources_parallel', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_github_trending', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_hackernews_top', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_arxiv_papers', return_value=[])
    @patch.object(ft.ContentFetcher, 'check_and_fetch_rss')
    def test_fetch_all_returns_ok_and_failed(self, mock_rss, *_):
        mock_rss.return_value = (
            [{'name': 'Feed', 'url': 'https://feed.com/rss', 'article_count': 2}],
            [{'name': 'Bad', 'url': 'https://bad.com/rss', 'error': 'Timeout'}],
        )
        ok, failed = self.fetcher.fetch_all()
        self.assertEqual(len(ok), 1)
        self.assertEqual(len(failed), 1)

    @patch.object(ft.ContentFetcher, 'fetch_web_sources_parallel', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_github_trending', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_hackernews_top', return_value=[])
    @patch.object(ft.ContentFetcher, 'fetch_arxiv_papers', return_value=[])
    @patch.object(ft.ContentFetcher, 'check_and_fetch_rss')
    def test_fetch_all_stores_failed_sources(self, mock_rss, *_):
        failed_list = [{'name': 'Bad', 'url': 'https://bad.com', 'error': 'Timeout'}]
        mock_rss.return_value = ([], failed_list)
        self.fetcher.fetch_all()
        self.assertEqual(self.fetcher.failed_sources, failed_list)


class TestHttpGetDefaultTimeout(unittest.TestCase):
    """Tests that _http_get uses the config fetch_timeout as default."""

    @patch.object(ft, '_HAS_HTTPX', False)
    @patch('urllib.request.urlopen')
    def test_uses_config_fetch_timeout(self, mock_urlopen):
        fetcher = _make_fetcher({'fetch_timeout': 25})
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'ok'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        fetcher._http_get('https://example.com')
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs.get('timeout'), 25)

    @patch.object(ft, '_HAS_HTTPX', False)
    @patch('urllib.request.urlopen')
    def test_explicit_timeout_overrides_config(self, mock_urlopen):
        fetcher = _make_fetcher({'fetch_timeout': 25})
        mock_resp = MagicMock()
        mock_resp.read.return_value = b'ok'
        mock_resp.__enter__ = lambda s: s
        mock_resp.__exit__ = MagicMock(return_value=False)
        mock_urlopen.return_value = mock_resp

        fetcher._http_get('https://example.com', timeout=5)
        _, kwargs = mock_urlopen.call_args
        self.assertEqual(kwargs.get('timeout'), 5)


class TestFetchGithubTrendingExtra(unittest.TestCase):
    """Additional edge case tests for fetch_github_trending."""

    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_description_truncated_to_200(self, mock_get):
        long_desc = 'x' * 300
        mock_get.return_value = json.dumps({
            'items': [{'full_name': 'u/r', 'html_url': 'https://github.com/u/r',
                       'description': long_desc, 'stargazers_count': 1, 'language': 'Python'}]
        })
        repos = self.fetcher.fetch_github_trending()
        self.assertLessEqual(len(repos[0]['description']), 200)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_stores_in_fetched_content(self, mock_get):
        mock_get.return_value = json.dumps({
            'items': [{'full_name': 'u/r', 'html_url': 'https://github.com/u/r',
                       'description': 'desc', 'stargazers_count': 10, 'language': 'Go'}]
        })
        self.fetcher.fetch_github_trending()
        self.assertEqual(len(self.fetcher.fetched_content['github_trending']), 1)

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_empty_items_list(self, mock_get):
        mock_get.return_value = json.dumps({'items': []})
        repos = self.fetcher.fetch_github_trending()
        self.assertEqual(repos, [])


class TestFetchArxivExtra(unittest.TestCase):
    """Additional edge case tests for fetch_arxiv_papers."""

    def setUp(self):
        self.fetcher = _make_fetcher({'arxiv_categories': ['cs.AI']})

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_summary_truncated_to_300(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        for p in papers:
            self.assertLessEqual(len(p['summary']), 300)

    @patch.object(ft.ContentFetcher, '_http_get', return_value=ARXIV_RESPONSE)
    def test_title_whitespace_stripped(self, mock_get):
        papers = self.fetcher.fetch_arxiv_papers()
        for p in papers:
            self.assertEqual(p['title'], p['title'].strip())

    @patch.object(ft.ContentFetcher, '_http_get')
    def test_entry_without_arxiv_id_skipped(self, mock_get):
        # Entry with no abs/ link → no arxiv_id → skipped
        xml = """\
<?xml version="1.0" encoding="UTF-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <entry>
    <title>No ID Paper</title>
    <summary>A paper without an abs link.</summary>
    <published>2026-03-01T00:00:00Z</published>
    <link href="https://arxiv.org/pdf/2603.01234" rel="related"/>
    <author><name>Author</name></author>
  </entry>
</feed>"""
        mock_get.return_value = xml
        papers = self.fetcher.fetch_arxiv_papers()
        self.assertEqual(papers, [])


# ── P1: Tests for _build_portfolio_context ────────────────────────────────

class TestBuildPortfolioContext(unittest.TestCase):
    def test_empty_when_no_holdings_no_watchlist(self):
        gen = _make_generator()
        result = gen._build_portfolio_context()
        self.assertEqual(result, '')

    def test_returns_content_with_holdings(self):
        gen = _make_generator({
            'portfolio_holdings': {
                'Tech': ['GOOG', 'NVDA'],
                'Semiconductors': ['TSM'],
            },
        })
        result = gen._build_portfolio_context()
        self.assertIn('PORTFOLIO CONTEXT', result)
        self.assertIn('Current Holdings', result)
        self.assertIn('**Tech:**', result)
        self.assertIn('GOOG, NVDA', result)
        self.assertIn('**Semiconductors:**', result)
        self.assertIn('TSM', result)

    def test_counts_total_positions_and_sectors(self):
        gen = _make_generator({
            'portfolio_holdings': {
                'Tech': ['GOOG', 'NVDA'],
                'China': ['BABA', 'FXI', 'KWEB'],
            },
        })
        result = gen._build_portfolio_context()
        self.assertIn('5 tickers', result)
        self.assertIn('2 sectors', result)

    def test_returns_content_with_watchlist_only(self):
        gen = _make_generator({
            'watchlist': {
                'tickers': ['AAPL', 'MSFT'],
                'themes': ['Quantum Computing', 'Robotics'],
            },
        })
        result = gen._build_portfolio_context()
        self.assertIn('Watchlist', result)
        self.assertIn('AAPL, MSFT', result)
        self.assertIn('Quantum Computing, Robotics', result)

    def test_watchlist_tickers_only(self):
        gen = _make_generator({
            'watchlist': {'tickers': ['AAPL']},
        })
        result = gen._build_portfolio_context()
        self.assertIn('Watchlist', result)
        self.assertIn('AAPL', result)
        self.assertNotIn('Themes', result)

    def test_watchlist_themes_only(self):
        gen = _make_generator({
            'watchlist': {'themes': ['AI Safety']},
        })
        result = gen._build_portfolio_context()
        self.assertIn('AI Safety', result)
        self.assertNotIn('Tickers', result)

    def test_both_holdings_and_watchlist(self):
        gen = _make_generator({
            'portfolio_holdings': {'Tech': ['GOOG']},
            'watchlist': {'tickers': ['AAPL'], 'themes': ['EV']},
        })
        result = gen._build_portfolio_context()
        self.assertIn('Current Holdings', result)
        self.assertIn('Watchlist', result)
        self.assertIn('GOOG', result)
        self.assertIn('AAPL', result)
        self.assertIn('EV', result)

    def test_empty_holdings_dict_returns_empty(self):
        gen = _make_generator({
            'portfolio_holdings': {},
            'watchlist': {},
        })
        result = gen._build_portfolio_context()
        self.assertEqual(result, '')


# ── P1: Expanded Tests for generate_brief Pipeline ───────────────────────

class TestGenerateBriefPipeline(unittest.TestCase):
    """Tests for the full generate_brief orchestration method."""

    def setUp(self):
        self.gen = _make_generator({
            'twitter_accounts': ['karpathy', 'AndrewYNg'],
            'rss_sources': [],
            'web_only_sources': [],
            'template': 'templates/ai-tech-brief.md',
            'prompt': 'prompts/ai-tech-brief.md',
            'brief_title': 'Test Brief',
        })

    def _mock_pipeline(self, brief_output='# Brief\nhttps://example.com\n## Top Stories\nContent'):
        """Set up standard mocks for the generate_brief pipeline."""
        patches = {
            'fetch_all': patch.object(
                ft.ContentFetcher, 'fetch_all',
                return_value=([], [])),
            'load_template': patch.object(
                rd.BriefRenderer, 'load_template',
                return_value='# $brief_title\n## Top Stories\n## Research Papers'),
            'fill_template': patch.object(
                rd.BriefRenderer, 'fill_template',
                return_value='# Test Brief\n## Top Stories\n## Research Papers'),
            'get_sections': patch.object(
                ft.ContentFetcher, 'get_formatted_sections',
                return_value={
                    'rss': 'RSS data', 'arxiv': 'arXiv data',
                    'hackernews': 'HN data', 'github': 'GH data', 'web': 'Web data'}),
            'summarize': patch.object(
                sm.Summarizer, 'summarize',
                return_value=brief_output),
            'validate': patch.object(
                rd.BriefRenderer, 'validate_brief',
                return_value=True),
            'render': patch.object(
                rd.BriefRenderer, 'render_output',
                return_value=brief_output + '\n---\nCoverage Report'),
        }
        mocks = {}
        for name, p in patches.items():
            mocks[name] = p.start()
        self.addCleanup(lambda: [p.stop() for p in patches.values()])
        return mocks

    def test_pipeline_calls_all_stages(self):
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        mocks['fetch_all'].assert_called_once()
        mocks['summarize'].assert_called_once()
        mocks['validate'].assert_called_once()
        mocks['render'].assert_called_once()

    def test_twitter_block_includes_accounts(self):
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertIn('@karpathy', prompt_vars['twitter_block'])
        self.assertIn('@AndrewYNg', prompt_vars['twitter_block'])

    def test_no_twitter_accounts_message(self):
        self.gen.config['twitter_accounts'] = []
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertEqual(prompt_vars['twitter_block'], 'No Twitter/X accounts configured.')

    def test_failed_sources_note_in_prompt(self):
        mocks = self._mock_pipeline()
        mocks['fetch_all'].return_value = (
            [],
            [{'name': 'BadFeed', 'url': 'https://bad.com', 'error': 'Timeout'}],
        )
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertIn('BadFeed', prompt_vars['failed_note'])
        self.assertIn('UNREACHABLE', prompt_vars['failed_note'])

    def test_no_failed_sources_empty_note(self):
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertEqual(prompt_vars['failed_note'], '')

    def test_unfetched_web_sources_block(self):
        self.gen.config['web_only_sources'] = [
            {'name': 'UnfetchedBlog', 'url': 'https://blog.com', 'category': 'newsletter'},
        ]
        mocks = self._mock_pipeline()
        # No web pages fetched, so UnfetchedBlog should appear in unavailable block
        self.gen.fetcher.fetched_content['web_pages'] = []
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertIn('UnfetchedBlog', prompt_vars['unavailable_web_block'])
        self.assertIn('Unavailable', prompt_vars['unavailable_web_block'])

    def test_fetched_web_sources_not_in_unavailable(self):
        self.gen.config['web_only_sources'] = [
            {'name': 'FetchedBlog', 'url': 'https://blog.com', 'category': 'newsletter'},
        ]
        mocks = self._mock_pipeline()
        self.gen.fetcher.fetched_content['web_pages'] = [{'source': 'FetchedBlog'}]
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertEqual(prompt_vars['unavailable_web_block'], '')

    def test_output_saved_when_path_provided(self):
        mocks = self._mock_pipeline()
        save_patcher = patch.object(rd.BriefRenderer, 'save')
        save_mock = save_patcher.start()
        self.addCleanup(save_patcher.stop)
        self.gen.generate_brief(output_path='/tmp/test-brief.md')
        save_mock.assert_called_once_with(
            mocks['render'].return_value, '/tmp/test-brief.md')

    def test_output_logged_when_no_path(self):
        self._mock_pipeline()
        self.gen.generate_brief(output_path=None)
        # Should have logged the output (not saved to file)
        self.gen.logger.info.assert_called()

    def test_validation_failure_continues_generation(self):
        mocks = self._mock_pipeline()
        mocks['validate'].return_value = False
        result = self.gen.generate_brief()
        # Should still return content despite validation warning
        self.assertIn('Coverage Report', result)
        self.gen.logger.warning.assert_called()

    def test_portfolio_vars_in_template(self):
        self.gen.config['portfolio_holdings'] = {
            'Tech': ['GOOG', 'NVDA'],
            'China': ['BABA'],
        }
        self.gen.config['watchlist'] = {
            'tickers': ['AAPL'],
            'themes': ['EV'],
        }
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        template_vars = mocks['fill_template'].call_args[0][1]
        self.assertEqual(template_vars['holdings_count'], '3')
        self.assertEqual(template_vars['sector_count'], '2')
        self.assertEqual(template_vars['watchlist_ticker_count'], '1')
        self.assertEqual(template_vars['watchlist_theme_count'], '1')

    def test_portfolio_context_passed_to_summarizer(self):
        self.gen.config['portfolio_holdings'] = {'Tech': ['GOOG']}
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertIn('PORTFOLIO CONTEXT', prompt_vars['portfolio_context'])
        self.assertIn('GOOG', prompt_vars['portfolio_context'])

    def test_no_portfolio_context_when_empty(self):
        mocks = self._mock_pipeline()
        self.gen.generate_brief()
        prompt_vars = mocks['summarize'].call_args[0][1]
        self.assertEqual(prompt_vars['portfolio_context'], '')

    def test_content_count_aliases(self):
        """Verify hackernews→hn, github_trending→github, web_pages→web aliases."""
        mocks = self._mock_pipeline()
        self.gen.fetcher.fetched_content = {
            'rss': [{'title': 'a'}],
            'arxiv': [{'title': 'b'}, {'title': 'c'}],
            'hackernews': [{'title': 'd'}] * 5,
            'github_trending': [{'name': 'e'}] * 3,
            'web_pages': [{'source': 'f'}],
        }
        self.gen.generate_brief()
        template_vars = mocks['fill_template'].call_args[0][1]
        self.assertEqual(template_vars['rss_count'], '1')
        self.assertEqual(template_vars['arxiv_count'], '2')
        self.assertEqual(template_vars['hn_count'], '5')
        self.assertEqual(template_vars['github_count'], '3')
        self.assertEqual(template_vars['web_count'], '1')


class TestFormatFailedSourcesWarningExtra(unittest.TestCase):
    """Extra tests for _format_failed_sources_warning."""

    def setUp(self):
        self.renderer = _make_renderer()

    def test_url_shown_in_parens(self):
        failed = [{'name': 'MySrc', 'url': 'https://my.com', 'error': 'Timeout'}]
        result = self.renderer._format_failed_sources_warning(failed)
        self.assertIn('(`https://my.com`)', result)

    def test_missing_url_no_parens(self):
        failed = [{'name': 'NoURL', 'error': 'No URL configured'}]
        result = self.renderer._format_failed_sources_warning(failed)
        self.assertNotIn('(``)', result)

    def test_multiple_failed_sources_all_listed(self):
        failed = [
            {'name': 'A', 'url': '', 'error': 'err1'},
            {'name': 'B', 'url': '', 'error': 'err2'},
            {'name': 'C', 'url': '', 'error': 'err3'},
        ]
        result = self.renderer._format_failed_sources_warning(failed)
        for name in ['A', 'B', 'C']:
            self.assertIn(name, result)


# ── P2: Tests for trafilatura code path in fetch_web_source ────────────────

class TestFetchWebSourceTrafilatura(unittest.TestCase):
    """Test the trafilatura-enabled code path in fetch_web_source."""

    def setUp(self):
        self.fetcher = _make_fetcher()

    @patch.object(ft, '_HAS_TRAFILATURA', True)
    @patch.object(ft.ContentFetcher, '_http_get')
    def test_trafilatura_extracts_content(self, mock_get):
        mock_get.return_value = '<html><body><p>Long enough content for extraction.</p></body></html>'
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = 'Extracted via trafilatura with enough chars to pass the length check!!'
        with patch.dict('sys.modules', {'trafilatura': mock_trafilatura}):
            # Re-bind the module-level reference
            original = getattr(ft, 'trafilatura', None)
            ft.trafilatura = mock_trafilatura
            try:
                result = self.fetcher.fetch_web_source('Test', 'https://test.com')
            finally:
                if original is not None:
                    ft.trafilatura = original
        self.assertIsNotNone(result)
        self.assertIn('Extracted via trafilatura', result['content'])

    @patch.object(ft, '_HAS_TRAFILATURA', True)
    @patch.object(ft.ContentFetcher, '_http_get')
    def test_trafilatura_returns_none_falls_to_empty(self, mock_get):
        mock_get.return_value = '<html><body>short</body></html>'
        mock_trafilatura = MagicMock()
        mock_trafilatura.extract.return_value = None
        with patch.dict('sys.modules', {'trafilatura': mock_trafilatura}):
            original = getattr(ft, 'trafilatura', None)
            ft.trafilatura = mock_trafilatura
            try:
                result = self.fetcher.fetch_web_source('Test', 'https://test.com')
            finally:
                if original is not None:
                    ft.trafilatura = original
        # None return + empty string < 50 chars → returns None
        self.assertIsNone(result)


# ── P2: Tests for generate_brief main() CLI ───────────────────────────────

class TestMainCLI(unittest.TestCase):
    """Tests for the main() CLI entry point."""

    @patch.object(gb.BriefGenerator, 'generate_brief', return_value='# Brief')
    @patch.object(gb.BriefGenerator, '__init__', return_value=None)
    def test_default_args(self, mock_init, mock_gen):
        mock_init.return_value = None
        gen_instance = gb.BriefGenerator.__new__(gb.BriefGenerator)
        gen_instance.config = gb.DEFAULT_CONFIG.copy()
        gen_instance.config['output_dir'] = '/tmp/briefs'
        gen_instance.logger = MagicMock()

        with patch('generate_brief.BriefGenerator', return_value=gen_instance):
            with patch('sys.argv', ['generate_brief.py']):
                gb.main()
        gen_instance.generate_brief.assert_called_once()

    @patch.object(gb.BriefGenerator, 'generate_brief', return_value='# Brief')
    def test_output_dir_override(self, mock_gen):
        with patch('sys.argv', ['generate_brief.py', '--output_dir', '/tmp/custom']):
            with patch.object(gb.BriefGenerator, '__init__', return_value=None):
                gen_instance = gb.BriefGenerator.__new__(gb.BriefGenerator)
                gen_instance.config = gb.DEFAULT_CONFIG.copy()
                gen_instance.config['output_dir'] = '/tmp/briefs'
                gen_instance.logger = MagicMock()
                gen_instance.generate_brief = MagicMock(return_value='# Brief')

                with patch('generate_brief.BriefGenerator', return_value=gen_instance):
                    gb.main()
                self.assertEqual(gen_instance.config['output_dir'], '/tmp/custom')

    @patch('builtins.print')
    def test_test_flag_prints_message(self, mock_print):
        with patch('sys.argv', ['generate_brief.py', '--test']):
            with patch.object(gb.BriefGenerator, '__init__', return_value=None):
                gen_instance = gb.BriefGenerator.__new__(gb.BriefGenerator)
                gen_instance.config = gb.DEFAULT_CONFIG.copy()
                gen_instance.config['output_dir'] = '/tmp/briefs'
                gen_instance.logger = MagicMock()
                gen_instance.generate_brief = MagicMock(return_value='# Brief')

                with patch('generate_brief.BriefGenerator', return_value=gen_instance):
                    gb.main()
                mock_print.assert_any_call("Running in test mode...")


if __name__ == '__main__':
    unittest.main()
