"""Tests for camera check vision char matching (mirrors TS logic)."""

import unicodedata


def _normalize(text: str) -> str:
    t = unicodedata.normalize("NFD", text.lower())
    t = "".join(c for c in t if unicodedata.category(c) != "Mn")
    return "".join(ch for ch in t if ch.isalnum())


def _spoken_matches_chars(spoken: str, expected: str) -> bool:
    norm = _normalize(spoken)
    target = expected.lower()
    if not norm or not target:
        return False
    ti = 0
    for ch in norm:
        if ch == target[ti]:
            ti += 1
        if ti >= len(target):
            return True
    return target in norm


def test_char_match_in_order():
    assert _spoken_matches_chars("P R S T L N E", "PRSTLNE")
    assert _spoken_matches_chars("prstlne", "PRSTLNE")
    assert not _spoken_matches_chars("hello", "PRSTLNE")


def test_distance_monotonic():
    ref_m = 0.65
    ref_ratio = 0.28

    def metres(ratio: float) -> float:
        effective = max(0.08, ratio)
        m = ref_m * (ref_ratio / effective)
        return round(max(0.35, min(2.5, m)), 2)

    assert metres(0.28) == 0.65
    assert metres(0.5) < metres(0.28)
