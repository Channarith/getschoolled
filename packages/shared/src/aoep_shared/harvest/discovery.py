"""Discover harvest seeds from OER catalogs, public data, and search engines."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Iterable, List, Optional
from urllib.parse import quote_plus

from .sources import SourceSpec

# Curated OER / public-education entry points (license-gated at fetch time).
OER_PORTALS: List[dict] = [
    {"url": "https://openstax.org/subjects", "license": "cc-by", "subject": "science", "title": "OpenStax"},
    {"url": "https://www.oercommons.org/browse", "license": "cc-by", "subject": "general", "title": "OER Commons"},
    {"url": "https://open.umn.edu/opentextbooks", "license": "cc-by-nc", "subject": "general", "title": "Open Textbooks"},
    {"url": "https://www.khanacademy.org", "license": "cc-by-nc-sa", "subject": "mathematics", "title": "Khan Academy"},
    {"url": "https://www.coursera.org/browse", "license": "oer", "subject": "technology", "title": "Coursera browse"},
    {"url": "https://www.edx.org/search", "license": "oer", "subject": "technology", "title": "edX"},
    {"url": "https://arxiv.org/list/cs.LG/recent", "license": "cc-by", "subject": "ai", "title": "arXiv ML"},
    {"url": "https://data.gov", "license": "public-domain", "subject": "civics", "title": "Data.gov"},
    {"url": "https://www.census.gov/data.html", "license": "public-domain", "subject": "statistics", "title": "US Census"},
    {"url": "https://www.nih.gov/health-information", "license": "public-domain", "subject": "biology", "title": "NIH"},
    {"url": "https://www.nasa.gov/learning-resources/", "license": "public-domain", "subject": "science", "title": "NASA Learning"},
    {"url": "https://www.loc.gov/education/", "license": "public-domain", "subject": "history", "title": "Library of Congress"},
]

# Public-sector compliance / workplace training entry points (used instead of
# generic OER portals when the topic is harassment/compliance-shaped).
COMPLIANCE_TOPIC_SEEDS: List[dict] = [
    {"url": "https://www.eeoc.gov/sexual-harassment", "license": "public-domain", "subject": "compliance", "title": "EEOC Sexual Harassment"},
    {"url": "https://www.eeoc.gov/harassment", "license": "public-domain", "subject": "compliance", "title": "EEOC Harassment Overview"},
    {"url": "https://www.dol.gov/general/topic/discrimination/harassment", "license": "public-domain", "subject": "compliance", "title": "DOL Workplace Harassment"},
    {"url": "https://www.osha.gov/workplace-violence", "license": "public-domain", "subject": "compliance", "title": "OSHA Workplace Violence"},
]

_COMPLIANCE_TOPIC_RE = (
    "harassment", "compliance", "discrimination", "workplace safety",
    "sexual harassment", "hostile work",
)


def _compliance_topic(topic: str) -> bool:
    t = (topic or "").lower()
    return any(k in t for k in _COMPLIANCE_TOPIC_RE)


# Site-restricted search templates (used when a search API key is configured).
_SEARCH_TEMPLATES = [
    "site:oercommons.org {topic} open educational resource",
    "site:openstax.org {topic}",
    "site:.gov {topic} education dataset",
    "site:.edu {topic} course syllabus",
    "site:archive.org {topic} textbook",
    "{topic} free course creative commons",
]


def portal_specs() -> List[SourceSpec]:
    return [
        SourceSpec(
            url=p["url"],
            license=p.get("license", "cc-by"),
            subject=p.get("subject"),
            title=p.get("title"),
            source_type="html",
            meta={"kind": "portal"},
        )
        for p in OER_PORTALS
    ]


def topic_search_queries(topic: str) -> List[str]:
    t = (topic or "").strip()
    if not t:
        return []
    return [tmpl.format(topic=t) for tmpl in _SEARCH_TEMPLATES]


def discover_from_search(
    topic: str,
    *,
    max_results: int = 12,
    engines: Optional[Iterable] = None,
) -> List[SourceSpec]:
    """Use configured search providers (Bing/Google/Brave/…) or mock offline."""
    specs: List[SourceSpec] = []
    if engines is None:
        try:
            from ..config import load_config
            from ..providers.search import MockSearchProvider, available_engines
            engines = available_engines(load_config())
        except Exception:
            from ..providers.search import MockSearchProvider
            engines = [MockSearchProvider()]

    seen: set[str] = set()
    for query in topic_search_queries(topic):
        for engine in engines:
            try:
                hits = engine.search(query, max_results=max_results)
            except Exception:
                continue
            for hit in hits:
                url = (hit.url or "").strip()
                if not url or url in seen:
                    continue
                if url.startswith("mock://"):
                    continue
                seen.add(url)
                specs.append(SourceSpec(
                    url=url,
                    license="cc-by",
                    subject=topic[:64],
                    title=hit.title or topic,
                    source_type="html",
                    meta={"kind": "search", "engine": getattr(hit, "engine", ""),
                          "snippet": hit.snippet or "", "query": query},
                ))
    return specs


def discover_topic(topic: str, *, include_portals: bool = True) -> List[SourceSpec]:
    """Build a seed list for a topic: search hits + optional OER portals."""
    specs = discover_from_search(topic)
    if _compliance_topic(topic):
        seen = {s.url for s in specs}
        for row in COMPLIANCE_TOPIC_SEEDS:
            if row["url"] in seen:
                continue
            seen.add(row["url"])
            specs.append(SourceSpec(
                url=row["url"],
                license=row["license"],
                subject=topic[:64] or row.get("subject"),
                title=row["title"],
                source_type="html",
                meta={"topic": topic, "kind": "compliance", "priority": 90},
            ))
        return specs
    if include_portals:
        for p in portal_specs():
            if p not in specs:
                p2 = SourceSpec(
                    url=p.url,
                    license=p.license,
                    subject=topic or p.subject,
                    title=p.title,
                    source_type=p.source_type,
                    meta={**p.meta, "topic": topic},
                )
                specs.append(p2)
    return specs


def load_seeds_file(path: str | Path) -> List[SourceSpec]:
    """Load JSONL ``SourceSpec`` rows (same format as ``--seeds``).

    Explicit seed files get high queue priority so they run before generic
    OER portal URLs enqueued by ``--topic``.
    """
    specs: List[SourceSpec] = []
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        d = json.loads(line)
        meta = dict(d.get("meta") or {})
        meta.setdefault("priority", 100)
        meta.setdefault("kind", "seed")
        d["meta"] = meta
        specs.append(SourceSpec(**d))
    return specs


def load_env_seeds() -> List[SourceSpec]:
    """``HARVEST_SEEDS`` env → JSONL file path or inline JSON array."""
    raw = os.environ.get("HARVEST_SEEDS", "").strip()
    if not raw:
        return []
    p = Path(raw)
    if p.is_file():
        return load_seeds_file(p)
    try:
        data = json.loads(raw)
        return [SourceSpec(**d) for d in data]
    except json.JSONDecodeError:
        return []
