"""Tests for mental_readiness module."""
import pytest

from aoep_shared.mental_readiness import (
    CognitivePressure,
    MentalReadinessAgent,
    ReadinessExercise,
    StressInoculationSession,
    ThreatCategory,
    analyse_threats,
    build_failure_mode_cards,
    format_rehearsal,
    get_rehearsal_script,
    regulation_check_in,
    run_pre_mortem,
)


class TestRegulationCheckIn:
    def test_high_stress_recommends_grounding(self):
        result = regulation_check_in(9, 5)
        assert result.recommended_exercise is ReadinessExercise.GROUNDING_BREATH

    def test_low_focus_recommends_grounding(self):
        result = regulation_check_in(5, 2)
        assert result.recommended_exercise is ReadinessExercise.GROUNDING_BREATH

    def test_moderate_recommends_rehearsal(self):
        result = regulation_check_in(6, 5)
        assert result.recommended_exercise is ReadinessExercise.MENTAL_REHEARSAL

    def test_optimal_recommends_pre_mortem(self):
        result = regulation_check_in(3, 8)
        assert result.recommended_exercise is ReadinessExercise.PRE_MORTEM

    def test_stressed_wellness_state_overrides(self):
        result = regulation_check_in(3, 8, wellness_state="stressed")
        assert result.recommended_exercise is ReadinessExercise.GROUNDING_BREATH

    def test_breath_cue_always_present(self):
        for stress in (2, 5, 8):
            for focus in (2, 5, 9):
                result = regulation_check_in(stress, focus)
                assert result.breath_cue


class TestPreMortem:
    def test_few_failure_modes_flags_residual(self):
        result = run_pre_mortem("Deploy new system", ["network might fail"])
        assert any("brainstorming" in r.lower() for r in result.residual_risks)

    def test_mitigations_generated_for_each_mode(self):
        modes = ["communication breakdown", "time pressure", "equipment failure"]
        result = run_pre_mortem("Emergency procedure", modes)
        assert len(result.mitigations) == len(modes)

    def test_wellness_adds_residual_note(self):
        result = run_pre_mortem("Plan", ["failure one", "failure two", "failure three"],
                                wellness_state="stressed")
        assert any("stress" in r.lower() or "wellness" in r.lower() for r in result.residual_risks)

    def test_confidence_adjustment_negative(self):
        result = run_pre_mortem("Any plan", ["f1", "f2", "f3", "f4", "f5"])
        assert result.confidence_adjustment < 0.0


class TestFailureModeCards:
    def test_engine_component_gets_catastrophic_card(self):
        cards = build_failure_mode_cards("Aviation Emergency", ["engine", "radio communication"])
        engine_card = next((c for c in cards if "engine" in c.component.lower()), None)
        assert engine_card is not None
        assert engine_card.severity == "catastrophic"

    def test_each_component_gets_a_card(self):
        components = ["engine", "radio", "fuel system"]
        cards = build_failure_mode_cards("Test", components)
        assert len(cards) == len(components)

    def test_all_cards_have_mitigation(self):
        cards = build_failure_mode_cards("Test", ["network", "medication"])
        for card in cards:
            assert card.mitigation


class TestMentalRehearsal:
    def test_engine_failure_script_exists(self):
        script = get_rehearsal_script("engine_failure_landing")
        assert script is not None
        assert len(script.steps) >= 5
        assert script.success_image

    def test_anaphylaxis_script_exists(self):
        script = get_rehearsal_script("anaphylaxis_response")
        assert script is not None

    def test_unknown_key_returns_none(self):
        assert get_rehearsal_script("nonexistent") is None

    def test_format_rehearsal_includes_steps(self):
        script = get_rehearsal_script("engine_failure_landing")
        text = format_rehearsal(script)
        for i, step in enumerate(script.steps, 1):
            assert str(i) in text

    def test_stressed_format_excludes_decision_gates(self):
        script = get_rehearsal_script("engine_failure_landing")
        normal = format_rehearsal(script, wellness_state="ok")
        stressed = format_rehearsal(script, wellness_state="stressed")
        assert "Decision gates" in normal
        assert "Decision gates" not in stressed


class TestStressInoculation:
    def test_advance_level_on_high_accuracy(self):
        session = StressInoculationSession(learner_id="t", domain="aviation", current_level=2)
        for _ in range(3):
            advanced, msg = session.advance_level(0.90)
        assert advanced
        assert session.current_level == 3

    def test_regress_level_on_low_accuracy(self):
        session = StressInoculationSession(learner_id="t", domain="aviation", current_level=3)
        session.advance_level(0.30)
        assert session.current_level == 2

    def test_does_not_exceed_level_5(self):
        session = StressInoculationSession(learner_id="t", domain="aviation", current_level=5)
        session.sessions_at_level = 2
        for _ in range(5):
            session.advance_level(0.95)
        assert session.current_level <= 5


class TestTEMAnalysis:
    def test_environmental_threat_categorised(self):
        result = analyse_threats("Windy conditions with poor visibility", ["strong winds", "low visibility"])
        cats = {t.category for t in result.threats_identified}
        assert ThreatCategory.ENVIRONMENTAL in cats

    def test_human_factors_always_flagged_as_gap(self):
        result = analyse_threats("Standard operation", ["equipment malfunction"])
        # Human factors not mentioned — should appear in undetected
        assert any("human" in u.lower() for u in result.undetected_threats)

    def test_time_pressure_creates_error_trap(self):
        result = analyse_threats("Rushed deployment with time constraints", ["system failure"])
        assert any("time" in e.lower() for e in result.error_traps)


class TestMentalReadinessAgent:
    def setup_method(self):
        self.agent = MentalReadinessAgent()

    def test_check_in_high_stress_grounding(self):
        result = self.agent.check_in(9, 4)
        assert result.recommended_exercise is ReadinessExercise.GROUNDING_BREATH

    def test_cognitive_pressure_stressed_is_restorative(self):
        p = self.agent.cognitive_pressure("stressed", 0.8)
        assert p is CognitivePressure.RESTORATIVE

    def test_cognitive_pressure_high_mastery_ok_wellness(self):
        p = self.agent.cognitive_pressure("ok", 0.9)
        assert p is CognitivePressure.HIGH

    def test_recommend_exercise_avoids_recent(self):
        recent = [ReadinessExercise.PRE_MORTEM, ReadinessExercise.FAILURE_MODE]
        ex = self.agent.recommend_exercise("ok", 0.7, recent)
        assert ex not in recent or ex is ReadinessExercise.MENTAL_REHEARSAL

    def test_rehearsal_prompt_returns_string(self):
        prompt = self.agent.rehearsal_prompt("engine_failure_landing")
        assert "Engine Failure" in prompt

    def test_rehearsal_prompt_unknown_key(self):
        prompt = self.agent.rehearsal_prompt("unknown_key")
        assert "unknown_key" in prompt

    def test_pre_mortem_runs(self):
        result = self.agent.run_pre_mortem(
            "Land aircraft in emergency",
            ["engine failure", "weather deterioration", "wrong field selection", "radio failure"]
        )
        assert len(result.mitigations) == 4

    def test_analyse_threats_runs(self):
        result = self.agent.analyse_threats(
            "Night flight in deteriorating weather",
            ["fatigue", "weather deterioration", "equipment unfamiliarity"]
        )
        assert result.feedback
        assert len(result.threats_identified) == 3
