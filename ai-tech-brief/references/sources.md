# AI Tech Brief - Complete Source List

**Last Verified:** March 5, 2026
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

## 📰 Newsletters (13)

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
| **One Useful Thing** | https://www.oneusefulthing.org | - | ❌ No RSS | Gemini Web Search |
| **Unsupervised Learning** | https://danielmiessler.com/newsletter | - | ❌ No RSS | Gemini Web Search |
| **Stratechery** | https://stratechery.com | - | ❌ No RSS | Gemini Web Search |
| **Simon Willison's Weblog** | https://simonwillison.net | https://simonwillison.net/atom/everything/ | ⚠️ Untested | blogwatcher + Gemini |

**Working RSS:** 1 out of 12 confirmed (Import AI); Simon Willison's Weblog untested

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

## 📺 YouTube Channels (6)

| Name | URL | Focus | Fetch Method |
|------|-----|-------|--------------|
| **Matthew Berman** | https://www.youtube.com/@matthew_berman | New model hands-on reviews | Gemini Web Search |
| **Two Minute Papers** | https://www.youtube.com/@TwoMinutePapers | Paper summaries | Gemini Web Search |
| **Yannic Kilcher** | https://www.youtube.com/@YannicKilcher | Technical paper deep-dives | Gemini Web Search |
| **3Blue1Brown** | https://www.youtube.com/@3blue1brown | Math/AI visualizations | Gemini Web Search |
| **Fireship** | https://www.youtube.com/@Fireship | Dev tools & AI news | Gemini Web Search |
| **AI Explained** | https://www.youtube.com/@aiexplained-official | Model evaluations & deep reads | Gemini Web Search |

---

## 🎙️ Podcasts (9)

| Name | Host(s) | URL | Focus | Fetch Method |
|------|---------|-----|-------|--------------|
| **No Priors** | Sarah Guo & Elad Gil | https://www.nopriorsshow.com | AI startups & commercialization | Gemini Web Search |
| **The TWIML AI Podcast** | Sam Charrington | https://twimlai.com/podcast/twimlai | Academic & industry ML | Gemini Web Search |
| **Machine Learning Street Talk** | Tim Scarfe et al. | https://www.youtube.com/@MachineLearningStreetTalk | Deep technical discussions with researchers | Gemini Web Search |
| **Lex Fridman Podcast** | Lex Fridman | https://lexfridman.com/podcast | Long-form interviews (Ilya, LeCun, Hinton…) | Gemini Web Search |
| **Gradient Dissent** | Lukas Biewald | https://wandb.ai/fully-connected/gradient-dissent | Model training & engineering practice (W&B) | Gemini Web Search |
| **Cognitive Revolution** | Nathan Labenz | https://www.cognitiverevolution.ai | AI capability evolution & applications | Gemini Web Search |
| **Dwarkesh Podcast** | Dwarkesh Patel | https://www.dwarkeshpatel.com/podcast | AI alignment & industry analysis | Gemini Web Search |
| **Training Data** | Bowery Capital | https://www.bowerycap.com/blog/training-data | Enterprise AI & B2B | Gemini Web Search |
| **The Robot Brains** | Pieter Abbeel | https://www.therobotbrains.ai | RL & robotics, embodied intelligence | Gemini Web Search |

---

## 🌐 Community / Forums (2)

| Name | URL | Focus | Fetch Method |
|------|-----|-------|--------------|
| **Hacker News** | https://news.ycombinator.com | Tech discussions (AI/ML trending) | Gemini Web Search |
| **GitHub Trending (AI/ML)** | https://github.com/trending | Trending AI/ML repositories | Gemini Web Search |

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
| Newsletters | 13 | 1 | Gemini Web Search + RSS |
| AI Labs | 4 | 1 | Gemini Web Search + RSS |
| Research Orgs | 2 | 1 | Gemini Web Search + RSS |
| YouTube | 6 | 0 | Gemini Web Search |
| Podcasts | 9 | 0 | Gemini Web Search |
| Community | 2 | 0 | Gemini Web Search |
| arXiv | 6 categories | N/A | Gemini Web Search |
| **TOTAL** | **54** | **3 (6%)** | **Hybrid** |

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
