"""Renderer module for the Brief Generator.

Handles template loading, placeholder substitution, output validation,
source coverage reporting, and file output. This module owns the output
format — it never contains LLM instructions or editorial logic.
"""

import logging
import os
import re
from string import Template
from typing import Dict, List, Optional


class BriefRenderer:
    """Loads format templates, validates briefs, and assembles final output."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger

    def load_template(self, template_path: str) -> str:
        """Read a template file and return its content."""
        try:
            with open(template_path, 'r') as f:
                content = f.read()
            self.logger.info(f"Loaded template from {template_path}")
            return content
        except FileNotFoundError:
            self.logger.error(f"Template file not found: {template_path}")
            raise
        except Exception as e:
            self.logger.error(f"Failed to load template: {e}")
            raise

    def fill_template(self, template: str, variables: dict) -> str:
        """Substitute $placeholders in the template using string.Template.

        Unknown placeholders are left as-is (safe_substitute).
        """
        t = Template(template)
        return t.safe_substitute(variables)

    def extract_sections(self, template: str) -> List[str]:
        """Extract expected section names from a format template.

        Parses ## headings from the template to derive the list of sections
        the brief should contain, so validation stays in sync with the template.
        """
        sections = []
        for match in re.finditer(r'^## (.+)$', template, re.MULTILINE):
            # Strip any trailing markdown formatting or parenthetical hints
            name = match.group(1).strip()
            sections.append(name)
        return sections

    def validate_brief(self, brief: str, format_template: str) -> bool:
        """Check that the brief has required structural elements.

        Validates against sections derived from the format template rather
        than a hardcoded list, so adding/removing template sections automatically
        updates validation.
        """
        # Basic structural checks
        if '#' not in brief:
            self.logger.warning("Brief missing required element: headings (#)")
            return False
        if 'http' not in brief:
            self.logger.warning("Brief missing required element: URLs (http)")
            return False

        # Check section coverage against the format template
        expected_sections = self.extract_sections(format_template)
        if not expected_sections:
            self.logger.warning("Could not extract sections from format template")
            return True  # Can't validate sections, pass anyway

        found = sum(1 for section in expected_sections if section in brief)
        total = len(expected_sections)
        min_required = max(3, total // 2)  # At least half or 3, whichever is larger

        if found < min_required:
            self.logger.warning(
                f"Brief may be missing section coverage (found {found}/{total} expected sections)")

        self.logger.info(f"Brief validation passed (found {found}/{total} expected sections)")
        return True

    def _format_failed_sources_warning(self, failed_sources: List[Dict]) -> str:
        """Format a warning block for sources that couldn't be reached."""
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

    def generate_source_coverage_report(self, fetched_content: Dict[str, list],
                                        source_coverage: Dict[str, int],
                                        failed_sources: List[Dict]) -> str:
        """Generate a report of what data was collected from each source.

        Args:
            fetched_content: Dict with fetched data lists per source type.
            source_coverage: Dict mapping source name to article count.
            failed_sources: List of failed source dicts.
        """
        lines = ["\n## Source Coverage Report\n"]

        # Data source reliability summary
        lines.append("### Data Collection Method")
        lines.append(f"- **RSS feeds (xml.etree):** {len(fetched_content.get('rss', []))} articles")
        lines.append(f"- **arXiv API:** {len(fetched_content.get('arxiv', []))} papers (verified IDs)")
        lines.append(f"- **Hacker News API:** {len(fetched_content.get('hackernews', []))} stories")
        lines.append(f"- **GitHub Search API:** {len(fetched_content.get('github_trending', []))} repos")
        lines.append(f"- **Web page extraction:** {len(fetched_content.get('web_pages', []))} pages")
        lines.append("- **Gemini web search:** Twitter accounts, unfetched web sources")
        lines.append("")

        # Twitter
        twitter_accounts = self.config.get('twitter_accounts', [])
        lines.append(f"### Twitter/X Accounts ({len(twitter_accounts)}) — via Gemini web search")
        for acc in twitter_accounts:
            lines.append(f"- @{acc}")

        # RSS sources by category (labels derived from category keys)
        rss_sources = self.config.get('rss_sources', [])
        categories = dict.fromkeys(s.get('category', '') for s in rss_sources if s.get('category'))
        for cat in categories:
            label = cat.replace('_', ' ').title()
            sources = [s for s in rss_sources if s.get('category') == cat]
            if not sources:
                continue
            lines.append(f"\n### {label} ({len(sources)}) — via RSS")
            for src in sources:
                name = src['name']
                count = source_coverage.get(name, 0)
                failed = any(f['name'] == name for f in failed_sources)
                if failed:
                    status = "Access failed"
                elif count > 0:
                    status = f"{count} articles"
                else:
                    status = "No articles found"
                lines.append(f"- [{status}] {name}")

        # Web-only
        web_only = self.config.get('web_only_sources', [])
        fetched_names = {p['source'] for p in fetched_content.get('web_pages', [])}
        if web_only:
            lines.append(f"\n### Web-only Sources ({len(web_only)})")
            for src in web_only:
                method = "page fetched" if src['name'] in fetched_names else "via Gemini search"
                lines.append(f"- [{method}] {src['name']}")

        return '\n'.join(lines)

    def render_output(self, brief: str, failed_sources: List[Dict],
                      fetched_content: Dict[str, list],
                      source_coverage: Dict[str, int]) -> str:
        """Assemble the final output: brief + warnings + coverage report."""
        output = brief

        if failed_sources:
            output += self._format_failed_sources_warning(failed_sources)

        coverage_report = self.generate_source_coverage_report(
            fetched_content, source_coverage, failed_sources)
        output += "\n\n" + coverage_report

        return output

    def save(self, content: str, output_path: str):
        """Write the final brief to a file."""
        output_dir = os.path.dirname(output_path)
        if output_dir:
            os.makedirs(output_dir, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(content)
        self.logger.info(f"Brief saved to: {output_path}")
