"""Personalized notification feed."""

from __future__ import annotations

import datetime as dt

from aoep_shared.notifications import NotificationFeed, build_feed


def test_feed_is_chronological_and_deduped():
    feed = build_feed(student_id="x", interests=["spanish"],
                      now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    assert isinstance(feed, NotificationFeed)
    ts = [i.created_at for i in feed.items]
    assert ts == sorted(ts, reverse=True)
    ids = [i.id for i in feed.items]
    assert len(ids) == len(set(ids))


def test_id_is_stable_for_same_inputs():
    a = build_feed(student_id="x", interests=["spanish"],
                   now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    b = build_feed(student_id="x", interests=["spanish"],
                   now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    assert [i.id for i in a.items] == [i.id for i in b.items]


def test_in_progress_emits_continue_items():
    feed = build_feed(in_progress_course_ids=["lang-es-phrases"],
                      now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    cont = [i for i in feed.items if i.kind == "continue"]
    assert len(cont) == 1
    assert cont[0].course_id == "lang-es-phrases"
    assert cont[0].deep_link == "aiclassroom://drive/lang-es-phrases"


def test_streak_only_when_positive():
    no_streak = build_feed(streak_days=0)
    assert all(i.kind != "streak" for i in no_streak.items)
    with_streak = build_feed(streak_days=7)
    assert any(i.kind == "streak" and "7-day" in i.title for i in with_streak.items)


def test_completed_courses_are_filtered_out_of_new():
    completed = ["lang-es-phrases"]
    feed = build_feed(completed_course_ids=completed, interests=["spanish"],
                      now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    assert all(i.course_id != "lang-es-phrases"
               for i in feed.items if i.kind == "new_class")


def test_locale_translates_titles_and_bodies():
    now = dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc)
    es = build_feed(locale="es", in_progress_course_ids=["lang-es-phrases"],
                    streak_days=3, now=now)
    titles = " ".join(i.title for i in es.items)
    bodies = " ".join(i.body for i in es.items)
    assert "Continúa" in titles or "Para ti" in titles or "Nueva clase" in titles
    assert "Tu clase diaria está lista" in titles or "donde" in bodies
    assert "Racha de 3 días" in titles or "tu racha" in bodies.lower() or "3" in titles

    fr = build_feed(locale="fr", streak_days=5, now=now)
    assert any("Série" in i.title or "quotidien" in i.title for i in fr.items)

    ja = build_feed(locale="ja", now=now)
    assert any("クラス" in i.title or "ドライブ" in i.body for i in ja.items)


def test_unknown_locale_falls_back_to_english():
    feed = build_feed(locale="xx", streak_days=2,
                      now=dt.datetime(2026, 6, 19, 12, tzinfo=dt.timezone.utc))
    assert any("Your daily class is ready" in i.title for i in feed.items)
    assert any("2-day streak" in i.title for i in feed.items)


def test_supported_locales_list_is_nonempty():
    from aoep_shared.notifications import SUPPORTED_NOTIFICATION_LOCALES
    assert "en" in SUPPORTED_NOTIFICATION_LOCALES
    assert len(SUPPORTED_NOTIFICATION_LOCALES) >= 10
