"""Design once, freeze, clone: the stable way to get a VoxCPM2 stock voice.

Voice design invents a voice from a text description, and the model card says results "can vary between runs". So a stock voice is made like this:
  1. design: synthesize a fixed sentence from the description with a fixed seed, a few takes (seed, seed+1, ...);
  2. pick the cleanest take (audio/text ratio, noise, clicks: tts_bakeoff.voice_clone.clean.analyze) and keep the cleaned reference only if it
     did not move the timbre (clean_file, mode "reference");
  3. freeze it: <assets>/_stock/<id>/ref.wav + ref.json (sha256, description, seed, take, model);
  4. every later clip clones from that wav in 'reference' mode (audio only, no transcript), so the voice is the same in every language,
     every run and on every machine that has the file.
Whether a fixed seed alone would also be stable is something this does not rely on; ref.json records the seed used.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import time
from pathlib import Path

from tts_bakeoff import adapters

from . import registry

DESIGN_LANG = "en"
DESIGN_SENTENCE = ("Hello, and welcome to your lesson. Today we will learn something new together, one clear step at a time, "
                   "and you can ask me to repeat anything.")
# The sentence a voice is designed on, per design language. 'yue' is written Cantonese (spoken register); it only seeds the frozen reference
# (the reference is cloned from in audio-only mode, so its text is never used downstream) but it is the sound the clone will copy.
DESIGN_SENTENCES = {
    "en": DESIGN_SENTENCE,
    "yue": "你好，歡迎嚟到今日嘅課堂。今日我哋會一齊學啲新嘢，一步一步嚟，你有咩唔明，隨時都可以叫我再講一次。",
}
MIN_REF_S, MAX_REF_S = 5.0, 20.0


def _shared_model(inner, key: str = "voxcpm2") -> None:
    """Reuse one loaded VoxCPM2 for every stock voice in this process (the clone pipeline's cache)."""
    from tts_bakeoff.voice_clone import profile

    if profile.MODEL_CACHE.get(key) is not None:
        inner._model = profile.MODEL_CACHE[key]


def _remember_model(inner, key: str = "voxcpm2") -> None:
    from tts_bakeoff.voice_clone import profile

    if getattr(inner, "_model", None) is not None:
        profile.MODEL_CACHE[key] = inner._model


def design_adapter(description: str, seed: int | None, gpu: bool = True, **extra):
    """A VoxCPM2 adapter in design mode (no reference). gpu=True applies the CUDA-required policy (Spark only)."""
    if gpu:
        from tts_bakeoff.voice_clone.synth import require_gpu

        require_gpu("voice-design:voxcpm2")
    inner = adapters.get("voxcpm2", design=description, seed=seed, **extra)
    _shared_model(inner)
    return inner


def freeze(voice_id: str, root: Path | None = None, takes: int = 3, adapter_factory=None, force: bool = False, log=print,
           path: Path = registry.STOCK) -> dict:
    """Design ``voice_id`` (a base id, or base~tone) and freeze the best take. Returns the sidecar dict. No-op when already frozen."""
    from tts_bakeoff.voice_clone import clean

    base, tone, dlang = registry.split_full(voice_id)
    design_lang = dlang or DESIGN_LANG
    sentence = DESIGN_SENTENCES[design_lang]
    entry = registry.get(base, path)
    if tone != registry.NEUTRAL and tone not in entry.get("tones", []):
        raise registry.StockError(f"{base} has no tone {tone!r} (tones: {', '.join(entry.get('tones', []))})")
    if not force:
        meta = registry.frozen_meta(voice_id, root)
        if meta:
            log(f"{voice_id}: already frozen (sha {meta['sha256'][:10]}), skipped")
            return meta
    description = registry.description_for(entry, tone)
    seed0 = registry.seed_for(entry, tone, dlang)
    make = adapter_factory or (lambda d, s: design_adapter(d, s))
    scored = []
    with tempfile.TemporaryDirectory() as td:
        for k in range(max(1, takes)):
            seed = seed0 + k
            adapter = make(description, seed)
            wav = Path(td) / f"take{k}.wav"
            adapter.synthesize(sentence, design_lang, wav)
            _remember_model(adapter)
            x, rate = clean.load_audio(wav)
            a = clean.analyze(x, rate, None, sentence, design_lang)
            seconds = len(x) / rate
            if not (MIN_REF_S <= seconds <= MAX_REF_S):
                a["score"] += 500   # a reference outside 5-20 s clones badly: any in-range take wins
                a["out_of_range"] = True
            scored.append({"take": k, "seed": seed, "seconds": round(seconds, 2), **a, "_wav": wav})
        best = min(scored, key=lambda s: s["score"])
        if best["score"] >= 500:
            raise registry.StockError(f"{voice_id}: no take gave a usable reference (all {len(scored)} mismatched or outside "
                                      f"{MIN_REF_S:.0f}-{MAX_REF_S:.0f} s); try a different seed in tts_manifest/stock_voices.json")
        ref, side = registry.ref_paths(voice_id, root)
        ref.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(best["_wav"], ref)
        cleaned = False
        try:
            rep = clean.clean_file(ref, mode="reference", force=True)   # keeps the original beside it as .raw when it changed the audio
            cleaned = bool(rep.get("kept_cleaned"))
        except Exception as exc:  # noqa: BLE001 - an unusable cleaner must not block freezing the raw take
            log(f"{voice_id}: reference cleaning skipped ({str(exc)[:80]})")
    meta = {
        "id": voice_id, "base": base, "tone": tone, "description": description, "seed": best["seed"], "chosen_take": best["take"],
        "takes": [{k: v for k, v in s.items() if k != "_wav"} for s in scored], "sentence": sentence, "lang": design_lang,
        "model": "openbmb/VoxCPM2", "cleaned": cleaned, "sha256": registry.sha256_file(ref), "ai_generated": True,
        "label": registry.AI_LABEL, "license": registry.LICENSE_NOTE, "frozen": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    side.write_text(json.dumps(meta, indent=1, ensure_ascii=False), encoding="utf-8")
    log(f"{voice_id}: frozen take {best['take']} (seed {best['seed']}, {best['seconds']} s, noise score {best['score']})")
    return meta


def build_adapter(voice_id: str, root: Path | None = None, gpu: bool = True, lang: str | None = None, path: Path = registry.STOCK, **extra):
    """The only way to synthesize with a stock voice: an adapter that clones from its frozen, hash-checked reference. ``lang`` picks the
    Cantonese-designed reference for a language the native speaker cleared with method 'yue-ref' (else the voice's own reference)."""
    ref, meta = registry.require_frozen(registry.reference_id(voice_id, lang, path, root), root)
    if gpu:
        from tts_bakeoff.voice_clone.synth import require_gpu

        require_gpu("voice-design:voxcpm2")
    inner = adapters.get("voxcpm2", reference_wav=str(ref), reference_text=meta["sentence"], ref_mode="reference", **extra)
    _shared_model(inner)
    return inner
