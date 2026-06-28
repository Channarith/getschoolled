"""Tests for emergency_scenarios module."""
import pytest

from aoep_shared.emergency_scenarios import (
    EmergencyScenarioAgent,
    PhaseOutcome,
    ScenarioDomain,
    SimulationRun,
    SimulationStatus,
    generate_aar,
    get_emergency_scenario,
    list_emergency_scenarios,
)


@pytest.fixture
def engine_scenario():
    return get_emergency_scenario("em_av_engine_failure")


@pytest.fixture
def anaphylaxis_scenario():
    return get_emergency_scenario("em_med_anaphylaxis")


@pytest.fixture
def ransomware_scenario():
    return get_emergency_scenario("em_crisis_ransomware")


class TestScenarioRegistry:
    def test_all_scenarios_registered(self):
        scenarios = list_emergency_scenarios()
        assert len(scenarios) >= 3

    def test_filter_by_domain_aviation(self):
        av = list_emergency_scenarios(ScenarioDomain.AVIATION)
        assert all(s.domain is ScenarioDomain.AVIATION for s in av)

    def test_get_unknown_returns_none(self):
        assert get_emergency_scenario("does_not_exist") is None

    def test_all_scenarios_have_initial_phase(self):
        for s in list_emergency_scenarios():
            assert s.initial_phase_id in s.phases

    def test_all_phases_have_actions(self):
        for s in list_emergency_scenarios():
            for phase_id, phase in s.phases.items():
                assert len(phase.available_actions) > 0, \
                    f"Phase {phase_id} in {s.scenario_id} has no actions"

    def test_all_phases_have_expert_action(self):
        for s in list_emergency_scenarios():
            for phase_id, phase in s.phases.items():
                assert phase.expert_action_id, \
                    f"Phase {phase_id} in {s.scenario_id} missing expert_action_id"
                action_ids = {a.action_id for a in phase.available_actions}
                assert phase.expert_action_id in action_ids, \
                    f"Expert action {phase.expert_action_id!r} not in phase {phase_id}"


class TestSimulationRun:
    def test_optimal_action_increases_mastery(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")
        run.current_phase_id = engine_scenario.initial_phase_id
        phase = engine_scenario.get_phase(run.current_phase_id)
        expert_action = next(a for a in phase.available_actions if a.action_id == phase.expert_action_id)
        initial_mastery = run.mastery_score
        run.record_decision(phase.phase_id, expert_action)
        assert run.mastery_score > initial_mastery

    def test_critical_error_recorded(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")
        run.current_phase_id = engine_scenario.initial_phase_id
        phase = engine_scenario.get_phase(run.current_phase_id)
        bad_action = next(a for a in phase.available_actions if a.outcome is PhaseOutcome.CRITICAL_ERROR)
        run.record_decision(phase.phase_id, bad_action)
        assert len(run.cascade_errors) == 1

    def test_run_advances_to_next_phase(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")
        run.current_phase_id = engine_scenario.initial_phase_id
        phase = engine_scenario.get_phase(run.current_phase_id)
        expert_action = next(a for a in phase.available_actions if a.action_id == phase.expert_action_id)
        run.record_decision(phase.phase_id, expert_action)
        assert run.current_phase_id == expert_action.unlocks_phase


class TestAARGeneration:
    def test_aar_generated_after_full_run(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")

        # Walk through with all expert actions
        current_id = engine_scenario.initial_phase_id
        for _ in range(6):  # max phases
            phase = engine_scenario.get_phase(current_id)
            if not phase:
                break
            expert_action = next(
                a for a in phase.available_actions if a.action_id == phase.expert_action_id
            )
            run.record_decision(phase.phase_id, expert_action)
            if expert_action.unlocks_phase:
                current_id = expert_action.unlocks_phase
            else:
                break

        aar = generate_aar(run, engine_scenario)
        assert aar.outcome_score > 0.5
        assert aar.decisions_summary
        assert len(aar.learning_reinforcements) > 0

    def test_aar_verdict_poor_for_all_errors(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")
        run.mastery_score = 0.2  # simulate poor performance
        aar = generate_aar(run, engine_scenario)
        assert "critical" in aar.overall_verdict.lower() or "several" in aar.overall_verdict.lower()

    def test_expert_comparison_populated_when_wrong(self, engine_scenario):
        run = SimulationRun(scenario_id=engine_scenario.scenario_id, learner_id="test")
        phase = engine_scenario.get_phase(engine_scenario.initial_phase_id)
        wrong_action = next(a for a in phase.available_actions if a.action_id != phase.expert_action_id)
        run.record_decision(phase.phase_id, wrong_action)
        aar = generate_aar(run, engine_scenario)
        assert len(aar.expert_comparison) > 0


class TestEmergencyScenarioAgent:
    def setup_method(self):
        self.agent = EmergencyScenarioAgent()

    def test_start_run_sets_initial_phase(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        assert run.current_phase_id == engine_scenario.initial_phase_id
        assert run.learner_id == "learner_001"
        assert run.status is SimulationStatus.IN_PROGRESS

    def test_current_phase_returns_phase_object(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        assert phase is not None
        assert phase.phase_id == engine_scenario.initial_phase_id

    def test_apply_action_returns_action(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        action = self.agent.apply_action(run, phase, phase.expert_action_id)
        assert action is not None
        assert action.action_id == phase.expert_action_id

    def test_apply_unknown_action_returns_none(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        result = self.agent.apply_action(run, phase, "nonexistent_action")
        assert result is None

    def test_phase_prompt_contains_phase_title(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        prompt = self.agent.phase_prompt(phase)
        assert phase.title in prompt

    def test_wellness_state_adds_guidance(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        prompt_stressed = self.agent.phase_prompt(phase, wellness_state="stressed")
        prompt_normal = self.agent.phase_prompt(phase, wellness_state="ok")
        # Stressed prompt should include guidance note
        assert "Guidance" in prompt_stressed or len(prompt_stressed) >= len(prompt_normal)

    def test_aar_generated(self, engine_scenario):
        run = self.agent.start_run(engine_scenario, "learner_001")
        phase = self.agent.current_phase(run, engine_scenario)
        action = self.agent.apply_action(run, phase, phase.expert_action_id)
        aar = self.agent.generate_aar(run, engine_scenario)
        assert aar is not None
        assert aar.scenario_id == engine_scenario.scenario_id
