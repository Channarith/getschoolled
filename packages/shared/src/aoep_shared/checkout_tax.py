"""Sales tax on a course purchase: pluggable, and it asserts no tax rule.

DRAFT for counsel / CPA review. Whether an online driver-education or food-safety course is taxable, in which states, and
whether out-of-state sales create a collection duty (economic nexus) is an OPEN QUESTION for the owner's CPA. This module only
carries out whatever the owner configures.

Modes (COURSE_TAX_MODE):
  none      no tax line (the owner or CPA has decided the course is not taxable, or tax is handled elsewhere). Default.
  provider  the card processor calculates tax on its hosted checkout (Stripe Tax: automatic_tax + billing address). The amount
            comes back in the session total and is recorded as the tax line. PayPal has no equivalent here: its orders carry
            only the manual amount below, so provider mode applies to card payments.
  manual    a rate per ship-to state from COURSE_TAX_RATES_JSON, e.g. {"CA": 0.0725, "NY": 0.04}. The buyer's state is asked
            for at checkout (only in this mode); a state with no entry is charged no tax.

Config (names only): COURSE_TAX_MODE, COURSE_TAX_RATES_JSON, COURSE_TAX_LABEL (default "Sales tax").
Apple and Google act as the seller of record for in-app purchases and handle tax themselves: nothing here applies to them.
"""

from __future__ import annotations

import json
import os
from decimal import ROUND_HALF_UP, Decimal
from typing import Any, Mapping, Optional

MODES = ("none", "provider", "manual")


def tax_mode() -> str:
    mode = os.environ.get("COURSE_TAX_MODE", "none").strip().lower()
    return mode if mode in MODES else "none"


def tax_label() -> str:
    return os.environ.get("COURSE_TAX_LABEL", "").strip() or "Sales tax"


def manual_rates() -> dict[str, Decimal]:
    raw = os.environ.get("COURSE_TAX_RATES_JSON", "").strip()
    if not raw:
        return {}
    try:
        data = json.loads(raw)
    except ValueError:
        return {}
    rates: dict[str, Decimal] = {}
    for state, value in (data.items() if isinstance(data, dict) else []):
        try:
            rate = Decimal(str(value))
        except Exception:  # noqa: BLE001 - one bad entry must not disable the rest
            continue
        if Decimal(0) <= rate < Decimal(1):
            rates[str(state).strip().upper()] = rate
    return rates


def needs_billing_state(mode: Optional[str] = None) -> bool:
    """Only manual mode needs to ask the buyer where they are; collect the minimum, and only then."""
    return (mode or tax_mode()) == "manual"


def compute_tax(
    amount_cents: int,
    *,
    mode: Optional[str] = None,
    state: str = "",
    rates: Optional[Mapping[str, Decimal]] = None,
) -> dict[str, Any]:
    """Tax for one purchase. Rounds half up to the cent. Provider mode returns 0 here: the processor adds its own."""
    chosen = (mode or tax_mode())
    result: dict[str, Any] = {"tax_cents": 0, "rate": None, "label": tax_label(), "state": "", "mode": chosen, "requires_state": False}
    if chosen != "manual":
        return result
    code = (state or "").strip().upper()
    result["state"] = code
    if not code:
        result["requires_state"] = True
        return result
    table = dict(rates) if rates is not None else manual_rates()
    rate = table.get(code)
    if rate is None:
        return result
    cents = (Decimal(int(amount_cents)) * rate).quantize(Decimal(1), rounding=ROUND_HALF_UP)
    result.update(tax_cents=int(cents), rate=float(rate))
    return result
