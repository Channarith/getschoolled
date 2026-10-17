#!/usr/bin/env python3
"""Write one CosyVoice parquet list with pyarrow (no pandas).

Upstream make_parquet_list.py imports pandas, which is not installed in the
CosyVoice venv. This writer keeps that venv unchanged.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import pyarrow as pa
import pyarrow.parquet as pq
import torch


def _load_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        key, value = text.split(maxsplit=1)
        out[key] = value
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--src_dir", type=Path, required=True)
    parser.add_argument("--des_dir", type=Path, required=True)
    args = parser.parse_args()
    utt2wav = _load_map(args.src_dir / "wav.scp")
    utt2text = _load_map(args.src_dir / "text")
    utt2spk = _load_map(args.src_dir / "utt2spk")
    utt2embedding = torch.load(args.src_dir / "utt2embedding.pt", map_location="cpu")
    spk2embedding = torch.load(args.src_dir / "spk2embedding.pt", map_location="cpu")
    utt2speech_token = torch.load(args.src_dir / "utt2speech_token.pt", map_location="cpu")
    utts = sorted(utt2wav)
    audio = [Path(utt2wav[utt]).read_bytes() for utt in utts]
    table = pa.table(
        {
            "utt": pa.array(utts, type=pa.string()),
            "audio_data": pa.array(audio, type=pa.binary()),
            "wav": pa.array([utt2wav[utt] for utt in utts], type=pa.string()),
            "text": pa.array([utt2text[utt] for utt in utts], type=pa.string()),
            "spk": pa.array([utt2spk[utt] for utt in utts], type=pa.string()),
            "utt_embedding": pa.array(
                [list(map(float, utt2embedding[utt])) for utt in utts],
                type=pa.list_(pa.float32()),
            ),
            "spk_embedding": pa.array(
                [list(map(float, spk2embedding[utt2spk[utt]])) for utt in utts],
                type=pa.list_(pa.float32()),
            ),
            "speech_token": pa.array(
                [list(map(int, utt2speech_token[utt])) for utt in utts],
                type=pa.list_(pa.int32()),
            ),
        }
    )
    args.des_dir.mkdir(parents=True, exist_ok=True)
    parquet_path = args.des_dir / "parquet_000000000.parquet"
    pq.write_table(table, parquet_path)
    (args.des_dir / "data.list").write_text(str(parquet_path.resolve()) + "\n", encoding="utf-8")
    print(f"utterances={len(utts)} parquet={parquet_path}")
    return 0 if utts else 1


if __name__ == "__main__":
    raise SystemExit(main())
