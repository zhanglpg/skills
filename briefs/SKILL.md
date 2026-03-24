---
name: briefs
description: "Generate daily briefs (AI tech or investment/portfolio) from curated sources. Reads a config JSON for source lists, fetches content via web tools, and produces a structured markdown brief. Triggers: daily brief, AI news brief, portfolio brief, market brief, investment brief, morning brief."
---

# Daily Brief Generator

Generate a daily brief by fetching content from curated sources and summarizing it into a structured markdown report.

## Instructions

### Step 1: Determine Brief Type

Ask the user which brief to generate if not specified:
- **AI Tech Brief** — `config.ai-tech.json`
- **Portfolio Brief** — `config.portfolio.json`

Or accept a `--config <path>` argument.

### Step 2: Read Configuration

Read the chosen config JSON file from this skill's directory. The config contains:
- `twitter_accounts` — handles to search for recent tweets
- `rss_sources` — sources with RSS feed URLs (fetch and parse these)
- `web_only_sources` — sources to search the web for (no RSS)
- `arxiv_categories` — arXiv categories to query (AI tech only)
- `portfolio_holdings` — held positions grouped by sector (portfolio only)
- `watchlist` — tickers and themes to monitor (portfolio only)
- `extra_data_path` — path to pre-exported quantitative JSON (portfolio only)
- `output_dir` — where to save the brief
- `brief_title` — display title for the brief

### Step 3: Gather Content

Fetch content from ALL configured sources. Use your web tools freely — you are both the fetcher and summarizer. Gather as much relevant content as possible.

#### RSS Feeds
For each source in `rss_sources`, fetch the RSS URL and extract recent article titles, URLs, dates, and summaries. If a feed fails, note it and move on.

#### arXiv Papers
If `arxiv_categories` is non-empty, search arXiv for recent papers in those categories. Record exact paper IDs, titles, authors, and abstract summaries.

#### Hacker News
Search for top AI-related stories on Hacker News. Include titles, URLs, scores, and comment counts.

#### GitHub Trending
Search for trending AI/ML repositories on GitHub from the past week. Include repo names, stars, languages, and descriptions.

#### Twitter/X
For each handle in `twitter_accounts`, search for their recent tweets (past 24-48 hours). Only include tweets you actually find.

#### Web-Only Sources
For each source in `web_only_sources`, search the web for their latest content. Focus on sources in the `newsletter`, `ai_lab`, `research_org`, `news`, and `analysis` categories.

#### Extra Quantitative Data (Portfolio only)
If `extra_data_path` is set and the file exists, read and incorporate it. Warn if the data is more than 2 days old (check the `generated_at` field).

### Step 4: Write the Brief

Compose the brief following the editorial guidelines and output format below. Choose the correct set based on the config used.

**Key rules:**
1. Every URL, title, and data point must come from your actual fetched content. Never fabricate.
2. Lead with the most impactful stories — items that appear across multiple sources belong at the top.
3. Merge duplicate coverage into single entries with multiple source links.
4. Skip sections that have no content rather than writing filler.
5. Prefer depth over breadth — meaningful commentary beats a long list.
6. It is better to have a shorter brief with all real content than a longer brief with fabricated entries.

### Step 5: Save Output

Save the brief to: `{output_dir}/{YYYY-MM-DD}-brief.md`

Where `output_dir` comes from the config (expand `~` and `$AGENT_DATA_DIR` as needed).

After saving, print the full brief to the console as well.

---

## AI Tech Brief — Editorial Guidelines

Use these guidelines when generating from `config.ai-tech.json`:

### Section Instructions

**Top Stories (3-5 items):**
Select the most significant items from ALL sources combined. Each item needs a clear headline, 1-2 sentence summary, why it matters, and source link(s) with exact URLs.

**Twitter/X Updates:**
Only include tweets you actually find. Group related tweets if multiple accounts discuss the same topic.

**Newsletter & Blog Highlights:**
Summarize notable articles from RSS feeds and web sources. Attribute each to its source with exact title and URL.

**AI Lab Updates:**
Highlight announcements from major AI labs (Anthropic, OpenAI, Google DeepMind, Meta AI, etc.). Only include if there is actual content.

**Research Papers:**
Summarize arXiv papers in a table format. Use exact arXiv IDs, URLs, and author names. Focus on the key finding.

**Hacker News AI Highlights:**
Use exact URLs, scores, and comment counts. Include both the article link and the HN discussion link.

**GitHub Trending:**
Use exact repo names, star counts, languages, and URLs.

**Quick Links:**
Remaining noteworthy items that didn't warrant full coverage. One line each.

### AI Tech Output Format

```markdown
# {brief_title} - {date}

## Top Stories

### [Headline]
- **Summary:** 1-2 sentences
- **Why it matters:** Impact/significance
- **Source:** [Original Article Title](url)

## Twitter/X Updates
- **@[handle]:** [Tweet summary] — [Link](url)

## Newsletter & Blog Highlights
- **[Source Name]:** [Article title] — [Link](url) — 1-2 sentence summary

## AI Lab Updates
- **[Lab Name]:** [Announcement] — [Link](url) — 1-2 sentence summary

## Research Papers
| Paper | Key Finding | Link |
|-------|-------------|------|
| [Title] | 1-2 sentence summary | [arXiv:ID](url) |

## Hacker News AI Highlights
- **[Title]** (score pts, N comments) — [Link](url) | [Discussion](hn_url)

## GitHub Trending
- **[repo/name]** (language, stars) — [Link](url) — description

## Quick Links
- [Title](url) — 1 sentence description

---
*Sources: RSS, arXiv API, Hacker News, GitHub, Twitter/X, Web*
```

---

## Portfolio Brief — Editorial Guidelines

Use these guidelines when generating from `config.portfolio.json`:

### Portfolio Context

When portfolio holdings and/or a watchlist are provided in the config:
1. In "Portfolio Impact", identify which stories directly affect held tickers or sectors.
2. In "Watchlist Alerts", flag stories relevant to watchlist tickers or themes.
3. When ranking "Top Stories", give extra weight to stories affecting held positions.
4. If no stories affect a holding or watchlist item, do not fabricate relevance.

### Section Instructions

**Market Snapshot:**
Summarize overall market conditions. If quantitative data is available, use it for actual closing prices and change percentages. Include key index levels and a 1-2 sentence sentiment assessment.

**Top Stories (3-5 items):**
Most impactful market-moving stories. Each needs a headline, summary, market impact, and source link.

**Portfolio Impact:**
Map stories to specific holdings. Only include holdings actually affected. Provide action considerations (Hold/Monitor/Review).

**Watchlist Alerts:**
Flag stories relevant to watchlist tickers and themes. Explain what happened and why it matters.

**Twitter/X Market Commentary:**
Only include tweets you actually find. Focus on market-relevant commentary.

**Technical & Risk Dashboard:**
If quantitative data is available, summarize technical signals, risk metrics, and alerts using exact numbers.

**Macro & Economic Data:**
Cover economic releases, Fed commentary, policy changes. Include specific readings and impact assessments.

**Sector Movers:**
Notable sector rotation or moves with direction, magnitude, and catalyst.

**Earnings & Corporate News:**
Notable earnings reports or corporate events with specific results (EPS, revenue, guidance).

**Newsletter & Analysis Highlights:**
Summarize notable analysis from feeds and web sources. Attribute with exact title and URL.

**Quick Links:**
Remaining noteworthy items. One line each.

### Portfolio Output Format

```markdown
# {brief_title} - {date}

## Market Snapshot

| Symbol | Price | Change | Sector |
|--------|-------|--------|--------|
| SPY | — | — | US Broad Market |
| QQQ | — | — | Nasdaq 100 |
| [other holdings] | — | — | — |

**Market Sentiment:** [1-2 sentence assessment]

## Top Stories

### [Headline]
- **Summary:** 1-2 sentences
- **Market Impact:** How this affects markets/portfolios
- **Source:** [Original Article Title](url)

## Portfolio Impact

### [Sector/Theme]
- **[TICKER]:** [How this affects this position] — [Source](url)
  - **Action consideration:** [Hold/Monitor/Review — brief rationale]

## Watchlist Alerts
- **[TICKER or Theme]:** [What happened] — [Source](url)
  - **Why it matters:** [1 sentence on potential opportunity or risk]

## Twitter/X Market Commentary
- **@[handle]:** [Tweet summary] — [Link](url)

## Technical & Risk Dashboard
- **Bullish:** [Symbols above SMA-20 with positive momentum]
- **Bearish:** [Symbols below SMA-20 or high drawdown]
- **Most Volatile:** [Top 3 by daily volatility]
- **Portfolio Correlation:** [Average pairwise correlation]
- **Alerts:** [Quantitative threshold-based alerts]

## Macro & Economic Data
- **Yield Curve:** [Status]
- **VIX Regime:** [Low/Medium/High — value]
- **Rate Direction:** [Rising/Falling/Stable]
- **[Indicator/Event]:** [Reading/Outcome] — Impact assessment

## Sector Movers
- **[Sector]:** [Direction and magnitude] — [Catalyst] — [Link](url)

## Earnings & Corporate News
- **[Company]:** [Result/Event] — [Link](url) — 1-2 sentence summary

## Newsletter & Analysis Highlights
- **[Source Name]:** [Article title] — [Link](url) — 1-2 sentence summary

## Quick Links
- [Title](url) — 1 sentence description

---
*Sources: RSS, Twitter/X, Web | Portfolio: positions across sectors | Watchlist: tickers, themes*
```

---

## Configuration

**Config files** (in this skill's directory):
- `config.ai-tech.json` — AI technology news brief
- `config.portfolio.json` — Financial markets and portfolio tracking

## Scheduling

**Cron Expression:** `0 9 * * *` (9:00 AM Asia/Shanghai)

**Save Location:** `~/briefs/YYYY-MM-DD-brief.md` (or as configured in `output_dir`)

---

**Version:** 3.0
**Changelog:**
- v3.0: Removed Python script layer — LLM-native skill that fetches and summarizes directly
- v2.0: Fetch-first architecture with Python orchestration
- v1.0: Initial release
