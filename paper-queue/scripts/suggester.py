#!/usr/bin/env python3
"""Related paper suggestions based on queue content and existing digests.

Builds search queries from the topics/categories in your queue and digests,
then queries the arXiv API for related papers not yet in the queue.
"""

import logging
import os
import re
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, Dict, List, Optional

from sources import ATOM_NS, ARXIV_NS, _parse_arxiv_entry, _fetch_text, ARXIV_API_URL
from storage import QueueDB

logger = logging.getLogger(__name__)


def _extract_topics_from_digests(digest_dir: str) -> List[str]:
    """Extract topic keywords from existing digest markdown files.

    Looks for arXiv categories mentioned in digest files (e.g. cs.LG, cs.AI)
    and common ML/AI keywords.
    """
    topics: list = []
    if not digest_dir or not os.path.isdir(digest_dir):
        return topics

    category_pattern = re.compile(r'\b(cs\.\w{2,4}|stat\.\w{2,4}|math\.\w{2,4}|eess\.\w{2,4})\b')

    for md_file in Path(digest_dir).glob("*.md"):
        try:
            content = md_file.read_text(encoding="utf-8", errors="replace")
            # Extract arXiv-style categories
            for m in category_pattern.finditer(content):
                topics.append(m.group(1))
        except OSError:
            continue

    return topics


def _build_arxiv_query(topics: List[str], max_terms: int = 5) -> str:
    """Build an arXiv API search query from topic categories.

    Prioritizes the most frequent categories in the queue.
    """
    if not topics:
        return ""

    # Count frequency
    freq: dict = {}
    for t in topics:
        t_lower = t.lower()
        freq[t_lower] = freq.get(t_lower, 0) + 1

    # Top categories by frequency
    top = sorted(freq.items(), key=lambda x: x[1], reverse=True)[:max_terms]

    # Build OR query: cat:cs.LG OR cat:cs.AI
    terms = [f"cat:{cat}" for cat, _ in top]
    return " OR ".join(terms)


def suggest_related(
    db: QueueDB,
    paper_id: Optional[int] = None,
    digest_dir: Optional[str] = None,
    max_results: int = 10,
) -> List[Dict[str, Any]]:
    """Suggest related papers not yet in the queue.

    Args:
        db: Queue database.
        paper_id: If given, focus suggestions on this paper's topics.
        digest_dir: Directory containing existing paper digests.
        max_results: Maximum number of suggestions to return.

    Returns:
        List of paper metadata dicts from arXiv.
    """
    # Collect topics from queue
    queue_topics = db.get_all_topics()

    # Collect topics from digests
    if digest_dir:
        digest_topics = _extract_topics_from_digests(digest_dir)
        queue_topics = queue_topics + digest_topics

    # If paper_id given, prioritize that paper's topics
    if paper_id:
        paper = db.get_paper(paper_id)
        if paper and paper.get("topics"):
            topics = paper["topics"]
            if isinstance(topics, str):
                import json
                try:
                    topics = json.loads(topics)
                except (ValueError, TypeError):
                    topics = []
            # Put this paper's topics first (repeated for higher weight)
            queue_topics = topics * 3 + queue_topics

    if not queue_topics:
        logger.info("No topics available for suggestions")
        return []

    # Build and execute arXiv query
    query = _build_arxiv_query(queue_topics)
    if not query:
        return []

    api_url = (
        f"{ARXIV_API_URL}?search_query={query}"
        f"&sortBy=submittedDate&sortOrder=descending"
        f"&max_results={max_results * 2}"  # Fetch extra to account for dedup
    )

    logger.info("Querying arXiv for suggestions: %s", query)

    try:
        xml_text = _fetch_text(api_url, timeout=30)
    except Exception as e:
        logger.warning("arXiv suggestion query failed: %s", e)
        return []

    root = ET.fromstring(xml_text)
    entries = root.findall(f"{ATOM_NS}entry")

    suggestions: list = []
    for entry in entries:
        paper_data = _parse_arxiv_entry(entry)
        arxiv_id = paper_data.get("arxiv_id")

        # Skip if already in queue
        if arxiv_id and db.get_by_arxiv_id(arxiv_id):
            continue

        # Skip error entries
        if not arxiv_id:
            continue

        suggestions.append(paper_data)
        if len(suggestions) >= max_results:
            break

    return suggestions
