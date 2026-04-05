#!/usr/bin/env python3
"""
Paper Digest — Structured academic paper summarizer.

Reads a paper (PDF file, URL, or arXiv ID) and produces a structured digest
with five sections: main contributions, key conclusions, relation to prior work,
personalized highlights, and further reading recommendations.

Usage:
    python3 scripts/digest_paper.py <paper>   [--config config.json]
                                               [--output_dir ~/digests]
                                               [--gemini_timeout 180]
                                               [--user_context "..."]

    <paper> can be:
      - A local PDF file path:       paper.pdf
      - A URL:                       https://arxiv.org/abs/2401.12345
      - A bare arXiv ID:             2401.12345

Dependencies: PyMuPDF (fitz), gemini CLI, httpx (optional)
"""

import argparse
import json
import logging
import os
import re
import subprocess
import sys
import tempfile
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

# Allow importing shared utilities from the repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging_utils import get_agent_data_dir, setup_logger as _shared_setup_logger
from shared.llm_utils import run_gemini

# ---------------------------------------------------------------------------
# PDF text extraction
# ---------------------------------------------------------------------------

def extract_text_from_pdf(pdf_path: str, max_chars: int = 120000) -> str:
    """Extract text from a PDF file using PyMuPDF (fitz)."""
    try:
        import fitz  # PyMuPDF
    except ImportError:
        print("PyMuPDF not installed. Installing...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", "PyMuPDF", "-q"])
        import fitz

    doc = fitz.open(pdf_path)
    text_parts = []
    total_chars = 0

    for page_num in range(len(doc)):
        page = doc[page_num]
        page_text = page.get_text()
        text_parts.append(f"\n--- Page {page_num + 1} ---\n{page_text}")
        total_chars += len(page_text)
        if total_chars >= max_chars:
            text_parts.append(
                f"\n[Text truncated at page {page_num + 1}/{len(doc)} "
                f"({total_chars} chars extracted)]"
            )
            break

    doc.close()
    return "".join(text_parts)


# ---------------------------------------------------------------------------
# Input resolution — PDF path, URL, or arXiv ID
# ---------------------------------------------------------------------------

ARXIV_ID_PATTERN = re.compile(r'^(\d{4}\.\d{4,5})(v\d+)?$')
ARXIV_ABS_PATTERN = re.compile(r'arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?')
ARXIV_PDF_PATTERN = re.compile(r'arxiv\.org/pdf/(\d{4}\.\d{4,5})(v\d+)?')


def _fetch_url(url: str, dest_path: str, timeout: int = 60) -> None:
    """Download a URL to a local file. Tries httpx, falls back to urllib."""
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            Path(dest_path).write_bytes(resp.content)
    except ImportError:
        import urllib.request
        urllib.request.urlretrieve(url, dest_path)


def resolve_input(paper_arg: str, logger: logging.Logger) -> Tuple[str, str]:
    """Resolve the input argument to a local PDF path and a source label.

    Returns:
        (pdf_path, source_label) — pdf_path is a local file; source_label
        is a human-readable origin (e.g. "arxiv:2401.12345" or the URL).
    """
    # Case 1: bare arXiv ID
    m = ARXIV_ID_PATTERN.match(paper_arg.strip())
    if m:
        arxiv_id = m.group(1) + (m.group(2) or '')
        return _download_arxiv(arxiv_id, logger), f"arxiv:{arxiv_id}"

    # Case 2: arXiv URL (abstract or PDF page)
    for pattern in (ARXIV_ABS_PATTERN, ARXIV_PDF_PATTERN):
        m = pattern.search(paper_arg)
        if m:
            arxiv_id = m.group(1) + (m.group(2) or '')
            return _download_arxiv(arxiv_id, logger), f"arxiv:{arxiv_id}"

    # Case 3: other URL ending in .pdf (or generic URL)
    if paper_arg.startswith('http://') or paper_arg.startswith('https://'):
        tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
        tmp.close()
        logger.info(f"Downloading PDF from {paper_arg}")
        _fetch_url(paper_arg, tmp.name)
        return tmp.name, paper_arg

    # Case 4: local file
    path = os.path.expanduser(paper_arg)
    if not os.path.isfile(path):
        raise FileNotFoundError(f"File not found: {path}")
    return path, path


def _download_arxiv(arxiv_id: str, logger: logging.Logger) -> str:
    """Download a PDF from arXiv given an ID like 2401.12345."""
    pdf_url = f"https://arxiv.org/pdf/{arxiv_id}.pdf"
    tmp = tempfile.NamedTemporaryFile(suffix='.pdf', delete=False)
    tmp.close()
    logger.info(f"Downloading arXiv paper {arxiv_id} from {pdf_url}")
    _fetch_url(pdf_url, tmp.name)
    return tmp.name


# ---------------------------------------------------------------------------
# Title extraction
# ---------------------------------------------------------------------------

def extract_title(text: str) -> str:
    """Best-effort title extraction from the first page of text."""
    lines = text.split('\n')
    # Skip blank lines and page markers at the top
    candidates = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith('---'):
            continue
        # Stop after collecting a few candidate lines
        if len(candidates) >= 3:
            break
        # Skip lines that look like arXiv headers
        if stripped.lower().startswith('arxiv:') or stripped.startswith('Preprint'):
            continue
        candidates.append(stripped)
    return candidates[0] if candidates else "Untitled Paper"


# ---------------------------------------------------------------------------
# Gemini CLI — imported from shared.llm_utils.run_gemini
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def load_template(path: str) -> str:
    """Load a file as a string."""
    return Path(path).read_text()


def build_prompt(prompt_template: str, variables: dict) -> str:
    """Fill placeholders in the prompt template."""
    safe_vars = defaultdict(str, variables)
    return prompt_template.format_map(safe_vars)


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------

def render_output(gemini_output: str, title: str, source: str) -> str:
    """Merge auto-generated fields into the Obsidian YAML frontmatter from Gemini output."""
    output = gemini_output.strip()
    date_str = datetime.now().strftime("%Y-%m-%d")

    auto_fields = (
        f"source: \"{source}\"\n"
        f"digested: {date_str}\n"
        f"status: digested\n"
    )

    # If Gemini produced a frontmatter block, inject our auto-generated fields
    if output.startswith('---'):
        # Find the closing ---
        end_idx = output.find('---', 3)
        if end_idx != -1:
            frontmatter_body = output[3:end_idx].strip()
            body_after = output[end_idx + 3:].strip()
            merged = (
                f"---\n{frontmatter_body}\n{auto_fields}---\n\n{body_after}"
            )
            return merged

    # Fallback: construct frontmatter from scratch if Gemini didn't produce one
    fallback_frontmatter = (
        f"---\ntitle: \"{title}\"\n{auto_fields}"
        f"categories:\n  - paper-digest\n---\n\n"
    )
    return fallback_frontmatter + output


def save_output(content: str, title: str, output_dir: str) -> Path:
    """Save digest to a file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    # Sanitize title for filename
    safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip().replace(' ', '-').lower()
    date_str = datetime.now().strftime("%Y-%m-%d")
    filename = f"{date_str}-{safe_title}.md" if safe_title else f"{date_str}-digest.md"
    filepath = output_path / filename
    filepath.write_text(content)
    return filepath


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def setup_logger(log_file: Optional[str] = None) -> logging.Logger:
    """Configure logging."""
    return _shared_setup_logger(
        'paper-digest',
        log_file=log_file,
        file_format='%(asctime)s %(levelname)s %(message)s',
    )


def parse_args(argv=None):
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Digest an academic paper into a structured summary."
    )
    parser.add_argument(
        'paper',
        help="PDF file path, URL, or arXiv ID (e.g. 2401.12345)"
    )
    parser.add_argument('--config', help="JSON config file for user context and settings")
    parser.add_argument('--output_dir', default=None, help="Output directory (default: ~/paper-digests)")
    parser.add_argument('--gemini_timeout', type=int, default=None, help="Gemini CLI timeout in seconds")
    parser.add_argument('--user_context', default=None, help="Description of your interests and background")
    parser.add_argument('--log_file', default=None, help="Log file path")
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)

    # Load config if provided
    config = {}
    if args.config:
        config_path = Path(args.config)
        if not config_path.is_absolute():
            # Resolve relative to skill directory
            skill_dir = Path(__file__).resolve().parent.parent
            config_path = skill_dir / args.config
        if config_path.exists():
            config = json.loads(config_path.read_text())

    # Merge CLI args over config
    output_dir = args.output_dir or config.get('output_dir', '~/paper-digests')
    get_agent_data_dir()  # ensure AGENT_DATA_DIR is set for expandvars
    output_dir = os.path.expanduser(os.path.expandvars(output_dir))
    gemini_timeout = args.gemini_timeout or config.get('gemini_timeout', 180)
    user_context = args.user_context or config.get('user_context', '')
    log_file = args.log_file or config.get('log_file', '/tmp/logs/skills/paper-digest/digest.log')

    logger = setup_logger(log_file)

    # Resolve paths relative to skill directory
    skill_dir = Path(__file__).resolve().parent.parent
    prompt_path = skill_dir / 'prompts' / 'digest-prompt.md'

    logger.info(f"Paper Digest starting — input: {args.paper}")

    # Step 1: Resolve input
    try:
        pdf_path, source_label = resolve_input(args.paper, logger)
    except FileNotFoundError as e:
        logger.error(str(e))
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        logger.error(f"Failed to resolve input: {e}")
        print(f"Error resolving input: {e}", file=sys.stderr)
        return 1

    # Step 2: Extract text
    logger.info("Extracting text from PDF...")
    try:
        paper_text = extract_text_from_pdf(pdf_path)
    except Exception as e:
        logger.error(f"Failed to extract text: {e}")
        print(f"Error extracting text from PDF: {e}", file=sys.stderr)
        return 1

    if not paper_text.strip():
        logger.error("No text extracted from PDF (may be image-based)")
        print("Error: No text could be extracted. The PDF may be image-based.", file=sys.stderr)
        return 1

    title = extract_title(paper_text)
    logger.info(f"Extracted title: {title}")
    logger.info(f"Extracted {len(paper_text)} characters of text")

    # Step 3: Build prompt
    prompt_template = load_template(str(prompt_path))

    user_context_text = user_context if user_context else (
        "No specific user context provided. "
        "Highlight the most broadly impactful and interesting aspects."
    )

    prompt = build_prompt(prompt_template, {
        'paper_text': paper_text,
        'user_context': user_context_text,
    })

    # Step 4: Summarize with Gemini
    logger.info("Sending paper to Gemini for digestion...")
    gemini_output = run_gemini(prompt, timeout=gemini_timeout, logger=logger)

    if gemini_output.startswith("Error:"):
        logger.error(gemini_output)
        print(gemini_output, file=sys.stderr)
        return 1

    # Step 5: Render and save
    digest = render_output(gemini_output, title, source_label)
    filepath = save_output(digest, title, output_dir)

    logger.info(f"Digest saved to: {filepath}")
    print(f"\nDigest saved to: {filepath}")
    print(f"Title: {title}")
    print(f"Source: {source_label}")
    print(f"Length: {len(digest)} characters")

    return 0


if __name__ == "__main__":
    sys.exit(main())
