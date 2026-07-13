"""CosyVoice 2 inference server (vLLM-accelerated) exposing our /tts contract.

Runs on a GPU (Vultr GPU pool). The speech gateway and the teach-&-present
presenter POST to ``{COSYVOICE_URL}/tts`` with JSON:

    {"text","language","speaker","instruct","mode","sample_rate",
     "reference_audio_b64"?}

and get audio/wav bytes back. Modes map to CosyVoice 2 inference calls:

    instruct2      -> inference_instruct2(text, instruct, prompt_speech)
    zero_shot      -> inference_zero_shot(text, prompt_text, prompt_speech)
    cross_lingual  -> inference_cross_lingual(text, prompt_speech)
    sft            -> inference_sft(text, speaker)   # no reference needed

vLLM acceleration is enabled with COSYVOICE_USE_VLLM=1 (recommended: much faster
generation => lower GPU cost). The heavy model deps (torch/torchaudio/cosyvoice/
vllm) are imported lazily so this module (and its tests) import without a GPU.
"""

from __future__ import annotations

import base64
import io
import os
import struct
import tempfile
import wave
from typing import Any, Iterable, List, Optional

from fastapi import FastAPI, HTTPException, Response
from pydantic import BaseModel


class TtsRequest(BaseModel):
    text: str
    language: str = "en"
    speaker: str = ""
    instruct: str = ""
    mode: str = ""
    sample_rate: int = 24000
    reference_audio_b64: str = ""
    speaker_wav_b64: str = ""      # alias accepted from the presenter/clone path
    prompt_text: str = ""


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default).strip()


def _to_int16(chunk: Any) -> List[int]:
    """Flatten a CosyVoice audio chunk (torch tensor / numpy / list) to int16 PCM."""
    # torch tensor -> cpu numpy
    if hasattr(chunk, "detach"):
        chunk = chunk.detach()
    if hasattr(chunk, "cpu"):
        chunk = chunk.cpu()
    if hasattr(chunk, "numpy"):
        chunk = chunk.numpy()
    # numpy array -> flat list
    if hasattr(chunk, "reshape"):
        chunk = chunk.reshape(-1).tolist()
    elif hasattr(chunk, "tolist"):
        chunk = chunk.tolist()
    out: List[int] = []
    for v in _flatten(chunk):
        f = float(v)
        if f > 1.0:
            f = 1.0
        elif f < -1.0:
            f = -1.0
        out.append(int(f * 32767.0))
    return out


def _flatten(x: Any) -> Iterable[float]:
    if isinstance(x, (list, tuple)):
        for v in x:
            yield from _flatten(v)
    else:
        yield x


def _wav_bytes(samples: List[int], sample_rate: int) -> bytes:
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(sample_rate)
        w.writeframes(struct.pack("<%dh" % len(samples), *samples))
    return buf.getvalue()


def _collect(result: Any) -> List[int]:
    """CosyVoice yields dicts with a 'tts_speech' tensor; concat all chunks."""
    samples: List[int] = []
    for item in result:
        speech = item.get("tts_speech") if isinstance(item, dict) else item
        samples.extend(_to_int16(speech))
    return samples


def synthesize(model: Any, req: TtsRequest, prompt_speech: Any = None) -> bytes:
    """Dispatch to the right CosyVoice 2 inference call and return WAV bytes."""
    text = (req.text or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="text is required")
    sr = getattr(model, "sample_rate", None) or req.sample_rate or 24000
    mode = (req.mode or "").strip() or ("instruct2" if req.instruct else
                                        "zero_shot" if prompt_speech is not None else
                                        "cross_lingual")

    if mode == "sft" or (prompt_speech is None and not req.instruct and mode not in ("cross_lingual",)):
        spk = req.speaker or _env("COSYVOICE_DEFAULT_SPK") or "中文女"
        result = model.inference_sft(text, spk, stream=False)
    elif mode == "instruct2":
        if prompt_speech is None:
            raise HTTPException(status_code=422, detail="instruct2 needs a reference voice")
        result = model.inference_instruct2(text, req.instruct or "Speak naturally.",
                                           prompt_speech, stream=False)
    elif mode == "cross_lingual":
        if prompt_speech is None:
            # No reference: fall back to a default enrolled speaker.
            spk = req.speaker or _env("COSYVOICE_DEFAULT_SPK") or "中文女"
            result = model.inference_sft(text, spk, stream=False)
        else:
            result = model.inference_cross_lingual(text, prompt_speech, stream=False)
    else:  # zero_shot
        if prompt_speech is None:
            raise HTTPException(status_code=422, detail="zero_shot needs a reference voice")
        result = model.inference_zero_shot(text, req.prompt_text or "",
                                           prompt_speech, stream=False)

    samples = _collect(result)
    if not samples:
        raise HTTPException(status_code=502, detail="CosyVoice produced no audio")
    return _wav_bytes(samples, int(sr))


def _load_prompt_speech(req: TtsRequest) -> Any:
    """Decode reference audio (base64) into a 16k prompt-speech tensor, or None."""
    b64 = req.reference_audio_b64 or req.speaker_wav_b64
    if not b64:
        return None
    raw = base64.b64decode(b64)
    from cosyvoice.utils.file_utils import load_wav  # type: ignore

    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as fh:
        fh.write(raw)
        path = fh.name
    return load_wav(path, 16000)


def _load_model() -> Any:
    """Load CosyVoice 2 with vLLM acceleration (lazy; GPU only)."""
    from cosyvoice.cli.cosyvoice import CosyVoice2  # type: ignore

    model_dir = _env("COSYVOICE_MODEL_DIR", "/models/CosyVoice2-0.5B")
    if not os.path.isdir(model_dir):
        # Pull weights on first start (ModelScope).
        from modelscope import snapshot_download  # type: ignore
        snapshot_download(_env("COSYVOICE_MODEL_ID", "iic/CosyVoice2-0.5B"),
                          local_dir=model_dir)
    use_vllm = _env("COSYVOICE_USE_VLLM", "1") not in ("0", "false", "no")
    return CosyVoice2(model_dir, load_jit=False, load_trt=False, load_vllm=use_vllm, fp16=True)


def build_app(model: Any = None) -> FastAPI:
    app = FastAPI(title="CosyVoice 2 TTS")
    app.state.model = model

    def _model() -> Any:
        if app.state.model is None:
            app.state.model = _load_model()
        return app.state.model

    @app.get("/health")
    def health() -> dict:
        return {"ok": True, "ready": app.state.model is not None,
                "vllm": _env("COSYVOICE_USE_VLLM", "1") not in ("0", "false", "no")}

    @app.post("/tts")
    def tts(req: TtsRequest) -> Response:
        model = _model()
        prompt = None
        if req.reference_audio_b64 or req.speaker_wav_b64:
            try:
                prompt = _load_prompt_speech(req)
            except Exception as exc:   # noqa: BLE001 - bad reference shouldn't 500
                raise HTTPException(status_code=400, detail=f"bad reference audio: {exc}")
        audio = synthesize(model, req, prompt_speech=prompt)
        return Response(content=audio, media_type="audio/wav",
                        headers={"Cache-Control": "no-store", "X-TTS-Engine": "cosyvoice"})

    return app


app = build_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=int(_env("COSYVOICE_PORT", "9880")))
