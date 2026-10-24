"""Drive Mode lessons adapted from Wikipedia carry the CC BY-SA credit; our own authored text does not."""
from aoep_shared import drive_topic_harvest as mod


def use_tmp_db(monkeypatch, tmp_path):
    db_path = tmp_path / "drive.db"
    monkeypatch.setattr(mod, "_DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(mod._db, "__defaults__", (db_path,))
    return db_path


def test_wikipedia_attribution_names_the_article_and_the_license():
    a = mod.wikipedia_attribution("Ancient Egypt")
    assert a["source_url"] == "https://en.wikipedia.org/wiki/Ancient_Egypt"
    assert a["license"] == "CC BY-SA 4.0" and "creativecommons.org/licenses/by-sa/4.0" in a["license_url"]
    assert "Wikipedia" in a["attribution"] and "same license" in a["attribution"] and "contributors" in a["attribution"]


def test_cached_source_marker_and_legacy_rows(monkeypatch, tmp_path):
    use_tmp_db(monkeypatch, tmp_path)
    segs = [("A", "text " * 40)] * 3
    mod.save_segments("Topic W", segs, source="wikipedia")
    mod.save_segments("Topic Own", segs, source="authored")
    assert mod.get_cached_source("Topic W") == "wikipedia"
    assert mod.get_cached_source("Topic Own") == "authored"
    con = mod._db()
    con.execute("INSERT INTO drive_segments (topic,version,created_at,segments_json,word_count) VALUES ('Legacy',1,'x','[]',0)")
    con.commit()
    assert mod.get_cached_source("Legacy") == "wikipedia"          # unknown provenance is credited, not hidden
    assert mod.get_cached_source("Never cached") == "wikipedia"


def test_harvest_topic_marks_authored_fallback_and_wikipedia_text(monkeypatch, tmp_path):
    use_tmp_db(monkeypatch, tmp_path)
    body = [(f"Heading {i}", "word " * 130) for i in range(40)]
    monkeypatch.setattr(mod, "fetch_wikipedia_sections", lambda topic: body)
    monkeypatch.setattr(mod, "TOPIC_SECTIONS", {"Own Topic": body, "Wiki Topic": body})
    mod.harvest_topic("Wiki Topic", force=True)
    assert mod.get_cached_source("Wiki Topic") == "wikipedia"
    monkeypatch.setattr(mod, "fetch_wikipedia_sections", lambda topic: [])
    mod.harvest_topic("Own Topic", force=True)
    assert mod.get_cached_source("Own Topic") == "authored"


def test_audio_course_credits_wikipedia_text_only(monkeypatch, tmp_path):
    from aoep_shared import audio_courses
    use_tmp_db(monkeypatch, tmp_path)
    body = [(f"Heading {i}", "word " * 130) for i in range(40)]
    monkeypatch.setattr(mod, "TOPIC_SECTIONS", {"Wiki Topic": body, "Own Topic": body})
    mod.save_segments("Wiki Topic", body, source="wikipedia")
    mod.save_segments("Own Topic", body, source="authored")
    monkeypatch.setattr(audio_courses, "TOPIC_SECTIONS", {"Wiki Topic": body, "Own Topic": body}, raising=False)
    wiki = audio_courses._knowledge_course("History", "Wiki Topic", "en", "en")
    own = audio_courses._knowledge_course("History", "Own Topic", "en", "en")
    assert wiki is not None and own is not None
    assert wiki.license == "CC BY-SA 4.0" and "Wikipedia" in wiki.attribution and wiki.source_url.endswith("Wiki_Topic")
    assert own.attribution == "" and own.license == ""
