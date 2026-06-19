"""Video-ad monetization engine (VAST/VMAP, tier gating)."""

import xml.etree.ElementTree as ET

from aoep_shared.ads import (
    AdPosition,
    ad_plan_for,
    build_vast,
    build_vmap,
)


def test_paid_tiers_are_ad_free():
    assert ad_plan_for("pro", duration_min=60) == []
    assert ad_plan_for("premium", duration_min=60) == []


def test_free_tier_gets_preroll_and_capped_midrolls():
    plan = ad_plan_for("free", duration_min=60, midroll_every_min=10, max_midrolls=3)
    positions = [b.position for b in plan]
    assert positions[0] is AdPosition.PRE_ROLL
    midrolls = [b for b in plan if b.position is AdPosition.MID_ROLL]
    assert len(midrolls) == 3  # capped
    # Mid-roll cue points are increasing minute marks.
    assert [b.offset_s for b in midrolls] == [600, 1200, 1800]


def test_short_course_has_no_midrolls():
    plan = ad_plan_for("free", duration_min=5, midroll_every_min=10)
    assert all(b.position is AdPosition.PRE_ROLL for b in plan)


def test_vast_is_well_formed_and_skippable():
    plan = ad_plan_for("free", duration_min=5)
    xml = build_vast(plan[0].ads[0])
    root = ET.fromstring(xml)
    assert root.tag == "VAST"
    assert "skipoffset" in xml
    assert "video/mp4" in xml


def test_vmap_well_formed_with_break_offsets():
    plan = ad_plan_for("free", duration_min=30)
    xml = build_vmap(plan)
    ns = {"vmap": "http://www.iab.net/videosuite/vmap"}
    root = ET.fromstring(xml)
    breaks = root.findall("vmap:AdBreak", ns)
    assert breaks[0].attrib["timeOffset"] == "start"
    assert any(b.attrib["timeOffset"] == "00:10:00" for b in breaks)
