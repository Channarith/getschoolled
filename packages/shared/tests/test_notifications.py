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
