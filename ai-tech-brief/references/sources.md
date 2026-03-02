# AI Tech Brief - Complete Source List

**Last Verified:** March 2, 2026  
**RSS Status:** See `RSS_FEED_STATUS.md` for detailed feed testing results

---

## ⚠️ Important Note on RSS Feeds

Only **3 out of 13 RSS feeds are working properly** (23% success rate):
- ✅ Import AI
- ✅ Anthropic
- ✅ Hugging Face

The skill uses a **hybrid approach**:
1. **blogwatcher** for the few working RSS feeds
2. **Gemini CLI web search** for comprehensive coverage of all 26 sources

This ensures all requested sources are covered even when RSS fails.

---

## 🐦 Twitter/X Accounts (12)

| Name | Handle | URL | Focus | Fetch Method |
|------|--------|-----|-------|--------------|
| Andrej Karpathy | @karpathy | https://x.com/karpathy | Eureka Labs, LLM education | Gemini Web Search |
| Ilya Sutskever | @ilyasut | https://x.com/ilyasut | SSI Founder, AI safety | Gemini Web Search |
| Andrew Ng | @AndrewYNg | https://x.com/AndrewYNg | AI education pioneer | Gemini Web Search |
| Lilian Weng | @lilianweng | https://x.com/lilianweng | Thinking Machines, AI safety | Gemini Web Search |
| Jim Fan | @DrJimFan | https://x.com/DrJimFan | NVIDIA, embodied AI | Gemini Web Search |
| Jeremy Howard | @jeremyphoward | https://x.com/jeremyphoward | fast.ai | Gemini Web Search |
| Nathan Lambert | @natolambert | https://x.com/natolambert | RLHF, open-source models | Gemini Web Search |
| Phil Duan | @philduanai | https://x.com/philduanai | AI applications/products | Gemini Web Search |
| Harrison Chase | @hwchase17 | https://x.com/hwchase17 | LangChain founder | Gemini Web Search |
| Guillermo Rauch | @rauchg | https://x.com/rauchg | Vercel CEO, dev tools | Gemini Web Search |
| Pieter Levels | @levelsio | https://x.com/levelsio | Indie developer | Gemini Web Search |
| swyx | @swyx | https://x.com/swyx | Latent Space host | Gemini Web Search |

**Note:** Twitter/X doesn't have reliable RSS feeds. All Twitter content is fetched via Gemini CLI web search.

---

## 📰 Newsletters (8)

| Name | URL | RSS Feed | Status | Fetch Method |
|------|-----|----------|--------|--------------|
| **Import AI** | https://jack-clark.net | https://jack-clark.net/feed/ | ✅ **WORKING** | blogwatcher + Gemini |
| **TLDR AI** | https://tldr.tech/ai | https://tldr.tech/rss | ⚠️ Redirects | blogwatcher + Gemini |
| **Latent Space** | https://latentspace.blog | https://latentspace.blog/rss | ⚠️ Redirects | blogwatcher + Gemini |
| **Ben's Bites** | https://bensbites.com | https://bensbites.beehiiv.com/rss | ❌ Blocked (403) | Gemini Web Search |
| **The Neuron** | https://theneuron.ai | https://theneuron.beehiiv.com/rss | ❌ Blocked (403) | Gemini Web Search |
| **Interconnects** | https://interconnects.ai | https://interconnects.ai/rss | ❌ Error (405) | Gemini Web Search |
| **The Batch** | https://www.deeplearning.ai/the-batch | - | ❌ No RSS | Gemini Web Search |
| **Superhuman AI** | https://superhuman.ai | - | ❌ No RSS | Gemini Web Search |

**Working RSS:** 1 out of 8 (Import AI)

---

## 🏢 AI Labs (4)

| Lab | URL | RSS Feed | Status | Fetch Method |
|-----|-----|----------|--------|--------------|
| **Anthropic** | https://anthropic.com/news | https://www.anthropic.com/news?format=rss | ✅ **WORKING** | blogwatcher + Gemini |
| **OpenAI** | https://openai.com/blog | https://openai.com/news/rss | ❌ Blocked (403) | Gemini Web Search |
| **Google DeepMind** | https://deepmind.google/discover/blog | - | ❌ No RSS | Gemini Web Search |
| **Meta AI** | https://ai.meta.com/blog | - | ❌ No RSS | Gemini Web Search |

**Working RSS:** 1 out of 4 (Anthropic)

---

## 🔬 Research Organizations (2)

| Name | URL | RSS Feed | Status | Fetch Method |
|------|-----|----------|--------|--------------|
| **Hugging Face** | https://huggingface.co/blog | https://huggingface.co/blog/feed.xml | ✅ **WORKING** | blogwatcher + Gemini |
| **LMSYS** | https://lmsys.org/blog | - | ❌ No RSS | Gemini Web Search |

**Working RSS:** 1 out of 2 (Hugging Face)

---

## 📄 arXiv Categories

| Code | Category | Priority | Fetch Method |
|------|----------|----------|--------------|
| cs.LG | Machine Learning | 🔴 High | Gemini Web Search |
| cs.AI | Artificial Intelligence | 🔴 High | Gemini Web Search |
| cs.SE | Software Engineering | 🔴 High | Gemini Web Search |
| cs.CL | Computation and Language | 🟡 Medium | Gemini Web Search |
| cs.CV | Computer Vision | 🟡 Medium | Gemini Web Search |
| cs.NE | Neural and Evolutionary Computing | 🟢 Low | Gemini Web Search |

**Fetch Method:** Gemini CLI searches arXiv directly

---

## 📊 Source Coverage Summary

| Category | Total Sources | Working RSS | Primary Fetch Method |
|----------|---------------|-------------|---------------------|
| Twitter/X | 12 | 0 | Gemini Web Search |
| Newsletters | 8 | 1 | Gemini Web Search + RSS |
| AI Labs | 4 | 1 | Gemini Web Search + RSS |
| Research Orgs | 2 | 1 | Gemini Web Search + RSS |
| arXiv | 6 categories | N/A | Gemini Web Search |
| **TOTAL** | **32** | **3 (9%)** | **Hybrid** |

---

## 🔧 Why This Works

Despite only 3 working RSS feeds, the skill successfully covers all sources because:

1. **Gemini CLI has web search capability** - Can check any website
2. **Prompt enforces comprehensive coverage** - Must check all 26 sources
3. **Source coverage report** - Shows which sources were checked
4. **Fallback mechanism** - If RSS fails, web search covers it

---

## ✅ Verification Commands

```bash
# Test RSS feeds manually
curl -I https://jack-clark.net/feed/
curl -I https://www.anthropic.com/news?format=rss
curl -I https://huggingface.co/blog/feed.xml

# Check blogwatcher status
~/go/bin/blogwatcher blogs
~/go/bin/blogwatcher scan
~/go/bin/blogwatcher articles

# View RSS status report
cat RSS_FEED_STATUS.md
```

---

## 📝 Related Files

- `RSS_FEED_STATUS.md` - Detailed RSS feed testing results
- `scripts/setup_blogwatcher.sh` - Setup script with working feeds
- `scripts/generate_brief.py` - Main script with hybrid fetch strategy

---

*Maintained as part of the ai-tech-brief skill*  
*GitHub: https://github.com/zhanglpg/skills*
