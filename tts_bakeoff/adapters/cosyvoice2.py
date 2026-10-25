"""CosyVoice 2 0.5B, our incumbent. Apache-2.0. No km/vi/th/sw/hi in the base model.

Two ways to run it, whichever works on the machine:
  - in-process (needs the CosyVoice repo on PYTHONPATH and Python 3.10): options model_dir, prompt_wav
  - over HTTP against the repo's server (COSYVOICE_URL, default http://127.0.0.1:9880): POST /tts
The HTTP path matches services/cosyvoice in this repo. NOT run against real weights here.

Option instruct (optional): an instruction text ending in <|endofprompt|>, e.g. 用可爱、甜美的语气说这句话<|endofprompt|>. It
switches the in-process path to inference_instruct2(text, instruct, prompt_wav), which takes the cloned prompt wav only.
The documented examples are Chinese; whether English text keeps the style is unverified, so compare by ear.
"""
from __future__ import annotations

import os
from pathlib import Path

from .base import Adapter, AdapterError, have, write_wav


def load_prompt_wav(path: str, target_sr: int = 16000):
    """Read the reference wav as a (1, T) float tensor at target_sr without torchaudio.load.

    Newer torchaudio routes load() through TorchCodec, which is not installed on the Spark, so CosyVoice's own
    load_wav raises ImportError on every clip. soundfile (if present) or the stdlib wave module reads the file; the
    resample uses torchaudio.functional, which has no TorchCodec dependency.
    """
    import numpy as np

    try:
        import soundfile as sf

        data, sr = sf.read(path, dtype="float32", always_2d=True)
        mono = data.mean(axis=1)
    except Exception:  # noqa: BLE001 - soundfile missing or cannot read this file: fall back to PCM16 via wave
        import wave

        with wave.open(path, "rb") as w:
            sr, ch, width = w.getframerate(), w.getnchannels(), w.getsampwidth()
            if width != 2:
                raise AdapterError(f"reference wav must be 16-bit PCM, got {width * 8}-bit: {path}") from None
            raw = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype("float32") / 32768.0
        mono = raw.reshape(-1, ch).mean(axis=1) if ch > 1 else raw
    import torch

    speech = torch.from_numpy(np.ascontiguousarray(mono)).unsqueeze(0)
    if sr != target_sr:
        import torchaudio.functional as taf

        speech = taf.resample(speech, sr, target_sr)
    return speech


class CosyVoice2Adapter(Adapter):
    name = "cosyvoice2"
    languages = {"en", "es", "zh"}

    def model_dir(self) -> str:
        """option model_dir, else $COSYVOICE_MODEL_DIR, else <repo>/pretrained_models/CosyVoice2-0.5B (repo = $COSYVOICE_REPO or ~/code/CosyVoice).

        Never a bare relative path: the model loads the directory if it exists and otherwise tries to DOWNLOAD that string as a model
        name, which fails with a confusing error when the process runs from another folder.
        """
        if self.options.get("model_dir"):
            return str(self.options["model_dir"])
        if os.environ.get("COSYVOICE_MODEL_DIR"):
            return os.environ["COSYVOICE_MODEL_DIR"]
        repo = os.environ.get("COSYVOICE_REPO") or os.path.join(os.path.expanduser("~"), "code", "CosyVoice")
        return os.path.join(repo, "pretrained_models", "CosyVoice2-0.5B")

    def check(self) -> dict:
        problems = []
        if not (have("cosyvoice") or os.environ.get("COSYVOICE_URL")):
            problems.append("neither the 'cosyvoice' module is importable nor COSYVOICE_URL is set")
        if not os.environ.get("COSYVOICE_URL") and not os.path.isdir(self.model_dir()):
            problems.append(f"model weights not found at {self.model_dir()} (download iic/CosyVoice2-0.5B there, or set COSYVOICE_MODEL_DIR)")
        return {"ok": not problems, "problems": problems, "languages": sorted(self.languages), "model_dir": self.model_dir()}

    def _infer(self, model, text: str, lang: str, prompt):
        if self.options.get("instruct"):
            return model.inference_instruct2(text, self.options["instruct"], prompt, stream=False)
        if self.options.get("prompt_text") and self.options.get("prompt_lang") == lang:  # same language as the sample: zero-shot
            return model.inference_zero_shot(text, self.options["prompt_text"], prompt, stream=False)
        return model.inference_cross_lingual(text, prompt, stream=False)

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

        self._model = self._model or CosyVoice2(self.model_dir())
        prompt = load_prompt_wav(self.options["prompt_wav"], 16000)
        gen = self._infer(self._model, text, lang, prompt)
        parts = [j["tts_speech"] for j in gen]
        import torch

        wav = torch.cat(parts, dim=1)
        write_wav(out_wav, wav.squeeze().cpu().numpy(), self._model.sample_rate)
        _ = torchaudio
        return self._model.sample_rate
