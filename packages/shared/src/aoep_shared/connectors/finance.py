"""Finance / payment connectors (Integrations, Phase 17).

Normalizes inbound payment-provider webhooks (Stripe-style) into a PaymentEvent
that the gateway turns into an entitlement grant/revoke + an outbound event. Plus
a FinanceConnector abstraction for payouts/accounting export with an offline Mock.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List

# Event types that grant vs revoke access.
_GRANT_TYPES = {"checkout.session.completed", "invoice.paid", "invoice.payment_succeeded"}
_REVOKE_TYPES = {"charge.refunded", "refund", "customer.subscription.deleted"}


@dataclass
class PaymentEvent:
    kind: str                 # "grant" | "revoke" | "ignore"
    customer: str = ""
    amount: float = 0.0
    currency: str = "usd"
    entitlement: str = "pro"
    raw_type: str = ""


def parse_payment_event(provider: str, payload: dict) -> PaymentEvent:
    """Normalize a provider webhook payload into a PaymentEvent."""
    etype = str(payload.get("type") or payload.get("event") or "")
    obj = (payload.get("data") or {}).get("object") or payload.get("data") or {}
    customer = str(obj.get("customer") or obj.get("customer_id") or payload.get("customer") or "")
    amount = float(obj.get("amount_total") or obj.get("amount") or 0) / (
        100.0 if obj.get("amount_total") or obj.get("amount") else 1.0)
    meta = obj.get("metadata") or {}
    entitlement = str(meta.get("entitlement") or meta.get("plan") or "pro")
    currency = str(obj.get("currency") or "usd")

    if etype in _GRANT_TYPES:
        kind = "grant"
    elif etype in _REVOKE_TYPES:
        kind = "revoke"
    else:
        kind = "ignore"
    return PaymentEvent(kind=kind, customer=customer, amount=amount, currency=currency,
                        entitlement=entitlement, raw_type=etype)


class FinanceConnector:
    """Outbound finance integration (payouts, accounting export)."""

    name = "finance"

    def record_revenue(self, amount: float, *, currency: str = "usd", memo: str = "") -> dict:
        raise NotImplementedError

    def payout(self, account: str, amount: float, *, currency: str = "usd") -> dict:
        raise NotImplementedError


@dataclass
class MockFinanceConnector(FinanceConnector):
    name: str = "mock-finance"
    revenue: List[dict] = field(default_factory=list)
    payouts: List[dict] = field(default_factory=list)

    def record_revenue(self, amount: float, *, currency: str = "usd", memo: str = "") -> dict:
        entry = {"amount": amount, "currency": currency, "memo": memo}
        self.revenue.append(entry)
        return entry

    def payout(self, account: str, amount: float, *, currency: str = "usd") -> dict:
        entry = {"account": account, "amount": amount, "currency": currency}
        self.payouts.append(entry)
        return entry
