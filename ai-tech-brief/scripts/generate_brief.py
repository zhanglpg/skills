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
    'newsletters': [
        "Ben's Bites", 'TLDR AI', 'Import AI', 'Latent Space', 
        'Interconnects', 'The Batch', 'The Neuron', 'Superhuman AI'
    ],
    'ai_labs': ['OpenAI', 'Anthropic', 'Google DeepMind', 'Meta AI'],
    'research_orgs': ['LMSYS', 'Hugging Face'],
    'timezone': 'Asia/Shanghai',
    'timezone_offset': 8,
    'gemini_timeout': 180,
    'blogwatcher_timeout': 60,
    'max_articles': 30,
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
        self.source_coverage = {}  # Track which sources were covered
    
    def _setup_logger(self) -> logging.Logger:
        """Setup logging to file and console."""
        logger = logging.getLogger('ai-tech-brief')
        logger.setLevel(logging.INFO)
        
        # Clear existing handlers
        logger.handlers = []
        
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
    
    def get_blogwatcher_articles(self, limit: int = 30) -> List[Dict[str, Any]]:
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
                            # Track source coverage
                            blog_name = current_article.get('blog', '')
                            if blog_name:
                                self.source_coverage[blog_name] = self.source_coverage.get(blog_name, 0) + 1
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
                    blog_name = current_article.get('blog', '')
                    if blog_name:
                        self.source_coverage[blog_name] = self.source_coverage.get(blog_name, 0) + 1
            
            self.logger.info(f"Found {len(articles)} unique articles from blogwatcher")
            self.logger.info(f"Source coverage: {self.source_coverage}")
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
                    timeout=self.config.get('gemini_timeout', 180),
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
        """Generate brief using Gemini CLI with comprehensive source coverage."""
        # Format RSS articles for prompt
        article_lines = []
        for article in rss_articles[:20]:  # Limit to 20 most recent
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
        
        # Get source lists from config
        twitter_accounts = self.config.get('twitter_accounts', [])
        newsletters = self.config.get('newsletters', [])
        ai_labs = self.config.get('ai_labs', [])
        research_orgs = self.config.get('research_orgs', [])
        arxiv_cats = self.config.get('arxiv_categories', [])
        
        date_display = self.get_date_display()
        
        prompt = f"""Generate a comprehensive daily AI tech brief for {date_display}.

MANDATORY: You MUST include content from ALL of the following source categories. If you cannot find recent content from a specific source, explicitly state "No updates from [source] today."

## REQUIRED SOURCE COVERAGE:

### 1. Twitter/X Thought Leaders (12 accounts) - MUST CHECK EACH:
{chr(10).join([f'- @{acc}' for acc in twitter_accounts])}
Search for tweets from past 24-48 hours. Include notable announcements, insights, or thread summaries.

### 2. Newsletters (8 publications) - MUST CHECK EACH:
{chr(10).join([f'- {nl}' for nl in newsletters])}
Include key stories and insights.

### 3. AI Lab Blogs (4 labs) - MUST CHECK EACH:
{chr(10).join([f'- {lab}' for lab in ai_labs])}
Include official announcements and research updates.

### 4. Research Organizations (2 orgs) - MUST CHECK EACH:
{chr(10).join([f'- {org}' for org in research_orgs])}
Include benchmarks, model releases, and research updates.

### 5. arXiv Papers (categories: {', '.join(arxiv_cats)}) - MUST CHECK:
List latest papers from past 48 hours with key findings.

## RSS FEED DATA (already collected):
{article_text}

## OUTPUT FORMAT:

```markdown
# 🤖 Daily AI Tech Brief - {date_display}

## 📊 Top Stories (3-5 items)
Must include stories from multiple source categories above.

### [Headline]
- **Summary:** 1-2 sentences
- **Why it matters:** Impact/significance
- **Source:** [Link](url)

## 🐦 Twitter/X Updates
Explicitly list updates from thought leaders. If no updates, say "No significant updates today."

## 📰 Newsletter Highlights
Summarize key stories from each newsletter checked.

## 🏢 AI Lab Updates
Updates from OpenAI, Anthropic, DeepMind, Meta AI.

## 🔬 Research Organization Updates
Updates from LMSYS, Hugging Face.

## 📄 New Research Papers
| Paper | Key Finding | Link |
|-------|-------------|------|
| [Title] | Finding | arXiv:XXXX |

## 🔗 Quick Links
Other notable links discovered.

---
*Sources checked: Twitter (12 accounts), Newsletters (8), AI Labs (4), Research Orgs (2), arXiv*
```

IMPORTANT: 
1. You MUST attempt to find content from ALL listed sources
2. Use web search to check each source individually
3. If a source has no updates, explicitly state that
4. Do not skip any source category
5. Make the brief comprehensive and technical
"""

        self.logger.info("Generating comprehensive brief with full source coverage...")
        return self.run_gemini(prompt)
    
    def validate_brief(self, brief: str) -> bool:
        """Validate that brief has required sections."""
        required_sections = [
            '#',  # Has a title
            '##',  # Has sections
            'http',  # Has links
        ]
        
        # Check for source coverage mention
        source_indicators = ['Twitter', 'Newsletter', 'Lab', 'Research', 'arXiv']
        found_sources = sum(1 for indicator in source_indicators if indicator in brief)
        
        for section in required_sections:
            if section not in brief:
                self.logger.warning(f"Brief missing required element: {section}")
                return False
        
        if found_sources < 3:
            self.logger.warning(f"Brief may be missing source coverage (only found {found_sources}/5 indicators)")
        
        self.logger.info(f"Brief validation passed (found {found_sources}/5 source indicators)")
        return True
    
    def generate_source_coverage_report(self) -> str:
        """Generate a report of which sources were covered."""
        lines = ["\n## 📊 Source Coverage Report\n"]
        
        # Twitter accounts
        lines.append("### Twitter/X Accounts (12)")
        for acc in self.config.get('twitter_accounts', []):
            status = "✅" if acc in str(self.source_coverage) else "❓"
            lines.append(f"- {status} @{acc}")
        
        # Newsletters
        lines.append("\n### Newsletters (8)")
        for nl in self.config.get('newsletters', []):
            count = self.source_coverage.get(nl, 0)
            status = f"✅ ({count} articles)" if count > 0 else "❌ No articles"
            lines.append(f"- {status} {nl}")
        
        # AI Labs
        lines.append("\n### AI Labs (4)")
        for lab in self.config.get('ai_labs', []):
            count = self.source_coverage.get(lab, 0)
            status = f"✅ ({count} articles)" if count > 0 else "❌ No articles"
            lines.append(f"- {status} {lab}")
        
        # Research orgs
        lines.append("\n### Research Organizations (2)")
        for org in self.config.get('research_orgs', []):
            count = self.source_coverage.get(org, 0)
            status = f"✅ ({count} articles)" if count > 0 else "❌ No articles"
            lines.append(f"- {status} {org}")
        
        return '\n'.join(lines)
    
    def generate_brief(self, output_path: Optional[str] = None) -> str:
        """Generate the daily brief."""
        self.logger.info("=" * 60)
        self.logger.info("AI Tech Brief Generator")
        self.logger.info("=" * 60)
        
        # Scan blogs
        self.logger.info("\n[1/5] Scanning RSS feeds with blogwatcher...")
        scan_result = self.run_blogwatcher_scan()
        self.logger.info(scan_result)
        
        # Get articles
        self.logger.info("\n[2/5] Fetching recent articles...")
        rss_articles = self.get_blogwatcher_articles(limit=self.config.get('max_articles', 30))
        self.logger.info(f"Found {len(rss_articles)} unique articles")
        
        # Generate content with Gemini
        self.logger.info("\n[3/5] Generating comprehensive brief with Gemini CLI...")
        brief = self.generate_brief_content(rss_articles)
        
        # Validate
        self.logger.info("\n[4/5] Validating brief...")
        is_valid = self.validate_brief(brief)
        if not is_valid:
            self.logger.warning("Brief validation had warnings, but continuing...")
        
        # Generate coverage report
        self.logger.info("\n[5/5] Generating source coverage report...")
        coverage_report = self.generate_source_coverage_report()
        
        # Append coverage report to brief
        brief_with_coverage = brief + "\n\n" + coverage_report
        
        # Output
        if output_path:
            output_dir = os.path.dirname(output_path)
            if output_dir:
                os.makedirs(output_dir, exist_ok=True)
            
            with open(output_path, 'w') as f:
                f.write(brief_with_coverage)
            self.logger.info(f"\n✅ Brief saved to: {output_path}")
        else:
            self.logger.info("\n" + "=" * 60)
            self.logger.info(brief_with_coverage)
            self.logger.info("=" * 60)
        
        self.logger.info("Brief generation complete!")
        return brief_with_coverage


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
