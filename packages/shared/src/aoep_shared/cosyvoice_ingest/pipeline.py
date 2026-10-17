"""Orchestrate download → denoise → segment → transcribe → CosyVoice export."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

from ..dictionary_audio import (
    TARGET_SR,
    clean_audio_file,
    read_wav_mono,
    write_wav_mono,
)
from .download import DownloadError, DownloadedMedia, copy_local_media, download_url
from .errors import classify_download_error, classify_qc_reason, sanitize_process_text
from .export import CosyVoiceUtterance, RecipePaths, write_cosyvoice_recipe
from .merge import default_merge_into, merge_language_pool
from .segment import segment_pcm16, slice_pcm16
from .transcribe import TranscriptResult, asr_available, transcribe_wav
from .urls import load_url_list


STAGES = ("download", "denoise", "segment", "transcribe", "export")


@dataclass
class IngestConfig:
    urls_file: Optional[Path] = None
    media_dir: Optional[Path] = None
    output_dir: Path = Path("output/cosyvoice_ingest")
    language: str = "en"
    speaker: str = "auto"
    sample_rate: int = TARGET_SR
    min_utt_sec: float = 1.0
    max_utt_sec: float = 12.0
    silence_db: float = -40.0
    instruct: str = ""
    split_name: str = "train"
    skip_download: bool = False
    allow_empty_transcripts: bool = False
    cosyvoice_repo: Optional[Path] = None
    max_urls: Optional[int] = None
    # After each export, rebuild a language-wide merged recipe for training.
    merge: bool = True
    merge_into: Optional[Path] = None
    merge_scan_root: Optional[Path] = None


@dataclass
class IngestReport:
    ok: bool
    output_dir: str
    recipe_dir: str = ""
    stages: dict = field(default_factory=dict)
    utterances: int = 0
    speakers: int = 0
    asr_available: bool = False
    errors: List[str] = field(default_factory=list)
    error_records: List[dict] = field(default_factory=list)
    error_counts: dict = field(default_factory=dict)
    partial: bool = False
    train_handoff: str = ""
    merge_dir: str = ""
    merge_utterances: int = 0
    merge_train_handoff: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


def _stage_enabled(name: str, start: str, stop: str) -> bool:
    return STAGES.index(start) <= STAGES.index(name) <= STAGES.index(stop)


def _record_error(
    report: IngestReport,
    *,
    category: str,
    stage: str,
    message: str,
    stderr: str = "",
    target: str = "",
) -> None:
    """Store a short string plus a structured record. Stderr is sanitized."""
    clean = sanitize_process_text(stderr, limit=400)
    # One real stderr sample per category. Repeating the same yt-dlp bot page
    # on every URL makes the report unreadably large.
    already = int(report.error_counts.get(category) or 0) > 0
    report.error_records.append(
        {
            "category": category,
            "stage": stage,
            "target": target,
            "message": (message or "")[:180],
            "stderr": "" if already else clean,
        }
    )
    report.error_counts[category] = int(report.error_counts.get(category) or 0) + 1
    report.errors.append(f"{stage}:{category}:{target}")


def run_ingest(
    config: IngestConfig,
    *,
    start_stage: str = "download",
    stop_stage: str = "export",
) -> IngestReport:
    """Run the CosyVoice ingest pipeline.

    Dual-mode knobs (env):
      COSYVOICE_INGEST_ROOT  default output parent
      COSYVOICE_REPO         CosyVoice checkout for TRAIN_HANDOFF.txt
      AOEP_ASR_MODEL / WHISPER_MODEL / FASTER_WHISPER_MODEL
      YT_DLP_BIN
    """
    if start_stage not in STAGES or stop_stage not in STAGES:
        raise ValueError(f"stages must be one of {STAGES}")
    if STAGES.index(start_stage) > STAGES.index(stop_stage):
        raise ValueError("start_stage after stop_stage")

    out = Path(
        config.output_dir
        or os.environ.get("COSYVOICE_INGEST_ROOT", "output/cosyvoice_ingest")
    )
    raw_dir = out / "01_raw"
    clean_dir = out / "02_clean"
    seg_dir = out / "03_segments"
    recipe_root = out / "04_cosyvoice"
    for d in (raw_dir, clean_dir, seg_dir, recipe_root):
        d.mkdir(parents=True, exist_ok=True)

    report = IngestReport(
        ok=True,
        output_dir=str(out.resolve()),
        asr_available=asr_available(),
    )
    media: List[DownloadedMedia] = []
    utterances: List[CosyVoiceUtterance] = []

    # --- download / local stage ---
    if _stage_enabled("download", start_stage, stop_stage):
        try:
            if config.media_dir and (config.skip_download or not config.urls_file):
                media = copy_local_media(Path(config.media_dir), raw_dir)
                report.stages["download"] = {
                    "mode": "local",
                    "count": len(media),
                    "dir": str(raw_dir),
                }
            elif config.urls_file:
                urls = load_url_list(config.urls_file)
                if config.max_urls is not None:
                    urls = urls[: max(0, int(config.max_urls))]
                for url in urls:
                    try:
                        media.append(
                            download_url(url, raw_dir, sample_rate=config.sample_rate)
                        )
                    except DownloadError as exc:
                        _record_error(
                            report,
                            category=exc.category,
                            stage="download",
                            message=str(exc),
                            stderr=exc.stderr,
                            target=url,
                        )
                        report.ok = False
                    except Exception as exc:
                        text = str(exc)
                        _record_error(
                            report,
                            category=classify_download_error(text),
                            stage="download",
                            message=text,
                            stderr=text,
                            target=url,
                        )
                        report.ok = False
                report.stages["download"] = {
                    "mode": "yt-dlp",
                    "requested": len(urls),
                    "ok": len(media),
                    "dir": str(raw_dir),
                }
            else:
                # Resume from existing raw/
                for wav in sorted(raw_dir.glob("*.wav")):
                    media.append(
                        DownloadedMedia(
                            url="",
                            media_id=wav.stem,
                            audio_path=wav,
                            skipped=True,
                            reason="resume",
                        )
                    )
                report.stages["download"] = {
                    "mode": "resume",
                    "count": len(media),
                    "dir": str(raw_dir),
                }
        except Exception as exc:
            text = str(exc)
            _record_error(
                report,
                category=classify_download_error(text),
                stage="download",
                message=text,
                stderr=text,
                target="stage",
            )
            report.ok = False
            report.stages["download"] = {"error": text[:300]}
    else:
        for wav in sorted(raw_dir.glob("*.wav")):
            media.append(
                DownloadedMedia(
                    url="", media_id=wav.stem, audio_path=wav, skipped=True, reason="skip_stage"
                )
            )

    # --- denoise (dictionary_audio) ---
    cleaned: List[tuple[DownloadedMedia, Path, Optional[float]]] = []
    if _stage_enabled("denoise", start_stage, stop_stage):
        ok_n = 0
        rejected = 0
        for m in media:
            dest = clean_dir / f"{m.media_id}.wav"
            result = clean_audio_file(m.audio_path, dest)
            if result.ok and result.crisp_path and result.crisp_path.is_file():
                cleaned.append((m, result.crisp_path, result.snr_db))
                ok_n += 1
                continue
            rejected += 1
            _record_error(
                report,
                category=classify_qc_reason(result.reason),
                stage="denoise",
                message=result.reason or "denoise_reject",
                stderr=result.stderr,
                target=m.media_id,
            )
        report.stages["denoise"] = {
            "inputs": len(media),
            "outputs": len(cleaned),
            "qc_ok": ok_n,
            "rejected": rejected,
            "engine": "dictionary_audio.clean_audio_file",
            "dir": str(clean_dir),
        }
    else:
        for m in media:
            cand = clean_dir / f"{m.media_id}.wav"
            src = cand if cand.is_file() else m.audio_path
            cleaned.append((m, src, None))

    # --- segment ---
    seg_paths: List[tuple[DownloadedMedia, Path, float, Optional[float]]] = []
    if _stage_enabled("segment", start_stage, stop_stage):
        for m, clean_path, snr in cleaned:
            try:
                pcm, rate = read_wav_mono(clean_path)
            except Exception as exc:
                report.errors.append(f"segment_read:{m.media_id}:{exc}")
                continue
            segs = segment_pcm16(
                pcm,
                rate,
                min_utt_sec=config.min_utt_sec,
                max_utt_sec=config.max_utt_sec,
                silence_db=config.silence_db,
            )
            if not segs:
                _record_error(
                    report,
                    category="no_segments",
                    stage="segment",
                    message="no speech segments after denoise",
                    target=m.media_id,
                )
            for i, seg in enumerate(segs):
                utt_id = f"{m.media_id}_{i:04d}"
                piece = slice_pcm16(pcm, seg.start_sample, seg.end_sample)
                dest = seg_dir / f"{utt_id}.wav"
                write_wav_mono(dest, piece, rate)
                seg_paths.append((m, dest, seg.duration_sec, snr))
        report.stages["segment"] = {
            "utterances": len(seg_paths),
            "dir": str(seg_dir),
            "min_utt_sec": config.min_utt_sec,
            "max_utt_sec": config.max_utt_sec,
        }
    else:
        for wav in sorted(seg_dir.glob("*.wav")):
            media_id = wav.stem.rsplit("_", 1)[0]
            m = DownloadedMedia(url="", media_id=media_id, audio_path=wav)
            try:
                pcm, rate = read_wav_mono(wav)
                dur = (len(pcm) / 2) / float(rate or config.sample_rate)
            except Exception:
                dur = 0.0
            seg_paths.append((m, wav, dur, None))

    # --- transcribe ---
    if _stage_enabled("transcribe", start_stage, stop_stage):
        empty = 0
        for m, wav_path, dur, snr in seg_paths:
            tr: TranscriptResult = transcribe_wav(wav_path, language=config.language)
            text = tr.text.strip()
            if not text:
                empty += 1
                if not config.allow_empty_transcripts:
                    # Still record stub utt for debugging when ASR missing?
                    # Skip export of empty — CosyVoice needs text.
                    continue
            if not config.speaker or config.speaker == "auto":
                spk = m.media_id
            else:
                spk = config.speaker.replace(" ", "_")
            utt_id = wav_path.stem
            utterances.append(
                CosyVoiceUtterance(
                    utt_id=utt_id,
                    wav_path=str(wav_path.resolve()),
                    text=text or f"<missing_transcript:{tr.reason}>",
                    spk_id=spk,
                    language=tr.language or config.language,
                    source_url=m.url,
                    duration_sec=dur,
                    snr_db=snr,
                    asr_engine=tr.engine,
                    qc_ok=bool(text) or config.allow_empty_transcripts,
                )
            )
        report.stages["transcribe"] = {
            "segments": len(seg_paths),
            "with_text": sum(1 for u in utterances if u.text and not u.text.startswith("<missing")),
            "empty": empty,
            "asr_available": report.asr_available,
        }
        if not report.asr_available:
            report.errors.append(
                "asr_unavailable: install packages/shared[cosyvoice-ingest] "
                "or set AOEP_ASR_MODEL after installing faster-whisper"
            )
    else:
        # Load prior segments without ASR — cannot invent text
        for m, wav_path, dur, snr in seg_paths:
            spk = (
                m.media_id
                if (not config.speaker or config.speaker == "auto")
                else config.speaker.replace(" ", "_")
            )
            utterances.append(
                CosyVoiceUtterance(
                    utt_id=wav_path.stem,
                    wav_path=str(wav_path.resolve()),
                    text="",
                    spk_id=spk,
                    language=config.language,
                    source_url=m.url,
                    duration_sec=dur,
                    snr_db=snr,
                    asr_engine="skipped",
                    qc_ok=False,
                )
            )

    # --- export ---
    recipe: Optional[RecipePaths] = None
    if _stage_enabled("export", start_stage, stop_stage):
        repo = config.cosyvoice_repo or Path(
            os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")
        )
        recipe = write_cosyvoice_recipe(
            utterances,
            recipe_root,
            language=config.language,
            instruct=config.instruct,
            cosyvoice_repo=repo if repo.exists() else repo,
            split_name=config.split_name,
            meta={
                "urls_file": str(config.urls_file) if config.urls_file else None,
                "media_dir": str(config.media_dir) if config.media_dir else None,
                "stages": report.stages,
                "errors": report.errors,
            },
        )
        report.recipe_dir = str(recipe.data_dir)
        report.train_handoff = str(recipe.train_handoff)
        report.utterances = sum(1 for u in utterances if u.qc_ok and u.text.strip())
        report.speakers = len({u.spk_id for u in utterances if u.qc_ok})
        report.stages["export"] = {
            "recipe_dir": report.recipe_dir,
            "wav_scp": str(recipe.wav_scp),
            "utterances_exported": report.utterances,
        }
        if report.utterances == 0:
            report.ok = False
            report.errors.append(
                "export_empty: no QC-ok utterances with transcripts "
                "(need ASR and/or allow_empty_transcripts for stubs)"
            )
        else:
            # A playlist that lost some URLs to bot checks still exported audio.
            # Those utterances stay trainable. Download failures stay in
            # error_records instead of flipping the whole channel to ok false.
            download_failures = sum(
                1 for rec in report.error_records if rec.get("stage") == "download"
            )
            report.partial = download_failures > 0
            report.ok = True

    # --- merge (always on by default; every channel run refreshes the pool) ---
    if config.merge and _stage_enabled("export", start_stage, stop_stage):
        merge_into = Path(
            config.merge_into
            or os.environ.get("COSYVOICE_MERGE_INTO", "")
            or default_merge_into(config.language)
        )
        scan_root = Path(
            config.merge_scan_root
            or os.environ.get("COSYVOICE_MERGE_SCAN_ROOT", "")
            or out.parent
        )
        repo = config.cosyvoice_repo or Path(
            os.environ.get("COSYVOICE_REPO", "/home/nvidia/code/CosyVoice")
        )
        current = Path(report.recipe_dir) if report.recipe_dir else None
        merge_report = merge_language_pool(
            language=config.language,
            merge_into=merge_into,
            scan_roots=[scan_root],
            current_recipe=current,
            split_name=config.split_name,
            cosyvoice_repo=repo if repo.exists() else repo,
        )
        report.merge_dir = merge_report.dest_dir
        report.merge_utterances = merge_report.utterances
        report.merge_train_handoff = merge_report.train_handoff
        report.stages["merge"] = merge_report.to_dict()
        # Prefer the merged handoff for operators when the pool has data.
        if merge_report.ok and merge_report.train_handoff:
            report.train_handoff = merge_report.train_handoff
        if not merge_report.ok and merge_report.errors:
            # Empty pool while channels are still downloading is expected; keep
            # channel-level ok/errors authoritative for this run.
            report.stages["merge"]["note"] = "merged recipe empty or incomplete"

    # Persist report
    (out / "report.json").write_text(
        json.dumps(report.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return report
