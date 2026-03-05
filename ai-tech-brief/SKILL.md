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
```

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3** | Script orchestration | Built-in on macOS/Linux |
| **gemini** | Summarization & Twitter search | `brew install gemini-cli` |
| **httpx** (optional) | HTTP fetching with redirects | `pip install httpx` |
| **trafilatura** (optional) | Web page content extraction | `pip install trafilatura` |

No external binaries (blogwatcher, Go) are required. RSS feeds are parsed with Python's built-in `xml.etree.ElementTree`. If `httpx`/`trafilatura` are not installed, the script falls back to `urllib` and regex-based extraction.

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

**Fetching:** arXiv API (guaranteed real paper IDs), RSS for lab blogs

### Tier 4: Community & Trending

1. **Hacker News** - Top AI stories via Firebase API
2. **GitHub Trending** - AI/ML repos via GitHub Search API

**Fetching:** Direct JSON APIs (structured, reliable)

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

## Workflow (Fetch-First Architecture)

1. **Fetch RSS** - Parse RSS/Atom feeds directly via `xml.etree` (no blogwatcher)
2. **Fetch APIs** - arXiv API, Hacker News Firebase API, GitHub Search API (in parallel)
3. **Fetch Web** - Extract content from web-only sources via `httpx` + `trafilatura`
4. **Summarize** - Pass all pre-fetched, verified content to Gemini CLI for summarization only
5. **Validate** - Check brief structure and source coverage
6. **Report** - Append coverage report and failed-source warnings
7. **Deliver** - Post to Discord channel via cron delivery

**Key design principle:** Gemini is used as a *summarizer*, not a *fetcher*. All content is collected via reliable, deterministic methods first. Gemini only searches the web for Twitter accounts and sources that couldn't be directly fetched.

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
| `scripts/generate_brief.py` | Main orchestration (direct API + RSS + Gemini summarization) |

## Configuration

**Config file:** `config.json`

```json
{
  "timezone_offset": 8,
  "gemini_timeout": 180,
  "rss_check_timeout": 10,
  "fetch_timeout": 15,
  "max_articles": 30,
  "output_dir": "~/ai-tech-briefs",
  "arxiv_categories": ["cs.LG", "cs.AI", "cs.SE"],
  "rss_sources": [
    {"name": "TLDR AI", "rss": "https://tldr.tech/rss", "category": "newsletter"}
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

### Gemini CLI timeout

1. Check your internet connection
2. Try running `gemini "test"` manually
3. Increase timeout in `config.json`: `"gemini_timeout": 180`

### RSS feeds not updating

The script fetches and parses RSS feeds directly (no blogwatcher needed). Check logs:

```bash
cat ~/ai-tech-briefs/generate.log
```

### API failures (arXiv, HN, GitHub)

Each API has independent error handling. If one fails, the brief still generates from other sources. Check logs for details.

### Brief generation fails

1. Check log file: `~/ai-tech-briefs/generate.log`
2. Test Gemini CLI manually: `gemini "test prompt"`
3. Verify Python 3 is available: `python3 --version`

### Optional dependencies not installed

The script works without `httpx` and `trafilatura` but is more reliable with them:

```bash
pip install httpx trafilatura
```

### Cron job not running

```bash
openclaw cron status
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

**Version:** 2.0
**Author:** Dean (ClawCoding)
**Last Updated:** March 5, 2026
**Changelog:**
- v2.0: Fetch-first architecture — replaced blogwatcher with direct RSS parsing (xml.etree), added arXiv API, Hacker News API, GitHub Search API, web page content extraction (httpx + trafilatura); Gemini now used as summarizer only, not fetcher
- v1.4: Aligned config with RSS_FEED_STATUS.md findings; separated no-RSS sources into web_only_sources
- v1.3: Added RSS_FEED_STATUS.md; documented that only 3/13 RSS feeds are active
- v1.2: Hard-coded RSS URLs in config; RSS reachability check; failure section in brief
- v1.1: Added logging, error handling, config file, deduplication
- v1.0: Initial release
