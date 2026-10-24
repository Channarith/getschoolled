"""Tiny, forward-only migration runner for the catalog database.

SQL lives in aoep_shared/catalog_db/sql/NNN_name.sql and ships in the package (see
package-data in packages/shared/pyproject.toml; a test fails if a .sql file is not packaged).

  * every pending file runs in its own transaction, in version order;
  * applied files are checksummed: editing an applied migration is refused, add a new one;
  * a Postgres advisory lock makes two replicas starting at once safe;
  * dry_run lists what would run and touches nothing.

psycopg (v3) is imported lazily so importing this module needs nothing installed.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, List, Optional

SQL_DIR = Path(__file__).resolve().parent / "sql"
_NAME_RE = re.compile(r"^(\d{3,})_([a-z0-9_]+)\.sql$")
ADVISORY_LOCK_KEY = 7_424_001
TABLE = "catalog_schema_migrations"


@dataclass(frozen=True)
class Migration:
    version: int
    name: str
    path: Path
    checksum: str
    sql: str


@dataclass
class MigrationReport:
    applied: List[str] = field(default_factory=list)
    pending: List[str] = field(default_factory=list)
    already: List[str] = field(default_factory=list)
    problems: List[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.problems


def discover(directory: Optional[Path] = None) -> List[Migration]:
    """All migrations in version order. Raises on duplicate versions or badly named files."""
    directory = Path(directory) if directory else SQL_DIR
    found: List[Migration] = []
    for path in sorted(directory.glob("*.sql")):
        match = _NAME_RE.match(path.name)
        if not match:
            raise ValueError(f"migration file name must look like 001_name.sql: {path.name}")
        sql = path.read_text(encoding="utf-8")
        found.append(
            Migration(
                version=int(match.group(1)),
                name=match.group(2),
                path=path,
                checksum=hashlib.sha256(sql.encode("utf-8")).hexdigest(),
                sql=sql,
            )
        )
    versions = [m.version for m in found]
    if len(set(versions)) != len(versions):
        raise ValueError(f"duplicate migration versions: {sorted(v for v in versions if versions.count(v) > 1)}")
    return sorted(found, key=lambda m: m.version)


def connect(dsn: str, **kwargs: Any):
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - exercised only without the driver
        raise RuntimeError(
            "psycopg is not installed: pip install 'psycopg[binary]>=3.2' (catalog database support)"
        ) from exc
    return psycopg.connect(dsn, **kwargs)


def _applied(conn: Any) -> dict:
    with conn.cursor() as cur:
        cur.execute(
            f"CREATE TABLE IF NOT EXISTS {TABLE} ("
            "version INTEGER PRIMARY KEY, name TEXT NOT NULL, checksum TEXT NOT NULL, "
            "applied_at TIMESTAMPTZ NOT NULL DEFAULT now())"
        )
        cur.execute(f"SELECT version, name, checksum FROM {TABLE} ORDER BY version")
        rows = cur.fetchall()
    conn.commit()
    return {int(v): (n, c) for v, n, c in rows}


def migrate(conn: Any, *, dry_run: bool = False, migrations: Optional[List[Migration]] = None) -> MigrationReport:
    """Apply every pending migration. Safe to call concurrently and repeatedly."""
    report = MigrationReport()
    migrations = migrations if migrations is not None else discover()
    with conn.cursor() as cur:
        cur.execute("SELECT pg_advisory_lock(%s)", (ADVISORY_LOCK_KEY,))
    conn.commit()
    try:
        applied = _applied(conn)
        for m in migrations:
            label = f"{m.version:03d}_{m.name}"
            if m.version in applied:
                if applied[m.version][1] != m.checksum:
                    report.problems.append(
                        f"{label}: file changed after it was applied (checksum mismatch); add a new migration instead"
                    )
                else:
                    report.already.append(label)
                continue
            if dry_run:
                report.pending.append(label)
                continue
            try:
                with conn.cursor() as cur:
                    cur.execute(m.sql)
                    cur.execute(
                        f"INSERT INTO {TABLE} (version, name, checksum) VALUES (%s, %s, %s)",
                        (m.version, m.name, m.checksum),
                    )
                conn.commit()
                report.applied.append(label)
            except Exception as exc:
                conn.rollback()
                report.problems.append(f"{label}: {exc}")
                break  # never run later migrations over a failed one
    finally:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_unlock(%s)", (ADVISORY_LOCK_KEY,))
        conn.commit()
    return report


def status(conn: Any) -> MigrationReport:
    return migrate(conn, dry_run=True)
