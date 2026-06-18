"""Integrations gateway service (Phase 16).

Manages outbound webhook subscriptions (HMAC-signed delivery with retries),
receives inbound webhooks (signature-verified), and issues API clients
(key + scopes) for third-party REST access. Connector adapters for payments
(Phase 17), LMS/SIS (Phase 18), and cloud/collab (Phase 19) build on this.
"""

from __future__ import annotations

import os
import uuid

from aoep_shared.service import create_service
from aoep_shared.webhooks import (
    MockSender,
    SubscriptionStore,
    WebhookEvent,
    WebhookSubscription,
    dispatch,
    verify_signature,
)
from fastapi import HTTPException, Request
from pydantic import BaseModel

from aoep_shared.connectors.finance import MockFinanceConnector, parse_payment_event

app = create_service("integrations")
app.state.subs = SubscriptionStore()
app.state.api_clients = {}          # api_key -> {"name", "scopes"}
# Default to an in-memory recording sender so the gateway runs offline; a real
# httpx sender is injected in production.
app.state.sender = MockSender()
# Entitlement grants from payments (customer -> set of features). In production
# this forwards to the billing service; held here for the offline gateway.
app.state.entitlements = {}
app.state.finance = MockFinanceConnector()


# --------------------------------------------------------------------------- #
# Webhook subscriptions + emit
# --------------------------------------------------------------------------- #
class CreateSubscriptionRequest(BaseModel):
    url: str
    event_types: list[str] = []
    secret: str = ""


@app.post("/webhooks/subscriptions", response_model=WebhookSubscription)
def create_subscription(req: CreateSubscriptionRequest) -> WebhookSubscription:
    return app.state.subs.add(WebhookSubscription(**req.model_dump()))


@app.get("/webhooks/subscriptions", response_model=list[WebhookSubscription])
def list_subscriptions() -> list[WebhookSubscription]:
    return app.state.subs.list()


class EmitRequest(BaseModel):
    event_type: str
    data: dict = {}


@app.post("/webhooks/emit")
def emit_event(req: EmitRequest) -> dict:
    event = WebhookEvent(event_type=req.event_type, data=req.data)
    results = dispatch(app.state.subs, event, sender=app.state.sender)
    return {
        "event_id": event.id,
        "delivered": sum(1 for r in results if r.delivered),
        "total": len(results),
        "results": [{"subscription_id": r.subscription_id, "delivered": r.delivered,
                     "attempts": r.attempts, "status": r.status} for r in results],
    }


# --------------------------------------------------------------------------- #
# Inbound webhooks (signature-verified)
# --------------------------------------------------------------------------- #
def _inbound_secret(provider: str) -> str:
    return os.environ.get(f"{provider.upper()}_WEBHOOK_SECRET", "") or \
        os.environ.get("WEBHOOK_SIGNING_KEY", "dev-webhook-secret")


@app.post("/webhooks/inbound/{provider}")
async def inbound_webhook(provider: str, request: Request) -> dict:
    body = await request.body()
    signature = request.headers.get("X-AOEP-Signature", "") or \
        request.headers.get("X-Signature", "")
    if not verify_signature(body, signature, _inbound_secret(provider)):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    return {"provider": provider, "accepted": True, "bytes": len(body)}


# --------------------------------------------------------------------------- #
# Finance / payment connectors (Phase 17)
# --------------------------------------------------------------------------- #
@app.post("/payments/webhook/{provider}")
async def payment_webhook(provider: str, request: Request) -> dict:
    body = await request.body()
    signature = request.headers.get("X-AOEP-Signature", "") or \
        request.headers.get("X-Signature", "")
    if not verify_signature(body, signature, _inbound_secret(provider)):
        raise HTTPException(status_code=401, detail="invalid webhook signature")
    import json

    event = parse_payment_event(provider, json.loads(body or b"{}"))
    if event.kind == "ignore":
        return {"provider": provider, "handled": False, "type": event.raw_type}

    feats = app.state.entitlements.setdefault(event.customer, set())
    if event.kind == "grant":
        feats.add(event.entitlement)
        app.state.finance.record_revenue(event.amount, currency=event.currency,
                                          memo=f"{provider}:{event.customer}")
        out = WebhookEvent(event_type="enrollment.paid",
                           data={"customer": event.customer, "entitlement": event.entitlement})
        dispatch(app.state.subs, out, sender=app.state.sender)
    elif event.kind == "revoke":
        feats.discard(event.entitlement)
    return {"provider": provider, "handled": True, "kind": event.kind,
            "customer": event.customer, "entitlements": sorted(feats)}


@app.get("/entitlements/{customer}")
def get_entitlements(customer: str) -> dict:
    return {"customer": customer, "entitlements": sorted(app.state.entitlements.get(customer, set()))}


class PayoutRequest(BaseModel):
    account: str
    amount: float
    currency: str = "usd"


@app.post("/finance/payout")
def finance_payout(req: PayoutRequest) -> dict:
    return app.state.finance.payout(req.account, req.amount, currency=req.currency)


# --------------------------------------------------------------------------- #
# API clients (key + scopes) for third-party REST access
# --------------------------------------------------------------------------- #
class CreateClientRequest(BaseModel):
    name: str
    scopes: list[str] = []


@app.post("/clients")
def create_client(req: CreateClientRequest) -> dict:
    api_key = "aoep_" + uuid.uuid4().hex
    app.state.api_clients[api_key] = {"name": req.name, "scopes": req.scopes}
    return {"name": req.name, "api_key": api_key, "scopes": req.scopes}


@app.get("/clients")
def list_clients() -> dict:
    return {"clients": [{"name": v["name"], "scopes": v["scopes"]}
                        for v in app.state.api_clients.values()]}
