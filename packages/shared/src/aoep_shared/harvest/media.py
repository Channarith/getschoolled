"""Audio + demo-video export for harvested courses."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

if TYPE_CHECKING:
    from .generate import GeneratedCourse

_SAFE = re.compile(r"[^a-zA-Z0-9._-]+")

# Subject/topic hints -> repo-relative demo clip for "watch and learn" slides.
_DEMO_CLIPS: List[tuple] = [
    (("algebra", "math", "fraction", "calculus"), "docs/demos/sample_demo_class_walkthrough.gif"),
    (("ai", "ml", "machine", "pattern", "predict", "data"), "docs/demos/salareen_20_minute_expert.mp4"),
    (("language", "spanish", "french", "esl"), "docs/demos/language_learning_demo.gif"),
    (("kid", "child", "elementary"), "docs/demos/kids_mode_platform_demo.gif"),
    (("career", "job", "engineer"), "docs/demos/careers_jobs_matching_demo.gif"),
    (("drive", "audio", "commute"), "docs/demos/drive_mode_audio_courses_demo.gif"),
]
_DEFAULT_DEMO = "docs/demos/platform_walkthrough.mp4"


def pick_demo_video(*, subject: str, title: str, repo_root: Optional[Path] = None) -> Optional[str]:
    """Return a repo-relative demo clip path when one exists on disk."""
    hay = f"{subject} {title}".lower()
    root = repo_root or Path.cwd()
    for keywords, rel in _DEMO_CLIPS:
        if any(k in hay for k in keywords):
            if (root / rel).is_file():
                return rel
    if (root / _DEFAULT_DEMO).is_file():
        return _DEFAULT_DEMO
    return None


def _slug(text: str, *, max_len: int = 48) -> str:
    s = _SAFE.sub("_", (text or "slide").strip()).strip("_").lower()
    return (s[:max_len] or "slide")


def tts_available() -> bool:
    return shutil.which("say") is not None or shutil.which("espeak") is not None


def _audio_has_content(path: Path) -> bool:
    if not path.is_file():
        return False
    if path.stat().st_size < 512:
        return False
    if shutil.which("afinfo"):
        try:
            out = subprocess.run(
                ["afinfo", str(path)],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if "audio bytes: 0" in out.stdout or "duration: 0.000000" in out.stdout:
                path.unlink(missing_ok=True)
                return False
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            pass
    return True


def synthesize_narration(
    text: str,
    out_path: Path,
    *,
    language: str = "en",
    voice: str = "Samantha",
) -> bool:
    """Write narration audio to ``out_path`` (.mp3 or .aiff). Returns True on success."""
    narration = (text or "").strip()
    if not narration:
        return False
    narration = narration[:8000]
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if shutil.which("say"):
        aiff = out_path.with_suffix(".aiff")
        try:
            subprocess.run(
                ["say", "-v", voice, "-o", str(aiff), narration],
                check=True,
                capture_output=True,
                timeout=120,
            )
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
        if not aiff.is_file():
            return False
        if shutil.which("ffmpeg") and out_path.suffix.lower() == ".mp3":
            try:
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(aiff), "-q:a", "4", str(out_path)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                aiff.unlink(missing_ok=True)
                return _audio_has_content(out_path)
            except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
                pass
        dest = out_path if out_path.suffix.lower() == ".aiff" else out_path.with_suffix(".aiff")
        if dest != aiff:
            shutil.copy(aiff, dest)
        return _audio_has_content(dest)

    if shutil.which("espeak"):
        wav = out_path.with_suffix(".wav")
        try:
            subprocess.run(
                ["espeak", "-w", str(wav), narration],
                check=True,
                capture_output=True,
                timeout=120,
            )
            if shutil.which("ffmpeg"):
                subprocess.run(
                    ["ffmpeg", "-y", "-i", str(wav), str(out_path)],
                    check=True,
                    capture_output=True,
                    timeout=60,
                )
                wav.unlink(missing_ok=True)
                return _audio_has_content(out_path)
            return _audio_has_content(wav)
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            return False
    return False


def speak_live(
    text: str,
    *,
    language: str = "en",
    voice: str = "Samantha",
    wpm: int = 150,
    pace_multiplier: float = 1.0,
) -> bool:
    """Speak ``text`` aloud on the local machine (blocking until finished).

    Uses macOS ``say`` or ``espeak`` when available. Returns True when audio
    was played; False when no engine is installed or text is empty.
    """
    narration = (text or "").strip()
    if not narration:
        return False
    narration = narration[:8000]
    rate = max(80, min(380, int(wpm * max(pace_multiplier, 0.5))))

    if shutil.which("say"):
        proc = None
        try:
            proc = subprocess.Popen(
                ["say", "-v", voice, "-r", str(rate), narration],
            )
            proc.wait(timeout=600)
            return proc.returncode == 0
        except KeyboardInterrupt:
            if proc is not None and proc.poll() is None:
                proc.terminate()
                try:
                    proc.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    proc.kill()
            raise
        except (subprocess.TimeoutExpired, OSError):
            if proc is not None and proc.poll() is None:
                proc.terminate()
            return False

    if shutil.which("espeak"):
        try:
            subprocess.run(["espeak", narration], check=True, timeout=600)
            return True
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired, OSError):
            return False
    return False


@dataclass
class MediaManifest:
    course_id: str
    title: str
    audio_dir: str
    slides: List[Dict] = field(default_factory=list)
    lesson_video: Optional[str] = None
    tts_engine: str = "manifest-only"

    def to_dict(self) -> Dict:
        return {
            "course_id": self.course_id,
            "title": self.title,
            "audio_dir": self.audio_dir,
            "tts_engine": self.tts_engine,
            "lesson_video": self.lesson_video,
            "slides": list(self.slides),
        }


def export_course_media(
    course: "GeneratedCourse",
    out_dir: str | Path,
    *,
    repo_root: Optional[Path] = None,
    synthesize_audio: bool = True,
    attach_demo_videos: bool = True,
    demo_every: int = 5,
) -> MediaManifest:
    """Export per-slide narration audio + optional demo-video references."""
    from ..teaching.lesson import lesson_from_generated_course

    out_dir = Path(out_dir)
    audio_dir = out_dir / "media" / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    root = repo_root or Path.cwd()

    lesson = lesson_from_generated_course(course, language=course.language)
    step_narrations = [s.narration for s in lesson.steps]

    engine = "manifest-only"
    if synthesize_audio and tts_available():
        engine = "say" if shutil.which("say") else "espeak"

    demo_rel = pick_demo_video(subject=course.subject, title=course.title, repo_root=root)
    manifest_slides: List[Dict] = []
    concept_idx = 0

    for i, slide in enumerate(course.slides):
        rel_audio: Optional[str] = None
        narr = slide.narration or slide.body
        if i < len(step_narrations) and step_narrations[i]:
            narr = step_narrations[i]

        fname = f"{i + 1:03d}_{_slug(slide.title)}.mp3"
        audio_path = audio_dir / fname
        if synthesize_audio and engine != "manifest-only":
            ext = ".mp3" if shutil.which("ffmpeg") else ".aiff"
            audio_path = audio_dir / f"{i + 1:03d}_{_slug(slide.title)}{ext}"
            if synthesize_narration(narr, audio_path, language=course.language):
                rel_audio = str(audio_path.relative_to(out_dir))

        media_url = slide.media_url
        media_kind = slide.media_kind or ""
        if attach_demo_videos and demo_rel and slide.category not in ("exercise", "recap", "summary"):
            if slide.category in ("concept", "example", "demo", "introduction"):
                concept_idx += 1
            if concept_idx > 0 and concept_idx % demo_every == 0 and not media_url:
                media_url = demo_rel
                media_kind = "video"

        slide.audio_path = rel_audio
        if media_url and not slide.media_url:
            slide.media_url = media_url
            slide.media_kind = media_kind

        manifest_slides.append({
            "index": i,
            "title": slide.title,
            "category": slide.category,
            "audio": rel_audio,
            "media_url": media_url,
            "media_kind": media_kind or ("audio" if rel_audio else ""),
            "narration": narr[:500],
        })

    manifest = MediaManifest(
        course_id=course.course_id,
        title=course.title,
        audio_dir=str(audio_dir.relative_to(out_dir)),
        slides=manifest_slides,
        tts_engine=engine,
    )
    if engine != "manifest-only" and not any(s.get("audio") for s in manifest_slides):
        manifest.tts_engine = "manifest-only"
    manifest_path = out_dir / "media_manifest.json"
    manifest_path.write_text(json.dumps(manifest.to_dict(), indent=2), encoding="utf-8")
    return manifest
