"""AOEPLX layered scene format tests."""

import pytest

from aoep_shared.scene import (
    FORMAT,
    DeltaOp,
    Layer,
    LayerType,
    Scene,
    SceneDelta,
    Stroke,
    TimeRange,
    Transform,
    apply_delta,
    content_hash,
    deserialize,
    extract_region,
    new_layer,
    serialize,
    sign_scene,
    verify_scene,
)


def _scene_with_video_and_drawing() -> Scene:
    scene = Scene(title="Photosynthesis")
    scene.add_layer(new_layer(LayerType.VIDEO, "vid", asset_key="s3://v.mp4", z=0))
    scene.add_layer(
        new_layer(
            LayerType.WHITEBOARD,
            "draw",
            z=1,
            transform=Transform(x=0.3, y=0.3, w=0.3, h=0.3),
            strokes=[Stroke(points=[(0.31, 0.31), (0.4, 0.4)])],
            time=TimeRange(start=5, end=10),
        )
    )
    return scene


def test_attach_audio_and_note_to_drawing():
    scene = _scene_with_video_and_drawing()
    note = new_layer(LayerType.NOTE, "n1", text="this is the leaf")
    audio = new_layer(LayerType.AUDIO, "a1", asset_key="s3://note.mp3")
    scene.attach("draw", note)
    scene.attach("draw", audio)
    anchored = {ly.id for ly in scene.annotations_of("draw")}
    assert anchored == {"n1", "a1"}
    # Annotations sit above the drawing they explain.
    assert scene.get_layer("n1").z > scene.get_layer("draw").z


def test_ordered_by_z():
    scene = _scene_with_video_and_drawing()
    assert [ly.id for ly in scene.ordered()] == ["vid", "draw"]


def test_apply_deltas_add_update_remove_stroke():
    scene = _scene_with_video_and_drawing()
    apply_delta(scene, SceneDelta(op=DeltaOp.APPEND_STROKE, layer_id="draw",
                                  stroke=Stroke(points=[(0.5, 0.5), (0.6, 0.6)])))
    assert len(scene.get_layer("draw").strokes) == 2

    apply_delta(scene, SceneDelta(op=DeltaOp.ADD_LAYER,
                                  layer=new_layer(LayerType.TEXT, "t1", text="hi")))
    assert scene.get_layer("t1") is not None

    apply_delta(scene, SceneDelta(op=DeltaOp.UPDATE_LAYER, layer_id="t1",
                                  patch={"text": "updated"}))
    assert scene.get_layer("t1").text == "updated"

    apply_delta(scene, SceneDelta(op=DeltaOp.REMOVE_LAYER, layer_id="t1"))
    assert scene.get_layer("t1") is None


def test_extract_instant_is_image_clip_is_video():
    scene = _scene_with_video_and_drawing()
    # Pause at t=7, lift the drawing region out as a still image object.
    img = extract_region(scene, layer_ids=["draw"], time=TimeRange(start=7, end=7),
                         title="leaf")
    assert img.kind == "image"
    assert any(ly.id == "draw" for ly in img.scene.layers)

    clip = extract_region(scene, layer_ids=["draw"], time=TimeRange(start=5, end=10))
    assert clip.kind == "clip"
    # Time rebased to start at 0.
    assert clip.scene.get_layer("draw").time.start == 0.0


def test_extract_includes_annotations_of_selected_layer():
    scene = _scene_with_video_and_drawing()
    scene.attach("draw", new_layer(LayerType.NOTE, "n1", text="leaf"))
    obj = extract_region(scene, layer_ids=["draw"])
    ids = {ly.id for ly in obj.scene.layers}
    assert {"draw", "n1"} <= ids


def test_extract_by_bbox_selects_intersecting_layers():
    scene = _scene_with_video_and_drawing()
    obj = extract_region(scene, bbox=Transform(x=0.0, y=0.0, w=0.2, h=0.2))
    # Only the full-frame video intersects the top-left corner; the drawing
    # (0.3..0.6) does not.
    ids = {ly.id for ly in obj.scene.layers}
    assert "vid" in ids and "draw" not in ids


def test_sign_verify_and_tamper_detection():
    scene = _scene_with_video_and_drawing()
    key = b"test-key"
    signed = sign_scene(scene, key)
    assert signed.format == FORMAT
    assert verify_scene(signed, key) is True
    # Wrong key fails.
    assert verify_scene(signed, b"other-key") is False
    # Tamper with the scene -> verification fails.
    signed.scene.title = "HACKED"
    assert verify_scene(signed, key) is False


def test_serialize_roundtrip():
    scene = _scene_with_video_and_drawing()
    key = b"k"
    text = serialize(sign_scene(scene, key))
    restored = deserialize(text)
    assert restored.scene.title == "Photosynthesis"
    assert verify_scene(restored, key) is True


def test_duplicate_layer_id_rejected():
    scene = Scene()
    scene.add_layer(new_layer(LayerType.TEXT, "dup", text="a"))
    with pytest.raises(ValueError):
        scene.add_layer(new_layer(LayerType.TEXT, "dup", text="b"))
