"""Every tuning knob must change a real decision, not just exist.

The lab used to "verify" tuning by range-checking the presets and confirming the
API returned a non-empty knob dict. Both pass happily for a knob that is wired to
nothing, which is why the sliders could look inert while every check was green.
These tests assert the property operators actually care about: move a knob, and
something the dashboard shows must move with it.
"""

from __future__ import annotations

import theodore_webcam_lab.tuning_probe as tuning_probe
from theodore_webcam_lab.tuning_probe import probe_knob_effects
from theodore_webcam_lab.vision_tuning import VisionTuning


def test_every_vision_knob_changes_a_scoring_decision():
    result = probe_knob_effects()
    assert result.total == len(VisionTuning().to_dict())
    assert result.dead == [], (
        "these knobs are declared, PATCHable and rendered as sliders but no "
        f"frame scenario reacts to them: {', '.join(result.dead)}"
    )


def test_probe_detects_a_disconnected_knob(monkeypatch):
    """Negative control: a probe that cannot fail is not a check.

    Pins one knob back to its default inside the analyzer, simulating a knob that
    is plumbed through the API but ignored by scoring, and requires the probe to
    single it out.
    """
    real = tuning_probe.WebcamSessionAnalyzer
    pinned = "eyes_closed_min_threshold"

    class IgnoresOneKnob(real):  # type: ignore[misc, valid-type]
        def __init__(self, *args, tuning=None, **kwargs):
            if tuning is not None:
                tuning = tuning.patched({pinned: getattr(VisionTuning(), pinned)})
            super().__init__(*args, tuning=tuning, **kwargs)

    monkeypatch.setattr(tuning_probe, "WebcamSessionAnalyzer", IgnoresOneKnob)
    result = probe_knob_effects()
    assert result.dead == [pinned]


def test_probe_reports_which_scenario_proved_each_knob():
    """A bare pass/fail is not actionable; the operator needs the frame that
    exercises the knob, since most knobs are invisible on an ordinary frame."""
    result = probe_knob_effects(only=["silhouette_consecutive_frames", "light_min_quality"])
    assert result.live["silhouette_consecutive_frames"] == "silhouette"
    assert result.live["light_min_quality"] == "framed_learner"
