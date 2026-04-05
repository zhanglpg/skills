---
name: wiki-query
description: "Answer research questions by searching the knowledge wiki (gen-notes/index.md), synthesizing answers from digest and entity pages, and optionally filing valuable answers back as synthesis pages. Use when: user asks a research question about topics covered in their reading, wants cross-paper analysis, or asks to search/query their wiki. Triggers: wiki query, search wiki, research question, cross-paper, compare papers."
---

# Wiki Query

Answer research questions by searching the knowledge wiki, synthesizing answers from existing pages, and filing valuable analyses back into the wiki.

## Workflow

1. **Read the index** — Start by reading `gen-notes/index.md` to understand what pages exist and find relevant ones
2. **Read relevant pages** — Open the digest, entity, and concept pages most relevant to the question
3. **Synthesize an answer** — Draw from multiple sources, cite pages with `[[wikilinks]]`
4. **File back if valuable** — If the answer is substantive (not a trivial lookup), save it as a synthesis page

## Filing Synthesis Pages

When an answer merits permanent storage:

1. Save to `gen-notes/syntheses/<Descriptive Title>.md`
2. Use this format:

```markdown
---
title: "Descriptive Title Based on the Question"
type: synthesis
date-created: YYYY-MM-DD
sources:
  - "[[Source Page 1]]"
  - "[[Source Page 2]]"
tags:
  - relevant-tag
status: 📥
---

# Descriptive Title

> **Query:** The original question asked
> **Date:** YYYY-MM-DD

## Answer

<Synthesized answer drawing from wiki pages. Use [[wikilinks]] for all references.>

## Sources Used

- [[Page 1]] — what was relevant from this page
- [[Page 2]] — what was relevant from this page
```

3. After saving, run `wiki_manager.py index` to update the index
4. Run `wiki_manager.py` log to record the query event (or append manually)

## When to File vs Not File

**File as comparison** (to `gen-notes/comparisons/`):
- Side-by-side comparisons of papers, methods, or approaches

**File as synthesis** (to `gen-notes/syntheses/`):
- Answers that required reading 3+ wiki pages
- Insights that connect concepts in non-obvious ways
- Answers the user is likely to want again

**Don't file:**
- Simple factual lookups ("when was X published?")
- Answers from a single page
- Trivial questions

## Notes

- Always check `gen-notes/index.md` first — it has one-line summaries of every page
- Prefer existing entity/concept pages over raw digests when available
- If the wiki doesn't cover the topic, say so — don't hallucinate from outside the wiki
- Cross-reference with entity pages to provide broader context
