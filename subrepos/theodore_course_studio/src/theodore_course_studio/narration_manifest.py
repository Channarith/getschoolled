"""Versioned narration manifest: render, validate, upload, and publish.

A record is one spoken slide in one language and one voice. Rendering calls
neural_tts.synthesize_course. Duration comes from ffprobe. Upload uses the
shared ProviderFactory object store. The manifest file is replaced only when
every expected record is present and valid.
"""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from .narration_catalog import canonical_hash, safe_token
from .narration_translate import SlideText, read_slide_text, translation_path
from .studio_languages import SUPPORTED_LANGUAGES

MANIFEST_VERSION = 2
# Audio identity changes only when spoken/display text changes. Manifest-only
# timing or visual metadata must not force identical MP3s to be regenerated.
_AUDIO_HASH_VERSION = 1
GENDERS = ("female", "male")
OBJECT_PREFIX = "course-audio/v1"
MANIFEST_OBJECT_KEY = "course-audio/manifest-v2.json"
PUBLIC_FIELDS = (
    "version",
    "slide_key",
    "language",
    "gender",
    "text",
    "display",
    "narration",
    "audio_url",
    "object_key",
    "duration",
    "segments",
    "hash",
)
_MAX_DURATION_S = 1800.0


class AudioPipelineError(RuntimeError):
    """Render, probe, or upload failed."""


class IncompleteManifest(AudioPipelineError):
    """Publication was refused because the manifest is not complete."""

    def __init__(self, problems: Sequence[str]) -> None:
        self.problems = tuple(problems)
        preview = "; ".join(self.problems[:8])
        super().__init__(f"manifest is incomplete: {preview}")


@dataclass(frozen=True)
class NarrationRecord:
    """One published audio row. text is the line sent to the synthesizer."""

    version: int
    slide_key: str
    language: str
    gender: str
    text: str
    display: str
    narration: str
    audio_url: str
    object_key: str
    duration: float
    segments: tuple[dict[str, Any], ...]
    hash: str

    def to_dict(self) -> dict[str, Any]:
        return {field: getattr(self, field) for field in PUBLIC_FIELDS}

    def identity(self) -> tuple[str, str, str]:
        return (self.slide_key, self.language, self.gender)


@dataclass(frozen=True)
class RenderedClip:
    record: NarrationRecord
    clip_path: str

    def absolute_path(self, work_dir: Path) -> Path:
        return work_dir / self.clip_path


def display_for(title: str, body: str) -> str:
    title = (title or "").strip()
    body = (body or "").strip()
    if title and body:
        return f"{title}\n{body}"
    return title or body


def narration_hash(
    *,
    slide_key: str,
    language: str,
    gender: str,
    text: str,
    display: str,
    narration: str,
) -> str:
    return canonical_hash(
        {
            "version": _AUDIO_HASH_VERSION,
            "slide_key": slide_key,
            "language": language,
            "gender": gender,
            "text": text,
            "display": display,
            "narration": narration,
        }
    )


def object_key_for(slide_key: str, language: str, gender: str, digest: str) -> str:
    return (
        f"{OBJECT_PREFIX}/{language}/{gender}/"
        f"{safe_token(slide_key)}-{digest[:12]}.mp3"
    )


def build_record(
    text: SlideText,
    gender: str,
    *,
    audio_url: str = "",
    duration: float = 0.0,
) -> NarrationRecord:
    if gender not in GENDERS:
        raise AudioPipelineError(f"unsupported gender {gender!r}")
    spoken = text.narration.strip()
    display = display_for(text.title, text.body)
    if not spoken or not display:
        raise AudioPipelineError(f"{text.slide_key} has nothing to speak or show")
    digest = narration_hash(
        slide_key=text.slide_key,
        language=text.language,
        gender=gender,
        text=spoken,
        display=display,
        narration=spoken,
    )
    return NarrationRecord(
        version=MANIFEST_VERSION,
        slide_key=text.slide_key,
        language=text.language,
        gender=gender,
        text=spoken,
        display=display,
        narration=spoken,
        audio_url=audio_url,
        object_key=object_key_for(text.slide_key, text.language, gender, digest),
        duration=duration,
        segments=sentence_timeline(spoken, duration) if duration > 0 else (),
        hash=digest,
    )


def split_sentences(text: str) -> list[str]:
    """Language-tolerant sentence/idea segmentation for visual cue alignment."""
    line = re.sub(r"\s+", " ", (text or "").strip())
    if not line:
        return []
    parts = [
        part.strip()
        for part in re.split(r"(?<=[.!?。！？؟។])\s*", line)
        if part.strip()
    ]
    return parts or [line]


def sentence_timeline(text: str, duration: float) -> tuple[dict[str, Any], ...]:
    """Map sentences continuously across a measured clip duration.

    Edge voices do not expose timing marks through every fallback path, so the
    measured full duration is apportioned by spoken-character weight. The audio
    element remains the master clock and the final segment is pinned to its end.
    """
    sentences = split_sentences(text)
    if not sentences or not math.isfinite(duration) or duration <= 0:
        return ()
    weights = [max(1, len(re.sub(r"\s+", "", sentence))) for sentence in sentences]
    total = sum(weights)
    rows: list[dict[str, Any]] = []
    elapsed = 0.0
    for index, (sentence, weight) in enumerate(zip(sentences, weights)):
        end = duration if index == len(sentences) - 1 else elapsed + duration * weight / total
        rows.append(
            {
                "index": index,
                "text": sentence,
                "start_s": round(elapsed, 3),
                "duration_s": round(max(0.001, end - elapsed), 3),
            }
        )
        elapsed = end
    return tuple(rows)


def synthesize_course_audio(text: str, language: str, gender: str) -> bytes:
    """Render one narration with the course studio neural voice."""
    from .neural_tts import synthesize_course

    if gender not in GENDERS:
        raise AudioPipelineError(f"unsupported gender {gender!r}")
    return synthesize_course(text, language, gender=gender)


def open_object_store():
    """Object store selected by aoep_shared ProviderFactory from config."""
    from aoep_shared.config import load_config
    from aoep_shared.factory import ProviderFactory

    return ProviderFactory(load_config()).object_store()


def probe_duration(path: Path) -> float:
    """Return a positive ffprobe duration in seconds, or raise."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise AudioPipelineError("ffprobe is required to validate narration audio")
    proc = subprocess.run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    if proc.returncode != 0:
        detail = (proc.stderr or proc.stdout or "ffprobe failed").strip()
        raise AudioPipelineError(f"ffprobe rejected {path.name}: {detail}")
    raw = (proc.stdout or "").strip()
    try:
        duration = float(raw)
    except ValueError as exc:
        raise AudioPipelineError(
            f"ffprobe returned no duration for {path.name}"
        ) from exc
    if not math.isfinite(duration) or duration <= 0 or duration > _MAX_DURATION_S:
        raise AudioPipelineError(
            f"invalid narration duration {duration} for {path.name}"
        )
    return round(duration, 3)


def sidecar_path(work_dir: Path, slide_key: str, language: str, gender: str) -> Path:
    return work_dir / "sidecars" / language / gender / f"{safe_token(slide_key)}.json"


def read_sidecar(
    work_dir: Path, slide_key: str, language: str, gender: str
) -> RenderedClip | None:
    path = sidecar_path(work_dir, slide_key, language, gender)
    if not path.is_file():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        record = record_from_dict(payload["record"])
        clip_path = str(payload["clip_path"])
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError):
        return None
    if (
        record.slide_key != slide_key
        or record.language != language
        or record.gender != gender
    ):
        return None
    return RenderedClip(record, clip_path)


def write_sidecar(work_dir: Path, clip: RenderedClip) -> None:
    path = sidecar_path(
        work_dir, clip.record.slide_key, clip.record.language, clip.record.gender
    )
    payload = {
        "version": MANIFEST_VERSION,
        "clip_path": clip.clip_path,
        "record": clip.record.to_dict(),
    }
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def require_translations(
    cache_dir: Path,
    slides: Sequence[Any],
    languages: Sequence[str],
) -> list[SlideText]:
    """Load translated slides or raise when a stage ran ahead of translate."""
    loaded: list[SlideText] = []
    missing: list[str] = []
    for slide in slides:
        for language in languages:
            text = read_slide_text(translation_path(cache_dir, language, slide.slide_key))
            if (
                text is None
                or text.slide_key != slide.slide_key
                or text.language != language
            ):
                missing.append(f"{slide.slide_key}/{language}")
            else:
                loaded.append(text)
    if missing:
        preview = ", ".join(missing[:8])
        raise AudioPipelineError(
            f"missing translations ({len(missing)}): {preview}. Run translate first."
        )
    return loaded


def render_audio(
    texts: Sequence[SlideText],
    *,
    genders: Sequence[str],
    work_dir: Path,
    workers: int = 4,
    synthesizer: Callable[..., bytes] | None = None,
) -> list[RenderedClip]:
    """Render each text and gender, reusing a clip whose hash still matches.

    workers renders in parallel. A failed ffprobe deletes that partial file.
    """
    if workers < 1:
        raise AudioPipelineError("workers must be >= 1")
    chosen = tuple(genders)
    for gender in chosen:
        if gender not in GENDERS:
            raise AudioPipelineError(f"unsupported gender {gender!r}")
    synth = synthesizer or synthesize_course_audio
    jobs = [(text, gender) for text in texts for gender in chosen]
    if not jobs:
        return []
    results: list[RenderedClip | None] = [None] * len(jobs)
    errors: list[BaseException] = []
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(render_job, text, gender, work_dir, synth): index
            for index, (text, gender) in enumerate(jobs)
        }
        for future in as_completed(futures):
            index = futures[future]
            try:
                results[index] = future.result()
            except Exception as exc:  # noqa: BLE001 — collected and re-raised
                errors.append(exc)
    if errors:
        raise AudioPipelineError(str(errors[0])) from errors[0]
    return [clip for clip in results if clip is not None]


def render_job(
    text: SlideText,
    gender: str,
    work_dir: Path,
    synthesizer: Callable[..., bytes],
) -> RenderedClip:
    record = build_record(text, gender)
    existing = read_sidecar(work_dir, text.slide_key, text.language, gender)
    if existing is not None and existing.record.hash == record.hash:
        clip = existing.absolute_path(work_dir)
        if clip.is_file() and clip.stat().st_size >= 32:
            try:
                duration = probe_duration(clip)
            except AudioPipelineError:
                clip.unlink(missing_ok=True)
            else:
                reused = with_duration(existing.record, duration)
                rendered = RenderedClip(reused, existing.clip_path)
                write_sidecar(work_dir, rendered)
                return rendered
    relative = (
        Path("clips")
        / text.language
        / gender
        / f"{safe_token(text.slide_key)}-{record.hash[:12]}.mp3"
    )
    destination = work_dir / relative
    destination.parent.mkdir(parents=True, exist_ok=True)
    audio = synthesizer(text.narration, text.language, gender)
    if not isinstance(audio, (bytes, bytearray)) or len(audio) < 32:
        raise AudioPipelineError(f"{text.slide_key} synthesizer returned empty audio")
    temporary = destination.with_suffix(".mp3.part")
    try:
        temporary.write_bytes(bytes(audio))
        duration = probe_duration(temporary)
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    rendered = RenderedClip(with_duration(record, duration), relative.as_posix())
    write_sidecar(work_dir, rendered)
    return rendered


def upload_audio(
    clips: Sequence[RenderedClip],
    *,
    work_dir: Path,
    store: Any | None = None,
) -> list[NarrationRecord]:
    """Upload clips that are not already in the object store.

    A sidecar with the same hash and a non-empty audio URL is left untouched.
    """
    target = store if store is not None else open_object_store()
    uploaded: list[NarrationRecord] = []
    for clip in clips:
        current = read_sidecar(
            work_dir,
            clip.record.slide_key,
            clip.record.language,
            clip.record.gender,
        )
        if _already_uploaded(current, clip.record.hash):
            assert current is not None
            uploaded.append(current.record)
            continue
        path = clip.absolute_path(work_dir)
        if not path.is_file():
            raise AudioPipelineError(f"missing audio file for {clip.record.slide_key}")
        data = path.read_bytes()
        if len(data) < 32:
            raise AudioPipelineError(f"audio file for {clip.record.slide_key} is empty")
        url = target.put(clip.record.object_key, data, content_type="audio/mpeg")
        if not url:
            url = target.url_for(clip.record.object_key)
        if not url:
            raise AudioPipelineError(
                f"object store returned no URL for {clip.record.object_key}"
            )
        record = NarrationRecord(
            version=clip.record.version,
            slide_key=clip.record.slide_key,
            language=clip.record.language,
            gender=clip.record.gender,
            text=clip.record.text,
            display=clip.record.display,
            narration=clip.record.narration,
            audio_url=str(url),
            object_key=clip.record.object_key,
            duration=clip.record.duration,
            segments=clip.record.segments,
            hash=clip.record.hash,
        )
        write_sidecar(work_dir, RenderedClip(record, clip.clip_path))
        uploaded.append(record)
    return uploaded


def publish_manifest(
    path: Path,
    records: Sequence[NarrationRecord],
    *,
    expected: Iterable[tuple[str, str, str]],
) -> None:
    """Atomically publish path only when expected is fully valid.

    An incomplete or invalid set leaves any existing manifest untouched.
    """
    wanted = set(expected)
    problems: list[str] = []
    got: dict[tuple[str, str, str], NarrationRecord] = {}
    for record in records:
        ident = record.identity()
        if ident in got:
            problems.append(f"duplicate {ident[0]}/{ident[1]}/{ident[2]}")
            continue
        problems.extend(record_problems(record))
        got[ident] = record
    for slide_key, language, gender in sorted(wanted - set(got)):
        problems.append(f"missing {slide_key}/{language}/{gender}")
    for slide_key, language, gender in sorted(set(got) - wanted):
        problems.append(f"unexpected {slide_key}/{language}/{gender}")
    if problems:
        raise IncompleteManifest(problems)
    ordered = [got[ident].to_dict() for ident in sorted(got)]
    payload = {
        "version": MANIFEST_VERSION,
        "complete": True,
        "records": ordered,
    }
    atomic_write(path, json.dumps(payload, ensure_ascii=False, indent=2) + "\n")


def upload_manifest(
    path: Path,
    *,
    store: Any | None = None,
    object_key: str = MANIFEST_OBJECT_KEY,
) -> str:
    """Publish the completed mutable index after its local atomic validation."""
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not payload.get("complete") or int(payload.get("version") or 0) != MANIFEST_VERSION:
        raise IncompleteManifest(["manifest file is not complete or current"])
    target = store if store is not None else open_object_store()
    data = path.read_bytes()
    url = target.put(object_key, data, content_type="application/json")
    return str(url or target.url_for(object_key) or "")


def record_problems(record: NarrationRecord) -> list[str]:
    label = f"{record.slide_key}/{record.language}/{record.gender}"
    problems: list[str] = []
    if record.version != MANIFEST_VERSION:
        problems.append(f"{label}: version {record.version}")
    if record.gender not in GENDERS:
        problems.append(f"{label}: gender")
    if record.language not in SUPPORTED_LANGUAGES:
        problems.append(f"{label}: language")
    if not record.text or record.text != record.narration:
        problems.append(f"{label}: text must match narration")
    if not record.display.strip():
        problems.append(f"{label}: display")
    if not record.audio_url:
        problems.append(f"{label}: audio_url")
    if not record.object_key or record.hash[:12] not in record.object_key:
        problems.append(f"{label}: object_key")
    if not math.isfinite(record.duration) or record.duration <= 0:
        problems.append(f"{label}: duration")
    if not record.segments:
        problems.append(f"{label}: segments")
    else:
        expected_start = 0.0
        for index, segment in enumerate(record.segments):
            start = float(segment.get("start_s", -1))
            segment_duration = float(segment.get("duration_s", 0))
            if int(segment.get("index", -1)) != index or not segment.get("text"):
                problems.append(f"{label}: segment {index}")
            if abs(start - expected_start) > 0.02 or segment_duration <= 0:
                problems.append(f"{label}: segment timing {index}")
            expected_start = start + segment_duration
        if abs(expected_start - record.duration) > 0.02:
            problems.append(f"{label}: segment duration")
    expected = narration_hash(
        slide_key=record.slide_key,
        language=record.language,
        gender=record.gender,
        text=record.text,
        display=record.display,
        narration=record.narration,
    )
    if record.hash != expected:
        problems.append(f"{label}: hash")
    return problems


def with_duration(record: NarrationRecord, duration: float) -> NarrationRecord:
    return NarrationRecord(
        version=MANIFEST_VERSION,
        slide_key=record.slide_key,
        language=record.language,
        gender=record.gender,
        text=record.text,
        display=record.display,
        narration=record.narration,
        audio_url=record.audio_url,
        object_key=record.object_key,
        duration=duration,
        segments=sentence_timeline(record.narration, duration),
        hash=record.hash,
    )


def record_from_dict(payload: dict[str, Any]) -> NarrationRecord:
    return NarrationRecord(
        version=int(payload["version"]),
        slide_key=str(payload["slide_key"]),
        language=str(payload["language"]),
        gender=str(payload["gender"]),
        text=str(payload["text"]),
        display=str(payload["display"]),
        narration=str(payload["narration"]),
        audio_url=str(payload.get("audio_url") or ""),
        object_key=str(payload.get("object_key") or ""),
        duration=float(payload.get("duration") or 0),
        segments=tuple(payload.get("segments") or ()),
        hash=str(payload["hash"]),
    )


def atomic_write(path: Path, payload: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as handle:
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(temporary, path)


def _already_uploaded(current: RenderedClip | None, digest: str) -> bool:
    if current is None:
        return False
    record = current.record
    return bool(
        record.hash == digest
        and record.audio_url
        and record.object_key
        and record.duration > 0
    )
