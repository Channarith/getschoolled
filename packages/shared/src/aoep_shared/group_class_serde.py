"""JSON serialization for scheduled group classes (Redis / shared store)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .group_classes import GroupClass, InstructorReview, Registration


def group_class_to_json(gc: GroupClass) -> str:
    import json

    return json.dumps(group_class_to_dict(gc), separators=(",", ":"))


def group_class_from_json(raw: str) -> GroupClass:
    import json

    return group_class_from_dict(json.loads(raw))


def group_class_to_dict(gc: GroupClass) -> Dict[str, Any]:
    d = asdict(gc)
    d["registrations"] = [asdict(r) for r in gc.registrations]
    d["reviews"] = [asdict(r) for r in gc.reviews]
    return d


def group_class_from_dict(data: Dict[str, Any]) -> GroupClass:
    regs = [Registration(**r) for r in (data.get("registrations") or [])]
    reviews = [InstructorReview(**r) for r in (data.get("reviews") or [])]
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
        reviews=reviews,
        created_by_account_id=data.get("created_by_account_id") or "",
        instructor_account_id=data.get("instructor_account_id") or "",
        instructor_name=data.get("instructor_name") or "",
        marketplace_listing=bool(data.get("marketplace_listing") or False),
        audit_required=bool(data.get("audit_required") or False),
        audit_status=data.get("audit_status") or "approved",
        credentials_summary=data.get("credentials_summary") or "",
        credential_photo_url=data.get("credential_photo_url") or "",
        identity_photo_url=data.get("identity_photo_url") or "",
        interview_notes=data.get("interview_notes") or "",
        demo_notes=data.get("demo_notes") or "",
        audited_by=data.get("audited_by") or "",
        audited_at=data.get("audited_at") or "",
        price_per_user_usd=float(data.get("price_per_user_usd") or 0.0),
        commission_rate=float(data.get("commission_rate") or 0.15),
        payment_required=bool(data.get("payment_required") or False),
        attendee_code_required=bool(data.get("attendee_code_required") or False),
        max_faces_allowed=int(data.get("max_faces_allowed") or 1),
        require_liveness=bool(data.get("require_liveness") if data.get("require_liveness") is not None else True),
        recording_protection_required=bool(
            data.get("recording_protection_required")
            if data.get("recording_protection_required") is not None
            else True
        ),
        device_profile=data.get("device_profile") or "",
        camera_ingest_mode=data.get("camera_ingest_mode") or "platform_default",
        camera_sources=[dict(row) for row in (data.get("camera_sources") or []) if isinstance(row, dict)],
        session_id=data.get("session_id") or "",
        bridge_session_id=data.get("bridge_session_id") or "",
        live_room_id=data.get("live_room_id") or "",
    )
