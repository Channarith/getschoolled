"""Payment methods and their routing to real processors.

The platform offers several consumer payment methods. Most are not separate
integrations: they are payment methods exposed by a processor.

  - card / Apple Pay / Google Pay / Cash App Pay  -> Stripe
  - PayPal / Venmo                                 -> PayPal/Braintree
  - Zelle                                          -> manual bank transfer
    (Zelle has no merchant checkout API; it is bank-to-bank, so we surface
     transfer instructions and reconcile out of band rather than a hosted page)

This module is the single source of truth for which methods exist and which
processor handles each, so the PaymentProvider implementations and the billing
API stay consistent. The local sandbox simulates every method so the product is
fully usable and testable offline; cloud providers advertise only what they can
actually process.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict


class PaymentMethod(str, Enum):
    CARD = "card"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    CASHAPP = "cashapp"
    PAYPAL = "paypal"
    VENMO = "venmo"
    ZELLE = "zelle"


class Processor(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"
    MANUAL = "manual"  # bank transfer (Zelle): instructions + out-of-band recon


# Which processor actually handles each method.
METHOD_PROCESSOR: Dict[PaymentMethod, Processor] = {
    PaymentMethod.CARD: Processor.STRIPE,
    PaymentMethod.APPLE_PAY: Processor.STRIPE,
    PaymentMethod.GOOGLE_PAY: Processor.STRIPE,
    PaymentMethod.CASHAPP: Processor.STRIPE,
    PaymentMethod.PAYPAL: Processor.PAYPAL,
    PaymentMethod.VENMO: Processor.PAYPAL,
    PaymentMethod.ZELLE: Processor.MANUAL,
}

# Human-readable labels for the UI.
METHOD_LABELS: Dict[PaymentMethod, str] = {
    PaymentMethod.CARD: "Credit / Debit Card",
    PaymentMethod.APPLE_PAY: "Apple Pay",
    PaymentMethod.GOOGLE_PAY: "Google Pay",
    PaymentMethod.CASHAPP: "Cash App Pay",
    PaymentMethod.PAYPAL: "PayPal",
    PaymentMethod.VENMO: "Venmo",
    PaymentMethod.ZELLE: "Zelle (bank transfer)",
}


def processor_for(method: PaymentMethod) -> Processor:
    return METHOD_PROCESSOR[method]


def label_for(method: PaymentMethod) -> str:
    return METHOD_LABELS[method]
