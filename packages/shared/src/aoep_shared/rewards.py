"""Learning rewards: points for course completion, redeemable for discounts/prizes.

Gamifies learning - learners earn points when they pass courses (more for harder
levels, high scores, and hands-on labs) and redeem them for class discounts,
swag, or RAFFLE ENTRIES for high-value prizes (e.g. a PlayStation 5 or a gold
bar). High-value prizes use a sweepstakes/raffle model (points buy entries)
rather than direct payout - the realistic + legally-sound approach (see
legal/SWEEPSTAKES.txt; a "no purchase necessary" free-entry path is required).

Pure/offline-testable; the identity service holds each account's ledger.
"""

from __future__ import annotations

import enum
import time
import uuid
from dataclasses import dataclass, field
from typing import List, Optional

_LEVEL_BASE = {"beginner": 100, "intermediate": 200, "advanced": 300}
_CONSOLATION = 10   # points even for a failed attempt (encourages retrying)


def points_for_completion(
    level: str = "beginner",
    *,
    passed: bool = True,
    score: Optional[float] = None,
    hands_on: bool = False,
) -> int:
    """Points awarded for completing a course."""
    base = _LEVEL_BASE.get((level or "beginner").lower(), 100)
    if not passed:
        return _CONSOLATION
    pts = base
    if score is not None:
        pts += int(base * 0.5 * max(0.0, min(1.0, score)))   # up to +50% by score
    if hands_on:
        pts += 50                                            # hands-on/lab bonus
    return pts


# --------------------------------------------------------------------------- #
# Points ledger
# --------------------------------------------------------------------------- #
@dataclass
class PointsEntry:
    delta: int
    reason: str
    ref: str = ""
    ts: float = field(default_factory=lambda: time.time())


class PointsLedger:
    def __init__(self) -> None:
        self.entries: List[PointsEntry] = []

    @property
    def balance(self) -> int:
        return sum(e.delta for e in self.entries)

    def earn(self, delta: int, reason: str, ref: str = "") -> PointsEntry:
        if delta <= 0:
            raise ValueError("earned points must be positive")
        entry = PointsEntry(delta=delta, reason=reason, ref=ref)
        self.entries.append(entry)
        return entry

    def spend(self, cost: int, reason: str, ref: str = "") -> PointsEntry:
        if cost <= 0:
            raise ValueError("cost must be positive")
        if cost > self.balance:
            raise ValueError("insufficient points")
        entry = PointsEntry(delta=-cost, reason=reason, ref=ref)
        self.entries.append(entry)
        return entry


# --------------------------------------------------------------------------- #
# Prize catalog + redemption
# --------------------------------------------------------------------------- #
class PrizeKind(str, enum.Enum):
    DISCOUNT = "discount"     # a voucher: % off a class / membership perk
    ITEM = "item"             # a fulfillable physical item (swag / attire)
    GIFT_CARD = "gift_card"   # real $ value: Amazon / Visa / app-store gift card
    DONATION = "donation"     # convert points into a charitable donation
    RAFFLE = "raffle"         # points buy entries into a sweepstakes for a big prize


_KIND_LABELS = {
    PrizeKind.DISCOUNT: "Discount",
    PrizeKind.ITEM: "Swag & attire",
    PrizeKind.GIFT_CARD: "Gift card",
    PrizeKind.DONATION: "Donation",
    PrizeKind.RAFFLE: "Raffle entry",
}


@dataclass(frozen=True)
class Prize:
    id: str
    name: str
    kind: PrizeKind
    cost_points: int
    detail: dict = field(default_factory=dict)   # e.g. {"percent": 10} | {"prize": "PS5"}

    @property
    def kind_label(self) -> str:
        """Human-friendly label for the prize kind (used by web/mobile UIs)."""
        return _KIND_LABELS.get(self.kind, self.kind.value.replace("_", " ").title())


# Reward catalog. Designed off common loyalty programs (Duolingo, Microsoft
# Rewards, Fetch, airline miles): a cheap entry-level reward so EVERY learner can
# redeem something early, mid-tier swag/attire + class discounts, real-$ gift
# cards priced for a sustainable economy (~1000 pts per $1, since a passed course
# grants ~300-450 pts), an optional charitable donation, and aspirational raffle
# prizes whose per-entry cost is high enough to feel meaningful.
REWARDS_CATALOG: List[Prize] = [
    # -- Class discounts & membership (drive more learning; cheap) ---------- #
    Prize("discount_10", "10% off any class", PrizeKind.DISCOUNT, 200, {"percent": 10}),
    Prize("discount_25", "25% off any class", PrizeKind.DISCOUNT, 500, {"percent": 25}),
    Prize("discount_50", "50% off any class", PrizeKind.DISCOUNT, 1000, {"percent": 50}),
    Prize("free_class", "One free class (100% off)", PrizeKind.DISCOUNT, 1500, {"percent": 100}),
    Prize("premium_month", "1 month Premium membership", PrizeKind.DISCOUNT, 4000,
          {"percent": 100, "grants": "premium_30d"}),

    # -- Swag & attire (physical fulfillment) ------------------------------ #
    Prize("swag_stickers", "Salareen sticker pack", PrizeKind.ITEM, 150, {"item": "stickers"}),
    Prize("swag_mug", "Salareen learner mug", PrizeKind.ITEM, 400, {"item": "mug"}),
    Prize("swag_socks", "Salareen socks", PrizeKind.ITEM, 700, {"item": "socks"}),
    Prize("swag_cap", "Embroidered cap", PrizeKind.ITEM, 900, {"item": "cap"}),
    Prize("swag_bottle", "Insulated water bottle", PrizeKind.ITEM, 1100, {"item": "bottle"}),
    Prize("swag_tshirt", "Salareen T-shirt", PrizeKind.ITEM, 1500, {"item": "tshirt"}),
    Prize("swag_hoodie", "Premium zip hoodie", PrizeKind.ITEM, 3500, {"item": "hoodie"}),
    Prize("swag_backpack", "Laptop backpack", PrizeKind.ITEM, 4000, {"item": "backpack"}),

    # -- Gift cards (real $ value) ----------------------------------------- #
    Prize("gift_amazon_5", "$5 Amazon gift card", PrizeKind.GIFT_CARD, 5000,
          {"brand": "Amazon", "value_usd": 5}),
    Prize("gift_amazon_10", "$10 Amazon gift card", PrizeKind.GIFT_CARD, 9500,
          {"brand": "Amazon", "value_usd": 10}),
    Prize("gift_amazon_25", "$25 Amazon gift card", PrizeKind.GIFT_CARD, 22500,
          {"brand": "Amazon", "value_usd": 25}),
    Prize("gift_visa_10", "$10 Visa prepaid card", PrizeKind.GIFT_CARD, 10000,
          {"brand": "Visa", "value_usd": 10}),
    Prize("gift_appstore_10", "$10 App Store & Google Play", PrizeKind.GIFT_CARD, 9500,
          {"brand": "App Store / Google Play", "value_usd": 10}),

    # -- Charitable donation ----------------------------------------------- #
    Prize("donate_stem_5", "Donate $5 to the STEM education fund", PrizeKind.DONATION, 4500,
          {"cause": "STEM education fund", "value_usd": 5}),

    # -- Raffle entries (aspirational; per-entry cost raised) --------------- #
    Prize("raffle_swag_bundle", "Raffle entry: limited-edition swag bundle", PrizeKind.RAFFLE, 800,
          {"prize": "Limited-edition swag bundle"}),
    Prize("raffle_scholarship", "Raffle entry: $500 course scholarship", PrizeKind.RAFFLE, 1200,
          {"prize": "$500 course scholarship"}),
    Prize("raffle_ps5", "Raffle entry: PlayStation 5", PrizeKind.RAFFLE, 1500,
          {"prize": "PlayStation 5"}),
    Prize("raffle_ipad", "Raffle entry: iPad (10th gen)", PrizeKind.RAFFLE, 1800,
          {"prize": "iPad (10th gen)"}),
    Prize("raffle_gold", "Raffle entry: 1g gold bar", PrizeKind.RAFFLE, 2000,
          {"prize": "1g gold bar"}),
    Prize("raffle_macbook", "Raffle entry: MacBook Air", PrizeKind.RAFFLE, 3000,
          {"prize": "MacBook Air"}),
]

_CATALOG_BY_ID = {p.id: p for p in REWARDS_CATALOG}


def prize_by_id(prize_id: str) -> Optional[Prize]:
    return _CATALOG_BY_ID.get(prize_id)


@dataclass
class Redemption:
    prize_id: str
    kind: str
    cost_points: int
    voucher_code: Optional[str] = None    # discount/item fulfillment
    percent: Optional[int] = None         # for discount vouchers
    raffle_entry_id: Optional[str] = None # for raffle entries
    detail: dict = field(default_factory=dict)
    created_at: float = field(default_factory=lambda: time.time())


def redeem_prize(ledger: PointsLedger, prize: Prize) -> Redemption:
    """Spend points on a prize; returns a voucher (discount/item) or a raffle entry."""
    ledger.spend(prize.cost_points, reason=f"redeem:{prize.id}", ref=prize.id)
    if prize.kind is PrizeKind.RAFFLE:
        return Redemption(prize_id=prize.id, kind=prize.kind.value,
                          cost_points=prize.cost_points,
                          raffle_entry_id=uuid.uuid4().hex[:12], detail=prize.detail)
    code = f"AOEP-{prize.id.upper()}-{uuid.uuid4().hex[:6].upper()}"
    return Redemption(prize_id=prize.id, kind=prize.kind.value,
                      cost_points=prize.cost_points, voucher_code=code,
                      percent=prize.detail.get("percent"), detail=prize.detail)
