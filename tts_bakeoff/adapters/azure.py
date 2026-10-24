"""Azure AI Speech neural TTS: the cloud quality ceiling (and the only cloud option found with Khmer).

REST call with SSML. Needs AZURE_SPEECH_KEY and AZURE_SPEECH_REGION. Voices are from Microsoft's
language-support page (retrieved 2026-10-24). Costs money per character: use --limit.
"""
from __future__ import annotations

import wave
from pathlib import Path
from xml.sax.saxutils import escape

from .base import Adapter, AdapterError

VOICES = {
    "km": ("km-KH", "km-KH-SreymomNeural"),
    "th": ("th-TH", "th-TH-AcharaNeural"),
    "vi": ("vi-VN", "vi-VN-HoaiMyNeural"),
    "sw": ("sw-KE", "sw-KE-ZuruNeural"),
    "hi": ("hi-IN", "hi-IN-SwaraNeural"),
    "es": ("es-MX", "es-MX-DaliaNeural"),
    "zh": ("zh-CN", "zh-CN-XiaoxiaoNeural"),
    "en": ("en-US", "en-US-JennyNeural"),
}


class AzureAdapter(Adapter):
    name = "azure"
    languages = set(VOICES)
    requires = ("requests",)
    env = ("AZURE_SPEECH_KEY", "AZURE_SPEECH_REGION")

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        import os

        import requests

        locale, voice = (self.options.get("voices") or {}).get(lang) or VOICES[lang]
        ssml = f"<speak version='1.0' xml:lang='{locale}'><voice name='{voice}'>{escape(text)}</voice></speak>"
        url = f"https://{os.environ['AZURE_SPEECH_REGION']}.tts.speech.microsoft.com/cognitiveservices/v1"
        r = requests.post(
            url,
            data=ssml.encode("utf-8"),
            headers={
                "Ocp-Apim-Subscription-Key": os.environ["AZURE_SPEECH_KEY"],
                "Content-Type": "application/ssml+xml",
                "X-Microsoft-OutputFormat": "riff-24khz-16bit-mono-pcm",
                "User-Agent": "salareen-tts-bakeoff",
            },
            timeout=60,
        )
        if r.status_code != 200:
            raise AdapterError(f"azure returned {r.status_code}: {r.text[:200]}")
        out_wav.write_bytes(r.content)
        with wave.open(str(out_wav), "rb") as w:
            return w.getframerate()
