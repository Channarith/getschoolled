"""Content scraper tests: PDF / HTML / transcript -> decks."""

import pytest
from fastapi.testclient import TestClient

from curriculum.ingest import (
    ClassFormat,
    TranscriptSegment,
    extract_html,
    extract_pdf,
    extract_transcript,
    sections_to_deck,
)
from curriculum.main import app

client = TestClient(app)

HTML = """
<html><head><title>Intro to Cells</title></head>
<body>
  <h1>Intro to Cells</h1>
  <h2>The Cell Membrane</h2>
  <p>The cell membrane controls what enters and leaves the cell. It is selectively permeable.</p>
  <h2>The Nucleus</h2>
  <p>The nucleus stores the cell's DNA and directs its activities.</p>
  <script>ignore()</script>
</body></html>
"""


def _make_pdf(lines: list[str]) -> bytes:
    # fpdf2 (provides the `fpdf` module) is a test-only dependency declared in the
    # package's [test] extra; skip cleanly if it isn't installed so the PDF
    # fixtures never error the suite.
    fpdf = pytest.importorskip("fpdf")
    FPDF = fpdf.FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    for line in lines:
        pdf.multi_cell(190, 8, line)
    out = pdf.output()
    return bytes(out)


def test_extract_html_into_sections():
    result = extract_html(HTML)
    assert result.title == "Intro to Cells"
    headings = [s.heading for s in result.sections]
    assert "The Cell Membrane" in headings
    assert "The Nucleus" in headings
    assert any("selectively permeable" in s.text for s in result.sections)


def test_html_to_deck():
    deck = sections_to_deck(extract_html(HTML), fmt=ClassFormat.ARTICLE, source="t")
    assert deck.title == "Intro to Cells"
    assert deck.format == "article"
    assert len(deck.slides) >= 2
    assert deck.slides[0].narration  # condensed narration present


def test_extract_pdf():
    data = _make_pdf([
        "Chapter 1",
        "Photosynthesis converts light energy into chemical energy stored in sugars.",
        "Chapter 2",
        "Cellular respiration releases energy from glucose for the cell to use.",
    ])
    result = extract_pdf(data, default_title="Bio")
    headings = " ".join(s.heading for s in result.sections)
    assert "Chapter 1" in headings or "Chapter 2" in headings
    assert any("Photosynthesis" in s.text or "respiration" in s.text for s in result.sections)


def test_transcript_to_deck_windows():
    segs = [TranscriptSegment(start=float(i * 20), text=f"point {i}") for i in range(8)]
    result = extract_transcript(segs, title="Lesson", window_seconds=60)
    # 8 segments * 20s = 160s -> ~3 windows
    assert len(result.sections) >= 2
    deck = sections_to_deck(result, fmt=ClassFormat.VIDEO)
    assert deck.format == "video"


def test_hands_on_format_adds_practice_prompt():
    result = extract_html(HTML)
    deck = sections_to_deck(result, fmt=ClassFormat.HANDS_ON)
    assert any("Try it" in s.body for s in deck.slides)


# --- API ---
def test_ingest_html_api_stores_deck():
    r = client.post("/ingest/html", json={"html": HTML, "title": "Cells", "fmt": "article"})
    assert r.status_code == 200, r.text
    deck = r.json()
    assert deck["format"] == "article" and len(deck["slides"]) >= 2
    # Stored in the CMS and presentable.
    assert client.get(f"/decks/{deck['deck_id']}").status_code == 200
    pres = client.get(f"/decks/{deck['deck_id']}/presentation").json()
    assert pres["slides"][0]["index"] == 0


def test_ingest_pdf_api():
    data = _make_pdf([
        "Section One",
        "Fractions represent parts of a whole and have a numerator and denominator.",
    ])
    r = client.post(
        "/ingest/pdf",
        files={"file": ("math.pdf", data, "application/pdf")},
        data={"title": "Math", "fmt": "lecture"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["source"] == "math.pdf"


def test_ingest_transcript_api():
    r = client.post(
        "/ingest/transcript",
        json={"title": "Talk", "segments": [
            {"start": 0, "text": "welcome"}, {"start": 70, "text": "next topic"}]},
    )
    assert r.status_code == 200, r.text
    assert r.json()["format"] == "video"


def test_unknown_format_rejected():
    r = client.post("/ingest/html", json={"html": HTML, "fmt": "bogus"})
    assert r.status_code == 422
