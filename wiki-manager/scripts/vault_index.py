"""Scan the Obsidian vault and build/update gen-notes/index.md."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional


@dataclass
class PageInfo:
    """Metadata extracted from a single markdown page."""

    path: Path
    title: str = ""
    page_type: str = "unknown"  # digest, entity, concept, synthesis
    tags: list[str] = field(default_factory=list)
    date_created: Optional[str] = None
    date_updated: Optional[str] = None
    status: str = ""
    summary: str = ""  # one-line summary (from TL;DR or first heading content)
    source_digests: list[str] = field(default_factory=list)

    @property
    def wikilink(self) -> str:
        """Return an Obsidian wikilink for this page."""
        return f"[[{self.path.stem}]]"


# ---------------------------------------------------------------------------
# Frontmatter parsing
# ---------------------------------------------------------------------------

_FM_PATTERN = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


def _parse_yaml_value(raw: str) -> str | list[str]:
    """Minimal YAML value parser (no external deps)."""
    raw = raw.strip()
    # Inline list: [a, b, c]
    if raw.startswith("[") and raw.endswith("]"):
        return [v.strip().strip('"').strip("'") for v in raw[1:-1].split(",") if v.strip()]
    return raw.strip('"').strip("'")


def parse_frontmatter(text: str) -> dict[str, str | list[str]]:
    """Extract YAML frontmatter from markdown text.

    Returns a flat dict.  List values indicated by subsequent ``  - item``
    lines are collected into Python lists.
    """
    m = _FM_PATTERN.match(text)
    if not m:
        return {}

    result: dict[str, str | list[str]] = {}
    current_key: Optional[str] = None
    current_list: list[str] | None = None

    for line in m.group(1).splitlines():
        # List continuation
        if line.startswith("  - ") or line.startswith("  -\t"):
            val = line.lstrip(" \t-").strip().strip('"').strip("'")
            if current_key is not None:
                if current_list is None:
                    current_list = []
                current_list.append(val)
                result[current_key] = current_list
            continue

        # New key
        if ":" in line:
            # Flush previous list
            current_list = None
            key, _, val = line.partition(":")
            key = key.strip()
            val = val.strip()
            current_key = key
            if val:
                result[key] = _parse_yaml_value(val)
            # If val is empty, we might be starting a list — wait for next lines
            continue

    return result


# ---------------------------------------------------------------------------
# Summary extraction
# ---------------------------------------------------------------------------

_HEADING_RE = re.compile(r"^##\s+(.+)", re.MULTILINE)


def _extract_summary(text: str, frontmatter: dict) -> str:
    """Extract a one-line summary from page content.

    Priority: frontmatter 'summary' > TL;DR section > first paragraph after
    first heading.
    """
    if "summary" in frontmatter:
        val = frontmatter["summary"]
        return val if isinstance(val, str) else val[0]

    # Look for TL;DR section
    tldr_match = re.search(r"##\s+TL;DR\s*\n+(.+?)(?:\n\n|\n##|\Z)", text, re.DOTALL)
    if tldr_match:
        return tldr_match.group(1).strip().split("\n")[0].strip()

    # Look for Main Idea section
    main_match = re.search(
        r"##\s+(?:1\.\s+)?Main Idea[^\n]*\n+(.+?)(?:\n\n|\n##|\Z)", text, re.DOTALL
    )
    if main_match:
        return main_match.group(1).strip().split("\n")[0].strip()

    # Fallback: first non-heading, non-empty line after frontmatter
    body = _FM_PATTERN.sub("", text).strip()
    for line in body.split("\n"):
        line = line.strip()
        if line and not line.startswith("#") and not line.startswith(">"):
            return line[:200]

    return ""


# ---------------------------------------------------------------------------
# Page type inference
# ---------------------------------------------------------------------------

_TYPE_DIR_MAP = {
    "digests": "digest",
    "entities": "entity",
    "concepts": "concept",
    "syntheses": "synthesis",
}


def _infer_page_type(path: Path, frontmatter: dict) -> str:
    """Infer page type from frontmatter or directory name."""
    if "type" in frontmatter:
        val = frontmatter["type"]
        return val if isinstance(val, str) else val[0]

    for dirname, ptype in _TYPE_DIR_MAP.items():
        if dirname in path.parts:
            return ptype

    if "categories" in frontmatter:
        cats = frontmatter["categories"]
        if isinstance(cats, list) and "paper-digest" in cats:
            return "digest"

    return "unknown"


# ---------------------------------------------------------------------------
# Vault scanning
# ---------------------------------------------------------------------------


def scan_vault(vault_root: str, gen_notes_dir: str = "gen-notes") -> list[PageInfo]:
    """Recursively scan gen-notes/ for markdown files and extract metadata."""
    root = Path(os.path.expanduser(vault_root))
    gen_path = root / gen_notes_dir
    if not gen_path.exists():
        return []

    pages: list[PageInfo] = []
    for md_file in sorted(gen_path.rglob("*.md")):
        # Skip index, log, schema, and lint reports
        if md_file.name in ("index.md", "entity_index.md", "log.md", "schema.md", "_lint-report.md"):
            continue

        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue

        fm = parse_frontmatter(text)
        title = fm.get("title", md_file.stem)
        if isinstance(title, list):
            title = title[0]

        tags = fm.get("tags", [])
        if isinstance(tags, str):
            tags = [tags]

        source_digests = fm.get("source-digests", [])
        if isinstance(source_digests, str):
            source_digests = [source_digests]

        page = PageInfo(
            path=md_file.relative_to(root),
            title=str(title),
            page_type=_infer_page_type(md_file, fm),
            tags=[str(t).lstrip("#") for t in tags],
            date_created=str(fm.get("date-created", fm.get("date", fm.get("digested", "")))),
            date_updated=str(fm.get("date-updated", fm.get("date", ""))),
            status=str(fm.get("status", "")),
            summary=_extract_summary(text, fm),
            source_digests=source_digests,
        )
        pages.append(page)

    return pages


# ---------------------------------------------------------------------------
# Index generation
# ---------------------------------------------------------------------------


def build_index(pages: list[PageInfo]) -> str:
    """Generate index.md content from a list of PageInfo objects."""
    lines: list[str] = []
    lines.append("---")
    lines.append("title: Wiki Index")
    lines.append(f"date-updated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("type: index")
    lines.append("---")
    lines.append("")
    lines.append("# Knowledge Wiki Index")
    lines.append("")
    lines.append(f"> Auto-generated on {datetime.now().strftime('%Y-%m-%d %H:%M')}. "
                 "Do not edit manually — run `wiki_manager.py index` to rebuild.")
    lines.append("")

    # Group by type
    digests = [p for p in pages if p.page_type == "digest"]
    entities = [p for p in pages if p.page_type == "entity"]
    concepts = [p for p in pages if p.page_type == "concept"]
    syntheses = [p for p in pages if p.page_type == "synthesis"]
    other = [p for p in pages if p.page_type not in ("digest", "entity", "concept", "synthesis")]

    # --- Recent Digests ---
    lines.append("## Recent Digests")
    lines.append("")
    if digests:
        # Sort by date descending
        sorted_digests = sorted(
            digests,
            key=lambda p: p.date_created or "",
            reverse=True,
        )
        for p in sorted_digests:
            date_str = f" ({p.date_created})" if p.date_created else ""
            summary_str = f" — {p.summary}" if p.summary else ""
            lines.append(f"- {p.wikilink}{date_str}{summary_str}")
    else:
        lines.append("*No digests yet.*")
    lines.append("")

    # --- Entities ---
    lines.append("## Entities")
    lines.append("")
    if entities:
        for p in sorted(entities, key=lambda p: p.title.lower()):
            summary_str = f" — {p.summary}" if p.summary else ""
            lines.append(f"- {p.wikilink}{summary_str}")
    else:
        lines.append("*No entity pages yet.*")
    lines.append("")

    # --- Concepts ---
    lines.append("## Concepts")
    lines.append("")
    if concepts:
        for p in sorted(concepts, key=lambda p: p.title.lower()):
            summary_str = f" — {p.summary}" if p.summary else ""
            lines.append(f"- {p.wikilink}{summary_str}")
    else:
        lines.append("*No concept pages yet.*")
    lines.append("")

    # --- Syntheses ---
    if syntheses:
        lines.append("## Syntheses")
        lines.append("")
        for p in sorted(syntheses, key=lambda p: p.date_created or "", reverse=True):
            summary_str = f" — {p.summary}" if p.summary else ""
            lines.append(f"- {p.wikilink}{summary_str}")
        lines.append("")

    # --- By Topic ---
    all_pages = digests + entities + concepts + syntheses + other
    tag_map: dict[str, list[PageInfo]] = {}
    for p in all_pages:
        for tag in p.tags:
            tag_map.setdefault(tag, []).append(p)

    if tag_map:
        lines.append("## By Topic")
        lines.append("")
        for tag in sorted(tag_map.keys()):
            tag_pages = tag_map[tag]
            lines.append(f"### {tag}")
            lines.append("")
            for p in sorted(tag_pages, key=lambda p: p.title.lower()):
                lines.append(f"- {p.wikilink} ({p.page_type})")
            lines.append("")

    # --- Stats ---
    lines.append("## Stats")
    lines.append("")
    lines.append("| Type | Count |")
    lines.append("|------|-------|")
    lines.append(f"| Digests | {len(digests)} |")
    lines.append(f"| Entities | {len(entities)} |")
    lines.append(f"| Concepts | {len(concepts)} |")
    lines.append(f"| Syntheses | {len(syntheses)} |")
    lines.append(f"| **Total** | **{len(all_pages)}** |")
    lines.append("")

    return "\n".join(lines)


def update_index(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
    entity_dir_rel: str = "gen-notes/entities",
) -> Path:
    """Scan vault and write/overwrite index.md and entity_index.md.

    Returns the path to the written index file.
    """
    pages = scan_vault(vault_root, gen_notes_dir)
    content = build_index(pages)

    root = Path(os.path.expanduser(vault_root))
    index_path = root / gen_notes_dir / "index.md"
    index_path.parent.mkdir(parents=True, exist_ok=True)
    index_path.write_text(content, encoding="utf-8")

    # Also rebuild the entity index
    update_entity_index(vault_root, gen_notes_dir, entity_dir_rel)

    return index_path


# ---------------------------------------------------------------------------
# Entity index generation
# ---------------------------------------------------------------------------


def build_entity_index(entity_dir: Path) -> str:
    """Generate entity_index.md content from entity pages.

    Produces a simple line-oriented format for easy consumption by other
    skills (e.g. paper-digest).  Each entity is listed as::

        - Canonical Name | aliases: Alias One, Alias Two

    If an entity has no aliases the ``| aliases:`` suffix is omitted.
    """
    if not entity_dir.exists():
        entities: list[tuple[str, list[str]]] = []
    else:
        entities = []
        for md_file in sorted(entity_dir.glob("*.md")):
            try:
                text = md_file.read_text(encoding="utf-8")
            except Exception:
                continue
            fm = parse_frontmatter(text)
            title = fm.get("title", md_file.stem)
            if isinstance(title, list):
                title = title[0]
            title = str(title)

            aliases = fm.get("aliases", [])
            if isinstance(aliases, str):
                aliases = [aliases]
            # Filter out the canonical title from aliases to avoid redundancy
            aliases = [str(a) for a in aliases if str(a).strip() and str(a) != title]

            entities.append((title, aliases))

    lines: list[str] = []
    lines.append("---")
    lines.append("title: Entity Index")
    lines.append("type: entity-index")
    lines.append(f"date-updated: {datetime.now().strftime('%Y-%m-%d')}")
    lines.append("---")
    lines.append("")
    lines.append("# Entity Index")
    lines.append("")
    lines.append("> Auto-generated. Do not edit manually "
                 "— run `wiki_manager.py index` to rebuild.")
    lines.append("")

    for title, aliases in entities:
        if aliases:
            lines.append(f"- {title} | aliases: {', '.join(aliases)}")
        else:
            lines.append(f"- {title}")

    lines.append("")
    return "\n".join(lines)


def update_entity_index(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
    entity_dir_rel: str = "gen-notes/entities",
) -> Path:
    """Build and write entity_index.md.

    Returns the path to the written file.
    """
    root = Path(os.path.expanduser(vault_root))
    entity_dir = root / entity_dir_rel
    content = build_entity_index(entity_dir)

    entity_index_path = root / gen_notes_dir / "entity_index.md"
    entity_index_path.parent.mkdir(parents=True, exist_ok=True)
    entity_index_path.write_text(content, encoding="utf-8")
    return entity_index_path
