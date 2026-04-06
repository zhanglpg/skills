You are creating a name page for a knowledge wiki. Name pages track notable people, datasets, models, places, and landmark papers that appear across multiple paper digests.

## Name

{name}

## Source Digest

{digest_content}

## Instructions

Generate a complete name page in Obsidian-compatible markdown. The page MUST begin with YAML frontmatter.

### Frontmatter

---
title: "{name}"
type: name
name-type: person | dataset | model | place | paper
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
- **name-type**: One of `person`, `dataset`, `model`, `place`, or `paper` — choose the best fit
- **aliases**: Include common alternate names, abbreviations, and full expansions (e.g., for "GPT-4" include "Generative Pre-trained Transformer 4"; for a person include name variations)
- **source-digests**: Wikilinks to the paper digest(s) that informed this page
- **tags**: Lowercase, hyphenated keywords from this taxonomy: `AI`, `LLM`, `transformer`, `attention`, `scaling`, `training`, `inference`, `data`, `systems`, `NLP`, `vision`, `multimodal`, `agents`, `reasoning`

### Page Sections

After the frontmatter, use exactly these sections:

# {name}

## Overview
<Who or what this is, why it matters, concise but substantive>

## Key Contributions
- [[Paper Title]] — <one-line contribution or connection>

## Timeline
<Key milestones and developments. For a first entry, describe what is known from the source digest.>

## Related Names
- [[Related Name One]] — <brief relation>
- [[Related Name Two]] — <brief relation>

## Related Concepts
- [[Related Concept One]] — <brief relation>
- [[Related Concept Two]] — <brief relation>

### Output format

Do NOT wrap your response in code fences (no ```markdown or ```yaml markers). Output the raw markdown directly, starting with the `---` frontmatter delimiter.

### Rules

- Use `[[wikilinks]]` for ALL cross-references to other names, concepts, and papers
- Be specific and substantive — generic descriptions are not useful
- The Overview should be understandable without reading the source papers
- For people: focus on their research contributions and influence on the field
- For datasets: describe what it contains, its scale, and why it became a benchmark
- For models: describe the architecture, capabilities, and impact
- For places: describe the institution/lab and its contributions to the field
- For papers: describe the key insight and lasting impact
- Name pages should only exist for independently notable subjects — those worthy of a Wikipedia article or mention in a survey paper
- When linking to an existing wiki page, use the EXACT name listed below. Do not invent alternate forms.

### Existing Wiki Pages (prefer these exact names for wikilinks when relevant)

#### Concepts
{existing_concepts}

#### Names
{existing_names}

#### Digests
{existing_digests}
