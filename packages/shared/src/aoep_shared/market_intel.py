"""Market intelligence + investor value model.

A cited, growable store of education / EdTech market reference points (market
sizes, growth rates, public spend, per-student value, demographics) used to build
the investor value story across regions and states, plus a transparent revenue/
ROI projection model that combines those references with our user tiers.

GROWTH PATH (how the data scales): the curated seed below is real, *attributed*
public reference data. New references are added by datamining (see
``scripts/datamine_market.py`` and ``harvest/market_bridge.py``), which writes
content packs of kind ``market`` that this module merges automatically — no code
change. Live web scraping requires outbound network egress to be enabled.

HONESTY CONTRACT:
- Every reference carries a ``source`` and ``reference`` and a ``note`` flagging
  that published figures must be VERIFIED before investor use.
- Projected dollar amounts from ``value_projection`` are MODEL OUTPUTS (clearly
  labelled, with the assumptions echoed back), not guarantees.

Pure/stdlib-only and offline-testable.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Dict, List, Optional

_VERIFY = "Published reference estimate; verify against primary source before investor use."


@dataclass
class MarketReference:
    metric: str
    value: float
    unit: str          # USD | USD_per_year | percent | count | USD_per_student
    region: str        # global | us | eu | india | africa | china | latam | mena | us-ny ...
    year: int
    source: str
    reference: str
    category: str      # market_size | growth | spend | per_student | demographic | benchmark
    note: str = _VERIFY
    url: str = ""

    def to_dict(self) -> dict:
        return {
            "metric": self.metric, "value": self.value, "unit": self.unit,
            "region": self.region, "year": self.year, "source": self.source,
            "reference": self.reference, "category": self.category,
            "note": self.note, "url": self.url,
        }


def _r(metric, value, unit, region, year, source, reference, category, note=_VERIFY) -> dict:
    return {"metric": metric, "value": value, "unit": unit, "region": region,
            "year": year, "source": source, "reference": reference,
            "category": category, "note": note}


# Curated, attributed seed of widely-published education/EdTech reference points.
# Values are representative published estimates (round figures) — always verify.
_SEED: List[dict] = [
    # ---- Global market size & growth ----
    _r("edtech_market_size", 142_000_000_000, "USD", "global", 2023,
       "Grand View Research", "EdTech Market Report", "market_size"),
    _r("edtech_market_cagr", 13.6, "percent", "global", 2030,
       "Grand View Research", "EdTech Market 2024-2030 CAGR", "growth"),
    _r("elearning_market_size", 315_000_000_000, "USD", "global", 2025,
       "Statista / industry reports", "E-learning market estimate", "market_size"),
    _r("global_education_expenditure", 5_000_000_000_000, "USD_per_year", "global", 2023,
       "UNESCO / World Bank", "Global education spending", "spend"),
    _r("corporate_training_market", 360_000_000_000, "USD_per_year", "global", 2023,
       "Training Industry / Statista", "Corporate training market", "market_size"),
    _r("online_learners", 1_000_000_000, "count", "global", 2023,
       "Industry aggregate (MOOCs + apps)", "Online learner population", "demographic"),
    # ---- United States ----
    _r("edtech_market_size", 45_000_000_000, "USD", "us", 2023,
       "HolonIQ / industry", "US EdTech market estimate", "market_size"),
    _r("k12_public_spend", 870_000_000_000, "USD_per_year", "us", 2023,
       "NCES", "US K-12 public education expenditure", "spend"),
    _r("k12_per_pupil", 15_600, "USD_per_student", "us", 2023,
       "NCES", "US average per-pupil spending", "per_student"),
    _r("k12_students", 49_500_000, "count", "us", 2023,
       "NCES", "US K-12 public enrollment", "demographic"),
    _r("higher_ed_spend", 700_000_000_000, "USD_per_year", "us", 2023,
       "NCES", "US higher-education expenditure", "spend"),
    # ---- US states (per-pupil benchmarks; approximate, verify) ----
    _r("k12_per_pupil", 26_000, "USD_per_student", "us-ny", 2022,
       "NCES / US Census", "New York per-pupil spending (highest tier)", "per_student"),
    _r("k12_per_pupil", 14_000, "USD_per_student", "us-ca", 2022,
       "NCES / US Census", "California per-pupil spending", "per_student"),
    _r("k12_per_pupil", 11_000, "USD_per_student", "us-tx", 2022,
       "NCES / US Census", "Texas per-pupil spending", "per_student"),
    _r("k12_per_pupil", 9_000, "USD_per_student", "us-ut", 2022,
       "NCES / US Census", "Utah per-pupil spending (lower tier)", "per_student"),
    _r("k12_students", 5_900_000, "count", "us-ca", 2023,
       "CDE / NCES", "California K-12 enrollment", "demographic"),
    _r("k12_students", 5_500_000, "count", "us-tx", 2023,
       "TEA / NCES", "Texas K-12 enrollment", "demographic"),
    # ---- Europe ----
    _r("edtech_market_size", 30_000_000_000, "USD", "eu", 2023,
       "HolonIQ / industry", "Europe EdTech market estimate", "market_size"),
    _r("education_spend_gdp", 4.7, "percent", "eu", 2022,
       "OECD", "EU public education spend (% of GDP)", "spend"),
    # ---- India ----
    _r("edtech_market_size", 10_000_000_000, "USD", "india", 2025,
       "RedSeer / industry", "India EdTech market estimate", "market_size"),
    _r("school_students", 248_000_000, "count", "india", 2022,
       "UDISE+ (Govt of India)", "India school enrollment", "demographic"),
    _r("edtech_market_cagr", 30.0, "percent", "india", 2025,
       "Industry reports", "India EdTech growth rate (high-growth market)", "growth"),
    # ---- China ----
    _r("edtech_market_size", 50_000_000_000, "USD", "china", 2023,
       "iResearch / industry", "China EdTech market estimate", "market_size"),
    # ---- Africa / LATAM / MENA (high-growth, young populations) ----
    _r("youth_population", 450_000_000, "count", "africa", 2023,
       "UN / World Bank", "Africa population under 18 (approx)", "demographic"),
    _r("edtech_market_size", 9_000_000_000, "USD", "latam", 2025,
       "HolonIQ / industry", "Latin America EdTech market estimate", "market_size"),
    _r("edtech_market_size", 7_000_000_000, "USD", "mena", 2025,
       "HolonIQ / industry", "MENA EdTech market estimate", "market_size"),
    # ---- Value / ROI benchmarks ----
    _r("tutoring_hourly_rate", 40, "USD", "us", 2023,
       "BLS / market surveys", "Typical private tutoring hourly rate", "benchmark"),
    _r("learning_gain_tutoring", 2.0, "benchmark", "global", 1984,
       "Bloom (2-sigma problem)", "1:1 tutoring vs class instruction effect", "benchmark",
       "Classic education research; effect-size reference, not a dollar figure."),
]


# --------------------------------------------------------------------------- #
# Combined corpus (seed + market packs), cached by pack fingerprint.
# --------------------------------------------------------------------------- #
_CACHE: dict = {"fingerprint": None, "data": None}


def _pack_refs():
    try:
        from .content_packs import load_records, pack_fingerprint

        return pack_fingerprint("market"), load_records("market")
    except Exception:  # pragma: no cover
        return "", []


def _all() -> List[MarketReference]:
    fp, records = _pack_refs()
    if _CACHE["fingerprint"] == fp and _CACHE["data"] is not None:
        return _CACHE["data"]
    out = [MarketReference(**{**{"note": _VERIFY, "url": ""}, **s}) for s in _SEED]
    for rec in records:
        if not (rec.get("metric") and rec.get("source") and rec.get("reference")):
            continue
        try:
            out.append(MarketReference(
                metric=str(rec["metric"]), value=float(rec.get("value", 0)),
                unit=str(rec.get("unit", "")), region=str(rec.get("region", "global")),
                year=int(rec.get("year", 0)), source=str(rec["source"]),
                reference=str(rec["reference"]), category=str(rec.get("category", "benchmark")),
                note=str(rec.get("note", _VERIFY)), url=str(rec.get("url", "")),
            ))
        except (TypeError, ValueError):
            continue
    _CACHE["fingerprint"] = fp
    _CACHE["data"] = out
    return out


def all_references() -> List[MarketReference]:
    return list(_all())


def search_references(
    *,
    region: Optional[str] = None,
    category: Optional[str] = None,
    metric: Optional[str] = None,
    q: Optional[str] = None,
    offset: int = 0,
    limit: Optional[int] = 100,
) -> List[MarketReference]:
    rows = _all()
    ql = (q or "").lower()
    out = []
    for r in rows:
        if region and r.region != region:
            continue
        if category and r.category != category:
            continue
        if metric and r.metric != metric:
            continue
        if ql and ql not in r.metric.lower() and ql not in r.source.lower() \
                and ql not in r.reference.lower() and ql not in r.region.lower():
            continue
        out.append(r)
    if offset:
        out = out[offset:]
    if limit is not None:
        out = out[:limit]
    return out


def regions() -> List[str]:
    return sorted({r.region for r in _all()})


def sources() -> List[Dict[str, object]]:
    counts: Dict[str, int] = {}
    for r in _all():
        counts[r.source] = counts.get(r.source, 0) + 1
    return [{"source": s, "count": n} for s, n in sorted(counts.items(), key=lambda x: (-x[1], x[0]))]


def meta() -> dict:
    rows = _all()
    cats: Dict[str, int] = {}
    regs: Dict[str, int] = {}
    for r in rows:
        cats[r.category] = cats.get(r.category, 0) + 1
        regs[r.region] = regs.get(r.region, 0) + 1
    from .content_packs import pack_record_count

    return {
        "count": len(rows),
        "builtin": len(_SEED),
        "from_packs": pack_record_count("market"),
        "regions": len(regs),
        "sources": len(sources()),
        "categories": cats,
        "region_counts": regs,
        "disclaimer": _VERIFY,
    }


def tam_for_region(region: str) -> Optional[MarketReference]:
    """Best total-addressable-market reference for a region (EdTech market size)."""
    candidates = [r for r in _all()
                  if r.region == region and r.metric == "edtech_market_size"
                  and r.unit == "USD"]
    if not candidates:
        return None
    return max(candidates, key=lambda r: (r.year, r.value))


# --------------------------------------------------------------------------- #
# Investor value / ROI projection (MODEL OUTPUT — not a guarantee)
# --------------------------------------------------------------------------- #
DEFAULT_ARPU_USD_PER_YEAR = 96.0      # conservative: ~$8/mo paying user
DEFAULT_PAID_CONVERSION = 0.05        # 5% of users convert to paid (assumption)


def value_projection(
    users_by_region: Dict[str, int],
    *,
    arpu_usd_per_year: float = DEFAULT_ARPU_USD_PER_YEAR,
    paid_conversion: float = DEFAULT_PAID_CONVERSION,
) -> dict:
    """Project annual revenue and TAM capture per region from user counts.

    All outputs are model projections from the echoed assumptions, combined with
    cited market references where available. Not financial advice or a guarantee.
    """
    regions_out: List[dict] = []
    total_users = 0
    total_paid = 0.0
    total_revenue = 0.0
    for region, users in sorted(users_by_region.items()):
        users = int(users)
        paid = users * paid_conversion
        revenue = paid * arpu_usd_per_year
        tam = tam_for_region(region)
        tam_usd = tam.value if tam else None
        capture_pct = round(100.0 * revenue / tam_usd, 6) if tam_usd else None
        total_users += users
        total_paid += paid
        total_revenue += revenue
        regions_out.append({
            "region": region,
            "users": users,
            "paid_users": round(paid, 2),
            "projected_annual_revenue_usd": round(revenue, 2),
            "tam_usd": tam_usd,
            "tam_source": (f"{tam.source} ({tam.year})" if tam else None),
            "tam_capture_pct": capture_pct,
        })
    return {
        "assumptions": {
            "arpu_usd_per_year": arpu_usd_per_year,
            "paid_conversion": paid_conversion,
        },
        "totals": {
            "users": total_users,
            "paid_users": round(total_paid, 2),
            "projected_annual_revenue_usd": round(total_revenue, 2),
        },
        "regions": regions_out,
        "disclaimer": ("Projection from the stated assumptions and cited market "
                       "references. Figures are model outputs to be validated, not "
                       "guarantees."),
    }
