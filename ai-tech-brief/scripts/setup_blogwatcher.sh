#!/bin/bash
# Setup blogwatcher with AI Tech Brief RSS feeds
# Run once to initialize blogwatcher with all sources
# This script is idempotent and non-interactive

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
        $BLOGWATCHER add "$name" "$url" 2>/dev/null && echo "  + $name" || echo "  ! $name (failed)"
    fi
}

# Main setup
main() {
    echo "========================================"
    echo "AI Tech Brief - Blogwatcher Setup"
    echo "========================================"
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
    
    # Add newsletters
    echo "Configuring newsletters..."
    add_blog_if_missing "Ben's Bites" "https://bensbites.beehiiv.com/rss"
    add_blog_if_missing "TLDR AI" "https://tldr.tech/rss"
    add_blog_if_missing "Latent Space" "https://latentspace.blog/rss"
    add_blog_if_missing "Interconnects" "https://interconnects.ai/rss"
    add_blog_if_missing "The Neuron" "https://theneuron.beehiiv.com/rss"
    add_blog_if_missing "Import AI" "https://jack-clark.net/feed/"
    add_blog_if_missing "The Batch" "https://www.deeplearning.ai/the-batch/feed/"
    echo ""
    
    # Add AI lab blogs
    echo "Configuring AI lab blogs..."
    add_blog_if_missing "OpenAI" "https://openai.com/news/rss"
    add_blog_if_missing "Anthropic" "https://www.anthropic.com/news?format=rss"
    add_blog_if_missing "Google DeepMind" "https://deepmind.google/discover/blog/rss/"
    add_blog_if_missing "Meta AI" "https://ai.meta.com/blog/rss/"
    echo ""
    
    # Add research orgs
    echo "Configuring research organizations..."
    add_blog_if_missing "LMSYS" "https://lmsys.org/blog/rss/"
    add_blog_if_missing "Hugging Face" "https://huggingface.co/blog/feed.xml"
    echo ""
    
    # Test scan
    echo "Testing RSS feeds..."
    $BLOGWATCHER scan 2>/dev/null || echo "  (scan completed with warnings)"
    echo ""
    
    # Summary
    echo "========================================"
    echo "Setup Complete!"
    echo "========================================"
    echo ""
    echo "Tracked blogs:"
    $BLOGWATCHER blogs 2>/dev/null | head -20
    echo ""
    echo "Commands:"
    echo "  Scan for updates:  $BLOGWATCHER scan"
    echo "  List articles:     $BLOGWATCHER articles"
    echo "  Mark as read:      $BLOGWATCHER read <id>"
    echo ""
}

# Run main
main
