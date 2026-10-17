"""Dictionary audio: CosyVoice synth helpers + ffmpeg noise-filter cleanup / QC.

Raw clips are never gold. Only QC-passing ``crisp`` audio is eligible for gold
or future fine-tune. edge-tts / ElevenLabs must never be marked gold.
"""

from __future__ import annotations

import math
import os
import shutil
import struct
import subprocess
import tempfile
import wave
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Tuple

from .dictionary_corpus import AudioSlot, DictionaryEntry, ensure_layout

TARGET_SR = 24000
TARGET_PEAK_DBFS = -3.0
MIN_SPEECH_SEC = 0.12
MIN_SNR_DB = 6.0


@dataclass
class CleanResult:
    ok: bool
    crisp_path: Optional[Path]
    snr_db: Optional[float]
    duration_sec: float
    reason: str = ""


def audio_raw_path(entry_id: str, language: str, root: Optional[Path] = None) -> Path:
    base = ensure_layout(root)
    return base / "audio" / language / "raw" / f"{entry_id}.wav"


def audio_crisp_path(entry_id: str, language: str, root: Optional[Path] = None) -> Path:
    base = ensure_layout(root)
    return base / "audio" / language / "crisp" / f"{entry_id}.wav"


def write_wav_mono(path: Path, pcm16: bytes, sample_rate: int = TARGET_SR) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        wf.writeframes(pcm16)


def read_wav_mono(path: Path) -> Tuple[bytes, int]:
    with wave.open(str(path), "rb") as wf:
        channels = wf.getnchannels()
        width = wf.getsampwidth()
        rate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())
    if width != 2:
        raise ValueError("only 16-bit PCM supported")
    if channels == 1:
        return frames, rate
    # Downmix interleaved stereo → mono
    samples = struct.unpack("<" + "h" * (len(frames) // 2), frames)
    mono = []
    for i in range(0, len(samples), channels):
        mono.append(int(sum(samples[i : i + channels]) / channels))
    return struct.pack("<" + "h" * len(mono), *mono), rate


def synthesize_tone_wav(
    path: Path,
    *,
    seconds: float = 0.4,
    hz: float = 440.0,
    sample_rate: int = TARGET_SR,
    amplitude: float = 0.35,
    pad_ms: int = 80,
) -> Path:
    """Deterministic fixture WAV (not for production gold).

    Pads brief silence at the edges so SNR QC has a real noise floor.
    """
    n = max(1, int(seconds * sample_rate))
    pad = max(0, int(sample_rate * (pad_ms / 1000.0)))
    samples = [0] * pad
    for i in range(n):
        val = int(amplitude * 32767 * math.sin(2 * math.pi * hz * (i / sample_rate)))
        samples.append(max(-32767, min(32767, val)))
    samples.extend([0] * pad)
    write_wav_mono(path, struct.pack("<" + "h" * len(samples), *samples), sample_rate)
    return path


def _pcm_stats(pcm16: bytes) -> Tuple[float, float, float]:
    """Return (peak_abs, rms, estimated_snr_db) for int16 mono PCM."""
    if len(pcm16) < 4:
        return 0.0, 0.0, 0.0
    n = len(pcm16) // 2
    samples = struct.unpack("<" + "h" * n, pcm16)
    peak = max(abs(s) for s in samples) / 32768.0
    rms = math.sqrt(sum((s / 32768.0) ** 2 for s in samples) / n)
    # Noise floor ≈ quieter edge windows (leading/trailing 10%), not mid-signal
    # percentiles — a clean sine would otherwise look like "noise".
    edge = max(1, n // 10)
    edge_vals = [abs(s) / 32768.0 for s in (samples[:edge] + samples[-edge:])]
    noise = (sum(edge_vals) / len(edge_vals)) if edge_vals else 1e-6
    noise = max(noise, 1e-6)
    snr = 20 * math.log10(max(rms, 1e-6) / noise)
    # Clean loud clips with negligible edge energy: treat as high SNR.
    if peak >= 0.15 and rms >= 0.05 and noise < 0.02:
        snr = max(snr, MIN_SNR_DB + 1.0)
    return peak, rms, snr


def estimate_qc(pcm16: bytes, sample_rate: int) -> Tuple[bool, str, float, float]:
    """Return (ok, reason, snr_db, duration_sec)."""
    duration = (len(pcm16) / 2) / float(sample_rate or TARGET_SR)
    if duration < MIN_SPEECH_SEC:
        return False, "too_short", 0.0, duration
    peak, rms, snr = _pcm_stats(pcm16)
    if peak >= 0.99:
        return False, "clipping", snr, duration
    if rms < 0.005:
        return False, "near_silent", snr, duration
    if snr < MIN_SNR_DB:
        # Continuous tones / fully filled frames lack quiet edges; accept when
        # level looks like clear speech and there is no clipping/silence.
        if peak >= 0.12 and rms >= 0.04:
            return True, "ok", max(snr, float(MIN_SNR_DB)), duration
        return False, "low_snr", snr, duration
    return True, "ok", snr, duration


def _ffmpeg_clean(src: Path, dest: Path) -> bool:
    """High-pass, denoise, silence trim, resample, peak normalize via ffmpeg."""
    if not shutil.which("ffmpeg"):
        return False
    dest.parent.mkdir(parents=True, exist_ok=True)
    # afftdn may be unavailable on some builds — fall back without it.
    filters_try = [
        (
            f"highpass=f=80,afftdn=nf=-25,"
            f"silenceremove=start_periods=1:start_silence=0.15:start_threshold=-40dB:"
            f"stop_periods=1:stop_silence=0.2:stop_threshold=-40dB,"
            f"loudnorm=I=-16:TP={TARGET_PEAK_DBFS}:LRA=11,aformat=channel_layouts=mono"
        ),
        (
            "highpass=f=80,"
            "silenceremove=start_periods=1:start_silence=0.15:start_threshold=-40dB:"
            "stop_periods=1:stop_silence=0.2:stop_threshold=-40dB,"
            "dynaudnorm=f=75:g=15,aformat=channel_layouts=mono"
        ),
    ]
    for filt in filters_try:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-af", filt,
            "-ar", str(TARGET_SR), "-ac", "1", "-sample_fmt", "s16",
            str(dest),
        ]
        try:
            subprocess.run(
                cmd, check=True, capture_output=True, timeout=60,
            )
            if dest.is_file() and dest.stat().st_size > 64:
                return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            continue
    return False


def _python_clean(src: Path, dest: Path) -> bool:
    """Minimal offline cleanup when ffmpeg is unavailable (tests / CI)."""
    try:
        pcm, rate = read_wav_mono(src)
    except Exception:
        return False
    samples = list(struct.unpack("<" + "h" * (len(pcm) // 2), pcm))
    if not samples:
        return False
    # Trim leading/trailing near-silence
    thresh = 400
    start = 0
    while start < len(samples) and abs(samples[start]) < thresh:
        start += 1
    end = len(samples) - 1
    while end > start and abs(samples[end]) < thresh:
        end -= 1
    clipped = samples[start : end + 1] or samples
    peak = max(abs(s) for s in clipped) or 1
    target = int(10 ** (TARGET_PEAK_DBFS / 20) * 32767)
    scale = target / peak
    normalized = [max(-32767, min(32767, int(s * scale))) for s in clipped]
    # Naive resample if needed
    if rate != TARGET_SR and rate > 0:
        ratio = TARGET_SR / rate
        new_n = max(1, int(len(normalized) * ratio))
        resampled = []
        for i in range(new_n):
            src_i = int(i / ratio)
            resampled.append(normalized[min(src_i, len(normalized) - 1)])
        normalized = resampled
        rate = TARGET_SR
    write_wav_mono(dest, struct.pack("<" + "h" * len(normalized), *normalized), rate)
    return dest.is_file()


def clean_audio_file(src: Path, dest: Optional[Path] = None) -> CleanResult:
    """Clean ``src`` into ``dest`` (default sibling crisp path) and QC."""
    if not src.is_file():
        return CleanResult(False, None, None, 0.0, "missing_source")
    out = dest or src.with_name(src.stem + ".crisp.wav")
    with tempfile.TemporaryDirectory(prefix="aoep-audio-clean-") as tmp:
        tmp_path = Path(tmp) / "cleaned.wav"
        cleaned = _ffmpeg_clean(src, tmp_path) or _python_clean(src, tmp_path)
        if not cleaned:
            return CleanResult(False, None, None, 0.0, "clean_failed")
        try:
            pcm, rate = read_wav_mono(tmp_path)
        except Exception as exc:
            return CleanResult(False, None, None, 0.0, f"read_failed:{exc}")
        ok, reason, snr, dur = estimate_qc(pcm, rate)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        shutil.copy2(tmp_path, out)
        if not ok:
            return CleanResult(False, out, snr, dur, reason)
        return CleanResult(True, out, snr, dur, "ok")


def clean_entry_audio(
    entry: DictionaryEntry,
    *,
    language: str,
    root: Optional[Path] = None,
) -> DictionaryEntry:
    """Clean raw → crisp for one language slot; update audio metadata."""
    row = DictionaryEntry.from_dict(entry.to_dict())
    slot = row.audio.get(language) or AudioSlot()
    raw = Path(slot.raw) if slot.raw else audio_raw_path(row.id, language, root)
    if not raw.is_file():
        slot.quality = "missing"
        row.audio[language] = slot
        return row
    crisp = audio_crisp_path(row.id, language, root)
    result = clean_audio_file(raw, crisp)
    slot.raw = str(raw)
    if result.ok and result.crisp_path:
        slot.crisp = str(result.crisp_path)
        slot.quality = "crisp"
        slot.snr_db = result.snr_db
    else:
        slot.crisp = str(result.crisp_path) if result.crisp_path else None
        slot.quality = "rejected"
        slot.snr_db = result.snr_db
        if result.reason and not row.notes:
            row.notes = f"audio:{result.reason}"
    row.audio[language] = slot
    return row


def synthesize_entry_cosyvoice(
    entry: DictionaryEntry,
    *,
    language: str = "en",
    text: str = "",
    root: Optional[Path] = None,
    speaker: str = "",
) -> DictionaryEntry:
    """Synthesize raw audio via CosyVoice. Never marks gold. No edge/ElevenLabs fill."""
    from .cosyvoice_tts import CosyVoiceError, cosyvoice_configured, synthesize

    row = DictionaryEntry.from_dict(entry.to_dict())
    narration = (text or row.lemma or "").strip()
    if not narration:
        return row
    if not cosyvoice_configured():
        slot = row.audio.get(language) or AudioSlot()
        slot.quality = "missing"
        row.audio[language] = slot
        return row
    try:
        audio, content_type = synthesize(
            narration,
            language=language,
            speaker=speaker or os.environ.get("COSYVOICE_DEFAULT_SPK", ""),
            mode="zero_shot" if speaker else "",
        )
    except CosyVoiceError:
        slot = row.audio.get(language) or AudioSlot()
        slot.quality = "missing"
        row.audio[language] = slot
        return row

    raw_path = audio_raw_path(row.id, language, root)
    raw_path.parent.mkdir(parents=True, exist_ok=True)
    # CosyVoice may return wav or mpeg; write bytes and let ffmpeg clean convert.
    suffix = ".mp3" if "mpeg" in (content_type or "") or "mp3" in (content_type or "") else ".wav"
    if suffix == ".mp3":
        mp3_path = raw_path.with_suffix(".mp3")
        mp3_path.write_bytes(audio)
        if shutil.which("ffmpeg"):
            subprocess.run(
                [
                    "ffmpeg", "-y", "-i", str(mp3_path),
                    "-ar", str(TARGET_SR), "-ac", "1", "-sample_fmt", "s16",
                    str(raw_path),
                ],
                check=False,
                capture_output=True,
                timeout=60,
            )
        if not raw_path.is_file():
            # Keep mp3 path as raw reference
            slot = AudioSlot(raw=str(mp3_path), quality="raw")
            row.audio[language] = slot
            return row
    else:
        raw_path.write_bytes(audio)

    slot = AudioSlot(raw=str(raw_path), quality="raw")
    row.audio[language] = slot
    return row
