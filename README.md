# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### Briefs

**Location:** `briefs/`

Generates daily briefs from curated sources using a fetch-first, summarize-second pipeline:
- Fetches RSS feeds, arXiv papers, Hacker News stories, GitHub trending repos, and web pages
- Passes all verified content to Gemini CLI for summarization into a configurable template
- Appends a source coverage report to every output

Two pre-built configurations are included:
- `briefs/config.ai-tech.json` — AI technology news (arXiv, AI labs, HN, GitHub trending)
- `briefs/config.portfolio.json` — Financial markets & portfolio tracking (market data, macro, earnings)

See `briefs/SKILL.md` for how to configure the pipeline for other topics.

### Check Market Movers

**Location:** `check-market-movers/`

Monitors and reports significant market movements, including top gainers, losers, and most active stocks.

### OpenBB Sync

**Location:** `openbb-sync/`

Synchronizes financial data using the OpenBB platform for market analysis and portfolio tracking.

### Paper Digest

**Location:** `paper-digest/`

Processes and summarizes academic papers from arXiv and other sources into digestible summaries.

### Paper Queue

**Location:** `paper-queue/`

Manages a queue of papers to read, tracking progress and prioritizing reading list.

### Paper Summarizer

**Location:** `paper-summarizer/`

Generates structured summaries of research papers with key findings, methodology, and takeaways.

### Shared

**Location:** `shared/`

Shared utilities and common code used across multiple skills.

## Skill Structure

Each skill follows a consistent structure:

```
skill-name/
├── SKILL.md                    # Skill definition and instructions
├── config.json                 # Configuration (if applicable)
├── scripts/                    # Executable scripts
├── templates/                  # Output format templates
└── references/                 # Reference documentation
```

## Contributing

To contribute a new skill:
1. Follow the structure above
2. Include clear documentation in SKILL.md
3. Test thoroughly before submitting

## License

MIT
