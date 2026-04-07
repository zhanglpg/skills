---
name: managing-wiki
description: "Maintains a living knowledge wiki in the Obsidian vault. After any paper is digested, extracts concepts and names, creates/updates concept and name pages, rebuilds the index, and appends to the log. Also supports periodic lint checks, LLM-powered compile analysis, index rebuilding, and broken wikilink repair. Use for wiki updates, ingestion, lint checks, compile analysis, or knowledge graph maintenance."
---

# Wiki Manager

Maintain a living knowledge wiki in the Obsidian vault. This skill transforms isolated paper digests into an interconnected knowledge graph by managing concept pages, name pages, a content index, and a chronological log.

## When to Use

- **After digesting a paper** — run ingest to create concept and name pages, update the index, and log the event
- **To rebuild the index** — run `index` to regenerate `index.md` from all vault pages
- **To check vault health** — run `lint` to find orphan pages, broken wikilinks, stale concepts
- **To fix broken wikilinks** — run the `fix-links` workflow (see below)
- **To run AI compile** — analyze the wiki for contradictions, stale claims, gaps, and missing cross-references
- **To view the log** — read `gen-notes/log.md` for a chronological record of all wiki activity

---

## Ingest (Agent-Primary)

After a paper digest is created, ingest it into the wiki to extract concepts and names and create their pages.

### Step 1: Extract metadata

```bash
python3 scripts/wiki_manager.py ingest <digest_path> --extract-only
```

This outputs JSON with:
- `digest_title`, `digest_content` — the parsed digest
- `concepts` — list of concepts from frontmatter (each with `name`, `exists`, `path`)
- `names` — list of names from frontmatter (each with `name`, `exists`, `path`)
- `existing_pages` — dict of existing page titles by type (`concepts`, `names`, `digests`)
- `concept_dir`, `names_dir` — directories for writing new pages
- `vault_root`, `gen_notes_dir`, `log_path` — vault paths

### Step 2: Create/update concept pages

For each concept in the extract output:

- **If new** (`exists: false`): Create a concept page following `prompts/concept-page-prompt.md`. Write to `<concept_dir>/<Concept Name>.md`.
- **If existing** (`exists: true`): Read the existing page at `path`, then update it to incorporate the new digest (add to Key Papers, update Evolution, add source-digest to frontmatter, update `date-updated`).

Concept page format requirements (see `prompts/concept-page-prompt.md` for full spec):
- YAML frontmatter: `title`, `type: concept`, `aliases`, `date-created`, `date-updated`, `source-digests`, `tags`, `status: 🔗`
- Sections: Overview, Key Papers, Evolution, Open Questions, Related Concepts
- Use `[[wikilinks]]` for all cross-references; use exact names from `existing_pages`

### Step 3: Create/update name pages

For each name in the extract output:

- **If new** (`exists: false`): Create a name page following `prompts/name-page-prompt.md`. Write to `<names_dir>/<Name>.md`.
- **If existing** (`exists: true`): Read the existing page at `path`, then update it similarly.

Name page format requirements (see `prompts/name-page-prompt.md` for full spec):
- YAML frontmatter: `title`, `type: name`, `name-type` (person/dataset/model/place/paper), `aliases`, `date-created`, `date-updated`, `source-digests`, `tags`, `status: 🔗`
- Sections: Overview, Key Contributions, Timeline, Related Names, Related Concepts
- Only for independently notable subjects (Wikipedia-worthy)

### Step 4: Update index and log

```bash
python3 scripts/wiki_manager.py index
```

Then manually append to `log.md` or note the ingest in the conversation.

### Fallback — Full Gemini Pipeline

```bash
python3 scripts/wiki_manager.py ingest <digest_path>
```

Runs the complete ingest with Gemini CLI for page generation. No agent involvement needed.

---

## Compile (Agent-Primary)

Analyze the wiki for semantic issues: contradictions between pages, stale claims, missing cross-references, concept gaps, and research questions.

### Step 1: Extract data and lint issues

```bash
python3 scripts/wiki_manager.py compile extract
```

This outputs JSON with:
- `batches` — page batches grouped by tag, each with `label`, `pages`, and `contents` (truncated page text)
- `wiki_summary` — compact one-line-per-page summary of the entire wiki
- `lint_issues` — structural issues found by deterministic lint checks
- `total_pages`, `vault_root`

### Step 2: Cross-page analysis

For each batch, analyze the pages for:
- **Contradictions** — conflicting claims between pages
- **Stale claims** — information superseded by newer pages
- **Missing cross-references** — pages that should link to each other but don't

See `prompts/compile-cross-page-prompt.md` for the detailed analysis instructions.
Output findings as a JSON array with `category`, `pages`, `description` fields.

### Step 3: Gap analysis

Using the `wiki_summary`, analyze the wiki as a whole for:
- **Concepts needing pages** — important topics that lack dedicated pages
- **Data gaps** — areas with thin coverage
- **Research questions** — new directions worth investigating

See `prompts/compile-gap-analysis-prompt.md` and `references/schema.md` for instructions.
Output findings in the same JSON array format.

### Step 4: Save report

Combine all findings from steps 2 and 3 into a single JSON array and pass to:

```bash
python3 scripts/wiki_manager.py compile save-report '<json_array>'
```

The script formats the report, saves `_compile-report.md`, and logs the event.

### Step 5: Review

Read the saved report and summarize key findings for the user.

---

## Non-LLM Commands (Script-Only)

These commands don't require LLM work — always run via script:

```bash
# Rebuild index.md from all vault pages
python3 scripts/wiki_manager.py index

# Run vault health checks (deterministic, no LLM)
python3 scripts/wiki_manager.py lint

# List all concept pages
python3 scripts/wiki_manager.py concepts

# List all name pages
python3 scripts/wiki_manager.py names
```

## Fixing Broken Wikilinks

### Workflow

**Step 1: Scan** — Get a JSON report of all broken links and existing pages.

```bash
python3 scripts/wiki_manager.py fix-links scan
```

Output includes `existing_pages` (every page with stem, title, type, aliases) and `broken_links` (every broken wikilink with file and `alias_hint`).

**Step 2: Decide resolutions** — Review the broken links against existing pages. Build a JSON mapping: `{"broken link text": "correct page stem", ...}`

**Step 3: Apply** — Batch-replace all resolved links.

```bash
python3 scripts/wiki_manager.py fix-links apply '{"Transformer Architecture": "Transformer"}'
```

Use `--dry-run` to preview changes.

### When to run fix-links

- After `ingest` — new pages may resolve previously-broken links
- After `lint` reports broken-links warnings
- Periodically as the vault grows

## Agent Workflow

When the user asks to digest or summarize a paper, the natural workflow is:

1. Use `paper-digest` or `paper-summarizer` to create the digest note
2. Then use this skill to ingest it into the knowledge wiki

## Vault Structure

```
gen-notes/
  index.md          — auto-generated catalog of all pages
  log.md            — append-only chronological record
  digests/          — paper digest notes
  concepts/         — concept pages (Transformer.md, RLHF.md, etc.)
  names/            — name pages (Geoffrey Hinton.md, ImageNet.md, etc.)
  syntheses/        — filed query answers and cross-paper analyses
  comparisons/      — side-by-side comparisons
```

## Page Types

| Type | Directory | Created by |
|------|-----------|------------|
| Digest | `digests/` | paper-digest, paper-summarizer |
| Concept | `concepts/` | wiki-manager ingest |
| Name | `names/` | wiki-manager ingest |
| Synthesis | `syntheses/` | wiki-query skill or manual |
| Comparison | `comparisons/` | wiki-query skill or manual |

## Configuration

See `config.json` for vault paths. All paths are relative to `vault_root`.

## Dependencies

| Tool | Purpose |
|------|---------|
| **Python 3.10+** | Runtime |

Gemini CLI is only needed for the ingest fallback pipeline (`ingest` without `--extract-only`).

## Files

| File | Purpose |
|------|---------|
| `scripts/wiki_manager.py` | CLI entry point |
| `scripts/vault_index.py` | Index generation |
| `scripts/log_writer.py` | Log operations |
| `scripts/concept_manager.py` | Concept page CRUD |
| `scripts/name_manager.py` | Name page CRUD |
| `scripts/lint_checker.py` | Vault health checks |
| `scripts/link_fixer.py` | Broken wikilink scan + batch-apply |
| `scripts/compile_checker.py` | LLM-powered AI compile |
| `prompts/concept-page-prompt.md` | Concept page format spec |
| `prompts/name-page-prompt.md` | Name page format spec |
| `prompts/compile-cross-page-prompt.md` | Cross-page analysis instructions |
| `prompts/compile-gap-analysis-prompt.md` | Gap analysis instructions |
| `prompts/index-update-prompt.md` | Index summary format |
| `references/schema.md` | Vault conventions reference |
| `config.json` | Default configuration |
