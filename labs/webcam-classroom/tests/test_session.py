"""ClassroomSession: pacing for solo/group x Theodore/self-teaching."""

from __future__ import annotations

import numpy as np

from webcam_classroom.config import WebcamLabConfig
from webcam_classroom.session import (
    GROUP,
    SOLO,
    TEACHER_SELF,
    TEACHER_THEODORE,
    ClassroomSession,
)
from webcam_classroom.silhouette import ABSENT, PRESENT, SilhouetteReading


def _cfg() -> WebcamLabConfig:
    return WebcamLabConfig(
        xai_api_key="",  # offline fallback voice
        looking_away_after=4.0,
        brief_absent_after=6.0,
        absent_after=20.0,
    )


def _present(cov: float = 0.2) -> SilhouetteReading:
    return SilhouetteReading(PRESENT, True, cov, (0.5, 0.5), 1, 0.9, "test")


def _absent() -> SilhouetteReading:
    return SilhouetteReading(ABSENT, False, 0.0, (0.5, 0.5), 0, 0.0, "test")


def test_solo_theodore_pauses_on_absence_and_resumes():
    s = ClassroomSession(mode=SOLO, teacher=TEACHER_THEODORE, config=_cfg())
    s.observe(_present(), attention=0.9, now=0.0)
    assert s.paused is False

    s.observe(_absent(), now=1.0)
    upd = s.observe(_absent(), now=25.0)  # crosses absent threshold
    assert upd.paused is True
    assert upd.event is not None and upd.event.became_absent
    assert upd.spoke is True and upd.spoken_text  # Theodore says something

    back = s.observe(_present(), attention=0.9, now=27.0)
    assert back.paused is False
    assert back.event is not None and back.event.returned
    assert back.spoke is True


def test_self_teaching_never_pauses_but_coaches():
    s = ClassroomSession(mode=SOLO, teacher=TEACHER_SELF, config=_cfg())
    s.observe(_present(), attention=0.9, now=0.0)
    s.observe(_absent(), now=1.0)
    upd = s.observe(_absent(), now=25.0)
    # No lecture to pause, but the coach still speaks on the transition.
    assert upd.paused is False
    assert upd.event is not None and upd.event.became_absent
    assert upd.spoke is True and upd.spoken_text


def test_group_holds_while_any_absent_then_resumes():
    s = ClassroomSession(mode=GROUP, teacher=TEACHER_THEODORE, config=_cfg(),
                         user_ids=["ana", "ben"])
    s.observe(_present(), user_id="ana", attention=0.9, now=0.0)
    s.observe(_present(), user_id="ben", attention=0.9, now=0.0)
    assert s.paused is False

    # Ben leaves; Ana stays present.
    s.observe(_absent(), user_id="ben", now=1.0)
    s.observe(_present(), user_id="ana", attention=0.9, now=25.0)
    upd = s.observe(_absent(), user_id="ben", now=25.0)
    assert upd.paused is True
    assert "ben" in s.pause_reason

    # Ben returns -> all present -> resume.
    resume = s.observe(_present(), user_id="ben", attention=0.9, now=27.0)
    assert resume.paused is False


def test_observe_accepts_a_real_frame():
    s = ClassroomSession(mode=SOLO, teacher=TEACHER_THEODORE, config=_cfg())
    # Bright background with a big dark centred subject -> present.
    img = np.full((240, 320, 3), 210, dtype=np.uint8)
    img[40:210, 90:230, :] = 35
    upd = s.observe(img, attention=0.9, now=0.0)
    assert upd.reading is not None
    assert upd.reading.present is True
    assert s.solo.is_present()


def test_presence_report_maps_to_orchestrator_kwargs():
    s = ClassroomSession(mode=SOLO, teacher=TEACHER_THEODORE, config=_cfg())
    s.observe(_present(), attention=0.9, now=0.0)
    rep = s.presence_report()
    assert rep["present"] is True
    assert rep["face_count"] == 1
    assert rep["liveness_state"] == "live"
    assert rep["source"] == "webcam-classroom"

    s.observe(_absent(), now=1.0)
    s.observe(_absent(), now=25.0)
    rep2 = s.presence_report()
    assert rep2["present"] is False
    assert rep2["liveness_state"] == "absent"


def test_realtime_voice_session_wiring():
    s = ClassroomSession(mode=SOLO, teacher=TEACHER_THEODORE, config=_cfg())
    sess = s.realtime_voice_session()
    assert sess["url"].startswith("wss://")
    assert "model=" in sess["url"]
    assert sess["session_update"]["type"] == "session.update"


def test_state_snapshot_shapes():
    solo = ClassroomSession(mode=SOLO, teacher=TEACHER_THEODORE, config=_cfg())
    solo.observe(_present(), attention=0.9, now=0.0)
    st = solo.state()
    assert st["mode"] == SOLO and "learner" in st

    grp = ClassroomSession(mode=GROUP, teacher=TEACHER_THEODORE, config=_cfg(),
                           user_ids=["ana"])
    grp.observe(_present(), user_id="ana", attention=0.9, now=0.0)
    gst = grp.state()
    assert gst["mode"] == GROUP and "learners" in gst
