"""The tutor answers in the learner's language: the prompt carries the rule."""

from __future__ import annotations

from orchestrator.main import app
from orchestrator.teaching import TeachingSessions

LESSON = "intro-to-photosynthesis"


def _sessions() -> TeachingSessions:
    return TeachingSessions(app.state.factory)


def test_ask_prompt_instructs_reply_language_for_non_english():
    sessions = _sessions()
    state = sessions.start_session(LESSON, "group")
    session = sessions.get_session(state.session_id)
    messages, *_ = sessions._ask_prompt(session, "What gas do plants release?", "es", None)
    joined = " ".join(m.content for m in messages)
    assert "Spanish" in joined
    assert "Respond entirely in Spanish" in joined


def test_ask_prompt_accepts_locale_and_no_rule_for_english():
    sessions = _sessions()
    session = sessions.get_session(sessions.start_session(LESSON, "group").session_id)

    # A device locale like "km-KH" still maps to Khmer.
    km, *_ = sessions._ask_prompt(session, "Explain again?", "km-KH", None)
    assert "Khmer" in " ".join(m.content for m in km)

    # English (the default) adds no language instruction.
    en, *_ = sessions._ask_prompt(session, "Explain again?", "en", None)
    assert "Respond entirely in" not in " ".join(m.content for m in en)
