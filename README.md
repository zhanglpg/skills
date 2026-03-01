# OpenClaw Skills

Curated agent skills for specialized workflows.

## Available Skills

### 🤖 AI Tech Brief

**Location:** `ai-tech-brief/`

Generates daily AI technology news briefs covering:
- AI Infrastructure (training/inference, GPUs/TPUs)
- Agentic Coding (autonomous agents, AI dev tools)
- AI Research Progress (papers, breakthroughs, model releases)

**Sources:**
- 12 Twitter/X thought leaders (Karpathy, Ilya, Andrew Ng, etc.)
- 9 newsletters (Ben's Bites, TLDR AI, Import AI, etc.)
- arXiv papers (cs.LG, cs.AI, cs.SE)
- AI lab blogs (OpenAI, Anthropic, DeepMind, Meta)
- LMSYS

**Installation:**
```bash
# Copy to your OpenClaw skills directory
cp -r ai-tech-brief ~/.openclaw/workspace-coding/skills/

# Install blogwatcher dependency
go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest

# Setup RSS feeds
cd ~/.openclaw/workspace-coding/skills/ai-tech-brief
./scripts/setup_blogwatcher.sh
```

**Usage:**
```bash
# Run via cron (configured in OpenClaw)
openclaw cron run ai-tech-daily-brief

# Or generate manually
cd ai-tech-brief
python3 scripts/generate_brief.py --output /tmp/brief.md
```

**Dependencies:**
- `blogwatcher` (Go CLI for RSS tracking)
- `gemini-cli` (for web search and content generation)
- Python 3

## Skill Structure

Each skill follows the OpenClaw skill format:

```
skill-name/
├── SKILL.md              # Skill definition and instructions
├── scripts/              # Executable scripts
│   ├── generate_brief.py
│   └── setup_blogwatcher.sh
└── references/           # Reference documentation
    └── sources.md
```

## Contributing

To contribute a new skill:
1. Follow the structure above
2. Include clear documentation in SKILL.md
3. Test thoroughly before submitting

## License

MIT
