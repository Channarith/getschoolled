"""Audio courses use only their own lesson; no other topic's text is borrowed."""

from __future__ import annotations

from aoep_shared import audio_courses as audio


def _knowledge():
    return [c for c in audio.build_catalog("en", "en") if not c.id.startswith("lang-")]


def test_no_course_borrows_related_context_from_another_topic():
    for course in _knowledge():
        assert not any("Related context" in s.heading for s in course.segments), course.id


def test_topics_without_a_lesson_are_not_listed_or_served():
    have = {c.id for c in _knowledge()}
    missing = [t for ts in audio._TOPICS.values() for t in ts if not audio.TOPIC_SECTIONS.get(t)]
    assert missing
    slug = lambda t: "audio-" + t.lower().replace(" ", "-").replace(",", "").replace("'", "")  # noqa: E731
    assert not any(slug(t) in have for t in missing[:50])
    assert audio.get_course(slug(missing[0]), locale="en", training_locale="en") is None


def test_listed_courses_show_their_real_length_and_are_not_clones():
    courses = _knowledge()
    assert courses
    texts = [tuple(s.text for s in c.segments[1:-1]) for c in courses]
    assert len(set(texts)) == len(texts)
    for c in courses:
        assert c.duration_min < 30


def test_a_translation_file_from_padded_content_is_not_served(tmp_path, monkeypatch):
    import json

    monkeypatch.setenv("AOEP_COURSE_TRANSLATION_DIR", str(tmp_path))
    course = _knowledge()[0]
    folder = tmp_path / course.id
    folder.mkdir()
    old = [{"heading": "x", "text": "y", "kind": "narration"}] * (len(course.segments) + 40)
    (folder / "fr.json").write_text(json.dumps({"course_id": course.id, "segments": old}))
    served = audio.get_course(course.id, locale="en", training_locale="fr")
    assert served.body_locale == "en" and len(served.segments) == len(course.segments)
