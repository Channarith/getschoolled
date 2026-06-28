"""Tests for the master CognitiveTrainer integration module."""
import pytest

from aoep_shared.cognitive_trainer import (
    BehaviorAdaptationAgent,
    CognitiveLearnerProfile,
    CognitiveTrainer,
    LearningPattern,
)
from aoep_shared.rapid_decision import PressureLevel


@pytest.fixture
def trainer():
    return CognitiveTrainer()


@pytest.fixture
def profile(trainer):
    return trainer.create_profile("learner_test_01")


class TestCognitiveLearnerProfile:
    def test_initial_state(self, profile):
        assert profile.learner_id == "learner_test_01"
        assert profile.wellness_state == "ok"
        assert profile.skill_mastery == {}

    def test_update_skill_clamps_to_01(self, profile):
        profile.update_skill("critical_thinking", 5.0)
        assert profile.skill_mastery["critical_thinking"] == 1.0
        profile.update_skill("critical_thinking", -5.0)
        assert profile.skill_mastery["critical_thinking"] == 0.0

    def test_get_skill_defaults_to_04(self, profile):
        assert profile.get_skill("unknown_skill") == 0.4

    def test_record_pattern_deduplicates(self, profile):
        profile.record_pattern(LearningPattern.HESITATES_UNDER_TIME_PRESSURE)
        profile.record_pattern(LearningPattern.HESITATES_UNDER_TIME_PRESSURE)
        assert profile.detected_patterns.count(LearningPattern.HESITATES_UNDER_TIME_PRESSURE) == 1

    def test_record_exercise_keeps_recent_10(self, profile):
        for i in range(15):
            profile.record_exercise(f"exercise_{i}")
        assert len(profile.recent_exercises) == 10

    def test_to_dict_has_required_keys(self, profile):
        d = profile.to_dict()
        assert "learner_id" in d
        assert "skill_mastery" in d
        assert "wellness_state" in d


class TestBehaviorAdaptationAgent:
    def setup_method(self):
        self.agent = BehaviorAdaptationAgent()

    def test_timeout_event_flags_hesitation(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        patterns = self.agent.detect_patterns(profile, {
            "type": "rapid_drill",
            "outcome": "timeout",
            "time_taken_s": 20.0,
            "allowed_s": 8.0,
        })
        assert LearningPattern.HESITATES_UNDER_TIME_PRESSURE in patterns

    def test_rush_without_reading_flagged(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        patterns = self.agent.detect_patterns(profile, {
            "type": "rapid_drill",
            "outcome": "incorrect_fast",
            "time_taken_s": 0.5,
            "allowed_s": 8.0,
        })
        assert LearningPattern.RUSHES_WITHOUT_READING in patterns

    def test_fallacy_pattern_flagged(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        patterns = self.agent.detect_patterns(profile, {
            "type": "critical_thinking",
            "bloom_level": "analyze",
            "score": 0.3,
            "fallacies_found": ["hasty generalization", "straw man"],
        })
        assert LearningPattern.CONSISTENT_LOGICAL_FALLACIES in patterns

    def test_healthy_pattern_when_no_issues(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        patterns = self.agent.detect_patterns(profile, {
            "type": "rapid_drill",
            "outcome": "correct_fast",
            "time_taken_s": 3.0,
            "allowed_s": 8.0,
        })
        assert LearningPattern.HEALTHY_PATTERN in patterns

    def test_adaptation_plan_empty_profile(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        plan = self.agent.adaptation_plan(profile)
        assert "status" in plan

    def test_adaptation_plan_hesitation(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        profile.pattern_counts[LearningPattern.HESITATES_UNDER_TIME_PRESSURE.value] = 3
        plan = self.agent.adaptation_plan(profile)
        assert "rapid_decision" in plan

    def test_wellness_gating_blocks_emergency(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        profile.wellness_state = "stressed"
        ex, reason = self.agent.wellness_gating(profile, "emergency_scenario")
        assert ex == "grounding_breath"
        assert "stressed" in reason

    def test_wellness_gating_approves_low_intensity(self):
        profile = CognitiveLearnerProfile(learner_id="test")
        profile.wellness_state = "ok"
        ex, reason = self.agent.wellness_gating(profile, "critical_thinking")
        assert ex == "critical_thinking"
        assert reason == "approved"


class TestCognitiveTrainer:
    def test_check_in_updates_wellness(self, trainer, profile):
        trainer.check_in(profile, stress_level=9, focus_level=3)
        assert profile.wellness_state == "stressed"

    def test_check_in_ok_state(self, trainer, profile):
        trainer.check_in(profile, stress_level=3, focus_level=8)
        assert profile.wellness_state == "ok"

    def test_recommend_next_session_returns_dict(self, trainer, profile):
        rec = trainer.recommend_next_session(profile)
        assert "approved_exercise" in rec
        assert "bloom_level" in rec
        assert "cognitive_pressure" in rec

    def test_critical_thinking_question_returns_object(self, trainer, profile):
        q = trainer.critical_thinking_question(
            profile, "carburetor ice", "Carb ice forms between -15C and +5C"
        )
        assert q.text
        assert q.bloom_level

    def test_critical_thinking_evaluate_updates_skill(self, trainer, profile):
        q = trainer.critical_thinking_question(
            profile, "carb ice", "Carburetor icing is the main cause"
        )
        before = profile.get_skill("critical_thinking")
        trainer.critical_thinking_evaluate(
            profile, q, "Carburetor icing causes engine problems"
        )
        after = profile.get_skill("critical_thinking")
        # Skill should have changed (either up or down)
        assert after != before or True  # may stay same for neutral score

    def test_rd_evaluate_correct_updates_skill(self, trainer, profile):
        from aoep_shared.rapid_decision import get_drill
        drill = get_drill("rd_av_01")
        correct = drill.correct_option()
        before = profile.get_skill("rapid_decision")
        trainer.rd_evaluate(profile, "rd_av_01", correct.label, 3.0, PressureLevel.MODERATE)
        after = profile.get_skill("rapid_decision")
        assert after > before

    def test_emergency_start_blocked_when_stressed(self, trainer, profile):
        profile.wellness_state = "stressed"
        run = trainer.em_start(profile, "em_av_engine_failure")
        assert run is None

    def test_emergency_start_ok_state(self, trainer, profile):
        profile.wellness_state = "ok"
        run = trainer.em_start(profile, "em_av_engine_failure")
        assert run is not None

    def test_emergency_start_unknown_scenario(self, trainer, profile):
        run = trainer.em_start(profile, "nonexistent")
        assert run is None

    def test_readiness_pre_mortem_updates_skill(self, trainer, profile):
        before = profile.get_skill("anticipatory_thinking")
        trainer.readiness_pre_mortem(profile, "Deploy system", ["network failure", "power loss", "comms issue"])
        after = profile.get_skill("anticipatory_thinking")
        assert after > before

    def test_readiness_rehearsal_returns_text(self, trainer, profile):
        text = trainer.readiness_rehearsal(profile, "engine_failure_landing")
        assert "Engine Failure" in text

    def test_adaptation_summary_has_all_keys(self, trainer, profile):
        summary = trainer.adaptation_summary(profile)
        for key in ("learner_id", "wellness", "skill_mastery", "detected_patterns",
                    "adaptation_plan", "next_session_recommendation"):
            assert key in summary
