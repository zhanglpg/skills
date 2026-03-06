"""Summarizer module for the Brief Generator.

Handles Gemini CLI interaction and prompt assembly. Takes pre-fetched
content sections and editorial instructions, assembles a complete prompt,
and invokes Gemini CLI for summarization.
"""

import logging
import os
import subprocess
from typing import Dict, List, Optional


class Summarizer:
    """Builds prompts from fetched content + editorial instructions and runs Gemini CLI."""

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

    def build_prompt(self, content_sections: Dict[str, str],
                     editorial_instructions: str, context: dict) -> str:
        """Assemble the full Gemini prompt from content sections and editorial instructions.

        Args:
            content_sections: Dict with keys 'rss', 'arxiv', 'hackernews', 'github', 'web'
                              containing formatted text for each source.
            editorial_instructions: The editorial/analytical instructions loaded from
                                    the prompt file (what to prioritize, how to judge content).
            context: Dict with keys:
                - twitter_accounts: List[str]
                - unfetched_web: List[str] — web source names that couldn't be fetched
                - failed_note: str — note about unreachable RSS sources (or empty)
                - portfolio_context: str — portfolio holdings/watchlist block (or empty)
                - output_format: str — the filled output format template for structural reference
        """
        twitter_accounts = context.get('twitter_accounts', [])
        unfetched_web = context.get('unfetched_web', [])
        failed_note = context.get('failed_note', '')
        portfolio_context = context.get('portfolio_context', '')
        output_format = context.get('output_format', '')

        prompt = f"""You are a summarizer. All content below has been PRE-FETCHED by a separate process and is ready for you to summarize.

IMPORTANT: USE ONLY the pre-fetched content provided in the sections below. Do NOT search the web for articles, arXiv papers, Hacker News stories, or GitHub repos — all of that content has already been gathered for you.
For Twitter/X accounts only: use your web search capability to find recent tweets.
Do NOT fabricate URLs, titles, or content. It is better to have a shorter brief with all real content than a longer brief with fabricated entries.{failed_note}

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

## TWITTER/X SOURCES (use Gemini web search for these only):

### Twitter/X Accounts ({len(twitter_accounts)}):
{chr(10).join([f'- @{acc}' for acc in twitter_accounts]) if twitter_accounts else 'No Twitter/X accounts configured.'}
Search for tweets from the past 24-48 hours. Only include tweets you actually find via web search.

{f"### Unavailable Web Sources (fetch failed — omit from brief):{chr(10)}{chr(10).join([f'- {name}' for name in unfetched_web])}" if unfetched_web else ''}
---
{portfolio_context}
## EDITORIAL INSTRUCTIONS:

{editorial_instructions}

---

## OUTPUT FORMAT REFERENCE:

Use this as a structural reference for the markdown format of your output.
You have editorial freedom to omit empty sections or merge related items,
but follow this general structure and formatting style:

```markdown
{output_format}
```
"""
        return prompt

    def summarize(self, content_sections: Dict[str, str],
                  editorial_instructions: str, context: dict) -> str:
        """Build prompt and run Gemini to generate the summary."""
        prompt = self.build_prompt(content_sections, editorial_instructions, context)
        self.logger.info("Sending pre-fetched content to Gemini for summarization...")
        return self.run_gemini(prompt)
