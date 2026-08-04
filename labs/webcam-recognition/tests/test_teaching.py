"""Theodore teaching vs self-teaching mode tests."""

from webcam_lab.presence import PresenceVerdict
from webcam_lab.teaching import TeachingMode, plan_teaching_turn, teaching_script


def test_theodore_teach_default():
    turn = plan_teaching_turn(mode=TeachingMode.THEODORE_TEACH, slide_title="Fractions")
    assert turn.speaker.startswith("Theodore")
    assert turn.action == "teach"
    assert turn.use_voice_agent is True


def test_self_teach_human_leads():
    turn = plan_teaching_turn(mode=TeachingMode.SELF_TEACH, slide_title="Fractions")
    assert turn.speaker == "Host"
    assert turn.action == "human_teach"
    assert turn.use_voice_agent is False


def test_presence_hold_pauses():
    presence = PresenceVerdict(
        present=False,
        liveness_state="absent",
        reason="user_absent",
        hold_recommended=True,
    )
    turn = plan_teaching_turn(
        mode=TeachingMode.THEODORE_TEACH,
        slide_title="Fractions",
        presence=presence,
    )
    assert turn.pause_class is True
    assert turn.action == "presence_hold"
    assert "pause" in turn.line.lower() or "camera" in turn.line.lower()


def test_self_teach_assist_on_question():
    turn = plan_teaching_turn(
        mode=TeachingMode.SELF_TEACH,
        slide_title="Fractions",
        learner_question="What is a numerator?",
    )
    assert turn.action == "assist_answer"
    assert turn.use_voice_agent is True


def test_teaching_script_length():
    turns = teaching_script(TeachingMode.THEODORE_TEACH, ["A", "B", "C"])
    assert len(turns) == 3
