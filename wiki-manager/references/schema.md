# Wiki Schema

This document codifies the conventions for the knowledge wiki. Folder paths below use `<gen_notes_dir>` as a placeholder — see `config.json` for the actual value (default: `gen-notes`). It serves as both human documentation and injectable LLM context.

## Contents
- Page Types (Digest, Concept, Name, Synthesis, Comparison)
- Frontmatter Conventions
- Wikilink Conventions
- Tag Taxonomy
- Status Conventions
- Index Conventions

## Page Types

### Digest
- **Directory:** `<gen_notes_dir>/digests/`
- **Created by:** paper-digest, paper-summarizer
- **Required frontmatter:** `title`, `authors`, `year`, `tags`, `categories`, `related`, `source`, `digested`, `status`
- **Sections:** TL;DR or Main Idea, Key Ideas/Conclusions, What's Novel, Method, Results, Limitations, Connections

### Concept
- **Directory:** `<gen_notes_dir>/concepts/`
- **Created by:** wiki-manager ingest
- **Required frontmatter:** `title`, `type: concept`, `aliases`, `date-created`, `date-updated`, `source-digests`, `tags`
- **Sections:** Overview, Key Papers, Evolution, Open Questions, Related Concepts
- **Naming:** Use the canonical concept name (e.g., `Transformer.md`, `RLHF.md`)

### Name
- **Directory:** `<gen_notes_dir>/names/`
- **Created by:** wiki-manager ingest
- **Required frontmatter:** `title`, `type: name`, `aliases`, `date-created`, `date-updated`, `source-digests`, `tags`, `name-type`
- **Sections:** Overview, Key Contributions, Timeline, Related Names, Related Concepts
- **Naming:** Use the canonical name (e.g., `Geoffrey Hinton.md`, `ImageNet.md`, `GPT-4.md`)
- **name-type values:** `person`, `dataset`, `model`, `place`, `paper`

### Synthesis
- **Directory:** `<gen_notes_dir>/syntheses/`
- **Created by:** wiki-query or manual
- **Required frontmatter:** `title`, `type: synthesis`, `date-created`, `sources`, `tags`
- **Sections:** Query (original question), Answer, Sources Used

### Comparison
- **Directory:** `<gen_notes_dir>/comparisons/`
- **Created by:** wiki-query or manual
- **Required frontmatter:** `title`, `type: comparison`, `date-created`, `sources`, `tags`
- **Sections:** Overview, Side-by-Side Comparison (table), Key Differences, Key Similarities, Verdict/Takeaway

## Frontmatter Conventions

All pages MUST have YAML frontmatter delimited by `---`. Common fields:

```yaml
---
title: "Page Title"
type: digest | concept | name | synthesis
date-created: YYYY-MM-DD
date-updated: YYYY-MM-DD
tags:
  - tag-one
  - tag-two
---
```

Concept pages additionally include:
```yaml
aliases:
  - "Alternate Name"
  - "Abbreviation"
source-digests:
  - "[[Paper Title One]]"
  - "[[Paper Title Two]]"
```

Name pages additionally include:
```yaml
name-type: person | dataset | model | place | paper
aliases:
  - "Alternate Name"
source-digests:
  - "[[Paper Title One]]"
```

## Wikilink Conventions

- Always use `[[Page Title]]` for cross-references
- Concept references: `[[Transformer]]`, `[[RLHF]]`
- Name references: `[[Geoffrey Hinton]]`, `[[ImageNet]]`
- Digest references: `[[Attention Is All You Need]]`
- Prefer exact page titles over approximate names
- The Connections section of every page should link to related pages

## Tag Taxonomy

Match existing vault categories:
- **AI/ML:** `AI`, `LLM`, `transformer`, `attention`, `scaling`, `training`, `inference`, `data`
- **Systems:** `systems`, `hardware`, `distributed`, `optimization`
- **Domain:** `NLP`, `vision`, `multimodal`, `agents`, `reasoning`
- **Meta:** `management`, `leadership`, `engineering`, `philosophy`, `history`

## Status Conventions

- `📥` — just added, not yet deeply read
- `⌨️` — in progress / working notes
- `🌴` — evergreen / fully processed
- `🔗` — concept/name page (auto-maintained)

## Index Conventions

`index.md` is auto-generated. Sections:
- **Recent Digests** — last 10 digested papers
- **Concepts** — alphabetical list with one-line descriptions
- **Names** — alphabetical list with one-line descriptions
- **By Topic** — grouped by primary tag
- **Stats** — counts by type and status
