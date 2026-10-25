"""Driver Ed sign art: standards-correct colours and shapes, centred, with every legend inside its sign."""
import os
import re
from pathlib import Path

import pytest

from theodore_course_studio import cert_multimodal, traffic_signs as ts

GOLDEN = Path(__file__).parent / "golden_signs"
KEY_SIGNS = (
    "School bus stop ahead", "School crossing", "School", "School speed limit", "End school zone", "Stop", "All Way",
    "Yield", "Do Not Enter", "Wrong Way", "Railroad crossbuck", "Straight only", "Left or straight", "Interstate route",
)


def _sign(name):
    sign = ts.sign_for_title(name)
    assert sign is not None, name
    return sign


def _points(markup):
    out = []
    for raw in re.findall(r'<polygon points="([^"]+)"', markup):
        out.append([tuple(float(v) for v in p.split(",")) for p in raw.split()])
    return out


def test_school_signs_are_yellow_green_with_a_black_legend_not_pale_green():
    for name in ("School", "School crossing", "School bus stop ahead"):
        sign = _sign(name)
        assert sign.face == ts.FYG, name  # MUTCD 7B.07: fluorescent yellow-green
        assert sign.ink == ts.INK and sign.border == ts.INK, name  # black legend and border, never dark green
    assert "#d9f99d" not in ts.sign_svg(_sign("School bus stop ahead"), animated=False)


def test_school_bus_stop_ahead_is_a_diamond_and_school_zone_signs_are_pentagons():
    assert _sign("School bus stop ahead").shape == "diamond"  # S3-1 is a warning diamond
    assert _sign("School").shape == "pentagon" and _sign("School crossing").shape == "pentagon"  # CA handbook: 5-sided
    assert _sign("School speed limit").shape == "school-speed"  # S5-1 is a rectangle, not a pentagon
    assert _sign("End school zone").shape == "rect"


def test_no_school_sign_is_red():
    for sign in ts.iter_signs():
        if "SCHOOL" in sign.legend:
            assert sign.face.lower() not in ("#b91c1c", "#dc2626", "#ef4444"), sign.name


def test_yield_triangle_points_down():
    (tri,) = _points(ts._shape_markup(_sign("Yield")))
    apex = max(tri, key=lambda p: p[1])
    base = [p for p in tri if p is not apex]
    assert apex[1] > base[0][1] and base[0][1] == base[1][1]  # apex lowest on screen, flat edge on top


def test_octagon_is_regular_and_centred_on_its_legend():
    (octo,) = _points(ts._shape_markup(_sign("Stop")))
    assert len(octo) == 8
    xs, ys = [p[0] for p in octo], [p[1] for p in octo]
    assert abs((min(xs) + max(xs)) / 2 - 400) < 1 and abs((min(ys) + max(ys)) / 2 - 175) < 1
    assert abs((max(xs) - min(xs)) - (max(ys) - min(ys))) < 1
    top = sorted(octo, key=lambda p: p[1])[:2]
    assert abs(top[0][1] - top[1][1]) < 0.2  # a flat top edge, as on a real STOP sign


def test_all_way_is_a_red_plaque_with_a_white_legend():
    sign = _sign("All Way")
    assert sign.shape == "plaque" and sign.face == "#b91c1c" and sign.ink == "#ffffff"  # MUTCD R1-3P


def test_lane_control_signs_are_distinguishable():
    faces = {n: ts._shape_markup(_sign(n)) for n in ("Straight only", "Left or straight", "Right or straight", "Left or right")}
    assert len(set(faces.values())) == 4


def _squeeze_ok(markup):
    for size, length, text in re.findall(r'font-size="([\d.]+)"[^>]*textLength="([\d.]+)"[^>]*>([^<]+)<', markup):
        natural = ts._text_width(text.replace("&amp;", "&"), float(size))
        assert float(length) >= natural * 0.9, (text, length, natural)  # never squeezed hard to fit


@pytest.mark.parametrize("sign", ts.iter_signs(), ids=lambda s: s.name)
def test_every_legend_fits_without_squeezing(sign):
    _squeeze_ok(ts._shape_markup(sign))


def test_diamond_text_respects_the_narrowing_width():
    for sign in ts.iter_signs():
        if sign.shape != "diamond":
            continue
        for x, y, size, length in re.findall(r'<text x="([\d.]+)" y="([\d.]+)"[^>]*font-size="([\d.]+)"[^>]*textLength="([\d.]+)"', ts._shape_markup(sign)):
            top, bottom = float(y) - float(size) * .82, float(y) + float(size) * .18
            half = 118 * (1 - max(abs(top - 175), abs(bottom - 175)) / 118)
            assert float(length) / 2 <= half + 0.5, (sign.name, length, half)


@pytest.mark.parametrize("name", KEY_SIGNS)
def test_golden_sign_svgs(name):
    got = ts.sign_svg(_sign(name), animated=False)
    path = GOLDEN / (re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") + ".svg")
    if os.environ.get("UPDATE_GOLDEN") or not path.exists():
        path.write_text(got, encoding="utf-8")
    assert got == path.read_text(encoding="utf-8"), f"{name} changed: review docs/driver-ed-sign-gallery.html, then UPDATE_GOLDEN=1"


def test_permit_slide_uses_the_dmv_minimum_age_not_16():
    kit = cert_multimodal._KITS["California learner's permit"]
    text = " ".join(kit.examples)
    assert "15½" in text and "You are 16" not in text  # CA DMV: at least 15 1/2 for the instruction permit
    assert kit.game_steps.index("Complete the application steps") < kit.game_steps.index("Pass vision and knowledge tests")


def test_school_bus_rule_mentions_multilane_roads():
    kit = cert_multimodal._KITS["School buses in California"]
    assert "two or more lanes" in " ".join(kit.examples) and "two or more lanes" in kit.quiz_explanation  # CVC 22454(b)


def test_gallery_lists_every_sign():
    page = ts.gallery_html()
    assert page.count("<figure>") == len(ts.iter_signs()) == 140
