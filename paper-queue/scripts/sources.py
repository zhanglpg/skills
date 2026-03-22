#!/usr/bin/env python3
"""Input source handlers for the paper queue.

Resolves papers from arXiv IDs/URLs, Twitter/X links, and manual entries.
Fetches metadata (title, authors, abstract, categories) via the arXiv Atom API.
"""

import logging
import re
import xml.etree.ElementTree as ET
from typing import Any, Dict, List, Optional
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# arXiv patterns (reused from paper-digest)
# ---------------------------------------------------------------------------

ARXIV_ID_PATTERN = re.compile(r'^(\d{4}\.\d{4,5})(v\d+)?$')
ARXIV_ABS_PATTERN = re.compile(r'arxiv\.org/abs/(\d{4}\.\d{4,5})(v\d+)?')
ARXIV_PDF_PATTERN = re.compile(r'arxiv\.org/pdf/(\d{4}\.\d{4,5})(v\d+)?')

ARXIV_API_URL = "http://export.arxiv.org/api/query"
ATOM_NS = "{http://www.w3.org/2005/Atom}"
ARXIV_NS = "{http://arxiv.org/schemas/atom}"

# Patterns for finding paper URLs in tweet content
PAPER_URL_PATTERNS = [
    re.compile(r'https?://arxiv\.org/(?:abs|pdf)/\d{4}\.\d{4,5}(?:v\d+)?'),
    re.compile(r'https?://(?:www\.)?semanticscholar\.org/paper/[^\s"<>]+'),
    re.compile(r'https?://(?:www\.)?openreview\.net/(?:forum|pdf)\?id=[^\s"<>]+'),
    re.compile(r'https?://(?:papers\.nips\.cc|proceedings\.neurips\.cc)/[^\s"<>]+'),
]


def _fetch_text(url: str, timeout: int = 30) -> str:
    """Fetch URL content as text."""
    req = Request(url, headers={"User-Agent": "OpenClaw-PaperQueue/1.0"})
    with urlopen(req, timeout=timeout) as resp:
        return resp.read().decode("utf-8", errors="replace")


def _extract_arxiv_id(input_str: str) -> Optional[str]:
    """Extract arXiv ID from a string (bare ID or URL). Returns None if not arXiv."""
    input_str = input_str.strip()
    m = ARXIV_ID_PATTERN.match(input_str)
    if m:
        return m.group(1) + (m.group(2) or "")

    for pattern in (ARXIV_ABS_PATTERN, ARXIV_PDF_PATTERN):
        m = pattern.search(input_str)
        if m:
            return m.group(1) + (m.group(2) or "")
    return None


def _parse_arxiv_entry(entry: ET.Element) -> Dict[str, Any]:
    """Parse a single arXiv Atom API entry into a paper dict."""
    title_el = entry.find(f"{ATOM_NS}title")
    title = title_el.text.strip().replace("\n", " ") if title_el is not None and title_el.text else "Untitled"

    authors = []
    for author_el in entry.findall(f"{ATOM_NS}author"):
        name_el = author_el.find(f"{ATOM_NS}name")
        if name_el is not None and name_el.text:
            authors.append(name_el.text.strip())

    abstract_el = entry.find(f"{ATOM_NS}summary")
    abstract = abstract_el.text.strip().replace("\n", " ") if abstract_el is not None and abstract_el.text else None

    # Extract arXiv ID from the entry id URL
    id_el = entry.find(f"{ATOM_NS}id")
    arxiv_id = None
    url = None
    if id_el is not None and id_el.text:
        url = id_el.text.strip()
        m = re.search(r'(\d{4}\.\d{4,5})(v\d+)?', url)
        if m:
            arxiv_id = m.group(1) + (m.group(2) or "")

    # Extract categories as topics
    topics = []
    for cat_el in entry.findall(f"{ARXIV_NS}primary_category"):
        term = cat_el.get("term")
        if term:
            topics.append(term)
    for cat_el in entry.findall(f"{ATOM_NS}category"):
        term = cat_el.get("term")
        if term and term not in topics:
            topics.append(term)

    # Published date
    published_el = entry.find(f"{ATOM_NS}published")
    published = published_el.text.strip() if published_el is not None and published_el.text else None

    return {
        "title": title,
        "arxiv_id": arxiv_id,
        "authors": ", ".join(authors),
        "abstract": abstract,
        "url": f"https://arxiv.org/abs/{arxiv_id}" if arxiv_id else url,
        "source": "arxiv",
        "topics": topics,
        "published": published,
    }


def fetch_arxiv_metadata(arxiv_id: str) -> Dict[str, Any]:
    """Fetch paper metadata from the arXiv Atom API.

    Args:
        arxiv_id: An arXiv ID like '2401.12345' or '2401.12345v2'.

    Returns:
        Dict with title, arxiv_id, authors, abstract, url, source, topics, published.

    Raises:
        ValueError: If the paper is not found on arXiv.
        URLError: If the API request fails.
    """
    # Strip version for the API query (it returns latest by default)
    base_id = re.sub(r'v\d+$', '', arxiv_id)
    api_url = f"{ARXIV_API_URL}?id_list={base_id}&max_results=1"
    logger.info("Fetching arXiv metadata for %s", arxiv_id)

    xml_text = _fetch_text(api_url)
    root = ET.fromstring(xml_text)

    entries = root.findall(f"{ATOM_NS}entry")
    if not entries:
        raise ValueError(f"No results from arXiv API for ID: {arxiv_id}")

    entry = entries[0]
    # Check for error (arXiv returns an entry with id containing "api/errors" on bad IDs)
    id_el = entry.find(f"{ATOM_NS}id")
    if id_el is not None and id_el.text and "api/errors" in id_el.text:
        raise ValueError(f"arXiv API error for ID {arxiv_id}")

    return _parse_arxiv_entry(entry)


def resolve_arxiv(input_str: str) -> Dict[str, Any]:
    """Resolve an arXiv ID or URL to a paper metadata dict.

    Args:
        input_str: A bare arXiv ID ('2401.12345') or URL ('https://arxiv.org/abs/2401.12345').

    Returns:
        Paper metadata dict.

    Raises:
        ValueError: If input is not a recognized arXiv format or paper not found.
    """
    arxiv_id = _extract_arxiv_id(input_str)
    if not arxiv_id:
        raise ValueError(f"Could not extract arXiv ID from: {input_str}")
    return fetch_arxiv_metadata(arxiv_id)


def resolve_twitter(tweet_url: str) -> List[Dict[str, Any]]:
    """Extract paper URLs from a Twitter/X link and resolve them.

    Fetches the tweet page content and looks for arXiv or other paper URLs.
    Each found paper URL is resolved to metadata.

    Args:
        tweet_url: A Twitter/X URL (e.g. 'https://x.com/user/status/123').

    Returns:
        List of paper metadata dicts. May be empty if no paper URLs found.
    """
    logger.info("Resolving Twitter URL: %s", tweet_url)

    # Normalize to nitter or other scraping-friendly alternative if needed
    # For now, attempt direct fetch
    try:
        content = _fetch_text(tweet_url, timeout=15)
    except (URLError, OSError) as e:
        logger.warning("Failed to fetch tweet page: %s", e)
        # Fall back: maybe the user pasted a tweet URL that contains an arXiv link
        # Try to extract arXiv ID from the URL itself (unlikely but harmless)
        content = tweet_url

    # Extract paper URLs from the page content
    found_urls: list = []
    seen: set = set()
    for pattern in PAPER_URL_PATTERNS:
        for match in pattern.finditer(content):
            url = match.group(0)
            if url not in seen:
                seen.add(url)
                found_urls.append(url)

    if not found_urls:
        logger.warning("No paper URLs found in tweet content")
        return []

    # Resolve each found URL
    papers: list = []
    # Try to extract tweet author from URL for source_meta
    tweet_author = None
    author_match = re.search(r'(?:twitter|x)\.com/(\w+)/status', tweet_url)
    if author_match:
        tweet_author = author_match.group(1)

    for url in found_urls:
        arxiv_id = _extract_arxiv_id(url)
        if arxiv_id:
            try:
                paper = fetch_arxiv_metadata(arxiv_id)
                paper["source"] = "twitter"
                paper["source_meta"] = {"tweet_url": tweet_url, "tweet_author": tweet_author}
                papers.append(paper)
            except (ValueError, URLError) as e:
                logger.warning("Failed to resolve arXiv paper from tweet: %s", e)
        else:
            # Non-arXiv paper URL — add as manual with URL
            papers.append({
                "title": f"Paper from {url}",
                "arxiv_id": None,
                "authors": None,
                "abstract": None,
                "url": url,
                "source": "twitter",
                "source_meta": {"tweet_url": tweet_url, "tweet_author": tweet_author},
                "topics": [],
            })

    return papers


def resolve_manual(
    title: str,
    url: Optional[str] = None,
    authors: Optional[str] = None,
    notes: Optional[str] = None,
) -> Dict[str, Any]:
    """Create a paper entry from manually provided metadata.

    Args:
        title: Paper title (required).
        url: Optional URL.
        authors: Optional author string.
        notes: Optional notes.

    Returns:
        Paper metadata dict.
    """
    return {
        "title": title,
        "arxiv_id": None,
        "authors": authors,
        "abstract": None,
        "url": url,
        "source": "manual",
        "source_meta": None,
        "topics": [],
        "notes": notes,
    }
