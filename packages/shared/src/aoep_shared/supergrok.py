"""SuperGrok subscription chat, with a fall-through when it is not entitled.

SuperGrok is the grok.com subscription, not an API model id. A logged-in Grok
CLI session (or ``SUPERGROK_TOKEN``) talks to the subscription proxy as
``grok-4.7``. Accounts the proxy refuses, and machines with no login, keep
using ``XAI_API_KEY`` on api.x.ai. The token is never included in errors.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from pathlib import Path

SUPERGROK_MODEL = "grok-4.7"
SUPERGROK_PROXY = "https://cli-chat-proxy.grok.com/v1"
_SIGN_IN = "https://accounts.x.ai/sign-in"
_CLIENT_VERSION = "0.2.93"


class SuperGrokUnavailable(RuntimeError):
    """No subscription login, or the proxy refused this account."""

    def __init__(self, message: str, *, status: int = 0) -> None:
        super().__init__(message)
        self.status = status


def subscription_token() -> str:
    """Return a SuperGrok session token, or an empty string."""
    for name in ("SUPERGROK_TOKEN", "XAI_OAUTH_TOKEN"):
        value = os.environ.get(name, "").strip()
        if value:
            return value
    if os.environ.get("AOEP_SUPERGROK", "").strip().lower() in {"0", "off", "false", "api"}:
        return ""
    explicit = os.environ.get("GROK_AUTH_FILE", "").strip()
    # Unit tests must not pick up a developer's real ``~/.grok`` login.
    if os.environ.get("PYTEST_CURRENT_TEST") and not explicit:
        return ""
    path = Path(explicit) if explicit else Path.home() / ".grok" / "auth.json"
    return _token_from_file(path)


def subscription_configured() -> bool:
    return bool(subscription_token())


def subscription_reply(
    messages: list[dict[str, str]],
    *,
    temperature: float = 0.2,
    max_tokens: int = 800,
    timeout_s: float = 25.0,
    model: str = "",
) -> str:
    """One SuperGrok chat completion. Raises when the subscription cannot answer."""
    token = subscription_token()
    if not token:
        raise SuperGrokUnavailable("SuperGrok is not signed in")
    chosen = (
        model.strip()
        or os.environ.get("SUPERGROK_MODEL", "").strip()
        or SUPERGROK_MODEL
    )
    base = os.environ.get("SUPERGROK_BASE_URL", SUPERGROK_PROXY).rstrip("/")
    body = {
        "model": chosen,
        "messages": messages,
        "temperature": temperature,
        "max_tokens": max_tokens,
    }
    version = os.environ.get("XAI_GROK_CLIENT_VERSION", "").strip() or _CLIENT_VERSION
    request = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(body).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {token}",
            "X-XAI-Token-Auth": "xai-grok-cli",
            "x-grok-client-identifier": "grok-shell",
            "x-grok-client-version": version,
        },
        method="POST",
    )
    try:
        with _open(request, timeout_s) as response:
            raw = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = _error_detail(exc)
        raise SuperGrokUnavailable(
            f"SuperGrok HTTP {exc.code}: {detail or exc.reason}",
            status=exc.code,
        ) from exc
    except urllib.error.URLError as exc:
        raise SuperGrokUnavailable(f"SuperGrok unreachable: {exc.reason}") from exc
    try:
        text = str(raw["choices"][0]["message"]["content"] or "").strip()
    except (KeyError, IndexError, TypeError) as exc:
        raise SuperGrokUnavailable("SuperGrok response had no message") from exc
    if not text:
        raise SuperGrokUnavailable("SuperGrok response was empty")
    return text


def _open(request: urllib.request.Request, timeout: float):
    try:
        return urllib.request.urlopen(request, timeout=timeout)
    except urllib.error.URLError as exc:
        text = str(exc).lower()
        if "tunnel connection failed" not in text or "403" not in text:
            raise
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        return opener.open(request, timeout=timeout)


def _error_detail(exc: urllib.error.HTTPError) -> str:
    try:
        return exc.read().decode("utf-8", errors="replace").strip()[:300]
    except Exception:  # noqa: BLE001
        return ""


def _token_from_file(path: Path) -> str:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(payload, dict):
        return ""
    record = payload.get(_SIGN_IN)
    if not isinstance(record, dict):
        record = payload
    for key in ("key", "access_token", "token"):
        value = record.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""
