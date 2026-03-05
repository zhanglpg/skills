"""Summarizer module for the Brief Generator.

Handles Gemini CLI interaction and prompt assembly. Takes pre-fetched
content sections and a template, assembles a complete prompt, and
invokes Gemini CLI for summarization.
"""

import logging
import os
import subprocess
from typing import Dict, List, Optional


class Summarizer:
    """Builds prompts from fetched content + template and runs Gemini CLI."""

    def __init__(self, config: dict, logger: logging.Logger):
        self.config = config
        self.logger = logger

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

    def build_prompt(self, content_sections: Dict[str, str], filled_template: str,
                     context: dict) -> str:
        """Assemble the full Gemini prompt from content sections, template, and context.

        Args:
            content_sections: Dict with keys 'rss', 'arxiv', 'hackernews', 'github', 'web'
                              containing formatted text for each source.
            filled_template: The output format template with placeholders already filled.
            context: Dict with keys:
                - twitter_accounts: List[str]
                - unfetched_web: List[str] — web source names that couldn't be fetched
                - failed_note: str — note about unreachable RSS sources (or empty)
        """
        twitter_accounts = context.get('twitter_accounts', [])
        unfetched_web = context.get('unfetched_web', [])
        failed_note = context.get('failed_note', '')

        prompt = f"""You are a summarizer. Below is VERIFIED, PRE-FETCHED content from multiple sources.
Your job is to organize and summarize this content into a structured daily brief.

IMPORTANT RULES:
1. For RSS articles, arXiv papers, Hacker News stories, and GitHub repos: USE ONLY the data provided below. These are verified — use the exact URLs and titles given.
2. For Twitter/X accounts: search the web for recent tweets from the accounts listed below. Only include tweets you can actually find. If you find nothing, write "No updates found."
3. For sources listed under "SOURCES TO SEARCH VIA WEB": search for recent content and only include what you can verify.
4. Do NOT fabricate URLs, titles, or content. Every item must have a real, working URL.
5. It is better to have a shorter brief with all real content than a longer brief with fabricated entries.{failed_note}

---

## PRE-FETCHED CONTENT (verified — use these directly):

### RSS Feed Articles
{content_sections.get('rss', 'No RSS articles collected.')}

### arXiv Papers (verified IDs and URLs)
{content_sections.get('arxiv', 'No arXiv papers collected.')}

### Hacker News Top AI Stories (verified)
{content_sections.get('hackernews', 'No Hacker News stories collected.')}

### GitHub Trending AI/ML Repos (verified)
{content_sections.get('github', 'No GitHub trending repos collected.')}

### Web Source Content (fetched and extracted)
{content_sections.get('web', 'No web page content collected.')}

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
{filled_template}
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
        return prompt

    def summarize(self, content_sections: Dict[str, str], filled_template: str,
                  context: dict) -> str:
        """Build prompt and run Gemini to generate the summary."""
        prompt = self.build_prompt(content_sections, filled_template, context)
        self.logger.info("Sending pre-fetched content to Gemini for summarization...")
        return self.run_gemini(prompt)
