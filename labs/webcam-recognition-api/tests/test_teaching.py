"""Tests for the teaching conductor (presence -> action -> speech)."""

from __future__ import annotations

from webcam_recognition.config import LabConfig
from webcam_recognition.presence import PresenceEvent, PresenceState
from webcam_recognition.session import ClassMode, SessionEvent, TeachingMode
from webcam_recognition.teaching import ActionKind, TeachingConductor
from webcam_recognition.voice_agent import XAIVoiceAgent

AGENT = XAIVoiceAgent(LabConfig(xai_api_key=""))  # fallback agent


def _conductor(class_mode=ClassMode.SOLO, teaching=TeachingMode.THEODORE):
    return TeachingConductor(
        AGENT, class_mode=class_mode, teaching_mode=teaching, topic="fractions"
    )


def _ev(kind, pid="learner"):
    return SessionEvent(pid, kind, at=1.0, state=PresenceState.PRESENT)


def test_arrival_greets():
    a = _conductor().on_presence_event(_ev(PresenceEvent.ARRIVED), learner_name="Sam")
    assert a.kind is ActionKind.GREET
    assert a.reply is not None and a.reply.text


def test_solo_absence_pauses():
    a = _conductor(ClassMode.SOLO).on_presence_event(
        _ev(PresenceEvent.LEFT), away_seconds=10
    )
    assert a.kind is ActionKind.PAUSE
    assert a.reply.text


def test_group_absence_speaks_but_does_not_pause():
    a = _conductor(ClassMode.GROUP).on_presence_event(_ev(PresenceEvent.LEFT))
    assert a.kind is ActionKind.SPEAK


def test_return_resumes():
    a = _conductor().on_presence_event(_ev(PresenceEvent.RETURNED))
    assert a.kind is ActionKind.RESUME
    assert a.reply.text


def test_attention_nudge_theodore_only_and_once():
    c = _conductor(teaching=TeachingMode.THEODORE)
    first = c.on_attention(0.1, learner_name="Sam")
    assert first.kind is ActionKind.NUDGE_ATTENTION
    # Repeated low attention should not spam nudges.
    second = c.on_attention(0.1)
    assert second.kind is ActionKind.NONE
    # Recovering attention resets the nudge latch.
    c.on_attention(0.9)
    third = c.on_attention(0.1)
    assert third.kind is ActionKind.NUDGE_ATTENTION


def test_self_teaching_never_nudges():
    c = _conductor(teaching=TeachingMode.SELF)
    assert c.on_attention(0.0).kind is ActionKind.NONE


def test_answer_produces_reply():
    a = _conductor().answer("what is a numerator?", learner_name="Sam")
    assert a.kind is ActionKind.ANSWER
    assert a.reply is not None and a.reply.text


def test_handle_events_batch_group():
    c = _conductor(ClassMode.GROUP)
    events = [_ev(PresenceEvent.ARRIVED, "a"), _ev(PresenceEvent.LEFT, "b")]
    actions = c.handle_events(
        events, name_lookup=lambda pid: pid.upper(), headcount=1
    )
    assert len(actions) == 2
    assert actions[0].kind is ActionKind.GREET
    assert actions[1].kind is ActionKind.SPEAK
