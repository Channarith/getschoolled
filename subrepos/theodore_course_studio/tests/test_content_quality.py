from __future__ import annotations

from theodore_course_studio.content_quality import (
    PageKind,
    analyze_document,
    classify_page,
    clean_text,
    derive_title,
    detect_boilerplate,
    similarity,
)
from theodore_course_studio.generate import _narration_for

COVER = "SEXUAL HARASSMENT\nPREVENTION TRAINING\nOffice of Human Resources\nRevised January 2024\n1"
TOC = (
    "Table of Contents\nIntroduction ......... 3\nDefinitions .......... 5\n"
    "Reporting ............ 9\nAppendix A ........... 21\n2"
)
REFS = (
    "References\n1. 29 C.F.R. 1604.11 (2023).\n"
    "2. Meritor Savings Bank v. Vinson, 477 U.S. 57 (1986).\n"
    "3. EEOC Compliance Manual, Sec. 615.\n21"
)
REAL = (
    "Office of Human Resources | Policy 4.12 | Page 7\nReporting options\n"
    "An employee may report concerns to a supervisor, to Human Resources, or through "
    "the anonymous hotline. Retaliation against a reporter is prohibited and is itself "
    "a violation of this policy.\nRevised January 2024"
)


def test_cover_toc_and_references_are_not_teachable():
    for text in (COVER, TOC, REFS):
        kind, reason = classify_page(text.splitlines()[0], text)
        assert kind is not PageKind.CONTENT, f"should reject: {text[:40]}"
        assert reason, "rejection needs a human-readable reason"


def test_real_policy_page_is_teachable():
    kind, _ = classify_page("Reporting options", REAL)
    assert kind is PageKind.CONTENT


def test_repeated_footer_detected_as_boilerplate():
    pages = [COVER, REAL, REAL.replace("Page 7", "Page 8")]
    assert "Revised January 2024" in detect_boilerplate(pages)


def test_clean_text_strips_running_headers_and_page_numbers():
    cleaned, removed = clean_text(REAL, {"Revised January 2024"})
    assert "Policy 4.12" not in cleaned  # running header gone
    assert "Revised January 2024" not in cleaned  # footer gone
    assert "anonymous hotline" in cleaned  # teaching content kept
    assert removed >= 2


def test_clean_text_repairs_hyphenated_line_breaks():
    cleaned, _ = clean_text("a condition of employ-\nment applies here.")
    assert "employment" in cleaned


def test_derive_title_prefers_heading_over_running_header():
    cleaned, _ = clean_text(REAL, {"Revised January 2024"})
    assert derive_title(cleaned, fallback="fallback") == "Reporting options"


def test_derive_title_summarizes_when_no_heading():
    body = (
        "Quid pro quo harassment occurs when submission to unwelcome conduct is made "
        "a condition of employment."
    )
    title = derive_title(body, fallback="Office of Human Resources | Page 5")
    assert "|" not in title
    assert title.lower().startswith("quid pro quo")


def test_analyze_document_keeps_only_teaching_pages():
    analysis = analyze_document(
        [
            (0, "SEXUAL HARASSMENT", COVER),
            (1, "Table of Contents", TOC),
            (2, "Reporting options", REAL),
            (3, "References", REFS),
        ]
    )
    teachable = analysis.teachable_pages
    assert len(teachable) == 1
    assert teachable[0].title == "Reporting options"


def test_similarity_flags_near_duplicates():
    assert similarity(REAL, REAL) > 0.95
    assert similarity(REAL, TOC) < 0.3


def test_narration_does_not_repeat_the_title():
    narration = _narration_for("Quid pro quo", "Quid pro quo\nQuid pro quo harassment occurs when x.")
    assert narration.lower().count("quid pro quo") == 2  # title + the definition, not 3
