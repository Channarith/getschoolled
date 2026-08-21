"""California driver-ed scenario bank (200+ scenes across many lessons).

Single source of truth for sample-curriculum driver-ed lessons and
cert_storyboard animated scenes. Study aid only — not DMV-approved
driver education.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator, Tuple

from .types import Cast, ObjectCallout, Scene, SegmentStoryboard


@dataclass(frozen=True)
class DriverScenario:
    """One teaching scenario (= one curriculum slide / storyboard scene)."""

    scenario_id: str
    lesson_id: str
    slide_index: int
    title: str
    concept: str
    narration: str
    backdrop: str
    camera: str
    preset: str
    callout: str


@dataclass(frozen=True)
class DriverLesson:
    lesson_id: str
    title: str
    summary: str
    scenarios: Tuple[DriverScenario, ...]


# Cast presets: (kind, x, y, scale, motion, flip)
CAST_PRESETS: dict[str, tuple[tuple, ...]] = {
    "adult_car": (("car-red", 380, 340, 1.1, "drive", False), ("adult", 200, 300, 1.0, "bob", False),),
    "adult_teen": (("adult", 420, 300, 1.0, "bob", False), ("teen", 500, 310, 1.0, "sway", False),),
    "adult_teen_car": (("car-blue", 300, 340, 1.1, "drive", False), ("adult", 500, 300, 1.0, "bob", False), ("teen", 560, 310, 1.0, "sway", False),),
    "alley": (("car-blue", 320, 360, 1.0, "approach", False), ("car-red", 600, 340, 1.0, "drive", False), ("pedestrian", 450, 380, 1.0, "walk", False),),
    "ambulance_right": (("ambulance", 200, 320, 1.05, "drive", False), ("car-blue", 520, 360, 1.0, "drive", False), ("car-green", 720, 350, 0.9, "drive", False),),
    "bike_box": (("bike", 420, 380, 1.0, "bob", False), ("car-blue", 300, 340, 1.0, "approach", False), ("traffic-light-red", 500, 120, 1.0, "flash", False),),
    "bike_share": (("bike", 360, 360, 1.0, "drive", False), ("car-green", 560, 340, 1.0, "drive", False), ("sign-bike", 140, 190, 0.9, "pulse", False),),
    "blind_spot": (("car-red", 400, 340, 1.15, "bob", False), ("motorcycle", 280, 380, 0.9, "drive", False), ("bike", 620, 390, 0.8, "cross-left", False),),
    "bus_pullout": (("school-bus", 360, 300, 1.0, "bob", False), ("car-red", 620, 350, 1.0, "drive", False),),
    "courtesy": (("car-blue", 240, 350, 1.0, "drive", False), ("car-green", 480, 340, 1.0, "drive", False), ("pedestrian", 680, 360, 1.0, "walk", False), ("adult", 740, 300, 1.0, "bob", False),),
    "cover_brake": (("car-red", 380, 340, 1.0, "approach", False), ("pedestrian", 560, 380, 1.0, "walk", False), ("sign-warning", 160, 190, 0.85, "pulse", False),),
    "crash_scene": (("car-red", 300, 340, 1.0, "bob", False), ("car-blue", 480, 350, 0.95, "sway", False), ("adult", 400, 280, 1.0, "bob", False), ("ambulance", 700, 300, 0.85, "drive", False),),
    "do_not_enter": (("sign-do-not-enter", 300, 190, 1.1, "pulse", False), ("car-red", 420, 360, 1.0, "approach", False),),
    "door_zone": (("car-red", 320, 340, 1.0, "bob", False), ("bike", 480, 360, 1.0, "cross-right", False), ("adult", 280, 300, 1.0, "sway", False),),
    "driveway": (("car-green", 300, 360, 1.0, "approach", False), ("pedestrian", 480, 370, 1.0, "cross-right", False),),
    "ems_intersect": (("ambulance", 220, 320, 1.05, "drive", False), ("car-blue", 480, 360, 1.0, "drive", False), ("traffic-light", 520, 120, 0.85, "flash", False),),
    "exit_prep": (("sign-guide", 300, 160, 1.1, "bob", False), ("car-red", 240, 350, 1.0, "drive", False), ("car-blue", 500, 340, 1.0, "drive", False),),
    "family_car": (("car-green", 360, 340, 1.15, "bob", False), ("adult", 280, 300, 1.0, "bob", False), ("child", 440, 310, 1.0, "hop", False), ("teen", 520, 305, 1.0, "sway", False),),
    "flash_red": (("traffic-light-red", 480, 120, 1.1, "flash", False), ("sign-stop", 200, 200, 0.7, "pulse", False), ("car-red", 340, 360, 1.0, "approach", False),),
    "flash_yellow": (("traffic-light-yellow", 480, 120, 1.1, "flash", False), ("car-green", 360, 350, 1.0, "drive", False),),
    "follow_gap": (("car-red", 200, 340, 1.0, "drive", False), ("car-blue", 420, 350, 0.95, "drive", False), ("truck", 680, 320, 0.9, "drive", False),),
    "four_way": (("sign-stop", 160, 200, 0.9, "pulse", False), ("sign-stop", 700, 200, 0.9, "pulse", False), ("car-red", 300, 360, 1.0, "approach", False), ("car-blue", 600, 300, 0.9, "cross-left", True),),
    "green_arrow": (("traffic-light-green", 480, 120, 1.1, "pulse", False), ("car-blue", 320, 360, 1.0, "drive", False), ("pedestrian", 600, 390, 1.0, "walk", False),),
    "gridlock": (("car-red", 300, 340, 1.0, "bob", False), ("car-blue", 480, 350, 1.0, "sway", False), ("car-green", 650, 300, 0.9, "bob", False),),
    "guide_sign": (("sign-guide", 320, 160, 1.1, "bob", False), ("car-blue", 200, 360, 1.0, "drive", False), ("truck", 620, 320, 0.9, "drive", False),),
    "hill_truck": (("truck", 360, 300, 1.1, "drive", False), ("car-red", 600, 350, 0.95, "drive", False), ("sign-warning", 140, 190, 0.85, "pulse", False),),
    "hov": (("car-blue", 320, 340, 1.0, "drive", False), ("car-green", 520, 350, 1.0, "drive", False), ("sign-guide", 160, 170, 0.9, "bob", False),),
    "lane_change": (("car-green", 400, 340, 1.1, "drive", False), ("motorcycle", 260, 380, 0.85, "drive", False), ("car-red", 700, 350, 0.9, "drive", False),),
    "lane_split": (("motorcycle", 420, 360, 1.0, "drive", False), ("car-red", 280, 340, 1.0, "drive", False), ("car-blue", 560, 340, 1.0, "drive", False),),
    "lane_use": (("sign-guide", 300, 160, 1.0, "bob", False), ("car-blue", 240, 350, 1.0, "drive", False), ("car-red", 480, 340, 1.0, "drive", False),),
    "light_green": (("traffic-light-green", 480, 120, 1.1, "pulse", False), ("car-green", 320, 360, 1.0, "drive", False), ("pedestrian", 560, 390, 1.0, "walk", False),),
    "light_red": (("traffic-light-red", 480, 120, 1.1, "flash", False), ("car-blue", 300, 360, 1.0, "approach", False), ("pedestrian", 520, 390, 1.0, "cross-right", False),),
    "light_yellow": (("traffic-light-yellow", 480, 120, 1.1, "flash", False), ("car-red", 300, 360, 1.0, "approach", False),),
    "long_drive": (("car-green", 400, 340, 1.1, "drive", False), ("truck", 650, 310, 0.95, "drive", False),),
    "merge": (("car-green", 220, 360, 1.0, "approach", False), ("car-blue", 480, 340, 1.0, "drive", False), ("truck", 720, 310, 0.9, "drive", False),),
    "moto_aware": (("motorcycle", 420, 360, 1.0, "drive", False), ("car-red", 200, 350, 1.0, "drive", False), ("car-blue", 680, 340, 1.0, "drive", False),),
    "multi_cars": (("car-red", 220, 340, 1.0, "drive", False), ("car-blue", 440, 350, 0.95, "drive", False), ("car-green", 680, 340, 0.9, "drive", False),),
    "multi_turn": (("car-red", 300, 360, 1.0, "drive", False), ("car-blue", 420, 350, 0.95, "drive", False), ("traffic-light-green", 560, 120, 0.9, "pulse", False),),
    "night_drive": (("car-blue", 320, 340, 1.1, "drive", False), ("sign-speed", 160, 190, 0.8, "pulse", False), ("car-red", 620, 350, 0.9, "drive", True),),
    "no_pass": (("car-blue", 280, 340, 1.0, "drive", False), ("car-red", 520, 350, 1.0, "drive", False), ("sign-warning", 140, 190, 0.8, "pulse", False),),
    "no_turn": (("sign-no-turn", 260, 190, 1.0, "pulse", False), ("traffic-light-red", 500, 120, 1.0, "flash", False), ("car-red", 360, 360, 1.0, "approach", False),),
    "one_way": (("sign-one-way", 280, 190, 1.0, "bob", False), ("car-blue", 400, 350, 1.0, "drive", False), ("car-green", 620, 340, 0.9, "drive", False),),
    "parking": (("car-white", 320, 340, 1.0, "bob", False), ("sign-stop", 160, 200, 0.75, "static", False), ("pedestrian", 560, 360, 1.0, "walk", False),),
    "pass_left": (("car-blue", 300, 360, 1.0, "drive", False), ("car-red", 500, 340, 1.0, "drive", False), ("car-green", 700, 350, 0.9, "drive", False),),
    "pass_right": (("car-blue", 360, 340, 1.0, "drive", False), ("car-red", 560, 360, 1.0, "drive", False),),
    "ped_blind": (("pedestrian", 460, 370, 1.0, "walk", False), ("car-blue", 280, 350, 1.0, "approach", False), ("adult", 540, 300, 1.0, "bob", False),),
    "ped_cross": (("pedestrian", 460, 380, 1.0, "cross-right", False), ("child", 400, 390, 1.0, "walk", False), ("car-blue", 220, 360, 1.0, "approach", False), ("traffic-light", 520, 120, 0.85, "flash", False),),
    "phone_ban": (("car-red", 380, 340, 1.1, "drive", False), ("phone-ban", 700, 200, 1.0, "pulse", False), ("sign-warning", 120, 180, 0.75, "static", False),),
    "procession": (("car-white", 240, 350, 1.0, "drive", False), ("car-white", 400, 350, 0.95, "drive", False), ("car-white", 560, 350, 0.9, "drive", False),),
    "rail_cross": (("sign-rail", 200, 180, 1.05, "flash", False), ("car-red", 360, 360, 1.0, "approach", False), ("sign-stop", 520, 200, 0.7, "static", False),),
    "rain_drive": (("car-blue", 360, 340, 1.0, "drive", False), ("sign-warning", 160, 180, 0.9, "pulse", False), ("car-red", 650, 350, 0.9, "drive", False),),
    "roundabout": (("sign-yield", 180, 200, 0.9, "pulse", False), ("car-green", 300, 360, 1.0, "drive", False), ("car-blue", 560, 300, 1.0, "cross-left", True), ("bike", 700, 380, 1.0, "cross-right", False),),
    "rural_animal": (("car-green", 380, 340, 1.0, "drive", False), ("sign-warning", 180, 190, 1.0, "pulse", False),),
    "scan_intersect": (("car-red", 280, 360, 1.0, "approach", False), ("car-blue", 620, 280, 0.85, "cross-left", True), ("pedestrian", 480, 400, 1.0, "walk", False), ("traffic-light", 500, 120, 0.9, "flash", False),),
    "school_bus_kids": (("school-bus", 360, 300, 1.0, "drive", False), ("child", 580, 360, 1.0, "hop", False), ("sign-school", 160, 190, 0.85, "pulse", False),),
    "school_zone": (("sign-school", 180, 180, 1.0, "flash", False), ("school-bus", 400, 300, 1.0, "drive", False), ("child", 620, 360, 1.0, "hop", False), ("child", 680, 365, 1.0, "walk", False),),
    "shoulder": (("car-blue", 300, 340, 1.0, "drive", False), ("sign-warning", 650, 200, 0.9, "pulse", False),),
    "shoulder_stop": (("car-red", 280, 360, 1.0, "bob", False), ("car-blue", 560, 340, 1.0, "drive", False), ("sign-warning", 160, 190, 0.85, "pulse", False),),
    "signs_cluster": (("sign-stop", 180, 200, 0.95, "pulse", False), ("sign-yield", 360, 210, 0.9, "bob", False), ("sign-warning", 540, 200, 0.9, "sway", False), ("sign-speed", 720, 200, 0.85, "pulse", False), ("car-red", 400, 360, 1.0, "drive", False),),
    "slow_traffic": (("car-white", 360, 340, 1.0, "drive", False), ("truck", 600, 310, 1.0, "drive", False),),
    "speed_25": (("sign-speed", 160, 180, 1.0, "pulse", False), ("car-blue", 400, 340, 1.0, "drive", False), ("pedestrian", 620, 360, 1.0, "walk", False),),
    "speed_freeway": (("sign-speed", 140, 180, 0.95, "pulse", False), ("car-green", 360, 340, 1.0, "drive", False), ("truck", 620, 310, 0.95, "drive", False),),
    "stop_distance": (("car-blue", 300, 340, 1.0, "drive", False), ("sign-speed", 650, 190, 0.85, "pulse", False),),
    "stop_ped": (("sign-stop", 180, 190, 1.0, "pulse", False), ("car-blue", 300, 360, 1.0, "approach", False), ("pedestrian", 520, 390, 1.0, "cross-right", False),),
    "t_intersect": (("car-blue", 400, 360, 1.0, "approach", False), ("car-red", 650, 300, 0.95, "drive", False), ("sign-yield", 200, 200, 0.85, "bob", False),),
    "tailgate": (("car-green", 360, 340, 1.0, "drive", False), ("car-red", 520, 350, 1.0, "approach", False),),
    "truck_freeway": (("truck", 400, 300, 1.15, "drive", False), ("car-red", 200, 370, 0.85, "drive", False), ("car-green", 700, 360, 0.85, "drive", False),),
    "turn_lane": (("car-green", 340, 360, 1.0, "drive", False), ("traffic-light-green", 500, 120, 0.95, "pulse", False),),
    "turnout": (("car-green", 300, 340, 1.0, "drive", False), ("car-red", 480, 350, 0.95, "drive", False), ("car-blue", 640, 340, 0.9, "drive", False),),
    "two_way": (("car-red", 280, 340, 1.0, "drive", False), ("car-blue", 620, 350, 0.95, "drive", True), ("sign-warning", 160, 190, 0.85, "pulse", False),),
    "u_turn": (("car-red", 400, 340, 1.1, "bob", False), ("sign-no-turn", 200, 190, 0.9, "pulse", False),),
    "uncontrolled": (("car-red", 280, 360, 1.0, "approach", False), ("car-green", 600, 300, 0.9, "cross-left", True),),
    "warning_curve": (("sign-warning", 200, 180, 1.1, "pulse", False), ("sign-curve", 700, 190, 0.9, "sway", False), ("car-red", 420, 350, 1.0, "drive", False),),
    "weave": (("car-green", 240, 360, 1.0, "approach", False), ("car-red", 480, 340, 1.0, "drive", False), ("car-blue", 700, 350, 0.95, "drive", True),),
    "work_zone": (("sign-work", 160, 190, 1.0, "pulse", False), ("cone", 300, 400, 1.0, "static", False), ("cone", 360, 400, 1.0, "static", False), ("cone", 420, 400, 1.0, "static", False), ("truck", 560, 310, 0.9, "bob", False), ("car-blue", 780, 350, 0.85, "drive", False),),
    "wrong_way": (("car-red", 400, 340, 1.0, "drive", True), ("car-blue", 650, 350, 1.0, "drive", False), ("sign-do-not-enter", 180, 190, 1.0, "pulse", False),),
    "yield_merge": (("sign-yield", 200, 190, 1.0, "bob", False), ("car-red", 280, 360, 1.0, "approach", False), ("car-blue", 600, 300, 0.95, "drive", False),),
}


def _cast_from_preset(name: str) -> tuple[Cast, ...]:
    rows = CAST_PRESETS.get(name) or CAST_PRESETS["multi_cars"]
    out: list[Cast] = []
    for kind, x, y, scale, motion, flip in rows:
        out.append(Cast(kind=kind, x=x, y=y, scale=scale, motion=motion, flip=flip))
    return tuple(out)


def _scene_for(sc: DriverScenario) -> Scene:
    return Scene(
        scene_id=sc.scenario_id,
        title=sc.title,
        backdrop=sc.backdrop,
        camera=sc.camera,
        narration=sc.narration,
        cast=_cast_from_preset(sc.preset),
        objects=(ObjectCallout(label=sc.callout, x=40, y=80),),
        concept=sc.concept,
    )


def _build_lessons() -> tuple[DriverLesson, ...]:
    raw = [
        (
            "ca-driver-ed-01-permit-licensing",
            "CA Driver Ed — Permit & licensing",
            "Provisional permit rules, eligibility, and handbook authority.",
            [
                ("Study aid, not DMV course", "Confirm every rule in the official handbook.", "This track is practice only. Always verify rules in the current California Driver's Handbook.", "residential", "ken-burns", "adult_teen", "Handbook wins"),
                ("Who needs a permit", "Instruction permit before solo provisional license.", "Most new drivers start with an instruction permit, then a provisional license after requirements are met.", "residential", "push-in", "adult_teen_car", "Permit first"),
                ("Age and driver education", "Teens usually need education plus parent consent.", "Typical teen applicants need driver education, practice hours, and a parent or guardian signature.", "school-zone", "pull-out", "school_bus_kids", "Education required"),
                ("Vision and knowledge tests", "Pass vision and knowledge before the permit issues.", "Expect a vision screening and a knowledge test covering signs, rules, and sharing the road.", "residential", "pan-right", "adult_car", "Vision + knowledge"),
                ("Practice hour log", "Log day and night supervised hours.", "California requires substantial supervised practice, including night hours, before the road test.", "night-road", "pan-left", "night_drive", "Log every hour"),
                ("Supervising driver rules", "Licensed adult in the front seat while practicing.", "With a permit, a qualified licensed driver must supervise from the front passenger seat.", "residential", "zoom-punch", "adult_teen_car", "Front-seat supervisor"),
                ("Provisional passenger limits", "First-year passenger restrictions apply.", "Provisional holders usually may carry only immediate family unless a qualified supervisor is present.", "residential", "dolly-shake", "family_car", "Family only at first"),
                ("Night curfew for teens", "Honor provisional nighttime limits.", "Provisional drivers face night driving limits unless an exception applies.", "night-road", "static", "night_drive", "Know curfew hours"),
                ("License classes overview", "Class C covers most passenger cars.", "Most learners seek a Class C license. Commercial and motorcycle classes have separate requirements.", "freeway", "tilt-up", "multi_cars", "Class C basics"),
                ("Keep documents current", "Carry license and insurance proof when you drive.", "Drive only with a valid license or permit and carry proof of financial responsibility when required.", "residential", "ken-burns", "adult_car", "License + insurance"),
            ],
        ),
        (
            "ca-driver-ed-02-signs-regulatory",
            "CA Driver Ed — Regulatory signs",
            "Stop, yield, speed, one-way, and other must-obey signs.",
            [
                ("Sign shapes and colors", "Shape and color signal meaning before you read text.", "Octagon means stop, triangle means yield, diamond warns, and white rectangles regulate.", "intersection", "ken-burns", "signs_cluster", "Learn shapes first"),
                ("Stop sign complete stop", "Wheels must fully stop behind the line.", "At a stop sign, come to a complete stop behind the limit line or crosswalk, then proceed when clear.", "intersection", "push-in", "stop_ped", "Full stop"),
                ("Yield triangle", "Slow and give way when others have priority.", "A yield sign means prepare to stop and give way to traffic and pedestrians as needed.", "intersection", "pull-out", "yield_merge", "Give way"),
                ("Speed limit maximum", "Posted speed is a maximum in ideal conditions.", "Never treat the posted limit as a target when weather, traffic, or visibility are poor.", "freeway", "pan-right", "speed_freeway", "Conditions first"),
                ("Do not enter", "Wrong-way entry risks a head-on crash.", "A do-not-enter sign means you are approaching from the wrong direction — turn around safely.", "intersection", "pan-left", "do_not_enter", "Wrong way — stop"),
                ("One-way streets", "Travel only in the marked direction.", "One-way signs and pavement arrows show the only legal direction of travel.", "intersection", "zoom-punch", "one_way", "Follow the arrows"),
                ("No turn signs", "Obey posted turn prohibitions.", "No-left-turn and no-U-turn signs override what a green light alone might allow.", "intersection", "dolly-shake", "no_turn", "No turn means no turn"),
                ("Keep right and lane use", "Lane-use signs assign which lane for which move.", "Lane-use control signs tell you whether a lane is for left, through, or right movements.", "freeway", "static", "lane_use", "Choose the correct lane"),
                ("Weight and truck limits", "Some roads restrict vehicle types or weight.", "Bridge and road signs may ban trucks or set weight limits — plan another route if needed.", "freeway", "tilt-up", "truck_freeway", "Check restrictions"),
                ("Regulatory vs guide", "White and black rules; green and blue guide.", "Regulatory signs create legal duties. Guide signs help you navigate but do not replace rules.", "freeway", "ken-burns", "guide_sign", "Rules vs guidance"),
            ],
        ),
        (
            "ca-driver-ed-03-signs-warning",
            "CA Driver Ed — Warning signs",
            "Yellow diamonds and hazard preparation.",
            [
                ("Yellow diamond meaning", "Slow and prepare — not always a full stop.", "Yellow diamond warning signs alert you to hazards ahead so you can adjust early.", "freeway", "ken-burns", "warning_curve", "Prepare early"),
                ("Curve and winding road", "Reduce speed before the curve, not in it.", "Curve signs mean ease off the gas before you enter and stay in your lane.", "freeway", "push-in", "warning_curve", "Brake before the bend"),
                ("Merge ahead", "Watch for vehicles entering your lane.", "Merge warning signs remind you to scan and create gaps for entering traffic.", "freeway", "pull-out", "merge", "Make a gap"),
                ("Pedestrian crossing ahead", "Expect people in or near the roadway.", "Pedestrian warning signs mean slow down and be ready to stop for walkers.", "residential", "pan-right", "ped_cross", "People first"),
                ("Bicycle warning", "Share space with cyclists ahead.", "Bike warning signs mean scan for cyclists and give them room.", "residential", "pan-left", "bike_share", "Watch for bikes"),
                ("Slippery when wet", "Reduce speed on wet pavement.", "Slippery-road warnings mean tires lose grip — slow down and avoid sudden inputs.", "freeway", "zoom-punch", "rain_drive", "Ease off in rain"),
                ("Deer and animal crossing", "Scan shoulders in rural areas.", "Animal crossing signs mean wildlife may enter the road, especially at dusk.", "freeway", "dolly-shake", "rural_animal", "Scan the shoulders"),
                ("Hill and downgrade", "Control speed on long descents.", "Downgrade signs mean use a lower gear and avoid riding the brakes.", "freeway", "static", "hill_truck", "Control the descent"),
                ("Soft shoulder", "Stay on pavement if the shoulder is soft.", "Soft-shoulder warnings mean leaving the pavement can pull you off the road.", "freeway", "tilt-up", "shoulder", "Stay on pavement"),
                ("Two-way traffic ahead", "Opposing traffic begins after a divided section.", "Two-way traffic signs mean keep right and expect oncoming vehicles.", "freeway", "ken-burns", "two_way", "Keep right"),
            ],
        ),
        (
            "ca-driver-ed-04-signals-markings",
            "CA Driver Ed — Signals & pavement markings",
            "Lights, arrows, and lane lines.",
            [
                ("Steady green", "Go only if the intersection is clear.", "A green light means proceed if the way is clear and you yield to pedestrians still crossing.", "intersection", "ken-burns", "light_green", "Clear before you go"),
                ("Steady yellow", "Stop if you can do so safely.", "Yellow means the light is changing to red — stop before the intersection if you can stop safely.", "intersection", "push-in", "light_yellow", "Don't race yellow"),
                ("Steady red", "Full stop; turns only when allowed.", "Red means stop. Right on red is allowed in California after a full stop unless signed otherwise.", "intersection", "pull-out", "light_red", "Stop on red"),
                ("Flashing red", "Treat like a stop sign.", "A flashing red signal requires a complete stop, then proceed when safe — like a stop sign.", "intersection", "pan-right", "flash_red", "Flash red = stop"),
                ("Flashing yellow", "Proceed with caution.", "Flashing yellow means slow down and proceed carefully through the intersection.", "intersection", "pan-left", "flash_yellow", "Caution through"),
                ("Green arrow", "Protected turn — still scan.", "A green arrow gives a protected turn, but still watch for pedestrians and red-light runners.", "intersection", "zoom-punch", "green_arrow", "Protected, still scan"),
                ("Yellow center lines", "Separate opposite directions.", "Yellow lines separate traffic moving in opposite directions.", "freeway", "dolly-shake", "multi_cars", "Yellow = opposing"),
                ("White lane lines", "Separate same-direction lanes.", "White lines separate lanes traveling in the same direction.", "freeway", "static", "multi_cars", "White = same way"),
                ("Solid vs broken", "Solid means do not cross for passing.", "A solid line on your side means do not pass or change lanes across it.", "freeway", "tilt-up", "no_pass", "Solid = stay"),
                ("Crosswalk markings", "Yield to people in the crosswalk.", "Marked and unmarked crosswalks require you to yield to pedestrians.", "intersection", "ken-burns", "ped_cross", "Yield in crosswalks"),
            ],
        ),
        (
            "ca-driver-ed-05-intersections",
            "CA Driver Ed — Intersections",
            "Scanning, stopping, and moving through intersections.",
            [
                ("Left-right-left scan", "Scan both ways before you enter.", "At every intersection, look left, right, then left again before proceeding.", "intersection", "ken-burns", "scan_intersect", "Left · right · left"),
                ("Limit lines", "Stop behind the painted line.", "Stop with your front bumper behind the limit line so cross traffic and walkers stay clear.", "intersection", "push-in", "stop_ped", "Behind the line"),
                ("Uncontrolled intersections", "Yield to the right when arriving together.", "With no signs or signals, yield to vehicles already in the intersection and to the right when tied.", "intersection", "pull-out", "uncontrolled", "Yield to the right"),
                ("T-intersections", "Through traffic usually has priority.", "At a T-intersection, traffic on the through road generally has the right of way.", "intersection", "pan-right", "t_intersect", "Through road first"),
                ("Blocked intersection", "Never enter if you will block it.", "Do not enter an intersection unless you can clear it — gridlock is illegal and dangerous.", "intersection", "pan-left", "gridlock", "Don't block the box"),
                ("Turning into correct lane", "Finish turns in the proper lane.", "Turn into the nearest lane of travel in your direction unless signs direct otherwise.", "intersection", "zoom-punch", "turn_lane", "Nearest lane"),
                ("U-turns in California", "Only where safe and legal.", "U-turns are restricted near hills, curves, and where signs prohibit them.", "residential", "dolly-shake", "u_turn", "Sight distance first"),
                ("Intersection bike boxes", "Respect bike waiting areas where marked.", "Some cities paint bike boxes — do not stop on top of them when waiting at red.", "intersection", "static", "bike_box", "Keep the bike box clear"),
                ("Late arrival at yellow", "If already committed, clear carefully.", "If you are too close to stop safely on yellow, continue through and clear the intersection.", "intersection", "tilt-up", "light_yellow", "Committed = clear"),
                ("Stale green awareness", "Expect yellow if the light has been green long.", "A long green may turn yellow soon — cover the brake as you approach.", "intersection", "ken-burns", "light_green", "Cover the brake"),
                ("Multi-lane turns", "Stay in your lane through the turn.", "In multi-lane turns, stay in your lane and watch for vehicles drifting beside you.", "intersection", "push-in", "multi_turn", "Hold your lane"),
                ("Emergency in intersection", "Never block for lights and sirens.", "If an emergency vehicle approaches, clear the intersection, then pull right.", "intersection", "pull-out", "ems_intersect", "Clear, then pull right"),
            ],
        ),
        (
            "ca-driver-ed-06-right-of-way",
            "CA Driver Ed — Right-of-way",
            "Who goes first — and when to yield anyway.",
            [
                ("Right-of-way is given, not taken", "Yielding prevents crashes even if you are 'right'.", "Having the right-of-way never means forcing others to stop — yield to avoid a collision.", "intersection", "ken-burns", "yield_merge", "Safety over ego"),
                ("Four-way stop order", "First to arrive goes first.", "At all-way stops, the first vehicle to arrive proceeds first; ties yield to the right.", "intersection", "push-in", "four_way", "First in, first out"),
                ("Pedestrians always", "Yield to pedestrians in crosswalks.", "Drivers must yield to pedestrians in marked or unmarked crosswalks.", "intersection", "pull-out", "ped_cross", "Walkers first"),
                ("Blind pedestrians", "Stop and give space to white cane or guide dog users.", "Yield extra space and time to pedestrians using a white cane or guide dog.", "residential", "pan-right", "ped_blind", "Extra patience"),
                ("Funeral processions", "Yield to processions where required.", "Do not cut into a funeral procession; yield and proceed only when safe and lawful.", "residential", "pan-left", "procession", "Do not cut in"),
                ("Transit buses pulling out", "Yield when required by local rules.", "In some areas you must yield to buses re-entering traffic — watch for signals.", "residential", "zoom-punch", "bus_pullout", "Watch bus signals"),
                ("Driveway vs sidewalk", "Sidewalk users go first.", "When leaving a driveway, stop and yield to pedestrians on the sidewalk before entering the street.", "residential", "dolly-shake", "driveway", "Sidewalk first"),
                ("Private road entry", "Yield to all traffic on the public road.", "Entering from an alley or private road, yield to vehicles and pedestrians on the public roadway.", "residential", "static", "alley", "Public road priority"),
                ("Roundabout right-of-way", "Yield to traffic already circulating.", "At roundabouts, yield to vehicles in the circle, then enter when there is a gap.", "intersection", "tilt-up", "roundabout", "Yield on entry"),
                ("When in doubt, yield", "Uncertainty means wait.", "If you are unsure who should go, wait — a few seconds of caution beats a crash.", "intersection", "ken-burns", "scan_intersect", "Doubt → yield"),
            ],
        ),
        (
            "ca-driver-ed-07-speed-space",
            "CA Driver Ed — Speed & space cushion",
            "Basic Speed Law, following distance, and space management.",
            [
                ("Basic Speed Law", "Never drive faster than is safe.", "California's Basic Speed Law requires a speed that is safe for conditions even below the posted limit.", "freeway", "ken-burns", "speed_freeway", "Safe for conditions"),
                ("Residential 25 mph", "Expect 25 unless posted otherwise.", "Business and residential districts are often 25 mph unless signs say otherwise.", "residential", "push-in", "speed_25", "Watch for 25"),
                ("School zone speeds", "Slow when children are present.", "School zones often reduce speed when children are present or lights flash.", "school-zone", "pull-out", "school_zone", "Kids nearby = slow"),
                ("Three-second rule", "Pick a marker and count three seconds.", "When the vehicle ahead passes a marker, you should not reach it before counting three seconds.", "freeway", "pan-right", "follow_gap", "Count 1-2-3"),
                ("Add time in bad conditions", "Rain, fog, and night need more gap.", "Increase following distance in rain, fog, night, heavy traffic, and behind large vehicles.", "freeway", "pan-left", "rain_drive", "More space needed"),
                ("Space beside you", "Avoid lingering in others' blind spots.", "Do not cruise beside other vehicles — pass promptly or drop back.", "freeway", "zoom-punch", "blind_spot", "Don't camp beside"),
                ("Space behind you", "If tailgated, create room ahead and change lanes.", "When someone is too close behind, increase your forward gap and move over when safe.", "freeway", "dolly-shake", "tailgate", "Ease the pressure"),
                ("Stopping distance factors", "Speed, tires, brakes, and road all matter.", "Stopping distance grows with speed and shrinks with good tires and dry pavement.", "freeway", "static", "stop_distance", "Speed multiplies stop"),
                ("Cover the brake", "Hover your foot when hazards appear.", "Covering the brake cuts reaction time when you see potential hazards ahead.", "residential", "tilt-up", "cover_brake", "Ready to brake"),
                ("Speed on ramps", "Match freeway flow before merging.", "Use the ramp to accelerate to near freeway speed so merging is smoother and safer.", "freeway", "ken-burns", "merge", "Match speed"),
                ("Slow vehicle pullouts", "Use turnouts so others can pass.", "On two-lane roads, use turnouts when five or more vehicles are backed up behind you.", "freeway", "push-in", "turnout", "Let them pass"),
                ("Minimum speed sense", "Too slow can also be unsafe.", "Driving far below traffic speed without cause can create hazards — keep with the flow when safe and legal.", "freeway", "pull-out", "slow_traffic", "Flow when safe"),
            ],
        ),
        (
            "ca-driver-ed-08-lanes-freeway",
            "CA Driver Ed — Lanes & freeway driving",
            "Merging, passing, HOV, and lane discipline.",
            [
                ("Mirror-signal-shoulder", "Every lane change needs a shoulder check.", "Check mirrors, signal, glance over your shoulder, then move smoothly into the gap.", "freeway", "ken-burns", "lane_change", "Shoulder check"),
                ("Freeway merge zipper", "Alternate gaps when lanes end.", "When two lanes merge, take turns — zipper merge reduces last-second cut-ins.", "freeway", "push-in", "merge", "Zipper merge"),
                ("Left lane for passing", "Pass, then return right when safe.", "Use the left lane to pass, then move right so faster traffic can continue.", "freeway", "pull-out", "pass_left", "Pass then right"),
                ("HOV carpool lanes", "Meet occupancy or enter legally.", "HOV lanes require the posted number of occupants or an authorized pass.", "freeway", "pan-right", "hov", "Check occupancy"),
                ("Exit early preparation", "Change lanes early for your exit.", "Read guide signs early and move toward your exit lane with time to spare.", "freeway", "pan-left", "exit_prep", "Plan the exit"),
                ("No stopping on freeway", "Only stop fully off the roadway if you must.", "Do not stop in a travel lane. If you must stop, get fully onto the shoulder and turn on hazards.", "freeway", "zoom-punch", "shoulder_stop", "Full shoulder only"),
                ("Weave zones", "Expect conflict where enter and exit meet.", "In weave areas, scan both sides and keep a flexible gap for entering and exiting cars.", "freeway", "dolly-shake", "weave", "Scan both sides"),
                ("Passing on the right", "Legal in some multi-lane cases — still careful.", "Passing on the right may be allowed on multi-lane roads but watch for right-turning vehicles.", "freeway", "static", "pass_right", "Watch right turns"),
                ("Truck climbing lanes", "Use extra lanes to pass slow trucks on hills.", "Climbing lanes let faster traffic pass — return right after you clear the truck.", "freeway", "tilt-up", "hill_truck", "Pass then merge back"),
                ("Freeway hypnosis", "Break monotony on long trips.", "On long drives, vary focus, take breaks, and avoid staring at one point ahead.", "freeway", "ken-burns", "long_drive", "Stay alert"),
                ("Wrong-way driver response", "Pull right, slow, warn — never swerve into them.", "If you see a wrong-way driver, move right, slow, honk, and flash lights.", "freeway", "push-in", "wrong_way", "Right + warn"),
                ("Lane splitting awareness", "Expect motorcycles between lanes in CA.", "California allows motorcycle lane splitting when done safely — check mirrors before changing lanes.", "freeway", "pull-out", "lane_split", "Expect bikes between"),
            ],
        ),
        (
            "ca-driver-ed-09-pedestrians-bikes",
            "CA Driver Ed — Pedestrians & bicycles",
            "Crosswalks, three-foot pass, and door-zone safety.",
            [
                ("Marked crosswalk duty", "Stop for people in the crosswalk.", "Yield to pedestrians in marked crosswalks and do not pass a vehicle stopped at a crosswalk.", "intersection", "ken-burns", "ped_cross", "Stop for walkers"),
                ("Unmarked crosswalks", "Corners are crosswalks too.", "Intersections have crosswalks even without paint — yield to people crossing.", "intersection", "push-in", "ped_cross", "Paint optional"),
                ("Mid-block joggers", "Expect people outside crosswalks.", "Scan for joggers and walkers mid-block, especially near parks and schools.", "residential", "pull-out", "ped_cross", "Scan mid-block"),
                ("Three-foot bike pass", "Leave at least three feet when passing.", "When overtaking a bicycle, leave at least three feet of space or wait until you can.", "residential", "pan-right", "bike_share", "3-foot pass"),
                ("Bike lanes respect", "Do not drive or park in bike lanes.", "Bike lanes are for bicycles — do not drive, stop, or park in them except where allowed.", "residential", "pan-left", "bike_share", "Keep bike lanes clear"),
                ("Dutch reach dooring", "Look back before opening your door.", "Open the door with the far hand so you naturally look for cyclists first.", "residential", "zoom-punch", "door_zone", "Look before you open"),
                ("Right hook risk", "Check for bikes before right turns.", "Before turning right, shoulder-check for cyclists coming up on your right.", "intersection", "dolly-shake", "bike_share", "Check right for bikes"),
                ("Left cross risk", "Watch bikes when turning left across a lane.", "Left turns across bike lanes need a clear gap — bikes move faster than you think.", "intersection", "static", "bike_box", "Bikes move fast"),
                ("Shared-use paths", "Yield where paths meet roads.", "Where a shared path crosses a road, slow and yield according to signs and markings.", "residential", "tilt-up", "ped_cross", "Path crossings"),
                ("Night bike lights", "Expect poorly lit riders — slow down.", "At night, scan carefully; not every cyclist has bright lights.", "night-road", "ken-burns", "bike_share", "Scan in the dark"),
            ],
        ),
        (
            "ca-driver-ed-10-trucks-motorcycles",
            "CA Driver Ed — Trucks & motorcycles",
            "No-zones, wide turns, and motorcycle visibility.",
            [
                ("Truck no-zones", "If you cannot see their mirrors, they cannot see you.", "Trucks have large blind spots on all sides — avoid lingering beside or close behind.", "freeway", "ken-burns", "truck_freeway", "Stay out of no-zones"),
                ("Truck stopping distance", "Never cut in and brake after passing.", "After passing a truck, leave a large gap before you pull in — they need long stopping distance.", "freeway", "push-in", "truck_freeway", "Big gap after pass"),
                ("Wide right turns", "Give trucks room to swing left before turning right.", "Trucks may move left before a right turn — do not squeeze inside.", "intersection", "pull-out", "truck_freeway", "Don't squeeze inside"),
                ("Mountain downgrades", "Trucks may use runaway ramps — stay clear.", "On steep grades, give trucks space and never block a runaway truck ramp.", "freeway", "pan-right", "hill_truck", "Clear the ramp"),
                ("Look twice for motorcycles", "Motorcycles hide in blind spots.", "Shoulder-check for motorcycles before every lane change — they are easy to miss.", "freeway", "pan-left", "moto_aware", "Look twice"),
                ("Full lane for motorcycles", "Give motorcycles a full lane width.", "Do not share a lane side-by-side with a motorcycle unless lane splitting is occurring safely.", "freeway", "zoom-punch", "moto_aware", "Full lane"),
                ("Motorcycle following gap", "Leave extra space behind bikes.", "Motorcycles can stop quickly — keep a generous following distance.", "freeway", "dolly-shake", "moto_aware", "Extra following space"),
                ("Lane splitting safe response", "Hold your lane; do not squeeze the rider.", "If a motorcycle splits lanes near you, hold a steady line and avoid sudden moves.", "freeway", "static", "lane_split", "Hold steady"),
                ("Filter at lights", "Expect bikes between stopped cars.", "At red lights, motorcycles may filter forward — check before you inch up.", "intersection", "tilt-up", "lane_split", "Check between cars"),
                ("Truck wind blast", "Grip the wheel when passing large vehicles.", "Passing trucks can buffet your car — keep both hands on the wheel and a steady speed.", "freeway", "ken-burns", "truck_freeway", "Two hands on wheel"),
            ],
        ),
        (
            "ca-driver-ed-11-school-buses",
            "CA Driver Ed — School buses & school zones",
            "Red lights, stop arms, and child unpredictability.",
            [
                ("Red lights and stop arm", "Both directions stop on undivided roads.", "When a school bus shows red flashing lights and a stop arm on an undivided road, traffic both ways must stop.", "school-zone", "ken-burns", "school_zone", "Red lights = stop"),
                ("Divided highway exception", "Only same-direction traffic stops on divided roads.", "On a divided highway, usually only traffic traveling the same direction as the bus must stop.", "school-zone", "push-in", "school_bus_kids", "Know the exception"),
                ("Yellow bus lights", "Prepare to stop — children may load soon.", "Flashing yellow bus lights mean slow down and prepare to stop.", "school-zone", "pull-out", "school_bus_kids", "Yellow = prepare"),
                ("Children darting out", "Expect kids from behind the bus.", "Children may cross in front of or dash from behind a bus — wait until clear.", "school-zone", "pan-right", "school_zone", "Kids may dart"),
                ("School zone flashing beacons", "Obey reduced limits when lights flash.", "Flashing school-zone beacons often activate lower speed limits — obey them.", "school-zone", "pan-left", "school_zone", "Beacon = slower"),
                ("Crossing guards", "Follow the guard's directions.", "Crossing guards control the crosswalk — stop when they signal and wait for their clearance.", "school-zone", "zoom-punch", "ped_cross", "Obey the guard"),
                ("Arrival and dismissal peaks", "Extra caution at bell times.", "Traffic near schools peaks at arrival and dismissal — expect congestion and double-parked cars.", "school-zone", "dolly-shake", "school_zone", "Bell-time caution"),
                ("No passing near schools", "Do not pass vehicles stopped for kids.", "Never pass a vehicle that is stopped for pedestrians in a school crosswalk.", "school-zone", "static", "ped_cross", "No passing"),
                ("Field trip buses", "Same stop rules apply to school activity buses.", "Activity buses loading students generally follow the same stop-arm rules — treat them seriously.", "school-zone", "tilt-up", "school_bus_kids", "Activity buses too"),
                ("Parking near schools", "Keep crosswalks and bus zones clear.", "Do not park in bus loading zones or block crosswalks near schools.", "school-zone", "ken-burns", "parking", "Clear the bus zone"),
            ],
        ),
        (
            "ca-driver-ed-12-work-rail",
            "CA Driver Ed — Work zones & railroads",
            "Cones, flaggers, gates, and tracks.",
            [
                ("Work zone speed", "Obey reduced speeds; fines often double.", "Slow to the posted work-zone speed — workers are close to traffic and fines often increase.", "work-zone", "ken-burns", "work_zone", "Slow in work zones"),
                ("Follow the flagger", "Hand signals override your usual plan.", "Flaggers control temporary right-of-way — stop or proceed exactly as directed.", "work-zone", "push-in", "work_zone", "Flagger is boss"),
                ("Lane shifts and tapers", "Merge early at cones.", "When cones create a taper, merge as soon as you can do so safely — avoid the last-second dive.", "work-zone", "pull-out", "work_zone", "Merge early"),
                ("Workers on foot", "Give a wide berth.", "Expect workers near the edge of the lane — leave extra lateral space.", "work-zone", "pan-right", "work_zone", "Space for workers"),
                ("Night work zones", "Glare and temporary lights confuse depth.", "Night construction lighting can hide cones — slow more than you think you need to.", "night-road", "pan-left", "work_zone", "Slow at night work"),
                ("Railroad flashing lights", "Never drive around gates.", "When lights flash or gates lower, stop at least 15 feet from the nearest rail.", "intersection", "zoom-punch", "rail_cross", "Gates down = stop"),
                ("Multiple tracks", "Wait for a second train.", "After one train passes, look both ways — another train may come on a second track.", "intersection", "dolly-shake", "rail_cross", "Check second track"),
                ("Stalled on tracks", "Exit immediately; run at an angle toward the train.", "If your vehicle stalls on tracks, get everyone out and move away at an angle toward the oncoming train.", "intersection", "static", "rail_cross", "Get out now"),
                ("Quiet zones", "Trains may not horn — still stop for signals.", "In quiet zones trains may not sound horns — signals and gates still mean stop.", "intersection", "tilt-up", "rail_cross", "No horn still stop"),
                ("Emergency vehicles at tracks", "Never follow EMS onto tracks.", "Do not follow an emergency vehicle across tracks unless signals are clear for you too.", "intersection", "ken-burns", "ems_intersect", "Clear signals for you"),
            ],
        ),
        (
            "ca-driver-ed-13-parking-maneuvers",
            "CA Driver Ed — Parking & maneuvers",
            "Curb colors, hills, parallel parking, and clearances.",
            [
                ("Colored curb meanings", "Read curb colors before you leave the car.", "Red, blue, green, yellow, and white curbs each carry different parking rules — learn your city's code.", "residential", "ken-burns", "parking", "Read the curb"),
                ("Hydrant clearance", "Stay far enough from fire hydrants.", "Do not park too close to a fire hydrant — emergency crews need immediate access.", "residential", "push-in", "parking", "Clear the hydrant"),
                ("Crosswalk and driveway clearance", "Keep crossings and driveways open.", "Parking too close to crosswalks, stop signs, or driveways blocks sight lines and access.", "residential", "pull-out", "parking", "Protect sight lines"),
                ("Hill parking uphill curb", "Turn wheels away from the curb uphill.", "When parking uphill with a curb, turn wheels away from the curb and set the parking brake.", "residential", "pan-right", "parking", "Uphill = away"),
                ("Hill parking downhill curb", "Turn wheels toward the curb downhill.", "When parking downhill with a curb, turn wheels toward the curb so a roll hits the curb.", "residential", "pan-left", "parking", "Downhill = toward"),
                ("Parallel parking steps", "Signal, align, reverse slowly, straighten.", "Signal, align with the car ahead, reverse into the space, then straighten and center.", "residential", "zoom-punch", "parking", "Slow and controlled"),
                ("Perpendicular parking", "Center in the stall; wheels straight.", "Pull into the stall centered with wheels straight so you do not stick out into the aisle.", "residential", "dolly-shake", "parking", "Center the stall"),
                ("Backing out of stalls", "Creep and yield to aisle traffic.", "Back out slowly, check both sides, and yield to pedestrians and cars in the aisle.", "residential", "static", "driveway", "Creep and check"),
                ("No double parking", "Never block a travel lane to wait.", "Double parking blocks traffic and emergency access — find a legal space.", "residential", "tilt-up", "parking", "No double parking"),
                ("Disabled parking rules", "Only with a valid placard or plates.", "Blue curb and disabled stalls require a valid placard or plates — misuse is heavily fined.", "residential", "ken-burns", "parking", "Placard required"),
            ],
        ),
        (
            "ca-driver-ed-14-night-weather",
            "CA Driver Ed — Night & weather",
            "Headlights, fog, rain, and hydroplaning.",
            [
                ("Headlight hours", "Lights on from dusk to dawn and in poor visibility.", "Use headlights from 30 minutes after sunset to 30 minutes before sunrise and whenever visibility is poor.", "night-road", "ken-burns", "night_drive", "Lights when needed"),
                ("Dim high beams", "Dim for oncoming and when following.", "Dim high beams for oncoming traffic and when you are following another vehicle closely.", "night-road", "push-in", "night_drive", "Dim for others"),
                ("Overdriving headlights", "If you cannot stop within what you see, you are too fast.", "At night, drive so you can stop within the distance your headlights reveal.", "night-road", "pull-out", "night_drive", "Stop within the light"),
                ("Fog low beams", "High beams bounce back in fog.", "In fog use low beams — high beams reflect and worsen glare.", "freeway", "pan-right", "rain_drive", "Low beams in fog"),
                ("Rain first minutes", "Roads are slickest just as rain begins.", "Oil and water mix when rain starts — slow down immediately in the first minutes of rain.", "freeway", "pan-left", "rain_drive", "First rain = slick"),
                ("Hydroplaning response", "Ease off the gas; steer straight.", "If you hydroplane, ease off the gas and steer straight until the tires regain grip — avoid sudden braking.", "freeway", "zoom-punch", "rain_drive", "Ease off, steer straight"),
                ("Standing water", "Slow before the puddle.", "Standing water can hide potholes and cause hydroplaning — slow before you hit it.", "freeway", "dolly-shake", "rain_drive", "Slow for puddles"),
                ("Wind gusts", "Two hands; watch high-profile vehicles.", "In strong wind, keep both hands on the wheel and give trucks and vans extra space.", "freeway", "static", "truck_freeway", "Two hands in wind"),
                ("Ice and black ice", "Bridges freeze first.", "Bridges and shaded spots freeze first — slow early and avoid sudden inputs.", "freeway", "tilt-up", "rain_drive", "Bridges freeze first"),
                ("Sun glare", "Visor, clean windshield, slower speed.", "Low sun can blind you — use the visor, keep glass clean, and slow until you can see.", "freeway", "ken-burns", "multi_cars", "Glare = slow"),
            ],
        ),
        (
            "ca-driver-ed-15-emergency-special",
            "CA Driver Ed — Emergency & special situations",
            "Sirens, move-over, stalls, and animals.",
            [
                ("Pull right for sirens", "Clear a path to the right edge.", "When you hear a siren or see emergency lights, check mirrors, signal, pull to the right, and stop.", "freeway", "ken-burns", "ambulance_right", "Pull right & stop"),
                ("Move-over law", "Change lanes away from stopped responders.", "When approaching stopped emergency or tow vehicles with lights, move over a lane if safe or slow significantly.", "freeway", "push-in", "ambulance_right", "Move over or slow"),
                ("Do not block intersections for EMS", "Clear the box first.", "Never stop in an intersection for an emergency vehicle — clear it, then pull over.", "intersection", "pull-out", "ems_intersect", "Clear the intersection"),
                ("Tire blowout", "Grip, ease off gas, steer straight.", "If a tire blows, hold the wheel firmly, ease off the gas, and steer straight to a safe stop.", "freeway", "pan-right", "shoulder_stop", "Grip and ease off"),
                ("Brake failure", "Pump, downshift, parking brake gradual.", "If brakes fail, pump the pedal, downshift, and apply the parking brake gradually while steering to safety.", "freeway", "pan-left", "shoulder_stop", "Pump · downshift · park brake"),
                ("Engine stall in traffic", "Signal, steer to safety, hazards on.", "If the engine stalls, shift to neutral if needed, steer off the roadway, and turn on hazard lights.", "freeway", "zoom-punch", "shoulder_stop", "Hazards on"),
                ("Animals in roadway", "Brake firmly; do not swerve into traffic.", "If an animal appears, brake firmly in a straight line — swerving can cause a worse crash.", "freeway", "dolly-shake", "rural_animal", "Brake, don't swerve"),
                ("Flooded roadway", "Turn around, don't drown.", "Never drive into flooded roadway — water hides depth and current. Turn around.", "freeway", "static", "rain_drive", "Turn around"),
                ("Smoke or dust cloud", "Slow; be ready for stopped traffic.", "Smoke or dust can hide stopped cars — slow immediately and increase following distance.", "freeway", "tilt-up", "rain_drive", "Slow for clouds"),
                ("Police traffic stop", "Signal, pull right, stay calm.", "When signaled to stop, pull safely to the right, stay in the vehicle, and keep hands visible.", "residential", "ken-burns", "adult_car", "Pull right, hands visible"),
            ],
        ),
        (
            "ca-driver-ed-16-distracted-impaired",
            "CA Driver Ed — Distracted & impaired driving",
            "Phones, fatigue, alcohol, and drugs.",
            [
                ("Handheld phone ban", "Handheld calling and texting while driving are illegal.", "California restricts handheld phone use while driving — use hands-free or pull over safely.", "freeway", "ken-burns", "phone_ban", "Phone down"),
                ("Hands-free still distracts", "Conversation still steals attention.", "Hands-free is safer legally but still distracts — keep calls short or pull over for complex talks.", "freeway", "push-in", "phone_ban", "Attention first"),
                ("Dashboard screens", "Set navigation before you move.", "Program navigation and playlists before you drive — do not stare at screens in motion.", "residential", "pull-out", "adult_car", "Set it before you go"),
                ("Eating and grooming", "Pull over for tasks that need hands or eyes.", "Eating, makeup, and reaching for dropped items take eyes and hands off the driving task.", "residential", "pan-right", "adult_car", "Pull over for tasks"),
                ("Passenger distraction", "You control the cabin.", "Ask passengers to keep noise down when you need focus — the driver owns the cabin safety.", "residential", "pan-left", "family_car", "Driver sets focus"),
                ("Drowsy driving", "Sleep beats caffeine for fatigue.", "If you are drowsy, stop and rest — microsleeps at highway speed are deadly.", "night-road", "zoom-punch", "night_drive", "Rest, don't push"),
                ("BAC 0.08 adult limit", "Adults 21+ face 0.08 percent BAC limit.", "For drivers 21 and older, the BAC limit is 0.08 percent — impairment starts earlier.", "night-road", "dolly-shake", "night_drive", "0.08 is the limit"),
                ("Zero tolerance under 21", "Any measurable alcohol can mean sanctions.", "Drivers under 21 face zero-tolerance rules for alcohol — arrange another ride.", "night-road", "static", "night_drive", "Zero tolerance under 21"),
                ("Medication impairment", "Read labels; ask a pharmacist.", "Some prescriptions and over-the-counter meds impair driving — check warnings before you drive.", "residential", "tilt-up", "adult_car", "Check the label"),
                ("Cannabis and driving", "Impaired is impaired — wait it out.", "Cannabis can impair judgment and reaction time. Do not drive until you are fully sober.", "night-road", "ken-burns", "night_drive", "Wait until sober"),
            ],
        ),
        (
            "ca-driver-ed-17-vehicle-checks",
            "CA Driver Ed — Vehicle safety checks",
            "Pre-drive inspections and warning lights.",
            [
                ("Walk-around check", "Look for leaks, low tires, and obstacles.", "Before you drive, walk around the car — check tires, lights, and anything behind the bumper.", "residential", "ken-burns", "adult_car", "Walk around first"),
                ("Tire pressure and tread", "Bald or soft tires fail in emergencies.", "Check tread and pressure regularly — underinflation and worn tread lengthen stopping distance.", "residential", "push-in", "adult_car", "Tires matter"),
                ("Lights and signals", "Confirm brake, turn, and headlamps work.", "Test headlights, brake lights, and turn signals so others can predict your moves.", "residential", "pull-out", "adult_car", "Lights working?"),
                ("Mirrors and seat", "Adjust before you shift into drive.", "Set seat, mirrors, and steering wheel before you move — not while rolling.", "residential", "pan-right", "adult_car", "Adjust before moving"),
                ("Windshield and wipers", "See clearly in rain.", "Keep glass clean and replace streaking wipers before the storm arrives.", "residential", "pan-left", "rain_drive", "Clear glass"),
                ("Fuel and range", "Do not run to empty.", "Keep enough fuel for traffic delays — running out on a freeway is a hazard.", "freeway", "zoom-punch", "adult_car", "Don't run empty"),
                ("Warning light response", "Red means stop safely soon.", "Learn your dash icons — red warnings usually mean stop safely and get help.", "residential", "dolly-shake", "adult_car", "Red = stop safely"),
                ("Brake feel check", "Soft pedal means get service.", "If the brake pedal feels soft or sinks, do not drive — have the system checked.", "residential", "static", "adult_car", "Soft pedal = service"),
                ("Child seat basics", "Install correctly; never front airbag with rear-facing.", "Use the correct car seat for age and size and never place a rear-facing seat in front of an active airbag.", "residential", "tilt-up", "family_car", "Seat the right way"),
                ("Loose cargo", "Secure loads so nothing becomes a projectile.", "Unsecured cargo can injure occupants in a sudden stop — stash or strap it down.", "residential", "ken-burns", "adult_car", "Secure the load"),
            ],
        ),
        (
            "ca-driver-ed-18-provisional-teen",
            "CA Driver Ed — Provisional & teen rules",
            "California provisional license restrictions and safe habits.",
            [
                ("Provisional overview", "Extra rules for new teen drivers.", "Provisional licenses add passenger and night limits designed to reduce crash risk for new drivers.", "residential", "ken-burns", "adult_teen_car", "Extra teen rules"),
                ("Passenger restriction window", "Friends in the back usually wait.", "During the first year, carrying young friends is typically restricted without a qualified supervisor.", "residential", "push-in", "family_car", "Passengers limited"),
                ("Night restriction window", "Plan activities around curfew.", "Know the current night driving window for provisional holders and plan rides home early.", "night-road", "pull-out", "night_drive", "Plan around curfew"),
                ("Exceptions exist — confirm them", "Work and school exceptions vary.", "Some exceptions exist for work or school — confirm current handbook language before relying on them.", "residential", "pan-right", "adult_teen", "Confirm exceptions"),
                ("Peer pressure in the car", "You are responsible for every choice.", "Friends may push risky moves — your license and safety come first.", "residential", "pan-left", "family_car", "You decide"),
                ("Parent-teen practice plan", "Short, frequent practice beats rare marathons.", "Practice in varied conditions: day, night, rain, freeways, and busy arterials.", "residential", "zoom-punch", "adult_teen_car", "Varied practice"),
                ("Phone rules for teens", "Zero tolerance for handheld use.", "Teen drivers should treat the phone as off-limits while the car is in motion.", "freeway", "dolly-shake", "phone_ban", "Phone away"),
                ("Graduated steps to full license", "Time and clean record unlock full privileges.", "Full adult privileges come after holding the provisional license for the required period without serious violations.", "residential", "static", "adult_teen", "Earn full privileges"),
                ("Crash risk peak ages", "Inexperience plus speed is deadly.", "New drivers crash more often — keep speeds modest and space large while skills build.", "freeway", "tilt-up", "follow_gap", "Space while learning"),
                ("Celebrate safe miles", "Safe habits are the real milestone.", "Logging safe supervised miles matters more than rushing to drive alone.", "residential", "ken-burns", "adult_teen_car", "Safe miles count"),
            ],
        ),
        (
            "ca-driver-ed-19-city-rural",
            "CA Driver Ed — City & rural driving",
            "Dense traffic, blind curves, and country roads.",
            [
                ("City scan rhythm", "Eyes move; never stare.", "In cities, keep your eyes moving among mirrors, signals, bikes, and pedestrians.", "intersection", "ken-burns", "scan_intersect", "Keep eyes moving"),
                ("One-way confusion", "Confirm direction before you turn.", "City grids include one-ways — read signs before you commit to a turn.", "intersection", "push-in", "one_way", "Confirm direction"),
                ("Delivery double-park risk", "Expect doors and vans.", "Delivery vans may stop suddenly — leave an out and watch for opening doors.", "residential", "pull-out", "door_zone", "Expect delivery vans"),
                ("Blind intersections downtown", "Creep until you can see.", "Where buildings block the view, creep forward until you can see cross traffic.", "intersection", "pan-right", "uncontrolled", "Creep to see"),
                ("Rural two-lane passing", "Pass only with sight distance and legal lines.", "On two-lane roads, pass only where lines and sight distance allow — never on hills or curves.", "freeway", "pan-left", "no_pass", "Sight distance first"),
                ("Gravel and dirt shoulders", "Slow; steering gets light.", "Loose gravel reduces traction — slow before turns and avoid hard braking.", "freeway", "zoom-punch", "shoulder", "Slow on gravel"),
                ("Unmarked rural intersections", "Assume cross traffic may not stop.", "Many rural intersections lack signals — slow and be ready to yield.", "intersection", "dolly-shake", "uncontrolled", "Assume they won't stop"),
                ("Farm equipment", "Pass wide and slow.", "Farm equipment is wide and slow — wait for a safe gap and give plenty of space.", "freeway", "static", "turnout", "Wide and slow pass"),
                ("Narrow bridges", "Yield when required; one lane at a time.", "Some rural bridges are one-lane — obey yield signs and wait your turn.", "freeway", "tilt-up", "yield_merge", "One lane — wait"),
                ("City freeway transitions", "Ramp meters and short merges.", "Urban freeways often have ramp meters and short merges — cooperate and match speed.", "freeway", "ken-burns", "merge", "Meter · match · merge"),
            ],
        ),
        (
            "ca-driver-ed-20-crashes-insurance",
            "CA Driver Ed — Crashes & insurance",
            "What to do after a collision and proof of insurance.",
            [
                ("Stop and secure the scene", "Never leave the scene of a crash.", "If involved in a crash, stop, turn on hazards if safe, and move out of traffic when you can.", "intersection", "ken-burns", "crash_scene", "Stop · hazards · safe spot"),
                ("Call for injuries", "People first, then property.", "Call 911 when anyone is hurt or when the crash blocks a roadway.", "intersection", "push-in", "crash_scene", "Injuries → 911"),
                ("Exchange information", "Names, contacts, license, insurance.", "Exchange names, contact info, driver license numbers, and insurance details with others involved.", "intersection", "pull-out", "crash_scene", "Exchange info"),
                ("Do not argue fault", "Facts and photos beat roadside debate.", "Do not argue fault at the scene — document facts and let insurers investigate.", "intersection", "pan-right", "crash_scene", "No fault debate"),
                ("Hit and run response", "Note details; report promptly.", "If the other driver flees, note plate, vehicle, and direction, then report to police.", "intersection", "pan-left", "crash_scene", "Note · report"),
                ("Proof of insurance", "Carry evidence of financial responsibility.", "California requires proof of financial responsibility — know how to show it digitally or on paper.", "residential", "zoom-punch", "adult_car", "Carry proof"),
                ("Uninsured motorist awareness", "Protect yourself with coverage.", "Uninsured and underinsured motorist coverage helps if the other driver lacks insurance.", "residential", "dolly-shake", "adult_car", "Know your coverage"),
                ("Report when required", "Some crashes must be reported to DMV or police.", "Report crashes that meet injury or damage thresholds as required by California law.", "residential", "static", "adult_car", "Know report thresholds"),
                ("Witnesses and cameras", "Gather neutral evidence.", "Ask witnesses for contact info and note nearby cameras that may have recorded the crash.", "intersection", "tilt-up", "crash_scene", "Witnesses help"),
                ("Aftercare and follow-up", "Seek medical care for delayed symptoms.", "Some injuries appear later — seek care and notify your insurer promptly.", "residential", "ken-burns", "adult_car", "Follow up on health"),
            ],
        ),
        (
            "ca-driver-ed-21-roundabouts-complex",
            "CA Driver Ed — Roundabouts & complex moves",
            "Circles, multi-lane choices, and unusual controls.",
            [
                ("Single-lane roundabout", "Yield, enter, signal to exit.", "Yield to circulating traffic, enter when clear, and signal before your exit.", "intersection", "ken-burns", "roundabout", "Yield · circulate · exit"),
                ("Multi-lane roundabout", "Choose the lane before you enter.", "Pick the correct lane for your exit before entering a multi-lane roundabout.", "intersection", "push-in", "roundabout", "Lane before entry"),
                ("Do not stop in the circle", "Keep moving once inside unless blocked.", "Avoid stopping in the circulating roadway except to avoid a collision.", "intersection", "pull-out", "roundabout", "Keep circulating"),
                ("Trucks in roundabouts", "Give large vehicles extra room.", "Trucks may use more than one lane in a roundabout — give them space.", "intersection", "pan-right", "truck_freeway", "Space for trucks"),
                ("Pedestrians at roundabouts", "Yield at each crosswalk.", "Yield to pedestrians at the entry and exit crosswalks of a roundabout.", "intersection", "pan-left", "roundabout", "Crosswalks still count"),
                ("Traffic circles vs roundabouts", "Follow the specific signs on site.", "Older traffic circles may differ from modern roundabouts — obey the signs you see.", "intersection", "zoom-punch", "roundabout", "Obey site signs"),
                ("Jughandle turns", "Some lefts are made by turning right first.", "Jughandle designs send left-turning traffic to the right first — follow the markings.", "intersection", "dolly-shake", "turn_lane", "Follow the jughandle"),
                ("Protected-permissive lefts", "Green ball means yield to oncoming.", "A green ball left turn is permissive — yield to oncoming traffic; a green arrow is protected.", "intersection", "static", "green_arrow", "Ball vs arrow"),
                ("Dual right-turn lanes", "Stay in your lane through the turn.", "Where two lanes may turn right, stay in your lane and watch for merges after the turn.", "intersection", "tilt-up", "multi_turn", "Hold your lane"),
                ("Complex signal timing", "Wait for your arrow; do not jump.", "At complex signals, wait for the indication that applies to your movement — do not assume.", "intersection", "ken-burns", "light_red", "Wait for your signal"),
            ],
        ),
        (
            "ca-driver-ed-22-review-practice",
            "CA Driver Ed — Review & practice habits",
            "Handbook study, quizzes, and calm test-day habits.",
            [
                ("Handbook is the authority", "Official wording beats any study aid.", "Re-read the California Driver's Handbook sections you find hardest — it is the authority.", "residential", "ken-burns", "adult_teen", "Handbook = authority"),
                ("Short study blocks", "Fifteen to twenty minutes with a quiz beats cramming.", "Use short study blocks and practice quizzes instead of marathon cramming sessions.", "residential", "push-in", "adult_teen", "Short blocks win"),
                ("Practice test habit", "Missed items become your next lesson.", "After each quiz, restudy every miss until you can explain the rule in your own words.", "residential", "pull-out", "adult_teen", "Restudy misses"),
                ("Scenario imagination", "Picture the scene, then the correct action.", "For each rule, imagine a street scene and say aloud what you would do.", "intersection", "pan-right", "scan_intersect", "Picture then act"),
                ("Calm behind the wheel", "Smooth inputs show control.", "On the road test, smooth braking, signaling, and scanning matter as much as knowing rules.", "residential", "pan-left", "adult_teen_car", "Smooth = skilled"),
                ("Narrate your scan", "Say what you see while you practice.", "During practice drives, quietly name hazards you see — it builds scanning habits.", "residential", "zoom-punch", "cover_brake", "Name the hazards"),
                ("Ask when unsure", "Instructors and the handbook beat guessing.", "If a rule is unclear, look it up or ask a qualified instructor — do not guess on the road.", "residential", "dolly-shake", "adult_teen", "Ask · don't guess"),
                ("Sleep before test day", "Fatigue looks like poor skill.", "Rest well before knowledge or drive tests — fatigue causes careless mistakes.", "night-road", "static", "night_drive", "Rest before test day"),
                ("Documents for the test", "Bring what the DMV checklist requires.", "Check the DMV appointment checklist so you arrive with required documents and fees.", "residential", "tilt-up", "adult_car", "Bring the checklist"),
                ("Keep learning after the license", "Skills grow with deliberate practice.", "A license is a starting line — keep practicing freeway, night, and rain skills with a mentor.", "freeway", "ken-burns", "multi_cars", "License = starting line"),
            ],
        ),
    ]
    lessons: list[DriverLesson] = []
    for lesson_id, title, summary, rows in raw:
        scenarios: list[DriverScenario] = []
        for idx, (t, concept, narr, backdrop, camera, preset, callout) in enumerate(rows):
            scenarios.append(
                DriverScenario(
                    scenario_id=f"{lesson_id}-{idx:02d}",
                    lesson_id=lesson_id,
                    slide_index=idx,
                    title=t,
                    concept=concept,
                    narration=narr,
                    backdrop=backdrop,
                    camera=camera,
                    preset=preset,
                    callout=callout,
                )
            )
        lessons.append(
            DriverLesson(
                lesson_id=lesson_id,
                title=title,
                summary=summary,
                scenarios=tuple(scenarios),
            )
        )
    return tuple(lessons)


DRIVER_ED_LESSONS: tuple[DriverLesson, ...] = _build_lessons()
DRIVER_ED_LESSON_IDS: tuple[str, ...] = tuple(L.lesson_id for L in DRIVER_ED_LESSONS)


def iter_driver_scenarios() -> Iterator[DriverScenario]:
    for lesson in DRIVER_ED_LESSONS:
        yield from lesson.scenarios


def driver_scenario_count() -> int:
    return sum(len(L.scenarios) for L in DRIVER_ED_LESSONS)


def build_driver_ed_segments(lesson_id: str) -> list[SegmentStoryboard]:
    for lesson in DRIVER_ED_LESSONS:
        if lesson.lesson_id != lesson_id:
            continue
        return [
            SegmentStoryboard(
                lesson_id=lesson_id,
                slide_index=sc.slide_index,
                verse_label=sc.title,
                learning_goal=sc.concept,
                scene=_scene_for(sc),
            )
            for sc in lesson.scenarios
        ]
    return []


def lesson_txt_for(lesson: DriverLesson) -> str:
    """Render a sample-curriculum lesson.txt for ``lesson``."""
    lines = [
        f"LESSON: {lesson.title}",
        "LANGUAGE: en",
        "AUDIENCE: general",
        "TRACK: Certifications",
        "LEVEL: Certification prep",
        "JURISDICTION: us-ca",
        "PREP_ONLY: true",
        "DELIVERY: 15–20 min short session",
        "FIT: Learners preparing for the California DMV knowledge / permit test.",
        f"SUMMARY: {lesson.summary} Study aid only — not a DMV-approved driver education course.",
        "",
    ]
    for sc in lesson.scenarios:
        lines.append(f"SLIDE {sc.slide_index + 1} | {sc.title}")
        lines.append(sc.concept + " " + sc.narration)
        lines.append(f"NARRATION: {sc.narration}")
        lines.append("")
    lines.append("FACT: Always verify rules in the current California Driver's Handbook.")
    lines.append("FACT: This Salareen lesson is practice prep, not DMV-approved education.")
    return "\n".join(lines).rstrip() + "\n"

