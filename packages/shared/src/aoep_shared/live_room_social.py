"""Live-room social layer: virtual gifts, floating reactions, host follows.

Pure/offline-testable; orchestrator persists gift feed on LiveRoom state and
uses LiveRoomGiftLedger for point balances when identity is unavailable.
"""

from __future__ import annotations

import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple

from .rewards import PointsLedger

REACTION_TYPES: Tuple[str, ...] = ("❤️", "👏", "🔥", "😂", "🎉", "👍")
REACTION_BUFFER_SIZE = 40
GIFT_FEED_SIZE = 50
DEFAULT_DEMO_BALANCE = 500


class LiveRoomSocialError(ValueError):
    """Invalid social live-room request."""


def _ts() -> str:
    return datetime.now(timezone.utc).isoformat()


@dataclass(frozen=True)
class GiftCatalogItem:
    id: str
    name: str
    emoji: str
    cost_points: int

    def to_dict(self) -> dict:
        return asdict(self)


GIFT_CATALOG: Tuple[GiftCatalogItem, ...] = (
    GiftCatalogItem("rose", "Rose", "🌹", 10),
    GiftCatalogItem("heart", "Heart", "💖", 20),
    GiftCatalogItem("star", "Star", "⭐", 50),
    GiftCatalogItem("crown", "Crown", "👑", 100),
    GiftCatalogItem("rocket", "Rocket", "🚀", 200),
    GiftCatalogItem("diamond", "Diamond", "💎", 500),
)

_CATALOG_BY_ID = {g.id: g for g in GIFT_CATALOG}


def gift_by_id(gift_id: str) -> Optional[GiftCatalogItem]:
    return _CATALOG_BY_ID.get((gift_id or "").strip())


@dataclass
class GiftEvent:
    id: str
    gift_id: str
    gift_name: str
    emoji: str
    cost_points: int
    sender_participant_id: str
    sender_name: str
    sender_identity: str
    recipient_participant_id: str
    recipient_name: str
    sent_at: str = ""

    def __post_init__(self) -> None:
        if not self.sent_at:
            self.sent_at = _ts()

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ReactionEvent:
    id: str
    emoji: str
    participant_id: str
    participant_name: str
    sent_at: str = ""

    def __post_init__(self) -> None:
        emoji = (self.emoji or "").strip()
        if emoji not in REACTION_TYPES:
            raise LiveRoomSocialError(
                f"reaction must be one of {', '.join(REACTION_TYPES)}"
            )
        self.emoji = emoji
        if not self.sent_at:
            self.sent_at = _ts()

    def to_dict(self) -> dict:
        return asdict(self)


class LiveRoomGiftLedger:
    """Per-identity sandbox points for live gifts (offline-safe demo economy)."""

    def __init__(self, *, default_balance: int = DEFAULT_DEMO_BALANCE) -> None:
        self._default = default_balance
        self._ledgers: Dict[str, PointsLedger] = {}

    def balance(self, identity: str) -> int:
        ident = (identity or "").strip()
        if not ident:
            return 0
        ledger = self._ledgers.get(ident)
        if ledger is None:
            return self._default
        return ledger.balance

    def _ensure(self, identity: str) -> PointsLedger:
        ident = (identity or "").strip()
        if ident not in self._ledgers:
            ledger = PointsLedger()
            ledger.earn(self._default, reason="live_room_demo_balance", ref=ident)
            self._ledgers[ident] = ledger
        return self._ledgers[ident]

    def spend(self, identity: str, cost: int, *, reason: str, ref: str = "") -> int:
        if cost <= 0:
            raise LiveRoomSocialError("gift cost must be positive")
        ident = (identity or "").strip()
        if not ident:
            raise LiveRoomSocialError("sender identity is required")
        ledger = self._ensure(ident)
        if cost > ledger.balance:
            raise LiveRoomSocialError("insufficient points for this gift")
        ledger.spend(cost, reason=reason, ref=ref)
        return ledger.balance

    def credit(self, identity: str, amount: int, *, reason: str, ref: str = "") -> int:
        if amount <= 0:
            raise LiveRoomSocialError("credit must be positive")
        ident = (identity or "").strip()
        if not ident:
            raise LiveRoomSocialError("recipient identity is required")
        ledger = self._ensure(ident)
        ledger.earn(amount, reason=reason, ref=ref)
        return ledger.balance


class HostFollowStore:
    """Minimal follow graph: follower identity -> host participant id per room."""

    def __init__(self) -> None:
        self._follows: Dict[str, set[str]] = {}

    def _key(self, room_id: str, host_id: str) -> str:
        return f"{room_id}:{host_id}"

    def follow(self, room_id: str, host_id: str, follower_identity: str) -> bool:
        ident = (follower_identity or "").strip()
        if not ident:
            raise LiveRoomSocialError("follower identity is required")
        key = self._key(room_id, host_id)
        bucket = self._follows.setdefault(key, set())
        if ident in bucket:
            return False
        bucket.add(ident)
        return True

    def unfollow(self, room_id: str, host_id: str, follower_identity: str) -> bool:
        ident = (follower_identity or "").strip()
        key = self._key(room_id, host_id)
        bucket = self._follows.get(key)
        if not bucket or ident not in bucket:
            return False
        bucket.discard(ident)
        return True

    def is_following(self, room_id: str, host_id: str, follower_identity: str) -> bool:
        ident = (follower_identity or "").strip()
        return ident in self._follows.get(self._key(room_id, host_id), set())

    def follower_count(self, room_id: str, host_id: str) -> int:
        return len(self._follows.get(self._key(room_id, host_id), set()))


@dataclass
class PresenceToast:
    kind: str
    participant_id: str
    name: str
    at: str = field(default_factory=_ts)

    def to_dict(self) -> dict:
        return asdict(self)
