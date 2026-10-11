"""Emit CosyVoice recipe manifests (wav.scp / text / utt2spk / spk2utt)."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Mapping, Optional, Sequence


@dataclass
class CosyVoiceUtterance:
    utt_id: str
    wav_path: str
    text: str
    spk_id: str
    language: str = "en"
    source_url: str = ""
    duration_sec: float = 0.0
    snr_db: Optional[float] = None
    asr_engine: str = ""
    qc_ok: bool = True


@dataclass
class RecipePaths:
    data_dir: Path
    wav_scp: Path
    text: Path
    utt2spk: Path
    spk2utt: Path
    utt2lang: Path
    meta_json: Path
    train_handoff: Path


def _kaldi_line(key: str, value: str) -> str:
    # CosyVoice prepare_data / make_parquet_list split on whitespace: key first token.
    key = key.replace(" ", "_").strip()
    value = " ".join(value.split())
    return f"{key} {value}\n"


def build_spk2utt(utt2spk: Mapping[str, str]) -> Dict[str, List[str]]:
    spk2utt: Dict[str, List[str]] = {}
    for utt, spk in utt2spk.items():
        spk2utt.setdefault(spk, []).append(utt)
    for spk in spk2utt:
        spk2utt[spk].sort()
    return spk2utt


def write_cosyvoice_recipe(
    utterances: Sequence[CosyVoiceUtterance],
    data_dir: Path | str,
    *,
    language: str = "en",
    instruct: str = "",
    meta: Optional[Mapping[str, object]] = None,
    cosyvoice_repo: Optional[Path] = None,
    split_name: str = "train",
) -> RecipePaths:
    """Write Kaldi-style lists CosyVoice ``run.sh`` stage 0 expects.

    Layout (under ``data_dir`` / ``split_name``)::

        wav.scp   utt_id /abs/or/rel/path.wav
        text      utt_id transcript words...
        utt2spk   utt_id spk_id
        spk2utt   spk_id utt_a utt_b ...
        utt2lang  utt_id lang   (AOEP sidecar; CosyVoice core ignores)
        instruct  optional (CosyVoice instruct2 recipes)
        meta.json pipeline provenance
        TRAIN_HANDOFF.txt how to continue in the CosyVoice checkout
    """
    root = Path(data_dir) / split_name
    root.mkdir(parents=True, exist_ok=True)

    # Only export QC-ok rows with non-empty text (CosyVoice training needs text).
    rows = [u for u in utterances if u.qc_ok and (u.text or "").strip() and u.wav_path]
    utt2wav = {u.utt_id: str(Path(u.wav_path).resolve()) for u in rows}
    utt2text = {u.utt_id: " ".join(u.text.split()) for u in rows}
    utt2spk = {u.utt_id: u.spk_id.replace(" ", "_") for u in rows}
    utt2lang = {u.utt_id: (u.language or language) for u in rows}
    spk2utt = build_spk2utt(utt2spk)

    wav_scp = root / "wav.scp"
    text_p = root / "text"
    utt2spk_p = root / "utt2spk"
    spk2utt_p = root / "spk2utt"
    utt2lang_p = root / "utt2lang"
    instruct_p = root / "instruct"
    meta_p = root / "meta.json"
    handoff_p = root / "TRAIN_HANDOFF.txt"

    with wav_scp.open("w", encoding="utf-8") as f:
        for k in sorted(utt2wav):
            f.write(_kaldi_line(k, utt2wav[k]))
    with text_p.open("w", encoding="utf-8") as f:
        for k in sorted(utt2text):
            f.write(_kaldi_line(k, utt2text[k]))
    with utt2spk_p.open("w", encoding="utf-8") as f:
        for k in sorted(utt2spk):
            f.write(_kaldi_line(k, utt2spk[k]))
    with spk2utt_p.open("w", encoding="utf-8") as f:
        for spk in sorted(spk2utt):
            f.write(f"{spk} {' '.join(spk2utt[spk])}\n")
    with utt2lang_p.open("w", encoding="utf-8") as f:
        for k in sorted(utt2lang):
            f.write(_kaldi_line(k, utt2lang[k]))

    if instruct:
        with instruct_p.open("w", encoding="utf-8") as f:
            for k in sorted(utt2text):
                f.write(_kaldi_line(k, instruct))

    payload = {
        "format": "cosyvoice_kaldi_lists",
        "compatible_with": [
            "CosyVoice/examples/libritts/cosyvoice/local/prepare_data.py",
            "CosyVoice/examples/libritts/cosyvoice2/run.sh stages 0–3,5",
            "CosyVoice/tools/make_parquet_list.py",
        ],
        "split": split_name,
        "language": language,
        "utterance_count": len(rows),
        "speaker_count": len(spk2utt),
        "sample_rate_hz": 24000,
        "utterances": [asdict(u) for u in rows],
        "note": (
            "Operator-supplied media only; do not ship third-party copyrighted "
            "corpora. CosyVoice train needs pretrained weights + GPU in the "
            "CosyVoice checkout — this export is data prep only."
        ),
    }
    if meta:
        payload["pipeline"] = dict(meta)
    meta_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    handoff_p.write_text(
        render_train_handoff(
            data_dir=root,
            cosyvoice_repo=cosyvoice_repo,
            split_name=split_name,
            has_instruct=bool(instruct),
        ),
        encoding="utf-8",
    )

    return RecipePaths(
        data_dir=root,
        wav_scp=wav_scp,
        text=text_p,
        utt2spk=utt2spk_p,
        spk2utt=spk2utt_p,
        utt2lang=utt2lang_p,
        meta_json=meta_p,
        train_handoff=handoff_p,
    )


def render_train_handoff(
    *,
    data_dir: Path,
    cosyvoice_repo: Optional[Path],
    split_name: str,
    has_instruct: bool,
) -> str:
    """Document real CosyVoice train entrypoints (no invented APIs)."""
    repo = cosyvoice_repo or Path(
        __import__("os").environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")
    )
    recipe = repo / "examples" / "libritts" / "cosyvoice2"
    abs_data = data_dir.resolve()
    lines = [
        "CosyVoice train handoff (generated by aoep_shared.cosyvoice_ingest)",
        "================================================================",
        "",
        "This directory already has stage-0 Kaldi lists:",
        f"  {abs_data / 'wav.scp'}",
        f"  {abs_data / 'text'}",
        f"  {abs_data / 'utt2spk'}",
        f"  {abs_data / 'spk2utt'}",
        f"  {abs_data / 'utt2lang'}  (AOEP sidecar; not required by CosyVoice)",
        "",
        f"CosyVoice checkout (set COSYVOICE_REPO): {repo}",
        f"Reference recipe: {recipe / 'run.sh'}",
        "",
        "Blocked / required outside this pipeline:",
        "  - CosyVoice pretrained weights under pretrained_models/ (e.g. CosyVoice2-0.5B)",
        "  - CUDA GPU(s) for train.py; Docker image optional (CosyVoice/docker)",
        "  - Python env from CosyVoice/requirements.txt + Matcha-TTS submodule",
        "  - Optional offline feature extract (campplus + speech tokenizer ONNX)",
        "",
        "Continue from CosyVoice (after copying or symlinking this split into data/):",
        "",
        f"  cd {recipe}",
        f"  mkdir -p data/{split_name}",
        f"  ln -sfn {abs_data}/wav.scp data/{split_name}/wav.scp",
        f"  ln -sfn {abs_data}/text data/{split_name}/text",
        f"  ln -sfn {abs_data}/utt2spk data/{split_name}/utt2spk",
        f"  ln -sfn {abs_data}/spk2utt data/{split_name}/spk2utt",
        "",
        "  # Stage 1–2 optional when using online features (see run.sh comments):",
        "  python ../../../tools/extract_embedding.py --dir data/"
        + split_name
        + " --onnx_path ../../../pretrained_models/CosyVoice2-0.5B/campplus.onnx",
        "  python ../../../tools/extract_speech_token.py --dir data/"
        + split_name
        + " --onnx_path ../../../pretrained_models/CosyVoice2-0.5B/speech_tokenizer_v3.onnx",
        "",
        "  # Stage 3 — parquet lists consumed by train.py:",
        f"  mkdir -p data/{split_name}/parquet",
        "  python ../../../tools/make_parquet_list.py --num_utts_per_parquet 1000 \\",
        f"    --src_dir data/{split_name} --des_dir data/{split_name}/parquet",
        "",
        "  # Stage 5 — real train entrypoint (CosyVoice2 LLM/flow/hifigan):",
        f"  cat data/{split_name}/parquet/data.list > data/train.data.list",
        "  # Provide a held-out split as data/dev.data.list the same way.",
        "  export CUDA_VISIBLE_DEVICES=0",
        "  torchrun --nnodes=1 --nproc_per_node=1 \\",
        "    --rdzv_id=1986 --rdzv_backend=c10d --rdzv_endpoint=localhost:1234 \\",
        "    ../../../cosyvoice/bin/train.py \\",
        "    --train_engine torch_ddp \\",
        "    --config conf/cosyvoice2.yaml \\",
        "    --train_data data/train.data.list \\",
        "    --cv_data data/dev.data.list \\",
        "    --qwen_pretrain_path ../../../pretrained_models/CosyVoice2-0.5B/CosyVoice-BlankEN \\",
        "    --model llm \\",
        "    --checkpoint ../../../pretrained_models/CosyVoice2-0.5B/llm.pt \\",
        "    --model_dir $(pwd)/exp/cosyvoice2/llm/torch_ddp \\",
        "    --tensorboard_dir $(pwd)/tensorboard/cosyvoice2/llm/torch_ddp \\",
        "    --num_workers 2 --prefetch 100 --pin_memory --use_amp",
        "",
        "Or run the stock recipe with stage/stop_stage after placing lists under data/<split>:",
        "  bash run.sh   # edit pretrained_model_dir + data paths first",
        "",
    ]
    if has_instruct:
        lines.append("instruct file present — keep it beside wav.scp for instruct2 / DPO recipes.")
        lines.append("")
    return "\n".join(lines)
