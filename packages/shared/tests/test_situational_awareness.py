"""Tests for situational_awareness module."""
import pytest

from aoep_shared.situational_awareness import (
    DECIDEPhase,
    DECIDEState,
    DECIDETrainer,
    OODAPhase,
    OODAState,
    OODATrainer,
    Scenario,
    SituationalAwarenessAgent,
    get_scenario,
    list_scenarios,
)


@pytest.fixture
def aviation_scenario():
    return get_scenario("sa_av_01")


@pytest.fixture
def medical_scenario():
    return get_scenario("sa_med_01")


class TestScenarioLibrary:
    def test_all_scenarios_have_cues(self):
        for s in list_scenarios():
            assert len(s.cues) > 0, f"Scenario {s.scenario_id} has no cues"

    def test_all_scenarios_have_correct_decision(self):
        for s in list_scenarios():
            assert s.correct_decision, f"Scenario {s.scenario_id} missing correct_decision"

    def test_filter_by_domain(self):
        aviation = list_scenarios("aviation")
        assert all(s.domain == "aviation" for s in aviation)

    def test_get_scenario_returns_none_for_unknown(self):
        assert get_scenario("nonexistent_999") is None

    def test_aviation_scenario_loaded(self, aviation_scenario):
        assert aviation_scenario is not None
        assert aviation_scenario.scenario_id == "sa_av_01"
        assert aviation_scenario.time_pressure_seconds == 120


class TestOODATrainer:
    def setup_method(self):
        self.trainer = OODATrainer()

    def test_prompt_observe_includes_scenario_description(self, aviation_scenario):
        prompt = self.trainer.prompt_for_phase(OODAPhase.OBSERVE, aviation_scenario)
        assert "OBSERVE" in prompt
        assert aviation_scenario.description[:30] in prompt

    def test_stressed_learner_observe_prompt_simplified(self, aviation_scenario):
        prompt = self.trainer.prompt_for_phase(
            OODAPhase.OBSERVE, aviation_scenario, wellness_state="stressed"
        )
        assert "single most important" in prompt

    def test_evaluate_observe_catches_critical_cues(self, aviation_scenario):
        state = OODAState()
        # Mention carb ice, EGT, and OAT
        learner_text = "I notice engine roughness and EGT rising 50 degrees and OAT is minus five"
        score, missed = self.trainer.evaluate_observe(state, aviation_scenario, learner_text)
        assert score > 0.0
        assert isinstance(missed, list)

    def test_evaluate_observe_penalises_missed_cues(self, aviation_scenario):
        state = OODAState()
        score, missed = self.trainer.evaluate_observe(state, aviation_scenario, "nothing unusual")
        assert score == 0.0 or len(missed) > 0

    def test_evaluate_decide_correct_answer_scores_well(self, aviation_scenario):
        state = OODAState()
        answer = "I would apply carburetor heat immediately and monitor the engine and declare precautionary"
        score = self.trainer.evaluate_decide(state, aviation_scenario, answer)
        assert score > 0.0

    def test_final_result_structure(self, aviation_scenario):
        state = OODAState(phase_scores={"observe": 0.8, "decide": 0.7})
        state.missed_critical = []
        result = self.trainer.final_result(state, aviation_scenario)
        assert 0.0 <= result.overall_score <= 1.0
        assert result.framework == "ooda"
        assert result.scenario_id == aviation_scenario.scenario_id


class TestDECIDETrainer:
    def setup_method(self):
        self.trainer = DECIDETrainer()

    def test_prompt_for_each_phase(self, medical_scenario):
        for phase in DECIDEPhase:
            prompt = self.trainer.prompt_for_phase(phase, medical_scenario)
            assert len(prompt) > 10

    def test_score_choose_higher_with_alternatives(self, medical_scenario):
        state = DECIDEState()
        multi = "I could either start CPR or alternatively call for help first or do both"
        single = "I will start CPR"
        score_multi = self.trainer.score_phase(DECIDEPhase.CHOOSE, multi, medical_scenario)
        score_single = self.trainer.score_phase(DECIDEPhase.CHOOSE, single, medical_scenario)
        assert score_multi >= score_single

    def test_final_result_includes_coaching(self, medical_scenario):
        state = DECIDEState(phase_scores={"detect": 0.4, "estimate": 0.3})
        result = self.trainer.final_result(state, medical_scenario)
        assert result.coaching_notes
        assert result.scenario_id == medical_scenario.scenario_id


class TestSituationalAwarenessAgent:
    def setup_method(self):
        self.agent = SituationalAwarenessAgent()

    def test_list_scenarios_returns_all(self):
        scenarios = self.agent.list_scenarios()
        assert len(scenarios) >= 3

    def test_list_scenarios_filtered_by_domain(self):
        av = self.agent.list_scenarios("aviation")
        assert all(s.domain == "aviation" for s in av)

    def test_ooda_prompt_returns_string(self):
        s = self.agent.get_scenario("sa_av_01")
        prompt = self.agent.ooda_prompt(OODAPhase.OBSERVE, s)
        assert isinstance(prompt, str)
        assert len(prompt) > 5

    def test_decide_prompt_returns_string(self):
        s = self.agent.get_scenario("sa_med_01")
        prompt = self.agent.decide_prompt(DECIDEPhase.DETECT, s)
        assert isinstance(prompt, str)

    def test_ooda_full_flow(self):
        scenario = self.agent.get_scenario("sa_av_01")
        state = OODAState()
        score, missed = self.agent.ooda_evaluate_observe(
            state, scenario,
            "I see engine roughness and EGT rising and the OAT is very cold minus five degrees"
        )
        decide_score = self.agent.ooda_evaluate_decide(
            state, scenario,
            "I will apply carburetor heat immediately and monitor and declare precautionary landing"
        )
        result = self.agent.ooda_result(state, scenario)
        assert 0.0 <= result.overall_score <= 1.0

    def test_decide_full_flow(self):
        scenario = self.agent.get_scenario("sa_med_01")
        state = DECIDEState()
        for phase in DECIDEPhase:
            score = self.agent.decide_score_phase(phase, state, scenario, f"answer for {phase.value}")
            assert 0.0 <= score <= 1.0
        result = self.agent.decide_result(state, scenario)
        assert result.framework == "decide"
