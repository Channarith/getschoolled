"""Durable, rate-limited publishing of harvested decks to the production catalog.

Production runs four small nodes, so the publisher is deliberately gentle:
  * a token bucket caps requests per second (and slows down further on 429/5xx),
  * retries use exponential backoff with jitter and honor Retry-After,
  * a circuit breaker stops hitting a failing service and probes it again after a cool-down,
  * progress lives in the SQLite index (courses.published_at), so a crash or restart never
    republishes a deck that already succeeded and never loses one that did not.

The curriculum POST /courses endpoint is NOT idempotent by itself (it always mints a new id),
so before posting we look the deck up by its sha tag and skip it if the catalog has it.
Everything that touches time, sleeping, randomness or the network is injectable for tests.
"""

from __future__ import annotations

import json
import random
import sqlite3
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Callable, Dict, List, Optional, Protocol, Tuple

from .bundle import migrate_index
from .errors import CorpusWallError
from .licensing import assert_product_safe
from .objectstore import ObjectStore, course_key, unpack_course

Transport = Callable[[str, str, Optional[dict], Dict[str, str]], Tuple[int, Dict[str, str], bytes]]

PUBLISH_SCHEMA = """
CREATE TABLE IF NOT EXISTS publish_failures (
  sha256 TEXT PRIMARY KEY, status INTEGER, reason TEXT, attempts INTEGER, at TEXT NOT NULL);
"""

TIER_LABELS = {0: "machine-generated", 1: "auto-validated", 2: "human-reviewed"}


def default_transport(
    method: str, url: str, body: Optional[dict], headers: Dict[str, str], timeout: float = 20.0
) -> Tuple[int, Dict[str, str], bytes]:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url, data=data, method=method, headers={"Content-Type": "application/json", **headers}
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return resp.status, {k.lower(): v for k, v in resp.headers.items()}, resp.read()
    except urllib.error.HTTPError as exc:
        return exc.code, {k.lower(): v for k, v in (exc.headers or {}).items()}, exc.read() or b""


class TransientError(Exception):
    def __init__(self, status: int, retry_after: Optional[float] = None, reason: str = "") -> None:
        super().__init__(reason or f"transient {status}")
        self.status, self.retry_after = status, retry_after


class PermanentError(Exception):
    def __init__(self, status: int, reason: str) -> None:
        super().__init__(reason)
        self.status = status


class AuthError(Exception):
    pass


class Sink(Protocol):
    def exists(self, sha: str) -> bool: ...
    def publish(self, sha: str, payload: dict) -> None: ...


class CurriculumHttpSink:
    """POST /courses on the curriculum service (internal token). Maps HTTP codes to retry classes."""

    def __init__(self, base_url: str, token: str, transport: Transport = default_transport) -> None:
        self.base = base_url.rstrip("/")
        self.headers = {"X-Internal-Token": token}
        self._t = transport

    def _call(self, method: str, path: str, body: Optional[dict] = None) -> Tuple[int, bytes]:
        try:
            status, headers, data = self._t(method, f"{self.base}{path}", body, self.headers)
        except (urllib.error.URLError, TimeoutError, ConnectionError, OSError) as exc:
            raise TransientError(0, None, f"network: {exc}") from exc
        if status in (401, 403):
            raise AuthError(f"{status} from {path}: check INTERNAL_TOKEN")
        if status == 429 or status >= 500:
            ra = headers.get("retry-after")
            raise TransientError(
                status, float(ra) if ra and ra.replace(".", "", 1).isdigit() else None
            )
        if status >= 400:
            raise PermanentError(status, data[:200].decode("utf-8", "replace"))
        return status, data

    def exists(self, sha: str) -> bool:
        _, data = self._call("GET", f"/courses/search?tag=sha:{sha[:16]}&limit=1")
        try:
            return bool(json.loads(data or b"[]"))
        except ValueError:
            return False

    def publish(self, sha: str, payload: dict) -> None:
        self._call("POST", "/courses", payload)


class ObjectStoreIndexSink:
    """Writes catalog index records to the object store (the source of truth for a future
    database-backed catalog). Content-addressed, so re-publishing is a harmless no-op."""

    def __init__(self, store: ObjectStore) -> None:
        self.store = store

    def exists(self, sha: str) -> bool:
        return self.store.exists(f"index/records/{sha[:2]}/{sha}.json")

    def publish(self, sha: str, payload: dict) -> None:
        self.store.put(
            f"index/records/{sha[:2]}/{sha}.json", json.dumps(payload, ensure_ascii=False).encode()
        )


def build_payload(
    course: dict, *, sha: str, tier: int, subject: str = "", source_url: str = "",
    license_tier: str = "", corpus: str = "product",
) -> dict:
    slides = course.get("slides") or []
    first = (slides[0].get("body") if slides else "") or ""
    return {
        "title": course.get("title") or "Untitled",
        "subject": subject or course.get("subject") or "general",
        "language": course.get("language") or "en",
        "description": first[:300],
        "media_format": "text",
        "preview": first[:160],
        "tags": [
            "harvest",
            f"sha:{sha[:16]}",
            f"tier:{tier}",
            TIER_LABELS.get(tier, "machine-generated"),
        ]
        + (["source:" + source_url[:80]] if source_url else [])
        + [f"corpus:{corpus or 'product'}"]
        + ([f"license:{license_tier}"] if license_tier else []),
    }


@dataclass
class PublishConfig:
    rate_per_sec: float = 2.0
    burst: int = 4
    batch_size: int = 20
    max_retries: int = 5
    backoff_base: float = 1.0
    backoff_max: float = 60.0
    breaker_failures: int = 5
    breaker_cooldown: float = 120.0
    max_breaker_waits: int = 3
    min_tier: int = 0
    max_total: Optional[int] = None
    dry_run: bool = False
    check_existing: bool = True


class TokenBucket:
    def __init__(
        self, rate: float, burst: int, clock: Callable[[], float], sleep: Callable[[float], None]
    ) -> None:
        self.base_rate, self.rate, self.burst = rate, rate, burst
        self._tokens, self._clock, self._sleep = float(burst), clock, sleep
        self._last = clock()

    def acquire(self) -> None:
        now = self._clock()
        self._tokens = min(self.burst, self._tokens + (now - self._last) * self.rate)
        self._last = now
        if self._tokens < 1:
            self._sleep((1 - self._tokens) / self.rate)
            self._last = self._clock()
            self._tokens = 1.0
        self._tokens -= 1

    def slow_down(self) -> None:
        self.rate = max(self.base_rate / 16, self.rate / 2)

    def recover(self) -> None:
        self.rate = min(self.base_rate, self.rate * 1.1)


class CircuitBreaker:
    def __init__(self, threshold: int, cooldown: float, clock: Callable[[], float]) -> None:
        self.threshold, self.cooldown, self._clock = threshold, cooldown, clock
        self.failures, self.opened_at = 0, None

    def allow(self) -> bool:
        if self.opened_at is None:
            return True
        return self._clock() - self.opened_at >= self.cooldown  # half-open: let one probe through

    def remaining(self) -> float:
        return (
            0.0
            if self.opened_at is None
            else max(0.0, self.cooldown - (self._clock() - self.opened_at))
        )

    def success(self) -> None:
        self.failures, self.opened_at = 0, None

    def failure(self) -> None:
        self.failures += 1
        if self.failures >= self.threshold:
            self.opened_at = self._clock()


@dataclass
class PublishReport:
    published: int = 0
    skipped_existing: int = 0
    failed_permanent: int = 0
    retries: int = 0
    breaker_trips: int = 0
    dry_run: int = 0
    wall_blocked: int = 0       # refused by the product/research wall (should always be 0)
    stopped: str = ""
    errors: List[str] = field(default_factory=list)


class Publisher:
    def __init__(
        self,
        index: sqlite3.Connection,
        store: ObjectStore,
        sink: Sink,
        cfg: Optional[PublishConfig] = None,
        *,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
        rng: Callable[[], float] = random.random,
    ) -> None:
        self.index, self.store, self.sink = index, store, sink
        self.cfg = cfg or PublishConfig()
        self._sleep, self._rng = sleep, rng
        self.bucket = TokenBucket(self.cfg.rate_per_sec, self.cfg.burst, clock, sleep)
        self.breaker = CircuitBreaker(self.cfg.breaker_failures, self.cfg.breaker_cooldown, clock)
        self.index.executescript(PUBLISH_SCHEMA)
        migrate_index(self.index)

    def _pending(self, limit: int, attempted: set) -> List[sqlite3.Row]:
        rows = self.index.execute(
            "SELECT c.sha256, c.tier, c.subject, c.source_url, c.license, c.license_tier, c.corpus FROM courses c "
            "LEFT JOIN publish_failures f ON f.sha256=c.sha256 "
            "WHERE c.published_at IS NULL AND f.sha256 IS NULL AND c.tier>=? ORDER BY c.tier DESC, c.subject, c.sha256 LIMIT ?",
            (self.cfg.min_tier, limit + len(attempted)),
        ).fetchall()
        # Every deck is tried at most once per run: dry runs, transient failures and a flapping
        # service can never make a run loop forever. A later run picks up what is left.
        return [r for r in rows if r["sha256"] not in attempted][:limit]

    def _with_retries(self, fn: Callable[[], object], report: PublishReport) -> object:
        for attempt in range(self.cfg.max_retries + 1):
            self.bucket.acquire()
            try:
                result = fn()
                self.bucket.recover()
                return result
            except TransientError as exc:
                self.bucket.slow_down()
                if attempt == self.cfg.max_retries:
                    raise
                report.retries += 1
                delay = min(self.cfg.backoff_max, self.cfg.backoff_base * (2**attempt))
                delay = max(
                    exc.retry_after or 0.0, delay * (0.5 + self._rng() / 2)
                )  # jitter 0.5x..1x
                self._sleep(delay)
        raise AssertionError("unreachable")

    def run(self) -> PublishReport:
        report = PublishReport()
        waits = 0
        attempted: set = set()
        while True:
            if (
                self.cfg.max_total is not None
                and report.published + report.dry_run >= self.cfg.max_total
            ):
                report.stopped = "max_total"
                break
            rows = self._pending(self.cfg.batch_size, attempted)
            if not rows:
                report.stopped = "done"
                break
            for row in rows:
                if (
                    self.cfg.max_total is not None
                    and report.published + report.dry_run >= self.cfg.max_total
                ):
                    break
                attempted.add(row["sha256"])
                if not self.breaker.allow():
                    waits += 1
                    if waits > self.cfg.max_breaker_waits:
                        report.stopped = "breaker_open"
                        return report
                    self._sleep(self.breaker.remaining())
                sha = row["sha256"]
                try:
                    # The wall, asserted again at the last moment: nothing from the research corpus and
                    # nothing whose license is not product-safe is ever sent to the catalog.
                    assert_product_safe(
                        license=row["license"], tier=row["license_tier"], corpus=row["corpus"],
                    )
                except CorpusWallError as exc:
                    self._fail(sha, 0, f"wall: {exc}")
                    report.failed_permanent += 1
                    report.wall_blocked += 1
                    continue
                try:
                    course = unpack_course(self.store.get(course_key(sha)))
                    payload = build_payload(
                        course,
                        sha=sha,
                        tier=row["tier"],
                        subject=row["subject"] or "",
                        source_url=row["source_url"] or "",
                        license_tier=row["license_tier"] or "",
                        corpus=row["corpus"] or "product",
                    )
                    if self.cfg.dry_run:
                        report.dry_run += 1
                        continue
                    if self.cfg.check_existing and self._with_retries(
                        lambda: self.sink.exists(sha), report
                    ):
                        self._mark(sha)
                        report.skipped_existing += 1
                        continue
                    self._with_retries(lambda: self.sink.publish(sha, payload), report)
                    self._mark(sha)
                    self.breaker.success()
                    report.published += 1
                except PermanentError as exc:
                    self._fail(sha, exc.status, str(exc))
                    report.failed_permanent += 1
                except TransientError as exc:
                    was_open = self.breaker.opened_at is not None
                    self.breaker.failure()
                    if self.breaker.opened_at is not None and not was_open:
                        report.breaker_trips += 1
                    report.errors.append(f"{sha[:12]}: {exc}")
                except AuthError as exc:
                    report.stopped = f"auth: {exc}"
                    return report
        return report

    def _mark(self, sha: str) -> None:
        self.index.execute(
            "UPDATE courses SET published_at=? WHERE sha256=?",
            (datetime.now(timezone.utc).isoformat(), sha),
        )
        self.index.commit()

    def _fail(self, sha: str, status: int, reason: str) -> None:
        self.index.execute(
            "INSERT OR REPLACE INTO publish_failures VALUES (?,?,?,?,?)",
            (sha, status, reason[:300], 1, datetime.now(timezone.utc).isoformat()),
        )
        self.index.commit()
