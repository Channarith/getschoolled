"""Rows for the tutoring truth curve.

Each scored answer records how well it stayed on the passage (groundedness),
whether it abstained, and a slot for a later human agree/disagree. The slot
stays null until a reviewer fills it. Nothing here issues a credential.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, Optional

_ABSTAIN_MARKERS = (
    "does not cover",
    "doesn't cover",
    "can't answer",
    "cannot answer",
    "don't want to guess",
    "do not want to guess",
    "not in this passage",
    "not covered",
)


def is_abstention(text: str) -> bool:
    folded = " ".join((text or "").lower().split())
    return any(marker in folded for marker in _ABSTAIN_MARKERS)


def passage_from_instruction(instruction: str) -> str:
    """Pull the passage out of a frozen-benchmark instruction, if it has one."""
    if "\n" not in (instruction or ""):
        return ""
    rest = instruction.split("\n", 1)[1]
    return rest.split("\n\n", 1)[0].strip()


def truth_fields(prediction: str, row: Dict) -> Dict:
    """Score one answer. ``human_agreement`` is left null on purpose."""
    from aoep_shared.groundedness import check_grounding

    passage = str(row.get("passage") or "") or passage_from_instruction(
        str(row.get("instruction") or "")
    )
    report = check_grounding(prediction, [passage] if passage else [])
    tags = [str(t) for t in (row.get("tags") or [])]
    expected = "abstain" in tags
    abstained = is_abstention(prediction)
    category = tags[0] if tags else None
    return {
        "id": row.get("id"),
        "category": category,
        "groundedness": report.groundedness,
        "hallucination_risk": report.hallucination_risk,
        "abstained": abstained,
        "abstain_expected": expected,
        "abstain_correct": abstained == expected,
        "human_agreement": None,
    }


def exam_fields(eval_path: str, adapter: str = "") -> Dict:
    """Label a truth-log row so later plots can separate exams and models."""
    name = Path(eval_path).name
    if name.startswith("eval_frozen_stem"):
        exam = "stem"
    elif name.startswith("eval_frozen"):
        exam = "frozen"
    else:
        exam = "split"
    return {"exam": exam, "model": "adapter" if adapter else "base"}


def append_truth_row(path: str, row: Dict) -> None:
    dest = Path(path)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, ensure_ascii=False) + "\n")


def record_human_agreement(path: str, item_id: str, agreed: Optional[bool]) -> int:
    """Fill ``human_agreement`` on existing rows with this id. Returns rows touched."""
    dest = Path(path)
    if not dest.is_file():
        return 0
    lines = []
    touched = 0
    for line in dest.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("id") == item_id and row.get("human_agreement") is None:
            row["human_agreement"] = agreed
            touched += 1
        lines.append(json.dumps(row, ensure_ascii=False))
    dest.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    return touched
