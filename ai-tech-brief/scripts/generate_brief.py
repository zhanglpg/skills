#!/usr/bin/env python3
"""
AI Tech Brief Generator

Generates daily AI technology news briefs from curated sources.
Uses blogwatcher for RSS feeds, Gemini CLI for web search.

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
import urllib.error
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple

# Default configuration
# RSS URLs are resolved once and hard-coded here so they never need re-discovery.
DEFAULT_CONFIG = {
    'blogwatcher_path': '~/go/bin/blogwatcher',
    'arxiv_categories': ['cs.LG', 'cs.AI', 'cs.SE'],
    'twitter_accounts': [
        'karpathy', 'ilyasut', 'AndrewYNg', 'lilianweng',
        'DrJimFan', 'jeremyphoward', 'natolambert', 'philduanai',
        'hwchase17', 'rauchg', 'levelsio', 'swyx'
    ],
    # Sources with an RSS URL (working or blocked).
    # rss_status is for human reference; the script probes each URL at runtime.
    # Verified March 2, 2026 — see RSS_FEED_STATUS.md for details.
    'rss_sources': [
        # confirmed working
        {'name': 'Import AI',    'rss': 'https://jack-clark.net/feed/',              'category': 'newsletter',   'rss_status': 'working'},
        {'name': 'Anthropic',    'rss': 'https://www.anthropic.com/news?format=rss', 'category': 'ai_lab',       'rss_status': 'working'},
        {'name': 'Hugging Face', 'rss': 'https://huggingface.co/blog/feed.xml',      'category': 'research_org', 'rss_status': 'working'},
        # redirects — may work via blogwatcher
        {'name': 'TLDR AI',      'rss': 'https://tldr.tech/rss',                     'category': 'newsletter',   'rss_status': 'redirects'},
        {'name': 'Latent Space', 'rss': 'https://latentspace.blog/rss',              'category': 'newsletter',   'rss_status': 'redirects'},
        # blocked/erroring — kept so failures surface in the brief
        {"name": "Ben's Bites",  'rss': 'https://bensbites.beehiiv.com/rss',         'category': 'newsletter',   'rss_status': 'blocked_403'},
        {'name': 'The Neuron',   'rss': 'https://theneuron.beehiiv.com/rss',         'category': 'newsletter',   'rss_status': 'blocked_403'},
        {'name': 'Interconnects','rss': 'https://interconnects.ai/rss',              'category': 'newsletter',   'rss_status': 'error_405'},
        {'name': 'OpenAI',       'rss': 'https://openai.com/news/rss',               'category': 'ai_lab',       'rss_status': 'blocked_403'},
    ],
    # Sources confirmed to have no RSS feed — fetched exclusively via Gemini CLI web search
    'web_only_sources': [
        {'name': 'The Batch',       'url': 'https://www.deeplearning.ai/the-batch',  'category': 'newsletter'},
        {'name': 'The Rundown AI',  'url': 'https://therundown.ai',                  'category': 'newsletter'},
        {'name': 'Superhuman AI',   'url': 'https://superhuman.ai',                  'category': 'newsletter'},
        {'name': 'Google DeepMind', 'url': 'https://deepmind.google/discover/blog',  'category': 'ai_lab'},
        {'name': 'Meta AI',         'url': 'https://ai.meta.com/blog',               'category': 'ai_lab'},
        {'name': 'LMSYS',           'url': 'https://lmsys.org/blog',                 'category': 'research_org'},
    ],
    'timezone': 'Asia/Shanghai',
    'timezone_offset': 8,
    'gemini_timeout': 180,
    'blogwatcher_timeout': 60,
    'rss_check_timeout': 10,
    'max_articles': 30,
    'output_dir': '~/ai-tech-briefs',
    'log_file': '~/ai-tech-briefs/generate.log',
}

class BriefGenerator:
    """AI Tech Brief Generator with logging and error handling."""

    def __init__(self, config_path: Optional[str] = None):
        """Initialize generator with optional config file."""
        self.config = DEFAULT_CONFIG.copy()
        self.logger = self._setup_logger()

        if config_path and os.path.exists(config_path):
            self._load_config(config_path)

        # Expand paths
        self.config['blogwatcher_path'] = os.path.expanduser(self.config['blogwatcher_path'])
        self.config['output_dir'] = os.path.expanduser(self.config['output_dir'])
        self.config['log_file'] = os.path.expanduser(self.config['log_file'])

        # Ensure output directory exists
        os.makedirs(self.config['output_dir'], exist_ok=True)

        self.seen_hashes: set = set()          # For deduplication
        self.source_coverage: Dict[str, int] = {}  # blogwatcher article counts per source
        self.failed_sources: List[Dict[str, str]] = []  # RSS sources that failed to fetch

    def _setup_logger(self) -> logging.Logger:
        """Setup logging to file and console."""
        logger = logging.getLogger('ai-tech-brief')
        logger.setLevel(logging.INFO)

        # Clear existing handlers
        logger.handlers = []

        # File handler
        try:
            log_file = os.path.expanduser('~/ai-tech-briefs/generate.log')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(fh)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")

        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)

        return logger

    def _load_config(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
            self.logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")

    def _get_blogwatcher_path(self) -> str:
        """Find blogwatcher binary."""
        # Try configured path first
        if os.path.exists(self.config['blogwatcher_path']):
            return self.config['blogwatcher_path']

        # Try PATH
        result = subprocess.run(['which', 'blogwatcher'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()

        # Try common locations
        common_paths = [
            os.path.expanduser('~/go/bin/blogwatcher'),
            '/usr/local/bin/blogwatcher',
            '/opt/homebrew/bin/blogwatcher',
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path

        raise FileNotFoundError("blogwatcher not found. Install with: go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest")

    def _hash_article(self, title: str, url: str = "") -> str:
        """Create hash for deduplication."""
        content = f"{title}:{url}"
        return hashlib.md5(content.encode()).hexdigest()

    def _is_duplicate(self, title: str, url: str = "") -> bool:
        """Check if article is duplicate."""
        article_hash = self._hash_article(title, url)
        if article_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(article_hash)
        return False

    def get_date_str(self) -> str:
        """Get current date in configured timezone."""
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%Y-%m-%d')

    def get_date_display(self) -> str:
        """Get formatted date for display."""
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%B %d, %Y')

    def _get_sources_by_category(self, category: str) -> List[Dict[str, str]]:
        """Return rss_sources entries matching the given category."""
        return [s for s in self.config.get('rss_sources', []) if s.get('category') == category]

    def check_rss_sources(self) -> Tuple[List[Dict], List[Dict]]:
        """
        Probe each configured RSS URL to confirm it is reachable.
        Returns (ok_sources, failed_sources).
        Each failed entry: {name, url, error}.
        """
        ok_sources: List[Dict] = []
        failed_sources: List[Dict] = []
        timeout = self.config.get('rss_check_timeout', 10)

        for source in self.config.get('rss_sources', []):
            name = source.get('name', 'Unknown')
            rss_url = source.get('rss', '')

            if not rss_url:
                failed_sources.append({'name': name, 'url': '', 'error': 'No RSS URL configured'})
                continue

            try:
                req = urllib.request.Request(
                    rss_url,
                    headers={'User-Agent': 'Mozilla/5.0 (compatible; AIBriefBot/1.0)'}
                )
                with urllib.request.urlopen(req, timeout=timeout) as resp:
                    if resp.status == 200:
                        ok_sources.append({'name': name, 'url': rss_url})
                        self.logger.debug(f"RSS OK: {name}")
                    else:
                        failed_sources.append({'name': name, 'url': rss_url, 'error': f'HTTP {resp.status}'})
                        self.logger.warning(f"RSS failed: {name} — HTTP {resp.status}")
            except urllib.error.HTTPError as e:
                failed_sources.append({'name': name, 'url': rss_url, 'error': f'HTTP {e.code}: {e.reason}'})
                self.logger.warning(f"RSS failed: {name} — HTTP {e.code}")
            except urllib.error.URLError as e:
                failed_sources.append({'name': name, 'url': rss_url, 'error': f'Connection failed: {e.reason}'})
                self.logger.warning(f"RSS failed: {name} — {e.reason}")
            except Exception as e:
                failed_sources.append({'name': name, 'url': rss_url, 'error': str(e)})
                self.logger.warning(f"RSS failed: {name} — {e}")

        self.logger.info(f"RSS check: {len(ok_sources)} reachable, {len(failed_sources)} failed")
        return ok_sources, failed_sources

    def _format_failed_sources_warning(self, failed_sources: List[Dict]) -> str:
        """
        Return a markdown warning section listing sources that could not be fetched.
        Appended to the brief so the reader is immediately aware of coverage gaps.
        """
        if not failed_sources:
            return ""
        lines = [
            "\n## ⚠️ Source Access Issues\n",
            "> The following sources **could not be reached** during this brief generation. "
            "Content from these sources may be absent or incomplete. "
            "Check the feed URLs and network connectivity.\n",
        ]
        for src in failed_sources:
            error = src.get('error', 'Unknown error')
            url = src.get('url', '')
            url_note = f" (`{url}`)" if url else ""
            lines.append(f"- **{src['name']}**{url_note} — {error}")
        return '\n'.join(lines)

    def run_blogwatcher_scan(self) -> str:
        """Scan blogs for new articles."""
        try:
            blogwatcher = self._get_blogwatcher_path()
            result = subprocess.run(
                [blogwatcher, 'scan'],
                capture_output=True,
                text=True,
                timeout=self.config.get('blogwatcher_timeout', 60)
            )
            self.logger.debug(f"Blogwatcher scan output: {result.stdout}")
            return result.stdout
        except subprocess.TimeoutExpired:
            self.logger.error("Blogwatcher scan timed out")
            return "Error: Blogwatcher scan timed out"
        except FileNotFoundError as e:
            self.logger.error(f"Blogwatcher not found: {e}")
            return f"Error: {e}"
        except Exception as e:
            self.logger.error(f"Blogwatcher scan failed: {e}")
            return f"Error scanning blogs: {e}"

    def get_blogwatcher_articles(self, limit: int = 30) -> List[Dict[str, Any]]:
        """Get recent articles from blogwatcher with better parsing."""
        articles = []
        try:
            blogwatcher = self._get_blogwatcher_path()
            result = subprocess.run(
                [blogwatcher, 'articles', '-a'],
                capture_output=True,
                text=True,
                timeout=30
            )

            lines = result.stdout.strip().split('\n')
            current_article: Dict[str, Any] = {}

            for line in lines:
                line = line.strip()
                if not line or line.startswith('Unread articles') or line.startswith('Tracked blogs'):
                    continue

                # Parse article ID and title
                if line.startswith('[') and '] [new]' in line:
                    # Save previous article if exists
                    if current_article.get('title'):
                        if not self._is_duplicate(current_article['title'], current_article.get('url', '')):
                            articles.append(current_article)
                            # Track source coverage
                            blog_name = current_article.get('blog', '')
                            if blog_name:
                                self.source_coverage[blog_name] = self.source_coverage.get(blog_name, 0) + 1
                            if len(articles) >= limit:
                                break

                    # Start new article
                    parts = line.split('] ', 2)
                    if len(parts) >= 3:
                        current_article = {
                            'id': parts[0].replace('[', ''),
                            'title': parts[2].strip(),
                            'blog': '',
                            'url': '',
                            'published': ''
                        }

                elif line.startswith('Blog:'):
                    current_article['blog'] = line.replace('Blog:', '').strip()
                elif line.startswith('URL:'):
                    current_article['url'] = line.replace('URL:', '').strip()
                elif line.startswith('Published:'):
                    current_article['published'] = line.replace('Published:', '').strip()

            # Don't forget the last article
            if current_article.get('title') and len(articles) < limit:
                if not self._is_duplicate(current_article['title'], current_article.get('url', '')):
                    articles.append(current_article)
                    blog_name = current_article.get('blog', '')
                    if blog_name:
                        self.source_coverage[blog_name] = self.source_coverage.get(blog_name, 0) + 1

            self.logger.info(f"Found {len(articles)} unique articles from blogwatcher")
            self.logger.info(f"Source coverage: {self.source_coverage}")
            return articles

        except Exception as e:
            self.logger.error(f"Failed to get blogwatcher articles: {e}")
            return []

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
                        time.sleep(2 ** attempt)  # Exponential backoff

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

    def generate_brief_content(self, rss_articles: List[Dict[str, Any]],
                               failed_sources: Optional[List[Dict]] = None) -> str:
        """Generate brief using Gemini CLI with comprehensive source coverage."""
        failed_sources = failed_sources or []

        # Format RSS articles for prompt
        article_lines = []
        for article in rss_articles[:20]:  # Limit to 20 most recent
            title = article.get('title', 'Unknown')
            blog = article.get('blog', '')
            url = article.get('url', '')
            published = article.get('published', '')

            line = f"- {title}"
            if blog:
                line += f" ({blog})"
            if url:
                line += f" - {url}"
            if published:
                line += f" [{published}]"
            article_lines.append(line)

        article_text = '\n'.join(article_lines) if article_lines else "No recent RSS articles found."

        # Derive source lists by category from the unified rss_sources config
        newsletters = [s['name'] for s in self._get_sources_by_category('newsletter')]
        web_only = [s['name'] for s in self.config.get('web_only_sources', [])]
        ai_labs = [s['name'] for s in self._get_sources_by_category('ai_lab')]
        research_orgs = [s['name'] for s in self._get_sources_by_category('research_org')]
        all_newsletters = newsletters + web_only

        twitter_accounts = self.config.get('twitter_accounts', [])
        arxiv_cats = self.config.get('arxiv_categories', [])
        date_display = self.get_date_display()

        # Inform Gemini about sources that were unreachable so it can label them
        failed_note = ""
        if failed_sources:
            failed_names = ', '.join(s['name'] for s in failed_sources)
            failed_note = (
                f"\n\n⚠️ IMPORTANT: The following RSS sources were UNREACHABLE this run "
                f"and may have no content available: {failed_names}. "
                f"For each of these, write 'Access failed — [error]' instead of their content."
            )

        prompt = f"""Generate a comprehensive daily AI tech brief for {date_display}.

MANDATORY: You MUST include content from ALL of the following source categories. If you cannot find recent content from a specific source, explicitly state "No updates from [source] today."{failed_note}

## REQUIRED SOURCE COVERAGE:

### 1. Twitter/X Thought Leaders ({len(twitter_accounts)} accounts) - MUST CHECK EACH:
{chr(10).join([f'- @{acc}' for acc in twitter_accounts])}
Search for tweets from past 24-48 hours. Include notable announcements, insights, or thread summaries.

### 2. Newsletters ({len(all_newsletters)} publications) - MUST CHECK EACH:
{chr(10).join([f'- {nl}' for nl in all_newsletters])}
Include key stories and insights.

### 3. AI Lab Blogs ({len(ai_labs)} labs) - MUST CHECK EACH:
{chr(10).join([f'- {lab}' for lab in ai_labs])}
Include official announcements and research updates.

### 4. Research Organizations ({len(research_orgs)} orgs) - MUST CHECK EACH:
{chr(10).join([f'- {org}' for org in research_orgs])}
Include benchmarks, model releases, and research updates.

### 5. arXiv Papers (categories: {', '.join(arxiv_cats)}) - MUST CHECK:
List latest papers from past 48 hours with key findings.

## RSS FEED DATA (already collected):
{article_text}

## OUTPUT FORMAT:

```markdown
# 🤖 Daily AI Tech Brief - {date_display}

## 📊 Top Stories (3-5 items)
Must include stories from multiple source categories above.

### [Headline]
- **Summary:** 1-2 sentences
- **Why it matters:** Impact/significance
- **Source:** [Link](url)

## 🐦 Twitter/X Updates
Explicitly list updates from thought leaders. If no updates, say "No significant updates today."

## 📰 Newsletter Highlights
Summarize key stories from each newsletter checked.

## 🏢 AI Lab Updates
Updates from {', '.join(ai_labs)}.

## 🔬 Research Organization Updates
Updates from {', '.join(research_orgs)}.

## 📄 New Research Papers
| Paper | Key Finding | Link |
|-------|-------------|------|
| [Title] | Finding | arXiv:XXXX |

## 🔗 Quick Links
Other notable links discovered.

---
*Sources checked: Twitter ({len(twitter_accounts)} accounts), Newsletters ({len(all_newsletters)}), AI Labs ({len(ai_labs)}), Research Orgs ({len(research_orgs)}), arXiv*
```

IMPORTANT:
1. You MUST attempt to find content from ALL listed sources
2. Use web search to check each source individually
3. If a source has no updates, explicitly state that
4. Do not skip any source category
5. Make the brief comprehensive and technical
"""

        self.logger.info("Generating comprehensive brief with full source coverage...")
        return self.run_gemini(prompt)

    def validate_brief(self, brief: str) -> bool:
        """Validate that brief has required sections."""
        required_sections = [
            '#',    # Has a title
            '##',   # Has sections
            'http',  # Has links
        ]

        # Check for source coverage mention
        source_indicators = ['Twitter', 'Newsletter', 'Lab', 'Research', 'arXiv']
        found_sources = sum(1 for indicator in source_indicators if indicator in brief)

        for section in required_sections:
            if section not in brief:
                self.logger.warning(f"Brief missing required element: {section}")
                return False

        if found_sources < 3:
            self.logger.warning(f"Brief may be missing source coverage (only found {found_sources}/5 indicators)")

        self.logger.info(f"Brief validation passed (found {found_sources}/5 source indicators)")
        return True

    def generate_source_coverage_report(self) -> str:
        """Generate a report of which sources were covered."""
        lines = ["\n## 📊 Source Coverage Report\n"]

        # Twitter accounts
        twitter_accounts = self.config.get('twitter_accounts', [])
        lines.append(f"### Twitter/X Accounts ({len(twitter_accounts)})")
        for acc in twitter_accounts:
            status = "✅" if acc in str(self.source_coverage) else "❓"
            lines.append(f"- {status} @{acc}")

        # RSS sources grouped by category
        category_labels = {
            'newsletter':    'Newsletters',
            'ai_lab':        'AI Labs',
            'research_org':  'Research Organizations',
        }
        for cat, label in category_labels.items():
            sources = self._get_sources_by_category(cat)
            if not sources:
                continue
            lines.append(f"\n### {label} ({len(sources)})")
            for src in sources:
                name = src['name']
                count = self.source_coverage.get(name, 0)
                failed = any(f['name'] == name for f in self.failed_sources)
                if failed:
                    status = "❌ Access failed"
                elif count > 0:
                    status = f"✅ ({count} articles)"
                else:
                    status = "❓ No articles found"
                lines.append(f"- {status} {name}")

        # Web-only sources (no RSS)
        web_only = self.config.get('web_only_sources', [])
        if web_only:
            lines.append(f"\n### Web-only Sources ({len(web_only)}) — fetched via Gemini")
            for src in web_only:
                lines.append(f"- 🌐 {src['name']}")

        return '\n'.join(lines)

    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief."""
        self.logger.info("=" * 60)
        self.logger.info("AI Tech Brief Generator")
        self.logger.info("=" * 60)

        # Check RSS source accessibility
        self.logger.info("\n[1/6] Checking RSS source accessibility...")
        ok_sources, failed_sources = self.check_rss_sources()
        self.failed_sources = failed_sources
        if failed_sources:
            failed_names = [s['name'] for s in failed_sources]
            self.logger.warning(f"Unreachable sources: {', '.join(failed_names)}")

        # Scan blogs
        self.logger.info("\n[2/6] Scanning RSS feeds with blogwatcher...")
        scan_result = self.run_blogwatcher_scan()
        self.logger.info(scan_result)

        # Get articles
        self.logger.info("\n[3/6] Fetching recent articles...")
        rss_articles = self.get_blogwatcher_articles(limit=self.config.get('max_articles', 30))
        self.logger.info(f"Found {len(rss_articles)} unique articles")

        # Generate content with Gemini
        self.logger.info("\n[4/6] Generating comprehensive brief with Gemini CLI...")
        brief = self.generate_brief_content(rss_articles, failed_sources=failed_sources)

        # Append failed-source warning to brief so readers notice immediately
        if failed_sources:
            brief += self._format_failed_sources_warning(failed_sources)

        # Validate
        self.logger.info("\n[5/6] Validating brief...")
        is_valid = self.validate_brief(brief)
        if not is_valid:
            self.logger.warning("Brief validation had warnings, but continuing...")

        # Generate coverage report
        self.logger.info("\n[6/6] Generating source coverage report...")
        coverage_report = self.generate_source_coverage_report()

        # Append coverage report to brief
        brief_with_coverage = brief + "\n\n" + coverage_report

        # Output
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)

            with open(output_path, 'w') as f:
                f.write(brief_with_coverage)
            self.logger.info(f"\n✅ Brief saved to: {output_path}")
        else:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(brief_with_coverage)
            self.logger.info("=" * 60)

        self.logger.info("Brief generation complete!")
        return brief_with_coverage


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description='Generate AI Tech Brief')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--config', type=str, help='Config file path (JSON)')

    args = parser.parse_args()

    if args.test:
        print("Running in test mode...")

    # Initialize generator
    generator = BriefGenerator(config_path=args.config)

    # Determine output path
    if args.output:
        output = args.output
    else:
        date_str = generator.get_date_str()
        output_dir = generator.config['output_dir']
        output = os.path.join(output_dir, f"{date_str}-ai-tech-brief.md")

    # Generate brief
    generator.generate_brief(output_path=output)


if __name__ == '__main__':
    main()
