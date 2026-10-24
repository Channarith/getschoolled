"""Vetted open sources and the do-not-harvest list.

Evidence for every entry is in docs/harvest-sources.txt (URL + retrieval date).
Retrieved 2026-10-24. Not legal advice; share-alike and attribution handling
needs the owner's legal review.

A VETTED entry lets a page with NO license evidence of its own inherit the
site-wide license. It never overrides evidence on the page: a page that carries
a different license, an all-rights-reserved notice, noai/noindex or a paywall is
still rejected. Hosts whose license varies per item (LibreTexts, OER Commons,
Open Textbook Library, Internet Archive, Saylor third-party resources) are NOT
vetted: the page itself must carry the license.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple
from urllib.parse import urlparse

from .licensing import LicenseInfo, host_of, parse_license, registered_host_matches

VERIFIED_AT = "2026-10-24"


@dataclass(frozen=True)
class VettedSource:
    domain: str
    license: str                    # parsed with parse_license
    basis_url: str                  # primary source for the claim
    verified_at: str = VERIFIED_AT
    exclude_path_prefixes: Tuple[str, ...] = ()
    notes: str = ""

    def info(self) -> LicenseInfo:
        base = parse_license(self.license, kind="vetted")
        return LicenseInfo(base.spdx, base.tier, base.family, base.version, base.port,
                           self.basis_url, f"vetted site {self.domain} ({self.basis_url})", "vetted")


VETTED_SOURCES: Tuple[VettedSource, ...] = (
    # Share-alike: ingested only when harvest.allow_share_alike is on.
    VettedSource(
        "wikipedia.org", "CC BY-SA 4.0",
        "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
        notes="Text is CC BY-SA 4.0 and GFDL (dual). Images and files carry their own licenses: text only.",
    ),
    VettedSource("wikibooks.org", "CC BY-SA 4.0", "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
                 notes="Same Wikimedia terms. Text only."),
    VettedSource("wikiversity.org", "CC BY-SA 4.0", "https://foundation.wikimedia.org/wiki/Policy:Terms_of_Use",
                 notes="Same Wikimedia terms. Text only."),
    # US government works (17 U.S.C. 105). Page-level notices still override.
    VettedSource(
        "nasa.gov", "US Government Work",
        "https://www.nasa.gov/nasa-brand-center/images-and-media/",
        notes="NASA content is generally not subject to US copyright; items marked as third-party are copyrighted; "
              "the NASA insignia is not public domain.",
    ),
    VettedSource(
        "medlineplus.gov", "US Government Work",
        "https://medlineplus.gov/about/using/usingcontent/",
        exclude_path_prefixes=("/ency/", "/druginfo/"),
        notes="Health topic summaries, tests and genetics pages are public domain. The A.D.A.M. encyclopedia "
              "(/ency/) and drug monographs (/druginfo/) are copyrighted and excluded.",
    ),
    VettedSource("nih.gov", "US Government Work", "https://www.nlm.nih.gov/web_policies.html",
                 notes="Federal works; marked third-party material is copyrighted."),
    VettedSource("eeoc.gov", "US Government Work", "https://www.copyright.gov/title17/92chap1.html",
                 notes="Federal agency pages (17 U.S.C. 105)."),
    VettedSource("dol.gov", "US Government Work", "https://www.copyright.gov/title17/92chap1.html",
                 notes="Federal agency pages (17 U.S.C. 105)."),
    VettedSource("osha.gov", "US Government Work", "https://www.copyright.gov/title17/92chap1.html",
                 notes="Federal agency pages (17 U.S.C. 105)."),
    VettedSource("census.gov", "US Government Work", "https://www.copyright.gov/title17/92chap1.html",
                 notes="Federal agency pages (17 U.S.C. 105)."),
    VettedSource(
        "gutenberg.org", "Public Domain",
        "https://www.gutenberg.org/policy/permission.html",
        notes="Most eBooks are public domain in the US only; other countries may differ. Remove the Project "
              "Gutenberg trademark/licence boilerplate (commercial use of the name needs a royalty).",
    ),
)


@dataclass(frozen=True)
class Denied:
    domain: str
    reason: str
    basis_url: str = ""


# Never harvested for the product. (A research-only corpus is a separate, opt-in switch.)
DENYLIST: Tuple[Denied, ...] = (
    Denied("khanacademy.org", "content is CC BY-NC-SA 4.0 and the Terms of Service forbid scraping and AI training use",
           "https://support.khanacademy.org/hc/en-us/articles/42929097425037-What-s-allowed-and-not-allowed-under-Khan-Academy-s-Terms-of-Service"),
    Denied("openstax.org", "textbooks are CC BY-NC-SA 4.0 (non-commercial); commercial use needs OpenStax permission",
           "https://help.openstax.org/s/article/Licensing-information-of-OpenStax-textbooks"),
    Denied("ocw.mit.edu", "MIT OpenCourseWare is CC BY-NC-SA 4.0: commercial use not permitted",
           "https://ocw.mit.edu/pages/privacy-and-terms-of-use/"),
    Denied("ck12.org", "CK-12 content is CC BY-NC-SA 3.0 / CK-12 curriculum materials license (non-commercial)",
           "https://info.ck12.org/terms-of-use"),
    Denied("coursera.org", "proprietary platform content; terms of service do not grant reuse"),
    Denied("udemy.com", "proprietary platform content; terms of service do not grant reuse"),
    Denied("edx.org", "proprietary platform content; terms of service do not grant reuse"),
    Denied("skillshare.com", "proprietary platform content"),
    Denied("linkedin.com", "login-walled proprietary content"),
    Denied("quizlet.com", "user-generated content under platform terms"),
    Denied("chegg.com", "proprietary and paywalled"),
    Denied("coursehero.com", "proprietary and paywalled"),
    Denied("youtube.com", "captions and videos are not openly licensed course text"),
    Denied("youtu.be", "captions and videos are not openly licensed course text"),
    Denied("vimeo.com", "videos are not openly licensed course text"),
    Denied("arxiv.org", "most papers use arXiv's non-exclusive licence, which grants no reuse rights; "
                         "only per-paper CC licences shown on the abs page could qualify",
           "https://info.arxiv.org/help/license/reuse.html"),
)

# Hosts whose license is per item: allowed only when the page itself carries the license.
PER_ITEM_HOSTS: Tuple[str, ...] = (
    "libretexts.org", "oercommons.org", "open.umn.edu", "archive.org", "saylor.org", "learn.saylor.org",
)


def is_denied(url_or_host: str) -> Optional[Denied]:
    host = url_or_host if "/" not in url_or_host and ":" not in url_or_host else host_of(url_or_host)
    host = (host or "").lower()
    if not host:
        return None
    hit = registered_host_matches(host, (d.domain for d in DENYLIST))
    return next((d for d in DENYLIST if d.domain == hit), None) if hit else None


def vetted_for(url: str) -> Optional[VettedSource]:
    host = host_of(url)
    if not host:
        return None
    hit = registered_host_matches(host, (v.domain for v in VETTED_SOURCES))
    if not hit:
        return None
    entry = next(v for v in VETTED_SOURCES if v.domain == hit)
    path = urlparse(url).path or "/"
    if any(path.startswith(p) for p in entry.exclude_path_prefixes):
        return None
    return entry


def is_per_item_host(url: str) -> bool:
    host = host_of(url)
    return bool(host and registered_host_matches(host, PER_ITEM_HOSTS))


def registry_summary() -> Dict[str, list]:
    return {
        "vetted": [v.domain for v in VETTED_SOURCES],
        "denied": [d.domain for d in DENYLIST],
        "per_item": list(PER_ITEM_HOSTS),
    }
