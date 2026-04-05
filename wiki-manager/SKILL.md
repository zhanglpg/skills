---
name: wiki-manager
description: "Maintain a living knowledge wiki in the Obsidian vault. After any paper is digested (via paper-digest or paper-summarizer), run the wiki-manager ingest step to extract entities, update entity/concept pages, rebuild the index, and append to the log. Also use for periodic lint checks, rebuilding the index, and querying the wiki. Triggers: wiki update, wiki ingest, update entities, rebuild index, lint wiki, wiki lint, knowledge graph."
---

# Wiki Manager

Maintain a living knowledge wiki in the Obsidian vault. This skill transforms isolated paper digests into an interconnected knowledge graph by managing entity pages, a content index, and a chronological log.

## When to Use

- **After digesting a paper** — run `ingest` to extract entities, create/update entity pages, update the index, and log the event
- **To rebuild the index** — run `index` to regenerate `index.md` from all vault pages
- **To check vault health** — run `lint` to find orphan pages, broken wikilinks, stale entities, missing concepts
- **To view the log** — read `gen-notes/log.md` for a chronological record of all wiki activity

## Quick Start

```bash
# After digesting a paper, ingest it into the wiki
python3 scripts/wiki_manager.py ingest gen-notes/digests/Attention-Is-All-You-Need.md

# Rebuild the index from scratch
python3 scripts/wiki_manager.py index

# Run a lint check on the wiki
python3 scripts/wiki_manager.py lint

# List all entity pages
python3 scripts/wiki_manager.py entities
```

## Agent Workflow

When the user asks to digest or summarize a paper, the natural workflow is:

1. Use `paper-digest` or `paper-summarizer` to create the digest note
2. Then use `wiki-manager ingest <digest_path>` to integrate it into the knowledge wiki

The ingest step:
1. Parses the digest — extracts frontmatter, TL;DR, wikilinks, tags
2. Extracts 3-8 key entities via LLM (methods, models, concepts, datasets)
3. For each entity: creates a new entity page or updates an existing one
4. Updates `gen-notes/index.md` with the new digest and any new entity pages
5. Appends to `gen-notes/log.md` with a record of all touched pages

## Vault Structure

All wiki pages live under flat subfolders in `gen-notes/`:

```
gen-notes/
  index.md          — auto-generated catalog of all pages
  log.md            — append-only chronological record
  digests/          — paper digest notes (managed by paper-digest/paper-summarizer)
  entities/         — entity pages (Transformer.md, RLHF.md, etc.)
  concepts/         — broader concept pages (Scaling Laws in Deep Learning.md)
  syntheses/        — filed query answers and cross-paper analyses
```

## Page Types

| Type | Directory | Created by |
|------|-----------|------------|
| Digest | `digests/` | paper-digest, paper-summarizer |
| Entity | `entities/` | wiki-manager ingest (auto) |
| Concept | `concepts/` | wiki-manager ingest or manual |
| Synthesis | `syntheses/` | wiki-query skill or manual |

## Commands Reference

| Command | Description |
|---------|-------------|
| `ingest <path>` | Ingest a digest into the wiki (extract entities, update index/log) |
| `index` | Rebuild `index.md` from all vault pages |
| `lint` | Run vault health checks |
| `entities` | List all entity pages |

## Configuration

See `config.json` for vault paths. All paths are relative to `vault_root`.

## Dependencies

| Tool | Purpose |
|------|---------|
| **Python 3.10+** | Runtime |
| **Gemini CLI** | LLM calls for entity extraction and page generation |

## Files

| File | Purpose |
|------|---------|
| `scripts/wiki_manager.py` | CLI entry point |
| `scripts/vault_index.py` | Index generation |
| `scripts/log_writer.py` | Log operations |
| `scripts/entity_manager.py` | Entity page CRUD |
| `scripts/lint_checker.py` | Vault health checks |
| `prompts/entity-page-prompt.md` | Entity page LLM template |
| `prompts/index-update-prompt.md` | Index summary LLM template |
| `references/schema.md` | Vault conventions reference |
| `config.json` | Default configuration |
