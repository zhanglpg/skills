"""Entity page CRUD for the knowledge wiki.

Entity pages are markdown files in gen-notes/entities/ that accumulate
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
    """Normalize an entity name for comparison."""
    return re.sub(r"[^a-z0-9]", "", name.lower())


def _load_alias_map(entity_dir: Path) -> dict[str, Path]:
    """Build a mapping from normalized alias → entity file path.

    Reads all entity files and collects aliases from frontmatter.
    """
    alias_map: dict[str, Path] = {}
    if not entity_dir.exists():
        return alias_map

    for md_file in entity_dir.glob("*.md"):
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


def find_entity_page(entity_name: str, entity_dir: str | Path) -> Optional[Path]:
    """Find an existing entity page by name or alias.

    Returns the Path to the entity file, or None if not found.
    """
    entity_dir = Path(os.path.expanduser(str(entity_dir)))
    alias_map = _load_alias_map(entity_dir)
    normalized = _normalize_name(entity_name)
    return alias_map.get(normalized)


def list_entities(entity_dir: str | Path) -> list[dict[str, str]]:
    """List all entity pages with title and path."""
    entity_dir = Path(os.path.expanduser(str(entity_dir)))
    if not entity_dir.exists():
        return []

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
        entities.append({"title": str(title), "path": str(md_file)})
    return entities


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
    """Convert entity name to a safe filename."""
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


def create_entity_page(
    entity_name: str,
    digest_content: str,
    entity_dir: str | Path,
    llm_fn: LLMFunction,
) -> Path:
    """Create a new entity page using an LLM.

    Args:
        entity_name: Canonical name for the entity.
        digest_content: The digest that introduced this entity.
        entity_dir: Directory for entity pages.
        llm_fn: Callable that takes a prompt and returns LLM output.

    Returns:
        Path to the created entity page.
    """
    entity_dir = Path(os.path.expanduser(str(entity_dir)))
    entity_dir.mkdir(parents=True, exist_ok=True)

    template = _load_prompt_template("entity-page-prompt.md")
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = template.replace("{entity_name}", entity_name)
    prompt = prompt.replace("{digest_content}", digest_content)
    prompt = prompt.replace("{today}", today)

    llm_output = _sanitize_llm_output(llm_fn(prompt))

    # If the LLM output doesn't start with frontmatter, wrap it
    if not llm_output.strip().startswith("---"):
        llm_output = (
            f"---\n"
            f'title: "{entity_name}"\n'
            f"type: entity\n"
            f"aliases:\n"
            f'  - "{entity_name}"\n'
            f"date-created: {today}\n"
            f"date-updated: {today}\n"
            f"source-digests: []\n"
            f"tags: []\n"
            f"status: 🔗\n"
            f"---\n\n"
            f"# {entity_name}\n\n"
            f"{llm_output}"
        )

    filename = _sanitize_filename(entity_name) + ".md"
    file_path = entity_dir / filename
    file_path.write_text(llm_output, encoding="utf-8")
    return file_path


def update_entity_page(
    entity_path: Path,
    digest_title: str,
    digest_content: str,
    llm_fn: LLMFunction,
) -> None:
    """Update an existing entity page with information from a new digest.

    Args:
        entity_path: Path to the existing entity page.
        digest_title: Title of the new paper digest.
        digest_content: Content of the new digest.
        llm_fn: Callable that takes a prompt and returns LLM output.
    """
    existing = entity_path.read_text(encoding="utf-8")
    today = datetime.now().strftime("%Y-%m-%d")

    prompt = (
        "You are updating an entity page in a knowledge wiki. "
        "The entity page already exists with accumulated knowledge. "
        "A new paper has been digested that is relevant to this entity.\n\n"
        "## Existing Entity Page\n\n"
        f"{existing}\n\n"
        "## New Paper Digest\n\n"
        f"{digest_content}\n\n"
        "## Instructions\n\n"
        "Update the entity page to incorporate insights from the new paper. "
        "Specifically:\n"
        "1. Update the Overview if the new paper changes understanding\n"
        f'2. Add `[[{digest_title}]]` to Key Papers with a one-line contribution note\n'
        "3. Update Evolution if this represents a shift or advancement, or if it is a predecessor to previous papers that forms lineage of the development\n"
        "4. Update Open Questions — add new ones, mark resolved ones\n"
        "5. Add any new Related Entities as wikilinks\n"
        f"6. Update date-updated to {today} in the frontmatter\n"
        f'7. Add `"[[{digest_title}]]"` to source-digests in frontmatter\n'
        "\n"
        "Return the COMPLETE updated entity page including frontmatter. "
        "Preserve the existing structure and content — only add/modify "
        "what the new paper warrants."
    )

    updated = _sanitize_llm_output(llm_fn(prompt))

    # Sanity check: only write if it looks like valid markdown with frontmatter
    if updated.strip().startswith("---"):
        entity_path.write_text(updated, encoding="utf-8")
    else:
        # Fallback: just append a reference to the new paper
        append_text = (
            f"\n\n### Update ({today})\n\n"
            f"New paper ingested: [[{digest_title}]]\n\n"
            f"*Auto-update via wiki-manager.*\n"
        )
        with open(entity_path, "a", encoding="utf-8") as f:
            f.write(append_text)


# ---------------------------------------------------------------------------
# Entity extraction from digest
# ---------------------------------------------------------------------------


def extract_entities_from_digest(
    digest_content: str,
    existing_entities: list[str],
    llm_fn: LLMFunction,
    max_entities: int = 8,
) -> list[str]:
    """Use an LLM to extract key entities from a paper digest.

    Args:
        digest_content: The full markdown content of the digest.
        existing_entities: Names of entities that already have pages.
        llm_fn: Callable that takes a prompt and returns LLM output.
        max_entities: Maximum number of entities to extract.

    Returns:
        List of entity names (preferring existing names where applicable).
    """
    existing_list = "\n".join(f"- {e}" for e in existing_entities) if existing_entities else "*None yet*"

    prompt = (
        "Extract the key entities from this paper digest. "
        "Entities are recurring concepts, methods, models, architectures, "
        "datasets, or techniques that would benefit from having their own "
        "wiki page.\n\n"
        "## Paper Digest\n\n"
        f"{digest_content}\n\n"
        "## Existing Entity Pages\n\n"
        f"{existing_list}\n\n"
        "## Instructions\n\n"
        f"Return a JSON array of {max_entities} or fewer entity names. "
        "If an entity matches an existing page (same concept, different name), "
        "use the EXISTING name. For new entities, use the most canonical/common "
        "name.\n\n"
        "**CRITICAL — Right level of abstraction:** Extract entities that a "
        "practitioner in the field would independently recognize and search "
        "for — NOT niche terms coined by this specific paper. If the paper "
        "introduces a specialized variant or sub-concept (e.g. 'attention "
        "residues', 'gated linear attention', 'time-depth duality'), extract "
        "the well-known parent concept instead (e.g. 'Attention', 'Linear "
        "Attention', 'Duality'). Ask: would this entity name appear as a "
        "topic in a textbook or survey paper? If not, go one level up. Only "
        "use paper-specific terms when they have already become widely adopted "
        "(e.g. 'LoRA', 'FlashAttention', 'Chain-of-Thought').\n\n"
        "Examples of good entities: 'Transformer', 'RLHF', 'Chain-of-Thought', "
        "'Scaling Laws', 'FlashAttention', 'BERT'\n"
        "Examples of BAD entities (too specific): 'attention residues', "
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
            entities = json.loads(match.group())
            return [str(e).strip() for e in entities if e][:max_entities]
    except (json.JSONDecodeError, ValueError):
        pass

    # Fallback: try to parse line-by-line
    entities = []
    for line in result.strip().split("\n"):
        line = line.strip().strip("-*•").strip().strip('"').strip("'")
        if line and not line.startswith("[") and not line.startswith("{"):
            entities.append(line)

    return entities[:max_entities]
