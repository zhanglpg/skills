#!/usr/bin/env python3
"""
Brief Generator

Generates daily briefs from curated sources.
Uses direct APIs and RSS parsing for reliable data collection, then passes
verified content to Gemini CLI for summarization and template rendering.

Usage:
    python3 generate_brief.py [--test] [--output FILE] [--config FILE]
"""

import sys
import os
import json
import logging
from datetime import datetime, timedelta
from typing import Optional

from fetcher import ContentFetcher
from summarizer import Summarizer
from renderer import BriefRenderer

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
    'output_dir': '~/briefs',
    'log_file': '~/briefs/generate.log',
    'template': 'templates/ai-tech-brief.md',
    'brief_title': 'Daily Brief',
}

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_CONFIG_PATH = os.path.join(_SKILL_DIR, 'config.ai-tech.json')


class BriefGenerator:
    """Brief Generator — orchestrates fetch → summarize → render."""

    def __init__(self, config_path: Optional[str] = None):
        self.config = DEFAULT_CONFIG.copy()

        # Load config BEFORE setting up logger so the config's log_file path is used
        resolved = config_path or DEFAULT_CONFIG_PATH
        config_loaded = False
        config_load_error = None
        if resolved and os.path.exists(resolved):
            try:
                with open(resolved, 'r') as f:
                    self.config.update(json.load(f))
                config_loaded = True
            except Exception as e:
                config_load_error = e

        self.config['output_dir'] = os.path.expanduser(self.config['output_dir'])
        self.config['log_file'] = os.path.expanduser(self.config['log_file'])
        os.makedirs(self.config['output_dir'], exist_ok=True)

        self.logger = self._setup_logger()

        if config_loaded:
            self.logger.info(f"Loaded config from {resolved}")
        elif config_load_error:
            self.logger.error(f"Failed to load config: {config_load_error}")
        elif not config_path:
            self.logger.warning(f"No config file found at {DEFAULT_CONFIG_PATH}. Using empty source lists.")

        self.fetcher = ContentFetcher(self.config, self.logger)
        self.summarizer = Summarizer(self.config, self.logger)
        self.renderer = BriefRenderer(self.config, self.logger)

    # ── Setup ──────────────────────────────────────────────────────────

    def _setup_logger(self) -> logging.Logger:
        logger = logging.getLogger('briefs')
        logger.setLevel(logging.INFO)
        logger.handlers = []

        try:
            log_file = self.config.get('log_file', os.path.expanduser('~/briefs/generate.log'))
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

    def get_date_str(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%Y-%m-%d')

    def get_date_display(self) -> str:
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%B %d, %Y')

    # ── Main Pipeline ──────────────────────────────────────────────────

    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief using fetch-first architecture."""
        self.logger.info("=" * 60)
        self.logger.info("Brief Generator v3.0 (modular)")
        self.logger.info("=" * 60)

        # Step 1: Fetch all content
        ok_sources, failed_sources = self.fetcher.fetch_all()

        # Step 2: Load and fill template
        template_rel = self.config.get('template', 'templates/ai-tech-brief.md')
        template_path = os.path.join(_SKILL_DIR, template_rel)
        template = self.renderer.load_template(template_path)

        date_display = self.get_date_display()
        brief_title = self.config.get('brief_title', 'Daily AI Tech Brief')
        twitter_accounts = self.config.get('twitter_accounts', [])

        template_vars = {
            'brief_title': brief_title,
            'date_display': date_display,
            'rss_count': str(len(self.fetcher.fetched_content['rss'])),
            'arxiv_count': str(len(self.fetcher.fetched_content['arxiv'])),
            'hn_count': str(len(self.fetcher.fetched_content['hackernews'])),
            'github_count': str(len(self.fetcher.fetched_content['github_trending'])),
            'web_count': str(len(self.fetcher.fetched_content['web_pages'])),
            'twitter_count': str(len(twitter_accounts)),
        }
        filled_template = self.renderer.fill_template(template, template_vars)

        # Step 3: Build context for summarizer
        web_only = self.config.get('web_only_sources', [])
        fetched_web_names = {p['source'] for p in self.fetcher.fetched_content.get('web_pages', [])}
        unfetched_web = [s['name'] for s in web_only
                         if s.get('category') in ('newsletter', 'ai_lab', 'research_org')
                         and s['name'] not in fetched_web_names]

        failed_note = ""
        if failed_sources:
            failed_names = ', '.join(s['name'] for s in failed_sources)
            failed_note = (
                f"\n\nNOTE: The following RSS sources were UNREACHABLE: {failed_names}. "
                f"You may still find their content via web search."
            )

        context = {
            'twitter_accounts': twitter_accounts,
            'unfetched_web': unfetched_web,
            'failed_note': failed_note,
        }

        # Step 4: Summarize
        self.logger.info("\n[6/7] Summarizing pre-fetched content with Gemini CLI...")
        content_sections = self.fetcher.get_formatted_sections()
        brief = self.summarizer.summarize(content_sections, filled_template, context)

        # Step 5: Validate
        is_valid = self.renderer.validate_brief(brief)
        if not is_valid:
            self.logger.warning("Brief validation had warnings, but continuing...")

        # Step 6: Render final output
        self.logger.info("\n[7/7] Generating source coverage report...")
        brief_with_coverage = self.renderer.render_output(
            brief, failed_sources,
            self.fetcher.fetched_content,
            self.fetcher.source_coverage)

        # Step 7: Output
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
        output = os.path.join(output_dir, f"{date_str}-brief.md")

    generator.generate_brief(output_path=output)


if __name__ == '__main__':
    main()
