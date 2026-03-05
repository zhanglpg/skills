#!/usr/bin/env python3
"""
AI Tech Brief Generator

Generates daily AI technology news briefs from curated sources.
Uses direct APIs (arXiv, HN, GitHub) and RSS parsing for reliable data
collection, then passes verified content to Gemini CLI for summarization.

Usage:
    python3 generate_brief.py [--test] [--output FILE] [--config FILE]
"""

import sys
import os
import subprocess
import json
import hashlib
import logging
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

# Optional but preferred imports — fall back gracefully
try:
    import httpx
    _HAS_HTTPX = True
except ImportError:
    _HAS_HTTPX = False

try:
    import trafilatura
    _HAS_TRAFILATURA = True
except ImportError:
    _HAS_TRAFILATURA = False

# Operational defaults — sources live in config.json alongside this script.
DEFAULT_CONFIG = {
    'arxiv_categories': ['cs.LG', 'cs.AI', 'cs.SE'],
    'twitter_accounts': [],
    'rss_sources': [],
    'web_only_sources': [],
    'timezone': 'Asia/Shanghai',
    'timezone_offset': 8,
    'gemini_timeout': 180,
    'rss_check_timeout': 10,
    'fetch_timeout': 15,
    'max_articles': 30,
    'output_dir': '~/ai-tech-briefs',
    'log_file': '~/ai-tech-briefs/generate.log',
}

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(_SKILL_DIR, 'config.json')

_USER_AGENT = 'Mozilla/5.0 (compatible; AIBriefBot/2.0; +https://github.com/clawcoding)'


class BriefGenerator:
    """AI Tech Brief Generator — fetch-first, then summarize."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = DEFAULT_CONFIG.copy()
        self.logger = self._setup_logger()

        resolved = config_path or DEFAULT_CONFIG_PATH
        if resolved and os.path.exists(resolved):
            self._load_config(resolved)
        elif not config_path:
            self.logger.warning(f"No config.json found at {DEFAULT_CONFIG_PATH}. Using empty source lists.")

        self.config['output_dir'] = os.path.expanduser(self.config['output_dir'])
        self.config['log_file'] = os.path.expanduser(self.config['log_file'])
        os.makedirs(self.config['output_dir'], exist_ok=True)

        self.seen_hashes: set = set()
        self.source_coverage: Dict[str, int] = {}
        self.failed_sources: List[Dict[str, str]] = []
        self.fetched_content: Dict[str, List[Dict[str, str]]] = {
            'rss': [],
            'arxiv': [],
            'hackernews': [],
            'github_trending': [],
            'web_pages': [],
        }

    # ── Setup ──────────────────────────────────────────────────────────

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('ai-tech-brief')
        logger.setLevel(logging.INFO)
        logger.handlers = []

        try:
            log_file = os.path.expanduser('~/ai-tech-briefs/generate.log')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter('%(asctime)s - %(levelname)s - %(message)s'))
            logger.addHandler(fh)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

        return logger

    def _load_config(self, config_path: str):
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
            self.logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")

    # ── Utility ────────────────────────────────────────────────────────

    def _hash_article(self, title: str, url: str = "") -> str:
        content = f"{title}:{url}"
        return hashlib.md5(content.encode()).hexdigest()

    def _is_duplicate(self, title: str, url: str = "") -> bool:
        article_hash = self._hash_article(title, url)
        if article_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(article_hash)
        return False

    def get_date_str(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%Y-%m-%d')

    def get_date_display(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%B %d, %Y')

    def _get_sources_by_category(self, category: str) -> List[Dict[str, str]]:
        return [s for s in self.config.get('rss_sources', []) if s.get('category') == category]

    def _http_get(self, url: str, timeout: Optional[int] = None, accept: str = '*/*') -> Optional[str]:
        """Fetch a URL via httpx (preferred) or urllib (fallback). Returns body text or None."""
        timeout = timeout or self.config.get('fetch_timeout', 15)
        if _HAS_HTTPX:
            try:
                resp = httpx.get(url, timeout=timeout, follow_redirects=True,
                                 headers={'User-Agent': _USER_AGENT, 'Accept': accept})
                resp.raise_for_status()
                return resp.text
            except Exception as e:
                self.logger.debug(f"httpx GET failed for {url}: {e}")
                return None
        else:
            try:
                req = urllib.request.Request(url, headers={'User-Agent': _USER_AGENT, 'Accept': accept})
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    return resp.read().decode('utf-8', errors='replace')
            except Exception as e:
                self.logger.debug(f"urllib GET failed for {url}: {e}")
                return None

    # ── RSS Feed Parsing (replaces blogwatcher) ────────────────────────

    def check_and_fetch_rss(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch and parse each RSS feed directly.
        Uses GET (not HEAD) so we actually retrieve the feed content.
        Returns (ok_sources_with_articles, failed_sources).
        """
        ok_sources: List[Dict] = []
        failed_sources: List[Dict] = []
        timeout = self.config.get('rss_check_timeout', 10)
        all_articles: List[Dict[str, str]] = []

        for source in self.config.get('rss_sources', []):
            name = source.get('name', 'Unknown')
            rss_url = source.get('rss', '')

            if not rss_url:
                failed_sources.append({'name': name, 'url': '', 'error': 'No RSS URL configured'})
                continue

            body = self._http_get(rss_url, timeout=timeout,
                                  accept='application/rss+xml, application/atom+xml, application/xml, text/xml')
            if body is None:
                failed_sources.append({'name': name, 'url': rss_url, 'error': 'Failed to fetch (timeout or HTTP error)'})
                self.logger.warning(f"RSS failed: {name} — could not fetch {rss_url}")
                continue

            articles = self._parse_feed_xml(body, name)
            if articles:
                ok_sources.append({'name': name, 'url': rss_url, 'article_count': len(articles)})
                all_articles.extend(articles)
                self.source_coverage[name] = len(articles)
                self.logger.info(f"RSS OK: {name} — {len(articles)} articles")
            else:
                # Feed fetched but no parsable items — still counts as reachable
                ok_sources.append({'name': name, 'url': rss_url, 'article_count': 0})
                self.logger.info(f"RSS OK (empty): {name}")

        # Deduplicate and store
        for art in all_articles:
            if not self._is_duplicate(art['title'], art.get('url', '')):
                self.fetched_content['rss'].append(art)

        self.logger.info(f"RSS total: {len(ok_sources)} reachable, {len(failed_sources)} failed, "
                         f"{len(self.fetched_content['rss'])} unique articles")
        return ok_sources, failed_sources

    def _parse_feed_xml(self, xml_text: str, source_name: str) -> List[Dict[str, str]]:
        """Parse RSS 2.0 or Atom feed XML into article dicts."""
        articles: List[Dict[str, str]] = []
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError as e:
            self.logger.debug(f"XML parse error for {source_name}: {e}")
            return []

        # Strip namespace prefixes for easier matching
        ns = ''
        if root.tag.startswith('{'):
            ns = root.tag.split('}')[0] + '}'

        # RSS 2.0: <rss><channel><item>
        for item in root.iter('item'):
            title = self._xml_text(item, 'title')
            link = self._xml_text(item, 'link')
            pub_date = self._xml_text(item, 'pubDate')
            description = self._xml_text(item, 'description')
            if title:
                articles.append({
                    'title': title,
                    'url': link or '',
                    'published': pub_date or '',
                    'summary': (description or '')[:300],
                    'source': source_name,
                })

        # Atom: <feed><entry>
        if not articles:
            for entry in root.iter(f'{ns}entry'):
                title = self._xml_text(entry, f'{ns}title')
                # Atom links are in <link href="..."/>
                link_el = entry.find(f'{ns}link[@rel="alternate"]')
                if link_el is None:
                    link_el = entry.find(f'{ns}link')
                link = link_el.get('href', '') if link_el is not None else ''
                updated = self._xml_text(entry, f'{ns}updated') or self._xml_text(entry, f'{ns}published')
                summary = self._xml_text(entry, f'{ns}summary') or self._xml_text(entry, f'{ns}content')
                if title:
                    articles.append({
                        'title': title,
                        'url': link,
                        'published': updated or '',
                        'summary': (summary or '')[:300],
                        'source': source_name,
                    })

        return articles[:15]  # cap per source

    @staticmethod
    def _xml_text(parent: ET.Element, tag: str) -> Optional[str]:
        el = parent.find(tag)
        if el is not None and el.text:
            return el.text.strip()
        return None

    # ── arXiv API ──────────────────────────────────────────────────────

    def fetch_arxiv_papers(self) -> List[Dict[str, str]]:
        """Fetch recent papers from arXiv API — guaranteed real IDs."""
        categories = self.config.get('arxiv_categories', ['cs.LG', 'cs.AI', 'cs.SE'])
        cat_query = '+OR+'.join([f'cat:{c}' for c in categories])
        url = (f'https://export.arxiv.org/api/query?search_query={cat_query}'
               f'&sortBy=submittedDate&sortOrder=descending&max_results=15')

        self.logger.info(f"Fetching arXiv papers ({', '.join(categories)})...")
        body = self._http_get(url, timeout=20, accept='application/atom+xml')
        if body is None:
            self.logger.warning("arXiv API request failed")
            return []

        papers = []
        try:
            root = ET.fromstring(body)
        except ET.ParseError:
            self.logger.warning("arXiv API returned unparsable XML")
            return []

        ns = '{http://www.w3.org/2005/Atom}'
        for entry in root.findall(f'{ns}entry'):
            title = self._xml_text(entry, f'{ns}title')
            summary = self._xml_text(entry, f'{ns}summary')
            published = self._xml_text(entry, f'{ns}published')
            arxiv_id = ''
            link = ''
            for link_el in entry.findall(f'{ns}link'):
                href = link_el.get('href', '')
                if 'abs/' in href:
                    link = href
                    # Extract ID: https://arxiv.org/abs/2503.01234v1 -> 2503.01234
                    arxiv_id = href.split('abs/')[-1].rstrip('/').split('v')[0]
                    break

            authors = []
            for author_el in entry.findall(f'{ns}author'):
                name = self._xml_text(author_el, f'{ns}name')
                if name:
                    authors.append(name)

            if title and arxiv_id:
                papers.append({
                    'title': title.replace('\n', ' ').strip(),
                    'arxiv_id': arxiv_id,
                    'url': link,
                    'summary': (summary or '').replace('\n', ' ').strip()[:300],
                    'published': published or '',
                    'authors': ', '.join(authors[:3]) + ('...' if len(authors) > 3 else ''),
                    'source': 'arXiv',
                })

        self.fetched_content['arxiv'] = papers
        self.logger.info(f"arXiv: fetched {len(papers)} papers")
        return papers

    # ── Hacker News API ────────────────────────────────────────────────

    def fetch_hackernews_top(self, limit: int = 10) -> List[Dict[str, str]]:
        """Fetch top HN stories via the official Firebase API."""
        self.logger.info("Fetching Hacker News top stories...")
        body = self._http_get('https://hacker-news.firebaseio.com/v0/topstories.json', timeout=10)
        if body is None:
            self.logger.warning("HN API: failed to fetch top stories")
            return []

        try:
            story_ids = json.loads(body)[:limit]
        except (json.JSONDecodeError, TypeError):
            self.logger.warning("HN API: unparsable response")
            return []

        stories: List[Dict[str, str]] = []
        # Fetch each story in parallel
        def _fetch_story(sid: int) -> Optional[Dict[str, str]]:
            detail = self._http_get(f'https://hacker-news.firebaseio.com/v0/item/{sid}.json', timeout=8)
            if not detail:
                return None
            try:
                item = json.loads(detail)
            except (json.JSONDecodeError, TypeError):
                return None
            if item.get('type') != 'story' or not item.get('title'):
                return None
            return {
                'title': item['title'],
                'url': item.get('url', f"https://news.ycombinator.com/item?id={sid}"),
                'hn_url': f"https://news.ycombinator.com/item?id={sid}",
                'score': str(item.get('score', 0)),
                'comments': str(item.get('descendants', 0)),
                'source': 'Hacker News',
            }

        with ThreadPoolExecutor(max_workers=5) as pool:
            futures = {pool.submit(_fetch_story, sid): sid for sid in story_ids}
            for f in as_completed(futures):
                result = f.result()
                if result:
                    stories.append(result)

        # Sort by score descending
        stories.sort(key=lambda s: int(s.get('score', '0')), reverse=True)
        # Filter to AI-related stories
        ai_keywords = {'ai', 'llm', 'gpt', 'claude', 'gemini', 'model', 'neural', 'transformer',
                       'machine learning', 'deep learning', 'openai', 'anthropic', 'deepmind',
                       'meta ai', 'hugging', 'agent', 'reasoning', 'benchmark', 'training',
                       'inference', 'diffusion', 'rag', 'embedding', 'fine-tun', 'lora',
                       'chatbot', 'copilot', 'coding agent', 'autonomous', 'robot'}
        ai_stories = [s for s in stories
                      if any(kw in s['title'].lower() for kw in ai_keywords)]
        # If not enough AI stories found, include the top ones anyway
        if len(ai_stories) < 3:
            ai_stories = stories[:limit]

        self.fetched_content['hackernews'] = ai_stories[:limit]
        self.logger.info(f"Hacker News: fetched {len(ai_stories)} AI-related stories")
        return ai_stories[:limit]

    # ── GitHub Trending ────────────────────────────────────────────────

    def fetch_github_trending(self) -> List[Dict[str, str]]:
        """Fetch GitHub trending repos via the GitHub search API (repos created/pushed recently with many stars)."""
        self.logger.info("Fetching GitHub trending AI/ML repos...")

        # Use GitHub search API: recently pushed repos with AI/ML topics sorted by stars
        since = (datetime.utcnow() - timedelta(days=7)).strftime('%Y-%m-%d')
        url = (f'https://api.github.com/search/repositories'
               f'?q=topic:machine-learning+topic:ai+pushed:>{since}'
               f'&sort=stars&order=desc&per_page=10')

        body = self._http_get(url, timeout=15, accept='application/vnd.github+json')
        if body is None:
            self.logger.warning("GitHub trending API request failed")
            return []

        try:
            data = json.loads(body)
        except (json.JSONDecodeError, TypeError):
            self.logger.warning("GitHub trending: unparsable response")
            return []

        repos = []
        for item in data.get('items', [])[:10]:
            repos.append({
                'name': item.get('full_name', ''),
                'url': item.get('html_url', ''),
                'description': (item.get('description') or '')[:200],
                'stars': str(item.get('stargazers_count', 0)),
                'language': item.get('language') or 'N/A',
                'source': 'GitHub',
            })

        self.fetched_content['github_trending'] = repos
        self.logger.info(f"GitHub trending: fetched {len(repos)} repos")
        return repos

    # ── Web Page Content Extraction ────────────────────────────────────

    def fetch_web_source(self, name: str, url: str) -> Optional[Dict[str, str]]:
        """Fetch a web page and extract main content using trafilatura (or raw HTML fallback)."""
        body = self._http_get(url, timeout=self.config.get('fetch_timeout', 15))
        if body is None:
            return None

        extracted_text = ''
        if _HAS_TRAFILATURA:
            extracted_text = trafilatura.extract(body, include_links=True, include_tables=False) or ''
        else:
            # Basic fallback: strip HTML tags
            import re
            extracted_text = re.sub(r'<[^>]+>', ' ', body)
            extracted_text = re.sub(r'\s+', ' ', extracted_text)[:2000]

        if not extracted_text or len(extracted_text) < 50:
            return None

        return {
            'source': name,
            'url': url,
            'content': extracted_text[:2000],  # Cap content length
        }

    def fetch_web_sources_parallel(self) -> List[Dict[str, str]]:
        """Fetch content from web-only sources in parallel."""
        web_only = self.config.get('web_only_sources', [])
        # Only fetch blog/newsletter/lab sources — skip YouTube, podcasts, community
        fetchable_categories = {'newsletter', 'ai_lab', 'research_org'}
        to_fetch = [s for s in web_only if s.get('category') in fetchable_categories]

        self.logger.info(f"Fetching {len(to_fetch)} web-only source pages...")
        results: List[Dict[str, str]] = []

        with ThreadPoolExecutor(max_workers=4) as pool:
            futures = {pool.submit(self.fetch_web_source, s['name'], s['url']): s for s in to_fetch}
            for f in as_completed(futures):
                src = futures[f]
                result = f.result()
                if result:
                    results.append(result)
                    self.logger.debug(f"Web fetch OK: {src['name']}")
                else:
                    self.logger.debug(f"Web fetch empty: {src['name']}")

        self.fetched_content['web_pages'] = results
        self.logger.info(f"Web sources: {len(results)}/{len(to_fetch)} fetched successfully")
        return results

    # ── Gemini CLI (now used as summarizer only) ───────────────────────

    def run_gemini(self, prompt: str, retry: int = 2) -> str:
        """Run Gemini CLI with retry logic."""
        env = os.environ.copy()
        env['PATH'] = f"/usr/sbin:/usr/bin:/bin:/sbin:{env.get('PATH', '')}"

        for attempt in range(retry + 1):
            try:
                self.logger.debug(f"Gemini CLI attempt {attempt + 1}/{retry + 1}")
                result = subprocess.run(
                    ['gemini', '-p', prompt],
                    capture_output=True,
                    text=True,
                    timeout=self.config.get('gemini_timeout', 180),
                    env=env
                )
                if result.returncode == 0:
                    return result.stdout
                else:
                    self.logger.warning(f"Gemini CLI failed (attempt {attempt + 1}): {result.stderr[:200]}")
                    if attempt < retry:
                        import time
                        time.sleep(2 ** attempt)
            except subprocess.TimeoutExpired:
                self.logger.error(f"Gemini CLI timed out (attempt {attempt + 1})")
                if attempt < retry:
                    import time
                    time.sleep(2 ** attempt)
            except Exception as e:
                self.logger.error(f"Gemini CLI error (attempt {attempt + 1}): {e}")
                if attempt < retry:
                    import time
                    time.sleep(2 ** attempt)

        return "Error: Gemini CLI failed after all retry attempts"

    # ── Brief Generation (fetch-first architecture) ────────────────────

    def _format_rss_articles_for_prompt(self) -> str:
        articles = self.fetched_content.get('rss', [])
        if not articles:
            return "No RSS articles collected."
        lines = []
        for a in articles[:20]:
            line = f"- **{a['title']}** ({a['source']})"
            if a.get('url'):
                line += f" — {a['url']}"
            if a.get('published'):
                line += f" [{a['published']}]"
            if a.get('summary'):
                line += f"\n  > {a['summary'][:150]}"
            lines.append(line)
        return '\n'.join(lines)

    def _format_arxiv_for_prompt(self) -> str:
        papers = self.fetched_content.get('arxiv', [])
        if not papers:
            return "No arXiv papers collected."
        lines = []
        for p in papers:
            lines.append(
                f"- **{p['title']}** (arXiv:{p['arxiv_id']})\n"
                f"  Authors: {p['authors']}\n"
                f"  URL: {p['url']}\n"
                f"  > {p['summary'][:200]}"
            )
        return '\n'.join(lines)

    def _format_hackernews_for_prompt(self) -> str:
        stories = self.fetched_content.get('hackernews', [])
        if not stories:
            return "No Hacker News stories collected."
        lines = []
        for s in stories:
            lines.append(
                f"- **{s['title']}** (score: {s['score']}, {s['comments']} comments)\n"
                f"  URL: {s['url']}\n"
                f"  HN discussion: {s['hn_url']}"
            )
        return '\n'.join(lines)

    def _format_github_for_prompt(self) -> str:
        repos = self.fetched_content.get('github_trending', [])
        if not repos:
            return "No GitHub trending repos collected."
        lines = []
        for r in repos:
            lines.append(
                f"- **{r['name']}** ({r['language']}, {r['stars']} stars)\n"
                f"  {r['description']}\n"
                f"  URL: {r['url']}"
            )
        return '\n'.join(lines)

    def _format_web_content_for_prompt(self) -> str:
        pages = self.fetched_content.get('web_pages', [])
        if not pages:
            return "No web page content collected."
        lines = []
        for p in pages:
            lines.append(
                f"### {p['source']} ({p['url']})\n"
                f"{p['content'][:500]}\n"
            )
        return '\n'.join(lines)

    def generate_brief_content(self, failed_sources: Optional[List[Dict]] = None) -> str:
        """Generate brief by passing pre-fetched, verified content to Gemini for summarization."""
        failed_sources = failed_sources or []

        twitter_accounts = self.config.get('twitter_accounts', [])
        date_display = self.get_date_display()

        # Inform Gemini about sources that were unreachable
        failed_note = ""
        if failed_sources:
            failed_names = ', '.join(s['name'] for s in failed_sources)
            failed_note = (
                f"\n\nNOTE: The following RSS sources were UNREACHABLE: {failed_names}. "
                f"You may still find their content via web search."
            )

        # Web-only source names that we couldn't fetch content for
        web_only = self.config.get('web_only_sources', [])
        fetched_web_names = {p['source'] for p in self.fetched_content.get('web_pages', [])}
        unfetched_web = [s['name'] for s in web_only
                         if s.get('category') in ('newsletter', 'ai_lab', 'research_org')
                         and s['name'] not in fetched_web_names]

        # Derive source lists by category
        newsletters = [s['name'] for s in self._get_sources_by_category('newsletter')]
        ai_labs = [s['name'] for s in self._get_sources_by_category('ai_lab')]
        research_orgs = [s['name'] for s in self._get_sources_by_category('research_org')]
        web_newsletters = [s['name'] for s in web_only if s.get('category') == 'newsletter']
        web_labs = [s['name'] for s in web_only if s.get('category') == 'ai_lab']
        web_research = [s['name'] for s in web_only if s.get('category') == 'research_org']
        all_newsletters = newsletters + web_newsletters
        all_labs = ai_labs + web_labs
        all_research = research_orgs + web_research

        prompt = f"""You are a summarizer. Below is VERIFIED, PRE-FETCHED content from multiple sources.
Your job is to organize and summarize this content into a structured daily AI tech brief.

IMPORTANT RULES:
1. For RSS articles, arXiv papers, Hacker News stories, and GitHub repos: USE ONLY the data provided below. These are verified — use the exact URLs and titles given.
2. For Twitter/X accounts: search the web for recent tweets from the accounts listed below. Only include tweets you can actually find. If you find nothing, write "No updates found."
3. For sources listed under "SOURCES TO SEARCH VIA WEB": search for recent content and only include what you can verify.
4. Do NOT fabricate URLs, titles, or content. Every item must have a real, working URL.
5. It is better to have a shorter brief with all real content than a longer brief with fabricated entries.{failed_note}

---

## PRE-FETCHED CONTENT (verified — use these directly):

### RSS Feed Articles
{self._format_rss_articles_for_prompt()}

### arXiv Papers (verified IDs and URLs)
{self._format_arxiv_for_prompt()}

### Hacker News Top AI Stories (verified)
{self._format_hackernews_for_prompt()}

### GitHub Trending AI/ML Repos (verified)
{self._format_github_for_prompt()}

### Web Source Content (fetched and extracted)
{self._format_web_content_for_prompt()}

---

## SOURCES TO SEARCH VIA WEB (use Gemini web search for these):

### Twitter/X Thought Leaders ({len(twitter_accounts)} accounts):
{chr(10).join([f'- @{acc}' for acc in twitter_accounts])}
Search for tweets from past 24-48 hours. Only include tweets you actually find via web search.

### Unfetched Web Sources (search for recent content):
{chr(10).join([f'- {name}' for name in unfetched_web]) if unfetched_web else 'All web sources were fetched successfully.'}

---

## OUTPUT FORMAT:

```markdown
# Daily AI Tech Brief - {date_display}

## Top Stories (3-5 items)
Select the most significant items from ALL the data above. Include only stories with verified URLs.

### [Headline]
- **Summary:** 1-2 sentences explaining what happened
- **Why it matters:** Impact/significance
- **Source:** [Original Article Title](exact_url)

## Twitter/X Updates
For each account where you found updates:
- **@[handle]:** [Tweet summary] — [Link](exact_url)

If no updates found: "No updates found from @[handle] today."

## Newsletter & Blog Highlights
For each source with content (from RSS or web fetch):
- **[Source Name]:** [Article title] — [Link](exact_url) — 1-2 sentence summary

## AI Lab Updates
For each lab with updates:
- **[Lab Name]:** [Announcement] — [Link](exact_url) — 1-2 sentence summary

## Research Papers
| Paper | Key Finding | Link |
|-------|-------------|------|
| [Title] | 1-2 sentence summary | [arXiv:ID](url) |

## Hacker News AI Highlights
For top AI stories from HN:
- **[Title]** (score pts, N comments) — [Link](url) | [Discussion](hn_url)

## GitHub Trending
For notable repos:
- **[repo/name]** (language, stars) — [Link](url) — description

## Quick Links
- [Title](url) — 1 sentence description

---
*Sources: RSS ({len(self.fetched_content['rss'])} articles), arXiv API ({len(self.fetched_content['arxiv'])} papers), HN API ({len(self.fetched_content['hackernews'])} stories), GitHub API ({len(self.fetched_content['github_trending'])} repos), Web ({len(self.fetched_content['web_pages'])} pages), Twitter ({len(twitter_accounts)} accounts searched)*
```

ACCURACY REQUIREMENTS:
1. Every item MUST have a real URL from the data provided above or from your web search
2. For arXiv papers: use the exact arXiv IDs and URLs provided — do NOT modify them
3. For HN stories: use the exact URLs and scores provided
4. For GitHub repos: use the exact repo names and URLs provided
5. For RSS articles: use the exact titles and URLs provided
6. For Twitter: only include tweets you verified via web search
7. If a section has no content, keep the header and write "No verified updates for this section today"
"""

        self.logger.info("Sending pre-fetched content to Gemini for summarization...")
        return self.run_gemini(prompt)

    # ── Validation ─────────────────────────────────────────────────────

    def validate_brief(self, brief: str) -> bool:
        required_sections = ['#', '##', 'http']
        source_indicators = ['Twitter', 'Newsletter', 'Lab', 'Research', 'arXiv', 'Hacker News', 'GitHub']
        found_sources = sum(1 for indicator in source_indicators if indicator in brief)

        for section in required_sections:
            if section not in brief:
                self.logger.warning(f"Brief missing required element: {section}")
                return False

        if found_sources < 3:
            self.logger.warning(f"Brief may be missing source coverage (only found {found_sources}/7 indicators)")

        self.logger.info(f"Brief validation passed (found {found_sources}/7 source indicators)")
        return True

    # ── Coverage Report ────────────────────────────────────────────────

    def _format_failed_sources_warning(self, failed_sources: List[Dict]) -> str:
        if not failed_sources:
            return ""
        lines = [
            "\n## Source Access Issues\n",
            "> The following sources **could not be reached** during this brief generation.\n",
        ]
        for src in failed_sources:
            error = src.get('error', 'Unknown error')
            url = src.get('url', '')
            url_note = f" (`{url}`)" if url else ""
            lines.append(f"- **{src['name']}**{url_note} — {error}")
        return '\n'.join(lines)

    def generate_source_coverage_report(self) -> str:
        lines = ["\n## Source Coverage Report\n"]

        # Data source reliability summary
        lines.append("### Data Collection Method")
        lines.append(f"- **RSS feeds (xml.etree):** {len(self.fetched_content['rss'])} articles")
        lines.append(f"- **arXiv API:** {len(self.fetched_content['arxiv'])} papers (verified IDs)")
        lines.append(f"- **Hacker News API:** {len(self.fetched_content['hackernews'])} stories")
        lines.append(f"- **GitHub Search API:** {len(self.fetched_content['github_trending'])} repos")
        lines.append(f"- **Web page extraction:** {len(self.fetched_content['web_pages'])} pages")
        lines.append(f"- **Gemini web search:** Twitter accounts, unfetched web sources")
        lines.append("")

        # Twitter
        twitter_accounts = self.config.get('twitter_accounts', [])
        lines.append(f"### Twitter/X Accounts ({len(twitter_accounts)}) — via Gemini web search")
        for acc in twitter_accounts:
            lines.append(f"- @{acc}")

        # RSS sources
        category_labels = {
            'newsletter': 'Newsletters',
            'ai_lab': 'AI Labs',
            'research_org': 'Research Organizations',
        }
        for cat, label in category_labels.items():
            sources = self._get_sources_by_category(cat)
            if not sources:
                continue
            lines.append(f"\n### {label} ({len(sources)}) — via RSS")
            for src in sources:
                name = src['name']
                count = self.source_coverage.get(name, 0)
                failed = any(f['name'] == name for f in self.failed_sources)
                if failed:
                    status = "Access failed"
                elif count > 0:
                    status = f"{count} articles"
                else:
                    status = "No articles found"
                lines.append(f"- [{status}] {name}")

        # Web-only
        web_only = self.config.get('web_only_sources', [])
        fetched_names = {p['source'] for p in self.fetched_content.get('web_pages', [])}
        if web_only:
            lines.append(f"\n### Web-only Sources ({len(web_only)})")
            for src in web_only:
                method = "page fetched" if src['name'] in fetched_names else "via Gemini search"
                lines.append(f"- [{method}] {src['name']}")

        return '\n'.join(lines)

    # ── Main Pipeline ──────────────────────────────────────────────────

    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief using fetch-first architecture."""
        self.logger.info("=" * 60)
        self.logger.info("AI Tech Brief Generator v2.0 (fetch-first)")
        self.logger.info("=" * 60)

        # Step 1: Fetch RSS feeds directly (replaces blogwatcher)
        self.logger.info("\n[1/7] Fetching and parsing RSS feeds...")
        ok_sources, failed_sources = self.check_and_fetch_rss()
        self.failed_sources = failed_sources
        if failed_sources:
            failed_names = [s['name'] for s in failed_sources]
            self.logger.warning(f"Unreachable RSS sources: {', '.join(failed_names)}")

        # Steps 2-4: Fetch from APIs in parallel
        self.logger.info("\n[2/7] Fetching arXiv papers via API...")
        self.logger.info("[3/7] Fetching Hacker News top stories via API...")
        self.logger.info("[4/7] Fetching GitHub trending via API...")

        with ThreadPoolExecutor(max_workers=3) as pool:
            arxiv_future = pool.submit(self.fetch_arxiv_papers)
            hn_future = pool.submit(self.fetch_hackernews_top)
            gh_future = pool.submit(self.fetch_github_trending)
            # Wait for all to complete
            arxiv_future.result()
            hn_future.result()
            gh_future.result()

        # Step 5: Fetch web page content
        self.logger.info("\n[5/7] Fetching web source pages...")
        self.fetch_web_sources_parallel()

        # Step 6: Summarize with Gemini (now uses pre-fetched content)
        self.logger.info("\n[6/7] Summarizing pre-fetched content with Gemini CLI...")
        brief = self.generate_brief_content(failed_sources=failed_sources)

        # Append failed-source warning
        if failed_sources:
            brief += self._format_failed_sources_warning(failed_sources)

        # Validate
        is_valid = self.validate_brief(brief)
        if not is_valid:
            self.logger.warning("Brief validation had warnings, but continuing...")

        # Step 7: Coverage report
        self.logger.info("\n[7/7] Generating source coverage report...")
        coverage_report = self.generate_source_coverage_report()
        brief_with_coverage = brief + "\n\n" + coverage_report

        # Output
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            with open(output_path, 'w') as f:
                f.write(brief_with_coverage)
            self.logger.info(f"\nBrief saved to: {output_path}")
        else:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(brief_with_coverage)
            self.logger.info("=" * 60)

        self.logger.info("Brief generation complete!")
        return brief_with_coverage


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate AI Tech Brief')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--config', type=str, help='Config file path (JSON)')
    args = parser.parse_args()

    if args.test:
        print("Running in test mode...")

    generator = BriefGenerator(config_path=args.config)

    if args.output:
        output = args.output
    else:
        date_str = generator.get_date_str()
        output_dir = generator.config['output_dir']
        output = os.path.join(output_dir, f"{date_str}-ai-tech-brief.md")

    generator.generate_brief(output_path=output)


if __name__ == '__main__':
    main()
