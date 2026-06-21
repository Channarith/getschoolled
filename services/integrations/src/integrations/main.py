"""Integrations gateway service (Phase 16).

Manages outbound webhook subscriptions (HMAC-signed delivery with retries),
receives inbound webhooks (signature-verified), and issues API clients
(key + scopes) for third-party REST access. Connector adapters for payments
(Phase 17), LMS/SIS (Phase 18), and cloud/collab (Phase 19) build on this.
"""

from __future__ import annotations

import os
import uuid

from aoep_shared.internal_auth import require_internal
from aoep_shared.service import create_service
from aoep_shared.webhooks import (
    MockSender,
    SubscriptionStore,
    WebhookEvent,
    WebhookSubscription,
    dispatch,
    verify_signature,
)
from fastapi import Depends, HTTPException, Request
from pydantic import BaseModel

from aoep_shared.connectors.finance import MockFinanceConnector, parse_payment_event
from aoep_shared.connectors.cloud import (
    MockCalendar,
    MockNotifier,
    schedule_event,
    verify_oidc_claims,
)
from aoep_shared.connectors.lms import (
    MockLMS,
    build_ags_score,
    build_xapi_statement,
    parse_lti_launch,
    parse_oneroster,
)

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
app.state.lms = MockLMS()           # production: a real Canvas/Moodle/Classroom adapter
app.state.rosters = {}              # context_id -> [members]
app.state.notifier = MockNotifier()  # production: Slack/Workspace adapter
app.state.calendar = MockCalendar()  # production: Google/Microsoft calendar adapter


# --------------------------------------------------------------------------- #
# Webhook subscriptions + emit
# --------------------------------------------------------------------------- #
class CreateSubscriptionRequest(BaseModel):
    url: str
    event_types: list[str] = []
    secret: str = ""


@app.post("/webhooks/subscriptions", response_model=WebhookSubscription,
          dependencies=[Depends(require_internal)])
def create_subscription(req: CreateSubscriptionRequest) -> WebhookSubscription:
    return app.state.subs.add(WebhookSubscription(**req.model_dump()))


@app.get("/webhooks/subscriptions", response_model=list[WebhookSubscription],
         dependencies=[Depends(require_internal)])
def list_subscriptions() -> list[WebhookSubscription]:
    return app.state.subs.list()


class EmitRequest(BaseModel):
    event_type: str
    data: dict = {}


@app.post("/webhooks/emit", dependencies=[Depends(require_internal)])
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
    """Resolve the HMAC secret for verifying an inbound webhook from
    ``provider``. Lookup order:

      1. ``{PROVIDER}_WEBHOOK_SECRET`` (per-provider override)
      2. ``WEBHOOK_SIGNING_KEY`` (platform default)
      3. ``"dev-webhook-secret"`` (LOCAL deploy mode only)

    In cloud/production deploy modes we refuse to fall back to the
    dev secret — if both env vars are unset we return an empty
    string, which makes signature verification fail closed instead
    of accepting payloads signed with a well-known dev key.
    """
    explicit = (os.environ.get(f"{provider.upper()}_WEBHOOK_SECRET", "") or
                os.environ.get("WEBHOOK_SIGNING_KEY", ""))
    if explicit:
        return explicit
    deploy_mode = (os.environ.get("DEPLOY_MODE", "local") or "local").lower()
    if deploy_mode == "local":
        return "dev-webhook-secret"
    # Fail-closed in cloud mode: return empty string so any inbound
    # signature comparison fails and we return 401.
    return ""


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


@app.post("/finance/payout", dependencies=[Depends(require_internal)])
def finance_payout(req: PayoutRequest) -> dict:
    return app.state.finance.payout(req.account, req.amount, currency=req.currency)


# --------------------------------------------------------------------------- #
# Education platform connectors: LMS / SIS (Phase 18)
# --------------------------------------------------------------------------- #
@app.post("/lms/lti/launch")
def lti_launch(claims: dict) -> dict:
    try:
        ctx = parse_lti_launch(claims)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    return {"user_id": ctx.user_id, "context_id": ctx.context_id,
            "roles": ctx.roles, "name": ctx.name}


class RosterImportRequest(BaseModel):
    context_id: str
    payload: dict                    # OneRoster users payload


@app.post("/lms/roster")
def lms_roster(req: RosterImportRequest) -> dict:
    members = parse_oneroster(req.payload)
    app.state.rosters[req.context_id] = members
    return {"context_id": req.context_id, "count": len(members),
            "members": [{"user_id": m.user_id, "role": m.role, "name": m.name} for m in members]}


class GradePassbackRequest(BaseModel):
    user_id: str
    score: float
    maximum: float = 1.0
    line_item: str = "homework"
    export_xapi: bool = False


@app.post("/lms/grade-passback")
def lms_grade_passback(req: GradePassbackRequest) -> dict:
    payload = build_ags_score(req.user_id, req.score, req.maximum, line_item=req.line_item)
    result = app.state.lms.push_grade(payload)
    out = {"pushed": payload, "result": result}
    if req.export_xapi:
        scaled = (req.score / req.maximum) if req.maximum else 0.0
        out["xapi"] = build_xapi_statement(req.user_id, "completed", req.line_item, scaled=scaled)
    return out


# --------------------------------------------------------------------------- #
# Cloud / collaboration connectors (Phase 19)
# --------------------------------------------------------------------------- #
class NotifyRequest(BaseModel):
    channel: str = "#general"
    text: str


@app.post("/notify")
def notify(req: NotifyRequest) -> dict:
    return app.state.notifier.send(req.channel, req.text)


class ScheduleRequest(BaseModel):
    title: str
    start: str                       # ISO 8601
    duration_min: int = 60
    attendees: list[str] = []


@app.post("/calendar/schedule")
def calendar_schedule(req: ScheduleRequest) -> dict:
    try:
        event = schedule_event(req.title, req.start, req.duration_min, req.attendees)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"bad start time: {exc}")
    return app.state.calendar.create_event(event)


class OidcRequest(BaseModel):
    claims: dict
    audience: str


@app.post("/sso/oidc")
def sso_oidc(req: OidcRequest) -> dict:
    try:
        ident = verify_oidc_claims(req.claims, audience=req.audience)
    except ValueError as exc:
        raise HTTPException(status_code=401, detail=str(exc))
    return {"subject": ident.subject, "email": ident.email, "name": ident.name,
            "provider": ident.provider}


# --------------------------------------------------------------------------- #
# API clients (key + scopes) for third-party REST access
# --------------------------------------------------------------------------- #
class CreateClientRequest(BaseModel):
    name: str
    scopes: list[str] = []


@app.post("/clients", dependencies=[Depends(require_internal)])
def create_client(req: CreateClientRequest) -> dict:
    api_key = "aoep_" + uuid.uuid4().hex
    app.state.api_clients[api_key] = {"name": req.name, "scopes": req.scopes}
    return {"name": req.name, "api_key": api_key, "scopes": req.scopes}


@app.get("/clients", dependencies=[Depends(require_internal)])
def list_clients() -> dict:
    return {"clients": [{"name": v["name"], "scopes": v["scopes"]}
                        for v in app.state.api_clients.values()]}
