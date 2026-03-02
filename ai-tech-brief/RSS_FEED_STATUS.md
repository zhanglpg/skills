# RSS Feed Status Report

**Generated:** March 2, 2026  
**Test Method:** HTTP HEAD requests to each RSS URL

---

## 📊 Summary

| Category | Total | Working | Blocked (403) | Not Found (404) | Other Issues |
|----------|-------|---------|---------------|-----------------|--------------|
| Newsletters | 7 | 1 (14%) | 2 (29%) | 1 (14%) | 3 (43%) |
| AI Labs | 4 | 1 (25%) | 1 (25%) | 2 (50%) | 0 (0%) |
| Research Orgs | 2 | 1 (50%) | 0 (0%) | 1 (50%) | 0 (0%) |
| **TOTAL** | **13** | **3 (23%)** | **3 (23%)** | **4 (31%)** | **3 (23%)** |

---

## 📰 Newsletters (7)

| Name | URL | Status | Code | Notes |
|------|-----|--------|------|-------|
| **Ben's Bites** | https://bensbites.beehiiv.com/rss | ❌ BLOCKED | 403 | Cloudflare protection |
| **TLDR AI** | https://tldr.tech/rss | ⚠️ REDIRECT | 308 | Redirects to /api/rss/tech |
| **Latent Space** | https://latentspace.blog/rss | ⚠️ REDIRECT | 301 | Working but redirects |
| **Interconnects** | https://interconnects.ai/rss | ❌ ERROR | 405 | Method not allowed |
| **The Neuron** | https://theneuron.beehiiv.com/rss | ❌ BLOCKED | 403 | Cloudflare protection |
| **Import AI** | https://jack-clark.net/feed/ | ✅ WORKING | 200 | Perfect |
| **The Batch** | https://www.deeplearning.ai/the-batch/feed/ | ❌ NOT FOUND | 404 | Feed doesn't exist |

### Working Newsletters:
- Import AI ✅

### Alternative URLs to Try:
- TLDR AI: Try https://tldr.tech/api/rss/tech
- Latent Space: Already works (just redirects)

---

## 🏢 AI Labs (4)

| Name | URL | Status | Code | Notes |
|------|-----|--------|------|-------|
| **OpenAI** | https://openai.com/news/rss | ❌ BLOCKED | 403 | Cloudflare protection |
| **Anthropic** | https://www.anthropic.com/news?format=rss | ✅ WORKING | 200 | Perfect |
| **Google DeepMind** | https://deepmind.google/discover/blog/rss/ | ❌ NOT FOUND | 404 | Wrong URL |
| **Meta AI** | https://ai.meta.com/blog/rss/ | ❌ NOT FOUND | 404 | Wrong URL |

### Working AI Labs:
- Anthropic ✅

### Alternative URLs to Try:
- Google DeepMind: Try https://deepmind.google/blog/rss.xml
- Meta AI: Try https://ai.meta.com/blog/rss.xml

---

## 🔬 Research Organizations (2)

| Name | URL | Status | Code | Notes |
|------|-----|--------|------|-------|
| **LMSYS** | https://lmsys.org/blog/rss/ | ❌ NOT FOUND | 404 | Wrong URL |
| **Hugging Face** | https://huggingface.co/blog/feed.xml | ✅ WORKING | 200 | Perfect |

### Working Research Orgs:
- Hugging Face ✅

### Alternative URLs to Try:
- LMSYS: Try https://lmsys.org/blog/feed.xml or check website for RSS link

---

## ✅ Currently Working RSS Feeds (3 Total)

1. **Import AI** - https://jack-clark.net/feed/
2. **Anthropic** - https://www.anthropic.com/news?format=rss
3. **Hugging Face** - https://huggingface.co/blog/feed.xml

---

## 🔧 Recommended Actions

### Option 1: Fix Broken URLs
Update setup_blogwatcher.sh with correct RSS URLs where available.

### Option 2: Use Web Scraping Fallback
For sources without working RSS, use Gemini CLI web search as fallback.

### Option 3: Hybrid Approach
- Use blogwatcher for the 3 working RSS feeds
- Use Gemini CLI web search for Twitter/X and non-RSS sources
- This is the current implementation

---

## 📝 Why So Many Failures?

1. **Cloudflare Protection (403)** - Ben's Bites, The Neuron, OpenAI
   - These sites use bot protection
   - Would need browser automation or API keys

2. **Wrong URLs (404)** - Google DeepMind, Meta AI, LMSYS, The Batch
   - RSS feeds may have moved or don't exist at these paths
   - Need to find correct URLs from websites

3. **Method Issues (405)** - Interconnects
   - Server doesn't accept HEAD requests
   - May work with GET requests

---

## 🎯 Conclusion

Only **3 out of 13 RSS feeds are working properly** (23% success rate).

**Recommendation:** Keep the current hybrid approach:
- Use blogwatcher for the few working RSS feeds
- Rely on Gemini CLI web search for comprehensive source coverage
- This ensures all 26 sources are checked even without working RSS

The skill is designed to work this way - RSS is just one input source, and Gemini CLI covers everything via web search.
