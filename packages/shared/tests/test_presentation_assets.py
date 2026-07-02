"""Rich slide deck asset staging."""

from pathlib import Path

from aoep_shared.meeting.presentation_assets import enrich_course_slides_for_deck, stage_asset


def test_stage_asset_copies_local_file(tmp_path):
    src_dir = tmp_path / "course"
    src_dir.mkdir()
    demo = src_dir / "clip.mp4"
    demo.write_bytes(b"fake-video")
    out = tmp_path / "show"
    rel = stage_asset(
        str(demo),
        assets_dir=out / "assets",
        course_dir=src_dir,
        repo_root=tmp_path,
    )
    assert rel == "assets/clip.mp4"
    assert (out / "assets" / "clip.mp4").is_file()


def test_enrich_adds_wallpaper_and_media(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    demo = repo / "docs" / "demos" / "demo.mp4"
    demo.parent.mkdir(parents=True)
    demo.write_bytes(b"vid")
    slides = [{
        "title": "Concept",
        "body": "Hello",
        "media_url": "docs/demos/demo.mp4",
        "media_kind": "video",
        "category": "concept",
    }]
    theme = {
        "wallpaper_url": "https://images.unsplash.com/photo-test?w=1920",
        "accent_hex": "#6366f1",
        "poster_url": "https://images.unsplash.com/photo-test?w=480",
    }
    out = enrich_course_slides_for_deck(
        slides,
        theme=theme,
        course_dir=tmp_path,
        repo_root=repo,
        out_dir=tmp_path / "deck",
    )
    assert out[0]["wallpaper_url"].startswith("https://")
    assert out[0]["media_url"] == "assets/demo.mp4"
