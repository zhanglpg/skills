You are analyzing a batch of related wiki pages for semantic health issues.

## Pages

{pages_content}

## Instructions

Analyze these pages carefully for the following issues:

### 1. Contradictions
Claims in one page that conflict with claims in another page. Quote the conflicting statements and identify which pages they come from.

### 2. Stale Claims
Information in older pages that appears outdated or superseded by newer pages in this batch. Reference the dates and explain what has changed.

### 3. Missing Cross-References
Pages that discuss closely related topics but do not link to each other via `[[wikilinks]]`. Only flag substantive relationships — not tangential mentions.

## Output Format

Return a JSON array of findings. Each finding must be an object with these fields:

```json
[
  {
    "category": "contradiction",
    "pages": ["Page-Stem-One", "Page-Stem-Two"],
    "description": "Page A claims X while Page B claims Y. These are incompatible because..."
  }
]
```

Valid categories: `"contradiction"`, `"stale-claim"`, `"missing-xref"`

## Rules

- Only report genuine issues, not stylistic preferences or minor wording differences
- For contradictions, quote the conflicting claims directly
- For stale claims, explain specifically what newer information supersedes the old
- For missing cross-references, only flag relationships where a reader would clearly benefit from a link
- Aim for precision over recall — fewer high-confidence findings are better than many speculative ones
- If no issues are found, return an empty array: `[]`

Return ONLY the JSON array, no other text.
