"""JSON serialization for Salareen live rooms (Redis / shared store)."""

from __future__ import annotations

from dataclasses import asdict
from typing import Any, Dict, List

from .live_room import (
    BannedUser,
    ChatMessage,
    LiveRoom,
    Participant,
    QueueEntry,
    RecordingState,
    SlideSync,
    UserReport,
)
from .live_room_social import GiftEvent, ReactionEvent


def live_room_to_json(room: LiveRoom) -> str:
  import json

  return json.dumps(live_room_to_dict(room), separators=(",", ":"))


def live_room_from_json(raw: str) -> LiveRoom:
  import json

  return live_room_from_dict(json.loads(raw))


def live_room_to_dict(room: LiveRoom) -> Dict[str, Any]:
  return {
      "room_id": room.room_id,
      "class_id": room.class_id,
      "session_id": room.session_id,
      "lesson_id": room.lesson_id,
      "title": room.title,
      "room_size": room.room_size,
      "participants": {k: asdict(v) for k, v in room.participants.items()},
      "chat": [asdict(m) for m in room.chat],
      "recording": asdict(room.recording),
      "slide": asdict(room.slide),
      "status": room.status,
      "opened_at": room.opened_at,
      "banned": {k: asdict(v) for k, v in room.banned.items()},
      "moderator_key": room.moderator_key,
      "speaking_queue": [asdict(e) for e in room.speaking_queue],
      "floor_participant_id": room.floor_participant_id,
      "reports": [asdict(r) for r in room.reports],
      "gift_feed": [asdict(g) for g in room.gift_feed],
      "reactions": [asdict(r) for r in room.reactions],
      "viewer_count": room.viewer_count,
      "country": room.country,
      "state": room.state,
      "city": room.city,
      "latitude": room.latitude,
      "longitude": room.longitude,
      "creator_name": room.creator_name,
      "creator_account_id": room.creator_account_id,
      "admin_participant_id": getattr(room, "admin_participant_id", "") or "",
      "presenting": bool(getattr(room, "presenting", False)),
      "scheduled_start": getattr(room, "scheduled_start", "") or "",
      "presentation_started_at": getattr(room, "presentation_started_at", "") or "",
      "slide_started_at": getattr(room, "slide_started_at", "") or "",
      "auto_advance_seconds": int(getattr(room, "auto_advance_seconds", 5) or 5),
      "auto_start_grace_seconds": int(getattr(room, "auto_start_grace_seconds", 300) or 300),
      "welcome_message": getattr(room, "welcome_message", "") or "",
      "welcome_started_at": getattr(room, "welcome_started_at", "") or "",
      "pre_class_welcome_seconds": int(getattr(room, "pre_class_welcome_seconds", 12) or 12),
      "duration_seconds": int(getattr(room, "duration_seconds", 0) or 0),
      "ended_at": getattr(room, "ended_at", "") or "",
      "xr_lab_enabled": bool(getattr(room, "xr_lab_enabled", False)),
      "xr_lab": getattr(room, "xr_lab", None),
      "xr_attempts": dict(getattr(room, "xr_attempts", None) or {}),
      "audience_profile": dict(getattr(room, "audience_profile", None) or {}),
      "group_game": dict(getattr(room, "group_game", None) or {}) or None,
  }


def live_room_from_dict(data: Dict[str, Any]) -> LiveRoom:
  participants = {}
  for k, raw in (data.get("participants") or {}).items():
      row = dict(raw)
      row.setdefault("account_id", "")
      row.setdefault("student_id", "")
      row.setdefault("readiness_band", "")
      row.setdefault("readiness_score", 0.0)
      # Drop unknown keys that older snapshots may lack / extras that break ctor.
      allowed = {
          "id", "name", "role", "identity", "account_id", "muted", "muted_by_host",
          "hand_raised", "can_publish", "language", "joined_at", "last_seen",
          "is_admin", "student_id", "readiness_band", "readiness_score",
      }
      participants[k] = Participant(**{kk: vv for kk, vv in row.items() if kk in allowed})
  chat = [ChatMessage(**m) for m in (data.get("chat") or [])]
  banned = {k: BannedUser(**v) for k, v in (data.get("banned") or {}).items()}
  speaking_queue: List[QueueEntry] = [
      QueueEntry(**e) for e in (data.get("speaking_queue") or [])
  ]
  reports = [UserReport(**r) for r in (data.get("reports") or [])]
  gift_feed = [GiftEvent(**g) for g in (data.get("gift_feed") or [])]
  reactions = [ReactionEvent(**r) for r in (data.get("reactions") or [])]
  recording = RecordingState(**(data.get("recording") or {}))
  slide = SlideSync(**(data.get("slide") or {}))
  return LiveRoom(
      room_id=data["room_id"],
      class_id=data["class_id"],
      session_id=data["session_id"],
      lesson_id=data["lesson_id"],
      title=data.get("title") or "Live class",
      room_size=int(data.get("room_size") or 6),
      participants=participants,
      chat=chat,
      recording=recording,
      slide=slide,
      status=data.get("status") or "live",
      opened_at=data.get("opened_at") or "",
      banned=banned,
      moderator_key=data.get("moderator_key") or "",
      speaking_queue=speaking_queue,
      floor_participant_id=data.get("floor_participant_id") or "",
      reports=reports,
      gift_feed=gift_feed,
      reactions=reactions,
      viewer_count=int(data.get("viewer_count") or 0),
      country=data.get("country") or "",
      state=data.get("state") or "",
      city=data.get("city") or "",
      latitude=float(data.get("latitude") or 0),
      longitude=float(data.get("longitude") or 0),
      creator_name=data.get("creator_name") or "",
      creator_account_id=data.get("creator_account_id") or "",
      admin_participant_id=data.get("admin_participant_id") or "",
      presenting=bool(data.get("presenting", False)),
      scheduled_start=data.get("scheduled_start") or "",
      presentation_started_at=data.get("presentation_started_at") or "",
      slide_started_at=data.get("slide_started_at") or "",
      auto_advance_seconds=int(data.get("auto_advance_seconds") or 5),
      auto_start_grace_seconds=int(data.get("auto_start_grace_seconds") or 300),
      welcome_message=data.get("welcome_message") or "",
      welcome_started_at=data.get("welcome_started_at") or "",
      pre_class_welcome_seconds=int(data.get("pre_class_welcome_seconds") or 12),
      duration_seconds=int(data.get("duration_seconds") or 0),
      ended_at=data.get("ended_at") or "",
      xr_lab_enabled=bool(data.get("xr_lab_enabled", False)),
      xr_lab=data.get("xr_lab"),
      xr_attempts=dict(data.get("xr_attempts") or {}),
      audience_profile=dict(data.get("audience_profile") or {}),
      group_game=dict(data.get("group_game") or {}) or None,
  )
