"""Billing / entitlements service.

Phase6b owns plans, subscriptions, credits, metered usage, and the single
entitlements API ``canStart(classType, language, features)``. PaymentProvider is
Stripe in cloud, sandbox stub locally. This skeleton exposes /health and the
entitlements check routed through the configured provider.
"""

from __future__ import annotations

from pydantic import BaseModel

from eduplatform_shared.factory import get_provider_factory
from eduplatform_shared.schemas import Entitlement
from eduplatform_shared.service import create_service_app

app = create_service_app("billing")


class CanStartRequest(BaseModel):
    account_id: str = "demo"
    class_type: str = "group"
    language: str = "en"
    features: list[str] = []


@app.post("/api/entitlements/can-start", response_model=Entitlement)
def can_start(req: CanStartRequest) -> Entitlement:
    provider = get_provider_factory().payment()
    allowed = provider.can_start(req.class_type, req.language, req.features)
    return Entitlement(
        allowed=allowed,
        reason="" if allowed else "upgrade required",
        plan="sandbox",
    )
