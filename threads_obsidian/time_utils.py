from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))


def parse_iso_datetime(value: str) -> datetime:
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    elif re.search(r"[+-]\d{4}$", normalized):
        normalized = f"{normalized[:-5]}{normalized[-5:-2]}:{normalized[-2:]}"

    dt = datetime.fromisoformat(normalized)
    if dt.tzinfo is None:
        raise ValueError(f"Datetime must be timezone-aware: {value}")
    return dt.astimezone(timezone.utc)


def to_kst(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        raise ValueError("Datetime must be timezone-aware")
    return dt.astimezone(KST)


def kst_date_str(dt: datetime) -> str:
    return to_kst(dt).strftime("%Y-%m-%d")


def utc_now() -> datetime:
    return datetime.now(timezone.utc)
