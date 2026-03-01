from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime

from threads_obsidian.drive_client import DriveUploadError, GoogleDriveUploader
from threads_obsidian.markdown import build_date_folder_name, build_filename, render_post_markdown
from threads_obsidian.models import CollectSummary, CollectWindow, Post
from threads_obsidian.threads_client import ThreadsAdapter, ThreadsAPIError

logger = logging.getLogger(__name__)


@dataclass
class AccountFailure:
    account: str
    reason: str


def filter_posts_by_window(posts: list[Post], window: CollectWindow) -> list[Post]:
    return [p for p in posts if window.start <= p.created_at <= window.end]


def collect_posts(
    *,
    accounts: list[str],
    window: CollectWindow,
    collected_at: datetime,
    threads_adapter: ThreadsAdapter,
    drive_uploader: GoogleDriveUploader,
) -> tuple[CollectSummary, list[AccountFailure]]:
    summary = CollectSummary(target_accounts=len(accounts))
    failures: list[AccountFailure] = []

    for account in accounts:
        try:
            account_posts = threads_adapter.fetch_posts(account=account, start=window.start, end=window.end)
        except ThreadsAPIError as exc:
            summary.failed_accounts += 1
            failures.append(AccountFailure(account=account, reason=str(exc)))
            logger.exception("Account fetch failed: %s", account)
            continue

        in_window_posts = filter_posts_by_window(account_posts, window)
        summary.fetched_posts += len(in_window_posts)

        for post in in_window_posts:
            date_folder = build_date_folder_name(post.created_at)
            filename = build_filename(post)

            try:
                folder_id = drive_uploader.ensure_date_folder(date_folder)
                exists = drive_uploader.file_exists(folder_id, filename)
            except DriveUploadError:
                logger.exception("Drive access failed while checking duplicate for %s", filename)
                raise

            if exists:
                summary.duplicates_skipped += 1
                logger.info("Duplicate skipped: %s", filename)
                continue

            markdown = render_post_markdown(post, collected_at=collected_at)
            try:
                drive_uploader.upload_markdown(folder_id=folder_id, filename=filename, content=markdown)
            except DriveUploadError:
                logger.exception("Drive upload failed for %s", filename)
                raise
            summary.new_saved += 1

    return summary, failures
