"""Double submit, retry and replay behaviour of the course-pay store (no money moves without the provider saying so)."""
from __future__ import annotations

import threading

from theodore_course_studio.course_pay import CoursePayStore


def _store(tmp_path):
    return CoursePayStore(tmp_path / "pay.json")


def test_replaying_a_confirm_returns_the_same_payment_and_records_once(tmp_path):
    s = _store(tmp_path)
    s.remember(session_id="cs_1", learner_id="acct:a1", course_id="c1", method="card")
    first = s.mark_paid("cs_1")
    again = s.mark_paid("cs_1")
    assert first and again and again["session_id"] == "cs_1" and again["status"] == "paid"
    assert s.is_paid("acct:a1", "c1")
    assert s.pending("cs_1") is None


def test_confirming_an_unknown_session_is_none_and_grants_nothing(tmp_path):
    s = _store(tmp_path)
    assert s.mark_paid("cs_nope") is None
    assert not s.is_paid("acct:a1", "c1")


def test_two_checkouts_for_one_course_only_the_paid_session_grants_access(tmp_path):
    s = _store(tmp_path)
    s.remember(session_id="cs_a", learner_id="acct:a1", course_id="c1", method="card")
    s.remember(session_id="cs_b", learner_id="acct:a1", course_id="c1", method="card")  # double submit past the cache window
    assert not s.is_paid("acct:a1", "c1")
    s.mark_paid("cs_a")
    assert s.is_paid("acct:a1", "c1")
    assert s.pending("cs_b") is not None  # the unpaid duplicate stays pending, never paid


def test_paid_is_per_learner_and_per_course(tmp_path):
    s = _store(tmp_path)
    s.remember(session_id="cs_1", learner_id="acct:a1", course_id="c1", method="card")
    s.mark_paid("cs_1")
    assert not s.is_paid("acct:a2", "c1")
    assert not s.is_paid("acct:a1", "c2")
    assert s.is_paid("acct:a1:audio", "c1")  # the audio-only suffix is the same payer


def test_concurrent_confirms_of_one_session_do_not_corrupt_the_store(tmp_path):
    s = _store(tmp_path)
    s.remember(session_id="cs_1", learner_id="acct:a1", course_id="c1", method="card")
    results, errs = [], []

    def go():
        try:
            results.append(s.mark_paid("cs_1"))
        except Exception as exc:  # noqa: BLE001
            errs.append(exc)

    threads = [threading.Thread(target=go) for _ in range(12)]
    [t.start() for t in threads]
    [t.join() for t in threads]
    assert not errs
    assert all(r and r["status"] == "paid" for r in results)
    assert s.is_paid("acct:a1", "c1")
