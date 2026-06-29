"""Tests for rapid_decision module."""
import pytest

from aoep_shared.rapid_decision import (
    DrillAttempt,
    DrillOutcome,
    PressureLevel,
    RapidDecisionAgent,
    RapidDecisionSession,
    allowed_time,
    build_adr,
    get_drill,
    list_drills,
)


@pytest.fixture
def aviation_drill():
    return get_drill("rd_av_01")


@pytest.fixture
def medical_drill():
    return get_drill("rd_med_01")


class TestDrillLibrary:
    def test_all_drills_have_correct_option(self):
        for d in list_drills():
            correct = d.correct_option()
            assert correct is not None, f"Drill {d.drill_id} has no correct option"
            assert correct.is_correct

    def test_all_drills_have_cue_to_spot(self):
        for d in list_drills():
            assert d.cue_to_spot, f"Drill {d.drill_id} missing cue_to_spot"

    def test_filter_by_domain(self):
        av = list_drills(domain="aviation")
        assert all(d.domain == "aviation" for d in av)

    def test_filter_by_skill_tag(self):
        cardiac = list_drills(skill_tag="cardiac_arrest")
        assert all(d.skill_tag == "cardiac_arrest" for d in cardiac)

    def test_get_drill_returns_none_for_unknown(self):
        assert get_drill("nonexistent_999") is None


class TestAllowedTime:
    def test_deliberate_gives_large_window(self, aviation_drill):
        t = allowed_time(aviation_drill, PressureLevel.DELIBERATE)
        assert t >= 20.0

    def test_split_second_gives_tiny_window(self, aviation_drill):
        t = allowed_time(aviation_drill, PressureLevel.SPLIT_SECOND)
        assert t < aviation_drill.ideal_seconds

    def test_wellness_extends_window(self, aviation_drill):
        normal = allowed_time(aviation_drill, PressureLevel.MODERATE)
        stressed = allowed_time(aviation_drill, PressureLevel.MODERATE, wellness_state="stressed")
        assert stressed > normal


class TestDrillAttempt:
    def test_correct_fast_outcome(self, aviation_drill):
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        outcome = attempt.outcome(aviation_drill, allowed_seconds=8.0)
        assert outcome is DrillOutcome.CORRECT_FAST

    def test_correct_slow_outcome(self, aviation_drill):
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=15.0,
            pressure_level=PressureLevel.MODERATE,
        )
        outcome = attempt.outcome(aviation_drill, allowed_seconds=8.0)
        assert outcome is DrillOutcome.CORRECT_SLOW

    def test_incorrect_fast_outcome(self, aviation_drill):
        wrong = next(o for o in aviation_drill.options if not o.is_correct)
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=wrong.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        outcome = attempt.outcome(aviation_drill, allowed_seconds=8.0)
        assert outcome is DrillOutcome.INCORRECT_FAST

    def test_timeout_outcome(self, aviation_drill):
        wrong = next(o for o in aviation_drill.options if not o.is_correct)
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=wrong.label,
            time_taken_s=50.0,
            pressure_level=PressureLevel.MODERATE,
        )
        outcome = attempt.outcome(aviation_drill, allowed_seconds=8.0)
        assert outcome is DrillOutcome.TIMEOUT


class TestBuildADR:
    def test_adr_contains_cue_spotlight(self, aviation_drill):
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        adr = build_adr(aviation_drill, attempt, DrillOutcome.CORRECT_FAST)
        assert aviation_drill.cue_to_spot in adr

    def test_adr_includes_failure_mode(self, aviation_drill):
        wrong = next(o for o in aviation_drill.options if not o.is_correct)
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=wrong.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        adr = build_adr(aviation_drill, attempt, DrillOutcome.INCORRECT_FAST)
        assert aviation_drill.failure_mode in adr


class TestRapidDecisionAgent:
    def setup_method(self):
        self.agent = RapidDecisionAgent()

    def test_list_drills_returns_all(self):
        drills = self.agent.list_drills()
        assert len(drills) >= 5

    def test_evaluate_correct_attempt(self, aviation_drill):
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=3.0,
            pressure_level=PressureLevel.MODERATE,
        )
        result = self.agent.evaluate_attempt(aviation_drill, attempt)
        assert result.outcome in (DrillOutcome.CORRECT_FAST, DrillOutcome.CORRECT_SLOW)

    def test_evaluate_updates_session(self, aviation_drill):
        session = RapidDecisionSession(
            session_id="test_session", pressure_level=PressureLevel.MODERATE
        )
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        self.agent.evaluate_attempt(aviation_drill, attempt, session)
        assert session.total_drills == 1
        assert session.correct_count == 1
        assert session.streak_correct == 1

    def test_session_summary_keys(self, aviation_drill):
        session = RapidDecisionSession(
            session_id="test_session", pressure_level=PressureLevel.MODERATE
        )
        correct = aviation_drill.correct_option()
        attempt = DrillAttempt(
            drill_id=aviation_drill.drill_id,
            chosen_label=correct.label,
            time_taken_s=2.0,
            pressure_level=PressureLevel.MODERATE,
        )
        self.agent.evaluate_attempt(aviation_drill, attempt, session)
        summary = self.agent.session_summary(session)
        assert "accuracy" in summary
        assert "recommended_next_pressure" in summary

    def test_calibrate_increases_pressure_on_high_accuracy(self):
        new_p, reason = self.agent.calibrate_pressure(0.90, PressureLevel.MODERATE)
        assert new_p is PressureLevel.TIME_CRITICAL

    def test_calibrate_decreases_pressure_on_low_accuracy(self):
        new_p, reason = self.agent.calibrate_pressure(0.30, PressureLevel.TIME_CRITICAL)
        assert new_p is PressureLevel.MODERATE

    def test_calibrate_wellness_overrides_to_deliberate(self):
        new_p, reason = self.agent.calibrate_pressure(
            0.95, PressureLevel.SPLIT_SECOND, wellness_state="stressed"
        )
        assert new_p is PressureLevel.DELIBERATE
