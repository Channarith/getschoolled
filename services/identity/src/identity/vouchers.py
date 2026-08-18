"""Vouchers, coupons, and gift codes — redeemable before or after checkout.

Three types:
  coupon:    percentage or flat discount applied at checkout (e.g. SAVE20 = 20% off)
  gift_code: pre-paid dollar amount (e.g. GIFT50 = $50 credit)
  free_pass: grants free access to one specific class or tier
"""
from __future__ import annotations
import json
import os
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

VOUCHER_DIR_ENV = "AOEP_VOUCHER_DIR"

@dataclass
class Voucher:
    code: str                    # uppercase, e.g. "SAVE20"
    kind: str                    # "coupon" | "gift_code" | "free_pass"
    value: float = 0.0           # percentage (0-100) for coupon, dollars for gift_code
    max_uses: int = 1            # 0 = unlimited
    uses: int = 0
    expires_at: Optional[float] = None   # unix timestamp, None = never
    class_id: Optional[str] = None       # for free_pass: which class
    created_at: float = field(default_factory=time.time)
    note: str = ""

    def is_valid(self) -> bool:
        if self.expires_at and time.time() > self.expires_at:
            return False
        if self.max_uses > 0 and self.uses >= self.max_uses:
            return False
        return True

    def apply_to_price(self, price_usd: float) -> tuple[float, str]:
        """Return (final_price, description)."""
        if self.kind == "coupon":
            discount = min(price_usd, price_usd * self.value / 100)
            return max(0.0, price_usd - discount), f"{self.value:.0f}% off"
        if self.kind == "gift_code":
            return max(0.0, price_usd - self.value), f"${self.value:.2f} gift credit applied"
        if self.kind == "free_pass":
            return 0.0, "Free pass applied"
        return price_usd, ""


class VoucherStore:
    def __init__(self, root: Path) -> None:
        self._path = root / "vouchers.json"
        self._vouchers: dict[str, Voucher] = {}
        self._load()

    @classmethod
    def open(cls) -> "VoucherStore":
        """Open the store in the first candidate directory we can actually write.

        mkdir succeeding does not mean the directory is writable (read-only home,
        restricted sandbox), and the failure then surfaced much later as an
        unhandled OSError from _save() mid-redemption. Probe up front instead.
        """
        raw = os.environ.get(VOUCHER_DIR_ENV, "").strip()
        candidates = [Path(raw)] if raw else []
        candidates.append(Path.home() / ".cache" / "aoep" / "vouchers")
        candidates.append(Path(tempfile.gettempdir()) / "aoep-vouchers")
        last_exc: OSError | None = None
        for root in candidates:
            try:
                root.mkdir(parents=True, exist_ok=True)
                probe = root / ".write_probe"
                probe.write_text("ok")
                probe.unlink(missing_ok=True)
                return cls(root)
            except OSError as exc:
                last_exc = exc
        raise OSError(f"could not open a writable voucher store: {last_exc}")

    def _load(self) -> None:
        if self._path.is_file():
            try:
                data = json.loads(self._path.read_text())
                for code, v in data.items():
                    try:
                        self._vouchers[code] = Voucher(**v)
                    except Exception as exc:
                        import logging
                        logging.getLogger(__name__).warning("Skipping corrupt voucher entry %r: %s", code, exc)
            except json.JSONDecodeError as exc:
                import logging
                logging.getLogger(__name__).error("vouchers.json is corrupt and could not be loaded: %s", exc)

    def _save(self) -> None:
        self._path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self._vouchers.copy()
        self._path.write_text(json.dumps({k: asdict(v) for k, v in tmp.items()}, indent=2))

    def create(self, code: str, kind: str, value: float = 0.0,
               max_uses: int = 1, expires_days: Optional[int] = None,
               class_id: Optional[str] = None, note: str = "") -> Voucher:
        code = code.upper().strip()
        if not code:
            raise ValueError("code is required")
        if code in self._vouchers:
            raise ValueError(f"code {code!r} already exists")
        expires_at = time.time() + expires_days * 86400 if expires_days else None
        v = Voucher(code=code, kind=kind, value=value, max_uses=max_uses,
                    expires_at=expires_at, class_id=class_id, note=note)
        self._vouchers[code] = v
        self._save()
        return v

    def lookup(self, code: str) -> Optional[Voucher]:
        return self._vouchers.get(code.upper().strip())

    def validate(self, code: str, price_usd: float, class_id: Optional[str] = None) -> tuple[Voucher, float, str]:
        """Validate and return (voucher, final_price, description). Raises ValueError on failure."""
        v = self.lookup(code)
        if v is None:
            raise ValueError(f"Code {code!r} is not valid")
        if not v.is_valid():
            raise ValueError(f"Code {code!r} has expired or reached its usage limit")
        # A class-scoped free pass is only valid for that class — including
        # when the caller omits class_id (the restriction used to be opt-in).
        if v.kind == "free_pass" and v.class_id and v.class_id != (class_id or ""):
            raise ValueError("This free pass is not valid for this class")
        final, desc = v.apply_to_price(price_usd)
        return v, final, desc

    def consume(self, code: str) -> None:
        v = self._vouchers.get(code.upper().strip())
        if v is None:
            raise ValueError(f"Code {code!r} is not valid")
        # Re-check at consume time: validate() and consume() are separate calls,
        # so N concurrent checkouts could all pass validation and over-consume
        # past max_uses/expires_at (TOCTOU).
        if not v.is_valid():
            raise ValueError(f"Code {code!r} has expired or reached its usage limit")
        v.uses += 1
        self._save()

    def list_all(self) -> list[Voucher]:
        return list(self._vouchers.values())
