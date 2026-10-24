"""License tiers, parsing, page-level detection and the harvest decision.

Salareen sells subscriptions, so the product catalog may only contain material
we may use commercially and adapt into courses. The old flat allowlist treated
``cc-by-nc``, ``cc-by-nc-sa``, ``oer`` and any caller-supplied string as fine.
This module replaces it:

  Tier.COMMERCIAL_OK   CC0, public domain, CC BY, MIT, Apache-2.0, BSD
  Tier.SHARE_ALIKE     CC BY-SA, GFDL (commercial use needs attribution AND the derivative
                       course must carry the same license); product corpus only when the
                       policy switch is on, otherwise research corpus
  Tier.NON_COMMERCIAL  any NC variant        -> RESEARCH corpus only, never the product
  Tier.NO_DERIVATIVES  ND without NC         -> rejected (we adapt content)
  Tier.PROPRIETARY     all rights reserved   -> rejected
  Tier.UNKNOWN         unparseable / empty / "oer" -> rejected

TWO CORPORA, ONE HARD WALL
  PRODUCT corpus   commercial-OK tier only (plus share-alike when the owner turns it on). The only
                   corpus that may be published to the catalog, translated for customers or shown
                   in the apps.
  RESEARCH corpus  non-commercial (and share-alike while that switch is off) text that is lawful to
                   read. Internal model evaluation and training experiments only. Never published,
                   never behind an API, never mixed into course catalogs. Separate database file;
                   corpus_store enforces the wall and publishing re-asserts it.
  Rejected outright in both: all rights reserved, no-derivatives, unknown or empty license,
  login/paywalled pages, noai/noindex pages, and the do-not-harvest hosts.

A license string supplied by a seed list is a CLAIM. It is only trusted when
the page itself says the same thing (link rel=license, meta tags, schema.org
license, JSON-LD, footer text) or the host is in the vetted-source registry.
Conflicting evidence rejects the page.

Not legal advice: share-alike and attribution handling needs legal review.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from enum import Enum
from html.parser import HTMLParser
from typing import Iterable, List, Optional, Sequence
from urllib.parse import urlparse


class Tier(str, Enum):
    COMMERCIAL_OK = "commercial_ok"
    SHARE_ALIKE = "share_alike"
    NON_COMMERCIAL = "non_commercial"
    NO_DERIVATIVES = "no_derivatives"
    PROPRIETARY = "proprietary"
    UNKNOWN = "unknown"


RESTRICTIVE_TIERS = frozenset({Tier.NON_COMMERCIAL, Tier.NO_DERIVATIVES, Tier.PROPRIETARY})


@dataclass(frozen=True)
class LicenseInfo:
    spdx: str = "UNKNOWN"          # canonical id, e.g. CC-BY-4.0, CC-BY-NC-SA-3.0, CC0-1.0
    tier: Tier = Tier.UNKNOWN
    family: str = ""               # by, by-sa, by-nc, ... cc0, pd, mit, apache, bsd, gfdl
    version: str = ""
    port: str = ""                 # jurisdiction port, e.g. de, igo
    url: str = ""                  # canonical license url when known
    evidence: str = ""             # the snippet / attribute the decision came from
    kind: str = "declared"         # declared | url | rel-license | meta | schema | jsonld | footer | vetted

    @property
    def known(self) -> bool:
        return self.tier is not Tier.UNKNOWN

    def to_dict(self) -> dict:
        return {
            "spdx": self.spdx, "tier": self.tier.value, "family": self.family,
            "version": self.version, "port": self.port, "url": self.url,
            "evidence": self.evidence[:300], "kind": self.kind,
        }


UNKNOWN_LICENSE = LicenseInfo()

_CC_URL = re.compile(
    r"creativecommons\.org/licenses/(?P<fam>by(?:-nc)?(?:-sa|-nd)?)/(?P<ver>\d\.\d)(?:/(?P<port>[a-z]{2,4}))?",
    re.I,
)
_CC_PD_URL = re.compile(r"creativecommons\.org/publicdomain/(?P<kind>zero|mark)/(?P<ver>\d\.\d)", re.I)
_CC_TOKEN = re.compile(
    r"\bcc[\s_-]*by(?P<nc>[\s_-]*nc)?(?P<mod>[\s_-]*(?:sa|nd))?(?:[\s_-]*(?P<ver>\d(?:\.\d)?))?\b",
    re.I,
)
_CC_WORDS = re.compile(
    r"creative\s+commons\s+attribution"
    r"(?P<nc>[\s-]*non[\s-]?commercial)?"
    r"(?P<mod>[\s-]*(?:share[\s-]?alike|no[\s-]?deriv(?:ative)?s?))?"
    r"(?:[^0-9]{0,40}?(?P<ver>\d\.\d))?",
    re.I,
)
_CC_BARE = re.compile(
    r"\battribution"
    r"(?P<nc>[\s-]*non[\s-]?commercial)?"
    r"(?P<mod>[\s-]*(?:share[\s-]?alike|no[\s-]?deriv(?:ative)?s?))?"
    r"[\s-]*(?P<ver>\d\.\d)\b",
    re.I,
)
_NONCOMMERCIAL_WORD = re.compile(r"non[\s_-]?commercial|\bnc\b", re.I)
_CC0_TOKEN = re.compile(r"\bcc[\s_-]*0\b|\bcc[\s_-]*zero\b|public\s+domain\s+dedication", re.I)
_PD_TOKEN = re.compile(
    r"\b(public[\s_-]*domain|publicdomain|pd|pdm|u\.?s\.?\s+government\s+work|"
    r"united\s+states\s+government\s+work|work\s+of\s+the\s+u\.?s\.?\s+government)\b",
    re.I,
)
_ARR_TOKEN = re.compile(
    r"all[\s_-]*rights[\s_-]*reserved|proprietary|not\s+licensed\s+for\s+reuse|"
    r"no\s+reuse|copyrighted|commercial\s+license\s+required",
    re.I,
)
_MIT = re.compile(r"^\s*mit(?:[\s-]license)?\s*$|\bmit\s+license\b", re.I)
_APACHE = re.compile(r"\bapache(?:[\s-]license)?[\s-]*(?:version\s*)?2(?:\.0)?\b", re.I)
_BSD = re.compile(r"\bbsd(?:[\s-]*[23][\s-]*clause)?\b", re.I)
_GFDL = re.compile(r"\bgfdl\b|gnu\s+free\s+documentation", re.I)


def _cc(fam: str, ver: str = "", port: str = "", url: str = "", evidence: str = "", kind: str = "declared") -> LicenseInfo:
    fam = fam.lower()
    parts = set(fam.split("-")) - {"by"}
    if "nc" in parts:
        tier = Tier.NON_COMMERCIAL
    elif "nd" in parts:
        tier = Tier.NO_DERIVATIVES
    elif "sa" in parts:
        tier = Tier.SHARE_ALIKE
    else:
        tier = Tier.COMMERCIAL_OK
    spdx = "CC-" + fam.upper() + (f"-{ver}" if ver else "")
    if port:
        spdx += f"-{port.upper()}"
    return LicenseInfo(spdx=spdx, tier=tier, family=fam, version=ver, port=port.lower(), url=url,
                       evidence=evidence, kind=kind)


def parse_license(text: Optional[str], *, kind: str = "declared") -> LicenseInfo:
    """Parse a license id, name or URL. Unparseable input is Tier.UNKNOWN."""
    raw = (text or "").strip()
    if not raw:
        return UNKNOWN_LICENSE
    ev = raw[:300]

    m = _CC_URL.search(raw)
    if m:
        return _cc(m.group("fam"), m.group("ver"), m.group("port") or "", url=_clean_url(raw), evidence=ev,
                   kind="url" if kind == "declared" else kind)
    m = _CC_PD_URL.search(raw)
    if m:
        if m.group("kind").lower() == "zero":
            return LicenseInfo("CC0-1.0", Tier.COMMERCIAL_OK, "cc0", m.group("ver"), url=_clean_url(raw), evidence=ev, kind=kind)
        return LicenseInfo("PDM-1.0", Tier.COMMERCIAL_OK, "pd", m.group("ver"), url=_clean_url(raw), evidence=ev, kind=kind)

    if _ARR_TOKEN.search(raw) and not (_CC_TOKEN.search(raw) or _CC_WORDS.search(raw)):
        return LicenseInfo("ALL-RIGHTS-RESERVED", Tier.PROPRIETARY, "arr", evidence=ev, kind=kind)

    m = _CC_WORDS.search(raw)
    if m:
        fam = "by"
        if m.group("nc"):
            fam += "-nc"
        mod = (m.group("mod") or "").lower()
        if "share" in mod:
            fam += "-sa"
        elif "deriv" in mod:
            fam += "-nd"
        return _cc(fam, m.group("ver") or "", evidence=ev, kind=kind)
    m = _CC_BARE.search(raw)
    if m:
        fam = "by"
        if m.group("nc"):
            fam += "-nc"
        mod = (m.group("mod") or "").lower()
        if "share" in mod:
            fam += "-sa"
        elif "deriv" in mod:
            fam += "-nd"
        return _cc(fam, m.group("ver") or "", evidence=ev, kind=kind)
    m = _CC_TOKEN.search(raw)
    if m:
        fam = "by"
        if m.group("nc"):
            fam += "-nc"
        if m.group("mod"):
            fam += "-" + re.sub(r"[\s_-]", "", m.group("mod")).lower()
        return _cc(fam, m.group("ver") or "", evidence=ev, kind=kind)
    if _CC0_TOKEN.search(raw):
        return LicenseInfo("CC0-1.0", Tier.COMMERCIAL_OK, "cc0", "1.0", evidence=ev, kind=kind)
    if _GFDL.search(raw):
        return LicenseInfo("GFDL", Tier.SHARE_ALIKE, "gfdl", evidence=ev, kind=kind)
    if _APACHE.search(raw):
        return LicenseInfo("Apache-2.0", Tier.COMMERCIAL_OK, "apache", "2.0", evidence=ev, kind=kind)
    if _MIT.search(raw):
        return LicenseInfo("MIT", Tier.COMMERCIAL_OK, "mit", evidence=ev, kind=kind)
    if _BSD.search(raw):
        return LicenseInfo("BSD", Tier.COMMERCIAL_OK, "bsd", evidence=ev, kind=kind)
    if _PD_TOKEN.search(raw):
        return LicenseInfo("PD", Tier.COMMERCIAL_OK, "pd", evidence=ev, kind=kind)
    if _ARR_TOKEN.search(raw):
        return LicenseInfo("ALL-RIGHTS-RESERVED", Tier.PROPRIETARY, "arr", evidence=ev, kind=kind)
    if _NONCOMMERCIAL_WORD.search(raw):
        return LicenseInfo("NON-COMMERCIAL", Tier.NON_COMMERCIAL, "nc", evidence=ev, kind=kind)
    # "oer", "open", "free", bare "creative commons": no usable terms.
    return LicenseInfo("UNKNOWN", Tier.UNKNOWN, evidence=ev, kind=kind)


def _clean_url(raw: str) -> str:
    m = re.search(r"https?://[^\s\"'<>]+", raw)
    return m.group(0) if m else ""


# ---------------------------------------------------------------- policy

@dataclass(frozen=True)
class HarvestPolicy:
    allow_share_alike: bool = False     # default OFF until the owner decides (legal review)
    research_enabled: bool = True       # keep non-product-but-lawful text in the research corpus (ON by default)

    def tier_allowed(self, tier: Tier) -> bool:
        """May this tier enter the PRODUCT corpus?"""
        if tier is Tier.COMMERCIAL_OK:
            return True
        return tier is Tier.SHARE_ALIKE and self.allow_share_alike

    def research_eligible(self, tier: Tier) -> bool:
        """May this tier enter the RESEARCH corpus? (non-commercial, or share-alike while it is off)"""
        if not self.research_enabled:
            return False
        return tier is Tier.NON_COMMERCIAL or (tier is Tier.SHARE_ALIKE and not self.allow_share_alike)


PRODUCT_CORPUS = "product"
RESEARCH_CORPUS = "research"


def _truthy(value: Optional[str]) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def policy_from_env(env: Optional[dict] = None) -> HarvestPolicy:
    env = os.environ if env is None else env
    return HarvestPolicy(
        allow_share_alike=_truthy(env.get("AOEP_HARVEST_ALLOW_SHARE_ALIKE")),
        # On unless explicitly switched off with AOEP_HARVEST_RESEARCH=0.
        research_enabled=(env.get("AOEP_HARVEST_RESEARCH", "1").strip().lower() not in {"0", "false", "no", "off"}),
    )


@dataclass
class Decision:
    action: str                       # "ingest" (product corpus) | "research" (research corpus) | "reject"
    reason: str
    info: LicenseInfo = UNKNOWN_LICENSE
    obligations: List[str] = field(default_factory=list)
    conflict: bool = False

    @property
    def ingest(self) -> bool:
        return self.action == "ingest"

    @property
    def research(self) -> bool:
        return self.action == "research"

    @property
    def corpus(self) -> str:
        """Which corpus this decision sends the material to ('' when rejected)."""
        return PRODUCT_CORPUS if self.ingest else RESEARCH_CORPUS if self.research else ""

    def to_dict(self) -> dict:
        return {"action": self.action, "corpus": self.corpus, "reason": self.reason, "license": self.info.to_dict(),
                "obligations": list(self.obligations), "conflict": self.conflict}


def obligations_for(info: LicenseInfo) -> List[str]:
    out: List[str] = []
    if info.tier in (Tier.COMMERCIAL_OK, Tier.SHARE_ALIKE) and info.family not in ("cc0", "pd"):
        out.append("attribution: credit the author/title/source and link the license")
        if info.family in ("mit", "bsd", "apache"):
            out.append("keep the copyright and license notice with the content")
    if info.tier is Tier.SHARE_ALIKE:
        out.append(f"share-alike: the derivative course must be offered under {info.spdx}")
    return out


def decide(info: LicenseInfo, policy: Optional[HarvestPolicy] = None, *, conflict: bool = False) -> Decision:
    """Turn a (verified) license into a decision for the product pipeline."""
    policy = policy or HarvestPolicy()
    if conflict:
        return Decision("reject", "conflicting license evidence on the page", info, conflict=True)
    if policy.tier_allowed(info.tier):
        return Decision("ingest", f"{info.spdx} is {info.tier.value}", info, obligations_for(info))
    if policy.research_eligible(info.tier):
        why = ("share-alike and harvest.allow_share_alike is off" if info.tier is Tier.SHARE_ALIKE
               else "non-commercial: not for the product")
        return Decision("research", f"{info.spdx}: {why}; kept in the research corpus only", info)
    if info.tier is Tier.SHARE_ALIKE:
        return Decision("reject", f"{info.spdx} is share-alike and harvest.allow_share_alike is off", info)
    return Decision("reject", f"{info.spdx or 'unknown license'} is {info.tier.value}", info)


# -------------------------------------------------------- page detection

class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.found: List[LicenseInfo] = []
        self.robots: List[str] = []
        self.paywalled = False
        self._script_ld = False
        self._ld: List[str] = []
        self._skip = 0
        self.text: List[str] = []
        self._in_license_a: Optional[str] = None

    def handle_starttag(self, tag: str, attrs) -> None:
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag in ("script", "style", "noscript"):
            self._skip += 1
            if tag == "script" and "ld+json" in a.get("type", "").lower():
                self._script_ld = True
        rel = a.get("rel", "").lower().split()
        if tag in ("link", "a") and "license" in rel and a.get("href"):
            info = parse_license(a["href"], kind="rel-license")
            if tag == "a":
                self._in_license_a = a["href"]
            self.found.append(info if info.known else parse_license(a["href"] + " " + a.get("title", ""), kind="rel-license"))
        if tag == "meta":
            name = (a.get("name") or a.get("property") or a.get("itemprop") or "").lower()
            content = a.get("content", "")
            if name in ("license", "dc.rights", "dcterms.license", "dc.license", "dcterms.rights",
                        "dc.rights.license", "og:license", "cc:license", "article:license"):
                self.found.append(parse_license(content, kind="meta"))
            if name == "robots" or name == "googlebot":
                self.robots.append(content.lower())
        if a.get("itemprop", "").lower() == "license":
            self.found.append(parse_license(a.get("href") or a.get("content") or a.get("src") or "", kind="schema"))

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
            if tag == "script":
                self._script_ld = False

    def handle_data(self, data: str) -> None:
        if self._script_ld:
            self._ld.append(data)
        elif not self._skip and data.strip():
            self.text.append(data.strip())


def _jsonld_licenses(blobs: Sequence[str]) -> List[LicenseInfo]:
    out: List[LicenseInfo] = []
    paywalled = False

    def walk(node) -> None:
        nonlocal paywalled
        if isinstance(node, dict):
            lic = node.get("license")
            if isinstance(lic, str):
                out.append(parse_license(lic, kind="jsonld"))
            elif isinstance(lic, dict):
                out.append(parse_license(str(lic.get("url") or lic.get("@id") or lic.get("name") or ""), kind="jsonld"))
            elif isinstance(lic, list):
                for item in lic:
                    out.append(parse_license(item if isinstance(item, str) else str(item.get("url") or item.get("@id") or ""), kind="jsonld"))
            if str(node.get("isAccessibleForFree", "")).lower() == "false":
                paywalled = True
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except (ValueError, TypeError):
            continue
    if paywalled:
        out.append(LicenseInfo("PAYWALLED", Tier.PROPRIETARY, "arr", evidence="JSON-LD isAccessibleForFree=false", kind="jsonld"))
    return out


_FOOTER_LICENSE = re.compile(
    r"(?:licensed\s+under|available\s+under|released\s+under|is\s+licensed|content\s+license|"
    r"text\s+is\s+available\s+under|creative\s+commons|all\s+rights\s+reserved)[^.\n]{0,220}",
    re.I,
)
_PAYWALL_TEXT = re.compile(
    r"subscribe\s+to\s+(?:continue|read)|sign\s+in\s+to\s+(?:continue|read|view)|"
    r"log\s*in\s+to\s+(?:continue|read|view)|create\s+a\s+free\s+account\s+to\s+(?:continue|read|view)|"
    r"this\s+content\s+is\s+for\s+(?:members|subscribers)",
    re.I,
)


@dataclass
class PageScan:
    licenses: List[LicenseInfo]
    robots_directives: List[str]
    noai: bool
    noindex: bool
    paywalled: bool
    title: str = ""
    canonical: str = ""
    author: str = ""


def scan_page(html: str, *, headers: Optional[dict] = None) -> PageScan:
    """Collect license evidence and crawl directives from an HTML page."""
    p = _Collector()
    try:
        p.feed(html or "")
    except Exception:  # malformed HTML: keep whatever was collected
        pass
    found = [i for i in p.found if i.known or i.tier is Tier.PROPRIETARY]
    found += [i for i in _jsonld_licenses(p._ld) if i.known or i.tier is Tier.PROPRIETARY]

    body = " ".join(p.text)
    for m in _FOOTER_LICENSE.finditer(body[-20000:] + " " + body[:4000]):
        info = parse_license(m.group(0), kind="footer")
        if info.known or info.tier is Tier.PROPRIETARY:
            found.append(info)
    directives = list(p.robots)
    if headers:
        xr = headers.get("X-Robots-Tag") or headers.get("x-robots-tag") or ""
        if xr:
            directives.append(xr.lower())
    joined = ",".join(directives)
    paywalled = bool(_PAYWALL_TEXT.search(body[:6000])) or any(i.spdx == "PAYWALLED" for i in found)
    title = ""
    m = re.search(r"<title[^>]*>(.*?)</title>", html or "", re.I | re.S)
    if m:
        title = re.sub(r"\s+", " ", m.group(1)).strip()[:200]
    canonical = ""
    m = re.search(r"<link[^>]+rel=[\"']canonical[\"'][^>]*href=[\"']([^\"']+)", html or "", re.I)
    if m:
        canonical = m.group(1)
    author = ""
    m = re.search(r"<meta[^>]+name=[\"'](?:author|dc\.creator)[\"'][^>]*content=[\"']([^\"']+)", html or "", re.I)
    if m:
        author = m.group(1).strip()[:160]
    return PageScan(
        licenses=found,
        robots_directives=directives,
        noai="noai" in joined or "noimageai" in joined,
        noindex="noindex" in joined or "none" in {d.strip() for d in joined.split(",")},
        paywalled=paywalled,
        title=title, canonical=canonical, author=author,
    )


_SEVERITY = {
    Tier.PROPRIETARY: 5, Tier.NON_COMMERCIAL: 4, Tier.NO_DERIVATIVES: 3,
    Tier.SHARE_ALIKE: 2, Tier.COMMERCIAL_OK: 1, Tier.UNKNOWN: 0,
}


def resolve_page_license(scan: PageScan) -> tuple[LicenseInfo, bool]:
    """Pick the page's license. Returns (info, conflict). Different tiers conflict.

    Structured evidence (rel=license, meta, schema.org, JSON-LD) outranks footer
    prose, but a footer that names a different tier than the structured data is
    still a conflict: when the page disagrees with itself we do not ingest it.
    """
    infos = [i for i in scan.licenses if i.known or i.tier is Tier.PROPRIETARY]
    if not infos:
        return UNKNOWN_LICENSE, False
    structured = [i for i in infos if i.kind != "footer"]
    footer = [i for i in infos if i.kind == "footer"]
    pool = structured or footer
    tiers = {i.tier for i in pool}
    if len(tiers) > 1 or (structured and {i.tier for i in footer} - tiers):
        worst = max(infos, key=lambda i: _SEVERITY[i.tier])
        return worst, True
    return pool[0], False


# ------------------------------------------------------- verification

@dataclass
class Verification:
    decision: Decision
    declared: LicenseInfo
    detected: LicenseInfo
    verified_by: str            # "page" | "vetted-site" | ""
    reason: str = ""


def verify_page(
    *,
    declared_license: Optional[str],
    html: str,
    url: str,
    headers: Optional[dict] = None,
    policy: Optional[HarvestPolicy] = None,
    vetted: Optional[LicenseInfo] = None,
) -> tuple[Verification, PageScan]:
    """Verify a fetched page's license. A seed's claim alone never ingests.

    ``vetted`` is the site-wide license from the vetted registry, usable only
    when the page itself carries no license evidence.
    """
    policy = policy or HarvestPolicy()
    declared = parse_license(declared_license) if declared_license else UNKNOWN_LICENSE
    scan = scan_page(html, headers=headers)
    detected, conflict = resolve_page_license(scan)

    if scan.noai or scan.noindex:
        d = Decision("reject", "page asks not to be indexed or used for AI (noai/noindex)", detected)
        return Verification(d, declared, detected, "", d.reason), scan
    if scan.paywalled:
        d = Decision("reject", "login-walled or paywalled content", detected)
        return Verification(d, declared, detected, "", d.reason), scan
    if conflict:
        return Verification(decide(detected, policy, conflict=True), declared, detected, "", "conflicting evidence"), scan

    if detected.known or detected.tier is Tier.PROPRIETARY:
        if declared.known and declared.tier is not detected.tier:
            d = Decision("reject", f"declared {declared.spdx} but the page says {detected.spdx}", detected, conflict=True)
            return Verification(d, declared, detected, "", d.reason), scan
        return Verification(decide(detected, policy), declared, detected, "page"), scan

    if vetted is not None and vetted.known:
        if declared.known and declared.tier is not vetted.tier:
            d = Decision("reject", f"declared {declared.spdx} but the vetted site license is {vetted.spdx}", vetted, conflict=True)
            return Verification(d, declared, vetted, "", d.reason), scan
        return Verification(decide(vetted, policy), declared, vetted, "vetted-site"), scan

    d = Decision("reject", "no license evidence on the page and the host is not a vetted site", declared)
    return Verification(d, declared, UNKNOWN_LICENSE, "", d.reason), scan


def host_of(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower().lstrip(".")
    except ValueError:
        return ""


def registered_host_matches(host: str, patterns: Iterable[str]) -> Optional[str]:
    """Return the matching pattern when host equals it or is a subdomain of it."""
    for pat in patterns:
        pat = pat.lower().lstrip(".")
        if host == pat or host.endswith("." + pat):
            return pat
    return None


def assert_product_safe(
    *,
    license: Optional[str] = None,
    tier: Optional[str] = None,
    corpus: Optional[str] = None,
    policy: Optional[HarvestPolicy] = None,
) -> None:
    """Publish-time assertion of the wall: raise unless this course may reach the catalog.

    A course is refused when it came from the research corpus, when its recorded tier is
    non-commercial / no-derivatives / proprietary / unknown, when it is share-alike while that
    switch is off, or (with no recorded tier) when its declared license parses to any of those."""
    from .errors import CorpusWallError

    policy = policy or policy_from_env()
    if corpus == RESEARCH_CORPUS:
        raise CorpusWallError("a research-corpus course can never be published")
    try:
        resolved = Tier(tier) if tier else parse_license(license).tier
    except ValueError:
        resolved = parse_license(license).tier
    if not policy.tier_allowed(resolved):
        raise CorpusWallError(f"{resolved.value} license ({license!r}) is not product-safe")
