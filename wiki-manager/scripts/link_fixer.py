"""Resolve broken wikilinks in the knowledge wiki.

Provides two CLI-friendly operations for an LLM agent to orchestrate:

  scan   — report all broken wikilinks, existing pages, and alias hints (JSON)
  apply  — batch-replace wikilink targets from a JSON mapping

Typical agent workflow:
  1. Run ``python3 link_fixer.py scan`` → read the JSON output
  2. Decide resolutions (using alias hints + semantic judgment)
  3. Run ``python3 link_fixer.py apply '<json>'`` → batch rewrite files
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path
from typing import Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
_SKILL_DIR = _SCRIPT_DIR.parent
_SKILLS_ROOT = _SKILL_DIR.parent
sys.path.insert(0, str(_SCRIPT_DIR))
sys.path.insert(0, str(_SKILLS_ROOT / "shared"))

from vault_index import PageInfo, parse_frontmatter, scan_vault
from concept_manager import _normalize_name, _load_alias_map
from name_manager import _load_name_alias_map
from lint_checker import _extract_wikilinks, _read_all_pages


# ---------------------------------------------------------------------------
# Vault-wide alias map
# ---------------------------------------------------------------------------


def build_vault_alias_map(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
) -> tuple[dict[str, str], set[str]]:
    """Build a unified mapping from normalized alias to canonical page stem.

    Combines concept aliases, name aliases, and digest stems/titles.

    Returns:
        (alias_map, ambiguous_keys) where alias_map maps normalized alias
        to the canonical wikilink target (page stem), and ambiguous_keys
        contains normalized keys that map to multiple different stems.
    """
    root = Path(os.path.expanduser(vault_root))
    gen_path = root / gen_notes_dir

    # Collect all candidates: normalized_key -> set of stems
    candidates: dict[str, set[str]] = {}

    def _add(normalized_key: str, stem: str) -> None:
        if not normalized_key:
            return
        candidates.setdefault(normalized_key, set()).add(stem)

    # --- Concept pages (aliases from frontmatter) ---
    concept_dir = gen_path / "concepts"
    if concept_dir.exists():
        concept_alias_map = _load_alias_map(concept_dir)
        for norm_key, file_path in concept_alias_map.items():
            _add(norm_key, file_path.stem)

    # --- Name pages (aliases from frontmatter) ---
    names_dir = gen_path / "names"
    if names_dir.exists():
        name_alias_map = _load_name_alias_map(names_dir)
        for norm_key, file_path in name_alias_map.items():
            _add(norm_key, file_path.stem)

    # --- Digest pages (stem + title) ---
    pages = scan_vault(vault_root, gen_notes_dir)
    for p in pages:
        stem = p.path.stem
        _add(_normalize_name(stem), stem)
        if p.title:
            _add(_normalize_name(p.title), stem)

    # Resolve: only keep unambiguous mappings
    alias_map: dict[str, str] = {}
    ambiguous_keys: set[str] = set()

    for norm_key, stems in candidates.items():
        if len(stems) == 1:
            alias_map[norm_key] = next(iter(stems))
        else:
            ambiguous_keys.add(norm_key)

    return alias_map, ambiguous_keys


# ---------------------------------------------------------------------------
# Scan: report broken links + existing pages + alias hints
# ---------------------------------------------------------------------------


def scan_broken_links(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
) -> dict:
    """Scan the vault and report all broken wikilinks with context.

    Returns a dict suitable for JSON serialization:
    {
        "existing_pages": [{"stem": ..., "title": ..., "type": ..., "aliases": [...]}, ...],
        "broken_links": [{"file": ..., "link": ..., "alias_hint": ... | null}, ...],
        "total_files": int
    }
    """
    root = Path(os.path.expanduser(vault_root))
    pages = scan_vault(vault_root, gen_notes_dir)
    all_content = _read_all_pages(root, gen_notes_dir)

    page_stems = {p.path.stem for p in pages}
    page_titles = {p.title for p in pages}

    alias_map, _ambiguous = build_vault_alias_map(vault_root, gen_notes_dir)

    # Build existing pages list with aliases
    existing_pages = []
    gen_path = root / gen_notes_dir
    for p in pages:
        entry: dict = {
            "stem": p.path.stem,
            "title": p.title,
            "type": p.page_type,
        }
        # Read aliases from frontmatter
        try:
            text = (root / p.path).read_text(encoding="utf-8")
            fm = parse_frontmatter(text)
            aliases = fm.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            entry["aliases"] = [str(a) for a in aliases]
        except Exception:
            entry["aliases"] = []
        existing_pages.append(entry)

    # Find broken links
    broken_links = []
    for file_path, content in all_content.items():
        for link in _extract_wikilinks(content):
            link_clean = link.strip()
            if link_clean in page_stems or link_clean in page_titles:
                continue
            # Check alias map for a hint
            alias_hint = alias_map.get(_normalize_name(link_clean))
            broken_links.append({
                "file": str(file_path),
                "link": link_clean,
                "alias_hint": alias_hint,
            })

    return {
        "existing_pages": existing_pages,
        "broken_links": broken_links,
        "total_files": len(all_content),
    }


# ---------------------------------------------------------------------------
# Apply: batch-replace wikilinks from a resolution map
# ---------------------------------------------------------------------------

# Matches [[target]] or [[target|display text]]
_WIKILINK_FULL_RE = re.compile(r"\[\[([^\]|]+)(\|[^\]]*)?\]\]")


def apply_link_fixes(
    vault_root: str,
    gen_notes_dir: str,
    fixes: dict[str, str],
    dry_run: bool = False,
) -> dict:
    """Batch-replace broken wikilinks across the vault.

    Args:
        vault_root: Path to the vault root.
        gen_notes_dir: Relative path to the gen-notes directory.
        fixes: Mapping of old_link_target → new_link_target.
        dry_run: If True, report what would change without writing files.

    Returns:
        {"applied": [(file, old, new), ...], "files_modified": int}
    """
    root = Path(os.path.expanduser(vault_root))
    all_content = _read_all_pages(root, gen_notes_dir)

    applied: list[tuple[str, str, str]] = []
    files_modified = 0

    for file_path, content in all_content.items():
        new_content = content
        file_applied = []

        for old_target, new_target in fixes.items():
            if old_target not in content:
                continue
            pattern = re.compile(
                r"\[\[" + re.escape(old_target) + r"(\|[^\]]*)?\]\]"
            )
            replaced = pattern.sub(
                lambda m, nt=new_target: f"[[{nt}{m.group(1) or ''}]]",
                new_content,
            )
            if replaced != new_content:
                file_applied.append((str(file_path), old_target, new_target))
                new_content = replaced

        if file_applied:
            if not dry_run:
                abs_path = root / file_path
                abs_path.write_text(new_content, encoding="utf-8")
            applied.extend(file_applied)
            files_modified += 1

    return {
        "applied": applied,
        "files_modified": files_modified,
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _load_config() -> dict:
    config_path = _SKILL_DIR / "config.json"
    if not config_path.exists():
        return {}
    try:
        from logging_utils import get_agent_data_dir
        get_agent_data_dir()
    except Exception:
        pass
    raw = config_path.read_text()
    expanded = os.path.expandvars(raw)
    return json.loads(expanded)


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(
        description="Wiki link fixer — scan broken links and batch-apply fixes",
    )
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("scan", help="Report broken wikilinks and existing pages (JSON)")

    p_apply = sub.add_parser("apply", help="Batch-replace wikilinks from a JSON mapping")
    p_apply.add_argument("mapping", help='JSON string: {"old_target": "new_target", ...}')
    p_apply.add_argument("--dry-run", action="store_true", help="Show fixes without applying")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    config = _load_config()
    vault_root = os.path.expanduser(config.get("vault_root", "~/notes"))
    gen_notes_dir = config.get("gen_notes_dir", "gen-notes")

    if args.command == "scan":
        result = scan_broken_links(vault_root, gen_notes_dir)
        print(json.dumps(result, indent=2))

    elif args.command == "apply":
        try:
            fixes = json.loads(args.mapping)
        except json.JSONDecodeError as e:
            print(f"Error: Invalid JSON mapping: {e}", file=sys.stderr)
            sys.exit(1)

        dry_run = getattr(args, "dry_run", False)
        result = apply_link_fixes(vault_root, gen_notes_dir, fixes, dry_run=dry_run)

        if result["applied"]:
            verb = "Would replace" if dry_run else "Replaced"
            for file_path, old, new in result["applied"]:
                print(f"  {verb}: {file_path}: [[{old}]] → [[{new}]]")
            print(f"\n{'Would modify' if dry_run else 'Modified'} {result['files_modified']} files")
        else:
            print("No replacements applied.")


if __name__ == "__main__":
    main()
