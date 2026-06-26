"""In-lesson pulse survey helpers."""

from aoep_shared.pulse_survey import (
    interpret_pulse,
    pulse_lx_sample,
    should_show_pulse,
    template,
)


def test_template_is_short():
    t = template()
    assert t["title"]
    assert len(t["questions"]) == 3
    assert t["interval_slides"] == 5


def test_should_show_pulse_every_fifth_slide():
    assert should_show_pulse(4) is True
    assert should_show_pulse(3) is False
    assert should_show_pulse(9) is True


def test_pulse_lx_sample():
    assert pulse_lx_sample(5) == 100.0
    assert pulse_lx_sample(3) == 60.0


def test_interpret_pulse_strategy_match():
    hints = interpret_pulse(
        going_well=5,
        pace="just right",
        working_best="examples",
        teaching_strategy="worked_examples",
    )
    assert hints["strategy_success"] is True
    assert hints["lx_score"] == 100.0


def test_interpret_pulse_flags_pace_issues():
    hints = interpret_pulse(going_well=2, pace="too fast", working_best="not sure")
    assert hints["strategy_failure"] is False
    assert any("too fast" in t["trigger"] for t in hints["triggers"])
