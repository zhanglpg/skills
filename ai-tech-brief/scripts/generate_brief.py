#!/usr/bin/env python3
"""
AI Tech Brief Generator

Generates daily AI technology news briefs from curated sources.
Uses blogwatcher for RSS feeds, Gemini CLI for web search.

Usage:
    python3 generate_brief.py [--test] [--output FILE] [--config FILE]
"""

import sys
import os
import subprocess
import json
import hashlib
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

# Default configuration
DEFAULT_CONFIG = {
    'blogwatcher_path': '~/go/bin/blogwatcher',
    'arxiv_categories': ['cs.LG', 'cs.AI', 'cs.SE'],
    'twitter_accounts': [
        'karpathy', 'ilyasut', 'AndrewYNg', 'lilianweng',
        'DrJimFan', 'jeremyphoward', 'natolambert', 'philduanai',
        'hwchase17', 'rauchg', 'levelsio', 'swyx'
    ],
    'timezone': 'Asia/Shanghai',
    'timezone_offset': 8,
    'gemini_timeout': 120,
    'blogwatcher_timeout': 60,
    'max_articles': 20,
    'output_dir': '~/ai-tech-briefs',
    'log_file': '~/ai-tech-briefs/generate.log',
}

class BriefGenerator:
    """AI Tech Brief Generator with logging and error handling."""
    
    def __init__(self, config_path: Optional[str] = None):
        """Initialize generator with optional config file."""
        self.config = DEFAULT_CONFIG.copy()
        self.logger = self._setup_logger()
        
        if config_path and os.path.exists(config_path):
            self._load_config(config_path)
        
        # Expand paths
        self.config['blogwatcher_path'] = os.path.expanduser(self.config['blogwatcher_path'])
        self.config['output_dir'] = os.path.expanduser(self.config['output_dir'])
        self.config['log_file'] = os.path.expanduser(self.config['log_file'])
        
        # Ensure output directory exists
        os.makedirs(self.config['output_dir'], exist_ok=True)
        
        self.seen_hashes = set()  # For deduplication
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging to file and console."""
        logger = logging.getLogger('ai-tech-brief')
        logger.setLevel(logging.INFO)
        
        # File handler
        try:
            log_file = os.path.expanduser('~/ai-tech-briefs/generate.log')
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            fh = logging.FileHandler(log_file)
            fh.setLevel(logging.DEBUG)
            fh.setFormatter(logging.Formatter(
                '%(asctime)s - %(levelname)s - %(message)s'
            ))
            logger.addHandler(fh)
        except Exception as e:
            print(f"Warning: Could not setup file logging: {e}")
        
        # Console handler
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO)
        ch.setFormatter(logging.Formatter('%(message)s'))
        logger.addHandler(ch)
        
        return logger
    
    def _load_config(self, config_path: str):
        """Load configuration from JSON file."""
        try:
            with open(config_path, 'r') as f:
                user_config = json.load(f)
                self.config.update(user_config)
            self.logger.info(f"Loaded config from {config_path}")
        except Exception as e:
            self.logger.error(f"Failed to load config: {e}")
    
    def _get_blogwatcher_path(self) -> str:
        """Find blogwatcher binary."""
        # Try configured path first
        if os.path.exists(self.config['blogwatcher_path']):
            return self.config['blogwatcher_path']
        
        # Try PATH
        result = subprocess.run(['which', 'blogwatcher'], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
        
        # Try common locations
        common_paths = [
            os.path.expanduser('~/go/bin/blogwatcher'),
            '/usr/local/bin/blogwatcher',
            '/opt/homebrew/bin/blogwatcher',
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
        
        raise FileNotFoundError("blogwatcher not found. Install with: go install github.com/Hyaxia/blogwatcher/cmd/blogwatcher@latest")
    
    def _hash_article(self, title: str, url: str = "") -> str:
        """Create hash for deduplication."""
        content = f"{title}:{url}"
        return hashlib.md5(content.encode()).hexdigest()
    
    def _is_duplicate(self, title: str, url: str = "") -> bool:
        """Check if article is duplicate."""
        article_hash = self._hash_article(title, url)
        if article_hash in self.seen_hashes:
            return True
        self.seen_hashes.add(article_hash)
        return False
    
    def get_date_str(self) -> str:
        """Get current date in configured timezone."""
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%Y-%m-%d')
    
    def get_date_display(self) -> str:
        """Get formatted date for display."""
        offset = self.config.get('timezone_offset', 8)
        now = datetime.utcnow() + timedelta(hours=offset)
        return now.strftime('%B %d, %Y')
    
    def run_blogwatcher_scan(self) -> str:
        """Scan blogs for new articles."""
        try:
            blogwatcher = self._get_blogwatcher_path()
            result = subprocess.run(
                [blogwatcher, 'scan'],
                capture_output=True,
                text=True,
                timeout=self.config.get('blogwatcher_timeout', 60)
            )
            self.logger.debug(f"Blogwatcher scan output: {result.stdout}")
            return result.stdout
        except subprocess.TimeoutExpired:
            self.logger.error("Blogwatcher scan timed out")
            return "Error: Blogwatcher scan timed out"
        except FileNotFoundError as e:
            self.logger.error(f"Blogwatcher not found: {e}")
            return f"Error: {e}"
        except Exception as e:
            self.logger.error(f"Blogwatcher scan failed: {e}")
            return f"Error scanning blogs: {e}"
    
    def get_blogwatcher_articles(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Get recent articles from blogwatcher with better parsing."""
        articles = []
        try:
            blogwatcher = self._get_blogwatcher_path()
            result = subprocess.run(
                [blogwatcher, 'articles', '-a'],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            lines = result.stdout.strip().split('\n')
            current_article = {}
            
            for line in lines:
                line = line.strip()
                if not line or line.startswith('Unread articles') or line.startswith('Tracked blogs'):
                    continue
                
                # Parse article ID and title
                if line.startswith('[') and '] [new]' in line:
                    # Save previous article if exists
                    if current_article.get('title'):
                        if not self._is_duplicate(current_article['title'], current_article.get('url', '')):
                            articles.append(current_article)
                            if len(articles) >= limit:
                                break
                    
                    # Start new article
                    parts = line.split('] ', 2)
                    if len(parts) >= 3:
                        current_article = {
                            'id': parts[0].replace('[', ''),
                            'title': parts[2].strip(),
                            'blog': '',
                            'url': '',
                            'published': ''
                        }
                
                elif line.startswith('Blog:'):
                    current_article['blog'] = line.replace('Blog:', '').strip()
                elif line.startswith('URL:'):
                    current_article['url'] = line.replace('URL:', '').strip()
                elif line.startswith('Published:'):
                    current_article['published'] = line.replace('Published:', '').strip()
            
            # Don't forget the last article
            if current_article.get('title') and len(articles) < limit:
                if not self._is_duplicate(current_article['title'], current_article.get('url', '')):
                    articles.append(current_article)
            
            self.logger.info(f"Found {len(articles)} unique articles from blogwatcher")
            return articles
            
        except Exception as e:
            self.logger.error(f"Failed to get blogwatcher articles: {e}")
            return []
    
    def run_gemini(self, prompt: str, retry: int = 2) -> str:
        """Run Gemini CLI with retry logic."""
        env = os.environ.copy()
        env['PATH'] = f"/usr/sbin:/usr/bin:/bin:/sbin:{env.get('PATH', '')}"
        
        for attempt in range(retry + 1):
            try:
                self.logger.debug(f"Gemini CLI attempt {attempt + 1}/{retry + 1}")
                result = subprocess.run(
                    ['gemini', '-p', prompt],
                    capture_output=True,
                    text=True,
                    timeout=self.config.get('gemini_timeout', 120),
                    env=env
                )
                
                if result.returncode == 0:
                    return result.stdout
                else:
                    self.logger.warning(f"Gemini CLI failed (attempt {attempt + 1}): {result.stderr[:200]}")
                    if attempt < retry:
                        import time
                        time.sleep(2 ** attempt)  # Exponential backoff
                        
            except subprocess.TimeoutExpired:
                self.logger.error(f"Gemini CLI timed out (attempt {attempt + 1})")
                if attempt < retry:
                    import time
                    time.sleep(2 ** attempt)
            except Exception as e:
                self.logger.error(f"Gemini CLI error (attempt {attempt + 1}): {e}")
                if attempt < retry:
                    import time
                    time.sleep(2 ** attempt)
        
        return "Error: Gemini CLI failed after all retry attempts"
    
    def generate_brief_content(self, rss_articles: List[Dict[str, Any]]) -> str:
        """Generate brief using Gemini CLI with blogwatcher context."""
        # Format RSS articles for prompt
        article_lines = []
        for article in rss_articles[:15]:  # Limit to 15 most recent
            title = article.get('title', 'Unknown')
            blog = article.get('blog', '')
            url = article.get('url', '')
            published = article.get('published', '')
            
            line = f"- {title}"
            if blog:
                line += f" ({blog})"
            if url:
                line += f" - {url}"
            if published:
                line += f" [{published}]"
            article_lines.append(line)
        
        article_text = '\n'.join(article_lines) if article_lines else "No recent RSS articles found."
        
        date_display = self.get_date_display()
        
        prompt = f"""Generate a daily AI tech brief for {date_display}.

RECENT RSS ARTICLES (from blogwatcher - use these as starting points):
{article_text}

Research and summarize:
1) AI Infrastructure news (training/inference, GPUs/TPUs, distributed systems)
2) Agentic Coding developments (autonomous coding agents, AI dev tools, code generation)
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

Include actual links and specific details. Make it technical but concise.
If RSS articles above are old, focus on fresh web research."""

        self.logger.info("Generating brief content with Gemini CLI...")
        return self.run_gemini(prompt)
    
    def validate_brief(self, brief: str) -> bool:
        """Validate that brief has required sections."""
        required_sections = [
            '#',  # Has a title
            '##',  # Has sections
            'http',  # Has links
        ]
        
        for section in required_sections:
            if section not in brief:
                self.logger.warning(f"Brief missing required element: {section}")
                return False
        
        self.logger.info("Brief validation passed")
        return True
    
    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief."""
        self.logger.info("=" * 60)
        self.logger.info("AI Tech Brief Generator")
        self.logger.info("=" * 60)
        
        # Scan blogs
        self.logger.info("\n[1/4] Scanning RSS feeds with blogwatcher...")
        scan_result = self.run_blogwatcher_scan()
        self.logger.info(scan_result)
        
        # Get articles
        self.logger.info("\n[2/4] Fetching recent articles...")
        rss_articles = self.get_blogwatcher_articles(limit=self.config.get('max_articles', 20))
        self.logger.info(f"Found {len(rss_articles)} unique articles")
        
        # Generate content with Gemini
        self.logger.info("\n[3/4] Generating brief with Gemini CLI...")
        brief = self.generate_brief_content(rss_articles)
        
        # Validate
        self.logger.info("\n[4/4] Validating brief...")
        if not self.validate_brief(brief):
            self.logger.warning("Brief validation failed, but continuing...")
        
        # Output
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(brief)
            self.logger.info(f"\n✅ Brief saved to: {output_path}")
        else:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(brief)
            self.logger.info("=" * 60)
        
        self.logger.info("Brief generation complete!")
        return brief


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description='Generate AI Tech Brief')
    parser.add_argument('--test', action='store_true', help='Test mode')
    parser.add_argument('--output', type=str, help='Output file path')
    parser.add_argument('--config', type=str, help='Config file path (JSON)')
    
    args = parser.parse_args()
    
    if args.test:
        print("Running in test mode...")
    
    # Initialize generator
    generator = BriefGenerator(config_path=args.config)
    
    # Determine output path
    if args.output:
        output = args.output
    else:
        date_str = generator.get_date_str()
        output_dir = generator.config['output_dir']
        output = os.path.join(output_dir, f"{date_str}-ai-tech-brief.md")
    
    # Generate brief
    generator.generate_brief(output_path=output)


if __name__ == '__main__':
    main()
