from __future__ import annotations

from urllib.parse import unquote

from theodore_course_studio.page_media import motion_data_url, picture_data_url, svg_data_url


def test_picture_is_still_svg_data_url():
    url = picture_data_url(title="Stop sign", symbol="🛑", color="#dc2626")
    assert url.startswith("data:image/svg+xml,")
    svg = unquote(url.split(",", 1)[1])
    assert "Stop sign" in svg
    assert "animateTransform" not in svg


def test_motion_includes_animation():
    url = motion_data_url(
        title="Handwash", symbol="🧼", color="#06b6d4", bounce_px=22, bounce_dur_s=2.5
    )
    svg = unquote(url.split(",", 1)[1])
    assert "animateTransform" in svg
    assert "2.5s" in svg


def test_svg_data_url_escapes_title():
    url = svg_data_url(title='A <B> & "C"', symbol="X", color="#111", animated=False)
    svg = unquote(url.split(",", 1)[1])
    assert "<B>" not in svg
    assert "&lt;B&gt;" in svg or "A" in svg
