"""Payment methods and their routing to real processors.

The platform offers 40+ consumer payment methods spanning the regions of
the 27 languages we support. Most are not separate integrations: they are
payment methods exposed by a regional processor.

  - card / Apple Pay / Google Pay / Cash App / ACH / Klarna / SEPA /
    iDEAL / Bancontact / Sofort / Giropay / EPS / P24 / Konbini /
    OXXO / Boleto / Alipay / WeChat Pay / JCB                  -> Stripe
  - PayPal / Venmo                                              -> PayPal/Braintree
  - Square checkout (US)                                        -> Square
  - UPI / Paytm / PhonePe / RuPay (India)                       -> Razorpay
  - PIX / Mercado Pago (Brazil + LATAM)                         -> Mercado Pago
  - VNPay / ATM cards (Vietnam)                                 -> VNPay
  - MoMo / ZaloPay (Vietnam wallets)                            -> MoMo
  - ABA Pay / KHQR / Wing (Cambodia)                            -> ABA / Bakong
  - Mir / YooMoney (Russia)                                     -> YooMoney
  - KakaoPay / NaverPay / Toss (Korea)                          -> Toss
  - Mada / STC Pay / Knet / Fawry (MENA)                        -> Stripe (Mada via Stripe MENA)
                                                                   or local PSP fallback
  - Zelle (US bank-to-bank, no merchant API)                    -> manual transfer

This module is the single source of truth for which methods exist, which
processor handles each, and which methods are commonly offered in each
country. The PaymentProvider implementations and the billing API stay
consistent. The local sandbox simulates every method so the product is
fully usable and testable offline; cloud providers advertise only what
they can actually process.
"""

from __future__ import annotations

from enum import Enum
from typing import Dict, FrozenSet, Iterable


class PaymentMethod(str, Enum):
    # ---- Global / US-centric (Stripe + PayPal/Braintree + Square + manual)
    CARD = "card"
    APPLE_PAY = "apple_pay"
    GOOGLE_PAY = "google_pay"
    CASHAPP = "cashapp"
    PAYPAL = "paypal"
    VENMO = "venmo"
    ZELLE = "zelle"
    SQUARE = "square"
    ACH = "ach"

    # ---- Buy-Now-Pay-Later (multi-region)
    KLARNA = "klarna"
    AFTERPAY = "afterpay"
    AFFIRM = "affirm"

    # ---- Europe / SEPA bank rails
    SEPA = "sepa"
    IDEAL = "ideal"            # Netherlands
    BANCONTACT = "bancontact"  # Belgium
    SOFORT = "sofort"          # Germany / Austria
    GIROPAY = "giropay"        # Germany
    EPS = "eps"                # Austria
    P24 = "p24"                # Poland (Przelewy24)

    # ---- Latin America
    PIX = "pix"                # Brazil instant
    BOLETO = "boleto"          # Brazil voucher
    OXXO = "oxxo"              # Mexico cash voucher
    MERCADO_PAGO = "mercado_pago"

    # ---- Russia / CIS
    MIR = "mir"
    YOOMONEY = "yoomoney"

    # ---- MENA (Arabic-speaking markets)
    MADA = "mada"              # Saudi Arabia debit
    STC_PAY = "stc_pay"        # Saudi mobile wallet
    KNET = "knet"              # Kuwait
    FAWRY = "fawry"            # Egypt

    # ---- South Asia (India + neighbours)
    UPI = "upi"
    PAYTM = "paytm"
    PHONEPE = "phonepe"
    RAZORPAY = "razorpay"
    RUPAY = "rupay"

    # ---- China / Greater China
    ALIPAY = "alipay"
    WECHAT_PAY = "wechat_pay"
    UNIONPAY = "unionpay"

    # ---- Japan
    JCB = "jcb"
    KONBINI = "konbini"
    PAYEASY = "payeasy"
    LINE_PAY = "line_pay"

    # ---- Korea
    KAKAO_PAY = "kakao_pay"
    NAVER_PAY = "naver_pay"
    TOSS = "toss"

    # ---- Vietnam
    VNPAY = "vnpay"
    MOMO = "momo"
    ZALO_PAY = "zalo_pay"

    # ---- Cambodia
    ABA_PAY = "aba_pay"        # ABA Bank push notification
    WING = "wing"              # Wing money transfer
    KHQR = "khqr"              # Bakong KHQR national QR


class Processor(str, Enum):
    STRIPE = "stripe"
    PAYPAL = "paypal"          # PayPal + Venmo via PayPal/Braintree
    SQUARE = "square"          # Square checkout (US)
    RAZORPAY = "razorpay"      # India: UPI, Paytm, PhonePe, RuPay
    MERCADO_PAGO = "mercado_pago"  # LATAM: PIX, Boleto, OXXO, regional cards
    VNPAY = "vnpay"            # Vietnam gateway (cards + bank ATM)
    MOMO = "momo"              # Vietnam wallet (MoMo + ZaloPay siblings)
    ABA = "aba"                # Cambodia / Bakong KHQR
    YOOMONEY = "yoomoney"      # Russia (Mir + YooMoney)
    TOSS = "toss"              # Korea (KakaoPay, NaverPay, Toss, KCP)
    PAYTM = "paytm"            # India alternate (legacy bank wallet)
    LOCAL_PSP = "local_psp"    # MENA / regional fallback (Mada, Knet, Fawry)
    MANUAL = "manual"          # bank transfer (Zelle, ACH bank): instructions only


# Which processor actually handles each method.
METHOD_PROCESSOR: Dict[PaymentMethod, Processor] = {
    # Stripe (global; covers a huge slice of methods natively)
    PaymentMethod.CARD:        Processor.STRIPE,
    PaymentMethod.APPLE_PAY:   Processor.STRIPE,
    PaymentMethod.GOOGLE_PAY:  Processor.STRIPE,
    PaymentMethod.CASHAPP:     Processor.STRIPE,
    PaymentMethod.ACH:         Processor.STRIPE,
    PaymentMethod.KLARNA:      Processor.STRIPE,
    PaymentMethod.AFTERPAY:    Processor.STRIPE,
    PaymentMethod.AFFIRM:      Processor.STRIPE,
    PaymentMethod.SEPA:        Processor.STRIPE,
    PaymentMethod.IDEAL:       Processor.STRIPE,
    PaymentMethod.BANCONTACT:  Processor.STRIPE,
    PaymentMethod.SOFORT:      Processor.STRIPE,
    PaymentMethod.GIROPAY:     Processor.STRIPE,
    PaymentMethod.EPS:         Processor.STRIPE,
    PaymentMethod.P24:         Processor.STRIPE,
    PaymentMethod.BOLETO:      Processor.STRIPE,
    PaymentMethod.OXXO:        Processor.STRIPE,
    PaymentMethod.ALIPAY:      Processor.STRIPE,
    PaymentMethod.WECHAT_PAY:  Processor.STRIPE,
    PaymentMethod.JCB:         Processor.STRIPE,
    PaymentMethod.KONBINI:     Processor.STRIPE,

    # PayPal / Braintree
    PaymentMethod.PAYPAL: Processor.PAYPAL,
    PaymentMethod.VENMO:  Processor.PAYPAL,

    # Square
    PaymentMethod.SQUARE: Processor.SQUARE,

    # Razorpay (India)
    PaymentMethod.UPI:      Processor.RAZORPAY,
    PaymentMethod.PHONEPE:  Processor.RAZORPAY,
    PaymentMethod.RUPAY:    Processor.RAZORPAY,
    PaymentMethod.RAZORPAY: Processor.RAZORPAY,
    PaymentMethod.PAYTM:    Processor.PAYTM,

    # Mercado Pago (LATAM)
    PaymentMethod.PIX:          Processor.MERCADO_PAGO,
    PaymentMethod.MERCADO_PAGO: Processor.MERCADO_PAGO,

    # Vietnam
    PaymentMethod.VNPAY:    Processor.VNPAY,
    PaymentMethod.MOMO:     Processor.MOMO,
    PaymentMethod.ZALO_PAY: Processor.MOMO,

    # Cambodia
    PaymentMethod.ABA_PAY: Processor.ABA,
    PaymentMethod.KHQR:    Processor.ABA,
    PaymentMethod.WING:    Processor.ABA,

    # Russia
    PaymentMethod.MIR:      Processor.YOOMONEY,
    PaymentMethod.YOOMONEY: Processor.YOOMONEY,

    # China extras (Stripe routes Alipay/WeChat above; UnionPay routed here)
    PaymentMethod.UNIONPAY: Processor.LOCAL_PSP,

    # Korea
    PaymentMethod.KAKAO_PAY: Processor.TOSS,
    PaymentMethod.NAVER_PAY: Processor.TOSS,
    PaymentMethod.TOSS:      Processor.TOSS,
    PaymentMethod.LINE_PAY:  Processor.LOCAL_PSP,
    PaymentMethod.PAYEASY:   Processor.LOCAL_PSP,

    # MENA
    PaymentMethod.MADA:    Processor.LOCAL_PSP,
    PaymentMethod.STC_PAY: Processor.LOCAL_PSP,
    PaymentMethod.KNET:    Processor.LOCAL_PSP,
    PaymentMethod.FAWRY:   Processor.LOCAL_PSP,

    # Manual (bank-to-bank; surface instructions only)
    PaymentMethod.ZELLE: Processor.MANUAL,
}


# Human-readable labels for the UI.
METHOD_LABELS: Dict[PaymentMethod, str] = {
    # Global / US
    PaymentMethod.CARD:       "Credit / Debit Card",
    PaymentMethod.APPLE_PAY:  "Apple Pay",
    PaymentMethod.GOOGLE_PAY: "Google Pay",
    PaymentMethod.CASHAPP:    "Cash App Pay",
    PaymentMethod.PAYPAL:     "PayPal",
    PaymentMethod.VENMO:      "Venmo",
    PaymentMethod.ZELLE:      "Zelle (bank transfer)",
    PaymentMethod.SQUARE:     "Square",
    PaymentMethod.ACH:        "Bank transfer (ACH)",
    # BNPL
    PaymentMethod.KLARNA:   "Klarna",
    PaymentMethod.AFTERPAY: "Afterpay",
    PaymentMethod.AFFIRM:   "Affirm",
    # Europe
    PaymentMethod.SEPA:       "SEPA Direct Debit",
    PaymentMethod.IDEAL:      "iDEAL (Netherlands)",
    PaymentMethod.BANCONTACT: "Bancontact (Belgium)",
    PaymentMethod.SOFORT:     "SOFORT",
    PaymentMethod.GIROPAY:    "Giropay (Germany)",
    PaymentMethod.EPS:        "EPS (Austria)",
    PaymentMethod.P24:        "Przelewy24 (Poland)",
    # LATAM
    PaymentMethod.PIX:          "PIX (Brazil)",
    PaymentMethod.BOLETO:       "Boleto (Brazil)",
    PaymentMethod.OXXO:         "OXXO (Mexico)",
    PaymentMethod.MERCADO_PAGO: "Mercado Pago",
    # Russia
    PaymentMethod.MIR:      "Mir card",
    PaymentMethod.YOOMONEY: "YooMoney",
    # MENA
    PaymentMethod.MADA:    "Mada (Saudi Arabia)",
    PaymentMethod.STC_PAY: "STC Pay",
    PaymentMethod.KNET:    "Knet (Kuwait)",
    PaymentMethod.FAWRY:   "Fawry (Egypt)",
    # India
    PaymentMethod.UPI:      "UPI",
    PaymentMethod.PAYTM:    "Paytm",
    PaymentMethod.PHONEPE:  "PhonePe",
    PaymentMethod.RAZORPAY: "Razorpay",
    PaymentMethod.RUPAY:    "RuPay card",
    # China
    PaymentMethod.ALIPAY:     "Alipay",
    PaymentMethod.WECHAT_PAY: "WeChat Pay",
    PaymentMethod.UNIONPAY:   "UnionPay",
    # Japan
    PaymentMethod.JCB:      "JCB card",
    PaymentMethod.KONBINI:  "Konbini (convenience store)",
    PaymentMethod.PAYEASY:  "Pay-easy",
    PaymentMethod.LINE_PAY: "LINE Pay",
    # Korea
    PaymentMethod.KAKAO_PAY: "KakaoPay",
    PaymentMethod.NAVER_PAY: "NaverPay",
    PaymentMethod.TOSS:      "Toss",
    # Vietnam
    PaymentMethod.VNPAY:    "VNPay",
    PaymentMethod.MOMO:     "MoMo",
    PaymentMethod.ZALO_PAY: "ZaloPay",
    # Cambodia
    PaymentMethod.ABA_PAY: "ABA Pay",
    PaymentMethod.WING:    "Wing",
    PaymentMethod.KHQR:    "KHQR (Bakong)",
}


# Country (ISO-3166-1 alpha-2) -> ordered list of recommended methods.
# Order matters: the UI shows the most popular first. Card is always
# kept toward the top because it's the universal fallback. The set is
# what we actively surface in checkout; the underlying processor may or
# may not be configured for a given deployment, in which case unsupported
# methods are filtered out by the active provider's supported_methods().
COUNTRY_METHODS: Dict[str, list[PaymentMethod]] = {
    # ---- North America
    "US": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.CASHAPP, PaymentMethod.PAYPAL, PaymentMethod.VENMO,
           PaymentMethod.SQUARE, PaymentMethod.ZELLE, PaymentMethod.ACH,
           PaymentMethod.KLARNA, PaymentMethod.AFTERPAY, PaymentMethod.AFFIRM],
    "CA": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.PAYPAL, PaymentMethod.KLARNA, PaymentMethod.AFTERPAY],
    # ---- Europe (SEPA + local rails)
    "GB": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.PAYPAL, PaymentMethod.KLARNA, PaymentMethod.AFTERPAY],
    "DE": [PaymentMethod.CARD, PaymentMethod.SEPA, PaymentMethod.KLARNA,
           PaymentMethod.SOFORT, PaymentMethod.GIROPAY, PaymentMethod.PAYPAL,
           PaymentMethod.GOOGLE_PAY, PaymentMethod.APPLE_PAY],
    "FR": [PaymentMethod.CARD, PaymentMethod.SEPA, PaymentMethod.KLARNA,
           PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "IT": [PaymentMethod.CARD, PaymentMethod.SEPA, PaymentMethod.KLARNA,
           PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "ES": [PaymentMethod.CARD, PaymentMethod.SEPA, PaymentMethod.KLARNA,
           PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "PT": [PaymentMethod.CARD, PaymentMethod.SEPA, PaymentMethod.KLARNA,
           PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "NL": [PaymentMethod.CARD, PaymentMethod.IDEAL, PaymentMethod.SEPA,
           PaymentMethod.KLARNA, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY],
    "BE": [PaymentMethod.CARD, PaymentMethod.BANCONTACT, PaymentMethod.SEPA,
           PaymentMethod.KLARNA, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY],
    "AT": [PaymentMethod.CARD, PaymentMethod.EPS, PaymentMethod.SEPA,
           PaymentMethod.KLARNA, PaymentMethod.SOFORT, PaymentMethod.APPLE_PAY],
    "PL": [PaymentMethod.CARD, PaymentMethod.P24, PaymentMethod.SEPA,
           PaymentMethod.KLARNA, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY],
    # ---- Russia
    "RU": [PaymentMethod.CARD, PaymentMethod.MIR, PaymentMethod.YOOMONEY],
    # ---- MENA (Arabic-speaking)
    "SA": [PaymentMethod.CARD, PaymentMethod.MADA, PaymentMethod.STC_PAY,
           PaymentMethod.APPLE_PAY],
    "AE": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.PAYPAL],
    "EG": [PaymentMethod.CARD, PaymentMethod.FAWRY, PaymentMethod.APPLE_PAY],
    "KW": [PaymentMethod.CARD, PaymentMethod.KNET, PaymentMethod.APPLE_PAY],
    "QA": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "JO": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "MA": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY],
    # ---- South Asia
    "IN": [PaymentMethod.UPI, PaymentMethod.CARD, PaymentMethod.PAYTM,
           PaymentMethod.PHONEPE, PaymentMethod.RAZORPAY, PaymentMethod.RUPAY,
           PaymentMethod.GOOGLE_PAY, PaymentMethod.APPLE_PAY],
    # ---- China + Greater China
    "CN": [PaymentMethod.ALIPAY, PaymentMethod.WECHAT_PAY, PaymentMethod.UNIONPAY,
           PaymentMethod.CARD],
    "HK": [PaymentMethod.CARD, PaymentMethod.ALIPAY, PaymentMethod.WECHAT_PAY,
           PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "TW": [PaymentMethod.CARD, PaymentMethod.JCB, PaymentMethod.LINE_PAY,
           PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    # ---- Japan
    "JP": [PaymentMethod.CARD, PaymentMethod.JCB, PaymentMethod.KONBINI,
           PaymentMethod.PAYEASY, PaymentMethod.LINE_PAY,
           PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY, PaymentMethod.PAYPAL],
    # ---- Korea
    "KR": [PaymentMethod.CARD, PaymentMethod.KAKAO_PAY, PaymentMethod.NAVER_PAY,
           PaymentMethod.TOSS, PaymentMethod.APPLE_PAY],
    # ---- Southeast Asia
    "VN": [PaymentMethod.CARD, PaymentMethod.VNPAY, PaymentMethod.MOMO,
           PaymentMethod.ZALO_PAY, PaymentMethod.APPLE_PAY],
    "KH": [PaymentMethod.CARD, PaymentMethod.ABA_PAY, PaymentMethod.WING,
           PaymentMethod.KHQR, PaymentMethod.APPLE_PAY],
    "TH": [PaymentMethod.CARD, PaymentMethod.KLARNA, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY, PaymentMethod.PAYPAL],
    "ID": [PaymentMethod.CARD, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "PH": [PaymentMethod.CARD, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "MY": [PaymentMethod.CARD, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "SG": [PaymentMethod.CARD, PaymentMethod.PAYPAL, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY, PaymentMethod.KLARNA],
    # ---- LATAM
    "BR": [PaymentMethod.PIX, PaymentMethod.CARD, PaymentMethod.BOLETO,
           PaymentMethod.MERCADO_PAGO, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "MX": [PaymentMethod.CARD, PaymentMethod.OXXO, PaymentMethod.MERCADO_PAGO,
           PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY],
    "AR": [PaymentMethod.CARD, PaymentMethod.MERCADO_PAGO, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "CL": [PaymentMethod.CARD, PaymentMethod.MERCADO_PAGO, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "CO": [PaymentMethod.CARD, PaymentMethod.MERCADO_PAGO, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    "PE": [PaymentMethod.CARD, PaymentMethod.MERCADO_PAGO, PaymentMethod.APPLE_PAY,
           PaymentMethod.GOOGLE_PAY],
    # ---- Oceania
    "AU": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.PAYPAL, PaymentMethod.KLARNA, PaymentMethod.AFTERPAY],
    "NZ": [PaymentMethod.CARD, PaymentMethod.APPLE_PAY, PaymentMethod.GOOGLE_PAY,
           PaymentMethod.PAYPAL, PaymentMethod.AFTERPAY],
}


# Locale -> default country fallback (when only the language is known).
# Used by the UI when there's no explicit country signal.
LOCALE_DEFAULT_COUNTRY: Dict[str, str] = {
    "en": "US", "es": "MX", "pt": "BR", "fr": "FR", "de": "DE",
    "it": "IT", "ru": "RU", "ar": "SA", "hi": "IN", "zh": "CN",
    "ja": "JP", "ko": "KR", "vi": "VN", "km": "KH",
    "th": "TH", "id": "ID", "ms": "MY", "tr": "TR",
    "nl": "NL", "pl": "PL", "uk": "UA", "sv": "SE", "fi": "FI",
    "no": "NO", "da": "DK", "el": "GR", "ro": "RO",
}


# Universal fallback when we don't recognise the country (matches the
# most internationally-accepted set: card + global wallets + PayPal).
_UNIVERSAL_FALLBACK = [
    PaymentMethod.CARD, PaymentMethod.APPLE_PAY,
    PaymentMethod.GOOGLE_PAY, PaymentMethod.PAYPAL,
]


def processor_for(method: PaymentMethod) -> Processor:
    return METHOD_PROCESSOR[method]


def label_for(method: PaymentMethod) -> str:
    return METHOD_LABELS.get(method, method.value.replace("_", " ").title())


def methods_for_country(country: str | None) -> list[PaymentMethod]:
    """Return the ordered list of payment methods commonly offered in
    ``country`` (ISO-3166-1 alpha-2). Falls back to the universal set
    when the country is unknown or None.
    """
    if not country:
        return list(_UNIVERSAL_FALLBACK)
    return list(COUNTRY_METHODS.get(country.upper(), _UNIVERSAL_FALLBACK))


def methods_for_locale(locale: str | None) -> list[PaymentMethod]:
    """Convenience: country-aware methods inferred from a locale code
    (e.g. ``"vi"`` -> ``"VN"``). Falls back to US for English."""
    country = LOCALE_DEFAULT_COUNTRY.get((locale or "").lower(), "US")
    return methods_for_country(country)


def all_methods_for_processors(processors: Iterable[Processor]) -> FrozenSet[PaymentMethod]:
    """Return every method routed through any of ``processors``. Used by
    cloud providers that aggregate several capabilities (e.g. Stripe)."""
    s = set(processors)
    return frozenset(m for m, p in METHOD_PROCESSOR.items() if p in s)
