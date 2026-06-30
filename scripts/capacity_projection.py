#!/usr/bin/env python3
"""Projected ecosystem performance across user tiers (10 / 100 / 1k / 1M).

Turns the capacity model documented in ``docs/scalability.txt`` into a concrete,
per-tier projection and renders a dependency-free SVG chart plus a plain-text
table and JSON. The model constants come from the MEASURED baseline in that doc:

  - 940 GET RPS per 1-CPU pod at p95 = 6.3 ms (measured).
  - ~1.3 API RPS per concurrent user (observed session shape).
  - Concurrency via Little's law: DAU * (session_min/60) / active_hours.
  - 2x peak-hour multiplier.
  - Per-service traffic shares; CDN absorbs ~80% of curriculum (catalog) reads.
  - Kubernetes HPA floor/ceiling of 3..30 pods per service per region.

Usage:
  python3 scripts/capacity_projection.py --print
  python3 scripts/capacity_projection.py --svg docs/charts/capacity_projection.svg \
      --doc docs/capacity-projection.txt --json out.json
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path
from typing import Dict, List

# --- Model constants (from docs/scalability.txt; measured baseline) ---------- #
RPS_PER_POD = 940.0           # measured: 1-CPU pod @ p95 6.3 ms
RPS_PER_CONCURRENT = 1.3      # ~40 calls / 30-min session
SESSION_MIN = 30.0
ACTIVE_HOURS = 16.0
PEAK_MULTIPLIER = 2.0
BASE_P95_MS = 6.3            # measured p95 at/under capacity
HPA_MIN_PODS = 3
HPA_MAX_PODS = 30            # per service, per region

# Per-service share of aggregate API traffic (sums to 1.0; notifications folded
# into curriculum). From the "Distribution across services" table.
SERVICE_SHARES: Dict[str, float] = {
    "curriculum": 0.40,
    "orchestrator": 0.25,
    "identity": 0.15,
    "memory": 0.10,
    "speech": 0.05,
    "perception": 0.03,
    "billing": 0.02,
}

# Fraction of a service's reads served from origin (1 - CDN offload). Curriculum
# catalog/audio reads are heavily CDN-cacheable; the rest are mostly dynamic.
ORIGIN_FRACTION: Dict[str, float] = {
    "curriculum": 0.20,   # CDN absorbs ~80% of catalog/audio/home reads
    "orchestrator": 1.0,
    "identity": 0.90,
    "memory": 1.0,
    "speech": 1.0,
    "perception": 1.0,
    "billing": 1.0,
}

USER_TIERS: List[int] = [10, 100, 1_000, 1_000_000]


def concurrent_users(dau: int) -> float:
    return dau * (SESSION_MIN / 60.0) / ACTIVE_HOURS


def project(dau: int) -> dict:
    """Project performance for a single DAU tier."""
    concurrent = concurrent_users(dau)
    avg_rps = concurrent * RPS_PER_CONCURRENT
    peak_rps = avg_rps * PEAK_MULTIPLIER

    services = {}
    total_pods = 0
    max_regions = 1
    for name, share in SERVICE_SHARES.items():
        svc_peak = peak_rps * share
        origin_peak = svc_peak * ORIGIN_FRACTION[name]
        # Pods needed to hold origin RPS at the measured per-pod budget.
        needed = max(HPA_MIN_PODS, math.ceil(origin_peak / RPS_PER_POD)) if origin_peak > 0 else HPA_MIN_PODS
        # A single region tops out at HPA_MAX_PODS; beyond that we add regions.
        regions = max(1, math.ceil(needed / HPA_MAX_PODS))
        pods_per_region = min(needed, HPA_MAX_PODS)
        max_regions = max(max_regions, regions)
        total_pods += needed
        services[name] = {
            "share": share,
            "peak_rps": round(svc_peak, 2),
            "origin_peak_rps": round(origin_peak, 2),
            "pods_needed": needed,
            "pods_per_region": pods_per_region,
            "regions": regions,
            "saturated": needed > HPA_MAX_PODS,
        }

    # p95 stays at the measured baseline while every service fits its region
    # ceiling; if any service would saturate a single region, we scale out to
    # more regions (geo-DNS), which keeps per-region load — and thus p95 — flat.
    any_saturated = any(s["saturated"] for s in services.values())
    p95_ms = BASE_P95_MS

    return {
        "dau": dau,
        "concurrent_users": round(concurrent, 2),
        "avg_aggregate_rps": round(avg_rps, 2),
        "peak_aggregate_rps": round(peak_rps, 2),
        "p95_ms": p95_ms,
        "total_pods_peak": total_pods,
        "regions_needed": max_regions,
        "single_region_ok": not any_saturated,
        "services": services,
    }


def build_projection(tiers: List[int] = None) -> List[dict]:
    return [project(d) for d in (tiers or USER_TIERS)]


# --------------------------------------------------------------------------- #
# Plain-text table
# --------------------------------------------------------------------------- #
def _fmt_int(n: float) -> str:
    return f"{int(round(n)):,}"


def render_table(rows: List[dict]) -> str:
    lines: List[str] = []
    lines.append("PROJECTED ECOSYSTEM PERFORMANCE BY USER TIER")
    lines.append("=" * 60)
    lines.append("Model: Little's law concurrency, 1.3 RPS/user, 2x peak,")
    lines.append("940 RPS/pod @ p95 6.3 ms (measured), HPA 3..30 pods/service,")
    lines.append("CDN absorbs ~80% of curriculum reads. Source: docs/scalability.txt")
    lines.append("")
    header = (f"{'Daily users':>14} | {'Concurrent':>11} | {'Peak RPS':>10} | "
              f"{'p95':>7} | {'Pods(peak)':>10} | {'Regions':>7} | {'1-region?':>9}")
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        lines.append(
            f"{_fmt_int(r['dau']):>14} | {_fmt_int(r['concurrent_users']):>11} | "
            f"{_fmt_int(r['peak_aggregate_rps']):>10} | {r['p95_ms']:>5} ms | "
            f"{_fmt_int(r['total_pods_peak']):>10} | {r['regions_needed']:>7} | "
            f"{'yes' if r['single_region_ok'] else 'multi':>9}"
        )
    lines.append("")
    lines.append("Per-service peak RPS (and pods needed) at each tier:")
    for r in rows:
        lines.append(f"\n  {_fmt_int(r['dau'])} daily users (peak {_fmt_int(r['peak_aggregate_rps'])} RPS):")
        for name, s in r["services"].items():
            lines.append(
                f"    {name:<13} {_fmt_int(s['peak_rps']):>10} RPS  "
                f"-> origin {_fmt_int(s['origin_peak_rps']):>10} RPS  "
                f"-> {s['pods_needed']:>2} pods"
                + ("  (multi-region)" if s["saturated"] else "")
            )
    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------------- #
# Dependency-free SVG chart (4 panels, one per key metric, bars across tiers)
# --------------------------------------------------------------------------- #
def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _human(n: float) -> str:
    n = float(n)
    if n >= 1_000_000:
        return f"{n/1_000_000:.1f}M".replace(".0M", "M")
    if n >= 1_000:
        return f"{n/1_000:.1f}k".replace(".0k", "k")
    if n >= 100:
        return f"{n:.0f}"
    return f"{n:g}"


def _panel(x0: int, y0: int, w: int, h: int, title: str, labels: List[str],
           values: List[float], unit: str, color: str) -> str:
    pad_top = 34
    pad_bottom = 30
    plot_h = h - pad_top - pad_bottom
    n = len(values)
    gap = 14
    bar_w = (w - gap * (n + 1)) / n
    vmax = max(values) if values and max(values) > 0 else 1.0
    parts = [
        f'<g transform="translate({x0},{y0})">',
        f'<rect x="0" y="0" width="{w}" height="{h}" rx="10" '
        f'fill="#ffffff" stroke="#e2e8f0"/>',
        f'<text x="14" y="22" font-size="14" font-weight="700" '
        f'fill="#0f172a">{_esc(title)}</text>',
    ]
    for i, (label, val) in enumerate(zip(labels, values)):
        bh = (val / vmax) * plot_h if vmax else 0
        bh = max(bh, 2 if val > 0 else 0)
        bx = gap + i * (bar_w + gap)
        by = pad_top + (plot_h - bh)
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
            f'rx="4" fill="{color}"/>'
        )
        parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{by - 6:.1f}" font-size="11" '
            f'text-anchor="middle" fill="#0f172a" font-weight="600">{_esc(_human(val))}</text>'
        )
        parts.append(
            f'<text x="{bx + bar_w/2:.1f}" y="{h - 10:.1f}" font-size="11" '
            f'text-anchor="middle" fill="#475569">{_esc(label)}</text>'
        )
    parts.append(
        f'<text x="{w - 12}" y="22" font-size="10" text-anchor="end" '
        f'fill="#94a3b8">{_esc(unit)}</text>'
    )
    parts.append("</g>")
    return "".join(parts)


def render_svg(rows: List[dict]) -> str:
    labels = [_human(r["dau"]) + " users" for r in rows]
    panels = [
        ("Concurrent users", [r["concurrent_users"] for r in rows], "count", "#2563eb"),
        ("Peak aggregate RPS", [r["peak_aggregate_rps"] for r in rows], "req/s", "#7c3aed"),
        ("Total pods at peak", [r["total_pods_peak"] for r in rows], "k8s pods", "#0891b2"),
        ("p95 latency", [r["p95_ms"] for r in rows], "ms (measured)", "#16a34a"),
    ]
    W, H = 920, 620
    pw, ph = 430, 230
    margin = 20
    gap = 20
    header_h = 70
    positions = [
        (margin, header_h),
        (margin + pw + gap, header_h),
        (margin, header_h + ph + gap),
        (margin + pw + gap, header_h + ph + gap),
    ]
    body = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#f8fafc"/>',
        f'<text x="{margin}" y="34" font-size="22" font-weight="800" '
        f'fill="#0f172a">Projected Ecosystem Performance by User Tier</text>',
        f'<text x="{margin}" y="56" font-size="13" fill="#475569">'
        f'Little&#39;s-law concurrency &#183; 1.3 RPS/user &#183; 2x peak &#183; '
        f'940 RPS/pod @ p95 6.3 ms (measured) &#183; HPA 3-30 pods/service &#183; '
        f'~80% CDN offload on catalog reads</text>',
    ]
    for (title, vals, unit, color), (x, y) in zip(panels, positions):
        body.append(_panel(x, y, pw, ph, title, labels, vals, unit, color))
    body.append(
        f'<text x="{margin}" y="{H - 8}" font-size="11" fill="#94a3b8">'
        f'Source: docs/scalability.txt measured baseline &#183; generated by '
        f'scripts/capacity_projection.py</text>'
    )
    body.append("</svg>")
    return "".join(body)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--svg", default="")
    ap.add_argument("--doc", default="")
    ap.add_argument("--json", default="")
    ap.add_argument("--tiers", default="", help="comma-separated DAU tiers")
    args = ap.parse_args(argv)

    tiers = ([int(x) for x in args.tiers.split(",") if x.strip()] if args.tiers else USER_TIERS)
    rows = build_projection(tiers)

    if args.do_print or not (args.svg or args.doc or args.json):
        print(render_table(rows))
    if args.doc:
        Path(args.doc).parent.mkdir(parents=True, exist_ok=True)
        Path(args.doc).write_text(render_table(rows), encoding="utf-8")
        print(f"doc  -> {args.doc}")
    if args.svg:
        Path(args.svg).parent.mkdir(parents=True, exist_ok=True)
        Path(args.svg).write_text(render_svg(rows), encoding="utf-8")
        print(f"svg  -> {args.svg}")
    if args.json:
        Path(args.json).parent.mkdir(parents=True, exist_ok=True)
        Path(args.json).write_text(json.dumps({"tiers": rows}, indent=2), encoding="utf-8")
        print(f"json -> {args.json}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
