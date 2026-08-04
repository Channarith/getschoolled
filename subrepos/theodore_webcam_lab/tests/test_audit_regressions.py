"""Regression tests for bugs found during the comprehensive lab audit.

Each test below pins a specific defect that was reproduced before being fixed, so a
future change cannot quietly reintroduce it.
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from theodore_webcam_lab.analysis import AnalyzerPolicy, WebcamSessionAnalyzer
from theodore_webcam_lab.live_metrics import LiveMetricsStore
from theodore_webcam_lab.main import app
from theodore_webcam_lab.training_orchestrator import load_runbook, load_state, run_forever
from theodore_webcam_lab.types import ClassMode, WebcamSignal
from theodore_webcam_lab.voice_agents import XaiVoiceAgent

client = TestClient(app)


def _live(participant_id: str, timestamp_ms: int = 1_000) -> WebcamSignal:
    return WebcamSignal(
        participant_id=participant_id,
        timestamp_ms=timestamp_ms,
        face_count=1,
        liveness_state="live",
        foreground_ratio=0.3,
        motion_score=0.1,
    )


def test_evaluate_does_not_mutate_caller_signal_list():
    """Synthetic 'missing' heartbeats must not leak back into the caller's list."""
    analyzer = WebcamSessionAnalyzer()
    signals = [_live("a")]

    analyzer.evaluate(
        session_id="no-mutation",
        mode=ClassMode.GROUP,
        signals=signals,
        expected_participant_ids=["a", "b", "c"],
    )
    assert [s.participant_id for s in signals] == ["a"]

    # Reusing the same list must stay stable rather than accumulating duplicates.
    second = analyzer.evaluate(
        session_id="no-mutation",
        mode=ClassMode.GROUP,
        signals=signals,
        expected_participant_ids=["a", "b", "c"],
    )
    assert [s.participant_id for s in signals] == ["a"]
    assert len(second.participants) == 3


def test_metric_series_stay_aligned_with_timestamps_when_samples_missing():
    """A missing sample must become a None gap, not shift later points onto wrong times."""
    analyzer = WebcamSessionAnalyzer()
    store = LiveMetricsStore()
    for index, mic_level in enumerate([None, 0.9, None, 0.7]):
        timestamp = 1_000 * (index + 1)
        evaluation = analyzer.evaluate(
            session_id="aligned",
            mode=ClassMode.SOLO,
            signals=[
                WebcamSignal(
                    participant_id="p1",
                    timestamp_ms=timestamp,
                    face_count=1,
                    liveness_state="live",
                    light_quality_score=0.5,
                    microphone_input_level_score=mic_level,
                )
            ],
        )
        store.record(session_id="aligned", evaluation=evaluation, updated_at_ms=timestamp)

    series = store.snapshot("aligned").participants[0]
    assert series.timestamps_ms == [1_000, 2_000, 3_000, 4_000]
    assert len(series.microphone_quality_score) == len(series.timestamps_ms)
    assert series.microphone_quality_score[0] is None
    assert series.microphone_quality_score[2] is None
    assert series.microphone_quality_score[1] == 0.9
    assert len(series.light_quality_score) == len(series.timestamps_ms)


def test_live_monitor_page_escapes_session_id():
    """The reflected session id must never be injectable as HTML or script."""
    payload = "<img src=x onerror=alert(1)>"
    resp = client.get("/theodore/webcam/live-monitor/" + payload)
    assert resp.status_code == 200
    assert payload not in resp.text
    assert "&lt;img src=x onerror=alert(1)&gt;" in resp.text

    # Angle brackets must be unicode-escaped inside the <script> block too, so a
    # payload can never terminate the script element or open a new tag.
    script_break = 'a";<script>alert(2)'
    resp2 = client.get("/theodore/webcam/live-monitor/" + script_break)
    assert resp2.status_code == 200
    assert "<script>alert(2)" not in resp2.text
    assert "\\u003cscript\\u003e" in resp2.text


def test_group_mode_does_not_flag_classmates_as_unexpected():
    """Group classes have no single 'original' learner; classmates are not intruders."""
    analyzer = WebcamSessionAnalyzer()
    evaluation = analyzer.evaluate(
        session_id="group-roster",
        mode=ClassMode.GROUP,
        signals=[_live("alice"), _live("bob"), _live("carol")],
    )
    assert evaluation.original_participant_id == ""
    assert evaluation.unexpected_participant_ids == []
    assert evaluation.training_paused is False


def test_group_mode_flags_only_participants_outside_the_roster():
    analyzer = WebcamSessionAnalyzer()
    evaluation = analyzer.evaluate(
        session_id="group-roster-2",
        mode=ClassMode.GROUP,
        signals=[_live("alice"), _live("stranger")],
        expected_participant_ids=["alice", "bob"],
    )
    assert evaluation.unexpected_participant_ids == ["stranger"]


def test_solo_original_user_lock_still_applies():
    """The solo-mode guarantee must survive the group-mode scoping fix."""
    analyzer = WebcamSessionAnalyzer()
    analyzer.evaluate(session_id="solo-lock", mode=ClassMode.SOLO, signals=[_live("owner")])
    replaced = analyzer.evaluate(
        session_id="solo-lock",
        mode=ClassMode.SOLO,
        signals=[_live("intruder", timestamp_ms=2_000)],
    )
    assert replaced.training_paused is True
    assert replaced.pause_reason == "original_user_not_present"
    assert replaced.unexpected_participant_ids == ["intruder"]


def test_analyzer_bounds_tracked_sessions():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(max_tracked_sessions=5))
    for index in range(60):
        analyzer.evaluate(
            session_id=f"session-{index}", mode=ClassMode.SOLO, signals=[_live("p")]
        )
    assert len(analyzer._state) <= 5
    assert len(analyzer._no_presence_started_ms) <= 5
    assert len(analyzer._original_participant_id) <= 5


def test_analyzer_keeps_the_active_session_under_eviction_pressure():
    analyzer = WebcamSessionAnalyzer(policy=AnalyzerPolicy(max_tracked_sessions=3))
    analyzer.evaluate(session_id="hot", mode=ClassMode.SOLO, signals=[_live("me")])
    for index in range(20):
        analyzer.evaluate(session_id=f"cold-{index}", mode=ClassMode.SOLO, signals=[_live("me")])
        analyzer.evaluate(session_id="hot", mode=ClassMode.SOLO, signals=[_live("me")])
    assert "hot" in analyzer._state


def test_live_metrics_store_bounds_sessions():
    analyzer = WebcamSessionAnalyzer()
    store = LiveMetricsStore(max_sessions=4)
    for index in range(40):
        session_id = f"metrics-{index}"
        evaluation = analyzer.evaluate(
            session_id=session_id, mode=ClassMode.SOLO, signals=[_live("p")]
        )
        store.record(session_id=session_id, evaluation=evaluation, updated_at_ms=1_000)
    assert len(store._history) <= 4
    assert len(store._last_eval) <= 4
    assert len(store._last_updated_ms) <= 4


def test_voice_agent_bounds_cache_and_session_history():
    agent = XaiVoiceAgent(api_key="", max_cache_entries=10, max_tracked_sessions=6)
    for index in range(200):
        agent.respond(
            learner_message=f"question {index}",
            class_mode=ClassMode.SOLO,
            session_id=f"chat-{index}",
        )
    assert len(agent._response_cache) <= 10
    assert len(agent._session_history) <= 6


def test_voice_cache_is_scoped_per_session(monkeypatch):
    """One learner must never be served another learner's cached reply."""
    agent = XaiVoiceAgent(api_key="test-key", cache_ttl_s=600)
    calls = {"count": 0}

    def _fake_transport(payload: dict, *, timeout_s=None) -> dict:
        calls["count"] += 1
        return {"choices": [{"message": {"content": f"answer-{calls['count']}"}}]}

    monkeypatch.setattr(agent, "_transport", _fake_transport)
    alice = agent.respond(
        learner_message="what is 2+2", class_mode=ClassMode.SOLO, session_id="alice"
    )
    bob = agent.respond(
        learner_message="what is 2+2", class_mode=ClassMode.SOLO, session_id="bob"
    )
    assert alice.message != bob.message
    assert bob.cache_hit is False
    assert calls["count"] == 2


def test_cache_hit_still_records_the_conversational_turn(monkeypatch):
    """A cached reply is a real turn; dropping it corrupts short-session memory."""
    agent = XaiVoiceAgent(api_key="test-key", cache_ttl_s=600)

    def _fake_transport(payload: dict, *, timeout_s=None) -> dict:
        return {"choices": [{"message": {"content": "Same reply."}}]}

    monkeypatch.setattr(agent, "_transport", _fake_transport)
    first = agent.respond(
        learner_message="hello", class_mode=ClassMode.SOLO, session_id="memory-session"
    )
    assert first.cache_hit is False
    history_after_first = len(agent._session_history["memory-session"])

    # Same wording again in the same session: served from cache, still remembered.
    agent._session_history["memory-session"] = []
    repeat = agent.respond(
        learner_message="hello", class_mode=ClassMode.SOLO, session_id="memory-session"
    )
    assert repeat.cache_hit is True
    assert len(agent._session_history["memory-session"]) == history_after_first == 2


def test_orchestrator_respects_zero_sleep_override(tmp_path: Path, monkeypatch):
    """`--sleep-seconds 0` is a valid tight-loop override, not a falsy no-op."""
    runbook_path = tmp_path / "runbook.json"
    runbook_path.write_text(
        json.dumps(
            {
                "loop_sleep_seconds": 900,
                "tasks": [
                    {
                        "task_id": "noop",
                        "description": "noop",
                        "command": ["python3", "-c", "pass"],
                        "cadence_minutes": 1,
                        "timeout_seconds": 10,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    slept: list[float] = []
    monkeypatch.setattr(
        "theodore_webcam_lab.training_orchestrator.time.sleep", lambda s: slept.append(s)
    )

    run_forever(
        runbook_path=runbook_path,
        state_path=tmp_path / "state.json",
        dry_run=True,
        iterations=2,
        sleep_override_seconds=0,
    )
    assert slept == [0]


def test_orchestrator_runbook_and_state_round_trip(tmp_path: Path):
    lab_root = Path(__file__).resolve().parents[1]
    runbook = load_runbook(lab_root / "training" / "vision_training_runbook.json")
    assert runbook.loop_sleep_seconds > 0
    assert any(task.enabled for task in runbook.tasks)
    state = load_state(tmp_path / "missing-state.json")
    assert state["last_run_ms"] == {}
