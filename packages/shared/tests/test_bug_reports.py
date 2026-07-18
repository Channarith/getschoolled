"""Bug report store: submit, list, attachments."""

from __future__ import annotations

import base64

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
