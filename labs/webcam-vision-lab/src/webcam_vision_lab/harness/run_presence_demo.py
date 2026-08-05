"""Print presence / silhouette state transitions for manual QA."""

from __future__ import annotations

from webcam_vision_lab.presence.absence import AbsenceTracker, PresenceProbe
from webcam_vision_lab.presence.silhouette import VisualStateInput, classify_visual_state
from webcam_vision_lab.scenarios import GROUP_CLASS_SCENARIO, SELF_TEACH_SCENARIO, SOLO_CLASS_SCENARIO


def _demo_visual_states() -> None:
    print("=== Silhouette visual states ===")
    cases = [
        ("group waiting", VisualStateInput(is_group_class=True, participant_joined=False)),
        ("camera off", VisualStateInput(camera_on=False)),
        ("probing", VisualStateInput(camera_on=True, face_count=-1)),
        ("absent", VisualStateInput(camera_on=True, face_count=0)),
        ("present", VisualStateInput(camera_on=True, face_count=1)),
        ("too many", VisualStateInput(camera_on=True, face_count=2, max_faces_allowed=1)),
    ]
    for label, inp in cases:
        state = classify_visual_state(inp)
        print(f"  {label:16} -> {state.value}")


def _demo_absence(scenario_name: str, policy) -> None:
    print(f"\n=== Absence tracker ({scenario_name}) ===")
    tracker = AbsenceTracker(policy)
    t0 = PresenceProbe(present=True, face_count=1, liveness_state="live", reason="verified")
    print(f"  live probe     -> {tracker.update(t0).value}")
    absent = PresenceProbe(
        present=False, face_count=0, liveness_state="absent", reason="no_face",
        observed_at=t0.observed_at,
    )
    print(f"  first absent   -> {tracker.update(absent).value}")
    tracker.simulate_grace_expiry(policy.grace_seconds + 1)
    print(f"  after grace    -> {tracker.state_at().value} (hold={tracker.hold_active})")
    back = PresenceProbe(
        present=True, face_count=1, liveness_state="live", reason="verified",
        observed_at=t0.observed_at,
    )
    print(f"  return live    -> {tracker.update(back).value}")


def main() -> None:
    _demo_visual_states()
    _demo_absence("solo", SOLO_CLASS_SCENARIO.presence_policy)
    _demo_absence("group", GROUP_CLASS_SCENARIO.presence_policy)
    _demo_absence("self_teach", SELF_TEACH_SCENARIO.presence_policy)
    print("\nDone.")


if __name__ == "__main__":
    main()
