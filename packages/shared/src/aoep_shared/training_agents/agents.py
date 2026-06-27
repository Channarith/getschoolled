"""Training agents: sensitive coaching beyond answer delivery."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional

from aoep_shared.adaptive import AdaptivePolicy, LearnerSignals
from aoep_shared.learner_adaptation import (
    LearnerAdaptation,
    detect_frustration,
    detect_wellness,
    merge_pacing_plan,
)
from aoep_shared.schemas import ClassType

from .models import (
    AgentTurn,
    ScenarioDefinition,
    TrainingAgentRole,
    TrainingPhase,
    TrainingSessionState,
)


def _gentle_prefix(adaptation: LearnerAdaptation) -> str:
    if adaptation.wellness_state in ("stressed", "unwell", "low_energy"):
        return "Take a breath — "
    if adaptation.sensitivity_rules:
        return "We'll go step by step — "
    return ""


@dataclass
class LearningBehaviorCoachAgent:
    """Adapts to learning behavior with sensitivity — trains, not just informs."""

    policy: AdaptivePolicy = field(default_factory=AdaptivePolicy)

    def tick(self, state: TrainingSessionState) -> Optional[AgentTurn]:
        plan = merge_pacing_plan(
            state.signals,
            adaptation=state.adaptation,
            class_type=ClassType.SOLO,
            policy=self.policy,
        )
        prefix = _gentle_prefix(state.adaptation)

        if plan.reteach and state.phase is not TrainingPhase.DEBRIEF:
            msg = (
                f"{prefix}I notice this topic is still forming for you. "
                "Let's slow down and connect this to something you already know — "
                "what part feels unclear?"
            )
            state.log(TrainingAgentRole.LEARNING_COACH, "nudge", msg, pacing=plan.pacing.value)
            return AgentTurn(
                TrainingAgentRole.LEARNING_COACH.value, "nudge", msg,
                meta={"pacing": plan.pacing.value, "difficulty": plan.difficulty.value},
            )

        if plan.pacing.value == "slow":
            msg = (
                f"{prefix}You're doing fine. We'll keep a steady pace — "
                "focus on one decision at a time."
            )
            state.log(TrainingAgentRole.LEARNING_COACH, "coach", msg)
            return AgentTurn(TrainingAgentRole.LEARNING_COACH.value, "coach", msg)

        if state.signals.attention_trend < 0.5:
            msg = (
                f"{prefix}Checking in — still with me? "
                "Name one thing you notice in the scenario so far."
            )
            state.log(TrainingAgentRole.LEARNING_COACH, "reengage", msg)
            return AgentTurn(TrainingAgentRole.LEARNING_COACH.value, "reengage", msg)

        return None

    def on_response(self, state: TrainingSessionState, text: str) -> Optional[AgentTurn]:
        frustration = detect_frustration(text)
        if frustration:
            state.adaptation.record_trigger(frustration, "learner frustration during training")
            msg = (
                "I hear you — that frustration is useful data. "
                "Let's reset: what felt wrong or rushed?"
            )
            state.log(TrainingAgentRole.LEARNING_COACH, "sensitivity", msg)
            return AgentTurn(TrainingAgentRole.LEARNING_COACH.value, "sensitivity", msg)

        wellness = detect_wellness(text)
        if wellness:
            wstate, phrase = wellness
            state.adaptation.record_wellness(wstate, phrase)
            msg = (
                f"Thanks for telling me you're {phrase}. "
                "We can ease pressure or pause — your call."
            )
            state.log(TrainingAgentRole.LEARNING_COACH, "wellness", msg)
            return AgentTurn(TrainingAgentRole.LEARNING_COACH.value, "wellness", msg)

        return None


@dataclass
class CriticalThinkingCoachAgent:
    """Socratic probes — builds reasoning, avoids handing out answers."""

    _prompt_idx: int = 0

    def tick(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if state.phase not in (TrainingPhase.SITUATIONAL_SCAN, TrainingPhase.DECISION):
            return None
        prompts = scenario.critical_thinking_prompts
        if not prompts or self._prompt_idx >= len(prompts):
            return None
        if state.tick % 3 != 1:
            return None
        prompt = prompts[self._prompt_idx]
        self._prompt_idx += 1
        msg = f"Before we move on — {prompt}"
        state.log(TrainingAgentRole.CRITICAL_THINKING, "probe", msg)
        return AgentTurn(TrainingAgentRole.CRITICAL_THINKING.value, "probe", msg)

    def evaluate_response(
        self, state: TrainingSessionState, text: str, scenario: ScenarioDefinition
    ) -> AgentTurn:
        lower = text.lower()
        has_reason = any(w in lower for w in ("because", "since", "therefore", "if", "assume"))
        has_evidence = any(w in lower for w in ("cue", "sign", "data", "see", "notice", "evidence"))
        if has_reason and has_evidence:
            msg = (
                "Good — you tied observation to reasoning. "
                "What would falsify your conclusion?"
            )
            kind = "affirm_probe"
        elif has_reason:
            msg = (
                "You stated a reason — what concrete cue in the scene supports it?"
            )
            kind = "evidence_nudge"
        else:
            msg = (
                "Walk me through your thinking: what did you notice first, "
                "and why does that matter?"
            )
            kind = "scaffold"
        state.log(TrainingAgentRole.CRITICAL_THINKING, kind, msg)
        return AgentTurn(TrainingAgentRole.CRITICAL_THINKING.value, kind, msg)


@dataclass
class SituationalAnalysisAgent:
    """Builds situational awareness — reveals cues progressively."""

    _cue_idx: int = 0

    def tick(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if state.phase is TrainingPhase.BRIEFING:
            msg = scenario.briefing
            state.phase = TrainingPhase.SITUATIONAL_SCAN
            state.log(TrainingAgentRole.SITUATIONAL_ANALYSIS, "briefing", msg)
            return AgentTurn(TrainingAgentRole.SITUATIONAL_ANALYSIS.value, "briefing", msg)

        if state.phase is not TrainingPhase.SITUATIONAL_SCAN:
            return None

        unrevealed = [c for c in scenario.cues if not c.revealed]
        if not unrevealed:
            state.phase = TrainingPhase.DECISION
            return None

        if state.tick % 2 != 0:
            return None

        cue = unrevealed[0]
        cue.revealed = True
        state.cues_seen.append(cue.cue_id)
        msg = f"Scan the scene — you notice: {cue.text}"
        state.log(
            TrainingAgentRole.SITUATIONAL_ANALYSIS, "cue", msg,
            cue_id=cue.cue_id, priority=cue.priority,
        )
        if cue.priority in ("high", "critical"):
            state.stress_level = min(1.0, state.stress_level + 0.15)
        return AgentTurn(
            TrainingAgentRole.SITUATIONAL_ANALYSIS.value, "cue", msg,
            meta={"cue_id": cue.cue_id, "priority": cue.priority},
        )

    def on_scan_response(
        self, state: TrainingSessionState, text: str, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        """Learner names what they consider important."""
        lower = text.lower()
        matched = [c for c in scenario.cues if c.cue_id in lower or c.text.lower()[:20] in lower]
        if not matched:
            for c in scenario.cues:
                words = c.text.lower().split()[:3]
                if any(w in lower for w in words if len(w) > 4):
                    matched.append(c)
                    break
        if matched:
            msg = (
                f"You flagged something important. "
                f"How does '{matched[0].text}' change your priorities?"
            )
        else:
            msg = "What is the highest-risk element in the scene right now — and why?"
        state.log(TrainingAgentRole.SITUATIONAL_ANALYSIS, "prioritize", msg)
        return AgentTurn(TrainingAgentRole.SITUATIONAL_ANALYSIS.value, "prioritize", msg)


@dataclass
class QuickDecisionAgent:
    """Split-minute thinking under time pressure."""

    def tick(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if state.phase is not TrainingPhase.DECISION:
            return None

        if state.time_remaining_s is None:
            state.time_remaining_s = scenario.decision_time_limit_s

        if state.tick % 1 == 0 and state.time_remaining_s is not None:
            state.time_remaining_s = max(0, state.time_remaining_s - 5)

        if state.time_remaining_s == 0:
            state.phase = TrainingPhase.FORESIGHT
            msg = "Time — commit to your decision. What did you choose?"
            state.log(TrainingAgentRole.QUICK_DECISION, "time_up", msg)
            return AgentTurn(TrainingAgentRole.QUICK_DECISION.value, "time_up", msg)

        if state.tick % 2 != 0:
            return None

        msg = (
            f"{scenario.decision_prompt} "
            f"({state.time_remaining_s}s remaining)"
        )
        state.stress_level = min(1.0, state.stress_level + 0.05)
        state.log(TrainingAgentRole.QUICK_DECISION, "pressure", msg)
        return AgentTurn(TrainingAgentRole.QUICK_DECISION.value, "pressure", msg)

    def on_decision(
        self, state: TrainingSessionState, text: str, scenario: ScenarioDefinition
    ) -> AgentTurn:
        state.decisions_made.append(text)
        state.phase = TrainingPhase.FORESIGHT
        lower = text.lower()
        prioritized = any(
            step.split("—")[0].strip().lower() in lower
            for step in scenario.emergency_steps[:2]
        ) if scenario.emergency_steps else True
        if prioritized:
            msg = (
                "Decision logged. We'll debrief whether sequence matched risk — "
                "for now, what do you expect to happen next?"
            )
            kind = "decision_logged"
        else:
            msg = (
                "Decision logged. Consider: did you address the highest-risk "
                "factor first? What would you reorder?"
            )
            kind = "decision_challenge"
        state.log(TrainingAgentRole.QUICK_DECISION, kind, msg)
        return AgentTurn(TrainingAgentRole.QUICK_DECISION.value, kind, msg)


@dataclass
class ForesightPrepAgent:
    """Mental rehearsal and forecasting before situations unfold."""

    _prompt_idx: int = 0

    def tick(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if state.phase is not TrainingPhase.FORESIGHT:
            return None
        prompts = scenario.foresight_prompts
        if not prompts or self._prompt_idx >= len(prompts):
            state.phase = TrainingPhase.DEBRIEF
            return None
        if state.tick % 2 != 0:
            return None
        prompt = prompts[self._prompt_idx]
        self._prompt_idx += 1
        msg = f"Forecast: {prompt}"
        state.log(TrainingAgentRole.FORESIGHT_PREP, "foresight", msg)
        return AgentTurn(TrainingAgentRole.FORESIGHT_PREP.value, "foresight", msg)

    def on_forecast(self, state: TrainingSessionState, text: str) -> AgentTurn:
        lower = text.lower()
        anticipates = any(w in lower for w in ("if", "might", "could", "next", "before", "prevent"))
        if anticipates:
            msg = (
                "You're thinking ahead — that's the skill. "
                "What's your earliest warning sign that things are going wrong?"
            )
        else:
            msg = (
                "Try projecting forward: what is the most likely complication "
                "in the next 5 minutes?"
            )
        state.log(TrainingAgentRole.FORESIGHT_PREP, "anticipation", msg)
        return AgentTurn(TrainingAgentRole.FORESIGHT_PREP.value, "anticipation", msg)


@dataclass
class EmergencyScenarioCoachAgent:
    """Domain emergency procedures — e.g. sim airplane emergency landing."""

    def tick(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if not scenario.emergency_steps:
            return None
        if scenario.domain.value != "aviation" and state.phase is not TrainingPhase.DECISION:
            return None
        if scenario.domain.value == "aviation" and state.phase not in (
            TrainingPhase.DECISION, TrainingPhase.DEBRIEF,
        ):
            return None
        if state.phase is TrainingPhase.DEBRIEF:
            return self._debrief(state, scenario)
        if state.stress_level < 0.3 or state.tick % 4 != 0:
            return None
        step = scenario.emergency_steps[min(len(state.decisions_made), len(scenario.emergency_steps) - 1)]
        msg = f"Emergency coach — remember: {step}"
        state.log(TrainingAgentRole.EMERGENCY_TRAINING, "emergency", msg)
        return AgentTurn(TrainingAgentRole.EMERGENCY_TRAINING.value, "emergency", msg)

    def _debrief(
        self, state: TrainingSessionState, scenario: ScenarioDefinition
    ) -> Optional[AgentTurn]:
        if state.score is not None:
            return None
        rubric = scenario.debrief_rubric
        decision_text = " ".join(state.decisions_made).lower()
        hits = sum(
            1 for item in rubric
            if any(w in decision_text for w in item.lower().split()[:2])
        )
        state.score = round(100.0 * hits / max(1, len(rubric)), 1)
        steps = "; ".join(scenario.emergency_steps[:3]) if scenario.emergency_steps else "N/A"
        msg = (
            f"Debrief — reference sequence: {steps}. "
            f"You hit {hits}/{len(rubric)} rubric points. "
            "What would you do differently with one more minute of prep?"
        )
        state.phase = TrainingPhase.DONE
        state.log(TrainingAgentRole.EMERGENCY_TRAINING, "debrief", msg, score=state.score)
        return AgentTurn(
            TrainingAgentRole.EMERGENCY_TRAINING.value, "debrief", msg,
            meta={"score": state.score},
        )
