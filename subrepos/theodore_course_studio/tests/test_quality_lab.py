from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_course_studio.engagement import (
    GameChallenge,
    GameKind,
    build_match_term_game,
    build_order_steps_game,
    build_spot_gap_game,
    grade_game,
    pick_game_for_slide,
)
from theodore_course_studio.main import app
from theodore_course_studio.quality_telemetry import StudioTelemetryStore
from theodore_course_studio.studio_tuning import (
    PRESETS,
    StudioTuning,
    get_tuning,
    reset_tuning,
)
from theodore_course_studio.types import CourseSlide

client = TestClient(app)


def _slide() -> CourseSlide:
    return CourseSlide(
        index=1,
        title="Photosynthesis basics",
        body="Plants convert sunlight into energy. Chlorophyll absorbs light. Water and carbon dioxide combine.",
        narration="Plants convert sunlight into energy.",
    )


def test_tuning_has_more_than_twenty_eight_knobs():
    tuning = StudioTuning()
    knobs = tuning.knob_names()
    assert len(knobs) >= 28
    for name in (
        "quiz_pass_score",
        "pop_quiz_interval_slides",
        "summary_quiz_max_questions",
        "game_pass_score",
        "slide_min_body_chars",
        "slide_max_body_chars",
        "narration_max_sentences",
        "teach_fade_ms",
        "checkpoint_soft_stop_min",
        "early_max_slides",
        "cert_max_slides",
        "content_cover_reject_weight",
        "content_dedupe_threshold",
        "quality_model_min_score",
        "tts_timeout_s",
        "voice_temperature",
        "voice_max_tokens",
        "voice_cache_ttl_s",
        "profile_gap_boost",
        "engagement_rotate_games",
        "spot_gap_options",
        "order_steps_min_parts",
        "child_i18n_cache_hours",
        "offline_epoch_default",
        "builder_max_slides_per_source",
        "builder_min_title_chars",
        "media_prefer_real",
        "telemetry_history_points",
    ):
        assert name in knobs


def test_tuning_from_env_and_presets():
    env = {"AOEP_STUDIO_QUIZ_PASS_SCORE": "0.9", "AOEP_STUDIO_EARLY_MAX_SLIDES": "6"}
    tuned = StudioTuning.from_env(env)
    assert tuned.quiz_pass_score == 0.9
    assert tuned.early_max_slides == 6
    for name in ("balanced", "kids_fast", "cert_strict", "adult_deep"):
        assert name in PRESETS
        assert isinstance(StudioTuning.preset(name), StudioTuning)
    assert StudioTuning.preset("cert_strict").quiz_pass_score == 0.85


def test_tuning_validate_rejects_bad_values():
    import pytest

    with pytest.raises(ValueError):
        StudioTuning(quiz_pass_score=1.5)
    with pytest.raises(ValueError):
        StudioTuning(pop_quiz_interval_slides=0)


def test_tuning_patch_ignores_unknown_and_coerces():
    tuning = StudioTuning()
    patched = tuning.patched({"summary_quiz_max_questions": "12", "bogus": 1})
    assert patched.summary_quiz_max_questions == 12
    assert not hasattr(patched, "bogus")


def test_tuning_api_patch_and_preset():
    reset_tuning()
    got = client.get("/api/studio/tuning")
    assert got.status_code == 200
    assert len(got.json()["tuning"]) >= 28
    patched = client.patch("/api/studio/tuning", json={"quiz_pass_score": 0.8})
    assert patched.status_code == 200
    assert patched.json()["tuning"]["quiz_pass_score"] == 0.8
    assert get_tuning().quiz_pass_score == 0.8
    preset = client.post("/api/studio/tuning/preset/cert_strict")
    assert preset.status_code == 200
    assert preset.json()["tuning"]["quiz_pass_score"] == 0.85
    assert client.post("/api/studio/tuning/preset/nope").status_code == 404
    reset_tuning()


def test_telemetry_reports_more_than_twenty_keys():
    store = StudioTelemetryStore()
    store.record_course_built(audience="general")
    store.record_early_course()
    store.record_cert_course()
    store.record_slide_taught(latency_ms=120)
    store.record_quiz(kind="pop", score=1.0, passed=True)
    store.record_quiz(kind="summary", score=0.5, passed=False)
    store.record_game(kind="match_term", score=1.0, passed=True)
    store.record_game(kind="spot_gap", score=0.0, passed=False)
    store.record_voice_turn(tts=True)
    store.record_checkpoint_pause()
    store.record_language_switch()
    store.record_review(keep=True)
    store.record_review(keep=False)
    store.record_offline_epochs(20)
    store.record_quality_reject(2)

    snap = store.snapshot()
    assert len(snap) >= 20
    assert snap["courses_built"] == 3
    assert snap["early_courses"] == 1
    assert snap["cert_courses"] == 1
    assert snap["slides_taught"] == 1
    assert snap["quizzes_started"] == 2
    assert snap["quizzes_passed"] == 1
    assert snap["games_started"] == 2
    assert snap["games_by_kind_started"]["match_term"] == 1
    assert snap["games_by_kind_passed"]["match_term"] == 1
    assert snap["voice_turns"] == 1
    assert snap["tts_requests"] == 1
    assert snap["checkpoint_pauses"] == 1
    assert snap["language_switches"] == 1
    assert snap["review_keeps"] == 1
    assert snap["review_rejects"] == 1
    assert snap["offline_epochs"] == 20
    assert snap["quality_rejects"] == 2
    assert snap["latency_teach_ms_avg"] == 120
    assert 0.0 <= snap["engagement_score"] <= 1.0


def test_telemetry_endpoint_available():
    resp = client.get("/api/studio/telemetry")
    assert resp.status_code == 200
    assert "engagement_score" in resp.json()


def test_all_three_game_kinds_grade_correctly():
    slide = _slide()

    match = build_match_term_game(slide, "obj-1")
    assert match.kind is GameKind.MATCH_TERM
    correct = match.payload["correct_index"]
    assert grade_game(match, {"selected_index": correct}).passed is True
    assert grade_game(match, {"selected_index": (correct + 1) % 3}).passed is False

    order = build_order_steps_game(slide, "obj-1")
    assert order.kind is GameKind.ORDER_STEPS
    right = grade_game(order, {"ordered_steps": order.payload["steps_correct"]})
    assert right.passed is True
    wrong = grade_game(order, {"ordered_steps": list(reversed(order.payload["steps_correct"]))})
    assert wrong.score <= right.score

    gap = build_spot_gap_game(slide, "obj-1")
    assert gap.kind is GameKind.SPOT_GAP
    assert "_____" in gap.payload["sentence_with_gap"]
    assert len(gap.payload["options"]) == 3
    gi = gap.payload["correct_index"]
    assert grade_game(gap, {"selected_index": gi}).passed is True
    assert grade_game(gap, {"selected_index": (gi + 1) % 3}).passed is False
    # Text answering also works.
    assert grade_game(gap, {"selected_text": gap.payload["answer"]}).passed is True


def test_pick_game_rotates_through_all_kinds():
    slide = _slide()
    kinds = [pick_game_for_slide(slide, "obj", rotate_index=i).kind for i in range(3)]
    assert kinds == [GameKind.MATCH_TERM, GameKind.ORDER_STEPS, GameKind.SPOT_GAP]
    # Wraps around.
    assert pick_game_for_slide(slide, "obj", rotate_index=3).kind is GameKind.MATCH_TERM


def test_spot_gap_falls_back_when_body_is_thin():
    thin = CourseSlide(index=0, title="Go", body="", narration="")
    game = build_spot_gap_game(thin, "obj-x")
    assert game.kind is GameKind.SPOT_GAP
    assert len(game.payload["options"]) == 3
    assert game.payload["answer"]


def test_teach_game_for_current_rotates_across_calls(tmp_path):
    from theodore_course_studio.generate import CourseBuilder
    from theodore_course_studio.teach import TeachEngine
    from theodore_course_studio.types import CategoryId, StudioCourse

    builder = CourseBuilder(data_dir=tmp_path / "data")
    builder.save_course(
        StudioCourse(
            course_id="game-rot",
            title="Games",
            category=CategoryId.LEADERSHIP,
            slides=[
                CourseSlide(
                    index=0,
                    title="Concept one",
                    body="First idea here. Second idea follows. Third idea closes.",
                    narration="First idea here.",
                ),
            ],
            status="ready",
        )
    )
    engine = TeachEngine(builder)
    engine.start(session_id="gr", course_id="game-rot", use_voice_agent=False)
    kinds = [engine.game_for_current("gr").kind for _ in range(3)]
    assert kinds == [GameKind.MATCH_TERM, GameKind.ORDER_STEPS, GameKind.SPOT_GAP]
