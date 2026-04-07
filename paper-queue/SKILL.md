---
name: managing-paper-queue
description: "Manages a reading queue of academic papers with priority scoring, progress tracking, and suggestions. Adds papers from arXiv IDs, URLs, or Twitter/X links. Tracks reading status (to-read, reading, digested) and auto-scores by citations, recency, and topic affinity. Integrates with the digesting-papers skill for processing queued papers. Use when managing a paper queue, reading list, or paper backlog."
---

# Paper Queue Manager

Manage a prioritized reading queue of academic papers with automatic scoring and integration with the paper-digest skill.

## Quick Start

```bash
# Add a paper by arXiv ID
python3 scripts/paper_queue.py add 2401.12345

# Add from a URL
python3 scripts/paper_queue.py add https://arxiv.org/abs/2401.12345

# Add from a tweet
python3 scripts/paper_queue.py add https://x.com/karpathy/status/123456

# Add manually
python3 scripts/paper_queue.py add --manual --title "Paper Title" --url "https://..."

# View the queue
python3 scripts/paper_queue.py list --top 10

# Mark as reading
python3 scripts/paper_queue.py status 1 reading

# Digest a paper (use paper-digest skill directly)
python3 paper-digest/scripts/digest_paper.py 2401.12345
# Then mark it digested in the queue
python3 scripts/paper_queue.py status 1 digested

# Get suggestions for new papers
python3 scripts/paper_queue.py suggest

# Queue stats
python3 scripts/paper_queue.py stats
```

## How It Works

1. **Add** — Papers enter the queue from arXiv (ID or URL), Twitter/X links (extracts embedded paper URLs), or manual entry
2. **Score** — Each paper is automatically scored on three dimensions:
   - **Citations** (30%) — From Semantic Scholar API (log scale)
   - **Recency** (30%) — How recently published (decay over time)
   - **Queue affinity** (40%) — Topic overlap with papers already in the queue. The reading history defines interests — no manual configuration needed.
3. **Track** — Papers move through statuses: `to-read` → `reading` → `digested`
4. **Digest** — Use the paper-digest skill directly (`python3 paper-digest/scripts/digest_paper.py <arXiv ID or URL>`), then mark the paper as digested with `status <id> digested`
5. **Suggest** — Get recommendations for new papers based on the queue's topic profile

## Priority Scoring

The scoring system learns from the queue itself — no need to configure interests or authors. When papers are added, the "queue affinity" component checks how well each paper's arXiv categories match the categories of papers already queued, read, or digested. An empty queue gives neutral affinity scores; as it grows, scoring becomes more personalized.

Re-score papers anytime with:
```bash
python3 scripts/paper_queue.py score        # Re-score all to-read papers
python3 scripts/paper_queue.py score 5      # Re-score paper #5
```

## Storage

Papers are stored in a SQLite database at `$AGENT_DATA_DIR/paper-queue/queue.db`. This provides efficient sorting, filtering, and querying while remaining portable (single file, no server).

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3.10+** | Runtime | Built-in on macOS/Linux |
| **sqlite3** | Storage | Built-in with Python |

No additional pip packages required. Uses stdlib `sqlite3`, `xml.etree`, and `urllib`.

Optional: `httpx` for better HTTP handling (falls back to `urllib`).

External APIs (no auth needed):
- **arXiv API** — Paper metadata
- **Semantic Scholar API** — Citation counts

## Configuration

Configuration via `config.json`:

```json
{
  "scoring_weights": {
    "citations": 0.30,
    "recency": 0.30,
    "queue_affinity": 0.40
  },
  "db_path": "$AGENT_DATA_DIR/paper-queue/queue.db",
  "digest_output_dir": "$AGENT_DATA_DIR/paper-digests",
  "max_suggestions": 10,
  "log_file": "$AGENT_DATA_DIR/logs/skills/paper-queue/queue.log"
}
```

## Commands Reference

| Command | Description |
|---------|-------------|
| `add <paper>` | Add paper (arXiv ID, URL, or tweet link) |
| `add --manual --title "..."` | Add paper manually |
| `list [--status S] [--top N] [--topic T]` | List queue |
| `status <id> <status>` | Update status (to-read, reading, digested) |
| `score [<id>]` | Re-score papers |
| `suggest [<id>]` | Get related paper suggestions |
| `stats` | Queue statistics |

## Testing

```bash
cd paper-queue/scripts
python3 -m unittest test_storage.py test_sources.py test_scorer.py test_paper_queue.py -v
```

## Files

| File | Purpose |
|------|---------|
| `scripts/paper_queue.py` | CLI entry point |
| `scripts/storage.py` | SQLite storage layer |
| `scripts/sources.py` | Input source handlers (arXiv, Twitter, manual) |
| `scripts/scorer.py` | Priority scoring (citations, recency, queue affinity) |
| `scripts/suggester.py` | Related paper suggestions |
| `prompts/suggest-prompt.md` | LLM prompt for ranking suggestions |
| `config.json` | Default configuration |
| `SKILL.md` | This documentation |

---

