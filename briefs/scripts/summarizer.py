"""Summarizer module for the Brief Generator.

Handles Gemini CLI interaction and prompt assembly. Takes a prompt template
(loaded from the prompts/ directory) and fills in runtime data placeholders,
then invokes Gemini CLI. All editorial instructions, accuracy rules, and
structural guidance live in the prompt files — this module contains none.
"""

import logging
import os
import subprocess
from collections import defaultdict
from typing import Dict


class Summarizer:
    """Fills prompt templates with runtime data and runs Gemini CLI."""

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

    def build_prompt(self, prompt_template: str, prompt_vars: Dict[str, str]) -> str:
        """Fill placeholders in the prompt template with runtime data.

        Uses format_map with a defaultdict so any unreferenced placeholders
        are left as-is rather than raising KeyError (similar to safe_substitute).

        Args:
            prompt_template: The full prompt loaded from the prompts/ directory,
                             containing {placeholder} markers for runtime data.
            prompt_vars: Dict mapping placeholder names to their runtime values.
                         Expected keys vary by brief type but typically include:
                         content_rss, content_arxiv, content_hackernews,
                         content_github, content_web, twitter_block,
                         unavailable_web_block, portfolio_context,
                         failed_note, output_format.
        """
        safe_vars = defaultdict(str, prompt_vars)
        return prompt_template.format_map(safe_vars)

    def summarize(self, prompt_template: str, prompt_vars: Dict[str, str]) -> str:
        """Build prompt from template + vars and run Gemini."""
        prompt = self.build_prompt(prompt_template, prompt_vars)
        self.logger.info("Sending pre-fetched content to Gemini for summarization...")
        return self.run_gemini(prompt)
