"""Build class scene pools (JSONL) for driver's ed and food safety.

Runtime loads the JSONL through the content-pack catalog. This script is the
authoring tool: each row is a different situation, and a number appears only
when that number changes the required action (speed, gap, temperature, day).
"""

from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


from class_scene_stories import driver_scene_rows, food_scene_rows

ROOT = Path(__file__).resolve().parents[1]
OUT = (
    ROOT
    / "packages"
    / "shared"
    / "src"
    / "aoep_shared"
    / "data"
    / "content_packs"
    / "class_scenes"
)


def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def _wrongs(correct: str, pool: list[str]) -> list[str]:
    needle = _norm(correct)
    picked: list[str] = []
    seen = {needle}
    for item in pool:
        key = _norm(item)
        if not key or key in seen or needle in key or key in needle:
            continue
        seen.add(key)
        picked.append(item)
        if len(picked) == 3:
            break
    fillers = [
        "Ignore it and continue at the same speed.",
        "That rule is optional once traffic looks light.",
        "Do the opposite of what the control device says.",
    ]
    for item in fillers:
        if len(picked) >= 3:
            break
        if _norm(item) not in seen:
            picked.append(item)
    return picked[:3]


class Bank:
    def __init__(self, topic: str) -> None:
        self.topic = topic
        self.rows: list[dict] = []
        self._prompts: set[str] = set()

    def add(
        self,
        skill: str,
        prompt: str,
        acceptable: str,
        rubric: str,
        spoken: str,
        wrongs: list[str],
    ) -> None:
        prompt = " ".join(prompt.split())
        acceptable = " ".join(acceptable.split())
        rubric = " ".join(rubric.split())
        spoken = " ".join(spoken.split())
        if prompt in self._prompts:
            raise SystemExit(f"duplicate prompt in {self.topic}: {prompt[:140]}")
        if len(prompt) < 40:
            raise SystemExit(f"prompt too short: {prompt}")
        if not acceptable or not rubric or not spoken:
            raise SystemExit(f"missing grade text: {prompt[:80]}")
        if len(spoken) > 240:
            raise SystemExit(f"spoken line too long ({len(spoken)}): {spoken}")
        self._prompts.add(prompt)
        self.rows.append(
            {
                "topic": self.topic,
                "skill": skill,
                "prompt": prompt,
                "acceptable": [acceptable],
                "rubric": [rubric],
                "spoken": spoken,
                "distractors": _wrongs(acceptable, wrongs),
                "locale": "en",
                "source_locale": "en",
            }
        )


# Tempting wrong moves reused inside a skill. Scene text still differs.
_ROW_WRONG = [
    "Roll through because the other car looks hesitant.",
    "The larger or faster vehicle goes first.",
    "Honk and take the gap before anyone else moves.",
    "Always yield to the car on your left.",
    "Arrival order does not matter; the car turning left always waits.",
    "A stop sign means slow to a crawl and go if you see nobody.",
]
_SPEED_WRONG = [
    "Drive the posted number no matter the weather.",
    "Match the car beside you even if that is over the limit.",
    "The posted limit is a target, so do not go slower.",
    "Speed up to get out of the bad weather faster.",
]
_PED_WRONG = [
    "Swerve around the person if the next lane looks empty.",
    "Honk so they hurry, then continue.",
    "Pedestrians must yield to cars once the light is green.",
    "Pass the stopped car; they are probably just waiting to park.",
]
_BUS_WRONG = [
    "Pass on the left if you do not see children yet.",
    "Stop only when you are behind the bus, never from the front.",
    "The amber lights mean you must already be fully stopped.",
    "A median does not matter; always stop for every school bus.",
]
_WX_WRONG = [
    "Use high beams in fog so you can see farther.",
    "Brake hard and steer sharply to regain grip.",
    "Keep cruise control on in heavy rain.",
    "Drive through water if the car ahead made it.",
]
_PARK_WRONG = [
    "Leave it in neutral on a hill so it can roll to the curb.",
    "Any open space at a blue curb is fine if you will be quick.",
    "The placard belongs to the car, so anyone may use it.",
    "You may stop in a red zone if the hazard lights are on.",
]
_FREEWAY_WRONG = [
    "Stop at the end of the on-ramp until someone lets you in.",
    "Cross the solid white line whenever your exit is close.",
    "Ride the truck's left side so you can see the mirror.",
    "Slow down in the through lane before you reach the exit lane.",
]
_EMERG_WRONG = [
    "Stand between the vehicles to explain what happened.",
    "Leave the scene if the damage looks minor and you are late.",
    "Move an injured person to the sidewalk so traffic can pass.",
    "Brake-check a tailgater so they back off.",
]
_FOOD_WRONG = [
    "Rinse it under hot water and serve it.",
    "Leave it out and decide after the rush.",
    "Taste it to see if it still seems fine.",
    "Put it in the freezer to make the temperature safe again.",
    "Wipe the surface and keep using the same gloves.",
    "Tell the guest it is probably fine if the kitchen is busy.",
]


def _drivers() -> Bank:
    bank = Bank("drivers-ed")
    _signs(bank)
    _signals(bank)
    _four_way(bank)
    _other_intersections(bank)
    _speed_and_space(bank)
    _people_and_buses(bank)
    _freeway_and_lanes(bank)
    _weather_night_emergency(bank)
    _parking_and_turns(bank)
    _license_and_impairment(bank)
    _sharing_and_special(bank)
    _signal_conflicts(bank)
    _hazard_by_road(bank)
    _gap_choices(bank)
    for row in driver_scene_rows():
        bank.add(*row, _ROW_WRONG + _SPEED_WRONG + _PED_WRONG)
    return bank


def _signs(bank: Bank) -> None:
    regulatory = [
        ("red octagon", "stop sign", "Come to a complete stop behind the limit line or crosswalk, then go only when it is clear.", "A stop sign requires a full stop, not a rolling slowdown.", "Full stop behind the line, then go when it is clear."),
        ("red and white triangle", "yield sign", "Slow down, be ready to stop, and give the right of way to traffic and pedestrians.", "Yield means give way. Stop if you cannot enter safely.", "Yield means slow and give way, and stop if you must."),
        ("red and white circle with a white bar", "do not enter sign", "Do not enter that road. Turn around by a safe route.", "Do Not Enter means you are facing the wrong direction.", "Do not enter. Turn around safely."),
        ("square red sign with a white horizontal bar", "wrong way sign", "You are going against traffic. Pull to the side and turn around when it is safe.", "Wrong Way means leave that roadway immediately by a safe turn.", "Wrong Way: get off that road safely."),
        ("white rectangle reading ONE WAY", "one-way sign", "Travel only in the direction of the arrow.", "One-way signs and arrows set the only legal direction.", "Follow the one-way arrow."),
        ("white sign with a crossed-out left arrow", "no left turn sign", "Do not turn left there, even on a green light.", "A no-left-turn sign overrides a green light.", "No left turn means no left turn."),
        ("white sign with a crossed-out U-turn arrow", "no U-turn sign", "Do not make a U-turn at that location.", "A posted U-turn ban is a legal duty, not a suggestion.", "The sign bans the U-turn."),
        ("white sign reading KEEP RIGHT", "keep right sign", "Stay to the right of the island or obstruction.", "Keep Right assigns the side you must pass on.", "Keep to the right of the divider."),
        ("black and white speed plaque reading 25", "25 mph speed sign", "Do not exceed 25 mph, and go slower if conditions are poor.", "A speed sign is a maximum under ideal conditions.", "Twenty-five is the maximum, not a target in bad conditions."),
        ("white sign with a red circle over a truck", "no trucks sign", "Do not take a truck or other banned vehicle onto that road. Reroute.", "A vehicle-class ban means choose another route.", "That road bans the truck. Use another route."),
        ("lane-use sign with a left-turn-only arrow over the left lane", "lane control sign", "Use the left lane only to turn left. Move over if you mean to go straight.", "Lane-use signs assign the movement for each lane.", "That lane is for the turn shown, not for going straight."),
        ("white sign reading NO PARKING ANY TIME", "no parking sign", "Do not park or leave the vehicle there.", "No Parking Any Time forbids leaving the vehicle.", "You cannot park there at any hour."),
    ]
    for shape, name, action, rubric, spoken in regulatory:
        bank.add(
            "signs-regulatory",
            f"Ahead you see a {shape}, the standard {name}. Traffic is moving and the pavement is dry. What must you do?",
            action,
            rubric,
            spoken,
            _ROW_WRONG + _SPEED_WRONG,
        )
    warnings = [
        ("a sharp curve arrow", "a curve you cannot take at highway speed", "Slow before the curve so you are not braking hard while turning.", "A curve warning means reduce speed before the bend."),
        ("a side-road junction symbol", "traffic may enter from the side road", "Cover the brake and watch the side road for vehicles that may not yield.", "A side-road warning means someone may enter."),
        ("a merging-lanes symbol", "traffic merging from the side", "Adjust speed to open a gap for the merge.", "A merge warning means make room, do not hold your line stubbornly."),
        ("a two-way traffic symbol", "oncoming traffic on a road that was divided", "Stay right and expect vehicles approaching in the opposite lane.", "Two-way traffic means the opposing lane is live."),
        ("a deer or animal symbol", "animals may cross", "Slow down and scan the shoulders, especially at dawn and dusk.", "An animal warning means reduce speed and watch the edges."),
        ("a slippery-when-wet symbol", "reduced grip in rain", "Slow down before the pavement gets slick and avoid sudden brakes or turns.", "Slippery when wet means ease off early."),
        ("a school symbol", "a school zone or school crossing", "Slow to the posted school speed when the zone is in effect and watch for children.", "A school warning means children may enter the road."),
        ("a pedestrian symbol", "people may be crossing", "Slow and yield to anyone in or entering the crosswalk.", "A pedestrian warning means be ready to stop."),
        ("a bicycle symbol", "bikes may be in or near the lane", "Look for riders and give them space when you pass.", "A bicycle warning means share the lane space."),
        ("a low-clearance or height number", "the bridge or overpass may be too low", "Know your vehicle height and take another route if you will not fit.", "A low-clearance warning is a do-not-guess height limit."),
        ("a traffic-signal-ahead symbol", "a signal you cannot see yet", "Start slowing so you can stop if the light is red when you arrive.", "Signal ahead means prepare to stop."),
        ("a stop-ahead symbol", "a stop sign beyond the crest or curve", "Begin slowing now so you can stop fully at the sign.", "Stop ahead means do not wait until you see the sign."),
        ("a lane-ends symbol", "your lane is about to disappear", "Merge early when you have a gap, and signal the move.", "Lane ends means merge before the lane closes."),
        ("a hill or grade symbol", "a steep grade", "Control speed before the hill. Do not coast in neutral.", "A grade warning means control speed with the gear and brakes."),
        ("a railroad symbol", "a crossing ahead", "Slow, look both ways, and be ready to stop for a train.", "A railroad warning means look and listen early."),
        ("a workers or flagger symbol", "a work zone or flagger", "Slow to the posted work-zone speed and obey the flagger over the signals.", "A flagger controls the lane. Follow the paddle, not your hurry."),
    ]
    for symbol, hazard, action, rubric in warnings:
        bank.add(
            "signs-warning",
            f"A yellow diamond shows {symbol}. It is warning you about {hazard}. How should you respond before you reach it?",
            action,
            rubric,
            action.split(".")[0] + ".",
            _SPEED_WRONG + _WX_WRONG,
        )
    guides = [
        ("a green guide sign", "Guide signs help you navigate. They do not cancel a stop, yield, or speed rule.", "Green is guidance. White regulatory signs still control what you must do.", "Green guides you. It does not replace a stop or speed rule."),
        ("a blue hospital or service sign", "Blue service signs point to help such as a hospital. They are not a right-of-way instruction.", "Blue means services, not a traffic command.", "Blue points to services. It is not a yield or stop."),
        ("a brown recreation sign", "Brown signs mark parks or cultural sites. They do not change the speed limit.", "Brown is information about a place, not a new rule of the road.", "Brown marks a place. Keep the posted speed."),
    ]
    for sign, action, rubric, spoken in guides:
        bank.add(
            "signs-guide",
            f"You see {sign} beside a white speed-limit sign. A passenger says the colored sign matters more. What is the difference?",
            action,
            rubric,
            spoken,
            ["Follow the colored sign and ignore the speed plaque.", "Colored signs always set the legal speed.", "Guide signs replace lane-use arrows."],
        )


def _signals(bank: Bank) -> None:
    scenes = [
        ("A circular green light is showing for you, and a pedestrian is still in your crosswalk.", "Wait for the pedestrian to clear, even though your light is green.", "Green does not override a person in the crosswalk.", "Green light, person still crossing: you wait."),
        ("Your signal is a green left arrow and the oncoming lanes have a red light.", "You may turn left while the arrow is green, still watching for anyone who has not cleared.", "A protected green arrow gives you the turn while oncoming traffic is held.", "The green arrow protects your left turn."),
        ("Your signal is a solid green circle and you want to turn left. Oncoming cars are coming straight.", "Yield to oncoming traffic and pedestrians, then turn when the gap is safe. The green is not protected.", "An unprotected left on a green circle must yield to oncoming traffic.", "Solid green for a left turn: yield to oncoming cars."),
        ("The light turns yellow as you approach, and you can still stop safely before the line.", "Stop. Yellow means the red is next, if you can stop safely.", "If you can stop safely on yellow, stop.", "Yellow and you can stop: stop."),
        ("The light turns yellow when you are already too close to stop without entering the intersection.", "Clear the intersection. Do not stop in the middle.", "If stopping on yellow would put you in the intersection, go through.", "Too close on yellow: clear the intersection."),
        ("You face a steady circular red light. You want to turn right. There is no sign banning the turn, and the crosswalk is empty.", "Stop completely, yield to pedestrians and cross traffic, then turn right if it is clear.", "Right on red is allowed in California only after a full stop, unless a sign prohibits it.", "Right on red: full stop, then turn only if it is clear."),
        ("A sign beside the red light reads NO TURN ON RED. You want to turn right.", "Wait until the signal gives you a green for that movement.", "No Turn on Red removes the usual right-on-red permission.", "The sign bans the turn until the light changes."),
        ("You face a red arrow pointing right.", "Stop and wait. A red arrow does not allow that turn the way a circular red sometimes does.", "A red arrow means do not make that movement.", "Red arrow: do not turn that way."),
        ("You are on a one-way street turning left onto another one-way street. The light is a circular red, no sign bans the turn, and the way is clear.", "Stop completely, yield, then you may turn left from a one-way onto a one-way.", "California allows a left on red only from a one-way street onto a one-way street, after a stop.", "One-way onto one-way: stop, then the left on red may be legal."),
        ("You are on a two-way street and want to turn left on a circular red light.", "You may not turn left on red from a two-way street. Wait for green.", "Left on red is not allowed from a two-way street.", "Two-way street: no left turn on red."),
        ("The light facing you is flashing red.", "Treat it as a stop sign: full stop, then go when it is your turn and the way is clear.", "Flashing red has the same duty as a stop sign.", "Flashing red means stop, then go when clear."),
        ("The light facing you is flashing yellow.", "Slow and proceed with caution. Be ready to yield.", "Flashing yellow is a warning to slow, not a stop, unless something else requires it.", "Flashing yellow: slow down and watch."),
        ("A lane signal over your lane shows a red X.", "Do not travel in that lane. Move to a lane with a green arrow.", "A red X closes the lane.", "Red X: leave that lane."),
        ("A lane signal over your lane shows a green arrow pointing down.", "You may drive in that lane.", "A green downward arrow means the lane is open for you.", "Green arrow over the lane: that lane is open."),
        ("You are in a marked crosswalk area and the walk signal is a flashing upraised hand. You have not entered yet.", "Do not start crossing. Wait for the next walk indication.", "A flashing don't-walk means do not begin to cross.", "Flashing hand: do not step off the curb."),
        ("You already started crossing on a walk signal and the hand starts flashing.", "Finish crossing. Do not turn around in the roadway.", "If you are already in the crosswalk when the hand flashes, continue across.", "Already crossing when the hand flashes: finish crossing."),
        ("Double solid yellow lines are on your left.", "Do not cross them to pass.", "Double solid yellow means no passing from either side.", "Double solid yellow: do not pass across them."),
        ("A broken yellow line is on your left and the oncoming lane is empty for a long gap.", "You may pass if it is safe and no sign bans it.", "A broken yellow centerline allows a pass only when the gap is safe.", "Broken yellow and a clear gap: you may pass if it is safe."),
        ("You want to cross a solid white line to reach an exit at the last moment.", "Do not cross the solid line. Take the next exit.", "A solid white line means stay in the lane.", "Solid white line: do not cross it for a late exit."),
        ("A shared center left-turn lane is marked on a two-way street.", "Use it only to slow and turn left, not as a driving lane or to pass.", "The center two-way left-turn lane is for turning, not for travel or passing.", "That center lane is for left turns only."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("signals-markings", prompt + " What should you do?", action, rubric, spoken, _ROW_WRONG + _SPEED_WRONG)


def _four_way(bank: Bank) -> None:
    arrivals = {
        "you_first": "You stopped fully before the other driver did.",
        "they_first": "The other driver stopped fully before you did.",
        "same": "You and the other driver stopped at the same moment.",
    }
    sides = {
        "right": "The other car is on your right.",
        "left": "The other car is on your left.",
        "opposite": "The other car faces you from the opposite leg.",
    }
    moves = {
        "straight": "going straight",
        "left": "turning left",
        "right": "turning right",
    }
    opposite = {
        ("left", "straight"): "Yield. Your left turn crosses their straight path.",
        ("straight", "left"): "You may go. They must yield for the left turn across you.",
        ("straight", "straight"): "You may both go straight because your paths do not cross.",
        ("left", "left"): "You may both turn left if you pass in front of each other without crossing paths.",
        ("right", "right"): "You may both turn right because those paths do not cross.",
        ("right", "straight"): "You may turn right while they go straight; your right turn does not cross their path.",
        ("straight", "right"): "You may go straight while they turn right; the paths do not cross.",
        ("right", "left"): "You may turn right. Their left turn must yield if it would cross you.",
        ("left", "right"): "Yield. Your left turn must wait if it would cross their right-turn path.",
    }
    peds = {
        False: "The crosswalks are empty.",
        True: "A pedestrian is in the crosswalk you would use.",
    }
    for arrival, arrival_text in arrivals.items():
        for side, side_text in sides.items():
            for your_move, your_text in moves.items():
                for their_move, their_text in moves.items():
                    for ped, ped_text in peds.items():
                        if ped:
                            lead = "Wait until the pedestrian has cleared your crosswalk."
                        else:
                            lead = ""
                        if arrival == "you_first":
                            rule = "You stopped first, so you go next once your path is clear."
                        elif arrival == "they_first":
                            rule = "They stopped first, so you yield until they take their turn."
                        elif side == "right":
                            rule = "You stopped together, so yield to the driver on your right."
                        elif side == "left":
                            rule = "You stopped together and they are on your left, so you go before they do."
                        else:
                            rule = opposite[(your_move, their_move)]
                        action = (lead + " " + rule).strip()
                        spoken = rule if not ped else "Person in the crosswalk first, then " + rule[0].lower() + rule[1:]
                        if len(spoken) > 220:
                            spoken = "Clear the crosswalk first, then follow the stop-sign order."
                        prompt = (
                            f"{side_text} You are {your_text} and they are {their_text}. "
                            f"{arrival_text} {ped_text} This is an all-way stop. "
                            "What should you do?"
                        )
                        tempting = (
                            "Yield to the right even though you arrived first."
                            if arrival == "you_first"
                            else "Go first even though they arrived and stopped before you."
                            if arrival == "they_first"
                            else "Ignore the driver on the right and turn immediately."
                        )
                        bank.add(
                            "right-of-way",
                            prompt,
                            action,
                            "At an all-way stop, clear pedestrians, then the first vehicle to stop goes first. A tie yields to the right, and a left turn yields to oncoming straight traffic.",
                            spoken,
                            [tempting, *_ROW_WRONG],
                        )


def _other_intersections(bank: Bank) -> None:
    scenes = [
        ("Two-way stop. You have a stop sign. Cross traffic does not. A car is approaching from your left, close enough that you cannot cross.", "Stay stopped and let the cross-street car pass. Your stop sign does not make them yield.", "Cross traffic on the through street has the right of way when only you have a stop sign.", "You have the stop sign. Wait for a real gap in cross traffic."),
        ("Two-way stop. You have the only stop sign. Both directions on the cross street are empty, and the crosswalk is empty.", "After the full stop, you may go because the through street and crosswalk are clear.", "Once you have stopped and the through street is clear, you may enter.", "Clear both ways: after the stop, you may go."),
        ("Two-way stop. You have stopped. A pedestrian steps into the far crosswalk as the traffic gap opens.", "Let the pedestrian finish crossing before you go, even though cars have passed.", "A gap in cars is not a gap if a person is in the crosswalk.", "The person in the crosswalk still comes first."),
        ("You have a yield sign at a merge. A car is beside you in the lane you need.", "Slow or stop and let that car go. Do not force the merge.", "A yield at a merge means the lane you are entering has priority.", "Yield the merge. Do not push in beside them."),
        ("You have a yield sign and the lane you need has a long empty gap.", "You may enter without stopping if you can do it safely, because yield does not always require a stop.", "Yield requires a stop only when the gap is not safe.", "Open gap at a yield: you may go without a needless stop."),
        ("Uncontrolled intersection, no signs or signals. A car on your right arrives at the same time.", "Yield to the vehicle on your right.", "When two vehicles arrive together and nothing is posted, yield to the right.", "Nothing posted, same time: yield to the right."),
        ("Uncontrolled intersection. You arrive while another car is already in the intersection.", "Let the car already in the intersection clear first.", "A vehicle already in the intersection has priority over one just arriving.", "They are already in it. You wait."),
        ("T intersection. You are on the stem, facing the through road. A car is coming from your left on the through road.", "Yield to the through road. Wait for that car.", "The driver on the ending road yields to the road that continues.", "Stem of the T: yield to the through road."),
        ("T intersection. You are on the through road, going straight. A car is waiting on the stem.", "You may continue. The car on the stem must yield to you.", "Through traffic at a T does not yield to the stem.", "You are on the through road. They wait."),
        ("You are leaving a driveway and the sidewalk has a person walking across the apron.", "Stop and let the person on the sidewalk pass before you enter the street.", "Driveway traffic yields to sidewalk users and then to the street.", "Sidewalk first, then the street."),
        ("You are leaving a driveway. The sidewalk is empty. A car is approaching on the street from your left.", "Yield to the street traffic. Do not pull out in front of that car.", "A driveway exit yields to traffic already on the road.", "From a driveway, the street has the right of way."),
        ("Roundabout ahead. Cars are circulating in the circle as you reach the entry.", "Yield to traffic already in the circle. Enter only when there is a gap, to the right.", "Roundabout entry yields to vehicles already circulating.", "Wait for a gap. Traffic in the circle goes first."),
        ("Roundabout. The circle is empty as you arrive.", "Enter without stopping in the circle, travel to the right, and signal your exit.", "An empty roundabout does not require a stop inside the circle.", "Empty circle: enter, keep right, signal the exit."),
        ("You are inside a roundabout and the car behind you wants to exit.", "Stay in your path and exit at yours. Do not stop inside the circle.", "Do not stop in a roundabout to be polite.", "Do not stop inside the circle."),
        ("Green light, you are turning right, and a bike is in the bike lane beside your right front corner.", "Yield to the bike. Do not turn across the bike lane until the rider has passed.", "A right turn must yield to a bike in the bike lane.", "The bike beside you goes before your right turn."),
        ("You are going straight in the through lane. A car to your right wants to turn right from a right-turn-only lane and has a red light.", "You may continue on your green. They must wait for their own gap or green.", "Their red right-turn lane does not take your green through movement.", "Your green through lane proceeds. Their red turn waits."),
        ("Four-way stop. An emergency vehicle with lights and siren approaches from your left while you are next to go.", "Pull to the right and stop. The emergency vehicle goes before the stop-sign order.", "Lights and siren override ordinary right-of-way.", "Yield the stop-sign turn to the emergency vehicle."),
        ("A funeral procession with headlights on is crossing. You are at the cross street.", "Yield until the procession passes. Do not cut through it.", "You do not break a funeral procession to take a turn.", "Let the procession pass."),
        ("Your light is green but the intersection ahead is blocked by stopped cars.", "Do not enter. Wait behind the line until you can clear the far side.", "Do not enter an intersection you cannot clear, even on green.", "Green light, gridlocked far side: stay behind the line."),
        ("You want to turn left at a green light. A motorcycle is oncoming in the through lane, small but close.", "Yield. The motorcycle has the same right of way as a car going straight.", "A motorcycle oncoming on green has priority over your left turn.", "The motorcycle is oncoming traffic. Your left turn waits."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("intersections", prompt + " What should you do?", action, rubric, spoken, _ROW_WRONG + _PED_WRONG)


def _speed_and_space(bank: Bank) -> None:
    gaps = [
        ("dry pavement in daylight", "at least a three-second following gap", "Three seconds is the dry-day minimum, and the physical gap grows as speed rises.", "Dry road: leave at least three seconds."),
        ("steady rain with spray", "at least a four-second gap and a speed below the posted maximum", "Rain needs more space because stopping distance grows.", "Rain: more than three seconds, and slower than the sign."),
        ("snow and packed ice", "at least a six-second gap and a speed far below the posted limit", "Ice multiplies stopping distance. Six seconds is a floor, not a dare.", "Ice: a long gap and much less speed."),
        ("fog that hides the next bend", "a gap of six seconds or more, low-beam headlights, and a speed you can stop within the distance you can see", "If you cannot see a stopping distance, you are going too fast.", "Fog: low beams, and only as fast as you can see to stop."),
        ("a gravel shoulder you had to enter", "a longer gap, no hard braking, and a gentle return to the pavement", "Gravel grabs a locked wheel. Ease back onto the road.", "Gravel: no hard brake, steer gently."),
        ("night on an unlit two-lane road", "at least a four-second gap and headlights on", "Darkness hides the stop ahead. Add space.", "Night: headlights and a longer gap than a sunny noon."),
        ("a motorcycle directly ahead", "a gap longer than three seconds because the rider can stop faster than you", "A close car behind a motorcycle is how riders get hit.", "Give the motorcycle extra space."),
        ("a large truck ahead that blocks your view of the road", "a gap big enough to see around the trailer, not a bumper-length following distance", "If you cannot see past the truck, you are too close.", "Back off the truck until you can see ahead."),
    ]
    for condition, action, rubric, spoken in gaps:
        bank.add(
            "speed-and-space",
            f"You are following traffic on {condition}. The posted limit is 55 mph and the car ahead is steady. How much space should you keep, and how should that change your speed?",
            action,
            rubric,
            spoken,
            _SPEED_WRONG,
        )
    limits = [
        ("an alley", "15 mph", "California's basic speed for an alley is 15 mph.", "Alleys are 15 mph unless a sign sets something else."),
        ("a blind intersection where you cannot see 100 feet both ways during the last 100 feet", "15 mph", "A blind intersection has a 15 mph basic speed when your view is blocked.", "If you cannot see across, creep through at 15 or less."),
        ("a residential district with no speed sign", "25 mph", "The prima facie residential speed is 25 mph when nothing is posted.", "No sign in a neighborhood: 25 mph."),
        ("a business district with no speed sign", "25 mph", "The prima facie business-district speed is 25 mph when nothing is posted.", "Unposted business district: 25 mph."),
        ("a school zone signed 25 when children are present, and children are on the sidewalk by the crosswalk", "25 mph or slower", "When the school sign is in effect, 25 is the maximum.", "Children are present. The school speed is 25."),
        ("a school zone signed 25 when children are present, on a Sunday with the school closed and no children around", "the ordinary posted or prima facie speed, while still scanning", "If the special school limit applies only when children are present, an empty Sunday does not keep the 25 in force. Stay alert anyway.", "No children and the sign says when children are present: the special 25 is not in force."),
        ("a work zone with a posted 35 and workers beside the lane", "no more than 35 mph, and slower if the workers are close", "The work-zone sign is the maximum while it is posted. Fines are often higher.", "Workers present: obey the 35 and give them room."),
        ("a freeway signed 65 in a downpour", "slower than 65, because 65 is only the maximum in good conditions", "The basic speed law overrides the number on the sign when rain, traffic, or visibility is poor.", "Sixty-five is not your speed in a downpour."),
        ("chain control that says chains or snow socks are required and you have neither", "do not continue. Turn around or wait until you are equipped.", "A chain-control requirement is a closure for unequipped vehicles.", "No chains when chains are required: do not go on."),
        ("a flagger holding a STOP paddle in a work zone while your signal farther ahead is green", "Stop for the flagger. The paddle controls you.", "A flagger's direction overrides the signal.", "The flagger's STOP overrides the green light."),
    ]
    for place, action, rubric, spoken in limits:
        bank.add(
            "speed-limits",
            f"You are entering {place}. What speed or choice does the law expect?",
            action,
            rubric,
            spoken,
            _SPEED_WRONG,
        )
    # Seconds stay the same; the distance the gap covers changes with speed.
    # That difference is the skill: do not count car lengths the same at 25 and 70.
    for speed, longer in ((25, "a shorter physical distance"), (45, "a longer physical distance"), (70, "a much longer physical distance")):
        bank.add(
            "following-distance",
            f"Dry daylight freeway, you are traveling {speed} mph behind a steady car. Someone says three car lengths is always enough. What gap do you actually need?",
            f"At least three seconds, which at {speed} mph is {longer} than the same three seconds at a lower speed. Three car lengths is not the rule.",
            "The three-second rule is time, so the distance grows with speed. Counting cars underestimates the gap at higher speed.",
            f"Three seconds at {speed}. Do not substitute three car lengths.",
            _SPEED_WRONG,
        )


def _people_and_buses(bank: Bank) -> None:
    buses = [
        ("behind a school bus on an undivided two-lane road. The red lights flash and the stop arm is out", "Stop and stay stopped until the red lights stop and the arm folds.", "On an undivided road you stop for flashing red school-bus lights from behind.", "Red lights and the stop arm: stop and wait."),
        ("approaching that bus from the opposite direction on the same undivided two-lane road, red lights flashing", "Stop. On an undivided road both directions stop for the flashing red lights.", "Opposite direction on a two-lane undivided road still stops.", "Facing the bus on a two-lane road: you stop too."),
        ("on the opposite side of a divided highway with a physical median. The bus has red lights on the far side", "You may proceed with caution. You do not stop for a bus on the far side of a divided highway.", "A physical median means opposite traffic does not stop for that bus.", "Median between you and the bus: you do not stop."),
        ("on a highway with two lanes in your direction and two the other way, no median, and the bus is on the opposite side with red lights", "You do not have to stop when the bus is on the opposite side of a multilane highway.", "California does not require the opposite direction to stop on a multilane highway.", "Opposite side of a multilane road: you are not required to stop."),
        ("behind the bus in the same direction on that multilane highway. Red lights are flashing", "Stop. Same-direction traffic stops even on a multilane road.", "The multilane exception is for the opposite direction, not for traffic behind the bus.", "You are behind the bus: stop."),
        ("seeing amber lights flashing on a school bus that is still rolling to the curb. The stop arm is not out", "Slow and prepare to stop. Do not pass. Amber means the red lights are next.", "Amber warns you to prepare. Do not swing around the bus.", "Amber lights: slow down and do not pass."),
        ("passing a bus pulled to the curb with no flashing lights and no stop arm, children already on the sidewalk", "You may pass carefully. The stop rule is the flashing red lights and stop arm, not the mere presence of a bus.", "No red lights and no stop arm means the special stop duty is not active. Still watch children.", "No lights, no arm: you may pass, but watch the kids."),
        ("on a road where a school activity bus is loading with red lights and a stop arm", "Stop. Activity buses loading students use the same stop-arm rule.", "The stop-arm rule is about the lights and the students, not only the yellow school-bus paint on a route bus.", "Stop arm out: treat it as a school-bus stop."),
    ]
    for setup, action, rubric, spoken in buses:
        bank.add(
            "school-bus",
            f"You are {setup}. What do you do?",
            action,
            rubric,
            spoken,
            _BUS_WRONG,
        )
    people = [
        ("A child runs after a ball from between parked cars on your right. You are at 25 mph.", "Brake and stop. Expect the child, not just the ball.", "A ball into the street means a child is next. Stop.", "Ball in the street: stop for the child behind it."),
        ("A person with a white cane is at the corner, waiting to cross.", "Stop and yield. Do not honk them across.", "A white cane means yield and give the person time.", "White cane at the corner: yield and wait."),
        ("A driver ahead has stopped at a marked crosswalk and you cannot see why.", "Do not pass. Someone may be crossing in front of that car.", "Never pass a vehicle stopped at a crosswalk.", "Stopped at a crosswalk: do not go around them."),
        ("Your light is green and a person steps off the curb into the crosswalk late.", "Yield. The person is in the crosswalk.", "Once a pedestrian is in the crosswalk, you yield even on a green light.", "They stepped off. You wait."),
        ("You are turning right and a person is walking on the sidewalk toward the curb but has not entered.", "Cover the brake and yield if they enter. Do not cut across their path.", "Right turns yield to pedestrians approaching the crosswalk you will cross.", "Do not turn across someone about to enter."),
        ("A bike is riding legally in the lane because the lane is too narrow to share.", "Slow and wait to pass. Do not squeeze past in the same lane.", "If there is no safe room to pass, the bike may take the lane and you wait.", "Narrow lane: wait. Do not squeeze the rider."),
        ("You can pass a bike with a full adjacent lane empty.", "Change lanes to pass, or at least leave three feet.", "California requires at least three feet when you pass a bicycle.", "Pass with three feet, more if you can change lanes."),
        ("A bike is approaching an intersection from the opposite direction and you are turning left.", "Yield to the bike the same way you yield to an oncoming car.", "A left turn yields to an oncoming bicycle.", "Oncoming bike: your left turn waits."),
        ("A horse and rider are on the right shoulder and you want to pass.", "Slow down and give them a wide, quiet pass. Do not honk.", "Animals and riders need a slow, wide pass.", "Slow and wide. Do not honk at the horse."),
        ("An emergency vehicle is approaching from behind with lights and siren. You are in the left lane.", "Signal, move right, and stop clear of the intersection until it passes.", "Pull to the right and stop for lights and siren. Do not stop in the intersection.", "Lights and siren behind you: move right and stop."),
        ("A police car is stopped on the shoulder ahead with lights flashing. You are on a multilane road and the right lane is open.", "Move over one lane away from the stopped car. If you cannot, slow down.", "Move-over law: give a lane to a stopped emergency vehicle when you can.", "Move over a lane for the stopped patrol car."),
        ("A stopped tow truck has amber lights on the shoulder and you cannot change lanes.", "Slow down as you pass and give as much space as the lane allows.", "If you cannot move over, you must slow for the stopped truck.", "Cannot move over: slow down as you pass."),
    ]
    for prompt, action, rubric, spoken in people:
        bank.add("sharing-the-road", prompt + " What should you do?", action, rubric, spoken, _PED_WRONG + _BUS_WRONG)


def _freeway_and_lanes(bank: Bank) -> None:
    scenes = [
        ("You are on a freeway on-ramp. Traffic in the right lane is beside you at ramp speed.", "Adjust your speed to match a gap. Yield to the freeway. Do not stop at the end of the ramp if traffic is moving.", "Merging traffic yields. Match speed and pick a gap.", "Match speed and yield. Do not stop in moving freeway traffic."),
        ("The on-ramp meter is red.", "Stop for the meter and go when it turns green, one car per green as posted.", "A ramp meter is a traffic signal for the merge.", "Red meter: wait for the green."),
        ("You need an exit in a quarter mile and you are in the left lane beside a solid white line at the exit gore.", "Stay on the freeway and take the next exit. Do not cross the gore or the solid line.", "Late exits do not justify crossing the gore.", "Miss the exit rather than cross the solid line."),
        ("You are entering an HOV lane across double solid white lines because you have two people.", "Do not cross the double white lines. Enter only where the line is broken.", "Occupancy does not let you cross a double white line.", "Two people still cannot cross the double white line."),
        ("You are alone in a car and the HOV lane is moving faster.", "Stay out of the HOV lane. One occupant does not qualify.", "HOV lanes have an occupancy rule. Do not use them to beat traffic.", "Alone in the car: the diamond lane is not for you."),
        ("A truck is on your right on a multilane freeway and you are beside its trailer doors.", "Speed up or drop back so you are not in the truck's no-zone.", "Beside a trailer you are in a blind area. Do not linger there.", "Do not ride beside the trailer."),
        ("You want to pass a truck on the right on a downgrade while it is in the left lane.", "Pass on the left when you can. Do not cut back in until you see the truck in your mirror.", "Finish the pass and return only with space. The right side of a truck is a blind zone.", "Pass left, then wait until you see the truck before you merge back."),
        ("Your exit is a left exit and you are in the right lane a mile out.", "Signal and move left early, one lane at a time, when each gap is safe.", "Left exits need an early lane change, not a last-second dive.", "Move toward the left exit early."),
        ("Traffic is stopped in your lane on the freeway and the next lane is moving.", "Stay stopped or creep with your lane. Do not whip into the moving lane without a gap.", "A closed lane does not create a right to force a merge.", "Wait for a real gap. Do not dive over."),
        ("You are in the carpool lane and your exit requires you to leave at a designated opening a mile ahead.", "Leave at the opening, not across the buffer.", "Exit the HOV lane only where the marking allows.", "Use the designated opening to leave the lane."),
        ("A car is drifting into your lane from the left without a signal.", "Ease off, horn if needed, and leave a space. Do not race them for the spot.", "Defend the space. Do not trade paint to hold a lane.", "Give way and hold a space. Do not fight for the lane."),
        ("You missed the lane for your freeway split and the gore is at your front wheel.", "Stay in the lane you are in and correct at the next exit. Do not bounce through the gore.", "The gore is not a lane.", "Do not drive through the gore point."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("freeway", prompt + " What should you do?", action, rubric, spoken, _FREEWAY_WRONG)
    # Lane position changes the legal move. Each marking is a different duty.
    markings = [
        ("a solid yellow line on your left and a broken yellow on the other side", "You may not pass. The solid line is on your side.", "Passing is banned on the side with the solid yellow line."),
        ("a broken yellow line on your side and a solid yellow on the oncoming side", "You may pass if the oncoming gap is safe. They may not pass.", "The broken line on your side allows the pass when it is safe."),
        ("white arrows in your lane pointing only left", "Turn left from that lane. Do not go straight from a left-turn-only lane.", "A turn-only arrow assigns the movement."),
        ("a bike lane to your right and you need to turn right at the next corner", "Merge into the bike lane only near the corner after yielding to riders, or turn from the designated pocket. Do not sit in the bike lane early.", "Enter a bike lane for a right turn only at the intersection, after yielding."),
        ("an edge line and a paved shoulder, and you want to pass on the right using the shoulder", "Do not pass on the shoulder.", "The shoulder is not a passing lane."),
        ("reversible-lane signals showing a yellow X over your lane", "The lane is about to close or reverse. Move out of it.", "A yellow X means leave the lane."),
    ]
    for marking, action, rubric in markings:
        bank.add(
            "lane-markings",
            f"Your lane has {marking}. What does that marking require?",
            action,
            rubric,
            action.split(".")[0] + ".",
            _FREEWAY_WRONG + _ROW_WRONG,
        )


def _weather_night_emergency(bank: Bank) -> None:
    scenes = [
        ("Your front tire blows out at freeway speed.", "Grip the wheel, ease off the gas, do not brake hard, and steer straight until the car is stable. Then brake gently and pull off.", "A blowout needs a steady wheel and no panic brake.", "Blowout: hold the wheel, ease off, no hard brake."),
        ("The rear of the car slides on a wet curve and you do not have ABS.", "Ease off the gas, look where you want to go, and steer that way. Do not slam the brakes.", "In a skid, look and steer toward the escape path. Hard braking makes it worse.", "Skid: eyes on the path, ease off the gas."),
        ("You have ABS and must stop hard for a car ahead.", "Brake firmly and steer. Do not pump ABS. The pedal throb is normal.", "ABS wants steady firm pressure, not pumping.", "ABS: press firm and steer. Do not pump."),
        ("You hit a patch of standing water and the wheel goes light.", "Ease off the accelerator and steer straight until the tires touch down. Do not brake hard.", "Hydroplaning: off the gas, straight wheel, no hard brake.", "Wheel goes light: ease off and hold straight."),
        ("Fog is thick and high beams are reflecting back at you.", "Switch to low beams and slow to a speed you can stop within.", "High beams in fog bounce back and hide the road.", "Fog: low beams, slower speed."),
        ("You cannot see the road in fog even at a crawl.", "Pull entirely off the roadway, away from traffic, and use hazard lights. Do not stop in the lane.", "If you must stop in fog, get off the traveled lane.", "Cannot see: leave the lane, hazards on."),
        ("Water covers the road and you do not know the depth.", "Turn around. Do not drive through. A foot of moving water can float a car.", "Unknown flood water is a turn-around, not a crossing.", "Turn around. Do not drive into the water."),
        ("The accelerator sticks open.", "Shift to neutral, brake to a stop off the road, then shut the engine off.", "Neutral and brakes first. Do not fight a stuck throttle by turning the key while you still need to steer.", "Stuck throttle: neutral, then brake off the road."),
        ("The brakes go to the floor.", "Pump the pedal, downshift, and use the parking brake gradually while you steer to the shoulder.", "Brake failure: pump, downshift, controlled parking brake, get off the road.", "No brakes: pump, downshift, ease the parking brake."),
        ("The hood flies up and blocks your view.", "Look through the gap at the bottom of the windshield, signal, and pull off. Do not stare at the hood.", "Use the low gap under the hood to see the lane and stop off the road.", "Hood up: look under it and pull off."),
        ("Smoke comes from under the hood while you are moving.", "Pull off, shut the engine off, get everyone out and away, and call for help. Do not open the hood if flames are showing.", "An engine fire means get people away. Do not keep driving.", "Smoke from the hood: stop, get out, stay back."),
        ("You feel faint at the wheel.", "Signal, slow, and stop off the road before you lose control. Hazards on.", "A medical spell means stop now, not at the next exit if you are fading.", "Feeling faint: get off the road before you pass out."),
        ("A deer is standing in your lane at night and the shoulders are clear.", "Brake straight if you can stop. Do not swerve into oncoming traffic.", "A swerve into the other lane is worse than a controlled stop.", "Deer ahead: brake in your lane. Do not swerve into traffic."),
        ("Oncoming headlights are high and blinding you.", "Look at the right edge line, slow down, and do not retaliate with your own high beams.", "Aim your eyes at the right edge until the glare passes.", "Glare: watch the right edge, stay in your lane."),
        ("It is 40 minutes after sunset and your headlights are still off.", "Turn the headlights on. California requires them from 30 minutes after sunset until 30 minutes before sunrise.", "Headlights are required in that darkness window, not only when you personally feel it is dark.", "Thirty minutes after sunset: headlights on."),
        ("Visibility ahead is under 1,000 feet in dust, but it is noon.", "Turn on low-beam headlights.", "Headlights are required when you cannot see 1,000 feet, day or night.", "Cannot see 1,000 feet: lights on."),
        ("You are following a car at night within about 300 feet.", "Use low beams so you do not blind the driver ahead.", "Low beams when you are close behind another car at night.", "Within 300 feet behind: low beams."),
        ("An oncoming car is within about 500 feet at night.", "Drop to low beams.", "High beams must come down for oncoming traffic within 500 feet.", "Oncoming within 500 feet: low beams."),
        ("A child unbuckles and stands up in the back seat on the freeway.", "Signal and pull off safely before you reach back. Do not fix the belt while moving.", "Stop first. Reaching back at speed is how cars leave the lane.", "Pull off, then buckle the child."),
        ("The car ahead drops a mattress into your lane.", "Brake or change lanes smoothly if the next lane is empty. Do not swerve into traffic.", "Avoid the debris only into an open space.", "Open lane: move over. Occupied lane: brake straight."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("emergencies", prompt + " What should you do?", action, rubric, spoken, _WX_WRONG + _EMERG_WRONG)


def _parking_and_turns(bank: Bank) -> None:
    hills = [
        ("uphill beside a curb", "Turn the front wheels away from the curb so the car rolls into the curb if the brake fails.", "Uphill with a curb: wheels away from the curb.", "Uphill with a curb: wheels turned out."),
        ("downhill beside a curb", "Turn the front wheels toward the curb.", "Downhill with a curb: wheels into the curb.", "Downhill: wheels toward the curb."),
        ("uphill or downhill with no curb", "Turn the front wheels toward the side of the road so the car rolls off the roadway, not into traffic.", "No curb: wheels toward the shoulder.", "No curb: aim the wheels at the shoulder."),
    ]
    for place, action, rubric, spoken in hills:
        bank.add(
            "parking",
            f"You are parking {place}. Which way do the front wheels go, and why?",
            action,
            rubric,
            spoken,
            _PARK_WRONG,
        )
    curbs = [
        ("red", "No stopping, standing, or parking, except a bus in a signed bus zone.", "Red means no stopping."),
        ("yellow", "Stop only long enough to load or unload passengers or freight, as the sign allows.", "Yellow is a timed loading zone, not all-day parking."),
        ("white", "Stop only to pick up or drop off passengers.", "White is passenger loading, not a parking space."),
        ("green", "Park only for the time posted on the sign.", "Green is a time-limited space."),
        ("blue", "Park only with a valid disabled placard or plates, and only while the person the placard belongs to is using the space.", "Blue is reserved. The placard belongs to the person, not the car."),
    ]
    for color, action, rubric in curbs:
        bank.add(
            "parking",
            f"The curb is painted {color}. What may you do there?",
            action,
            rubric,
            action.split(".")[0] + ".",
            _PARK_WRONG,
        )
    more = [
        ("You want to park beside a fire hydrant.", "Stay at least 15 feet away from the hydrant.", "California forbids parking within 15 feet of a fire hydrant.", "Fifteen feet from the hydrant."),
        ("A disabled placard is on the mirror but the person it was issued to is not with you.", "Do not use the blue space. The placard is not for the car or for errands without that person.", "The placard follows the person, not the vehicle.", "No placard holder in the car: do not use the space."),
        ("You want to make a U-turn on a residential street and a car is approaching within 200 feet.", "Do not make the U-turn. Wait until you can see that no vehicle is that close.", "A residential U-turn is illegal when a vehicle is approaching within 200 feet.", "Car within 200 feet: no U-turn."),
        ("A sign bans U-turns at the intersection where you wanted to turn around.", "Obey the sign. Go around the block.", "A posted no U-turn is absolute at that spot.", "The sign ends the U-turn idea."),
        ("You want to pass on a two-lane road and the intersection is 80 feet ahead.", "Do not pass. Do not pass within 100 feet of an intersection.", "Passing is banned within 100 feet of an intersection.", "Too close to the intersection to pass."),
        ("A railroad crossing is 60 feet ahead and you want to pass a slow car.", "Do not pass. Stay back from the crossing.", "Do not pass within 100 feet of a railroad crossing.", "Crossing ahead: finish the pass somewhere else."),
        ("You will turn right at the next corner from a live lane.", "Signal at least 100 feet before the turn, then turn from the right lane.", "The turn signal goes on at least 100 feet before the turn.", "Signal 100 feet before you turn."),
        ("You are backing out of a driveway onto a street with a sidewalk.", "Look over your shoulder and yield to sidewalk users and street traffic before you back out.", "Backing onto a sidewalk or street yields to the people already there.", "Back out only after the sidewalk and street are clear."),
        ("Your parallel-park space is on a hill and you set the brake but leave the transmission in neutral.", "Put the car in park or in gear, set the brake, and curb the wheels. Neutral is not a parking gear.", "Neutral plus a brake is how cars roll. Use park or a gear, the brake, and the curb.", "Do not leave it in neutral."),
        ("You stop in a crosswalk to drop a passenger because the curb lane is full.", "Do not stop in the crosswalk. Go around the block and find a legal curb.", "A crosswalk is not a loading zone.", "Never stop in the crosswalk."),
    ]
    for prompt, action, rubric, spoken in more:
        bank.add("parking-and-turns", prompt + " What is the legal move?", action, rubric, spoken, _PARK_WRONG + _ROW_WRONG)


def _license_and_impairment(bank: Bank) -> None:
    scenes = [
        ("A 16-year-old has an instruction permit. A 20-year-old licensed friend wants to supervise from the front seat. The friend is not a parent, spouse, or instructor.", "That friend is too young to supervise. The supervisor must be at least 25 with a valid license, unless they are a licensed parent, guardian, spouse, or instructor who is at least 18.", "Permit supervision has an age rule. A licensed 20-year-old friend does not qualify.", "A friend who is 20 cannot be the supervising driver."),
        ("A teen with a permit is practicing. The licensed parent, age 42, sits in the back seat.", "The supervisor must sit in the front passenger seat, where they can take control.", "Supervision from the back seat does not count.", "Front seat only for the supervising driver."),
        ("A provisional driver in the first 12 months wants to drive at midnight with no licensed adult.", "Do not drive. The first year has a night limit, generally 11 p.m. to 5 a.m., unless a legal exception applies.", "Provisional night limits block that midnight trip without a qualified adult.", "Midnight alone in the first year: do not drive."),
        ("A provisional driver in the first 12 months wants to carry two 17-year-old friends and no adult.", "Do not. Passengers under 20 are not allowed in that first year unless a qualified licensed driver is along.", "The passenger limit is part of the provisional license, not a suggestion.", "No friends under 20 without a qualified adult."),
        ("An 18-year-old provisional driver needs to drive to a documented job at 11:30 p.m. and has the required note.", "A work exception can allow that trip if the documentation is in the car. Friends still do not come along.", "Night exceptions exist for work, school, or medical need with proof. They do not add passengers.", "Work note in the car: the trip can be legal. The extra passengers are not."),
        ("A driver under 18 wants to use a phone with a hands-free mount.", "Do not. Drivers under 18 may not use a cell phone at all, including hands-free.", "The under-18 phone ban includes hands-free devices.", "Under 18: no phone, hands-free included."),
        ("A driver over 18 holds the phone to talk while moving.", "Put it down. Adults may use hands-free only, not a handheld phone.", "Handheld phone use while driving is illegal for adults too.", "Handheld call: pull over or use hands-free."),
        ("An adult driver is 21 and blows a 0.06 after two drinks but is clearly impaired.", "Do not drive. You can be arrested for impairment below 0.08, and 0.08 is the per-se limit, not a safe target.", "Impairment is illegal even under 0.08. The only safe choice is not to drive.", "Below 0.08 can still be a DUI. Do not drive."),
        ("A 20-year-old driver has a blood alcohol of 0.01.", "Do not drive. Under 21, a 0.01 level is illegal.", "Zero tolerance for drivers under 21 is 0.01.", "Under 21: 0.01 is already over the line."),
        ("A commercial driver is at 0.04.", "Do not drive a commercial vehicle. The commercial limit is 0.04.", "Commercial drivers are illegal at 0.04.", "Commercial limit is 0.04. Do not drive."),
        ("An open beer can is in the passenger area while you drive, and you have not drunk from it.", "It is still illegal. Do not drive with an open container in the passenger area.", "An open container in the passenger area is an offense even if you are not drinking.", "Open container in the cabin: do not drive that way."),
        ("You are fighting sleep on a dark highway and the next exit is two miles.", "Leave the road at the first safe shoulder or exit and nap. Coffee does not replace sleep.", "Drowsy driving is treated like impairment. Stop.", "Pull off and sleep. Do not push to the next city."),
        ("A passenger offers you a ride-share shift after you took a sleep medication labeled not to drive.", "Do not drive. The label warning is the rule.", "A medication warning against driving means you are not fit.", "The label says not to drive. Decline the shift."),
        ("You must carry proof of insurance and your license is at home.", "Do not drive. You need a valid license or permit and evidence of financial responsibility.", "Driving without a license on you and without insurance proof is not a legal trip.", "No license and no proof of insurance: do not drive."),
        ("Your registration is expired and a friend says enforcement is light tonight.", "Do not drive the car until the registration is valid.", "Expired registration does not become legal because the street looks empty.", "Park it until the registration is current."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("licensing-and-impairment", prompt + " What is the right choice?", action, rubric, spoken, _EMERG_WRONG + _SPEED_WRONG)


def _sharing_and_special(bank: Bank) -> None:
    scenes = [
        ("Railroad lights are flashing and the gate is down. The train is not in sight yet.", "Stop and wait. Do not go around the gate.", "Flashing lights and a lowered gate mean stop until they clear.", "Do not drive around the gate."),
        ("A railroad crossing has a stop sign and no train is coming.", "Stop between 15 and 50 feet from the nearest rail, look both ways, then go if it is clear.", "A stop sign at the tracks still requires a full stop at the required distance.", "Stop 15 to 50 feet from the rail, then look."),
        ("Traffic stops on a railroad crossing and you would be the car left on the tracks.", "Wait behind the line. Never stop on the tracks.", "If you cannot clear the far side, you do not enter the crossing.", "Do not be the car sitting on the rails."),
        ("A traffic officer is in the intersection waving you through a red light.", "Follow the officer. An officer's direction overrides the signal.", "A directing officer outranks the light.", "The officer's wave beats the red light."),
        ("You are in a crash with another car. The bumpers are locked and someone says they are fine, but a passenger is dizzy.", "Move to safety if the cars can, call emergency help, and do not leave. Exchange information and report as required.", "A crash with injury means stop, help, and report. Do not leave.", "Injury crash: stop, call, stay, exchange information."),
        ("You hit a parked car and the owner is not there.", "Leave a note with your name and address, and notify law enforcement as the law requires. Do not drive off anonymously.", "A parked-car hit still requires you to identify yourself.", "Leave your information. Do not disappear."),
        ("Another driver gets out and walks toward your door, shouting, after a near miss.", "Lock the doors, avoid eye contact, and drive to a public place or call police. Do not get out and argue.", "Road rage is a leave-and-report problem, not a debate.", "Do not get out. Go to a public place."),
        ("A tailgater is inches from your bumper on the freeway.", "Ease off gradually so they pass. Do not brake-check.", "A brake-check causes the crash you are trying to avoid.", "Let them pass. Do not tap the brakes at them."),
        ("You are towing a small trailer and the trailer starts to sway.", "Ease off the gas and hold the wheel straight. Do not brake hard or make a sharp correction.", "Trailer sway gets worse if you brake hard or steer big.", "Sway: off the gas, wheel straight."),
        ("A motorcycle is lane-splitting slowly between lanes in traffic that is stopped or crawling, which California allows when done safely.", "Hold your lane and do not open a door or move sideways into the rider.", "Give the splitting rider a predictable car. Do not close the gap on purpose.", "Hold still in your lane and let the rider pass."),
        ("You are about to open the driver's door on a street with a bike lane.", "Look back for bikes, then open the door with the far hand so your body turns. Do not fling the door into the lane.", "Dooring a bike is the hazard. Look before the door moves.", "Look back before you open the door."),
        ("Your GPS says to turn down a road with a DO NOT ENTER sign.", "Ignore the GPS and stay out. The sign controls you.", "A navigation app does not cancel a Do Not Enter sign.", "The sign wins over the GPS."),
        ("You see a wrong-way driver coming at you on the freeway.", "Slow, move right, honk, flash your lights, and get away from their lane. Call 911 when you can stop safely.", "A wrong-way driver is an evade-and-report emergency.", "Move right, warn, and get away. Then call."),
        ("Night, no street lights, and a person in dark clothes is walking on the right edge of your lane.", "Slow and move left if the oncoming lane is empty. Do not assume they see you.", "An unlit pedestrian is easy to miss. Slow early.", "Person in dark clothes: slow down now."),
        ("A school crossing guard holds a stop sign in the crosswalk.", "Stop and stay stopped until the guard releases you.", "The guard's stop sign controls the crosswalk.", "The guard's sign means stop."),
        ("You plan to pass a slow farm vehicle on a two-lane road and the yellow line becomes solid beside you.", "Drop back and wait. The solid line ends the pass.", "A solid yellow line on your side cancels the pass.", "Solid line: cancel the pass."),
        ("Ice covers an overpass while the road before it looked wet only.", "Slow before the bridge. Bridges freeze first.", "Shaded bridges ice over before the rest of the pavement.", "Bridge ice: slow before you are on it."),
        ("Strong crosswind hits you as you leave a cut on the freeway in a high-profile van.", "Grip the wheel and steer gently back. Do not overcorrect.", "A wind gust needs a small correction, not a yank.", "Crosswind: small steering, firm hands."),
        ("Your view at a corner is blocked by a parked truck, and you need to turn right.", "Creep forward until you can see, yielding as you nose out. Do not swing wide into the left lane.", "A blind corner is a creep-and-look, from the correct lane.", "Inch out until you can see. Stay in your lane."),
        ("You are first at a green light with a stalled car in the intersection from the cross street.", "Wait until the stalled car is clear. Do not go around it into oncoming lanes.", "A green light does not let you thread around a stalled car into opposing traffic.", "Wait. Do not squeeze past into the oncoming lane."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("special-situations", prompt + " What should you do?", action, rubric, spoken, _EMERG_WRONG + _ROW_WRONG + _FREEWAY_WRONG)


def _signal_conflicts(bank: Bank) -> None:
    """Signal face, your movement, and the conflict. Invalid combos are skipped."""
    faces = [
        "green circle",
        "green left arrow",
        "yellow and you can still stop safely",
        "yellow and you are too close to stop",
        "steady red circle",
        "red arrow for your movement",
        "flashing red",
        "flashing yellow",
    ]
    moves = ["straight", "left", "right"]
    conflicts = [
        "the crosswalk you need is empty and no one is oncoming",
        "a pedestrian is in the crosswalk you would enter",
        "an oncoming car is close and going straight",
        "a bike is in the bike lane on your right",
        "an emergency vehicle with lights and siren is approaching",
        "stopped cars fill the intersection past the far line",
    ]
    for face in faces:
        for move in moves:
            for conflict in conflicts:
                action = _signal_action(face, move, conflict)
                if action is None:
                    continue
                acceptable, rubric, spoken = action
                bank.add(
                    "signals-and-conflicts",
                    f"You want to go {move} on a {face}. Right now {conflict}. What should you do?",
                    acceptable,
                    rubric,
                    spoken,
                    _ROW_WRONG + _PED_WRONG,
                )


def _signal_action(face: str, move: str, conflict: str) -> tuple[str, str, str] | None:
    if "emergency" in conflict:
        return (
            "Pull right and stop for the emergency vehicle before you take the turn or the green.",
            "Lights and siren outrank the signal and your intended movement.",
            "Emergency vehicle first. Then look at the signal again.",
        )
    if "stopped cars fill" in conflict:
        return (
            "Wait behind the line until there is room for you beyond the intersection.",
            "Do not enter an intersection you cannot clear.",
            "Far side is full: stay behind the line.",
        )
    if "pedestrian" in conflict:
        return (
            "Wait until the pedestrian clears the crosswalk, even if the signal favors you.",
            "A person in the crosswalk comes before a green light or a turn.",
            "Let the person finish crossing.",
        )
    if face == "red arrow for your movement":
        return (
            f"Stop and wait. A red arrow does not allow you to go {move}.",
            "A red arrow forbids that movement until it changes.",
            "Red arrow: do not go.",
        )
    if face == "steady red circle" and move == "straight":
        return (
            "Stop and stay stopped until a green light.",
            "A steady red circle means stop. Straight through on red is not allowed.",
            "Red light: wait for green.",
        )
    if face == "steady red circle" and move == "left":
        return (
            "Wait. You may not turn left on a red circle from a two-way street.",
            "Left on red is only from a one-way street onto a one-way street, which this is not.",
            "No left turn on this red.",
        )
    if face == "steady red circle" and move == "right":
        if "bike" in conflict:
            return (
                "After a full stop, yield to the bike in the bike lane. Turn only when that lane and the crosswalk are clear, and only if no sign bans the turn.",
                "Right on red still yields to a bike beside you.",
                "Stop, then wait for the bike before the right turn.",
            )
        return (
            "Stop completely. If no sign bans it, turn right only when pedestrians and cross traffic are clear.",
            "Right on a circular red requires a full stop and a clear path.",
            "Full stop, then the right turn if it is clear.",
        )
    if face == "yellow and you can still stop safely":
        return (
            "Stop before the line. You can still do it safely.",
            "Yellow means stop when a safe stop is still possible.",
            "You can stop: stop.",
        )
    if face == "yellow and you are too close to stop":
        if "bike" in conflict and move == "right":
            return (
                "Do not turn across the bike. Brake as well as you can without swerving into them, and let the rider clear.",
                "A late yellow does not let you cut off a bike in the bike lane.",
                "The bike is in the turn. Do not cut across.",
            )
        return (
            "Clear the intersection. Stopping now would leave you in it.",
            "If you cannot stop safely on yellow, go through rather than stop in the intersection.",
            "Too close: clear the intersection.",
        )
    if face == "flashing red":
        if "oncoming" in conflict and move == "left":
            return (
                "Stop fully, then yield to the oncoming car before you turn left.",
                "Flashing red is a stop sign, and a left turn still yields to oncoming traffic.",
                "Stop, then wait for the oncoming car.",
            )
        if "bike" in conflict and move == "right":
            return (
                "Stop fully and let the bike pass before you turn right.",
                "A flashing red does not move a bike out of your turn.",
                "Stop, and yield to the bike.",
            )
        return (
            "Make a full stop, then go when it is your turn and the way is clear.",
            "Flashing red means stop, then proceed like a stop sign.",
            "Flashing red: full stop, then go when clear.",
        )
    if face == "flashing yellow":
        if "oncoming" in conflict and move == "left":
            return (
                "Slow down and yield to the oncoming car before the left turn.",
                "Flashing yellow is caution, and a left turn still yields.",
                "Ease off and let the oncoming car go.",
            )
        return (
            "Slow down and go through only if the lane is clear. Flashing yellow is not a stop by itself.",
            "Flashing yellow means proceed with caution.",
            "Slow and watch. It is not a stop sign.",
        )
    if face == "green left arrow":
        if move != "left":
            return None
        return (
            "You may turn left on the green arrow. Oncoming traffic is being held. Still watch the intersection.",
            "A green arrow protects the left turn.",
            "The arrow is yours. Turn left while watching.",
        )
    if face == "green circle":
        if move == "left" and "oncoming" in conflict:
            return (
                "Yield to the oncoming car. A green circle does not protect a left turn.",
                "Unprotected left turns yield to oncoming traffic.",
                "Oncoming car first. Then your left turn.",
            )
        if move == "left":
            return (
                "You may turn left when there is a safe gap. The green circle does not by itself clear oncoming traffic.",
                "Left on a green circle is unprotected.",
                "Turn left only through a real gap.",
            )
        if move == "right" and "bike" in conflict:
            return (
                "Yield to the bike in the bike lane, then turn.",
                "A green light does not let you turn across a bike.",
                "Bike first, then the right turn.",
            )
        return (
            f"You may go {move}. The path described is clear and the light is a green circle.",
            "A green circle allows the movement when the crosswalk and the lane are clear.",
            "Green and clear: you may go.",
        )
    return None


def _hazard_by_road(bank: Bank) -> None:
    roads = [
        "a two-lane road with oncoming traffic",
        "a multilane freeway",
        "a bridge with no shoulder",
        "a tunnel",
        "a school zone with children on the sidewalk",
        "a one-way street",
        "a roundabout",
        "a mountain downgrade",
    ]
    hazards = [
        ("a deer in your lane", _deer),
        ("a mattress falling from the truck ahead", _debris),
        ("water of unknown depth across the lane", _flood),
        ("a wrong-way driver in your lane", _wrong_way),
        ("a downed power line on the pavement", _wire),
        ("a flagger you can see holding SLOW while workers stand in the next lane", _flagger),
        ("ice only on the shaded pavement ahead", _ice),
        ("a crash blocking your lane with people standing in the lane", _crash_block),
    ]
    for road in roads:
        for label, fn in hazards:
            action, rubric, spoken = fn(road)
            bank.add(
                "hazards",
                f"You are on {road} and you see {label}. What should you do?",
                action,
                rubric,
                spoken,
                _WX_WRONG + _EMERG_WRONG + _SPEED_WRONG,
            )


def _deer(road: str) -> tuple[str, str, str]:
    if "freeway" in road or "two-lane" in road:
        return (
            "Brake straight in your lane. Do not swerve into oncoming traffic or across freeway lanes.",
            "A swerve into another lane is worse than a controlled stop for an animal.",
            "Brake in your lane. Do not swerve into traffic.",
        )
    if "bridge" in road or "tunnel" in road:
        return (
            "Slow as much as you can while staying in your lane. There is no shoulder to escape onto.",
            "No shoulder means you cannot swerve off. Control speed in the lane you have.",
            "No shoulder here. Stay in the lane and slow down.",
        )
    return (
        "Slow early and give the animal room. Do not honk and charge.",
        "Animals are unpredictable. Reduce speed before you reach them.",
        "Ease off now and give the animal space.",
    )


def _debris(road: str) -> tuple[str, str, str]:
    if "freeway" in road:
        return (
            "Change lanes only if the next lane is empty. Otherwise brake straight. Do not dart across lanes.",
            "Debris avoidance on a freeway uses an open lane, not a blind swerve.",
            "Open lane: move over. If not, brake straight.",
        )
    if "two-lane" in road:
        return (
            "Brake straight. Do not swerve into the oncoming lane to miss it.",
            "Oncoming traffic makes a swerve the bigger crash.",
            "Stay in your lane and brake.",
        )
    return (
        "Slow and go around it only if the path is empty. Otherwise stop short of it.",
        "Miss the debris only when the escape path is actually empty.",
        "Do not swerve until you know the next space is empty.",
    )


def _flood(road: str) -> tuple[str, str, str]:
    if "downgrade" in road:
        return (
            "Stop before the water. Do not ride the brakes down into a flooded grade.",
            "Unknown water on a downgrade can stall you with no way back up.",
            "Stop before the water. Do not descend into it.",
        )
    return (
        "Turn around or wait. Do not drive through water when you cannot see the road underneath.",
        "Depth you cannot judge is a reason to turn around on any road.",
        "Turn around. Do not drive into the water.",
    )


def _wrong_way(road: str) -> tuple[str, str, str]:
    if "one-way" in road:
        return (
            "Move to the right curb, stop, and call for help. On a one-way street their lane is your lane.",
            "A wrong-way driver on a one-way street has no opposing lane to return to. Get out of their path.",
            "Pull right and stop. Then report it.",
        )
    if "freeway" in road:
        return (
            "Slow, move right, flash your lights, and leave their path. Call 911 when you can stop safely.",
            "Freeway wrong-way drivers are an evade-right emergency.",
            "Move right, get away, then call.",
        )
    if "roundabout" in road:
        return (
            "Do not enter against them. Yield the circle, pull to the side after you exit, and report it.",
            "Never meet a wrong-way driver inside the circle if you can stay out.",
            "Stay out of the circle and report the wrong-way driver.",
        )
    return (
        "Slow, move right, and give them your lane. Do not play chicken.",
        "Yield the lane to a wrong-way driver and warn others when you can.",
        "Give them the lane and get right.",
    )


def _wire(road: str) -> tuple[str, str, str]:
    if "tunnel" in road or "bridge" in road:
        return (
            "Stop well back if you can, stay in the car if the wire is on the car, and tell everyone else to stay back. Call for help.",
            "A downed line on a bridge or in a tunnel still means stay away from the wire.",
            "Stay back from the wire and call for help.",
        )
    return (
        "Stop far back, keep others away, and call emergency services. Do not drive over the line or leave the car if it is touching the wire.",
        "A downed power line is an electrocution hazard. Distance and a call, not a drive-over.",
        "Stop well back. Do not drive over the line.",
    )


def _flagger(road: str) -> tuple[str, str, str]:
    if "school" in road:
        return (
            "Obey the flagger and the school speed. Children beside the lane mean you do not roll past on a SLOW paddle.",
            "SLOW from a flagger is not a wave-through when children are next to the lane.",
            "Flagger plus children: creep past only as directed.",
        )
    return (
        "Follow the flagger, at the work-zone speed, and do not pass the workers.",
        "The flagger controls this lane on every road type.",
        "Do what the flagger signals, slowly.",
    )


def _ice(road: str) -> tuple[str, str, str]:
    if "downgrade" in road or "bridge" in road:
        return (
            "Slow before you reach the ice, in a lower gear. Do not brake hard once you are on it.",
            "Grades and bridges need the speed cut before the icy surface.",
            "Slow before the ice, then no hard brake.",
        )
    if "roundabout" in road:
        return (
            "Slow before the entry. Do not brake hard while turning in the circle.",
            "Ice in a roundabout means the speed comes off before the curve.",
            "Scrub speed before the circle, not in it.",
        )
    return (
        "Reduce speed before the icy pavement and lengthen your gap. No sudden brake or turn.",
        "Ice rewards early, gentle inputs.",
        "Ease off before the ice.",
    )


def _crash_block(road: str) -> tuple[str, str, str]:
    if "freeway" in road:
        return (
            "Slow early, put on hazards, and stop well back. Do not squeeze past people standing in the lane.",
            "People in a freeway lane mean stop back, not a thread-through.",
            "Hazards on, stop back, do not pass the people.",
        )
    if "tunnel" in road:
        return (
            "Stop back, hazards on, and do not leave the car in the travel lane if you can still reverse out to the portal.",
            "A tunnel crash with people in the lane is a stop-and-call, not a pass.",
            "Do not pass people in a tunnel lane.",
        )
    return (
        "Stop, hazards on, and wait for direction. Do not move injured people and do not drive through them.",
        "A blocked lane with people standing is a stop.",
        "Stop well back and wait.",
    )


def _gap_choices(bank: Bank) -> None:
    """The safe gap in seconds depends on the surface. Speed changes the distance."""
    surfaces = [
        ("dry pavement", 3),
        ("rain", 4),
        ("snow and ice", 6),
        ("fog", 6),
    ]
    # A few speeds and gaps, not every combination. The seconds and the
    # leader change the action; extra speeds only show that distance grows.
    speeds = [25, 35, 45, 55, 65]
    gaps = [2, 4, 6]
    leaders = [
        ("a passenger car", 0, "Match the seconds for the pavement. Do not use car lengths."),
        ("a motorcycle", 1, "Add at least one more second because a motorcycle can stop faster than you."),
        ("a truck that blocks your view of the road ahead", 1, "Add time and drop back until you can see past the trailer."),
    ]
    for surface, base in surfaces:
        for speed in speeds:
            for leader, extra, why in leaders:
                need = base + extra
                distance = round(speed * 1.467 * need)
                for have in gaps:
                    if have >= need:
                        action = (
                            f"Keep at least {need} seconds behind {leader} on {surface}. "
                            f"You have {have} seconds, about {round(speed * 1.467 * have)} feet at {speed} mph. "
                            f"{why}"
                        )
                        spoken = f"{need} seconds is enough here. Stay there."
                    else:
                        action = (
                            f"Drop back to at least {need} seconds behind {leader}. "
                            f"{have} seconds is too close on {surface}. "
                            f"At {speed} mph that is about {distance} feet. {why}"
                        )
                        spoken = f"Open the gap to {need} seconds, about {distance} feet."
                    bank.add(
                        "following-gap",
                        f"At {speed} mph on {surface}, {leader} is ahead of you and the gap is {have} seconds. What should you do?",
                        action,
                        f"On {surface} the base following time is {base} seconds. {why} At {speed} mph, {need} seconds is about {distance} feet.",
                        spoken,
                        _SPEED_WRONG,
                    )


def _danger_time(bank: Bank) -> None:
    """Hours in the danger zone change the correction. The food changes the reheating rule."""
    foods = [
        ("chicken soup", "reheat it to 165°F"),
        ("cooked rice", "reheat it to 165°F"),
        ("beef chili", "reheat it to 165°F"),
        ("cut melon", "you cannot make cut melon safe by reheating it"),
        ("tuna salad", "you cannot make tuna salad safe by reheating it"),
        ("sliced deli turkey", "you cannot make sliced turkey safe by reheating it"),
        ("cooked pasta", "reheat it to 165°F"),
        ("mashed potatoes", "reheat them to 165°F"),
        ("shrimp cocktail", "you cannot make a cold shrimp cocktail safe by reheating it"),
        ("cooked beans", "reheat them to 165°F"),
        ("potato salad", "you cannot make potato salad safe by reheating it"),
        ("gravy", "reheat it to 165°F"),
        ("fried rice", "reheat it to 165°F"),
        ("macaroni and cheese", "reheat it to 165°F"),
        ("lentil soup", "reheat it to 165°F"),
        ("cheese sauce", "reheat it to 165°F"),
        ("meat sauce", "reheat it to 165°F"),
        ("clam chowder", "reheat it to 165°F"),
        ("cooked ground beef", "reheat it to 165°F"),
        ("rice pudding", "reheat it to 165°F"),
        ("quiche", "reheat it to 165°F"),
        ("cooked vegetables held for service", "reheat them to 165°F"),
        ("peeled hard-boiled eggs", "you cannot make peeled eggs safe by reheating them"),
        ("chicken salad", "you cannot make chicken salad safe by reheating it"),
        ("cut tomatoes", "you cannot make cut tomatoes safe by reheating them"),
        ("cream-filled pastry", "you cannot make a cream pastry safe by reheating it"),
        ("opened tofu in broth", "reheat it to 165°F"),
        ("cooked noodles", "reheat them to 165°F"),
        ("sliced ham", "you cannot make sliced ham safe by reheating it"),
    ]
    uses = [
        "serve it immediately",
        "cool it and store it for tomorrow",
        "put it in the hot well",
    ]
    bands = [
        ("30 minutes", "short"),
        ("3 hours", "mid"),
        ("5 hours", "long"),
        ("an unknown time", "unknown"),
    ]
    for food, reheat in foods:
        cold_rte = reheat.startswith("you cannot")
        for label, band in bands:
            for use in uses:
                if band == "unknown" or band == "long":
                    action = f"Discard the {food}. {label[0].upper() + label[1:]} in the danger zone is too long or not provable."
                    spoken = f"Discard the {food}."
                    rubric = "More than four hours, or an unknown time, in the danger zone means discard."
                elif cold_rte and use == "put it in the hot well":
                    action = f"Do not put the {food} in the hot well. It is a cold ready-to-eat food. Chill it to 41°F or below if it has been warm only a short known time, otherwise discard it."
                    spoken = f"The {food} does not go in the hot well."
                    rubric = "Cold ready-to-eat food is not saved by hot holding."
                elif band == "mid" and cold_rte:
                    action = f"Discard the {food}. It is cold ready-to-eat food that has already been in the danger zone for {label}."
                    spoken = f"Discard the {food}."
                    rubric = "Cold ready-to-eat food left warm for hours is discarded, not reheated."
                elif band == "mid" and use == "cool it and store it for tomorrow":
                    action = f"Do not cool the {food} for tomorrow after {label} in the danger zone. Discard it, or reheat it to 165°F and serve it now."
                    spoken = f"Do not save the {food} for tomorrow."
                    rubric = "After two hours in the danger zone, do not start cooling for later storage."
                elif band == "mid":
                    action = f"Reheat the {food} to 165°F and then serve it. Do not cool it for later after {label} in the danger zone."
                    spoken = f"Reheat the {food} to 165 and serve it now."
                    rubric = "Hot food between two and four hours can be reheated to 165°F for immediate service."
                elif cold_rte and use == "cool it and store it for tomorrow":
                    action = f"The {food} has been warm only {label}. Cool it to 41°F quickly in shallow pans, or discard it if you cannot."
                    spoken = f"Chill the {food} to 41 now, or discard it."
                    rubric = "A short time above 41°F can still be corrected by rapid chilling."
                elif cold_rte:
                    action = f"Chill the {food} to 41°F or below before you serve it. It has been warm only {label}."
                    spoken = f"Get the {food} back to 41 before it is served."
                    rubric = "Cold ready-to-eat food served after a short warm spell still has to be at 41°F or below."
                elif use == "cool it and store it for tomorrow":
                    action = f"The {food} has been warm only {label}. Cool it in shallow pans to 70°F within two hours and to 41°F within four more."
                    spoken = "Cool it in shallow pans, or discard it."
                    rubric = "Under two hours, hot food can still be cooled on the two-stage clock."
                elif use == "put it in the hot well":
                    action = f"Reheat the {food} to 165°F first, then hold it at 135°F or above. Do not drop it in the well at a danger-zone temperature."
                    spoken = f"Reheat the {food} to 165, then hold it at 135 or above."
                    rubric = "Food going back to hot holding is reheated to 165°F, not warmed gently in the well."
                else:
                    action = f"Reheat the {food} to 165°F, then serve it. It has been in the danger zone only {label}."
                    spoken = f"Reheat the {food} to 165, then serve it."
                    rubric = "Under two hours, hot food can be reheated to 165°F and served."
                bank.add(
                    "danger-zone-time",
                    f"The {food} has been in the danger zone for {label}. You want to {use}. What do you do?",
                    action,
                    rubric,
                    spoken,
                    _FOOD_WRONG,
                )


def _food() -> Bank:
    bank = Bank("food-safety")
    _temps(bank)
    _hygiene(bank)
    _contamination(bank)
    _allergens(bank)
    _clean_and_receive(bank)
    _time_and_storage(bank)
    _service(bank)
    _danger_time(bank)
    for row in food_scene_rows():
        bank.add(*row, _FOOD_WRONG)
    return bank


_FOODS = [
    ("chicken breast", "poultry", "flat-top"),
    ("roasted turkey", "poultry", "oven"),
    ("ground turkey burger", "poultry", "grill"),
    ("duck breast", "poultry", "saute pan"),
    ("stuffed chicken breast", "stuffed", "oven"),
    ("stuffed pasta with meat", "stuffed", "steam well"),
    ("ground beef patty", "ground", "grill"),
    ("ground pork meatball", "ground", "oven"),
    ("raw sausage link", "ground", "flat-top"),
    ("injected beef roast", "ground", "oven"),
    ("beef steak", "whole", "grill"),
    ("pork chop", "whole", "flat-top"),
    ("lamb loin", "whole", "oven"),
    ("salmon fillet", "whole", "saute pan"),
    ("cod fillet", "whole", "steamer"),
    ("shrimp", "whole", "saute pan"),
    ("scrambled eggs for the buffet", "egg_hold", "steam well"),
    ("an egg cooked to order for immediate service", "egg_now", "saute pan"),
    ("beef gravy", "reheat", "steam well"),
    ("leftover chili reheated for hot holding", "reheat", "steam kettle"),
    ("cooked rice", "tcs_hold", "steam well"),
    ("cooked black beans", "tcs_hold", "steam well"),
    ("mashed potatoes", "tcs_hold", "steam well"),
    ("cooked pasta", "tcs_hold", "steam well"),
    ("chicken soup", "tcs_hold", "steam well"),
    ("cut cantaloupe", "cold", "cold well"),
    ("sliced tomatoes", "cold", "prep table"),
    ("cut leafy greens", "cold", "walk-in"),
    ("tuna salad", "cold", "cold well"),
    ("potato salad", "cold", "walk-in"),
    ("opened milk", "cold", "reach-in"),
    ("soft cheese tray", "cold", "cold well"),
    ("cooked shrimp cocktail", "cold", "cold well"),
    ("previously cooked chicken for a salad", "cold", "walk-in"),
    ("beef stew for a catering cambro", "reheat", "cambro"),
    ("fish stored for sushi rice service", "cold", "sushi case"),
    ("hollandaise", "egg_hold", "steam well"),
    ("breaded chicken tender", "poultry", "fryer"),
    ("whole beef roast", "roast", "oven"),
    ("comminuted fish cake", "ground", "flat-top"),
]


_TARGETS = {
    "poultry": "165°F",
    "stuffed": "165°F in the center of the stuffing as well as the meat",
    "ground": "155°F for 17 seconds",
    "whole": "145°F for 15 seconds",
    "egg_hold": "155°F for 17 seconds",
    "egg_now": "145°F for 15 seconds",
    "reheat": "165°F within 2 hours",
    "tcs_hold": "135°F while it is hot-held, and 165°F if you must reheat it for hot holding",
    "cold": "41°F or below",
    "roast": "145°F for 4 minutes",
}


def _temps(bank: Bank) -> None:
    # Readings chosen at the decision boundary for that food, not a sweep.
    below = {
        "poultry": "158°F",
        "stuffed": "160°F in the meat but the stuffing is cooler",
        "ground": "150°F",
        "whole": "140°F",
        "egg_hold": "150°F",
        "egg_now": "130°F",
        "reheat": "150°F and it has been reheating for 30 minutes",
        "tcs_hold": "120°F",
        "cold": "50°F",
        "roast": "145°F but you just got there and have not held it",
    }
    at = {
        "poultry": "165°F in the thickest part",
        "stuffed": "165°F in the center of the stuffing",
        "ground": "155°F and the probe has been steady for 17 seconds",
        "whole": "145°F for 15 seconds",
        "egg_hold": "155°F for 17 seconds",
        "egg_now": "145°F for 15 seconds and it will be served now",
        "reheat": "165°F and you started reheating less than 2 hours ago",
        "tcs_hold": "140°F",
        "cold": "39°F",
        "roast": "145°F and it has held that temperature for 4 minutes",
    }
    hold_kinds = {"tcs_hold", "reheat", "egg_hold"}
    for food, kind, station in _FOODS:
        target = _TARGETS[kind]
        reading_low = below[kind]
        reading_ok = at[kind]
        if kind == "cold":
            bank.add(
                "cold-holding",
                f"The {food} in the {station} reads {reading_low}. It is a cold food, not something you cook hotter. What do you do?",
                f"Do not serve the {food} at {reading_low}. Cold TCS food must be 41°F or below. If you know it just came out and you can chill it immediately, do that. If the time above 41°F is unknown, discard it.",
                f"{food.capitalize()} is held cold at 41°F or below. {reading_low} is already too warm.",
                f"{reading_low} is too warm for the {food}. Chill it or discard it.",
                _FOOD_WRONG,
            )
            bank.add(
                "cold-holding",
                f"The {food} in the {station} reads {reading_ok} in the thickest part. What may you do?",
                f"Keep the {food} at 41°F or below and serve it cold. Do not set it on the counter.",
                f"{reading_ok} meets cold holding for {food}.",
                f"The {food} is cold enough. Keep it that way.",
                _FOOD_WRONG,
            )
        else:
            bank.add(
                "cooking-and-holding",
                f"The {food} on the {station} reads {reading_low}. It is still coming up to temperature. The rule for this food is {target}. What do you do?",
                f"Keep cooking the {food} until it reaches {target}. Do not serve it yet.",
                f"{food.capitalize()} is not done at {reading_low}. It needs {target}.",
                f"Not yet. Carry the {food} to {target}.",
                _FOOD_WRONG,
            )
            bank.add(
                "cooking-and-holding",
                f"The {food} on the {station} reads {reading_ok}. What may you do with it now?",
                f"The {food} has reached {target}. You may serve it or hot-hold it at 135°F or above.",
                f"The check shows {food} has reached {target}.",
                f"That reading is enough for the {food}.",
                _FOOD_WRONG,
            )
        if kind == "cold":
            bank.add(
                "cold-holding",
                f"The {food} in the {station} reads 48°F and nobody knows how long it has been above 41°F. What do you do?",
                f"Discard the {food}. Cold TCS food above 41°F for an unknown time is not saved by chilling it now.",
                "Unknown time in the danger zone means discard, not a quick chill and serve.",
                f"Time unknown above 41: discard the {food}.",
                _FOOD_WRONG,
            )
            bank.add(
                "receiving",
                f"A delivery of {food} arrives at 38°F with intact packaging and no odor. Do you accept it?",
                f"Accept the {food}. Cold TCS food received at 41°F or below, with sound packaging, can come in.",
                "Cold deliveries must be 41°F or below. 38°F meets that.",
                f"38°F and sound packaging: accept the {food}.",
                _FOOD_WRONG,
            )
            bank.add(
                "receiving",
                f"A delivery of {food} arrives at 50°F. The driver says the truck was only warm for a few minutes. Do you accept it?",
                f"Reject the {food}. Cold TCS food received above 41°F does not come into the kitchen.",
                "Receiving temperature is checked at the door. A driver's story does not replace the thermometer.",
                f"50°F at the dock: reject the {food}.",
                _FOOD_WRONG,
            )
        elif kind in hold_kinds:
            bank.add(
                "hot-holding",
                f"The {food} on the {station} has fallen to 125°F. You know it dropped below 135°F less than two hours ago. What do you do?",
                f"Reheat the {food} to 165°F within two hours and then hot-hold it at 135°F or above. Do not just turn the well up and leave it at 125°F.",
                "A known short time below 135°F can be corrected by reheating to 165°F. Holding warmer is not reheating.",
                f"Reheat the {food} to 165, then hold it at 135 or above.",
                _FOOD_WRONG,
            )
            bank.add(
                "hot-holding",
                f"The {food} on the {station} reads 120°F and the cook who opened the station is gone. Nobody can say when it left 135°F. What do you do?",
                f"Discard the {food}. Unknown time under 135°F is not a reheat-and-serve situation.",
                "If you cannot prove the time below 135°F, you discard the food.",
                f"Time unknown under 135: discard the {food}.",
                _FOOD_WRONG,
            )
            bank.add(
                "receiving",
                f"Hot {food} arrives for a catering drop at 150°F in a closed carrier. What do you do?",
                f"You may accept the {food} because hot TCS food received at 135°F or above is in range. Keep it hot or serve it.",
                "Hot food must arrive at 135°F or above. 150°F passes.",
                f"150°F at receiving: the {food} can come in.",
                _FOOD_WRONG,
            )


def _hygiene(bank: Bank) -> None:
    moments = [
        ("You breaded raw chicken and the next ticket is a green salad.", "Take off the gloves, wash hands with soap for 20 seconds, dry with a single-use towel, and put on new gloves before the salad.", "Raw poultry to ready-to-eat food requires a wash and a new pair of gloves.", "Raw chicken, then salad: wash, then new gloves."),
        ("You return from the restroom and the line is in the weeds.", "Wash hands for 20 seconds before gloves or food. The rush does not skip the sink.", "Restroom use is always a handwash, before gloves.", "Restroom, then the sink, then the line."),
        ("You took a personal call on your phone at the pass and need to plate food.", "Wash before you touch food or clean utensils. The phone is not a clean surface.", "Phones are dirty. Wash after using one and before food.", "Phone down, then wash, then plate."),
        ("You took out the trash and came straight back to the sandwich station.", "Wash hands before you build the sandwich.", "Trash handling is a handwash moment.", "After trash: wash before food."),
        ("Your glove tears while you portion ready-to-eat cheese.", "Throw the glove away, wash, and put on a new glove. Do not tape it.", "A torn glove is a new glove plus a wash, not a patch.", "Torn glove: wash and replace it."),
        ("You want to rinse the same single-use gloves and keep going.", "Throw them away. Single-use gloves are not washed and reused.", "Washing gloves does not reset them.", "Those gloves are done. Wash your hands and get a new pair."),
        ("A cook says hand sanitizer is enough because the sink is across the kitchen.", "Walk to the sink. Sanitizer does not replace soap and water in food service.", "Hand sanitizer is not a handwash.", "Sanitizer is not the wash."),
        ("You have a cut on your finger and want to keep plating.", "Cover it with a bandage and a glove, or leave the food line if it is not covered. Do not work with an open cut.", "A wound on the hand needs a bandage and a glove.", "Bandage and glove, or step off the line."),
        ("Blood from a cut has touched a ready-to-eat sandwich.", "Discard the sandwich. Wash, cover the wound, glove, and tell a manager.", "Blood on ready-to-eat food means that portion is discarded.", "The sandwich is trash. Then cover the cut."),
        ("You have diarrhea this morning and the shift is short-staffed.", "Do not work with food. Call the manager and report the symptoms.", "Diarrhea excludes you from food handling. The schedule does not override that.", "Stay home and tell the manager."),
        ("You vomited before the shift and feel better now.", "Do not start the shift. Report it. Return only when the exclusion rule your manager applies says you may.", "Vomiting excludes you. Feeling a little better is not clearance.", "Vomiting means you do not handle food."),
        ("Your eyes look yellow and a coworker mentions jaundice.", "Stop working with food and tell the manager immediately. Jaundice is an exclusion symptom.", "Jaundice is reported and you are excluded. You do not diagnose yourself and keep working.", "Yellow eyes: off the line, tell the manager."),
        ("A doctor told you that you have hepatitis A.", "Tell the manager before any food work. Diagnosed hepatitis A is a Big Six exclusion and reporting event.", "Hepatitis A is one of the Big Six. Report it. Do not work.", "Hepatitis A: tell the manager and do not work."),
        ("You have a sore throat and fever.", "Tell the manager before handling food. A sore throat with fever restricts or excludes you under the policy.", "Sore throat with fever is reported, not hidden for the shift.", "Fever and sore throat: report it before you touch food."),
        ("Your hair is down and you are about to plate.", "Restrain your hair before you handle food.", "A hair restraint is part of the uniform, not a style choice.", "Tie the hair back before you plate."),
        ("You are wearing a ring with a stone on the prep hand.", "Remove the ring before you work with food. It traps soil and tears gloves.", "Jewelry that can hold soil or tear a glove comes off.", "The ring comes off for the shift."),
        ("You need a drink of water on the line.", "Use a closed cup with a straw, stored so it cannot spill onto food, or step away. No open cup on the line.", "Open drinks on the line contaminate the station.", "Closed cup, or drink away from the food."),
        ("You taste a sauce with your finger.", "Do not. Use a clean spoon once and put that spoon in the dish pit.", "Finger tasting contaminates the batch.", "One clean spoon, then the pit. Not your finger."),
        ("A glove has been on for four hours of continuous sandwich work and is not torn.", "Wash and change the gloves. Four hours is the longest continuous use, and sooner if they are dirty.", "Gloves are changed at least every four hours, and any time they are contaminated.", "Four hours: wash and change gloves."),
        ("You handled raw ground beef and the next task is ready-to-eat rolls.", "Wash, new gloves, and clean utensils before the rolls.", "Raw ground meat to ready-to-eat bread is a wash and a tool change.", "New wash, new gloves, clean tool, then the rolls."),
    ]
    for prompt, action, rubric, spoken in moments:
        bank.add("hygiene", prompt + " What do you do?", action, rubric, spoken, _FOOD_WRONG)
    # Same symptom, different pathogen duty — the diagnosis changes the report.
    big_six = [
        ("norovirus", "exclude yourself and tell the manager so the regulatory report can be made"),
        ("hepatitis A", "exclude yourself and tell the manager immediately so hepatitis A is reported"),
        ("Salmonella Typhi", "exclude yourself and tell the manager. Typhoid is not a work-through illness"),
        ("nontyphoidal Salmonella", "exclude yourself and tell the manager. Do not return until the rule for Salmonella says you may"),
        ("Shigella", "exclude yourself and tell the manager. Shigella is a Big Six exclusion"),
        ("Shiga toxin-producing E. coli", "exclude yourself and tell the manager. STEC is a Big Six exclusion"),
    ]
    for name, action in big_six:
        bank.add(
            "illness",
            f"A clinician told you that you have {name}. You feel well enough to work the lunch line. What do you do?",
            action + ".",
            f"{name} is one of the Big Six. Food employees report it and stay out of food handling.",
            f"{name}: do not work. Tell the manager.",
            _FOOD_WRONG,
        )


def _contamination(bank: Bank) -> None:
    raws = [
        ("raw chicken juice", "poultry"),
        ("raw ground beef", "ground"),
        ("raw shrimp shells", "seafood"),
        ("a cracked raw egg", "egg"),
    ]
    rte = ["lettuce for salads", "sliced melon", "cooked rice for the line", "sliced turkey", "a finished sandwich"]
    will_cook = ["a raw steak that will be cooked to 145°F", "a raw burger that will be cooked to 155°F"]
    for raw, _kind in raws:
        for food in rte:
            bank.add(
                "cross-contamination",
                f"{raw.capitalize()} drips onto {food}, which will not be cooked again. What do you do with that {food} and with the station?",
                f"Discard the {food}. Wash your hands, change gloves, and wash-rinse-sanitize the surface before any other food.",
                "Ready-to-eat food touched by raw animal food is discarded. The station is then cleaned and sanitized.",
                f"The {food} is discarded. Then wash and sanitize.",
                _FOOD_WRONG,
            )
        for food in will_cook:
            bank.add(
                "cross-contamination",
                f"{raw.capitalize()} splashes onto {food}. What is different from a splash onto a salad?",
                f"You may still cook the {food} to its required temperature because it will be cooked, but wash, change gloves, and wash-rinse-sanitize the board before it touches anything else.",
                "Food that will still be cooked can be cooked to temperature. Ready-to-eat food that was splashed cannot.",
                f"Cook it to temperature. Clean the board before the next food.",
                _FOOD_WRONG,
            )
    storage = [
        ("raw chicken stored above an open pan of cooked rice", "Move the chicken to the bottom shelf and discard the rice if juice could have dripped in.", "Raw poultry goes below ready-to-eat food. Suspect rice is discarded.", "Poultry on the bottom. Rice that was underneath is not served."),
        ("raw ground beef stored above whole fish", "Move the ground beef below the fish. Ground meat has a higher cooking temperature and must not drip onto seafood.", "Store by final cooking temperature: higher minimums go lower.", "Ground beef below the fish."),
        ("ready-to-eat salad on the bottom and raw chicken on the top", "Swap them. Ready-to-eat food goes above raw poultry.", "Top to bottom: ready-to-eat, then seafood, whole cuts, ground meat, poultry at the bottom.", "Salad above, chicken at the bottom."),
        ("a sanitizer bucket stored over the prep table so drips hit the cutting board", "Move the bucket off the food surface and discard any food the sanitizer touched.", "Chemicals do not live above food. Contaminated food is discarded.", "Bucket down. Food it dripped on is discarded."),
        ("a spray bottle of degreaser in an unlabeled bottle that used to hold juice", "Label it or discard it. Never store a chemical in a food container a person could drink from.", "Chemicals stay in labeled containers that cannot be mistaken for food.", "Do not leave degreaser in a juice bottle."),
        ("ice that cooled a raw-chicken pan is about to go into drinks", "Throw that ice away. Ice that touched raw food is not beverage ice.", "Ice is food. Ice used as a coolant for raw food is not served.", "That ice is not for drinks."),
        ("a can of tomatoes with swollen ends", "Reject or discard it. Swelling can mean gas from spoilage.", "Swollen cans do not get opened for service.", "Swollen can: do not use it."),
        ("a can with a deep dent on the side seam", "Reject it. A seam dent can let bacteria in.", "Seam damage is a reject, even if the rest of the can looks fine.", "Dent on the seam: reject the can."),
        ("a frozen fish fillet with ice crystals and soft spots", "Reject it. Those signs can mean it thawed and was refrozen.", "Ice crystals and soft flesh are a receiving reject.", "Do not accept fish that thawed and refroze."),
        ("mouse droppings on the flour shelf and flour bags that are open", "Stop, tell the manager, and discard the exposed flour. Do not scoop around the droppings.", "Pests plus exposed food means discard the exposed food and report it.", "Discard the open flour and call the manager."),
    ]
    for prompt, action, rubric, spoken in storage:
        bank.add("contamination", prompt[0].upper() + prompt[1:] + ". What do you do?", action, rubric, spoken, _FOOD_WRONG)


def _allergens(bank: Bank) -> None:
    allergens = [
        ("peanuts", "the fryer oil was used for peanut-crusted items"),
        ("tree nuts", "the pesto was made with walnuts"),
        ("milk", "the mashed potatoes were finished with butter"),
        ("eggs", "the bun is egg-washed"),
        ("fish", "the marinade includes fish sauce"),
        ("shellfish", "the same fryer just cooked shrimp"),
        ("wheat", "the soy sauce contains wheat"),
        ("soy", "the sauce is soy sauce"),
        ("sesame", "the bun is topped with sesame seeds"),
    ]
    for allergen, hidden in allergens:
        bank.add(
            "allergens",
            f"A guest says they have a {allergen} allergy. You know {hidden}. They ask if the plate is safe. What do you do?",
            f"Do not guess and do not serve that plate. Tell the guest and the manager, and remake the order with clean utensils and a surface that has not touched {allergen}.",
            f"Cross-contact with {allergen} is enough to harm the guest. The honest answer is that this plate is not safe.",
            f"That plate is not safe for a {allergen} allergy. Remake it clean.",
            _FOOD_WRONG,
        )
        bank.add(
            "allergens",
            f"A guest with a {allergen} allergy asks you to pick off the visible {allergen} and serve the same plate.",
            f"Do not pick it off and serve it. {allergen.capitalize()} protein can remain. Remake the dish with separate tools.",
            "Removing the visible allergen does not remove cross-contact.",
            f"Picking off the {allergen} is not enough. Remake the plate.",
            _FOOD_WRONG,
        )
    scenes = [
        ("The menu does not list sesame and a guest asks if the sauce contains it. You are not sure.", "Say you will check with the manager or the recipe. Do not say it is probably fine.", "An unknown allergen answer is a check, not a guess.", "If you are not sure, you say so and check."),
        ("A pan just used for shrimp is the only saute pan, and the next order is a shellfish allergy.", "Wash-rinse-sanitize the pan or use a clean one. Do not rinse and reuse.", "A rinse does not remove allergen protein.", "The shrimp pan is not clean enough. Wash it fully or replace it."),
        ("A bakery tray of cookies shares a case with peanut cookies and the crumbs are mixed.", "Do not sell the plain cookies as peanut-free.", "Shared crumbs are cross-contact.", "Mixed crumbs: do not call those cookies peanut-free."),
        ("A child says they cannot have milk. The soup is finished with cream.", "Tell the adult the soup contains milk. Offer a soup that does not, made with clean tools.", "Cream is milk. Say so.", "The soup has milk. Offer something else."),
        ("Gluten-free pasta is boiled in the water that just cooked regular pasta.", "Use fresh water. Shared water transfers wheat.", "Pasta water carries the allergen.", "New water for the gluten-free pasta."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("allergens", prompt + " What do you do?", action, rubric, spoken, _FOOD_WRONG)


def _clean_and_receive(bank: Bank) -> None:
    scenes = [
        ("A chlorine sanitizer bucket reads 0 ppm on the test strip. The label range for this food-contact bucket is 50 to 100 ppm.", "Dump it and remix the bucket until the strip reads inside 50 to 100 ppm.", "Zero ppm does not sanitize. Remake it to the labeled range.", "Zero on the strip: remake the bucket."),
        ("A chlorine food-contact bucket reads 75 ppm and the labeled range is 50 to 100 ppm.", "The bucket is in range. Keep wiping cloths in it between uses.", "75 ppm chlorine is inside a 50 to 100 ppm food-contact range.", "75 ppm matches the label. Use it."),
        ("A chlorine food-contact bucket reads 200 ppm and the labeled range is 50 to 100 ppm.", "Remake it. 200 ppm is too strong for that bucket.", "Over-strength sanitizer is not 'extra clean.' Match the label.", "200 ppm is too high. Mix it again."),
        ("A quat bucket's label says 200 to 400 ppm and the strip reads 150 ppm.", "Remake the quat bucket. 150 is below the label.", "Quat concentration follows the label on that product, not the chlorine numbers.", "150 ppm quat is weak for a 200 to 400 label. Remake it."),
        ("A quat bucket's label says 200 to 400 ppm and the strip reads 300 ppm.", "It is in range. Store the wiping cloths in the bucket.", "300 ppm is inside a 200 to 400 quat label.", "300 ppm quat: the bucket is ready."),
        ("A cook sprays sanitizer on a table still coated with grease and wipes food onto it.", "Clean the grease off with detergent and rinse, then sanitize. Sanitizer does not work through soil.", "Clean first, then sanitize.", "Degrease and rinse, then sanitize."),
        ("Dishes come out of the third compartment and someone towels them with the wiping cloth.", "Let them air-dry. Do not towel them with a cloth that lives in the bucket.", "Air-drying avoids putting soil back on a sanitized surface.", "Air-dry. Do not towel with the sanitizer cloth."),
        ("The three-compartment sink is set up sanitize, then wash, then rinse.", "Reset it: wash, rinse, sanitize, then air-dry.", "The order is wash, rinse, sanitize. Sanitizer first does not clean.", "Wash, then rinse, then sanitize."),
        ("A wiping cloth is on the cutting board between uses.", "Put the cloth back in the sanitizer bucket. Do not leave it on the board.", "Cloths are stored in sanitizer, not on food-contact surfaces.", "Cloth goes back in the bucket."),
        ("The dish machine's final rinse is not reaching the temperature on the gauge posted on the machine.", "Stop using it for sanitizing, tell the manager, and use the three-compartment sink until it is fixed.", "A dish machine that misses its sanitizing temperature is out of service.", "Gauge is low: stop and switch to the sink."),
        ("You need to thaw frozen chicken for tonight on the counter because the walk-in is full.", "Do not thaw it on the counter. Thaw it in the refrigerator, under cold running water, in the microwave if you cook it immediately, or as part of cooking.", "Room-temperature thawing is not an approved method.", "Counter thawing is a no. Use the fridge or another approved method."),
        ("Frozen soup is thawed under running water and the water in the sink is pooled and warm.", "Use cold running water at 70°F or below, with the food submerged and the water moving. Warm standing water is not the method.", "Thawing water must be cold and running, not a warm bath.", "Dump the warm water. Use cold running water."),
        ("You microwave-thawed chili and want to put it back in the walk-in for tomorrow.", "Cook it immediately. Food thawed in the microwave is not saved for later.", "Microwave thawing is followed by cooking right away.", "Microwave thaw: cook it now."),
        ("A walk-in thermometer reads 45°F and has been that way since you arrived. The chicken and milk are in it.", "Tell the manager, do not add more food, and discard TCS food that has been above 41°F for an unknown time.", "A walk-in above 41°F is an emergency for the food already inside.", "45°F walk-in: stop storing TCS food there and check what must be discarded."),
        ("The hot-holding well reads 135°F at the food surface and the food has been there since the check an hour ago.", "You may keep holding it. Check it again on schedule. 135°F is the minimum, so watch that it does not fall.", "135°F is the hot-holding floor. It is legal and it has no margin, so keep checking.", "135 at the food: still legal. Check it again soon."),
        ("Rice cooled from 135°F to 80°F in two hours.", "It missed 70°F. Reheat it to 165°F and start cooling again, or discard it.", "The first cooling stage is 135°F to 70°F within two hours.", "80°F at two hours: reheat to 165 and restart, or discard."),
        ("Soup cooled from 135°F to 68°F in two hours. It is now hour two.", "Keep cooling. It must reach 41°F within four more hours.", "Hitting 70°F within two hours means the second stage is four hours to 41°F.", "On track. Get it to 41 within four more hours."),
        ("Chili has been cooling for six hours and is still 50°F.", "Discard it. The total cooling time cannot exceed six hours.", "Six hours and still above 41°F is a discard.", "Six hours and 50°F: throw it out."),
        ("A cook wants to cool a stockpot of chili in the walk-in with the lid on, full depth.", "Split it into shallow pans, leave them loosely covered, and stir or use an ice bath so it actually cools.", "A deep covered pot will not meet the cooling times.", "Shallow pans, not one deep covered pot."),
        ("Raw chicken, ready-to-eat ham, and whole fish need homes in the walk-in.", "Ham on top, whole fish in the middle, raw chicken on the bottom.", "Ready-to-eat above seafood, and poultry at the bottom so it cannot drip on food with a lower cooking temperature.", "Ham above, chicken on the bottom."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("cleaning-and-temperature-control", prompt + " What do you do?", action, rubric, spoken, _FOOD_WRONG)


def _time_and_storage(bank: Bank) -> None:
    foods = ["cooked rice", "opened deli turkey", "tuna salad", "cut melon", "soups cooled yesterday", "cooked pasta"]
    # Day count changes the action: day 7 may still be used, day 8 is discard.
    for food in foods:
        for day, action, spoken in (
            (1, f"The {food} may be kept. Day of prep is day 1. Mark the date.", f"Day 1 for the {food}: mark it and keep it at 41°F or below."),
            (6, f"The {food} may still be used today if it has stayed at 41°F or below. Tomorrow is the last day.", f"Day 6: still usable if it stayed cold."),
            (7, f"The {food} may be used through today if it stayed at 41°F or below. Discard it at the end of day 7.", f"Day 7 is the last day for the {food}."),
            (8, f"Discard the {food}. Ready-to-eat TCS food is kept only seven days at 41°F, and the prep day counts as day 1.", f"Day 8: discard the {food}."),
        ):
            bank.add(
                "date-marking",
                f"The {food} was prepared on day 1 and held at 41°F. Today is day {day}. What do you do with it?",
                action,
                "Ready-to-eat TCS food held more than 24 hours is date-marked and discarded after seven days at 41°F.",
                spoken,
                _FOOD_WRONG,
            )
    scenes = [
        ("New stock of milk is behind older milk in the reach-in.", "Rotate it. Use the older milk first, if it is still in date and cold.", "First in, first out. New stock goes behind old stock.", "Older milk comes forward."),
        ("A pan of soup has no date mark and the cook who made it yesterday is off.", "Discard it if you cannot verify the day it was made. Do not guess a date.", "Unmarked ready-to-eat TCS food you cannot date is not served.", "No date and no one who knows: discard it."),
        ("You are prepping lettuce that will be used within four hours and kept above 41°F under a written time policy.", "Mark the time it became food without temperature control and discard it at four hours.", "Time as a public health control needs a start time and a hard discard time.", "Mark the start. Four hours, then it is trash."),
        ("That same lettuce has no time mark and has been on the counter since the opener left.", "Discard it. Without a start time you cannot use the four-hour rule.", "No mark means you do not get to assume it is inside the window.", "No time on it: discard the lettuce."),
        ("Chemicals are stored on the same shelf as dry pasta.", "Move the chemicals to a separate, labeled area below or away from food.", "Chemicals and food do not share a shelf.", "Pasta stays. Chemicals move away."),
        ("A food employee is eating a plate of fries at the prep table.", "Move the meal to a break area. Eating is not done over the prep surface.", "The prep table is not a break table.", "Eat away from the prep table."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("storage", prompt + " What do you do?", action, rubric, spoken, _FOOD_WRONG)


def _service(bank: Bank) -> None:
    scenes = [
        ("A self-serve buffet sneeze guard is missing over the cut melon.", "Stop service of that pan until a guard or an employee serves it. Do not leave cut melon open to the room.", "Ready-to-eat self service needs a sneeze guard or a server.", "No guard: do not leave the melon self-serve."),
        ("A guest uses their fingers in the buffet salad and puts some back.", "Discard the salad the hand touched and replace the utensil. Tell a manager if the pan is in doubt.", "A hand in the pan contaminates that food.", "That salad comes off the buffet."),
        ("The buffet spoon for the rice is resting with the handle in the rice.", "Turn it so the handle sticks out, or replace it if the handle was soiled.", "Utensil handles stay out of the food.", "Handle out of the rice."),
        ("A catering cambro of chicken left the kitchen at 150°F. Two hours later on the site it is 110°F and the trip time was not logged.", "Do not serve it. Unknown time below 135°F means discard.", "Transport without a time and temperature log does not get the benefit of the doubt.", "110°F and no log: do not serve the chicken."),
        ("A school tray line keeps milk in a well that reads 43°F.", "Move the milk to a colder well or ice it to 41°F or below before service. Recheck.", "Milk on the line is still cold-holding at 41°F or below.", "43°F is too warm for the milk."),
        ("A hospital tray has a 'no fish' diet note and the sauce was made with fish stock.", "Do not send the tray. Remake the plate without fish and tell the supervisor.", "A diet restriction is an allergen-style stop. Fish stock is fish.", "Fish stock counts. Remake the tray."),
        ("Bare hands are used to place pickles on a ready-to-eat burger in a kitchen that does not have an approved bare-hand procedure.", "Stop. Use a glove, deli paper, or tongs. Wash first if you switch.", "Without an approved procedure, ready-to-eat food gets a barrier.", "Use a barrier. Bare hands are not the default."),
        ("A guest asks for the burger rare. Your menu does not have a consumer advisory and the guest is a child.", "Cook the burger to 155°F for 17 seconds. Do not serve an undercooked burger to a child, and do not invent an advisory.", "Undercooked ground beef is not served to children, and not at all without a proper advisory where the code allows it.", "The child's burger is cooked to 155."),
        ("A food truck's cold drawer reads 46°F at the lunch stop and the sliced tomatoes have been in it since prep with no time mark.", "Stop selling those tomatoes and any other TCS food that warm. Tell the operator. Discard what you cannot prove was held cold.", "A food truck uses the same 41°F rule. A warm drawer is not a gray area.", "46°F drawer: those tomatoes are done."),
        ("An employee with a nosebleed pinches their nose over the prep table.", "Step away, wash, and discard any food that may have been exposed. Tell the manager.", "Blood over a prep table means the exposed food is discarded.", "Away from the food. Discard what might have been hit."),
        ("The sanitizer test strips expired last month.", "Do not trust them. Get current strips before you sign off a bucket as safe.", "An expired strip cannot prove the concentration.", "Expired strips: do not guess the bucket is fine."),
        ("A case of shell eggs is stored above ready-to-eat salad mix.", "Move the eggs below the salad so a broken egg cannot drip onto it.", "Shell eggs are a raw animal food. They go below ready-to-eat food.", "Eggs under the salad, not over it."),
        ("You washed produce in the handwashing sink.", "Do not. The hand sink is only for hands. Use the prep sink.", "The hand sink is not a food sink.", "Hands only in that sink. Produce goes to the prep sink."),
        ("The hand sink has no soap and no paper towels at the start of service.", "Restock soap and towels before anyone handles food. Handwashing without them is not a wash.", "A hand sink without soap and a way to dry is not open for service.", "Soap and towels first, then the line opens."),
        ("A leftover hotel pan of rice from last night was cooled correctly, marked day 1, and held at 40°F. Today you will hot-hold it.", "Reheat it to 165°F within two hours, then hold it at 135°F or above.", "Food reheated for hot holding must reach 165°F.", "Reheat the rice to 165, then hold it hot."),
        ("A pot of soup is held at 140°F and a cook dilutes it with a quart of cold water.", "Recheck the temperature. If it fell below 135°F, reheat to 165°F. Do not assume the well will catch up.", "Adding cold food or water can drop hot food out of the holding range.", "Stir and recheck. Reheat to 165 if it fell below 135."),
    ]
    for prompt, action, rubric, spoken in scenes:
        bank.add("service", prompt + " What do you do?", action, rubric, spoken, _FOOD_WRONG)


def _extra_driver_context(bank: Bank) -> None:
    """Same legal duty, different road context that changes what 'safe' looks like."""
    contexts = [
        ("a raining night on an unlit rural highway", "slow well below the posted limit and lengthen the gap past three seconds"),
        ("a sunny noon on a dry freeway", "you may use the posted maximum if traffic and your sight distance allow, with at least a three-second gap"),
        ("dawn fog in a school zone that is in effect", "school speed first, low beams, and a gap you can stop inside"),
        ("a mountain downgrade with a loaded car", "use a lower gear so the brakes do not fade, and keep a long gap"),
        ("an icy bridge in full sun while the road before it is wet", "slow before the bridge. The deck can be frozen when the road is not"),
        ("a construction lane shift at night with barrels", "follow the barrels at the posted work speed, not the old lane lines"),
        ("a busy downtown one-way street with a bus stop", "watch the bus and people stepping out. Do not pass a stopped bus in the same lane"),
        ("a parking-lot aisle with pedestrians walking behind cars", "creep, cover the brake, and yield to people walking, even without a crosswalk"),
    ]
    duties = [
        ("You need to stop for a signal you can see turning yellow.", "Stop if you can do it safely before the line; otherwise clear the intersection.", "Yellow still means stop when you can, in this setting as anywhere."),
        ("A pedestrian steps into the roadway ahead.", "Stop and yield. The setting does not remove the duty.", "People in the road come before the flow of traffic."),
        ("Your following gap has closed to under two seconds.", "Drop back until the gap matches the conditions.", "Under two seconds is too close in every one of these settings."),
    ]
    for place, how in contexts:
        for duty, action, rubric in duties:
            bank.add(
                "conditions",
                f"Setting: {place}. {duty} How do the conditions change the way you do it?",
                f"{action} Here you also {how}.",
                rubric + " " + how[0].upper() + how[1:] + ".",
                how[0].upper() + how[1:] + ".",
                _SPEED_WRONG + _WX_WRONG,
            )


def _extra_food_context(bank: Bank) -> None:
    places = [
        "a hospital tray line",
        "a school cafeteria",
        "a grocery deli",
        "a food truck at a lunch stop",
        "a wedding buffet",
        "a sushi bar",
        "a daycare kitchen",
        "a late-night diner",
    ]
    problems = [
        (
            "A ready-to-eat salad has been at 50°F for an unknown time.",
            "Discard the salad. The place does not get a different cold-holding rule.",
            "41°F or a marked time plan. Unknown time at 50°F is a discard everywhere.",
            "50°F and no clock: discard it.",
        ),
        (
            "An employee with vomiting wants to finish the shift.",
            "Send them home and tell the manager. Vomiting excludes food employees in every kitchen.",
            "The exclusion for vomiting does not depend on the type of restaurant.",
            "Vomiting: off the shift.",
        ),
        (
            "Raw chicken is stored above ready-to-eat food.",
            "Move the chicken below and discard ready-to-eat food that may have been dripped on.",
            "Storage order does not change because the kitchen is small.",
            "Chicken goes to the bottom shelf.",
        ),
        (
            "The only sanitizer bucket has no test strip available.",
            "Do not guess the strength. Get a strip or remake and verify before you call it sanitized.",
            "No strip means you have not verified the concentration.",
            "No strip: do not pretend the bucket is safe.",
        ),
        (
            "A guest reports an allergy and the line cook says to scrape the allergen off.",
            "Remake the order with clean tools. Scraping is cross-contact.",
            "Allergy service is a remake, in a diner or a hospital.",
            "Scrape-off is not allowed. Remake it.",
        ),
    ]
    for place in places:
        for problem, action, rubric, spoken in problems:
            bank.add(
                "workplace",
                f"You are working {place}. {problem} What do you do?",
                action,
                rubric,
                spoken,
                _FOOD_WRONG,
            )


def _finish(bank: Bank) -> None:
    bank.rows.sort(key=lambda row: (row["skill"], row["prompt"]))
    for index, row in enumerate(bank.rows, start=1):
        row["scene_id"] = f"{bank.topic}-{index:04d}"
    prompts = [row["prompt"] for row in bank.rows]
    if len(prompts) != len(set(prompts)):
        raise SystemExit(f"{bank.topic} produced duplicate prompts")
    prefixes = Counter(" ".join(row["prompt"].split()[:8]) for row in bank.rows)
    top, count = prefixes.most_common(1)[0]
    share = count / len(bank.rows)
    answers = {row["acceptable"][0] for row in bank.rows}
    skills = {row["skill"] for row in bank.rows}
    print(
        f"{bank.topic}: {len(bank.rows)} scenes, "
        f"{len(skills)} skills, {len(answers)} distinct answers, "
        f"top prefix {count} ({share:.1%}): {top}"
    )
    if len(bank.rows) <= 1000:
        raise SystemExit(f"{bank.topic} pool is {len(bank.rows)}, need > 1000")
    if share >= 0.08:
        raise SystemExit(f"{bank.topic} prefix too common: {top} ({count})")
    if len(answers) < 80:
        raise SystemExit(f"{bank.topic} has only {len(answers)} distinct answers")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    drivers = _drivers()
    _extra_driver_context(drivers)
    foods = _food()
    _extra_food_context(foods)
    _finish(drivers)
    _finish(foods)
    for bank, name in ((drivers, "drivers_ed.jsonl"), (foods, "food_safety.jsonl")):
        path = OUT / name
        with path.open("w", encoding="utf-8") as handle:
            for row in bank.rows:
                handle.write(json.dumps(row, ensure_ascii=False) + "\n")
        print(f"wrote {path} ({path.stat().st_size} bytes)")


if __name__ == "__main__":
    main()
