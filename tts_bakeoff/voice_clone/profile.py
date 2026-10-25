"""Voice profile: the best enrolled reference sample for each target language, and fine-tune readiness per speaker.

  python3 -m tts_bakeoff.voice_clone.profile report [--speaker wei-miao] [--model voxcpm2]
  python3 -m tts_bakeoff.voice_clone.profile choose --speaker wei-miao --lang yue
  python3 -m tts_bakeoff.voice_clone.profile refs   --speaker wei [--lang yue] [--dry-run]    # cut the short exact-transcript references
  python3 -m tts_bakeoff.voice_clone.profile prep   --speaker wei-miao --model voxcpm2 --out ~/voices/wei-miao/finetune   # stub: writes a manifest only

Zero-shot cloning (what runs today) does NOT train anything: the model hears one enrolled sample as a reference and imitates it. A speaker
can have several samples (different languages, sessions); this module picks the one that suits each target language.

Fallback order for a target language L (first tier that has a sample wins; inside a tier the cleanest sample, then the longest):
  1. same-language   a sample recorded in L (a Cantonese reference for yue; its transcript matches what was said)
  2. close-language  a sample in a close variety (yue <-> zh): same script and many shared sounds, but different tones and words
  3. cross-lingual   the cleanest sample in any other language (the model carries the timbre across languages; accent can drift)
Every pick goes through registry.require_consent, which re-hashes the signed form and every enrolled sample first.

Reference clips: the enrollment page saves each prompt as its own take (raw/<lang>/<lang>-N.wav) and the prompt text is known, so
'refs' picks ONE clean single-utterance take of 5-20 s per language (closest to 11 s, highest SNR) and registers it as a sample with
role "reference" and its exact prompt text. Synthesis prefers these over the long concatenated sample: models want a short reference
(VoxCPM2 'continue' mode needs the EXACT transcript of the audio; CosyVoice 2 zero-shot wants a prompt under about 30 s), and a
60 s recording with a joined transcript that is not word for word what was said is what makes speech drift from the text.

Reference mode (VoxCPM2), --ref-mode auto|continue|reference:
  continue    reference audio + its exact transcript, the model continues the voice: for the SAME language as a reference whose
              transcript is exact
  reference   audio only, no prompt text: for another language, or when the transcript is not known to be exact (the long
              concatenated sample); the voice carries over and the words come only from the text
  auto        continue when the pick is a same-language reference with an exact transcript, otherwise reference
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import threading
import wave
from dataclasses import dataclass
from pathlib import Path

from . import registry

CLOSE = {"yue": ("zh",), "zh": ("yue",)}
LANG_NAMES = {"en": "English", "yue": "Cantonese", "zh": "Mandarin", "es": "Spanish", "vi": "Vietnamese", "th": "Thai", "km": "Khmer",
              "sw": "Swahili", "hi": "Hindi"}
ALL_LANGS = ("en", "es", "zh", "yue", "vi", "th", "km", "sw", "hi")   # what "--langs all" means
FALLBACK_ORDER = ("same-language", "close-language", "cross-lingual")

# What the model docs say about fine-tuning data (read 2026-10-25). VoxCPM README: "With as little as 5-10 minutes of audio, you can adapt
# to a specific speaker, language, or domain"; its fine-tuning guide: clips of 3-30 s, 5-50 clips to clone a single speaker (LoRA),
# 30-50% of samples with a reference clip. CosyVoice 2's README states no minimum (its training recipes are written for large corpora).
FINE_TUNE = {
    "voxcpm2": {"min_minutes": 5.0, "good_minutes": 10.0, "clip_s": (3.0, 30.0), "min_clips": 5,
                "source": "VoxCPM README 'Fine-tuning' and the Fine-tuning Guide (voxcpm.readthedocs.io)"},
    "cosyvoice2": {"min_minutes": None, "good_minutes": None, "clip_s": None, "min_clips": None,
                   "source": "CosyVoice README states no minimum; plan on at least the VoxCPM numbers and expect to need more"},
}


def norm_lang(lang: str) -> str:
    l = (lang or "en").lower().replace("_", "-")
    if l.startswith("yue") or l.startswith("zh-hk") or l.startswith("zh-yue"):
        return "yue"
    return l.split("-")[0]


@dataclass(frozen=True)
class Reference:
    path: Path
    transcript: str
    lang: str
    rel: str
    tier: str
    snr_db: float
    cleaned: bool
    seconds: float
    role: str = "session"          # "reference" = one clean single-utterance take with its exact prompt text; "session" = a long enrolled recording
    exact: bool = False            # the transcript is known to be word for word what was said

    @property
    def reason(self) -> str:
        return (f"{self.tier}: {self.rel} ({self.lang}, {self.role}, {self.seconds:.0f} s, {self.snr_db:.0f} dB SNR"
                f"{', cleaned' if self.cleaned else ''}{', exact transcript' if self.exact else ''})")


def language_name(code: str) -> str:
    return LANG_NAMES.get(norm_lang(code), code)


def speaker_languages(speaker: str, base: Path | None = None) -> list[str]:
    """The languages a speaker was enrolled in, own language first: most clean audio, then the language of the consent text they saw.

    This is a speaker's default language list for the clone bake-off, tones and the demo render (an explicit --langs overrides it), so
    a Cantonese voice speaks Cantonese and shows up under Cantonese, not English, unless someone asks for English.
    """
    totals: dict[str, float] = {}
    consent_lang = None
    for _rel, info, _path in _sessions(speaker, base):
        lang = norm_lang(info.get("lang", ""))
        totals[lang] = totals.get(lang, 0.0) + float(info.get("seconds") or 0)
        consent_lang = consent_lang or (norm_lang(info["consent_language"]) if info.get("consent_language") not in (None, "signed-form") else None)
    return sorted(totals, key=lambda l: (-totals[l], l != consent_lang, l))


def primary_language(speaker: str, base: Path | None = None, default: str = "en") -> str:
    return (speaker_languages(speaker, base) or [default])[0]


def display_label(speaker: str, name: str, base: Path | None = None) -> str:
    """'Wei (Cantonese)', 'Wei Miao (English)': the name from the consent record plus the voice's own language."""
    return f"{name} ({language_name(primary_language(speaker, base))})"


def expand_langs(arg: str | None, speaker: str, base: Path | None = None) -> list[str]:
    """--langs value to a language list: empty = the speaker's own languages, 'all' = every demo language, else the explicit list."""
    if not arg:
        return speaker_languages(speaker, base) or ["en"]
    if arg == "all":
        return list(ALL_LANGS)
    return [x for x in arg.split(",") if x]


def _quality(info: dict) -> float:
    if info.get("cleaned") and info.get("snr_db_clean") is not None:
        return float(info["snr_db_clean"])
    return float(info.get("snr_db") or 0.0)


def _sessions(speaker: str, base: Path | None):
    """Enrolled recordings without the short reference clips (those are cut from the same takes: counting them would double the minutes)."""
    return ((rel, info, path) for rel, info, path in _candidates(speaker, base) if info.get("role") != "reference")


def _candidates(speaker: str, base: Path | None):
    rec = registry.require_consent(speaker, "course_narration", base)
    d = registry.speaker_dir(speaker, base)
    for rel, info in sorted(rec["samples"].items()):
        yield rel, info, d / rel


def choose_reference(speaker: str, target_lang: str, base: Path | None = None) -> Reference:
    target = norm_lang(target_lang)
    pool = list(_candidates(speaker, base))
    if not pool:
        raise registry.ConsentError(f"{speaker!r} has consent but no enrolled sample yet: record one first")

    def tier_of(info: dict) -> str:
        lang = norm_lang(info.get("lang", ""))
        if lang == target:
            return FALLBACK_ORDER[0]
        if lang in CLOSE.get(target, ()):
            return FALLBACK_ORDER[1]
        return FALLBACK_ORDER[2]

    # tier first; inside a tier a short exact-transcript reference beats a long session recording; then cleanest, then longest
    rel, info, path = min(pool, key=lambda p: (FALLBACK_ORDER.index(tier_of(p[1])), p[1].get("role") != "reference", -_quality(p[1]),
                                               -float(p[1].get("seconds") or 0), p[0]))
    return Reference(path, info["transcript"], info.get("lang", "en"), rel, tier_of(info), _quality(info), bool(info.get("cleaned")),
                     float(info.get("seconds") or 0), info.get("role", "session"), bool(info.get("transcript_exact")))


REF_MODES = ("auto", "continue", "reference")


def decide_ref_mode(ref: Reference, target_lang: str, requested: str = "auto") -> str:
    """continue only for a same-language reference whose transcript is exact (and short enough to be an utterance); else reference-only."""
    if requested in ("continue", "reference"):
        return requested
    same = norm_lang(ref.lang) == norm_lang(target_lang)
    return "continue" if same and ref.exact and ref.seconds <= 20 else "reference"


MODEL_CACHE: dict[str, object] = {}   # model name -> the loaded model, shared by every speaker's adapter in this process (one load per process)
GPU_LOCK = threading.RLock()          # one synthesis at a time on the GPU; the CPU stage of a clip (scoring, cleaning) runs outside it


class ProfileAdapter:
    """Wraps a cloning adapter and, before every synthesis, points it at the best reference sample for that sentence's language.

    One model load serves every language. Attribute access falls through to the wrapped adapter, so tones, 'say' and the demo
    render use it exactly like the adapter they had before.
    """

    def __init__(self, inner, speaker: str, base: Path | None = None, ref_mode: str = "auto", cache_key: str | None = None):
        if ref_mode not in REF_MODES:
            raise ValueError(f"ref_mode must be one of {REF_MODES}")
        self.inner, self.speaker, self.base, self.ref_mode = inner, speaker, base, ref_mode
        self.last_reference: Reference | None = None
        self.cache_key = cache_key
        if cache_key and MODEL_CACHE.get(cache_key) is not None:
            self.inner._model = MODEL_CACHE[cache_key]   # already loaded for another speaker

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def use(self, lang: str) -> Reference:
        ref = choose_reference(self.speaker, lang, self.base)
        self.inner.options.update(reference_wav=str(ref.path), reference_text=ref.transcript, prompt_wav=str(ref.path),
                                  prompt_text=ref.transcript, prompt_lang=ref.lang, ref_mode=decide_ref_mode(ref, lang, self.ref_mode))
        self.last_reference = ref
        return ref

    def synthesize(self, text, lang, out_wav, *args, **kwargs):
        with GPU_LOCK:   # use() rewrites the inner adapter's options: reference and synthesis must stay together
            self.use(lang)
            row = self.inner.synthesize(text, lang, out_wav, *args, **kwargs)
            if self.cache_key and getattr(self.inner, "_model", None) is not None:
                MODEL_CACHE.setdefault(self.cache_key, self.inner._model)
        return row


REF_MIN_S, REF_MAX_S, REF_TARGET_S = 5.0, 20.0, 11.0
REF_ASR_MAX_ERROR = 0.35


def _write_wav(path: Path, x, rate: int) -> None:
    import numpy as np

    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(int(rate))
        w.writeframes((np.clip(x, -1, 1) * 32767).astype("<i2").tobytes())


def build_reference(speaker: str, lang: str, base: Path | None = None, dry_run: bool = False) -> dict:
    """Pick ONE clean single-utterance take for ``lang`` and register it as the reference sample (role "reference").

    Takes are raw/<lang>/<lang>-N.wav and the text of each is the prompt the speaker read (enroll_ui.prompts), so the transcript is the
    exact prompt text. Candidates are 5-20 s, not clipped, above the SNR floor; the best is the highest SNR, penalised by distance from
    11 s. With GS_CLONE_ASR=1 (whisper installed) a take whose round trip does not match its prompt is rejected, and the reference is
    marked transcript_verified. The cleaned copy is kept only if cleaning leaves the voice alone (the same rule as the enrollment sample).
    """
    from . import clean as audio_clean
    from . import enroll
    from .enroll_ui.prompts import PROMPT_SETS

    registry.require_consent(speaker, "model_training", base)
    d = registry.speaker_dir(speaker, base)
    texts = {p["id"]: p["text"] for p in PROMPT_SETS.get(lang, [])}
    asr_on = os.environ.get("GS_CLONE_ASR", "0") == "1"
    best, rejected = None, []
    for pid, text in texts.items():
        take = d / "raw" / lang / f"{pid}.wav"
        if not take.is_file():
            continue
        x, rate = enroll.read_wav(take)
        x = enroll.trim_silence(x, rate)
        secs, snr = len(x) / rate, enroll.snr_db(x, rate)
        why = ("too short" if secs < REF_MIN_S else "too long" if secs > REF_MAX_S else "clipped" if float(abs(x).max()) >= 0.999
               else "too noisy" if snr < enroll.MIN_SNR_DB else None)
        if why is None and asr_on:
            wer = audio_clean.asr_wer(take, text, lang)
            if wer is not None and wer > REF_ASR_MAX_ERROR:
                why = f"does not match its prompt (round-trip error {wer:.2f})"
        if why:
            rejected.append(f"{pid}: {why} ({secs:.0f} s, {snr:.0f} dB)")
            continue
        score = snr - 1.5 * abs(secs - REF_TARGET_S)
        if best is None or score > best["score"]:
            best = {"pid": pid, "text": text, "x": x, "rate": rate, "secs": secs, "snr": snr, "score": score}
    if best is None:
        return {"lang": lang, "written": False, "reason": "no usable take (need one of 5-20 s, clean, matching its prompt)" if texts else f"no prompts for {lang}",
                "rejected": rejected}
    y, cleaned, snr_clean = audio_clean._normalize(best["x"]), False, None
    if audio_clean.enabled():
        cy, rep = audio_clean.clean_reference(y, best["rate"])
        if rep["kept_cleaned"]:
            y, cleaned, snr_clean = cy, True, rep["after"]["snr_db"]
    info = {"lang": lang, "written": not dry_run, "take": best["pid"], "seconds": round(best["secs"], 1), "snr_db": round(best["snr"], 1),
            "cleaned": cleaned, "transcript_verified": asr_on, "rejected": rejected, "text": best["text"]}
    if dry_run:
        return info
    rel = f"samples/ref-{lang}.wav"
    dest = d / rel
    (d / "samples").mkdir(exist_ok=True)
    if rel in registry.load_consent(speaker, base)["samples"]:
        registry.remove_sample(speaker, rel, base)
    _write_wav(dest, y, best["rate"])
    extra = {"seconds": info["seconds"], "snr_db": info["snr_db"], "cleaned": cleaned, "role": "reference", "transcript_exact": True,
             "transcript_verified": asr_on, "source_take": best["pid"]}
    if snr_clean is not None:
        extra["snr_db_clean"] = round(float(snr_clean), 1)
    registry.add_sample(speaker, dest, best["text"], lang, base, extra=extra)
    return {**info, "file": rel}


def build_references(speaker: str, base: Path | None = None, langs: list[str] | None = None, dry_run: bool = False) -> list[dict]:
    d = registry.speaker_dir(speaker, base)
    found = sorted(p.name for p in (d / "raw").iterdir() if p.is_dir()) if (d / "raw").is_dir() else []
    return [build_reference(speaker, lang, base, dry_run) for lang in (langs or found)]


def readiness(speaker: str, model: str = "voxcpm2", base: Path | None = None) -> dict:
    """Clean audio per language against what the model docs say fine-tuning needs. Counts only enrolled, consented samples."""
    spec = FINE_TUNE[model]
    langs: dict[str, dict] = {}
    for rel, info, _ in _sessions(speaker, base):
        row = langs.setdefault(norm_lang(info.get("lang", "")), {"seconds": 0.0, "samples": 0, "snr": [], "cleaned": 0, "consent_languages": set()})
        row["seconds"] += float(info.get("seconds") or 0)
        row["samples"] += 1
        row["snr"].append(_quality(info))
        row["cleaned"] += bool(info.get("cleaned"))
        if info.get("consent_language"):
            row["consent_languages"].add(info["consent_language"])
    out = {}
    for lang, r in sorted(langs.items()):
        minutes = r["seconds"] / 60
        need = spec["min_minutes"]
        if need is None:
            state = "unknown: the model docs state no minimum"
        elif minutes >= (spec["good_minutes"] or need):
            state = "ready"
        elif minutes >= need:
            state = "enough to try; more is better"
        else:
            state = f"not ready: {need - minutes:.1f} more minutes of clean speech"
        out[lang] = {"clean_minutes": round(minutes, 1), "samples": r["samples"], "snr_db_min": round(min(r["snr"]), 1),
                     "snr_db_avg": round(sum(r["snr"]) / len(r["snr"]), 1), "cleaned_samples": r["cleaned"],
                     "consent_languages": sorted(r["consent_languages"]), "fine_tune": state}
    return {"speaker": speaker, "model": model, "needs": spec, "languages": out}


def format_report(rep: dict) -> str:
    spec = rep["needs"]
    need = "no minimum stated" if spec["min_minutes"] is None else f"{spec['min_minutes']:.0f}-{spec['good_minutes']:.0f} min of clean speech per language"
    lines = [f"{rep['speaker']} - fine-tune readiness for {rep['model']} ({need}; {spec['source']})",
             "  Zero-shot cloning needs only one sample and trains nothing. Fine-tuning needs the minutes below, per language."]
    for lang, r in rep["languages"].items():
        lines.append(f"  {lang:4s} {r['clean_minutes']:5.1f} min in {r['samples']} sample(s), SNR {r['snr_db_min']:.0f}-{r['snr_db_avg']:.0f} dB, "
                     f"{r['cleaned_samples']} cleaned, consent text {','.join(r['consent_languages']) or 'unknown'}: {r['fine_tune']}")
    return "\n".join(lines)


def prep_finetune(speaker: str, model: str, out: Path, base: Path | None = None, force: bool = False) -> dict:
    """STUB: write a fine-tuning manifest from consented samples. Does not train, cut or align anything.

    Needs the model_training scope (checked here). Rows follow the VoxCPM fine-tuning guide (audio, text, duration, dataset_id).
    Samples longer than the guide's 3-30 s window are flagged: they would need segmenting with a forced aligner first (not built).
    """
    registry.require_consent(speaker, "model_training", base)
    spec = FINE_TUNE[model]
    rep = readiness(speaker, model, base)
    lo, hi = spec["clip_s"] or (0.0, 1e9)
    rows, flags = [], []
    for i, (rel, info, path) in enumerate(_sessions(speaker, base)):
        secs = float(info.get("seconds") or 0)
        rows.append({"audio": str(path), "text": info["transcript"], "duration": secs, "dataset_id": 0, "lang": norm_lang(info.get("lang", "")),
                     "sha256": info["sha256"]})
        if not lo <= secs <= hi:
            flags.append(f"{rel}: {secs:.0f} s is outside {lo:.0f}-{hi:.0f} s per clip: segment it before training")
    ready = all(v["fine_tune"] in ("ready", "enough to try; more is better") for v in rep["languages"].values())
    if not ready and not force:
        return {"written": False, "ready": False, "report": format_report(rep), "flags": flags}
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    return {"written": True, "ready": ready, "manifest": str(out / "manifest.jsonl"), "rows": len(rows), "flags": flags, "report": format_report(rep)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("report")
    r.add_argument("--speaker")
    r.add_argument("--model", default="voxcpm2", choices=sorted(FINE_TUNE))
    c = sub.add_parser("choose")
    c.add_argument("--speaker", required=True)
    c.add_argument("--lang", required=True)
    rf = sub.add_parser("refs", help="cut one clean 5-20 s single-utterance reference per language from the per-prompt takes")
    rf.add_argument("--speaker", required=True)
    rf.add_argument("--lang", default="", help="comma list; default: every language that has takes under raw/")
    rf.add_argument("--dry-run", action="store_true")
    p = sub.add_parser("prep")
    p.add_argument("--speaker", required=True)
    p.add_argument("--model", default="voxcpm2", choices=sorted(FINE_TUNE))
    p.add_argument("--out", required=True)
    p.add_argument("--force", action="store_true", help="write the manifest even if the minutes are not there yet")
    a = ap.parse_args(argv)
    try:
        if a.cmd == "report":
            for s in [a.speaker] if a.speaker else registry.list_speakers():
                print(format_report(readiness(s, a.model)))
            return 0
        if a.cmd == "choose":
            print(choose_reference(a.speaker, a.lang).reason)
            return 0
        if a.cmd == "refs":
            for r in build_references(a.speaker, None, [x for x in a.lang.split(",") if x] or None, a.dry_run):
                if r.get("take"):
                    print(f"{a.speaker} {r['lang']}: {'would use' if a.dry_run else 'wrote'} take {r['take']} ({r['seconds']} s, {r['snr_db']} dB"
                          f"{', cleaned' if r['cleaned'] else ''}{', transcript verified by ASR' if r['transcript_verified'] else ''}): {r['text'][:60]}")
                else:
                    print(f"{a.speaker} {r['lang']}: no reference - {r['reason']}")
                for why in r.get("rejected", []):
                    print(f"    skipped {why}")
            return 0
        res = prep_finetune(a.speaker, a.model, Path(a.out).expanduser(), force=a.force)
        print(res["report"])
        for f in res["flags"]:
            print("  note:", f)
        print(f"manifest written: {res['manifest']} ({res['rows']} rows). Nothing was trained." if res["written"] else "not written: not enough clean audio yet (use --force to write anyway). Nothing was trained.")
        return 0 if res["written"] else 3
    except registry.ConsentError as exc:
        print(f"refused: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
