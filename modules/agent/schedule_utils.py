"""Compute next run times for story agent schedules (UTC storage)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def compute_next_run_at(
    *,
    schedule_type: str,
    run_at: datetime,
    weekdays: list[int] | None,
    tz_name: str,
    after: datetime | None = None,
) -> datetime | None:
    """
    Return the next UTC instant when the schedule should fire.

    schedule_type: once | daily | weekly
    run_at: anchor datetime (for once = exact fire time; for recurring = time-of-day anchor)
    weekdays: 0=Monday .. 6=Sunday (Python weekday); used for weekly
    """
    after = _ensure_utc(after or datetime.now(timezone.utc))
    run_at_utc = _ensure_utc(run_at)

    if schedule_type == "once":
        return run_at_utc if run_at_utc > after else None

    try:
        tz = ZoneInfo(tz_name or "UTC")
    except Exception:
        tz = ZoneInfo("UTC")

    local_anchor = run_at_utc.astimezone(tz)
    hour, minute = local_anchor.hour, local_anchor.minute
    second = 0
    microsecond = 0

    local_after = after.astimezone(tz)

    if schedule_type == "daily":
        candidate = local_after.replace(
            hour=hour, minute=minute, second=second, microsecond=microsecond
        )
        if candidate <= local_after:
            candidate += timedelta(days=1)
        return candidate.astimezone(timezone.utc)

    if schedule_type == "weekly":
        allowed = sorted(set(weekdays or [local_anchor.weekday()]))
        if not allowed:
            allowed = [local_anchor.weekday()]

        for offset in range(8):
            day = local_after + timedelta(days=offset)
            if day.weekday() not in allowed:
                continue
            candidate = day.replace(
                hour=hour, minute=minute, second=second, microsecond=microsecond
            )
            if candidate > local_after:
                return candidate.astimezone(timezone.utc)
        return None

    return None
