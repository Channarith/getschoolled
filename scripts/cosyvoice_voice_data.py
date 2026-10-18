#!/usr/bin/env python3
"""Grow Khmer and Salane CosyVoice data under output/spark/voice-data.

Uses the denoise / segment / transcribe / export pipeline on raw wavs that
are already on disk, plus FLEURS Khmer (CC-BY-4.0) gold transcripts. YouTube
URLs are not downloaded unless YT_DLP_COOKIES or COSYVOICE_COOKIES_FILE is
set to a path. This script never reads or prints that file.

Salane is the live class speaker id (sala / salane), not a language pool.
Studio recordings would live in voices/sala or voices/salane. None are invented.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import shutil
import subprocess
import sys
import wave
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "packages" / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))


def _cookies_configured() -> bool:
    for name in ("YT_DLP_COOKIES", "COSYVOICE_COOKIES_FILE"):
        if os.environ.get(name, "").strip():
            return True
    return False


class _GpuLock:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.handle = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.handle = self.path.open("a", encoding="utf-8")
        fcntl.flock(self.handle.fileno(), fcntl.LOCK_EX)
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        if self.handle is not None:
            fcntl.flock(self.handle.fileno(), fcntl.LOCK_UN)
            self.handle.close()


def _duration(path: Path) -> float:
    try:
        with wave.open(str(path), "rb") as handle:
            rate = handle.getframerate() or 1
            return handle.getnframes() / float(rate)
    except (wave.Error, OSError, EOFError):
        return 0.0


def _stage_local(rows: list[dict], stage_root: Path) -> list[Path]:
    """Copy or trim selected raw files into per-channel media dirs."""
    channels = []
    by_channel: dict[str, list[dict]] = {}
    for row in rows:
        by_channel.setdefault(row["channel"], []).append(row)
    for channel, items in by_channel.items():
        dest = stage_root / channel
        dest.mkdir(parents=True, exist_ok=True)
        for item in items:
            target = dest / f"{item['stem']}.wav"
            if target.is_file() and target.stat().st_size > 1000:
                continue
            take = item.get("take_sec")
            if take:
                subprocess.run(
                    [
                        "ffmpeg", "-y", "-i", str(item["path"]),
                        "-t", str(take),
                        "-ar", "24000", "-ac", "1", "-sample_fmt", "s16",
                        str(target),
                    ],
                    check=True,
                    capture_output=True,
                    timeout=600,
                )
            else:
                if target.exists():
                    target.unlink()
                try:
                    os.link(item["path"], target)
                except OSError:
                    shutil.copy2(item["path"], target)
        channels.append(dest)
    return channels


def _ingest_channel(media_dir: Path, output_dir: Path, language: str) -> dict:
    from aoep_shared.cosyvoice_ingest.pipeline import IngestConfig, run_ingest

    speaker = media_dir.name
    if speaker.startswith("cosyvoice_"):
        speaker = speaker[len("cosyvoice_") :]
    report = run_ingest(
        IngestConfig(
            media_dir=media_dir,
            output_dir=output_dir,
            language=language,
            speaker=speaker,
            skip_download=True,
            merge=False,
            cosyvoice_repo=Path(os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")),
        )
    )
    return report.to_dict()


def _extract_fleurs(src_root: Path, audio_root: Path) -> None:
    audio_root.mkdir(parents=True, exist_ok=True)
    if any(audio_root.rglob("*.wav")):
        return
    tars = sorted(src_root.rglob("*.tar.gz"))
    if not tars:
        raise FileNotFoundError(f"no FLEURS tarballs under {src_root}")
    for tar in tars:
        subprocess.run(
            ["tar", "-xzf", str(tar), "-C", str(audio_root)],
            check=True,
            timeout=1800,
        )


def _qc_fleurs(paired: list[dict], clean_dir: Path, *, language: str, gold_max_sec: float):
    from aoep_shared.cosyvoice_ingest.export import CosyVoiceUtterance
    from aoep_shared.cosyvoice_ingest.quality import transcript_reject_reason
    from aoep_shared.dictionary_audio import clean_audio_file, estimate_qc, read_wav_mono

    clean_dir.mkdir(parents=True, exist_ok=True)
    reasons: Counter = Counter()
    utterances = []
    long_clips = []
    for index, row in enumerate(paired):
        utt_id = f"fleurs_{index:05d}_{Path(row['filename']).stem}"[:80]
        dest = clean_dir / f"{utt_id}.wav"
        if dest.is_file() and dest.stat().st_size > 1000:
            try:
                pcm, rate = read_wav_mono(dest)
                ok, reason, snr, dur = estimate_qc(pcm, rate)
            except Exception as exc:
                reasons[f"read_failed:{exc}"] += 1
                continue
        else:
            result = clean_audio_file(row["wav"], dest)
            ok, reason, snr, dur = result.ok, result.reason, result.snr_db, result.duration_sec
            if not result.crisp_path:
                reasons[reason or "denoise_reject"] += 1
                continue
        if not ok:
            reasons[reason or "denoise_reject"] += 1
            continue
        if dur < 1.0:
            reasons["too_short"] += 1
            continue
        why = transcript_reject_reason(row["text"], language)
        if why:
            reasons[why] += 1
            continue
        if dur > gold_max_sec:
            long_clips.append((utt_id, dest, row["text"], snr, dur))
            reasons["held_for_segment"] += 1
            continue
        utterances.append(
            CosyVoiceUtterance(
                utt_id=utt_id,
                wav_path=str(dest.resolve()),
                text=row["text"],
                spk_id="fleurs_km",
                language=language,
                source_url="huggingface://google/fleurs/data/km_kh",
                duration_sec=float(dur),
                snr_db=snr,
                asr_engine="fleurs-transcript",
                qc_ok=True,
            )
        )
        if (index + 1) % 200 == 0:
            print(f"fleurs qc {index + 1}/{len(paired)} kept={len(utterances)}", flush=True)
    return utterances, reasons, long_clips


def _segment_long_clips(long_clips: list, seg_dir: Path, *, language: str) -> tuple[list, Counter]:
    from aoep_shared.cosyvoice_ingest.export import CosyVoiceUtterance
    from aoep_shared.cosyvoice_ingest.quality import transcript_reject_reason
    from aoep_shared.cosyvoice_ingest.segment import segment_pcm16, slice_pcm16
    from aoep_shared.cosyvoice_ingest.transcribe import transcribe_wav
    from aoep_shared.dictionary_audio import read_wav_mono, write_wav_mono

    seg_dir.mkdir(parents=True, exist_ok=True)
    reasons: Counter = Counter()
    utterances = []
    for utt_id, path, _gold, snr, _dur in long_clips:
        try:
            pcm, rate = read_wav_mono(path)
        except Exception as exc:
            reasons[f"segment_read:{exc}"] += 1
            continue
        segs = segment_pcm16(pcm, rate, min_utt_sec=1.0, max_utt_sec=12.0)
        if not segs:
            reasons["no_segments"] += 1
            continue
        for index, seg in enumerate(segs):
            piece = slice_pcm16(pcm, seg.start_sample, seg.end_sample)
            dest = seg_dir / f"{utt_id}_{index:04d}.wav"
            write_wav_mono(dest, piece, rate)
            tr = transcribe_wav(dest, language=language)
            text = (tr.text or "").strip()
            if not text:
                reasons["empty_transcript"] += 1
                continue
            why = transcript_reject_reason(text, language)
            if why:
                reasons[why] += 1
                continue
            utterances.append(
                CosyVoiceUtterance(
                    utt_id=dest.stem,
                    wav_path=str(dest.resolve()),
                    text=text,
                    spk_id="fleurs_km",
                    language=language,
                    source_url="huggingface://google/fleurs/data/km_kh",
                    duration_sec=seg.duration_sec,
                    snr_db=snr,
                    asr_engine=tr.engine,
                    qc_ok=True,
                )
            )
    return utterances, reasons


def _write_recipe(utterances: list, dest_root: Path, *, language: str, note: str) -> Path:
    from aoep_shared.cosyvoice_ingest.export import write_cosyvoice_recipe

    recipe = write_cosyvoice_recipe(
        utterances,
        dest_root / "04_cosyvoice",
        language=language,
        cosyvoice_repo=Path(os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")),
        meta={"note": note, "language": language},
    )
    return recipe.data_dir


def _finalize_recipe(recipe_dir: Path, *, language: str, note: str) -> dict:
    from aoep_shared.cosyvoice_ingest.export import render_train_handoff
    from aoep_shared.cosyvoice_ingest.spark_manifest import dedupe_recipe_by_audio_hash

    stats = dedupe_recipe_by_audio_hash(recipe_dir)
    handoff = recipe_dir / "TRAIN_HANDOFF.txt"
    body = render_train_handoff(
        data_dir=recipe_dir,
        cosyvoice_repo=Path(os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")),
        split_name=recipe_dir.name,
        has_instruct=False,
    )
    minutes = float(stats["seconds"]) / 60.0
    extra = [
        "Corpus counts",
        "-------------",
        f"language: {language}",
        f"utterances: {stats['utterances']}",
        f"speakers: {stats['speakers']}",
        f"clean_seconds: {stats['seconds']}",
        f"clean_minutes: {minutes:.2f}",
        f"dropped_duplicate_audio: {stats['dropped_duplicate_audio']}",
        f"dropped_missing: {stats['dropped_missing']}",
        f"note: {note}",
        "",
    ]
    handoff.write_text(body + "\n" + "\n".join(extra), encoding="utf-8")
    meta_path = recipe_dir / "meta.json"
    meta = {}
    if meta_path.is_file():
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            meta = {}
    meta.update(
        {
            "language": language,
            "utterance_count": stats["utterances"],
            "speaker_count": stats["speakers"],
            "duration_seconds": stats["seconds"],
            "clean_minutes": round(minutes, 2),
            "note": note,
        }
    )
    meta_path.write_text(json.dumps(meta, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    stats["train_handoff"] = str(handoff.resolve())
    stats["clean_minutes"] = round(minutes, 2)
    return stats


def _baseline(scan_root: Path) -> dict:
    import hashlib

    merged = scan_root / "cosyvoice_km_merged" / "04_cosyvoice" / "train" / "wav.scp"
    seen = set()
    seconds = 0.0
    listed = 0
    missing = 0
    if not merged.is_file():
        return {"utterances": 0, "seconds": 0.0, "minutes": 0.0, "listed": 0, "missing": 0}
    for line in merged.read_text(encoding="utf-8").splitlines():
        parts = line.split(maxsplit=1)
        if len(parts) < 2:
            continue
        listed += 1
        audio = Path(parts[1])
        if not audio.is_file():
            missing += 1
            continue
        digest = hashlib.sha256(audio.read_bytes()).hexdigest()
        if digest in seen:
            continue
        seen.add(digest)
        seconds += _duration(audio)
    return {
        "utterances": len(seen),
        "seconds": round(seconds, 3),
        "minutes": round(seconds / 60.0, 2),
        "listed": listed,
        "missing": missing,
    }


def _salane_sources(scan_root: Path, voices_root: Path) -> dict:
    from aoep_shared.cosyvoice_ingest.spark_manifest import count_salane

    counted = count_salane(scan_root, voices_root if voices_root.is_dir() else None)
    studio = []
    if voices_root.is_dir():
        for folder in ("sala", "salane"):
            base = voices_root / folder
            if base.is_dir():
                studio.extend(str(path) for path in base.rglob("*") if path.is_file())
    return {"count": counted, "studio_files": studio}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dest", type=Path, default=ROOT / "output" / "spark" / "voice-data")
    parser.add_argument("--scan-root", type=Path, default=Path("/home/nvidia/code/getschoolled/output"))
    parser.add_argument("--voices-root", type=Path, default=ROOT / "voices")
    parser.add_argument("--fleurs-root", type=Path, default=None)
    parser.add_argument("--lesson-budget-sec", type=float, default=20 * 60)
    parser.add_argument("--gpu-lock", type=Path, default=Path.home() / ".gs-gpu.lock")
    parser.add_argument("--skip-local", action="store_true")
    parser.add_argument("--skip-fleurs", action="store_true")
    args = parser.parse_args(argv)

    os.environ.setdefault("AOEP_ASR_ENGINE", "openai")
    os.environ.setdefault("AOEP_ASR_MODEL", "large-v3")
    os.environ.setdefault("AOEP_ASR_DEVICE", "cuda")

    from aoep_shared.cosyvoice_ingest.licensed import index_wavs, pair_fleurs_rows, parse_fleurs_tsv
    from aoep_shared.cosyvoice_ingest.local_pool import select_local_khmer

    dest = args.dest
    dest.mkdir(parents=True, exist_ok=True)
    fleurs_root = args.fleurs_root or (dest / "sources" / "fleurs")
    baseline = _baseline(args.scan_root) if args.scan_root.is_dir() else {
        "utterances": 0, "seconds": 0.0, "minutes": 0.0, "listed": 0, "missing": 0
    }
    salane_before = _salane_sources(args.scan_root, args.voices_root)
    summary = {
        "youtube_cookies_set": _cookies_configured(),
        "youtube": "skipped" if not _cookies_configured() else "not_run_this_batch",
        "before": {"km": baseline, "salane": salane_before["count"]},
        "reject_reasons": {},
    }
    (dest / "before.json").write_text(json.dumps(summary["before"], indent=2) + "\n", encoding="utf-8")

    recipes: list[Path] = []
    if not args.skip_local and args.scan_root.is_dir():
        rows = select_local_khmer(args.scan_root, lesson_budget_sec=args.lesson_budget_sec)
        summary["local_selected"] = [
            {
                "channel": row["channel"],
                "stem": row["stem"],
                "duration_sec": round(row["duration_sec"], 2),
                "take_sec": row["take_sec"],
                "kind": row["kind"],
            }
            for row in rows
        ]
        print(f"local files {len(rows)}", flush=True)
        stage_root = dest / "staged" / "km"
        channels = _stage_local(rows, stage_root)
        local_reasons: Counter = Counter()
        with _GpuLock(args.gpu_lock):
            for media_dir in channels:
                out = dest / "km" / "channels" / media_dir.name
                print(f"ingest {media_dir.name}", flush=True)
                report = _ingest_channel(media_dir, out, "km")
                (out / "report.json").write_text(
                    json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
                )
                for key, count in (report.get("error_counts") or {}).items():
                    local_reasons[key] += int(count)
                transcribe = (report.get("stages") or {}).get("transcribe") or {}
                for key, count in (transcribe.get("rejected_transcript") or {}).items():
                    local_reasons[f"transcript:{key}"] += int(count)
                recipe = out / "04_cosyvoice" / "train"
                if (recipe / "wav.scp").is_file() and recipe.joinpath("wav.scp").stat().st_size > 0:
                    recipes.append(recipe)
        summary["reject_reasons"]["local"] = dict(local_reasons)

    fleurs_reasons: Counter = Counter()
    if not args.skip_fleurs:
        audio_root = dest / "sources" / "fleurs_wav"
        try:
            _extract_fleurs(fleurs_root, audio_root)
        except FileNotFoundError as exc:
            fleurs_reasons["missing_tarball"] += 1
            summary["fleurs_error"] = str(exc)
        else:
            rows = []
            tsv_dir = next(fleurs_root.rglob("km_kh"), None)
            if tsv_dir is None:
                fleurs_reasons["missing_tsv"] += 1
            else:
                for tsv in sorted(tsv_dir.glob("*.tsv")):
                    rows.extend(parse_fleurs_tsv(tsv))
            wavs = index_wavs(audio_root)
            paired, missing = pair_fleurs_rows(rows, wavs)
            fleurs_reasons["missing_audio"] += missing
            print(f"fleurs rows {len(rows)} paired {len(paired)}", flush=True)
            utterances, qc_reasons, long_clips = _qc_fleurs(
                paired, dest / "km" / "fleurs" / "02_clean", language="km", gold_max_sec=30.0
            )
            fleurs_reasons.update(qc_reasons)
            if long_clips:
                print(f"fleurs long clips {len(long_clips)}", flush=True)
                with _GpuLock(args.gpu_lock):
                    extra, seg_reasons = _segment_long_clips(
                        long_clips, dest / "km" / "fleurs" / "03_segments", language="km"
                    )
                utterances.extend(extra)
                fleurs_reasons.update(seg_reasons)
            if utterances:
                recipe_dir = _write_recipe(
                    utterances,
                    dest / "km" / "fleurs",
                    language="km",
                    note="FLEURS Khmer CC-BY-4.0 gold transcripts after denoise QC.",
                )
                recipes.append(recipe_dir)
        summary["reject_reasons"]["fleurs"] = dict(fleurs_reasons)

    from aoep_shared.cosyvoice_ingest.merge import merge_cosyvoice_recipes

    km_dest = dest / "km" / "04_cosyvoice"
    if recipes:
        merge_cosyvoice_recipes(
            recipes,
            km_dest,
            language="km",
            cosyvoice_repo=Path(os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")),
        )
        km_stats = _finalize_recipe(
            km_dest / "train",
            language="km",
            note=(
                "Deduped Khmer pool. YouTube downloads were skipped because no cookies "
                "file was configured. FLEURS text is the corpus transcript. Local "
                "channel text is large-v3 ASR and must be mostly Khmer script."
            ),
        )
    else:
        km_stats = _finalize_recipe(
            _write_recipe([], km_dest, language="km", note="No Khmer clips passed QC."),
            language="km",
            note="No Khmer clips passed QC.",
        )
    summary["after_km"] = km_stats

    salane_note = (
        "No Salane studio recordings. voices/sala and voices/salane are absent, "
        "and no recipe speaker id matches sala or salane. YouTube cannot fill "
        "this speaker. Record a consented studio set before retraining Salane."
    )
    salane_recipe = _write_recipe([], dest / "salane", language="salane", note=salane_note)
    salane_stats = _finalize_recipe(salane_recipe, language="salane", note=salane_note)
    summary["after_salane"] = salane_stats
    summary["target_minutes"] = 30
    summary["km_reaches_30_min"] = float(km_stats.get("clean_minutes") or 0) >= 30
    summary["salane_reaches_30_min"] = float(salane_stats.get("clean_minutes") or 0) >= 30

    (dest / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    lines = [
        "Voice data growth",
        f"youtube: {summary['youtube']}",
        f"km before utterances={baseline['utterances']} minutes={baseline['minutes']}",
        f"km after utterances={km_stats.get('utterances')} minutes={km_stats.get('clean_minutes')}",
        f"salane before utterances={salane_before['count'].get('training_utterances')} "
        f"minutes={round(float(salane_before['count'].get('duration_seconds') or 0) / 60.0, 2)}",
        f"salane after utterances={salane_stats.get('utterances')} minutes={salane_stats.get('clean_minutes')}",
        f"km TRAIN_HANDOFF: {km_stats.get('train_handoff')}",
        f"salane TRAIN_HANDOFF: {salane_stats.get('train_handoff')}",
        f"reject_reasons: {json.dumps(summary['reject_reasons'], ensure_ascii=False)}",
    ]
    (dest / "SUMMARY.txt").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
