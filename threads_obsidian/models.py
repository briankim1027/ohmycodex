from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class Post:
    author_id: str
    post_id: str
    created_at: datetime
    text: str
    post_url: str


@dataclass(frozen=True)
class CollectWindow:
    start: datetime
    end: datetime


@dataclass
class CollectSummary:
    target_accounts: int = 0
    fetched_posts: int = 0
    new_saved: int = 0
    duplicates_skipped: int = 0
    failed_accounts: int = 0
