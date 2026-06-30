"""Datamine market/ROI reference points and write them as ``market`` packs.

Two halves:
- ``extract_market_numbers``: offline, deterministic extraction of dollar amounts
  and percentages from text (e.g. a downloaded report/HTML), tagged with the
  source so they can be reviewed and verified.
- ``write_market_pack``: persist references as a content pack of kind ``market``
  so ``aoep_shared.market_intel`` merges them automatically.

Live fetching lives in ``scripts/datamine_market.py`` (network-gated). This module
is pure/stdlib so the extraction + persistence are fully testable offline.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterable, List, Optional, Sequence

_MULT = {
    "trillion": 1_000_000_000_000, "tn": 1_000_000_000_000,
    "billion": 1_000_000_000, "bn": 1_000_000_000, "b": 1_000_000_000,
    "million": 1_000_000, "mn": 1_000_000, "m": 1_000_000,
    "thousand": 1_000, "k": 1_000,
}

# "$142.4 billion", "USD 5 trillion", "$870B"
_MONEY_RE = re.compile(
    r"(?:US\$|USD|\$)\s?([0-9][0-9,]*(?:\.[0-9]+)?)\s*(trillion|billion|million|thousand|tn|bn|mn|[bmk])?",
    re.IGNORECASE,
)
# "13.6% CAGR", "growth of 30 percent"
_PCT_RE = re.compile(r"([0-9]+(?:\.[0-9]+)?)\s*(?:%|percent)", re.IGNORECASE)
_YEAR_RE = re.compile(r"\b(20[1-4][0-9])\b")


@dataclass
class MarketRecord:
    metric: str
    value: float
    unit: str
    region: str
    year: int
    source: str
    reference: str
    category: str
    note: str = "Auto-extracted by datamining; verify before investor use."
    url: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _nearest_year(text: str, pos: int, default: int) -> int:
    best = default
    best_dist = 10 ** 9
    for m in _YEAR_RE.finditer(text):
        d = abs(m.start() - pos)
        if d < best_dist:
            best_dist = d
            best = int(m.group(1))
    return best


def extract_market_numbers(
    text: str,
    *,
    source: str,
    reference: str,
    region: str = "global",
    default_year: int = 0,
    max_records: int = 50,
) -> List[MarketRecord]:
    """Extract $ amounts and percentages from text as candidate market records."""
    records: List[MarketRecord] = []
    for m in _MONEY_RE.finditer(text):
        num = float(m.group(1).replace(",", ""))
        mult = _MULT.get((m.group(2) or "").lower(), 1)
        value = num * mult
        if value < 1000:  # ignore trivially small/ambiguous money mentions
            continue
        year = _nearest_year(text, m.start(), default_year)
        records.append(MarketRecord(
            metric="market_value", value=value, unit="USD", region=region,
            year=year, source=source, reference=reference, category="market_size",
        ))
        if len(records) >= max_records:
            break
    for m in _PCT_RE.finditer(text):
        value = float(m.group(1))
        if value <= 0 or value > 200:
            continue
        year = _nearest_year(text, m.start(), default_year)
        records.append(MarketRecord(
            metric="growth_or_share_pct", value=value, unit="percent", region=region,
            year=year, source=source, reference=reference, category="growth",
        ))
        if len(records) >= max_records * 2:
            break
    return records


def write_market_pack(
    records: Iterable[MarketRecord | dict],
    out_path: str | Path,
    *,
    pack_name: str = "datamined",
    description: str = "Datamined market reference points",
) -> int:
    out_records: List[dict] = []
    for rec in records:
        d = rec.to_dict() if isinstance(rec, MarketRecord) else dict(rec)
        if d.get("metric") and d.get("source") and d.get("reference"):
            out_records.append(d)
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"pack": pack_name, "description": description, "records": out_records}, indent=2),
        encoding="utf-8",
    )
    return len(out_records)


def default_market_packs_dir() -> Path:
    env = os.environ.get("AOEP_CONTENT_PACKS", "")
    first = next((p for p in env.split(os.pathsep) if p.strip()), "")
    base = Path(first) if first else (Path(os.path.expanduser("~")) / ".cache" / "aoep" / "content-packs")
    return base / "market"
