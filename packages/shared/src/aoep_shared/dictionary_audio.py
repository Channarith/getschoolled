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
# Frame SNR below this is a noise bed. Broadcast speech after loudnorm can
# sit just above 5 dB on a short window; white noise measures under 1 dB.
MIN_SNR_DB = 5.0
# A pure tone has no quieter frames, so the ratio is ~0 dB. Periodicity
# accepts it and the report stays at the historical 6 dB floor.
_PERIODIC_SNR_DB = 6.0


@dataclass
class CleanResult:
    ok: bool
    crisp_path: Optional[Path]
    snr_db: Optional[float]
    duration_sec: float
    reason: str = ""
    stderr: str = ""


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


# A pure tone's normalized autocorrelation in the pitch range sits near 1.
# White noise and a tone buried in noise stay well below this.
_PERIODIC_AUTOCORR = 0.6
_FRAME_SEC = 0.02


def _periodic_peak(samples: Tuple[int, ...], sample_rate: int) -> float:
    """Peak normalized autocorrelation between 70 Hz and 400 Hz.

    Used only when frame SNR has no separable noise floor. A clean sine then
    still passes. A noise bed does not.
    """
    rate = sample_rate if sample_rate and sample_rate > 0 else TARGET_SR
    frame = max(1, int(rate * _FRAME_SEC))
    if len(samples) < frame:
        return 0.0
    best_rms = -1.0
    best_at = 0
    for start in range(0, len(samples) - frame + 1, frame):
        acc = 0.0
        for sample in samples[start : start + frame]:
            val = sample / 32768.0
            acc += val * val
        if acc > best_rms:
            best_rms = acc
            best_at = start
    win_n = min(len(samples) - best_at, int(rate * 0.25))
    window = samples[best_at : best_at + win_n]
    if len(window) < max(32, int(rate * 0.05)):
        return 0.0
    mean = sum(window) / float(len(window))
    centered = [sample - mean for sample in window]
    energy = sum(val * val for val in centered)
    if energy <= 1e-3:
        return 0.0
    lag_lo = max(1, int(rate / 400))
    lag_hi = min(len(centered) - 2, int(rate / 70))
    if lag_hi <= lag_lo:
        return 0.0
    peak = 0.0
    span = len(centered)
    for lag in range(lag_lo, lag_hi + 1):
        corr = 0.0
        for index in range(span - lag):
            corr += centered[index] * centered[index + lag]
        ratio = corr / energy
        if ratio > peak:
            peak = ratio
    return peak


def _pcm_stats(pcm16: bytes, sample_rate: int = TARGET_SR) -> Tuple[float, float, float]:
    """Return (peak_abs, rms, snr_db) for mono int16 PCM at ``sample_rate``.

    SNR is ``20*log10(loud_frame_rms / quiet_frame_rms)`` on 20 ms frames.
    Comparing full-file RMS to the mean absolute value of the first and last
    10% is not an SNR: after end-trim those edges are the signal, and a clean
    sine measures about 0.9 dB at every amplitude. That number sat under the
    old 6 dB gate, so every continuous file was ``low_snr`` unless a loudness
    escape (peak >= 0.12 and rms >= 0.04) rewrote the report to 6 dB.
    """
    if len(pcm16) < 4:
        return 0.0, 0.0, 0.0
    n = len(pcm16) // 2
    samples = struct.unpack("<" + "h" * n, pcm16)
    peak = max(abs(sample) for sample in samples) / 32768.0
    rms = math.sqrt(sum((sample / 32768.0) ** 2 for sample in samples) / n)
    rate = sample_rate if sample_rate and sample_rate > 0 else TARGET_SR
    frame = max(1, int(rate * _FRAME_SEC))
    frame_rms: list[float] = []
    for start in range(0, n - frame + 1, frame):
        acc = 0.0
        for sample in samples[start : start + frame]:
            val = sample / 32768.0
            acc += val * val
        frame_rms.append(math.sqrt(acc / frame))
    if not frame_rms:
        frame_rms.append(rms)
    ordered = sorted(frame_rms)
    take = max(1, len(ordered) // 5)
    noise = sum(ordered[:take]) / take
    active = sum(ordered[-take:]) / take
    snr = 20.0 * math.log10(max(active, 1e-6) / max(noise, 1e-6))
    # Stationary tone: the quiet frames are the signal, so the ratio is ~0 dB.
    # Periodicity distinguishes that from a noise bed.
    if snr < _PERIODIC_SNR_DB and _periodic_peak(samples, rate) >= _PERIODIC_AUTOCORR:
        snr = _PERIODIC_SNR_DB
    return peak, rms, snr


def estimate_qc(pcm16: bytes, sample_rate: int) -> Tuple[bool, str, float, float]:
    """Return (ok, reason, snr_db, duration_sec).

    ``pcm16`` is mono 16-bit little-endian. ``sample_rate`` is that buffer's
    rate in Hz (after any stereo downmix). Duration is ``n_samples / rate``,
    not ``n_samples / 24000`` and not ``n_bytes / rate``.
    """
    rate = int(sample_rate or TARGET_SR)
    if rate <= 0:
        rate = TARGET_SR
    duration = (len(pcm16) / 2) / float(rate)
    if duration < MIN_SPEECH_SEC:
        return False, "too_short", 0.0, duration
    peak, rms, snr = _pcm_stats(pcm16, rate)
    if peak >= 0.99:
        return False, "clipping", snr, duration
    if rms < 0.005:
        return False, "near_silent", snr, duration
    if snr < MIN_SNR_DB:
        return False, "low_snr", snr, duration
    return True, "ok", snr, duration


def _wav_duration_seconds(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate() or 1
            return handle.getnframes() / float(rate)
    except (wave.Error, OSError, EOFError):
        return 0.0


def _ffmpeg_clean(src: Path, dest: Path) -> tuple[bool, str]:
    """High-pass, gain, then trim only the ends.

    Silence removal used to run before loudnorm with ``stop_periods=1``.
    Quiet speech (around -45 dBFS, common on downloaded talks) was treated as
    silence and the wav collapsed to a header. Gain runs first. A filter that
    still deletes most of a source longer than half a second is discarded.
    """
    if not shutil.which("ffmpeg"):
        return False, ""
    dest.parent.mkdir(parents=True, exist_ok=True)
    src_dur = _wav_duration_seconds(src)
    end_trim = (
        "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-40dB:detection=rms,"
        "areverse,"
        "silenceremove=start_periods=1:start_duration=0.15:start_threshold=-40dB:detection=rms,"
        "areverse,"
    )
    # afftdn may be unavailable on some builds — fall back without it.
    filters_try = [
        (
            f"highpass=f=80,afftdn=nf=-25,loudnorm=I=-16:TP={TARGET_PEAK_DBFS}:LRA=11,"
            f"{end_trim}aformat=channel_layouts=mono"
        ),
        (
            f"highpass=f=80,loudnorm=I=-16:TP={TARGET_PEAK_DBFS}:LRA=11,"
            "aformat=channel_layouts=mono"
        ),
        "highpass=f=80,dynaudnorm=f=75:g=15,aformat=channel_layouts=mono",
    ]
    last_err = ""
    for filt in filters_try:
        cmd = [
            "ffmpeg", "-y", "-i", str(src),
            "-af", filt,
            "-ar", str(TARGET_SR), "-ac", "1", "-sample_fmt", "s16",
            str(dest),
        ]
        try:
            proc = subprocess.run(
                cmd, check=True, capture_output=True, timeout=120, text=True,
            )
        except subprocess.CalledProcessError as exc:
            last_err = (exc.stderr or exc.stdout or "")[-800:]
            continue
        except (subprocess.TimeoutExpired, OSError) as exc:
            last_err = str(exc)[:400]
            continue
        if not dest.is_file() or dest.stat().st_size <= 64:
            last_err = (proc.stderr or "")[-800:] or "ffmpeg wrote no audio"
            continue
        out_dur = _wav_duration_seconds(dest)
        if src_dur >= 0.5 and out_dur < max(MIN_SPEECH_SEC, src_dur * 0.5):
            last_err = (
                f"cleaned duration {out_dur:.3f}s collapsed from {src_dur:.3f}s"
            )
            continue
        return True, ""
    return False, last_err


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
        ffmpeg_ok, ffmpeg_err = _ffmpeg_clean(src, tmp_path)
        cleaned = ffmpeg_ok or _python_clean(src, tmp_path)
        if not cleaned:
            return CleanResult(False, None, None, 0.0, "clean_failed", stderr=ffmpeg_err)
        try:
            pcm, rate = read_wav_mono(tmp_path)
        except Exception as exc:
            return CleanResult(False, None, None, 0.0, f"read_failed:{exc}", stderr=ffmpeg_err)
        ok, reason, snr, dur = estimate_qc(pcm, rate)
        out.parent.mkdir(parents=True, exist_ok=True)
        if out.exists():
            out.unlink()
        shutil.copy2(tmp_path, out)
        if not ok:
            if reason == "near_silent":
                reason = "silent_source"
            return CleanResult(False, out, snr, dur, reason, stderr=ffmpeg_err)
        return CleanResult(True, out, snr, dur, "ok", stderr="")


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
