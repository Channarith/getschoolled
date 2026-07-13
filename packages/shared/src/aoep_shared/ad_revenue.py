"""Ad revenue accounting — impression/click ledger + CPM/eCPM estimates.

Records ad impressions and clicks fired by the web + mobile clients (best-effort
beacons) and estimates revenue from them so operators can see and reconcile ad
earnings alongside real ad-network payout dashboards.

Revenue model (estimates, not billed):
  * Impressions earn CPM/1000 (CPM = revenue per 1000 impressions).
  * Clicks earn an additional CPC (cost-per-click).
  * eCPM = total_revenue / impressions * 1000 (effective earnings per 1000).

CPM/CPC defaults vary by network and format (video ads earn more than display).
When a real network (AdSense/AdMob/GAM) is wired, the payout of record is that
network's dashboard; this ledger is our in-app estimate + funnel (impressions,
clicks, CTR) for product decisions. Pure/offline and thread-safe.
"""

from __future__ import annotations

import threading
import time
from collections import deque
from typing import Deque, Dict, List, Optional

from pydantic import BaseModel, Field

# Estimated CPM (USD per 1000 impressions) by network + format. House inventory
# is our own promos (no external payout) but we still estimate its opportunity
# value. Third-party estimates are conservative mid-range figures; override with
# real reported eCPM once a network is live.
CPM_USD: Dict[str, Dict[str, float]] = {
    "house": {"display": 0.50, "video": 1.00},
    "google_adsense": {"display": 2.50, "video": 8.00},
    "google_ad_manager": {"display": 3.00, "video": 10.00},
    "admob": {"display": 2.00, "video": 9.00},
    "meta_audience": {"display": 2.20, "video": 7.50},
}
# Estimated cost-per-click (USD) by network.
CPC_USD: Dict[str, float] = {
    "house": 0.02,
    "google_adsense": 0.35,
    "google_ad_manager": 0.40,
    "admob": 0.30,
    "meta_audience": 0.28,
}
DEFAULT_NETWORK = "house"
DEFAULT_FORMAT = "display"


def estimated_cpm(network: str, fmt: str = DEFAULT_FORMAT) -> float:
    net = (network or DEFAULT_NETWORK).lower()
    fmt = (fmt or DEFAULT_FORMAT).lower()
    table = CPM_USD.get(net, CPM_USD[DEFAULT_NETWORK])
    return table.get(fmt, table.get(DEFAULT_FORMAT, 0.0))


def estimated_cpc(network: str) -> float:
    return CPC_USD.get((network or DEFAULT_NETWORK).lower(), CPC_USD[DEFAULT_NETWORK])


class AdEvent(BaseModel):
    kind: str                       # "impression" | "click"
    placement: str                  # e.g. "home-banner", "class-preroll", "watch-midroll"
    network: str = DEFAULT_NETWORK
    fmt: str = DEFAULT_FORMAT        # "display" | "video"
    tier: str = "free"
    unit_id: str = ""               # slot id / ad unit id
    creative_id: str = ""
    advertiser: str = ""
    revenue_usd: float = 0.0
    ts: float = Field(default_factory=time.time)


def _round(x: float) -> float:
    return round(x, 6)


class AdRevenueLedger:
    """In-memory impression/click ledger with running revenue aggregates.

    Per-service singleton (like TelemetryStore). Events are kept in a capped ring
    buffer for the recent feed; aggregate counters are unbounded but tiny.
    """

    def __init__(self, max_events: int = 5000) -> None:
        self._lock = threading.Lock()
        self._events: Deque[AdEvent] = deque(maxlen=max_events)
        self._impressions = 0
        self._clicks = 0
        self._revenue = 0.0
        # placement/network -> {impressions, clicks, revenue_usd}
        self._by_placement: Dict[str, Dict[str, float]] = {}
        self._by_network: Dict[str, Dict[str, float]] = {}
        self._by_day: Dict[str, Dict[str, float]] = {}

    def _bucket(self, table: Dict[str, Dict[str, float]], key: str) -> Dict[str, float]:
        return table.setdefault(key, {"impressions": 0.0, "clicks": 0.0, "revenue_usd": 0.0})

    def record(
        self,
        kind: str,
        *,
        placement: str,
        network: str = DEFAULT_NETWORK,
        fmt: str = DEFAULT_FORMAT,
        tier: str = "free",
        unit_id: str = "",
        creative_id: str = "",
        advertiser: str = "",
        cpm_usd: Optional[float] = None,
        cpc_usd: Optional[float] = None,
    ) -> AdEvent:
        kind = "click" if kind == "click" else "impression"
        network = (network or DEFAULT_NETWORK).lower()
        fmt = (fmt or DEFAULT_FORMAT).lower()
        if kind == "impression":
            cpm = cpm_usd if cpm_usd is not None else estimated_cpm(network, fmt)
            revenue = _round(cpm / 1000.0)
        else:
            cpc = cpc_usd if cpc_usd is not None else estimated_cpc(network)
            revenue = _round(cpc)

        event = AdEvent(
            kind=kind, placement=placement or "unknown", network=network, fmt=fmt,
            tier=(tier or "free").lower(), unit_id=unit_id, creative_id=creative_id,
            advertiser=advertiser, revenue_usd=revenue,
        )
        day = time.strftime("%Y-%m-%d", time.gmtime(event.ts))
        with self._lock:
            self._events.append(event)
            self._revenue = _round(self._revenue + revenue)
            for table, key in ((self._by_placement, event.placement),
                               (self._by_network, network),
                               (self._by_day, day)):
                b = self._bucket(table, key)
                b[kind + "s"] += 1
                b["revenue_usd"] = _round(b["revenue_usd"] + revenue)
            if kind == "impression":
                self._impressions += 1
            else:
                self._clicks += 1
        return event

    def record_impression(self, placement: str, **kw) -> AdEvent:
        return self.record("impression", placement=placement, **kw)

    def record_click(self, placement: str, **kw) -> AdEvent:
        return self.record("click", placement=placement, **kw)

    @staticmethod
    def _finalize(rows: Dict[str, Dict[str, float]]) -> List[dict]:
        out: List[dict] = []
        for key, b in rows.items():
            imp = int(b["impressions"])
            clk = int(b["clicks"])
            out.append({
                "key": key,
                "impressions": imp,
                "clicks": clk,
                "ctr": _round(clk / imp) if imp else 0.0,
                "revenue_usd": _round(b["revenue_usd"]),
                "ecpm_usd": _round(b["revenue_usd"] / imp * 1000.0) if imp else 0.0,
            })
        out.sort(key=lambda r: r["revenue_usd"], reverse=True)
        return out

    def summary(self, *, since_s: Optional[float] = None, recent_limit: int = 50) -> dict:
        with self._lock:
            imp, clk, rev = self._impressions, self._clicks, self._revenue
            by_placement = self._finalize(self._by_placement)
            by_network = self._finalize(self._by_network)
            by_day = self._finalize(self._by_day)
            events = list(self._events)
        if since_s is not None:
            cutoff = time.time() - since_s
            events = [e for e in events if e.ts >= cutoff]
        recent = [e.model_dump() for e in list(reversed(events))[:recent_limit]]
        by_day.sort(key=lambda r: r["key"])
        return {
            "totals": {
                "impressions": imp,
                "clicks": clk,
                "ctr": _round(clk / imp) if imp else 0.0,
                "revenue_usd": _round(rev),
                "ecpm_usd": _round(rev / imp * 1000.0) if imp else 0.0,
            },
            "by_network": by_network,
            "by_placement": by_placement,
            "by_day": by_day,
            "recent": recent,
        }
