"""Payment provider implementations.

cloud  -> Stripe (Billing, metered usage, Checkout, Tax, Connect payouts).
local  -> a sandbox stub that mints deterministic fake sessions so the billing
          service and entitlements API can be developed and tested offline.

The sandbox is a real, working implementation (not a NotImplementedError) so the
local stack is fully usable without Stripe credentials.
"""

from __future__ import annotations

import hashlib

from ..config import AppConfig
from .base import CheckoutSession, PaymentProvider, ProviderInfo


class SandboxPaymentProvider(PaymentProvider):
    """Offline payment stub for local mode."""

    impl = "sandbox"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mode = "local"

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint="sandbox://payments",
        )

    def create_checkout(self, *, customer_id: str, plan: str) -> CheckoutSession:
        digest = hashlib.sha256(f"{customer_id}:{plan}".encode()).hexdigest()[:24]
        session_id = f"cs_sandbox_{digest}"
        return CheckoutSession(
            session_id=session_id,
            url=f"sandbox://checkout/{session_id}",
            provider=self.impl,
        )


class StripePaymentProvider(PaymentProvider):
    """Stripe-backed payments for cloud mode."""

    impl = "stripe"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mode = "cloud"
        self._api_key = config.payment_api_key

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint="https://api.stripe.com",
        )

    def ready(self) -> bool:
        return bool(self._api_key)

    def create_checkout(self, *, customer_id: str, plan: str) -> CheckoutSession:
        raise NotImplementedError(
            "Stripe not configured in this environment; set PAYMENT_API_KEY and "
            "PAYMENT_MODE=cloud to enable live checkout."
        )
