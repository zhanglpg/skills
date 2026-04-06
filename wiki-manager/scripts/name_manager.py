"""Name page CRUD for the knowledge wiki.

Name pages are markdown files in gen-notes/names/ that track notable
people, datasets, models, places, and landmark papers across multiple
paper digests.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from vault_index import parse_frontmatter
from concept_manager import _normalize_name, _sanitize_llm_output, _sanitize_filename, _format_existing_pages


# ---------------------------------------------------------------------------
# Alias handling
# ---------------------------------------------------------------------------


def _load_name_alias_map(names_dir: Path) -> dict[str, Path]:
    """Build a mapping from normalized alias → name file path.

    Reads all name files and collects aliases from frontmatter.
    """
    alias_map: dict[str, Path] = {}
    if not names_dir.exists():
        return alias_map

    for md_file in names_dir.glob("*.md"):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = parse_frontmatter(text)

        # Map the filename stem
        alias_map[_normalize_name(md_file.stem)] = md_file

        # Map frontmatter title
        title = fm.get("title", "")
        if isinstance(title, str) and title:
            alias_map[_normalize_name(title)] = md_file

        # Map explicit aliases
        aliases = fm.get("aliases", [])
        if isinstance(aliases, str):
            aliases = [aliases]
        for alias in aliases:
            alias_map[_normalize_name(str(alias))] = md_file

    return alias_map


# ---------------------------------------------------------------------------
# Lookup
# ---------------------------------------------------------------------------


def find_name_page(name: str, names_dir: str | Path) -> Optional[Path]:
    """Find an existing name page by name or alias.

    Returns the Path to the name file, or None if not found.
    """
    names_dir = Path(os.path.expanduser(str(names_dir)))
    alias_map = _load_name_alias_map(names_dir)
    normalized = _normalize_name(name)
    return alias_map.get(normalized)


def list_names(names_dir: str | Path) -> list[dict[str, str]]:
    """List all name pages with title and path."""
    names_dir = Path(os.path.expanduser(str(names_dir)))
    if not names_dir.exists():
        return []

    names = []
    for md_file in sorted(names_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = parse_frontmatter(text)
        title = fm.get("title", md_file.stem)
        if isinstance(title, list):
            title = title[0]
        names.append({"title": str(title), "path": str(md_file)})
    return names


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

# Type alias for the LLM function: takes a prompt string, returns generated text
LLMFunction = Callable[[str], str]


def _load_prompt_template(template_name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    template_path = prompts_dir / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return ""


def create_name_page(
    name: str,
    digest_content: str,
    names_dir: str | Path,
    llm_fn: LLMFunction,
    existing_page_names: Optional[dict[str, list[str]]] = None,
) -> Path:
    """Create a new name page using an LLM.

    Args:
        name: Canonical name for the subject.
        digest_content: The digest that introduced this name.
        names_dir: Directory for name pages.
        llm_fn: Callable that takes a prompt and returns LLM output.
        existing_page_names: Dict with keys 'concepts', 'names', 'digests',
            each a list of existing page titles for wikilink context.

    Returns:
        Path to the created name page.
    """
    names_dir = Path(os.path.expanduser(str(names_dir)))
    names_dir.mkdir(parents=True, exist_ok=True)

    template = _load_prompt_template("name-page-prompt.md")
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = template.replace("{name}", name)
    prompt = prompt.replace("{digest_content}", digest_content)
    prompt = prompt.replace("{today}", today)

    pages_ctx = _format_existing_pages(existing_page_names)
    for key, value in pages_ctx.items():
        prompt = prompt.replace("{" + key + "}", value)

    llm_output = _sanitize_llm_output(llm_fn(prompt))

    # If the LLM output doesn't start with frontmatter, wrap it
    if not llm_output.strip().startswith("---"):
        llm_output = (
            f"---\n"
            f'title: "{name}"\n'
            f"type: name\n"
            f"name-type: unknown\n"
            f"aliases:\n"
            f'  - "{name}"\n'
            f"date-created: {today}\n"
            f"date-updated: {today}\n"
            f"source-digests: []\n"
            f"tags: []\n"
            f"status: 🔗\n"
            f"---\n\n"
            f"# {name}\n\n"
            f"{llm_output}"
        )

    filename = _sanitize_filename(name) + ".md"
    file_path = names_dir / filename
    file_path.write_text(llm_output, encoding="utf-8")
    return file_path


def update_name_page(
    name_path: Path,
    digest_title: str,
    digest_content: str,
    llm_fn: LLMFunction,
    existing_page_names: Optional[dict[str, list[str]]] = None,
) -> None:
    """Update an existing name page with information from a new digest.

    Args:
        name_path: Path to the existing name page.
        digest_title: Title of the new paper digest.
        digest_content: Content of the new digest.
        llm_fn: Callable that takes a prompt and returns LLM output.
        existing_page_names: Dict with keys 'concepts', 'names', 'digests',
            each a list of existing page titles for wikilink context.
    """
    existing = name_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    pages_ctx = _format_existing_pages(existing_page_names)
    existing_pages_note = (
        "\n\n## Existing Wiki Pages (use these exact names for wikilinks)\n\n"
        f"Concepts: {pages_ctx['existing_concepts']}\n"
        f"Names: {pages_ctx['existing_names']}\n"
        f"Digests: {pages_ctx['existing_digests']}\n"
    )

    prompt = (
        "You are updating a name page in a knowledge wiki. "
        "The name page already exists with accumulated knowledge. "
        "A new paper has been digested that is relevant to this subject.\n\n"
        "## Existing Name Page\n\n"
        f"{existing}\n\n"
        "## New Paper Digest\n\n"
        f"{digest_content}\n\n"
        f"{existing_pages_note}\n"
        "## Instructions\n\n"
        "Update the name page to incorporate insights from the new paper. "
        "Specifically:\n"
        "1. Update the Overview if the new paper changes understanding\n"
        f'2. Add `[[{digest_title}]]` to Key Contributions with a one-line note\n'
        "3. Update Timeline if this represents a new milestone\n"
        "4. Add any new Related Names or Related Concepts as wikilinks\n"
        f"5. Update date-updated to {today} in the frontmatter\n"
        f'6. Add `"[[{digest_title}]]"` to source-digests in frontmatter\n'
        "\n"
        "When adding wikilinks, use the EXACT names from the existing wiki "
        "pages list above when relevant. Do not invent alternate forms.\n\n"
        "Return the COMPLETE updated name page including frontmatter. "
        "Preserve the existing structure and content — only add/modify "
        "what the new paper warrants."
    )

    updated = _sanitize_llm_output(llm_fn(prompt))

    # Sanity check: only write if it looks like valid markdown with frontmatter
    if updated.strip().startswith("---"):
        name_path.write_text(updated, encoding="utf-8")
    else:
        # Fallback: just append a reference to the new paper
        append_text = (
            f"\n\n### Update ({today})\n\n"
            f"New paper ingested: [[{digest_title}]]\n\n"
            f"*Auto-update via wiki-manager.*\n"
        )
        with open(name_path, "a", encoding="utf-8") as f:
            f.write(append_text)


# ---------------------------------------------------------------------------
# Name extraction from digest
# ---------------------------------------------------------------------------


def extract_names_from_digest(
    digest_content: str,
    existing_names: list[str],
    llm_fn: LLMFunction,
    max_names: int = 5,
) -> list[str]:
    """Use an LLM to extract notable proper names from a paper digest.

    Args:
        digest_content: The full markdown content of the digest.
        existing_names: Names that already have pages.
        llm_fn: Callable that takes a prompt and returns LLM output.
        max_names: Maximum number of names to extract.

    Returns:
        List of names (preferring existing names where applicable).
    """
    existing_list = "\n".join(f"- {n}" for n in existing_names) if existing_names else "*None yet*"

    prompt = (
        "Extract the most notable proper names from this paper digest. "
        "Names include: people, datasets, models, places (institutions/labs), "
        "and landmark papers that are most related to the digested paper.\n\n"
        "## Paper Digest\n\n"
        f"{digest_content}\n\n"
        "## Existing Name Pages\n\n"
        f"{existing_list}\n\n"
        "## Instructions\n\n"
        f"Return a JSON array of {max_names} or fewer notable proper names. "
        "If a name matches an existing page (same subject, different form), "
        "use the EXISTING name. For new names, use the most canonical/common "
        "form.\n\n"
        "**CRITICAL — Notability criteria:** Only extract names that are "
        "independently notable and well-known beyond this single paper. "
        "Each name should be worthy of a survey paper or a public Wikipedia "
        "page itself.\n\n"
        "Good examples: 'Geoffrey Hinton', 'ImageNet', 'GPT-4', "
        "'Stanford University', 'Attention Is All You Need'\n"
        "Bad examples: a first-time PhD student, a minor internal benchmark, "
        "a niche university lab\n\n"
        "Return ONLY the JSON array, no other text.\n"
        'Example: ["Geoffrey Hinton", "ImageNet", "GPT-4"]'
    )

    result = llm_fn(prompt)

    # Parse JSON array from response
    try:
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if match:
            names = json.loads(match.group())
            return [str(n).strip() for n in names if n][:max_names]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: try to parse line-by-line
    names = []
    for line in result.strip().split("\n"):
        line = line.strip().strip("-*•").strip().strip('"').strip("'")
        if line and not line.startswith("[") and not line.startswith("{"):
            names.append(line)

    return names[:max_names]
