"""Pure helpers: license tiers, stable ids, and composing harvested decks into multi-lesson courses.

The harvester produces lesson-sized decks (~11 slides). The catalog sells *courses*: ~8 lessons
(modules) each. compose_courses() groups decks that belong together (same language, subject and
source series) into courses with a STABLE id derived from the decks' content hashes, so running an
import twice, or importing overlapping bundles, never creates a second copy.

No database, no network: everything here is unit-testable.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence
from urllib.parse import urlparse

DECK_ID_PREFIX = "obj:"  # Module.deck_id for a body that lives in object storage: obj:<sha256>

# Restrictiveness order: a course is only as usable as its most restrictive lesson.
TIER_ORDER = ("owned", "product_safe", "share_alike", "research_only", "unknown")
SERVABLE_TIERS = {"owned", "product_safe"}


def normalize_license(value: Optional[str]) -> str:
    return re.sub(r"[\s_]+", "-", (value or "").strip().lower())


def local_license_tier(license_value: Optional[str]) -> str:
    """Map a VERIFIED license identifier to a tier. Unknown/undefined strings are 'unknown'.

    NC (non-commercial) and ND (no derivatives: we adapt decks into courses) are research_only.
    SA/GFDL need attribution + the same license on the derivative: share_alike, off by default
    until legal review. 'oer' on its own says nothing about the underlying license: unknown.
    """
    lic = normalize_license(license_value)
    if not lic:
        return "unknown"
    if lic in {"owned", "internal", "licensed"}:
        return "owned"
    if re.search(r"(^|-)nc(-|$)|noncommercial|non-commercial", lic) or re.search(r"(^|-)nd(-|$)", lic):
        return "research_only"
    if re.search(r"(^|-)sa(-|$)", lic) or lic.startswith("gfdl"):
        return "share_alike"
    if lic in {"cc0", "cc0-1.0", "public-domain", "publicdomain", "pd", "us-gov", "us-gov-pd"}:
        return "product_safe"
    if re.fullmatch(r"cc-by(-\d(\.\d)?)?", lic):
        return "product_safe"
    if lic in {"mit", "apache-2.0", "apache", "bsd", "bsd-2-clause", "bsd-3-clause", "isc"}:
        return "product_safe"
    return "unknown"


_EXTERNAL_TIER = {
    "commercial_ok": "product_safe",
    "share_alike": "share_alike",
    "non_commercial": "research_only",
    "no_derivatives": "research_only",
    "proprietary": "research_only",
    "unknown": "unknown",
}


def license_tier(license_value: Optional[str]) -> str:
    """The tier for a license id, name or URL: the local mapping, tightened by the harvester's
    parser (aoep_shared.harvest.licensing.parse_license) when it is importable.

    When both know the license and disagree, the more restrictive tier wins; when only the parser
    knows it (a license URL, an SPDX id) its answer is used. A broken or missing optional import can never loosen the gate.
    """
    local = local_license_tier(license_value)
    try:
        from aoep_shared.harvest.licensing import parse_license

        tier = parse_license(license_value).tier
        external = _EXTERNAL_TIER.get(getattr(tier, "value", str(tier)), "unknown")
        if local == "unknown":
            return external  # the harvester's parser also understands license URLs and SPDX ids
        if TIER_ORDER.index(external) > TIER_ORDER.index(local):
            return external
    except Exception:
        pass
    return local


def most_restrictive(tiers: Iterable[str]) -> str:
    worst = "owned"
    for tier in tiers:
        t = tier if tier in TIER_ORDER else "unknown"
        if TIER_ORDER.index(t) > TIER_ORDER.index(worst):
            worst = t
    return worst


def is_servable(tier: str, *, allow_share_alike: bool = False) -> bool:
    return tier in SERVABLE_TIERS or (allow_share_alike and tier == "share_alike")


def canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def course_content_hash(title: str, language: str, subject: str, modules: Sequence[Dict[str, Any]]) -> str:
    """Identity of a course: what it is called and which lessons it holds, in order."""
    body = {
        "title": (title or "").strip(),
        "language": (language or "").strip().lower(),
        "subject": (subject or "").strip().lower(),
        "modules": [
            [str(m.get("title") or ""), str(m.get("deck_id") or ""), str(m.get("scene_id") or "")] for m in modules
        ],
    }
    return hashlib.sha256(canonical_json(body)).hexdigest()


def deck_sha_from_deck_id(deck_id: Optional[str]) -> Optional[str]:
    if deck_id and deck_id.startswith(DECK_ID_PREFIX):
        sha = deck_id[len(DECK_ID_PREFIX):]
        if re.fullmatch(r"[0-9a-f]{64}", sha):
            return sha
    return None


@dataclass
class DeckRef:
    sha256: str
    title: str = ""
    subject: str = "general"
    language: str = "en"
    source_url: str = ""
    license: str = ""
    slides: int = 0
    quality_tier: int = 0
    first_text: str = ""
    harvested_at: str = ""
    attribution: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ComposedCourse:
    course_id: str
    payload: Dict[str, Any]           # a dict accepted by curriculum.catalog.Course(**payload)
    decks: List[DeckRef]
    license_tier: str
    quality_tier: int
    content_hash: str


def _series_key(source_url: str) -> str:
    """Decks from the same book/site area belong together: host + first two path segments."""
    parsed = urlparse(source_url or "")
    parts = [p for p in parsed.path.split("/") if p][:2]
    return (parsed.netloc.lower() + "/" + "/".join(parts)).strip("/")


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (text or "").lower()).strip("-") or "general"


def _title_case(text: str) -> str:
    return " ".join(w[:1].upper() + w[1:] for w in (text or "general").replace("-", " ").replace("_", " ").split())


def compose_courses(
    decks: Iterable[DeckRef],
    *,
    per_course: int = 8,
    min_modules: int = 3,
    allow_share_alike: bool = False,
) -> tuple[List[ComposedCourse], List[tuple[DeckRef, str]]]:
    """Group decks into courses of ~per_course lessons. Returns (courses, rejected).

    Rejected decks are those whose license tier is not servable (research_only, unknown, and
    share_alike unless allowed); they are returned with the reason, never silently dropped.
    """
    if per_course < 1 or min_modules < 1:
        raise ValueError("per_course and min_modules must be >= 1")
    rejected: List[tuple[DeckRef, str]] = []
    groups: Dict[tuple, List[DeckRef]] = {}
    seen: set = set()
    for deck in decks:
        if deck.sha256 in seen:
            continue  # the same body twice in one batch
        seen.add(deck.sha256)
        tier = license_tier(deck.license)
        if not is_servable(tier, allow_share_alike=allow_share_alike):
            rejected.append((deck, f"license tier {tier!r} ({deck.license!r}) cannot serve in the product"))
            continue
        key = ((deck.language or "en").lower(), _slug(deck.subject), _series_key(deck.source_url))
        groups.setdefault(key, []).append(deck)

    courses: List[ComposedCourse] = []
    for (language, subject_slug, series), members in sorted(groups.items()):
        members.sort(key=lambda d: (d.source_url, d.title, d.sha256))
        chunks = [members[i:i + per_course] for i in range(0, len(members), per_course)]
        if len(chunks) > 1 and len(chunks[-1]) < min_modules:
            tail = chunks.pop()
            chunks[-1].extend(tail)  # an over-full last course beats a 1-lesson stub
        for part, chunk in enumerate(chunks, 1):
            courses.append(_build(chunk, language, subject_slug, series, part, len(chunks)))
    return courses, rejected


def _build(chunk: List[DeckRef], language: str, subject_slug: str, series: str, part: int, parts: int) -> ComposedCourse:
    sha_id = hashlib.sha256("|".join(sorted(d.sha256 for d in chunk)).encode()).hexdigest()
    course_id = "hc" + sha_id[:16]
    subject = _title_case(subject_slug)
    label = series.split("/", 1)[-1].replace("/", " ").replace("-", " ").strip()
    title = f"{subject}: {label.title()}" if label else subject
    if parts > 1:
        title += f" (Part {part})"
    modules = [
        {
            "module_id": f"m{i + 1}-{d.sha256[:8]}",
            "title": d.title or f"Lesson {i + 1}",
            "deck_id": DECK_ID_PREFIX + d.sha256,
            "order": i,
        }
        for i, d in enumerate(chunk)
    ]
    tiers = [license_tier(d.license) for d in chunk]
    lic_tier = most_restrictive(tiers)
    quality = min(d.quality_tier for d in chunk)
    first = (chunk[0].first_text or "").strip()
    host = series.split("/", 1)[0]
    payload = {
        "course_id": course_id,
        "title": title,
        "subject": subject_slug,
        "language": language,
        "description": first[:300],
        "preview": first[:160],
        "media_format": "text",
        "level": "beginner",
        "duration_min": sum(max(d.slides, 1) for d in chunk) * 2,
        "modules": modules,
        "validation_status": "validated" if quality >= 1 else "unvalidated",
        "tags": [
            "harvest",
            f"sha:{sha_id[:16]}",
            f"tier:{quality}",
            f"license:{lic_tier}",
        ] + ([f"source:{host}"] if host else []),
        "source": "harvest",
        "source_fingerprint": sha_id,
    }
    return ComposedCourse(
        course_id=course_id,
        payload=payload,
        decks=chunk,
        license_tier=lic_tier,
        quality_tier=quality,
        content_hash=course_content_hash(title, language, subject_slug, modules),
    )
