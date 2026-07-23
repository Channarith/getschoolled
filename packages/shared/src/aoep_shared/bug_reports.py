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
import urllib.parse
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
    private_issue_url: str = ""
    public_issue_url: str = ""
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


def _github_json(
    method: str,
    url: str,
    token: str,
    payload: Dict[str, Any],
) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8") if method.upper() not in ("GET", "HEAD") else None
    headers = {
        "Accept": "application/vnd.github+json",
        "Authorization": f"Bearer {token}",
        "User-Agent": "salareen-bug-reporter",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if body is not None:
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=body, method=method, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:  # noqa: S310
        body = response.read()
        if not body or getattr(response, "status", 200) == 204:
            return {}
        return dict(json.loads(body.decode("utf-8")))


def _create_github_issue(
    repo: str,
    token: str,
    title: str,
    body: str,
) -> str:
    result = _github_json(
        "POST",
        f"https://api.github.com/repos/{repo}/issues",
        token,
        {"title": title, "body": body},
    )
    return str(result.get("html_url", ""))


# GitHub Contents API rejects files larger than 1 MB; use the Git blobs API
# (which accepts up to 100 MB) for anything bigger.
_GITHUB_CONTENTS_MAX_BYTES = 900_000


def _upload_one_screenshot(
    data: bytes,
    repo: str,
    repo_path: str,
    token: str,
) -> str:
    """Upload a single file to the repo and return its html_url."""
    api_path = urllib.parse.quote(repo_path, safe="/")
    b64 = base64.b64encode(data).decode("ascii")

    if len(data) <= _GITHUB_CONTENTS_MAX_BYTES:
        # Small file — Contents API (single PUT, no tree wiring needed).
        result = _github_json(
            "PUT",
            f"https://api.github.com/repos/{repo}/contents/{api_path}",
            token,
            {"message": f"Add {repo_path}", "content": b64},
        )
        return str((result.get("content") or {}).get("html_url", ""))

    # Large file — Git Data API: create blob → get default branch → create tree
    # → create commit → update ref.
    blob = _github_json(
        "POST",
        f"https://api.github.com/repos/{repo}/git/blobs",
        token,
        {"content": b64, "encoding": "base64"},
    )
    blob_sha = str(blob.get("sha", ""))
    if not blob_sha:
        raise ValueError("blob creation returned no sha")

    # Get the current HEAD sha and tree sha.
    repo_info = _github_json(
        "GET",  # type: ignore[arg-type]
        f"https://api.github.com/repos/{repo}",
        token,
        {},
    )
    default_branch = str(repo_info.get("default_branch", "main"))
    ref_data = _github_json(
        "GET",  # type: ignore[arg-type]
        f"https://api.github.com/repos/{repo}/git/ref/heads/{default_branch}",
        token,
        {},
    )
    head_sha = str((ref_data.get("object") or {}).get("sha", ""))
    commit_data = _github_json(
        "GET",  # type: ignore[arg-type]
        f"https://api.github.com/repos/{repo}/git/commits/{head_sha}",
        token,
        {},
    )
    base_tree_sha = str((commit_data.get("tree") or {}).get("sha", ""))

    tree = _github_json(
        "POST",
        f"https://api.github.com/repos/{repo}/git/trees",
        token,
        {
            "base_tree": base_tree_sha,
            "tree": [{"path": repo_path, "mode": "100644", "type": "blob", "sha": blob_sha}],
        },
    )
    new_commit = _github_json(
        "POST",
        f"https://api.github.com/repos/{repo}/git/commits",
        token,
        {
            "message": f"Add large screenshot for {repo_path}",
            "tree": str(tree.get("sha", "")),
            "parents": [head_sha],
        },
    )
    _github_json(
        "PATCH",
        f"https://api.github.com/repos/{repo}/git/refs/heads/{default_branch}",
        token,
        {"sha": str(new_commit.get("sha", ""))},
    )
    return f"https://github.com/{repo}/blob/{default_branch}/{repo_path}"


def _upload_private_screenshots(
    report: BugReport,
    root: Path,
    repo: str,
    token: str,
) -> tuple[List[str], List[str]]:
    """Upload screenshots to the private QA repo and return operator-only links."""
    links: List[str] = []
    errors: List[str] = []
    for filename in report.attachments:
        path = root / report.id / filename
        try:
            data = path.read_bytes()
            repo_path = f"bug-report-attachments/{report.id}/{filename}"
            url = _upload_one_screenshot(data, repo, repo_path, token)
            if url:
                links.append(f"- ![{filename}]({url})")
            else:
                errors.append(f"{filename}: upload returned no URL")
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            errors.append(f"{filename}: {str(exc)[:200]}")
    return links, errors


def _private_issue_body(
    report: BugReport,
    attachment_links: List[str],
    attachment_errors: List[str],
) -> str:
    diagnostics = {
        "report_id": report.id,
        "screen": report.screen,
        "platform": report.platform,
        "app_version": report.app_version,
        "user_id": report.user_id,
        "email": report.email,
        "snapshot": report.snapshot,
        "logs": report.logs[-100:],
    }
    attachments = "\n".join(attachment_links) or "No screenshots attached."
    if attachment_errors:
        attachments += "\n\nUpload errors:\n" + "\n".join(
            f"- {error}" for error in attachment_errors
        )
    return (
        "Submitted by the in-app floating bug reporter.\n\n"
        f"Description:\n{report.description}\n\n"
        f"Screenshots (private repository):\n{attachments}\n\n"
        "Diagnostics (request bodies, auth headers, and URL query strings are not captured):\n"
        f"```json\n{json.dumps(diagnostics, indent=2, default=str)[:55_000]}\n```"
    )


def _public_issue_body(report: BugReport, private_url: str) -> str:
    """Public mirror deliberately excludes free text, identities, logs and images."""
    private_line = (
        f"Operator evidence: {private_url}"
        if private_url
        else "Operator evidence is retained in the private QA inbox."
    )
    return (
        "A redacted user QA report was received.\n\n"
        f"- Report ID: `{report.id}`\n"
        f"- Category: `{report.category}`\n"
        f"- Platform: `{report.platform}`\n"
        f"- App version: `{report.app_version}`\n"
        f"- Screen: `{report.screen.split('?', 1)[0]}`\n"
        f"- {private_line}\n\n"
        "The user description, account identifiers, diagnostics, and screenshots "
        "are intentionally excluded from this public issue."
    )


def _github_delivery(report: BugReport, root: Path) -> tuple[str, str, str]:
    """Deliver full evidence privately and a metadata-only mirror publicly."""
    private_repo = (
        os.environ.get("BUG_REPORT_GITHUB_PRIVATE_REPO", "").strip().strip("/")
        or os.environ.get("BUG_REPORT_GITHUB_REPO", "").strip().strip("/")
    )
    public_repo = os.environ.get("BUG_REPORT_GITHUB_PUBLIC_REPO", "").strip().strip("/")
    token = os.environ.get("BUG_REPORT_GITHUB_TOKEN", "").strip()
    if not private_repo and not public_repo:
        return "", "", ""
    if not token:
        return "", "", "BUG_REPORT_GITHUB_TOKEN is not configured"

    private_url = ""
    public_url = ""
    errors: List[str] = []
    title = f"[User QA] {report.platform} {report.app_version}: {report.description[:100]}"

    if private_repo:
        links, upload_errors = _upload_private_screenshots(
            report, root, private_repo, token
        )
        try:
            private_url = _create_github_issue(
                private_repo,
                token,
                title,
                _private_issue_body(report, links, upload_errors),
            )
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            errors.append(f"private issue: {str(exc)[:300]}")

    if public_repo:
        public_title = (
            f"[User QA] {report.platform} {report.app_version} "
            f"on {report.screen.split('?', 1)[0] or 'unknown screen'}"
        )
        try:
            public_url = _create_github_issue(
                public_repo,
                token,
                public_title[:150],
                _public_issue_body(report, private_url),
            )
        except (OSError, ValueError, urllib.error.HTTPError) as exc:
            errors.append(f"public issue: {str(exc)[:300]}")

    return private_url, public_url, "; ".join(errors)


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
        private_url, public_url, delivery_error = _github_delivery(report, self.root)
        if private_url or public_url:
            report.destination = "github"
            report.private_issue_url = private_url
            report.public_issue_url = public_url
            report.external_url = private_url or public_url
        if delivery_error:
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
