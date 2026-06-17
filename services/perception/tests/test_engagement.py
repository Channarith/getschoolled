"""Engagement (gaze/expression) + cross-session memory tests."""

from aoep_shared.vision import FaceGallery, estimate_engagement
from aoep_shared.vision.engine import cosine_similarity


def _frontal_landmarks():
    # right_eye, left_eye, nose (centered), mouth corners - a frontal neutral face.
    return [(40.0, 50.0), (80.0, 50.0), (60.0, 65.0), (48.0, 85.0), (72.0, 85.0)]


def test_frontal_face_scores_high_attention():
    eng = estimate_engagement(_frontal_landmarks(), bbox=(30, 30, 70, 80), frame_size=(200, 200))
    assert eng.gaze_frontal > 0.8
    assert eng.attention > 0.6


def test_turned_head_scores_low_gaze():
    # Nose shifted toward the left eye -> head turned.
    lm = [(40.0, 50.0), (80.0, 50.0), (44.0, 65.0), (48.0, 85.0), (72.0, 85.0)]
    eng = estimate_engagement(lm, bbox=(30, 30, 70, 80), frame_size=(200, 200))
    assert eng.gaze_frontal < 0.6


def test_smile_detected_from_wide_mouth():
    lm = [(40.0, 50.0), (80.0, 50.0), (60.0, 65.0), (38.0, 85.0), (82.0, 85.0)]
    eng = estimate_engagement(lm, bbox=(30, 30, 70, 80), frame_size=(200, 200))
    assert eng.expression in ("smiling", "surprised")


def test_missing_landmarks_safe():
    eng = estimate_engagement([], bbox=(0, 0, 10, 10), frame_size=(100, 100))
    assert eng.attention == 0.0 and eng.expression == "unknown"


def test_gallery_persistence_remembers_across_sessions(tmp_path):
    # Enroll, persist, reload into a FRESH gallery -> still recognized.
    g = FaceGallery(match_threshold=0.5)
    emb = [1.0, 0.0, 0.0]
    g.enroll("alice", emb)
    path = str(tmp_path / "gallery.json")
    g.save_json(path)

    reloaded = FaceGallery.load_json(path)
    assert "alice" in reloaded.students()
    m = reloaded.identify([0.95, 0.05, 0.0])
    assert m.matched and m.student_id == "alice"


def test_load_missing_gallery_is_empty(tmp_path):
    g = FaceGallery.load_json(str(tmp_path / "nope.json"))
    assert g.students() == []


def test_real_detected_faces_have_landmarks_and_engagement(engine, dataset):
    # Uses the real YuNet+SFace pipeline (skips if models/dataset unavailable).
    path = dataset["train"]["obama"][0]
    faces = engine.detect_faces(path)
    assert faces and len(faces[0].landmarks) == 5
    eng = estimate_engagement(faces[0].landmarks, faces[0].bbox, faces[0].frame_size)
    assert 0.0 <= eng.attention <= 1.0
    assert eng.expression in ("neutral", "smiling", "surprised", "unknown")
