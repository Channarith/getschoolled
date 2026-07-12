"""Instructor personality catalog."""

from __future__ import annotations

import re

from aoep_shared.instructors import (
    INSTRUCTORS,
    get_instructor,
    list_instructors,
    resolve_instructor,
)

# ElevenLabs voice-style presets the /tts endpoint understands.
_EL_STYLES = {"standard", "warm", "energetic", "calm", "storyteller"}
_RATE_RE = re.compile(r"^[+-]\d+%$")
_PITCH_RE = re.compile(r"^[+-]\d+Hz$")


def test_has_requested_personalities():
    ids = {i.id for i in INSTRUCTORS}
    for want in ["kind", "strict", "professional", "child", "cartoon"]:
        assert want in ids, want
    assert len(INSTRUCTORS) >= 8


def test_fields_valid():
    seen = set()
    for i in INSTRUCTORS:
        assert i.id not in seen
        seen.add(i.id)
        assert i.voice_style in _EL_STYLES, f"{i.id}: bad style {i.voice_style}"
        assert _RATE_RE.match(i.edge_rate), f"{i.id}: bad rate {i.edge_rate}"
        assert _PITCH_RE.match(i.edge_pitch), f"{i.id}: bad pitch {i.edge_pitch}"
        assert i.tone_hint and i.label and i.emoji


def test_personality_prosody_differs():
    # child/cartoon are higher & faster; strict is lower & slower than professional.
    child = get_instructor("child")
    strict = get_instructor("strict")
    prof = get_instructor("professional")
    assert int(child.edge_pitch.rstrip("Hz")) > int(prof.edge_pitch.rstrip("Hz"))
    assert int(strict.edge_pitch.rstrip("Hz")) < int(prof.edge_pitch.rstrip("Hz"))


def test_get_and_resolve():
    assert get_instructor("KIND").id == "kind"     # case-insensitive
    assert get_instructor("nope") is None
    assert resolve_instructor("") is None          # unset -> caller default
    assert resolve_instructor("cartoon").voice_style == "storyteller"


def test_list_for_picker():
    rows = list_instructors()
    assert {"id", "label", "emoji", "description", "voice_style"} <= set(rows[0])
