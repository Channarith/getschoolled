"""Song learning drills: quiz, memory, paraphrase, and whole-song sing check.

The music lab already lets a learner pronounce one line and ask about it. This
module covers the rest of a learning loop for a featured song:

* quiz — multiple-choice checks that the learner actually learned the words
* memory — recall a line (English ↔ target) without looking
* paraphrase — other natural ways to say the same line
* sing check — score every line of the song in English or the learner language

Everything is offline-first: lexicon + curated translations + difflib scoring.
An optional Grok call only widens the paraphrase list when ``XAI_API_KEY`` is set.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import urllib.error
import urllib.request
from typing import Any

from .ask_ai import _focus_line
from .catalog import Song, SongLine
from .lexicon import EXAMPLES, LEXICON, gloss, terms_in_line
from .pronounce import REC_LANG, score_attempt
from .sing import VOICE_TAGS, speakable
from .translations import (
    XAI_DEFAULT_MODEL,
    language_name,
    translate_line,
    translate_song,
    validate_language,
)

# Hand-authored alternate phrasings for common featured-song lines. Keys are
# lowercase folded English; values are natural English paraphrases a beginner
# can reuse. The learner language is then applied through the translation stack.
_PARAPHRASE_EN: dict[str, list[str]] = {
    "i go to work": ["I'm heading to work.", "I leave for work."],
    "i go to school": ["I'm going to school.", "I head to school."],
    "i say hello": ["I greet people.", "I say hi."],
    "please and thank you": ["Please — and thank you.", "Say please, then thank you."],
    "can you help me": ["Could you help me?", "Would you help me, please?"],
    "how much is this": ["What does this cost?", "What's the price of this?"],
    "i need a ticket": ["I'd like a ticket.", "Can I get a ticket?"],
    "i need a map": ["I'd like a map.", "Can I have a map?"],
    "come with us": ["Join us.", "Come along with us."],
    "hello friend how are you": [
        "Hi friend, how are you doing?",
        "Hello my friend — how are you?",
    ],
    "i am good yes me too": ["I'm fine — yes, me too.", "I'm well; yes, same here."],
    "wheels on the bus go round and round": [
        "The bus wheels turn round and round.",
        "The bus wheels keep spinning.",
    ],
    "hold my hand dont let go": [
        "Hold my hand and don't let go.",
        "Take my hand — don't let go.",
    ],
    "say it soft say it loud": [
        "Say it quietly, then say it loudly.",
        "Whisper it, then shout it.",
    ],
    "we can learn them now": [
        "We can learn these words now.",
        "Let's learn them right now.",
    ],
    "left and right up and down": [
        "Left, right, up, and down.",
        "To the left and right, up and down.",
    ],
    "this way that way": ["This way or that way.", "One way, then the other."],
    "near and far": ["Close by and far away.", "Nearby and far off."],
    "turn around and smile": ["Spin around and smile.", "Turn and give a smile."],
}


def _fold_key(text: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9 ]+", " ", (text or "").lower()).split())


def _stable_rng(seed: str) -> random.Random:
    digest = hashlib.sha256(seed.encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _unique_lines(song: Song) -> list[SongLine]:
    """Drop chorus repeats so a quiz does not ask the same line three times."""
    seen: set[str] = set()
    rows: list[SongLine] = []
    for line in song.lines:
        key = _fold_key(line.text)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(line)
    return rows


def _vocab_for_song(song: Song, language: str) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    seen: set[str] = set()
    for line in song.lines:
        for term in terms_in_line(line.text):
            if term in seen:
                continue
            target = gloss(term, language) if language != "en" else term
            if not target:
                continue
            seen.add(term)
            rows.append(
                {
                    "en": term,
                    "target": speakable(target) or target,
                    "example_en": EXAMPLES.get(term, ""),
                }
            )
    return rows


def _mcq_choices(
    correct: str, pool: list[str], rng: random.Random, *, n: int = 4
) -> list[str]:
    options = [correct]
    distractors = [c for c in pool if c and _fold_key(c) != _fold_key(correct)]
    rng.shuffle(distractors)
    for item in distractors:
        if item not in options:
            options.append(item)
        if len(options) >= n:
            break
    if len(options) < n:
        for term in LEXICON:
            if len(options) >= n:
                break
            if term not in options and _fold_key(term) != _fold_key(correct):
                options.append(term)
    rng.shuffle(options)
    return options[:n]


def build_quiz(
    song: Song,
    language: str = "es",
    *,
    count: int = 8,
    seed: str = "",
) -> dict[str, Any]:
    """Build a mixed multiple-choice quiz from the song's lines and vocabulary."""
    lang = validate_language(language)
    rng = _stable_rng(seed or f"{song.song_id}:{lang}:{count}")
    vocab = _vocab_for_song(song, lang)
    lines = _unique_lines(song)
    questions: list[dict[str, Any]] = []

    for row in vocab:
        if len(questions) >= count:
            break
        pool = [v["target"] for v in vocab]
        choices = _mcq_choices(row["target"], pool, rng)
        if len(choices) < 2:
            continue
        questions.append(
            {
                "id": f"vocab-en-{row['en']}",
                "kind": "vocab_en_to_target",
                "prompt": f"What does \"{row['en']}\" mean in {language_name(lang)}?",
                "prompt_en": f'What does "{row["en"]}" mean?',
                "choices": choices,
                "answer": row["target"],
                "hint": row.get("example_en") or f'From the song: "{row["en"]}".',
                "line_no": None,
            }
        )

    for row in vocab:
        if len(questions) >= count:
            break
        pool = [v["en"] for v in vocab]
        choices = _mcq_choices(row["en"], pool, rng)
        if len(choices) < 2:
            continue
        questions.append(
            {
                "id": f"vocab-tr-{row['en']}",
                "kind": "vocab_target_to_en",
                "prompt": f"Which English word matches \"{row['target']}\"?",
                "prompt_en": f'Which English word matches "{row["target"]}"?',
                "choices": choices,
                "answer": row["en"],
                "hint": row.get("example_en") or "",
                "line_no": None,
            }
        )

    if lang != "en":
        translated_pool: list[str] = []
        for line in lines:
            tr = translate_line(line, lang)["translation"]
            spoken = speakable(tr) or tr
            if spoken:
                translated_pool.append(spoken)
        for line in lines:
            if len(questions) >= count:
                break
            tr = translate_line(line, lang)["translation"]
            spoken = speakable(tr) or tr
            if not spoken or spoken == line.text:
                continue
            choices = _mcq_choices(spoken, translated_pool, rng)
            if len(choices) < 2:
                continue
            questions.append(
                {
                    "id": f"line-{line.line_no}",
                    "kind": "line_en_to_target",
                    "prompt": (
                        f'How do you say this line in {language_name(lang)}?\n'
                        f'"{line.text}"'
                    ),
                    "prompt_en": f'How do you say: "{line.text}"?',
                    "choices": choices,
                    "answer": spoken,
                    "hint": f"Section: {line.section or 'verse'}",
                    "line_no": line.line_no,
                }
            )

    rng.shuffle(questions)
    questions = questions[: max(1, min(count, len(questions) or 1))]
    public = [{k: v for k, v in q.items() if k != "answer"} for q in questions]
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "language": lang,
        "language_name": language_name(lang),
        "count": len(public),
        "questions": public,
        "answer_key": {q["id"]: q["answer"] for q in questions},
    }


def grade_quiz(
    song: Song,
    *,
    language: str,
    answers: dict[str, str],
    count: int = 8,
    seed: str = "",
) -> dict[str, Any]:
    """Re-build the same quiz (stable seed) and score the learner's answers."""
    lang = validate_language(language)
    built = build_quiz(
        song,
        lang,
        count=count,
        seed=seed or f"{song.song_id}:{lang}:{count}",
    )
    key = built["answer_key"]
    results = []
    correct = 0
    for question in built["questions"]:
        qid = question["id"]
        expected = key.get(qid, "")
        given = (answers.get(qid) or "").strip()
        ok = _fold_key(given) == _fold_key(expected) and bool(expected)
        if ok:
            correct += 1
        results.append({**question, "answer": expected, "given": given, "correct": ok})
    total = len(results) or 1
    score = int(round(100 * correct / total))
    return {
        "song_id": song.song_id,
        "language": built["language"],
        "language_name": built["language_name"],
        "score": score,
        "passed": score >= 60,
        "correct": correct,
        "total": len(results),
        "stars": 3 if score >= 85 else 2 if score >= 60 else 1 if score >= 1 else 0,
        "feedback": (
            "Excellent — you know this song's words."
            if score >= 85
            else "Solid — review the missed words, then try again."
            if score >= 60
            else "Keep practising — replay the song, then retake the quiz."
        ),
        "results": results,
    }


def build_memory_drill(
    song: Song,
    language: str = "es",
    *,
    direction: str = "en_to_target",
    count: int = 6,
    seed: str = "",
) -> dict[str, Any]:
    """Flashcard-style recall: show one side, ask the learner for the other."""
    lang = validate_language(language)
    direction = (direction or "en_to_target").strip().lower()
    if direction not in {"en_to_target", "target_to_en"}:
        raise ValueError("direction must be 'en_to_target' or 'target_to_en'")
    if lang == "en" and direction == "en_to_target":
        direction = "target_to_en"
    rng = _stable_rng(seed or f"mem:{song.song_id}:{lang}:{direction}:{count}")
    lines = list(_unique_lines(song))
    rng.shuffle(lines)
    cards: list[dict[str, Any]] = []
    for line in lines:
        if len(cards) >= count:
            break
        tr = translate_line(line, lang)
        target = speakable(tr["translation"]) or tr["translation"]
        if direction == "en_to_target":
            if not target or _fold_key(target) == _fold_key(line.text):
                continue
            prompt = line.text
            answer = target
            prompt_label = "English lyric"
            answer_label = language_name(lang)
        else:
            prompt = target or line.text
            answer = line.text
            prompt_label = language_name(lang)
            answer_label = "English"
        cards.append(
            {
                "id": f"mem-{line.line_no}",
                "line_no": line.line_no,
                "section": line.section,
                "prompt": prompt,
                "prompt_label": prompt_label,
                "answer_label": answer_label,
                "answer": answer,
                "hint": f"Section: {line.section or 'verse'} · line {line.line_no}",
            }
        )
    public = [{k: v for k, v in c.items() if k != "answer"} for c in cards]
    speak_lang = "en" if direction == "target_to_en" else lang
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "language": lang,
        "language_name": language_name(lang),
        "direction": direction,
        "count": len(public),
        "cards": public,
        "answer_key": {c["id"]: c["answer"] for c in cards},
        "recognition_lang": REC_LANG.get(speak_lang, "en-US"),
        "voice_tag": VOICE_TAGS.get(speak_lang, "en-US"),
    }


def grade_memory(
    song: Song,
    *,
    language: str,
    direction: str,
    answers: dict[str, str],
    count: int = 6,
    seed: str = "",
) -> dict[str, Any]:
    """Score typed/spoken memory answers with the same pronunciation scorer."""
    lang = validate_language(language)
    direction = (direction or "en_to_target").strip().lower()
    built = build_memory_drill(
        song,
        lang,
        direction=direction,
        count=count,
        seed=seed or f"mem:{song.song_id}:{lang}:{direction}:{count}",
    )
    key = built["answer_key"]
    results = []
    passed_n = 0
    total_score = 0
    for card in built["cards"]:
        cid = card["id"]
        expected = key.get(cid, "")
        given = (answers.get(cid) or "").strip()
        scored = score_attempt(expected, given)
        if scored["passed"]:
            passed_n += 1
        total_score += scored["score"]
        results.append(
            {
                **card,
                "answer": expected,
                "given": given,
                "score": scored["score"],
                "passed": scored["passed"],
                "missed_words": scored["missed_words"],
                "wrong_words": scored["wrong_words"],
                "feedback": scored["feedback"],
            }
        )
    total = len(results) or 1
    avg = int(round(total_score / total))
    return {
        "song_id": song.song_id,
        "language": built["language"],
        "language_name": built["language_name"],
        "direction": built["direction"],
        "score": avg,
        "passed": passed_n >= max(1, int(round(total * 0.6))),
        "correct": passed_n,
        "total": len(results),
        "stars": 3 if avg >= 85 else 2 if avg >= 60 else 1 if avg >= 1 else 0,
        "feedback": (
            "Great memory — you can recall this song's lines."
            if avg >= 85
            else "Good recall — cover the ones you missed and try again."
            if avg >= 60
            else "Replay the song once, then retry the memory cards."
        ),
        "results": results,
    }


def _offline_paraphrases(english: str, language: str) -> list[dict[str, str]]:
    """Curated English alternates, plus their translation when not English."""
    key = _fold_key(english)
    alts = list(_PARAPHRASE_EN.get(key, []))
    if not alts:
        clean = (english or "").strip().rstrip(".")
        if clean:
            if clean.lower().startswith("i "):
                alts.append("I'm " + clean[2:] + ".")
            alts.append(f"Another way: {clean}.")
    rows: list[dict[str, str]] = []
    for alt in alts[:4]:
        if language == "en":
            rows.append({"text": alt, "language": "en", "source": "curated"})
            continue
        fake = SongLine(line_no=0, text=alt, meaning_en=alt)
        tr = translate_line(fake, language)
        spoken = speakable(tr["translation"]) or tr["translation"]
        rows.append(
            {
                "text": spoken or alt,
                "english": alt,
                "language": language,
                "source": tr.get("tier") or "curated",
            }
        )
    return rows


def _xai_paraphrases(english: str, language: str) -> list[str]:
    api_key = os.getenv("XAI_API_KEY", "").strip()
    if not api_key:
        return []
    base = os.getenv("XAI_BASE_URL", "https://api.x.ai/v1").rstrip("/")
    model = os.getenv("XAI_MODEL", XAI_DEFAULT_MODEL).strip() or XAI_DEFAULT_MODEL
    try:
        timeout = float(os.getenv("XAI_TIMEOUT_S", "40") or 40)
    except ValueError:
        timeout = 40.0
    name = language_name(language)
    payload = {
        "model": model,
        "temperature": 0.4,
        "max_tokens": 220,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You help language learners. Give 3 short, natural alternate "
                    f"ways to say the same idea in {name}. One phrase per line. "
                    "No numbering, no quotes, no explanations. Keep beginner level."
                ),
            },
            {"role": "user", "content": english},
        ],
    }
    req = urllib.request.Request(
        f"{base}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = json.loads(resp.read().decode("utf-8"))
        text = str(body["choices"][0]["message"]["content"]).strip()
    except (urllib.error.URLError, OSError, ValueError, KeyError, IndexError):
        return []
    rows = []
    for raw in text.splitlines():
        line = re.sub(r"^[\-\*\d\.\)\s]+", "", raw).strip().strip("\"'")
        if line and _fold_key(line) != _fold_key(english):
            rows.append(line)
    return rows[:3]


def paraphrase_line(
    song: Song,
    *,
    line_no: int | None,
    language: str = "en",
    allow_llm: bool = True,
) -> dict[str, Any]:
    """Other natural ways to say the focus line, in the learner's language."""
    lang = validate_language(language)
    line = _focus_line(song, line_no)
    if line is None:
        raise ValueError("Song has no lines")
    translated = translate_line(line, lang)
    base = (
        speakable(translated["translation"]) or translated["translation"]
        if lang != "en"
        else line.text
    )
    alts = _offline_paraphrases(line.text, lang)
    provider = "curated"
    if allow_llm:
        fresh = _xai_paraphrases(line.text if lang == "en" else base, lang)
        if fresh:
            provider = "llm"
            for text in fresh:
                if any(_fold_key(text) == _fold_key(row["text"]) for row in alts):
                    continue
                alts.append({"text": text, "language": lang, "source": "llm"})
    primary = {
        "text": base,
        "language": lang,
        "source": "song",
        "english": line.text,
    }
    deduped = [primary]
    for row in alts:
        if _fold_key(row["text"]) == _fold_key(primary["text"]):
            continue
        deduped.append(row)
    return {
        "song_id": song.song_id,
        "line_no": line.line_no,
        "section": line.section,
        "text": line.text,
        "language": lang,
        "language_name": language_name(lang),
        "translation": translated["translation"],
        "alternatives": deduped[:5],
        "provider": provider,
        "voice_tag": VOICE_TAGS.get(lang, "en-US"),
        "recognition_lang": REC_LANG.get(lang, "en-US"),
        "prompt": (
            f"Try saying the same idea another way in {language_name(lang)}. "
            "Pick one alternative, or invent your own and check it."
        ),
    }


def check_song_singing(
    song: Song,
    *,
    language: str = "en",
    practice: str = "translation",
    lines: list[dict[str, Any]],
) -> dict[str, Any]:
    """Score a whole-song attempt — one heard string per lyric line."""
    lang = validate_language(language)
    mode = (practice or "translation").strip().lower()
    if mode not in {"english", "translation"}:
        raise ValueError("practice must be 'english' or 'translation'")
    if mode == "english":
        lang = "en"

    translation = translate_song(
        song, lang if mode == "translation" else "en", allow_llm=False
    )
    by_no = {int(row.get("line_no") or 0): str(row.get("heard") or "") for row in lines}
    results = []
    passed_n = 0
    total_score = 0
    for row in translation["lines"]:
        line_no = int(row["line_no"])
        target = row["text"] if mode == "english" else (row["translation"] or row["text"])
        target_speak = speakable(target) if mode == "translation" else target
        heard = by_no.get(line_no, "")
        scored = score_attempt(target_speak, heard)
        if scored["passed"]:
            passed_n += 1
        total_score += scored["score"]
        results.append(
            {
                "line_no": line_no,
                "section": row.get("section", ""),
                "target": target_speak,
                "target_display": target,
                "heard": heard,
                "score": scored["score"],
                "passed": scored["passed"],
                "missed_words": scored["missed_words"],
                "wrong_words": scored["wrong_words"],
                "verdict": scored["verdict"],
            }
        )
    total = len(results) or 1
    avg = int(round(total_score / total))
    coverage = sum(1 for r in results if r["heard"].strip())
    out_lang = lang if mode == "translation" else "en"
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "practice": mode,
        "language": out_lang,
        "language_name": language_name(out_lang),
        "voice_tag": VOICE_TAGS.get(out_lang, "en-US"),
        "recognition_lang": REC_LANG.get(out_lang, "en-US"),
        "line_count": total,
        "attempted": coverage,
        "correct": passed_n,
        "score": avg,
        "passed": passed_n >= max(1, int(round(total * 0.6)))
        and coverage >= max(1, total // 2),
        "stars": 3 if avg >= 85 else 2 if avg >= 60 else 1 if avg >= 1 else 0,
        "feedback": (
            f"You can sing this song in {language_name(out_lang)}!"
            if avg >= 85 and passed_n >= total * 0.8
            else "Strong run — polish the missed lines and try the full song again."
            if avg >= 60
            else "Keep going — practise line by line, then retry the whole song."
        ),
        "lines": results,
    }


def practice_menu(song: Song, language: str = "en") -> dict[str, Any]:
    """Catalogue of drills the player can open for this song."""
    lang = validate_language(language)
    return {
        "song_id": song.song_id,
        "title_en": song.title_en,
        "language": lang,
        "language_name": language_name(lang),
        "modes": [
            {
                "id": "pronounce",
                "title": "Say / sing this line",
                "blurb": "Hear a model, then speak or type the current verse for a score.",
            },
            {
                "id": "quiz",
                "title": "Test what you learned",
                "blurb": "Multiple-choice on vocabulary and line meanings from this song.",
            },
            {
                "id": "memory",
                "title": "Test your memory",
                "blurb": "See one side of a line, recall the other without peeking.",
            },
            {
                "id": "ask",
                "title": "Ask about the lyrics",
                "blurb": "Ask free-form questions about grammar, meaning, or pronunciation.",
            },
            {
                "id": "paraphrase",
                "title": "Other ways to say it",
                "blurb": "See alternate phrasings of this line, then try one yourself.",
            },
            {
                "id": "sing",
                "title": "Sing the whole song",
                "blurb": f"Sing every line in {language_name(lang)} and get a full-song score.",
            },
        ],
    }
