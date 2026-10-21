"""Build the Redis URL each process should actually dial.

Local ``config/local.env`` points at the compose service name ``redis``. On a
laptop that name does not answer (no resolver, no ``redis`` package, or only
Docker's stub DNS), and leaving it set makes the free plan return 503. Native
local/dev mode skips that hostname unless a ping succeeds, and keeps seats
in-process.

Vultr Redis (``infra/k8s/redis.yaml``) is started with ``--requirepass``. The
password lives in the ``aoep-secrets`` key ``redis-password`` (also copied to
``REDIS_PASSWORD``) and must not be written into the ConfigMap. Cloud and any
URL whose host is not the compose name keep the configured URL, with the
password added when the URL does not already have one.
"""

from __future__ import annotations

import logging
import os
import socket
from urllib.parse import quote, urlparse, urlunparse

logger = logging.getLogger(__name__)

_LOCAL_MODES = {"local", "dev", "development", "test", "debug"}
_logged_unresolved: set[str] = set()


def redis_password() -> str:
    """Password from the secret, under either env name pods actually receive."""
    for key in ("REDIS_PASSWORD", "redis-password"):
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


def _without_password(url: str) -> str:
    parts = urlparse(url)
    if not parts.password and not parts.username:
        return url
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    return urlunparse((parts.scheme, f"{host}{port}", parts.path, "", parts.query, parts.fragment))


# A stuck Redis command must fail the request. With no socket timeout, redis-py
# blocks until the gateway returns 504 (signup and onboarding hit this).
_DEFAULT_SOCKET_TIMEOUT_S = 2.0


def open_redis(url: str, **kwargs):
    """Connect and ping. If Redis has no password yet, retry without AUTH.

    Vultr manifests set ``--requirepass``, but a cluster whose StatefulSet did
    not roll still answers without one. Sending AUTH there fails the free-plan
    seat lock. A wrong password still fails closed.
    """
    import redis

    kwargs.setdefault("socket_connect_timeout", _DEFAULT_SOCKET_TIMEOUT_S)
    kwargs.setdefault("socket_timeout", _DEFAULT_SOCKET_TIMEOUT_S)
    client = redis.from_url(url, **kwargs)
    try:
        client.ping()
        return client
    except Exception as exc:
        text = str(exc).lower()
        bare = _without_password(url)
        if "without any password" not in text or bare == url:
            raise
        logger.warning("Redis has no password configured; connecting without AUTH")
        client = redis.from_url(bare, **kwargs)
        client.ping()
        return client


def authenticated_redis_url(url: str | None = None) -> str:
    """Return ``url`` with ``REDIS_PASSWORD`` applied when the URL has none."""
    raw = (url if url is not None else os.environ.get("REDIS_URL", "")).strip()
    password = redis_password()
    if not raw or not password:
        return raw
    parts = urlparse(raw)
    if parts.password:
        return raw
    host = parts.hostname or ""
    port = f":{parts.port}" if parts.port else ""
    user = quote(parts.username or "", safe="")
    auth = f"{user}:{quote(password, safe='')}"
    netloc = f"{auth}@{host}{port}"
    return urlunparse((parts.scheme, netloc, parts.path, "", parts.query, parts.fragment))


def _local_mode() -> bool:
    mode = os.environ.get("DEPLOY_MODE", "local").strip().lower()
    return mode in _LOCAL_MODES


def _redis_importable() -> bool:
    try:
        import redis  # type: ignore[import-not-found]  # noqa: F401
    except ImportError:
        return False
    return True


def _compose_redis_reachable(url: str) -> bool:
    """True only when the compose hostname answers a Redis ping.

    Localhost testing points REDIS_URL at ``redis``, which is the compose
    service name. Docker Desktop can make that name resolve while nothing is
    listening, and the laptop venv often has no ``redis`` package. Either case
    must skip Redis instead of turning the free plan into a 503.
    """
    if not _redis_importable():
        return False
    parts = urlparse(url)
    host = parts.hostname or ""
    port = parts.port or 6379
    try:
        socket.getaddrinfo(host, port, socket.AF_UNSPEC, socket.SOCK_STREAM)
    except OSError:
        return False
    try:
        import redis

        client = redis.from_url(
            authenticated_redis_url(url),
            socket_connect_timeout=0.4,
            socket_timeout=0.4,
        )
        client.ping()
    except Exception:
        return False
    return True


def runtime_redis_url() -> str:
    """URL safe to pass to a Redis client.

    Local/dev/test skips the compose hostname ``redis`` unless it actually
    answers. Cloud keeps the cluster URL, including the Vultr password, so a
    missing Redis fails closed instead of handing out a seat this process
    cannot record.
    """
    url = os.environ.get("REDIS_URL", "").strip()
    if not url:
        return ""
    authed = authenticated_redis_url(url)
    if _local_mode() and (urlparse(url).hostname or "").lower() == "redis":
        if not _compose_redis_reachable(url):
            if url not in _logged_unresolved:
                _logged_unresolved.add(url)
                logger.warning(
                    "REDIS_URL host redis is not usable in local mode; skipping Redis"
                )
            return ""
    return authed
