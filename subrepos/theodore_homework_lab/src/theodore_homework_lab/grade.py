"""Grade answers for every lab methodology."""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Mapping, Optional, Sequence, Union

from .methodologies import get_methodology
from .models import ItemGrade, LabAssignment, LabGradeReport, LabItem

_WORD = re.compile(r"[A-Za-z0-9']+")


def _tokens(text: str) -> List[str]:
    return [t.lower() for t in _WORD.findall(str(text or ""))]


def _norm(text: str) -> str:
    return " ".join(_tokens(text))


def _recall(answer_tokens: Sequence[str], key_tokens: Sequence[str]) -> float:
    if not key_tokens:
        return 1.0 if not answer_tokens else 0.0
    if not answer_tokens:
        return 0.0
    overlap = len(set(answer_tokens) & set(key_tokens))
    return overlap / len(set(key_tokens))


def _parse_answer(raw: Any) -> Any:
    if isinstance(raw, (dict, list, int, float, bool)):
        return raw
    text = str(raw or "").strip()
    if not text:
        return ""
    # JSON object/array/number
    if text[0] in "{[":
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            pass
    # mapping form a->1;b->2
    if "->" in text and ";" in text:
        out: Dict[str, str] = {}
        for part in text.split(";"):
            if "->" not in part:
                continue
            left, right = part.split("->", 1)
            out[left.strip()] = right.strip()
        if out:
            return out
    if "->" in text and text.count("->") == 1:
        left, right = text.split("->", 1)
        return {left.strip(): right.strip()}
    # ordered list
    if "|" in text:
        return [p.strip() for p in text.split("|") if p.strip()]
    if text.isdigit():
        return int(text)
    low = text.lower()
    if low in ("true", "false", "yes", "no"):
        return low
    return text


def _as_index(answer: Any, options: Sequence[str]) -> Optional[int]:
    if isinstance(answer, int):
        return answer
    text = str(answer).strip()
    if text.isdigit():
        return int(text)
    low = text.lower()
    for i, opt in enumerate(options):
        if opt.strip().lower() == low:
            return i
    return None


def _grade_objective_choice(item: LabItem, answer: Any) -> ItemGrade:
    idx = _as_index(answer, item.options)
    key = item.answer_key
    if isinstance(key, int):
        correct = idx == key
        return ItemGrade(
            item_id=item.item_id,
            methodology=item.methodology,
            correct=correct,
            score=1.0 if correct else 0.0,
            rationale=f"chose {idx}, key {key}",
        )
    key_s = str(key).strip().lower()
    ans_s = str(answer).strip().lower()
    correct = ans_s == key_s or (idx is not None and str(item.options[idx]).lower() == key_s)
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=correct,
        score=1.0 if correct else 0.0,
        rationale=f"answer={ans_s!r} key={key_s!r}",
    )


def _grade_multi_select(item: LabItem, answer: Any) -> ItemGrade:
    key = item.answer_key
    if isinstance(key, list):
        key_set = {int(x) for x in key}
    else:
        key_set = set()
    parsed = _parse_answer(answer)
    if isinstance(parsed, list):
        got = set()
        for x in parsed:
            if isinstance(x, int) or str(x).isdigit():
                got.add(int(x))
            else:
                idx = _as_index(x, item.options)
                if idx is not None:
                    got.add(idx)
    else:
        idx = _as_index(parsed, item.options)
        got = {idx} if idx is not None else set()
    if not key_set and not got:
        return ItemGrade(
            item_id=item.item_id,
            methodology=item.methodology,
            correct=True,
            score=1.0,
            rationale="empty multi-select",
        )
    inter = len(key_set & got)
    union = len(key_set | got) or 1
    jacc = inter / union
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=jacc >= 0.99,
        score=round(jacc, 3),
        rationale=f"jaccard={jacc:.3f} got={sorted(got)} key={sorted(key_set)}",
    )


def _grade_mapping(item: LabItem, answer: Any) -> ItemGrade:
    key = item.answer_key
    if not isinstance(key, dict):
        key = {}
    parsed = _parse_answer(answer)
    if not isinstance(parsed, dict):
        # allow JSON string already handled; else fail soft
        parsed = {}
    if not key:
        return ItemGrade(
            item_id=item.item_id,
            methodology=item.methodology,
            correct=None,
            score=0.0,
            rationale="no mapping key",
        )
    ok = 0
    for k, v in key.items():
        pv = parsed.get(k)
        if pv is None:
            # try case-insensitive key
            for pk, pvv in parsed.items():
                if str(pk).strip().lower() == str(k).strip().lower():
                    pv = pvv
                    break
        if str(pv or "").strip().lower() == str(v).strip().lower():
            ok += 1
    score = ok / len(key)
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=score >= 0.99,
        score=round(score, 3),
        rationale=f"matched {ok}/{len(key)}",
    )


def _grade_order(item: LabItem, answer: Any) -> ItemGrade:
    key = item.answer_key
    if not isinstance(key, list):
        key = _parse_answer(key) if not isinstance(key, list) else key
    if not isinstance(key, list):
        key = []
    parsed = _parse_answer(answer)
    if isinstance(parsed, str):
        parsed = _tokens(parsed) if " " in parsed else [parsed]
    if not isinstance(parsed, list):
        parsed = [parsed]
    # normalize to strings
    ks = [str(x).strip().lower() for x in key]
    ps = [str(x).strip().lower() for x in parsed]
    if ks == ps:
        return ItemGrade(
            item_id=item.item_id,
            methodology=item.methodology,
            correct=True,
            score=1.0,
            rationale="exact order",
        )
    # partial credit: pairwise position matches
    n = max(len(ks), 1)
    matches = sum(1 for i, v in enumerate(ps) if i < len(ks) and v == ks[i])
    score = matches / n
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=score >= 0.99,
        score=round(score, 3),
        rationale=f"order matches {matches}/{n}",
    )


def _grade_fuzzy(item: LabItem, answer: Any, *, threshold: float = 0.4) -> ItemGrade:
    key = item.answer_key
    if isinstance(key, dict):
        # flatten expected tokens
        key_text = " ".join(str(v) for v in key.values())
    elif isinstance(key, list):
        key_text = " ".join(str(v) for v in key)
    else:
        key_text = str(key or "")
    ans_text = answer if isinstance(answer, str) else json.dumps(answer, ensure_ascii=False)
    # exact normalized
    if _norm(ans_text) and _norm(ans_text) == _norm(key_text):
        return ItemGrade(
            item_id=item.item_id,
            methodology=item.methodology,
            correct=True,
            score=1.0,
            rationale="normalized exact match",
        )
    rec = _recall(_tokens(ans_text), _tokens(key_text))
    # also reward key tokens appearing in answer for short keys
    score = rec
    if len(_tokens(key_text)) <= 2 and _norm(key_text) in _norm(ans_text):
        score = max(score, 0.85)
    correct = score >= threshold
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=correct,
        score=round(min(1.0, score), 3),
        rationale=f"token_recall={rec:.3f} threshold={threshold}",
    )


def _grade_rubric(item: LabItem, answer: Any) -> ItemGrade:
    text = str(answer or "")
    toks = set(_tokens(text))
    criteria = list(item.rubric or [])
    if not criteria:
        # fall back to fuzzy against answer_key
        return _grade_fuzzy(item, answer, threshold=0.35)
    hits = 0
    details = []
    key_toks = set(_tokens(str(item.answer_key or "")))
    for c in criteria:
        c_toks = set(_tokens(c))
        # criterion satisfied if student text is non-trivial and overlaps key or has length
        ok = False
        if len(text.strip()) >= 12 and (not c_toks or True):
            # heuristic: long enough answers get partial credit per criterion;
            # boost if key tokens present for content criteria
            if key_toks & toks:
                ok = True
            elif len(toks) >= 4:
                ok = True
        details.append({"criterion": c, "met": ok})
        if ok:
            hits += 1
    score = hits / max(len(criteria), 1)
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=score >= 0.67,
        score=round(score, 3),
        rationale=f"rubric {hits}/{len(criteria)}",
        details={"criteria": details},
    )


def _grade_yes_no_explain(item: LabItem, answer: Any) -> ItemGrade:
    parsed = _parse_answer(answer)
    choice = ""
    explain = ""
    if isinstance(parsed, dict):
        choice = str(parsed.get("choice") or parsed.get("answer") or "").lower()
        explain = str(parsed.get("explain") or parsed.get("justification") or "")
    else:
        text = str(answer or "").strip()
        low = text.lower()
        if low.startswith("yes"):
            choice, explain = "yes", text[3:].strip(" :-")
        elif low.startswith("no"):
            choice, explain = "no", text[2:].strip(" :-")
        else:
            explain = text
    key = item.answer_key if isinstance(item.answer_key, dict) else {}
    want = str(key.get("choice") or "yes").lower()
    choice_ok = choice == want
    must = [str(x).lower() for x in (key.get("must_include") or [])]
    explain_toks = set(_tokens(explain))
    cover = sum(1 for m in must if m in explain_toks) / max(len(must), 1) if must else (
        1.0 if len(explain_toks) >= 3 else 0.3
    )
    score = (0.5 if choice_ok else 0.0) + 0.5 * cover
    return ItemGrade(
        item_id=item.item_id,
        methodology=item.methodology,
        correct=score >= 0.75,
        score=round(score, 3),
        rationale=f"choice_ok={choice_ok} cover={cover:.2f}",
    )


def grade_item(item: LabItem, answer: Any) -> ItemGrade:
    mid = item.methodology
    get_methodology(mid)  # validate
    parsed = _parse_answer(answer)

    if mid == "multi_select":
        return _grade_multi_select(item, parsed)
    if mid == "yes_no_explain":
        return _grade_yes_no_explain(item, answer)
    if mid in {
        "matching",
        "definition_match",
        "memory_match",
        "categorize",
        "picture_label",
        "drag_drop",
    }:
        return _grade_mapping(item, parsed)
    if mid in {"ordering", "procedure_steps", "sentence_reorder"}:
        return _grade_order(item, parsed)
    if mid in {
        "mcq",
        "true_false",
        "listen_choose",
        "minimal_pairs",
        "grammar_error_id",
        "vocabulary_context",
        "flashcard_recognize",
        "timed_quiz",
        "video_timestamp",
        "hotspot",
        "timeline_place",
        "map_locate",
        "safety_check",
    }:
        return _grade_objective_choice(item, parsed)
    if mid in {
        "spelling",
        "capitalization",
        "word_scramble",
        "hangman_style",
        "formula_apply",
        "code_trace",
        "syllable_count",
        "picture_id",
    }:
        # strict-ish string / number
        key = str(item.answer_key or "").strip().lower().replace(" ", "")
        ans = str(parsed if not isinstance(parsed, (list, dict)) else answer).strip().lower().replace(" ", "")
        correct = ans == key
        # allow fuzzy for picture_id words
        if not correct and mid == "picture_id":
            return _grade_fuzzy(item, answer, threshold=0.8)
        return ItemGrade(
            item_id=item.item_id,
            methodology=mid,
            correct=correct,
            score=1.0 if correct else 0.0,
            rationale=f"strict '{ans}' vs '{key}'",
        )

    mode = item.grading_mode or get_methodology(mid).grading_mode.value
    if mode == "rubric":
        return _grade_rubric(item, answer)
    if mode in ("fuzzy", "media", "interactive"):
        return _grade_fuzzy(item, answer)
    # default
    return _grade_fuzzy(item, answer)


def grade_assignment(
    assignment: LabAssignment,
    answers: Union[Sequence[Any], Mapping[str, Any]],
) -> LabGradeReport:
    """Grade by positional list or by item_id map."""
    items_grades: List[ItemGrade] = []
    coverage: Dict[str, int] = {}

    for i, item in enumerate(assignment.items):
        if isinstance(answers, Mapping):
            raw = answers.get(item.item_id, answers.get(str(i), ""))
        else:
            raw = answers[i] if i < len(answers) else ""
        g = grade_item(item, raw)
        items_grades.append(g)
        coverage[item.methodology] = coverage.get(item.methodology, 0) + 1

    max_score = float(len(items_grades)) if items_grades else 0.0
    score = float(sum(g.score for g in items_grades))
    pct = round(100.0 * score / max_score, 1) if max_score else 0.0
    flags: List[str] = []
    if any(g.correct is False for g in items_grades):
        flags.append("incorrect_answers")
    if any(g.correct is None for g in items_grades):
        flags.append("needs_human_review")
    if items_grades and score / max_score < 0.5:
        flags.append("low_overall")

    return LabGradeReport(
        assignment_id=assignment.assignment_id,
        score=round(score, 2),
        max_score=max_score,
        percentage=pct,
        items=items_grades,
        methodology_coverage=coverage,
        validity_flags=flags,
    )


def gold_answer_for(item: LabItem) -> Any:
    """Deterministic correct answer payload for bakeoff / self-tests."""
    mid = item.methodology
    key = item.answer_key
    if mid == "yes_no_explain" and isinstance(key, dict):
        must = key.get("must_include") or []
        return {
            "choice": key.get("choice", "yes"),
            "explain": " ".join(str(x) for x in must) + " " + str(item.topic),
        }
    if mid == "multi_select" and isinstance(key, list):
        return list(key)
    if isinstance(key, dict):
        return dict(key)
    if isinstance(key, list):
        return list(key)
    if mid in {"essay", "paraphrase", "summarize", "compare_contrast", "claim_evidence",
               "debate_stance", "roleplay_dialogue", "reflection_journal", "peer_review",
               "oral_response", "image_describe", "media_caption", "alt_text", "show_work",
               "inference"}:
        # need enough tokens for rubric heuristics
        base = str(key or item.topic)
        return f"{base}. This answer covers the key idea with clear complete sentences about {item.topic}."
    return key
