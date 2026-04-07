#!/usr/bin/env python3
"""
Wiki Manager — Maintain a living knowledge wiki in the Obsidian vault.

Usage:
    python3 scripts/wiki_manager.py ingest <digest_path>
    python3 scripts/wiki_manager.py index
    python3 scripts/wiki_manager.py lint
    python3 scripts/wiki_manager.py fix-links scan
    python3 scripts/wiki_manager.py fix-links apply '{"old": "new"}'
    python3 scripts/wiki_manager.py compile
    python3 scripts/wiki_manager.py concepts

Commands:
    ingest <path>   Ingest a digest into the wiki (extract concepts, update index/log)
    index           Rebuild index.md from all vault pages
    lint            Run vault health checks (auto-fixes resolvable broken links)
    fix-links scan  Scan broken wikilinks (JSON output for agent)
    fix-links apply Batch-replace wikilinks from agent-provided JSON mapping
    compile         Run LLM-powered AI compile
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
from compile_checker import format_compile_report, build_page_batches, parse_llm_findings
from link_fixer import scan_broken_links, apply_link_fixes


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


def _resolve_paths(config: dict) -> dict:
    """Resolve all vault paths from config.

    Sub-directory keys (concept_dir, names_dir, etc.) are relative to
    gen_notes_dir, which is itself relative to vault_root.  This helper
    returns a dict with fully-resolved Path objects and the relative
    strings needed by vault_index helpers.
    """
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")

    concept_sub = config.get("concept_dir", "concepts")
    names_sub = config.get("names_dir", "names")
    log_sub = config.get("log_path", "log.md")

    root = Path(vault_root)
    gen = root / gen_notes_dir

    return {
        "vault_root": vault_root,
        "gen_notes_dir": gen_notes_dir,
        # Absolute paths
        "concept_dir": gen / concept_sub,
        "names_dir": gen / names_sub,
        "log_path": gen / log_sub,
        # Relative to vault_root (for vault_index helpers)
        "concept_dir_rel": str(Path(gen_notes_dir) / concept_sub),
        "names_dir_rel": str(Path(gen_notes_dir) / names_sub),
    }


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

    paths = _resolve_paths(config)
    vault_root = paths["vault_root"]
    gen_notes_dir = paths["gen_notes_dir"]
    concept_dir = paths["concept_dir"]
    concept_dir_rel = paths["concept_dir_rel"]
    names_dir = paths["names_dir"]
    names_dir_rel = paths["names_dir_rel"]
    log_path = paths["log_path"]
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

    # 2. Get concepts — prefer frontmatter
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

    # 3.5 Get names — prefer frontmatter, fall back to LLM extraction
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

    # 3.6 Build existing page names for wikilink context
    all_pages = scan_vault(vault_root, gen_notes_dir)
    existing_page_names = {
        "concepts": [p.title for p in all_pages if p.page_type == "concept"],
        "names": [p.title for p in all_pages if p.page_type == "name"],
        "digests": [p.title for p in all_pages if p.page_type == "digest"],
    }

    # --extract-only: output extracted data as JSON, skip LLM calls
    if getattr(args, 'extract_only', False) is True:
        concepts_info = []
        for c in concepts:
            existing_path = find_concept_page(c, concept_dir)
            concepts_info.append({
                "name": c,
                "exists": existing_path is not None,
                "path": str(existing_path) if existing_path else None,
            })
        names_info = []
        for n in name_list:
            existing_path = find_name_page(n, names_dir)
            names_info.append({
                "name": n,
                "exists": existing_path is not None,
                "path": str(existing_path) if existing_path else None,
            })
        extract_data = {
            "digest_path": str(digest_path),
            "digest_title": digest_title,
            "digest_content": digest_content,
            "concepts": concepts_info,
            "names": names_info,
            "existing_pages": existing_page_names,
            "vault_root": vault_root,
            "concept_dir": str(concept_dir),
            "names_dir": str(names_dir),
            "gen_notes_dir": gen_notes_dir,
            "log_path": str(log_path),
        }
        print(json.dumps(extract_data, ensure_ascii=False))
        return

    # 4. Create or update concept pages
    touched_pages: list[str] = []
    for concept_name in concepts:
        existing_path = find_concept_page(concept_name, concept_dir)
        if existing_path:
            logger.info(f"  Updating concept: {concept_name}")
            update_concept_page(existing_path, digest_title, digest_content, llm_fn, existing_page_names)
            touched_pages.append(f"Updated concept: [[{concept_name}]]")
        else:
            logger.info(f"  Creating concept: {concept_name}")
            create_concept_page(concept_name, digest_content, concept_dir, llm_fn, existing_page_names)
            touched_pages.append(f"Created concept: [[{concept_name}]]")

    # 5. Create or update name pages
    for name in name_list:
        existing_path = find_name_page(name, names_dir)
        if existing_path:
            logger.info(f"  Updating name: {name}")
            update_name_page(existing_path, digest_title, digest_content, llm_fn, existing_page_names)
            touched_pages.append(f"Updated name: [[{name}]]")
        else:
            logger.info(f"  Creating name: {name}")
            create_name_page(name, digest_content, names_dir, llm_fn, existing_page_names)
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
    paths = _resolve_paths(config)
    vault_root = paths["vault_root"]
    gen_notes_dir = paths["gen_notes_dir"]
    concept_dir_rel = paths["concept_dir_rel"]
    names_dir_rel = paths["names_dir_rel"]
    log_path = paths["log_path"]

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
    paths = _resolve_paths(config)
    vault_root = paths["vault_root"]
    gen_notes_dir = paths["gen_notes_dir"]
    log_path = paths["log_path"]

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


def cmd_fix_links(args, config: dict, logger) -> None:
    """Scan or apply broken wikilink fixes.

    Subcommands:
      fix-links scan          — print JSON report of broken links + existing pages
      fix-links apply <json>  — batch-replace wikilinks from a JSON mapping
    """
    paths = _resolve_paths(config)
    vault_root = paths["vault_root"]
    gen_notes_dir = paths["gen_notes_dir"]
    log_path = paths["log_path"]

    sub = getattr(args, "fix_sub", None)

    if sub == "scan":
        import json as _json
        result = scan_broken_links(vault_root, gen_notes_dir)
        print(_json.dumps(result, indent=2))

    elif sub == "apply":
        import json as _json
        try:
            fixes = _json.loads(args.mapping)
        except _json.JSONDecodeError as e:
            print(f"Error: Invalid JSON: {e}", file=sys.stderr)
            sys.exit(1)

        dry_run = getattr(args, "dry_run", False)
        result = apply_link_fixes(vault_root, gen_notes_dir, fixes, dry_run=dry_run)

        if result["applied"]:
            verb = "Would replace" if dry_run else "Replaced"
            for file_path, old, new in result["applied"]:
                print(f"  {verb}: {file_path}: [[{old}]] → [[{new}]]")
            print(f"\n{'Would modify' if dry_run else 'Modified'} {result['files_modified']} files")

            if not dry_run:
                append_log(
                    log_path,
                    event_type="fix-links",
                    title=f"Fixed {len(result['applied'])} broken wikilinks",
                )
        else:
            print("No replacements applied.")
    else:
        print("Usage: wiki_manager.py fix-links {scan|apply <json>}")
        sys.exit(1)


def cmd_compile(args, config: dict, logger) -> None:
    """Agent-powered wiki compile with extract/save-report subcommands."""
    paths = _resolve_paths(config)
    vault_root = paths["vault_root"]
    gen_notes_dir = paths["gen_notes_dir"]
    log_path = paths["log_path"]

    sub = getattr(args, "compile_sub", None)

    if sub == "extract":
        from lint_checker import _read_all_pages
        root = Path(vault_root)
        pages = scan_vault(vault_root, gen_notes_dir)
        all_content = _read_all_pages(root, gen_notes_dir)
        batches = build_page_batches(pages, all_content)

        # Build wiki summary for gap analysis
        wiki_lines = []
        for p in sorted(pages, key=lambda p: p.title.lower()):
            tags_str = ", ".join(p.tags) if p.tags else "none"
            summary = p.summary[:150] if p.summary else "(no summary)"
            wiki_lines.append(f"- {p.title} ({p.page_type}) [{tags_str}] — {summary}")

        # Serialize batches
        batches_json = []
        for batch in batches:
            batches_json.append({
                "label": batch["label"],
                "page_count": len(batch["pages"]),
                "pages": [
                    {"title": p.title, "type": p.page_type,
                     "tags": p.tags, "stem": p.path.stem}
                    for p in batch["pages"]
                ],
                "contents": batch["contents"],
            })

        # Run deterministic lint
        lint_issues = run_full_lint(vault_root, gen_notes_dir)
        lint_json = [
            {"severity": i.severity, "check": i.check,
             "page": i.page, "message": i.message}
            for i in lint_issues
        ]

        extract_data = {
            "vault_root": vault_root,
            "total_pages": len(pages),
            "batches": batches_json,
            "wiki_summary": "\n".join(wiki_lines),
            "lint_issues": lint_json,
        }
        print(json.dumps(extract_data, ensure_ascii=False))

    elif sub == "save-report":
        # Parse agent-provided findings JSON
        findings = parse_llm_findings(args.findings_json)

        # Re-run lint fresh for current state
        lint_issues = run_full_lint(vault_root, gen_notes_dir)

        # Format and write report
        report = format_compile_report(findings, lint_issues)
        report_path = Path(vault_root) / gen_notes_dir / "_compile-report.md"
        report_path.write_text(report, encoding="utf-8")

        # Log it
        append_log(
            log_path,
            event_type="compile",
            title=f"AI compile: {len(findings)} findings, {len(lint_issues)} lint issues",
        )

        print(report)
        print(f"\n✓ Report saved: {report_path}")

    else:
        print("Usage: wiki_manager.py compile {extract|save-report <json>}")
        sys.exit(1)


def cmd_concepts(args, config: dict, logger) -> None:
    """List all concept pages."""
    paths = _resolve_paths(config)
    concept_dir = paths["concept_dir"]

    concepts = list_concepts(concept_dir)
    if not concepts:
        print("No concept pages yet.")
        return

    print(f"{len(concepts)} concept pages:\n")
    for e in concepts:
        print(f"  • {e['title']}")


def cmd_names(args, config: dict, logger) -> None:
    """List all name pages."""
    paths = _resolve_paths(config)
    names_dir = paths["names_dir"]

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
    p_ingest.add_argument("--extract-only", action="store_true",
                          help="Output extracted data as JSON (no LLM calls)")

    # index
    sub.add_parser("index", help="Rebuild index.md")

    # lint
    sub.add_parser("lint", help="Run vault health checks")

    # fix-links (with scan/apply subcommands)
    p_fix = sub.add_parser("fix-links", help="Scan or apply broken wikilink fixes")
    fix_sub = p_fix.add_subparsers(dest="fix_sub")
    fix_sub.add_parser("scan", help="Report broken links and existing pages (JSON)")
    p_apply = fix_sub.add_parser("apply", help="Batch-replace wikilinks from JSON mapping")
    p_apply.add_argument("mapping", help='JSON string: {"old_target": "new_target", ...}')
    p_apply.add_argument("--dry-run", action="store_true", help="Show fixes without applying")

    # compile (with extract/save-report subcommands)
    p_compile = sub.add_parser("compile", help="Agent-powered wiki compile")
    compile_sub = p_compile.add_subparsers(dest="compile_sub")
    compile_sub.add_parser("extract", help="Extract batched data + lint (JSON)")
    p_save = compile_sub.add_parser("save-report", help="Format and save compile report")
    p_save.add_argument("findings_json", help="JSON array of findings")

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
        "fix-links": cmd_fix_links,
        "compile": cmd_compile,
        "concepts": cmd_concepts,
        "names": cmd_names,
    }
    commands[args.command](args, config, logger)


if __name__ == "__main__":
    main()
