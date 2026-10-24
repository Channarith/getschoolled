"""CosyVoice 2 0.5B, our incumbent. Apache-2.0. No km/vi/th/sw/hi in the base model.

Two ways to run it, whichever works on the machine:
  - in-process (needs the CosyVoice repo on PYTHONPATH and Python 3.10): options model_dir, prompt_wav
  - over HTTP against the repo's server (COSYVOICE_URL, default http://127.0.0.1:9880): POST /tts
The HTTP path matches services/cosyvoice in this repo. NOT run against real weights here.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Adapter, AdapterError, have, write_wav


class CosyVoice2Adapter(Adapter):
    name = "cosyvoice2"
    languages = {"en", "es", "zh"}

    def check(self) -> dict:
        problems = []
        if not (have("cosyvoice") or os.environ.get("COSYVOICE_URL")):
            problems.append("neither the 'cosyvoice' module is importable nor COSYVOICE_URL is set")
        return {"ok": not problems, "problems": problems, "languages": sorted(self.languages)}

    def _synth(self, text: str, lang: str, out_wav: Path) -> int:
        url = os.environ.get("COSYVOICE_URL")
        if url:
            import requests

            r = requests.post(url.rstrip("/") + "/tts", json={"text": text, "language": lang}, timeout=120)
            if r.status_code != 200:
                raise AdapterError(f"cosyvoice server returned {r.status_code}: {r.text[:200]}")
            out_wav.write_bytes(r.content)
            import wave

            with wave.open(str(out_wav), "rb") as w:
                return w.getframerate()
        import torchaudio
        from cosyvoice.cli.cosyvoice import CosyVoice2
        from cosyvoice.utils.file_utils import load_wav

        self._model = self._model or CosyVoice2(self.options.get("model_dir", "pretrained_models/CosyVoice2-0.5B"))
        prompt = load_wav(self.options["prompt_wav"], 16000)
        parts = [j["tts_speech"] for j in self._model.inference_cross_lingual(text, prompt, stream=False)]
        import torch

        wav = torch.cat(parts, dim=1)
        write_wav(out_wav, wav.squeeze().cpu().numpy(), self._model.sample_rate)
        _ = torchaudio
        return self._model.sample_rate
