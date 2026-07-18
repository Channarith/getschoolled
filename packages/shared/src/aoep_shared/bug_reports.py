"""In-app bug reports for user-driven QA.

Learners submit what went wrong along with optional screenshots, a redacted app
snapshot (route/screen, version, device), and a ring buffer of client logs. Reports
persist to disk (JSONL index + attachment files) so they survive process restarts
and give operators free QA signal without a third-party crash reporter.
"""

from __future__ import annotations

import base64
import json
import os
import re
import time
import uuid
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

MAX_SCREENSHOT_BYTES = 2_000_000
MAX_SCREENSHOTS = 3
MAX_LOG_LINES = 200
MAX_LOG_LINE_CHARS = 2000
MAX_DESCRIPTION_CHARS = 4000
MAX_SNAPSHOT_BYTES = 64_000


def default_bug_report_dir() -> Path:
    raw = os.environ.get("AOEP_BUG_REPORT_DIR", "").strip()
    if raw:
        return Path(raw).expanduser()
    return Path.home() / ".cache" / "aoep" / "bug-reports"


class BugScreenshotUpload(BaseModel):
    """Client attachment (base64) before the server writes it to disk."""

    filename: str = "screenshot.png"
    content_type: str = "image/png"
    data_base64: str = ""


class BugReportSubmit(BaseModel):
    description: str
    category: str = "bug"  # bug | crash | ux | other
    screen: str = ""
    platform: str = "web"  # web | ios | android
    app_version: str = ""
    user_id: str = ""
    email: str = ""
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    screenshots: List[BugScreenshotUpload] = Field(default_factory=list)


class BugReport(BaseModel):
    id: str
    created_at: float
    description: str
    category: str = "bug"
    screen: str = ""
    platform: str = "web"
    app_version: str = ""
    user_id: str = ""
    email: str = ""
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    logs: List[str] = Field(default_factory=list)
    attachments: List[str] = Field(default_factory=list)
    destination: str = "qa-inbox"
    external_url: str = ""
    delivery_error: str = ""


def _safe_filename(name: str) -> str:
    base = re.sub(r"[^a-zA-Z0-9._-]+", "_", (name or "screenshot.png").strip())[:80]
    return base or "screenshot.png"


def _trim_logs(lines: List[str]) -> List[str]:
    out: List[str] = []
    for line in lines[-MAX_LOG_LINES:]:
        s = str(line or "")[:MAX_LOG_LINE_CHARS]
        if s:
            out.append(s)
    return out


def _trim_snapshot(data: Dict[str, Any]) -> Dict[str, Any]:
    try:
        blob = json.dumps(data, separators=(",", ":"), default=str)
    except TypeError:
        data = {"unserializable": True}
        blob = "{}"
    if len(blob.encode("utf-8")) <= MAX_SNAPSHOT_BYTES:
        return data
    return {
        "truncated": True,
        "preview": blob[: MAX_SNAPSHOT_BYTES // 2],
    }


def _github_issue(report: BugReport) -> tuple[str, str]:
    """Optionally mirror a report to GitHub Issues, without exposing credentials.

    Configure both BUG_REPORT_GITHUB_REPO=owner/repo and
    BUG_REPORT_GITHUB_TOKEN. The local QA inbox remains the durable source of
    truth when GitHub is unavailable or intentionally not configured.
    """
    repo = os.environ.get("BUG_REPORT_GITHUB_REPO", "").strip().strip("/")
    token = os.environ.get("BUG_REPORT_GITHUB_TOKEN", "").strip()
    if not repo or not token:
        return "", ""
    title = f"[User QA] {report.platform} {report.app_version}: {report.description[:100]}"
    diagnostics = {
        "report_id": report.id,
        "screen": report.screen,
        "platform": report.platform,
        "app_version": report.app_version,
        "user_id": report.user_id,
        "snapshot": report.snapshot,
        "logs": report.logs[-100:],
        "attachments_in_qa_inbox": report.attachments,
    }
    body = (
        "Submitted by the in-app floating bug reporter.\n\n"
        f"Description:\n{report.description}\n\n"
        "Diagnostics (request bodies, auth headers, and URL query strings are not captured):\n"
        f"```json\n{json.dumps(diagnostics, indent=2, default=str)[:55_000]}\n```"
    )
    payload = json.dumps({
        "title": title,
        "body": body,
    }).encode("utf-8")
    request = urllib.request.Request(
        f"https://api.github.com/repos/{repo}/issues",
        data=payload,
        method="POST",
        headers={
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
            "User-Agent": "salareen-bug-reporter",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=5) as response:  # noqa: S310
            result = json.loads(response.read().decode("utf-8"))
        return str(result.get("html_url", "")), ""
    except (OSError, ValueError, urllib.error.HTTPError) as exc:
        return "", str(exc)[:500]


@dataclass
class BugReportStore:
    """Filesystem-backed bug report inbox."""

    root: Path

    def __post_init__(self) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        self._index_path = self.root / "reports.jsonl"

    @classmethod
    def open(cls, root: Path | None = None) -> "BugReportStore":
        return cls(root or default_bug_report_dir())

    def _append_index(self, report: BugReport) -> None:
        line = json.dumps(report.model_dump(), separators=(",", ":"))
        with self._index_path.open("a", encoding="utf-8") as fh:
            fh.write(line + "\n")

    def _save_screenshot(self, report_id: str, upload: BugScreenshotUpload, idx: int) -> str:
        raw = (upload.data_base64 or "").strip()
        if raw.startswith("data:"):
            raw = raw.split(",", 1)[-1]
        try:
            data = base64.b64decode(raw, validate=True)
        except Exception as exc:
            raise ValueError(f"invalid screenshot data ({exc})") from exc
        if len(data) > MAX_SCREENSHOT_BYTES:
            raise ValueError(f"screenshot exceeds {MAX_SCREENSHOT_BYTES} bytes")
        folder = self.root / report_id
        folder.mkdir(parents=True, exist_ok=True)
        fname = f"{idx:02d}-{_safe_filename(upload.filename)}"
        path = folder / fname
        path.write_bytes(data)
        return fname

    def submit(self, req: BugReportSubmit) -> BugReport:
        desc = (req.description or "").strip()
        if not desc:
            raise ValueError("description is required")
        if len(desc) > MAX_DESCRIPTION_CHARS:
            raise ValueError("description is too long")
        if len(req.screenshots) > MAX_SCREENSHOTS:
            raise ValueError(f"at most {MAX_SCREENSHOTS} screenshots")

        report_id = f"bug-{uuid.uuid4().hex[:12]}"
        attachments: List[str] = []
        for i, shot in enumerate(req.screenshots):
            if not (shot.data_base64 or "").strip():
                continue
            attachments.append(self._save_screenshot(report_id, shot, i))

        report = BugReport(
            id=report_id,
            created_at=time.time(),
            description=desc,
            category=(req.category or "bug").strip().lower()[:32] or "bug",
            screen=(req.screen or "").strip()[:256],
            platform=(req.platform or "web").strip().lower()[:16] or "web",
            app_version=(req.app_version or "").strip()[:32],
            user_id=(req.user_id or "").strip()[:64],
            email=(req.email or "").strip()[:128],
            snapshot=_trim_snapshot(dict(req.snapshot or {})),
            logs=_trim_logs(list(req.logs or [])),
            attachments=attachments,
        )
        external_url, delivery_error = _github_issue(report)
        if external_url:
            report.destination = "github"
            report.external_url = external_url
        elif delivery_error:
            report.delivery_error = delivery_error
        self._append_index(report)
        return report

    def list_reports(self, *, limit: int = 50) -> List[BugReport]:
        if not self._index_path.is_file():
            return []
        rows: List[BugReport] = []
        for line in self._index_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(BugReport(**json.loads(line)))
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
        rows.sort(key=lambda r: r.created_at, reverse=True)
        return rows[: max(1, min(limit, 200))]

    def get(self, report_id: str) -> Optional[BugReport]:
        rid = (report_id or "").strip()
        if not rid:
            return None
        for row in self.list_reports(limit=10_000):
            if row.id == rid:
                return row
        return None

    def attachment_bytes(self, report_id: str, filename: str) -> tuple[bytes, str]:
        rid = (report_id or "").strip()
        fname = _safe_filename(filename)
        if not rid or not fname:
            raise FileNotFoundError("missing attachment")
        path = self.root / rid / fname
        if not path.is_file():
            raise FileNotFoundError(fname)
        # Basic content-type guess for the handful of image types we accept.
        ct = "application/octet-stream"
        low = fname.lower()
        if low.endswith(".png"):
            ct = "image/png"
        elif low.endswith(".jpg") or low.endswith(".jpeg"):
            ct = "image/jpeg"
        elif low.endswith(".webp"):
            ct = "image/webp"
        return path.read_bytes(), ct
