"""Store purchases (App Store, Google Play) land in the SAME ledger as web purchases. Client receipts are never trusted:
the server verifies with the store, binds to the logged-in account, and records idempotently. See aoep_shared.store_iap."""

from __future__ import annotations

import hmac
import json
import logging
import os
from typing import Any, Optional

from fastapi import APIRouter, Header, HTTPException, Request
from pydantic import BaseModel

from aoep_shared import store_iap as iap
from aoep_shared.course_entitlement import account_id
from aoep_shared.course_studio_access import purchasable_course
from aoep_shared.purchases import PurchaseConflict, PurchaseStore

from . import pay_routes as base

logger = logging.getLogger(__name__)
router = APIRouter()


def _record(store: PurchaseStore, paid: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    course = purchasable_course(paid["course_id"])
    if course is None:
        raise HTTPException(status_code=400, detail="That purchase does not match a course.")
    cents = paid.get("amount_cents")
    try:
        return store.record_paid(
            account_id=paid["account_id"], course_id=paid["course_id"],
            amount_cents=int(cents) if cents else int(course["price_cents"]),
            tax_cents=0, provider=paid["provider"], provider_ref=paid["provider_ref"],
            currency=paid.get("currency", "usd"), email="", meta=paid.get("meta") or {},
        )
    except PurchaseConflict as exc:
        raise HTTPException(status_code=409, detail="That purchase already belongs to another account.") from exc


def _fail(exc: iap.StoreVerificationError) -> HTTPException:
    status = {"store_error": 503, "not_configured": 503, "account_mismatch": 409, "revoked": 402, "not_purchased": 402}.get(exc.code, 400)
    return HTTPException(status_code=status, detail=exc.message)


@router.get("/api/studio/iap/products")
def iap_products(course_id: str, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    """Product ids and the account tokens the app must attach to the purchase (so the store signs them in)."""
    who = base._require_caller(authorization, request)
    ids = iap.product_ids(course_id)
    if not ids:
        raise HTTPException(status_code=404, detail="That course is not sold in the app.")
    account = account_id(who)
    return {"course_id": course_id, "products": ids,
            "apple_app_account_token": iap.apple_account_token(account),
            "google_obfuscated_account_id": iap.google_account_token(account)}


class AppleVerify(BaseModel):
    signed_transaction: str = ""  # StoreKit 2 JWS, when the app can send it
    transaction_id: str = ""      # otherwise the id: the server asks Apple for the signed transaction itself


class GoogleVerify(BaseModel):
    product_id: str
    purchase_token: str


def _result(order: dict[str, Any], created: bool) -> dict[str, Any]:
    return {"status": "paid", "created": created, "order_id": order["order_id"], "course_id": order["course_id"]}


@router.post("/api/studio/iap/apple/verify")
def apple_verify(req: AppleVerify, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    base._same_origin(request)
    who = base._require_caller(authorization, request)
    try:
        signed = req.signed_transaction.strip()
        if not signed:
            if not req.transaction_id.strip():
                raise HTTPException(status_code=400, detail="signed_transaction or transaction_id is required")
            signed = iap.apple_get_transaction(req.transaction_id.strip())
        payload = iap.verify_apple_jws(signed)
        paid = iap.apple_transaction_to_paid(payload, account_id=account_id(who))
    except iap.StoreVerificationError as exc:
        raise _fail(exc) from exc
    order, created = _record(base.get_store(), paid)
    return _result(order, created)


@router.post("/api/studio/iap/google/verify")
def google_verify(req: GoogleVerify, request: Request, authorization: str = Header(default="")) -> dict[str, Any]:
    base._same_origin(request)
    who = base._require_caller(authorization, request)
    try:
        info = iap.google_get_purchase(req.product_id, req.purchase_token)
        paid = iap.google_purchase_to_paid(info, account_id=account_id(who), product_id=req.product_id, purchase_token=req.purchase_token)
    except iap.StorePending:
        return {"status": "pending", "detail": "Your payment is still pending. The course unlocks when it completes."}
    except iap.StoreVerificationError as exc:
        raise _fail(exc) from exc
    order, created = _record(base.get_store(), paid)
    if not (info.get("acknowledgementState") == 1):
        try:
            iap.google_acknowledge(req.product_id, req.purchase_token)
        except iap.StoreVerificationError as exc:
            logger.error("google acknowledge failed (will retry on restore): %s", exc.code)
            return {**_result(order, created), "acknowledged": False}
    return {**_result(order, created), "acknowledged": True}


@router.post("/api/studio/iap/apple/notifications")
async def apple_notifications(request: Request) -> dict[str, Any]:
    """App Store Server Notifications V2. Only refund/revoke act: the signature chain is the authentication."""
    try:
        body = json.loads((await request.body()).decode("utf-8"))
        note = iap.decode_apple_notification(str(body.get("signedPayload") or ""))
    except (ValueError, iap.StoreVerificationError) as exc:
        raise HTTPException(status_code=400, detail="bad notification") from exc
    txn = note["transaction"]
    original = str(txn.get("originalTransactionId") or "")
    if note["type"] in iap.APPLE_REVOKING and original:
        base.get_store().revoke_by_ref("apple", original, reason=f"apple:{note['type']}", by="apple")
    return {"received": True}


@router.post("/api/studio/iap/google/notifications")
async def google_notifications(request: Request, token: str = "") -> dict[str, Any]:
    """Pub/Sub push for Real-time Developer Notifications. The push URL carries a shared secret (GOOGLE_RTDN_SECRET)."""
    secret = os.environ.get("GOOGLE_RTDN_SECRET", "").strip()
    if not secret or not hmac.compare_digest(token, secret):
        raise HTTPException(status_code=403, detail="forbidden")
    try:
        note = iap.decode_rtdn(json.loads((await request.body()).decode("utf-8")))
    except (ValueError, iap.StoreVerificationError) as exc:
        raise HTTPException(status_code=400, detail="bad notification") from exc
    if note["kind"] in {"voided", "canceled"} and note["token"]:
        base.get_store().revoke_by_ref("google", note["token"], reason=f"google:{note['kind']}", by="google")
    return {"received": True}
