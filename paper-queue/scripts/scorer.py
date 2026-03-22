#!/usr/bin/env python3
"""Priority scoring for queued papers.

Scores papers on three dimensions:
  - Citations (from Semantic Scholar API)
  - Recency (how recently the paper was published)
  - Queue affinity (topic overlap with papers already in the queue)

No user-configured interests needed — the queue itself is the signal.
"""

import json
import logging
import math
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple
from urllib.error import URLError
from urllib.request import Request, urlopen

logger = logging.getLogger(__name__)

SEMANTIC_SCHOLAR_API = "https://api.semanticscholar.org/graph/v1/paper"

DEFAULT_WEIGHTS = {
    "citations": 0.30,
    "recency": 0.30,
    "queue_affinity": 0.40,
}


# ---------------------------------------------------------------------------
# Citation scoring
# ---------------------------------------------------------------------------

def fetch_citation_count(arxiv_id: str, timeout: int = 10) -> int:
    """Fetch citation count from Semantic Scholar API.

    Args:
        arxiv_id: arXiv ID (e.g. '2401.12345').
        timeout: Request timeout in seconds.

    Returns:
        Citation count, or 0 if not found / request fails.
    """
    # Strip version suffix for Semantic Scholar
    base_id = re.sub(r'v\d+$', '', arxiv_id)
    url = f"{SEMANTIC_SCHOLAR_API}/ArXiv:{base_id}?fields=citationCount"
    req = Request(url, headers={"User-Agent": "OpenClaw-PaperQueue/1.0"})
    try:
        with urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data.get("citationCount", 0) or 0
    except (URLError, OSError, json.JSONDecodeError, KeyError) as e:
        logger.debug("Semantic Scholar lookup failed for %s: %s", arxiv_id, e)
        return 0


def score_citations(count: int) -> Tuple[float, str]:
    """Convert citation count to a 0-10 score using log scale.

    Scale: 0→0, 10→4, 50→6, 100→7.5, 500→10
    """
    if count <= 0:
        return 0.0, "No citations"
    # log10(count) / log10(500) * 10, capped at 10
    score = min(10.0, (math.log10(count) / math.log10(500)) * 10)
    return round(score, 2), f"{count} citations"


# ---------------------------------------------------------------------------
# Recency scoring
# ---------------------------------------------------------------------------

def score_recency(published_date: Optional[str]) -> Tuple[float, str]:
    """Score based on how recently the paper was published.

    Scale: <1 week → 10, <1 month → 8, <3 months → 6, <1 year → 3, older → 1
    """
    if not published_date:
        return 5.0, "Unknown publication date"

    try:
        # Parse ISO format dates
        pub = datetime.fromisoformat(published_date.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        days = (now - pub).days
    except (ValueError, TypeError):
        return 5.0, f"Could not parse date: {published_date}"

    if days < 0:
        days = 0

    if days <= 7:
        score = 10.0
        detail = f"Published {days} days ago (this week)"
    elif days <= 30:
        score = 8.0
        detail = f"Published {days} days ago (this month)"
    elif days <= 90:
        score = 6.0
        detail = f"Published {days} days ago (last 3 months)"
    elif days <= 365:
        score = 3.0
        detail = f"Published {days} days ago (this year)"
    else:
        score = 1.0
        detail = f"Published {days} days ago (older than 1 year)"

    return score, detail


# ---------------------------------------------------------------------------
# Queue affinity scoring
# ---------------------------------------------------------------------------

def score_queue_affinity(
    paper_topics: List[str],
    queue_topics: List[str],
) -> Tuple[float, str]:
    """Score based on topic overlap with existing queue papers.

    Compares the paper's arXiv categories/topics against all topics from
    papers already in the queue (especially 'reading' and 'digested' ones).

    Args:
        paper_topics: This paper's topics (e.g. ['cs.LG', 'cs.AI']).
        queue_topics: All topics from existing queue papers.

    Returns:
        (score, detail) where score is 0-10.
    """
    if not paper_topics:
        return 3.0, "No topics to compare"

    if not queue_topics:
        return 5.0, "Empty queue (no affinity signal yet)"

    paper_set = {t.lower() for t in paper_topics}
    queue_set = {t.lower() for t in queue_topics}

    overlap = paper_set & queue_set
    if not overlap:
        return 1.0, "No topic overlap with queue"

    # Score based on fraction of paper topics that match queue
    match_ratio = len(overlap) / len(paper_set)
    # Also consider how many queue papers share these topics (frequency boost)
    queue_freq = sum(1 for t in queue_topics if t.lower() in overlap) / len(queue_topics)

    # Combine: 60% match ratio + 40% frequency in queue
    raw = match_ratio * 0.6 + queue_freq * 0.4
    score = min(10.0, round(raw * 10, 2))

    return score, f"Overlap: {', '.join(sorted(overlap))} ({len(overlap)}/{len(paper_set)} topics match)"


# ---------------------------------------------------------------------------
# Combined scoring
# ---------------------------------------------------------------------------

def score_paper(
    paper: Dict[str, Any],
    queue_topics: List[str],
    weights: Optional[Dict[str, float]] = None,
    citation_count: Optional[int] = None,
) -> Tuple[float, List[Dict[str, Any]]]:
    """Compute overall priority score for a paper.

    Args:
        paper: Paper dict (must have 'topics', optionally 'published', 'arxiv_id').
        queue_topics: All topics from existing queue papers.
        weights: Optional scoring weight overrides.
        citation_count: Pre-fetched citation count (if None, fetches from API).

    Returns:
        (total_score, components) where components is a list of dicts with
        'component', 'value', and 'detail' keys.
    """
    w = {**DEFAULT_WEIGHTS, **(weights or {})}
    components = []

    # Citations
    if citation_count is None and paper.get("arxiv_id"):
        citation_count = fetch_citation_count(paper["arxiv_id"])
    cit_score, cit_detail = score_citations(citation_count or 0)
    components.append({"component": "citations", "value": cit_score, "detail": cit_detail})

    # Recency
    rec_score, rec_detail = score_recency(paper.get("published"))
    components.append({"component": "recency", "value": rec_score, "detail": rec_detail})

    # Queue affinity
    paper_topics = paper.get("topics", [])
    if isinstance(paper_topics, str):
        try:
            paper_topics = json.loads(paper_topics)
        except (json.JSONDecodeError, TypeError):
            paper_topics = []
    aff_score, aff_detail = score_queue_affinity(paper_topics, queue_topics)
    components.append({"component": "queue_affinity", "value": aff_score, "detail": aff_detail})

    # Weighted sum
    total = (
        w.get("citations", 0.3) * cit_score
        + w.get("recency", 0.3) * rec_score
        + w.get("queue_affinity", 0.4) * aff_score
    )
    total = round(total, 2)

    return total, components
