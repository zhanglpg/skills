# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### Briefs

**Location:** `briefs/`

LLM-native skill that generates daily tech briefs. The LLM directly fetches and curates content from configured sources (arXiv, GitHub Trending, news sites, blogs, RSS feeds) using web tools, then assembles a structured Markdown brief.

Pre-built configurations included:
- `briefs/config.ai-tech.json` — AI technology news (arXiv, AI labs, HN, GitHub trending, newsletters)
- `briefs/config.portfolio.json` — Portfolio and market brief (customizable holdings, watchlist, macro sources)

See `briefs/SKILL.md` for the full prompt and the config files to customize sources and sections.

### Check Market Movers

**Location:** `check-market-movers/`

Hourly portfolio monitoring that checks for significant price moves in configured holdings using Yahoo Finance data. Silent by default — only interrupts when portfolio-relevant thresholds are crossed. Tickers and thresholds are defined in config. Main script: `scripts/check-market-movers.py`.

### OpenBB Sync

**Location:** `openbb-sync/`

Shell script (`sync.sh`) that pulls the OpenBB repo from GitHub, reruns the data pipeline when changes are detected, and restarts the dashboard. Silent by default — reporting is the caller's responsibility. macOS-specific (uses `launchctl`).

### Paper Digest

**Location:** `paper-digest/`

Digests academic papers (local PDF, URL, or arXiv ID) into structured Markdown summaries using PyMuPDF for PDF extraction and Gemini CLI for summarization. Supports five output sections: main contributions, key conclusions, relation to prior work, personalized highlights, and further reading. Prompt template in `prompts/digest-prompt.md`.

### Paper Queue

**Location:** `paper-queue/`

Prioritized reading queue for academic papers backed by SQLite. Papers enter from arXiv IDs, URLs, or Twitter/X links and are auto-scored on three dimensions: citations (30%, via Semantic Scholar), recency (30%), and queue affinity (40%, topic overlap with already-queued papers). Integrates with paper-digest for summarization and includes a suggester for new paper recommendations.

### Paper Summarizer

**Location:** `paper-summarizer/`

LLM-native skill that fetches and summarizes papers, articles, or blog posts, then saves structured notes directly to a configured notes directory. Includes wikilinks, tags, and a "Connections" section for cross-linking. Also supports a reading-backlog mode that processes unchecked items from a configurable backlog file. Note template in `references/note-template.md`.

### Wiki Manager

**Location:** `wiki-manager/`

Maintains a living knowledge wiki by transforming isolated paper digests into an interconnected knowledge graph. After digesting a paper, the `ingest` command extracts entities, creates/updates entity and concept pages, rebuilds the index, and appends to a chronological log. Also supports `index`, `lint`, and `entities` commands for vault maintenance. Main script: `scripts/wiki_manager.py`.

### Wiki Query

**Location:** `wiki-query/`

LLM-native skill that answers research questions by searching the knowledge wiki index, reading relevant digest and entity pages, and synthesizing cross-paper analyses. Substantive answers are optionally filed back as synthesis pages for future reference.

### Shared

**Location:** `shared/`

Shared utilities used across skills. Contains `logging_utils.py` for consistent log formatting and `llm_utils.py` for common LLM interaction helpers.

## Skill Structure

Skills vary in structure depending on whether they are script-based or LLM-native:

**Script-based skills** (check-market-movers, paper-digest, paper-queue, openbb-sync, wiki-manager):
```
skill-name/
├── SKILL.md                    # Skill definition and instructions
├── config.json                 # Configuration (if applicable)
├── prompts/                    # Prompt templates (if applicable)
├── references/                 # Reference documentation (if applicable)
└── scripts/                    # Python scripts and unit tests
```

**LLM-native skills** (paper-summarizer, wiki-query):
```
skill-name/
├── SKILL.md                    # Skill definition, prompt, and instructions
├── config*.json                # Configuration(s) (if applicable)
├── prompts/                    # Prompt templates (if applicable)
└── references/                 # Reference documentation (if applicable)
```

**Hybrid skills** (briefs):
```
skill-name/
├── SKILL.md                    # Skill definition, prompt, and instructions
├── config*.json                # Configuration(s)
└── scripts/                    # Helper scripts (e.g., fetch_prices.py)
```

A `pyproject.toml` at the repo root defines Python dependencies (`yfinance`, `pandas`, `PyMuPDF`) and `ruff` linting configuration for the script-based skills.

## Contributing

To contribute a new skill:
1. Follow the appropriate structure above
2. Include clear documentation in SKILL.md
3. Test thoroughly before submitting

## License

MIT
