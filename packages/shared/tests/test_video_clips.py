"""Lesson clip references stay metadata; missing sources become a title card."""

from pathlib import Path

from aoep_shared.video_clips import (
    apply_lesson_clips,
    build_lesson_clips,
    render_title_card,
)

_VIDEO_SUFFIXES = {".mp4", ".webm", ".mkv", ".m4v", ".mov", ".gif"}


def _files(root: Path) -> list[Path]:
    if not root.exists():
        return []
    return [path for path in root.rglob("*") if path.is_file()]


def test_youtube_reference_is_metadata_not_a_downloaded_file(tmp_path):
    out = tmp_path / "out"
    built = build_lesson_clips(
        topic="Fractions",
        language="en",
        duration_sec=30,
        source_url="https://www.youtube.com/watch?v=abcdefghijk&t=12",
        out_dir=out,
        repo_root=None,
    )
    clip = built["clips"][0]
    assert clip["source"] == "youtube"
    assert clip["title"] == "Fractions"
    assert clip["duration"] == 30
    assert clip["play"]["video_id"] == "abcdefghijk"
    assert clip["play"]["start_sec"] == 12
    assert clip["play"]["end_sec"] == 42
    assert clip["play"]["source_url"] == "https://www.youtube.com/watch?v=abcdefghijk&t=12"
    assert clip["play"]["embed_url"].startswith("https://www.youtube.com/embed/abcdefghijk?")
    assert "start=12" in clip["play"]["embed_url"]
    assert "end=42" in clip["play"]["embed_url"]
    assert clip["play"]["path"] == ""
    assert built["trailer_url"] == clip["how"]
    assert _files(out) == []
    assert not any(path.suffix.lower() in _VIDEO_SUFFIXES for path in _files(tmp_path))


def test_online_reference_is_metadata_not_a_downloaded_file(tmp_path):
    out = tmp_path / "out"
    built = build_lesson_clips(
        topic="Cells",
        language="en",
        duration_sec=20,
        source_url="https://vimeo.com/123456789",
        out_dir=out,
        repo_root=None,
    )
    clip = built["clips"][0]
    assert clip["source"] == "online"
    assert clip["play"]["video_id"] == "123456789"
    assert clip["play"]["source_url"] == "https://vimeo.com/123456789"
    assert clip["how"].startswith("https://player.vimeo.com/video/123456789")
    assert clip["play"]["path"] == ""
    assert _files(out) == []


def test_catalog_reference_matches_topic_without_downloading(tmp_path):
    out = tmp_path / "out"
    built = build_lesson_clips(
        topic="Understanding fractions",
        language="en",
        duration_sec=30,
        references=[{
            "title": "Intro fractions",
            "url": "https://youtu.be/abcdefghijk",
            "topics": ["fraction"],
            "language": "en",
        }],
        out_dir=out,
        repo_root=None,
    )
    clip = built["clips"][0]
    assert clip["source"] == "youtube"
    assert clip["title"] == "Intro fractions"
    assert clip["play"]["video_id"] == "abcdefghijk"
    assert _files(out) == []


def test_missing_source_falls_back_to_generated_clip(tmp_path):
    out = tmp_path / "out"
    built = build_lesson_clips(
        topic="Photosynthesis",
        language="es",
        duration_sec=15,
        source_url="https://evil.example/video.mp4",
        out_dir=out,
        repo_root=tmp_path,
    )
    clip = built["clips"][0]
    assert clip["source"] == "generated"
    assert clip["title"] == "Photosynthesis"
    assert clip["duration"] == 15
    assert clip["play"]["svg"].startswith("<svg")
    assert "Photosynthesis" in clip["play"]["svg"]
    assert clip["play"]["path"]
    written = Path(clip["play"]["path"])
    assert written.is_file()
    assert written.suffix == ".svg"
    assert written.read_text(encoding="utf-8") == clip["play"]["svg"]
    assert built["trailer_url"].startswith("data:image/svg+xml")
    assert not any(path.suffix.lower() in _VIDEO_SUFFIXES for path in _files(out))


def test_harvest_demo_is_referenced_not_copied(tmp_path):
    demo = tmp_path / "docs" / "demos" / "sample_demo_class_walkthrough.gif"
    demo.parent.mkdir(parents=True)
    demo.write_bytes(b"GIF89a-existing")
    out = tmp_path / "out"
    built = build_lesson_clips(
        topic="algebra",
        language="en",
        duration_sec=30,
        out_dir=out,
        repo_root=tmp_path,
    )
    reused = [clip for clip in built["clips"] if clip["play"].get("reused")]
    assert len(reused) == 1
    assert reused[0]["play"]["url"].endswith("sample_demo_class_walkthrough.gif")
    assert Path(reused[0]["play"]["path"]) == demo
    assert not any(path.suffix.lower() == ".gif" for path in _files(out))
    assert built["clips"][0]["source"] == "generated"
    assert built["trailer_url"].startswith("data:image/svg+xml")


def test_clip_list_shape_includes_source_title_duration():
    built = build_lesson_clips(
        topic="Water cycle",
        language="en",
        duration_sec=45,
        repo_root=None,
    )
    assert built["media_format"] == "video"
    assert built["clips"]
    for clip in built["clips"]:
        assert clip["source"] in {"youtube", "online", "generated"}
        assert isinstance(clip["title"], str) and clip["title"]
        assert isinstance(clip["duration"], int)
        assert 15 <= clip["duration"] <= 60
        assert clip["how"]
        assert clip["play"]["url"]


def test_duration_is_clamped_to_short_window():
    short = build_lesson_clips(topic="Short", duration_sec=5, repo_root=None)
    long = build_lesson_clips(topic="Long", duration_sec=180, repo_root=None)
    assert short["clips"][0]["duration"] == 15
    assert long["clips"][0]["duration"] == 60


def test_title_card_is_deterministic():
    first = render_title_card("Water cycle", "en", 30)
    second = render_title_card("Water cycle", "en", 30)
    assert first == second
    assert "animate" in first


def test_apply_points_course_and_slide_at_reference_not_a_file():
    built = build_lesson_clips(
        topic="Cells",
        source_url="abcdefghijk",
        duration_sec=30,
        repo_root=None,
    )
    course = {
        "title": "Cells",
        "media_format": "text",
        "slides": [{"title": "Look", "body": "See", "media_url": ""}, {"title": "Next"}],
    }
    patched = apply_lesson_clips(course, built)
    assert patched["media_format"] == "video"
    assert patched["trailer_url"].startswith("https://www.youtube.com/embed/abcdefghijk?")
    assert patched["slides"][0]["media_url"] == patched["trailer_url"]
    assert patched["slides"][0]["media_kind"] == "video"
    assert "media_url" not in patched["slides"][1]
    assert course["slides"][0]["media_url"] == ""
