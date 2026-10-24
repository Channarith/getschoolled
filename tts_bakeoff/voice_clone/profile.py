"""Voice profile: the best enrolled reference sample for each target language, and fine-tune readiness per speaker.

  python3 -m tts_bakeoff.voice_clone.profile report [--speaker wei-miao] [--model voxcpm2]
  python3 -m tts_bakeoff.voice_clone.profile choose --speaker wei-miao --lang yue
  python3 -m tts_bakeoff.voice_clone.profile prep   --speaker wei-miao --model voxcpm2 --out ~/voices/wei-miao/finetune   # stub: writes a manifest only

Zero-shot cloning (what runs today) does NOT train anything: the model hears one enrolled sample as a reference and imitates it. A speaker
can have several samples (different languages, sessions); this module picks the one that suits each target language.

Fallback order for a target language L (first tier that has a sample wins; inside a tier the cleanest sample, then the longest):
  1. same-language   a sample recorded in L (a Cantonese reference for yue; its transcript matches what was said)
  2. close-language  a sample in a close variety (yue <-> zh): same script and many shared sounds, but different tones and words
  3. cross-lingual   the cleanest sample in any other language (the model carries the timbre across languages; accent can drift)
Every pick goes through registry.require_consent, which re-hashes the signed form and every enrolled sample first.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from pathlib import Path

from . import registry

CLOSE = {"yue": ("zh",), "zh": ("yue",)}
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

    @property
    def reason(self) -> str:
        return f"{self.tier}: {self.rel} ({self.lang}, {self.seconds:.0f} s, {self.snr_db:.0f} dB SNR{', cleaned' if self.cleaned else ''})"


def _quality(info: dict) -> float:
    if info.get("cleaned") and info.get("snr_db_clean") is not None:
        return float(info["snr_db_clean"])
    return float(info.get("snr_db") or 0.0)


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

    rel, info, path = min(pool, key=lambda p: (FALLBACK_ORDER.index(tier_of(p[1])), -_quality(p[1]), -float(p[1].get("seconds") or 0), p[0]))
    return Reference(path, info["transcript"], info.get("lang", "en"), rel, tier_of(info), _quality(info), bool(info.get("cleaned")),
                     float(info.get("seconds") or 0))


class ProfileAdapter:
    """Wraps a cloning adapter and, before every synthesis, points it at the best reference sample for that sentence's language.

    One model load serves every language. Attribute access falls through to the wrapped adapter, so tones, 'say' and the demo
    render use it exactly like the adapter they had before.
    """

    def __init__(self, inner, speaker: str, base: Path | None = None):
        self.inner, self.speaker, self.base = inner, speaker, base
        self.last_reference: Reference | None = None

    def __getattr__(self, name):
        return getattr(self.inner, name)

    def use(self, lang: str) -> Reference:
        ref = choose_reference(self.speaker, lang, self.base)
        self.inner.options.update(reference_wav=str(ref.path), reference_text=ref.transcript, prompt_wav=str(ref.path),
                                  prompt_text=ref.transcript, prompt_lang=ref.lang)
        self.last_reference = ref
        return ref

    def synthesize(self, text, lang, out_wav, *args, **kwargs):
        self.use(lang)
        return self.inner.synthesize(text, lang, out_wav, *args, **kwargs)


def readiness(speaker: str, model: str = "voxcpm2", base: Path | None = None) -> dict:
    """Clean audio per language against what the model docs say fine-tuning needs. Counts only enrolled, consented samples."""
    spec = FINE_TUNE[model]
    langs: dict[str, dict] = {}
    for rel, info, _ in _candidates(speaker, base):
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
    for i, (rel, info, path) in enumerate(_candidates(speaker, base)):
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
