"""Learn-by-playing mini-games + scoring (engine).

Subject mini-games across biology, chemistry, physics, math, science, history,
art, technology and programming. Three game modes:

- ``quiz``  : pick the correct answer (untimed)
- ``speed`` : same questions, timed, with a speed bonus
- ``match`` : match terms to their definitions

Pure/offline + stdlib + pydantic only. The service builds a round (with the
answer key kept server-side), serves a sanitized ``public()`` view to the client,
and scores submissions here. Points feed the existing rewards ledger and the
leaderboard, so learning is competitive and fun.
"""

from __future__ import annotations

import enum
import random
import uuid
from typing import Dict, List, Optional

from pydantic import BaseModel, Field


class GameType(str, enum.Enum):
    QUIZ = "quiz"
    SPEED = "speed"
    MATCH = "match"
    MARATHON = "marathon"
    TILES = "tiles"
    RESOURCE = "resource"
    DEPENDENCY = "dependency"
    RPG = "rpg"
    CARTOON = "cartoon"
    IDIOM = "idiom"
    CREATE = "create"
    DOING = "doing"
    FARM = "farm"
    SPELLING = "spelling"
    GEOMETRY = "geometry"


EXTENDED_ONLY_SUBJECTS = frozenset({
    "life_growth", "etiquette", "wordplay", "geometry", "creation", "farming",
})

EXTENDED_GAME_TYPES = frozenset({
    GameType.TILES, GameType.RESOURCE, GameType.DEPENDENCY, GameType.RPG,
    GameType.CARTOON, GameType.IDIOM, GameType.CREATE, GameType.DOING,
    GameType.FARM, GameType.SPELLING, GameType.GEOMETRY,
})


class AgeGroup(str, enum.Enum):
    KIDS = "kids"      # ~5-8
    TWEEN = "tween"    # ~9-12
    TEEN = "teen"      # ~13-17
    ADULT = "adult"    # 18+


# Age-group metadata + fallback chain (use the nearest available content when a
# subject has no bank for the requested age).
AGE_GROUPS = [
    {"id": "kids", "name": "Kids", "range": "ages 5-8"},
    {"id": "tween", "name": "Tweens", "range": "ages 9-12"},
    {"id": "teen", "name": "Teens", "range": "ages 13-17"},
    {"id": "adult", "name": "Adults", "range": "18+"},
]

# Subjects the arcade supports (kept independent of the course catalog).
GAME_SUBJECTS: List[str] = [
    "biology", "chemistry", "physics", "math", "science",
    "history", "art", "technology", "programming",
    "life_growth", "etiquette", "wordplay", "geometry", "creation", "farming",
]

SPEED_TIME_LIMIT_S = 45
MARATHON_TIME_LIMIT_S = 180
MAX_ROUND_ITEMS = 25
DEFAULT_MARATHON_ITEMS = 20


class MCQItem(BaseModel):
    id: str
    prompt: str
    options: List[str]
    answer_index: int
    explain: str = ""
    content_id: str = ""
    kind: str = "mcq"
    meta: dict = Field(default_factory=dict)


class MatchPair(BaseModel):
    id: str
    term: str
    match: str


# --------------------------------------------------------------------------- #
# Question banks (compact but real). Each subject: MCQs + match pairs.
# --------------------------------------------------------------------------- #
def _mcq(prompt, options, ans, explain=""):
    return {"prompt": prompt, "options": options, "answer_index": ans, "explain": explain}


_MCQ_BANK: Dict[str, List[dict]] = {
    "biology": [
        _mcq("What is the powerhouse of the cell?", ["Nucleus", "Mitochondria", "Ribosome", "Golgi"], 1,
             "Mitochondria produce ATP, the cell's energy currency."),
        _mcq("Which molecule carries genetic information?", ["DNA", "ATP", "Glucose", "Lipid"], 0),
        _mcq("Plants make food via…", ["Respiration", "Photosynthesis", "Digestion", "Fermentation"], 1),
        _mcq("Red blood cells carry…", ["Oxygen", "Hormones", "Enzymes", "Antibodies"], 0),
        _mcq("The basic unit of life is the…", ["Atom", "Cell", "Organ", "Tissue"], 1),
    ],
    "chemistry": [
        _mcq("Chemical symbol for water?", ["CO2", "H2O", "O2", "NaCl"], 1),
        _mcq("Atomic number = number of…", ["Neutrons", "Protons", "Electrons + neutrons", "Isotopes"], 1),
        _mcq("pH below 7 is…", ["Basic", "Neutral", "Acidic", "Inert"], 2),
        _mcq("Which is a noble gas?", ["Oxygen", "Helium", "Hydrogen", "Nitrogen"], 1),
        _mcq("Table salt is…", ["NaCl", "KCl", "HCl", "CaCO3"], 0),
    ],
    "physics": [
        _mcq("Unit of force?", ["Joule", "Newton", "Watt", "Pascal"], 1),
        _mcq("Speed of light is about…", ["3×10^5 m/s", "3×10^8 m/s", "3×10^3 m/s", "3×10^6 m/s"], 1),
        _mcq("F = m × …?", ["velocity", "acceleration", "distance", "time"], 1),
        _mcq("Energy of motion is…", ["Potential", "Kinetic", "Thermal", "Chemical"], 1),
        _mcq("Gravity on Earth ≈", ["9.8 m/s²", "1.6 m/s²", "98 m/s²", "0 m/s²"], 0),
    ],
    "math": [
        _mcq("12 × 8 = ?", ["86", "96", "108", "84"], 1),
        _mcq("What is 25% of 200?", ["25", "40", "50", "75"], 2),
        _mcq("Solve: 3x = 21, x = ?", ["6", "7", "8", "9"], 1),
        _mcq("Area of a circle?", ["2πr", "πr²", "πd", "r²"], 1),
        _mcq("Next prime after 7?", ["9", "10", "11", "13"], 2),
    ],
    "science": [
        _mcq("Closest planet to the Sun?", ["Venus", "Mercury", "Earth", "Mars"], 1),
        _mcq("Water boils at (sea level)…", ["50°C", "100°C", "150°C", "212°C"], 1),
        _mcq("Gas plants absorb?", ["Oxygen", "Nitrogen", "Carbon dioxide", "Helium"], 2),
        _mcq("What causes day and night?", ["Earth's rotation", "Earth's orbit", "Moon", "Tilt"], 0),
        _mcq("Largest planet?", ["Saturn", "Jupiter", "Neptune", "Earth"], 1),
    ],
    "history": [
        _mcq("Who was the first US President?", ["Lincoln", "Washington", "Jefferson", "Adams"], 1),
        _mcq("The Great Wall is in…", ["India", "China", "Egypt", "Peru"], 1),
        _mcq("WWII ended in…", ["1918", "1939", "1945", "1950"], 2),
        _mcq("Egyptian writing system?", ["Cuneiform", "Hieroglyphs", "Latin", "Runes"], 1),
        _mcq("Renaissance began in…", ["France", "Italy", "England", "Spain"], 1),
    ],
    "art": [
        _mcq("Who painted the Mona Lisa?", ["Michelangelo", "Da Vinci", "Picasso", "Van Gogh"], 1),
        _mcq("Primary colors?", ["Red, green, blue", "Red, yellow, blue", "Cyan, magenta, yellow", "Black, white, gray"], 1),
        _mcq("'Starry Night' is by…", ["Monet", "Van Gogh", "Dali", "Rembrandt"], 1),
        _mcq("Sculpture 'David' is by…", ["Donatello", "Michelangelo", "Bernini", "Rodin"], 1),
        _mcq("A warm color is…", ["Blue", "Green", "Orange", "Purple"], 2),
    ],
    "technology": [
        _mcq("CPU stands for…", ["Central Processing Unit", "Computer Power Unit", "Core Program Unit", "Central Print Unit"], 0),
        _mcq("HTTP is used for…", ["Email", "Web pages", "Printing", "Storage"], 1),
        _mcq("Binary uses which digits?", ["0-9", "0 and 1", "1-10", "A-F"], 1),
        _mcq("RAM is…", ["Permanent storage", "Temporary memory", "A processor", "A network"], 1),
        _mcq("The 'cloud' refers to…", ["Weather data", "Remote servers", "Local disk", "A GPU"], 1),
    ],
    "programming": [
        _mcq("Which is a Python list?", ["{1,2}", "[1,2]", "(1,2)", "<1,2>"], 1),
        _mcq("'==' in most languages means…", ["Assign", "Compare equality", "Add", "Not equal"], 1),
        _mcq("A function that calls itself is…", ["Looping", "Recursion", "Iteration", "Nesting"], 1),
        _mcq("Output of print(2 ** 3)?", ["6", "8", "9", "23"], 1),
        _mcq("HTML is a … language", ["Programming", "Markup", "Query", "Machine"], 1),
    ],
}

_PAIR_BANK: Dict[str, List[tuple]] = {
    "biology": [("Mitochondria", "Energy (ATP)"), ("Ribosome", "Protein synthesis"),
                ("Chlorophyll", "Captures light"), ("DNA", "Genetic code")],
    "chemistry": [("H2O", "Water"), ("NaCl", "Salt"), ("O2", "Oxygen gas"), ("CO2", "Carbon dioxide")],
    "physics": [("Newton", "Force"), ("Joule", "Energy"), ("Watt", "Power"), ("Pascal", "Pressure")],
    "math": [("π", "≈ 3.14159"), ("Prime", "Divisible by 1 and itself"),
             ("Hypotenuse", "Longest side"), ("Sum", "Result of addition")],
    "science": [("Mercury", "Closest planet"), ("Photosynthesis", "Plants make food"),
                ("H2O", "Boils at 100°C"), ("Rotation", "Causes day/night")],
    "history": [("Washington", "First US President"), ("Italy", "Renaissance origin"),
                ("1945", "WWII ends"), ("Hieroglyphs", "Egyptian writing")],
    "art": [("Da Vinci", "Mona Lisa"), ("Van Gogh", "Starry Night"),
            ("Michelangelo", "David"), ("Orange", "Warm color")],
    "technology": [("CPU", "Processor"), ("RAM", "Temporary memory"),
                   ("HTTP", "Web protocol"), ("Binary", "0 and 1")],
    "programming": [("List", "[1, 2]"), ("Recursion", "Calls itself"),
                    ("==", "Equality check"), ("HTML", "Markup language")],
}


# --------------------------------------------------------------------------- #
# Age-tiered content. KIDS = gentle/playful; ADULT = harder extras layered on
# top of the core (teen/tween use the core bank). Subjects without a tier fall
# back via the chain in mcq_bank_for/pair_bank_for.
# --------------------------------------------------------------------------- #
_KIDS_MCQ: Dict[str, List[dict]] = {
    "biology": [
        _mcq("Which animal says 'moo'?", ["Dog", "Cow", "Cat", "Duck"], 1),
        _mcq("What do plants need to grow?", ["Candy", "Sunlight", "Toys", "Rocks"], 1),
        _mcq("How many legs does a spider have?", ["4", "6", "8", "10"], 2),
        _mcq("Where do fish live?", ["Trees", "Water", "Sky", "Sand"], 1),
    ],
    "chemistry": [
        _mcq("What do we drink when thirsty?", ["Sand", "Water", "Glue", "Rocks"], 1),
        _mcq("Ice is frozen…", ["Juice", "Water", "Milk", "Air"], 1),
        _mcq("What tastes salty?", ["Sugar", "Salt", "Apple", "Bread"], 1),
        _mcq("Bubbles in soda are made of…", ["Sand", "Gas", "Water", "Rocks"], 1),
    ],
    "physics": [
        _mcq("What goes up must come…", ["Up", "Down", "Sideways", "Away"], 1),
        _mcq("The sun gives us light and…", ["Snow", "Heat", "Rain", "Wind"], 1),
        _mcq("Magnets stick to…", ["Wood", "Metal", "Paper", "Water"], 1),
        _mcq("A ball moves when you…", ["Look at it", "Push it", "Sing", "Sleep"], 1),
    ],
    "math": [
        _mcq("2 + 3 = ?", ["4", "5", "6", "7"], 1),
        _mcq("How many fingers on one hand?", ["3", "4", "5", "6"], 2),
        _mcq("Which is bigger?", ["4", "7", "2", "1"], 1),
        _mcq("5 - 2 = ?", ["1", "2", "3", "4"], 2),
    ],
    "science": [
        _mcq("We see stars and the moon in the…", ["Morning", "Night", "Lunch", "Bath"], 1),
        _mcq("Water falls from the sky as…", ["Rain", "Sand", "Rocks", "Toys"], 0),
        _mcq("How many seasons are there?", ["2", "3", "4", "5"], 2),
        _mcq("The sun rises in the…", ["Night", "Morning", "Pool", "Box"], 1),
    ],
    "history": [
        _mcq("Big reptiles that lived long ago were…", ["Dinosaurs", "Cars", "Robots", "Phones"], 0),
        _mcq("A king wears a…", ["Hat", "Crown", "Sock", "Cup"], 1),
        _mcq("Knights rode on…", ["Horses", "Bikes", "Planes", "Boats"], 0),
        _mcq("Pyramids are found in…", ["Egypt", "Space", "Ocean", "Mall"], 0),
    ],
    "art": [
        _mcq("Blue and yellow make…", ["Red", "Green", "Black", "Pink"], 1),
        _mcq("You paint with a…", ["Spoon", "Brush", "Shoe", "Cup"], 1),
        _mcq("A rainbow has many…", ["Rocks", "Colors", "Numbers", "Words"], 1),
        _mcq("Which is a color?", ["Loud", "Purple", "Fast", "Cold"], 1),
    ],
    "technology": [
        _mcq("You call someone far away with a…", ["Spoon", "Phone", "Hat", "Ball"], 1),
        _mcq("You type on a…", ["Keyboard", "Pillow", "Plate", "Door"], 0),
        _mcq("Robots are machines that can…", ["Sleep only", "Move and help", "Eat cake", "Cry"], 1),
        _mcq("A computer shows things on a…", ["Screen", "Rock", "Leaf", "Sock"], 0),
    ],
    "programming": [
        _mcq("A list of steps for a computer is a…", ["Snack", "Program", "Cloud", "Hat"], 1),
        _mcq("You move the arrow on screen with a…", ["Mouse", "Cat", "Cup", "Sock"], 0),
        _mcq("Computers like to count with…", ["Colors", "0s and 1s", "Apples", "Songs"], 1),
        _mcq("A mistake in code is called a…", ["Bug", "Cat", "Star", "Hat"], 0),
    ],
}

_KIDS_PAIRS: Dict[str, List[tuple]] = {
    "biology": [("Cow", "Moo"), ("Dog", "Bark"), ("Fish", "Swim"), ("Bird", "Fly")],
    "chemistry": [("Ice", "Cold"), ("Fire", "Hot"), ("Water", "Drink"), ("Salt", "Salty")],
    "physics": [("Sun", "Hot"), ("Magnet", "Metal"), ("Ball", "Roll"), ("Up", "Down")],
    "math": [("1", "One"), ("2", "Two"), ("3", "Three"), ("4", "Four")],
    "science": [("Rain", "Sky"), ("Star", "Night"), ("Sun", "Day"), ("Fish", "Water")],
    "history": [("King", "Crown"), ("Knight", "Horse"), ("Pyramid", "Egypt"), ("Dino", "Long ago")],
    "art": [("Red", "Color"), ("Brush", "Paint"), ("Sun", "Yellow"), ("Grass", "Green")],
    "technology": [("Phone", "Call"), ("Keyboard", "Type"), ("Screen", "Show"), ("Robot", "Help")],
    "programming": [("Mouse", "Click"), ("Bug", "Mistake"), ("Code", "Steps"), ("0/1", "Binary")],
}

_ADULT_MCQ: Dict[str, List[dict]] = {
    "math": [
        _mcq("d/dx of x² is…", ["x", "2x", "x²", "2"], 1),
        _mcq("log₂(8) = ?", ["2", "3", "4", "8"], 1),
        _mcq("Solve 2^x = 16, x = ?", ["2", "3", "4", "5"], 2),
    ],
    "physics": [
        _mcq("E = mc² relates energy and…", ["charge", "mass", "time", "volume"], 1),
        _mcq("Unit of capacitance?", ["Ohm", "Farad", "Henry", "Tesla"], 1),
    ],
    "chemistry": [
        _mcq("Avogadro's number ≈", ["6.02×10²³", "3.14", "9.81", "1.6×10⁻¹⁹"], 0),
        _mcq("A catalyst…", ["Is consumed", "Speeds a reaction", "Stops reactions", "Adds mass"], 1),
    ],
    "biology": [
        _mcq("Protein synthesis occurs at the…", ["Nucleus", "Ribosome", "Vacuole", "Membrane"], 1),
        _mcq("The Krebs cycle occurs in the…", ["Nucleus", "Mitochondria", "Ribosome", "Golgi"], 1),
    ],
    "programming": [
        _mcq("Big-O of binary search?", ["O(n)", "O(log n)", "O(n²)", "O(1)"], 1),
        _mcq("A stack is…", ["FIFO", "LIFO", "Random", "Sorted"], 1),
        _mcq("Which is immutable in Python?", ["list", "dict", "tuple", "set"], 2),
    ],
    "history": [
        _mcq("The Berlin Wall fell in…", ["1979", "1989", "1991", "2001"], 1),
        _mcq("The Magna Carta was signed in…", ["1066", "1215", "1492", "1776"], 1),
    ],
    "science": [
        _mcq("Speed of sound in air ≈", ["34 m/s", "343 m/s", "3,430 m/s", "3×10⁸ m/s"], 1),
    ],
    "technology": [
        _mcq("TCP/IP is a…", ["File format", "Protocol suite", "CPU", "Database"], 1),
    ],
    "art": [
        _mcq("'Chiaroscuro' refers to…", ["Color theory", "Light/shadow contrast", "Sculpture", "Symmetry"], 1),
    ],
}


def mcq_bank_for(subject: str, age: AgeGroup) -> List[dict]:
    """Age-appropriate MCQ pool for a subject (with sensible fallbacks)."""
    if age is AgeGroup.KIDS:
        core = _KIDS_MCQ.get(subject) or _MCQ_BANK.get(subject, [])
    elif age is AgeGroup.ADULT:
        core = _MCQ_BANK.get(subject, []) + _ADULT_MCQ.get(subject, [])
    else:
        core = _MCQ_BANK.get(subject, [])
    if not core:
        core = _MCQ_BANK.get("science", [])
    return core
    # Triple the bank with review/challenge variants for longer, addictive sessions.
    expanded: List[dict] = []
    for prefix in ("", "Review — ", "Challenge — "):
        for q in core:
            expanded.append({**q, "prompt": prefix + q["prompt"]})
    return expanded


def pair_bank_for(subject: str, age: AgeGroup) -> List[tuple]:
    if age is AgeGroup.KIDS:
        core = _KIDS_PAIRS.get(subject) or _PAIR_BANK.get(subject, [])
    else:
        core = _PAIR_BANK.get(subject, [])
    if not core:
        core = _PAIR_BANK.get("science", [])
    return core
    expanded = list(core)
    for term, match in core:
        expanded.append((f"Review: {term}", match))
    return expanded


class GameRound(BaseModel):
    game_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    subject: str
    game_type: GameType
    age_group: AgeGroup = AgeGroup.TEEN
    locale: str = "en"
    time_limit_s: int = 0
    mcqs: List[MCQItem] = Field(default_factory=list)
    pairs: List[MatchPair] = Field(default_factory=list)

    def public(self) -> dict:
        """Client-facing round with answers stripped."""
        from .games_i18n import localize_mcq_item

        out: dict = {
            "game_id": self.game_id, "subject": self.subject,
            "game_type": self.game_type.value, "age_group": self.age_group.value,
            "locale": self.locale, "time_limit_s": self.time_limit_s,
        }
        if self.game_type is GameType.MATCH:
            rng = random.Random(self.game_id)
            options = [{"id": p.id, "text": p.match} for p in self.pairs]
            rng.shuffle(options)
            out["terms"] = [{"id": p.id, "term": p.term} for p in self.pairs]
            out["options"] = options
        else:
            out["items"] = [
                localize_mcq_item({
                    "id": m.id, "prompt": m.prompt, "options": m.options,
                    "content_id": m.content_id, "kind": m.kind, "meta": m.meta,
                }, self.locale)
                for m in self.mcqs
            ]
        return out


class ItemResult(BaseModel):
    id: str
    correct: bool
    answer_index: Optional[int] = None
    explain: str = ""


class ScoreResult(BaseModel):
    game_id: str
    subject: str
    game_type: GameType
    correct: int
    total: int
    accuracy: float
    base_points: int
    speed_bonus: int
    accuracy_bonus: int
    points: int
    results: List[ItemResult] = Field(default_factory=list)


def _extended_mcq_bank(subject: str, game_type: GameType, age: AgeGroup) -> List[dict]:
    from .games_extended import extended_bank, extended_bank_for_subject

    if game_type in EXTENDED_GAME_TYPES:
        rows = extended_bank(subject, game_type.value, age)
    elif subject in EXTENDED_ONLY_SUBJECTS:
        rows = extended_bank_for_subject(subject, age)
    else:
        rows = extended_bank(subject, game_type.value, age)
    return [
        {
            "prompt": r["prompt"], "options": r["options"],
            "answer_index": r["answer_index"], "explain": r.get("explain", ""),
            "content_id": r.get("content_id", ""), "kind": r.get("kind", game_type.value),
            "meta": r.get("meta", {}),
        }
        for r in rows
    ]


def make_round(subject: str, game_type: GameType, *, age_group: AgeGroup = AgeGroup.TEEN,
               n: int = 5, seed: Optional[int] = None, locale: str = "en") -> GameRound:
    from .games_i18n import normalize_locale

    subject = subject if subject in GAME_SUBJECTS else "science"
    loc = normalize_locale(locale)
    rng = random.Random(seed)
    if game_type is GameType.MARATHON:
        n = max(n, DEFAULT_MARATHON_ITEMS)
    cap = MAX_ROUND_ITEMS if game_type is GameType.MARATHON else min(n, MAX_ROUND_ITEMS)
    if game_type is GameType.MATCH:
        bank = pair_bank_for(subject, age_group)[:]
        rng.shuffle(bank)
        pairs = [MatchPair(id=uuid.uuid4().hex[:8], term=t, match=m)
                 for t, m in bank[: max(2, min(n, len(bank), cap))]]
        return GameRound(subject=subject, game_type=game_type, age_group=age_group,
                         locale=loc, pairs=pairs)
    bank: List[dict] = []
    if game_type in EXTENDED_GAME_TYPES or subject in EXTENDED_ONLY_SUBJECTS:
        bank = _extended_mcq_bank(subject, game_type, age_group)
    if not bank:
        bank = mcq_bank_for(subject, age_group)[:]
    if game_type is GameType.MARATHON and len(bank) < cap:
        # Supplement with extended subject items so marathon has enough depth.
        from .games_extended import extended_bank_for_subject
        seen = {q.get("content_id") for q in bank}
        bank = bank + [q for q in extended_bank_for_subject(subject, age_group)
                       if q.get("content_id") not in seen]
    rng.shuffle(bank)
    take = max(1, min(n, len(bank), cap))
    mcqs = [
        MCQItem(
            id=uuid.uuid4().hex[:8],
            prompt=q["prompt"],
            options=q["options"],
            answer_index=q["answer_index"],
            explain=q.get("explain", ""),
            content_id=q.get("content_id", ""),
            kind=q.get("kind", game_type.value),
            meta=q.get("meta", {}),
        )
        for q in bank[:take]
    ]
    if game_type is GameType.MARATHON:
        tl = MARATHON_TIME_LIMIT_S
    elif game_type is GameType.SPEED:
        tl = SPEED_TIME_LIMIT_S
    else:
        tl = 0
    return GameRound(subject=subject, game_type=game_type, age_group=age_group,
                     locale=loc, mcqs=mcqs, time_limit_s=tl)


def score_round(rnd: GameRound, answers: Dict[str, object],
                *, elapsed_s: Optional[float] = None) -> ScoreResult:
    """Score a submission. ``answers`` maps item/term id -> chosen index or option id."""
    results: List[ItemResult] = []
    if rnd.game_type is GameType.MATCH:
        total = len(rnd.pairs)
        correct = 0
        for p in rnd.pairs:
            chosen = answers.get(p.id)
            ok = str(chosen) == p.id  # correct option shares the term's id
            correct += 1 if ok else 0
            results.append(ItemResult(id=p.id, correct=ok, explain=f"{p.term} → {p.match}"))
    else:
        total = len(rnd.mcqs)
        correct = 0
        for m in rnd.mcqs:
            chosen = answers.get(m.id)
            ok = chosen is not None and int(chosen) == m.answer_index
            correct += 1 if ok else 0
            results.append(ItemResult(id=m.id, correct=ok,
                                      answer_index=m.answer_index, explain=m.explain))

    accuracy = round(correct / total, 3) if total else 0.0
    base = correct * 10
    accuracy_bonus = 20 if total and correct == total else 0
    speed_bonus = 0
    if rnd.game_type is GameType.SPEED and base > 0 and rnd.time_limit_s > 0 \
            and elapsed_s is not None and elapsed_s < rnd.time_limit_s:
        frac_left = max(0.0, 1.0 - (elapsed_s / rnd.time_limit_s))
        speed_bonus = int(round(base * frac_left * 0.5))
    marathon_bonus = 0
    if rnd.game_type is GameType.MARATHON and correct >= 3:
        marathon_bonus = correct * 5 + (10 if correct == total else 0)
    points = base + accuracy_bonus + speed_bonus + marathon_bonus
    return ScoreResult(
        game_id=rnd.game_id, subject=rnd.subject, game_type=rnd.game_type,
        correct=correct, total=total, accuracy=accuracy, base_points=base,
        speed_bonus=speed_bonus, accuracy_bonus=accuracy_bonus, points=points,
        results=results,
    )


def games_catalog(*, locale: Optional[str] = None) -> dict:
    from .games_i18n import localized_catalog_game_types, localized_subjects
    from .languages import SUPPORTED_LANGUAGES

    base_types = [
        {"id": GameType.QUIZ.value, "name": "Quiz", "desc": "Pick the correct answer."},
        {"id": GameType.SPEED.value, "name": "Speed Round", "desc": "Beat the clock for a bonus."},
        {"id": GameType.MATCH.value, "name": "Match", "desc": "Match terms to definitions."},
        {"id": GameType.MARATHON.value, "name": "Marathon", "desc": "20+ questions, streak bonuses, 3 min timer."},
        {"id": GameType.TILES.value, "name": "Word Tiles", "desc": "Build words from letter tiles (Bananagrams-style)."},
        {"id": GameType.RESOURCE.value, "name": "Resource Choices", "desc": "Choose wisely with limited resources."},
        {"id": GameType.DEPENDENCY.value, "name": "Order & Dependencies", "desc": "Put steps in the right order."},
        {"id": GameType.RPG.value, "name": "Story RPG", "desc": "Role-play choices that teach real lessons."},
        {"id": GameType.CARTOON.value, "name": "Cartoon Clips", "desc": "Spot the moral or science idea in a scene."},
        {"id": GameType.IDIOM.value, "name": "Slang & Idioms", "desc": "Match expressions to their meanings."},
        {"id": GameType.CREATE.value, "name": "Create & ID", "desc": "Identify what was built or created."},
        {"id": GameType.DOING.value, "name": "Learn by Doing", "desc": "Practice skills step by step."},
        {"id": GameType.FARM.value, "name": "Farm Sim", "desc": "Grow crops and learn along the way."},
        {"id": GameType.SPELLING.value, "name": "Spelling", "desc": "Pick the correct spelling."},
        {"id": GameType.GEOMETRY.value, "name": "Geometry Play", "desc": "Shapes, angles, and spatial reasoning."},
    ]
    return {
        "subjects": GAME_SUBJECTS,
        "subjects_localized": localized_subjects(GAME_SUBJECTS, locale),
        "age_groups": AGE_GROUPS,
        "game_types": localized_catalog_game_types(base_types, locale),
        "locales": list(SUPPORTED_LANGUAGES),
    }
