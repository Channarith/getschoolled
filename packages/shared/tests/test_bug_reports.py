"""Bug report store: submit, list, attachments."""

from __future__ import annotations

import base64
import json

import pytest

from aoep_shared.bug_reports import BugReportStore, BugReportSubmit, BugScreenshotUpload


def _tiny_png_b64() -> str:
    # 1x1 transparent PNG
    data = base64.b64decode(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
    )
    return base64.b64encode(data).decode("ascii")


def test_submit_persists_report_and_screenshot(tmp_path):
    store = BugReportStore.open(tmp_path / "bugs")
    report = store.submit(
        BugReportSubmit(
            description="Start class button loops",
            platform="web",
            app_version="0.19.92",
            screen="/live-room/demo",
            snapshot={"route": "/live-room/demo", "viewport": "1280x720"},
            logs=["error: narration blocked"],
            screenshots=[
                BugScreenshotUpload(
                    filename="screen.png",
                    content_type="image/png",
                    data_base64=_tiny_png_b64(),
                )
            ],
        )
    )
    assert report.id.startswith("bug-")
    assert report.attachments
    listed = store.list_reports()
    assert listed[0].id == report.id
    data, ct = store.attachment_bytes(report.id, report.attachments[0])
    assert ct == "image/png"
    assert len(data) > 0


def test_submit_requires_description(tmp_path):
    store = BugReportStore.open(tmp_path / "bugs")
    with pytest.raises(ValueError, match="description"):
        store.submit(BugReportSubmit(description="   ", platform="ios"))


def test_submit_optionally_routes_to_github(tmp_path, monkeypatch):
    class FakeResponse:
        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps({"html_url": "https://github.com/acme/app/issues/12"}).encode()

    monkeypatch.setenv("BUG_REPORT_GITHUB_REPO", "acme/app")
    monkeypatch.setenv("BUG_REPORT_GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        "aoep_shared.bug_reports.urllib.request.urlopen",
        lambda *_args, **_kwargs: FakeResponse(),
    )
    report = BugReportStore.open(tmp_path / "bugs").submit(
        BugReportSubmit(description="Course screen froze", platform="android")
    )
    assert report.destination == "github"
    assert report.external_url.endswith("/issues/12")
    assert report.private_issue_url.endswith("/issues/12")


def test_submit_routes_screenshots_privately_and_redacts_public_issue(
    tmp_path, monkeypatch
):
    requests = []

    class FakeResponse:
        def __init__(self, payload):
            self.payload = payload

        def __enter__(self):
            return self

        def __exit__(self, *_args):
            return None

        def read(self):
            return json.dumps(self.payload).encode()

    def fake_urlopen(request, **_kwargs):
        body = json.loads(request.data.decode())
        requests.append((request.full_url, body))
        if "/contents/" in request.full_url:
            return FakeResponse(
                {"content": {"html_url": "https://github.com/acme/private/blob/main/shot.png"}}
            )
        if "/repos/acme/private/issues" in request.full_url:
            return FakeResponse({"html_url": "https://github.com/acme/private/issues/7"})
        return FakeResponse({"html_url": "https://github.com/acme/public/issues/8"})

    monkeypatch.setenv("BUG_REPORT_GITHUB_PRIVATE_REPO", "acme/private")
    monkeypatch.setenv("BUG_REPORT_GITHUB_PUBLIC_REPO", "acme/public")
    monkeypatch.setenv("BUG_REPORT_GITHUB_TOKEN", "test-token")
    monkeypatch.setattr(
        "aoep_shared.bug_reports.urllib.request.urlopen",
        fake_urlopen,
    )

    report = BugReportStore.open(tmp_path / "bugs").submit(
        BugReportSubmit(
            description="Email me at learner@example.com; token secret-value",
            platform="web",
            app_version="0.20.7",
            screen="/drive?student=private",
            email="learner@example.com",
            user_id="student-123",
            logs=["private log"],
            screenshots=[
                BugScreenshotUpload(
                    filename="screen.png",
                    content_type="image/png",
                    data_base64=_tiny_png_b64(),
                )
            ],
        )
    )

    assert report.private_issue_url.endswith("/issues/7")
    assert report.public_issue_url.endswith("/issues/8")
    assert any("/contents/bug-report-attachments/" in url for url, _ in requests)

    private_body = next(
        body["body"]
        for url, body in requests
        if "/repos/acme/private/issues" in url
    )
    assert "learner@example.com" in private_body
    assert "screen.png" in private_body

    public_body = next(
        body["body"]
        for url, body in requests
        if "/repos/acme/public/issues" in url
    )
    assert "learner@example.com" not in public_body
    assert "private log" not in public_body
    assert "student-123" not in public_body
    assert "student=private" not in public_body
    assert "screen.png" not in public_body
