"""Payment provider implementations.

local  -> a sandbox stub that mints deterministic fake checkout sessions for
          EVERY method so the billing service and UI can be developed and
          tested offline.

cloud  -> a routed real-processor stack:
          - Stripe         : card, Apple/Google/Cash App, ACH, Klarna, BNPL,
                             SEPA, iDEAL, Bancontact, Sofort, Giropay, EPS, P24,
                             Konbini, OXXO, Boleto, Alipay, WeChat Pay, JCB
          - PayPal/Braintree: PayPal + Venmo
          - Square         : Square checkout (US)
          - Razorpay       : UPI, PhonePe, RuPay, etc. (India)
          - Mercado Pago   : PIX (Brazil), Mercado Pago (LATAM)
          - VNPay          : VNPay (Vietnam)
          - MoMo           : MoMo + ZaloPay (Vietnam)
          - ABA / Bakong   : ABA Pay, KHQR, Wing (Cambodia)
          - YooMoney       : Mir + YooMoney (Russia)
          - Toss           : KakaoPay, NaverPay, Toss (Korea)
          - Local PSP      : Mada, STC Pay, Knet, Fawry, Pay-easy, LINE Pay,
                             UnionPay (regional fallbacks)
          - Manual         : Zelle (bank-to-bank, no merchant API)

Each cloud provider raises ``NotImplementedError`` from ``create_checkout``
unless the appropriate API key is configured. The set of methods exposed to
the user comes from the active provider's ``supported_methods()``, so the same
code/UI adapts to whichever processors are turned on -- no code forks.
"""

from __future__ import annotations

import hashlib

from ..config import AppConfig
from ..payments import (
    PaymentMethod,
    Processor,
    all_methods_for_processors,
    processor_for,
)
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
    """Offline payment stub for local mode; simulates every method so the
    full UX (including regional methods like UPI, PIX, KHQR, etc.) is
    testable without any cloud credentials."""

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


class _CloudProviderBase(PaymentProvider):
    """Shared scaffolding for the cloud-mode regional providers.

    Subclasses set ``impl``, ``processors``, ``endpoint``, and the
    ``api_key_attr`` they want to read from ``AppConfig``. Methods are
    derived from the processor list (single source of truth), and
    ``create_checkout`` raises NotImplementedError unless the key is set.
    """

    impl: str = "abstract"
    endpoint: str = ""
    api_key_attr: str = ""
    processors: tuple[Processor, ...] = ()

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mode = "cloud"
        self._api_key = (
            getattr(config, self.api_key_attr, "") if self.api_key_attr else ""
        )

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self.endpoint or f"https://{self.impl}.example",
        )

    def ready(self) -> bool:
        return bool(self._api_key)

    def supported_methods(self) -> frozenset:
        return all_methods_for_processors(self.processors)

    def create_checkout(
        self, *, customer_id: str, plan: str, method=None
    ) -> CheckoutSession:
        m = _coerce_method(method)
        if not self.supports(m):
            raise ValueError(
                f"{m.value} is not handled by {self.impl}; route to the "
                f"{processor_for(m).value} provider instead."
            )
        raise NotImplementedError(
            f"{self.impl} not configured in this environment; set "
            f"{self.api_key_attr.upper()} and PAYMENT_MODE=cloud "
            f"to enable live checkout."
        )


class StripePaymentProvider(_CloudProviderBase):
    """Stripe-backed payments. Stripe natively supports the widest set
    of regional payment methods of any single processor we use, so it's
    our default cloud router for everything that isn't a regional
    PSP-only method (UPI, PIX, MoMo, KHQR, etc.).
    """

    impl = "stripe"
    endpoint = "https://api.stripe.com"
    api_key_attr = "payment_api_key"
    processors = (Processor.STRIPE,)


class PayPalPaymentProvider(_CloudProviderBase):
    """PayPal/Braintree handles PayPal + Venmo on a single account."""

    impl = "paypal"
    endpoint = "https://api-m.paypal.com"
    api_key_attr = "paypal_api_key"
    processors = (Processor.PAYPAL,)


class SquarePaymentProvider(_CloudProviderBase):
    """Square checkout (US-first, also CA/UK/AU/JP/IE/ES/FR)."""

    impl = "square"
    endpoint = "https://connect.squareup.com"
    api_key_attr = "square_api_key"
    processors = (Processor.SQUARE,)


class RazorpayPaymentProvider(_CloudProviderBase):
    """Razorpay aggregator for India: UPI, PhonePe, RuPay, India-issued
    cards, NetBanking, etc."""

    impl = "razorpay"
    endpoint = "https://api.razorpay.com"
    api_key_attr = "razorpay_api_key"
    processors = (Processor.RAZORPAY,)


class PaytmPaymentProvider(_CloudProviderBase):
    """Paytm Payment Gateway (India alternate to Razorpay)."""

    impl = "paytm"
    endpoint = "https://securegw.paytm.in"
    api_key_attr = "paytm_api_key"
    processors = (Processor.PAYTM,)


class MercadoPagoPaymentProvider(_CloudProviderBase):
    """Mercado Pago for LATAM: PIX (Brazil), Boleto, OXXO (Mexico),
    Mercado Pago wallet, regional cards."""

    impl = "mercado_pago"
    endpoint = "https://api.mercadopago.com"
    api_key_attr = "mercado_pago_api_key"
    processors = (Processor.MERCADO_PAGO,)


class VNPayPaymentProvider(_CloudProviderBase):
    """VNPay gateway (Vietnam): VNPay-QR, ATM card, international card."""

    impl = "vnpay"
    endpoint = "https://sandbox.vnpayment.vn"
    api_key_attr = "vnpay_api_key"
    processors = (Processor.VNPAY,)


class MoMoPaymentProvider(_CloudProviderBase):
    """MoMo wallet + ZaloPay (Vietnam)."""

    impl = "momo"
    endpoint = "https://test-payment.momo.vn"
    api_key_attr = "momo_api_key"
    processors = (Processor.MOMO,)


class ABAPaymentProvider(_CloudProviderBase):
    """ABA PayWay / Bakong KHQR (Cambodia) - covers ABA Pay, KHQR, Wing."""

    impl = "aba"
    endpoint = "https://payway.ababank.com"
    api_key_attr = "aba_api_key"
    processors = (Processor.ABA,)


class YooMoneyPaymentProvider(_CloudProviderBase):
    """YooMoney + SBP (Russia): Mir card, YooMoney wallet."""

    impl = "yoomoney"
    endpoint = "https://yoomoney.ru/api"
    api_key_attr = "yoomoney_api_key"
    processors = (Processor.YOOMONEY,)


class TossPaymentProvider(_CloudProviderBase):
    """Toss Payments (Korea) - covers KakaoPay, NaverPay, Toss, KCP."""

    impl = "toss"
    endpoint = "https://api.tosspayments.com"
    api_key_attr = "toss_api_key"
    processors = (Processor.TOSS,)


class LocalPSPPaymentProvider(_CloudProviderBase):
    """Aggregated regional fallback for the methods we don't yet route to
    a dedicated cloud connector: Mada, STC Pay, Knet, Fawry, Pay-easy,
    LINE Pay, UnionPay. The deployment configures whichever local PSP it
    has a direct contract with; the same connector class fronts them.
    """

    impl = "local_psp"
    endpoint = ""
    api_key_attr = "local_psp_api_key"
    processors = (Processor.LOCAL_PSP,)


# A convenience tuple the factory can iterate to build the active set
# of cloud providers (only those with their api_key configured will be
# advertised as "available" in /payment-methods).
ALL_CLOUD_PROVIDERS: tuple[type[_CloudProviderBase], ...] = (
    StripePaymentProvider,
    PayPalPaymentProvider,
    SquarePaymentProvider,
    RazorpayPaymentProvider,
    PaytmPaymentProvider,
    MercadoPagoPaymentProvider,
    VNPayPaymentProvider,
    MoMoPaymentProvider,
    ABAPaymentProvider,
    YooMoneyPaymentProvider,
    TossPaymentProvider,
    LocalPSPPaymentProvider,
)


class RoutedPaymentProvider(PaymentProvider):
    """Cloud-mode router that fans method-specific checkouts out to the
    correct regional processor.

    The router holds an instance of every cloud provider in
    ``ALL_CLOUD_PROVIDERS`` and routes each ``create_checkout`` to the
    one whose ``processors`` includes the method's processor. The set
    of methods advertised in ``supported_methods()`` is the union of
    every CONFIGURED provider's method set (a provider is configured
    when its API key is non-empty). Unconfigured providers stay on the
    list so the platform can return a clear "not configured" error
    instead of routing to a sandbox in production.

    Manual methods (Zelle) are handled inline (instructions only).
    """

    impl = "routed"

    def __init__(self, config: AppConfig) -> None:
        self._config = config
        self._mode = "cloud"
        self._providers: list[_CloudProviderBase] = [
            cls(config) for cls in ALL_CLOUD_PROVIDERS
        ]
        # Index by processor for O(1) routing.
        self._by_processor: dict[Processor, _CloudProviderBase] = {}
        for p in self._providers:
            for proc in p.processors:
                self._by_processor[proc] = p

    def info(self) -> ProviderInfo:
        active = [p.impl for p in self._providers if p.ready()]
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=("routed:" + ",".join(active)) if active
                     else "routed:none-configured",
        )

    def ready(self) -> bool:
        return any(p.ready() for p in self._providers)

    def supported_methods(self) -> frozenset:
        configured: set[PaymentMethod] = set()
        for p in self._providers:
            if p.ready():
                configured |= p.supported_methods()
        # Manual methods (Zelle) work without an API key as long as we
        # surface the bank-transfer instructions.
        configured.add(PaymentMethod.ZELLE)
        return frozenset(configured)

    def create_checkout(
        self, *, customer_id: str, plan: str, method=None
    ) -> CheckoutSession:
        m = _coerce_method(method)
        proc = processor_for(m)
        if proc is Processor.MANUAL:
            digest = hashlib.sha256(
                f"{customer_id}:{plan}:{m.value}".encode()
            ).hexdigest()[:24]
            return CheckoutSession(
                session_id=f"cs_manual_{m.value}_{digest}",
                url="",
                provider="manual",
                method=m.value,
                instructions=_ZELLE_INSTRUCTIONS,
            )
        provider = self._by_processor.get(proc)
        if provider is None:
            raise ValueError(
                f"No cloud provider registered for processor {proc.value}"
            )
        return provider.create_checkout(
            customer_id=customer_id, plan=plan, method=m,
        )
