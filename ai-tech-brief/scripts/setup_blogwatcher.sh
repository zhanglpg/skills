#!/bin/bash
# Setup blogwatcher with AI Tech Brief RSS feeds
# Run once to initialize blogwatcher with all sources
# This script is idempotent and non-interactive
# NOTE: Only 3 out of 13 RSS feeds are working (see RSS_FEED_STATUS.md)

set -e  # Exit on error

BLOGWATCHER=""

# Find blogwatcher binary
find_blogwatcher() {
    if command -v blogwatcher &> /dev/null; then
        BLOGWATCHER="blogwatcher"
        return 0
    fi
    
    if [ -f ~/go/bin/blogwatcher ]; then
        BLOGWATCHER=~/go/bin/blogwatcher
        return 0
    fi
    
    if [ -f /usr/local/bin/blogwatcher ]; then
        BLOGWATCHER=/usr/local/bin/blogwatcher
        return 0
    fi
    
    if [ -f /opt/homebrew/bin/blogwatcher ]; then
        BLOGWATCHER=/opt/homebrew/bin/blogwatcher
        return 0
    fi
    
    echo "ERROR: blogwatcher not found!"
    echo "Install with: go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest"
    exit 1
}

# Check if blog already exists (non-interactive)
blog_exists() {
    local name="$1"
    $BLOGWATCHER blogs 2>/dev/null | grep -qi "^  $name$"
    return $?
}

# Add blog if it doesn't exist
add_blog_if_missing() {
    local name="$1"
    local url="$2"
    
    if blog_exists "$name"; then
        echo "  ✓ $name (already configured)"
    else
        $BLOGWATCHER add "$name" "$url" 2>/dev/null && echo "  + $name" || echo "  ! $name (failed - may need manual check)"
    fi
}

# Main setup
main() {
    echo "========================================"
    echo "AI Tech Brief - Blogwatcher Setup"
    echo "========================================"
    echo ""
    echo "⚠️  NOTE: Only 3 out of 13 RSS feeds are currently working."
    echo "   See RSS_FEED_STATUS.md for details."
    echo "   Gemini CLI web search will cover all other sources."
    echo ""
    
    # Find blogwatcher
    echo "Finding blogwatcher..."
    find_blogwatcher
    echo "  Using: $BLOGWATCHER"
    echo ""
    
    # Show current blogs
    echo "Current tracked blogs:"
    $BLOGWATCHER blogs 2>/dev/null || echo "  (none)"
    echo ""
    
    # === WORKING RSS FEEDS (3) ===
    echo "=== Adding WORKING RSS Feeds (3) ==="
    echo ""
    
    echo "Newsletters (1 working):"
    add_blog_if_missing "Import AI" "https://jack-clark.net/feed/"
    echo ""
    
    echo "AI Labs (1 working):"
    add_blog_if_missing "Anthropic" "https://www.anthropic.com/news?format=rss"
    echo ""
    
    echo "Research Orgs (1 working):"
    add_blog_if_missing "Hugging Face" "https://huggingface.co/blog/feed.xml"
    echo ""
    
    # === PROBLEMATIC RSS FEEDS (May or may not work) ===
    echo "=== Adding PROBLEMATIC RSS Feeds (may not work) ==="
    echo "These feeds have issues but we'll try anyway:"
    echo ""
    
    echo "Newsletters with redirects/issues:"
    add_blog_if_missing "TLDR AI" "https://tldr.tech/rss"
    add_blog_if_missing "Latent Space" "https://latentspace.blog/rss"
    echo ""
    
    echo "Newsletters blocked by Cloudflare (likely won't work):"
    add_blog_if_missing "Ben's Bites" "https://bensbites.beehiiv.com/rss"
    add_blog_if_missing "The Neuron" "https://theneuron.beehiiv.com/rss"
    echo ""
    
    echo "AI Labs with missing/broken feeds:"
    add_blog_if_missing "OpenAI" "https://openai.com/news/rss"
    add_blog_if_missing "Google DeepMind" "https://deepmind.google/discover/blog/rss/"
    add_blog_if_missing "Meta AI" "https://ai.meta.com/blog/rss/"
    echo ""
    
    echo "Research Orgs with missing feeds:"
    add_blog_if_missing "LMSYS" "https://lmsys.org/blog/rss/"
    echo ""
    
    # Test scan
    echo "Testing RSS feeds..."
    $BLOGWATCHER scan 2>/dev/null || echo "  (scan completed with warnings - this is normal)"
    echo ""
    
    # Summary
    echo "========================================"
    echo "Setup Complete!"
    echo "========================================"
    echo ""
    echo "Tracked blogs:"
    $BLOGWATCHER blogs 2>/dev/null | head -30
    echo ""
    echo "IMPORTANT NOTES:"
    echo "- Only ~3 RSS feeds are expected to work properly"
    echo "- The skill uses Gemini CLI web search for comprehensive coverage"
    echo "- All 26 sources (Twitter, newsletters, labs) are checked via web search"
    echo "- RSS is just a supplementary data source"
    echo ""
    echo "Commands:"
    echo "  Scan for updates:  $BLOGWATCHER scan"
    echo "  List articles:     $BLOGWATCHER articles"
    echo "  Mark as read:      $BLOGWATCHER read <id>"
    echo ""
    echo "For full source list, see: references/sources.md"
    echo "For RSS status, see: RSS_FEED_STATUS.md"
    echo ""
}

# Run main
main
