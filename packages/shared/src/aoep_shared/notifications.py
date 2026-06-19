"""Notification feed generator for the mobile/web inbox.

The mobile app's Notifications screen (and web parity, later) calls
``GET /notifications/feed`` on the curriculum service. The endpoint returns a
chronological list of personalized notification items - new audio classes,
"continue listening" reminders, recommendations, daily streak nudges, etc.

Notifications are deterministic given the inputs (audio catalog, optional
student state) so server-side rendering and client-side caching match. Local
push notifications (delivered by the OS via expo-notifications on the device)
are scheduled by the client from these items - no remote push server is
required for the demo.

Pure/offline + stdlib + pydantic.
"""

from __future__ import annotations

import datetime as _dt
import hashlib
from typing import List, Optional

from pydantic import BaseModel, Field

from .audio_courses import build_catalog


class NotificationItem(BaseModel):
    id: str
    kind: str  # new_class | continue | recommended | reminder | streak | system
    title: str
    body: str
    course_id: Optional[str] = None
    deep_link: Optional[str] = None
    created_at: str  # ISO-8601 UTC timestamp
    icon: str = "bell"  # bell | sparkle | flame | play | trophy | gift


class NotificationFeed(BaseModel):
    student_id: str = "guest"
    generated_at: str
    unread: int = 0
    items: List[NotificationItem] = Field(default_factory=list)


def _stable_id(*parts: str) -> str:
    return hashlib.sha1("|".join(parts).encode()).hexdigest()[:16]


def _iso(ts: _dt.datetime) -> str:
    return ts.replace(microsecond=0, tzinfo=_dt.timezone.utc).isoformat()


def build_feed(
    *,
    student_id: str = "guest",
    completed_course_ids: Optional[List[str]] = None,
    in_progress_course_ids: Optional[List[str]] = None,
    interests: Optional[List[str]] = None,
    streak_days: int = 0,
    now: Optional[_dt.datetime] = None,
    limit: int = 30,
) -> NotificationFeed:
    """Render a personalized notification feed.

    The feed mixes:
      * "new class" entries from the latest audio catalog (top of list);
      * "continue listening" reminders for any course the student has paused;
      * "recommended for you" suggestions matching the student's interests;
      * a "daily reminder" entry (Drive Mode greeting);
      * a "streak" entry when the student has an active streak.
    """
    completed = set(completed_course_ids or [])
    in_progress = list(in_progress_course_ids or [])
    interests_l = [i.lower() for i in (interests or [])]
    base = (now or _dt.datetime.now(_dt.timezone.utc)).replace(microsecond=0)

    items: List[NotificationItem] = []
    catalog = build_catalog()
    fresh = [c for c in catalog if c.id not in completed][:120]

    matched = []
    if interests_l:
        for c in fresh:
            blob = " ".join([c.category.lower(), c.subject.lower(),
                             c.title.lower(), *(t.lower() for t in c.tags)])
            if any(i in blob for i in interests_l):
                matched.append(c)
    pool = (matched or fresh)[:6]
    for offset, c in enumerate(pool[:3]):
        ts = base - _dt.timedelta(minutes=15 * (offset + 1))
        items.append(NotificationItem(
            id=_stable_id("new", student_id, c.id),
            kind="new_class",
            title=f"New audio class: {c.title}",
            body=f"{c.duration_min} min · {c.category} · {c.level}. Tap to start in Drive Mode.",
            course_id=c.id,
            deep_link=f"aiclassroom://drive/{c.id}",
            created_at=_iso(ts),
            icon="sparkle",
        ))

    by_id = {c.id: c for c in catalog}
    for offset, cid in enumerate(in_progress[:3]):
        c = by_id.get(cid)
        if c is None:
            continue
        ts = base - _dt.timedelta(hours=offset + 1)
        items.append(NotificationItem(
            id=_stable_id("continue", student_id, c.id),
            kind="continue",
            title=f"Continue: {c.title}",
            body="Pick up where you left off — your spot is saved.",
            course_id=c.id,
            deep_link=f"aiclassroom://drive/{c.id}",
            created_at=_iso(ts),
            icon="play",
        ))

    if matched:
        rec = matched[3:6]
        for offset, c in enumerate(rec):
            ts = base - _dt.timedelta(hours=2 + offset)
            items.append(NotificationItem(
                id=_stable_id("rec", student_id, c.id),
                kind="recommended",
                title=f"Picked for you: {c.title}",
                body=f"Matches your interest in {', '.join(interests_l[:2])}.",
                course_id=c.id,
                deep_link=f"aiclassroom://drive/{c.id}",
                created_at=_iso(ts),
                icon="gift",
            ))

    if streak_days > 0:
        items.append(NotificationItem(
            id=_stable_id("streak", student_id, str(streak_days), base.date().isoformat()),
            kind="streak",
            title=f"{streak_days}-day streak! 🔥",
            body="Keep the momentum — one short class today extends your streak.",
            deep_link="aiclassroom://drive",
            created_at=_iso(base - _dt.timedelta(hours=8)),
            icon="flame",
        ))

    items.append(NotificationItem(
        id=_stable_id("daily", student_id, base.date().isoformat()),
        kind="reminder",
        title="Your daily class is ready",
        body="A 5-minute audio class is waiting in Drive Mode.",
        deep_link="aiclassroom://drive",
        created_at=_iso(base - _dt.timedelta(hours=10)),
        icon="bell",
    ))

    items.sort(key=lambda i: i.created_at, reverse=True)
    items = items[: max(1, limit)]
    return NotificationFeed(
        student_id=student_id,
        generated_at=_iso(base),
        unread=sum(1 for i in items if i.kind in {"new_class", "continue", "recommended"}),
        items=items,
    )
