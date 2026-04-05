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
from typing import Optional, Tuple, List, Dict

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
    return "".join(text_parts).replace("\x00", "")


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
# Hacker News integration — search for paper threads and fetch comments
# ---------------------------------------------------------------------------

HN_SEARCH_URL = "https://hn.algolia.com/api/v1/search"
HN_ITEM_URL = "https://hn.algolia.com/api/v1/items"


def _hn_get_json(url: str, timeout: int = 15) -> Optional[dict]:
    """Fetch JSON from a URL. Returns None on failure."""
    try:
        import httpx
        with httpx.Client(follow_redirects=True, timeout=timeout) as client:
            resp = client.get(url)
            resp.raise_for_status()
            return resp.json()
    except ImportError:
        import urllib.request
        import urllib.error
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "paper-digest/1.0"})
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                return json.loads(resp.read().decode())
        except (urllib.error.URLError, urllib.error.HTTPError, json.JSONDecodeError):
            return None
    except Exception:
        return None


def search_hn_for_paper(title: str, logger: logging.Logger) -> Optional[int]:
    """Search Hacker News for a story matching the paper title.

    Returns the HN story ID if a good match is found, else None.
    """
    import urllib.parse
    # Use the first ~100 chars of title to avoid overly long queries
    query = title[:100].strip()
    params = urllib.parse.urlencode({"query": query, "tags": "story"})
    url = f"{HN_SEARCH_URL}?{params}"

    logger.info(f"Searching HN for paper: {query}")
    data = _hn_get_json(url)
    if not data or not data.get("hits"):
        logger.info("No HN threads found for this paper")
        return None

    # Check if the top hit title is a reasonable match
    top_hit = data["hits"][0]
    hit_title = top_hit.get("title", "").lower()
    query_words = set(re.findall(r'\w+', query.lower()))
    hit_words = set(re.findall(r'\w+', hit_title))

    # Require at least 40% word overlap for a match
    if not query_words:
        return None
    overlap = len(query_words & hit_words) / len(query_words)
    if overlap < 0.4:
        logger.info(f"Best HN hit has low overlap ({overlap:.0%}): {hit_title}")
        return None

    story_id = top_hit.get("objectID")
    logger.info(f"Found HN thread: {hit_title} (id={story_id}, overlap={overlap:.0%})")
    return int(story_id)


def _collect_comments(item: dict, max_depth: int = 2, depth: int = 0) -> List[Dict]:
    """Recursively collect comments from an HN item tree."""
    comments = []
    for child in item.get("children", []):
        text = child.get("text") or ""
        author = child.get("author") or "unknown"
        if text and child.get("type") == "comment":
            comments.append({
                "author": author,
                "text": text,
                "points": child.get("points"),
                "depth": depth,
            })
        if depth < max_depth:
            comments.extend(_collect_comments(child, max_depth, depth + 1))
    return comments


def fetch_hn_comments(
    story_id: int,
    logger: logging.Logger,
    max_comments: int = 20,
    max_chars: int = 8000,
) -> str:
    """Fetch top-level and nested comments from an HN story.

    Returns a formatted text block of comments suitable for inclusion in the
    digest prompt. Returns empty string on failure or if no comments found.
    """
    url = f"{HN_ITEM_URL}/{story_id}"
    logger.info(f"Fetching HN comments for story {story_id}")
    data = _hn_get_json(url)
    if not data:
        return ""

    story_title = data.get("title", "")
    story_url = f"https://news.ycombinator.com/item?id={story_id}"

    comments = _collect_comments(data, max_depth=2)
    if not comments:
        return ""

    # Sort by depth (prefer top-level), then truncate
    comments.sort(key=lambda c: c["depth"])
    comments = comments[:max_comments]

    # Format comments as text
    parts = [
        f"### Hacker News Discussion",
        f"Thread: {story_title}",
        f"URL: {story_url}",
        f"Total comments collected: {len(comments)}",
        "",
    ]

    total_chars = 0
    for i, c in enumerate(comments, 1):
        # Strip HTML tags from HN comment text
        clean_text = re.sub(r'<[^>]+>', ' ', c["text"]).strip()
        clean_text = re.sub(r'\s+', ' ', clean_text)
        indent = "  " * c["depth"]
        entry = f"{indent}[{c['author']}]: {clean_text}"
        total_chars += len(entry)
        if total_chars > max_chars:
            parts.append(f"[Truncated at {i-1} comments due to length]")
            break
        parts.append(entry)

    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Gemini CLI — imported from shared.llm_utils.run_gemini
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Prompt assembly
# ---------------------------------------------------------------------------

def load_entity_index(entity_index_path: str) -> str:
    """Load entity_index.md and return just the entity list lines.

    Returns empty string if the file does not exist.
    """
    path = Path(os.path.expanduser(entity_index_path))
    if not path.exists():
        return ""
    try:
        text = path.read_text(encoding="utf-8")
    except Exception:
        return ""
    # Strip frontmatter
    m = re.match(r"^---\s*\n.*?\n---\s*\n", text, re.DOTALL)
    if m:
        text = text[m.end():]
    # Keep only list lines (- Entity ...)
    lines = []
    for line in text.strip().splitlines():
        if line.strip().startswith("- "):
            lines.append(line.strip())
    return "\n".join(lines)


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


def _digest_filename(title: str) -> str:
    """Return the sanitized markdown filename for a given title."""
    safe_title = re.sub(r'[^\w\s-]', '', title)[:60].strip().replace(' ', '-').lower()
    return f"{safe_title}.md" if safe_title else "digest.md"


def save_output(content: str, title: str, output_dir: str) -> Path:
    """Save digest to a file."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    filepath = output_path / _digest_filename(title)
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
    parser.add_argument('--entity_index', default=None,
                        help="Path to entity_index.md from wiki-manager")
    parser.add_argument('--force', action='store_true',
                        help="Re-digest even if a digest file already exists")
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
    entity_index_path = args.entity_index or config.get('entity_index_path', '')
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

    # Check for existing digest (skip unless --force)
    expected_path = Path(output_dir) / _digest_filename(title)
    if expected_path.exists() and not args.force:
        logger.info(f"Digest already exists: {expected_path} (use --force to re-digest)")
        print(f"Digest already exists: {expected_path}")
        print("Use --force to re-digest.")
        return 0

    # Step 2b: Search Hacker News for the paper
    hn_comments_block = ""
    try:
        story_id = search_hn_for_paper(title, logger)
        if story_id:
            hn_comments_block = fetch_hn_comments(story_id, logger)
            if hn_comments_block:
                logger.info(f"Included HN comments from story {story_id}")
            else:
                logger.info("HN thread found but no comments to include")
    except Exception as e:
        logger.warning(f"HN search failed (non-fatal): {e}")

    # Step 3: Build prompt
    prompt_template = load_template(str(prompt_path))

    user_context_text = user_context if user_context else (
        "No specific user context provided. "
        "Highlight the most broadly impactful and interesting aspects."
    )

    # Load known entities for merging/matching
    entity_list_text = load_entity_index(entity_index_path) if entity_index_path else ""
    if entity_list_text:
        known_entities_block = (
            "**IMPORTANT — Known entities in the wiki:**\n"
            "The following entities already exist in the knowledge wiki. "
            "DO NOT add an entity that is substantially similar to one below — "
            "use the EXISTING canonical name exactly as shown instead. This ensures "
            "entities focus on well-known technologies, datasets, trends, and principles "
            "rather than paper-specific jargon.\n\n"
            f"{entity_list_text}\n\n"
            "Only introduce a new entity name if it is clearly distinct from all of "
            "the above."
        )
    else:
        known_entities_block = ""

    prompt = build_prompt(prompt_template, {
        'paper_text': paper_text,
        'user_context': user_context_text,
        'known_entities': known_entities_block,
        'hn_comments': hn_comments_block,
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
