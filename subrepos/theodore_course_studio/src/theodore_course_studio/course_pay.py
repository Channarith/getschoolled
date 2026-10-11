"""One-time $19.99 checkout for the rest of a course.

Card payments are Stripe Checkout. PayPal payments are PayPal Orders.
The browser never sends a card number here. A course stays locked until the
processor says the payment is authorized.
"""

from __future__ import annotations

import json
import os
import threading
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any, Callable

from aoep_shared.course_studio_access import COURSE_PRICE_CENTS, COURSE_PRICE_LABEL

_LOCK = threading.RLock()
_OPENER = urllib.request.urlopen


def course_price() -> dict[str, Any]:
    return {
        "amount_cents": COURSE_PRICE_CENTS,
        "currency": "usd",
        "label": COURSE_PRICE_LABEL,
    }


def payer_id(learner_id: str) -> str:
    learner = (learner_id or "").strip()
    if learner.endswith(":audio"):
        return learner[: -len(":audio")]
    return learner


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
    learner_id: str,
    course_id: str,
    title: str,
    return_url: str,
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
        "client_reference_id": f"{learner_id}:{course_id}"[:200],
        "line_items[0][quantity]": "1",
        "line_items[0][price_data][currency]": "usd",
        "line_items[0][price_data][unit_amount]": str(COURSE_PRICE_CENTS),
        "line_items[0][price_data][product_data][name]": (title or "Full course")[:120],
        "payment_method_types[0]": "card",
        "metadata[learner_id]": learner_id[:200],
        "metadata[course_id]": course_id[:200],
    }
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


def card_is_paid(session_id: str, *, opener: Callable[..., Any] = _OPENER) -> bool:
    secret = _stripe_secret()
    if not secret:
        return False
    payload = _request_json(
        "https://api.stripe.com/v1/checkout/sessions/" + urllib.parse.quote(session_id, safe=""),
        headers={"Authorization": f"Bearer {secret}"},
        opener=opener,
    )
    return str(payload.get("payment_status") or "") == "paid"


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
    learner_id: str,
    course_id: str,
    title: str,
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
                        "custom_id": f"{learner_id}:{course_id}"[:127],
                        "description": (title or "Full course")[:127],
                        "amount": {"currency_code": "USD", "value": "19.99"},
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


def paypal_is_paid(order_id: str, *, opener: Callable[..., Any] = _OPENER) -> bool:
    access = _paypal_token(opener)
    captured = _request_json(
        _paypal_base() + "/v2/checkout/orders/" + urllib.parse.quote(order_id, safe="") + "/capture",
        method="POST",
        data=b"{}",
        headers={
            "Authorization": f"Bearer {access}",
            "Content-Type": "application/json",
        },
        opener=opener,
    )
    return str(captured.get("status") or "") == "COMPLETED"


class CoursePayStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def _read(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {"pending": {}, "paid": {}}
        try:
            loaded = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {"pending": {}, "paid": {}}
        if not isinstance(loaded, dict):
            return {"pending": {}, "paid": {}}
        loaded.setdefault("pending", {})
        loaded.setdefault("paid", {})
        return loaded

    def _write(self, payload: dict[str, Any]) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(json.dumps(payload), encoding="utf-8")

    def remember(
        self, *, session_id: str, learner_id: str, course_id: str, method: str
    ) -> None:
        with _LOCK:
            payload = self._read()
            payload["pending"][session_id] = {
                "learner_id": payer_id(learner_id),
                "course_id": course_id,
                "method": method,
                "amount_cents": COURSE_PRICE_CENTS,
            }
            self._write(payload)

    def pending(self, session_id: str) -> dict[str, Any] | None:
        with _LOCK:
            row = self._read()["pending"].get(session_id)
        return dict(row) if isinstance(row, dict) else None

    def mark_paid(self, session_id: str) -> dict[str, Any] | None:
        with _LOCK:
            payload = self._read()
            row = payload["pending"].get(session_id)
            if not isinstance(row, dict):
                for saved in payload["paid"].values():
                    if isinstance(saved, dict) and saved.get("session_id") == session_id:
                        return dict(saved)
                return None
            key = f"{row['learner_id']}:{row['course_id']}"
            saved = {**row, "session_id": session_id, "status": "paid"}
            payload["paid"][key] = saved
            payload["pending"].pop(session_id, None)
            self._write(payload)
            return saved

    def is_paid(self, learner_id: str, course_id: str) -> bool:
        key = f"{payer_id(learner_id)}:{course_id}"
        with _LOCK:
            row = self._read()["paid"].get(key)
        return isinstance(row, dict) and row.get("status") == "paid"
