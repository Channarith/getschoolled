"""Billing API tests for the expanded global payment-method coverage:

- /payment-methods?country=XX returns the popular set ordered by region
- /payment-methods?locale=YY infers the country from the locale
- /payment-methods/by-country returns the full matrix
- The 'available' flag reflects what the active provider can process
"""

from __future__ import annotations

from billing.main import app
from fastapi.testclient import TestClient


client = TestClient(app)


def test_payment_methods_default_lists_every_method():
    """Without a country filter, return every method the platform
    supports."""
    r = client.get("/payment-methods")
    assert r.status_code == 200
    methods = {m["method"] for m in r.json()["methods"]}
    # Spot-check globally important ones.
    for m in ("card", "apple_pay", "paypal", "venmo", "zelle", "square",
              "upi", "alipay", "wechat_pay", "pix", "klarna",
              "vnpay", "momo", "aba_pay", "khqr"):
        assert m in methods, f"missing globally: {m}"


def test_payment_methods_us_includes_zelle_venmo_paypal_square():
    r = client.get("/payment-methods?country=US")
    assert r.status_code == 200
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "zelle", "venmo", "paypal", "square", "cashapp",
              "apple_pay", "google_pay", "ach"):
        assert m in methods, f"US country list missing {m}"


def test_payment_methods_brazil_leads_with_pix():
    r = client.get("/payment-methods?country=BR")
    methods = [m["method"] for m in r.json()["methods"]]
    assert methods[0] == "pix", f"Brazil should lead with PIX; got {methods}"
    for m in ("boleto", "mercado_pago", "card"):
        assert m in methods


def test_payment_methods_india_includes_upi_phonepe_paytm():
    r = client.get("/payment-methods?country=IN")
    methods = [m["method"] for m in r.json()["methods"]]
    assert methods[0] == "upi"
    for m in ("paytm", "phonepe", "razorpay", "rupay", "card"):
        assert m in methods


def test_payment_methods_china_includes_alipay_wechat_unionpay():
    r = client.get("/payment-methods?country=CN")
    methods = [m["method"] for m in r.json()["methods"]]
    assert methods[0] == "alipay"
    for m in ("wechat_pay", "unionpay", "card"):
        assert m in methods


def test_payment_methods_germany_includes_sepa_giropay_klarna_sofort():
    r = client.get("/payment-methods?country=DE")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "sepa", "klarna", "sofort", "giropay", "paypal"):
        assert m in methods


def test_payment_methods_vietnam_includes_vnpay_momo_zalopay():
    r = client.get("/payment-methods?country=VN")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "vnpay", "momo", "zalo_pay"):
        assert m in methods


def test_payment_methods_cambodia_includes_aba_khqr_wing():
    r = client.get("/payment-methods?country=KH")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "aba_pay", "wing", "khqr"):
        assert m in methods


def test_payment_methods_arabic_market_saudi():
    r = client.get("/payment-methods?country=SA")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "mada", "stc_pay", "apple_pay"):
        assert m in methods


def test_payment_methods_locale_param_infers_country():
    """locale=km should infer country=KH and return ABA/KHQR/Wing."""
    r = client.get("/payment-methods?locale=km")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("aba_pay", "khqr", "wing"):
        assert m in methods, f"km->KH inference missed {m}"


def test_payment_methods_unknown_country_returns_universal_set():
    r = client.get("/payment-methods?country=ZZ")
    methods = [m["method"] for m in r.json()["methods"]]
    for m in ("card", "apple_pay", "google_pay", "paypal"):
        assert m in methods


def test_payment_methods_available_flag_local_mode_is_all_true():
    """Local sandbox simulates every method, so every entry should be
    marked available=True."""
    r = client.get("/payment-methods")
    for entry in r.json()["methods"]:
        assert entry["available"] is True, (
            f"local sandbox should support every method but {entry['method']} "
            f"shows available=False"
        )


def test_by_country_endpoint_returns_full_matrix():
    r = client.get("/payment-methods/by-country")
    assert r.status_code == 200
    data = r.json()
    assert "countries" in data and "locales" in data
    countries = data["countries"]
    # Spot-check coverage for every region we localise into.
    for c in ("US", "BR", "DE", "IN", "CN", "JP", "KR", "VN", "KH",
              "SA", "RU", "FR", "ES", "IT", "MX"):
        assert c in countries, f"missing country {c} in by-country matrix"
        assert isinstance(countries[c], list) and len(countries[c]) > 0
    # Locales we ship UI translations for must all map to a country.
    locales = data["locales"]
    for loc in ("en", "es", "fr", "de", "it", "pt", "ru", "ar",
                "hi", "zh", "ja", "ko", "vi", "km"):
        assert loc in locales, f"locale {loc} missing default country"
