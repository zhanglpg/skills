"""LLM-powered AI compile — semantic analysis across pages."""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from vault_index import PageInfo, scan_vault
from lint_checker import _read_all_pages


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------


@dataclass
class CompileFinding:
    """A single finding from the LLM-powered compile."""

    category: str  # contradiction, stale-claim, missing-xref,
    #                concept-needs-page, data-gap, research-question
    severity: str  # "warning" or "info"
    pages: list[str] = field(default_factory=list)
    description: str = ""


# Map categories to default severities
_CATEGORY_SEVERITY = {
    "contradiction": "warning",
    "stale-claim": "warning",
    "missing-xref": "info",
    "concept-needs-page": "info",
    "data-gap": "info",
    "research-question": "info",
}

_CATEGORY_LABELS = {
    "contradiction": "Contradictions Between Pages",
    "stale-claim": "Stale or Superseded Claims",
    "missing-xref": "Missing Cross-References",
    "concept-needs-page": "Concepts Needing Pages",
    "data-gap": "Data Gaps",
    "research-question": "Research Questions to Investigate",
}


# ---------------------------------------------------------------------------
# Batching — deterministic logic
# ---------------------------------------------------------------------------


def build_page_batches(
    pages: list[PageInfo],
    all_content: dict[Path, str],
    max_batch_size: int = 15,
    max_chars_per_page: int = 4000,
) -> list[dict]:
    """Group pages into batches for LLM analysis.

    Groups by primary tag (first tag), splits large groups, merges small ones.
    Returns a list of batch dicts::

        {"label": str, "pages": list[PageInfo], "contents": dict[str, str]}

    The ``contents`` dict maps ``page.path.stem`` to truncated page text.
    """
    # Group by primary tag
    tag_groups: dict[str, list[PageInfo]] = {}
    for p in pages:
        tag = p.tags[0] if p.tags else "untagged"
        tag_groups.setdefault(tag, []).append(p)

    # Build batches: split large groups, collect small ones for merging
    batches: list[dict] = []
    assorted_pages: list[PageInfo] = []

    for tag, group in sorted(tag_groups.items()):
        if len(group) < 3:
            assorted_pages.extend(group)
            continue
        # Split into chunks of max_batch_size
        for i in range(0, len(group), max_batch_size):
            chunk = group[i : i + max_batch_size]
            suffix = f" (part {i // max_batch_size + 1})" if len(group) > max_batch_size else ""
            batches.append({
                "label": f"{tag}{suffix}",
                "pages": chunk,
                "contents": _truncated_contents(chunk, all_content, max_chars_per_page),
            })

    # Merge assorted small groups into batches
    if assorted_pages:
        for i in range(0, len(assorted_pages), max_batch_size):
            chunk = assorted_pages[i : i + max_batch_size]
            batches.append({
                "label": "assorted",
                "pages": chunk,
                "contents": _truncated_contents(chunk, all_content, max_chars_per_page),
            })

    return batches


def _truncated_contents(
    pages: list[PageInfo],
    all_content: dict[Path, str],
    max_chars: int,
) -> dict[str, str]:
    """Build a stem→content dict with truncated page text."""
    result: dict[str, str] = {}
    for p in pages:
        content = all_content.get(p.path, "")
        if len(content) > max_chars:
            content = content[:max_chars] + "\n\n[... truncated ...]"
        result[p.path.stem] = content
    return result


# ---------------------------------------------------------------------------
# Prompt building — deterministic logic
# ---------------------------------------------------------------------------


def build_batch_prompt(batch: dict, prompt_template: str) -> str:
    """Inject page contents into the cross-page analysis prompt template."""
    parts: list[str] = []
    for p in batch["pages"]:
        stem = p.path.stem
        tags_str = ", ".join(p.tags) if p.tags else "none"
        content = batch["contents"].get(stem, "")
        parts.append(
            f"### {p.title} ({p.page_type})\n"
            f"Tags: {tags_str}\n"
            f"Path: {stem}\n\n"
            f"{content}\n\n---"
        )
    pages_content = "\n\n".join(parts)
    return prompt_template.replace("{pages_content}", pages_content)


def build_gap_prompt(
    pages: list[PageInfo],
    prompt_template: str,
    schema_text: str,
) -> str:
    """Build the wiki-wide gap analysis prompt with compact page summaries."""
    lines: list[str] = []
    for p in sorted(pages, key=lambda p: p.title.lower()):
        tags_str = ", ".join(p.tags) if p.tags else "none"
        summary = p.summary[:150] if p.summary else "(no summary)"
        lines.append(f"- {p.title} ({p.page_type}) [{tags_str}] — {summary}")
    wiki_summary = "\n".join(lines)
    result = prompt_template.replace("{wiki_summary}", wiki_summary)
    result = result.replace("{schema_excerpt}", schema_text)
    return result


# ---------------------------------------------------------------------------
# LLM output parsing — deterministic logic
# ---------------------------------------------------------------------------


def parse_llm_findings(llm_response: str) -> list[CompileFinding]:
    """Parse LLM response into CompileFinding objects.

    Expects a JSON array of objects with ``category``, ``pages``, and
    ``description`` keys.  Falls back gracefully on malformed output.
    """
    if not llm_response or not llm_response.strip():
        return []

    # Try direct JSON parse
    text = llm_response.strip()
    findings: list[CompileFinding] = []

    parsed = _try_parse_json_array(text)
    if parsed is None:
        # Try extracting JSON array from surrounding text
        match = re.search(r"\[.*\]", text, re.DOTALL)
        if match:
            parsed = _try_parse_json_array(match.group(0))

    if parsed is None:
        return []

    for item in parsed:
        if not isinstance(item, dict):
            continue
        category = str(item.get("category", "")).strip()
        if not category:
            continue
        pages = item.get("pages", [])
        if isinstance(pages, str):
            pages = [pages]
        pages = [str(p) for p in pages]
        description = str(item.get("description", ""))
        severity = _CATEGORY_SEVERITY.get(category, "info")
        findings.append(CompileFinding(
            category=category,
            severity=severity,
            pages=pages,
            description=description,
        ))

    return findings


def _try_parse_json_array(text: str) -> list | None:
    """Attempt to parse text as a JSON array, return None on failure."""
    try:
        result = json.loads(text)
        if isinstance(result, list):
            return result
    except (json.JSONDecodeError, ValueError):
        pass
    return None


# ---------------------------------------------------------------------------
# Report formatting
# ---------------------------------------------------------------------------


def format_compile_report(
    findings: list[CompileFinding],
    lint_issues: list | None = None,
) -> str:
    """Format compile findings and lint issues into a unified markdown report."""
    lines: list[str] = [
        "---",
        "title: Wiki AI Compile",
        "type: compile-report",
        f"date: {datetime.now().strftime('%Y-%m-%d')}",
        "---",
        "",
        "# Wiki AI Compile",
        "",
        f"> Generated {datetime.now().strftime('%Y-%m-%d %H:%M')}",
        "",
    ]

    # Summary counts
    n_lint = len(lint_issues) if lint_issues else 0
    n_findings = len(findings)
    lines.append(f"**{n_lint} structural issues, {n_findings} semantic findings**")
    lines.append("")

    # --- Section 1: Structural Issues (from deterministic lint) ---
    lines.append("## Structural Issues")
    lines.append("")
    if not lint_issues:
        lines.append("All structural checks passed.")
        lines.append("")
    else:
        from lint_checker import LintIssue
        by_severity: dict[str, list] = {}
        for issue in lint_issues:
            by_severity.setdefault(issue.severity, []).append(issue)

        for severity in ("error", "warning", "info"):
            group = by_severity.get(severity, [])
            if not group:
                continue
            icon = {"error": "\U0001f534", "warning": "\U0001f7e1", "info": "\U0001f535"}[severity]
            lines.append(f"### {icon} {severity.title()}s ({len(group)})")
            lines.append("")
            for issue in group:
                lines.append(f"- **{issue.page}**: {issue.message}")
            lines.append("")

    # --- Section 2: Semantic Findings (from LLM) ---
    lines.append("## Semantic Findings")
    lines.append("")
    if not findings:
        lines.append("No semantic issues found.")
        lines.append("")
    else:
        # Group by category
        by_category: dict[str, list[CompileFinding]] = {}
        for f in findings:
            by_category.setdefault(f.category, []).append(f)

        for category in (
            "contradiction",
            "stale-claim",
            "missing-xref",
            "concept-needs-page",
            "data-gap",
            "research-question",
        ):
            group = by_category.pop(category, [])
            if not group:
                continue
            label = _CATEGORY_LABELS.get(category, category)
            lines.append(f"### {label}")
            lines.append("")
            for f in group:
                pages_str = ", ".join(f"[[{p}]]" for p in f.pages) if f.pages else ""
                if pages_str:
                    lines.append(f"- **{pages_str}**: {f.description}")
                else:
                    lines.append(f"- {f.description}")
            lines.append("")

        # Any remaining unexpected categories
        for category, group in by_category.items():
            label = _CATEGORY_LABELS.get(category, category)
            lines.append(f"### {label}")
            lines.append("")
            for f in group:
                pages_str = ", ".join(f"[[{p}]]" for p in f.pages) if f.pages else ""
                if pages_str:
                    lines.append(f"- **{pages_str}**: {f.description}")
                else:
                    lines.append(f"- {f.description}")
            lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------


def run_compile(
    vault_root: str,
    gen_notes_dir: str = "gen-notes",
    llm_fn: Callable[[str], str] | None = None,
    max_batch_size: int = 15,
    max_chars_per_page: int = 4000,
    logger=None,
) -> list[CompileFinding]:
    """Run the full LLM-powered compile and return findings.

    1. Load vault and read all page content
    2. Build page batches clustered by tag
    3. Run cross-page analysis on each batch
    4. Run gap analysis across the whole wiki
    5. Return combined findings
    """
    if llm_fn is None:
        if logger:
            logger.warning("No LLM function provided — skipping semantic compile")
        return []

    root = Path(os.path.expanduser(vault_root))
    pages = scan_vault(vault_root, gen_notes_dir)
    all_content = _read_all_pages(root, gen_notes_dir)

    if not pages:
        if logger:
            logger.info("No pages found in vault — nothing to compile")
        return []

    # Load prompt templates
    prompt_dir = Path(__file__).resolve().parent.parent / "prompts"
    cross_page_template = _load_prompt(prompt_dir / "compile-cross-page-prompt.md")
    gap_template = _load_prompt(prompt_dir / "compile-gap-analysis-prompt.md")
    schema_text = _load_prompt(
        Path(__file__).resolve().parent.parent / "references" / "schema.md"
    )

    all_findings: list[CompileFinding] = []

    # --- Cross-page analysis (per batch) ---
    batches = build_page_batches(pages, all_content, max_batch_size, max_chars_per_page)

    for i, batch in enumerate(batches, 1):
        if logger:
            logger.info(
                f"Compiling batch {i}/{len(batches)}: {batch['label']} "
                f"({len(batch['pages'])} pages)"
            )
        prompt = build_batch_prompt(batch, cross_page_template)
        try:
            response = llm_fn(prompt)
            findings = parse_llm_findings(response)
            all_findings.extend(findings)
        except Exception as e:
            if logger:
                logger.error(f"LLM call failed for batch {batch['label']}: {e}")

    # --- Gap analysis (wiki-wide, once) ---
    if logger:
        logger.info("Running wiki-wide gap analysis")
    gap_prompt = build_gap_prompt(pages, gap_template, schema_text)
    try:
        response = llm_fn(gap_prompt)
        findings = parse_llm_findings(response)
        all_findings.extend(findings)
    except Exception as e:
        if logger:
            logger.error(f"LLM call failed for gap analysis: {e}")

    if logger:
        logger.info(f"Compile complete: {len(all_findings)} findings")

    return all_findings


def _load_prompt(path: Path) -> str:
    """Load a prompt template file, return empty string if missing."""
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return ""
