You are creating an entity page for a knowledge wiki. Entity pages track recurring concepts, methods, models, architectures, datasets, or techniques across multiple paper digests.

## Entity Name

{entity_name}

## Source Digest

{digest_content}

## Instructions

Generate a complete entity page in Obsidian-compatible markdown. The page MUST begin with YAML frontmatter.

### Frontmatter

---
title: "{entity_name}"
type: entity
aliases:
  - "Alias One"
  - "Abbreviation"
date-created: {today}
date-updated: {today}
source-digests:
  - "[[Paper Title]]"
tags:
  - relevant-tag
status: 🔗
---

**Frontmatter rules:**
- **aliases**: Include common alternate names, abbreviations, and full expansions (e.g., for "RLHF" include "Reinforcement Learning from Human Feedback")
- **source-digests**: Wikilinks to the paper digest(s) that informed this page
- **tags**: Lowercase, hyphenated keywords from this taxonomy: `AI`, `LLM`, `transformer`, `attention`, `scaling`, `training`, `inference`, `data`, `systems`, `NLP`, `vision`, `multimodal`, `agents`, `reasoning`

### Page Sections

After the frontmatter, use exactly these sections:

# {entity_name}

## Overview
<What this entity is, why it matters, concise but substantive>

## Key Papers
- [[Paper Title]] — <one-line contribution to this entity>

## Evolution
<How understanding of this entity has developed. For a first entry, describe the state of the art as presented in the source digest.>

## Open Questions
- <Unresolved issues, limitations, or future directions related to this entity>

## Related Entities
- [[Related Entity One]] — <brief relation>
- [[Related Entity Two]] — <brief relation>

### Output format

Do NOT wrap your response in code fences (no ```markdown or ```yaml markers). Output the raw markdown directly, starting with the `---` frontmatter delimiter.

### Rules

- Use `[[wikilinks]]` for ALL cross-references to other entities, papers, or concepts
- Be specific and substantive — generic descriptions are not useful
- The Overview should be understandable without reading the source papers
- Open Questions should reflect genuine unresolved issues, not filler
- Related Entities should link to concepts that would plausibly have their own pages
- Entity pages should cover well-known, field-level concepts (e.g. "Attention", "Transformer", "Residual Connection") — not paper-specific jargon or niche sub-variants. If this entity name would not appear as a topic in a textbook or survey paper, the page probably should not exist.
