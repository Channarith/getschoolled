"""Multi-source extractors: text, database (sqlite), dispatch + file inference."""

import sqlite3

import pytest

from aoep_shared.harvest import (
    SUPPORTED_SOURCE_TYPES,
    extract,
    extract_database,
    extract_text,
)


def test_extract_text_splits_sections():
    text = (
        "Introduction\n"
        "Welcome to the class. We will learn algebra.\n\n"
        "History\n"
        "Algebra has ancient roots in Babylon.\n"
    )
    doc = extract_text(text, default_title="Algebra 101")
    headings = [h for h, _ in doc.sections]
    assert "Introduction" in headings
    assert "History" in headings
    assert doc.source_type == "text"


def test_extract_database_from_sqlite(tmp_path):
    db = tmp_path / "lessons.db"
    conn = sqlite3.connect(db)
    conn.execute("CREATE TABLE lessons (topic TEXT, body TEXT)")
    conn.executemany(
        "INSERT INTO lessons VALUES (?, ?)",
        [("Cells", "The cell is the basic unit of life."),
         ("Genetics", "DNA carries genetic information.")],
    )
    conn.commit()
    conn.close()

    doc = extract_database(db_path=str(db), query="SELECT topic, body FROM lessons",
                           heading_column="topic", title="Biology")
    assert doc.title == "Biology"
    headings = [h for h, _ in doc.sections]
    assert headings == ["Cells", "Genetics"]
    assert "basic unit of life" in doc.sections[0][1]


def test_extract_dispatch_and_supported_types():
    assert "database" in SUPPORTED_SOURCE_TYPES
    doc = extract("text", "Overview\nThis is a quick overview of the topic.")
    assert doc.nonempty_sections()
    with pytest.raises(ValueError):
        extract("bogus", "x")
