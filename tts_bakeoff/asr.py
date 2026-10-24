"""Speech recognition for the round-trip score. Heavy engines import lazily.

Engines:
  faster-whisper:large-v3   good for most languages (GPU or CPU)
  whisper:large-v3          openai-whisper
  mms                       facebook/mms-1b-all CTC with a per-language adapter; used for Khmer
  fake:<noise>              test engine: returns the reference with deterministic character noise
  auto                      mms for km, faster-whisper:large-v3 for everything else

The ASR model is a measuring instrument: a weak ASR makes every TTS look bad in that language. Always read
the leaderboard next to the ASR used, and sanity check with the human panel.
"""
from __future__ import annotations

import hashlib

MMS_LANG = {"km": "khm", "th": "tha", "vi": "vie", "sw": "swh", "hi": "hin", "es": "spa", "en": "eng", "zh": "cmn-script_simplified"}
WHISPER_LANG = {"km": "km", "th": "th", "vi": "vi", "sw": "sw", "hi": "hi", "es": "es", "en": "en", "zh": "zh", "yue": "yue"}


class ASR:
    name = "base"

    def transcribe(self, wav_path: str, lang: str, reference: str | None = None) -> str:  # pragma: no cover
        raise NotImplementedError


class FakeASR(ASR):
    """Deterministic noisy echo of the reference, for tests and dry runs. noise = fraction of characters changed."""

    def __init__(self, noise: float = 0.0):
        self.noise = float(noise)
        self.name = f"fake:{noise}"

    def transcribe(self, wav_path: str, lang: str, reference: str | None = None) -> str:
        text = reference or ""
        if self.noise <= 0:
            return text
        out = []
        for i, ch in enumerate(text):
            h = int(hashlib.sha256(f"{wav_path}:{i}".encode()).hexdigest(), 16) % 1000 / 1000.0
            out.append("x" if h < self.noise and not ch.isspace() else ch)
        return "".join(out)


class FasterWhisperASR(ASR):
    def __init__(self, model: str = "large-v3", device: str = "auto", compute_type: str = "auto"):
        self.name = f"faster-whisper:{model}"
        self.model_name, self.device, self.compute_type = model, device, compute_type
        self._model = None

    def transcribe(self, wav_path, lang, reference=None):
        if self._model is None:
            from faster_whisper import WhisperModel

            self._model = WhisperModel(self.model_name, device=self.device, compute_type=self.compute_type)
        segments, _ = self._model.transcribe(wav_path, language=WHISPER_LANG.get(lang), beam_size=5, vad_filter=False)
        return " ".join(s.text.strip() for s in segments).strip()


class OpenAIWhisperASR(ASR):
    def __init__(self, model: str = "large-v3", device: str | None = None):
        self.name = f"whisper:{model}"
        self.model_name, self.device = model, device
        self._model = None

    def transcribe(self, wav_path, lang, reference=None):
        if self._model is None:
            import whisper

            self._model = whisper.load_model(self.model_name, device=self.device)
        return self._model.transcribe(wav_path, language=WHISPER_LANG.get(lang), fp16=self.device != "cpu")["text"].strip()


class MmsASR(ASR):
    name = "mms-1b-all"

    def __init__(self, device: str | None = None):
        self.device = device
        self._loaded = None

    def transcribe(self, wav_path, lang, reference=None):
        import numpy as np
        import torch
        from transformers import AutoProcessor, Wav2Vec2ForCTC

        if self._loaded is None:
            device = self.device or ("cuda" if torch.cuda.is_available() else "cpu")
            proc = AutoProcessor.from_pretrained("facebook/mms-1b-all")
            model = Wav2Vec2ForCTC.from_pretrained("facebook/mms-1b-all").to(device)
            self._loaded = (proc, model, device, set())
        proc, model, device, adapters = self._loaded
        code = MMS_LANG[lang]
        if code not in adapters:
            proc.tokenizer.set_target_lang(code)
            model.load_adapter(code)
            adapters.clear()
            adapters.add(code)
        from .scoring import read_wav

        audio, rate = read_wav(wav_path)
        if rate != 16000:
            # nearest-neighbour is crude but adequate for a measuring pass; use soundfile/librosa for better
            idx = np.linspace(0, len(audio) - 1, int(len(audio) * 16000 / rate)).astype(int)
            audio = audio[idx]
        inputs = proc(audio, sampling_rate=16000, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits
        return proc.batch_decode(torch.argmax(logits, dim=-1))[0].strip()


class AutoASR(ASR):
    """mms for Khmer, faster-whisper large-v3 for the rest."""

    name = "auto(mms:km, faster-whisper:large-v3)"

    def __init__(self, device: str = "auto"):
        self._mms = MmsASR(None if device == "auto" else device)
        self._fw = FasterWhisperASR(device=device)

    def transcribe(self, wav_path, lang, reference=None):
        return (self._mms if lang == "km" else self._fw).transcribe(wav_path, lang, reference)


def get(spec: str, device: str = "auto") -> ASR:
    kind, _, arg = spec.partition(":")
    if kind == "fake":
        return FakeASR(float(arg or 0))
    if kind == "faster-whisper":
        return FasterWhisperASR(arg or "large-v3", device)
    if kind == "whisper":
        return OpenAIWhisperASR(arg or "large-v3", None if device == "auto" else device)
    if kind == "mms":
        return MmsASR(None if device == "auto" else device)
    if kind == "auto":
        return AutoASR(device)
    raise ValueError(f"unknown ASR spec {spec!r}")


# Optional naturalness predictor (UTMOS). Returns None when it cannot be loaded; never required.
_utmos = None


def predict_naturalness(wav_path: str) -> float | None:
    global _utmos
    try:
        import torch
        import torchaudio

        if _utmos is None:
            _utmos = torch.hub.load("tarepan/SpeechMOS:v1.2.0", "utmos22_strong", trust_repo=True)
        wave_, rate = torchaudio.load(wav_path)
        return float(_utmos(wave_, rate).mean())
    except Exception:  # noqa: BLE001 - optional; an unavailable predictor must not fail a run
        return None
