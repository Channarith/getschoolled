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


def _checkout_amount(plan: str) -> tuple[int, str]:
    """Cents and decimal dollars for a named plan."""
    from ..plan_pricing import price_usd_for_tier

    key = (plan or "").strip().lower()
    if key == "vip":
        key = "premium"
    dollars = price_usd_for_tier(key)
    if dollars <= 0 and key != "free":
        dollars = price_usd_for_tier("basic")
    return int(round(dollars * 100)), f"{dollars:.2f}"


def _public_web() -> str:
    import os

    return (os.environ.get("PUBLIC_WEB_URL") or "https://www.salareen.com").rstrip("/")


def _http_json(url: str, payload, headers: dict) -> dict:
    import json
    import urllib.request

    data = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode() or "{}")


def _hosted_checkout(provider, *, customer_id: str, plan: str, method: PaymentMethod) -> CheckoutSession:
    """Open a hosted checkout at the processor that owns this method."""
    import base64
    import os
    import uuid

    impl = provider.impl
    key = provider._api_key
    cents, dollars = _checkout_amount(plan)
    web = _public_web()
    success = f"{web}/billing?checkout=success"
    cancel = f"{web}/billing?checkout=cancel"
    if impl == "stripe":
        price_env = os.environ.get(f"STRIPE_PRICE_{plan.upper()}", "").strip()
        fields = {
            "mode": "subscription" if price_env else "payment",
            "success_url": success,
            "cancel_url": cancel,
            "client_reference_id": customer_id,
        }
        if price_env:
            fields["line_items[0][price]"] = price_env
            fields["line_items[0][quantity]"] = "1"
        else:
            fields.update({
                "line_items[0][quantity]": "1",
                "line_items[0][price_data][currency]": "usd",
                "line_items[0][price_data][unit_amount]": str(cents),
                "line_items[0][price_data][product_data][name]": plan or "Salareen",
            })
        import urllib.parse
        body = _http_json(
            "https://api.stripe.com/v1/checkout/sessions",
            urllib.parse.urlencode(fields).encode(),
            {
                "Authorization": "Basic " + base64.b64encode(f"{key}:".encode()).decode(),
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )
        return CheckoutSession(
            session_id=str(body.get("id") or ""),
            url=str(body.get("url") or ""),
            provider="stripe",
            method=method.value,
        )
    if impl == "paypal":
        body = _http_json(
            "https://api-m.paypal.com/v2/checkout/orders",
            {
                "intent": "CAPTURE",
                "purchase_units": [{
                    "custom_id": customer_id,
                    "description": plan or "Salareen",
                    "amount": {"currency_code": "USD", "value": dollars},
                }],
                "application_context": {"return_url": success, "cancel_url": cancel},
            },
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        approve = next(
            (link.get("href") for link in body.get("links") or [] if link.get("rel") == "approve"),
            "",
        )
        return CheckoutSession(
            session_id=str(body.get("id") or ""),
            url=str(approve),
            provider="paypal",
            method=method.value,
        )
    if impl == "square":
        body = _http_json(
            "https://connect.squareup.com/v2/online-checkout/payment-links",
            {
                "idempotency_key": uuid.uuid4().hex,
                "quick_pay": {
                    "name": plan or "Salareen",
                    "price_money": {"amount": cents, "currency": "USD"},
                    "location_id": os.environ.get("SQUARE_LOCATION_ID", "main"),
                },
                "checkout_options": {"redirect_url": success},
            },
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        link = body.get("payment_link") or {}
        return CheckoutSession(
            session_id=str(link.get("id") or body.get("id") or ""),
            url=str(link.get("url") or link.get("long_url") or ""),
            provider="square",
            method=method.value,
        )
    if impl == "razorpay":
        key_id, _, secret = key.partition(":")
        token = base64.b64encode(f"{key_id}:{secret or key_id}".encode()).decode()
        body = _http_json(
            "https://api.razorpay.com/v1/payment_links",
            {
                "amount": cents,
                "currency": "USD",
                "description": plan or "Salareen",
                "reference_id": customer_id[:40],
                "callback_url": success,
                "callback_method": "get",
            },
            {
                "Authorization": f"Basic {token}",
                "Content-Type": "application/json",
            },
        )
        return CheckoutSession(
            session_id=str(body.get("id") or ""),
            url=str(body.get("short_url") or ""),
            provider="razorpay",
            method=method.value,
        )
    if impl == "mercado_pago":
        body = _http_json(
            "https://api.mercadopago.com/checkout/preferences",
            {
                "items": [{
                    "title": plan or "Salareen",
                    "quantity": 1,
                    "currency_id": "USD",
                    "unit_price": float(dollars),
                }],
                "external_reference": customer_id,
                "back_urls": {"success": success, "failure": cancel, "pending": success},
            },
            {
                "Authorization": f"Bearer {key}",
                "Content-Type": "application/json",
            },
        )
        return CheckoutSession(
            session_id=str(body.get("id") or ""),
            url=str(body.get("init_point") or ""),
            provider="mercado_pago",
            method=method.value,
        )
    raise NotImplementedError(
        f"{impl} checkout is not available in this environment"
    )


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
        if not self.ready():
            raise NotImplementedError(
                f"{self.impl} not configured in this environment; set "
                f"{self.api_key_attr.upper()} and PAYMENT_MODE=cloud "
                f"to enable live checkout."
            )
        return _hosted_checkout(self, customer_id=customer_id, plan=plan, method=m)


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
