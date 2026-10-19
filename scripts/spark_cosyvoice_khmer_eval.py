#!/usr/bin/env python3
"""Compare a Khmer CosyVoice candidate with the previous one-epoch checkpoint.

Writes held-out CER, campplus speaker cosine, and a short listening set under
output/spark/cosyvoice-khmer/samples/. Does not load the live server, does not
edit pretrained_models, and does not change the serving config.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
import traceback
from pathlib import Path

import numpy as np
import onnxruntime
import soundfile as sf
import torch
import torchaudio
import torchaudio.compliance.kaldi as kaldi

from aoep_shared.cosyvoice_ingest.khmer_eval import (
    candidate_beats_baseline,
    character_error_rate,
    choose_prompts,
    choose_sample_utts,
    metric_summary,
)


def _patch_torchaudio_load() -> None:
    """torchaudio.load on this box requires TorchCodec. Read wavs with soundfile."""
    from io import BytesIO

    import numpy as np
    import soundfile as sf
    import torchaudio

    def load(source, *args, **kwargs):
        del args, kwargs
        if isinstance(source, (bytes, bytearray, memoryview)):
            source = BytesIO(bytes(source))
        data, sample_rate = sf.read(source, dtype="float32", always_2d=True)
        audio = torch.from_numpy(np.ascontiguousarray(data.T))
        return audio, int(sample_rate)

    torchaudio.load = load


def _force_cpu_onnx() -> None:
    """This host's onnxruntime has no CUDA provider. CosyVoice still asks for one."""
    import onnxruntime as ort

    if getattr(ort, "_aoep_cpu_only", False):
        return
    real = ort.InferenceSession
    available = set(ort.get_available_providers())

    def session(*args, **kwargs):
        providers = kwargs.get("providers")
        if providers:
            kept = [item for item in providers if item in available]
            kwargs["providers"] = kept or ["CPUExecutionProvider"]
        return real(*args, **kwargs)

    ort.InferenceSession = session
    ort._aoep_cpu_only = True


def _load_map(path: Path) -> dict[str, str]:
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8").splitlines():
        text = line.strip()
        if not text:
            continue
        key, value = text.split(maxsplit=1)
        out[key] = value
    return out


def _duration(path: str) -> float:
    info = sf.info(path)
    if info.samplerate <= 0:
        return 0.0
    return float(info.frames) / float(info.samplerate)


def _stage_model(dest: Path, base: Path, llm_ckpt: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    for name in (
        "campplus.onnx",
        "speech_tokenizer_v1.onnx",
        "flow.pt",
        "hift.pt",
        "cosyvoice.yaml",
        "config.json",
        "configuration.json",
    ):
        link = dest / name
        if link.is_symlink() or link.exists():
            link.unlink()
        link.symlink_to(base / name)
    blob = torch.load(llm_ckpt, map_location="cpu", weights_only=False)
    if isinstance(blob, dict):
        blob = {key: value for key, value in blob.items() if key not in ("epoch", "step")}
    torch.save(blob, dest / "llm.pt")


def _embed(path: Path, session: onnxruntime.InferenceSession) -> list[float]:
    data, sample_rate = sf.read(path, dtype="float32", always_2d=True)
    audio = torch.from_numpy(np.ascontiguousarray(data.T))
    if sample_rate != 16000:
        audio = torchaudio.transforms.Resample(orig_freq=sample_rate, new_freq=16000)(audio)
    if audio.shape[0] > 1:
        audio = audio.mean(dim=0, keepdim=True)
    feat = kaldi.fbank(audio, num_mel_bins=80, dither=0, sample_frequency=16000)
    feat = feat - feat.mean(dim=0, keepdim=True)
    embedding = session.run(
        None,
        {session.get_inputs()[0].name: feat.unsqueeze(dim=0).cpu().numpy()},
    )[0].flatten()
    return embedding.tolist()


def _cosine(left: list[float], right: list[float]) -> float:
    a = torch.tensor(left, dtype=torch.float32)
    b = torch.tensor(right, dtype=torch.float32)
    denom = torch.linalg.vector_norm(a) * torch.linalg.vector_norm(b)
    if float(denom) == 0.0:
        return 0.0
    return float(torch.dot(a, b) / denom)


def _synthesize(model, text: str, prompt_text: str, prompt_wav: str, out_path: Path) -> float:
    chunks = []
    for item in model.inference_zero_shot(
        text,
        prompt_text,
        prompt_wav,
        stream=False,
        text_frontend=False,
    ):
        speech = item["tts_speech"]
        if hasattr(speech, "detach"):
            speech = speech.detach().cpu()
        chunks.append(speech)
    if not chunks:
        raise RuntimeError("no audio")
    audio = torch.cat(chunks, dim=-1).squeeze().numpy()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    sf.write(out_path, audio, int(model.sample_rate))
    return float(len(audio)) / float(model.sample_rate)


def _synth_side(
    *,
    name: str,
    model_dir: Path,
    pairs: list[dict],
    text: dict[str, str],
    wavs: dict[str, str],
    out_dir: Path,
) -> list[dict]:
    from cosyvoice.cli.cosyvoice import CosyVoice

    print(f"loading {name} from {model_dir}", flush=True)
    model = CosyVoice(str(model_dir), fp16=False)
    rows = []
    try:
        for index, pair in enumerate(pairs, 1):
            utt = pair["utt"]
            prompt = pair["prompt_utt"]
            dest = out_dir / f"{utt}.wav"
            row = {
                "utt": utt,
                "prompt_utt": prompt,
                "speaker": pair["speaker"],
                "reference": text.get(utt, ""),
                "ok": False,
                "seconds": 0.0,
                "error": "",
            }
            try:
                row["seconds"] = round(
                    _synthesize(model, text[utt], text[prompt], wavs[prompt], dest),
                    3,
                )
                row["ok"] = row["seconds"] >= 0.3 and dest.is_file()
                if not row["ok"]:
                    row["error"] = "too_short"
            except Exception as exc:  # noqa: BLE001 - one bad line should not drop the set
                row["error"] = type(exc).__name__
                print(f"{name} {utt} failed {type(exc).__name__}", flush=True)
                traceback.print_exc()
            rows.append(row)
            if index % 8 == 0 or index == len(pairs):
                print(f"{name} synth {index}/{len(pairs)}", flush=True)
    finally:
        del model
        if torch.cuda.is_available():
            torch.cuda.empty_cache()
    return rows


def _transcribe(paths: list[Path]) -> dict[str, str]:
    import whisper

    device = "cuda" if torch.cuda.is_available() else "cpu"
    print(f"loading whisper large-v3 on {device}", flush=True)
    asr = whisper.load_model("large-v3", device=device)
    found: dict[str, str] = {}
    for index, path in enumerate(paths, 1):
        if not path.is_file():
            found[path.stem] = ""
            continue
        result = asr.transcribe(
            str(path),
            language="km",
            temperature=0,
            fp16=device == "cuda",
            condition_on_previous_text=False,
            verbose=False,
        )
        found[str(path)] = (result.get("text") or "").strip()
        if index % 8 == 0 or index == len(paths):
            print(f"asr {index}/{len(paths)}", flush=True)
    del asr
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    return found


def _score_rows(
    rows: list[dict],
    hypotheses: dict[str, str],
    session: onnxruntime.InferenceSession,
    references: dict[str, str],
) -> list[dict]:
    cache: dict[str, list[float]] = {}
    scored = []
    for row in rows:
        item = dict(row)
        utt = item["utt"]
        synth = item.get("wav")
        item["hypothesis"] = hypotheses.get(str(Path(synth)) if synth else "", "")
        if not item.get("ok") or not synth or not Path(synth).is_file():
            item["ok"] = False
            item["cer"] = None
            item["speaker_similarity"] = None
            scored.append(item)
            continue
        ref_path = references[utt]
        if ref_path not in cache:
            cache[ref_path] = _embed(Path(ref_path), session)
        synth_emb = _embed(Path(synth), session)
        item["cer"] = round(character_error_rate(item["reference"], item["hypothesis"]), 4)
        item["speaker_similarity"] = round(_cosine(synth_emb, cache[ref_path]), 4)
        scored.append(item)
    return scored


def _write_samples(scored: list[dict], sample_utts: list[str], dest: Path) -> None:
    dest.mkdir(parents=True, exist_ok=True)
    manifest = []
    for index, utt in enumerate(sample_utts, 1):
        row = next((item for item in scored if item["utt"] == utt), None)
        if row is None or not row.get("wav"):
            continue
        src = Path(row["wav"])
        if not src.is_file():
            continue
        name = f"{index:02d}_{utt}.wav"
        shutil.copyfile(src, dest / name)
        manifest.append(
            {
                "file": name,
                "utt": utt,
                "speaker": row.get("speaker"),
                "reference": row.get("reference"),
                "hypothesis": row.get("hypothesis"),
                "cer": row.get("cer"),
                "speaker_similarity": row.get("speaker_similarity"),
            }
        )
    (dest / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _report(before: dict, after: dict, decision: dict) -> str:
    def _fmt(value) -> str:
        return "n/a" if value is None else f"{float(value):.4f}"

    lines = [
        "Khmer CosyVoice held-out comparison",
        "====================================",
        f"baseline_scored: {before.get('scored')}",
        f"candidate_scored: {after.get('scored')}",
        f"cer_before: {_fmt(before.get('cer'))}",
        f"cer_after: {_fmt(after.get('cer'))}",
        f"speaker_similarity_before: {_fmt(before.get('speaker_similarity'))}",
        f"speaker_similarity_after: {_fmt(after.get('speaker_similarity'))}",
        f"metric_win: {decision['wins']}",
        f"reasons: {', '.join(decision['reasons']) or 'none'}",
        "serving_config: unchanged",
        "promoted: false",
        "The live sidecar stays on CosyVoice-300M-SFT. This candidate is a",
        "CosyVoice-300M zero-shot LLM and has no enrolled speakers.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, required=True)
    parser.add_argument("--train-dir", type=Path, required=True)
    parser.add_argument("--dev-dir", type=Path, required=True)
    parser.add_argument("--model-src", type=Path, required=True)
    parser.add_argument("--baseline-ckpt", type=Path, required=True)
    parser.add_argument("--candidate-ckpt", type=Path, required=True)
    parser.add_argument("--samples", type=int, default=8)
    args = parser.parse_args()

    if not args.baseline_ckpt.is_file():
        print(f"baseline checkpoint missing: {args.baseline_ckpt}", file=sys.stderr)
        return 2
    if not args.candidate_ckpt.is_file():
        print(f"candidate checkpoint missing: {args.candidate_ckpt}", file=sys.stderr)
        return 2
    _force_cpu_onnx()
    _patch_torchaudio_load()

    train_wav = _load_map(args.train_dir / "wav.scp")
    dev_wav = _load_map(args.dev_dir / "wav.scp")
    train_text = _load_map(args.train_dir / "text")
    dev_text = _load_map(args.dev_dir / "text")
    train_spk = _load_map(args.train_dir / "utt2spk")
    dev_spk = _load_map(args.dev_dir / "utt2spk")
    durations = {utt: _duration(path) for utt, path in {**train_wav, **dev_wav}.items()}
    pairs = choose_prompts(
        list(train_wav),
        list(dev_wav),
        {**train_spk, **dev_spk},
        durations,
    )
    if len(pairs) < 8:
        print(f"only {len(pairs)} eval pairs", file=sys.stderr)
        return 2
    (args.dest / "km").mkdir(parents=True, exist_ok=True)
    (args.dest / "km" / "eval_pairs.json").write_text(
        json.dumps(pairs, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    holdout = args.dest / "samples" / "holdout"
    sides = {}
    for name, ckpt in (("baseline", args.baseline_ckpt), ("candidate", args.candidate_ckpt)):
        model_dir = args.dest / "eval-models" / name
        print(f"staging {name}", flush=True)
        _stage_model(model_dir, args.model_src, ckpt)
        rows = _synth_side(
            name=name,
            model_dir=model_dir,
            pairs=pairs,
            text={**train_text, **dev_text},
            wavs={**train_wav, **dev_wav},
            out_dir=holdout / name,
        )
        for row in rows:
            row["wav"] = str(holdout / name / f"{row['utt']}.wav")
        sides[name] = rows

    wav_paths = [
        Path(row["wav"])
        for rows in sides.values()
        for row in rows
        if row.get("ok")
    ]
    hypotheses = _transcribe(wav_paths)
    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = 1
    session = onnxruntime.InferenceSession(
        str(args.model_src / "campplus.onnx"),
        sess_options=options,
        providers=["CPUExecutionProvider"],
    )
    scored = {
        name: _score_rows(rows, hypotheses, session, {**train_wav, **dev_wav})
        for name, rows in sides.items()
    }
    before = metric_summary(scored["baseline"])
    after = metric_summary(scored["candidate"])
    decision = candidate_beats_baseline(before, after)
    sample_utts = choose_sample_utts(pairs, limit=max(5, min(10, int(args.samples))))
    _write_samples(scored["candidate"], sample_utts, args.dest / "samples")
    _write_samples(scored["baseline"], sample_utts, args.dest / "samples" / "baseline")

    report = {
        "promoted": False,
        "serving_config": "unchanged",
        "baseline_checkpoint": str(args.baseline_ckpt),
        "candidate_checkpoint": str(args.candidate_ckpt),
        "held_out": len(pairs),
        "before": before,
        "after": after,
        "decision": decision,
        "samples": str(args.dest / "samples"),
        "rows": scored,
    }
    (args.dest / "km" / "eval.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    text = _report(before, after, decision)
    (args.dest / "EVAL.txt").write_text(text, encoding="utf-8")
    print(text, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
