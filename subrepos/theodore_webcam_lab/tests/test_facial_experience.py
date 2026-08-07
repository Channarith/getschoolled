from __future__ import annotations

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.facial_experience import estimate_from_luminance_grid
from theodore_webcam_lab.types import ClassMode, WebcamSignal


def _grid(h: int, w: int, fill: float = 0.55) -> list[list[float]]:
    return [[fill for _ in range(w)] for _ in range(h)]


def _paint_person(grid: list[list[float]], *, smile: bool, head_low: bool = False) -> None:
    h, w = len(grid), len(grid[0])
    cy = int(h * (0.62 if head_low else 0.42))
    cx = w // 2
    # Dark head + torso
    for y in range(max(0, cy - 8), min(h, cy + 18)):
        for x in range(max(0, cx - 10), min(w, cx + 10)):
            grid[y][x] = 0.18
    # Eyes darker
    ey = cy - 3
    for x in range(cx - 6, cx - 2):
        grid[ey][x] = 0.08
        grid[ey][x + 8] = 0.08
    # Mouth: smiling = bright horizontal structure; sad = flat dark line
    my = cy + 5
    if smile:
        for x in range(cx - 5, cx + 5):
            grid[my][x] = 0.72 if (x - cx) % 2 == 0 else 0.28
            if my + 1 < h:
                grid[my + 1][x] = 0.65 if (x - cx) % 2 else 0.22
    else:
        for x in range(cx - 4, cx + 4):
            grid[my][x] = 0.12


def test_estimate_marks_empty_room_as_away():
    flat = _grid(36, 64, 0.52)
    est = estimate_from_luminance_grid(flat)
    assert est is not None
    assert est.face_present is False
    assert est.attention == "away_from_webcam"


def test_estimate_detects_happy_and_sad_faces():
    happy = _grid(36, 64, 0.62)
    _paint_person(happy, smile=True)
    sad = _grid(36, 64, 0.62)
    _paint_person(sad, smile=False)

    h_est = estimate_from_luminance_grid(happy)
    s_est = estimate_from_luminance_grid(sad)
    assert h_est is not None and s_est is not None
    assert h_est.face_present and s_est.face_present
    assert h_est.expression_label == "happy"
    assert s_est.expression_label in {"sad", "neutral"}
    assert h_est.smile_score > s_est.smile_score


def test_estimate_flags_head_low_as_eyes_away():
    grid = _grid(36, 64, 0.60)
    _paint_person(grid, smile=False, head_low=True)
    est = estimate_from_luminance_grid(grid)
    assert est is not None
    assert est.face_present
    assert est.gaze_down_score >= 0.45


def test_analyzer_fills_expression_from_luminance_grid():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=50_000))
    happy = _grid(36, 64, 0.62)
    _paint_person(happy, smile=True)
    result = analyzer.evaluate(
        session_id="facial-1",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=1_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.4,
                motion_score=0.2,
                luminance_grid=happy,
            )
        ],
    )
    p = result.participants[0]
    assert p.dominant_expression == "happy"
    assert p.expression_confidence is not None and p.expression_confidence > 0.4
    assert any(a.code == "learner_mood_happy" for a in result.lesson_alerts)


def test_analyzer_marks_empty_frame_away_and_alerts():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(absence_grace_ms=1))
    flat = _grid(36, 64, 0.5)
    first = analyzer.evaluate(
        session_id="facial-away",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=100,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
                luminance_grid=flat,
            )
        ],
    )
    second = analyzer.evaluate(
        session_id="facial-away",
        mode=ClassMode.SOLO,
        signals=[
            WebcamSignal(
                participant_id="camera-local",
                timestamp_ms=2_000,
                face_count=1,
                liveness_state="live",
                foreground_ratio=0.2,
                motion_score=0.1,
                luminance_grid=flat,
            )
        ],
    )
    assert first.participants[0].face_count == 0
    assert second.participants[0].state.value in {"temporarily_missing", "absent"}
    assert any(
        a.code in {"student_absent", "student_temporarily_missing"}
        for a in second.lesson_alerts
    )
