from __future__ import annotations

from datetime import datetime

from threads_obsidian.models import Post
from threads_obsidian.time_utils import KST, kst_date_str


def generate_title(body_text: str, max_chars: int = 80) -> str:
    lines = [line.strip() for line in body_text.splitlines() if line.strip()]
    if not lines:
        return "Untitled"
    first_line = lines[0]
    return first_line[:max_chars]


def build_filename(post: Post) -> str:
    return f"{kst_date_str(post.created_at)}_{post.author_id}_{post.post_id}.md"


def build_date_folder_name(created_at: datetime) -> str:
    return kst_date_str(created_at)


def render_post_markdown(post: Post, collected_at: datetime) -> str:
    created_at_iso = post.created_at.isoformat()
    collected_at_iso = collected_at.isoformat()
    title = generate_title(post.text)
    created_at_kst = post.created_at.astimezone(KST).strftime("%Y-%m-%d %H:%M:%S %z")

    body_text = post.text.strip() or ""

    return (
        "---\n"
        "source: threads\n"
        f"author_id: {post.author_id}\n"
        f"post_id: {post.post_id}\n"
        f"post_url: {post.post_url}\n"
        f"created_at: {created_at_iso}\n"
        f"collected_at: {collected_at_iso}\n"
        "---\n\n"
        f"# {title}\n\n"
        "## 날짜\n"
        f"{created_at_kst}\n\n"
        "## 제목\n"
        f"{title}\n\n"
        "## 본문 내용\n"
        f"{body_text}\n"
    )
