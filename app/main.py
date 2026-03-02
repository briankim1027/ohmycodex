from __future__ import annotations

import logging
import sys
from datetime import datetime
from pathlib import Path

import typer

# Allow running as `python app/main.py ...` from project root.
if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from threads_obsidian.collector import collect_posts
from threads_obsidian.config import ProjectConfig, Settings, load_accounts, parse_accounts_override
from threads_obsidian.drive_client import DriveClientConfig, DriveUploadError, GoogleDriveUploader
from threads_obsidian.state_store import StateStore, resolve_collect_window
from threads_obsidian.threads_client import ThreadsAPIError
from threads_obsidian.scraper_client import PlaywrightThreadsAdapter, PlaywrightThreadsAdapterConfig
from threads_obsidian.time_utils import KST, utc_now

app = typer.Typer(help="Threads posts collector to Obsidian markdown on Google Drive")


def _build_project_config() -> tuple[ProjectConfig, Settings]:
    project_root = Path(__file__).resolve().parent.parent
    settings = Settings()
    return ProjectConfig(project_root=project_root, settings=settings), settings


def _build_threads_client(settings: Settings) -> PlaywrightThreadsAdapter:
    # Use the Playwright Scraper instead of the official API
    return PlaywrightThreadsAdapter(
        PlaywrightThreadsAdapterConfig(
            headless=False,
            timeout_seconds=45
        )
    )


def _build_drive_client(cfg: ProjectConfig, settings: Settings) -> GoogleDriveUploader:
    return GoogleDriveUploader(
        DriveClientConfig(
            root_folder_id=settings.google_drive_root_folder_id,
            credentials_file=cfg.oauth_client_secret_file,
            token_file=cfg.oauth_token_file,
        )
    )


def configure_logging(log_dir: Path) -> Path:
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(KST).strftime("%Y%m%d-%H%M%S")
    log_path = log_dir / f"collect-{stamp}.log"

    formatter = logging.Formatter("%(asctime)s %(levelname)s [%(name)s] %(message)s")
    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(logging.INFO)

    file_handler = logging.FileHandler(log_path, encoding="utf-8")
    file_handler.setFormatter(formatter)
    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    root.addHandler(file_handler)
    root.addHandler(stream_handler)
    return log_path


@app.command()
def collect(accounts: str = typer.Option(None, "--accounts", help="Comma-separated account list override")):
    """Collect posts from Threads and upload markdown files to Google Drive."""

    cfg, settings = _build_project_config()

    log_file = configure_logging(cfg.log_dir)
    logging.info("Run started. log_file=%s", log_file)

    override_accounts = parse_accounts_override(accounts)
    target_accounts = override_accounts or load_accounts(cfg.accounts_file)
    if not target_accounts:
        raise typer.BadParameter(
            "No accounts provided. Set config/accounts.yaml accounts or pass --accounts"
        )

    run_now = utc_now()
    state_store = StateStore(cfg.state_file)
    state = state_store.load()
    window = resolve_collect_window(now_utc=run_now, state=state)

    logging.info(
        "Collect window start=%s end=%s accounts=%s",
        window.start.isoformat(),
        window.end.isoformat(),
        len(target_accounts),
    )

    threads_client = _build_threads_client(settings)
    drive_client = _build_drive_client(cfg, settings)

    try:
        summary, failures = collect_posts(
            accounts=target_accounts,
            window=window,
            collected_at=run_now,
            threads_adapter=threads_client,
            drive_uploader=drive_client,
        )
    except DriveUploadError as exc:
        logging.exception("Collection aborted due to Drive error: %s", exc)
        raise typer.Exit(code=1)

    run_id = run_now.astimezone(KST).strftime("%Y%m%d-%H%M%S")
    state_store.save_success(run_id=run_id, success_at=run_now)

    for failure in failures:
        logging.error("Account failure account=%s reason=%s", failure.account, failure.reason)

    logging.info("=== Collection Summary ===")
    logging.info("target_accounts=%s", summary.target_accounts)
    logging.info("fetched_posts=%s", summary.fetched_posts)
    logging.info("new_saved=%s", summary.new_saved)
    logging.info("duplicates_skipped=%s", summary.duplicates_skipped)
    logging.info("failed_accounts=%s", summary.failed_accounts)

    typer.echo("Collection complete.")


@app.command("check-drive")
def check_drive() -> None:
    """Verify Google Drive OAuth/token and root folder write access (non-destructive)."""

    cfg, settings = _build_project_config()
    drive_client = _build_drive_client(cfg, settings)
    try:
        result = drive_client.check_root_folder_access()
    except DriveUploadError as exc:
        typer.echo(f"Drive check failed: {exc}")
        raise typer.Exit(code=1)

    typer.echo("Drive check OK")
    typer.echo(f"Root folder: {result.get('name')} ({result.get('id')})")
    typer.echo(f"Can write children: {result.get('can_write')}")
    if result.get("trashed"):
        typer.echo("Warning: root folder is trashed.")


@app.command("check-threads")
def check_threads(
    account: str = typer.Option(..., "--account", help="Threads username or numeric user id"),
    limit: int = typer.Option(3, "--limit", min=1, max=20, help="Sample posts to fetch"),
) -> None:
    """Verify Threads token/account access by fetching a recent sample."""

    _, settings = _build_project_config()
    threads_client = _build_threads_client(settings)

    try:
        resolved_user_id = threads_client.resolve_threads_user_id(account)
        sample_posts = threads_client.fetch_recent_sample(account=resolved_user_id, sample_limit=limit)
    except ThreadsAPIError as exc:
        typer.echo(f"Threads check failed: {exc}")
        raise typer.Exit(code=1)

    typer.echo("Threads check OK")
    typer.echo(f"Resolved user id: {resolved_user_id}")
    typer.echo(f"Fetched sample posts: {len(sample_posts)}")
    for post in sample_posts[:limit]:
        typer.echo(f"- {post.post_id} @ {post.created_at.isoformat()}")


if __name__ == "__main__":
    app()
