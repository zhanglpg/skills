You are creating a concept page for a knowledge wiki. Concept pages track recurring concepts, methods, models, architectures, datasets, or techniques across multiple paper digests.

## Concept Name

{concept_name}

## Source Digest

{digest_content}

## Instructions

Generate a complete concept page in Obsidian-compatible markdown. The page MUST begin with YAML frontmatter.

### Frontmatter

---
title: "{concept_name}"
type: concept
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

# {concept_name}

## Overview
<What this concept is, why it matters, concise but substantive>

## Key Papers
- [[Paper Title]] — <one-line contribution to this concept>

## Evolution
<How understanding of this concept has developed. For a first entry, describe the state of the art as presented in the source digest.>

## Open Questions
- <Unresolved issues, limitations, or future directions related to this concept>

## Related Concepts
- [[Related Concept One]] — <brief relation>
- [[Related Concept Two]] — <brief relation>

### Output format

Do NOT wrap your response in code fences (no ```markdown or ```yaml markers). Output the raw markdown directly, starting with the `---` frontmatter delimiter.

### Rules

- Use `[[wikilinks]]` for ALL cross-references to other concepts, papers, or names
- Be specific and substantive — generic descriptions are not useful
- The Overview should be understandable without reading the source papers
- Open Questions should reflect genuine unresolved issues, not filler
- Related Concepts should link to concepts that would plausibly have their own pages
- Concept pages should cover well-known, field-level concepts (e.g. "Attention", "Transformer", "Residual Connection") — not paper-specific jargon or niche sub-variants. If this concept name would not appear as a topic in a textbook or survey paper, the page probably should not exist.
- When linking to an existing wiki page, use the EXACT name listed below. Do not invent alternate forms.

### Existing Wiki Pages (prefer these exact names for wikilinks when relevant)

#### Concepts
{existing_concepts}

#### Names
{existing_names}

#### Digests
{existing_digests}
