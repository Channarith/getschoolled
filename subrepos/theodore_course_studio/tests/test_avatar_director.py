from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.avatar_director import (
    avatar_script_for_slide,
    narration_duration,
    validate_avatar_script,
)
from theodore_course_studio.certification_prep import (
    CertTrackId,
    build_cert_course,
    list_cert_courses,
)
from theodore_course_studio.driver_avatar_cues import DRIVER_AVATAR_TITLES
from theodore_course_studio.food_avatar_cues import FOOD_AVATAR_TITLES
from theodore_course_studio.main import app
from theodore_course_studio.types import AvatarCue, AvatarScript, CourseSlide


def _course_titles(track: CertTrackId) -> set[str]:
    titles: set[str] = set()
    for option in list_cert_courses(track):
        course = build_cert_course(track=track, lesson_id=option.lesson_id)
        titles.update(slide.title for slide in course.slides)
    return titles


def test_all_driver_and_food_slides_have_curated_choreography():
    driver = _course_titles(CertTrackId.CA_DMV_PERMIT)
    food = _course_titles(CertTrackId.ALAMEDA_FOOD_HANDLER)
    assert len(driver) == 32
    assert len(food) == 30
    assert DRIVER_AVATAR_TITLES == driver
    assert FOOD_AVATAR_TITLES == food


def test_curated_scripts_have_valid_timing_joints_and_visemes():
    for option in list_cert_courses():
        course = build_cert_course(track=option.track, lesson_id=option.lesson_id)
        for slide in course.slides:
            assert slide.avatar_script is not None
            script = avatar_script_for_slide(slide)
            assert script.source == "explicit"
            assert script.cues
            assert script.visemes
            validate_avatar_script(script)
            assert all(cue.start_s + cue.duration_s <= script.duration_s + 0.01 for cue in script.cues)
            assert any(cue.gaze in {"learner", "slide"} for cue in script.cues)


def test_explicit_script_overrides_inference_and_keeps_lip_sync():
    slide = CourseSlide(
        index=0,
        title="Custom",
        body="Custom body",
        narration="Say this slowly.",
        avatar_script=AvatarScript(
            duration_s=4,
            cues=[
                AvatarCue(
                    start_s=0,
                    duration_s=2,
                    gesture="point-right",
                    gaze="right",
                )
            ],
            source="explicit",
        ),
    )
    script = avatar_script_for_slide(slide)
    assert script.source == "explicit"
    assert script.cues[0].gesture == "point-right"
    assert script.visemes
    assert script.duration_s >= narration_duration(slide.narration)


def test_avatar_assets_are_offline_and_studio_wires_accessibility_controls():
    client = TestClient(app)
    glb = client.get("/api/studio/avatar/theodore.glb")
    runtime = client.get("/api/studio/avatar/avatar_runtime.js")
    loader = client.get("/api/studio/avatar/loaders/GLTFLoader.js")
    geometry_utils = client.get("/api/studio/avatar/utils/BufferGeometryUtils.js")
    page = client.get("/studio")
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"
    assert runtime.status_code == 200
    assert loader.status_code == 200
    assert geometry_utils.status_code == 200
    assert "class TheodoreAvatar" in runtime.text
    assert "three" in page.text
    assert 'id="theodore-avatar"' in page.text
    assert 'id="avatar-enabled"' in page.text
    assert 'id="avatar-motion"' in page.text
    assert 'id="avatar-reduced"' in page.text
    assert "prefers-reduced-motion" in page.text
    assert "theodore-avatar-fallback" in page.text
    assert "speechBoundary" in page.text
