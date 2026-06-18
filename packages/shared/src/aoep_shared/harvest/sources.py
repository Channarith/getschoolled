"""Harvest source specs + license gate (the first guard of the 24/7 harvester).

Only permissively-licensed / OER material is allowed into the catalog. The
license gate runs before any fetch so disallowed sources are never downloaded.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Set

# Permissive / open licenses we accept (normalized, lowercase).
LICENSE_ALLOWLIST: Set[str] = {
    "cc0", "cc-by", "cc-by-sa", "cc-by-nc", "cc-by-nc-sa",
    "public-domain", "publicdomain", "pd",
    "mit", "apache-2.0", "bsd", "oer", "gfdl",
}


def normalize_license(license: Optional[str]) -> str:
    return (license or "").strip().lower().replace(" ", "-").replace("_", "-")


def is_allowed(license: Optional[str], *, allowlist: Optional[Set[str]] = None) -> bool:
    return normalize_license(license) in (allowlist or LICENSE_ALLOWLIST)


@dataclass
class SourceSpec:
    url: str
    license: Optional[str] = None
    source_type: str = "html"        # html | pdf | url | transcript | youtube
    subject: Optional[str] = None
    title: Optional[str] = None
    meta: dict = field(default_factory=dict)

    def allowed(self, *, allowlist: Optional[Set[str]] = None) -> bool:
        return is_allowed(self.license, allowlist=allowlist)
