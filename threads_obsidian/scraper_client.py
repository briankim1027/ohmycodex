from __future__ import annotations

import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Any

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

from threads_obsidian.models import Post
from threads_obsidian.time_utils import parse_iso_datetime
from threads_obsidian.threads_client import ThreadsAdapter, ThreadsAPIError

logger = logging.getLogger(__name__)

class PlaywrightThreadsAdapterConfig:
    def __init__(self, headless: bool = False, timeout_seconds: int = 45):
        self.headless = headless
        self.timeout_seconds = timeout_seconds

class PlaywrightThreadsAdapter:
    def __init__(self, config: PlaywrightThreadsAdapterConfig) -> None:
        self.config = config

    def fetch_posts(self, account: str, start: datetime, end: datetime) -> list[Post]:
        logger.info(f"Scraping account '{account}' using Playwright...")
        
        posts_data = self._scrape_account(account)
        posts: list[Post] = []
        
        for item in posts_data:
            try:
                post = self._parse_post(account, item)
                posts.append(post)
            except Exception as exc:
                logger.warning(f"Skipping malformed post for account={account} error={exc}")
                
        return posts

    def fetch_recent_sample(self, account: str, sample_limit: int = 3) -> list[Post]:
        logger.info(f"Scraping sample for account '{account}' using Playwright...")
        posts_data = self._scrape_account(account) or []
        posts: list[Post] = []
        
        for item in posts_data[:sample_limit]:
            try:
                post = self._parse_post(account, item)
                posts.append(post)
            except Exception as exc:
                logger.warning(f"Skipping malformed post for account={account} error={exc}")
                
        return posts

    def resolve_threads_user_id(self, account: str) -> str:
        # For scraping, we don't strictly need the numeric ID, username works for URLs.
        return account

    def _scrape_account(self, account: str) -> list[dict[str, Any]]:
        url = f"https://www.threads.net/@{account}"
        posts_data = []

        with sync_playwright() as p:
            # We use chromium as it's the most reliable for Meta sites
            browser = p.chromium.launch(headless=self.config.headless)
            context = browser.new_context(
                viewport={"width": 1280, "height": 800},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            try:
                # Go to the page and wait for it to load
                page.goto(url, wait_until="networkidle", timeout=self.config.timeout_seconds * 1000)
                
                # Wait for the main feed to appear by looking for something that is almost certainly there
                # The user's username is usually in the nav or posts.
                page.wait_for_selector(f'text={account}', timeout=15000)
                logger.info(f"Page loaded, extracting posts from DOM...")
                
                # Scroll down a few times to trigger more loads if needed
                for _ in range(3):
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                    page.wait_for_timeout(1500)
                    
                # Debug: Take a screenshot to see what's rendered
                page.screenshot(path="threads_debug.png", full_page=True)
                logger.info(f"Saved screenshot to threads_debug.png")
                
                # Threads loads posts asynchronously, find all post containers
                # Sometimes the DOM is obfuscated. A more reliable way is to extract the 
                # initial data from the script tags.
                import re
                import json
                
                content = page.content()
                
                # The data is often inside script tags with data-sjs or similar, 
                # containing JSON with Require... ["RelayPrefetchedStreamCache", ... "data": {...}]
                # We will look for anything that looks like a post.
                
                # Look for "thread_items": [...]
                # Let's just find the big JSON blocks and parse them.
                script_locators = page.locator('script[type="application/json"]').all()
                for script in script_locators:
                    try:
                        script_text = script.inner_text()
                        if "thread_items" in script_text:
                            data = json.loads(script_text)
                            # This structure is deeply nested, let's just do a string search/regex
                            # to find the posts, it's more robust than exact tree traversal.
                            break
                    except:
                        pass
                
                # A simpler regex approach for text and ids to bypass complex JSON parsing
                # Post IDs usually look like "post_id":"358178143241" or similar
                # We can also just extract all "text":"..." that follows "caption":{"text":"..."}
                
                # Threads DOM is highly obfuscated and JSON is heavily nested/variable.
                # However, the initial data is loaded entirely in script tags. Let's parse them directly.
                script_locators = page.locator('script').all()
                all_text = ""
                for script in script_locators:
                    try:
                        all_text += script.inner_text() + "\n"
                    except:
                        pass
                        
                with open("threads_debug_json.txt", "w", encoding="utf-8") as f:
                    f.write(all_text)
                
                import json
                import re
                
                all_posts = []
                def find_posts_recursive(data, results_list):
                    if isinstance(data, dict):
                        if 'code' in data and 'user' in data and ('caption' in data or 'text_post_app_info' in data):
                            results_list.append(data)
                        elif 'thread_items' in data:
                            for item in data['thread_items']:
                                if 'post' in item:
                                    results_list.append(item['post'])
                        else:
                            for v in data.values():
                                find_posts_recursive(v, results_list)
                    elif isinstance(data, list):
                        for item in data:
                            find_posts_recursive(item, results_list)
                            
                for line in all_text.split('\n'):
                    line = line.strip()
                    if not line: continue
                    if line.startswith('{') and line.endswith('}'):
                        try:
                            data = json.loads(line)
                            find_posts_recursive(data, all_posts)
                        except json.JSONDecodeError:
                            pass
                    
                    matches = re.findall(r'<script.*?>(\{.*?\})</script>', line)
                    for m in matches:
                        try:
                            data = json.loads(m)
                            find_posts_recursive(data, all_posts)
                        except json.JSONDecodeError:
                            pass
                            
                unique_posts = {}
                for p in all_posts:
                    code = p.get('code')
                    if code and code not in unique_posts:
                        unique_posts[code] = p
                
                for code, post_data in unique_posts.items():
                    user = post_data.get('user', {})
                    username = user.get('username')
                    
                    if not username or username.lower() != account.lower():
                        continue
                        
                    # Extract text
                    text = ""
                    caption = post_data.get('caption')
                    if caption and isinstance(caption, dict) and 'text' in caption:
                        text = caption['text']
                    else:
                        text_info = post_data.get('text_post_app_info', {})
                        fragments = text_info.get('text_fragments', {}).get('fragments', [])
                        for fragment in fragments:
                            if 'plaintext' in fragment and fragment['plaintext']:
                                text += fragment['plaintext']
                                
                    if not text.strip(): continue
                    
                    taken_at = post_data.get('taken_at')
                    if not taken_at: continue
                    
                    # Store in schema
                    posts_data.append(dict(
                        author_id=account,
                        post_id=post_data.get('id') or post_data.get('pk') or code,
                        created_at=int(taken_at),
                        text=text.strip(),
                        code=code,
                    ))
                    
                logger.info(f"Found {len(posts_data)} posts via script tag json parsing")
                        
            except PlaywrightTimeoutError:
                logger.warning(f"Playwright timeout while loading {url}")
            except Exception as exc:
                logger.error(f"Playwright error: {exc}")
            finally:
                browser.close()
                
        return posts_data

    @staticmethod
    def _parse_post(account: str, item: dict[str, Any]) -> Post:
        post_id = item.get("post_id")
        if not post_id:
            raise ValueError("missing post id")
            
        author_id = item.get("author_id") or account
        
        created_raw = item.get("created_at")
        if not created_raw:
            raise ValueError("missing taken_at")
            
        text = item.get("text", "")
        
        # Build URL
        code = item.get("code")
        post_url = f"https://www.threads.net/@{author_id}/post/{code}" if code else f"https://www.threads.net/@{author_id}"
        
        return Post(
            author_id=author_id,
            post_id=str(post_id),
            created_at=datetime.fromtimestamp(int(created_raw), tz=timezone.utc),
            text=text,
            post_url=post_url,
        )
