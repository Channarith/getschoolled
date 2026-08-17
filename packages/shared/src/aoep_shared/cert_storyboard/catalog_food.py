"""Storyboard scenes for CA / Alameda food-handler courses."""

from __future__ import annotations

from .types import Cast, ObjectCallout, Scene, SegmentStoryboard

C = Cast
O = ObjectCallout


def _seg(
    lesson_id: str,
    idx: int,
    *,
    title: str,
    backdrop: str,
    camera: str,
    narration: str,
    cast: list[Cast],
    objects: list[ObjectCallout] | None = None,
    concept: str = "",
    verse: str = "",
    goal: str = "",
    scene_id: str = "",
) -> SegmentStoryboard:
    sid = scene_id or f"{lesson_id}-{idx:02d}"
    return SegmentStoryboard(
        lesson_id=lesson_id,
        slide_index=idx,
        verse_label=verse or title,
        learning_goal=goal or concept,
        scene=Scene(
            scene_id=sid,
            title=title,
            backdrop=backdrop,
            camera=camera,
            narration=narration,
            cast=tuple(cast),
            objects=tuple(objects or ()),
            concept=concept,
        ),
    )


def build_food_hygiene(lesson_id: str = "ca-alameda-food-handler-hygiene") -> list[SegmentStoryboard]:
    return [
        _seg(
            lesson_id, 0,
            title="Prep card, not accreditation",
            backdrop="kitchen",
            camera="ken-burns",
            concept="Practice aid — finish your employer's approved course for the card.",
            narration="This track is study practice for food safety habits. Finish your employer's approved California food handler course for your official card.",
            cast=[C("plate", 400, 320, motion="bob"), C("adult", 220, 300), C("glove", 600, 280, motion="sway")],
            objects=[O("Practice ≠ official card", 40, 80)],
        ),
        _seg(
            lesson_id, 1,
            title="Why food handler cards matter",
            backdrop="kitchen",
            camera="push-in",
            concept="California requires cards; Alameda County inspects practices.",
            narration="California requires many food employees to hold a valid food handler card. Local environmental health, including Alameda County, enforces safe practices during inspections.",
            cast=[C("adult", 300, 300, motion="bob"), C("teen", 420, 310, motion="sway"), C("plate", 620, 320, motion="pulse")],
            objects=[O("Keep your card current", 40, 90)],
        ),
        _seg(
            lesson_id, 2,
            title="Handwashing that works",
            backdrop="prep-station",
            camera="push-in",
            concept="20 seconds with soap — sanitizer is not a substitute.",
            narration="Wash with soap and warm water for at least 20 seconds before handling food, after restroom use, after raw meat, and when switching tasks. Sanitizer is not a substitute for washing.",
            cast=[
                C("sink", 380, 300, scale=1.1, motion="bob"),
                C("soap", 560, 260, motion="pulse"),
                C("adult", 200, 300, motion="sway"),
            ],
            objects=[O("20 seconds · soap · warm water", 40, 80)],
        ),
        _seg(
            lesson_id, 3,
            title="Gloves done right",
            backdrop="prep-station",
            camera="ken-burns",
            concept="Wash, then glove; change after raw proteins and before RTE.",
            narration="Change gloves when torn or dirty, after raw proteins, and before ready-to-eat foods. Wash hands before putting on a new pair.",
            cast=[
                C("glove", 420, 280, scale=1.2, motion="pulse"),
                C("cutting-board", 280, 340, motion="bob"),
                C("plate", 620, 320, motion="sway"),
            ],
            objects=[O("Wash → glove → work", 40, 90)],
        ),
        _seg(
            lesson_id, 4,
            title="Illness reporting",
            backdrop="kitchen",
            camera="static",
            concept="Report vomiting, diarrhea, jaundice, or fever with sore throat.",
            narration="Report vomiting, diarrhea, jaundice, or sore throat with fever to your manager before working. Diagnosed pathogens require exclusion rules your manager must follow.",
            cast=[C("adult", 360, 300, motion="bob"), C("plate", 560, 340, motion="sway")],
            objects=[O("Tell your manager first", 40, 80)],
        ),
        _seg(
            lesson_id, 5,
            title="Personal cleanliness",
            backdrop="kitchen",
            camera="pull-out",
            concept="Clean clothes, restrained hair, no jewelry traps.",
            narration="Wear clean clothes and aprons, restrain hair, keep nails short and clean, and avoid jewelry that can trap soil. Do not eat, drink, or smoke in food prep areas.",
            cast=[C("adult", 320, 300, motion="bob"), C("teen", 480, 310, motion="sway"), C("sink", 680, 300, scale=0.85)],
            objects=[O("Uniform is food safety", 40, 90)],
        ),
        _seg(
            lesson_id, 6,
            title="Ready-to-eat foods",
            backdrop="prep-station",
            camera="push-in",
            concept="Use gloves, tongs, or deli paper — no bare-hand contact.",
            narration="Do not touch ready-to-eat foods with bare hands where rules require barriers — use gloves, tongs, or deli paper as trained.",
            cast=[
                C("plate", 400, 300, scale=1.2, motion="bob"),
                C("glove", 280, 260, motion="pulse"),
                C("cutting-board", 620, 340, motion="sway"),
            ],
            objects=[O("Barrier between hands & food", 40, 80)],
        ),
        _seg(
            lesson_id, 7,
            title="Cuts and bandages",
            backdrop="prep-station",
            camera="zoom-punch",
            concept="Cover wounds; glove over hand bandages.",
            narration="Cover wounds with clean bandages and wear gloves over hand wounds. Stay off the line if you cannot protect food from contamination.",
            cast=[C("glove", 400, 280, scale=1.3, motion="pulse"), C("adult", 240, 300), C("soap", 620, 260)],
            objects=[O("Bandage + glove", 40, 90)],
        ),
        _seg(
            lesson_id, 8,
            title="Customer allergen basics",
            backdrop="kitchen",
            camera="ken-burns",
            concept="FDA Big 9 includes sesame — never guess ingredients.",
            narration="Know major allergens — the FDA Big 9 includes sesame. Never guess ingredients; check with the kitchen and prevent cross-contact.",
            cast=[C("plate", 360, 300, motion="bob"), C("cutting-board", 560, 340, motion="sway"), C("adult", 200, 300)],
            objects=[O("Verify before you serve", 40, 80)],
        ),
        _seg(
            lesson_id, 9,
            title="Next short block",
            backdrop="kitchen",
            camera="pull-out",
            concept="Continue with temps and contamination in another short session.",
            narration="Continue with temperature control and contamination prevention in another 15 to 20 minute session. Spaced practice beats marathon cramming.",
            cast=[C("thermometer-41", 300, 260, motion="pulse"), C("plate", 480, 320, motion="bob"), C("adult", 650, 300)],
            objects=[O("Pause and resume later", 40, 90)],
        ),
    ]


def build_food_temps(lesson_id: str = "ca-alameda-food-handler-temps") -> list[SegmentStoryboard]:
    return [
        _seg(
            lesson_id, 0,
            title="Temperature danger zone",
            backdrop="kitchen",
            camera="ken-burns",
            concept="Danger zone is 41°F to 135°F — bacteria multiply fast.",
            narration="The temperature danger zone is 41 to 135 degrees Fahrenheit. Keep TCS foods out of this range as much as possible.",
            cast=[
                C("thermometer-41", 280, 260, motion="pulse"),
                C("thermometer-135", 480, 260, motion="pulse"),
                C("stove", 700, 320, scale=0.9, motion="bob"),
            ],
            objects=[O("41°F – 135°F = danger", 40, 80)],
        ),
        _seg(
            lesson_id, 1,
            title="Cold holding",
            backdrop="cold-storage",
            camera="push-in",
            concept="Hold cold TCS at 41°F or below; raw under ready-to-eat.",
            narration="Hold cold TCS foods at 41 degrees or below. Check refrigerators with a calibrated thermometer. Store raw animal foods below ready-to-eat items.",
            cast=[
                C("fridge", 360, 280, scale=1.2, motion="bob"),
                C("thermometer-41", 580, 240, motion="pulse"),
                C("plate", 200, 340, motion="sway"),
            ],
            objects=[O("Raw below ready-to-eat", 40, 90)],
        ),
        _seg(
            lesson_id, 2,
            title="Hot holding",
            backdrop="kitchen",
            camera="pan-right",
            concept="Hot hold at 135°F+ after proper reheating.",
            narration="Hold hot TCS foods at 135 degrees or above. Hot-holding equipment is not for reheating from cold — reheat properly first.",
            cast=[
                C("stove", 400, 300, scale=1.15, motion="bob"),
                C("thermometer-135", 620, 240, motion="pulse"),
                C("plate", 220, 340, motion="sway"),
            ],
            objects=[O("135°F or hotter", 40, 80)],
        ),
        _seg(
            lesson_id, 3,
            title="Safe cooking targets",
            backdrop="kitchen",
            camera="zoom-punch",
            concept="Poultry 165 · ground 155 · whole cuts/fish 145.",
            narration="Common minimum internal temps: poultry 165, ground meats 155, whole cuts of beef pork or lamb and fish 145 with rest where required. Always verify with a food thermometer.",
            cast=[
                C("thermometer-165", 240, 240, motion="pulse"),
                C("thermometer-155", 420, 240, motion="pulse"),
                C("thermometer-145", 600, 240, motion="pulse"),
                C("stove", 720, 320, scale=0.85),
            ],
            objects=[O("Probe the thickest part", 40, 90)],
        ),
        _seg(
            lesson_id, 4,
            title="Cooling cooked food",
            backdrop="cold-storage",
            camera="ken-burns",
            concept="135→70 in 2 hours, then to 41 in 4 more — 6 hours total.",
            narration="Cool from 135 to 70 within 2 hours, then to 41 within 4 more hours — 6 hours total. Use shallow pans, ice baths, or blast chillers.",
            cast=[
                C("thermometer-135", 260, 240, motion="pulse"),
                C("thermometer-41", 480, 240, motion="pulse"),
                C("fridge", 680, 300, scale=1.0, motion="bob"),
            ],
            objects=[O("Two-step cooling", 40, 80)],
        ),
        _seg(
            lesson_id, 5,
            title="Reheating",
            backdrop="kitchen",
            camera="push-in",
            concept="Reheat leftovers to 165°F within 2 hours.",
            narration="Reheat previously cooked TCS food to 165 degrees within 2 hours before hot holding. Do not rely on steam tables or slow cookers to reheat.",
            cast=[
                C("stove", 380, 300, scale=1.2, motion="bob"),
                C("thermometer-165", 600, 240, motion="pulse"),
                C("plate", 220, 340),
            ],
            objects=[O("165°F before hot hold", 40, 90)],
        ),
        _seg(
            lesson_id, 6,
            title="Thawing safely",
            backdrop="cold-storage",
            camera="pan-left",
            concept="Never thaw on the counter.",
            narration="Thaw in a refrigerator, under cold running water, in a microwave if cooking immediately, or as part of cooking. Never thaw on the counter.",
            cast=[
                C("fridge", 340, 280, scale=1.15, motion="bob"),
                C("sink", 620, 300, scale=0.9, motion="sway"),
                C("plate", 180, 340),
            ],
            objects=[O("No counter thawing", 40, 80)],
        ),
        _seg(
            lesson_id, 7,
            title="Receiving checks",
            backdrop="dock",
            camera="dolly-shake",
            concept="Reject warm, damaged, or pest-infested deliveries.",
            narration="Reject deliveries that arrive too warm, damaged, pest-infested, or past safe dating. Keep the cold chain unbroken from dock to storage.",
            cast=[
                C("truck", 300, 300, scale=1.1, motion="drive"),
                C("thermometer-41", 560, 240, motion="pulse"),
                C("adult", 700, 300, motion="bob"),
            ],
            objects=[O("Inspect before you accept", 40, 90)],
        ),
        _seg(
            lesson_id, 8,
            title="Date marking",
            backdrop="cold-storage",
            camera="static",
            concept="Label RTE TCS; typical 7-day refrigerated hold.",
            narration="Label prepared ready-to-eat TCS foods and follow the typical 7-day refrigerated hold rule unless your code or policy is stricter.",
            cast=[C("fridge", 400, 280, scale=1.2, motion="bob"), C("plate", 220, 340, motion="sway"), C("adult", 650, 300)],
            objects=[O("Date mark · discard on time", 40, 80)],
        ),
        _seg(
            lesson_id, 9,
            title="Thermometer habits",
            backdrop="kitchen",
            camera="pull-out",
            concept="Calibrate, clean, probe thickest part, log when required.",
            narration="Calibrate and clean thermometers. Probe the thickest part of food. Log temperatures when your site requires it — inspectors look for consistent control.",
            cast=[
                C("thermometer-165", 360, 250, scale=1.2, motion="pulse"),
                C("stove", 560, 320, motion="bob"),
                C("adult", 200, 300),
            ],
            objects=[O("Clean · calibrated · logged", 40, 90)],
        ),
    ]


def build_food_contamination(lesson_id: str = "ca-alameda-food-handler-contamination") -> list[SegmentStoryboard]:
    return [
        _seg(
            lesson_id, 0,
            title="Cross-contamination",
            backdrop="prep-station",
            camera="ken-burns",
            concept="Keep raw and ready-to-eat paths separate.",
            narration="Cross-contamination spreads pathogens from raw foods, dirty surfaces, or hands onto ready-to-eat foods. Keep paths separate and clean between tasks.",
            cast=[
                C("cutting-board", 280, 320, motion="bob"),
                C("cutting-board", 520, 330, scale=0.9, motion="sway"),
                C("plate", 700, 300, motion="pulse"),
                C("glove", 180, 260),
            ],
            objects=[O("Separate raw & ready-to-eat", 40, 80)],
        ),
        _seg(
            lesson_id, 1,
            title="Clean then sanitize",
            backdrop="prep-station",
            camera="push-in",
            concept="Scrape, wash, rinse, sanitize, air dry — in that order.",
            narration="Scrape, wash with detergent, rinse, sanitize at correct concentration, then air dry. Sanitizing dirty surfaces does not work.",
            cast=[
                C("sink", 360, 300, scale=1.15, motion="bob"),
                C("soap", 560, 250, motion="pulse"),
                C("cutting-board", 700, 340, motion="sway"),
            ],
            objects=[O("Clean first, then sanitize", 40, 90)],
        ),
        _seg(
            lesson_id, 2,
            title="Sanitizer strength",
            backdrop="kitchen",
            camera="zoom-punch",
            concept="Mix per label; verify with test strips.",
            narration="Mix chlorine, quat, or iodine per label. Verify with test strips and replace dirty or weak solutions.",
            cast=[C("sink", 400, 300, motion="bob"), C("soap", 580, 250, scale=1.1, motion="pulse"), C("adult", 220, 300)],
            objects=[O("Test strips every time", 40, 80)],
        ),
        _seg(
            lesson_id, 3,
            title="FIFO stock rotation",
            backdrop="cold-storage",
            camera="pan-right",
            concept="First In, First Out — oldest product first.",
            narration="First In, First Out: place new stock behind older product and use the oldest first to reduce spoilage risk.",
            cast=[
                C("fridge", 340, 280, scale=1.15, motion="bob"),
                C("plate", 560, 320, motion="sway"),
                C("plate", 680, 340, scale=0.85, motion="bob"),
                C("adult", 180, 300),
            ],
            objects=[O("Oldest in front", 40, 90)],
        ),
        _seg(
            lesson_id, 4,
            title="Pest prevention",
            backdrop="dock",
            camera="dolly-shake",
            concept="Deny food, water, shelter; use licensed pest control.",
            narration="Seal gaps, store food sealed, clean spills, and remove clutter. Use licensed pest control — do not spray pesticides over food areas yourself.",
            cast=[
                C("pest", 420, 340, scale=1.2, motion="hop"),
                C("pest", 520, 360, scale=0.9, motion="hop", delay=0.3),
                C("truck", 200, 300, scale=0.9),
                C("adult", 700, 300, motion="bob"),
            ],
            objects=[O("Deny food · water · shelter", 40, 80)],
        ),
        _seg(
            lesson_id, 5,
            title="Allergen cross-contact",
            backdrop="prep-station",
            camera="ken-burns",
            concept="Dedicated tools and cleaning; menu accuracy matters.",
            narration="Allergens need dedicated handling: clean equipment, separate prep, and accurate menu communication. Cleaning alone may not remove allergen residues.",
            cast=[
                C("cutting-board", 300, 320, motion="bob"),
                C("plate", 520, 300, motion="pulse"),
                C("glove", 680, 260, motion="sway"),
            ],
            objects=[O("Treat allergen requests as critical", 40, 90)],
        ),
        _seg(
            lesson_id, 6,
            title="Common pathogens",
            backdrop="kitchen",
            camera="push-in",
            concept="Hygiene and correct cooking stop the common pathogens.",
            narration="Know high-risk associations: Salmonella with poultry and eggs, STEC with ground beef and produce, Listeria with deli foods, norovirus with hands and ready-to-eat foods.",
            cast=[
                C("thermometer-165", 280, 240, motion="pulse"),
                C("soap", 450, 250, motion="bob"),
                C("plate", 620, 320, motion="sway"),
                C("glove", 180, 280),
            ],
            objects=[O("Cook · clean · don't touch RTE bare", 40, 80)],
        ),
        _seg(
            lesson_id, 7,
            title="Health inspections",
            backdrop="kitchen",
            camera="static",
            concept="Fix critical violations immediately; ask when unsure.",
            narration="Alameda County Environmental Health inspects for critical violations that can cause illness. Keep logs, fix problems immediately, and ask supervisors when unsure.",
            cast=[C("adult", 320, 300, motion="bob"), C("thermometer-41", 520, 250, motion="pulse"), C("fridge", 700, 300, scale=0.9)],
            objects=[O("Critical = fix now", 40, 90)],
        ),
        _seg(
            lesson_id, 8,
            title="If a guest gets sick",
            backdrop="kitchen",
            camera="zoom-punch",
            concept="Notify a manager; preserve food if instructed.",
            narration="Take complaints seriously, notify a manager, preserve suspected food if instructed, and cooperate with investigators.",
            cast=[C("adult", 360, 300, motion="bob"), C("plate", 560, 320, motion="pulse"), C("teen", 220, 310, motion="sway")],
            objects=[O("Report to manager immediately", 40, 80)],
        ),
        _seg(
            lesson_id, 9,
            title="Finish with the official course",
            backdrop="kitchen",
            camera="pull-out",
            concept="Complete your employer's approved course for the card.",
            narration="Review your employer's approved California food handler course materials, then take the official assessment for your card. This studio track is practice only.",
            cast=[C("plate", 400, 300, motion="bob"), C("adult", 240, 300), C("teen", 560, 310, motion="sway"), C("glove", 700, 260)],
            objects=[O("Official course → card", 40, 90)],
        ),
    ]


def food_hygiene_segments() -> list[SegmentStoryboard]:
    return build_food_hygiene()


def food_temps_segments() -> list[SegmentStoryboard]:
    return build_food_temps()


def food_contamination_segments() -> list[SegmentStoryboard]:
    return build_food_contamination()
