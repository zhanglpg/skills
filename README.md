# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### Briefs

**Location:** `briefs/`

LLM-native skill that generates daily tech briefs. The LLM directly fetches and curates content from configured sources (arXiv, GitHub Trending, news sites, blogs, RSS feeds) using web tools, then assembles a structured Markdown brief.

Pre-built configuration included:
- `briefs/config.ai-tech.json` — AI technology news (arXiv, AI labs, HN, GitHub trending, newsletters)

See `briefs/SKILL.md` for the full prompt and `briefs/config.ai-tech.json` to customize sources and sections.

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
├── prompts/                    # Prompt templates for LLM calls
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
