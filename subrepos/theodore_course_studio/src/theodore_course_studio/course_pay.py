"""One-time checkout for the rest of a course (web: Stripe Checkout and PayPal Orders).

The browser never sends a card number, a price or an account id here: the server takes the price and title from its own
course list, the account from the verified login, and a course stays locked until the processor says the payment is
authorized (return confirmation) or its signed webhook says so. The durable record is aoep_shared.purchases.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable, Optional

from aoep_shared.course_studio_access import COURSE_PRICE_CENTS, COURSE_PRICE_LABEL

_OPENER = urllib.request.urlopen


def course_price() -> dict[str, Any]:
    return {
        "amount_cents": COURSE_PRICE_CENTS,
        "currency": "usd",
        "label": COURSE_PRICE_LABEL,
    }


def _paypal_creds() -> tuple[str, str]:
    key = os.environ.get("PAYPAL_API_KEY", "").strip()
    secret = os.environ.get("PAYPAL_API_SECRET", "").strip()
    if not secret and ":" in key:
        key, secret = key.split(":", 1)
    return key.strip(), secret.strip()


def _stripe_secret() -> str:
    return (
        os.environ.get("PAYMENT_API_KEY", "").strip()
        or os.environ.get("STRIPE_SECRET_KEY", "").strip()
        or os.environ.get("STRIPE_API_KEY", "").strip()
    )


def _paypal_base() -> str:
    if os.environ.get("PAYPAL_ENV", "").strip().lower() == "sandbox":
        return "https://api-m.sandbox.paypal.com"
    return "https://api-m.paypal.com"


def same_site_return(return_url: str, host: str) -> str:
    """Keep the processor's return on the site that started checkout."""
    parts = urllib.parse.urlsplit((return_url or "").strip())
    expected = (host or "").split(",")[0].strip()
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError("return_url must be an absolute http(s) URL")
    if parts.netloc != expected and (parts.hostname or "") != expected.split(":")[0]:
        raise ValueError("return_url must stay on this site")
    query = [
        (key, value)
        for key, value in urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
        if key not in {"paid", "session_id", "token", "PayerID"}
    ]
    return urllib.parse.urlunsplit(
        (parts.scheme, parts.netloc, parts.path, urllib.parse.urlencode(query), "")
    )


def _request_json(
    url: str,
    *,
    method: str = "GET",
    data: bytes | None = None,
    headers: dict[str, str] | None = None,
    opener: Callable[..., Any] = _OPENER,
) -> dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with opener(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")[:500]
        raise RuntimeError(f"payment processor returned {exc.code}: {detail}") from exc
    if not raw:
        return {}
    parsed = json.loads(raw)
    if not isinstance(parsed, dict):
        raise RuntimeError("payment processor returned an unexpected payload")
    return parsed


def start_card_checkout(
    *,
    account_id: str,
    course_id: str,
    title: str,
    amount_cents: int,
    return_url: str,
    email: str = "",
    automatic_tax: bool = False,
    opener: Callable[..., Any] = _OPENER,
) -> dict[str, str]:
    secret = _stripe_secret()
    if not secret:
        raise RuntimeError(
            "Card payments need PAYMENT_API_KEY (a Stripe secret key) on the server."
        )
    join = "&" if "?" in return_url else "?"
    success = return_url + join + "paid=1&session_id={CHECKOUT_SESSION_ID}"
    fields = {
        "mode": "payment",
        "success_url": success,
        "cancel_url": return_url,
        "client_reference_id": f"{account_id}:{course_id}"[:200],
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(int(amount_cents)),
        "line_items[0][price_data][product_data][name]": (title or "Full course")[:120],
        "payment_method_types[0]": "card",
        "metadata[account_id]": account_id[:200],
        "metadata[course_id]": course_id[:200],
    }
    if email:
        fields["customer_email"] = email[:200]
    if automatic_tax:
        fields["automatic_tax[enabled]"] = "true"
        fields["billing_address_collection"] = "required"
        fields["line_items[0][price_data][tax_behavior]"] = "exclusive"
    body = urllib.parse.urlencode(fields, safe="{}").encode()
    payload = _request_json(
        "https://api.stripe.com/v1/checkout/sessions",
        method="POST",
        data=body,
        headers={
            "Authorization": f"Bearer {secret}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        opener=opener,
    )
    session_id = str(payload.get("id") or "")
    url = str(payload.get("url") or "")
    if not session_id or not url:
        raise RuntimeError("Stripe did not return a card checkout")
    return {"session_id": session_id, "url": url, "provider": "stripe", "method": "card"}


def card_session(session_id: str, *, opener: Callable[..., Any] = _OPENER) -> dict[str, Any]:
    """The Stripe Checkout session, fetched with the secret key (never trust the browser's word that it paid)."""
    secret = _stripe_secret()
    if not secret:
        return {}
    return _request_json(
        "https://api.stripe.com/v1/checkout/sessions/" + urllib.parse.quote(session_id, safe=""),
        headers={"Authorization": f"Bearer {secret}"},
        opener=opener,
    )


def card_is_paid(session_id: str, *, opener: Callable[..., Any] = _OPENER) -> bool:
    return str(card_session(session_id, opener=opener).get("payment_status") or "") == "paid"


def paid_from_stripe_session(session: dict[str, Any]) -> Optional[dict[str, Any]]:
    """Normalize a paid Checkout session into the fields the purchase ledger needs, or None when it is not paid."""
    if str(session.get("payment_status") or "") != "paid":
        return None
    meta = session.get("metadata") or {}
    ref = str(session.get("client_reference_id") or "")
    account_id = str(meta.get("account_id") or (ref.split(":", 1)[0] if ":" in ref else ""))
    course_id = str(meta.get("course_id") or (ref.split(":", 1)[1] if ":" in ref else ""))
    details = session.get("customer_details") or {}
    totals = session.get("total_details") or {}
    total = int(session.get("amount_total") or 0)
    tax = int(totals.get("amount_tax") or 0)
    return {
        "account_id": account_id, "course_id": course_id, "provider": "stripe", "provider_ref": str(session.get("id") or ""),
        "amount_cents": max(total - tax, 0), "tax_cents": tax, "currency": str(session.get("currency") or "usd"),
        "email": str(details.get("email") or ""), "payment_intent": str(session.get("payment_intent") or ""),
    }


def verify_stripe_signature(
    payload: bytes, header: str, secret: str, *, tolerance_s: int = 300, now: Callable[[], float] = time.time
) -> bool:
    """Stripe-Signature: t=<ts>,v1=<hmac>. Constant-time compare, replay window, any v1 may match (key rotation)."""
    if not secret or not header:
        return False
    parts = [p.split("=", 1) for p in header.split(",") if "=" in p]
    stamps = [v for k, v in parts if k.strip() == "t"]
    sigs = [v for k, v in parts if k.strip() == "v1"]
    if not stamps or not sigs:
        return False
    try:
        stamp = int(stamps[0])
    except ValueError:
        return False
    if abs(now() - stamp) > tolerance_s:
        return False
    expected = hmac.new(secret.encode(), f"{stamp}.".encode() + payload, hashlib.sha256).hexdigest()
    return any(hmac.compare_digest(expected, sig.strip()) for sig in sigs)


def stripe_webhook_secret() -> str:
    return os.environ.get("STRIPE_WEBHOOK_SECRET", "").strip()


def _paypal_token(opener: Callable[..., Any]) -> str:
    client_id, secret = _paypal_creds()
    if not client_id or not secret:
        raise RuntimeError(
            "PayPal payments need PAYPAL_API_KEY and PAYPAL_API_SECRET on the server."
        )
    token = _request_json(
        _paypal_base() + "/v1/oauth2/token",
        method="POST",
        data=b"grant_type=client_credentials",
        headers={
            "Authorization": "Basic " + _basic(client_id, secret),
            "Content-Type": "application/x-www-form-urlencoded",
        },
        opener=opener,
    )
    access = str(token.get("access_token") or "")
    if not access:
        raise RuntimeError("PayPal did not return an access token")
    return access


def _basic(client_id: str, secret: str) -> str:
    import base64

    return base64.b64encode(f"{client_id}:{secret}".encode()).decode()


def start_paypal_checkout(
    *,
    account_id: str,
    course_id: str,
    title: str,
    amount_cents: int,
    return_url: str,
    opener: Callable[..., Any] = _OPENER,
) -> dict[str, str]:
    access = _paypal_token(opener)
    join = "&" if "?" in return_url else "?"
    order = _request_json(
        _paypal_base() + "/v2/checkout/orders",
        method="POST",
        data=json.dumps(
            {
                "intent": "CAPTURE",
                "purchase_units": [
                    {
                        "custom_id": f"{account_id}:{course_id}"[:127],
                        "description": (title or "Full course")[:127],
                        "amount": {"currency_code": "USD", "value": f"{int(amount_cents) // 100}.{int(amount_cents) % 100:02d}"},
                    }
                ],
                "application_context": {
                    "return_url": return_url + join + "paid=1",
                    "cancel_url": return_url,
                    "user_action": "PAY_NOW",
                },
            }
        ).encode(),
        headers={
            "Authorization": f"Bearer {access}",
            "Content-Type": "application/json",
        },
        opener=opener,
    )
    session_id = str(order.get("id") or "")
    url = ""
    for link in order.get("links") or []:
        if isinstance(link, dict) and link.get("rel") == "approve":
            url = str(link.get("href") or "")
    if not session_id or not url:
        raise RuntimeError("PayPal did not return a checkout")
    return {"session_id": session_id, "url": url, "provider": "paypal", "method": "paypal"}


def paypal_capture(order_id: str, *, opener: Callable[..., Any] = _OPENER) -> dict[str, Any]:
    """Capture an approved PayPal order. A repeat capture (already captured) reads the order instead, so it is idempotent."""
    access = _paypal_token(opener)
    headers = {"Authorization": f"Bearer {access}", "Content-Type": "application/json"}
    quoted = urllib.parse.quote(order_id, safe="")
    try:
        order = _request_json(
            _paypal_base() + "/v2/checkout/orders/" + quoted + "/capture", method="POST", data=b"{}", headers=headers, opener=opener
        )
    except RuntimeError as exc:
        if "ORDER_ALREADY_CAPTURED" not in str(exc):
            raise
        order = _request_json(_paypal_base() + "/v2/checkout/orders/" + quoted, headers=headers, opener=opener)
    return order


def paid_from_paypal_order(order: dict[str, Any]) -> Optional[dict[str, Any]]:
    if str(order.get("status") or "") != "COMPLETED":
        return None
    unit = (order.get("purchase_units") or [{}])[0]
    custom = str(unit.get("custom_id") or "")
    account_id, _, course_id = custom.partition(":")
    capture = ((unit.get("payments") or {}).get("captures") or [{}])[0]
    value = (capture.get("amount") or unit.get("amount") or {}).get("value") or "0"
    try:
        cents = int(round(float(value) * 100))
    except ValueError:
        cents = 0
    payer = order.get("payer") or {}
    return {
        "account_id": account_id, "course_id": course_id, "provider": "paypal", "provider_ref": str(order.get("id") or ""),
        "amount_cents": cents, "tax_cents": 0, "currency": "usd", "email": str(payer.get("email_address") or ""),
        "capture_id": str(capture.get("id") or ""),
    }


def paypal_is_paid(order_id: str, *, opener: Callable[..., Any] = _OPENER) -> bool:
    return paid_from_paypal_order(paypal_capture(order_id, opener=opener)) is not None


def verify_paypal_webhook(
    headers: dict[str, str], body: bytes, webhook_id: str, *, opener: Callable[..., Any] = _OPENER
) -> bool:
    """PayPal verifies its own signature: ask its API (needs PAYPAL_WEBHOOK_ID). Anything but SUCCESS is a forgery."""
    if not webhook_id:
        return False
    lowered = {k.lower(): v for k, v in headers.items()}
    try:
        event = json.loads(body.decode("utf-8"))
    except ValueError:
        return False
    payload = {
        "auth_algo": lowered.get("paypal-auth-algo", ""),
        "cert_url": lowered.get("paypal-cert-url", ""),
        "transmission_id": lowered.get("paypal-transmission-id", ""),
        "transmission_sig": lowered.get("paypal-transmission-sig", ""),
        "transmission_time": lowered.get("paypal-transmission-time", ""),
        "webhook_id": webhook_id,
        "webhook_event": event,
    }
    if not all(payload[k] for k in ("auth_algo", "cert_url", "transmission_id", "transmission_sig", "transmission_time")):
        return False
    access = _paypal_token(opener)
    result = _request_json(
        _paypal_base() + "/v1/notifications/verify-webhook-signature",
        method="POST",
        data=json.dumps(payload).encode(),
        headers={"Authorization": f"Bearer {access}", "Content-Type": "application/json"},
        opener=opener,
    )
    return str(result.get("verification_status") or "") == "SUCCESS"
