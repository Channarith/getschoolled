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

app = create_service("integrations")
app.state.subs = SubscriptionStore()
app.state.api_clients = {}          # api_key -> {"name", "scopes"}
# Default to an in-memory recording sender so the gateway runs offline; a real
# httpx sender is injected in production.
app.state.sender = MockSender()


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
