from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "src" / "theodore_children_webcam_lab" / "static" / "app.css").read_text()


def test_touch_toggle_steps_aside_for_tutorials_and_win_cards():
    assert "body:has(.pq-tutorial) #touch-mode" in CSS
    assert "body:has(.gt-overlay:not([hidden])) #touch-mode" in CSS
    assert "body:has(.pq-win) #touch-mode" in CSS


def test_controls_and_toggle_lift_above_the_voice_widget_on_tall_phones():
    assert "@media(min-height:560px)" in CSS
    assert "#theodore-live-audio.voice-open:not(.voice-hidden)) .controls{bottom:7.5rem}" in CSS
    assert "#theodore-live-audio.voice-open:not(.voice-hidden)) #touch-mode{bottom:calc(15rem" in CSS


def test_readout_leaves_room_for_the_clock_on_phones():
    assert "body.phone-play #vision-readout" in CSS and "right:196px!important" in CSS
