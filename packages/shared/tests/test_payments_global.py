"""Global payment coverage: methods, country routing, and the
RoutedPaymentProvider for cloud mode.

The platform supports 27 languages, so the payment surface has to
cover the popular methods in each of those markets. This test pins
the contract so we don't accidentally drop a region or break the
processor mapping.
"""

from __future__ import annotations

import pytest

from aoep_shared.config import load_config
from aoep_shared.factory import build_factory
from aoep_shared.payments import (
    COUNTRY_METHODS,
    LOCALE_DEFAULT_COUNTRY,
    METHOD_PROCESSOR,
    PaymentMethod,
    Processor,
    label_for,
    methods_for_country,
    methods_for_locale,
    processor_for,
)
from aoep_shared.providers.payment import (
    ALL_CLOUD_PROVIDERS,
    RoutedPaymentProvider,
    SandboxPaymentProvider,
)


# --------------------------------------------------------------------------- #
# Method enum + processor mapping
# --------------------------------------------------------------------------- #
def test_every_method_has_a_processor():
    """No payment method may exist without a routing entry; otherwise
    /checkout would 500 silently with a KeyError instead of a clean
    error to the caller."""
    for method in PaymentMethod:
        assert method in METHOD_PROCESSOR, (
            f"PaymentMethod.{method.name} has no entry in METHOD_PROCESSOR"
        )
        assert isinstance(METHOD_PROCESSOR[method], Processor)


def test_every_method_has_a_label():
    """Every method must render with a human label in the UI."""
    for method in PaymentMethod:
        label = label_for(method)
        assert label and isinstance(label, str)


def test_critical_us_methods_present():
    """USA-popular methods explicitly called out by stakeholders:
    Zelle, Venmo, PayPal, Square, Cash App, Apple/Google Pay, ACH,
    plus card and the major BNPL providers."""
    for m in (PaymentMethod.ZELLE, PaymentMethod.VENMO, PaymentMethod.PAYPAL,
              PaymentMethod.SQUARE, PaymentMethod.CASHAPP,
              PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
              PaymentMethod.ACH, PaymentMethod.CARD,
              PaymentMethod.KLARNA, PaymentMethod.AFTERPAY,
              PaymentMethod.AFFIRM):
        assert m in PaymentMethod, f"{m} missing from PaymentMethod enum"


def test_regional_methods_present():
    """Regional methods for the non-English markets we localise into."""
    expected = {
        # Europe
        "DE": (PaymentMethod.SEPA, PaymentMethod.GIROPAY, PaymentMethod.SOFORT,
               PaymentMethod.KLARNA),
        "NL": (PaymentMethod.IDEAL,),
        "BE": (PaymentMethod.BANCONTACT,),
        "AT": (PaymentMethod.EPS,),
        "PL": (PaymentMethod.P24,),
        # LATAM
        "BR": (PaymentMethod.PIX, PaymentMethod.BOLETO,
               PaymentMethod.MERCADO_PAGO),
        "MX": (PaymentMethod.OXXO, PaymentMethod.MERCADO_PAGO),
        # India
        "IN": (PaymentMethod.UPI, PaymentMethod.PAYTM, PaymentMethod.PHONEPE,
               PaymentMethod.RAZORPAY, PaymentMethod.RUPAY),
        # China
        "CN": (PaymentMethod.ALIPAY, PaymentMethod.WECHAT_PAY,
               PaymentMethod.UNIONPAY),
        # Japan
        "JP": (PaymentMethod.JCB, PaymentMethod.KONBINI,
               PaymentMethod.PAYEASY, PaymentMethod.LINE_PAY),
        # Korea
        "KR": (PaymentMethod.KAKAO_PAY, PaymentMethod.NAVER_PAY,
               PaymentMethod.TOSS),
        # Vietnam
        "VN": (PaymentMethod.VNPAY, PaymentMethod.MOMO,
               PaymentMethod.ZALO_PAY),
        # Cambodia
        "KH": (PaymentMethod.ABA_PAY, PaymentMethod.WING, PaymentMethod.KHQR),
        # Russia
        "RU": (PaymentMethod.MIR, PaymentMethod.YOOMONEY),
        # MENA
        "SA": (PaymentMethod.MADA, PaymentMethod.STC_PAY),
        "KW": (PaymentMethod.KNET,),
        "EG": (PaymentMethod.FAWRY,),
    }
    for country, methods in expected.items():
        country_set = set(methods_for_country(country))
        for m in methods:
            assert m in country_set, (
                f"{country}'s recommended methods should include "
                f"{m.value}; got {[x.value for x in country_set]}"
            )


# --------------------------------------------------------------------------- #
# Country / locale routing
# --------------------------------------------------------------------------- #
@pytest.mark.parametrize("country,first", [
    ("US", PaymentMethod.CARD),
    ("DE", PaymentMethod.CARD),
    ("BR", PaymentMethod.PIX),     # Brazil leads with PIX
    ("IN", PaymentMethod.UPI),     # India leads with UPI
    ("CN", PaymentMethod.ALIPAY),  # China leads with Alipay
    ("VN", PaymentMethod.CARD),
    ("KH", PaymentMethod.CARD),
])
def test_country_routing_orders_methods_correctly(country, first):
    methods = methods_for_country(country)
    assert methods[0] is first, (
        f"{country} should lead with {first.value}, got {methods[0].value}"
    )


def test_unknown_country_falls_back_to_universal_set():
    methods = methods_for_country("XX")
    assert PaymentMethod.CARD in methods
    assert PaymentMethod.PAYPAL in methods


def test_none_country_returns_universal_set():
    methods = methods_for_country(None)
    assert PaymentMethod.CARD in methods


def test_locale_routing_uses_default_country():
    # vi -> VN -> includes VNPay, MoMo, ZaloPay
    methods = methods_for_locale("vi")
    assert PaymentMethod.VNPAY in methods
    assert PaymentMethod.MOMO in methods
    # km -> KH -> includes ABA, KHQR
    methods = methods_for_locale("km")
    assert PaymentMethod.ABA_PAY in methods
    assert PaymentMethod.KHQR in methods
    # hi -> IN -> includes UPI
    assert PaymentMethod.UPI in methods_for_locale("hi")
    # zh -> CN -> includes Alipay + WeChat
    methods = methods_for_locale("zh")
    assert PaymentMethod.ALIPAY in methods
    assert PaymentMethod.WECHAT_PAY in methods


def test_every_localised_locale_has_a_country_default():
    """Every locale we ship must have a default country mapping so the
    UI knows which method picker to render even without an explicit
    country signal."""
    # The 14 user-facing locales the platform localises into.
    user_locales = {
        "en", "es", "fr", "de", "it", "pt", "ru", "ar",
        "hi", "zh", "ja", "ko", "vi", "km",
    }
    for loc in user_locales:
        assert loc in LOCALE_DEFAULT_COUNTRY, (
            f"locale {loc} has no LOCALE_DEFAULT_COUNTRY entry"
        )
        country = LOCALE_DEFAULT_COUNTRY[loc]
        assert country in COUNTRY_METHODS, (
            f"locale {loc} maps to country {country} which has no "
            f"COUNTRY_METHODS entry"
        )


# --------------------------------------------------------------------------- #
# Sandbox provider (local mode)
# --------------------------------------------------------------------------- #
def test_sandbox_supports_every_method():
    cfg = load_config(env={})
    sandbox = SandboxPaymentProvider(cfg)
    supported = sandbox.supported_methods()
    for m in PaymentMethod:
        assert m in supported, f"sandbox should support {m.value}"


def test_sandbox_creates_session_for_every_method():
    cfg = load_config(env={})
    sandbox = SandboxPaymentProvider(cfg)
    for m in PaymentMethod:
        s = sandbox.create_checkout(customer_id="cu_test", plan="pro", method=m)
        assert s.method == m.value
        # Manual methods (Zelle) get instructions only, no URL.
        if processor_for(m) is Processor.MANUAL:
            assert s.instructions
        else:
            assert s.url


# --------------------------------------------------------------------------- #
# Routed cloud provider
# --------------------------------------------------------------------------- #
def test_routed_provider_advertises_no_methods_when_no_keys_set():
    """In cloud mode without ANY API keys configured, only manual
    methods (Zelle) should be advertised - the rest are NotImplemented
    until the keys land. This is the fail-closed posture we want for
    fresh production deployments."""
    cfg = load_config(env={"DEPLOY_MODE": "cloud"})
    routed = RoutedPaymentProvider(cfg)
    methods = routed.supported_methods()
    # Zelle is always supported because it's manual instructions, not API.
    assert PaymentMethod.ZELLE in methods
    # No other method should be advertised yet.
    assert PaymentMethod.CARD not in methods
    assert PaymentMethod.UPI not in methods


def test_routed_provider_lights_up_methods_per_configured_processor():
    """When a processor's API key is set, all of its native methods
    become available via the routed provider."""
    cfg = load_config(env={
        "DEPLOY_MODE": "cloud",
        "PAYMENT_API_KEY": "sk_test_stripe",      # Stripe -> CARD, etc.
        "RAZORPAY_API_KEY": "rzp_test",           # India  -> UPI, etc.
        "MOMO_API_KEY": "momo_test",              # Vietnam wallet
        "ABA_API_KEY": "aba_test",                # Cambodia
    })
    routed = RoutedPaymentProvider(cfg)
    methods = routed.supported_methods()
    # Stripe-native methods should now be live.
    for m in (PaymentMethod.CARD, PaymentMethod.APPLE_PAY,
              PaymentMethod.GOOGLE_PAY, PaymentMethod.KLARNA,
              PaymentMethod.IDEAL, PaymentMethod.BANCONTACT,
              PaymentMethod.SEPA, PaymentMethod.ALIPAY,
              PaymentMethod.WECHAT_PAY):
        assert m in methods, f"Stripe should make {m.value} available"
    # Razorpay
    for m in (PaymentMethod.UPI, PaymentMethod.PHONEPE, PaymentMethod.RUPAY):
        assert m in methods, f"Razorpay should make {m.value} available"
    # MoMo
    for m in (PaymentMethod.MOMO, PaymentMethod.ZALO_PAY):
        assert m in methods, f"MoMo should make {m.value} available"
    # ABA
    for m in (PaymentMethod.ABA_PAY, PaymentMethod.KHQR, PaymentMethod.WING):
        assert m in methods, f"ABA should make {m.value} available"
    # PayPal not configured -> not in set.
    assert PaymentMethod.PAYPAL not in methods
    assert PaymentMethod.VENMO not in methods


def test_routed_provider_zelle_returns_instructions_with_no_keys(monkeypatch):
    cfg = load_config(env={"DEPLOY_MODE": "cloud"})
    routed = RoutedPaymentProvider(cfg)
    s = routed.create_checkout(customer_id="cu_x", plan="pro",
                                method=PaymentMethod.ZELLE)
    assert s.method == "zelle"
    assert s.url == ""
    assert "Zelle" in s.instructions


def test_routed_provider_unconfigured_method_raises_not_implemented():
    cfg = load_config(env={"DEPLOY_MODE": "cloud"})
    routed = RoutedPaymentProvider(cfg)
    with pytest.raises(NotImplementedError):
        routed.create_checkout(customer_id="cu_x", plan="pro",
                                method=PaymentMethod.CARD)


def test_routed_provider_routes_to_correct_processor():
    """Each method must reach its owning processor's class instance,
    not just any cloud provider that happens to be configured. Test by
    asking for a Razorpay method when only Razorpay has a key set."""
    cfg = load_config(env={
        "DEPLOY_MODE": "cloud",
        "RAZORPAY_API_KEY": "rzp_test",
    })
    routed = RoutedPaymentProvider(cfg)
    # Razorpay is configured -> UPI request reaches Razorpay's
    # NotImplementedError saying "razorpay not configured" would be
    # WRONG; instead we want Razorpay's create_checkout to be called.
    # The stub raises NotImplementedError mentioning 'razorpay'.
    with pytest.raises(NotImplementedError) as exc:
        routed.create_checkout(customer_id="cu_x", plan="pro",
                                method=PaymentMethod.UPI)
    # Stub message includes the impl name, confirming routing.
    assert "razorpay" in str(exc.value).lower()


def test_factory_uses_routed_in_cloud_and_sandbox_in_local():
    """Cloud mode -> routed; local mode -> sandbox."""
    cloud = build_factory(load_config(env={"DEPLOY_MODE": "cloud"}))
    assert isinstance(cloud.payment(), RoutedPaymentProvider)

    local = build_factory(load_config(env={"DEPLOY_MODE": "local"}))
    assert isinstance(local.payment(), SandboxPaymentProvider)


def test_all_cloud_providers_have_unique_processors():
    """Two cloud provider classes must not claim the same processor;
    that would make routing ambiguous."""
    seen: dict = {}
    for cls in ALL_CLOUD_PROVIDERS:
        for proc in cls.processors:
            assert proc not in seen, (
                f"processor {proc.value} claimed by both "
                f"{seen[proc].__name__} and {cls.__name__}"
            )
            seen[proc] = cls
