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


# Subjects the arcade supports (kept independent of the course catalog).
GAME_SUBJECTS: List[str] = [
    "biology", "chemistry", "physics", "math", "science",
    "history", "art", "technology", "programming",
]

SPEED_TIME_LIMIT_S = 45


class MCQItem(BaseModel):
    id: str
    prompt: str
    options: List[str]
    answer_index: int
    explain: str = ""


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


class GameRound(BaseModel):
    game_id: str = Field(default_factory=lambda: uuid.uuid4().hex[:12])
    subject: str
    game_type: GameType
    time_limit_s: int = 0
    mcqs: List[MCQItem] = Field(default_factory=list)
    pairs: List[MatchPair] = Field(default_factory=list)

    def public(self) -> dict:
        """Client-facing round with answers stripped."""
        out: dict = {
            "game_id": self.game_id, "subject": self.subject,
            "game_type": self.game_type.value, "time_limit_s": self.time_limit_s,
        }
        if self.game_type is GameType.MATCH:
            rng = random.Random(self.game_id)
            options = [{"id": p.id, "text": p.match} for p in self.pairs]
            rng.shuffle(options)
            out["terms"] = [{"id": p.id, "term": p.term} for p in self.pairs]
            out["options"] = options
        else:
            out["items"] = [{"id": m.id, "prompt": m.prompt, "options": m.options}
                            for m in self.mcqs]
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


def make_round(subject: str, game_type: GameType, *, n: int = 5,
               seed: Optional[int] = None) -> GameRound:
    subject = subject if subject in GAME_SUBJECTS else "science"
    rng = random.Random(seed)
    if game_type is GameType.MATCH:
        bank = _PAIR_BANK[subject][:]
        rng.shuffle(bank)
        pairs = [MatchPair(id=uuid.uuid4().hex[:8], term=t, match=m)
                 for t, m in bank[: max(2, min(n, len(bank)))]]
        return GameRound(subject=subject, game_type=game_type, pairs=pairs)
    bank = _MCQ_BANK[subject][:]
    rng.shuffle(bank)
    mcqs = [MCQItem(id=uuid.uuid4().hex[:8], **q) for q in bank[: max(1, min(n, len(bank)))]]
    tl = SPEED_TIME_LIMIT_S if game_type is GameType.SPEED else 0
    return GameRound(subject=subject, game_type=game_type, mcqs=mcqs, time_limit_s=tl)


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
    points = base + accuracy_bonus + speed_bonus
    return ScoreResult(
        game_id=rnd.game_id, subject=rnd.subject, game_type=rnd.game_type,
        correct=correct, total=total, accuracy=accuracy, base_points=base,
        speed_bonus=speed_bonus, accuracy_bonus=accuracy_bonus, points=points,
        results=results,
    )


def games_catalog() -> dict:
    return {
        "subjects": GAME_SUBJECTS,
        "game_types": [
            {"id": GameType.QUIZ.value, "name": "Quiz", "desc": "Pick the correct answer."},
            {"id": GameType.SPEED.value, "name": "Speed Round", "desc": "Beat the clock for a bonus."},
            {"id": GameType.MATCH.value, "name": "Match", "desc": "Match terms to definitions."},
        ],
    }
