"""Concept page CRUD for the knowledge wiki.

Concept pages are markdown files in gen-notes/concepts/ that accumulate
knowledge about recurring concepts, methods, models, and datasets across
multiple paper digests.
"""

from __future__ import annotations

import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Callable, Optional

from vault_index import parse_frontmatter


# ---------------------------------------------------------------------------
# Alias handling
# ---------------------------------------------------------------------------


def _normalize_name(name: str) -> str:
    """Normalize a concept name for comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load_alias_map(concept_dir: Path) -> dict[str, Path]:
    """Build a mapping from normalized alias → concept file path.

    Reads all concept files and collects aliases from frontmatter.
    """
    alias_map: dict[str, Path] = {}
    if not concept_dir.exists():
        return alias_map

    for md_file in concept_dir.glob("*.md"):
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


def find_concept_page(concept_name: str, concept_dir: str | Path) -> Optional[Path]:
    """Find an existing concept page by name or alias.

    Returns the Path to the concept file, or None if not found.
    """
    concept_dir = Path(os.path.expanduser(str(concept_dir)))
    alias_map = _load_alias_map(concept_dir)
    normalized = _normalize_name(concept_name)
    return alias_map.get(normalized)


def list_concepts(concept_dir: str | Path) -> list[dict[str, str]]:
    """List all concept pages with title and path."""
    concept_dir = Path(os.path.expanduser(str(concept_dir)))
    if not concept_dir.exists():
        return []

    concepts = []
    for md_file in sorted(concept_dir.glob("*.md")):
        try:
            text = md_file.read_text(encoding="utf-8")
        except Exception:
            continue
        fm = parse_frontmatter(text)
        title = fm.get("title", md_file.stem)
        if isinstance(title, list):
            title = title[0]
        concepts.append({"title": str(title), "path": str(md_file)})
    return concepts


# ---------------------------------------------------------------------------
# Create / Update
# ---------------------------------------------------------------------------

# Type alias for the LLM function: takes a prompt string, returns generated text
LLMFunction = Callable[[str], str]


def _sanitize_llm_output(text: str) -> str:
    """Strip code-fence wrapping and duplicated frontmatter from LLM output."""
    result = text.strip()

    # Strip outer code-fence wrapping (```markdown ... ``` or ```yaml ... ```)
    fence_pattern = re.compile(
        r"^```(?:markdown|yaml|text)?\s*\n(.*?)```\s*$",
        re.DOTALL,
    )
    m = fence_pattern.match(result)
    if m:
        result = m.group(1).strip()

    # Detect and remove duplicated frontmatter — keep only the last occurrence
    fm_blocks = list(
        re.finditer(r"^---\s*\n.*?\n---\s*\n", result, re.DOTALL | re.MULTILINE)
    )
    if len(fm_blocks) >= 2:
        result = result[fm_blocks[-1].start():]

    return result.strip()


def _sanitize_filename(name: str) -> str:
    """Convert concept name to a safe filename."""
    # Replace slashes, colons, and other problematic chars
    name = re.sub(r'[<>:"/\\|?*]', "", name)
    name = name.strip(". ")
    return name


def _load_prompt_template(template_name: str) -> str:
    """Load a prompt template from the prompts/ directory."""
    prompts_dir = Path(__file__).parent.parent / "prompts"
    template_path = prompts_dir / template_name
    if template_path.exists():
        return template_path.read_text(encoding="utf-8")
    return ""


def _format_existing_pages(existing_page_names: Optional[dict[str, list[str]]]) -> dict[str, str]:
    """Format existing page name lists for prompt substitution.

    Returns a dict with keys 'existing_concepts', 'existing_names',
    'existing_digests', each a formatted string for template injection.
    """
    if not existing_page_names:
        return {
            "existing_concepts": "(none yet)",
            "existing_names": "(none yet)",
            "existing_digests": "(none yet)",
        }
    result = {}
    for key in ("concepts", "names", "digests"):
        names = existing_page_names.get(key, [])
        if names:
            result[f"existing_{key}"] = ", ".join(names[:100])
        else:
            result[f"existing_{key}"] = "(none yet)"
    return result


def create_concept_page(
    concept_name: str,
    digest_content: str,
    concept_dir: str | Path,
    llm_fn: LLMFunction,
    existing_page_names: Optional[dict[str, list[str]]] = None,
) -> Path:
    """Create a new concept page using an LLM.

    Args:
        concept_name: Canonical name for the concept.
        digest_content: The digest that introduced this concept.
        concept_dir: Directory for concept pages.
        llm_fn: Callable that takes a prompt and returns LLM output.
        existing_page_names: Dict with keys 'concepts', 'names', 'digests',
            each a list of existing page titles for wikilink context.

    Returns:
        Path to the created concept page.
    """
    concept_dir = Path(os.path.expanduser(str(concept_dir)))
    concept_dir.mkdir(parents=True, exist_ok=True)

    template = _load_prompt_template("concept-page-prompt.md")
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = template.replace("{concept_name}", concept_name)
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
            f'title: "{concept_name}"\n'
            f"type: concept\n"
            f"aliases:\n"
            f'  - "{concept_name}"\n'
            f"date-created: {today}\n"
            f"date-updated: {today}\n"
            f"source-digests: []\n"
            f"tags: []\n"
            f"status: 🔗\n"
            f"---\n\n"
            f"# {concept_name}\n\n"
            f"{llm_output}"
        )

    filename = _sanitize_filename(concept_name) + ".md"
    file_path = concept_dir / filename
    file_path.write_text(llm_output, encoding="utf-8")
    return file_path


def update_concept_page(
    concept_path: Path,
    digest_title: str,
    digest_content: str,
    llm_fn: LLMFunction,
    existing_page_names: Optional[dict[str, list[str]]] = None,
) -> None:
    """Update an existing concept page with information from a new digest.

    Args:
        concept_path: Path to the existing concept page.
        digest_title: Title of the new paper digest.
        digest_content: Content of the new digest.
        llm_fn: Callable that takes a prompt and returns LLM output.
        existing_page_names: Dict with keys 'concepts', 'names', 'digests',
            each a list of existing page titles for wikilink context.
    """
    existing = concept_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    pages_ctx = _format_existing_pages(existing_page_names)
    existing_pages_note = (
        "\n\n## Existing Wiki Pages (use these exact names for wikilinks)\n\n"
        f"Concepts: {pages_ctx['existing_concepts']}\n"
        f"Names: {pages_ctx['existing_names']}\n"
        f"Digests: {pages_ctx['existing_digests']}\n"
    )

    prompt = (
        "You are updating a concept page in a knowledge wiki. "
        "The concept page already exists with accumulated knowledge. "
        "A new paper has been digested that is relevant to this concept.\n\n"
        "## Existing Concept Page\n\n"
        f"{existing}\n\n"
        "## New Paper Digest\n\n"
        f"{digest_content}\n\n"
        f"{existing_pages_note}\n"
        "## Instructions\n\n"
        "Update the concept page to incorporate insights from the new paper. "
        "Specifically:\n"
        "1. Update the Overview if the new paper changes understanding\n"
        f'2. Add `[[{digest_title}]]` to Key Papers with a one-line contribution note\n'
        "3. Update Evolution if this represents a shift or advancement, or if it is a predecessor to previous papers that forms lineage of the development\n"
        "4. Update Open Questions — add new ones, mark resolved ones\n"
        "5. Add any new Related Concepts as wikilinks\n"
        f"6. Update date-updated to {today} in the frontmatter\n"
        f'7. Add `"[[{digest_title}]]"` to source-digests in frontmatter\n'
        "\n"
        "When adding wikilinks, use the EXACT names from the existing wiki "
        "pages list above when relevant. Do not invent alternate forms.\n\n"
        "Return the COMPLETE updated concept page including frontmatter. "
        "Preserve the existing structure and content — only add/modify "
        "what the new paper warrants."
    )

    updated = _sanitize_llm_output(llm_fn(prompt))

    # Sanity check: only write if it looks like valid markdown with frontmatter
    if updated.strip().startswith("---"):
        concept_path.write_text(updated, encoding="utf-8")
    else:
        # Fallback: just append a reference to the new paper
        append_text = (
            f"\n\n### Update ({today})\n\n"
            f"New paper ingested: [[{digest_title}]]\n\n"
            f"*Auto-update via wiki-manager.*\n"
        )
        with open(concept_path, "a", encoding="utf-8") as f:
            f.write(append_text)


# ---------------------------------------------------------------------------
# Concept extraction from digest
# ---------------------------------------------------------------------------


def extract_concepts_from_digest(
    digest_content: str,
    existing_concepts: list[str],
    llm_fn: LLMFunction,
    max_concepts: int = 8,
) -> list[str]:
    """Use an LLM to extract key concepts from a paper digest.

    Args:
        digest_content: The full markdown content of the digest.
        existing_concepts: Names of concepts that already have pages.
        llm_fn: Callable that takes a prompt and returns LLM output.
        max_concepts: Maximum number of concepts to extract.

    Returns:
        List of concept names (preferring existing names where applicable).
    """
    existing_list = "\n".join(f"- {e}" for e in existing_concepts) if existing_concepts else "*None yet*"

    prompt = (
        "Extract the key concepts from this paper digest. "
        "Concepts are recurring concepts, methods, models, architectures, "
        "datasets, or techniques that would benefit from having their own "
        "wiki page.\n\n"
        "## Paper Digest\n\n"
        f"{digest_content}\n\n"
        "## Existing Concept Pages\n\n"
        f"{existing_list}\n\n"
        "## Instructions\n\n"
        f"Return a JSON array of {max_concepts} or fewer concept names. "
        "If a concept matches an existing page (same concept, different name), "
        "use the EXISTING name. For new concepts, use the most canonical/common "
        "name.\n\n"
        "**CRITICAL — Right level of abstraction:** Extract concepts that a "
        "practitioner in the field would independently recognize and search "
        "for — NOT niche terms coined by this specific paper. If the paper "
        "introduces a specialized variant or sub-concept (e.g. 'attention "
        "residues', 'gated linear attention', 'time-depth duality'), extract "
        "the well-known parent concept instead (e.g. 'Attention', 'Linear "
        "Attention', 'Duality'). Ask: would this concept name appear as a "
        "topic in a textbook or survey paper? If not, go one level up. Only "
        "use paper-specific terms when they have already become widely adopted "
        "(e.g. 'LoRA', 'FlashAttention', 'Chain-of-Thought').\n\n"
        "Examples of good concepts: 'Transformer', 'RLHF', 'Chain-of-Thought', "
        "'Scaling Laws', 'FlashAttention', 'BERT'\n"
        "Examples of BAD concepts (too specific): 'attention residues', "
        "'residue connection', 'time-depth duality', 'grokfast'\n\n"
        "Return ONLY the JSON array, no other text.\n"
        'Example: ["Transformer", "Attention", "BERT"]'
    )

    result = llm_fn(prompt)

    # Parse JSON array from response
    try:
        # Find JSON array in the response
        match = re.search(r"\[.*?\]", result, re.DOTALL)
        if match:
            concepts = json.loads(match.group())
            return [str(e).strip() for e in concepts if e][:max_concepts]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: try to parse line-by-line
    concepts = []
    for line in result.strip().split("\n"):
        line = line.strip().strip("-*•").strip().strip('"').strip("'")
        if line and not line.startswith("[") and not line.startswith("{"):
            concepts.append(line)

    return concepts[:max_concepts]
