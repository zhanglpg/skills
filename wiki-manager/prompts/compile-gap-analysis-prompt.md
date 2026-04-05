You are analyzing a knowledge wiki to identify gaps and growth opportunities.

## Current Wiki Contents

{wiki_summary}

## Wiki Conventions

{schema_excerpt}

## Instructions

Based on the wiki's current coverage, identify high-value opportunities in these categories:

### 1. Concepts Needing Pages
Important topics that appear across multiple pages but lack their own dedicated entity or concept page. Go beyond simple mention-counting — consider whether a concept is foundational, frequently referenced, or would help readers navigate the wiki. Suggest whether each should be an **entity** page (specific method, model, technique) or a **concept** page (broader theme or research area).

### 2. Data Gaps
Specific areas where the wiki's coverage is thin and a web search or new paper digest could meaningfully improve it. Be concrete — name the topic and what kind of information is missing (recent developments, benchmarks, comparisons, historical context, etc.).

### 3. Research Questions
New directions or questions worth investigating, grounded in patterns you see across the wiki. These should be questions that reading additional papers or doing web research could help answer.

## Output Format

Return a JSON array of findings:

```json
[
  {
    "category": "concept-needs-page",
    "pages": ["Related-Page-One", "Related-Page-Two"],
    "description": "The concept of X appears in pages A, B, and C but has no dedicated page. It would be valuable as an entity page because..."
  }
]
```

Valid categories: `"concept-needs-page"`, `"data-gap"`, `"research-question"`

## Rules

- Aim for 5–15 high-value findings total, not 50 marginal ones
- For concepts needing pages, explain why the concept is important enough to warrant its own page
- For data gaps, be specific about what information is missing and how it could be found
- For research questions, ground them in what the wiki already covers — show the connection
- If the wiki is comprehensive with no clear gaps, return fewer findings rather than forcing weak ones
- Return ONLY the JSON array, no other text
