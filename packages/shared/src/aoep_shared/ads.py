"""Video-ad monetization (IAB VAST/VMAP).

Builds ad-break schedules for course playback - pre-roll, mid-roll (at cue
points), and post-roll - and renders them as IAB-standard VMAP + VAST XML that
client video players (e.g. Google IMA) can consume directly. Ads are tier-gated:
free/basic (Standard) members see ads; VIP (premium) and legacy pro are ad-free.

Pure/offline; an `AdProvider` can later swap the static house inventory for a
real ad-decisioning server (SSP/ad exchange) without changing callers.
"""

from __future__ import annotations

import enum
from typing import List, Optional
from xml.sax.saxutils import escape, quoteattr

from pydantic import BaseModel, Field

# Tiers that get an ad-free experience (entitlement). Free/basic see ads.
AD_FREE_TIERS = {"pro", "premium"}

MAX_MIDROLLS = 3
DEFAULT_MIDROLL_EVERY_MIN = 10


class AdPosition(str, enum.Enum):
    PRE_ROLL = "preroll"
    MID_ROLL = "midroll"
    POST_ROLL = "postroll"


class AdCreative(BaseModel):
    id: str
    title: str
    advertiser: str = "AOEP House"
    media_url: str
    duration_s: int = 15
    click_url: Optional[str] = None
    skippable_after_s: Optional[int] = 5   # None => non-skippable


class AdBreak(BaseModel):
    position: AdPosition
    offset_s: int = 0                      # cue time (mid-roll); 0 for pre-roll
    ads: List[AdCreative] = Field(default_factory=list)


# Small rotating house inventory (stand-in for a real ad server).
HOUSE_INVENTORY: List[AdCreative] = [
    AdCreative(id="house-pro", title="Upgrade to AOEP Pro - go ad-free",
               media_url="https://cdn.example/ads/pro.mp4", duration_s=15,
               click_url="https://aoep.example/membership"),
    AdCreative(id="house-rewards", title="Earn points, win prizes",
               media_url="https://cdn.example/ads/rewards.mp4", duration_s=20,
               click_url="https://aoep.example/rewards"),
    AdCreative(id="house-foryou", title="Personalized classes picked for you",
               media_url="https://cdn.example/ads/foryou.mp4", duration_s=10,
               click_url="https://aoep.example/recommended"),
]


def _fmt_offset(seconds: int) -> str:
    h, rem = divmod(max(0, seconds), 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


def ad_plan_for(
    tier: str,
    *,
    duration_min: int,
    inventory: Optional[List[AdCreative]] = None,
    midroll_every_min: int = DEFAULT_MIDROLL_EVERY_MIN,
    max_midrolls: int = MAX_MIDROLLS,
) -> List[AdBreak]:
    """Return the ad-break schedule for a viewer of `tier` watching a course.

    Paid tiers are ad-free (empty plan). Otherwise: one pre-roll, plus mid-rolls
    every `midroll_every_min` minutes (capped), each filled from the inventory.
    """
    if (tier or "free").lower() in AD_FREE_TIERS:
        return []
    inv = inventory or HOUSE_INVENTORY
    if not inv:
        return []

    breaks: List[AdBreak] = []
    pick = lambda i: inv[i % len(inv)]  # noqa: E731 - tiny rotation helper

    breaks.append(AdBreak(position=AdPosition.PRE_ROLL, offset_s=0, ads=[pick(0)]))

    n = 0
    cue = midroll_every_min
    while cue < duration_min and n < max_midrolls:
        breaks.append(AdBreak(position=AdPosition.MID_ROLL, offset_s=cue * 60,
                              ads=[pick(n + 1)]))
        n += 1
        cue += midroll_every_min
    return breaks


def build_vast(ad: AdCreative) -> str:
    """Minimal IAB VAST 4.0 inline linear ad."""
    skip = f' skipoffset="{_fmt_offset(ad.skippable_after_s)}"' if ad.skippable_after_s else ""
    click = (f"<ClickThrough><![CDATA[{ad.click_url}]]></ClickThrough>"
             if ad.click_url else "")
    return (
        '<VAST version="4.0">'
        f'<Ad id={quoteattr(ad.id)}><InLine>'
        f"<AdSystem>AOEP</AdSystem>"
        f"<AdTitle>{escape(ad.title)}</AdTitle>"
        "<Creatives><Creative><Linear" + skip + ">"
        f"<Duration>{_fmt_offset(ad.duration_s)}</Duration>"
        "<MediaFiles><MediaFile delivery=\"progressive\" type=\"video/mp4\">"
        f"<![CDATA[{ad.media_url}]]></MediaFile></MediaFiles>"
        f"<VideoClicks>{click}</VideoClicks>"
        "</Linear></Creative></Creatives>"
        "</InLine></Ad></VAST>"
    )


def build_vmap(breaks: List[AdBreak]) -> str:
    """Render ad breaks as an IAB VMAP 1.0 document embedding inline VAST."""
    out: List[str] = []
    for i, br in enumerate(breaks):
        if br.position is AdPosition.PRE_ROLL:
            time_offset = "start"
        elif br.position is AdPosition.POST_ROLL:
            time_offset = "end"
        else:
            time_offset = _fmt_offset(br.offset_s)
        vast = build_vast(br.ads[0]) if br.ads else '<VAST version="4.0"/>'
        out.append(
            f'<vmap:AdBreak timeOffset="{time_offset}" breakType="linear" '
            f'breakId="break-{i}"><vmap:AdSource allowMultipleAds="false" '
            'followRedirects="true"><vmap:VASTAdData>'
            + vast +
            "</vmap:VASTAdData></vmap:AdSource></vmap:AdBreak>"
        )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<vmap:VMAP xmlns:vmap="http://www.iab.net/videosuite/vmap" version="1.0">'
        + "".join(out) +
        "</vmap:VMAP>"
    )
