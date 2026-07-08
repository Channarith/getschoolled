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
  }


def live_room_from_dict(data: Dict[str, Any]) -> LiveRoom:
  participants = {}
  for k, raw in (data.get("participants") or {}).items():
      row = dict(raw)
      row.setdefault("account_id", "")
      participants[k] = Participant(**row)
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
  )
