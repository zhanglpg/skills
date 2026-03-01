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

**Script:** Use `scripts/fetch_twitter.py` to fetch recent tweets from these accounts.

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

**Script:** Use `scripts/fetch_newsletters.py` to scrape latest posts.

### Tier 3: Academic & Research (3 categories)

1. **arXiv Papers** - cs.LG, cs.AI, cs.SE categories
2. **AI Lab Blogs** - OpenAI, Anthropic, Google DeepMind, Meta AI
3. **LMSYS** - lmsys.org/blog

**Script:** Use `scripts/fetch_arxiv.py` for latest papers.

## Output Format

Structure the brief as:

```markdown
# 🤖 Daily AI Tech Brief - [DATE]

## 📊 Top Stories (3-5 items)

### [Headline]
- **Summary:** 1-2 sentences
- **Why it matters:** Impact/significance
- **Source:** [Link](url)

## 📄 New Research Papers

| Paper | Key Finding | Link |
|-------|-------------|------|
| [Title] | Finding | arXiv:XXXX |

## 🐦 Notable Tweets/Announcements

- [@user](url): Tweet summary

## 📰 Newsletter Highlights

- **Publication:** Key story

## 🔗 Quick Links

- [Link 1](url) - Description
- [Link 2](url) - Description
```

## Workflow

1. **Fetch** - Run fetch scripts for all source tiers
2. **Filter** - Select high-signal items (avoid duplicates, hype)
3. **Summarize** - Write concise summaries with "why it matters"
4. **Format** - Structure as markdown with tables/lists
5. **Deliver** - Post to Discord channel via cron delivery

## Scheduling

**Cron Expression:** `0 9 * * *` (9:00 AM Asia/Shanghai)

**Delivery:** Discord channel `channel:1477516149968339127`

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
| `scripts/setup_blogwatcher.sh` | Initialize RSS feeds (run once) |

**blogwatcher commands:**
- `blogwatcher scan` - Scan all RSS feeds for new articles
- `blogwatcher articles` - List recent articles
- `blogwatcher read <id>` - Mark article as read
- `blogwatcher blogs` - List tracked blogs

## References

| File | Content |
|------|---------|
| `references/sources.md` | Complete source list with URLs |
| `references/arxiv_categories.md` | Relevant arXiv category codes |
| `references/template.md` | Output template examples |

## Configuration

Store in `TOOLS.md` or environment:

```bash
# Optional: API keys for enhanced fetching
TWITTER_API_KEY=xxx
ARXIV_API_BASE=https://export.arxiv.org/api/query
```

## Error Handling

- **API rate limits:** Retry with exponential backoff
- **Missing sources:** Skip and note in brief
- **Duplicate detection:** Hash-based deduplication
- **Delivery failure:** Log error, retry next cycle

## Testing

Run locally before deploying:

```bash
cd skills/ai-tech-brief
python3 scripts/generate_brief.py --test --output /tmp/test-brief.md
cat /tmp/test-brief.md
```

## Related Skills

- **investment-brief** - Daily market/investment summaries
- **github-digest** - GitHub activity summaries
- **research-monitor** - Academic paper tracking

---

**Version:** 1.0  
**Author:** Dean (ClawCoding)  
**Last Updated:** March 1, 2026
