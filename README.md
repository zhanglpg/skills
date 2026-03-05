# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### 🤖 AI Tech Brief

**Location:** `briefs/`

Generates daily AI technology news briefs covering:
- AI Infrastructure (training/inference, GPUs/TPUs)
- Agentic Coding (autonomous agents, AI dev tools)
- AI Research Progress (papers, breakthroughs, model releases)

**Sources:**
- 12 Twitter/X thought leaders (Karpathy, Ilya, Andrew Ng, etc.)
- 9 newsletters (Ben's Bites, TLDR AI, Import AI, etc.)
- arXiv papers (cs.LG, cs.AI, cs.SE)
- AI lab blogs (OpenAI, Anthropic, Google DeepMind, Meta AI)
- Hacker News + GitHub Trending (community & trending)

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
python3 scripts/generate_brief.py --output /tmp/brief.md
```

**Dependencies:**
- `gemini-cli` (for Twitter/X search and summarization)
- Python 3
- `httpx` + `trafilatura` (optional, for better web content fetching)

## Skill Structure

Each skill follows the OpenClaw skill format:

```
briefs/
├── SKILL.md                    # Skill definition and instructions
├── config.json                 # Sources, settings, and configuration
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
