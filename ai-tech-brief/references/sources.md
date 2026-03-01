# AI Tech Brief - Complete Source List

**Last Verified:** March 1, 2026

---

## Twitter/X Accounts (12)

| Name | Handle | URL | Focus |
|------|--------|-----|-------|
| Andrej Karpathy | @karpathy | https://x.com/karpathy | Eureka Labs, LLM education |
| Ilya Sutskever | @ilyasut | https://x.com/ilyasut | SSI Founder, AI safety |
| Andrew Ng | @AndrewYNg | https://x.com/AndrewYNg | AI education pioneer |
| Lilian Weng | @lilianweng | https://x.com/lilianweng | Thinking Machines, AI safety |
| Jim Fan | @DrJimFan | https://x.com/DrJimFan | NVIDIA, embodied AI |
| Jeremy Howard | @jeremyphoward | https://x.com/jeremyphoward | fast.ai |
| Nathan Lambert | @natolambert | https://x.com/natolambert | RLHF, open-source models |
| Phil Duan | @philduanai | https://x.com/philduanai | AI applications/products |
| Harrison Chase | @hwchase17 | https://x.com/hwchase17 | LangChain founder |
| Guillermo Rauch | @rauchg | https://x.com/rauchg | Vercel CEO, dev tools |
| Pieter Levels | @levelsio | https://x.com/levelsio | Indie developer |
| swyx | @swyx | https://x.com/swyx | Latent Space host |

**Fetch Method:** Gemini CLI web search (no API key needed)

---

## Newsletters (9)

| Name | URL | RSS Feed | Status |
|------|-----|----------|--------|
| Ben's Bites | https://bensbites.com | https://bensbites.beehiiv.com/rss | ✅ Active |
| TLDR AI | https://tldr.tech/ai | https://tldr.tech/rss | ✅ Active |
| Latent Space | https://latentspace.blog | https://latentspace.blog/rss | ✅ Active |
| Interconnects | https://interconnects.ai | https://interconnects.ai/rss | ✅ Active |
| The Neuron | https://theneuron.ai | https://theneuron.beehiiv.com/rss | ✅ Active |
| Import AI | https://jack-clark.net | https://jack-clark.net/feed/ | ✅ Active |
| The Batch | https://www.deeplearning.ai/the-batch | https://www.deeplearning.ai/the-batch/feed/ | ✅ Active |
| The Rundown AI | https://therundown.ai | - | ⚠️ Web only |
| Superhuman AI | https://superhuman.ai | - | ⚠️ Web only |

**Fetch Method:** blogwatcher RSS feeds (web fallback via Gemini CLI)

---

## AI Lab Blogs (4)

| Lab | URL | RSS Feed | Status |
|-----|-----|----------|--------|
| OpenAI | https://openai.com/blog | https://openai.com/news/rss | ✅ Active |
| Anthropic | https://anthropic.com/news | https://www.anthropic.com/news?format=rss | ✅ Active |
| Google DeepMind | https://deepmind.google/discover/blog | https://deepmind.google/discover/blog/rss/ | ✅ Active |
| Meta AI | https://ai.meta.com/blog | https://ai.meta.com/blog/rss/ | ✅ Active |

**Fetch Method:** blogwatcher RSS feeds

---

## Research Organizations (2)

| Name | URL | RSS Feed | Focus |
|------|-----|----------|-------|
| LMSYS | https://lmsys.org/blog | https://lmsys.org/blog/rss/ | Benchmarks, open models |
| Hugging Face | https://huggingface.co/blog | https://huggingface.co/blog/feed.xml | Open-source models |

**Fetch Method:** blogwatcher RSS feeds

---

## arXiv Categories

| Code | Category | Priority |
|------|----------|----------|
| cs.LG | Machine Learning | 🔴 High |
| cs.AI | Artificial Intelligence | 🔴 High |
| cs.SE | Software Engineering | 🔴 High |
| cs.CL | Computation and Language | 🟡 Medium |
| cs.CV | Computer Vision | 🟡 Medium |
| cs.NE | Neural and Evolutionary Computing | 🟢 Low |

**Fetch Method:** Gemini CLI web search

---

## Backup Sources

If primary sources fail, these provide similar content:

| Category | Backup Source |
|----------|---------------|
| AI News | https://venturebeat.com/ai/ |
| Research | https://www.technologyreview.com/topic/artificial-intelligence/ |
| Papers | https://paperswithcode.com/ |
| Models | https://huggingface.co/spaces |

---

## Fetch Priorities

1. **Morning sweep** (8 AM Beijing): Check all sources
2. **Filter**: Remove duplicates, low-signal items
3. **Prioritize**: Papers > Lab blogs > Newsletters > Tweets
4. **Summarize**: 2-3 sentences per item max

---

## Verification Commands

```bash
# Test RSS feeds
curl -I https://tldr.tech/rss

# Check blogwatcher status
~/go/bin/blogwatcher blogs

# Scan for new articles
~/go/bin/blogwatcher scan

# List recent articles
~/go/bin/blogwatcher articles
```

---

## Known Issues

| Source | Issue | Workaround |
|--------|-------|------------|
| The Rundown AI | No RSS feed | Gemini CLI web search |
| Superhuman AI | No RSS feed | Gemini CLI web search |
| Twitter/X | Rate limits | Gemini CLI web search (no API needed) |

---

*Maintained as part of the ai-tech-brief skill*  
*GitHub: https://github.com/zhanglpg/skills*
