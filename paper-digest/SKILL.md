---
name: digesting-papers
description: "Digests and summarizes academic papers (PDF, URL, or arXiv ID). Produces a structured summary covering main contributions, key conclusions, relation to prior work, personalized highlights, and further reading recommendations. Use when asked for a paper summary, research digest, arXiv summary, or paper review."
---

# Paper Digest Skill

Read and digest academic papers into structured summaries tailored to the reader's interests.

## Quick Start

```bash
# Digest from a local PDF
python3 ~/.openclaw/workspace/skills/custom/paper-digest/scripts/digest_paper.py paper.pdf

# Digest from a URL
python3 scripts/digest_paper.py https://arxiv.org/abs/2401.12345

# Digest from an arXiv ID
python3 scripts/digest_paper.py 2401.12345

# Save output to a specific directory
python3 scripts/digest_paper.py paper.pdf --output_dir ~/digests

# Re-digest a paper even if a digest already exists
python3 scripts/digest_paper.py paper.pdf --force
```

## How It Works

1. **Resolve Input** — Accepts a local PDF path, a URL (including arXiv abstract pages), or a bare arXiv ID
2. **Extract Text** — Extracts text from PDFs using `PyMuPDF` (fitz); fetches arXiv PDFs automatically
3. **Search Hacker News** — Searches HN Algolia API for discussion threads about the paper; fetches and formats insightful comments if found
4. **Build Prompt** — Assembles the extracted text, HN comments (if any), and a structured prompt template
5. **Summarize** — Passes content to Gemini CLI for structured analysis
6. **Check Existing** — Skips if a digest already exists (use `--force` to re-digest)
7. **Render Output** — Writes the digest as a Markdown file

## Output Format — IMPORTANT

**The default prompt template produces generic academic summaries.** For the Obsidian vault, the output should match the personalized digest style:

- TL;DR upfront (1-2 sentences, direct conclusion)
- Voice: Narrate with thinking. Clear opinions. 
- Tables for structured comparisons
- `[[wikilinks]]` connecting to vault notes
- Key quotes extracted
- "Worth thinking" section with personal perspective
- Obsidian frontmatter at bottom (date, status, tags, categories, related)

**To use the default academic format**, keep current prompt. **To match the personalized style**, update `prompts/digest-prompt.md` with instructions for the format above.

## Output Sections (Default Template)

Each digest includes five sections (defined in `prompts/digest-prompt.md`):

1. **Main Idea & Contributions**
2. **Key Conclusions & Insights**
3. **Relation to Prior Work**
4. **Personalized Highlights**
5. **Further Reading**
6. **Community Insights (Hacker News)** — included only when HN discussion is found

See the prompt file for detailed section guidelines.

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3** | Script runtime | Built-in on macOS/Linux |
| **gemini** | LLM summarization | `brew install gemini-cli` |
| **PyMuPDF** | PDF text extraction | `pip install PyMuPDF` |
| **httpx** (optional) | HTTP fetching | `pip install httpx` |

If `httpx` is not installed, the script falls back to `urllib`.

## Configuration

The skill can be personalized via a JSON config file:

```bash
python3 scripts/digest_paper.py paper.pdf --config config.json
```

```json
{
  "user_context": "ML researcher working on LLM agents and code generation. Interested in training efficiency, tool use, and reasoning.",
  "output_dir": "~/paper-digests",
  "gemini_timeout": 180,
  "log_file": "~/.openclaw/logs/skills/paper-digest/digest.log"
}
```

**user_context** — A description of your background and interests. Used to generate the "Personalized Highlights" section. If omitted, this section gives general highlights instead.

### `--force`

By default, the script skips papers that already have a digest file in the output directory. Pass `--force` to re-digest and overwrite the existing file.

## Output

Digests are saved as Markdown files in the output directory. Each file has a metadata header (title, source, date) followed by the five sections above.

## Testing

```bash
cd skills/paper-digest

# Run unit tests
python3 -m unittest scripts/test_digest_paper.py -v

# Test with a real paper
python3 scripts/digest_paper.py 2401.12345 --output_dir /tmp/
```

## Troubleshooting

### PyMuPDF not installed
```bash
pip3 install PyMuPDF
```

### Gemini CLI timeout
1. Check your internet connection
2. Try running `gemini "test"` manually
3. Increase timeout: `--gemini_timeout 300`

### PDF text extraction fails
- Some PDFs are image-based (scanned). PyMuPDF extracts text layers only.
- Try converting with OCR first if the PDF is scanned.

### arXiv download fails
- Check your internet connection
- Verify the arXiv ID is valid (e.g., `2401.12345`)
- arXiv may rate-limit; wait and retry

## Files

| File | Purpose |
|------|---------|
| `scripts/digest_paper.py` | Main script — CLI entry point |
| `scripts/test_digest_paper.py` | Unit tests |
| `prompts/digest-prompt.md` | LLM prompt template (single source of truth for section structure) |
| `SKILL.md` | This documentation |

---

