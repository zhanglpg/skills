---
name: ai-tech-brief
description: "Generate daily AI technology news briefs covering AI infrastructure, agentic coding, and research progress. Use when creating scheduled technical news digests from high-quality sources including arXiv papers, AI lab blogs, Twitter/X thought leaders, and newsletters. Triggers: daily briefs, AI news summaries, technical research digests, scheduled news reports."
---

# Briefs Skill

Generate daily briefs from curated sources using a fetch-first, summarize-second pipeline.

## Quick Start

```bash
# Run via cron job (configured in OpenClaw)
openclaw cron run ai-tech-daily-brief

# Or invoke directly
cd skills/briefs
python3 scripts/generate_brief.py --output /tmp/brief.md

# Use a custom config
python3 scripts/generate_brief.py --config config.ai-tech.json --output /tmp/brief.md
```

## How It Works

The pipeline runs in five stages:

1. **Fetch RSS** — Parses RSS/Atom feeds directly via `xml.etree` (no external dependencies)
2. **Fetch APIs** — Calls arXiv, Hacker News, and GitHub Search APIs in parallel
3. **Fetch Web** — Extracts content from web-only sources via `httpx` + `trafilatura`
4. **Summarize** — Passes all verified, pre-fetched content to Gemini CLI for summarization and template filling
5. **Render** — Validates output, appends a source coverage report, and writes the final file

**Design principle:** Gemini is used as a *summarizer*, not a *fetcher*. All content is collected deterministically first. Gemini only searches the web for Twitter/X accounts and any sources that could not be fetched directly.

## Dependencies

| Tool | Purpose | Install |
|------|---------|---------|
| **Python 3** | Script orchestration | Built-in on macOS/Linux |
| **gemini** | Summarization & Twitter search | `brew install gemini-cli` |
| **httpx** (optional) | HTTP fetching with redirects | `pip install httpx` |
| **trafilatura** (optional) | Web page content extraction | `pip install trafilatura` |

If `httpx`/`trafilatura` are not installed, the script falls back to `urllib` and regex-based extraction.

## Configuration

**Config file:** `config.ai-tech.json` (loaded automatically; pass `--config` to use a different file)

```json
{
  "arxiv_categories": ["cs.LG", "cs.AI"],
  "twitter_accounts": ["handle1", "handle2"],
  "rss_sources": [
    {"name": "Source Name", "rss": "https://example.com/feed", "category": "newsletter"}
  ],
  "web_only_sources": [
    {"name": "Source Name", "url": "https://example.com", "category": "newsletter"}
  ],
  "timezone_offset": 8,
  "gemini_timeout": 180,
  "rss_check_timeout": 10,
  "fetch_timeout": 15,
  "max_articles": 30,
  "output_dir": "~/briefs",
  "log_file": "~/briefs/generate.log",
  "template": "templates/ai-tech-brief.md",
  "brief_title": "Daily Brief"
}
```

**Source categories:** Any string value — used to group sources in the coverage report. The AI tech config uses `newsletter`, `ai_lab`, `research_org`, `youtube`, `podcast`, and `community`.

**arxiv_categories:** Leave as `[]` to skip arXiv fetching.

**twitter_accounts:** List of handles without `@`. Fetched via Gemini web search.

## Templates

The template file (set via `"template"` in config) defines the output format. It supports `$placeholder` substitution:

| Placeholder | Value |
|-------------|-------|
| `$brief_title` | `brief_title` from config |
| `$date_display` | Current date (e.g. `March 5, 2026`) |
| `$rss_count` | Number of RSS articles fetched |
| `$arxiv_count` | Number of arXiv papers fetched |
| `$hn_count` | Number of Hacker News stories fetched |
| `$github_count` | Number of GitHub repos fetched |
| `$web_count` | Number of web pages fetched |
| `$twitter_count` | Number of Twitter accounts searched |

The filled template is passed to Gemini as the required output format. See `templates/ai-tech-brief.md` for an example.

## Scripts

| Script | Purpose |
|--------|---------|
| `scripts/generate_brief.py` | Main orchestrator — CLI entry point |
| `scripts/fetcher.py` | Content fetching (RSS, APIs, web extraction) |
| `scripts/summarizer.py` | Gemini CLI integration and prompt assembly |
| `scripts/renderer.py` | Template rendering, validation, and file output |

## Scheduling

**Cron Expression:** `0 9 * * *` (9:00 AM Asia/Shanghai)

**Delivery:** Discord channel `channel:1477516149968339127`

**Save Location:** `~/briefs/YYYY-MM-DD-brief.md`

## Testing

```bash
cd skills/briefs

# Run unit tests
python3 -m unittest scripts/test_generate_brief.py -v

# Test mode with output
python3 scripts/generate_brief.py --test --output /tmp/test-brief.md

# View output
cat /tmp/test-brief.md

# Check logs
cat ~/briefs/generate.log
```

## Troubleshooting

### Gemini CLI timeout

1. Check your internet connection
2. Try running `gemini "test"` manually
3. Increase timeout in config: `"gemini_timeout": 180`

### RSS feeds not updating

The script fetches and parses RSS feeds directly. Check logs:

```bash
cat ~/briefs/generate.log
```

### API failures (arXiv, HN, GitHub)

Each API has independent error handling. If one fails, the brief still generates from other sources.

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

## References

| File | Content |
|------|---------|
| `references/sources.md` | Complete source list with URLs |
| `config.ai-tech.json` | AI tech brief configuration |
| `templates/ai-tech-brief.md` | AI tech brief output template |

---

**Version:** 2.0
**Author:** Dean (ClawCoding)
**Last Updated:** March 5, 2026
**Changelog:**
- v2.0: Fetch-first architecture — replaced blogwatcher with direct RSS parsing (xml.etree), added arXiv API, Hacker News API, GitHub Search API, web page content extraction (httpx + trafilatura); Gemini now used as summarizer only, not fetcher; config renamed to config.ai-tech.json; skill docs made generic
- v1.4: Aligned config with RSS_FEED_STATUS.md findings; separated no-RSS sources into web_only_sources
- v1.3: Added RSS_FEED_STATUS.md; documented that only 3/13 RSS feeds are active
- v1.2: Hard-coded RSS URLs in config; RSS reachability check; failure section in brief
- v1.1: Added logging, error handling, config file, deduplication
- v1.0: Initial release
