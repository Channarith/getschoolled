"""Refund eligibility for a course purchase. DRAFT policy for counsel review: every number is configuration.

Proposed default (the owner/counsel can change any of it): a web purchase can be refunded within 14 days of purchase when the
learner has completed no more than 20% of the lessons and no completion certificate has been issued. Everything else goes to a
person (support), never to a silent "no".

Config (names only): REFUND_WINDOW_DAYS (14), REFUND_MAX_PROGRESS_PCT (20), REFUND_BLOCK_AFTER_CERTIFICATE (1),
REFUND_AUTO_APPROVE (1; 0 sends every request to support), SELLER_SUPPORT_EMAIL.
Store purchases (Apple, Google) are refunded by the store; our server only revokes access when the store tells us.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Optional

STORE_PROVIDERS = ("apple", "google")
WEB_PROVIDERS = ("stripe", "paypal")

# Reason codes (stable: the UI and tests use them).
ELIGIBLE = "eligible"
NEEDS_REVIEW = "needs_review"
NOT_PAID = "not_paid"
STORE_PURCHASE = "store_purchase"
WINDOW_PASSED = "window_passed"
TOO_MUCH_PROGRESS = "too_much_progress"
CERTIFICATE_ISSUED = "certificate_issued"


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


@dataclass(frozen=True)
class RefundPolicy:
    window_days: int = 14
    max_progress_pct: int = 20
    block_after_certificate: bool = True
    auto_approve: bool = True

    @classmethod
    def from_env(cls) -> "RefundPolicy":
        return cls(
            window_days=_int_env("REFUND_WINDOW_DAYS", 14),
            max_progress_pct=_int_env("REFUND_MAX_PROGRESS_PCT", 20),
            block_after_certificate=_int_env("REFUND_BLOCK_AFTER_CERTIFICATE", 1) != 0,
            auto_approve=_int_env("REFUND_AUTO_APPROVE", 1) != 0,
        )

    def public(self) -> dict[str, Any]:
        return {"window_days": self.window_days, "max_progress_pct": self.max_progress_pct,
                "block_after_certificate": self.block_after_certificate, "auto_approve": self.auto_approve}


def evaluate(
    order: Mapping[str, Any],
    *,
    progress_pct: Optional[float],
    certificate_issued: bool = False,
    policy: Optional[RefundPolicy] = None,
    now: Callable[[], float] = time.time,
) -> dict[str, Any]:
    """Is this order refundable by the rules? Returns {eligible, reason, message, days_left, auto}."""
    rules = policy or RefundPolicy.from_env()
    provider = str(order.get("provider") or "").lower()
    out = {"eligible": False, "reason": NOT_PAID, "message": "", "days_left": 0, "auto": False}
    if order.get("status") != "paid":
        out["message"] = "This purchase is already refunded or closed."
        return out
    if provider in STORE_PROVIDERS:
        out.update(reason=STORE_PURCHASE, message=(
            "This purchase was made through the App Store or Google Play. Ask them for the refund from your purchase history; "
            "your access ends automatically when they confirm it."))
        return out
    elapsed_days = max(0.0, (now() - float(order.get("created_at") or 0)) / 86400.0)
    out["days_left"] = max(0, int(rules.window_days - elapsed_days))
    if elapsed_days > rules.window_days:
        out.update(reason=WINDOW_PASSED, message=f"Refunds are available for {rules.window_days} days after purchase. Contact support if something went wrong.")
        return out
    if certificate_issued and rules.block_after_certificate:
        out.update(reason=CERTIFICATE_ISSUED, message="A completion certificate has been issued for this course, so it is not eligible for an automatic refund. Contact support.")
        return out
    if progress_pct is None:
        out.update(reason=NEEDS_REVIEW, message="We could not check your progress automatically. Support will review your request.")
        return out
    if progress_pct > rules.max_progress_pct:
        out.update(reason=TOO_MUCH_PROGRESS, message=f"More than {rules.max_progress_pct}% of the course has been completed. Contact support and we will take a look.")
        return out
    out.update(eligible=True, reason=ELIGIBLE, message="This purchase is eligible for a refund.", auto=rules.auto_approve)
    return out
