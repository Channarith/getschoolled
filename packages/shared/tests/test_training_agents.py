"""Cognitive training agents: scenarios, the five agents, engine, and lab."""

import pytest

from aoep_shared.schemas import ClassType
from aoep_shared.training_agents import (
    CriticalThinkingAgent,
    LearningBehaviorAgent,
    RapidDecisionAgent,
    SituationalAwarenessAgent,
    TrainingSession,
    get_scenario,
    list_scenarios,
    run_training_agents_lab,
)


def _flagship():
    sc = get_scenario("engine-out-emergency-landing")
    assert sc is not None
    return sc


# --------------------------------------------------------------------------- #
# Scenario registry
# --------------------------------------------------------------------------- #
def test_registry_has_flagship_and_links_phases():
    ids = {s.id for s in list_scenarios()}
    assert "engine-out-emergency-landing" in ids
    sc = _flagship()
    assert len(sc.phases) >= 4
    # Linear chaining resolves for every phase except the last.
    for ph in sc.phases[:-1]:
        assert sc.next_phase_id(ph.id) is not None
    assert sc.next_phase_id(sc.phases[-1].id) is None
    # Each phase has exactly one textbook-correct, top-scoring option.
    for ph in sc.phases:
        best = ph.best_option()
        assert best.score == pytest.approx(1.0)
        assert any(o.is_correct for o in ph.options)


# --------------------------------------------------------------------------- #
# Situational awareness
# --------------------------------------------------------------------------- #
def test_situational_awareness_scores_recall():
    ph = _flagship().first_phase()
    agent = SituationalAwarenessAgent()
    pic = agent.assess(ph)
    assert pic.perception and pic.projection
    assert pic.sa_score is None  # no learner recall provided

    # Mention the engine/prop and altitude cues -> partial recall, with misses.
    scored = agent.assess(ph, noticed=["the engine and prop went quiet", "altitude"])
    assert scored.sa_score is not None
    assert 0.0 < scored.sa_score <= 1.0
    assert len(scored.missed_cues) < len(ph.cues)


# --------------------------------------------------------------------------- #
# Rapid decision (speed matters)
# --------------------------------------------------------------------------- #
def test_rapid_decision_penalizes_slowness():
    ph = _flagship().first_phase()
    correct = ph.best_option()
    agent = RapidDecisionAgent()
    fast = agent.score(ph, correct, elapsed_s=ph.decision_window_s / 2)
    slow = agent.score(ph, correct, elapsed_s=ph.decision_window_s * 3)
    assert fast.on_time and not slow.on_time
    assert fast.score > slow.score
    assert fast.quality == slow.quality == pytest.approx(1.0)


def test_rapid_decision_fast_but_wrong_is_low():
    ph = _flagship().first_phase()
    worst = min(ph.options, key=lambda o: o.score)
    res = RapidDecisionAgent().score(ph, worst, elapsed_s=1.0)
    assert res.on_time
    assert res.score < 0.4  # speed cannot rescue a bad decision


# --------------------------------------------------------------------------- #
# Critical thinking
# --------------------------------------------------------------------------- #
def test_critical_thinking_flags_emotional_and_absolute_language():
    ph = _flagship().first_phase()
    opt = ph.best_option()
    review = CriticalThinkingAgent().evaluate(
        ph, opt, "I always just panic and go with my gut feeling."
    )
    joined = " ".join(review.detected_issues)
    assert "emotional" in joined
    assert "overgeneralization" in joined
    assert review.emotional_markers >= 1
    assert review.socratic_probe


def test_critical_thinking_rewards_grounded_causal_reasoning():
    ph = _flagship().first_phase()
    opt = ph.best_option()
    weak = CriticalThinkingAgent().evaluate(ph, opt, "ok")
    strong = CriticalThinkingAgent().evaluate(
        ph, opt,
        "I lower the nose to hold best glide airspeed because the prop is "
        "windmilling and altitude is bleeding; instead of fixating on the engine I "
        "fly the aircraft first.",
    )
    assert strong.reasoning_score > weak.reasoning_score
    assert strong.rubric["evidence"] > 0
    assert strong.strengths


def test_critical_thinking_empty_rationale_scores_zero():
    ph = _flagship().first_phase()
    review = CriticalThinkingAgent().evaluate(ph, ph.best_option(), "")
    assert review.reasoning_score == 0.0
    assert review.detected_issues


# --------------------------------------------------------------------------- #
# Learning behavior adaptation
# --------------------------------------------------------------------------- #
def test_learning_behavior_supports_struggling_and_stretches_strong():
    agent = LearningBehaviorAgent()
    struggling = agent.adapt(
        scores=[0.2, 0.1, 0.2], timeliness=[0.5, 0.4, 0.5],
        reasoning_scores=[0.1, 0.2, 0.1], frustration_markers=2,
    )
    assert struggling.tone == "supportive"
    assert struggling.coaching_style == "scaffold"
    assert struggling.window_scale > 1.0
    assert "overload_detected" in struggling.flags or "struggling" in struggling.flags

    strong = agent.adapt(
        scores=[1.0, 0.9, 1.0], timeliness=[1.0, 1.0, 1.0],
        reasoning_scores=[0.9, 0.9, 0.9], frustration_markers=0,
    )
    assert strong.coaching_style == "stretch"
    assert strong.window_scale < 1.0
    assert "on_a_roll" in strong.flags


# --------------------------------------------------------------------------- #
# Engine: full run
# --------------------------------------------------------------------------- #
def test_engine_full_correct_run_passes():
    sc = _flagship()
    session = TrainingSession(scenario=sc, class_type=ClassType.SOLO)
    while not session.done:
        brief = session.brief()
        assert brief.premortem.risks
        assert brief.situation_picture.projection
        best = sc.phase(brief.phase_id).best_option()
        session.decide(best.id, elapsed_s=2.0, rationale=(
            "Reading the cues, this is the textbook action because it keeps me "
            "ahead of the aircraft; the alternative is worse."
        ))
    summary = session.summary()
    assert summary["completed"] is True
    assert summary["passed"] is True
    assert summary["overall_score"] >= 0.9
    assert summary["per_skill"]


def test_engine_unknown_option_raises():
    session = TrainingSession(scenario=_flagship())
    with pytest.raises(KeyError):
        session.decide("nope", elapsed_s=1.0)


def test_engine_decide_window_scales_with_behavior():
    """A struggling start should widen the next phase's decision window."""
    session = TrainingSession(scenario=_flagship())
    base_window = session.current_phase().decision_window_s
    # Deliberately bad + emotional first call to trigger scaffolding.
    session.decide(
        min(session.current_phase().options, key=lambda o: o.score).id,
        elapsed_s=base_window * 4, rationale="panic, i just freak out",
    )
    brief = session.brief()
    next_base = session.current_phase().decision_window_s
    assert brief.decision_window_s >= next_base  # widened (window_scale >= 1)


# --------------------------------------------------------------------------- #
# Lab
# --------------------------------------------------------------------------- #
def test_training_agents_lab_all_checks_pass():
    result = run_training_agents_lab()
    assert result.checks
    failed = [label for label, ok in result.checks if not ok]
    assert not failed, f"lab checks failed: {failed}"
    assert result.summary["completed"] is True
    agents = {e["agent"] for e in result.agent_events}
    assert agents >= {
        "situational_awareness", "forecasting", "rapid_decision",
        "critical_thinking", "learning_behavior",
    }


def test_lab_runs_secondary_scenario():
    result = run_training_agents_lab(
        scenario_id="kitchen-grease-fire",
        script=[("lid_off_heat", 3.0, "Smother with a lid and kill the heat because water on grease flares up."),
                ("leave_cool_ventilate", 5.0, "Leave the lid on to cool because hot oil can re-ignite.")],
    )
    assert result.summary["passed"] is True
