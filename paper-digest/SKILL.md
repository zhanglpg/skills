---
name: paper-digest
description: "Digest and summarize academic papers (PDF, URL, or arXiv ID). Produces a structured summary covering main contributions, key conclusions, relation to prior work, personalized highlights, and further reading recommendations. Triggers: paper summary, research digest, arXiv summary, paper review, read paper."
---

# Paper Digest Skill

Read and digest academic papers into structured summaries tailored to your interests.

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
```

## How It Works

1. **Resolve Input** — Accepts a local PDF path, a URL (including arXiv abstract pages), or a bare arXiv ID
2. **Extract Text** — Extracts text from PDFs using `PyMuPDF` (fitz); fetches arXiv PDFs automatically
3. **Build Prompt** — Assembles the extracted text with a structured prompt template
4. **Summarize** — Passes content to Gemini CLI for structured analysis
5. **Render Output** — Writes the digest as a Markdown file

## Output Sections

Each digest includes five sections:

| # | Section | Purpose |
|---|---------|---------|
| 1 | **Main Idea & Contributions** | Core thesis, novelty, and what the paper adds to the field |
| 2 | **Key Conclusions & Insights** | Important results, takeaways, and surprising findings |
| 3 | **Relation to Prior Work** | How this paper builds on, differs from, or extends existing research |
| 4 | **Personalized Highlights** | What aspects are most relevant to the user's interests and work |
| 5 | **Further Reading** | Recommended papers, surveys, or resources to explore next |

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
  "log_file": "~/paper-digests/digest.log"
}
```

**user_context** — A description of your background and interests. Used to generate the "Personalized Highlights" section. If omitted, this section gives general highlights instead.

## Output

### Example

```markdown
# Paper Digest: Attention Is All You Need

**Source:** arxiv:1706.03762
**Digested:** March 11, 2026

## 1. Main Idea & Contributions
The paper introduces the Transformer architecture...

## 2. Key Conclusions & Insights
- Self-attention can replace recurrence entirely...
- The model achieves state-of-the-art on WMT translation...

## 3. Relation to Prior Work
Builds on sequence-to-sequence models (Sutskever et al., 2014)...

## 4. Personalized Highlights
Given your work on LLM agents, the key insight is...

## 5. Further Reading
- "BERT: Pre-training of Deep Bidirectional Transformers" (Devlin et al., 2019)
- "Language Models are Few-Shot Learners" (Brown et al., 2020)
```

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
| `prompts/digest-prompt.md` | LLM prompt template |
| `templates/digest-output.md` | Output format template |
| `SKILL.md` | This documentation |

---

**Version:** 1.0
**Author:** Liping (via OpenClaw)
**Last Updated:** March 11, 2026
