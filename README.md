# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### Briefs

**Location:** `briefs/`

Generates daily briefs from curated sources using a fetch-first, summarize-second pipeline:
- Fetches RSS feeds, arXiv papers, Hacker News stories, GitHub trending repos, and web pages
- Passes all verified content to Gemini CLI for summarization into a configurable template
- Appends a source coverage report to every output

Configured via `briefs/config.ai-tech.json` for AI technology news. See `briefs/SKILL.md` for how to configure the pipeline for other topics.

**Installation:**
```bash
# Copy to your OpenClaw skills directory
cp -r briefs ~/.openclaw/workspace-coding/skills/ai-tech-brief

# Optional: install for better web content fetching
pip install httpx trafilatura
```

**Usage:**
```bash
# Run via cron (configured in OpenClaw)
openclaw cron run ai-tech-daily-brief

# Or generate manually
cd briefs
python3 scripts/generate_brief.py --config config.ai-tech.json --output /tmp/brief.md
```

**Dependencies:**
- `gemini-cli` (for Twitter/X search and summarization)
- Python 3
- `httpx` + `trafilatura` (optional, for better web content fetching)

## Skill Structure

```
briefs/
├── SKILL.md                    # Skill definition and instructions
├── config.ai-tech.json         # AI tech brief sources and settings
├── scripts/                    # Executable scripts
│   ├── generate_brief.py       # Main orchestration
│   ├── fetcher.py              # Content fetching (RSS, APIs, web)
│   ├── summarizer.py           # Gemini CLI integration
│   ├── renderer.py             # Template rendering & output
│   └── test_generate_brief.py # Unit tests
├── templates/                  # Output format templates
│   └── ai-tech-brief.md
└── references/                 # Reference documentation
    └── sources.md
```

## Contributing

To contribute a new skill:
1. Follow the structure above
2. Include clear documentation in SKILL.md
3. Test thoroughly before submitting

## License

MIT
