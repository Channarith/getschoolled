#!/usr/bin/env python3
"""Investor value chart: projected annual revenue by region across user tiers.

Combines the capacity user tiers with the market-intel value projection to render
a dependency-free SVG bar chart for investor decks. Projections are model outputs
from the echoed assumptions + cited market references (verify before use).

  python3 scripts/market_value_chart.py --svg docs/charts/investor_value.svg \
      --doc docs/investor-value.txt
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Dict, List

from aoep_shared.market_intel import value_projection

# Illustrative regional mix of total daily users at each company-scale tier.
# (Distribution is an assumption; totals match the 10/100/1k/1M capacity tiers.)
_REGION_MIX = {"us": 0.45, "eu": 0.20, "india": 0.20, "latam": 0.10, "mena": 0.05}
_TIERS = [10, 100, 1_000, 1_000_000]


def _split(total: int) -> Dict[str, int]:
    return {region: int(round(total * share)) for region, share in _REGION_MIX.items()}


def build() -> List[dict]:
    rows = []
    for tier in _TIERS:
        proj = value_projection(_split(tier))
        rows.append({"tier": tier, "projection": proj})
    return rows


def _human_usd(n: float) -> str:
    n = float(n)
    if n >= 1e9:
        return f"${n/1e9:.1f}B"
    if n >= 1e6:
        return f"${n/1e6:.1f}M"
    if n >= 1e3:
        return f"${n/1e3:.1f}k"
    return f"${n:.0f}"


def _human_users(n: int) -> str:
    if n >= 1_000_000:
        return f"{n/1_000_000:.0f}M"
    if n >= 1000:
        return f"{n/1000:.0f}k"
    return str(n)


def render_table(rows: List[dict]) -> str:
    out = ["PROJECTED ANNUAL REVENUE BY USER TIER (MODEL OUTPUT)",
           "=" * 60,
           "Assumptions: ARPU $96/yr, 5% paid conversion. Regional mix: "
           "US 45%, EU 20%, India 20%, LATAM 10%, MENA 5%.",
           "Projections combine our capacity tiers with cited EdTech market "
           "references (see docs/capacity-projection.txt + market_intel).",
           ""]
    out.append(f"{'Daily users':>14} | {'Paid users':>12} | {'Proj. annual revenue':>22}")
    out.append("-" * 54)
    for r in rows:
        t = r["projection"]["totals"]
        out.append(f"{_human_users(r['tier']):>14} | {t['paid_users']:>12,.0f} | "
                   f"{_human_usd(t['projected_annual_revenue_usd']):>22}")
    out.append("")
    out.append("Per-region at 1,000,000 daily users:")
    big = rows[-1]["projection"]
    for reg in big["regions"]:
        cap = f"{reg['tam_capture_pct']:.4f}% of TAM" if reg["tam_capture_pct"] is not None else "TAM n/a"
        out.append(f"  {reg['region']:<7} {reg['paid_users']:>12,.0f} paid  "
                   f"{_human_usd(reg['projected_annual_revenue_usd']):>10}/yr  ({cap})")
    out.append("")
    out.append("DISCLAIMER: " + rows[-1]["projection"]["disclaimer"])
    return "\n".join(out) + "\n"


def _esc(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def render_svg(rows: List[dict]) -> str:
    W, H = 900, 460
    margin, top = 30, 90
    plot_h = H - top - 70
    plot_w = W - margin * 2
    revenues = [r["projection"]["totals"]["projected_annual_revenue_usd"] for r in rows]
    labels = [_human_users(r["tier"]) + " users" for r in rows]
    vmax = max(revenues) or 1.0
    n = len(rows)
    gap = 40
    bar_w = (plot_w - gap * (n + 1)) / n
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" '
        f'viewBox="0 0 {W} {H}" font-family="Segoe UI, Helvetica, Arial, sans-serif">',
        f'<rect width="{W}" height="{H}" fill="#f8fafc"/>',
        f'<text x="{margin}" y="34" font-size="22" font-weight="800" fill="#0f172a">'
        f'Projected Annual Revenue by User Tier</text>',
        f'<text x="{margin}" y="56" font-size="13" fill="#475569">'
        f'Model output &#183; ARPU $96/yr &#183; 5% paid conversion &#183; multi-region mix '
        f'&#183; combined with cited EdTech market references</text>',
    ]
    for i, (rev, label) in enumerate(zip(revenues, labels)):
        bh = (rev / vmax) * plot_h
        bh = max(bh, 2 if rev > 0 else 0)
        bx = margin + gap + i * (bar_w + gap)
        by = top + (plot_h - bh)
        parts.append(f'<rect x="{bx:.1f}" y="{by:.1f}" width="{bar_w:.1f}" height="{bh:.1f}" '
                     f'rx="6" fill="#7c3aed"/>')
        parts.append(f'<text x="{bx + bar_w/2:.1f}" y="{by - 8:.1f}" font-size="14" '
                     f'text-anchor="middle" font-weight="700" fill="#0f172a">'
                     f'{_esc(_human_usd(rev))}/yr</text>')
        parts.append(f'<text x="{bx + bar_w/2:.1f}" y="{top + plot_h + 24:.1f}" font-size="12" '
                     f'text-anchor="middle" fill="#475569">{_esc(label)}</text>')
    parts.append(f'<text x="{margin}" y="{H - 12}" font-size="11" fill="#94a3b8">'
                 f'Projection (not a guarantee) &#183; verify market references &#183; '
                 f'generated by scripts/market_value_chart.py</text>')
    parts.append("</svg>")
    return "".join(parts)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--print", action="store_true", dest="do_print")
    ap.add_argument("--svg", default="")
    ap.add_argument("--doc", default="")
    args = ap.parse_args(argv)

    rows = build()
    if args.do_print or not (args.svg or args.doc):
        print(render_table(rows))
    if args.doc:
        Path(args.doc).parent.mkdir(parents=True, exist_ok=True)
        Path(args.doc).write_text(render_table(rows), encoding="utf-8")
        print(f"doc -> {args.doc}")
    if args.svg:
        Path(args.svg).parent.mkdir(parents=True, exist_ok=True)
        Path(args.svg).write_text(render_svg(rows), encoding="utf-8")
        print(f"svg -> {args.svg}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
