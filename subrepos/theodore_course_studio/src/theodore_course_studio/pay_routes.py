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

import hmac
import json
import logging
import os
import time
import urllib.parse
from typing import Any, Callable, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from fastapi.responses import HTMLResponse, Response
from pydantic import BaseModel

from aoep_shared.course_entitlement import (
    FREE, LOGIN_REQUIRED, MUST_PAY, PAID, account_id, entitled_to_course, unlocks_full_class,
)
from aoep_shared import checkout_tax, receipts
from aoep_shared import refund_policy as refunds
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
    billing_state: str = ""  # asked for ONLY when COURSE_TAX_MODE=manual


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
    tax = checkout_tax.compute_tax(int(course["price_cents"]), state=req.billing_state)
    if tax["requires_state"]:
        raise HTTPException(status_code=422, detail="Choose your state so we can calculate tax.", headers={"X-AOEP-Gate": "billing_state_required"})
    try:
        if method == "card":
            session = pay.start_card_checkout(
                account_id=uid, course_id=course["id"], title=course["title"], amount_cents=int(course["price_cents"]),
                return_url=return_url, email=str(who.get("email") or ""),
                automatic_tax=checkout_tax.tax_mode() == "provider", tax_cents=tax["tax_cents"], tax_label=tax["label"],
            )
        else:
            session = pay.start_paypal_checkout(
                account_id=uid, course_id=course["id"], title=course["title"], amount_cents=int(course["price_cents"]),
                return_url=return_url, tax_cents=tax["tax_cents"], tax_label=tax["label"],
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
            currency=paid.get("currency", "usd"), email=paid.get("email", ""), last4=paid.get("last4", ""),
            meta={k: paid[k] for k in ("payment_intent", "capture_id") if paid.get(k)},
        )
    except PurchaseConflict as exc:
        raise HTTPException(status_code=409, detail="That payment belongs to another account.") from exc


def _email_receipt(store: PurchaseStore, order: dict[str, Any], to_email: str) -> dict[str, Any]:
    """Send the receipt once. Idempotent: an order already emailed is not emailed again."""
    if (order.get("meta") or {}).get("receipt_emailed"):
        return {"sent": False, "reason": "already sent", "already": True}
    result = receipts.send_receipt_email(receipts.build_receipt(order), to_email or order.get("email", ""))
    if result.get("sent"):
        store.set_meta(order["order_id"], receipt_emailed=True)
    return result


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
    store = get_store()
    order, created = _record(store, paid)
    if created and receipts.email_configured():
        try:
            _email_receipt(store, order, str(who.get("email") or ""))
        except Exception as exc:  # noqa: BLE001 - a mail problem must never undo a recorded payment
            logger.error("receipt email failed: %s", exc)
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
    store = get_store()
    rows = store.list_for_account(account_id(who))
    keep = ("order_id", "course_id", "amount_cents", "tax_cents", "total_cents", "currency", "provider", "status", "created_at", "last4")
    out = []
    for row in rows:
        item = {k: row.get(k) for k in keep}
        item["receipt_url"] = f"/api/studio/account/receipts/{row['order_id']}.html"
        item["refund"] = _refund_view(store, row)
        item["refund_requested"] = bool((row.get("meta") or {}).get("refund_requested"))
        out.append(item)
    return {"purchases": out}


def _progress_pct(store: PurchaseStore, order: dict[str, Any]) -> Optional[float]:
    """0 when the account never opened the full class; otherwise unknown (None) until a lesson-progress source is wired."""
    return None if store.has_started(order["account_id"], order["course_id"]) else 0.0


def _refund_view(store: PurchaseStore, order: dict[str, Any]) -> dict[str, Any]:
    verdict = refunds.evaluate(order, progress_pct=_progress_pct(store, order))
    return {k: verdict[k] for k in ("eligible", "reason", "message", "days_left")}


def _owned_order(store: PurchaseStore, who: dict, order_id: str) -> dict[str, Any]:
    order = store.get(order_id)
    if order is None or order.get("account_id") != account_id(who):
        raise HTTPException(status_code=404, detail="We could not find that purchase.")
    return order


@router.get("/api/studio/pay/quote")
def pay_quote(course_id: str, request: Request, state: str = "", authorization: str = Header(default="")) -> dict[str, Any]:
    """Price, tax and total for the signed-in buyer: the server's own numbers, shown only after login."""
    _require_caller(authorization, request)
    course = purchasable_course(course_id)
    if course is None:
        raise HTTPException(status_code=404, detail="That course is not for sale.")
    tax = checkout_tax.compute_tax(int(course["price_cents"]), state=state)
    total = int(course["price_cents"]) + int(tax["tax_cents"])
    return {"course_id": course_id, "amount_cents": int(course["price_cents"]), "tax_cents": tax["tax_cents"], "tax_label": tax["label"],
            "tax_mode": tax["mode"], "requires_state": tax["requires_state"], "total_cents": total, "total_label": receipts.money(total)}


@router.get("/api/studio/policy")
def policy() -> dict[str, Any]:
    """The configured sales policy, so the policy pages always match what the server does."""
    seller = receipts.seller()
    return {"refund": refunds.RefundPolicy.from_env().public(), "tax_mode": checkout_tax.tax_mode(),
            "seller": {"legal_name": seller["legal_name"], "address": seller["address"], "support_email": seller["support_email"]},
            "disclaimer": receipts.disclaimer_text(), "draft": True}


def _receipt_for(order: dict[str, Any], kind: str) -> dict[str, Any]:
    if kind == "credit_note" and order.get("status") == "paid":
        raise HTTPException(status_code=404, detail="There is no credit note for this purchase.")
    return receipts.build_receipt(order, "credit_note" if kind == "credit_note" else "receipt")


@router.get("/api/studio/account/receipts/{order_id}.html")
def receipt_html(order_id: str, request: Request, type: str = "receipt", authorization: str = Header(default="")) -> Response:
    who = _require_caller(authorization, request)
    order = _owned_order(get_store(), who, order_id)
    page = receipts.render_html(_receipt_for(order, "credit_note" if type in ("credit-note", "credit_note") else "receipt"))
    return HTMLResponse(page, headers={"Cache-Control": "private, no-store"})


@router.get("/api/studio/account/receipts/{order_id}.pdf")
def receipt_pdf(order_id: str, request: Request, type: str = "receipt", authorization: str = Header(default="")) -> Response:
    who = _require_caller(authorization, request)
    order = _owned_order(get_store(), who, order_id)
    pdf = receipts.render_pdf(_receipt_for(order, "credit_note" if type in ("credit-note", "credit_note") else "receipt"))
    if pdf is None:
        raise HTTPException(status_code=501, detail="PDF receipts are not available here. Open the receipt page and choose Print, then Save as PDF.")
    return Response(pdf, media_type="application/pdf", headers={"Cache-Control": "private, no-store",
                                                                "Content-Disposition": f'inline; filename="receipt-{order_id}.pdf"'})


@router.post("/api/studio/account/receipts/{order_id}/email")
def receipt_email(order_id: str, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    _same_origin(request)
    who = _require_caller(authorization, request)
    store = get_store()
    order = _owned_order(store, who, order_id)
    result = _email_receipt(store, order, str(who.get("email") or ""))
    if not result.get("sent") and not result.get("already"):
        # Honest answer: nothing was sent (no email sender configured, or the send failed).
        raise HTTPException(status_code=503, detail="We could not email the receipt right now. You can open it and save it as a PDF instead.")
    return {"sent": bool(result.get("sent")), "already_sent": bool(result.get("already"))}


@router.get("/api/studio/receipts/verify")
def receipt_verify(order: str, code: str, kind: str = "receipt") -> dict[str, Any]:
    """Anyone holding a receipt can check it against our record. No personal data is returned."""
    row = get_store().get(order)
    kind = "credit_note" if kind in ("credit-note", "credit_note") else "receipt"
    if row is None or not hmac_equal(receipts.verification_code(row, kind), code.strip().upper()):
        return {"valid": False}
    return {"valid": True, "total": receipts.money(row["total_cents"], row.get("currency", "usd")), "status": row["status"]}


def hmac_equal(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


def _provider_refund(order: dict[str, Any], amount_cents: int) -> None:
    provider = order.get("provider")
    try:
        if provider == "stripe":
            pay.stripe_refund((order.get("meta") or {}).get("payment_intent", ""), amount_cents, order_id=order["order_id"])
        elif provider == "paypal":
            pay.paypal_refund((order.get("meta") or {}).get("capture_id", ""), amount_cents, order_id=order["order_id"])
        else:
            raise RuntimeError("store purchases are refunded by the store")
    except (RuntimeError, OSError, ValueError) as exc:
        logger.error("provider refund failed order=%s: %s", order.get("order_id"), exc)
        raise HTTPException(status_code=503, detail="We could not complete the refund with the payment provider. Nothing was changed; please try again or contact support.") from exc


@router.post("/api/studio/account/purchases/{order_id}/refund-request")
def refund_request(order_id: str, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """Self-service refund: rule-checked automatically, otherwise routed to a person. Never a silent 'no'."""
    _same_origin(request)
    who = _require_caller(authorization, request)
    store = get_store()
    order = _owned_order(store, who, order_id)
    verdict = refunds.evaluate(order, progress_pct=_progress_pct(store, order))
    if not (verdict["eligible"] and verdict["auto"]):
        if verdict["reason"] not in (refunds.NOT_PAID, refunds.STORE_PURCHASE):
            store.set_meta(order_id, refund_requested={"reason": verdict["reason"], "by": account_id(who), "at": time.time()})
            store.audit("refund_requested", order_id=order_id, account_id=account_id(who), reason=verdict["reason"])
        return {"refunded": False, "routed_to_support": verdict["reason"] not in (refunds.NOT_PAID, refunds.STORE_PURCHASE),
                "reason": verdict["reason"], "message": verdict["message"]}
    _provider_refund(order, int(order["total_cents"]))
    store.mark_refunded(order_id, reason="customer_request", by=account_id(who), amount_cents=int(order["total_cents"]))
    return {"refunded": True, "credit_note_url": f"/api/studio/account/receipts/{order_id}.html?type=credit-note",
            "message": "Your refund is on its way. Your access to the course has ended."}


class AdminRefundRequest(BaseModel):
    reason: str = "admin_refund"
    amount_cents: Optional[int] = None


@router.post("/api/studio/admin/purchases/{order_id}/refund")
def admin_refund(order_id: str, req: AdminRefundRequest, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """Operator refund through the provider API. Verified admin only; idempotent; audited."""
    _same_origin(request)
    who = _require_caller(authorization, request)
    if who.get("is_admin") is not True:
        raise HTTPException(status_code=403, detail="Only an admin can refund a purchase.")
    store = get_store()
    order = store.get(order_id)
    if order is None:
        raise HTTPException(status_code=404, detail="We could not find that purchase.")
    if order["status"] != "paid":
        return {"refunded": False, "already": True, "status": order["status"]}
    amount = int(req.amount_cents if req.amount_cents is not None else order["total_cents"])
    if not 0 < amount <= int(order["total_cents"]):
        raise HTTPException(status_code=422, detail="That refund amount is not valid.")
    _provider_refund(order, amount)
    store.mark_refunded(order_id, reason=req.reason[:80], by=account_id(who), amount_cents=amount)
    return {"refunded": True, "order_id": order_id, "amount_cents": amount}
