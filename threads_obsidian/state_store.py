from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from threads_obsidian.models import CollectWindow
from threads_obsidian.time_utils import KST, parse_iso_datetime


@dataclass
class CollectorState:
    last_success_at: datetime | None = None
    last_run_id: str | None = None
    version: int = 1


class StateStore:
    def __init__(self, path: Path) -> None:
        self.path = path

    def load(self) -> CollectorState:
        if not self.path.exists():
            return CollectorState()

        data = json.loads(self.path.read_text(encoding="utf-8"))
        last_success_at = data.get("last_success_at")
        return CollectorState(
            last_success_at=parse_iso_datetime(last_success_at) if last_success_at else None,
            last_run_id=data.get("last_run_id"),
            version=int(data.get("version", 1)),
        )

    def save_success(self, run_id: str, success_at: datetime) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "last_success_at": success_at.astimezone(KST).isoformat(),
            "last_run_id": run_id,
            "version": 1,
        }
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def resolve_collect_window(now_utc: datetime, state: CollectorState) -> CollectWindow:
    if now_utc.tzinfo is None:
        raise ValueError("now_utc must be timezone-aware")

    if state.last_success_at:
        start = state.last_success_at.astimezone(timezone.utc)
    else:
        now_kst = now_utc.astimezone(KST)
        start_kst = datetime(year=now_kst.year, month=now_kst.month, day=now_kst.day, tzinfo=KST)
        start = start_kst.astimezone(timezone.utc)

    return CollectWindow(start=start, end=now_utc.astimezone(timezone.utc))
