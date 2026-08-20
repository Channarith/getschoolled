"""Synced slide deck HTML generation."""

from aoep_shared.meeting.base import PresentationPlan, PresentationStep
from aoep_shared.meeting.presentation_sync import SyncedSlideShow, write_slide_deck_html


def test_slide_deck_html_contains_slides(tmp_path):
    plan = PresentationPlan(
        title="Algebra",
        steps=[
            PresentationStep(0, "intro", "Welcome", "Hello class", est_seconds=5, slide_index=0),
            PresentationStep(1, "segment", "Variables", "x is unknown", est_seconds=8, slide_index=1),
        ],
    )
    path = write_slide_deck_html(
        plan,
        out_path=tmp_path / "slide_deck.html",
        course_title="Algebra",
        course_slides=[{"body": "Welcome line\nSecond line", "category": "introduction"}],
    )
    html = path.read_text(encoding="utf-8")
    assert "Welcome" in html
    assert "DECK" in html
    assert "state.json" in html


def test_slideshow_start_skips_browser_when_headless(monkeypatch, tmp_path):
    opened: list[str] = []
    monkeypatch.setattr(
        "aoep_shared.meeting.presentation_sync.webbrowser.open",
        lambda url: opened.append(url),
    )
    monkeypatch.setenv("HEADLESS", "1")
    show = SyncedSlideShow(tmp_path)
    try:
        url = show.start(open_browser=True)
        assert url.startswith("http://127.0.0.1:")
        assert opened == []
    finally:
        show.stop()


def test_slideshow_start_opens_browser_when_not_headless(monkeypatch, tmp_path):
    opened: list[str] = []
    monkeypatch.setattr(
        "aoep_shared.meeting.presentation_sync.webbrowser.open",
        lambda url: opened.append(url),
    )
    monkeypatch.delenv("HEADLESS", raising=False)
    show = SyncedSlideShow(tmp_path)
    try:
        url = show.start(open_browser=True)
        assert opened == [url]
    finally:
        show.stop()
