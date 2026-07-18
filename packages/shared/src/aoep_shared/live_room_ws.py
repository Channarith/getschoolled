"""WebSocket event helpers for Salareen live rooms."""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, Optional


class LiveRoomWsEvent(str, Enum):
    CHAT = "chat"
    REACTION = "reaction"
    GIFT = "gift"
    PRESENCE = "presence"
    QUEUE = "queue"
    SLIDE = "slide"
    ROOM = "room"
    FOLLOW = "follow"
    VIEWER_COUNT = "viewer_count"
    HOST_DELTA = "host_delta"
    LAB = "lab"
    LAB_SCORE = "lab_score"
    AUDIENCE = "audience"
    GAME = "game"


def ws_event(kind: LiveRoomWsEvent, payload: Dict[str, Any], *, room_id: str = "") -> dict:
    return {
        "type": kind.value,
        "room_id": room_id,
        "payload": payload,
    }


def ws_chat(message: dict, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.CHAT, {"message": message}, room_id=room_id)


def ws_reaction(reaction: dict, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.REACTION, {"reaction": reaction}, room_id=room_id)


def ws_gift(gift: dict, *, room_id: str = "", sender_balance: Optional[int] = None) -> dict:
    body: Dict[str, Any] = {"gift": gift}
    if sender_balance is not None:
        body["sender_balance"] = sender_balance
    return ws_event(LiveRoomWsEvent.GIFT, body, room_id=room_id)


def ws_presence(toast: dict, *, room_id: str = "", viewer_count: int = 0) -> dict:
    return ws_event(
        LiveRoomWsEvent.PRESENCE,
        {"toast": toast, "viewer_count": viewer_count},
        room_id=room_id,
    )


def ws_queue(room: dict, *, room_id: str = "") -> dict:
    return ws_event(
        LiveRoomWsEvent.QUEUE,
        {
            "speaking_queue": room.get("speaking_queue") or [],
            "floor_participant_id": room.get("floor_participant_id") or "",
            "floor_holder": room.get("floor_holder"),
        },
        room_id=room_id,
    )


def ws_slide(slide: dict, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.SLIDE, {"slide": slide}, room_id=room_id)


def ws_room_snapshot(room: dict, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.ROOM, {"room": room}, room_id=room_id)


def ws_follow(following: bool, follower_count: int, *, room_id: str = "") -> dict:
    return ws_event(
        LiveRoomWsEvent.FOLLOW,
        {"following": following, "follower_count": follower_count},
        room_id=room_id,
    )


def ws_viewer_count(count: int, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.VIEWER_COUNT, {"viewer_count": count}, room_id=room_id)


def ws_lab(lab: dict, *, room_id: str = "", enabled: bool = True) -> dict:
    return ws_event(
        LiveRoomWsEvent.LAB,
        {"enabled": enabled, "lab": lab},
        room_id=room_id,
    )


def ws_lab_score(summary: dict, *, room_id: str = "", participant_id: str = "") -> dict:
    return ws_event(
        LiveRoomWsEvent.LAB_SCORE,
        {"participant_id": participant_id, "attempt": summary},
        room_id=room_id,
    )


def ws_audience(profile: dict, *, room_id: str = "") -> dict:
    return ws_event(LiveRoomWsEvent.AUDIENCE, {"audience_profile": profile}, room_id=room_id)


def ws_game(
    game: dict, *, room_id: str = "", event: Optional[dict] = None,
    room: Optional[dict] = None,
) -> dict:
    return ws_event(
        LiveRoomWsEvent.GAME,
        {"game": game, "event": event or {}, "room": room},
        room_id=room_id,
    )


def ws_host_delta(
    *,
    text: str = "",
    done: bool = False,
    message: Optional[dict] = None,
    asker: str = "",
    room_id: str = "",
) -> dict:
    """Incremental AI-host (Theodore) answer streaming to the whole room.

    ``text`` is the next chunk to append (a sentence-ish segment). ``done`` marks
    the end of the answer and carries the final ``message`` (the posted host chat
    message) so late/other participants render the same finalized answer. ``asker``
    is the learner Theodore is answering, for a "answering @Name…" affordance.
    """
    return ws_event(
        LiveRoomWsEvent.HOST_DELTA,
        {"text": text, "done": done, "message": message, "asker": asker},
        room_id=room_id,
    )
