"""Stable clip id shared with apps/web/app/lib/cloneVoice.ts, apps/mobile/src/cloneVoice.ts and the Vision Play
clone_voice.js: cyrb53 over UTF-16 code units of "<lang>␟<normalized text>", as 14 hex digits."""
from __future__ import annotations

import re
import unicodedata

_WS = re.compile("[ \t\n\r\f\v\u00a0\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]+")
SEP = "\u241f"
_M = 0xFFFFFFFF


def normalize(text: str) -> str:
    return _WS.sub(" ", unicodedata.normalize("NFC", text or "")).strip()


def primary_lang(lang: str) -> str:
    return (lang or "en").split("-")[0].split("_")[0].lower()


def _imul(a: int, b: int) -> int:
    return (a * b) & _M


def cyrb53(s: str, seed: int = 0) -> int:
    h1 = (0xDEADBEEF ^ seed) & _M
    h2 = (0x41C6CE57 ^ seed) & _M
    raw = s.encode("utf-16-le")
    for i in range(0, len(raw), 2):
        ch = raw[i] | (raw[i + 1] << 8)
        h1 = _imul(h1 ^ ch, 2654435761)
        h2 = _imul(h2 ^ ch, 1597334677)
    h1 = _imul(h1 ^ (h1 >> 16), 2246822507)
    h1 ^= _imul(h2 ^ (h2 >> 13), 3266489909)
    h2 = _imul(h2 ^ (h2 >> 16), 2246822507)
    h2 ^= _imul(h1 ^ (h1 >> 13), 3266489909)
    return 4294967296 * (h2 & 2097151) + (h1 & _M)


def clip_hash(lang: str, text: str) -> str:
    return format(cyrb53(primary_lang(lang) + SEP + normalize(text)), "014x")
