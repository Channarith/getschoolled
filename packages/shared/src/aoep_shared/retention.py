"""Data-retention / deletion enforcement.

The schema and consent records carry a retention window (retention_days); this
module turns that into ENFORCED deletion so personal/biometric data is not kept
longer than allowed (GDPR storage limitation, COPPA/BIPA retention, FERPA). Pure
and datetime-aware; the memory store + a scheduled runner call it.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Optional


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _aware(dt: datetime) -> datetime:
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def is_expired(
    recorded_at: datetime,
    retention_days: Optional[int],
    *,
    now: Optional[datetime] = None,
    default_days: Optional[int] = None,
) -> bool:
    """Whether data recorded at ``recorded_at`` is past its retention window.

    A record with no explicit retention_days uses ``default_days`` if provided;
    if neither is set, the record is kept (not expired).
    """
    days = retention_days if retention_days is not None else default_days
    if days is None:
        return False
    now = now or _utcnow()
    return _aware(now) >= _aware(recorded_at) + timedelta(days=days)


@dataclass
class PurgeReport:
    scanned: int = 0
    consent_records_purged: int = 0
    students_purged: int = 0
