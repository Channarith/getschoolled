"""Billing FastAPI app.

Exposes the single entitlements gate -- can_start(class_type, language, features)
-- that every other service consults before starting a class, plus checkout
creation via the PaymentProvider (Stripe in cloud, sandbox stub local).
"""

from __future__ import annotations

from aoep_shared.entitlements import PLANS, can_start
from aoep_shared.schemas import ClassType, PlanTier
from aoep_shared.service import create_service
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


class CheckoutResponse(BaseModel):
    session_id: str
    url: str
    provider: str


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


@app.post("/checkout", response_model=CheckoutResponse)
def checkout(req: CheckoutRequest) -> CheckoutResponse:
    payment = app.state.factory.payment()
    session = payment.create_checkout(customer_id=req.customer_id, plan=req.plan.value)
    return CheckoutResponse(
        session_id=session.session_id, url=session.url, provider=session.provider
    )
