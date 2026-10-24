"""Friendly error bodies for browser-facing FastAPI apps.

Keeps the machine contract (`detail` and the status code are untouched) and adds an
`error` code plus a `friendly_message` for 404, 501 and 5xx. A person who lands on a
bad URL in a browser gets the mascot page instead of bare JSON.
"""

from __future__ import annotations

import json
from html import escape
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

_COPY_FILE = Path(__file__).with_name("static") / "friendly_error_copy.json"
_COPY: dict[str, Any] = json.loads(_COPY_FILE.read_text(encoding="utf-8"))


def friendly_kind(status: int) -> str | None:
    """404/410 -> notfound, 501 -> notimpl, 502-504 -> network, other 5xx -> oops, else None."""
    if status in (404, 410):
        return "notfound"
    if status == 501:
        return "notimpl"
    if status in (502, 503, 504) or 520 <= status <= 524:
        return "network"
    if status >= 500:
        return "oops"
    return None


def friendly_message(status: int, locale: str = "en") -> str | None:
    kind = friendly_kind(status)
    if kind is None:
        return None
    block = _COPY.get(locale) or _COPY["en"]
    text = block.get(kind) or _COPY["en"][kind]
    return f"{text['title']}. {text['body']}"


def _wants_html(request: Request) -> bool:
    accept = request.headers.get("accept", "")
    if "text/html" not in accept:
        return False
    # An API call that happens to accept anything must keep getting JSON.
    return not request.url.path.startswith("/api/")


def _html_page(status: int, script_url: str) -> str:
    kind = friendly_kind(status) or "oops"
    en = _COPY["en"][kind]
    return (
        '<!doctype html><html lang="en"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width,initial-scale=1">'
        f"<meta name=\"robots\" content=\"noindex\"><title>{escape(en['title'])} - Salareen</title></head>"
        '<body style="margin:0;background:#0b1020;color:#eef2ff;font-family:system-ui,sans-serif">'
        f"<noscript><h1>{escape(en['title'])}</h1><p>{escape(en['body'])}</p></noscript>"
        f'<script src="{escape(script_url)}"></script>'
        f"<script>SalaFriendlyError.show({{status:{int(status)},homeHref:\"/\"}})</script></body></html>"
    )


def _json_body(status: int, detail: Any) -> dict[str, Any]:
    kind = friendly_kind(status) or "oops"
    body: dict[str, Any] = {"detail": detail, "error": kind, "status": status}
    message = friendly_message(status)
    if message:
        body["friendly_message"] = message
    return body


def install_friendly_errors(app: FastAPI, script_url: str = "/static/friendly_error.js") -> None:
    """Register handlers on `app`. `script_url` is where this app serves friendly_error.js."""

    @app.exception_handler(StarletteHTTPException)
    async def _http_exception(request: Request, exc: StarletteHTTPException):
        if friendly_kind(exc.status_code) is None:
            return await http_exception_handler(request, exc)
        if _wants_html(request):
            return HTMLResponse(_html_page(exc.status_code, script_url), status_code=exc.status_code, headers=exc.headers)
        return JSONResponse(_json_body(exc.status_code, exc.detail), status_code=exc.status_code, headers=exc.headers)

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception):  # noqa: ARG001 - the server still logs it
        if _wants_html(request):
            return HTMLResponse(_html_page(500, script_url), status_code=500)
        return JSONResponse(_json_body(500, "Internal Server Error"), status_code=500)
