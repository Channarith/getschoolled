"""Teaching session: solo/group × Theodore/self-teach + voice."""

from __future__ import annotations

import pytest

from webcam_lab.prompts import instructions_for, presence_nudge
from webcam_lab.teaching import ClassMode, TeachingMode, TeachingSession
from webcam_lab.xai_voice import OfflineVoiceAgent


@pytest.mark.asyncio
async def test_solo_theodore_absence_hold_and_nudge():
    voice = OfflineVoiceAgent()
    session = TeachingSession.create(
        class_mode="solo",
        teaching_mode="theodore",
        topic="gravity",
        voice=voice,
    )
    session.add_participant("p1", "Ada")
    session.report_presence("p1", face_count=1)
    assert session.should_pause_teaching() is False

    for _ in range(3):
        session.report_presence("p1", face_count=0, silhouette_count=0)
    assert session.should_pause_teaching() is True
    assert session.hold_reason == "user_absent"

    line = await session.handle_presence_voice("p1")
    assert line and "camera" in line.lower()
    assert voice.spoken
    assert session.teaching_mode == TeachingMode.THEODORE
    assert session.class_mode == ClassMode.SOLO


def test_group_allows_multiple_seats():
    session = TeachingSession.create(class_mode="group", teaching_mode="self_teach")
    session.add_participant("a", "Ada")
    session.add_participant("b", "Bea")
    assert len(session.seats) == 2
    assert "self" in session.system_instructions.lower() or "peer" in session.system_instructions.lower()


def test_solo_rejects_second_seat():
    session = TeachingSession.create(class_mode="solo")
    session.add_participant("a", "Ada")
    with pytest.raises(ValueError):
        session.add_participant("b", "Bea")


def test_prompt_table_and_nudge():
    assert "Theodore" in instructions_for("theodore", "solo")
    assert "group" in instructions_for("theodore", "group").lower()
    assert presence_nudge("verified") == ""
    assert "guide" in presence_nudge("silhouette_only").lower()
    assert "camera" in presence_nudge("user_absent").lower()
