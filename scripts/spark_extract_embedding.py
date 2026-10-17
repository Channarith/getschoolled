#!/usr/bin/env python3
"""Campplus speaker embeddings via soundfile, CPU ONNX only.

Upstream extract_embedding.py calls torchaudio.load() without a backend.
TorchAudio on this box requires TorchCodec for that path. Loading with the
soundfile backend keeps the live CosyVoice venv unchanged.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import onnxruntime
import soundfile as sf
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi


def _load_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        key, value = text.split(maxsplit=1)
        out[key] = value
    return out


def _one(
    utt: str,
    wav_path: str,
    session: onnxruntime.InferenceSession,
) -> tuple[str, list]:
    data, sample_rate = sf.read(wav_path, dtype="float32", always_2d=True)
    audio = torch.from_numpy(data.T.copy())
    if sample_rate != 16000:
        audio = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(audio)
    feat = kaldi.fbank(audio, num_mel_bins=80, dither=0, sample_frequency=16000)
    feat = feat - feat.mean(dim=0, keepdim=True)
    embedding = session.run(
        None,
        {session.get_inputs()[0].name: feat.unsqueeze(dim=0).cpu().numpy()},
    )[0].flatten().tolist()
    return utt, embedding


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dir", type=Path, required=True)
    parser.add_argument("--onnx_path", type=Path, required=True)
    parser.add_argument("--num_thread", type=int, default=4)
    args = parser.parse_args()
    utt2wav = _load_map(args.dir / "wav.scp")
    utt2spk = _load_map(args.dir / "utt2spk")
    options = onnxruntime.SessionOptions()
    options.graph_optimization_level = onnxruntime.GraphOptimizationLevel.ORT_ENABLE_ALL
    options.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        str(args.onnx_path),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    utt2embedding: dict[str, list] = {}
    spk2embedding: dict[str, list] = {}
    workers = max(1, int(args.num_thread))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = [
            pool.submit(_one, utt, wav, session) for utt, wav in utt2wav.items()
        ]
        for future in as_completed(futures):
            utt, embedding = future.result()
            utt2embedding[utt] = embedding
            spk = utt2spk[utt]
            spk2embedding.setdefault(spk, []).append(embedding)
    averaged = {
        spk: torch.tensor(rows).mean(dim=0).tolist() for spk, rows in spk2embedding.items()
    }
    torch.save(utt2embedding, args.dir / "utt2embedding.pt")
    torch.save(averaged, args.dir / "spk2embedding.pt")
    print(
        f"utterances={len(utt2embedding)} speakers={len(averaged)} "
        f"out={args.dir / 'utt2embedding.pt'}"
    )
    return 0 if utt2embedding else 1


if __name__ == "__main__":
    raise SystemExit(main())
