#!/usr/bin/env python3
"""Paper Queue Manager — CLI entry point.

Manage a reading queue of academic papers with priority scoring,
progress tracking, and integration with the paper-digest skill.

Usage:
    python3 scripts/paper_queue.py add <paper>           # arXiv ID, URL, or tweet
    python3 scripts/paper_queue.py add --manual --title "..."
    python3 scripts/paper_queue.py list [--status S] [--top N] [--topic T]
    python3 scripts/paper_queue.py status <id> <status>
    python3 scripts/paper_queue.py digest <id>
    python3 scripts/paper_queue.py score [<id>]
    python3 scripts/paper_queue.py suggest [<id>]
    python3 scripts/paper_queue.py stats
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path
from typing import Optional

# Allow importing sibling modules and shared utilities
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from shared.logging_utils import get_agent_data_dir, setup_logger as _shared_setup_logger
from storage import QueueDB
from sources import resolve_arxiv, resolve_twitter, resolve_manual, _extract_arxiv_id
from scorer import score_paper

_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DEFAULT_CONFIG_PATH = os.path.join(_SKILL_DIR, 'config.json')


def load_config(config_path: Optional[str] = None) -> dict:
    """Load configuration from JSON file."""
    path = config_path or _DEFAULT_CONFIG_PATH
    if os.path.isfile(path):
        with open(path) as f:
            return json.load(f)
    return {}


def setup_logger(config: dict):
    log_file = config.get("log_file", "")
    if log_file:
        log_file = os.path.expandvars(os.path.expanduser(log_file))
    return _shared_setup_logger("paper-queue", log_file=log_file or None)


def resolve_db_path(config: dict, db_override: Optional[str] = None) -> str:
    agent_dir = get_agent_data_dir()
    db_path = db_override or config.get(
        "db_path", os.path.join(agent_dir, "paper-queue", "queue.db")
    )
    return os.path.expandvars(os.path.expanduser(db_path))


# ---------------------------------------------------------------------------
# Subcommands
# ---------------------------------------------------------------------------

def cmd_add(args, config, db, logger):
    """Add a paper to the queue."""
    if args.manual:
        if not args.title:
            print("Error: --title is required with --manual")
            return 1
        paper = resolve_manual(
            title=args.title, url=args.url, authors=args.authors, notes=args.notes
        )
    else:
        if not args.paper:
            print("Error: provide an arXiv ID, URL, or tweet link")
            return 1

        input_str = args.paper
        # Detect Twitter/X URLs
        if "twitter.com/" in input_str or "x.com/" in input_str:
            papers = resolve_twitter(input_str)
            if not papers:
                print("No paper URLs found in the tweet.")
                return 1
            added = 0
            for p in papers:
                if _add_single_paper(p, db, logger, config):
                    added += 1
            print(f"Added {added} paper(s) from tweet.")
            return 0
        else:
            # Try arXiv resolution
            arxiv_id = _extract_arxiv_id(input_str)
            if arxiv_id:
                paper = resolve_arxiv(input_str)
            else:
                # Treat as manual URL
                paper = resolve_manual(title=f"Paper from {input_str}", url=input_str)

    if _add_single_paper(paper, db, logger, config):
        return 0
    return 1


def _add_single_paper(paper: dict, db: QueueDB, logger, config: dict) -> bool:
    """Add a single paper dict to the DB. Returns True on success."""
    arxiv_id = paper.get("arxiv_id")

    # Dedup check
    if arxiv_id:
        existing = db.get_by_arxiv_id(arxiv_id)
        if existing:
            print(f"Already in queue (id={existing['id']}): {existing['title']}")
            return False

    pid = db.add_paper(
        title=paper["title"],
        arxiv_id=arxiv_id,
        authors=paper.get("authors"),
        abstract=paper.get("abstract"),
        url=paper.get("url"),
        source=paper.get("source"),
        source_meta=paper.get("source_meta"),
        topics=paper.get("topics"),
        notes=paper.get("notes"),
    )

    # Score immediately
    queue_topics = db.get_all_topics()
    total, components = score_paper(
        paper, queue_topics,
        weights=config.get("scoring_weights"),
        citation_count=paper.get("citation_count"),
    )
    db.update_score(pid, total, components)

    if paper.get("citation_count"):
        db.update_citation_count(pid, paper["citation_count"])

    print(f"Added (id={pid}, score={total:.1f}): {paper['title']}")
    logger.info("Added paper id=%d: %s", pid, paper["title"])
    return True


def cmd_list(args, config, db, logger):
    """List papers in the queue."""
    papers = db.list_papers(
        status=args.status,
        topic=args.topic,
        sort_by=args.sort or "priority_score",
        limit=args.top,
    )
    if not papers:
        print("Queue is empty.")
        return 0

    # Table header
    print(f"{'ID':>4}  {'Score':>5}  {'Status':<10}  {'Source':<8}  {'Title'}")
    print(f"{'─'*4}  {'─'*5}  {'─'*10}  {'─'*8}  {'─'*40}")
    for p in papers:
        title = p["title"]
        if len(title) > 60:
            title = title[:57] + "..."
        print(f"{p['id']:>4}  {p['priority_score']:>5.1f}  {p['status']:<10}  {(p['source'] or '-'):<8}  {title}")
    print(f"\n{len(papers)} paper(s)")
    return 0


def cmd_status(args, config, db, logger):
    """Update paper status."""
    paper = db.get_paper(args.id)
    if not paper:
        print(f"Paper id={args.id} not found.")
        return 1
    db.update_status(args.id, args.new_status)
    print(f"Updated id={args.id}: {paper['title']} → {args.new_status}")
    return 0


def cmd_digest(args, config, db, logger):
    """Run paper-digest on a queued paper."""
    paper = db.get_paper(args.id)
    if not paper:
        print(f"Paper id={args.id} not found.")
        return 1

    # Determine what to pass to paper-digest
    digest_input = paper.get("arxiv_id") or paper.get("url")
    if not digest_input:
        print(f"Paper id={args.id} has no arXiv ID or URL to digest.")
        return 1

    # Build paper-digest command
    digest_script = os.path.join(_SKILL_DIR, '..', 'paper-digest', 'scripts', 'digest_paper.py')
    if not os.path.isfile(digest_script):
        print(f"paper-digest script not found at: {digest_script}")
        return 1

    cmd = [sys.executable, digest_script, digest_input]

    output_dir = config.get("digest_output_dir")
    if output_dir:
        output_dir = os.path.expandvars(os.path.expanduser(output_dir))
        cmd.extend(["--output_dir", output_dir])

    digest_config = config.get("paper_digest_config")
    if digest_config:
        digest_config_path = os.path.join(_SKILL_DIR, digest_config)
        if os.path.isfile(digest_config_path):
            cmd.extend(["--config", digest_config_path])

    print(f"Running paper-digest on: {paper['title']}")
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"paper-digest failed: {result.stderr[:500]}")
        return 1

    # Try to find the output file
    if output_dir:
        # Look for most recent file in output dir
        try:
            files = sorted(Path(output_dir).glob("*.md"), key=os.path.getmtime, reverse=True)
            if files:
                digest_path = str(files[0])
                db.update_digest_path(args.id, digest_path)
                print(f"Digest saved: {digest_path}")
                return 0
        except OSError:
            pass

    # Mark digested even if we can't find the file
    db.update_status(args.id, "digested")
    print(f"Paper marked as digested (id={args.id})")
    return 0


def cmd_score(args, config, db, logger):
    """Re-score papers."""
    if args.id:
        papers = [db.get_paper(args.id)]
        if not papers[0]:
            print(f"Paper id={args.id} not found.")
            return 1
    else:
        papers = db.list_papers(status="to-read")
        if not papers:
            print("No to-read papers to score.")
            return 0

    queue_topics = db.get_all_topics()
    weights = config.get("scoring_weights")

    for p in papers:
        total, components = score_paper(p, queue_topics, weights=weights)
        db.update_score(p["id"], total, components)
        print(f"  id={p['id']:>3}  score={total:>5.1f}  {p['title'][:50]}")

    print(f"\nScored {len(papers)} paper(s).")
    return 0


def cmd_suggest(args, config, db, logger):
    """Suggest related papers."""
    # Lazy import to avoid circular deps
    from suggester import suggest_related

    digest_dir = config.get("digest_output_dir")
    if digest_dir:
        digest_dir = os.path.expandvars(os.path.expanduser(digest_dir))

    suggestions = suggest_related(
        db,
        paper_id=args.id,
        digest_dir=digest_dir,
        max_results=config.get("max_suggestions", 10),
    )

    if not suggestions:
        print("No suggestions found.")
        return 0

    print(f"{'#':>2}  {'Title':<60}  {'arXiv ID'}")
    print(f"{'─'*2}  {'─'*60}  {'─'*15}")
    for i, s in enumerate(suggestions, 1):
        title = s["title"]
        if len(title) > 57:
            title = title[:54] + "..."
        print(f"{i:>2}  {title:<60}  {s.get('arxiv_id', '-')}")

    print(f"\n{len(suggestions)} suggestion(s). Use 'add <arxiv_id>' to queue one.")
    return 0


def cmd_stats(args, config, db, logger):
    """Show queue statistics."""
    stats = db.get_stats()
    print(f"Total papers: {stats['total']}")
    print("By status:")
    for status, count in stats["by_status"].items():
        print(f"  {status}: {count}")
    if stats["avg_priority_to_read"]:
        print(f"Avg priority (to-read): {stats['avg_priority_to_read']:.1f}")
    if stats["topics"]:
        print(f"Topics: {', '.join(stats['topics'][:15])}")
    return 0


# ---------------------------------------------------------------------------
# CLI argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="paper_queue",
        description="Manage a reading queue of academic papers.",
    )
    parser.add_argument("--config", help="Path to config.json")
    parser.add_argument("--db", help="Override database path")

    subs = parser.add_subparsers(dest="command", help="Available commands")

    # add
    add_p = subs.add_parser("add", help="Add a paper to the queue")
    add_p.add_argument("paper", nargs="?", help="arXiv ID, URL, or tweet link")
    add_p.add_argument("--manual", action="store_true", help="Add manually")
    add_p.add_argument("--title", help="Paper title (with --manual)")
    add_p.add_argument("--url", help="Paper URL (with --manual)")
    add_p.add_argument("--authors", help="Authors (with --manual)")
    add_p.add_argument("--notes", help="Notes")

    # list
    list_p = subs.add_parser("list", help="List papers in the queue")
    list_p.add_argument("--status", choices=["to-read", "reading", "digested"])
    list_p.add_argument("--top", type=int, help="Show top N papers")
    list_p.add_argument("--topic", help="Filter by topic")
    list_p.add_argument("--sort", choices=["priority_score", "added_at", "citation_count", "title"])

    # status
    status_p = subs.add_parser("status", help="Update paper status")
    status_p.add_argument("id", type=int, help="Paper ID")
    status_p.add_argument("new_status", choices=["to-read", "reading", "digested"])

    # digest
    digest_p = subs.add_parser("digest", help="Run paper-digest on a paper")
    digest_p.add_argument("id", type=int, help="Paper ID")

    # score
    score_p = subs.add_parser("score", help="Re-score papers")
    score_p.add_argument("id", type=int, nargs="?", help="Paper ID (or all to-read)")

    # suggest
    suggest_p = subs.add_parser("suggest", help="Suggest related papers")
    suggest_p.add_argument("id", type=int, nargs="?", help="Suggest papers related to this ID")

    # stats
    subs.add_parser("stats", help="Show queue statistics")

    # init
    subs.add_parser("init", help="Initialize a new queue database")

    return parser


def main(argv=None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)

    if not args.command:
        parser.print_help()
        return 1

    config = load_config(args.config)
    logger = setup_logger(config)
    db_path = resolve_db_path(config, args.db)

    # Handle init separately — it creates the DB
    if args.command == "init":
        try:
            db = QueueDB.init_db(db_path)
            db.close()
            print(f"Queue initialized: {db_path}")
            return 0
        except FileExistsError:
            print(f"Queue already exists: {db_path}")
            return 1

    # All other commands require an existing DB
    try:
        db = QueueDB(db_path)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        return 1

    commands = {
        "add": cmd_add,
        "list": cmd_list,
        "status": cmd_status,
        "digest": cmd_digest,
        "score": cmd_score,
        "suggest": cmd_suggest,
        "stats": cmd_stats,
    }

    try:
        return commands[args.command](args, config, db, logger)
    except Exception as e:
        logger.exception("Command '%s' failed", args.command)
        print(f"Error: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
