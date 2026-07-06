"""JSON serialization for scheduled group classes (Redis / shared store)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .group_classes import GroupClass, Registration


def group_class_to_json(gc: GroupClass) -> str:
    import json

    return json.dumps(group_class_to_dict(gc), separators=(",", ":"))


def group_class_from_json(raw: str) -> GroupClass:
    import json

    return group_class_from_dict(json.loads(raw))


def group_class_to_dict(gc: GroupClass) -> Dict[str, Any]:
    d = asdict(gc)
    d["registrations"] = [asdict(r) for r in gc.registrations]
    return d


def group_class_from_dict(data: Dict[str, Any]) -> GroupClass:
    regs = [Registration(**r) for r in (data.get("registrations") or [])]
    return GroupClass(
        title=data.get("title") or "",
        lesson_id=data.get("lesson_id") or "",
        platform=data.get("platform") or "salareen",
        meeting_url=data.get("meeting_url") or "",
        start_time=data.get("start_time") or "",
        duration_min=int(data.get("duration_min") or 60),
        host=data.get("host") or "Salareen AI",
        capacity=int(data.get("capacity") or 100),
        room_size=int(data.get("room_size") or 6),
        language=data.get("language") or "en",
        description=data.get("description") or "",
        id=data.get("id") or "",
        status=data.get("status") or "scheduled",
        registrations=regs,
        session_id=data.get("session_id") or "",
        bridge_session_id=data.get("bridge_session_id") or "",
        live_room_id=data.get("live_room_id") or "",
    )
