"""Vault health checks for the knowledge wiki."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from vault_index import PageInfo, parse_frontmatter, scan_vault


@dataclass
class LintIssue:
    """A single lint finding."""

    severity: str  # "error", "warning", "info"
    check: str  # name of the check that found it
    page: str  # page path or title
    message: str


# ---------------------------------------------------------------------------
# Wikilink extraction
# ---------------------------------------------------------------------------

_WIKILINK_RE = re.compile(r"\[\[([^\]|]+)(?:\|[^\]]*)?\]\]")


def _extract_wikilinks(text: str) -> list[str]:
    """Extract all wikilink targets from markdown text."""
    return _WIKILINK_RE.findall(text)


def _read_all_pages(vault_root: Path, gen_notes_dir: str) -> dict[Path, str]:
    """Read all markdown files and return {relative_path: content}."""
    gen_path = vault_root / gen_notes_dir
    if not gen_path.exists():
        return {}
    pages = {}
    for md_file in gen_path.rglob("*.md"):
        if md_file.name in ("index.md", "log.md", "schema.md", "_lint-report.md", "_scan-report.md"):
            continue
        try:
            pages[md_file.relative_to(vault_root)] = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
    return pages


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------


def check_orphans(pages: list[PageInfo], all_content: dict[Path, str]) -> list[LintIssue]:
    """Find pages with no inbound wikilinks from any other page."""
    # Build set of all referenced stems
    referenced: set[str] = set()
    for _, content in all_content.items():
        for link in _extract_wikilinks(content):
            referenced.add(link.strip())

    issues = []
    for p in pages:
        stem = p.path.stem
        title = p.title
        # A page is orphaned if neither its stem nor title appears in any wikilink
        if stem not in referenced and title not in referenced:
            issues.append(LintIssue(
                severity="warning",
                check="orphan-pages",
                page=str(p.path),
                message=f"No inbound wikilinks found for '{p.title}'",
            ))
    return issues


def check_broken_links(all_content: dict[Path, str], page_stems: set[str],
                        page_titles: set[str]) -> list[LintIssue]:
    """Find wikilinks that point to non-existent pages."""
    issues = []
    for path, content in all_content.items():
        for link in _extract_wikilinks(content):
            link_clean = link.strip()
            if link_clean not in page_stems and link_clean not in page_titles:
                issues.append(LintIssue(
                    severity="warning",
                    check="broken-links",
                    page=str(path),
                    message=f"Broken wikilink [[{link_clean}]]",
                ))
    return issues


def check_stale_concepts(pages: list[PageInfo], max_age_days: int = 90) -> list[LintIssue]:
    """Find concept pages not updated in a long time."""
    issues = []
    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    for p in pages:
        if p.page_type != "concept":
            continue
        date = p.date_updated or p.date_created or ""
        if date and date < cutoff:
            issues.append(LintIssue(
                severity="info",
                check="stale-concepts",
                page=str(p.path),
                message=f"Concept '{p.title}' last updated {date} (>{max_age_days} days ago)",
            ))
    return issues


def check_missing_concepts(
    pages: list[PageInfo],
    all_content: dict[Path, str],
    concept_stems: set[str],
    min_mentions: int = 3,
) -> list[LintIssue]:
    """Find concepts mentioned in multiple digests that lack a concept page."""
    # Count how many digests mention each wikilink target
    mention_count: dict[str, int] = {}
    for p in pages:
        if p.page_type != "digest":
            continue
        content = all_content.get(p.path, "")
        seen: set[str] = set()
        for link in _extract_wikilinks(content):
            link_clean = link.strip()
            if link_clean not in seen:
                seen.add(link_clean)
                mention_count[link_clean] = mention_count.get(link_clean, 0) + 1

    issues = []
    for name, count in sorted(mention_count.items(), key=lambda x: -x[1]):
        if count >= min_mentions and name not in concept_stems:
            issues.append(LintIssue(
                severity="info",
                check="missing-concepts",
                page="(none)",
                message=f"'{name}' mentioned in {count} digests but has no concept page",
            ))
    return issues


def check_frontmatter(pages: list[PageInfo]) -> list[LintIssue]:
    """Check pages for missing required frontmatter fields."""
    issues = []
    for p in pages:
        missing = []
        if not p.title:
            missing.append("title")
        if p.page_type in ("concept", "name", "synthesis") and not p.date_created:
            missing.append("date-created")
        if p.page_type == "digest" and not p.tags:
            missing.append("tags")
        if missing:
            issues.append(LintIssue(
                severity="warning",
                check="frontmatter",
                page=str(p.path),
                message=f"Missing frontmatter: {', '.join(missing)}",
            ))
    return issues


def check_duplicate_concepts(pages: list[PageInfo]) -> list[LintIssue]:
    """Find concept pages that may cover the same concept."""
    from concept_manager import _normalize_name

    concepts = [p for p in pages if p.page_type == "concept"]
    seen: dict[str, list[PageInfo]] = {}

    for p in concepts:
        key = _normalize_name(p.title)
        seen.setdefault(key, []).append(p)

    issues = []
    for _key, group in seen.items():
        if len(group) > 1:
            paths = ", ".join(str(p.path) for p in group)
            issues.append(LintIssue(
                severity="error",
                check="duplicate-concepts",
                page=paths,
                message=f"Possible duplicate concept pages: {paths}",
            ))
    return issues


def check_stale_names(pages: list[PageInfo], max_age_days: int = 90) -> list[LintIssue]:
    """Find name pages not updated in a long time."""
    issues = []
    cutoff = (datetime.now() - timedelta(days=max_age_days)).strftime("%Y-%m-%d")

    for p in pages:
        if p.page_type != "name":
            continue
        date = p.date_updated or p.date_created or ""
        if date and date < cutoff:
            issues.append(LintIssue(
                severity="info",
                check="stale-names",
                page=str(p.path),
                message=f"Name '{p.title}' last updated {date} (>{max_age_days} days ago)",
            ))
    return issues


def check_duplicate_names(pages: list[PageInfo]) -> list[LintIssue]:
    """Find name pages that may cover the same subject."""
    from concept_manager import _normalize_name

    names = [p for p in pages if p.page_type == "name"]
    seen: dict[str, list[PageInfo]] = {}

    for p in names:
        key = _normalize_name(p.title)
        seen.setdefault(key, []).append(p)

    issues = []
    for _key, group in seen.items():
        if len(group) > 1:
            paths = ", ".join(str(p.path) for p in group)
            issues.append(LintIssue(
                severity="error",
                check="duplicate-names",
                page=paths,
                message=f"Possible duplicate name pages: {paths}",
            ))
    return issues


# ---------------------------------------------------------------------------
# Full lint pass
# ---------------------------------------------------------------------------


def run_full_lint(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
    max_stale_days: int = 90,
    min_concept_mentions: int = 3,
) -> list[LintIssue]:
    """Run all lint checks and return a list of issues."""
    root = Path(os.path.expanduser(vault_root))
    pages = scan_vault(vault_root, gen_notes_dir)
    all_content = _read_all_pages(root, gen_notes_dir)

    page_stems = {p.path.stem for p in pages}
    page_titles = {p.title for p in pages}
    concept_stems = {p.path.stem for p in pages if p.page_type == "concept"}

    issues: list[LintIssue] = []
    issues.extend(check_orphans(pages, all_content))
    issues.extend(check_broken_links(all_content, page_stems, page_titles))
    issues.extend(check_stale_concepts(pages, max_stale_days))
    issues.extend(check_missing_concepts(pages, all_content, concept_stems, min_concept_mentions))
    issues.extend(check_frontmatter(pages))
    issues.extend(check_duplicate_concepts(pages))
    issues.extend(check_stale_names(pages, max_stale_days))
    issues.extend(check_duplicate_names(pages))

    return issues


def format_lint_report(issues: list[LintIssue]) -> str:
    """Format lint issues as a markdown report."""
    lines = [
        "---",
        "title: Lint Report",
        "type: lint-report",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
        "",
        "# Wiki Lint Report",
        "",
        f"> Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    if not issues:
        lines.append("All checks passed. No issues found.")
        return "\n".join(lines)

    # Group by severity
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]
    infos = [i for i in issues if i.severity == "info"]

    lines.append(f"**{len(issues)} issues found:** "
                 f"{len(errors)} errors, {len(warnings)} warnings, {len(infos)} info")
    lines.append("")

    for severity, group in [("error", errors), ("warning", warnings), ("info", infos)]:
        if not group:
            continue
        icon = {"error": "🔴", "warning": "🟡", "info": "🔵"}[severity]
        lines.append(f"## {icon} {severity.title()}s ({len(group)})")
        lines.append("")

        # Group by check
        by_check: dict[str, list[LintIssue]] = {}
        for issue in group:
            by_check.setdefault(issue.check, []).append(issue)

        for check, check_issues in by_check.items():
            lines.append(f"### {check}")
            lines.append("")
            for issue in check_issues:
                lines.append(f"- **{issue.page}**: {issue.message}")
            lines.append("")

    return "\n".join(lines)
