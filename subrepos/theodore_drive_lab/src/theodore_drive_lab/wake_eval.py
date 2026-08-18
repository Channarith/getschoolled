"""Python port of Drive Mode wake / command parsing (mirrors voiceCommands.ts)."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from .drive_tuning import DriveTuning

_WAKE_RE = re.compile(r"\b(hey\s+sala(?:reen)?|salareen|sala)\b", re.I)
_QUESTION_STARTERS = re.compile(
    r"^(what'?s?|why|how|when|where|who|whom|whose|which|can|could|would|will|"
    r"do|does|did|is|are|am|should|shall|may|might|have|has|had|explain|define|"
    r"describe|tell me|help me|i (?:don'?t|do not) (?:understand|get))\b",
    re.I,
)
_DATA = Path(__file__).resolve().parents[2] / "data" / "wake_utterances.jsonl"


def has_wake_word(text: str) -> bool:
    return bool(_WAKE_RE.search(text or ""))


def strip_wake_words(text: str) -> str:
    t = text or ""
    t = re.sub(r"\bhey\s+sala(?:reen)?\b", "", t, flags=re.I)
    t = re.sub(r"\bsalareen\b", "", t, flags=re.I)
    t = re.sub(r"\bsala\b", "", t, flags=re.I)
    return t.strip()


def extract_after_wake(text: str) -> Optional[str]:
    m = _WAKE_RE.search(text or "")
    if not m:
        return None
    return re.sub(r"^[\s,.:;!?-]+", "", (text or "")[m.end() :]).strip()


def is_question(text: str) -> bool:
    t = (text or "").strip()
    if not t:
        return False
    if t.endswith("?"):
        return True
    return bool(_QUESTION_STARTERS.search(t))


def classify_command(text: str) -> dict:
    t = (text or "").strip().lower()
    if not t:
        return {"kind": "none"}
    # Boundary that works for Latin AND scripts where \b fails (Devanagari, etc.).
    b = r"(?:^|[\s,.:;!?¿¡\"\'()\[\]{}|/\\-]+)"
    e = r"(?:$|[\s,.:;!?¿¡\"\'()\[\]{}|/\\-]+)"

    def has(*words: str) -> bool:
        return any(re.search(b + re.escape(w) + e, t, re.I) for w in words)

    # English plus common command glosses so Drive Mode works across the
    # platform's 26+ languages (wake word stays Sala / Salareen).
    if has(
        "pause", "stop", "hold on", "wait",
        "pausa", "pausar", "arrêter", "arrêt", "anhalten", "stopp",
        "parar", "pauzeren", "zatrzymaj", "пауза", "зупини",
        "duraklat", "توقف", "השהה", "रुको", "पाउज़", "বিরতি", "رکو", "مکث",
        "暂停", "一時停止", "일시정지", "tạm dừng", "หยุด", "jeda", "simama",
        "παύση", "pozastavit", "ផ្អាក",
    ):
        return {"kind": "pause"}
    if has(
        "resume", "continue", "keep going", "go on",
        "continuar", "reanudar", "reprendre", "fortsetzen", "weiter",
        "riprendi", "hervatten", "wznów", "продолжить", "продовжити",
        "devam", "استئناف", "המשך", "जारी", "চালিয়ে", "جاری", "ادامه",
        "继续", "再開", "계속", "tiếp tục", "ต่อ", "lanjut", "endelea",
        "συνέχεια", "pokračovat", "បន្ត",
    ):
        return {"kind": "resume"}
    if has(
        "next", "skip", "forward",
        "siguiente", "suivant", "nächste", "nächster", "prossimo", "próximo",
        "volgende", "następny", "следующий", "наступний",
        "sonraki", "التالي", "הבא", "अगला", "পরবর্তী", "اگلا", "بعدی",
        "下一个", "次", "다음", "tiếp", "ถัดไป", "berikutnya", "ijayo",
        "επόμενο", "další", "បន្ទាប់",
    ):
        return {"kind": "next"}
    if has(
        "previous", "back", "last one",
        "anterior", "précédent", "vorherige", "precedente",
        "vorige", "poprzedni", "предыдущий", "попередній",
        "önceki", "السابق", "הקודם", "पिछला", "পূর্ববর্তী", "پچھلا", "قبلی",
        "上一个", "前", "이전", "trước", "ก่อนหน้า", "sebelumnya", "iliyotangulia",
        "προηγούμενο", "předchozí", "មុន",
    ):
        return {"kind": "previous"}
    if has(
        "repeat", "say that again", "say it again", "one more time",
        "repetir", "répéter", "wiederholen", "ripeti", "herhaal",
        "powtórz", "повторить", "повторити",
        "tekrar", "كرر", "חזור", "दोहराओ", "আবার", "دہراؤ", "تکرار",
        "重复", "もう一度", "다시", "lặp lại", "ซ้ำ", "ulang", "rudia",
        "επανάλαβε", "opakovat", "ធ្វើម្តងទៀត",
    ):
        return {"kind": "repeat"}
    if is_question(t):
        return {"kind": "question", "text": text.strip()}
    return {"kind": "none"}


def parse_wake_utterance(text: str, *, wake_required: bool = True) -> dict:
    """Return command payload after wake gating."""
    raw = text or ""
    if wake_required:
        after = extract_after_wake(raw)
        if after is None:
            return {"kind": "none", "wake": False, "raw": raw}
        if not after:
            return {"kind": "none", "wake": True, "armed": True, "raw": raw}
        cmd = classify_command(after)
        cmd["wake"] = True
        cmd["raw"] = raw
        return cmd
    cmd = classify_command(strip_wake_words(raw) or raw)
    cmd["wake"] = has_wake_word(raw)
    cmd["raw"] = raw
    return cmd


def token_set(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9']+", (text or "").lower()) if t}


def is_likely_echo(utterance: str, last_tts: str, *, min_overlap: float) -> bool:
    """Detect narration bleed: learner mic heard what the agent just spoke."""
    a = token_set(utterance)
    b = token_set(last_tts)
    if not a or not b:
        return False
    overlap = len(a & b) / len(a)
    return overlap >= float(min_overlap)


@dataclass
class WakeCase:
    text: str
    expect_wake: bool
    expect_kind: str
    last_tts: str = ""
    expect_echo: bool = False

    @classmethod
    def from_dict(cls, row: dict) -> "WakeCase":
        return cls(
            text=str(row.get("text") or ""),
            expect_wake=bool(row.get("expect_wake", False)),
            expect_kind=str(row.get("expect_kind") or "none"),
            last_tts=str(row.get("last_tts") or ""),
            expect_echo=bool(row.get("expect_echo", False)),
        )


def load_wake_cases(path: Optional[Path] = None) -> List[WakeCase]:
    p = path or _DATA
    if not p.exists():
        return _builtin_cases()
    rows: List[WakeCase] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(WakeCase.from_dict(json.loads(line)))
    return rows or _builtin_cases()


def _builtin_cases() -> List[WakeCase]:
    return [
        WakeCase("hey sala pause", True, "pause"),
        WakeCase("salareen what is photosynthesis", True, "question"),
        WakeCase("what is photosynthesis", False, "none"),
        WakeCase("plants convert sunlight", False, "none", "Plants convert sunlight into energy.", True),
        WakeCase("hey sala next", True, "next"),
        WakeCase("hey sala resume", True, "resume"),
        WakeCase("hey sala repeat", True, "repeat"),
        WakeCase("sala previous", True, "previous"),
    ]


def evaluate_wake(cases: List[WakeCase], tuning: DriveTuning) -> dict:
    tp = fp = fn = tn = 0
    kind_ok = 0
    echo_ok = 0
    echo_n = 0
    details = []
    for case in cases:
        woke = has_wake_word(case.text)
        if case.expect_wake and woke:
            tp += 1
        elif case.expect_wake and not woke:
            fn += 1
        elif not case.expect_wake and woke:
            fp += 1
        else:
            tn += 1

        parsed = parse_wake_utterance(case.text, wake_required=tuning.wake_required)
        if case.expect_wake:
            if parsed.get("kind") == case.expect_kind or (
                case.expect_kind == "question" and parsed.get("kind") == "question"
            ):
                kind_ok += 1
        elif not case.expect_wake and parsed.get("kind") == "none":
            kind_ok += 1

        if case.last_tts:
            echo_n += 1
            echo = is_likely_echo(
                case.text, case.last_tts, min_overlap=tuning.echo_min_overlap
            )
            if echo == case.expect_echo:
                echo_ok += 1
            details.append({"text": case.text, "echo": echo, "expect_echo": case.expect_echo})

    precision = tp / max(1, tp + fp)
    recall = tp / max(1, tp + fn)
    kind_acc = kind_ok / max(1, len(cases))
    echo_acc = echo_ok / max(1, echo_n) if echo_n else 1.0
    # Blended drive wake quality.
    quality = 0.4 * precision + 0.4 * recall + 0.2 * echo_acc
    return {
        "n": len(cases),
        "wake_precision": round(precision, 4),
        "wake_recall": round(recall, 4),
        "kind_accuracy": round(kind_acc, 4),
        "echo_accuracy": round(echo_acc, 4),
        "wake_quality": round(quality, 4),
        "tp": tp,
        "fp": fp,
        "fn": fn,
        "tn": tn,
    }
