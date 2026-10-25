import pytest

pytest.importorskip("fastapi")


def test_paid_engine_budget_is_per_address_and_falls_over_not_errors(monkeypatch):
    from speech_gw import main as m

    monkeypatch.setenv("AOEP_PAID_TTS_CHARS_PER_MIN", "1000")
    monkeypatch.setenv("RATE_LIMIT_BACKEND", "memory")
    from aoep_shared.ratelimit import InMemoryTokenBucket, RateLimit

    m.app.state.rate_limiter = InMemoryTokenBucket(RateLimit(120, 60))
    assert m._paid_tts_allowed("203.0.113.9", 600) is True
    assert m._paid_tts_allowed("203.0.113.9", 600) is False          # over the minute's 1000 characters
    assert m._paid_tts_allowed("198.51.100.7", 600) is True          # another address has its own budget


def test_one_huge_request_cannot_exceed_the_budget_for_free(monkeypatch):
    from speech_gw import main as m
    from aoep_shared.ratelimit import InMemoryTokenBucket, RateLimit

    monkeypatch.setenv("AOEP_PAID_TTS_CHARS_PER_MIN", "1000")
    m.app.state.rate_limiter = InMemoryTokenBucket(RateLimit(120, 60))
    assert m._paid_tts_allowed("203.0.113.9", 5000) is True          # charged at most the whole budget
    assert m._paid_tts_allowed("203.0.113.9", 10) is False


def test_budget_can_be_switched_off(monkeypatch):
    from speech_gw import main as m

    monkeypatch.setenv("AOEP_PAID_TTS_CHARS_PER_MIN", "0")
    assert m._paid_tts_allowed("203.0.113.9", 5000) is True
