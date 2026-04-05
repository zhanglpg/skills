"""Shared LLM utilities used across skills."""

from __future__ import annotations

import logging
import os
import subprocess
import time
from typing import Optional


def run_gemini(
    prompt: str,
    timeout: int = 180,
    retry: int = 2,
    logger: Optional[logging.Logger] = None,
) -> str:
    """Run Gemini CLI with retry logic.

    Args:
        prompt: The prompt text to send to Gemini.
        timeout: Timeout per attempt in seconds.
        retry: Number of retries after the first attempt.
        logger: Optional logger for debug/error messages.

    Returns:
        The Gemini CLI stdout on success, or an error message string.
    """
    env = os.environ.copy()
    env["PATH"] = f"/usr/sbin:/usr/bin:/bin:/sbin:{env.get('PATH', '')}"

    for attempt in range(retry + 1):
        try:
            if logger:
                logger.debug(f"Gemini CLI attempt {attempt + 1}/{retry + 1}")
            result = subprocess.run(
                ["gemini", "-p", prompt],
                capture_output=True,
                text=True,
                timeout=timeout,
                env=env,
            )
            if result.returncode == 0:
                return result.stdout
            else:
                msg = f"Gemini CLI failed (attempt {attempt + 1}): {result.stderr[:200]}"
                if logger:
                    logger.warning(msg)
                if attempt < retry:
                    time.sleep(2**attempt)
        except subprocess.TimeoutExpired:
            if logger:
                logger.error(f"Gemini CLI timed out (attempt {attempt + 1})")
            if attempt < retry:
                time.sleep(2**attempt)
        except FileNotFoundError:
            return "Error: gemini CLI not found. Install with: brew install gemini-cli"
        except Exception as e:
            if logger:
                logger.error(f"Gemini CLI error (attempt {attempt + 1}): {e}")
            if attempt < retry:
                time.sleep(2**attempt)

    return "Error: Gemini CLI failed after all retry attempts"
