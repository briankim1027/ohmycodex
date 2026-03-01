from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    threads_access_token: str = Field(default="", alias="THREADS_ACCESS_TOKEN")
    threads_api_base_url: str = Field(default="https://graph.threads.net", alias="THREADS_API_BASE_URL")
    threads_profile_lookup_endpoint: str = Field(
        default="/v1.0/profile_lookup",
        alias="THREADS_PROFILE_LOOKUP_ENDPOINT",
    )
    threads_user_threads_endpoint_template: str = Field(
        default="/v1.0/{threads_user_id}/threads",
        alias="THREADS_USER_THREADS_ENDPOINT_TEMPLATE",
    )
    threads_posts_fields: str = Field(
        default="id,text,timestamp,permalink,username",
        alias="THREADS_POSTS_FIELDS",
    )
    threads_posts_limit: int = Field(default=25, alias="THREADS_POSTS_LIMIT")
    threads_timeout_seconds: int = Field(default=20, alias="THREADS_TIMEOUT_SECONDS")
    threads_max_retries: int = Field(default=5, alias="THREADS_MAX_RETRIES")

    google_drive_root_folder_id: str = Field(
        default="1r2pv6RTDIpWt-3iTXvr8OGWUR3rtNgbQ",
        alias="GOOGLE_DRIVE_ROOT_FOLDER_ID",
    )
    google_oauth_client_secret_file: str = Field(
        default="credentials/client_secret.json", alias="GOOGLE_OAUTH_CLIENT_SECRET_FILE"
    )
    google_oauth_token_file: str = Field(default="state/google_token.json", alias="GOOGLE_OAUTH_TOKEN_FILE")

    collector_state_file: str = Field(default="state/collector_state.json", alias="COLLECTOR_STATE_FILE")
    collector_log_dir: str = Field(default="logs", alias="COLLECTOR_LOG_DIR")
    collector_accounts_file: str = Field(default="config/accounts.yaml", alias="COLLECTOR_ACCOUNTS_FILE")


class ProjectConfig:
    def __init__(self, project_root: Path, settings: Settings) -> None:
        self.project_root = project_root
        self.settings = settings

    @property
    def state_file(self) -> Path:
        return self.project_root / self.settings.collector_state_file

    @property
    def log_dir(self) -> Path:
        return self.project_root / self.settings.collector_log_dir

    @property
    def accounts_file(self) -> Path:
        return self.project_root / self.settings.collector_accounts_file

    @property
    def oauth_client_secret_file(self) -> Path:
        return self.project_root / self.settings.google_oauth_client_secret_file

    @property
    def oauth_token_file(self) -> Path:
        return self.project_root / self.settings.google_oauth_token_file


def parse_accounts_override(raw: str | None) -> list[str] | None:
    if not raw:
        return None
    parsed = [item.strip() for item in raw.split(",") if item.strip()]
    return parsed or None


def load_accounts(config_path: Path) -> list[str]:
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    accounts = payload.get("accounts") or []
    return [str(acc).strip() for acc in accounts if str(acc).strip()]
