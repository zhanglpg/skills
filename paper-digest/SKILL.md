---
name: digesting-papers
description: "Digests and summarizes academic papers (PDF, URL, or arXiv ID). Produces a structured summary covering main contributions, key conclusions, relation to prior work, personalized highlights, and further reading recommendations. Use when asked for a paper digest, research digest, arXiv summary, or detailed paper review with structured sections and metadata."
---

# Paper Digest Skill

Read and digest academic papers into structured summaries tailored to the reader's interests.

## Workflow

1. **Resolve & extract** — Use the helper script for PDF text extraction and HN comment fetching:

   ```bash
   python3 scripts/digest_paper.py <paper> --extract-only [--config config.json] [--concept_index <path>] [--name_index <path>]
   ```

   `<paper>` can be a local PDF path, URL, or bare arXiv ID (e.g. `2401.12345`).

   This outputs JSON with: `title`, `source`, `output_dir`, `paper_text`, `user_context`, `hn_comments`, `known_concepts`, `known_names`.

   **Alternative:** For web-accessible content, you can also use `web_fetch` (for HTML/blog posts) or the `pdf` tool directly instead of the script.

2. **Generate the digest** — Read `prompts/digest-prompt.md` for the canonical format specification. Produce a structured summary with YAML frontmatter and these sections:
   1. Main Idea & Contributions
   2. Key Conclusions & Insights
   3. Relation to Prior Work
   4. Personalized Highlights (tailored to `user_context`)
   5. Further Reading
   6. Community Insights (Hacker News) — only if HN comments were found

   **Frontmatter must include:** `title`, `authors`, `year`, `tags`, `categories` (always include `paper-digest`), `related`, `concepts` (up to 3 key concepts), `names` (up to 5 notable names).

   See `prompts/digest-prompt.md` for detailed rules on concept/name extraction, abstraction level, and notability criteria.

3. **Post-process frontmatter** — After generating the digest, add these auto-generated fields to the YAML frontmatter:
   - `source: "<url or path from extract step>"`
   - `digested: YYYY-MM-DD` (today's date)
   - `status: digested`

   These fields are in addition to the LLM-generated frontmatter (`title`, `authors`, `year`, `tags`, `categories`, `related`, `concepts`, `names`). Do NOT include `queue_id` in the frontmatter — that is added separately by paper-queue.

4. **Save** — Write the digest as a Markdown file:
   - Default directory: `~/paper-digests` (or `output_dir` from config/extract JSON)
   - Filename: sanitized title (max 60 chars) + `.md`
   - If a digest already exists at that path, ask before overwriting

5. **Confirm** — Tell the user the note was saved, with a one-line headline of the paper's key contribution.

## Output Format

See `prompts/digest-prompt.md` for the full format specification. Key points:

- Obsidian-compatible YAML frontmatter at the top
- `[[wikilinks]]` for cross-references to vault concepts and names
- Specific, cite-able results — no vague summaries
- Use the `known_concepts` and `known_names` from the extract step to avoid creating duplicates

## Fallback — Script + Gemini Pipeline

If the agent cannot perform the digest (e.g. running headlessly), the full pipeline can be run via:

```bash
python3 scripts/digest_paper.py <paper> [--config config.json] [--output_dir ~/digests] [--force]
```

This runs extraction, Gemini CLI summarization, and file output in one step. Requires `gemini` CLI (`brew install gemini-cli`).

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3** | Script runtime | Built-in on macOS/Linux |
| **PyMuPDF** | PDF text extraction | `pip install PyMuPDF` |
| **httpx** (optional) | HTTP fetching | `pip install httpx` |

If `httpx` is not installed, the script falls back to `urllib`.

## Configuration

```json
{
  "user_context": "ML researcher working on LLM agents and code generation.",
  "output_dir": "~/paper-digests",
  "gemini_timeout": 180,
  "concept_index_path": "~/notes/gen-notes/concept_index.md",
  "name_index_path": "~/notes/gen-notes/name_index.md"
}
```

## Files

| File | Purpose |
|------|---------|
| `scripts/digest_paper.py` | Extraction script (PDF, arXiv, HN) + Gemini fallback |
| `prompts/digest-prompt.md` | Canonical format spec for digest output |
| `SKILL.md` | This documentation |
