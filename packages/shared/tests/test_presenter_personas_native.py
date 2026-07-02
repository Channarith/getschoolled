"""Presenter personas and native slide rendering."""

from pathlib import Path

import pytest

from aoep_shared.meeting.native_slides import page_for_step, prepare_native_slides
from aoep_shared.meeting.presentation_sync import write_slide_deck_html
from aoep_shared.meeting.presenter_personas import list_presenter_personas, resolve_persona
from aoep_shared.meeting.base import PresentationPlan, PresentationStep


def test_list_personas_nonempty():
    rows = list_presenter_personas()
    assert len(rows) >= 5
    assert rows[0]["id"]


def test_resolve_persona_by_id():
    p = resolve_persona("davis")
    assert p is not None
    assert p.present_mode == "lewin"
    assert "Neural" in p.voice


def test_resolve_persona_unknown():
    with pytest.raises(ValueError):
        resolve_persona("not_a_real_persona")


def test_page_for_step_clamps():
    assert page_for_step(0, 5) == 0
    assert page_for_step(99, 5) == 4


def test_native_deck_html_includes_image(tmp_path):
    pages_dir = tmp_path / "pages"
    pages_dir.mkdir()
    png = pages_dir / "page-001.png"
    png.write_bytes(b"\x89PNG\r\n\x1a\n")
    plan = PresentationPlan(
        title="Demo",
        steps=[
            PresentationStep(
                order=0,
                kind="segment",
                heading="Slide 1",
                narration="Hello",
                on_screen_points=["a"],
                est_seconds=5,
                slide_index=0,
            ),
        ],
    )
    html_path = write_slide_deck_html(
        plan,
        out_path=tmp_path / "slide_deck.html",
        course_title="Demo",
        native_pages=[png],
    )
    text = html_path.read_text(encoding="utf-8")
    assert "page-001.png" in text
    assert "slide-img" in text


@pytest.mark.skipif(
    not __import__("importlib").util.find_spec("fitz"),
    reason="pymupdf not installed",
)
def test_prepare_native_slides_pdf(tmp_path):
    import fitz

    pdf = tmp_path / "tiny.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "Hello physics")
    doc.save(str(pdf))
    doc.close()
    pages = prepare_native_slides(pdf, tmp_path / "show")
    assert len(pages) == 1
    assert pages[0].is_file()
