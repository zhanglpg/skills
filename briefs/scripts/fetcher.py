"""Content fetching module for the Brief Generator.

Handles all data collection: RSS feeds, arXiv API, Hacker News API,
GitHub trending, and web page extraction. Formats fetched content
into prompt-ready text for the summarizer.
"""

import hashlib
import json
import logging
import os
import urllib.request
import xml.etree.ElementTree as ET
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

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

_USER_AGENT = 'Mozilla/5.0 (compatible; AIBriefBot/2.0; +https://github.com/clawcoding)'


class ContentFetcher:
    """Fetches and formats content from multiple sources."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger
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
        self.openbb_data: Optional[dict] = None

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

    # ── RSS Feed Parsing ──────────────────────────────────────────────

    def check_and_fetch_rss(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Fetch and parse each RSS feed directly.
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

    # ── arXiv API ─────────────────────────────────────────────────────

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

    # ── Hacker News API ───────────────────────────────────────────────

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
        if len(ai_stories) < 3:
            ai_stories = stories[:limit]

        self.fetched_content['hackernews'] = ai_stories[:limit]
        self.logger.info(f"Hacker News: fetched {len(ai_stories)} AI-related stories")
        return ai_stories[:limit]

    # ── GitHub Trending ───────────────────────────────────────────────

    def fetch_github_trending(self) -> List[Dict[str, str]]:
        """Fetch GitHub trending repos via the GitHub search API."""
        self.logger.info("Fetching GitHub trending AI/ML repos...")

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

    # ── Web Page Content Extraction ───────────────────────────────────

    def fetch_web_source(self, name: str, url: str) -> Optional[Dict[str, str]]:
        """Fetch a web page and extract main content."""
        body = self._http_get(url, timeout=self.config.get('fetch_timeout', 15))
        if body is None:
            return None

        extracted_text = ''
        if _HAS_TRAFILATURA:
            extracted_text = trafilatura.extract(body, include_links=True, include_tables=False) or ''
        else:
            import re
            extracted_text = re.sub(r'<[^>]+>', ' ', body)
            extracted_text = re.sub(r'\s+', ' ', extracted_text)[:2000]

        if not extracted_text or len(extracted_text) < 50:
            return None

        return {
            'source': name,
            'url': url,
            'content': extracted_text[:2000],
        }

    def fetch_web_sources_parallel(self) -> List[Dict[str, str]]:
        """Fetch content from web-only sources in parallel."""
        web_only = self.config.get('web_only_sources', [])
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

    # ── Content Formatting for Prompts ────────────────────────────────

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

    # ── OpenBB Data Loading ──────────────────────────────────────────

    def fetch_openbb_data(self) -> Optional[dict]:
        """Load pre-exported OpenBB quantitative data from JSON.

        Checks staleness: if the data is more than 2 days old, logs an error
        and marks it as stale so the brief can include a warning.
        """
        openbb_path = self.config.get('openbb_data_path', '')
        if not openbb_path:
            return None

        openbb_path = os.path.expanduser(openbb_path)
        if not os.path.exists(openbb_path):
            self.logger.warning(f"OpenBB data file not found: {openbb_path}")
            return None

        try:
            with open(openbb_path, 'r') as f:
                self.openbb_data = json.load(f)

            generated_at = self.openbb_data.get('generated_at', '')
            self.logger.info(f"OpenBB data loaded from {openbb_path} "
                             f"(generated {generated_at})")

            # Staleness check: warn if data is more than 2 days old
            if generated_at:
                try:
                    gen_time = datetime.fromisoformat(generated_at)
                    age = datetime.now() - gen_time
                    if age > timedelta(days=2):
                        stale_msg = (f"OpenBB data is STALE ({age.days} days old, "
                                     f"generated {generated_at}). "
                                     f"Run brief_exporter.py to refresh.")
                        self.logger.error(stale_msg)
                        self.openbb_data['_stale'] = True
                        self.openbb_data['_stale_message'] = stale_msg
                except (ValueError, TypeError) as e:
                    self.logger.warning(f"Could not parse OpenBB generated_at timestamp: {e}")

            return self.openbb_data
        except Exception as e:
            self.logger.warning(f"Failed to load OpenBB data: {e}")
            return None

    def _format_openbb_for_prompt(self) -> str:
        """Format OpenBB data as a prompt-ready text block."""
        data = self.openbb_data
        if not data:
            return ""

        lines = []

        # Staleness warning
        if data.get('_stale'):
            lines.append(f"**WARNING: {data['_stale_message']}**")
            lines.append("The quantitative data below may be outdated. Note this in the brief.")
            lines.append("")

        # Portfolio snapshot
        snapshot = data.get('portfolio_snapshot', [])
        if snapshot:
            lines.append("### Portfolio Price Snapshot (latest close)")
            lines.append("| Symbol | Sector | Price | Change % | Volume |")
            lines.append("|--------|--------|-------|----------|--------|")
            for s in sorted(snapshot, key=lambda x: x.get('symbol', '')):
                chg = f"{s['change_pct']:+.2f}%" if s.get('change_pct') is not None else "N/A"
                vol = f"{s.get('volume', 0):,.0f}" if s.get('volume') else "N/A"
                lines.append(f"| {s['symbol']} | {s.get('sector', '')} | ${s.get('price', 0):.2f} | {chg} | {vol} |")
            lines.append("")

        # Technical signals
        technicals = data.get('technical_signals', {})
        if technicals:
            bullish = []
            bearish = []
            for sym, t in technicals.items():
                if t.get('error'):
                    continue
                label = f"{sym} (SMA-20: {t.get('price_vs_sma20', '?')}, return: {t.get('total_return_pct', 0):.1f}%, drawdown: {t.get('max_drawdown_pct', 0):.1f}%)"
                if t.get('price_vs_sma20') == 'above':
                    bullish.append(label)
                else:
                    bearish.append(label)
            lines.append("### Technical Signals")
            if bullish:
                lines.append(f"**Bullish (above SMA-20):** {', '.join(sorted(bullish))}")
            if bearish:
                lines.append(f"**Bearish (below SMA-20):** {', '.join(sorted(bearish))}")
            lines.append("")

        # Valuation check
        valuations = data.get('valuation_check', [])
        if valuations:
            lines.append("### Valuation Screen")
            lines.append("| Symbol | PE | PB | FCF Yield | Earnings Yield |")
            lines.append("|--------|----|----|-----------|----------------|")
            for v in valuations[:15]:
                pe = f"{v['pe_ratio']:.1f}" if v.get('pe_ratio') else "N/A"
                pb = f"{v['pb_ratio']:.1f}" if v.get('pb_ratio') else "N/A"
                fcf = f"{v['fcf_yield']:.1f}%" if v.get('fcf_yield') else "N/A"
                ey = f"{v['earnings_yield']:.1f}%" if v.get('earnings_yield') else "N/A"
                lines.append(f"| {v['symbol']} | {pe} | {pb} | {fcf} | {ey} |")
            lines.append("")

        # Risk dashboard
        risk = data.get('risk_dashboard', {})
        if risk:
            lines.append("### Risk Dashboard")
            portfolio = risk.get('portfolio', {})
            if portfolio:
                corr = portfolio.get('avg_pairwise_correlation')
                if corr is not None:
                    lines.append(f"- **Avg Pairwise Correlation:** {corr:.2f}")
            most_vol = risk.get('most_volatile_3', [])
            if most_vol:
                lines.append(f"- **Most Volatile:** {', '.join(most_vol)}")
            least_vol = risk.get('least_volatile_3', [])
            if least_vol:
                lines.append(f"- **Least Volatile:** {', '.join(least_vol)}")
            lines.append("")

        # Macro snapshot
        macro = data.get('macro_snapshot', {})
        if macro:
            lines.append("### Macro Snapshot")
            yc = macro.get('yield_curve_status')
            if yc:
                lines.append(f"- **Yield Curve:** {yc}")
            vix = macro.get('vix_regime')
            if vix:
                lines.append(f"- **VIX Regime:** {vix}")
            rate_dir = macro.get('rate_direction')
            if rate_dir:
                lines.append(f"- **Rate Direction:** {rate_dir}")
            indicators = macro.get('indicators', [])
            for ind in indicators:
                val = ind.get('latest_value')
                if val is not None:
                    chg_1m = ind.get('change_1m')
                    chg_str = f" (1m change: {chg_1m:+.2f})" if chg_1m is not None else ""
                    lines.append(f"- **{ind['series_id']}:** {val:.2f}{chg_str}")
            lines.append("")

        # SEC activity
        sec = data.get('sec_activity', {})
        recent_8k = sec.get('recent_8k_activity', [])
        if recent_8k:
            lines.append("### Recent SEC 8-K Filings")
            for filing in recent_8k[:5]:
                desc = filing.get('description', 'N/A')
                lines.append(f"- **{filing['symbol']}** ({filing.get('filing_date', '?')}): {desc}")
            lines.append("")

        # Alerts
        alerts = data.get('alerts', [])
        if alerts:
            lines.append("### Quantitative Alerts")
            for a in alerts:
                sev = a.get('severity', 'info').upper()
                lines.append(f"- [{sev}] {a.get('message', '')}")
            lines.append("")

        return '\n'.join(lines)

    def get_formatted_sections(self) -> Dict[str, str]:
        """Return all formatted content sections as a dict."""
        sections = {
            'rss': self._format_rss_articles_for_prompt(),
            'arxiv': self._format_arxiv_for_prompt(),
            'hackernews': self._format_hackernews_for_prompt(),
            'github': self._format_github_for_prompt(),
            'web': self._format_web_content_for_prompt(),
        }
        openbb_text = self._format_openbb_for_prompt()
        if openbb_text:
            sections['openbb'] = openbb_text
        return sections

    # ── Full Pipeline ─────────────────────────────────────────────────

    def fetch_all(self) -> Tuple[List[Dict], List[Dict]]:
        """Run the complete fetch pipeline. Returns (ok_sources, failed_sources)."""
        # Step 1: RSS feeds
        self.logger.info("\n[1/6] Fetching and parsing RSS feeds...")
        ok_sources, failed_sources = self.check_and_fetch_rss()
        self.failed_sources = failed_sources
        if failed_sources:
            failed_names = [s['name'] for s in failed_sources]
            self.logger.warning(f"Unreachable RSS sources: {', '.join(failed_names)}")

        # Steps 2-4: APIs in parallel
        self.logger.info("\n[2/6] Fetching arXiv papers via API...")
        self.logger.info("[3/6] Fetching Hacker News top stories via API...")
        self.logger.info("[4/6] Fetching GitHub trending via API...")

        with ThreadPoolExecutor(max_workers=3) as pool:
            arxiv_future = pool.submit(self.fetch_arxiv_papers)
            hn_future = pool.submit(self.fetch_hackernews_top)
            gh_future = pool.submit(self.fetch_github_trending)
            arxiv_future.result()
            hn_future.result()
            gh_future.result()

        # Step 5: Web pages
        self.logger.info("\n[5/6] Fetching web source pages...")
        self.fetch_web_sources_parallel()

        # Step 6: OpenBB quantitative data (if configured)
        if self.config.get('openbb_data_path'):
            self.logger.info("\n[6/6] Loading OpenBB quantitative data...")
            self.fetch_openbb_data()

        return ok_sources, failed_sources
