"""Redis URL: local compose hostname bypass, Vultr password injection."""

from aoep_shared.redis_url import authenticated_redis_url, runtime_redis_url


def test_password_is_added_when_the_url_has_none(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "cluster-secret")
    assert (
        authenticated_redis_url("redis://redis.aoep.svc.cluster.local:6379/0")
        == "redis://:cluster-secret@redis.aoep.svc.cluster.local:6379/0"
    )


def test_password_is_quoted(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "p@ss/word")
    assert (
        authenticated_redis_url("redis://redis.aoep.svc.cluster.local:6379/0")
        == "redis://:p%40ss%2Fword@redis.aoep.svc.cluster.local:6379/0"
    )


def test_existing_password_is_left_alone(monkeypatch):
    monkeypatch.setenv("REDIS_PASSWORD", "other")
    url = "redis://:already@redis.aoep.svc.cluster.local:6379/0"
    assert authenticated_redis_url(url) == url


def test_local_unresolvable_compose_host_is_skipped(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setattr("aoep_shared.redis_url._redis_importable", lambda: True)

    def _unresolved(*_args, **_kwargs):
        raise OSError("nodename nor servname provided, or not known")

    monkeypatch.setattr("aoep_shared.redis_url.socket.getaddrinfo", _unresolved)
    assert runtime_redis_url() == ""


def test_local_compose_host_without_redis_package_is_skipped(monkeypatch):
    """The laptop venv has REDIS_URL set and no redis package. That must not 503."""
    monkeypatch.setenv("DEPLOY_MODE", "local")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setattr("aoep_shared.redis_url._redis_importable", lambda: False)
    assert runtime_redis_url() == ""


def test_cloud_unresolvable_host_stays_configured(monkeypatch):
    monkeypatch.setenv("DEPLOY_MODE", "cloud")
    monkeypatch.setenv("REDIS_URL", "redis://redis:6379/0")
    monkeypatch.setenv("REDIS_PASSWORD", "cluster-secret")

    def _unresolved(*_args, **_kwargs):
        raise OSError("down")

    monkeypatch.setattr("aoep_shared.redis_url.socket.getaddrinfo", _unresolved)
    assert runtime_redis_url() == "redis://:cluster-secret@redis:6379/0"


def test_hyphenated_secret_env_is_accepted(monkeypatch):
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    monkeypatch.setenv("redis-password", "from-secret")
    assert (
        authenticated_redis_url("redis://redis.aoep.svc.cluster.local:6379/0")
        == "redis://:from-secret@redis.aoep.svc.cluster.local:6379/0"
    )
    monkeypatch.delenv("redis-password", raising=False)


def test_blank_url_stays_blank(monkeypatch):
    monkeypatch.delenv("REDIS_URL", raising=False)
    monkeypatch.delenv("REDIS_PASSWORD", raising=False)
    assert runtime_redis_url() == ""
