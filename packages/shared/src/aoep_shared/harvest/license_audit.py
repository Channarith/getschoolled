"""Audit an existing harvest corpus for sources we may not use commercially.

Older corpora (made before license tiers existed) hold sources whose license is just
whatever the seed claimed: ``cc-by-nc``, ``cc-by-nc-sa``, ``oer`` and so on, plus
courses and text chunks generated from them. This reads a corpus database READ-ONLY,
classifies every source, and can mark the bad ones ``quarantined`` (reversible:
nothing is deleted, and quarantined sources drop out of RAG retrieval).

Buckets
  ok            commercially usable AND supported by evidence (verified provenance, or a vetted site)
  quarantine    non-commercial / no-derivatives / proprietary / unknown ("oer", empty) / do-not-harvest host
  needs_review  declared usable (CC BY, public domain, share-alike when off) but nothing proves it

Not legal advice.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from .corpus_store import add_missing_columns, _COURSE_COLUMNS, _SOURCE_COLUMNS
from .licensing import HarvestPolicy, Tier, parse_license
from .vetted_sources import is_denied, is_per_item_host, vetted_for

AUDIT_REASON_PREFIX = "audit:"
BUCKET_OK, BUCKET_QUARANTINE, BUCKET_REVIEW = "ok", "quarantine", "needs_review"


@dataclass
class Finding:
    url_key: str
    url: str
    declared_license: str
    tier: str
    bucket: str
    reason: str
    domain: str

    def to_dict(self) -> Dict[str, str]:
        return self.__dict__.copy()


def classify_source(row: Dict[str, Any], policy: Optional[HarvestPolicy] = None) -> Finding:
    policy = policy or HarvestPolicy()
    url = str(row.get("url") or "")
    declared = str(row.get("license") or "")
    domain = (urlparse(url).hostname or "").lower().removeprefix("www.")
    stored_tier = str(row.get("license_tier") or "")
    info = parse_license(declared)
    tier = Tier(stored_tier) if stored_tier in {t.value for t in Tier} else info.tier

    def f(bucket: str, reason: str) -> Finding:
        return Finding(str(row.get("url_key") or ""), url, declared, tier.value, bucket, reason, domain)

    denied = is_denied(url)
    if denied is not None:
        return f(BUCKET_QUARANTINE, f"{denied.domain}: {denied.reason}")
    if tier is Tier.NON_COMMERCIAL:
        return f(BUCKET_QUARANTINE, "non-commercial license")
    if tier is Tier.NO_DERIVATIVES:
        return f(BUCKET_QUARANTINE, "no-derivatives license (we adapt content)")
    if tier is Tier.PROPRIETARY:
        return f(BUCKET_QUARANTINE, "all rights reserved / proprietary")
    if tier is Tier.UNKNOWN:
        return f(BUCKET_QUARANTINE, f"license not usable or unknown ({declared or 'empty'})")
    verified = bool(row.get("license_verified_by")) and stored_tier == tier.value
    vet = vetted_for(url)
    if tier is Tier.SHARE_ALIKE and not policy.allow_share_alike:
        return f(BUCKET_QUARANTINE, "share-alike license and harvest.allow_share_alike is off")
    if verified or vet is not None:
        if vet is not None and vet.info().tier is not tier and tier is not Tier.UNKNOWN:
            return f(BUCKET_REVIEW, f"declared {declared} but the vetted site license is {vet.info().spdx}")
        return f(BUCKET_OK, "verified" if verified else f"vetted site {vet.domain}")
    if is_per_item_host(url):
        return f(BUCKET_REVIEW, "license is per item on this host and was never checked on the page")
    return f(BUCKET_REVIEW, "declared by the seed list, never verified on the page")


@dataclass
class AuditReport:
    db_path: str
    generated_at: str
    sources: int = 0
    courses: int = 0
    chunks: int = 0
    findings: List[Finding] = field(default_factory=list)
    by_bucket: Dict[str, int] = field(default_factory=dict)
    by_license: Dict[str, Dict[str, int]] = field(default_factory=dict)   # declared -> bucket -> n
    by_domain: Dict[str, Dict[str, int]] = field(default_factory=dict)
    courses_by_bucket: Dict[str, int] = field(default_factory=dict)
    chunks_by_bucket: Dict[str, int] = field(default_factory=dict)
    examples: Dict[str, List[Dict[str, str]]] = field(default_factory=dict)

    def to_dict(self, *, with_findings: bool = True) -> Dict[str, Any]:
        d = {
            "db_path": self.db_path, "generated_at": self.generated_at,
            "sources": self.sources, "courses": self.courses, "chunks": self.chunks,
            "by_bucket": self.by_bucket, "by_license": self.by_license, "by_domain": self.by_domain,
            "courses_by_bucket": self.courses_by_bucket, "chunks_by_bucket": self.chunks_by_bucket,
            "examples": self.examples,
        }
        if with_findings:
            d["findings"] = [x.to_dict() for x in self.findings]
        return d

    def text(self) -> str:
        lines = [f"Harvest license audit of {self.db_path} ({self.generated_at})", "",
                 f"sources {self.sources}, courses {self.courses}, chunks {self.chunks}", ""]
        for bucket in (BUCKET_QUARANTINE, BUCKET_REVIEW, BUCKET_OK):
            lines.append(
                f"{bucket:13} sources {self.by_bucket.get(bucket, 0):6}  "
                f"courses {self.courses_by_bucket.get(bucket, 0):6}  chunks {self.chunks_by_bucket.get(bucket, 0):8}"
            )
        lines += ["", "by declared license (source counts):"]
        for lic, b in sorted(self.by_license.items(), key=lambda kv: -sum(kv[1].values())):
            lines.append(f"  {lic or '(empty)':18} " + ", ".join(f"{k} {v}" for k, v in sorted(b.items())))
        lines += ["", "top domains in quarantine:"]
        top = sorted(((d, b.get(BUCKET_QUARANTINE, 0)) for d, b in self.by_domain.items()), key=lambda x: -x[1])[:15]
        lines += [f"  {d:34} {n}" for d, n in top if n]
        for bucket in (BUCKET_QUARANTINE, BUCKET_REVIEW):
            lines += ["", f"examples ({bucket}):"]
            for ex in self.examples.get(bucket, [])[:6]:
                lines.append(f"  {ex['declared_license'] or '(empty)':14} {ex['url'][:90]}  [{ex['reason']}]")
        return "\n".join(lines) + "\n"


def _connect(path: Path, *, write: bool) -> sqlite3.Connection:
    if write:
        conn = sqlite3.connect(str(path))
    else:
        conn = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def _columns(conn: sqlite3.Connection, table: str) -> set:
    return {r[1] for r in conn.execute(f"PRAGMA table_info({table})")}


def audit_db(path: str | Path, policy: Optional[HarvestPolicy] = None, *, examples: int = 8) -> AuditReport:
    """Classify every source in a corpus DB (opened read-only) and count what hangs off it."""
    path = Path(path)
    report = AuditReport(str(path), datetime.now(timezone.utc).isoformat(timespec="seconds"))
    conn = _connect(path, write=False)
    try:
        scols = _columns(conn, "sources")
        optional = [c for c in ("license_tier", "license_verified_by") if c in scols]
        sel = ", ".join(["url_key", "url", "license"] + optional)
        rows = [dict(r) for r in conn.execute(f"SELECT {sel} FROM sources")]
        report.sources = len(rows)
        report.courses = conn.execute("SELECT COUNT(*) FROM courses").fetchone()[0]
        report.chunks = conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0]
        bucket_of: Dict[str, str] = {}
        by_license: Dict[str, Counter] = defaultdict(Counter)
        by_domain: Dict[str, Counter] = defaultdict(Counter)
        by_bucket: Counter = Counter()
        ex: Dict[str, List[Dict[str, str]]] = defaultdict(list)
        for row in rows:
            fnd = classify_source(row, policy)
            report.findings.append(fnd)
            bucket_of[fnd.url_key] = fnd.bucket
            by_bucket[fnd.bucket] += 1
            by_license[fnd.declared_license][fnd.bucket] += 1
            by_domain[fnd.domain][fnd.bucket] += 1
            if len(ex[fnd.bucket]) < examples:
                ex[fnd.bucket].append(fnd.to_dict())
        courses_by: Counter = Counter()
        for r in conn.execute("SELECT url_key, COUNT(*) AS n FROM courses GROUP BY url_key"):
            courses_by[bucket_of.get(r["url_key"], BUCKET_QUARANTINE)] += r["n"]   # no source row = no proof
        chunks_by: Counter = Counter()
        for r in conn.execute("SELECT url_key, COUNT(*) AS n FROM chunks GROUP BY url_key"):
            chunks_by[bucket_of.get(r["url_key"], BUCKET_QUARANTINE)] += r["n"]
        report.by_bucket = dict(by_bucket)
        report.by_license = {k: dict(v) for k, v in by_license.items()}
        report.by_domain = {k: dict(v) for k, v in by_domain.items()}
        report.courses_by_bucket = dict(courses_by)
        report.chunks_by_bucket = dict(chunks_by)
        report.examples = dict(ex)
    finally:
        conn.close()
    return report


def manifest(report: AuditReport, *, include: Iterable[str] = (BUCKET_QUARANTINE,)) -> Dict[str, Any]:
    include = set(include)
    return {
        "db_path": report.db_path,
        "generated_at": report.generated_at,
        "buckets": sorted(include),
        "sources": [x.to_dict() for x in report.findings if x.bucket in include],
    }


def apply_quarantine(path: str | Path, report: AuditReport, *, include: Iterable[str] = (BUCKET_QUARANTINE,)) -> Dict[str, int]:
    """Mark flagged sources and their courses quarantined. Reversible; deletes nothing."""
    include = set(include)
    path = Path(path)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    conn = _connect(path, write=True)
    try:
        add_missing_columns(conn, "sources", _SOURCE_COLUMNS)
        add_missing_columns(conn, "courses", _COURSE_COLUMNS)
        n_sources = n_courses = 0
        with conn:
            for fnd in report.findings:
                if fnd.bucket not in include:
                    continue
                reason = f"{AUDIT_REASON_PREFIX}{fnd.bucket}: {fnd.reason}"[:300]
                n_sources += conn.execute(
                    "UPDATE sources SET quarantined=1, quarantine_reason=?, quarantined_at=?, license_tier=COALESCE(license_tier, ?) "
                    "WHERE url_key=? AND COALESCE(quarantined,0)=0",
                    (reason, now, fnd.tier, fnd.url_key),
                ).rowcount
                n_courses += conn.execute(
                    "UPDATE courses SET quarantined=1, quarantine_reason=? WHERE url_key=? AND COALESCE(quarantined,0)=0",
                    (reason, fnd.url_key),
                ).rowcount
            # Courses that point at no known source have no license proof either.
            n_courses += conn.execute(
                "UPDATE courses SET quarantined=1, quarantine_reason=? "
                "WHERE COALESCE(quarantined,0)=0 AND (url_key IS NULL OR url_key NOT IN (SELECT url_key FROM sources))",
                (f"{AUDIT_REASON_PREFIX}no source record",),
            ).rowcount
        return {"sources_quarantined": n_sources, "courses_quarantined": n_courses}
    finally:
        conn.close()


def restore_quarantine(path: str | Path) -> Dict[str, int]:
    """Undo apply_quarantine: only rows whose reason starts with 'audit:' are restored."""
    conn = _connect(Path(path), write=True)
    try:
        with conn:
            s = conn.execute(
                "UPDATE sources SET quarantined=0, quarantine_reason=NULL, quarantined_at=NULL "
                "WHERE quarantine_reason LIKE ?", (AUDIT_REASON_PREFIX + "%",)).rowcount
            c = conn.execute(
                "UPDATE courses SET quarantined=0, quarantine_reason=NULL WHERE quarantine_reason LIKE ?",
                (AUDIT_REASON_PREFIX + "%",)).rowcount
        return {"sources_restored": s, "courses_restored": c}
    finally:
        conn.close()


def scan_course_files(root: str | Path, report: AuditReport, *, limit: int = 0) -> Dict[str, Any]:
    """Count on-disk *.course.json packages by the bucket of the source they came from.

    Packages written by the new pipeline carry ``license_tier`` and ``provenance``; older
    ones have neither, so they are matched through the corpus ``courses`` table.
    """
    root = Path(root)
    tiers: Counter = Counter()
    with_prov = without = 0
    for i, p in enumerate(root.rglob("*.course.json")):
        if limit and i >= limit:
            break
        try:
            data = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if data.get("provenance"):
            with_prov += 1
            tiers[str(data.get("license_tier") or "unknown")] += 1
        else:
            without += 1
    return {"root": str(root), "with_provenance": with_prov, "without_provenance": without,
            "tiers_with_provenance": dict(tiers)}
