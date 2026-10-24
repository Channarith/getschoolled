"""Source specs and the license gate for the harvester.

``license`` on a SourceSpec is a CLAIM made by whoever wrote the seed. It is only
a pre-fetch filter: nothing is ingested on the claim alone (see licensing.verify_page).
The tiers, parsing and the commercial-use rules live in licensing.py.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

from .licensing import (
    Decision,
    HarvestPolicy,
    LicenseInfo,
    Tier,
    decide,
    parse_license,
    policy_from_env,
)
from .vetted_sources import is_denied

# Declared license ids that are commercially usable with attribution at most.
# Kept for callers that import the name; NC, SA/GFDL, ND, "oer" and unknown ids
# are NOT here. Share-alike is a policy decision (harvest.allow_share_alike).
LICENSE_ALLOWLIST: Set[str] = {
    "cc0", "cc-by", "public-domain", "publicdomain", "pd", "mit", "apache-2.0", "bsd",
}


def normalize_license(license: Optional[str]) -> str:
    return (license or "").strip().lower().replace(" ", "-").replace("_", "-")


def is_allowed(
    license: Optional[str],
    *,
    allowlist: Optional[Set[str]] = None,
    policy: Optional[HarvestPolicy] = None,
) -> bool:
    """True when the declared license may enter the product pipeline.

    ``allowlist`` is an explicit override (tests, special runs). Otherwise the
    license is parsed into a tier: commercially usable tiers pass, share-alike
    passes only when the policy allows it, everything else fails.
    """
    if allowlist is not None:
        return normalize_license(license) in allowlist
    return (policy or policy_from_env()).tier_allowed(parse_license(license).tier)


@dataclass
class SourceSpec:
    url: str
    license: Optional[str] = None
    source_type: str = "html"        # html | pdf | url | transcript | youtube
    subject: Optional[str] = None
    title: Optional[str] = None
    meta: dict = field(default_factory=dict)
    # Seed lists must say who checked the license and when. A seed without these
    # is treated as an unverified claim and the page itself has to confirm it.
    license_verified_by: str = ""
    license_verified_at: str = ""
    license_evidence: str = ""

    def allowed(self, *, allowlist: Optional[Set[str]] = None) -> bool:
        return is_allowed(self.license, allowlist=allowlist)

    def declared(self) -> LicenseInfo:
        return parse_license(self.license)


@dataclass
class PrefetchDecision:
    ok: bool
    needs_detection: bool
    reason: str
    declared: LicenseInfo

    def to_decision(self) -> Decision:
        return Decision("ingest" if self.ok else "reject", self.reason, self.declared)


def spec_allowed(
    spec: "SourceSpec",
    *,
    allowlist: Optional[Set[str]] = None,
    policy: Optional[HarvestPolicy] = None,
    allow_unverified: bool = False,
) -> bool:
    """Gate used by the worker and the catalog pipeline (declared license only)."""
    if allowlist is not None:
        return is_allowed(spec.license, allowlist=allowlist)
    return prefetch_decision(spec, policy, allow_unverified=allow_unverified).ok


def prefetch_decision(
    spec: SourceSpec,
    policy: Optional[HarvestPolicy] = None,
    *,
    allow_unverified: bool = False,
) -> PrefetchDecision:
    """Cheap gate before any fetch.

    Rejects denied hosts and declared licenses that can never be used. An empty
    or unparseable declared license is only let through when ``allow_unverified``
    (the crawler, which then reads the page's own license before ingesting).
    """
    policy = policy or policy_from_env()
    denied = is_denied(spec.url)
    declared = parse_license(spec.license)
    if denied is not None:
        return PrefetchDecision(False, False, f"{denied.domain}: {denied.reason}", declared)
    if declared.known or declared.tier is Tier.PROPRIETARY:
        d = decide(declared, policy)
        return PrefetchDecision(d.ingest, False, d.reason, declared)
    if allow_unverified:
        return PrefetchDecision(True, True, "license not declared: the page must carry one", declared)
    return PrefetchDecision(False, False, "no usable license declared", declared)
