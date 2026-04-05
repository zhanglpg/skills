#!/usr/bin/env python3
"""
Wiki Manager — Maintain a living knowledge wiki in the Obsidian vault.

Usage:
    python3 scripts/wiki_manager.py ingest <digest_path>
    python3 scripts/wiki_manager.py index
    python3 scripts/wiki_manager.py lint
    python3 scripts/wiki_manager.py entities

Commands:
    ingest <path>   Ingest a digest into the wiki (extract entities, update index/log)
    index           Rebuild index.md from all vault pages
    lint            Run vault health checks
    entities        List all entity pages
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

# Add parent dirs to path for imports
_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_SKILLS_ROOT = _SKILL_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SKILLS_ROOT / "shared"))

from logging_utils import get_agent_data_dir, setup_logger
from vault_index import parse_frontmatter, scan_vault, build_index, update_index, update_entity_index
from log_writer import append_log
from entity_manager import (
    extract_entities_from_digest,
    find_entity_page,
    create_entity_page,
    update_entity_page,
    list_entities,
)
from lint_checker import run_full_lint, format_lint_report


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    """Load config.json with env-var expansion."""
    config_path = _SKILL_DIR / "config.json"
    if not config_path.exists():
        return {}
    get_agent_data_dir()  # ensure AGENT_DATA_DIR is set
    raw = config_path.read_text()
    expanded = os.path.expandvars(raw)
    return json.loads(expanded)


# ---------------------------------------------------------------------------
# LLM wrapper
# ---------------------------------------------------------------------------


def _make_llm_fn(config: dict, logger):
    """Create a callable LLM function using Gemini CLI."""
    timeout = config.get("gemini_timeout", 180)

    def llm_fn(prompt: str) -> str:
        try:
            from llm_utils import run_gemini
            return run_gemini(prompt, timeout=timeout, logger=logger)
        except ImportError:
            logger.error("shared/llm_utils.py not found — cannot make LLM calls")
            return "Error: LLM unavailable"

    return llm_fn


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------


def cmd_ingest(args, config: dict, logger) -> None:
    """Ingest a digest into the knowledge wiki."""
    digest_path = Path(args.digest_path).resolve()
    if not digest_path.exists():
        logger.error(f"Digest not found: {digest_path}")
        sys.exit(1)

    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    entity_dir_rel = config.get("entity_dir", "gen-notes/entities")
    entity_dir = Path(vault_root) / entity_dir_rel
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")
    log_path = Path(vault_root) / config.get("log_path", "gen-notes/log.md")
    max_entities = config.get("max_entities_per_ingest", 8)

    # 1. Read the digest
    digest_content = digest_path.read_text(encoding="utf-8")
    fm = parse_frontmatter(digest_content)
    digest_title = fm.get("title", digest_path.stem)
    if isinstance(digest_title, list):
        digest_title = digest_title[0]
    digest_title = str(digest_title)

    logger.info(f"Ingesting: {digest_title}")

    # 2. Set up LLM
    llm_fn = _make_llm_fn(config, logger)

    # 3. Get entities — prefer frontmatter, fall back to LLM extraction
    fm_entities = fm.get("entities", [])
    if isinstance(fm_entities, str):
        fm_entities = [fm_entities]

    if fm_entities:
        entities = [str(e).strip() for e in fm_entities if e][:max_entities]
        logger.info(f"Entities from frontmatter: {entities}")
    else:
        logger.info("No entities in frontmatter — falling back to LLM extraction")
        existing = list_entities(entity_dir)
        existing_names = [e["title"] for e in existing]
        entities = extract_entities_from_digest(
            digest_content, existing_names, llm_fn, max_entities
        )
        logger.info(f"Extracted entities via LLM: {entities}")

    # 4. Create or update entity pages
    touched_pages: list[str] = []
    for entity_name in entities:
        existing_path = find_entity_page(entity_name, entity_dir)
        if existing_path:
            logger.info(f"  Updating entity: {entity_name}")
            update_entity_page(existing_path, digest_title, digest_content, llm_fn)
            touched_pages.append(f"Updated entity: [[{entity_name}]]")
        else:
            logger.info(f"  Creating entity: {entity_name}")
            create_entity_page(entity_name, digest_content, entity_dir, llm_fn)
            touched_pages.append(f"Created entity: [[{entity_name}]]")

    # 5. Update index
    index_path = update_index(vault_root, gen_notes_dir, entity_dir_rel)
    touched_pages.append(f"Updated index: {index_path.name}")
    logger.info(f"Index updated: {index_path}")

    # 6. Append to log
    append_log(
        log_path,
        event_type="ingest",
        title=f'"{digest_title}" → [[{digest_path.stem}]]',
        details=touched_pages,
    )
    logger.info(f"Log updated: {log_path}")

    # Summary
    print(f"\n✓ Ingested: {digest_title}")
    print(f"  Entities: {len(entities)} ({len([t for t in touched_pages if 'Created' in t])} new, "
          f"{len([t for t in touched_pages if 'Updated entity' in t])} updated)")
    print("  Index and log updated")


def cmd_index(args, config: dict, logger) -> None:
    """Rebuild index.md and entity_index.md from all vault pages."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")
    entity_dir_rel = config.get("entity_dir", "gen-notes/entities")
    log_path = Path(vault_root) / config.get("log_path", "gen-notes/log.md")

    pages = scan_vault(vault_root, gen_notes_dir)
    index_path = update_index(vault_root, gen_notes_dir, entity_dir_rel)

    append_log(
        log_path,
        event_type="index-rebuild",
        title=f"Rebuilt index ({len(pages)} pages)",
    )

    print(f"✓ Index rebuilt: {index_path}")
    print(f"  Entity index updated")
    print(f"  {len(pages)} pages indexed")


def cmd_lint(args, config: dict, logger) -> None:
    """Run vault health checks."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")
    log_path = Path(vault_root) / config.get("log_path", "gen-notes/log.md")

    issues = run_full_lint(vault_root, gen_notes_dir)
    report = format_lint_report(issues)

    # Write report
    report_path = Path(vault_root) / gen_notes_dir / "_lint-report.md"
    report_path.write_text(report, encoding="utf-8")

    # Log it
    severity_counts = {}
    for issue in issues:
        severity_counts[issue.severity] = severity_counts.get(issue.severity, 0) + 1
    summary = ", ".join(f"{v} {k}s" for k, v in severity_counts.items()) if issues else "clean"

    append_log(
        log_path,
        event_type="lint",
        title=f"Lint pass: {len(issues)} issues ({summary})",
    )

    print(report)
    print(f"\n✓ Report saved: {report_path}")


def cmd_entities(args, config: dict, logger) -> None:
    """List all entity pages."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    entity_dir = Path(vault_root) / config.get("entity_dir", "gen-notes/entities")

    entities = list_entities(entity_dir)
    if not entities:
        print("No entity pages yet.")
        return

    print(f"{len(entities)} entity pages:\n")
    for e in entities:
        print(f"  • {e['title']}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Wiki Manager — maintain a living knowledge wiki",
    )
    sub = parser.add_subparsers(dest="command")

    # ingest
    p_ingest = sub.add_parser("ingest", help="Ingest a digest into the wiki")
    p_ingest.add_argument("digest_path", help="Path to the digest markdown file")

    # index
    sub.add_parser("index", help="Rebuild index.md")

    # lint
    sub.add_parser("lint", help="Run vault health checks")

    # entities
    sub.add_parser("entities", help="List all entity pages")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = _load_config()
    log_file = config.get("log_file", "/tmp/logs/skills/wiki-manager/wiki.log")
    logger = setup_logger("wiki-manager", log_file=log_file)

    commands = {
        "ingest": cmd_ingest,
        "index": cmd_index,
        "lint": cmd_lint,
        "entities": cmd_entities,
    }
    commands[args.command](args, config, logger)


if __name__ == "__main__":
    main()
