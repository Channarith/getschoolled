"""edge-tts: the free Microsoft neural voices that today's speech gateway falls back to (our 'current voice').

INTERNAL REFERENCE ONLY. edge-tts is an unofficial client of Microsoft's Edge Read Aloud service, whose terms do not
license third-party commercial use: do not count it as shippable (see candidates.yaml). Needs the `edge-tts` package and
network access. Converts the service's mp3 to wav with ffmpeg.
"""
from __future__ import annotations

import asyncio
import subprocess
import tempfile
import wave
from pathlib import Path

from .base import Adapter, AdapterError

VOICES = {
    "km": "km-KH-SreymomNeural",
    "th": "th-TH-PremwadeeNeural",
    "vi": "vi-VN-HoaiMyNeural",
    "es": "es-MX-DaliaNeural",
    "zh": "zh-CN-XiaoxiaoNeural",
    "en": "en-US-AvaNeural",
    "sw": "sw-KE-ZuriNeural",
    "hi": "hi-IN-SwaraNeural",
    "yue": "zh-HK-HiuMaanNeural",  # Cantonese
}


class EdgeTTSAdapter(Adapter):
    name = "edge_tts"
    languages = set(VOICES)
    requires = ("edge_tts",)

    def supports(self, lang: str) -> bool:
        return bool(self.options.get("voice")) or lang in self.languages  # an explicit voice may read any language it has

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import edge_tts

        voice = self.options.get("voice") or (self.options.get("voices") or {}).get(lang) or VOICES[lang]
        # Voice character: prosody only (the free service ignores SSML styles). rate "+10%", pitch "+20Hz", volume "-10%".
        prosody = {k: str(self.options[k]) for k in ("rate", "pitch", "volume") if self.options.get(k)}
        retries = int(self.options.get("retries", 4))
        with tempfile.TemporaryDirectory() as d:
            mp3 = Path(d) / "x.mp3"
            for attempt in range(retries):
                try:
                    asyncio.run(edge_tts.Communicate(text, voice, **prosody).save(str(mp3)))
                    break
                except Exception as exc:  # noqa: BLE001 - the service rate-limits: back off and retry
                    if attempt == retries - 1:
                        raise AdapterError(f"edge-tts failed for {voice}: {exc}") from exc
                    import time

                    time.sleep(1.5 * (attempt + 1))
            if not mp3.exists() or mp3.stat().st_size < 500:
                raise AdapterError(f"edge-tts returned no audio for {voice}")
            r = subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), "-ac", "1", "-ar", "24000",
                                "-sample_fmt", "s16", str(out_wav)], capture_output=True, text=True)
            if r.returncode != 0:
                raise AdapterError(f"ffmpeg failed: {r.stderr[:200]}")
        with wave.open(str(out_wav), "rb") as w:
            return w.getframerate()
