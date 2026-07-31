"""Geo grouping and distance helpers for Salareen live-room discovery (Bigo-style browse)."""

from __future__ import annotations

import math
from typing import Dict, List, TYPE_CHECKING

if TYPE_CHECKING:
    from .live_room import LiveRoom

EARTH_RADIUS_KM = 6371.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Great-circle distance in km between two WGS84 points."""
    if not (lat1 and lon1 and lat2 and lon2):
        return 999_999.0
    rlat1, rlon1, rlat2, rlon2 = map(math.radians, (lat1, lon1, lat2, lon2))
    dlat = rlat2 - rlat1
    dlon = rlon2 - rlon1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlon / 2) ** 2
    return EARTH_RADIUS_KM * 2 * math.asin(math.sqrt(min(1.0, a)))


def room_listing_dict(room: "LiveRoom", *, viewer_lat: float = 0.0, viewer_lng: float = 0.0) -> dict:
    """Compact card for browse feeds — no chat/participant PII beyond counts."""
    dist = haversine_km(viewer_lat, viewer_lng, room.latitude, room.longitude)
    return {
        "room_id": room.room_id,
        "title": room.title,
        "status": room.status,
        "room_size": room.room_size,
        "learner_count": room.learner_count,
        "seats_left": room.seats_left,
        "viewer_count": room.viewer_count or room.learner_count,
        "opened_at": room.opened_at,
        "host_name": room.host().name,
        "creator_name": room.creator_name or room.host().name,
        "country": room.country,
        "state": room.state,
        "city": room.city,
        "latitude": room.latitude,
        "longitude": room.longitude,
        "distance_km": round(dist, 1) if dist < 999_000 else None,
        "class_id": room.class_id,
    }


def group_rooms_by_location(rooms: List["LiveRoom"]) -> List[dict]:
    """Group live rooms: country → state → city → room cards (Bigo-style hierarchy)."""
    tree: Dict[str, Dict[str, Dict[str, List[dict]]]] = {}
    for room in rooms:
        country = (room.country or "Unknown").strip() or "Unknown"
        state = (room.state or "—").strip() or "—"
        city = (room.city or "—").strip() or "—"
        card = room_listing_dict(room)
        tree.setdefault(country, {}).setdefault(state, {}).setdefault(city, []).append(card)

    groups: List[dict] = []
    for country in sorted(tree.keys()):
        states_out: List[dict] = []
        for state in sorted(tree[country].keys()):
            cities_out: List[dict] = []
            for city in sorted(tree[country][state].keys()):
                cards = sorted(
                    tree[country][state][city],
                    key=lambda c: (-(c.get("viewer_count") or 0), c.get("title") or ""),
                )
                cities_out.append({"city": city, "rooms": cards, "count": len(cards)})
            states_out.append({"state": state, "cities": cities_out, "count": sum(c["count"] for c in cities_out)})
        groups.append({
            "country": country,
            "states": states_out,
            "count": sum(s["count"] for s in states_out),
        })
    return groups


def apply_location(
    room: "LiveRoom",
    *,
    country: str = "",
    state: str = "",
    city: str = "",
    latitude: float = 0.0,
    longitude: float = 0.0,
    creator_name: str = "",
    creator_account_id: str = "",
) -> None:
    """Attach geo + creator metadata to a room (in-place)."""
    if country:
        room.country = country.strip()
    if state:
        room.state = state.strip()
    if city:
        room.city = city.strip()
    if latitude:
        room.latitude = float(latitude)
    if longitude:
        room.longitude = float(longitude)
    if creator_name:
        room.creator_name = creator_name.strip()
    if creator_account_id:
        room.creator_account_id = creator_account_id.strip()
