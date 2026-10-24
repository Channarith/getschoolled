"""Objective scoring for synthesized speech: ASR round-trip error rates and audio sanity checks.

Pure Python plus numpy for audio. No model is loaded here, so it runs and tests anywhere.

Round trip: synthesize text -> transcribe the audio -> compare with the source text. Low error means the
speech is intelligible in that language. It does NOT measure naturalness or voice quality: pair it with the
blind listening panel (panel.py). Khmer, Thai and Chinese are scored by character error rate (CER); the
space-separated languages by word error rate (WER).
"""
from __future__ import annotations

import unicodedata
import wave
from pathlib import Path

CER_LANGS = {"km", "th", "zh"}

_ZERO_WIDTH = dict.fromkeys(map(ord, "​‌‍⁠﻿"), None)


# ---- number words (digits in an ASR transcript become the words our reference sentences use) --------------

_EN_ONES = "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split()
_EN_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()
_ES_ONES = ("cero uno dos tres cuatro cinco seis siete ocho nueve diez once doce trece catorce quince dieciséis diecisiete "
            "dieciocho diecinueve veinte veintiuno veintidós veintitrés veinticuatro veinticinco veintiséis veintisiete "
            "veintiocho veintinueve").split()
_ES_TENS = "_ _ _ treinta cuarenta cincuenta sesenta setenta ochenta noventa".split()
_ES_HUNDREDS = "_ ciento doscientos trescientos cuatrocientos quinientos seiscientos setecientos ochocientos novecientos".split()
_ZH_DIGITS = "零一二三四五六七八九"


def num_words_en(n: int) -> str:
    if n < 20:
        return _EN_ONES[n]
    if n < 100:
        return _EN_TENS[n // 10] + ("" if n % 10 == 0 else "-" + _EN_ONES[n % 10])
    if n < 1000:
        return _EN_ONES[n // 100] + " hundred" + ("" if n % 100 == 0 else " " + num_words_en(n % 100))
    if n < 1_000_000:
        return num_words_en(n // 1000) + " thousand" + ("" if n % 1000 == 0 else " " + num_words_en(n % 1000))
    return str(n)


def num_words_es(n: int) -> str:
    if n < 30:
        return _ES_ONES[n]
    if n < 100:
        return _ES_TENS[n // 10] + ("" if n % 10 == 0 else " y " + _ES_ONES[n % 10])
    if n == 100:
        return "cien"
    if n < 1000:
        return _ES_HUNDREDS[n // 100] + ("" if n % 100 == 0 else " " + num_words_es(n % 100))
    if n < 1_000_000:
        head = "mil" if n // 1000 == 1 else num_words_es(n // 1000) + " mil"
        return head + ("" if n % 1000 == 0 else " " + num_words_es(n % 1000))
    return str(n)


def num_words_zh(n: int) -> str:
    if n < 10:
        return _ZH_DIGITS[n]
    if n < 20:
        return "十" + ("" if n == 10 else _ZH_DIGITS[n - 10])
    if n < 100:
        return _ZH_DIGITS[n // 10] + "十" + ("" if n % 10 == 0 else _ZH_DIGITS[n % 10])
    if n < 1000:
        rest = n % 100
        mid = "" if rest == 0 else ("零" + _ZH_DIGITS[rest] if rest < 10 else num_words_zh(rest))
        return _ZH_DIGITS[n // 100] + "百" + mid
    if n < 10000:
        rest = n % 1000
        mid = "" if rest == 0 else ("零" + num_words_zh(rest) if rest < 100 else num_words_zh(rest))
        return _ZH_DIGITS[n // 1000] + "千" + mid
    return str(n)


NUM_WORDS = {"en": num_words_en, "es": num_words_es, "zh": num_words_zh}


def spell_numbers(text: str, lang: str) -> tuple[str, bool]:
    """Replace digit runs by words for en/es/zh. Returns (text, had_unhandled_digits).

    For other languages digits are dropped and the flag is True, so a report can say the score ignored
    numerals in that sentence rather than pretending it handled them.
    """
    import re

    fn = NUM_WORDS.get(lang)
    unhandled = False

    def repl(m):
        nonlocal unhandled
        digits = m.group(0)
        if fn and len(digits) < 7:
            return " " + fn(int(digits)) + " "
        unhandled = True
        return " "

    return re.sub(r"\d+", repl, text), unhandled


# ---- normalization and error rates -------------------------------------------------------------------------

def normalize(text: str, lang: str) -> tuple[str, bool]:
    """Lowercase, spell numbers, drop punctuation and zero-width marks. Returns (text, digits_unhandled)."""
    form = "NFKC" if lang == "zh" else "NFC"
    text = unicodedata.normalize(form, text or "").translate(_ZERO_WIDTH).lower()
    text, unhandled = spell_numbers(text, lang)
    cleaned = []
    for ch in text:
        cat = unicodedata.category(ch)
        cleaned.append(" " if cat[0] in "PS" or ch.isspace() else ch)
    out = " ".join("".join(cleaned).split())
    if lang in CER_LANGS:
        out = out.replace(" ", "")
    return out, unhandled


def edit_distance(a: list, b: list) -> int:
    if not a:
        return len(b)
    if not b:
        return len(a)
    prev = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        cur = [i]
        for j, y in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (x != y)))
        prev = cur
    return prev[-1]


def error_rate(reference: str, hypothesis: str, lang: str) -> dict:
    ref, ref_unhandled = normalize(reference, lang)
    hyp, hyp_unhandled = normalize(hypothesis, lang)
    metric = "cer" if lang in CER_LANGS else "wer"
    r = list(ref) if metric == "cer" else ref.split()
    h = list(hyp) if metric == "cer" else hyp.split()
    edits = edit_distance(r, h)
    return {
        "metric": metric,
        "value": edits / len(r) if r else (0.0 if not h else 1.0),
        "edits": edits,
        "ref_len": len(r),
        "digits_ignored": bool(ref_unhandled or hyp_unhandled),
    }


# ---- audio sanity ------------------------------------------------------------------------------------------

# Plausible speaking rate, as units per second of audio (words for WER languages, characters for CER languages).
RATE_BOUNDS = {
    "en": ("words", 1.2, 4.8), "es": ("words", 1.5, 5.2), "vi": ("words", 2.0, 6.5), "sw": ("words", 1.0, 4.0), "hi": ("words", 1.5, 5.0),
    "zh": ("chars", 2.0, 8.5), "th": ("chars", 4.0, 18.0), "km": ("chars", 4.0, 18.0),
}


def read_wav(path: Path | str):
    """Return (samples float32 in [-1, 1], sample_rate). 16-bit PCM only; use soundfile for anything else."""
    import numpy as np

    with wave.open(str(path), "rb") as w:
        if w.getsampwidth() != 2:
            raise ValueError(f"{path}: only 16-bit PCM wav is supported by the scorer (got {8 * w.getsampwidth()}-bit)")
        rate, channels = w.getframerate(), w.getnchannels()
        data = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
    if channels > 1:
        data = data.reshape(-1, channels).mean(axis=1)
    return data, rate


def analyze_audio(path: Path | str, text: str, lang: str, silence_db: float = -45.0, frame_ms: float = 20.0) -> dict:
    import numpy as np

    x, rate = read_wav(path)
    n = len(x)
    duration = n / rate if rate else 0.0
    if n == 0:
        return {"duration_s": 0.0, "flags": ["empty"], "rate_per_s": None}
    peak = float(np.max(np.abs(x)))
    rms = float(np.sqrt(np.mean(x ** 2)))
    clipped = float(np.mean(np.abs(x) >= 0.999))
    frame = max(1, int(rate * frame_ms / 1000))
    usable = (n // frame) * frame
    frames = x[:usable].reshape(-1, frame) if usable else x.reshape(1, -1)
    level = 20 * np.log10(np.sqrt(np.mean(frames ** 2, axis=1)) + 1e-9)
    loud = level > silence_db
    if loud.any():
        first, last = int(np.argmax(loud)), int(len(loud) - 1 - np.argmax(loud[::-1]))
        lead = first * frame_ms / 1000
        trail = (len(loud) - 1 - last) * frame_ms / 1000
        inner = ~loud[first:last + 1]
        longest = run = 0
        for v in inner:
            run = run + 1 if v else 0
            longest = max(longest, run)
        max_pause = longest * frame_ms / 1000
    else:
        lead = trail = duration
        max_pause = duration
    norm, _ = normalize(text, lang)
    kind, lo, hi = RATE_BOUNDS.get(lang, ("words", 1.0, 6.0))
    units = len(norm) if kind == "chars" else len(norm.split())
    # Speaking rate over the voiced span, so leading/trailing silence does not distort it.
    voiced = max(duration - lead - trail, 1e-6)
    rate_per_s = units / voiced
    flags = []
    if rms < 0.005 or not loud.any():
        flags.append("silent")
    if clipped > 0.001:
        flags.append("clipped")
    if lead > 1.0:
        flags.append("dead_air_start")
    if trail > 1.5:
        flags.append("dead_air_end")
    if max_pause > 1.5:
        flags.append("long_pause")
    if rate_per_s < lo:
        flags.append("too_slow")
    if rate_per_s > hi:
        flags.append("too_fast")
    return {
        "duration_s": round(duration, 3), "sample_rate": rate, "peak": round(peak, 4), "rms": round(rms, 4),
        "clipped_fraction": round(clipped, 5), "lead_silence_s": round(lead, 3), "trail_silence_s": round(trail, 3),
        "max_pause_s": round(max_pause, 3), "rate_per_s": round(rate_per_s, 3), "rate_unit": kind, "flags": flags,
    }
