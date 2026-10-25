"""Verify App Store and Google Play course purchases on the SERVER. The phone's word is never enough.

Apple (StoreKit 2): the app sends the signed transaction (a JWS). We verify its x5c certificate chain against Apple's Root CA
(APPLE_ROOT_CA_PEM / APPLE_ROOT_CA_PEM_FILE: download "Apple Root CA - G3" from https://www.apple.com/certificateauthority/),
the Apple certificate-extension OIDs, validity dates, then the ES256 signature. Then bundle id, product, environment, revocation
and the appAccountToken (a UUID derived from our account id, set by the app at purchase) must all match. App Store Server
Notifications V2 (REFUND / REVOKE) use the same verification and revoke access.

Google Play: the app sends productId + purchaseToken. We call the Play Developer API (purchases.products.get) with a service
account, require purchaseState 0 (purchased), require the obfuscated account id to be ours, record the order, then
acknowledge the purchase (Google refunds unacknowledged purchases after 3 days). Real-time developer notifications arrive on a
Pub/Sub push endpoint guarded by a shared secret; voided purchases revoke access.

Both map to the SAME ledger as web purchases (aoep_shared.purchases): provider "apple" or "google", one reference one
account, idempotent, refunds revoke. A purchase token used by another account is refused.

Config (NAMES ONLY): IAP_PRODUCTS_JSON {"drivers-ed": {"apple": "<product id>", "google": "<product id>"}}, APPLE_BUNDLE_ID,
APPLE_ROOT_CA_PEM | APPLE_ROOT_CA_PEM_FILE, IAP_ALLOW_SANDBOX (default 1: App Review tests with sandbox purchases against
production; such orders are marked environment=sandbox in the ledger), GOOGLE_PLAY_PACKAGE_NAME,
GOOGLE_PLAY_SERVICE_ACCOUNT_JSON (the JSON, or a path to it), GOOGLE_RTDN_SECRET, IAP_ACCOUNT_SALT.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from typing import Any, Callable, Optional

APPLE_LEAF_OID = "1.2.840.113635.100.6.11.1"
APPLE_INTERMEDIATE_OID = "1.2.840.113635.100.6.2.1"
_ANDROID_SCOPE = "https://www.googleapis.com/auth/androidpublisher"
_TOKEN_URI = "https://oauth2.googleapis.com/token"
_PLAY = "https://androidpublisher.googleapis.com/androidpublisher/v3/applications"


class StoreVerificationError(Exception):
    """A store purchase could not be verified. `code` is stable; `message` is safe to show."""

    def __init__(self, code: str, message: str = "") -> None:
        super().__init__(message or code)
        self.code = code
        self.message = message or code


class StorePending(Exception):
    """The store says the payment is not final yet (e.g. a pending Google Play purchase): grant nothing, try again later."""


# ---------------------------------------------------------------- config
def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def products() -> dict[str, dict[str, str]]:
    try:
        data = json.loads(_env("IAP_PRODUCTS_JSON", "{}"))
    except ValueError:
        return {}
    return {str(k): {str(p): str(v) for p, v in (row or {}).items()} for k, row in data.items()} if isinstance(data, dict) else {}


def course_for_product(platform: str, product_id: str) -> Optional[str]:
    for course_id, row in products().items():
        if row.get(platform) == product_id:
            return course_id
    return None


def product_ids(course_id: str) -> dict[str, str]:
    return dict(products().get(course_id, {}))


def _salt() -> str:
    return _env("IAP_ACCOUNT_SALT", _env("AUTH_SIGNING_KEY", "dev-iap-salt"))


def apple_account_token(account_id: str) -> str:
    """The UUID the app passes as appAccountToken so Apple signs it into the transaction (binds the purchase to the account)."""
    digest = hashlib.sha256(f"aoep-iap-apple|{_salt()}|{account_id}".encode()).digest()
    return str(uuid.UUID(bytes=digest[:16], version=5)).lower()


def google_account_token(account_id: str) -> str:
    """The obfuscatedAccountId the app passes to Play Billing (no personal data, 32 hex characters)."""
    return hashlib.sha256(f"aoep-iap-google|{_salt()}|{account_id}".encode()).hexdigest()[:32]


def allow_sandbox() -> bool:
    return _env("IAP_ALLOW_SANDBOX", "1") != "0"


# ---------------------------------------------------------------- Apple
def _root_pem() -> bytes:
    inline = _env("APPLE_ROOT_CA_PEM")
    if inline:
        return inline.encode()
    path = _env("APPLE_ROOT_CA_PEM_FILE")
    if path and os.path.isfile(path):
        with open(path, "rb") as handle:
            return handle.read()
    raise StoreVerificationError("not_configured", "App Store purchases are not set up on the server yet.")


def _cert_sig_ok(child: Any, issuer: Any) -> bool:
    from cryptography.exceptions import InvalidSignature
    from cryptography.hazmat.primitives.asymmetric import ec, padding

    key = issuer.public_key()
    try:
        if isinstance(key, ec.EllipticCurvePublicKey):
            key.verify(child.signature, child.tbs_certificate_bytes, ec.ECDSA(child.signature_hash_algorithm))
        else:
            key.verify(child.signature, child.tbs_certificate_bytes, padding.PKCS1v15(), child.signature_hash_algorithm)
    except (InvalidSignature, ValueError, TypeError):
        return False
    return True


def _has_oid(cert: Any, dotted: str) -> bool:
    return any(ext.oid.dotted_string == dotted for ext in cert.extensions)


def verify_apple_jws(jws: str, *, root_pem: Optional[bytes] = None, now: Callable[[], float] = time.time, require_oids: bool = True) -> dict[str, Any]:
    """Verify an Apple-signed JWS (transaction or notification) and return its payload."""
    import jwt
    from cryptography import x509
    from cryptography.hazmat.primitives import serialization

    try:
        header = jwt.get_unverified_header(jws)
    except jwt.PyJWTError as exc:
        raise StoreVerificationError("bad_signature", "That purchase receipt is not valid.") from exc
    chain = header.get("x5c") or []
    if header.get("alg") != "ES256" or len(chain) != 3:
        raise StoreVerificationError("bad_signature", "That purchase receipt is not valid.")
    try:
        leaf, inter, top = [x509.load_der_x509_certificate(base64.b64decode(c)) for c in chain]
        trusted = x509.load_pem_x509_certificate(root_pem if root_pem is not None else _root_pem())
    except (ValueError, TypeError) as exc:
        raise StoreVerificationError("bad_chain", "That purchase receipt is not valid.") from exc
    der = serialization.Encoding.DER
    if top.public_bytes(der) != trusted.public_bytes(der):
        raise StoreVerificationError("bad_chain", "That purchase receipt did not come from Apple.")
    if not (_cert_sig_ok(leaf, inter) and _cert_sig_ok(inter, trusted)):
        raise StoreVerificationError("bad_chain", "That purchase receipt did not come from Apple.")
    moment = datetime.fromtimestamp(now(), tz=timezone.utc)
    for cert in (leaf, inter, trusted):
        if not (cert.not_valid_before_utc <= moment <= cert.not_valid_after_utc):
            raise StoreVerificationError("expired_cert", "That purchase receipt is not valid.")
    if require_oids and not (_has_oid(leaf, APPLE_LEAF_OID) and _has_oid(inter, APPLE_INTERMEDIATE_OID)):
        raise StoreVerificationError("bad_chain", "That purchase receipt did not come from Apple.")
    try:
        return jwt.decode(jws, leaf.public_key(), algorithms=["ES256"],
                          options={"verify_exp": False, "verify_aud": False, "verify_iss": False, "verify_nbf": False, "verify_iat": False})
    except jwt.PyJWTError as exc:
        raise StoreVerificationError("bad_signature", "That purchase receipt is not valid.") from exc


def apple_transaction_to_paid(payload: dict[str, Any], *, account_id: str) -> dict[str, Any]:
    """Validate a verified Apple transaction for THIS account and normalize it for the ledger."""
    bundle = _env("APPLE_BUNDLE_ID")
    if not bundle:
        raise StoreVerificationError("not_configured", "App Store purchases are not set up on the server yet.")
    if payload.get("bundleId") != bundle:
        raise StoreVerificationError("wrong_app", "That purchase is for a different app.")
    course_id = course_for_product("apple", str(payload.get("productId") or ""))
    if not course_id:
        raise StoreVerificationError("unknown_product", "That product is not a course we sell.")
    environment = str(payload.get("environment") or "Production")
    if environment.lower() == "sandbox" and not allow_sandbox():
        raise StoreVerificationError("sandbox_not_allowed", "Test purchases are not accepted.")
    if payload.get("revocationDate"):
        raise StoreVerificationError("revoked", "That purchase was refunded.")
    token = str(payload.get("appAccountToken") or "").lower()
    if token and token != apple_account_token(account_id):
        raise StoreVerificationError("account_mismatch", "That purchase belongs to another account.")
    if payload.get("type") and payload.get("type") != "Non-Consumable":
        raise StoreVerificationError("wrong_type", "That purchase is not a course.")
    original = str(payload.get("originalTransactionId") or payload.get("transactionId") or "")
    if not original:
        raise StoreVerificationError("bad_signature", "That purchase receipt is not valid.")
    try:
        cents = int(round(float(payload.get("price")) / 10.0)) if payload.get("price") is not None else None
    except (TypeError, ValueError):
        cents = None
    return {
        "account_id": account_id, "course_id": course_id, "provider": "apple", "provider_ref": original,
        "amount_cents": cents, "tax_cents": 0, "currency": str(payload.get("currency") or "usd").lower(), "email": "",
        "meta": {"environment": environment, "transaction_id": str(payload.get("transactionId") or ""),
                 "product_id": str(payload.get("productId") or ""), "token_bound": bool(token)},
    }


def decode_apple_notification(signed_payload: str, *, root_pem: Optional[bytes] = None, now: Callable[[], float] = time.time) -> dict[str, Any]:
    """App Store Server Notification V2: verify the outer JWS and the transaction inside it."""
    outer = verify_apple_jws(signed_payload, root_pem=root_pem, now=now)
    data = outer.get("data") or {}
    bundle = _env("APPLE_BUNDLE_ID")
    if bundle and data.get("bundleId") and data["bundleId"] != bundle:
        raise StoreVerificationError("wrong_app", "That notification is for a different app.")
    transaction: dict[str, Any] = {}
    if data.get("signedTransactionInfo"):
        transaction = verify_apple_jws(data["signedTransactionInfo"], root_pem=root_pem, now=now)
    return {"type": str(outer.get("notificationType") or ""), "subtype": str(outer.get("subtype") or ""),
            "environment": str(data.get("environment") or ""), "transaction": transaction}


APPLE_REVOKING = {"REFUND", "REVOKE"}


# ---------------------------------------------------------------- Google
def _request(url: str, *, method: str = "GET", data: Optional[bytes] = None, headers: Optional[dict[str, str]] = None,
             opener: Callable[..., Any] = urllib.request.urlopen) -> dict[str, Any]:
    request = urllib.request.Request(url, data=data, headers=headers or {}, method=method)
    try:
        with opener(request, timeout=20) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raise StoreVerificationError("store_error" if exc.code >= 500 else "store_rejected",
                                     "We could not confirm that purchase with Google Play.") from exc
    except (urllib.error.URLError, OSError) as exc:
        raise StoreVerificationError("store_error", "We could not reach Google Play. Please try again.") from exc
    return json.loads(raw) if raw else {}


def service_account() -> dict[str, Any]:
    raw = _env("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON")
    if raw and os.path.isfile(raw):
        with open(raw, encoding="utf-8") as handle:
            raw = handle.read()
    try:
        info = json.loads(raw) if raw else {}
    except ValueError:
        info = {}
    if not (info.get("client_email") and info.get("private_key")):
        raise StoreVerificationError("not_configured", "Google Play purchases are not set up on the server yet.")
    return info


_TOKEN_CACHE: dict[str, Any] = {"value": "", "exp": 0.0}


def google_access_token(*, opener: Callable[..., Any] = urllib.request.urlopen, now: Callable[[], float] = time.time) -> str:
    import jwt

    if _TOKEN_CACHE["value"] and _TOKEN_CACHE["exp"] > now() + 60:
        return str(_TOKEN_CACHE["value"])
    info = service_account()
    issued = int(now())
    assertion = jwt.encode(
        {"iss": info["client_email"], "scope": _ANDROID_SCOPE, "aud": info.get("token_uri") or _TOKEN_URI, "iat": issued, "exp": issued + 3300},
        info["private_key"], algorithm="RS256")
    body = urllib.parse.urlencode({"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}).encode()
    token = _request(info.get("token_uri") or _TOKEN_URI, method="POST", data=body,
                     headers={"Content-Type": "application/x-www-form-urlencoded"}, opener=opener)
    value = str(token.get("access_token") or "")
    if not value:
        raise StoreVerificationError("store_error", "We could not reach Google Play. Please try again.")
    _TOKEN_CACHE.update(value=value, exp=now() + int(token.get("expires_in") or 3000))
    return value


def _package() -> str:
    package = _env("GOOGLE_PLAY_PACKAGE_NAME")
    if not package:
        raise StoreVerificationError("not_configured", "Google Play purchases are not set up on the server yet.")
    return package


def google_get_purchase(product_id: str, purchase_token: str, *, opener: Callable[..., Any] = urllib.request.urlopen,
                        now: Callable[[], float] = time.time) -> dict[str, Any]:
    url = f"{_PLAY}/{urllib.parse.quote(_package(), safe='')}/purchases/products/{urllib.parse.quote(product_id, safe='')}/tokens/{urllib.parse.quote(purchase_token, safe='')}"
    return _request(url, headers={"Authorization": f"Bearer {google_access_token(opener=opener, now=now)}"}, opener=opener)


def google_acknowledge(product_id: str, purchase_token: str, *, opener: Callable[..., Any] = urllib.request.urlopen,
                       now: Callable[[], float] = time.time) -> None:
    url = (f"{_PLAY}/{urllib.parse.quote(_package(), safe='')}/purchases/products/{urllib.parse.quote(product_id, safe='')}"
           f"/tokens/{urllib.parse.quote(purchase_token, safe='')}:acknowledge")
    _request(url, method="POST", data=b"{}", headers={"Authorization": f"Bearer {google_access_token(opener=opener, now=now)}",
                                                     "Content-Type": "application/json"}, opener=opener)


def google_purchase_to_paid(info: dict[str, Any], *, account_id: str, product_id: str, purchase_token: str) -> dict[str, Any]:
    course_id = course_for_product("google", product_id)
    if not course_id:
        raise StoreVerificationError("unknown_product", "That product is not a course we sell.")
    state = info.get("purchaseState")
    if state == 2:
        raise StorePending("The payment is still pending.")
    if state != 0:
        raise StoreVerificationError("not_purchased", "That purchase was cancelled or refunded.")
    bound = str(info.get("obfuscatedExternalAccountId") or "")
    if bound and bound != google_account_token(account_id):
        raise StoreVerificationError("account_mismatch", "That purchase belongs to another account.")
    test = info.get("purchaseType") == 0
    if test and not allow_sandbox():
        raise StoreVerificationError("sandbox_not_allowed", "Test purchases are not accepted.")
    return {
        "account_id": account_id, "course_id": course_id, "provider": "google", "provider_ref": purchase_token,
        "amount_cents": None, "tax_cents": 0, "currency": "usd", "email": "",
        "meta": {"environment": "sandbox" if test else "production", "order_id": str(info.get("orderId") or ""),
                 "product_id": product_id, "token_bound": bool(bound), "acknowledged": info.get("acknowledgementState") == 1},
    }


def decode_rtdn(body: dict[str, Any]) -> dict[str, Any]:
    """A Pub/Sub push message from Google Play: the notification type and the purchase token it is about."""
    data = ((body or {}).get("message") or {}).get("data") or ""
    try:
        payload = json.loads(base64.b64decode(data + "=" * (-len(data) % 4)).decode("utf-8"))
    except (ValueError, TypeError) as exc:
        raise StoreVerificationError("bad_payload", "That notification is not valid.") from exc
    if payload.get("testNotification") is not None:
        return {"kind": "test", "token": ""}
    voided = payload.get("voidedPurchaseNotification")
    if voided:
        return {"kind": "voided", "token": str(voided.get("purchaseToken") or "")}
    one_time = payload.get("oneTimeProductNotification")
    if one_time:
        # 1 = purchased, 2 = canceled
        return {"kind": "canceled" if one_time.get("notificationType") == 2 else "purchased", "token": str(one_time.get("purchaseToken") or ""),
                "product_id": str(one_time.get("sku") or "")}
    return {"kind": "ignored", "token": ""}
