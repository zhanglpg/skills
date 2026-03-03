---
name: ai-tech-brief
description: Generate daily AI technology news briefs covering AI infrastructure, agentic coding, and research progress. Use when creating scheduled technical news digests from high-quality sources including arXiv papers, AI lab blogs, Twitter/X thought leaders, and newsletters. Triggers: daily briefs, AI news summaries, technical research digests, scheduled news reports.
---

# AI Tech Brief Skill

Generate comprehensive daily AI technology news briefs from curated high-quality sources.

## Quick Start

```bash
# Run via cron job (configured in OpenClaw)
openclaw cron run ai-tech-daily-brief

# Or invoke directly
cd skills/ai-tech-brief
python3 scripts/generate_brief.py --output /tmp/brief.md

# Scan RSS feeds manually
~/go/bin/blogwatcher scan
~/go/bin/blogwatcher articles
```

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **blogwatcher** | RSS feed tracking | `go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest` |
| **gemini** | Web search, content generation | `brew install gemini-cli` |
| **Python 3** | Script orchestration | Built-in on macOS |

**Setup RSS feeds (run once):**
```bash
./scripts/setup_blogwatcher.sh
```

## Coverage Areas

| Topic | What to Cover |
|-------|---------------|
| **AI Infrastructure** | Training/inference systems, distributed computing, GPUs/TPUs, optimization |
| **Agentic Coding** | Autonomous coding agents, AI dev tools, code generation, IDE integration |
| **AI Research** | New papers, breakthroughs, model releases, benchmarks |

## Source Priority

### Tier 1: Twitter/X Thought Leaders (12 accounts)

Check these accounts daily for announcements, insights, and thread summaries:

| Name | Handle | Focus |
|------|--------|-------|
| Andrej Karpathy | @karpathy | Eureka Labs, LLM education |
| Ilya Sutskever | @ilyasut | SSI, AI safety |
| Andrew Ng | @AndrewYNg | AI education |
| Lilian Weng | @lilianweng | Thinking Machines, safety |
| Jim Fan | @DrJimFan | NVIDIA, embodied AI |
| Jeremy Howard | @jeremyphoward | fast.ai |
| Nathan Lambert | @natolambert | RLHF, open models |
| Phil Duan | @philduanai | AI apps/products |
| Harrison Chase | @hwchase17 | LangChain |
| Guillermo Rauch | @rauchg | Vercel, dev tools |
| Pieter Levels | @levelsio | Indie dev |
| swyx | @swyx | Latent Space |

**Fetching:** Via Gemini CLI web search (no Twitter API needed)

### Tier 2: Newsletters & Daily Briefs (9 publications)

Scan these newsletters for curated AI news:

1. **Ben's Bites** - bensbites.com
2. **The Rundown AI**
3. **TLDR AI**
4. **Import AI** (Jack Clark)
5. **The Batch** (Andrew Ng)
6. **Superhuman AI**
7. **The Neuron**
8. **Latent Space** - latentspace.blog
9. **Interconnects** (Nathan Lambert)

**Fetching:** Via blogwatcher RSS feeds

### Tier 3: Academic & Research (3 categories)

1. **arXiv Papers** - cs.LG, cs.AI, cs.SE categories
2. **AI Lab Blogs** - OpenAI, Anthropic, Google DeepMind, Meta AI
3. **LMSYS** - lmsys.org/blog

**Fetching:** Gemini CLI for arXiv, blogwatcher for lab blogs

## Output Format

Structure the brief as:

```markdown
# 🤖 Daily AI Tech Brief - [DATE]

## 📊 Top Stories (3-5 items)

### [Headline]
- **Summary:** 1-2 sentences explaining what happened
- **Why it matters:** Impact/significance
- **Source:** [Original Article Title](exact_url) — 1 sentence summary

## 🐦 Twitter/X Updates

For each account with updates:
- **@[handle]:** [Tweet text summary] — [Link to tweet](exact_url)

If no updates: "No significant updates today from @[handle]."

## 📰 Newsletter Highlights

For each newsletter:
- **[Newsletter Name]:** [Article/story title] — [Link](exact_url) — 1-2 sentence summary

If no updates: "No updates from [Newsletter Name] today."

## 🏢 AI Lab Updates

For each lab:
- **[Lab Name]:** [Announcement/title] — [Link](exact_url) — 1-2 sentence summary

If no updates: "No updates from [Lab Name] today."

## 🔬 Research Organization Updates

For each org:
- **[Org Name]:** [Update/title] — [Link](exact_url) — 1-2 sentence summary

If no updates: "No updates from [Org Name] today."

## 📄 New Research Papers

| Paper | Key Finding | Link |
|-------|-------------|------|
| [Full Title] | 1-2 sentence summary of contribution | [arXiv:XXXX](exact_arxiv_url) |

## 🔗 Quick Links

- [Title/description](exact_url) — 1 sentence what this is about
```

### Format Requirements

Every item MUST include:
1. **Title/Headline** - Clear, descriptive title
2. **1-2 Sentence Summary** - What happened or what the content is about
3. **Exact URL Link** - Direct link to original source (not just domain)

For example:
- ❌ Bad: "OpenAI released new model [link]"
- ✅ Good: "OpenAI released GPT-5 with 10M context window — [GPT-5 Technical Report](https://openai.com/research/gpt-5) — New architecture achieves SOTA on reasoning benchmarks"

## Workflow

1. **Check** - Probe each hard-coded RSS URL; record failures
2. **Fetch** - Scan RSS feeds with blogwatcher
3. **Filter** - Select high-signal items (avoid duplicates, hype)
4. **Summarize** - Write concise summaries with "why it matters"
5. **Format** - Structure as markdown; append `⚠️ Source Access Issues` section for any unreachable feeds
6. **Deliver** - Post to Discord channel via cron delivery

## Scheduling

**Cron Expression:** `0 9 * * *` (9:00 AM Asia/Shanghai)

**Delivery:** Discord channel `channel:1477516149968339127`

**Save Location:** `~/ai-tech-briefs/YYYY-MM-DD-ai-tech-brief.md`

## Quality Guidelines

### Do

- ✅ Prioritize primary sources (papers, official blogs)
- ✅ Include "why it matters" for each item
- ✅ Link to original sources
- ✅ Keep summaries concise (2-3 sentences max)
- ✅ Focus on technical substance over hype

### Don't

- ❌ Include clickbait or unsubstantiated claims
- ❌ Duplicate stories across sections
- ❌ Write lengthy explanations (link out instead)
- ❌ Cover non-AI tech news (stay focused)

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/generate_brief.py` | Main orchestration (blogwatcher + Gemini CLI) |
| `scripts/setup_blogwatcher.sh` | Initialize RSS feeds (run once, idempotent) |

**blogwatcher commands:**
- `blogwatcher scan` - Scan all RSS feeds for new articles
- `blogwatcher articles` - List recent articles
- `blogwatcher read <id>` - Mark article as read
- `blogwatcher blogs` - List tracked blogs

## Configuration

**Optional config file:** `config.json` (copy from `config.example.json`)

RSS URLs for every source are **hard-coded** in `rss_sources` — they are resolved once and stored, so the script never needs to re-discover them. If you add a new source, find its RSS feed once and add it to this list.

```json
{
  "blogwatcher_path": "~/go/bin/blogwatcher",
  "timezone_offset": 8,
  "gemini_timeout": 180,
  "rss_check_timeout": 10,
  "max_articles": 30,
  "output_dir": "~/ai-tech-briefs",
  "rss_sources": [
    {"name": "TLDR AI", "rss": "https://tldr.tech/rss", "category": "newsletter"},
    {"name": "OpenAI",  "rss": "https://openai.com/news/rss", "category": "ai_lab"}
  ],
  "web_only_sources": [
    {"name": "The Rundown AI", "url": "https://therundown.ai", "category": "newsletter"}
  ]
}
```

**Source categories:** `newsletter` | `ai_lab` | `research_org`

**Usage:**
```bash
python3 scripts/generate_brief.py --config config.json --output /tmp/brief.md
```

## Troubleshooting

### blogwatcher not found

```bash
# Install blogwatcher
go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest

# Verify installation
~/go/bin/blogwatcher --version
```

### Gemini CLI timeout

The script has a 120-second timeout. If Gemini CLI consistently times out:

1. Check your internet connection
2. Try running `gemini "test"` manually
3. Increase timeout in `config.json`: `"gemini_timeout": 180`

### RSS feeds not updating

```bash
# Force rescan
~/go/bin/blogwatcher scan

# Check if feeds are valid
curl -I https://tldr.tech/rss
```

### No articles found

Some blogs don't have RSS feeds. The script falls back to Gemini CLI web search. Check logs:

```bash
cat ~/ai-tech-briefs/generate.log
```

### Brief generation fails

1. Check log file: `~/ai-tech-briefs/generate.log`
2. Test Gemini CLI manually: `gemini "test prompt"`
3. Verify Python 3 is available: `python3 --version`

### Duplicate articles

The script has built-in deduplication using content hashing. If you see duplicates:

1. Clear the seen hashes (restart the script)
2. Check if RSS feeds are publishing duplicates

### Cron job not running

```bash
# Check cron status
openclaw cron status

# Check cron logs
openclaw cron runs --id ai-tech-daily-brief --limit 5
```

## Testing

Run locally before deploying:

```bash
cd skills/ai-tech-brief

# Test mode with output
python3 scripts/generate_brief.py --test --output /tmp/test-brief.md

# View output
cat /tmp/test-brief.md

# Check logs
cat ~/ai-tech-briefs/generate.log
```

## References

| File | Content |
|------|---------|
| `references/sources.md` | Complete source list with URLs |
| `config.example.json` | Configuration template |

## Related Skills

- **investment-brief** - Daily market/investment summaries
- **github-digest** - GitHub activity summaries
- **research-monitor** - Academic paper tracking

---

**Version:** 1.4
**Author:** Dean (ClawCoding)
**Last Updated:** March 2, 2026
**Changelog:**
- v1.4: Aligned config with RSS_FEED_STATUS.md findings; separated no-RSS sources into web_only_sources
- v1.3: Added RSS_FEED_STATUS.md; documented that only 3/13 RSS feeds are active
- v1.2: Hard-coded RSS URLs in config; RSS reachability check; ⚠️ failure section in brief
- v1.1: Added logging, error handling, config file, deduplication
- v1.0: Initial release
