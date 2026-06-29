"""Investor value chart builder + renderers."""

import importlib
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

mvc = importlib.import_module("market_value_chart")


def test_build_scales_with_tiers():
    rows = mvc.build()
    revenues = [r["projection"]["totals"]["projected_annual_revenue_usd"] for r in rows]
    assert revenues == sorted(revenues)
    assert rows[-1]["tier"] == 1_000_000


def test_renderers_emit_output():
    rows = mvc.build()
    table = mvc.render_table(rows)
    assert "PROJECTED ANNUAL REVENUE" in table
    assert "DISCLAIMER" in table
    svg = mvc.render_svg(rows)
    assert svg.startswith("<svg") and svg.rstrip().endswith("</svg>")
