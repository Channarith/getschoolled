"""edge-tts audio that still plays when the process proxy refuses the speech host.

aiohttp does not use HTTP(S)_PROXY unless a proxy is passed in. A configured
proxy is tried first. When that proxy answers 403, or cannot reach the speech
service, the same line is rendered with a direct connection.
"""

from __future__ import annotations

import os

_PROXY_KEYS = (
    "HTTPS_PROXY",
    "https_proxy",
    "ALL_PROXY",
    "all_proxy",
    "HTTP_PROXY",
    "http_proxy",
)


def proxy_from_env() -> str:
    for key in _PROXY_KEYS:
        value = os.environ.get(key, "").strip()
        if value:
            return value
    return ""


async def render_edge_mp3(
    text: str,
    *,
    voice: str,
    rate: str = "+0%",
    pitch: str = "+0Hz",
    volume: str = "+0%",
) -> bytes:
    """MP3 bytes for one line, in the requested neural voice."""
    import edge_tts

    configured = proxy_from_env()
    attempts: list[str | None] = [configured, None] if configured else [None]
    last: BaseException | None = None
    for index, proxy in enumerate(attempts):
        try:
            comm = edge_tts.Communicate(
                text,
                voice=voice,
                rate=rate or "+0%",
                pitch=pitch or "+0Hz",
                volume=volume or "+0%",
                proxy=proxy,
            )
            audio = bytearray()
            async for chunk in comm.stream():
                if chunk.get("type") == "audio" and chunk.get("data"):
                    audio.extend(chunk["data"])
            if not audio:
                raise RuntimeError("edge-tts returned no audio")
            return bytes(audio)
        except Exception as exc:  # noqa: BLE001 — the direct attempt may still work
            last = exc
            if index + 1 < len(attempts):
                continue
            raise
    if last is not None:
        raise last
    raise RuntimeError("edge-tts returned no audio")
