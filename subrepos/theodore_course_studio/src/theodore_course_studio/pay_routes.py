"""Course purchase routes: entitlement, checkout, return confirmation, signed webhooks, purchase list.

Rules this module enforces (docs/course-payments.txt):
  * payment needs a VERIFIED login (identity /auth/me); an anonymous caller gets 401 and no price;
  * the course, the price and the title come from the server's own list, never from the request;
  * the purchase is bound to the verified account, so it unlocks the class on the web and in the apps;
  * the processor, not the browser, says a payment happened (return confirmation fetches it with our key, webhooks are
    signature-verified), and recording it is idempotent;
  * entitled accounts (admin, VIP/premium, already paid) never get a checkout.
Errors are short human sentences; raw processor text stays in the log.
"""

from __future__ import annotations

import json
import logging
import os
import urllib.parse
from typing import Any, Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from aoep_shared.course_entitlement import (
    FREE, LOGIN_REQUIRED, MUST_PAY, PAID, account_id, entitled_to_course, unlocks_full_class,
)
from aoep_shared.course_studio_access import purchasable_course
from aoep_shared.purchases import PurchaseConflict, PurchaseStore, PurchaseStoreUnavailable, default_store

from . import course_pay as pay
from .caller_claims import authorization_from, verified_caller

logger = logging.getLogger(__name__)
router = APIRouter()

# Tests replace these; production uses the identity service and the Redis-backed ledger.
_identity: Callable[[str], Optional[dict]] = lambda authorization: verified_caller(authorization)
_store_factory: Callable[[], PurchaseStore] = lambda: default_store()


def get_store() -> PurchaseStore:
    try:
        return _store_factory()
    except PurchaseStoreUnavailable as exc:
        logger.error("purchase store unavailable: %s", exc)
        raise HTTPException(status_code=503, detail="Payments are paused for a moment. Please try again shortly.") from exc


def _caller(authorization: str, request: Optional[Request] = None) -> Optional[dict]:
    return _identity(authorization_from(authorization, request.cookies if request is not None else None))


def _same_origin(request: Request) -> None:
    """State-changing calls must come from this site: a cross-site page cannot ride the login cookie."""
    origin = (request.headers.get("origin") or "").strip()
    if not origin:
        return
    host = (request.headers.get("host") or "").split(",")[0].strip()
    if urllib.parse.urlsplit(origin).netloc != host:
        raise HTTPException(status_code=403, detail="That request did not come from this site.")


def _require_caller(authorization: str, request: Optional[Request] = None) -> dict:
    who = _caller(authorization, request)
    if not account_id(who):
        raise HTTPException(status_code=401, detail="Log in to buy the course.", headers={"X-AOEP-Gate": "login_required"})
    return who  # type: ignore[return-value]


def _offer(course: dict[str, Any]) -> dict[str, Any]:
    return {
        "course_id": course["id"], "title": course["title"], "amount_cents": int(course["price_cents"]),
        "currency": "usd", "label": course["price_label"],
    }


@router.get("/api/studio/pay/price")
def pay_price() -> dict[str, Any]:
    return pay.course_price()


@router.get("/api/studio/entitlement")
def entitlement(course_id: str, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """What this caller may do with a course. Anonymous callers never receive a price."""
    course = purchasable_course(course_id)
    who = _caller(authorization, request)
    if course is None:
        return {"course_id": course_id, "entitlement": FREE if account_id(who) else LOGIN_REQUIRED, "purchasable": False}
    ent = entitled_to_course(who, course_id, purchases=get_store() if account_id(who) else None)
    body: dict[str, Any] = {"course_id": course_id, "entitlement": ent, "purchasable": True}
    if ent == MUST_PAY:
        body["offer"] = _offer(course)
    return body


class CheckoutRequest(BaseModel):
    course_id: str
    method: str = "card"
    return_url: str = ""


class ConfirmRequest(BaseModel):
    session_id: str
    method: str = ""


@router.post("/api/studio/pay/checkout")
def pay_checkout(req: CheckoutRequest, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    _same_origin(request)
    method = (req.method or "").strip().lower()
    if method not in {"card", "paypal"}:
        raise HTTPException(status_code=422, detail="Choose card or PayPal.")
    who = _require_caller(authorization, request)
    course = purchasable_course(req.course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="That course is not for sale.")
    store = get_store()
    ent = entitled_to_course(who, course["id"], purchases=store)
    if unlocks_full_class(ent):
        return {"already_entitled": True, "entitlement": ent, "course_id": course["id"]}
    try:
        return_url = pay.same_site_return(req.return_url, request.headers.get("host", ""))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="That return page is not allowed.") from exc
    uid = account_id(who)
    try:
        if method == "card":
            session = pay.start_card_checkout(
                account_id=uid, course_id=course["id"], title=course["title"], amount_cents=int(course["price_cents"]),
                return_url=return_url, email=str(who.get("email") or ""),
                automatic_tax=os.environ.get("COURSE_TAX_MODE", "none").strip().lower() == "provider",
            )
        else:
            session = pay.start_paypal_checkout(
                account_id=uid, course_id=course["id"], title=course["title"], amount_cents=int(course["price_cents"]),
                return_url=return_url,
            )
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("checkout start failed: %s", exc)
        raise HTTPException(status_code=503, detail="Payments are not available right now. Please try again later.") from exc
    return {**session, **_offer(course)}


def _record(store: PurchaseStore, paid: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    course = purchasable_course(paid.get("course_id", ""))
    if course is None or not paid.get("account_id"):
        raise HTTPException(status_code=400, detail="That payment does not match a course.")
    if int(paid.get("amount_cents") or 0) < int(course["price_cents"]):
        logger.error("underpaid order ref=%s amount=%s", paid.get("provider_ref"), paid.get("amount_cents"))
        raise HTTPException(status_code=402, detail="The payment amount does not match the course price.")
    try:
        return store.record_paid(
            account_id=paid["account_id"], course_id=paid["course_id"], amount_cents=int(paid["amount_cents"]),
            tax_cents=int(paid.get("tax_cents") or 0), provider=paid["provider"], provider_ref=paid["provider_ref"],
            currency=paid.get("currency", "usd"), email=paid.get("email", ""),
            meta={k: paid[k] for k in ("payment_intent", "capture_id") if paid.get(k)},
        )
    except PurchaseConflict as exc:
        raise HTTPException(status_code=409, detail="That payment belongs to another account.") from exc


@router.post("/api/studio/pay/confirm")
def pay_confirm(req: ConfirmRequest, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """Return-page confirmation. The processor is asked, with our key; the caller must own the order."""
    _same_origin(request)
    who = _require_caller(authorization, request)
    session_id = (req.session_id or "").strip()
    if not session_id:
        raise HTTPException(status_code=400, detail="session_id is required")
    method = (req.method or "").strip().lower() or ("card" if session_id.startswith("cs_") else "paypal")
    try:
        paid = (
            pay.paid_from_paypal_order(pay.paypal_capture(session_id))
            if method == "paypal"
            else pay.paid_from_stripe_session(pay.card_session(session_id))
        )
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("confirm failed: %s", exc)
        raise HTTPException(status_code=503, detail="We could not reach the payment provider. Please try again.") from exc
    if paid is None:
        raise HTTPException(status_code=402, detail="The payment is not complete yet.")
    if paid["account_id"] != account_id(who):
        raise HTTPException(status_code=403, detail="That payment belongs to another account.")
    order, created = _record(get_store(), paid)
    return {"status": "paid", "created": created, "order_id": order["order_id"], "course_id": order["course_id"]}


@router.post("/api/studio/pay/webhook/stripe")
async def stripe_webhook(request: Request) -> dict[str, Any]:
    body = await request.body()
    if not pay.verify_stripe_signature(body, request.headers.get("stripe-signature", ""), pay.stripe_webhook_secret()):
        raise HTTPException(status_code=400, detail="bad signature")
    try:
        event = json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bad payload") from exc
    kind = str(event.get("type") or "")
    obj = (event.get("data") or {}).get("object") or {}
    store = get_store()
    if kind in {"checkout.session.completed", "checkout.session.async_payment_succeeded"}:
        paid = pay.paid_from_stripe_session(obj)
        if paid is not None:
            _record(store, paid)
    elif kind in {"charge.refunded", "charge.dispute.created", "charge.dispute.funds_withdrawn"}:
        intent = str(obj.get("payment_intent") or "")
        if intent:
            for order in store.find_orders(lambda o: o.get("provider") == "stripe" and (o.get("meta") or {}).get("payment_intent") == intent):
                store.revoke_by_ref("stripe", order["provider_ref"], reason=kind, by="stripe")
    return {"received": True}


@router.post("/api/studio/pay/webhook/paypal")
async def paypal_webhook(request: Request) -> dict[str, Any]:
    body = await request.body()
    try:
        ok = pay.verify_paypal_webhook(dict(request.headers), body, os.environ.get("PAYPAL_WEBHOOK_ID", "").strip())
    except (RuntimeError, OSError, ValueError):
        ok = False
    if not ok:
        raise HTTPException(status_code=400, detail="bad signature")
    try:
        event = json.loads(body.decode("utf-8"))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="bad payload") from exc
    kind = str(event.get("event_type") or "")
    res = event.get("resource") or {}
    order_id = str(((res.get("supplementary_data") or {}).get("related_ids") or {}).get("order_id") or "")
    store = get_store()
    if kind == "PAYMENT.CAPTURE.COMPLETED" and order_id:
        custom = str(res.get("custom_id") or "")
        account, _, course = custom.partition(":")
        try:
            cents = int(round(float((res.get("amount") or {}).get("value") or "0") * 100))
        except ValueError:
            cents = 0
        _record(store, {"account_id": account, "course_id": course, "provider": "paypal", "provider_ref": order_id,
                        "amount_cents": cents, "currency": "usd", "capture_id": str(res.get("id") or "")})
    elif kind in {"PAYMENT.CAPTURE.REFUNDED", "PAYMENT.CAPTURE.REVERSED", "PAYMENT.CAPTURE.DENIED"} and order_id:
        store.revoke_by_ref("paypal", order_id, reason=kind, by="paypal")
    return {"received": True}


@router.get("/api/studio/account/purchases")
def my_purchases(request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    who = _require_caller(authorization, request)
    rows = get_store().list_for_account(account_id(who))
    keep = ("order_id", "course_id", "amount_cents", "tax_cents", "total_cents", "currency", "provider", "status", "created_at", "last4")
    return {"purchases": [{k: r.get(k) for k in keep} for r in rows]}
