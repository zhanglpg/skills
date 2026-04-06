"""Resolve broken wikilinks in the knowledge wiki.

Builds a vault-wide alias map from concept, name, and digest pages,
then rewrites broken [[wikilinks]] to their canonical page stems.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

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
# Link resolution
# ---------------------------------------------------------------------------


def resolve_broken_link(
    link_text: str,
    alias_map: dict[str, str],
) -> Optional[str]:
    """Attempt to resolve a broken wikilink target to its canonical stem.

    Returns the canonical page stem if an unambiguous match is found,
    None otherwise.
    """
    normalized = _normalize_name(link_text)
    return alias_map.get(normalized)


# ---------------------------------------------------------------------------
# File rewriting
# ---------------------------------------------------------------------------

# Matches [[target]] or [[target|display text]]
_WIKILINK_FULL_RE = re.compile(r"\[\[([^\]|]+)(\|[^\]]*)?\]\]")


def fix_links_in_file(
    file_path: Path,
    content: str,
    alias_map: dict[str, str],
    page_stems: set[str],
    page_titles: set[str],
    dry_run: bool = False,
) -> tuple[str, list[tuple[str, str]]]:
    """Rewrite broken wikilinks in a single file's content.

    Args:
        file_path: Path to the file (for reporting).
        content: The file's text content.
        alias_map: Normalized alias -> canonical stem.
        page_stems: Set of all existing page stems.
        page_titles: Set of all existing page titles.
        dry_run: If True, return what would change without writing.

    Returns:
        (new_content, replacements) where replacements is a list of
        (old_target, new_target) tuples.
    """
    replacements: list[tuple[str, str]] = []
    # Collect broken links that can be resolved
    broken_targets: dict[str, str] = {}  # old_target -> canonical_target

    for link in _extract_wikilinks(content):
        link_clean = link.strip()
        if link_clean in page_stems or link_clean in page_titles:
            continue  # valid link
        if link_clean in broken_targets:
            continue  # already resolved
        canonical = resolve_broken_link(link_clean, alias_map)
        if canonical and canonical != link_clean:
            broken_targets[link_clean] = canonical

    if not broken_targets:
        return content, []

    # Apply replacements
    new_content = content
    for old_target, new_target in broken_targets.items():
        pattern = re.compile(
            r"\[\[" + re.escape(old_target) + r"(\|[^\]]*)?\]\]"
        )
        new_content = pattern.sub(
            lambda m: f"[[{new_target}{m.group(1) or ''}]]",
            new_content,
        )
        replacements.append((old_target, new_target))

    if not dry_run and new_content != content:
        file_path.write_text(new_content, encoding="utf-8")

    return new_content, replacements


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------


def fix_all_links(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
    dry_run: bool = False,
) -> dict:
    """Resolve broken wikilinks across the entire vault.

    Args:
        vault_root: Path to the vault root.
        gen_notes_dir: Relative path to the gen-notes directory.
        dry_run: If True, report what would change without writing files.

    Returns:
        Summary dict with keys:
        - "fixed": list of (file_path, old_target, new_target)
        - "unresolved": list of (file_path, link_target)
        - "ambiguous_keys": set of normalized keys with multiple candidates
        - "total_files": number of files scanned
    """
    root = Path(os.path.expanduser(vault_root))
    pages = scan_vault(vault_root, gen_notes_dir)
    all_content = _read_all_pages(root, gen_notes_dir)

    page_stems = {p.path.stem for p in pages}
    page_titles = {p.title for p in pages}

    alias_map, ambiguous_keys = build_vault_alias_map(vault_root, gen_notes_dir)

    fixed: list[tuple[str, str, str]] = []
    unresolved: list[tuple[str, str]] = []

    for file_path, content in all_content.items():
        abs_path = root / file_path
        _, replacements = fix_links_in_file(
            abs_path, content, alias_map, page_stems, page_titles, dry_run
        )
        for old_target, new_target in replacements:
            fixed.append((str(file_path), old_target, new_target))

        # Track unresolved broken links
        for link in _extract_wikilinks(content):
            link_clean = link.strip()
            if (link_clean not in page_stems
                    and link_clean not in page_titles
                    and _normalize_name(link_clean) not in alias_map):
                unresolved.append((str(file_path), link_clean))

    return {
        "fixed": fixed,
        "unresolved": unresolved,
        "ambiguous_keys": ambiguous_keys,
        "total_files": len(all_content),
    }
