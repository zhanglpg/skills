#!/usr/bin/env python3
"""
AI Tech Brief Generator

Generates daily AI technology news briefs from curated sources.
Uses blogwatcher for RSS feeds, Gemini CLI for web search.

Usage:
    python3 generate_brief.py [--test] [--output FILE]
"""

import sys
import os
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
BLOGWATCHER = os.path.expanduser("~/go/bin/blogwatcher")

ARXIV_CATEGORIES = ['cs.LG', 'cs.AI', 'cs.SE']

TWITTER_ACCOUNTS = [
    'karpathy', 'ilyasut', 'AndrewYNg', 'lilianweng',
    'DrJimFan', 'jeremyphoward', 'natolambert', 'philduanai',
    'hwchase17', 'rauchg', 'levelsio', 'swyx'
]

def get_date_str():
    """Get current date in Beijing time."""
    now = datetime.utcnow() + timedelta(hours=8)
    return now.strftime('%Y-%m-%d')

def get_date_display():
    """Get formatted date for display."""
    now = datetime.utcnow() + timedelta(hours=8)
    return now.strftime('%B %d, %Y')

def run_blogwatcher_scan():
    """Scan blogs for new articles."""
    try:
        result = subprocess.run(
            [BLOGWATCHER, 'scan'],
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.stdout
    except Exception as e:
        return f"Error scanning blogs: {e}"

def get_blogwatcher_articles(limit=20):
    """Get recent articles from blogwatcher."""
    try:
        result = subprocess.run(
            [BLOGWATCHER, 'articles', '-a'],
            capture_output=True,
            text=True,
            timeout=30
        )
        lines = result.stdout.strip().split('\n')
        articles = []
        for line in lines:
            if 'Blog:' in line or 'URL:' in line or 'Published:' in line:
                continue
            if '[new]' in line or line.strip().startswith('['):
                # Extract title
                title = line.split('] ')[-1].strip()
                articles.append({'title': title})
        return articles[:limit]
    except Exception as e:
        return []

def fetch_arxiv_papers(categories, limit=10):
    """Fetch latest papers from arXiv using Gemini CLI."""
    prompt = f"List {limit} latest arXiv papers in categories {', '.join(categories)} from past 48 hours. Format: title, key finding, arXiv ID."
    return run_gemini(prompt)

def fetch_twitter_updates(accounts, limit=10):
    """Fetch notable tweets using Gemini CLI web search."""
    accounts_str = ' '.join([f'@{a}' for a in accounts[:6]])
    prompt = f"Find notable AI-related tweets from past 24 hours from: {accounts_str}. Include tweet text and author."
    return run_gemini(prompt)

def run_gemini(prompt):
    """Run Gemini CLI with prompt."""
    try:
        env = os.environ.copy()
        env['PATH'] = f"/usr/sbin:/usr/bin:/bin:/sbin:{env.get('PATH', '')}"
        result = subprocess.run(
            ['gemini', '-p', prompt],
            capture_output=True,
            text=True,
            timeout=120,  # Increased timeout for complex queries
            env=env
        )
        return result.stdout
    except subprocess.TimeoutExpired:
        return "Error: Gemini CLI timed out (took > 120s)"
    except Exception as e:
        return f"Error: {e}"

def generate_brief_content():
    """Generate brief using Gemini CLI with blogwatcher context."""
    # Get blogwatcher articles
    articles = get_blogwatcher_articles(limit=10)
    article_titles = '\n'.join([f"- {a['title']}" for a in articles])
    
    date_display = get_date_display()
    
    prompt = f"""Generate a daily AI tech brief for {date_display}.

RECENT RSS ARTICLES (from blogwatcher):
{article_titles}

Research and summarize:
1) AI Infrastructure news (training/inference, GPUs/TPUs, distributed systems)
2) Agentic Coding developments (autonomous coding agents, AI dev tools)
3) AI Research papers (arXiv cs.LG, cs.AI, cs.SE from past 48 hours)

Check these sources:
- Twitter: @karpathy, @ilyasut, @AndrewYNg, @lilianweng, @DrJimFan, @jeremyphoward, @natolambert, @hwchase17, @rauchg, @levelsio, @swyx
- Newsletters: Ben's Bites, TLDR AI, Import AI, Latent Space, Interconnects
- arXiv: Latest papers in cs.LG, cs.AI, cs.SE
- AI Labs: OpenAI, Anthropic, DeepMind, Meta AI blogs
- LMSYS: lmsys.org/blog

Format as markdown with:
- Top 3-5 stories with 'why it matters'
- Research papers table (title, finding, link)
- Notable tweets
- Newsletter highlights
- Quick links section

Include actual links and specific details. Make it technical but concise."""

    return run_gemini(prompt)

def generate_brief(output_path=None):
    """Generate the daily brief."""
    print("=" * 60)
    print("AI Tech Brief Generator")
    print("=" * 60)
    
    # Scan blogs
    print("\n[1/4] Scanning RSS feeds with blogwatcher...")
    scan_result = run_blogwatcher_scan()
    print(scan_result)
    
    # Generate content with Gemini
    print("\n[2/4] Fetching arXiv papers and Twitter updates...")
    print("\n[3/4] Generating brief with Gemini CLI...")
    brief = generate_brief_content()
    
    # Output
    if output_path:
        with open(output_path, 'w') as f:
            f.write(brief)
        print(f"\n✅ Brief saved to: {output_path}")
    else:
        print("\n" + "=" * 60)
        print(brief)
        print("=" * 60)
    
    return brief

def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate AI Tech Brief')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--output', type=str, help='Output file path')
    
    args = parser.parse_args()
    
    if args.test:
        print("Running in test mode...")
    
    output = args.output or '/tmp/ai-tech-brief.md'
    generate_brief(output)

if __name__ == '__main__':
    main()
