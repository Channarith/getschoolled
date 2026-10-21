"""Durable, category-scoped acquisition jobs and safe local source intake."""

from __future__ import annotations

import csv
import hashlib
import json
import lzma
import sqlite3
import tarfile
import time
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator, Optional

from .sources import is_allowed

_ARCHIVE_MAX_FILES = 1_000
_ARCHIVE_MAX_BYTES = 256 * 1024 * 1024
_OWNED_RIGHTS = {"owned", "licensed", "internal"}
_IMPORT_SUFFIXES = {
    ".csv", ".pdf", ".doc", ".docx", ".html", ".htm", ".txt", ".ppt", ".pptx",
    ".zip", ".tar", ".gz", ".tgz", ".xz", ".db", ".sqlite", ".sqlite3",
}


@dataclass(frozen=True)
class CategoryBlueprint:
    slug: str
    title: str
    min_courses: int = 1
    max_courses: int = 60
    required_topics: tuple[str, ...] = ()
    audience: str = ""
    source_policy: str = "open_or_owned"

    def __post_init__(self) -> None:
        if not self.slug.strip():
            raise ValueError("category slug is required")
        if not 1 <= self.min_courses <= self.max_courses <= 60:
            raise ValueError("course bounds must satisfy 1 <= min <= max <= 60")


@dataclass(frozen=True)
class IntakeAsset:
    path: Path
    sha256: str
    byte_size: int
    source_kind: str
    rights_assertion: str
    license: str = ""


@dataclass(frozen=True)
class AcquisitionJob:
    job_id: str
    category_slug: str
    payload: dict[str, Any]
    idempotency_key: str
    attempts: int = 0


def source_fingerprint(*, source_uri: str, sha256: str, category_slug: str) -> str:
    raw = f"{source_uri}\0{sha256}\0{category_slug}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def validate_rights(*, license: Optional[str], rights_assertion: str) -> bool:
    """Allow open sources or explicitly declared platform-owned/licensed assets."""
    return is_allowed(license) or rights_assertion.strip().lower() in _OWNED_RIGHTS


def inspect_import(
    path: str | Path,
    *,
    rights_assertion: str,
    license: str = "",
) -> IntakeAsset:
    """Validate an owned import before it enters the durable acquisition queue."""
    candidate = Path(path).expanduser().resolve()
    if not candidate.is_file():
        raise ValueError(f"import is not a file: {candidate}")
    if candidate.suffix.lower() not in _IMPORT_SUFFIXES:
        raise ValueError(f"unsupported import type: {candidate.suffix}")
    if not validate_rights(license=license, rights_assertion=rights_assertion):
        raise ValueError("a permitted open license or explicit owned/licensed rights assertion is required")
    digest = hashlib.sha256()
    with candidate.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return IntakeAsset(
        path=candidate,
        sha256=digest.hexdigest(),
        byte_size=candidate.stat().st_size,
        source_kind=candidate.suffix.lower().lstrip("."),
        rights_assertion=rights_assertion.strip().lower(),
        license=license.strip(),
    )


def iter_import_files(path: str | Path) -> Iterator[Path]:
    """Yield safe, supported children from an archive or a single source file."""
    asset = Path(path)
    if asset.suffix.lower() not in {".zip", ".tar", ".gz", ".tgz", ".xz"}:
        yield asset
        return
    # Archives must be unpacked by an operator into a controlled intake directory.
    # This validates traversal and expansion budgets without writing attacker paths.
    if zipfile.is_zipfile(asset):
        with zipfile.ZipFile(asset) as archive:
            infos = archive.infolist()
            _validate_archive_members(((i.filename, i.file_size) for i in infos))
            for info in infos:
                if not info.is_dir() and Path(info.filename).suffix.lower() in _IMPORT_SUFFIXES:
                    yield Path(info.filename)
        return
    if tarfile.is_tarfile(asset):
        with tarfile.open(asset) as archive:
            members = [m for m in archive.getmembers() if m.isfile()]
            _validate_archive_members(((m.name, m.size) for m in members))
            for member in members:
                if Path(member.name).suffix.lower() in _IMPORT_SUFFIXES:
                    yield Path(member.name)
        return
    if asset.suffix.lower() == ".xz":
        with lzma.open(asset, "rb") as stream:
            if len(stream.read(_ARCHIVE_MAX_BYTES + 1)) > _ARCHIVE_MAX_BYTES:
                raise ValueError("xz archive exceeds decompression limit")
        yield asset


def _validate_archive_members(members: Iterable[tuple[str, int]]) -> None:
    total = 0
    count = 0
    for name, size in members:
        normalized = Path(name)
        if normalized.is_absolute() or ".." in normalized.parts:
            raise ValueError(f"unsafe archive member: {name}")
        count += 1
        total += max(0, size)
        if count > _ARCHIVE_MAX_FILES or total > _ARCHIVE_MAX_BYTES:
            raise ValueError("archive exceeds file-count or decompression limit")


class SQLiteAcquisitionQueue:
    """Local test/development queue with Postgres-compatible job semantics.

    Production workers use the equivalent ``catalog_acquisition_jobs`` schema in
    ``0004_deep_catalog_acquisition.sql``. This implementation makes claims
    atomic via ``BEGIN IMMEDIATE`` and is intentionally category scoped.
    """

    def __init__(self, path: str | Path) -> None:
        self.path = str(path)
        self._ensure()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.path, timeout=30, isolation_level=None)
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure(self) -> None:
        with self._connect() as conn:
            conn.executescript(
                """CREATE TABLE IF NOT EXISTS acquisition_jobs (
                    job_id TEXT PRIMARY KEY, idempotency_key TEXT NOT NULL UNIQUE,
                    category_slug TEXT NOT NULL, payload_json TEXT NOT NULL,
                    state TEXT NOT NULL DEFAULT 'pending', priority INTEGER NOT NULL DEFAULT 0,
                    attempts INTEGER NOT NULL DEFAULT 0, available_at REAL NOT NULL,
                    claimed_by TEXT, claim_expires_at REAL, result_json TEXT NOT NULL DEFAULT '{}',
                    error TEXT, created_at REAL NOT NULL, updated_at REAL NOT NULL
                );
                CREATE INDEX IF NOT EXISTS idx_acquisition_claim
                ON acquisition_jobs(category_slug, state, priority DESC, available_at);"""
            )

    def enqueue(self, *, category_slug: str, payload: dict[str, Any], priority: int = 0) -> bool:
        source = str(payload.get("source_uri", ""))
        digest = str(payload.get("sha256", ""))
        key = source_fingerprint(source_uri=source, sha256=digest, category_slug=category_slug)
        now = time.time()
        with self._connect() as conn:
            cursor = conn.execute(
                """INSERT OR IGNORE INTO acquisition_jobs
                (job_id,idempotency_key,category_slug,payload_json,priority,available_at,created_at,updated_at)
                VALUES (?,?,?,?,?,?,?,?)""",
                (uuid.uuid4().hex, key, category_slug, json.dumps(payload, sort_keys=True),
                 priority, now, now, now),
            )
        return cursor.rowcount == 1

    def claim_next(self, *, worker_id: str, category_slug: str, lease_seconds: int = 300) -> AcquisitionJob | None:
        now = time.time()
        with self._connect() as conn:
            conn.execute("BEGIN IMMEDIATE")
            row = conn.execute(
                """SELECT * FROM acquisition_jobs
                   WHERE category_slug=? AND available_at<=?
                   AND (state IN ('pending','retry') OR (state='processing' AND claim_expires_at<?))
                   ORDER BY priority DESC, created_at LIMIT 1""",
                (category_slug, now, now),
            ).fetchone()
            if row is None:
                conn.execute("COMMIT")
                return None
            conn.execute(
                """UPDATE acquisition_jobs SET state='processing', claimed_by=?, claim_expires_at=?,
                   attempts=attempts+1, updated_at=? WHERE job_id=?""",
                (worker_id, now + lease_seconds, now, row["job_id"]),
            )
            conn.execute("COMMIT")
        return AcquisitionJob(
            job_id=row["job_id"], category_slug=row["category_slug"],
            payload=json.loads(row["payload_json"]), idempotency_key=row["idempotency_key"],
            attempts=int(row["attempts"]) + 1,
        )

    def finish(self, job: AcquisitionJob, *, result: dict[str, Any]) -> None:
        self._set_terminal(job.job_id, "completed", result=result)

    def reject(self, job: AcquisitionJob, *, reason: str) -> None:
        self._set_terminal(job.job_id, "rejected", error=reason)

    def fail(self, job: AcquisitionJob, *, error: str, retry_delay_s: int = 60, max_attempts: int = 3) -> None:
        state = "dead_letter" if job.attempts >= max_attempts else "retry"
        with self._connect() as conn:
            conn.execute(
                """UPDATE acquisition_jobs SET state=?, error=?, available_at=?, claimed_by=NULL,
                   claim_expires_at=NULL, updated_at=? WHERE job_id=?""",
                (state, error[:2_000], time.time() + retry_delay_s, time.time(), job.job_id),
            )

    def _set_terminal(self, job_id: str, state: str, *, result: dict[str, Any] | None = None,
                      error: str | None = None) -> None:
        with self._connect() as conn:
            conn.execute(
                """UPDATE acquisition_jobs SET state=?, result_json=?, error=?, claimed_by=NULL,
                   claim_expires_at=NULL, updated_at=? WHERE job_id=?""",
                (state, json.dumps(result or {}, sort_keys=True), error, time.time(), job_id),
            )

    def status(self, *, category_slug: str | None = None) -> dict[str, int]:
        where, params = ("", ()) if category_slug is None else (" WHERE category_slug=?", (category_slug,))
        with self._connect() as conn:
            rows = conn.execute(
                f"SELECT state, COUNT(*) AS count FROM acquisition_jobs{where} GROUP BY state", params,
            ).fetchall()
        return {str(row["state"]): int(row["count"]) for row in rows}


def csv_rows_as_sections(path: str | Path, *, heading_column: str | None = None) -> list[tuple[str, str]]:
    """Normalize a CSV import without allowing spreadsheet formula execution."""
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        rows = list(csv.DictReader(stream))
    sections = []
    for index, row in enumerate(rows, start=1):
        heading = (row.get(heading_column or "", "") or f"Row {index}").strip()
        body = " ".join(str(value).strip() for value in row.values() if value).strip()
        if body:
            sections.append((heading, body))
    return sections
