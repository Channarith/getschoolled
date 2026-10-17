#!/usr/bin/env python3
"""Speech-token extract for CosyVoice-300M using the CPU ONNX provider.

The upstream tool forces CUDAExecutionProvider. This host's CosyVoice venv
ships onnxruntime without CUDA, and the live TTS server must keep its own
process. Tokens are written beside wav.scp as utt2speech_token.pt. Nothing is
copied into pretrained_models.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import numpy as np
import onnxruntime
import soundfile as sf
import torch
import torchaudio
import whisper


def _load_wav_scp(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        utt, wav = text.split(maxsplit=1)
        out[utt] = wav
    return out


def _one(utt: str, wav_path: str, session: onnxruntime.InferenceSession) -> tuple[str, list]:
    data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    audio = torch.from_numpy(data.T.copy())
    if sample_rate != 16000:
        audio = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(audio)
    if audio.shape[0] > 1:
        audio = audio.mean(dim=0, keepdim=True)
    if audio.shape[1] / 16000 > 30:
        return utt, []
    feat = whisper.log_mel_spectrogram(audio, n_mels=128)
    inputs = session.get_inputs()
    tokens = session.run(
        None,
        {
            inputs[0].name: feat.detach().cpu().numpy(),
            inputs[1].name: np.array([feat.shape[2]], dtype=np.int32),
        },
    )[0].flatten().tolist()
    return utt, tokens


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--onnx_path", type=Path, required=True)
    parser.add_argument("--num_thread", type=int, default=4)
    args = parser.parse_args()
    utt2wav = _load_wav_scp(args.dir / "wav.scp")
    options = onnxruntime.SessionOptions()
    options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        str(args.onnx_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    tokens: dict[str, list] = {}
    workers = max(1, int(args.num_thread))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [pool.submit(_one, utt, wav, session) for utt, wav in utt2wav.items()]
        for future in as_completed(futures):
            utt, speech_token = future.result()
            tokens[utt] = speech_token
    empty = sum(1 for value in tokens.values() if not value)
    torch.save(tokens, args.dir / "utt2speech_token.pt")
    print(f"utterances={len(tokens)} empty_tokens={empty} out={args.dir / 'utt2speech_token.pt'}")
    return 0 if tokens and empty < len(tokens) else 1


if __name__ == "__main__":
    raise SystemExit(main())
