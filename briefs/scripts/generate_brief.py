#!/usr/bin/env python3
"""
Brief Generator

Generates daily briefs from curated sources.
Uses direct APIs and RSS parsing for reliable data collection, then passes
verified content to Gemini CLI for summarization and template rendering.

Usage:
    python3 generate_brief.py [--test] [--output_dir DIR] [--config FILE]
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

# Allow importing shared utilities from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging_utils import get_agent_data_dir, setup_logger as _shared_setup_logger
from fetcher import ContentFetcher
from summarizer import Summarizer
from renderer import BriefRenderer

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(_SKILL_DIR, 'config.ai-tech.json')


class BriefGenerator:
    """Brief Generator — orchestrates fetch → summarize → render."""

    def __init__(self, config_path: Optional[str] = None):
        # Load config BEFORE setting up logger so the config's log_file path is used
        resolved = config_path or DEFAULT_CONFIG_PATH
        if not resolved or not os.path.exists(resolved):
            raise FileNotFoundError(
                f"Config file not found: {resolved}. "
                "A valid JSON config file is required."
            )
        with open(resolved, 'r') as f:
            self.config = json.load(f)

        get_agent_data_dir()  # ensure AGENT_DATA_DIR is set for expandvars
        self.config['output_dir'] = os.path.expanduser(os.path.expandvars(self.config['output_dir']))
        if 'log_file' in self.config:
            self.config['log_file'] = os.path.expanduser(self.config['log_file'])
        os.makedirs(self.config['output_dir'], exist_ok=True)

        self.logger = self._setup_logger()
        self.logger.info(f"Loaded config from {resolved}")

        self.fetcher = ContentFetcher(self.config, self.logger)
        self.summarizer = Summarizer(self.config, self.logger)
        self.renderer = BriefRenderer(self.config, self.logger)

    # ── Setup ──────────────────────────────────────────────────────────

    def _setup_logger(self) -> logging.Logger:
        return _shared_setup_logger('briefs', log_file=self.config.get('log_file'))

    # ── Utility ────────────────────────────────────────────────────────

    def get_date_str(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%Y-%m-%d')

    def get_date_display(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%B %d, %Y')

    def _build_portfolio_context(self) -> str:
        """Build portfolio context block for the prompt, if holdings/watchlist exist."""
        holdings = self.config.get('portfolio_holdings', {})
        watchlist = self.config.get('watchlist', {})
        if not holdings and not watchlist:
            return ''

        lines = ['## PORTFOLIO CONTEXT (use this to prioritize and contextualize stories):\n']
        if holdings:
            lines.append('### Current Holdings:')
            all_tickers = []
            for sector, tickers in holdings.items():
                lines.append(f'- **{sector}:** {", ".join(tickers)}')
                all_tickers.extend(tickers)
            lines.append(f'\nTotal positions: {len(all_tickers)} tickers across {len(holdings)} sectors.\n')
        if watchlist:
            lines.append('### Watchlist:')
            if watchlist.get('tickers'):
                lines.append(f'- **Tickers:** {", ".join(watchlist["tickers"])}')
            if watchlist.get('themes'):
                lines.append(f'- **Themes:** {", ".join(watchlist["themes"])}')
            lines.append('')
        lines.append('---\n')
        return '\n'.join(lines)

    # ── Main Pipeline ──────────────────────────────────────────────────

    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief using fetch-first architecture."""
        self.logger.info("=" * 60)
        self.logger.info("Brief Generator v3.1 (editorial/format split)")
        self.logger.info("=" * 60)

        # Step 1: Fetch all content
        ok_sources, failed_sources = self.fetcher.fetch_all()

        # Step 2: Load format template and fill placeholders (renderer owns this)
        template_rel = self.config.get('template', 'templates/ai-tech-brief.md')
        template_path = os.path.join(_SKILL_DIR, template_rel)
        format_template = self.renderer.load_template(template_path)

        date_display = self.get_date_display()
        brief_title = self.config.get('brief_title', 'Daily AI Tech Brief')
        twitter_accounts = self.config.get('twitter_accounts', [])

        # Build template vars from fetched content counts
        template_vars = {
            'brief_title': brief_title,
            'date_display': date_display,
            'twitter_count': str(len(twitter_accounts)),
        }
        # Add all fetched content counts dynamically
        count_aliases = {
            'hackernews': 'hn',
            'github_trending': 'github',
            'web_pages': 'web',
        }
        for key, items in self.fetcher.fetched_content.items():
            name = count_aliases.get(key, key)
            template_vars[f'{name}_count'] = str(len(items))

        # Add portfolio-specific vars if holdings/watchlist exist in config
        holdings = self.config.get('portfolio_holdings', {})
        watchlist = self.config.get('watchlist', {})
        if holdings or watchlist:
            all_tickers = [t for tickers in holdings.values() for t in tickers]
            template_vars['holdings_count'] = str(len(all_tickers))
            template_vars['sector_count'] = str(len(holdings))
            template_vars['watchlist_ticker_count'] = str(len(watchlist.get('tickers', [])))
            template_vars['watchlist_theme_count'] = str(len(watchlist.get('themes', [])))
        filled_format = self.renderer.fill_template(format_template, template_vars)

        # Step 3: Load prompt template
        prompt_rel = self.config.get('prompt', 'prompts/ai-tech-brief.md')
        prompt_path = os.path.join(_SKILL_DIR, prompt_rel)
        prompt_template = self.renderer.load_template(prompt_path)

        # Step 4: Build prompt variables (all runtime data the prompt template needs)
        content_sections = self.fetcher.get_formatted_sections()

        web_only = self.config.get('web_only_sources', [])
        fetched_web_names = {p['source'] for p in self.fetcher.fetched_content.get('web_pages', [])}
        unfetched_web = [s['name'] for s in web_only
                         if s.get('category') in ('newsletter', 'ai_lab', 'research_org')
                         and s['name'] not in fetched_web_names]

        # Twitter block
        if twitter_accounts:
            twitter_lines = [f"### Twitter/X Accounts ({len(twitter_accounts)}):"]
            twitter_lines.extend(f'- @{acc}' for acc in twitter_accounts)
            twitter_lines.append("Search for tweets from the past 24-48 hours. Only include tweets you actually find via web search.")
            twitter_block = '\n'.join(twitter_lines)
        else:
            twitter_block = "No Twitter/X accounts configured."

        # Unavailable web sources block
        if unfetched_web:
            unavailable_lines = ["### Unavailable Web Sources (fetch failed — omit from brief):"]
            unavailable_lines.extend(f'- {name}' for name in unfetched_web)
            unavailable_web_block = '\n'.join(unavailable_lines)
        else:
            unavailable_web_block = ""

        # Failed RSS note
        failed_note = ""
        if failed_sources:
            failed_names = ', '.join(s['name'] for s in failed_sources)
            failed_note = (
                f"\nNOTE: The following RSS sources were UNREACHABLE and have no content "
                f"available: {failed_names}. Do not include them in the brief."
            )

        prompt_vars = {
            'content_rss': content_sections.get('rss', 'No RSS articles collected.'),
            'content_arxiv': content_sections.get('arxiv', 'No arXiv papers collected.'),
            'content_hackernews': content_sections.get('hackernews', 'No Hacker News stories collected.'),
            'content_github': content_sections.get('github', 'No GitHub trending repos collected.'),
            'content_web': content_sections.get('web', 'No web page content collected.'),
            'content_extra_data': content_sections.get('extra_data', ''),
            'twitter_block': twitter_block,
            'unavailable_web_block': unavailable_web_block,
            'portfolio_context': self._build_portfolio_context(),
            'failed_note': failed_note,
            'output_format': filled_format,
        }

        # Step 5: Summarize (prompt template + runtime vars → Gemini)
        self.logger.info("\n[6/7] Summarizing pre-fetched content with Gemini CLI...")
        brief = self.summarizer.summarize(prompt_template, prompt_vars)

        # Step 6: Validate (renderer checks against format template sections)
        is_valid = self.renderer.validate_brief(brief, format_template)
        if not is_valid:
            self.logger.warning("Brief validation had warnings, but continuing...")

        # Step 7: Render final output (deterministic: append warnings + coverage report)
        self.logger.info("\n[7/7] Generating source coverage report...")
        brief_with_coverage = self.renderer.render_output(
            brief, failed_sources,
            self.fetcher.fetched_content,
            self.fetcher.source_coverage)

        # Append staleness warning if extra quantitative data is outdated
        extra_data = self.fetcher.extra_data
        if extra_data and extra_data.get('_stale'):
            brief_with_coverage += (
                "\n\n> **DATA WARNING:** "
                + extra_data['_stale_message']
                + "\n"
            )

        # Step 8: Output
        if output_path:
            self.renderer.save(brief_with_coverage, output_path)
        else:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(brief_with_coverage)
            self.logger.info("=" * 60)

        self.logger.info("Brief generation complete!")
        return brief_with_coverage


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Generate a daily brief from curated sources')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--output_dir', type=str, help='Output directory for briefs (overrides config)')
    parser.add_argument('--config', type=str, help='Config file path (JSON)')
    args = parser.parse_args()

    if args.test:
        print("Running in test mode...")

    generator = BriefGenerator(config_path=args.config)

    if args.output_dir:
        generator.config['output_dir'] = os.path.expanduser(args.output_dir)

    date_str = generator.get_date_str()
    output_dir = generator.config['output_dir']
    output = os.path.join(output_dir, f"{date_str}-brief.md")

    generator.generate_brief(output_path=output)


if __name__ == '__main__':
    main()
