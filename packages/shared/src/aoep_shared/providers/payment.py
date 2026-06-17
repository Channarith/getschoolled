"""Payment provider implementations.

cloud  -> real processors: Stripe (card, Apple Pay, Google Pay, Cash App Pay)
          and PayPal/Braintree (PayPal, Venmo). Zelle is a manual bank transfer.
local  -> a sandbox stub that mints deterministic fake sessions for EVERY method
          so the billing service and UI can be developed and tested offline.

The set of methods exposed to the user comes from the active provider's
``supported_methods()``, so the same code/UI adapts to whichever processors are
configured -- no code forks.
"""

from __future__ import annotations

import hashlib

from ..config import AppConfig
from ..payments import PaymentMethod, Processor, processor_for
from .base import CheckoutSession, PaymentProvider, ProviderInfo

_ZELLE_INSTRUCTIONS = (
    "Send your payment via Zelle to billing@aoep.example using your account id "
    "as the memo. Access unlocks once the transfer is confirmed."
)


def _coerce_method(method) -> PaymentMethod:
    if method is None:
        return PaymentMethod.CARD
    if isinstance(method, PaymentMethod):
        return method
    return PaymentMethod(str(method))


class SandboxPaymentProvider(PaymentProvider):
    """Offline payment stub for local mode; simulates every method."""

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

    def supported_methods(self) -> frozenset:
        # The sandbox can simulate them all so the full UX is testable offline.
        return frozenset(PaymentMethod)

    def create_checkout(
        self, *, customer_id: str, plan: str, method=None
    ) -> CheckoutSession:
        m = _coerce_method(method)
        digest = hashlib.sha256(
            f"{customer_id}:{plan}:{m.value}".encode()
        ).hexdigest()[:24]
        session_id = f"cs_sandbox_{m.value}_{digest}"
        if processor_for(m) is Processor.MANUAL:
            return CheckoutSession(
                session_id=session_id,
                url="",
                provider=self.impl,
                method=m.value,
                instructions=_ZELLE_INSTRUCTIONS,
            )
        return CheckoutSession(
            session_id=session_id,
            url=f"sandbox://checkout/{m.value}/{session_id}",
            provider=self.impl,
            method=m.value,
        )


class StripePaymentProvider(PaymentProvider):
    """Stripe-backed payments for cloud mode.

    Stripe natively exposes card plus the Apple Pay / Google Pay wallets and Cash
    App Pay as payment methods on one Checkout/PaymentIntent. PayPal and Venmo go
    through a separate PayPal provider; Zelle is handled manually.
    """

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

    def supported_methods(self) -> frozenset:
        return frozenset(
            {
                PaymentMethod.CARD,
                PaymentMethod.APPLE_PAY,
                PaymentMethod.GOOGLE_PAY,
                PaymentMethod.CASHAPP,
            }
        )

    def create_checkout(
        self, *, customer_id: str, plan: str, method=None
    ) -> CheckoutSession:
        m = _coerce_method(method)
        if not self.supports(m):
            raise ValueError(
                f"{m.value} is not handled by Stripe; route to the "
                f"{processor_for(m).value} provider instead."
            )
        raise NotImplementedError(
            "Stripe not configured in this environment; set PAYMENT_API_KEY and "
            "PAYMENT_MODE=cloud to enable live checkout."
        )
