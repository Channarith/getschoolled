"""Fish Speech V1.5, REFERENCE ONLY: the weights are CC-BY-NC-SA-4.0 (non-commercial). NOT SHIPPABLE.

Run the project's API server (python tools/api_server.py ...) and point FISH_SPEECH_URL at it
(default http://127.0.0.1:8080). Languages on the card: no Khmer, Vietnamese, Thai, Swahili, Hindi.
NOT run against real weights here; the request shape follows the project's /v1/tts endpoint.
"""
from __future__ import annotations

import os
import wave
from pathlib import Path

from .base import Adapter, AdapterError


class FishSpeech15Adapter(Adapter):
    name = "fish_speech15"
    languages = {"en", "es", "zh"}
    requires = ("requests",)

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import requests

        url = os.environ.get("FISH_SPEECH_URL", "http://127.0.0.1:8080").rstrip("/") + "/v1/tts"
        r = requests.post(url, json={"text": text, "format": "wav", "streaming": False}, timeout=180)
        if r.status_code != 200:
            raise AdapterError(f"fish speech server returned {r.status_code}: {r.text[:200]}")
        out_wav.write_bytes(r.content)
        with wave.open(str(out_wav), "rb") as w:
            return w.getframerate()
