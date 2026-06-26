"""Sandbox billing validation (card Luhn, expiry, address).

PCI note: production must use a hosted PSP (Stripe Elements, etc.) — never
persist full PAN/CVV. Local mode validates format only for UX testing.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import List, Optional


def _digits_only(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def luhn_valid(card_number: str) -> bool:
    digits = _digits_only(card_number)
    if len(digits) < 13 or len(digits) > 19:
        return False
    total = 0
    reverse = digits[::-1]
    for i, ch in enumerate(reverse):
        n = int(ch)
        if i % 2 == 1:
            n *= 2
            if n > 9:
                n -= 9
        total += n
    return total % 10 == 0


def validate_card(
    card_number: str,
    exp_month: int,
    exp_year: int,
    cvv: str,
    *,
    now: Optional[datetime] = None,
) -> List[str]:
    """Return human-readable validation errors (empty => ok)."""
    errors: List[str] = []
    pan = _digits_only(card_number)
    if not luhn_valid(pan):
        errors.append("card number failed validation")
    if exp_month < 1 or exp_month > 12:
        errors.append("expiration month must be 1–12")
    if exp_year < 100:
        exp_year += 2000
    clock = now or datetime.now(timezone.utc).replace(tzinfo=None)
    if exp_year < clock.year or (exp_year == clock.year and exp_month < clock.month):
        errors.append("card is expired")
    cvv_digits = _digits_only(cvv)
    if len(cvv_digits) not in (3, 4):
        errors.append("security code must be 3 or 4 digits")
    return errors


_POSTAL_RE = {
    "US": re.compile(r"^\d{5}(-\d{4})?$"),
    "CA": re.compile(r"^[A-Za-z]\d[A-Za-z][ -]?\d[A-Za-z]\d$"),
    "GB": re.compile(r"^[A-Za-z]{1,2}\d[A-Za-z\d]? ?\d[A-Za-z]{2}$"),
}


def validate_billing_address(
    *,
    line1: str,
    city: str,
    postal_code: str,
    country: str,
    state: str = "",
) -> List[str]:
    """Basic address checks for onboarding (not a full geocoder)."""
    errors: List[str] = []
    if not (line1 or "").strip():
        errors.append("street address is required")
    if not (city or "").strip():
        errors.append("city is required")
    cc = (country or "US").strip().upper()[:2]
    if not cc.isalpha() or len(cc) != 2:
        errors.append("country must be a 2-letter code (e.g. US)")
    postal = (postal_code or "").strip()
    if not postal:
        errors.append("postal code is required")
    else:
        pattern = _POSTAL_RE.get(cc)
        if pattern and not pattern.match(postal):
            errors.append(f"postal code format invalid for {cc}")
    if cc in ("US", "CA", "AU") and not (state or "").strip():
        errors.append("state/province is required for this country")
    return errors


def mask_card_last4(card_number: str) -> str:
    digits = _digits_only(card_number)
    return digits[-4:] if len(digits) >= 4 else ""
