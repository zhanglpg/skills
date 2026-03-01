#!/bin/bash
# Setup blogwatcher with AI Tech Brief RSS feeds
# Run once to initialize blogwatcher with all sources

BLOGWATCHER=~/go/bin/blogwatcher

echo "Setting up blogwatcher for AI Tech Brief..."
echo ""

# Remove existing blogs first
$BLOGWATCHER blogs | grep -E "^\s+\w" | awk '{print $1}' | while read blog; do
    $BLOGWATCHER remove "$blog" 2>/dev/null
done

# Newsletters - with correct RSS URLs
$BLOGWATCHER add "Ben's Bites" https://bensbites.beehiiv.com/rss
$BLOGWATCHER add "TLDR AI" https://tldr.tech/rss
$BLOGWATCHER add "Latent Space" https://latentspace.blog/rss
$BLOGWATCHER add "Interconnects" https://interconnects.ai/rss
$BLOGWATCHER add "The Neuron" https://theneuron.beehiiv.com/rss
$BLOGWATCHER add "Import AI" https://jack-clark.net/feed/
$BLOGWATCHER add "The Batch" https://www.deeplearning.ai/the-batch/feed/

# AI Lab Blogs - with correct RSS URLs
$BLOGWATCHER add "OpenAI" https://openai.com/news/rss
$BLOGWATCHER add "Anthropic" https://www.anthropic.com/news?format=rss
$BLOGWATCHER add "Google DeepMind" https://deepmind.google/discover/blog/rss/
$BLOGWATCHER add "Meta AI" https://ai.meta.com/blog/rss/

# Research Orgs
$BLOGWATCHER add "LMSYS" https://lmsys.org/blog/rss/
$BLOGWATCHER add "Hugging Face" https://huggingface.co/blog/feed.xml

echo ""
echo "Setup complete! Listing tracked blogs:"
echo ""
$BLOGWATCHER blogs

echo ""
echo "To scan for new articles: $BLOGWATCHER scan"
echo "To list articles: $BLOGWATCHER articles"
