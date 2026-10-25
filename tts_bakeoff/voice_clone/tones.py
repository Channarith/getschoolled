"""Tones (professional, cute, anime ... and their blends) for cloned voices, by two mechanisms that are compared by ear.

  model  the model is asked for the style: VoxCPM2 "controllable cloning" (a description in parentheses before the text,
         reference audio only) and CosyVoice 2 instruct mode (inference_instruct2 with an instruction ending in
         <|endofprompt|>). Written from the model card and example.py; NOT yet run against the real weights.
  dsp    the neutral clone is post-processed with ffmpeg (pitch, tempo, a small brightness tilt, gain). Works for any model.
         Pitch is shifted by resampling, so formants move with the pitch (no independent formant control: that needs
         WORLD or rubberband, which are not installed). Limits are conservative so the voice stays recognisable.

Any tone other than "neutral" needs the speaker's separate stylized_versions consent (registry.grant_scope).

  python3 -m tts_bakeoff.voice_clone.bakeoff tones --out runs/2026-10-25-clone-tones --langs en,es,zh
"""
from __future__ import annotations

import json
import math
import shutil
import socket
import subprocess
import tempfile
import time
import wave
from dataclasses import dataclass
from pathlib import Path

from tts_bakeoff.voice_types import BLEND_WEIGHTS, PRESETS, blend

from . import clean as audio_clean
from . import profile, registry, synth

NEUTRAL = "neutral"
REF_F0_HZ = 170.0          # edge-tts preset pitch offsets (Hz) are turned into semitones around this voice pitch
MAX_SEMITONES = 3.0        # beyond this a voice stops sounding like the person
MAX_TEMPO = 0.15           # +-15% speed
MAX_TILT_DB = 1.5          # brightness shelf
MAX_GAIN_DB = 3.0

# Model-side descriptions, per preset. English for VoxCPM2 (its card shows English descriptions), Chinese instructions for
# CosyVoice 2 (the documented instruct examples are Chinese, e.g. 用四川话说这句话<|endofprompt|>).
VOX_STYLE = {
    "professional": "clear, calm, professional narrator voice",
    "warm": "warm, friendly, reassuring voice",
    "calm": "calm, soothing, slightly slower voice",
    "energetic": "energetic, upbeat, slightly faster voice",
    "cute": "cute, sweet, bright, slightly high-pitched voice",
    "anime": "high-pitched, lively, expressive anime character voice",
    "tough": "tough, firm, confident, lower voice",
    "heavy": "deep, heavy, slow, serious voice",
    "light": "light, airy, gentle voice",
}
COSY_INSTRUCT = {
    "professional": "用专业、清晰、沉稳的语气说这句话",
    "warm": "用温暖、亲切的语气说这句话",
    "calm": "用平静、舒缓的语气说这句话",
    "energetic": "用充满活力、积极向上的语气说这句话",
    "cute": "用可爱、甜美的语气说这句话",
    "anime": "用夸张、活泼的动漫角色语气说这句话",
    "tough": "用坚定、强硬的语气说这句话",
    "heavy": "用低沉、缓慢的语气说这句话",
    "light": "用轻柔、飘逸的语气说这句话",
}


@dataclass(frozen=True)
class Tone:
    name: str
    weights: dict          # preset -> weight (a plain preset is {name: 100})
    semitones: float
    tempo: float           # 1.0 = unchanged
    tilt_db: float         # + brighter, - darker
    gain_db: float

    @property
    def is_blend(self) -> bool:
        return len(self.weights) > 1

    @property
    def lab_style(self) -> str:
        """Value of the lab's Voice type filter: a preset name or blend-<label>."""
        return f"blend-{self.name}" if self.is_blend else self.name


def _clamp(x: float, lim: float) -> float:
    return max(-lim, min(lim, x))


def _params(weights: dict) -> tuple[float, float, float, float]:
    """(semitones, tempo, tilt_db, gain_db) from the same rate/pitch/volume the edge-tts presets use, with caps."""
    rate, pitch, volume = (float(v.rstrip("%Hz")) for v in blend(weights))
    semitones = _clamp(12 * math.log2((REF_F0_HZ + pitch) / REF_F0_HZ), MAX_SEMITONES)
    tempo = 1.0 + _clamp(rate / 100.0, MAX_TEMPO)
    gain_db = _clamp(20 * math.log10(max(0.01, 1 + volume / 100.0)), MAX_GAIN_DB)
    return semitones, tempo, _clamp(0.5 * semitones, MAX_TILT_DB), gain_db


def _build() -> dict:
    tones = {}
    for name in PRESETS:
        st, tempo, tilt, gain = _params({name: 100})
        tones[name] = Tone(name, {name: 100}, st, tempo, tilt, gain)
    for label, weights in BLEND_WEIGHTS.items():
        st, tempo, tilt, gain = _params(weights)
        tones[label] = Tone(label, dict(weights), st, tempo, tilt, gain)
    return tones


TONES = _build()
PRESET_NAMES = tuple(PRESETS)
BLEND_NAMES = tuple(BLEND_WEIGHTS)


def get_tone(name: str) -> Tone | None:
    if name == NEUTRAL:
        return None
    if name not in TONES:
        raise registry.ConsentError(f"unknown tone {name!r}; use neutral, a preset ({', '.join(PRESET_NAMES)}) or a blend")
    return TONES[name]


def vox_style(tone: Tone) -> str:
    """Parenthetical description for VoxCPM2 controllable cloning, e.g. 'mostly clear ... with a hint of cute ...'."""
    ranked = sorted(tone.weights.items(), key=lambda kv: -kv[1])
    (top, top_w), rest = ranked[0], ranked[1:]
    if not rest:
        return VOX_STYLE[top]
    if top_w >= 60:
        return f"mostly {VOX_STYLE[top]}, with a hint of " + " and ".join(VOX_STYLE[n] for n, _ in rest)
    return " and ".join(VOX_STYLE[n] for n, _ in ranked)


def cosy_instruct(tone: Tone) -> str:
    """CosyVoice 2 instruction text, ready for inference_instruct2 (ends with the required <|endofprompt|>)."""
    ranked = sorted(tone.weights.items(), key=lambda kv: -kv[1])
    base = COSY_INSTRUCT[ranked[0][0]]
    if len(ranked) > 1:
        extras = "、".join(COSY_INSTRUCT[n].replace("用", "").replace("的语气说这句话", "") for n, _ in ranked[1:])
        base = f"{base}，同时带有{extras}的感觉"
    return base + "<|endofprompt|>"


# ---------------------------------------------------------------- consent gate
def require_tone_consent(speaker: str, tone: str, base: Path | None = None) -> None:
    """neutral needs the normal narration consent; any other tone also needs the stylized_versions scope."""
    get_tone(tone)
    registry.require_consent(speaker, "course_narration", base)
    if tone != NEUTRAL:
        registry.require_consent(speaker, "stylized_versions", base)


# ---------------------------------------------------------------- dsp
def ffmpeg_filter(tone: Tone, rate: int) -> str:
    ratio = 2 ** (tone.semitones / 12.0)
    parts = [f"asetrate={rate * ratio:.3f}", f"aresample={rate}", f"atempo={tone.tempo / ratio:.5f}"]
    if abs(tone.tilt_db) >= 0.05:
        parts.append(f"treble=g={tone.tilt_db:.2f}:f=4000" if tone.tilt_db > 0 else f"bass=g={-tone.tilt_db:.2f}:f=250")
    if abs(tone.gain_db) >= 0.05:
        parts.append(f"volume={tone.gain_db:.2f}dB")
    parts.append("alimiter=limit=0.95")
    return ",".join(parts)


def _wav_rate(path: Path) -> int:
    with wave.open(str(path), "rb") as w:
        return w.getframerate()


def apply_tone_dsp(src: Path | str, dst: Path | str, tone_name: str) -> Path:
    """Write ``dst`` = ``src`` with the tone applied (post-processing). neutral just copies."""
    src, dst = Path(src), Path(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    tone = get_tone(tone_name)
    if tone is None:
        shutil.copyfile(src, dst)
        return dst
    if not shutil.which("ffmpeg"):
        raise RuntimeError("ffmpeg is required for tone post-processing")
    rate = _wav_rate(src)
    with tempfile.TemporaryDirectory() as t:
        tmp = Path(t) / "out.wav"
        r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(src), "-af", ffmpeg_filter(tone, rate),
                            "-ac", "1", "-ar", str(rate), "-sample_fmt", "s16", str(tmp)], capture_output=True, text=True)
        if r.returncode != 0:
            raise RuntimeError(f"ffmpeg failed: {r.stderr[:200]}")
        shutil.copyfile(tmp, dst)
    return dst


# ---------------------------------------------------------------- synthesis
def tone_adapter(model: str, speaker: str, tone: str, base: Path | None = None, gpu: bool = True):
    """Adapter for the model-side mechanism, after the tone consent gate. neutral gives the plain clone adapter."""
    require_tone_consent(speaker, tone, base)
    t = get_tone(tone)
    extra = {}
    if t is not None:
        extra = {"style": vox_style(t)} if model == "voxcpm2" else {"instruct": cosy_instruct(t)} if model == "cosyvoice2" else {}
    return synth.build_adapter(model, speaker, base, gpu=gpu, **extra)


def render_tone_clip(speaker: str, model: str, text: str, lang: str, tone: str, mechanism: str, out_wav: Path | str,
                     base: Path | None = None, gpu: bool = True, takes: int | None = None, clean: bool | None = None) -> dict:
    """One clip of ``speaker`` in ``tone``. mechanism 'model' (style asked of the model) or 'dsp' (neutral clone, then
    post-processing). The consent gate runs first in both. The neutral or model clip goes through the best-of-N + cleaning
    stage (clean.synthesize_best_of; takes/clean as there). Reusable by the Say-anything flow."""
    if mechanism not in ("model", "dsp"):
        raise ValueError("mechanism must be 'model' or 'dsp'")
    out = Path(out_wav)
    require_tone_consent(speaker, tone, base)
    if mechanism == "model" or tone == NEUTRAL:
        res = audio_clean.synthesize_best_of(tone_adapter(model, speaker, tone, base, gpu), text, lang, out, takes=takes, clean=clean)
    else:
        with tempfile.TemporaryDirectory() as t:
            raw = Path(t) / "neutral.wav"
            res = audio_clean.synthesize_best_of(tone_adapter(model, speaker, NEUTRAL, base, gpu), text, lang, raw, takes=takes, clean=clean)
            apply_tone_dsp(raw, out, tone)
    res["tone"], res["mechanism"] = tone, mechanism
    return res


def run_tones(out: Path, speakers: list[str], models: list[str], langs: list[str] | None, tones: list[str], mechanisms: list[str],
              limit: int | None = 1, base: Path | None = None, gpu: bool = True, model_blends: bool = False, takes: int | None = None, clean: bool | None = None) -> dict:
    """Listening set under ``out`` (loadable by tts_bakeoff.lab): <model>~<speaker>~<mechanism>-<tone>/<lang>/<id>.wav.

    The neutral clone is synthesized once per speaker/model/language/sentence and every dsp tone is derived from it, so
    the dsp half costs CPU only. The model half costs one GPU synthesis per tone."""
    from tts_bakeoff.build_sentences import load

    counts = {"ok": 0, "failed": 0, "refused": 0, "skipped_unsupported": 0}
    for speaker in speakers:
        try:
            rec = registry.require_consent(speaker, "course_narration", base)
        except registry.ConsentError as exc:
            print(f"REFUSED {speaker}: {exc}")
            counts["refused"] += 1
            continue
        try:
            registry.require_consent(speaker, "stylized_versions", base)
            allowed = list(tones)
        except registry.ConsentError:
            allowed = [t for t in tones if t == NEUTRAL]
            if len(allowed) != len(tones):
                print(f"REFUSED tones for {speaker}: no signed stylized_versions addendum; neutral only")
                counts["refused"] += len(tones) - len(allowed)
        enrolled = profile.speaker_languages(speaker, base) or ["en"]
        own = langs or enrolled   # no --langs: the language(s) the speaker was enrolled in; anything else is cross-lingual
        for model in models:
            adapter = synth.build_adapter(model, speaker, base, gpu=gpu)
            for lang in own:
                if not adapter.supports(lang):
                    counts["skipped_unsupported"] += 1
                    continue
                for item in load(lang, limit):
                    with tempfile.TemporaryDirectory() as t:
                        raw = Path(t) / "neutral.wav"
                        try:
                            audio_clean.synthesize_best_of(adapter, item["text"], lang, raw, takes=takes, clean=clean)
                        except Exception as exc:  # noqa: BLE001
                            print(f"[{model}~{speaker}] {lang} {item['id']} neutral failed: {exc}")
                            counts["failed"] += 1
                            continue
                        for tone in allowed:
                            for mech in mechanisms:
                                if mech == "model" and (tone == NEUTRAL or (tone in BLEND_NAMES and not model_blends)):
                                    continue
                                _emit(out, model, speaker, rec, lang, item, tone, mech, raw, base, gpu, counts, takes, clean, cross=lang not in enrolled)
    return counts


def _emit(out, model, speaker, rec, lang, item, tone, mech, raw, base, gpu, counts, takes=None, clean=None, cross=False):
    t = get_tone(tone)
    vid = f"{model}~{speaker}" if t is None else f"{model}~{speaker}~{mech}-{tone}"
    root = out / vid
    root.mkdir(parents=True, exist_ok=True)
    wav = root / lang / f"{item['id']}.wav"
    if t is None and wav.exists():
        return
    row = {"model": vid, "lang": lang, "id": item["id"], "text": item["text"], "wav": wav.relative_to(out).as_posix(),
           "tone": tone, "mechanism": mech if t else "neutral", **({"cross_lingual": True} if cross else {})}
    try:
        if t is None:
            apply_tone_dsp(raw, wav, NEUTRAL)
        elif mech == "dsp":
            apply_tone_dsp(raw, wav, tone)
        else:
            row.update(audio_clean.synthesize_best_of(tone_adapter(model, speaker, tone, base, gpu), item["text"], lang, wav,
                                                      takes=takes, clean=clean))
        row["status"] = "ok"
        counts["ok"] += 1
    except Exception as exc:  # noqa: BLE001
        row.update({"status": "failed", "error": f"{type(exc).__name__}: {str(exc)[:300]}"})
        counts["failed"] += 1
    meta_path = root / "meta.json"
    if not meta_path.exists():
        meta = {"model": vid, "clone": True, "consented": True, "base_model": model, "speaker": speaker, "role": rec["role"],
                "consent_date": rec["date"], "host": socket.gethostname(), "started": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
                "voice": f"{model}~{speaker}", "kind": "style" if t else "plain", "style": t.lab_style if t else None,
                "stylized": t is not None, "mechanism": mech if t else "neutral",
                "label": f"{profile.display_label(speaker, rec['name'], base)} · {tone}" + (" (model)" if t and mech == "model" else " (post-processed)" if t else "")}
        if t:
            meta["tone_params"] = {"semitones": round(t.semitones, 2), "tempo": round(t.tempo, 3), "tilt_db": round(t.tilt_db, 2),
                                   "gain_db": round(t.gain_db, 2)}
        meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8")
        (root / "scores.jsonl").touch()
    with (root / "manifest.jsonl").open("a", encoding="utf-8") as mf:
        mf.write(json.dumps(row, ensure_ascii=False) + "\n")
    print(f"[{vid}] {lang} {item['id']} {row['status']}")
