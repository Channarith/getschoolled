"""Profile avatar catalog — Realistic and Cute styles with stable IDs.

Locally bundled SVG assets live at /avatars/{id}.svg (web) and
apps/mobile/assets/avatars/{id}.svg (mobile). No runtime network dependency.
Legacy IDs (empty, logo/mascot placeholders, initials) resolve gracefully so
persisted accounts keep working after the redesign.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, List, Literal, Optional

AvatarStyle = Literal["realistic", "cute"]

DEFAULT_AVATAR_ID = "r-nova"
AVATAR_ASSET_PREFIX = "/avatars"
AVATAR_ASSET_EXT = "svg"


@dataclass(frozen=True)
class AvatarEntry:
    id: str
    label: str
    style: AvatarStyle
    alt: str
    skin: str = ""
    hair: str = ""
    accessories: str = ""
    expression: str = "warm smile"


AVATAR_CATALOG: Dict[str, AvatarEntry] = {
    # --- Realistic (illustrated portrait, polished, recognizable at small size) ---
    "r-nova": AvatarEntry(
        "r-nova", "Nova", "realistic",
        "Portrait of Nova, medium-brown skin, short curly hair, round glasses",
        skin="medium-brown", hair="short curly dark brown", accessories="round glasses",
    ),
    "r-amir": AvatarEntry(
        "r-amir", "Amir", "realistic",
        "Portrait of Amir, deep brown skin, short fade haircut, warm smile",
        skin="deep brown", hair="short fade black",
    ),
    "r-mei": AvatarEntry(
        "r-mei", "Mei", "realistic",
        "Portrait of Mei, light-medium skin, sleek bob, soft smile",
        skin="light-medium", hair="black bob",
    ),
    "r-sofia": AvatarEntry(
        "r-sofia", "Sofia", "realistic",
        "Portrait of Sofia, olive skin, long wavy hair, gold hoop earrings",
        skin="olive", hair="long wavy chestnut", accessories="gold hoops",
    ),
    "r-jordan": AvatarEntry(
        "r-jordan", "Jordan", "realistic",
        "Portrait of Jordan, fair skin with freckles, short auburn hair",
        skin="fair freckled", hair="short auburn",
    ),
    "r-kai": AvatarEntry(
        "r-kai", "Kai", "realistic",
        "Portrait of Kai, tan skin, textured coils under a soft beanie",
        skin="tan", hair="textured coils", accessories="slate beanie",
    ),
    "r-priya": AvatarEntry(
        "r-priya", "Priya", "realistic",
        "Portrait of Priya, warm brown skin, long dark hair with side part",
        skin="warm brown", hair="long dark side-part",
    ),
    "r-leo": AvatarEntry(
        "r-leo", "Leo", "realistic",
        "Portrait of Leo, medium-dark skin, short locs, clear glasses",
        skin="medium-dark", hair="short locs", accessories="clear glasses",
    ),
    "r-sam": AvatarEntry(
        "r-sam", "Sam", "realistic",
        "Portrait of Sam, light skin, silver-streak short hair, kind smile",
        skin="light", hair="short silver-streak", expression="kind smile",
    ),
    # --- Cute (friendly rounded characters people will love) ---
    "c-peach": AvatarEntry(
        "c-peach", "Peach", "cute",
        "Cute avatar Peach, peachy skin, pigtails, rosy cheeks",
        skin="peach", hair="brown pigtails", accessories="blush cheeks",
    ),
    "c-mint": AvatarEntry(
        "c-mint", "Mint", "cute",
        "Cute avatar Mint, soft skin, mint bob hair, freckles",
        skin="soft ivory", hair="mint bob", accessories="freckles",
    ),
    "c-coco": AvatarEntry(
        "c-coco", "Coco", "cute",
        "Cute avatar Coco, deep brown skin, afro puffs, star hair clip",
        skin="deep brown", hair="afro puffs", accessories="star clip",
    ),
    "c-sky": AvatarEntry(
        "c-sky", "Sky", "cute",
        "Cute avatar Sky, light skin, blue beanie, round cheeks",
        skin="light", hair="hidden under beanie", accessories="sky-blue beanie",
    ),
    "c-honey": AvatarEntry(
        "c-honey", "Honey", "cute",
        "Cute avatar Honey, golden skin, messy bun, round glasses",
        skin="golden", hair="messy bun", accessories="round glasses",
    ),
    "c-berry": AvatarEntry(
        "c-berry", "Berry", "cute",
        "Cute avatar Berry, medium skin, curly bangs, heart hair clip",
        skin="medium", hair="curly bangs", accessories="heart clip",
    ),
    "c-moss": AvatarEntry(
        "c-moss", "Moss", "cute",
        "Cute avatar Moss, olive skin, short fluffy hair, headphones",
        skin="olive", hair="short fluffy", accessories="headphones",
    ),
    "c-luna": AvatarEntry(
        "c-luna", "Luna", "cute",
        "Cute avatar Luna, pale skin, silver hair, crescent pin",
        skin="pale", hair="silver bob", accessories="crescent pin",
    ),
    "c-sunny": AvatarEntry(
        "c-sunny", "Sunny", "cute",
        "Cute avatar Sunny, warm brown skin, cornrows, bright smile",
        skin="warm brown", hair="cornrows",
    ),
}

# Graceful migration for pre-catalog / placeholder values persisted on accounts.
LEGACY_AVATAR_ALIASES: Dict[str, str] = {
    "": DEFAULT_AVATAR_ID,
    "default": DEFAULT_AVATAR_ID,
    "none": DEFAULT_AVATAR_ID,
    "null": DEFAULT_AVATAR_ID,
    "undefined": DEFAULT_AVATAR_ID,
    "logo": "c-sunny",
    "logo-mark": "c-sunny",
    "bayon": "c-sunny",
    "bayon-buddy": "c-sunny",
    "mascot": "c-sunny",
    "salareen-mascot": "c-sunny",
    "initials": DEFAULT_AVATAR_ID,
    "emoji": "c-peach",
    "graduate": "c-sunny",
    "theodore": "c-moss",
    "ai-host": "c-moss",
    "presenter-male": "r-amir",
    "presenter-female": "r-sofia",
}


def avatar_asset_path(avatar_id: str, *, ext: str = AVATAR_ASSET_EXT) -> str:
    resolved = resolve_avatar_id(avatar_id)
    return f"{AVATAR_ASSET_PREFIX}/{resolved}.{ext}"


def resolve_avatar_id(avatar_id: Optional[str]) -> str:
    """Map a stored / legacy ID to a catalog ID (never raises)."""
    raw = (avatar_id or "").strip().lower()
    if raw in LEGACY_AVATAR_ALIASES:
        return LEGACY_AVATAR_ALIASES[raw]
    if raw in AVATAR_CATALOG:
        return raw
    # Tolerate prefixed legacy forms like "avatar:logo" or "profile/logo".
    for sep in (":", "/", "."):
        if sep in raw:
            tail = raw.split(sep)[-1]
            if tail in LEGACY_AVATAR_ALIASES:
                return LEGACY_AVATAR_ALIASES[tail]
            if tail in AVATAR_CATALOG:
                return tail
    return DEFAULT_AVATAR_ID


def get_avatar(avatar_id: Optional[str]) -> AvatarEntry:
    return AVATAR_CATALOG[resolve_avatar_id(avatar_id)]


def resolve_avatar(avatar_id: Optional[str]) -> Dict:
    entry = get_avatar(avatar_id)
    return {
        "id": entry.id,
        "label": entry.label,
        "style": entry.style,
        "alt": entry.alt,
        "path": avatar_asset_path(entry.id),
        "skin": entry.skin,
        "hair": entry.hair,
        "accessories": entry.accessories,
        "expression": entry.expression,
        "resolved_from": (avatar_id or "").strip() or None,
    }


def avatar_catalog_list(*, style: Optional[str] = None) -> List[Dict]:
    items = []
    for entry in AVATAR_CATALOG.values():
        if style and entry.style != style:
            continue
        items.append({
            **asdict(entry),
            "path": avatar_asset_path(entry.id),
        })
    return items


def avatar_styles() -> List[Dict[str, str]]:
    return [
        {"id": "realistic", "label": "Realistic", "description": "Warm illustrated portraits"},
        {"id": "cute", "label": "Cute", "description": "Friendly rounded characters"},
    ]


def is_known_avatar_id(avatar_id: str) -> bool:
    return resolve_avatar_id(avatar_id) in AVATAR_CATALOG and (
        (avatar_id or "").strip().lower() in AVATAR_CATALOG
        or (avatar_id or "").strip().lower() in LEGACY_AVATAR_ALIASES
        or not (avatar_id or "").strip()
    )
