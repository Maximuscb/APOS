from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional


def utcnow() -> datetime:
    """Server-side 'now' in UTC (naive, canonical)."""
    return datetime.utcnow()


def parse_iso_datetime(value: Optional[str]) -> Optional[datetime]:
    """
    Parse an ISO-8601 datetime string and normalize to UTC-naive datetime.

    - None / "" -> None
    - "YYYY-MM-DDTHH:MM" (naive) is interpreted as UTC
    - "...Z" or "...+/-HH:MM" is converted to UTC and tzinfo is stripped
    """
    if value is None:
        return None
    s = value.strip()
    if not s:
        return None

    # Accept trailing Z
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"

    dt = datetime.fromisoformat(s)

    # Normalize to UTC-naive
    if dt.tzinfo is None:
        # interpret naive as UTC
        return dt.replace(tzinfo=None)

    return dt.astimezone(timezone.utc).replace(tzinfo=None)


def to_utc_z(dt: Optional[datetime]) -> Optional[str]:
    """
    Serializes datetime to ISO-8601 with trailing 'Z'.
    If dt is naive, it is treated as UTC.
    """
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    dt_utc = dt.astimezone(timezone.utc).replace(microsecond=0)
    return dt_utc.isoformat().replace("+00:00", "Z")
