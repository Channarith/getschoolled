"""Data-quality gate for training sessions.

Every session must pass before it can reach a fine-tune:
  - source + consent are present and acceptable (authored content, or opt-in class data;
    children's data needs guardian opt-in);
  - language is a known tag;
  - no protected attribute (race, ethnicity) anywhere: keys, audience, tags;
  - personal data is scrubbed (emails, phone numbers, SSNs, card numbers, secret-bearing URLs)
    or the session is dropped;
  - exact and near duplicates are removed (same question or same answer, ignoring case,
    spacing and punctuation);
  - sizes are sane.

Pure Python, no torch. Used by training/quality_gate.py and spark_nightly.sh.
"""

from __future__ import annotations

import re
import unicodedata
from typing import Dict, Iterable, List, Tuple

PROTECTED_KEYS = {"race", "ethnicity", "ethnic_group", "skin_color"}
KNOWN_LANGUAGES = {
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "uk", "ru", "tr", "ar", "he", "fa", "ur", "hi",
    "bn", "id", "vi", "th", "km", "zh", "ja", "ko", "sw", "el", "cs",
}
CONSENT_OK = {"authored", "opt-in", "guardian-opt-in", "staff-reviewed"}
MAX_STUDENT_CHARS = 4000
MAX_TEACHER_CHARS = 4000
MIN_TEACHER_CHARS = 3
LONG_ANSWER_CHARS = 120

_EMAIL = re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")
_PHONE = re.compile(r"(?<!\d)(?:\+?\d{1,3}[\s.\-]?)?(?:\(\d{2,4}\)|\d{2,4})[\s.\-]?\d{3,4}[\s.\-]?\d{3,4}(?!\d)")
_SSN = re.compile(r"(?<!\d)\d{3}-\d{2}-\d{4}(?!\d)")
_CARD = re.compile(r"(?<!\d)(?:\d[ \-]?){13,19}(?!\d)")
_SECRET_URL = re.compile(r"https?://\S*(?:token|key|secret|password|session)=\S+", re.I)
_PASSWORD = re.compile(r"(?:password|passcode|pin)\s*(?:is|:|=)\s*\S+", re.I)


def _luhn(digits: str) -> bool:
    total = 0
    for i, ch in enumerate(reversed(digits)):
        n = int(ch)
        if i % 2 == 1:
            n = n * 2 - 9 if n * 2 > 9 else n * 2
        total += n
    return total % 10 == 0


def _part_of_longer_number(text: str, m: "re.Match") -> bool:
    """A phone-shaped match that continues into more digits is some other number, not a phone."""
    return bool(re.match(r"[\s.\-]?\d", text[m.end():]) or re.search(r"\d[\s.\-]?$", text[:m.start()]))


def _is_phone(text: str, m: "re.Match") -> bool:
    digits = len(re.sub(r"\D", "", m.group(0)))
    return 9 <= digits <= 15 and not _part_of_longer_number(text, m)  # E.164 tops out at 15 digits


def find_pii(text: str) -> List[str]:
    kinds: List[str] = []
    if _EMAIL.search(text):
        kinds.append("email")
    if _SSN.search(text):
        kinds.append("ssn")
    for m in _CARD.finditer(text):
        digits = re.sub(r"\D", "", m.group(0))
        if 13 <= len(digits) <= 19 and _luhn(digits):
            kinds.append("card")
            break
    if _SECRET_URL.search(text):
        kinds.append("secret_url")
    if _PASSWORD.search(text):
        kinds.append("password")
    for m in _PHONE.finditer(text):
        if _is_phone(text, m):
            kinds.append("phone")
            break
    return kinds


def scrub_pii(text: str) -> str:
    text = _EMAIL.sub("[EMAIL]", text)
    text = _SSN.sub("[SSN]", text)
    text = _SECRET_URL.sub("[LINK]", text)
    text = _PASSWORD.sub("[SECRET]", text)

    def card(m: re.Match) -> str:
        digits = re.sub(r"\D", "", m.group(0))
        return "[CARD]" if 13 <= len(digits) <= 19 and _luhn(digits) else m.group(0)

    text = _CARD.sub(card, text)

    def phone(m: re.Match) -> str:
        return "[PHONE]" if _is_phone(m.string, m) else m.group(0)

    return _PHONE.sub(phone, text)


def _norm_key(text: str) -> str:
    text = unicodedata.normalize("NFKC", text or "").casefold()
    text = "".join(ch for ch in text if unicodedata.category(ch)[0] in ("L", "M", "N") or ch.isspace())
    return " ".join(text.split())


def _walk_keys(obj) -> Iterable[str]:
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield str(k).lower()
            yield from _walk_keys(v)
    elif isinstance(obj, list):
        for v in obj:
            yield from _walk_keys(v)


def check_session(session: dict) -> Tuple[List[str], List[str]]:
    """Return (hard_problems, drop_reasons). Hard problems fail the whole run."""
    hard: List[str] = []
    drop: List[str] = []
    leaked = sorted(set(_walk_keys(session)) & PROTECTED_KEYS)
    if leaked:
        hard.append(f"protected attribute key(s) present: {leaked}")
    tags = [str(t).lower() for t in (session.get("tags") or [])]
    if any(t in PROTECTED_KEYS for t in tags):
        hard.append("protected attribute used as a tag")

    source = str(session.get("source") or "").strip()
    consent = str(session.get("consent") or "").strip()
    audience = session.get("audience") or {}
    if not source:
        drop.append("no_source")
    if consent not in CONSENT_OK:
        drop.append("no_consent")
    elif str(audience.get("age_band", "")).lower() == "child" and consent not in ("guardian-opt-in", "authored"):
        drop.append("child_without_guardian_consent")
    elif source and not source.startswith("authored") and not source.startswith("mt-") and consent == "authored":
        drop.append("authored_consent_on_non_authored_source")

    language = str(audience.get("language") or "en")
    if language not in KNOWN_LANGUAGES:
        drop.append("unknown_language")

    turns = session.get("turns") or []
    if len(turns) < 2:
        drop.append("too_few_turns")
    else:
        student, teacher = str(turns[0].get("text", "")), str(turns[1].get("text", ""))
        if not student.strip():
            drop.append("empty_student")
        if len(teacher.strip()) < MIN_TEACHER_CHARS:
            drop.append("empty_teacher")
        if len(student) > MAX_STUDENT_CHARS or len(teacher) > MAX_TEACHER_CHARS:
            drop.append("too_long")
    return hard, drop


def run_gate(sessions: List[dict], *, scrub: bool = True) -> Tuple[List[dict], Dict]:
    """Filter, scrub and dedupe. Returns (clean_sessions, report)."""
    report: Dict = {"in": len(sessions), "kept": 0, "dropped": {}, "scrubbed": 0, "hard": [], "by_language": {}}
    seen_q: set = set()
    seen_a: set = set()
    clean: List[dict] = []

    def drop(reason: str) -> None:
        report["dropped"][reason] = report["dropped"].get(reason, 0) + 1

    for index, session in enumerate(sessions):
        hard, reasons = check_session(session)
        if hard:
            report["hard"].extend(f"session {index}: {h}" for h in hard)
            continue
        if reasons:
            for r in reasons:
                drop(r)
            continue
        session = {**session, "turns": [dict(t) for t in session["turns"]]}
        pii_found = False
        for turn in session["turns"]:
            text = str(turn.get("text", ""))
            if find_pii(text):
                pii_found = True
                if scrub:
                    turn["text"] = scrub_pii(text)
                    if find_pii(turn["text"]):
                        pii_found = True
                    else:
                        pii_found = False
                        report["scrubbed"] += 1
        if pii_found:
            drop("pii")
            continue
        q = _norm_key(session["turns"][0]["text"])
        a = _norm_key(session["turns"][1]["text"])
        if q in seen_q:
            drop("duplicate_question")
            continue
        # Short canned replies (a polite refusal, an abstention) legitimately repeat; only
        # long identical answers count as duplicates.
        if len(a) >= LONG_ANSWER_CHARS and a in seen_a:
            drop("duplicate_answer")
            continue
        seen_q.add(q)
        seen_a.add(a)
        clean.append(session)
        lang = str((session.get("audience") or {}).get("language") or "en")
        report["by_language"][lang] = report["by_language"].get(lang, 0) + 1
    report["kept"] = len(clean)
    return clean, report
