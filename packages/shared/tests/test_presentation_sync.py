"""Synced slide deck HTML generation."""

from aoep_shared.meeting.base import PresentationPlan, PresentationStep
from aoep_shared.meeting.presentation_sync import write_slide_deck_html


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
