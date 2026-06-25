"""Tests for subject-aware course poster URLs."""

from aoep_shared.course_artwork import resolve_course_poster, resolve_course_poster_from_mapping


def test_explicit_thumbnail_passthrough():
    url = "https://cdn.example.com/bio.jpg"
    assert resolve_course_poster(title="Biology", thumbnail=url) == url


def test_stale_unsplash_thumbnail_is_recomputed():
    old = "https://images.unsplash.com/photo-1416879595882-ce2fa732bc2c?w=480"
    poster = resolve_course_poster(title="Intro to Photosynthesis", thumbnail=old)
    assert poster != old
    assert "1542601906990-b4d3fb778b09" in poster


def test_title_keyword_photosynthesis():
    poster = resolve_course_poster(title="Intro to Photosynthesis", category="Science & Nature")
    assert "unsplash.com" in poster
    assert "1542601906990-b4d3fb778b09" in poster


def test_title_keyword_python():
    poster = resolve_course_poster(title="Python - Chapter 10: Modules", category="Technology")
    assert "1526374965328" in poster


def test_audio_format_fallback():
    poster = resolve_course_poster(
        title="Morning mindfulness audio", category="General", format="audio",
    )
    assert "1493225457124" in poster


def test_category_mathematics():
    poster = resolve_course_poster(title="Number sense", category="Mathematics", subject="math")
    assert "1532012197267" in poster


def test_mapping_wrapper():
    poster = resolve_course_poster_from_mapping({
        "title": "Intro to Fractions",
        "category": "Mathematics",
        "subject": "Mathematics",
        "tags": [],
        "format": "live_class",
    })
    assert "1554475901" in poster


def test_home_rail_dict_includes_thumbnail():
    from aoep_shared.learnable import build_learnable_index, learnable_home_rails

    rails = learnable_home_rails(build_learnable_index(), per_rail=3)
    assert rails
    course = rails[0]["courses"][0]
    assert course.get("thumbnail", "").startswith("https://images.unsplash.com/")
