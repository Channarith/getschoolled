"""Drop links, media, and databases into the shared training intake."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from aoep_shared.training_intake import drop_training, host_is_public, train_dropped


def test_links_split_across_voice_and_resources(tmp_path: Path):
    report = drop_training(
        links=[
            "https://www.youtube.com/watch?v=abcdefghijk",
            "https://vimeo.com/123456789",
            "https://example.com/news/story",
            "http://127.0.0.1/secret",
        ],
        language="es",
        expand_limit=0,
        fetch_pages=False,
        root=tmp_path,
        expand=lambda url, limit: [],
    )
    voice = (tmp_path / "voice" / "urls.txt").read_text(encoding="utf-8")
    assert "youtube.com/watch?v=abcdefghijk" in voice
    assert "vimeo.com/123456789" in voice
    resources = (tmp_path / "resources" / "links.txt").read_text(encoding="utf-8")
    assert "https://example.com/news/story" in resources
    assert "http://127.0.0.1/secret" in resources
    secret = next(path for path in (tmp_path / "rag").glob("*.txt") if "127.0.0.1" in path.read_text())
    assert "secret" in secret.read_text(encoding="utf-8")
    local = drop_training(
        links=["http://127.0.0.1/secret"],
        fetch_pages=True,
        expand_limit=0,
        root=tmp_path / "local",
    )
    assert local["accepted"][0]["fetched"] is False
    assert report["language"] == "es"
    assert report["voice_urls"] == 2
    assert report["resource_links"] == 2
    assert not host_is_public("127.0.0.1")
    assert not host_is_public("localhost")


def test_channel_drop_stores_expanded_videos(tmp_path: Path):
    def expand(url: str, limit: int) -> list[str]:
        assert "/videos" in url
        assert limit == 2
        return [
            "https://www.youtube.com/watch?v=aaaabbbbccc",
            "https://www.youtube.com/watch?v=ddddeeeefff",
        ]

    report = drop_training(
        links=["@ExampleChannel"],
        expand_limit=2,
        root=tmp_path,
        expand=expand,
    )
    text = (tmp_path / "voice" / "urls.txt").read_text(encoding="utf-8")
    assert "aaaabbbbccc" in text
    assert "ddddeeeefff" in text
    assert report["accepted"][0]["expanded"] is True
    assert report["accepted"][0]["videos"] == 2


def test_files_notes_media_and_sqlite(tmp_path: Path):
    db_path = tmp_path / "source.sqlite"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE lessons (title TEXT, transcript TEXT, url TEXT)")
    conn.execute(
        "INSERT INTO lessons VALUES (?, ?, ?)",
        ("Cats", "The cat sat on the mat for a long time.", "https://vimeo.com/999"),
    )
    conn.commit()
    conn.close()
    qa = [{"question": "What is a fraction?", "answer": "Part of a whole.", "language": "en"}]
    report = drop_training(
        files=[
            ("notes.txt", b"Plants make food from sunlight."),
            ("clip.wav", b"RIFFdemo"),
            ("urls.txt", b"https://www.youtube.com/watch?v=zzzzzzzzzzz\n"),
            ("qa.json", json.dumps(qa).encode()),
            ("source.sqlite", db_path.read_bytes()),
        ],
        expand_limit=0,
        root=tmp_path / "intake",
    )
    base = tmp_path / "intake"
    assert (base / "voice" / "media" / "clip.wav").is_file()
    assert "zzzzzzzzzzz" in (base / "voice" / "urls.txt").read_text(encoding="utf-8")
    assert "vimeo.com/999" in (base / "voice" / "urls.txt").read_text(encoding="utf-8")
    rag = "\n".join(path.read_text(encoding="utf-8") for path in (base / "rag").glob("*.txt"))
    assert "Plants make food" in rag
    assert "cat sat on the mat" in rag
    llm = (base / "llm" / "dropped_rag.jsonl").read_text(encoding="utf-8")
    assert "What is a fraction?" in llm
    kinds = {row["kind"] for row in report["accepted"]}
    assert {"rag_text", "media", "voice_url", "table"} <= kinds


def test_train_dropped_uses_only_the_intake(tmp_path: Path):
    drop_training(
        links=["https://www.youtube.com/watch?v=abcdefghijk"],
        root=tmp_path,
        expand_limit=0,
    )
    calls = []

    class Report:
        def __init__(self):
            self.ok = True

        def to_dict(self):
            return {"ok": True, "utterances": 1}

    def fake(config):
        calls.append(config)
        return Report()

    trained = train_dropped(root=tmp_path, max_urls=1, run_ingest=fake)
    assert trained["ok"] is True
    assert calls[0].urls_file == tmp_path / "voice" / "urls.txt"
    assert calls[0].max_urls == 1
