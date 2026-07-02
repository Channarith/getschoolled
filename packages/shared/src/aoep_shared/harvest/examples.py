"""Extract and synthesize worked examples with concrete data — not meta placeholders."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

_EXAMPLE_CUE = re.compile(
    r"\b(for instance|consider|suppose|e\.g\.|such as|"
    r"worked example|sample problem)\b",
    re.I,
)
_META_EXAMPLE = re.compile(
    r"\b(an example of|example of an example|this is an example|"
    r"for example,? an example|tiny example|small example)\b",
    re.I,
)
_CONCRETE = re.compile(
    r"(?:"
    r"\d+\s*[+\-*/=]\s*\d+"           # 2 + 3, A + B = 10 style fragments
    r"|[A-Za-z]\s*[+\-]\s*[A-Za-z]\s*="  # A + B =
    r"|\d+\s*=\s*\d+"                 # x = 5
    r"|\[\s*\d"                       # list of numbers
    r")",
)
_CODE_BLOCK = re.compile(
    r"(?:^|\n)\s{2,}([^\n]+(?:\n\s{2,}[^\n]+)*)",
    re.MULTILINE,
)
_INLINE_CODE = re.compile(r"`([^`]+)`|(\b(?:for|while|def|if|print|import)\s+[^\n]{8,80})")


@dataclass
class WorkedExample:
    title: str
    body: str
    narration: str
    source: str  # "extracted" | "synthesized"
    concrete_data: str = ""


def _topic_key(title: str, subject: str, seed: str) -> str:
    return f"{subject}|{title}|{seed}".lower()


def _pick_index(key: str, n: int) -> int:
    if n <= 0:
        return 0
    digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
    return int(digest[:8], 16) % n


def _is_meta_example_prose(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return True
    if _META_EXAMPLE.search(t):
        return True
    if t.lower().count("example") >= 2:
        return True
    if _CONCRETE.search(t):
        return False
    if len(t) > 80 and not re.search(r"\d", t):
        return True
    return False


def _code_blocks(text: str) -> List[str]:
    blocks: List[str] = []
    for m in _CODE_BLOCK.finditer(text or ""):
        block = re.sub(r"\n\s+", "\n  ", m.group(1).strip())
        if len(block) >= 12:
            blocks.append(block)
    for m in _INLINE_CODE.finditer(text or ""):
        snippet = (m.group(1) or m.group(2) or "").strip()
        if len(snippet) >= 12:
            blocks.append(snippet)
    return blocks[:2]


def _concrete_sentences(text: str) -> List[str]:
    """Sentences that already contain numbers, code cues, or explicit setups."""
    out: List[str] = []
    for part in re.split(r"(?<=[.!?])\s+", text or ""):
        s = part.strip()
        if len(s) < 20:
            continue
        if _is_meta_example_prose(s):
            continue
        if _CONCRETE.search(s) or _EXAMPLE_CUE.search(s):
            out.append(s)
        elif re.search(r"\d", s) and len(s) >= 40:
            out.append(s)
    return out[:3]


# --------------------------------------------------------------------------- #
# Concrete synthesized problems (real numbers, real steps)
# --------------------------------------------------------------------------- #
_LINEAR_SYSTEMS: List[Tuple[List[str], Dict[str, str], str]] = [
    (
        ["A + B = 10", "A + C = 12", "B + C = 9"],
        {"A": "6.5", "B": "3.5", "C": "5.5"},
        "Add the first two equations: 2A + B + C = 22. Subtract the third: 2A = 13, so A = 6.5. "
        "Then B = 10 − 6.5 = 3.5 and C = 12 − 6.5 = 5.5. Check: 3.5 + 5.5 = 9.",
    ),
    (
        ["x + y = 7", "x − y = 3"],
        {"x": "5", "y": "2"},
        "Add the equations: 2x = 10, so x = 5. Substitute: 5 + y = 7, so y = 2.",
    ),
    (
        ["2m + n = 11", "m − n = 1"],
        {"m": "4", "n": "3"},
        "Add: 3m = 12, so m = 4. Then 4 + n = 11 gives n = 3.",
    ),
]

_ONE_VARIABLE: List[Tuple[str, List[str], str]] = [
    (
        "2x + 5 = 15",
        ["2x + 5 = 15", "2x = 10", "x = 5"],
        "Subtract 5 from both sides: 2x = 10. Divide by 2: x = 5. Check: 2(5)+5 = 15.",
    ),
    (
        "3a − 4 = 11",
        ["3a − 4 = 11", "3a = 15", "a = 5"],
        "Add 4: 3a = 15. Divide by 3: a = 5.",
    ),
    (
        "y/4 + 2 = 5",
        ["y/4 + 2 = 5", "y/4 = 3", "y = 12"],
        "Subtract 2: y/4 = 3. Multiply by 4: y = 12.",
    ),
]

_FRACTIONS: List[Tuple[str, List[str], str]] = [
    (
        "1/2 + 1/3",
        ["LCD = 6", "3/6 + 2/6 = 5/6"],
        "Common denominator 6: 1/2 = 3/6 and 1/3 = 2/6. Sum: 5/6.",
    ),
]

_DATA_STATS: List[Tuple[List[int], str, str]] = [
    ([12, 15, 18, 21], "mean = 16.5", "Sum = 66. Divide by 4 scores: mean = 16.5."),
    ([4, 8, 10, 16, 22], "median = 10", "Ordered list; middle value is 10."),
]

_ML_ROWS: List[Tuple[str, str, str]] = [
    (
        "hours_studied,passed\n1,0\n3,0\n5,1\n7,1\n9,1",
        "threshold near 5 hours",
        "At 5+ hours every label is 1; below 5, label is 0 — a clear decision boundary.",
    ),
]


def _format_system(eqs: List[str], sol: Dict[str, str]) -> str:
    lines = ["Given:"] + [f"  {i + 1}. {eq}" for i, eq in enumerate(eqs)]
    lines.append("Solution:")
    for k, v in sol.items():
        lines.append(f"  {k} = {v}")
    return "\n".join(lines)


def _synthesize_math(title: str, seed: str, key: str) -> WorkedExample:
    hay = f"{title} {seed}".lower()
    if any(w in hay for w in ("system", "two equation", "three unknown", "A + B", "simultaneous")):
        eqs, sol, walk = _LINEAR_SYSTEMS[_pick_index(key, len(_LINEAR_SYSTEMS))]
        data = "; ".join(eqs)
        body = _format_system(eqs, sol) + f"\n\nSteps:\n  {walk}"
        narr = f"Three concrete equations: {data}. {walk}"
        return WorkedExample(
            title=f"Worked: {eqs[0][:40]}",
            body=body,
            narration=narr,
            source="synthesized",
            concrete_data=data,
        )
    if any(w in hay for w in ("fraction", "ratio", "percent")):
        expr, steps, walk = _FRACTIONS[_pick_index(key, len(_FRACTIONS))]
        body = f"Compute: {expr}\n" + "\n".join(f"  {s}" for s in steps)
        return WorkedExample(
            title=f"Worked: {expr}",
            body=body,
            narration=f"Compute {expr}. {walk}",
            source="synthesized",
            concrete_data=expr,
        )
    expr, steps, walk = _ONE_VARIABLE[_pick_index(key, len(_ONE_VARIABLE))]
    body = "Solve:\n" + "\n".join(f"  {s}" for s in steps)
    return WorkedExample(
        title=f"Worked: {expr}",
        body=body,
        narration=f"Solve {expr}. {walk}",
        source="synthesized",
        concrete_data=expr,
    )


def _synthesize_data(title: str, seed: str, key: str) -> WorkedExample:
    values, result, walk = _DATA_STATS[_pick_index(key, len(_DATA_STATS))]
    data = ", ".join(str(v) for v in values)
    body = f"Data: [{data}]\n{result}\nSteps: {walk}"
    return WorkedExample(
        title=f"Worked: {result.split('=')[0].strip()} of [{data}]",
        body=body,
        narration=f"Using the values {data}. {walk}",
        source="synthesized",
        concrete_data=data,
    )


def _synthesize_ml(title: str, seed: str, key: str) -> WorkedExample:
    csv, label, walk = _ML_ROWS[_pick_index(key, len(_ML_ROWS))]
    body = f"Dataset:\n{csv}\n\nPattern: {label}\n{walk}"
    return WorkedExample(
        title="Worked: classify from study hours",
        body=body,
        narration=f"Look at the rows: {walk}",
        source="synthesized",
        concrete_data=label,
    )


def _synthesize_science(title: str, seed: str, key: str) -> WorkedExample:
    # Concrete stoichiometry-style mass balance
    reactants = "2H₂ + O₂ → 2H₂O"
    body = (
        f"Reaction: {reactants}\n"
        f"Given: 4 g H₂ (molar mass 2 g/mol) → 2 mol H₂\n"
        f"Need: 1 mol O₂ (32 g) for complete reaction\n"
        f"Produces: 2 mol H₂O (36 g water)"
    )
    narr = (
        "Balance 2H₂ + O₂ → 2H₂O. With 4 g hydrogen (2 mol), you need 32 g oxygen "
        "and you get 36 g water — every coefficient is a mole ratio you can calculate."
    )
    return WorkedExample(
        title="Worked: 4 g H₂ to H₂O",
        body=body,
        narration=narr,
        source="synthesized",
        concrete_data="4 g H₂ → 36 g H₂O",
    )


def _synthesize_general(title: str, seed: str, key: str) -> WorkedExample:
    """Fallback with a concrete scenario (names, counts, dates) — not 'an example of'."""
    idx = _pick_index(key, 3)
    scenarios = [
        (
            "Inventory check",
            "Shelf A holds 24 units, Shelf B holds 18. Total = 42. "
            "If you move 6 from A to B, A = 18 and B = 24 — totals stay 42.",
            "24 + 18 = 42; after moving 6: 18 + 24 = 42.",
        ),
        (
            "Schedule block",
            "Meeting 9:00–10:30 (90 min), break 10:30–10:45 (15 min), "
            "work block 10:45–12:15 (90 min). Total focused time: 180 min.",
            "90 + 90 = 180 minutes of work; 15-minute break between.",
        ),
        (
            "Budget line",
            "Revenue $1,200; costs $750 rent + $200 supplies = $950. "
            "Remaining: $1,200 − $950 = $250.",
            "$1,200 − $950 = $250 left.",
        ),
    ]
    label, body, data = scenarios[idx]
    return WorkedExample(
        title=f"Worked: {label}",
        body=body,
        narration=body.replace("\n", " "),
        source="synthesized",
        concrete_data=data,
    )


def _synthesize_example(title: str, seed: str, subject: str) -> WorkedExample:
    subj = (subject or "general").lower()
    key = _topic_key(title, subj, seed)
    if any(k in subj for k in ("math", "algebra", "calculus", "equation")):
        return _synthesize_math(title, seed, key)
    if any(k in subj for k in ("stat", "data", "probability")):
        return _synthesize_data(title, seed, key)
    if any(k in subj for k in ("ai", "ml", "machine", "pattern", "predict")):
        return _synthesize_ml(title, seed, key)
    if any(k in subj for k in ("bio", "science", "chem", "physics")):
        return _synthesize_science(title, seed, key)
    return _synthesize_general(title, seed, key)


def extract_worked_examples(
    text: str,
    title: str,
    *,
    subject: str = "general",
) -> List[WorkedExample]:
    """Return up to two teachable worked examples with concrete data."""
    examples: List[WorkedExample] = []
    for block in _code_blocks(text):
        body = f"Code trace:\n{block}\n\nLine-by-line: what variable changes after each step?"
        examples.append(WorkedExample(
            title=f"Worked: {title[:60]}",
            body=body,
            narration=f"Trace this code. {block[:220]}",
            source="extracted",
            concrete_data=block.split("\n")[0][:80],
        ))
    for sent in _concrete_sentences(text):
        examples.append(WorkedExample(
            title=f"Worked: {title[:60]}",
            body=f"Given:\n{sent}",
            narration=sent,
            source="extracted",
            concrete_data=sent[:120],
        ))
    if not examples:
        first_line = (text or "").split(".")[0][:120] or title
        examples.append(_synthesize_example(title, first_line, subject))
    return examples[:2]
