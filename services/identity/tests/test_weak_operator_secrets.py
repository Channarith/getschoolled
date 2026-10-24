from identity.bootstrap import weak_operator_secrets


def test_flags_unset_short_and_published_values(monkeypatch):
    monkeypatch.delenv("ADMIN_SECRET", raising=False)
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "88888888")
    assert weak_operator_secrets() == ["ADMIN_SECRET", "DEFAULT_ADMIN_PASSWORD"]


def test_accepts_long_random_values(monkeypatch):
    monkeypatch.setenv("ADMIN_SECRET", "k7Qz-4vLm2Xp9RtYw8Nc")
    monkeypatch.setenv("DEFAULT_ADMIN_PASSWORD", "hD3!rVq8-ZmT5uLx0aE")
    assert weak_operator_secrets() == []
