"""Receipts and credit notes for course purchases. DRAFT wording for counsel review; seller details are configuration.

One receipt per order (idempotent: the same order always renders the same receipt). It shows the order number, UTC and local
time, the buyer's account email, the item, price, tax line(s), total, the payment method TYPE (card last four only, never a
full number), the seller's legal details, the refund-policy link and the AI-assisted-instruction disclaimer, plus a short
verification code (HMAC) so a copy can be checked against our record. A refunded order also gets a credit note.

Store purchases (Apple, Google): the store sends its own receipt; ours is only our entitlement record and says so.

Config (names only): SELLER_LEGAL_NAME, SELLER_ADDRESS, SELLER_SUPPORT_EMAIL, SELLER_PERMIT_NUMBER, SELLER_TIMEZONE
(default America/Los_Angeles), REFUND_POLICY_URL, TERMS_URL, COURSE_DMV_DISCLAIMER, RECEIPT_SIGNING_KEY (falls back to
AUTH_SIGNING_KEY), SMTP_HOST / SMTP_PORT / SMTP_USER / SMTP_PASSWORD / SMTP_FROM (email; without SMTP_HOST nothing is sent).
"""

from __future__ import annotations

import hashlib
import hmac
import html
import io
import os
import smtplib
import time
from datetime import datetime, timezone
from email.message import EmailMessage
from typing import Any, Callable, Mapping, Optional

DEFAULT_DMV_DISCLAIMER = (
    "AI-assisted instruction. This course is not a DMV-approved or DMV-licensed driver education course, and completing it "
    "does not satisfy California licensing requirements, unless the course page says otherwise."
)
PLACEHOLDER = "[to be set by the seller]"
_PAYMENT_TYPES = {"stripe": "Card", "paypal": "PayPal", "apple": "Apple App Store", "google": "Google Play"}


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, "").strip() or default


def disclaimer_text() -> str:
    return _env("COURSE_DMV_DISCLAIMER", DEFAULT_DMV_DISCLAIMER)


def seller() -> dict[str, str]:
    return {
        "legal_name": _env("SELLER_LEGAL_NAME", PLACEHOLDER),
        "address": _env("SELLER_ADDRESS", PLACEHOLDER),
        "support_email": _env("SELLER_SUPPORT_EMAIL", PLACEHOLDER),
        "permit_number": _env("SELLER_PERMIT_NUMBER", PLACEHOLDER),
    }


def money(cents: int, currency: str = "usd") -> str:
    sign = "-" if int(cents) < 0 else ""
    value = abs(int(cents))
    prefix = "$" if currency.lower() == "usd" else ""
    suffix = "" if prefix else f" {currency.upper()}"
    return f"{sign}{prefix}{value // 100}.{value % 100:02d}{suffix}"


def _signing_key() -> bytes:
    return (_env("RECEIPT_SIGNING_KEY") or _env("AUTH_SIGNING_KEY", "dev-receipt-key")).encode()


def verification_code(order: Mapping[str, Any], kind: str = "receipt") -> str:
    """Short HMAC over the facts a receipt states, so a copy can be checked against our record."""
    parts = [kind, str(order.get("order_id")), str(order.get("account_id")), str(order.get("total_cents")),
             str(int(float(order.get("created_at") or 0)))]
    if kind == "credit_note":
        parts.append(str((order.get("refunded") or order.get("revoked") or {}).get("at", "")))
    return hmac.new(_signing_key(), "|".join(parts).encode(), hashlib.sha256).hexdigest()[:16].upper()


def _local_time(ts: float) -> tuple[str, str]:
    utc = datetime.fromtimestamp(ts, tz=timezone.utc)
    zone_name = _env("SELLER_TIMEZONE", "America/Los_Angeles")
    try:
        from zoneinfo import ZoneInfo

        local = utc.astimezone(ZoneInfo(zone_name))
    except Exception:  # noqa: BLE001 - an unknown zone name falls back to UTC rather than failing the receipt
        local, zone_name = utc, "UTC"
    return utc.strftime("%Y-%m-%d %H:%M UTC"), f"{local.strftime('%Y-%m-%d %H:%M')} {zone_name}"


def item_label(course_id: str) -> str:
    try:
        from aoep_shared.course_studio_access import purchasable_course

        course = purchasable_course(course_id)
    except Exception:  # noqa: BLE001
        course = None
    if not course:
        return f"Full course: {course_id}"
    sub = f" ({course['subtitle']})" if course.get("subtitle") else ""
    return f"Full course: {course['title']}{sub}"


def build_receipt(order: Mapping[str, Any], kind: str = "receipt") -> dict[str, Any]:
    """The receipt (or credit note) as data. Never includes more than the last four card digits."""
    currency = str(order.get("currency") or "usd")
    utc, local = _local_time(float(order.get("created_at") or 0))
    provider = str(order.get("provider") or "").lower()
    method = _PAYMENT_TYPES.get(provider, provider.title() or "Payment")
    last4 = str(order.get("last4") or "")[-4:]
    if last4 and provider == "stripe":
        method += f" ending {last4}"
    lines = [{"description": item_label(str(order.get("course_id") or "")), "amount": money(order.get("amount_cents", 0), currency)}]
    if int(order.get("tax_cents") or 0):
        lines.append({"description": _env("COURSE_TAX_LABEL", "Sales tax"), "amount": money(order["tax_cents"], currency)})
    receipt: dict[str, Any] = {
        "kind": kind, "order_id": order.get("order_id"), "date_utc": utc, "date_local": local,
        "buyer_email": order.get("email") or "", "lines": lines, "total": money(order.get("total_cents", 0), currency),
        "payment_method": method, "seller": seller(),
        "refund_policy_url": _env("REFUND_POLICY_URL", "/legal/refund-policy"), "terms_url": _env("TERMS_URL", "/legal/terms-of-sale"),
        "disclaimer": disclaimer_text(), "code": verification_code(order, kind),
        "store_note": ("This is our record of your entitlement. The App Store or Google Play sends its own receipt for the payment."
                       if provider in ("apple", "google") else ""),
    }
    if kind == "credit_note":
        ended = order.get("refunded") or order.get("revoked") or {}
        r_utc, r_local = _local_time(float(ended.get("at") or 0))
        receipt.update(refund_amount=money(ended.get("amount_cents", order.get("total_cents", 0)), currency),
                       refund_date_utc=r_utc, refund_date_local=r_local, refund_reason=str(ended.get("reason") or ""))
    return receipt


def render_html(receipt: Mapping[str, Any]) -> str:
    """A self-contained, print-friendly page (Save as PDF works). Everything is escaped."""
    e = lambda value: html.escape(str(value if value is not None else ""))  # noqa: E731
    title = "Credit note" if receipt.get("kind") == "credit_note" else "Receipt"
    s = receipt.get("seller") or {}
    rows = "".join(f"<tr><td>{e(l['description'])}</td><td class=r>{e(l['amount'])}</td></tr>" for l in receipt.get("lines", []))
    credit = ""
    if receipt.get("kind") == "credit_note":
        credit = (f"<p><strong>Refunded:</strong> {e(receipt.get('refund_amount'))} on {e(receipt.get('refund_date_utc'))} "
                  f"({e(receipt.get('refund_date_local'))})</p>")
    store = f"<p class=note>{e(receipt['store_note'])}</p>" if receipt.get("store_note") else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{e(title)} {e(receipt.get('order_id'))}</title>
<style>body{{font:15px/1.5 system-ui,sans-serif;color:#111;max-width:720px;margin:24px auto;padding:0 16px}}
h1{{margin:0 0 4px}}table{{width:100%;border-collapse:collapse;margin:12px 0}}td{{padding:6px 0;border-bottom:1px solid #ddd}}
.r{{text-align:right}}.total td{{font-weight:700;border-top:2px solid #111}}.note,.small{{color:#555;font-size:13px}}
@media print{{a{{color:inherit;text-decoration:none}}}}</style></head><body>
<h1>{e(title)}</h1><p class=small>DRAFT wording pending legal review</p>
<p><strong>Order number:</strong> {e(receipt.get('order_id'))}<br><strong>Date:</strong> {e(receipt.get('date_utc'))} ({e(receipt.get('date_local'))})<br>
<strong>Account email:</strong> {e(receipt.get('buyer_email'))}<br><strong>Payment method:</strong> {e(receipt.get('payment_method'))}</p>
{credit}<table>{rows}<tr class=total><td>Total</td><td class=r>{e(receipt.get('total'))}</td></tr></table>{store}
<p><strong>Seller:</strong> {e(s.get('legal_name'))}<br>{e(s.get('address'))}<br>Support: {e(s.get('support_email'))}<br>
Seller permit: {e(s.get('permit_number'))}</p>
<p class=small>{e(receipt.get('disclaimer'))}</p>
<p class=small><a href="{e(receipt.get('refund_policy_url'))}">Refund policy</a> · <a href="{e(receipt.get('terms_url'))}">Terms of sale</a><br>
Verification code: {e(receipt.get('code'))}</p></body></html>"""


def render_pdf(receipt: Mapping[str, Any]) -> Optional[bytes]:
    """A simple PDF, or None when reportlab is not installed (the HTML page prints to PDF in any browser)."""
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import getSampleStyleSheet
        from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table
    except ImportError:
        return None
    styles = getSampleStyleSheet()
    esc = lambda value: html.escape(str(value if value is not None else ""))  # noqa: E731
    s = receipt.get("seller") or {}
    story: list[Any] = [Paragraph("Credit note" if receipt.get("kind") == "credit_note" else "Receipt", styles["Title"]),
                        Paragraph("DRAFT wording pending legal review", styles["Italic"]), Spacer(1, 8),
                        Paragraph(f"<b>Order number:</b> {esc(receipt.get('order_id'))}", styles["Normal"]),
                        Paragraph(f"<b>Date:</b> {esc(receipt.get('date_utc'))} ({esc(receipt.get('date_local'))})", styles["Normal"]),
                        Paragraph(f"<b>Account email:</b> {esc(receipt.get('buyer_email'))}", styles["Normal"]),
                        Paragraph(f"<b>Payment method:</b> {esc(receipt.get('payment_method'))}", styles["Normal"]), Spacer(1, 10)]
    if receipt.get("kind") == "credit_note":
        story += [Paragraph(f"<b>Refunded:</b> {esc(receipt.get('refund_amount'))} on {esc(receipt.get('refund_date_utc'))}", styles["Normal"]), Spacer(1, 6)]
    table = [[l["description"], l["amount"]] for l in receipt.get("lines", [])] + [["Total", receipt.get("total")]]
    story += [Table(table, colWidths=[360, 100]), Spacer(1, 10)]
    if receipt.get("store_note"):
        story += [Paragraph(esc(receipt["store_note"]), styles["Normal"]), Spacer(1, 6)]
    story += [Paragraph(f"<b>Seller:</b> {esc(s.get('legal_name'))}, {esc(s.get('address'))}. Support: {esc(s.get('support_email'))}. "
                        f"Seller permit: {esc(s.get('permit_number'))}", styles["Normal"]), Spacer(1, 6),
              Paragraph(esc(receipt.get("disclaimer")), styles["Normal"]), Spacer(1, 6),
              Paragraph(f"Refund policy: {esc(receipt.get('refund_policy_url'))} · Terms: {esc(receipt.get('terms_url'))}", styles["Normal"]),
              Paragraph(f"Verification code: {esc(receipt.get('code'))}", styles["Normal"])]
    buffer = io.BytesIO()
    SimpleDocTemplate(buffer, pagesize=letter, title=f"Receipt {receipt.get('order_id')}").build(story)
    return buffer.getvalue()


def email_configured() -> bool:
    return bool(_env("SMTP_HOST"))


def send_receipt_email(
    receipt: Mapping[str, Any],
    to_email: str,
    *,
    smtp_factory: Callable[..., Any] = smtplib.SMTP,
) -> dict[str, Any]:
    """Send the receipt by SMTP when SMTP_HOST is configured; otherwise report that nothing was sent (no silent success)."""
    if not to_email:
        return {"sent": False, "reason": "no email address on the account"}
    if not email_configured():
        return {"sent": False, "reason": "email sending is not configured (set SMTP_HOST)"}
    msg = EmailMessage()
    msg["Subject"] = f"Your receipt {receipt.get('order_id')}"
    msg["From"] = _env("SMTP_FROM", _env("SELLER_SUPPORT_EMAIL", "receipts@localhost"))
    msg["To"] = to_email
    msg.set_content(f"Receipt {receipt.get('order_id')}: {receipt.get('total')}. Open the HTML part for the full receipt.")
    msg.add_alternative(render_html(receipt), subtype="html")
    pdf = render_pdf(receipt)
    if pdf:
        msg.add_attachment(pdf, maintype="application", subtype="pdf", filename=f"receipt-{receipt.get('order_id')}.pdf")
    try:
        with smtp_factory(_env("SMTP_HOST"), int(_env("SMTP_PORT", "587")), timeout=15) as client:
            if _env("SMTP_USER"):
                client.starttls()
                client.login(_env("SMTP_USER"), _env("SMTP_PASSWORD"))
            client.send_message(msg)
    except (OSError, smtplib.SMTPException) as exc:
        return {"sent": False, "reason": f"email failed: {exc.__class__.__name__}"}
    return {"sent": True, "reason": ""}
