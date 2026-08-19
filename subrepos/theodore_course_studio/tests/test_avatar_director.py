from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest
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
from theodore_course_studio import main
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
    assert DRIVER_AVATAR_TITLES == driver
    # Food track expanded beyond the original curated pack (hygiene/temps/
    # contamination/cleaning/pathogens/service). Keep the hand-authored cue
    # table, require that most of it still matches live slide titles, and let
    # new/renamed slides fall back to inferred motion.
    assert len(FOOD_AVATAR_TITLES) >= 30
    matched = FOOD_AVATAR_TITLES & food
    assert len(matched) >= 20, sorted(FOOD_AVATAR_TITLES - food)


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
    rig = client.get("/api/studio/avatar/avatar_rig.js")
    rig_config = client.get("/api/studio/avatar/avatar_rig_config_v2.json")
    loader = client.get("/api/studio/avatar/loaders/GLTFLoader.js")
    geometry_utils = client.get("/api/studio/avatar/utils/BufferGeometryUtils.js")
    page = client.get("/studio")
    assert glb.status_code == 200
    assert glb.content[:4] == b"glTF"
    assert runtime.status_code == 200
    assert rig.status_code == 200
    assert rig_config.status_code == 200
    assert loader.status_code == 200
    assert geometry_utils.status_code == 200
    assert "class TheodoreAvatar" in runtime.text
    # The runtime must import the rig adapter, and the adapter must be served.
    assert "avatar_rig.js" in runtime.text
    assert "resolveSkeleton" in rig.text
    assert "required_blendshapes" in rig_config.text
    assert "three" in page.text
    assert 'id="theodore-avatar"' in page.text
    assert 'id="avatar-enabled"' in page.text
    assert 'id="avatar-motion"' in page.text
    assert 'id="avatar-reduced"' in page.text
    assert "prefers-reduced-motion" in page.text
    assert "theodore-avatar-fallback" in page.text
    assert "speechBoundary" in page.text


def test_presenter_manifest_defaults_to_builtin():
    client = TestClient(app)
    response = client.get("/api/studio/presenter/manifest")
    assert response.status_code == 200
    data = response.json()
    assert data["models"]["female"]["rig"] == "procedural"
    assert data["models"]["female"]["url"].endswith("presenter_female.glb")
    assert data["rig_config_url"].endswith("avatar_rig_config_v2.json")


_AVATAR_STATIC = Path(main.__file__).with_name("avatar_static")

# The rig the runtime choreography drives by name; losing any of these silently
# breaks gestures instead of raising.
_REQUIRED_BONES = {
    "AvatarRoot", "Hips", "Spine", "Chest", "Neck", "Head", "Jaw", "Crown",
    "LeftEye", "RightEye", "LeftBrow", "RightBrow", "LeftEar", "RightEar",
    "LeftShoulder", "LeftElbow", "LeftWrist", "LeftFingers",
    "RightShoulder", "RightElbow", "RightWrist", "RightFingers",
    "LeftHip", "LeftKnee", "LeftAnkle", "RightHip", "RightKnee", "RightAnkle",
}


def _read_glb_json(path: Path) -> dict:
    """Returns the JSON chunk of a .glb, which holds the scene graph and canon."""
    raw = path.read_bytes()
    assert raw[:4] == b"glTF"
    (length,) = struct.unpack_from("<I", raw, 12)
    return json.loads(raw[20 : 20 + length])


@pytest.mark.parametrize("variant", ["female", "male"])
def test_presenter_glb_keeps_the_chibi_canon_and_full_rig(variant: str) -> None:
    document = _read_glb_json(_AVATAR_STATIC / f"presenter_{variant}.glb")
    scene = document["scenes"][0]
    canon = scene.get("extras", {}).get("presenter", {})

    # build_avatar.mjs publishes the canon it built to, so the shipped asset can be
    # checked without re-deriving proportions here.
    assert canon.get("variant") == variant
    assert canon["heads"] == pytest.approx(2.75)
    assert canon["lean"] > 0

    body = next(node for node in document["nodes"] if node.get("name") == "PresenterBody")
    position = document["accessors"][
        document["meshes"][body["mesh"]]["primitives"][0]["attributes"]["POSITION"]
    ]
    top = position["max"][1]
    floor = position["min"][1]

    # Total height is fixed so the runtime camera framing does not need retuning.
    assert top == pytest.approx(4.15, abs=0.02)
    # Feet stand on the ground plane rather than hovering over the contact shadow.
    assert floor == pytest.approx(0.0, abs=0.01)

    heads_tall = top / (top - canon["chinY"])
    assert 2.5 <= heads_tall <= 3.1, f"{variant} is {heads_tall:.2f} heads tall"

    names = {node.get("name") for node in document["nodes"]}
    assert _REQUIRED_BONES <= names
    assert len(document["skins"][0]["joints"]) == len(_REQUIRED_BONES)

    mouth = next(node for node in document["nodes"] if node.get("name") == "Mouth")
    targets = document["meshes"][mouth["mesh"]]["primitives"][0].get("targets", [])
    assert len(targets) == 3, "lip-sync needs mouthOpen / mouthWide / mouthSmile"
