"""Store purchases: verified on the server, bound to the account, idempotent, revoked on refund. No store is contacted."""

from __future__ import annotations

import base64
import datetime as dt
import json
import time

import jwt
import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier
from fastapi.testclient import TestClient

from aoep_shared import store_iap as iap
from aoep_shared.purchases import PurchaseStore, _MemoryBackend

COURSE = "drivers-ed"
ALICE = {"id": "acct-alice", "email": "a@example.com"}
BOB = {"id": "acct-bob", "email": "b@example.com"}
USERS = {"Bearer alice": ALICE, "Bearer bob": BOB}


def _name(cn):
    return x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, cn)])


def _cert(subject, issuer_name, key, signer, oid=None, ca=False):
    now = dt.datetime.now(dt.timezone.utc)
    b = (x509.CertificateBuilder().subject_name(_name(subject)).issuer_name(issuer_name).public_key(key.public_key())
         .serial_number(x509.random_serial_number()).not_valid_before(now - dt.timedelta(days=1)).not_valid_after(now + dt.timedelta(days=30)))
    if oid:
        b = b.add_extension(x509.UnrecognizedExtension(ObjectIdentifier(oid), b"\x05\x00"), critical=False)
    return b.sign(signer, hashes.SHA256())


class Pki:
    def __init__(self):
        self.root_key, self.inter_key, self.leaf_key = (ec.generate_private_key(ec.SECP256R1()) for _ in range(3))
        self.root = _cert("Test Root", _name("Test Root"), self.root_key, self.root_key)
        self.inter = _cert("Test Inter", _name("Test Root"), self.inter_key, self.root_key, iap.APPLE_INTERMEDIATE_OID)
        self.leaf = _cert("Test Leaf", _name("Test Inter"), self.leaf_key, self.inter_key, iap.APPLE_LEAF_OID)
        self.root_pem = self.root.public_bytes(serialization.Encoding.PEM)

    def sign(self, payload, chain=None):
        der = serialization.Encoding.DER
        certs = chain or [self.leaf, self.inter, self.root]
        return jwt.encode(payload, self.leaf_key, algorithm="ES256",
                          headers={"x5c": [base64.b64encode(c.public_bytes(der)).decode() for c in certs]})


@pytest.fixture
def env(monkeypatch):
    import theodore_course_studio.caller_claims as claims
    import theodore_course_studio.pay_routes as routes
    from theodore_course_studio.main import app

    pki = Pki()
    store = PurchaseStore(_MemoryBackend())
    monkeypatch.setattr(routes, "_store_factory", lambda: store)
    monkeypatch.setattr(claims, "_fetch_me", lambda auth: USERS.get(auth))
    claims._CACHE.clear()
    monkeypatch.setenv("APPLE_ROOT_CA_PEM", pki.root_pem.decode())
    monkeypatch.setenv("APPLE_BUNDLE_ID", "com.example.salareen")
    monkeypatch.setenv("IAP_PRODUCTS_JSON", json.dumps({COURSE: {"apple": "com.example.full", "google": "full_course"}}))
    monkeypatch.setenv("GOOGLE_RTDN_SECRET", "rtdn-secret")
    monkeypatch.setenv("GOOGLE_PLAY_PACKAGE_NAME", "com.example.salareen")
    return {"pki": pki, "store": store, "client": TestClient(app), "mp": monkeypatch}


def txn(account="acct-alice", **over):
    base = {"bundleId": "com.example.salareen", "productId": "com.example.full", "originalTransactionId": "2000001",
            "transactionId": "2000001", "environment": "Sandbox", "type": "Non-Consumable",
            "appAccountToken": iap.apple_account_token(account), "price": 19990, "currency": "USD"}
    base.update(over)
    return base


def verify(env, signed, who="Bearer alice"):
    return env["client"].post("/api/studio/iap/apple/verify", json={"signed_transaction": signed}, headers={"Authorization": who})


def test_apple_purchase_unlocks_and_is_idempotent(env):
    signed = env["pki"].sign(txn())
    first = verify(env, signed)
    assert first.status_code == 200 and first.json()["created"] is True
    assert verify(env, signed).json()["created"] is False
    assert env["store"].is_paid("acct-alice", COURSE)
    assert len(env["store"].list_for_account("acct-alice")) == 1


def test_apple_requires_login(env):
    r = env["client"].post("/api/studio/iap/apple/verify", json={"signed_transaction": env["pki"].sign(txn())})
    assert r.status_code == 401


def test_apple_forged_chain_is_refused(env):
    other = Pki()
    r = verify(env, other.sign(txn()))
    assert r.status_code == 400 and not env["store"].is_paid("acct-alice", COURSE)


def test_apple_tampered_payload_is_refused(env):
    signed = env["pki"].sign(txn())
    head, _, sig = signed.split(".")
    forged = base64.urlsafe_b64encode(json.dumps(txn(productId="com.example.full", price=1)).encode()).rstrip(b"=").decode()
    assert verify(env, f"{head}.{forged}.{sig}").status_code == 400


def test_apple_self_signed_leaf_without_apple_oids_is_refused(env):
    pki = env["pki"]
    plain = _cert("Leaf", _name("Test Inter"), pki.leaf_key, pki.inter_key)
    assert verify(env, pki.sign(txn(), chain=[plain, pki.inter, pki.root])).status_code == 400


def test_apple_wrong_bundle_product_and_revoked(env):
    assert verify(env, env["pki"].sign(txn(bundleId="com.evil"))).status_code == 400
    assert verify(env, env["pki"].sign(txn(productId="com.other"))).status_code == 400
    assert verify(env, env["pki"].sign(txn(revocationDate=1700000000000))).status_code == 402
    assert not env["store"].is_paid("acct-alice", COURSE)


def test_apple_token_for_another_account_is_refused(env):
    signed = env["pki"].sign(txn(account="acct-alice"))
    assert verify(env, signed, who="Bearer bob").status_code == 409
    assert not env["store"].is_paid("acct-bob", COURSE)


def test_apple_receipt_without_token_cannot_move_between_accounts(env):
    signed = env["pki"].sign(txn(appAccountToken=""))
    assert verify(env, signed).status_code == 200
    assert verify(env, signed, who="Bearer bob").status_code == 409
    assert env["store"].is_paid("acct-alice", COURSE) and not env["store"].is_paid("acct-bob", COURSE)


def test_apple_sandbox_can_be_switched_off(env):
    env["mp"].setenv("IAP_ALLOW_SANDBOX", "0")
    assert verify(env, env["pki"].sign(txn())).status_code == 400


def test_apple_refund_notification_revokes_and_stays_revoked(env):
    verify(env, env["pki"].sign(txn()))
    note = env["pki"].sign({"notificationType": "REFUND", "data": {"bundleId": "com.example.salareen", "environment": "Sandbox",
                                                                  "signedTransactionInfo": env["pki"].sign(txn())}})
    r = env["client"].post("/api/studio/iap/apple/notifications", json={"signedPayload": note})
    assert r.status_code == 200 and not env["store"].is_paid("acct-alice", COURSE)
    again = verify(env, env["pki"].sign(txn()))
    assert not env["store"].is_paid("acct-alice", COURSE), again.text


def test_apple_notification_with_bad_signature_does_nothing(env):
    verify(env, env["pki"].sign(txn()))
    note = Pki().sign({"notificationType": "REFUND", "data": {"signedTransactionInfo": Pki().sign(txn())}})
    assert env["client"].post("/api/studio/iap/apple/notifications", json={"signedPayload": note}).status_code == 400
    assert env["store"].is_paid("acct-alice", COURSE)


def test_products_endpoint_gives_account_tokens(env):
    r = env["client"].get(f"/api/studio/iap/products?course_id={COURSE}", headers={"Authorization": "Bearer alice"})
    assert r.json()["apple_app_account_token"] == iap.apple_account_token("acct-alice")
    assert r.json()["products"]["google"] == "full_course"
    assert env["client"].get(f"/api/studio/iap/products?course_id={COURSE}").status_code == 401


# ---- Google
def play(state=0, ack=0, bound=None, purchase_type=None):
    info = {"purchaseState": state, "acknowledgementState": ack, "orderId": "GPA.1"}
    if bound is not None:
        info["obfuscatedExternalAccountId"] = bound
    if purchase_type is not None:
        info["purchaseType"] = purchase_type
    return info


def google(env, info, who="Bearer alice", token="tok-1"):
    acks = env.setdefault("acks", [])
    env["mp"].setattr(iap, "google_get_purchase", lambda product, tok, **k: info)
    env["mp"].setattr(iap, "google_acknowledge", lambda product, tok, **k: acks.append(tok))
    return env["client"].post("/api/studio/iap/google/verify", json={"product_id": "full_course", "purchase_token": token}, headers={"Authorization": who})


def test_google_purchase_unlocks_and_acknowledges_once(env):
    r = google(env, play(bound=iap.google_account_token("acct-alice")))
    assert r.status_code == 200 and r.json()["acknowledged"] is True and env["acks"] == ["tok-1"]
    assert env["store"].is_paid("acct-alice", COURSE)
    again = google(env, play(ack=1, bound=iap.google_account_token("acct-alice")))
    assert again.json()["created"] is False and env["acks"] == ["tok-1"]


def test_google_pending_cancelled_and_other_account(env):
    assert google(env, play(state=2)).json()["status"] == "pending"
    assert google(env, play(state=1)).status_code == 402
    assert google(env, play(bound=iap.google_account_token("acct-bob"))).status_code == 409
    assert not env["store"].is_paid("acct-alice", COURSE)


def test_google_token_reuse_by_another_account_is_refused(env):
    assert google(env, play()).status_code == 200
    assert google(env, play(), who="Bearer bob").status_code == 409
    assert not env["store"].is_paid("acct-bob", COURSE)


def test_google_unknown_product_and_store_outage(env):
    env["mp"].setattr(iap, "google_get_purchase", lambda *a, **k: (_ for _ in ()).throw(iap.StoreVerificationError("store_error", "down")))
    r = env["client"].post("/api/studio/iap/google/verify", json={"product_id": "full_course", "purchase_token": "t"}, headers={"Authorization": "Bearer alice"})
    assert r.status_code == 503
    assert google(env, play()).status_code == 200
    r = env["client"].post("/api/studio/iap/google/verify", json={"product_id": "nope", "purchase_token": "t2"}, headers={"Authorization": "Bearer alice"})
    assert r.status_code == 400


def test_google_voided_notification_revokes_and_needs_secret(env):
    google(env, play())
    data = base64.b64encode(json.dumps({"voidedPurchaseNotification": {"purchaseToken": "tok-1"}}).encode()).decode()
    body = {"message": {"data": data}}
    assert env["client"].post("/api/studio/iap/google/notifications?token=wrong", json=body).status_code == 403
    assert env["store"].is_paid("acct-alice", COURSE)
    assert env["client"].post("/api/studio/iap/google/notifications?token=rtdn-secret", json=body).status_code == 200
    assert not env["store"].is_paid("acct-alice", COURSE)


def test_google_access_token_exchange_uses_service_account(env):
    from cryptography.hazmat.primitives.asymmetric import rsa
    rsa_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = rsa_key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    env["mp"].setenv("GOOGLE_PLAY_SERVICE_ACCOUNT_JSON", json.dumps({"client_email": "sa@x.iam", "private_key": pem}))
    iap._TOKEN_CACHE.update(value="", exp=0.0)
    seen = []

    class Resp:
        def __init__(self, data): self.data = data
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps(self.data).encode()

    def opener(request, timeout=0):
        seen.append(request.full_url)
        return Resp({"access_token": "ya29", "expires_in": 3600} if "oauth2" in request.full_url else {"purchaseState": 0})

    assert iap.google_get_purchase("full_course", "tok", opener=opener) == {"purchaseState": 0}
    assert any("oauth2.googleapis.com" in u for u in seen) and any("/purchases/products/full_course/tokens/tok" in u for u in seen)
    iap._TOKEN_CACHE.update(value="", exp=0.0)


def test_apple_transaction_id_is_resolved_by_asking_apple(env):
    signed = env["pki"].sign(txn())
    asked = []
    env["mp"].setattr(iap, "apple_get_transaction", lambda tid, **k: asked.append(tid) or signed)
    r = env["client"].post("/api/studio/iap/apple/verify", json={"transaction_id": "2000001"}, headers={"Authorization": "Bearer alice"})
    assert r.status_code == 200 and asked == ["2000001"] and env["store"].is_paid("acct-alice", COURSE)
    assert env["client"].post("/api/studio/iap/apple/verify", json={}, headers={"Authorization": "Bearer alice"}).status_code == 400


def test_apple_server_api_tries_sandbox_after_production_404(env):
    from cryptography.hazmat.primitives.asymmetric import ec as _ec
    key = _ec.generate_private_key(_ec.SECP256R1()).private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    for k, v in {"APPLE_IAP_KEY_ID": "KID", "APPLE_IAP_ISSUER_ID": "ISS", "APPLE_IAP_PRIVATE_KEY": key}.items():
        env["mp"].setenv(k, v)
    import urllib.error
    seen = []

    class Resp:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def read(self): return json.dumps({"signedTransactionInfo": "JWS"}).encode()

    def opener(request, timeout=0):
        seen.append(request.full_url)
        if "sandbox" not in request.full_url:
            raise urllib.error.HTTPError(request.full_url, 404, "nf", {}, None)
        return Resp()

    assert iap.apple_get_transaction("7", opener=opener) == "JWS"
    assert "storekit.itunes" in seen[0] and "storekit-sandbox" in seen[1]
