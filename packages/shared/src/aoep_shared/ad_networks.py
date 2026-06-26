"""Ad network connector — house inventory + third-party SSP hooks.

Configure via env:
  AD_NETWORK=house|google_adsense|google_ad_manager|meta_audience
  ADSENSE_CLIENT=ca-pub-xxxxxxxx
  GAM_AD_UNIT=/network/unit
  META_PLACEMENT_ID=xxxxxxxx

Production: register with each network, obtain publisher IDs, and set the env
vars in cloud config. Local/dev defaults to rotating house promos (no keys).
"""

from __future__ import annotations

import enum
import os
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class AdNetworkId(str, enum.Enum):
    HOUSE = "house"
    GOOGLE_ADSENSE = "google_adsense"
    GOOGLE_AD_MANAGER = "google_ad_manager"
    META_AUDIENCE = "meta_audience"


class AdSlotConfig(BaseModel):
    slot_id: str
    network: AdNetworkId
    width: int = 728
    height: int = 90
    label: str = ""
    # Third-party identifiers (when configured).
    client_id: str = ""
    ad_unit_path: str = ""
    placement_id: str = ""
    # House / fallback creative.
    click_url: str = ""
    image_url: str = ""
    script_url: str = ""


HOUSE_SLOTS: List[AdSlotConfig] = [
    AdSlotConfig(
        slot_id="home-banner",
        network=AdNetworkId.HOUSE,
        width=728, height=90,
        label="Upgrade to Salareen Pro — learn ad-free",
        click_url="/billing",
        image_url="https://cdn.example/ads/pro-banner.png",
    ),
    AdSlotConfig(
        slot_id="class-midroll",
        network=AdNetworkId.HOUSE,
        width=300, height=250,
        label="Earn rewards while you learn",
        click_url="/rewards",
        image_url="https://cdn.example/ads/rewards-rect.png",
    ),
]


def active_network() -> AdNetworkId:
    raw = (os.environ.get("AD_NETWORK") or "house").strip().lower()
    try:
        return AdNetworkId(raw)
    except ValueError:
        return AdNetworkId.HOUSE


def network_configured(network: AdNetworkId) -> bool:
    if network == AdNetworkId.HOUSE:
        return True
    if network == AdNetworkId.GOOGLE_ADSENSE:
        return bool(os.environ.get("ADSENSE_CLIENT", "").strip())
    if network == AdNetworkId.GOOGLE_AD_MANAGER:
        return bool(os.environ.get("GAM_AD_UNIT", "").strip())
    if network == AdNetworkId.META_AUDIENCE:
        return bool(os.environ.get("META_PLACEMENT_ID", "").strip())
    return False


def resolve_slot(slot_id: str, *, tier: str = "free") -> Optional[Dict[str, Any]]:
    """Return ad slot payload for a viewer tier. VIP/paid tiers get no display ads."""
    from .ads import AD_FREE_TIERS

    if (tier or "free").lower() in AD_FREE_TIERS:
        return None

    network = active_network()
    if not network_configured(network):
        network = AdNetworkId.HOUSE

    base = next((s for s in HOUSE_SLOTS if s.slot_id == slot_id), HOUSE_SLOTS[0])
    payload: Dict[str, Any] = {
        "slot_id": slot_id,
        "network": network.value,
        "width": base.width,
        "height": base.height,
        "label": base.label,
    }

    if network == AdNetworkId.GOOGLE_ADSENSE:
        client = os.environ.get("ADSENSE_CLIENT", "")
        payload.update({
            "client_id": client,
            "script_url": f"https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client={client}",
            "data_ad_slot": os.environ.get("ADSENSE_SLOT_" + slot_id.upper(), ""),
            "data_ad_format": "auto",
            "data_full_width_responsive": True,
        })
    elif network == AdNetworkId.GOOGLE_AD_MANAGER:
        payload.update({
            "ad_unit_path": os.environ.get("GAM_AD_UNIT", ""),
            "script_url": "https://securepubads.g.doubleclick.net/tag/js/gpt.js",
        })
    elif network == AdNetworkId.META_AUDIENCE:
        payload.update({
            "placement_id": os.environ.get("META_PLACEMENT_ID", ""),
            "script_url": "https://connect.facebook.net/en_US/fbad.js",
        })
    else:
        payload.update({
            "click_url": base.click_url,
            "image_url": base.image_url,
            "house": True,
        })
    return payload


def list_networks() -> List[Dict[str, Any]]:
    """Onboarding doc for operators — which networks are configured."""
    rows = []
    for net in AdNetworkId:
        rows.append({
            "id": net.value,
            "configured": network_configured(net),
            "env": {
                AdNetworkId.GOOGLE_ADSENSE: ["ADSENSE_CLIENT", "ADSENSE_SLOT_*"],
                AdNetworkId.GOOGLE_AD_MANAGER: ["GAM_AD_UNIT"],
                AdNetworkId.META_AUDIENCE: ["META_PLACEMENT_ID"],
            }.get(net, []),
        })
    return rows
