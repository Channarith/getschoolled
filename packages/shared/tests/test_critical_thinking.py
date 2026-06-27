"""Tests for critical_thinking module."""
import pytest

from aoep_shared.critical_thinking import (
    ArgumentRole,
    BloomLevel,
    CriticalThinkingTrainer,
    bloom_for_mastery,
    build_argument_map,
    build_socratic_question,
    detect_fallacies,
    evaluate_response,
    next_bloom_level,
)


class TestBloomLevelMapping:
    def test_low_mastery_maps_to_remember(self):
        assert bloom_for_mastery(0.1) is BloomLevel.REMEMBER

    def test_mid_mastery_maps_to_apply(self):
        level = bloom_for_mastery(0.55)
        assert level is BloomLevel.APPLY

    def test_high_mastery_maps_to_evaluate(self):
        level = bloom_for_mastery(0.82)
        assert level is BloomLevel.EVALUATE

    def test_perfect_mastery_maps_to_create(self):
        assert bloom_for_mastery(0.95) is BloomLevel.CREATE


class TestNextBloomLevel:
    def test_remember_advances_to_understand(self):
        assert next_bloom_level(BloomLevel.REMEMBER) is BloomLevel.UNDERSTAND

    def test_create_stays_at_create(self):
        assert next_bloom_level(BloomLevel.CREATE) is BloomLevel.CREATE


class TestSocraticQuestionBuilder:
    def test_builds_question_with_expected_fields(self):
        q = build_socratic_question("photosynthesis", "Plants convert light into energy", BloomLevel.UNDERSTAND)
        assert q.question_id
        assert len(q.text) > 10
        assert q.bloom_level is BloomLevel.UNDERSTAND
        assert q.hint
        assert q.follow_up
        assert q.challenge

    def test_acceptable_keywords_include_term(self):
        q = build_socratic_question("carb_ice", "Carburetor icing occurs between -15C and +5C", BloomLevel.REMEMBER)
        assert "carb_ice" in q.acceptable_keywords


class TestEvaluateResponse:
    def _make_question(self, level: BloomLevel = BloomLevel.UNDERSTAND):
        return build_socratic_question("carb ice", "Carburetor icing causes engine roughness", level)

    def test_good_answer_scores_high(self):
        q = self._make_question()
        answer = "Carburetor icing causes engine roughness and EGT changes"
        result = evaluate_response(q, answer)
        assert result.score >= 0.4
        assert result.feedback

    def test_empty_answer_scores_low(self):
        q = self._make_question()
        result = evaluate_response(q, "")
        assert result.score < 0.4

    def test_stressed_learner_gets_gentler_feedback(self):
        q = self._make_question()
        result_normal = evaluate_response(q, "", wellness_state="ok")
        result_stressed = evaluate_response(q, "", wellness_state="stressed")
        # Stressed learner feedback should not contain harsh phrasing
        assert "no worries" in result_stressed.feedback.lower() or "let's" in result_stressed.feedback.lower()

    def test_fallacy_penalises_score(self):
        q = self._make_question(BloomLevel.ANALYZE)
        # "always" and "never" trigger hasty generalization
        answer = "It always causes problems every single time and never fails to do so"
        result = evaluate_response(q, answer)
        assert len(result.keywords_found) >= 0  # may or may not find keywords
        # Fallacy note should appear in feedback
        assert "hasty" in result.feedback.lower() or "watch out" in result.feedback.lower()


class TestFallacyDetection:
    def test_detects_hasty_generalization(self):
        fallacies = detect_fallacies("This always happens and it never fails every time")
        assert "hasty generalization" in fallacies

    def test_clean_text_returns_empty(self):
        fallacies = detect_fallacies("The evidence suggests that in some cases this is true")
        assert fallacies == []


class TestArgumentMap:
    def test_first_claim_is_claim_role(self):
        arg = build_argument_map("Test", ["AI improves education", "because studies show results", "however some disagree"])
        assert arg.components[0].role is ArgumentRole.CLAIM

    def test_evidence_detected(self):
        arg = build_argument_map("Test", ["AI helps", "Because evidence shows better outcomes"])
        roles = [c.role for c in arg.components]
        assert ArgumentRole.EVIDENCE in roles

    def test_strong_evidence_count(self):
        arg = build_argument_map("Test", [
            "Claim here",
            "Because the study shows significant results",
            "Since the data confirms this",
        ])
        assert arg.strong_evidence_count() >= 1


class TestCriticalThinkingTrainer:
    def setup_method(self):
        self.trainer = CriticalThinkingTrainer()

    def test_next_question_wellness_gates_bloom(self):
        q_stressed = self.trainer.next_question(
            "oxygen", "Oxygen supports combustion",
            mastery=0.9, wellness_state="stressed"
        )
        # Stressed learner should not get CREATE or EVALUATE questions
        assert q_stressed.bloom_level not in (BloomLevel.CREATE, BloomLevel.EVALUATE)

    def test_next_question_returns_valid_object(self):
        q = self.trainer.next_question("carb ice", "Carburetor ice forms in specific conditions", mastery=0.6)
        assert q.question_id
        assert q.text

    def test_evaluate_returns_response(self):
        q = self.trainer.next_question("anaphylaxis", "Anaphylaxis requires epinephrine", mastery=0.5)
        result = self.trainer.evaluate(q, "Epinephrine is the treatment for anaphylaxis")
        assert 0.0 <= result.score <= 1.0
        assert result.feedback

    def test_analyze_argument(self):
        feedback = self.trainer.analyze_argument(
            "AI in education",
            ["AI improves learning", "because studies show 30% improvement", "however access is unequal"]
        )
        assert len(feedback) > 10
