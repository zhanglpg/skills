#!/usr/bin/env python3
"""
Wiki Manager — Maintain a living knowledge wiki in the Obsidian vault.

Usage:
    python3 scripts/wiki_manager.py ingest <digest_path>
    python3 scripts/wiki_manager.py index
    python3 scripts/wiki_manager.py lint
    python3 scripts/wiki_manager.py concepts

Commands:
    ingest <path>   Ingest a digest into the wiki (extract concepts, update index/log)
    index           Rebuild index.md from all vault pages
    lint            Run vault health checks
    concepts        List all concept pages
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
from vault_index import parse_frontmatter, scan_vault, build_index, update_index, update_concept_index
from log_writer import append_log
from concept_manager import (
    extract_concepts_from_digest,
    find_concept_page,
    create_concept_page,
    update_concept_page,
    list_concepts,
)
from name_manager import (
    extract_names_from_digest,
    find_name_page,
    create_name_page,
    update_name_page,
    list_names,
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
    concept_dir_rel = config.get("concept_dir", "gen-notes/concepts")
    concept_dir = Path(vault_root) / concept_dir_rel
    names_dir_rel = config.get("names_dir", "gen-notes/names")
    names_dir = Path(vault_root) / names_dir_rel
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")
    log_path = Path(vault_root) / config.get("log_path", "gen-notes/log.md")
    max_concepts = config.get("max_concepts_per_ingest", 8)
    max_names = config.get("max_names_per_ingest", 5)

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

    # 3. Get concepts — prefer frontmatter, fall back to LLM extraction
    fm_concepts = fm.get("concepts", [])
    if isinstance(fm_concepts, str):
        fm_concepts = [fm_concepts]

    if fm_concepts:
        concepts = [str(e).strip() for e in fm_concepts if e][:max_concepts]
        logger.info(f"Concepts from frontmatter: {concepts}")
    else:
        logger.info("No concepts in frontmatter — falling back to LLM extraction")
        existing = list_concepts(concept_dir)
        existing_names = [e["title"] for e in existing]
        concepts = extract_concepts_from_digest(
            digest_content, existing_names, llm_fn, max_concepts
        )
        logger.info(f"Extracted concepts via LLM: {concepts}")

    # 4. Create or update concept pages
    touched_pages: list[str] = []
    for concept_name in concepts:
        existing_path = find_concept_page(concept_name, concept_dir)
        if existing_path:
            logger.info(f"  Updating concept: {concept_name}")
            update_concept_page(existing_path, digest_title, digest_content, llm_fn)
            touched_pages.append(f"Updated concept: [[{concept_name}]]")
        else:
            logger.info(f"  Creating concept: {concept_name}")
            create_concept_page(concept_name, digest_content, concept_dir, llm_fn)
            touched_pages.append(f"Created concept: [[{concept_name}]]")

    # 5. Get names — prefer frontmatter, fall back to LLM extraction
    fm_names = fm.get("names", [])
    if isinstance(fm_names, str):
        fm_names = [fm_names]

    if fm_names:
        name_list = [str(n).strip() for n in fm_names if n][:max_names]
        logger.info(f"Names from frontmatter: {name_list}")
    else:
        logger.info("No names in frontmatter — falling back to LLM extraction")
        existing_names_list = list_names(names_dir)
        existing_name_strings = [n["title"] for n in existing_names_list]
        name_list = extract_names_from_digest(
            digest_content, existing_name_strings, llm_fn, max_names
        )
        logger.info(f"Extracted names via LLM: {name_list}")

    # 6. Create or update name pages
    for name in name_list:
        existing_path = find_name_page(name, names_dir)
        if existing_path:
            logger.info(f"  Updating name: {name}")
            update_name_page(existing_path, digest_title, digest_content, llm_fn)
            touched_pages.append(f"Updated name: [[{name}]]")
        else:
            logger.info(f"  Creating name: {name}")
            create_name_page(name, digest_content, names_dir, llm_fn)
            touched_pages.append(f"Created name: [[{name}]]")

    # 7. Update index
    index_path = update_index(vault_root, gen_notes_dir, concept_dir_rel, names_dir_rel)
    touched_pages.append(f"Updated index: {index_path.name}")
    logger.info(f"Index updated: {index_path}")

    # 8. Append to log
    append_log(
        log_path,
        event_type="ingest",
        title=f'"{digest_title}" → [[{digest_path.stem}]]',
        details=touched_pages,
    )
    logger.info(f"Log updated: {log_path}")

    # Summary
    print(f"\n✓ Ingested: {digest_title}")
    print(f"  Concepts: {len(concepts)} ({len([t for t in touched_pages if 'Created concept' in t])} new, "
          f"{len([t for t in touched_pages if 'Updated concept' in t])} updated)")
    print(f"  Names: {len(name_list)} ({len([t for t in touched_pages if 'Created name' in t])} new, "
          f"{len([t for t in touched_pages if 'Updated name' in t])} updated)")
    print("  Index and log updated")


def cmd_index(args, config: dict, logger) -> None:
    """Rebuild index.md, concept_index.md, and name_index.md from all vault pages."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")
    concept_dir_rel = config.get("concept_dir", "gen-notes/concepts")
    names_dir_rel = config.get("names_dir", "gen-notes/names")
    log_path = Path(vault_root) / config.get("log_path", "gen-notes/log.md")

    pages = scan_vault(vault_root, gen_notes_dir)
    index_path = update_index(vault_root, gen_notes_dir, concept_dir_rel, names_dir_rel)

    append_log(
        log_path,
        event_type="index-rebuild",
        title=f"Rebuilt index ({len(pages)} pages)",
    )

    print(f"✓ Index rebuilt: {index_path}")
    print("  Concept and name indexes updated")
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


def cmd_concepts(args, config: dict, logger) -> None:
    """List all concept pages."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    concept_dir = Path(vault_root) / config.get("concept_dir", "gen-notes/concepts")

    concepts = list_concepts(concept_dir)
    if not concepts:
        print("No concept pages yet.")
        return

    print(f"{len(concepts)} concept pages:\n")
    for e in concepts:
        print(f"  • {e['title']}")


def cmd_names(args, config: dict, logger) -> None:
    """List all name pages."""
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    names_dir = Path(vault_root) / config.get("names_dir", "gen-notes/names")

    names = list_names(names_dir)
    if not names:
        print("No name pages yet.")
        return

    print(f"{len(names)} name pages:\n")
    for n in names:
        print(f"  • {n['title']}")


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

    # concepts
    sub.add_parser("concepts", help="List all concept pages")

    # names
    sub.add_parser("names", help="List all name pages")

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
        "concepts": cmd_concepts,
        "names": cmd_names,
    }
    commands[args.command](args, config, logger)


if __name__ == "__main__":
    main()
