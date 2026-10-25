"""California driver education sign bank.

Each sign is one study page: a drawn face plus what the driver must do.
Lessons stay within the studio's 20-slide cap.
"""

from __future__ import annotations

import html
import urllib.parse
from dataclasses import dataclass


@dataclass(frozen=True)
class RoadSign:
    name: str
    legend: str
    shape: str
    face: str
    ink: str
    border: str
    meaning: str
    key: str


@dataclass(frozen=True)
class SignLessonSpec:
    lesson_id: str
    title: str
    description: str
    signs: tuple[RoadSign, ...]


def _s(
    name: str,
    legend: str,
    shape: str,
    face: str,
    ink: str,
    border: str,
    meaning: str,
    key: str,
) -> RoadSign:
    return RoadSign(name, legend, shape, face, ink, border, meaning, key)


_REG = ("rect", "#ffffff", "#111827", "#111827")
_STOP = ("octagon", "#b91c1c", "#ffffff", "#7f1d1d")
_YIELD = ("yield", "#ffffff", "#b91c1c", "#b91c1c")
_WARN = ("diamond", "#facc15", "#111827", "#111827")
# MUTCD 7B.07: school warning signs are yellow, or fluorescent yellow-green (FYG), with a BLACK legend and border.
# FYG is a fluorescent pigment; #c7f000 is the closest screen colour that stays readable.
FYG = "#c7f000"
INK = "#111827"
_SCHOOL = ("pentagon", FYG, INK, INK)  # S1-1 school, S1-5 school crossing: the 5-sided school sign
_SCHOOL_WARN = ("diamond", FYG, INK, INK)  # S3-1 school bus stop ahead: a diamond warning sign
_SCHOOL_SPEED = ("school-speed", "#ffffff", INK, INK)  # S5-1: FYG SCHOOL panel over a white speed-limit panel
_ALLWAY = ("plaque", "#b91c1c", "#ffffff", "#ffffff")  # R1-3P ALL WAY: white legend and border on red, a rectangle
_DNE = ("do-not-enter", "#b91c1c", "#ffffff", "#ffffff")  # R5-1: red disc with a white bar
_WRONG = ("wrong-way", "#b91c1c", "#ffffff", "#ffffff")  # R5-1a: white legend on a red rectangle
_PLAQUE_Y = ("plaque", "#facc15", INK, INK)  # W14-1 DEAD END, W14-2 NO OUTLET: yellow rectangles
_LANE = ("lane", "#ffffff", INK, INK)  # R3-5 lane control: arrows plus ONLY
_GUIDE = ("rect", "#166534", "#ffffff", "#14532d")
_BLUE = ("rect", "#1d4ed8", "#ffffff", "#1e3a8a")
_WORK = ("diamond", "#fb923c", "#111827", "#9a3412")
_RR = ("crossbuck", "#ffffff", "#111827", "#111827")
_BAN = ("prohibit", "#ffffff", "#111827", "#b91c1c")
_PENNANT = ("pennant", "#facc15", "#111827", "#111827")
_SHIELD = ("shield", "#1d4ed8", "#ffffff", "#b91c1c")
_ROUND = ("circle", "#facc15", "#111827", "#111827")
_BROWN = ("rect", "#7c4a2d", "#ffffff", "#5c3317")


def _r(name: str, legend: str, style: tuple[str, str, str, str], meaning: str, key: str) -> RoadSign:
    shape, face, ink, border = style
    return _s(name, legend, shape, face, ink, border, meaning, key)


SIGN_LESSONS: tuple[SignLessonSpec, ...] = (
    SignLessonSpec(
        "ca-dmv-sign-stop-yield",
        "Signs — stop, yield, and wrong way",
        "Stop, yield, do-not-enter, one-way, and access signs.",
        (
            _r("Stop", "STOP", _STOP, "A red octagon means a complete stop behind the limit line or crosswalk. Go only when the way is clear.", "ca-dmv-sign.stop"),
            _r("All Way", "ALL WAY", _ALLWAY, "The ALL WAY plaque under a stop sign means every approach stops. The first vehicle to stop goes first; if two stop together, yield to the driver on your right.", "ca-dmv-sign.all-way"),
            _r("Yield", "YIELD", _YIELD, "A downward triangle means slow down and give the right-of-way. Stop if you cannot merge or cross safely.", "ca-dmv-sign.yield"),
            _r("Yield to pedestrians", "YIELD TO PEDESTRIANS", _YIELD, "Drivers must let people in the crosswalk go first. Stop if they are in or about to enter your half of the road.", "ca-dmv-sign.yield-pedestrians"),
            _r("Do Not Enter", "DO NOT ENTER", _DNE, "A red circle with a white bar means this road is closed to your direction. Do not drive past it.", "ca-dmv-sign.do-not-enter"),
            _r("Wrong Way", "WRONG WAY", _WRONG, "You are facing oncoming traffic. Stop and turn around only when it is safe. Do not continue.", "ca-dmv-sign.wrong-way"),
            _r("One Way right", "ONE WAY", _REG, "Traffic on this street moves only in the direction of the arrow. Do not enter against it.", "ca-dmv-sign.one-way-right"),
            _r("One Way left", "ONE WAY", _REG, "The arrow points left. Enter only if you will travel that direction.", "ca-dmv-sign.one-way-left"),
            _r("Keep Right", "KEEP RIGHT", _REG, "A divider or obstruction is ahead. Pass it on the right side.", "ca-dmv-sign.keep-right"),
            _r("Keep Left", "KEEP LEFT", _REG, "Pass the island or obstruction on the left side.", "ca-dmv-sign.keep-left"),
            _r("Divided highway", "DIVIDED HIGHWAY", _WARN, "The road ahead is split by a median. Stay to the right of the divider.", "ca-dmv-sign.divided-highway"),
            _r("Divided highway ends", "DIVIDED HIGHWAY ENDS", _WARN, "The median ends and opposing traffic is no longer separated. Watch for oncoming vehicles.", "ca-dmv-sign.divided-highway-ends"),
            _r("Two-way traffic", "TWO WAY TRAFFIC", _WARN, "You are leaving a one-way road. Traffic now comes toward you. Stay in your lane.", "ca-dmv-sign.two-way"),
            _r("Road closed", "ROAD CLOSED", _REG, "This road is closed to through traffic. Follow the posted detour. Do not drive around the barricade.", "ca-dmv-sign.road-closed"),
            _r("No outlet", "NO OUTLET", _PLAQUE_Y, "The street does not connect through. You will have to turn around to leave.", "ca-dmv-sign.no-outlet"),
            _r("Dead end", "DEAD END", _PLAQUE_Y, "The road ends ahead. Slow down and plan your turnaround before the end.", "ca-dmv-sign.dead-end"),
            _r("Stop here for pedestrians", "STOP HERE FOR PEDESTRIANS", _REG, "Stop at this line, not in the crosswalk, when people are crossing.", "ca-dmv-sign.stop-here-ped"),
            _r("Stop here on red", "STOP HERE ON RED", _REG, "When the signal is red, stop at this line so you do not block the intersection or sensors.", "ca-dmv-sign.stop-here-red"),
            _r("Emergency stop", "EMERGENCY STOPPING ONLY", _REG, "Use this shoulder or area only for a real emergency, not for parking, calls, or rest.", "ca-dmv-sign.emergency-stop"),
            _r("Authorized vehicles only", "AUTHORIZED VEHICLES ONLY", _REG, "The lane or driveway is closed to the public. Do not enter unless you are an authorized vehicle.", "ca-dmv-sign.authorized-only"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-turns",
        "Signs — turns and lane use",
        "Turn prohibitions, turn-only lanes, and red-light turn signs.",
        (
            _r("No left turn", "NO LEFT TURN", _BAN, "Do not turn left at this intersection. Continue straight or follow the allowed movement.", "ca-dmv-sign.no-left"),
            _r("No right turn", "NO RIGHT TURN", _BAN, "Do not turn right here. Choose another legal route.", "ca-dmv-sign.no-right"),
            _r("No U-turn", "NO U-TURN", _BAN, "Do not make a U-turn at this location, even if the path looks wide enough.", "ca-dmv-sign.no-u-turn"),
            _r("No turns", "NO TURNS", _BAN, "Neither left nor right turns are allowed. Stay in the through lane.", "ca-dmv-sign.no-turns"),
            _r("No left turn on red", "NO LEFT TURN ON RED", _BAN, "A left turn on a red light is forbidden here, including from a one-way street.", "ca-dmv-sign.no-left-on-red"),
            _r("No right turn on red", "NO RIGHT TURN ON RED", _BAN, "California's usual right-on-red rule does not apply here. Wait for a green light.", "ca-dmv-sign.no-right-on-red"),
            _r("Left turn only", "LEFT TURN ONLY", _LANE, "This lane may only turn left. Get into it before the intersection if you need that turn.", "ca-dmv-sign.left-only"),
            _r("Right turn only", "RIGHT TURN ONLY", _LANE, "This lane must turn right. Do not go straight from it.", "ca-dmv-sign.right-only"),
            _r("Straight only", "ONLY", _LANE, "This lane must continue straight. Do not turn from it.", "ca-dmv-sign.straight-only"),
            _r("Left or straight", "ONLY", _LANE, "From this lane you may turn left or go straight. You may not turn right.", "ca-dmv-sign.left-or-straight"),
            _r("Right or straight", "ONLY", _LANE, "From this lane you may turn right or go straight. You may not turn left.", "ca-dmv-sign.right-or-straight"),
            _r("Left or right", "ONLY", _LANE, "This lane must turn. You may turn left or right, but you may not go straight.", "ca-dmv-sign.left-or-right"),
            _r("Center left-turn lane", "CENTER LANE LEFT TURN ONLY", _REG, "The shared center lane is only for left turns from either direction. Do not use it to pass or to travel through.", "ca-dmv-sign.center-left"),
            _r("U-turn yield", "U-TURN YIELD TO RIGHT TURN", _REG, "You may U-turn, but you must yield to vehicles turning right on the green arrow or light.", "ca-dmv-sign.u-turn-yield"),
            _r("Left turn yield on green", "LEFT TURN YIELD ON GREEN", _REG, "A green ball lets you turn left only after you yield to oncoming traffic and pedestrians.", "ca-dmv-sign.left-yield-green"),
            _r("Begin right turn lane", "BEGIN RIGHT TURN LANE", _WARN, "A right-turn lane is opening. Move into it only if you are turning right.", "ca-dmv-sign.begin-right-lane"),
            _r("Must turn right", "MUST TURN RIGHT", _LANE, "Every vehicle in this lane has to turn right at the upcoming intersection.", "ca-dmv-sign.must-turn-right"),
            _r("Two-way left turn", "TWO WAY LEFT TURN", _REG, "The center lane is a two-way left-turn lane. Enter it close to your turn and leave it promptly.", "ca-dmv-sign.two-way-left"),
            _r("No straight through", "NO STRAIGHT THROUGH", _BAN, "You cannot continue ahead. Turn in an allowed direction.", "ca-dmv-sign.no-straight"),
            _r("Turn left with care", "LEFT TURN MUST YIELD", _REG, "The turn is allowed, but oncoming cars and people in the crosswalk still have the right-of-way.", "ca-dmv-sign.left-must-yield"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-speed-hov",
        "Signs — speed, parking, and HOV",
        "Speed limits, parking bans, and carpool-lane signs.",
        (
            _r("Speed limit 25", "SPEED LIMIT 25", _REG, "The maximum legal speed here is 25 miles per hour when conditions are good. Go slower in rain, fog, or heavy traffic.", "ca-dmv-sign.speed-25"),
            _r("Speed limit 35", "SPEED LIMIT 35", _REG, "Do not exceed 35 mph. The basic speed law still requires a safe speed for the conditions.", "ca-dmv-sign.speed-35"),
            _r("Speed limit 45", "SPEED LIMIT 45", _REG, "The posted maximum is 45 mph. Match the limit only if the road, weather, and traffic allow it.", "ca-dmv-sign.speed-45"),
            _r("Speed limit 55", "SPEED LIMIT 55", _REG, "The posted maximum is 55 mph. Many undivided highways and some freeways use this limit.", "ca-dmv-sign.speed-55"),
            _r("Speed limit 65", "SPEED LIMIT 65", _REG, "The posted maximum is 65 mph. Keep a longer following gap at freeway speed.", "ca-dmv-sign.speed-65"),
            _r("Speed limit 70", "SPEED LIMIT 70", _REG, "Where posted, 70 mph is the maximum. Trucks and vehicles towing may have a lower limit on the same road.", "ca-dmv-sign.speed-70"),
            _r("Reduced speed ahead", "REDUCED SPEED AHEAD", _WARN, "The limit drops soon. Start slowing before you reach the lower sign.", "ca-dmv-sign.reduced-speed"),
            _r("Minimum speed", "MINIMUM SPEED 45", _REG, "If you cannot keep at least this speed in normal conditions, use another road. You may go slower when traffic or weather requires it.", "ca-dmv-sign.minimum-speed"),
            _r("School speed limit", "SCHOOL SPEED LIMIT 25 WHEN FLASHING", _SCHOOL_SPEED, "When the beacons flash, the school-zone limit is in force. Watch for children even if the lights are off.", "ca-dmv-sign.school-speed"),
            _r("End school zone", "END SCHOOL ZONE", _REG, "The special school limit ends. Return to the next posted speed and keep watching for children nearby.", "ca-dmv-sign.end-school-zone"),
            _r("No parking", "NO PARKING", _BAN, "You may stop briefly to load or unload where allowed, but you may not leave the vehicle parked.", "ca-dmv-sign.no-parking"),
            _r("No stopping", "NO STOPPING", _BAN, "Do not stop here at all, except to avoid a crash or to obey a signal or officer.", "ca-dmv-sign.no-stopping"),
            _r("No standing", "NO STANDING", _BAN, "You may not wait at the curb with or without a driver, except a brief passenger pickup where local rules allow.", "ca-dmv-sign.no-standing"),
            _r("No parking any time", "NO PARKING ANY TIME", _BAN, "The ban applies day and night. Do not assume evenings or weekends are exempt unless a sign says so.", "ca-dmv-sign.no-parking-any-time"),
            _r("Tow-away zone", "TOW-AWAY NO STOPPING", _BAN, "A vehicle left here can be towed. Read the hours. Stopping even briefly can be illegal.", "ca-dmv-sign.tow-away"),
            _r("HOV 2 or more", "HOV 2+ ONLY", _REG, "This lane is for high-occupancy vehicles with at least the posted number of people. Solo drivers may not use it unless a sign allows a clean-air decal.", "ca-dmv-sign.hov-2"),
            _r("HOV 3 or more", "HOV 3+ ONLY", _REG, "Three or more people are required during the posted hours. Count every occupant, including children.", "ca-dmv-sign.hov-3"),
            _r("HOV lane ahead", "HOV LANE AHEAD", _WARN, "A carpool lane begins soon. Enter only at a broken line if you qualify.", "ca-dmv-sign.hov-ahead"),
            _r("HOV lane ends", "HOV LANE ENDS", _REG, "The restriction ends ahead. Merge smoothly back with general traffic.", "ca-dmv-sign.hov-ends"),
            _r("Do not cross double white", "DO NOT CROSS DOUBLE WHITE LINE", _REG, "A double solid white line beside an HOV lane means do not change lanes across it. Wait for a broken white opening.", "ca-dmv-sign.double-white"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-merge-curves",
        "Signs — merging, curves, and hills",
        "Merge, lane-end, curve, and hill warning signs.",
        (
            _r("Merge", "MERGE", _WARN, "Traffic from another road is joining yours. Adjust speed and let a gap open. Do not race the merging driver.", "ca-dmv-sign.merge"),
            _r("Merge left", "MERGE LEFT", _WARN, "Your lane is joining traffic on the left. Signal, check the mirror and blind spot, and move left when clear.", "ca-dmv-sign.merge-left"),
            _r("Merge right", "MERGE RIGHT", _WARN, "Your lane joins on the right. Signal early and match the speed of the lane you are entering.", "ca-dmv-sign.merge-right"),
            _r("Added lane", "ADDED LANE", _WARN, "A new lane opens. You do not have to merge. Stay in your lane and let the other stream enter beside you.", "ca-dmv-sign.added-lane"),
            _r("Lane ends", "LANE ENDS", _WARN, "Your lane is about to disappear. Merge in the direction of the arrow while you still have room.", "ca-dmv-sign.lane-ends"),
            _r("Right lane ends", "RIGHT LANE ENDS", _WARN, "The right lane closes. If you are in it, move left at the broken line. If you are in the through lane, hold your speed and leave a gap.", "ca-dmv-sign.right-lane-ends"),
            _r("Left lane ends", "LEFT LANE ENDS", _WARN, "The left lane closes. Merge right early instead of squeezing in at the last moment.", "ca-dmv-sign.left-lane-ends"),
            _r("Curve right", "CURVE RIGHT", _WARN, "The road bends right. Slow before the curve, then steer smoothly. Do not brake hard in the middle of the bend.", "ca-dmv-sign.curve-right"),
            _r("Curve left", "CURVE LEFT", _WARN, "The road bends left. Reduce speed before the curve and stay in your lane.", "ca-dmv-sign.curve-left"),
            _r("Sharp right turn", "SHARP RIGHT TURN", _WARN, "A tight right turn is ahead. Slow more than you would for a gentle curve.", "ca-dmv-sign.sharp-right"),
            _r("Sharp left turn", "SHARP LEFT TURN", _WARN, "A tight left turn is ahead. Slow early so you do not cross the center line.", "ca-dmv-sign.sharp-left"),
            _r("Winding road", "WINDING ROAD", _WARN, "Several curves follow one another. Keep a lower speed until the road straightens.", "ca-dmv-sign.winding"),
            _r("Reverse curve", "REVERSE CURVE", _WARN, "The road curves one way, then the other. Stay centered and do not cut either bend.", "ca-dmv-sign.reverse-curve"),
            _r("Slippery when wet", "SLIPPERY WHEN WET", _WARN, "The pavement loses grip in rain. Slow down, avoid sudden steering, and lengthen your following gap.", "ca-dmv-sign.slippery"),
            _r("Hill", "HILL", _WARN, "A steep grade is ahead. Downshift if needed and watch for slow trucks.", "ca-dmv-sign.hill"),
            _r("Steep downgrade", "STEEP DOWNGRADE", _WARN, "Use a lower gear on a long downhill so the brakes do not fade. Do not ride the brake pedal.", "ca-dmv-sign.downgrade"),
            _r("Narrow bridge", "NARROW BRIDGE", _WARN, "The bridge is narrower than the road. Slow down and let wide vehicles through one at a time if needed.", "ca-dmv-sign.narrow-bridge"),
            _r("Road narrows", "ROAD NARROWS", _WARN, "Both edges come in. Move toward the center of your lane and watch for oncoming traffic.", "ca-dmv-sign.road-narrows"),
            _r("No passing zone", "NO PASSING ZONE", _PENNANT, "A yellow pennant on the left side of the road means do not pass. The zone often starts before a hill or curve.", "ca-dmv-sign.no-passing-pennant"),
            _r("Low shoulder", "LOW SHOULDER", _WARN, "The shoulder is lower than the pavement. Avoid drifting off the edge, and return gently if you do.", "ca-dmv-sign.low-shoulder"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-crossings",
        "Signs — intersections, schools, and people",
        "Intersection warnings, pedestrians, bikes, and school signs.",
        (
            _r("Cross road", "CROSS ROAD", _WARN, "A road crosses yours ahead. Look left and right even if you have the right-of-way.", "ca-dmv-sign.cross-road"),
            _r("Side road", "SIDE ROAD", _WARN, "Traffic may enter from the side street shown. Cover the brake and watch that approach.", "ca-dmv-sign.side-road"),
            _r("T intersection", "T INTERSECTION", _WARN, "Your road ends at a crossroad. You must turn left or right. Slow down before the junction.", "ca-dmv-sign.t-intersection"),
            _r("Y intersection", "Y INTERSECTION", _WARN, "The road splits into two branches. Choose your lane early.", "ca-dmv-sign.y-intersection"),
            _r("Roundabout ahead", "ROUNDABOUT AHEAD", _WARN, "A circular intersection is ahead. Slow, yield to traffic already in the circle, and enter when clear.", "ca-dmv-sign.roundabout-ahead"),
            _r("Stop ahead", "STOP AHEAD", _WARN, "A stop sign is coming. Begin braking now so you can stop smoothly at the line.", "ca-dmv-sign.stop-ahead"),
            _r("Yield ahead", "YIELD AHEAD", _WARN, "A yield sign is coming. Be ready to slow or stop for cross traffic.", "ca-dmv-sign.yield-ahead"),
            _r("Signal ahead", "SIGNAL AHEAD", _WARN, "A traffic signal is ahead, often over a hill or around a curve. Do not accelerate toward a stale green.", "ca-dmv-sign.signal-ahead"),
            _r("Pedestrian crossing", "PED XING", _WARN, "People may be crossing. Yield to anyone in the crosswalk. Stop if they are in your path.", "ca-dmv-sign.ped-xing"),
            _r("Bicycle crossing", "BIKE XING", _WARN, "Bikes may cross or ride through here. Look before turning across a bike lane.", "ca-dmv-sign.bike-xing"),
            _r("School crossing", "SCHOOL CROSSING", _SCHOOL, "A marked school crosswalk is ahead. Stop for children and crossing guards. The pentagon shape means school.", "ca-dmv-sign.school-crossing"),
            _r("School", "SCHOOL", _SCHOOL, "You are entering a school area. Expect children on foot and on bikes at odd hours, not only at the bell.", "ca-dmv-sign.school"),
            _r("School bus stop ahead", "SCHOOL BUS STOP AHEAD", _SCHOOL_WARN, "A yellow-green diamond warns that a school bus may be stopped around the curve or over the hill. Be ready to stop for flashing red lights.", "ca-dmv-sign.school-bus-ahead"),
            _r("Deer crossing", "DEER CROSSING", _WARN, "Animals cross this road. Scan the shoulders at dawn and dusk and slow if you see movement.", "ca-dmv-sign.deer"),
            _r("Cattle crossing", "CATTLE CROSSING", _WARN, "Livestock may be on the roadway. Stop if a herd or a rider is crossing. Do not honk at animals.", "ca-dmv-sign.cattle"),
            _r("Farm machinery", "FARM MACHINERY", _WARN, "Slow tractors and equipment may enter the road. Pass only when you can see far enough ahead.", "ca-dmv-sign.farm"),
            _r("Truck crossing", "TRUCK CROSSING", _WARN, "Heavy trucks enter or cross here. Give them time to accelerate and do not pull into a gap they need.", "ca-dmv-sign.truck-crossing"),
            _r("Wheelchair crossing", "WHEELCHAIR", _WARN, "People using wheelchairs or mobility devices may cross. Yield and do not block the ramp.", "ca-dmv-sign.wheelchair"),
            _r("Playground", "PLAYGROUND", _WARN, "Children may run toward the street. Slow down and expect sudden movement.", "ca-dmv-sign.playground"),
            _r("Fire station", "FIRE STATION", _WARN, "Emergency vehicles may pull out. If lights flash or a siren sounds, yield and do not block the driveway.", "ca-dmv-sign.fire-station"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-railroad",
        "Signs — railroad crossings",
        "Advance warnings, crossbucks, gates, and track rules.",
        (
            _r("Railroad advance", "RR", _ROUND, "A yellow circular advance sign means tracks are ahead. Slow, look both ways, and listen. Be ready to stop.", "ca-dmv-sign.rr-advance"),
            _r("Railroad crossbuck", "RAILROAD CROSSING", _RR, "The white X-shaped crossbuck marks the crossing itself. Treat it as a yield to trains. Never try to beat a train.", "ca-dmv-sign.crossbuck"),
            _r("Two tracks", "2 TRACKS", _REG, "More than one track crosses the road. A train on the near track can hide a second train. Wait until you can see both ways.", "ca-dmv-sign.two-tracks"),
            _r("Three tracks", "3 TRACKS", _REG, "Three tracks cross here. Count them. Do not start across until every track is clear.", "ca-dmv-sign.three-tracks"),
            _r("Exempt crossing", "EXEMPT", _REG, "An EXEMPT plaque means the crossing is not used by regular trains and some special vehicles need not stop. Other drivers still look and listen.", "ca-dmv-sign.exempt"),
            _r("Low ground clearance", "LOW GROUND CLEARANCE", _WARN, "A low car, trailer, or truck can get stuck on a raised crossing. Do not enter if your vehicle might hang up.", "ca-dmv-sign.low-ground"),
            _r("Skewed crossing", "SKEWED CROSSING", _WARN, "The tracks cross the road at an angle. Look farther down the rails because a train is harder to see.", "ca-dmv-sign.skewed"),
            _r("Do not stop on tracks", "DO NOT STOP ON TRACKS", _REG, "Never wait on the rails in a traffic queue. Stop before the tracks until there is room for your whole vehicle on the other side.", "ca-dmv-sign.do-not-stop-tracks"),
            _r("Stop at railroad", "STOP", _STOP, "When a stop sign is posted at a crossing, stop, look, and listen, then go only if no train is coming.", "ca-dmv-sign.rr-stop"),
            _r("Number of tracks plaque", "4 TRACKS", _REG, "The small plaque under the crossbuck tells how many tracks you must clear. Do not assume the first train is the only one.", "ca-dmv-sign.four-tracks"),
            _r("Parallel railroad", "RAILROAD PARALLEL", _WARN, "Tracks run beside the road and then cross a side street. Watch for a train as you turn.", "ca-dmv-sign.rr-parallel"),
            _r("Light rail crossing", "LIGHT RAIL CROSSING", _WARN, "Trains or trolleys may run in or beside the street. Obey the signals and never drive on the tracks to pass.", "ca-dmv-sign.light-rail"),
            _r("No train horn", "NO TRAIN HORN", _WARN, "Trains do not routinely sound the horn at this quiet-zone crossing. Do not rely on hearing a whistle.", "ca-dmv-sign.no-horn"),
            _r("High speed trains", "TRAINS MAY EXCEED 80 MPH", _REG, "Trains here are faster than they look. If lights flash or gates move, the train is closer than you think.", "ca-dmv-sign.high-speed-train"),
            _r("Gate crossing", "GATES DOWN MEANS STOP", _REG, "When lights flash or gates lower, stop at least 15 feet from the nearest rail. Do not drive around a lowered gate.", "ca-dmv-sign.gates"),
            _r("Emergency notification", "REPORT EMERGENCY 1-800", _BLUE, "The blue sign shows who to call if a vehicle is stuck or a signal is broken. Note the crossing number, then get clear of the tracks.", "ca-dmv-sign.rr-emergency"),
            _r("Storage space", "STORAGE SPACE", _WARN, "There may not be room to clear the tracks if traffic is stopped beyond them. Wait until the far side has space for your vehicle.", "ca-dmv-sign.storage-space"),
            _r("Pavement RXR", "RXR", _WARN, "White RXR letters on the pavement repeat the railroad warning. They are not the place to stop. Stop at the line or at least 15 feet from the rail.", "ca-dmv-sign.rxr"),
            _r("Rough crossing", "ROUGH CROSSING", _WARN, "The crossing surface is uneven. Slow down so you do not lose control or spill a load.", "ca-dmv-sign.rough-crossing"),
            _r("Stop line at tracks", "STOP LINE", _REG, "The wide white line before the tracks is where you stop for a signal, flagger, or train. Do not creep past it.", "ca-dmv-sign.rr-stop-line"),
        ),
    ),
    SignLessonSpec(
        "ca-dmv-sign-work-guide",
        "Signs — work zones, guide, and services",
        "Construction signs plus route, exit, and service signs.",
        (
            _r("Road work ahead", "ROAD WORK AHEAD", _WORK, "A work zone is coming. Slow down, put the phone away, and watch for workers and sudden stops.", "ca-dmv-sign.road-work"),
            _r("Flagger ahead", "FLAGGER AHEAD", _WORK, "A person with a sign or paddle will direct you. Obey the flagger even if a signal says something else.", "ca-dmv-sign.flagger"),
            _r("Detour", "DETOUR", _WORK, "The usual road is closed. Follow the detour arrows. Do not follow a navigation app through the closure.", "ca-dmv-sign.detour"),
            _r("Lane closed ahead", "LANE CLOSED AHEAD", _WORK, "A lane ends in the work zone. Merge at the posted point. Do not jump the queue at the cones.", "ca-dmv-sign.lane-closed"),
            _r("Right lane closed", "RIGHT LANE CLOSED", _WORK, "The right lane is closed. Move left when the signs and cones tell you to.", "ca-dmv-sign.right-closed"),
            _r("Be prepared to stop", "BE PREPARED TO STOP", _WORK, "Traffic in the work zone may stop with little warning. Close the gap to the car ahead only as much as you can still stop.", "ca-dmv-sign.prepare-stop"),
            _r("End road work", "END ROAD WORK", _WORK, "The work zone is over. Do not speed up until you have passed the last cone and the workers.", "ca-dmv-sign.end-road-work"),
            _r("Fines double", "FINES DOUBLE IN WORK ZONES", _WORK, "Speeding and other violations can carry a higher fine when workers are present. The sign is a warning, not a suggestion.", "ca-dmv-sign.fines-double"),
            _r("Exit only", "EXIT ONLY", _GUIDE, "This lane leaves the freeway. If you do not want the exit, change lanes before the solid line.", "ca-dmv-sign.exit-only"),
            _r("Exit 25 mph", "EXIT 25 MPH", _WARN, "The ramp speed is much lower than the freeway. Brake before the curve, not in it.", "ca-dmv-sign.exit-speed"),
            _r("Interstate route", "INTERSTATE", _SHIELD, "The red, white, and blue shield marks an Interstate highway. Even numbers run east-west. Odd numbers run north-south.", "ca-dmv-sign.interstate"),
            _r("Hospital", "HOSPITAL", _BLUE, "A blue sign with a white H points to emergency medical care. It is a service sign, not a command.", "ca-dmv-sign.hospital"),
            _r("Gas", "GAS", _BLUE, "Blue service signs point to fuel. They do not change the speed limit or the lane you must use.", "ca-dmv-sign.gas"),
            _r("Food", "FOOD", _BLUE, "Blue signs mark food services at the exit. Read the distance so you do not leave the freeway too early.", "ca-dmv-sign.food"),
            _r("Lodging", "LODGING", _BLUE, "Blue signs mark hotels or lodging. Follow the exit, then the trailblazer signs on the cross street.", "ca-dmv-sign.lodging"),
            _r("Rest area", "REST AREA", _BLUE, "A rest area is ahead. Use it if you are drowsy. Drowsiness is a reason to stop, not to push on.", "ca-dmv-sign.rest-area"),
            _r("Airport", "AIRPORT", _GUIDE, "The sign directs you toward an airport. Follow the arrows rather than guessing at the next split.", "ca-dmv-sign.airport"),
            _r("Bike lane", "BIKE LANE", _REG, "The lane marked with a bike symbol is for bicycles. Do not drive or stop in it except when a sign or marking says you may turn across it.", "ca-dmv-sign.bike-lane"),
            _r("Bike route", "BIKE ROUTE", _GUIDE, "The street is a designated bike route. Expect riders and give them the full lane when it is narrow.", "ca-dmv-sign.bike-route"),
            _r("Park and recreation", "PARK", _BROWN, "A brown sign marks a park or recreation area. Brown is guidance, not a regulatory order.", "ca-dmv-sign.park"),
        ),
    ),
)


def iter_signs() -> tuple[RoadSign, ...]:
    return tuple(sign for lesson in SIGN_LESSONS for sign in lesson.signs)


def sign_count() -> int:
    return len(iter_signs())


_BY_NAME = {sign.name: sign for sign in iter_signs()}
if len(_BY_NAME) != sign_count():
    raise RuntimeError("traffic sign names must be unique")


def sign_for_title(title: str) -> RoadSign | None:
    return _BY_NAME.get(title)


import itertools
import math

# Advance widths (em) of Arial Bold capitals, digits and punctuation. Close enough to size a legend so it fits its shape.
_ADV = {" ": .28, "I": .28, "J": .56, "L": .61, "T": .61, "F": .61, "E": .67, "Z": .61, "S": .67, "Y": .67, "V": .67,
        "X": .67, "P": .67, "B": .72, "R": .72, "K": .72, "W": .94, "M": .83, "-": .33, ".": .28, ",": .28, "/": .28,
        "+": .58, "1": .56, "2": .56, "3": .56, "4": .56, "5": .56, "6": .56, "7": .56, "8": .56, "9": .56, "0": .56}


def _text_width(text: str, size: float) -> float:
    return sum(_ADV.get(ch, .72) for ch in text) * size * 1.04


def _layouts(legend: str):
    words = legend.split()
    for n_lines in (1, 2, 3):
        if n_lines > len(words):
            break
        for cuts in itertools.combinations(range(1, len(words)), n_lines - 1):
            bounds = (0, *cuts, len(words))
            yield [" ".join(words[a:b]) for a, b in zip(bounds, bounds[1:])]


def _lines(legend: str) -> list[str]:
    """Kept for callers that only need a sensible split; the real fit is _fit_legend."""
    return _fit_legend(legend, 210, 120, 34)[0]


def _fit_legend(legend: str, max_w: float, max_h: float, max_size: float, min_size: float = 10, gap: float = .16,
                width_at=None):
    """Pick the line split and font size that keep the whole legend inside max_w x max_h. width_at(dy) (optional) is the
    usable width of the sign at distance dy from the text block's centre, for shapes that narrow (a diamond's tips).
    Never returns a size that overflows unless even min_size does not fit: then textLength squeezes the glyphs."""
    best = None
    for lines in _layouts(legend):
        size = max_size
        while True:
            block = size * (len(lines) + gap * (len(lines) - 1))
            ok = block <= max_h
            for i, line in enumerate(lines):
                top = -block / 2 + i * size * (1 + gap)
                limit = max_w if width_at is None else min(max_w, width_at(max(abs(top), abs(top + size))))
                ok = ok and _text_width(line, size) <= limit
            if ok or size <= min_size:
                break
            size -= .5
        score = (ok, size, -len(lines))
        if best is None or score > best[0]:
            best = (score, lines, size)
    return best[1], best[2]


def _legend_text(legend: str, cx: float, cy: float, max_w: float, max_h: float, ink: str, max_size: float = 36,
                 weight: int = 700, lines: list[str] | None = None, size: float | None = None, width_at=None) -> str:
    if lines is None:
        lines, size = _fit_legend(legend, max_w, max_h, max_size, width_at=width_at)
    gap = .16
    block = size * (len(lines) + gap * (len(lines) - 1))
    out = []
    for i, line in enumerate(lines):
        top = -block / 2 + i * size * (1 + gap)  # line's top edge relative to the block centre
        limit = max_w if width_at is None else min(max_w, width_at(max(abs(top), abs(top + size))))
        base = cy + top + size * 0.82
        width = min(_text_width(line, size), limit)
        out.append(
            f'<text x="{cx:.1f}" y="{base:.1f}" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" '
            f'font-weight="{weight}" font-size="{size:.1f}" fill="{ink}" textLength="{width:.1f}" '
            f'lengthAdjust="spacingAndGlyphs">{html.escape(line)}</text>'
        )
    return "".join(out)


def _regular_polygon(cx: float, cy: float, flat_radius: float, sides: int, rotation: float) -> str:
    r = flat_radius / math.cos(math.pi / sides)
    pts = [(cx + r * math.cos(rotation + 2 * math.pi * k / sides), cy + r * math.sin(rotation + 2 * math.pi * k / sides)) for k in range(sides)]
    return " ".join(f"{x:.1f},{y:.1f}" for x, y in pts)


_ARROWS = {
    "Straight only": ("up",), "Left or straight": ("up", "left"), "Right or straight": ("up", "right"),
    "Left or right": ("left", "right"), "Left turn only": ("left-turn",), "Right turn only": ("right-turn",),
    "Must turn right": ("right-turn",),
}


def _arrow_markup(kinds: tuple[str, ...], ink: str) -> str:
    st = f'stroke="{ink}" stroke-width="14" stroke-linecap="round" stroke-linejoin="round" fill="none"'
    head = f'fill="{ink}"'
    out = []
    if "up" in kinds:
        out.append(f'<line x1="400" y1="205" x2="400" y2="135" {st}/><polygon points="400,100 372,140 428,140" {head}/>')
        if "left" in kinds:
            out.append(f'<path d="M400 172 H352" {st}/><polygon points="322,172 356,150 356,194" {head}/>')
        if "right" in kinds:
            out.append(f'<path d="M400 172 H448" {st}/><polygon points="478,172 444,150 444,194" {head}/>')
    elif "left" in kinds and "right" in kinds:
        out.append(f'<path d="M400 205 V172 M400 172 H352" {st}/><polygon points="322,172 356,150 356,194" {head}/>')
        out.append(f'<path d="M400 172 H448" {st}/><polygon points="478,172 444,150 444,194" {head}/>')
    elif "left-turn" in kinds:
        out.append(f'<path d="M420 205 V160 H370" {st}/><polygon points="338,160 372,138 372,182" {head}/>')
    elif "right-turn" in kinds:
        out.append(f'<path d="M380 205 V160 H430" {st}/><polygon points="462,160 428,138 428,182" {head}/>')
    return "".join(out)


def _shape_markup(sign: RoadSign) -> str:
    """Draw one sign face centred on (400, 175). Every legend is measured and fitted into its shape's safe box."""
    face, border, ink = html.escape(sign.face), html.escape(sign.border), html.escape(sign.ink)
    common = f'fill="{face}" stroke="{border}" stroke-width="10" stroke-linejoin="round"'
    shape = sign.shape
    if shape == "octagon":
        body = f'<polygon points="{_regular_polygon(400, 175, 100, 8, math.pi / 8)}" {common}/>'
        return body + _legend_text(sign.legend, 400, 175, 150, 80, ink, max_size=44, weight=800)
    if shape == "yield":  # points DOWN: apex at the bottom
        body = f'<polygon points="280,88 520,88 400,296" fill="#ffffff" stroke="{border}" stroke-width="12" stroke-linejoin="round"/>'
        return body + _legend_text(sign.legend, 400, 140, 130, 56, ink, max_size=30, weight=800)
    if shape == "diamond":
        body = f'<polygon points="400,57 518,175 400,293 282,175" {common}/>'
        return body + _legend_text(sign.legend, 400, 175, 160, 96, ink, max_size=32, width_at=lambda dy: 2 * 118 * (1 - dy / 118) - 16)
    if shape == "pentagon":
        body = f'<polygon points="400,62 520,148 474,288 326,288 280,148" {common}/>'
        return body + _legend_text(sign.legend, 400, 196, 138, 80, ink, max_size=32)
    if shape == "school-speed":  # S5-1: FYG SCHOOL panel above a white SPEED LIMIT panel
        body = (
            f'<rect x="312" y="45" width="176" height="260" rx="10" fill="#ffffff" stroke="{border}" stroke-width="8"/>'
            f'<rect x="316" y="49" width="168" height="62" rx="6" fill="{FYG}" stroke="{border}" stroke-width="3"/>'
        )
        body += _legend_text("SCHOOL", 400, 80, 150, 44, ink, max_size=40, weight=800)
        body += _legend_text("SPEED LIMIT", 400, 140, 150, 30, ink, max_size=30, weight=800)
        number = next((w for w in sign.legend.split() if w.isdigit()), "25")
        body += _legend_text(number, 400, 200, 110, 70, ink, max_size=70, weight=800)
        tail = sign.legend.split(number, 1)[-1].strip() or "WHEN FLASHING"
        return body + _legend_text(tail, 400, 266, 150, 40, ink, max_size=26, weight=800)
    if shape == "prohibit":
        body = (
            f'<rect x="290" y="62" width="220" height="238" rx="14" {common}/>'
            f'<circle cx="400" cy="147" r="58" fill="none" stroke="#b91c1c" stroke-width="12"/>'
            f'<line x1="359" y1="106" x2="441" y2="188" stroke="#b91c1c" stroke-width="12"/>'
        )
        return body + _legend_text(sign.legend, 400, 250, 190, 62, ink, max_size=26)
    if shape == "do-not-enter":
        body = (
            f'<rect x="290" y="62" width="220" height="228" rx="12" fill="#ffffff" stroke="{INK}" stroke-width="6"/>'
            '<circle cx="400" cy="176" r="96" fill="#b91c1c"/>'
            '<rect x="322" y="152" width="156" height="48" fill="#ffffff"/>'
        )
        return body  # R5-1 is a red disc with a white bar; the sign's name is captioned by the slide
    if shape == "wrong-way":
        body = f'<rect x="270" y="120" width="260" height="110" rx="12" {common}/>'
        return body + _legend_text(sign.legend, 400, 175, 220, 78, ink, max_size=38, weight=800)
    if shape == "plaque":
        body = f'<rect x="270" y="130" width="260" height="90" rx="10" {common}/>'
        return body + _legend_text(sign.legend, 400, 175, 230, 64, ink, max_size=40, weight=800)
    if shape == "lane":
        body = f'<rect x="290" y="64" width="220" height="222" rx="10" {common}/>' + _arrow_markup(_ARROWS.get(sign.name, ("up",)), ink)
        return body + _legend_text(sign.legend, 400, 250, 190, 52, ink, max_size=34, weight=800)
    if shape == "crossbuck":
        bars = (
            f'<g transform="rotate(35 400 175)"><rect x="262" y="152" width="276" height="46" rx="4" {common}/></g>'
            f'<g transform="rotate(-35 400 175)"><rect x="262" y="152" width="276" height="46" rx="4" {common}/></g>'
        )
        words = sign.legend.split()
        if len(words) == 2:  # RAILROAD and CROSSING each sit on the outer half of their own bar, clear of the crossing
            for word, ang, offset in ((words[0], 35, 70), (words[1], -35, -70)):
                size = min(22.0, 112 / _text_width(word, 1))
                bars += f'<g transform="rotate({ang} 400 175)">{_legend_text(word, 400 + offset, 175, 112, 34, ink, lines=[word], size=size, weight=800)}</g>'
            return bars
        return bars + _legend_text(sign.legend, 400, 175, 120, 60, ink, max_size=22)
    if shape == "pennant":
        body = f'<polygon points="290,100 530,175 290,250" {common}/>'
        return body + _legend_text(sign.legend, 375, 175, 120, 70, ink, max_size=24)
    if shape == "shield":
        path = "M326 78 h148 v96 c0 52 -74 96 -74 96 s-74 -44 -74 -96 z"
        body = (
            f'<defs><clipPath id="tsh"><path d="{path}"/></clipPath></defs>'
            f'<path d="{path}" {common}/>'
            f'<rect x="326" y="78" width="148" height="34" fill="#b91c1c" clip-path="url(#tsh)"/>'
            f'<path d="{path}" fill="none" stroke="#ffffff" stroke-width="5" stroke-linejoin="round"/>'
        )
        return body + _legend_text(sign.legend, 400, 168, 112, 60, ink, max_size=24)
    if shape == "circle":
        body = f'<circle cx="400" cy="175" r="102" {common}/>'
        return body + _legend_text(sign.legend, 400, 175, 140, 80, ink, max_size=64, weight=800)
    body = f'<rect x="272" y="92" width="256" height="166" rx="10" {common}/>'
    return body + _legend_text(sign.legend, 400, 175, 226, 126, ink, max_size=38)


def sign_svg(sign: RoadSign, *, animated: bool) -> str:
    label = html.escape(sign.name)
    motion = (
        '<animateTransform attributeName="transform" type="translate" '
        'values="0 0;0 -14;0 0" dur="2.6s" repeatCount="indefinite"/>'
        if animated
        else ""
    )
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="800" height="450" viewBox="0 0 800 450" '
        f'role="img" aria-label="{label}">'
        '<rect width="800" height="450" fill="#d7e4f2"/>'
        '<rect y="318" width="800" height="132" fill="#4b5563"/>'
        '<rect y="372" width="800" height="10" fill="#facc15"/>'
        '<rect x="388" y="286" width="24" height="70" fill="#6b7280"/>'
        f'<g>{motion}{_shape_markup(sign)}</g>'
        f'<text x="400" y="430" text-anchor="middle" font-family="Georgia, serif" font-size="28" fill="#f8fafc">{label}</text>'
        "</svg>"
    )


def _data_url(svg: str) -> str:
    return "data:image/svg+xml;utf8," + urllib.parse.quote(svg)


def sign_media_urls(title: str) -> tuple[str, str] | None:
    sign = sign_for_title(title)
    if sign is None:
        return None
    return _data_url(sign_svg(sign, animated=False)), _data_url(sign_svg(sign, animated=True))


def gallery_html() -> str:
    """One self-contained review page with every sign face, for eyeballing colours, shapes and text fit."""
    cells = []
    for sg in iter_signs():
        svg = f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="220 40 360 270" width="190" height="142">{_shape_markup(sg)}</svg>'
        cells.append(
            f'<figure><div class="f">{svg}</div><figcaption>{html.escape(sg.name)}<br>'
            f'<small>{html.escape(sg.shape)} {html.escape(sg.face)} / {html.escape(sg.legend)}</small></figcaption></figure>'
        )
    return (
        "<!doctype html><meta charset=utf-8><title>Driver Ed sign gallery</title>"
        "<style>body{font:13px Arial;background:#e5e7eb;margin:12px}figure{display:inline-block;margin:6px;width:200px;"
        "vertical-align:top;background:#fff;border-radius:8px;padding:4px;text-align:center}.f{background:#dbe7f3;"
        "border-radius:6px}small{color:#555}</style>"
        f"<h2>Driver Ed sign gallery: {len(cells)} signs</h2><p>Colors and shapes follow MUTCD 2003r1 Part 2 and 7B and the CA DMV "
        "Driver Handbook; see docs/driver-ed-signs-and-facts-audit.txt.</p>" + "".join(cells)
    )


if __name__ == "__main__":  # python -m theodore_course_studio.traffic_signs gallery.html
    import sys

    out = sys.argv[1] if len(sys.argv) > 1 else "driver-ed-sign-gallery.html"
    with open(out, "w", encoding="utf-8") as fh:
        fh.write(gallery_html())
    print(f"wrote {out}")
