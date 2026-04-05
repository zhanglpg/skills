---
name: wiki-manager
description: "Maintain a living knowledge wiki in the Obsidian vault. After any paper is digested (via paper-digest or paper-summarizer), run the wiki-manager ingest step to extract concepts and names, update concept/name pages, rebuild the index, and append to the log. Also use for periodic lint checks, health scans, rebuilding the index, and querying the wiki. Triggers: wiki update, wiki ingest, update concepts, rebuild index, lint wiki, wiki lint, wiki scan, health check, knowledge graph."
---

# Wiki Manager

Maintain a living knowledge wiki in the Obsidian vault. This skill transforms isolated paper digests into an interconnected knowledge graph by managing concept pages, name pages, a content index, and a chronological log.

## When to Use

- **After digesting a paper** — run `ingest` to extract concepts and names, create/update their pages, update the index, and log the event
- **To rebuild the index** — run `index` to regenerate `index.md` from all vault pages
- **To check vault health** — run `lint` to find orphan pages, broken wikilinks, stale concepts, missing concepts
- **To run a deep health scan** — run `scan` for LLM-powered analysis: contradictions between pages, stale claims, missing cross-references, concept gaps, data gaps, and research questions
- **To view the log** — read `gen-notes/log.md` for a chronological record of all wiki activity

## Quick Start

```bash
# After digesting a paper, ingest it into the wiki
python3 scripts/wiki_manager.py ingest gen-notes/digests/Attention-Is-All-You-Need.md

# Rebuild the index from scratch
python3 scripts/wiki_manager.py index

# Run a lint check on the wiki
python3 scripts/wiki_manager.py lint

# Run a deep LLM-powered health scan
python3 scripts/wiki_manager.py scan

# List all concept pages
python3 scripts/wiki_manager.py concepts

# List all name pages
python3 scripts/wiki_manager.py names
```

## Agent Workflow

When the user asks to digest or summarize a paper, the natural workflow is:

1. Use `paper-digest` or `paper-summarizer` to create the digest note
2. Then use `wiki-manager ingest <digest_path>` to integrate it into the knowledge wiki

The ingest step:
1. Parses the digest — extracts frontmatter, TL;DR, wikilinks, tags
2. Reads concepts from the digest frontmatter (added by paper-digest). Falls back to LLM extraction for older digests without a `concepts` field
3. For each concept: creates a new concept page or updates an existing one
4. Reads names from the digest frontmatter (added by paper-digest). Falls back to LLM extraction for older digests without a `names` field
5. For each name: creates a new name page or updates an existing one
6. Updates `gen-notes/index.md` with the new digest and any new concept/name pages
7. Appends to `gen-notes/log.md` with a record of all touched pages

## Vault Structure

All wiki pages live under flat subfolders in `gen-notes/`:

```
gen-notes/
  index.md          — auto-generated catalog of all pages
  log.md            — append-only chronological record
  digests/          — paper digest notes (managed by paper-digest/paper-summarizer)
  concepts/         — concept pages (Transformer.md, RLHF.md, etc.)
  names/            — name pages (Geoffrey Hinton.md, ImageNet.md, etc.)
  syntheses/        — filed query answers and cross-paper analyses
  comparisons/      — side-by-side comparisons of papers, methods, or approaches
```

## Page Types

| Type | Directory | Created by |
|------|-----------|------------|
| Digest | `digests/` | paper-digest, paper-summarizer |
| Concept | `concepts/` | wiki-manager ingest (auto) |
| Name | `names/` | wiki-manager ingest (auto) |
| Synthesis | `syntheses/` | wiki-query skill or manual |
| Comparison | `comparisons/` | wiki-query skill or manual |

## Commands Reference

| Command | Description |
|---------|-------------|
| `ingest <path>` | Ingest a digest into the wiki (extract concepts and names, update index/log) |
| `index` | Rebuild `index.md` from all vault pages |
| `lint` | Run vault health checks |
| `scan` | Run LLM-powered wiki health scan (contradictions, stale claims, gaps, cross-refs) |
| `concepts` | List all concept pages |
| `names` | List all name pages |

## Configuration

See `config.json` for vault paths. All paths are relative to `vault_root`.

## Dependencies

| Tool | Purpose |
|------|---------|
| **Python 3.10+** | Runtime |
| **Gemini CLI** | LLM calls for concept/name page generation (and extraction fallback for older digests) |

## Files

| File | Purpose |
|------|---------|
| `scripts/wiki_manager.py` | CLI entry point |
| `scripts/vault_index.py` | Index generation |
| `scripts/log_writer.py` | Log operations |
| `scripts/concept_manager.py` | Concept page CRUD |
| `scripts/name_manager.py` | Name page CRUD |
| `scripts/lint_checker.py` | Vault health checks |
| `scripts/scan_checker.py` | LLM-powered semantic scan |
| `prompts/concept-page-prompt.md` | Concept page LLM template |
| `prompts/scan-cross-page-prompt.md` | Cross-page analysis LLM template |
| `prompts/scan-gap-analysis-prompt.md` | Wiki-wide gap analysis LLM template |
| `prompts/name-page-prompt.md` | Name page LLM template |
| `prompts/index-update-prompt.md` | Index summary LLM template |
| `references/schema.md` | Vault conventions reference |
| `config.json` | Default configuration |
