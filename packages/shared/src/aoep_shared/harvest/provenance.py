"""Provenance for harvested material: where it came from, under what license, and
what credit it needs. Recorded in the corpus DB, in every *.course.json, and as an
ATTRIBUTION.txt next to each exported course.

Not legal advice. Share-alike and attribution wording needs the owner's legal review.
"""

from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from .licensing import (Decision, HarvestPolicy, LicenseInfo, PageScan, Tier, Verification,
                        combine_course_license, host_of, info_from_dict)

CREDITS_SLIDE_TITLE = "Sources and licenses"


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def license_label(info: LicenseInfo) -> str:
    if info.family == "pd":
        return "Public domain"
    if info.family == "cc0":
        return "CC0 1.0 Universal (public domain dedication)"
    return info.spdx


def attribution_text(*, title: str, author: str, source_url: str, info: LicenseInfo, site: str = "") -> str:
    """One credit line. Public-domain sources still name the source."""
    who = author or site or host_of(source_url) or "the original author"
    base = f'"{title or source_url}" by {who}, {source_url}'
    if info.family in ("pd", "cc0"):
        return f"{base}. {license_label(info)}."
    lic = license_label(info)
    link = f" ({info.url})" if info.url else ""
    text = f"{base}, licensed under {lic}{link}."
    if info.tier is Tier.SHARE_ALIKE:
        text += f" This course is an adaptation and is shared under the same license ({info.spdx})."
    return text


@dataclass
class Provenance:
    source_url: str
    canonical_url: str = ""
    final_url: str = ""
    fetched_at: str = field(default_factory=_now)
    content_hash: str = ""
    license: Dict[str, Any] = field(default_factory=dict)
    license_tier: str = Tier.UNKNOWN.value
    license_verified_by: str = ""          # page | vetted-site | seed
    declared_license: str = ""
    attribution: Dict[str, str] = field(default_factory=dict)
    obligations: List[str] = field(default_factory=list)
    robots: Dict[str, Any] = field(default_factory=dict)
    recipe: Dict[str, Any] = field(default_factory=dict)
    decision: str = ""
    corpus: str = "product"                # "product" or "research": which side of the wall this came from

    def to_dict(self) -> Dict[str, Any]:
        return {
            "source_url": self.source_url,
            "canonical_url": self.canonical_url,
            "final_url": self.final_url,
            "fetched_at": self.fetched_at,
            "content_hash": self.content_hash,
            "license": self.license,
            "license_tier": self.license_tier,
            "license_verified_by": self.license_verified_by,
            "declared_license": self.declared_license,
            "attribution": self.attribution,
            "obligations": self.obligations,
            "robots": self.robots,
            "recipe": self.recipe,
            "decision": self.decision,
            "corpus": self.corpus,
        }

    def credits_lines(self) -> List[str]:
        lines = [self.attribution.get("text", "")]
        lines += [f"Obligation: {o}" for o in self.obligations]
        return [l for l in lines if l]


def default_recipe() -> Dict[str, Any]:
    return {
        "pipeline": "aoep.harvest.generate_course",
        "model": os.environ.get("AOEP_HARVEST_MODEL", "none (rule-based composition)"),
        "generator_version": os.environ.get("AOEP_VERSION", ""),
    }


def build_provenance(
    *,
    spec_url: str,
    raw: bytes,
    verification: Verification,
    scan: Optional[PageScan],
    fetch_info: Optional[Dict[str, Any]] = None,
    declared: str = "",
    title: str = "",
) -> Provenance:
    fetch_info = fetch_info or {}
    d: Decision = verification.decision
    info: LicenseInfo = d.info
    site = (urlparse(spec_url).hostname or "").removeprefix("www.")
    author = scan.author if scan else ""
    shown_title = (scan.title if scan and scan.title else title) or spec_url
    attribution = {
        "title": shown_title,
        "author": author,
        "source": site,
        "source_url": spec_url,
        "license_name": license_label(info),
        "license_url": info.url,
        "text": attribution_text(title=shown_title, author=author, source_url=spec_url, info=info, site=site),
    }
    return Provenance(
        source_url=spec_url,
        canonical_url=(scan.canonical if scan else "") or "",
        final_url=str(fetch_info.get("final_url") or spec_url),
        fetched_at=str(fetch_info.get("fetched_at") or _now()),
        content_hash=hashlib.sha256(raw).hexdigest(),
        license=info.to_dict(),
        license_tier=info.tier.value,
        license_verified_by=verification.verified_by,
        declared_license=declared,
        attribution=attribution,
        obligations=list(d.obligations),
        robots=dict(fetch_info.get("robots") or {}),
        recipe=default_recipe(),
        decision=d.action,
        corpus=d.corpus or "product",
    )


def attribution_file(prov: Provenance, *, course_title: str = "") -> str:
    """Text for ATTRIBUTION.txt next to an exported course."""
    lines = [f"Sources and licenses{' for ' + course_title if course_title else ''}", "=" * 60, ""]
    lines.append(prov.attribution.get("text", ""))
    lines.append("")
    if prov.obligations:
        lines.append("What this license requires of this course:")
        lines += [f"  - {o}" for o in prov.obligations]
        lines.append("")
    lines += [
        f"Corpus: {prov.corpus}" + ("  (internal research only, never published)" if prov.corpus == "research" else ""),
        f"License tier: {prov.license_tier}",
        f"License evidence: {prov.license.get('evidence', '')} [{prov.license.get('kind', '')}]",
        f"Verified by: {prov.license_verified_by or 'n/a'}",
        f"Fetched: {prov.fetched_at}",
        f"Content hash (sha256): {prov.content_hash}",
        f"Generation: {prov.recipe.get('pipeline', '')} / {prov.recipe.get('model', '')}",
        "",
        "Salareen adapts this material into a course. Attribution above must stay with the course.",
    ]
    return "\n".join(lines) + "\n"


def attach_to_course(course: Any, prov: Provenance) -> None:
    """Put provenance on a GeneratedCourse and append the credits slide once."""
    course.provenance = prov.to_dict()
    slides = getattr(course, "slides", None)
    if slides is None:
        return
    if any(getattr(s, "title", "") == CREDITS_SLIDE_TITLE for s in slides):
        return
    from .generate import GeneratedSlide

    body = "\n".join(prov.credits_lines())
    slides.append(GeneratedSlide(
        title=CREDITS_SLIDE_TITLE,
        body=body,
        narration=("This lesson is based on the source credited on screen. "
                   "Its license and any sharing requirements are listed here."),
        category="resources",
    ))
    comp = getattr(course, "composition", None)
    if comp is not None and hasattr(comp, "add_node"):
        comp.add_node("resources", subnode=CREDITS_SLIDE_TITLE)


def merge_course_provenance(provs: List[Provenance], policy: Optional[HarvestPolicy] = None) -> Dict[str, Any]:
    """License block for a course made from several harvested sources.

    Raises LicenseConflictError when the sources cannot be combined (for example a share-alike source with a
    non-commercial one). Returns {"course_license": ..., "attributions": [...]} for the course JSON.
    """
    lic = combine_course_license([info_from_dict(p.license) for p in provs], policy)
    return {
        "course_license": {
            **lic,
            "note": ("This course is an adaptation of the credited sources and is offered under the same license."
                     if lic["share_alike"] else ""),
        },
        "attributions": [dict(p.attribution) for p in provs],
    }
