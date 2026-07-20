"""Billing FastAPI app.

Exposes the single entitlements gate -- can_start(class_type, language, features)
-- that every other service consults before starting a class, plus checkout
creation via the PaymentProvider (Stripe in cloud, sandbox stub local).
"""

from __future__ import annotations

import os
import threading
import time

from aoep_shared.auth import verify_token
from aoep_shared.entitlements import PLANS, can_start
from aoep_shared.flags import require_admin
from aoep_shared.plan_pricing import CONSUMER_PLANS, consumer_plan_for_tier
from aoep_shared.payments import (
    COUNTRY_METHODS,
    LOCALE_DEFAULT_COUNTRY,
    PaymentMethod,
    label_for,
    methods_for_country,
    methods_for_locale,
    processor_for,
)
from aoep_shared.schemas import ClassType, PlanTier
from aoep_shared.service import create_service
from fastapi import Depends, Header, HTTPException
from pydantic import BaseModel

_AUTH_KEY_DEFAULT = "dev-auth-signing-key"


def _token_key() -> bytes:
    return os.environ.get("AUTH_SIGNING_KEY", _AUTH_KEY_DEFAULT).encode()


def current_account_id(authorization: str = Header(default="")) -> str:
    """Resolve Bearer token to account ID (401 if missing/invalid)."""
    token = authorization[7:] if authorization.lower().startswith("bearer ") else authorization
    claims = verify_token(token, _token_key()) if token else None
    if not claims:
        raise HTTPException(status_code=401, detail="invalid or expired session")
    return claims.get("sub", "")


def _admin_secret() -> str:
    return os.environ.get("ADMIN_SECRET", "dev-admin-secret")


def require_admin_secret(x_admin_secret: str = Header(default="")) -> str:
    """Admin shared-secret gate for internal/ops endpoints."""
    if not require_admin(x_admin_secret, _admin_secret()):
        raise HTTPException(status_code=403, detail="admin secret required")
    return x_admin_secret


# Idempotency cache: (customer_id, plan) -> (created_at, CheckoutResponse)
_checkout_cache: dict[tuple, tuple] = {}
_checkout_cache_lock = threading.Lock()
_CHECKOUT_CACHE_TTL = 60.0  # seconds


def _get_cached_checkout(customer_id: str, plan: str):
    """Return cached CheckoutResponse if created within TTL, else None."""
    key = (customer_id, plan)
    with _checkout_cache_lock:
        entry = _checkout_cache.get(key)
        if entry and (time.time() - entry[0]) < _CHECKOUT_CACHE_TTL:
            return entry[1]
        if entry:
            del _checkout_cache[key]
    return None


def _cache_checkout(customer_id: str, plan: str, response) -> None:
    key = (customer_id, plan)
    with _checkout_cache_lock:
        _checkout_cache[key] = (time.time(), response)

app = create_service("billing")

# Ad revenue ledger (impressions/clicks/CPM). In-memory per replica, like
# telemetry; the admin console reads GET /ads/revenue for a live estimate.
from aoep_shared.ad_revenue import AdRevenueLedger  # noqa: E402

app.state.ad_ledger = AdRevenueLedger()


class CanStartRequest(BaseModel):
    tier: PlanTier
    class_type: ClassType = ClassType.GROUP
    language: str = "en"
    features: list[str] = []


class CanStartResponse(BaseModel):
    allowed: bool
    reasons: list[str] = []


class CheckoutRequest(BaseModel):
    customer_id: str
    plan: PlanTier
    method: PaymentMethod = PaymentMethod.CARD


class CheckoutResponse(BaseModel):
    session_id: str
    url: str
    provider: str
    method: str
    instructions: str = ""


class PaymentMethodInfo(BaseModel):
    method: str
    label: str
    processor: str
    available: bool


class PaymentMethodsResponse(BaseModel):
    methods: list[PaymentMethodInfo]


@app.get("/plans")
def plans() -> dict:
    out: dict = {}
    for tier, plan in PLANS.items():
        consumer = consumer_plan_for_tier(tier.value)
        entry = {
            "languages": sorted(plan.languages),
            "solo_classes": plan.solo_classes,
            "cross_class_memory": plan.cross_class_memory,
            "recordings": plan.recordings,
            "analytics": plan.analytics,
        }
        if consumer:
            entry.update({
                "display_name": consumer.display_name,
                "price_usd": consumer.price_usd,
                "billing_interval": consumer.billing_interval,
                "ads": consumer.ads,
                "blurb": consumer.blurb,
                "consumer": True,
            })
        else:
            entry["consumer"] = False
        out[tier.value] = entry
    return out


@app.get("/plans/consumer")
def consumer_plans() -> dict:
    """Netflix-style Standard ($19.99) and VIP ($29.99) picker data."""
    return {
        tier: {
            "tier": p.tier,
            "display_name": p.display_name,
            "price_usd": p.price_usd,
            "billing_interval": p.billing_interval,
            "ads": p.ads,
            "blurb": p.blurb,
        }
        for tier, p in CONSUMER_PLANS.items()
    }


@app.post("/entitlements/can-start", response_model=CanStartResponse)
def entitlements_can_start(req: CanStartRequest) -> CanStartResponse:
    decision = can_start(
        req.tier,
        class_type=req.class_type,
        language=req.language,
        features=req.features,
    )
    return CanStartResponse(allowed=decision.allowed, reasons=decision.reasons)


@app.get("/payment-methods", response_model=PaymentMethodsResponse)
def payment_methods(
    country: str | None = None,
    locale: str | None = None,
) -> PaymentMethodsResponse:
    """List payment methods, optionally filtered/ordered for a specific
    country or locale.

    - ``country=US|BR|DE|...`` returns the methods popular in that
      country, ordered by popularity (CARD always near the top).
    - ``locale=vi|km|hi|...`` does the same but infers the country
      from the locale (vi -> VN, km -> KH, hi -> IN, etc.).
    - With neither, returns every method the platform knows about.

    Each method is flagged by whether the active provider can currently
    process it. In local/sandbox mode every method is "available"; in
    cloud mode only methods whose processor has its API key set show
    available=True.
    """
    payment = app.state.factory.payment()
    available = payment.supported_methods()

    if country:
        methods = methods_for_country(country)
    elif locale:
        methods = methods_for_locale(locale)
    else:
        methods = list(PaymentMethod)

    return PaymentMethodsResponse(
        methods=[
            PaymentMethodInfo(
                method=m.value,
                label=label_for(m),
                processor=processor_for(m).value,
                available=m in available,
            )
            for m in methods
        ]
    )


class CountryMethodsResponse(BaseModel):
    countries: dict[str, list[str]]
    locales: dict[str, str]


@app.get("/payment-methods/by-country", response_model=CountryMethodsResponse)
def payment_methods_by_country() -> CountryMethodsResponse:
    """Full country/locale -> method-id matrix. Used by the web + mobile
    UI to render the right method picker per audience without round-
    tripping for every user (the data is small enough to ship once at
    page load)."""
    return CountryMethodsResponse(
        countries={c: [m.value for m in ms] for c, ms in COUNTRY_METHODS.items()},
        locales=dict(LOCALE_DEFAULT_COUNTRY),
    )


@app.post("/checkout", response_model=CheckoutResponse)
def checkout(
    req: CheckoutRequest,
    acct_id: str = Depends(current_account_id),
) -> CheckoutResponse:
    # Bug 2: Validate that the authenticated user owns the customer_id being checked out.
    if req.customer_id != acct_id:
        raise HTTPException(status_code=403, detail="customer_id does not match authenticated user")

    # Bug 1: Return cached session if the same (customer_id, plan) was processed recently.
    cached = _get_cached_checkout(req.customer_id, req.plan.value)
    if cached is not None:
        return cached

    payment = app.state.factory.payment()
    try:
        session = payment.create_checkout(
            customer_id=req.customer_id, plan=req.plan.value, method=req.method
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    resp = CheckoutResponse(
        session_id=session.session_id,
        url=session.url,
        provider=session.provider,
        method=session.method,
        instructions=session.instructions,
    )
    _cache_checkout(req.customer_id, req.plan.value, resp)
    return resp


@app.get("/ads/networks")
def ads_networks() -> dict:
    from aoep_shared.ad_networks import active_network, list_networks

    return {"active": active_network().value, "networks": list_networks()}


@app.get("/ads/slot/{slot_id}")
def ads_slot(slot_id: str, tier: str = "free") -> dict:
    from aoep_shared.ad_networks import resolve_slot

    slot = resolve_slot(slot_id, tier=tier)
    if slot is None:
        return {"slot_id": slot_id, "show": False}
    return {"show": True, **slot}


@app.get("/ads/plan")
def ads_plan(tier: str = "free", duration_min: int = 30) -> dict:
    """Course-agnostic ad-break schedule (tier-gated house inventory).

    Used by surfaces that don't have a catalog course id (e.g. Drive Mode audio
    courses). curriculum's /courses/{id}/ad-breaks is the course-specific path.
    """
    from aoep_shared.ads import AD_FREE_TIERS, ad_plan_for

    breaks = ad_plan_for(tier, duration_min=max(1, duration_min))
    return {
        "tier": tier,
        "ad_free": (tier or "free").lower() in AD_FREE_TIERS,
        "breaks": [b.model_dump(mode="json") for b in breaks],
    }


class AdEventRequest(BaseModel):
    placement: str                      # e.g. "home-banner", "class-preroll"
    network: str = "house"
    fmt: str = "display"                # "display" | "video"
    tier: str = "free"
    unit_id: str = ""
    creative_id: str = ""
    advertiser: str = ""


@app.post("/ads/impression")
def ads_impression(req: AdEventRequest) -> dict:
    """Record an ad impression beacon (web AdSlot / video ad / mobile AdMob).

    Best-effort: browsers/mobile POST this when an ad is actually shown so we can
    estimate revenue (CPM) and the ads funnel. Not the payout of record — real
    money is reported by the ad network's own dashboard.
    """
    ev = app.state.ad_ledger.record_impression(
        req.placement, network=req.network, fmt=req.fmt, tier=req.tier,
        unit_id=req.unit_id, creative_id=req.creative_id, advertiser=req.advertiser,
    )
    return {"ok": True, "revenue_usd": ev.revenue_usd}


@app.post("/ads/click")
def ads_click(req: AdEventRequest) -> dict:
    """Record an ad click beacon (adds estimated CPC revenue)."""
    ev = app.state.ad_ledger.record_click(
        req.placement, network=req.network, fmt=req.fmt, tier=req.tier,
        unit_id=req.unit_id, creative_id=req.creative_id, advertiser=req.advertiser,
    )
    return {"ok": True, "revenue_usd": ev.revenue_usd}


@app.get("/ads/revenue")
def ads_revenue(days: float = 0.0, _: str = Depends(require_admin_secret)) -> dict:
    """Ad-revenue report (impressions, clicks, CTR, estimated revenue + eCPM).

    Read-only aggregate for the admin console (client-gated like telemetry).
    ``days`` optionally limits the recent-event feed to a time window.
    """
    since = days * 86400.0 if days and days > 0 else None
    return {"active_network": _active_ad_network(), **app.state.ad_ledger.summary(since_s=since)}


def _active_ad_network() -> str:
    from aoep_shared.ad_networks import active_network

    return active_network().value
