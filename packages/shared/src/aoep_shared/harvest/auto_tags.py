"""Infer harvest metadata (subject, pricing, career, tags) via RAG + taxonomy.

When generating a course from a local file, callers should not need to hand-type
``--subject``, ``--access-tier``, ``--price``, ``--career-path``, or ``--tags``.
This module:

  1. Builds a lexical RAG index over the course catalog (content packs +
     sample-curriculum lessons) and retrieves the nearest neighbors.
  2. Applies the skills taxonomy (``course_relevance``) for audiences, core
     fundamentals, and career-path hints.
  3. Optionally queries the knowledge store for domain/category keywords.
  4. Merges those signals into ``CourseTags`` + a subject slug.

Offline-safe (no LLM keys). Manual CLI flags still override any inferred field.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from ..content_packs import load_records
from ..plan_pricing import price_usd_for_tier
from ..rag import Document, RagIndex
from ..skills_taxonomy import CORE_SKILL_KEYWORDS, FUNDAMENTAL, PROFESSIONS, RELEVANCE, course_relevance
from .extractors import ExtractedDoc
from .tagging import ACCESS_TIERS, CourseTags

# One-time catalog course prices when neighbors lack an explicit price_usd.
TIER_COURSE_PRICE_USD: Dict[str, float] = {
    "free": 0.0,
    "basic": 49.0,
    "pro": 99.0,
    "premium": 199.0,
    "enterprise": 299.0,
}

# Subject slug hints (longer phrases first).
SUBJECT_HINTS: Tuple[Tuple[str, str], ...] = (
    ("machine learning", "ai"),
    ("artificial intelligence", "ai"),
    ("deep learning", "ai"),
    ("data science", "data-science"),
    ("computer science", "computer-science"),
    ("software engineering", "software-engineering"),
    ("cyber security", "cybersecurity"),
    ("cybersecurity", "cybersecurity"),
    ("nursing", "nursing"),
    ("anatomy", "medicine"),
    ("biology", "biology"),
    ("chemistry", "chemistry"),
    ("physics", "physics"),
    ("calculus", "mathematics"),
    ("algebra", "mathematics"),
    ("statistics", "mathematics"),
    ("python", "programming"),
    ("programming", "programming"),
    ("marketing", "marketing"),
    ("finance", "finance"),
    ("accounting", "finance"),
)

_ADVANCED_MARKERS = frozenset({
    "fellowship", "architect", "graduate", "doctoral", "research", "advanced",
    "enterprise", "professional", "specialist",
})
_INTRO_MARKERS = frozenset({
    "introduction", "intro", "fundamentals", "basics", "101", "essentials",
    "getting started", "beginner",
})

_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = frozenset({
    "the", "a", "an", "to", "of", "for", "and", "with", "in", "on", "is", "are",
    "this", "that", "from", "by", "as", "at", "or", "be", "was", "were", "it",
})


@dataclass
class InferredMetadata:
    subject: str
    tags: CourseTags
    matched_keywords: List[str] = field(default_factory=list)
    similar_courses: List[dict] = field(default_factory=list)
    rationale: str = ""

    def to_dict(self) -> dict:
        return {
            "subject": self.subject,
            "tags": self.tags.to_dict(),
            "matched_keywords": list(self.matched_keywords),
            "similar_courses": list(self.similar_courses),
            "rationale": self.rationale,
        }


def _tokens(text: str) -> set[str]:
    return {w for w in _TOKEN.findall((text or "").lower()) if w and w not in _STOP}


def _doc_query(doc: ExtractedDoc, *, max_chars: int = 6000) -> str:
    parts = [doc.title]
    for heading, body in doc.nonempty_sections()[:24]:
        parts.append(heading)
        parts.append(body[:400])
    return " ".join(parts)[:max_chars]


def _catalog_records(repo_root: Optional[Path] = None) -> List[dict]:
    records: List[dict] = list(load_records("courses"))
    root = repo_root or Path(__file__).resolve().parents[4]
    sample = root / "sample-curriculum"
    if sample.is_dir():
        for lesson in sorted(sample.glob("*/lesson.txt")):
            slug = lesson.parent.name
            try:
                text = lesson.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            if not text.strip():
                continue
            title = slug.replace("-", " ").title()
            first = text.strip().splitlines()[0][:120] if text.strip() else title
            subject = "general"
            if slug.startswith("ai-") or "ml" in slug:
                subject = "ai"
            elif slug.startswith("python-") or "java-" in slug:
                subject = "programming"
            elif "data-" in slug:
                subject = "data-science"
            elif "nursing" in slug or "medical" in slug:
                subject = "medicine"
            records.append({
                "course_id": f"sample:{slug}",
                "title": title,
                "subject": subject,
                "category": subject,
                "description": first,
                "tags": [t for t in slug.split("-") if t],
                "access_tier": "pro" if "fellowship" in slug or "architect" in slug else "free",
                "price_usd": 199.0 if "fellowship" in slug else 0.0,
                "level": "advanced" if "fellowship" in slug else "beginner",
                "core_skill": slug.startswith("intro-") or "fundamentals" in slug,
            })
    return records


def _course_doc_text(rec: dict) -> str:
    bits = [
        rec.get("title", ""),
        rec.get("subject", ""),
        rec.get("category", ""),
        rec.get("description", ""),
        rec.get("level", ""),
        " ".join(str(t) for t in (rec.get("tags") or [])),
        " ".join(str(a) for a in (rec.get("audiences") or [])),
    ]
    return " ".join(b for b in bits if b)


_catalog_index: Optional[RagIndex] = None
_catalog_by_id: Dict[str, dict] = {}


def _catalog_rag(repo_root: Optional[Path] = None) -> Tuple[RagIndex, Dict[str, dict]]:
    global _catalog_index, _catalog_by_id
    records = _catalog_records(repo_root)
    fp = "|".join(r.get("course_id", "") for r in records[:50]) + f":{len(records)}"
    if _catalog_index is not None and _catalog_by_id and getattr(_catalog_rag, "_fp", "") == fp:
        return _catalog_index, _catalog_by_id
    index = RagIndex()
    by_id: Dict[str, dict] = {}
    for rec in records:
        cid = str(rec.get("course_id") or rec.get("title") or len(by_id))
        by_id[cid] = rec
        index.add(Document.from_text(cid, rec.get("title", cid), _course_doc_text(rec)))
    _catalog_index = index
    _catalog_by_id = by_id
    _catalog_rag._fp = fp  # type: ignore[attr-defined]
    return index, by_id


def _infer_subject(
    query: str,
    tokens: set[str],
    neighbors: Sequence[dict],
    neighbor_scores: Sequence[float],
    *,
    min_rag_score: float = 0.04,
) -> str:
    q = query.lower()
    for phrase, slug in SUBJECT_HINTS:
        if phrase in q:
            return slug
    for kw, slug in SUBJECT_HINTS:
        if kw in tokens:
            return slug
    if neighbors and neighbor_scores and neighbor_scores[0] >= min_rag_score:
        subj = (neighbors[0].get("subject") or "").strip().lower()
        if subj and subj != "general":
            return subj
    return "general"


def _infer_career_path(tokens: set[str], relevance: dict) -> Optional[str]:
    scores: Counter[str] = Counter()
    for kw in tokens:
        for prof in RELEVANCE.get(kw, ()):
            scores[prof] += 1
        for prof in FUNDAMENTAL.get(kw, ()):
            scores[prof] += 2
    for aud in relevance.get("audiences") or []:
        scores[str(aud)] += 1
    if not scores:
        return None
    return scores.most_common(1)[0][0]


def _infer_tier_and_price(
    query: str,
    tokens: set[str],
    neighbors: Sequence[dict],
    neighbor_scores: Sequence[float],
    *,
    core: bool,
    min_rag_score: float = 0.04,
) -> Tuple[str, float]:
    has_ml = bool(tokens & {"machine", "learning", "neural", "deep", "algorithm", "prediction", "ai"})
    if has_ml:
        return "premium", TIER_COURSE_PRICE_USD["premium"]

    tier_votes: Counter[str] = Counter()
    prices: List[float] = []
    for rec, score in zip(neighbors, neighbor_scores):
        if score < min_rag_score:
            continue
        tier = (rec.get("access_tier") or "free").lower()
        if tier in ACCESS_TIERS:
            tier_votes[tier] += 1
        p = float(rec.get("price_usd") or 0.0)
        if p > 0:
            prices.append(p)

    q = query.lower()
    if any(m in q for m in _INTRO_MARKERS) and core:
        tier_votes["free"] += 2
        tier_votes["basic"] += 1
    if any(m in q for m in _ADVANCED_MARKERS):
        tier_votes["premium"] += 2
        tier_votes["pro"] += 1

    if tier_votes:
        tier = tier_votes.most_common(1)[0][0]
    else:
        tier = "basic" if core else "pro"

    if prices:
        price = round(sum(prices) / len(prices), 2)
    else:
        price = TIER_COURSE_PRICE_USD.get(tier, price_usd_for_tier(tier))
    if tier == "free":
        price = 0.0
    return tier, price


def _knowledge_labels(query: str, *, limit: int = 5) -> List[str]:
    try:
        from ..training_agents.knowledge_store import KnowledgeStore
        store = KnowledgeStore()
        hits = store.search(q=query[:200], limit=limit)
    except Exception:
        return []
    labels: List[str] = []
    for h in hits:
        cat = (h.get("category") or "").strip()
        if cat:
            labels.append(cat.lower().replace(" ", "-"))
    return labels


def infer_harvest_metadata(
    doc: ExtractedDoc,
    *,
    repo_root: Optional[Path] = None,
) -> InferredMetadata:
    """Infer subject + CourseTags for a harvested document."""
    query = _doc_query(doc)
    tokens = _tokens(query)
    index, by_id = _catalog_rag(repo_root)
    retrieved = index.retrieve(query, top_k=5)
    neighbors = [by_id[r.document.doc_id] for r in retrieved if r.document.doc_id in by_id]
    neighbor_scores = [r.score for r in retrieved[: len(neighbors)]]

    pseudo = {
        "title": doc.title,
        "subject": _infer_subject(query, tokens, neighbors, neighbor_scores),
        "tags": sorted(tokens & (set(RELEVANCE) | set(FUNDAMENTAL) | CORE_SKILL_KEYWORDS))[:12],
        "category": doc.title,
    }
    relevance = course_relevance(pseudo)
    core = bool(relevance.get("core_skill"))
    subject = pseudo["subject"]
    career = _infer_career_path(tokens, relevance)
    tier, price = _infer_tier_and_price(
        query, tokens, neighbors, neighbor_scores, core=core,
    )

    labels: List[str] = []
    labels.extend(relevance.get("matched_subjects") or [])
    labels.extend(pseudo["tags"][:8])
    for rec in neighbors[:3]:
        for t in rec.get("tags") or []:
            if t and t not in labels:
                labels.append(str(t))
    for lbl in _knowledge_labels(query):
        if lbl not in labels:
            labels.append(lbl)

    tags = CourseTags(
        access_tier=tier,
        price_usd=price,
        career_path=career,
        core_fundamental=core,
        audiences=list(relevance.get("audiences") or []),
        labels=labels[:16],
        meta={
            "inferred_by": "rag+taxonomy",
            "rag_top": neighbors[0].get("title", "") if neighbors else "",
        },
    )

    rationale_parts = []
    if neighbors:
        rationale_parts.append(
            f"RAG nearest catalog course: {neighbors[0].get('title', '?')} "
            f"(subject={neighbors[0].get('subject', '?')})"
        )
    if career:
        rationale_parts.append(f"career_path={career} ({PROFESSIONS.get(career, career)})")
    rationale_parts.append(f"access_tier={tier} price_usd={price}")
    if core:
        rationale_parts.append("core_fundamental=true")

    return InferredMetadata(
        subject=subject,
        tags=tags,
        matched_keywords=pseudo["tags"],
        similar_courses=[
            {"course_id": r.get("course_id"), "title": r.get("title"),
             "subject": r.get("subject"), "access_tier": r.get("access_tier"),
             "rag_score": neighbor_scores[i] if i < len(neighbor_scores) else 0.0}
            for i, r in enumerate(neighbors[:3])
        ],
        rationale="; ".join(rationale_parts),
    )


def merge_tags(
    inferred: Optional[InferredMetadata],
    *,
    subject: Optional[str] = None,
    access_tier: Optional[str] = None,
    price_usd: Optional[float] = None,
    career_path: Optional[str] = None,
    linkedin_job_id: Optional[str] = None,
    core_fundamental: Optional[bool] = None,
    extra_labels: Optional[Sequence[str]] = None,
) -> Tuple[str, CourseTags]:
    """Merge CLI overrides onto inferred metadata (explicit wins)."""
    base = inferred.tags if inferred else CourseTags()
    subj = (subject or (inferred.subject if inferred else None) or "general").strip()
    labels = list(base.labels)
    for lbl in extra_labels or ():
        s = str(lbl).strip()
        if s and s not in labels:
            labels.append(s)
    tags = CourseTags(
        access_tier=access_tier or base.access_tier,
        price_usd=price_usd if price_usd is not None else base.price_usd,
        career_path=career_path or base.career_path,
        linkedin_job_id=linkedin_job_id or base.linkedin_job_id,
        core_fundamental=core_fundamental if core_fundamental is not None else base.core_fundamental,
        audiences=list(base.audiences),
        labels=labels,
        meta=dict(base.meta),
    )
    return subj, tags
