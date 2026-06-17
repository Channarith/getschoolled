"""Unit tests for payment methods and provider routing (no network)."""

import pytest

from aoep_shared.config import load_config
from aoep_shared.payments import (
    METHOD_PROCESSOR,
    PaymentMethod,
    Processor,
    label_for,
    processor_for,
)
from aoep_shared.providers.payment import (
    SandboxPaymentProvider,
    StripePaymentProvider,
)


def test_all_methods_have_processor_and_label():
    for m in PaymentMethod:
        assert m in METHOD_PROCESSOR
        assert label_for(m)


def test_method_processor_routing():
    assert processor_for(PaymentMethod.APPLE_PAY) is Processor.STRIPE
    assert processor_for(PaymentMethod.GOOGLE_PAY) is Processor.STRIPE
    assert processor_for(PaymentMethod.CASHAPP) is Processor.STRIPE
    assert processor_for(PaymentMethod.VENMO) is Processor.PAYPAL
    assert processor_for(PaymentMethod.PAYPAL) is Processor.PAYPAL
    assert processor_for(PaymentMethod.ZELLE) is Processor.MANUAL


def test_sandbox_supports_every_method():
    p = SandboxPaymentProvider(load_config())
    assert p.supported_methods() == frozenset(PaymentMethod)


@pytest.mark.parametrize("method", list(PaymentMethod))
def test_sandbox_checkout_each_method(method):
    p = SandboxPaymentProvider(load_config())
    session = p.create_checkout(customer_id="c1", plan="pro", method=method)
    assert session.method == method.value
    assert session.provider == "sandbox"
    if method is PaymentMethod.ZELLE:
        assert session.url == "" and session.instructions  # manual transfer
    else:
        assert session.url and method.value in session.url


def test_stripe_supports_wallets_and_cashapp_not_venmo_zelle():
    p = StripePaymentProvider(load_config())
    supported = p.supported_methods()
    assert {
        PaymentMethod.CARD,
        PaymentMethod.APPLE_PAY,
        PaymentMethod.GOOGLE_PAY,
        PaymentMethod.CASHAPP,
    } <= supported
    assert PaymentMethod.VENMO not in supported
    assert PaymentMethod.ZELLE not in supported


def test_stripe_rejects_unsupported_method_with_value_error():
    p = StripePaymentProvider(load_config())
    with pytest.raises(ValueError):
        p.create_checkout(customer_id="c1", plan="pro", method=PaymentMethod.VENMO)


def test_default_method_is_card():
    p = SandboxPaymentProvider(load_config())
    session = p.create_checkout(customer_id="c1", plan="pro")
    assert session.method == "card"
