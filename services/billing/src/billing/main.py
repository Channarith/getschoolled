"""Billing FastAPI app.

Exposes the single entitlements gate -- can_start(class_type, language, features)
-- that every other service consults before starting a class, plus checkout
creation via the PaymentProvider (Stripe in cloud, sandbox stub local).
"""

from __future__ import annotations

from aoep_shared.entitlements import PLANS, can_start
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
from fastapi import HTTPException
from pydantic import BaseModel

app = create_service("billing")


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
    return {
        tier.value: {
            "languages": sorted(plan.languages),
            "solo_classes": plan.solo_classes,
            "cross_class_memory": plan.cross_class_memory,
            "recordings": plan.recordings,
            "analytics": plan.analytics,
        }
        for tier, plan in PLANS.items()
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
def checkout(req: CheckoutRequest) -> CheckoutResponse:
    payment = app.state.factory.payment()
    try:
        session = payment.create_checkout(
            customer_id=req.customer_id, plan=req.plan.value, method=req.method
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    except NotImplementedError as exc:
        raise HTTPException(status_code=503, detail=str(exc))
    return CheckoutResponse(
        session_id=session.session_id,
        url=session.url,
        provider=session.provider,
        method=session.method,
        instructions=session.instructions,
    )


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
