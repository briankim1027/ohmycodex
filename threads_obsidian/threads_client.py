from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Protocol

try:
    import httpx
except ImportError:  # pragma: no cover - allows pure-logic tests without optional deps installed
    httpx = None  # type: ignore[assignment]

from threads_obsidian.models import Post
from threads_obsidian.time_utils import parse_iso_datetime

logger = logging.getLogger(__name__)


class ThreadsAPIError(RuntimeError):
    pass


class ThreadsAdapter(Protocol):
    def fetch_posts(self, account: str, start: datetime, end: datetime) -> list[Post]:
        ...


@dataclass(frozen=True)
class HttpThreadsAdapterConfig:
    access_token: str
    base_url: str
    profile_lookup_endpoint: str
    user_threads_endpoint_template: str
    posts_fields: str
    posts_limit: int = 25
    timeout_seconds: int = 20
    max_retries: int = 5


class HttpThreadsAdapter:
    def __init__(self, config: HttpThreadsAdapterConfig) -> None:
        self.config = config

    def fetch_posts(self, account: str, start: datetime, end: datetime) -> list[Post]:
        if not self.config.access_token:
            raise ThreadsAPIError("THREADS_ACCESS_TOKEN is empty; set .env value before collecting.")

        threads_user_id = self.resolve_threads_user_id(account)
        url = self.build_user_threads_url(threads_user_id)
        params = self.build_threads_query_params(
            since=start,
            until=end,
            fields=self.config.posts_fields,
            limit=self.config.posts_limit,
        )
        payload = self._request_with_retry(
            url=url,
            params=params,
            context=f"threads fetch account='{account}' user_id='{threads_user_id}'",
        )

        records = payload.get("data") or payload.get("posts") or []
        if not isinstance(records, list):
            raise ThreadsAPIError(f"Unexpected API payload structure for account '{account}'.")

        posts: list[Post] = []
        for item in records:
            try:
                posts.append(self._parse_post(account, threads_user_id, item))
            except Exception as exc:  # pragma: no cover
                logger.warning("Skipping malformed post payload for account=%s error=%s", account, exc)
        return posts

    def fetch_recent_sample(self, account: str, sample_limit: int = 3) -> list[Post]:
        threads_user_id = self.resolve_threads_user_id(account)
        url = self.build_user_threads_url(threads_user_id)
        payload = self._request_with_retry(
            url=url,
            params=self.build_threads_query_params(
                fields=self.config.posts_fields,
                limit=sample_limit,
            ),
            context=f"threads sample account='{account}' user_id='{threads_user_id}'",
        )
        records = payload.get("data") or []
        if not isinstance(records, list):
            raise ThreadsAPIError("Unexpected Threads response while fetching sample posts.")
        return [self._parse_post(account, threads_user_id, item) for item in records if isinstance(item, dict)]

    def resolve_threads_user_id(self, account: str) -> str:
        if self._looks_like_user_id(account):
            return account

        url = self.build_profile_lookup_url()
        payload = self._request_with_retry(
            url=url,
            params=self.build_profile_lookup_params(account),
            context=f"profile lookup username='{account}'",
        )
        return self.extract_user_id_from_profile_lookup(payload, username=account)

    def _request_with_retry(self, url: str, params: dict[str, str], *, context: str) -> dict[str, Any]:
        if httpx is None:
            raise ThreadsAPIError(
                "httpx is not installed. Install requirements.txt to enable Threads HTTP calls."
            )

        headers = {
            "Authorization": f"Bearer {self.config.access_token}",
            "Accept": "application/json",
        }

        last_error: Exception | None = None
        for attempt in range(1, self.config.max_retries + 1):
            try:
                response = httpx.get(url, params=params, headers=headers, timeout=self.config.timeout_seconds)
            except httpx.HTTPError as exc:
                last_error = exc
                if attempt >= self.config.max_retries:
                    break
                wait_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "Threads request failed (attempt=%s/%s), retrying in %ss: %s",
                    attempt,
                    self.config.max_retries,
                    wait_seconds,
                    exc,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code == 429 and attempt < self.config.max_retries:
                wait_seconds = 2 ** (attempt - 1)
                logger.warning(
                    "Threads rate-limited (429), retrying in %ss (attempt=%s/%s)",
                    wait_seconds,
                    attempt,
                    self.config.max_retries,
                )
                time.sleep(wait_seconds)
                continue

            if response.status_code >= 400:
                raise ThreadsAPIError(
                    self._format_http_error(response.status_code, response.text, context)
                )

            try:
                decoded = response.json()
            except ValueError as exc:
                raise ThreadsAPIError("Threads API returned non-JSON response") from exc

            if not isinstance(decoded, dict):
                raise ThreadsAPIError("Threads API JSON response must be an object")
            return decoded

        raise ThreadsAPIError(f"Threads API request failed after retries ({context}): {last_error}")

    def build_profile_lookup_url(self) -> str:
        return self._build_url(self.config.profile_lookup_endpoint)

    def build_user_threads_url(self, threads_user_id: str) -> str:
        endpoint = self.config.user_threads_endpoint_template.format(threads_user_id=threads_user_id)
        return self._build_url(endpoint)

    def _build_url(self, endpoint: str) -> str:
        return f"{self.config.base_url.rstrip('/')}/{endpoint.lstrip('/')}"

    @staticmethod
    def _looks_like_user_id(account: str) -> bool:
        candidate = account.strip()
        return bool(candidate) and candidate.isdigit()

    @staticmethod
    def build_profile_lookup_params(username: str) -> dict[str, str]:
        return {"username": username}

    @staticmethod
    def build_threads_query_params(
        *,
        fields: str,
        limit: int,
        since: datetime | None = None,
        until: datetime | None = None,
    ) -> dict[str, str]:
        safe_limit = max(1, limit)
        params = {"fields": fields, "limit": str(safe_limit)}
        if since is not None:
            params["since"] = since.isoformat()
        if until is not None:
            params["until"] = until.isoformat()
        return params

    @staticmethod
    def extract_user_id_from_profile_lookup(payload: dict[str, Any], *, username: str) -> str:
        user_id = str(payload.get("id") or payload.get("threads_user_id") or "").strip()
        if user_id:
            return user_id

        data = payload.get("data")
        if isinstance(data, dict):
            nested_id = str(data.get("id") or data.get("threads_user_id") or "").strip()
            if nested_id:
                return nested_id

        if isinstance(data, list) and data:
            first = data[0]
            if isinstance(first, dict):
                list_id = str(first.get("id") or first.get("threads_user_id") or "").strip()
                if list_id:
                    return list_id

        raise ThreadsAPIError(
            f"Unable to resolve Threads user id for '{username}'. "
            "This account may be permission-gated or unavailable to your token."
        )

    @staticmethod
    def _format_http_error(status_code: int, body: str, context: str) -> str:
        shortened = re.sub(r"\s+", " ", body).strip()[:300]
        if status_code in (401, 403, 404):
            return (
                f"Threads API error {status_code} during {context}. "
                f"Account/token may be permission-gated. Response: {shortened}"
            )
        return f"Threads API error {status_code} during {context}: {shortened}"

    @staticmethod
    def _parse_post(account: str, threads_user_id: str, item: dict[str, Any]) -> Post:
        post_id = str(item.get("post_id") or item.get("id") or "").strip()
        if not post_id:
            raise ValueError("missing post id")

        author_id = str(
            item.get("author_id")
            or (item.get("user") or {}).get("id")
            or item.get("username")
            or threads_user_id
            or account
        ).strip()
        if not author_id:
            raise ValueError("missing author id")

        created_raw = item.get("created_at") or item.get("timestamp")
        if not created_raw:
            raise ValueError("missing created_at")

        text = str(item.get("text") or item.get("body") or item.get("content") or "")
        post_url = str(item.get("post_url") or item.get("permalink") or item.get("url") or "")

        return Post(
            author_id=author_id,
            post_id=post_id,
            created_at=parse_iso_datetime(str(created_raw)),
            text=text,
            post_url=post_url,
        )
