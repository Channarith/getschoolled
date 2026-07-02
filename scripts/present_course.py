#!/usr/bin/env python3
"""Present an existing harvested course with the smart AI presenter.

Loads a ``.course.json`` (+ optional ``.pptx``), builds a LessonPlan, and runs
the smart presenter (digressions, summarization, time-aware skip/compress).

Examples:
  python3 scripts/present_course.py output/harvest/algebra.course.json
  python3 scripts/present_course.py output/harvest/algebra.course.json \\
      --present-mode workshop
  python3 scripts/present_course.py output/harvest/algebra.course.json \\
      --meeting-provider mock --no-present   # plan JSON only, no playback
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_REPO / "packages" / "shared" / "src"))

from aoep_shared.harvest import GeneratedCourse, GeneratedSlide, CourseTags, resolve_course_pptx  # noqa: E402
from aoep_shared.meeting import (  # noqa: E402
    build_smart_presentation_plan,
    present_with_provider,
)
from aoep_shared.teaching.lesson import teach_course  # noqa: E402


def _load_course(path: Path) -> tuple[GeneratedCourse, dict | None]:
    data = json.loads(path.read_text(encoding="utf-8"))
    slides = [
        GeneratedSlide(
            title=s["title"],
            body=s.get("body", ""),
            narration=s.get("narration", s.get("body", "")),
            category=s.get("category", "concept"),
            audio_path=s.get("audio_path"),
            media_url=s.get("media_url"),
            media_kind=s.get("media_kind", ""),
        )
        for s in data.get("slides", [])
    ]
    tags_raw = data.get("tags") or {}
    tags = CourseTags(**{k: v for k, v in tags_raw.items() if k in CourseTags.__dataclass_fields__})
    course = GeneratedCourse(
        course_id=data.get("course_id", path.stem),
        title=data.get("title", path.stem),
        subject=data.get("subject", "general"),
        language=data.get("language", "en"),
        source=data.get("source", str(path)),
        fmt=data.get("format", data.get("fmt", "lecture")),
        slides=slides,
        tags=tags,
        presentation_mode_index=int(data.get("presentation_mode_index", 0)),
    )
    return course, data.get("theme")


def _ensure_rich_media(course: GeneratedCourse, course_dir: Path, theme: dict | None) -> dict:
    """Export demo videos + theme; return resolved theme dict."""
    from aoep_shared.harvest.export import export_course_json
    from aoep_shared.harvest.media import export_course_media
    from aoep_shared.harvest.themes import resolve_slide_theme

    export_course_media(course, course_dir, repo_root=_REPO)
    if not theme:
        theme = resolve_slide_theme(
            title=course.title,
            subject=course.subject,
            tags=course.tags.label_list() if course.tags else (),
            fmt=course.fmt,
        ).to_dict()
    json_path = next(course_dir.glob("*.course.json"), course_dir / f"{course.title}.course.json")
    export_course_json(course, json_path, theme=theme)
    return theme


def _resolve_slide_source(explicit: str | None, course_path: Path, pptx: str) -> Path | None:
    if explicit:
        path = Path(explicit)
        if not path.is_file():
            raise SystemExit(f"slide source not found: {path}")
        if path.suffix.lower() not in (".pdf", ".pptx"):
            raise SystemExit(f"--slide-source must be .pdf or .pptx, got {path.suffix}")
        return path
    return None


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("course_json", nargs="?", default=None, help="path to *.course.json from harvester")
    ap.add_argument("--pptx", default=None, help="optional .pptx (for ppt_trainer engine)")
    ap.add_argument("--meeting-provider", default="local",
                    help="local|mock|google_meet|zoom|teams (default local = speak aloud)")
    ap.add_argument("--no-audio", action="store_true",
                    help="with local provider: show slides + captions only, no TTS")
    ap.add_argument("--no-slides", action="store_true",
                    help="terminal-only playback (no browser slide deck)")
    ap.add_argument("--tts-engine", default="auto",
                    choices=("auto", "edge", "neural", "say", "clone",
                             "chatterbox", "xtts", "elevenlabs"),
                    help="TTS backend: auto|edge|clone|chatterbox|xtts|elevenlabs|say")
    ap.add_argument("--voice", default="",
                    help="TTS voice (Edge neural id, or clone:<voice_id>)")
    ap.add_argument("--voice-sample", default=None,
                    help="reference WAV/MP3 for voice cloning (overrides persona sample)")
    ap.add_argument("--open-meeting", action="store_true",
                    help="open Zoom/Meet/Teams join URL in browser (with --meeting-provider)")
    ap.add_argument("--duration-min", type=int, default=45,
                    help="scheduled class length (default 45)")
    ap.add_argument("--elapsed-min", type=float, default=0.0,
                    help="minutes already used in this session")
    ap.add_argument("--realtime", action="store_true",
                    help="sleep for spoken duration (wall-clock playback)")
    ap.add_argument("--no-smart", action="store_true",
                    help="read narration verbatim (legacy mode)")
    ap.add_argument("--no-present", action="store_true",
                    help="only write presentation_plan.json")
    ap.add_argument("--present-mode", default=None,
                    help="presentation matrix mode: index, preset (lecture/workshop/drill/"
                         "survey/flipped/express), single axis token, or "
                         "arc|voice|time|engage|media (quote in shell: 'drill|smart|...')")
    ap.add_argument("--list-modes", action="store_true",
                    help="print finite presentation mode catalog and exit")
    ap.add_argument("--persona", default=None,
                    help="presenter personality preset (aria, davis, guy, sonia, …)")
    ap.add_argument("--list-personas", action="store_true",
                    help="print persona catalog (preset + registered clone voices)")
    ap.add_argument("--list-voices", action="store_true",
                    help="print registered clone voice profiles and exit")
    ap.add_argument("--slide-source", default=None,
                    help="show original .pdf/.pptx pages instead of generated HTML bullets")
    ap.add_argument("--with-media", action="store_true",
                    help="attach themed backgrounds + demo video clips per slide (export media first)")
    ap.add_argument("--out-dir", default=None, help="write plan/result JSON here")
    args = ap.parse_args(argv)

    if args.list_personas:
        from aoep_shared.meeting.presenter_personas import list_presenter_personas
        print(json.dumps(list_presenter_personas(repo_root=_REPO), indent=2))
        return 0

    if args.list_voices:
        from aoep_shared.meeting.voice_profiles import list_voice_profiles
        from aoep_shared.meeting.clone_tts import engine_status
        print(json.dumps({
            "engines": engine_status(),
            "voices": list_voice_profiles(repo_root=_REPO),
        }, indent=2))
        return 0

    if args.list_modes:
        from aoep_shared.meeting.presentation_matrix import (
            PRESENTATION_MODE_CAPACITY,
            list_presentation_modes,
        )
        rows = list_presentation_modes(limit=50)
        print(json.dumps({"capacity": PRESENTATION_MODE_CAPACITY, "sample": rows}, indent=2))
        return 0

    if not args.course_json:
        ap.error("course_json is required unless --list-modes is set")
    course_path = Path(args.course_json)
    course, theme = _load_course(course_path)
    out_dir = Path(args.out_dir or course_path.parent)
    out_dir.mkdir(parents=True, exist_ok=True)

    if args.with_media:
        theme = _ensure_rich_media(course, out_dir, theme)
        print(f"Exported media + theme to {out_dir}", file=sys.stderr)

    pptx_path = resolve_course_pptx(course_path)
    if args.pptx:
        explicit = Path(args.pptx)
        if not explicit.is_file():
            raise SystemExit(f"pptx not found: {explicit}")
        pptx_path = explicit
    pptx = str(pptx_path) if pptx_path else None
    slide_source = _resolve_slide_source(args.slide_source, course_path, pptx or "")
    if slide_source is None and pptx_path:
        slide_source = pptx_path
    lesson = teach_course(
        course,
        engine="fallback",
        pptx_path=pptx_path,
        out_dir=out_dir / "lesson",
    )

    smart = not args.no_smart
    present_mode = args.present_mode
    if present_mode is None and getattr(course, "presentation_mode_index", None):
        present_mode = course.presentation_mode_index

    if smart:
        from aoep_shared.meeting.presentation_matrix import PresentationProfile
        from aoep_shared.meeting.smart_presenter import build_smart_presentation_plan, corpus_rag_search
        profile = PresentationProfile.resolve(present_mode)
        plan = build_smart_presentation_plan(
            lesson,
            duration_min=args.duration_min,
            elapsed_min=args.elapsed_min,
            rag_search=corpus_rag_search,
            profile=profile,
        )
        profile_path = out_dir / "presentation_profile.json"
        profile_path.write_text(profile.to_json(), encoding="utf-8")
    else:
        from aoep_shared.meeting import build_presentation_plan
        plan = build_presentation_plan(lesson)

    plan_path = out_dir / "presentation_plan.json"
    plan_path.write_text(json.dumps(plan.to_dict(), indent=2), encoding="utf-8")
    print(f"Wrote {plan_path} ({plan.total_seconds:.0f}s est, {len(plan.steps)} steps)",
          file=sys.stderr)

    if args.no_present:
        return 0

    elif not theme:
        from aoep_shared.meeting.presentation_assets import load_theme
        theme = load_theme(
            out_dir,
            course_title=course.title,
            subject=course.subject,
            fmt=course.fmt,
            tags=course.tags.label_list() if course.tags else None,
        )

    print(f"\nStarting AI presentation: {course.title}", file=sys.stderr)
    print(f"  provider={args.meeting_provider}  mode={present_mode or 'default'}  "
          f"persona={args.persona or 'default'}  slides={'native' if slide_source else 'rich'}  "
          f"theme={'yes' if theme else 'no'}  "
          f"steps={len(plan.steps)}  est={plan.total_seconds:.0f}s  "
          f"tts={args.tts_engine}\n", file=sys.stderr)

    course_slides = [s.to_dict() for s in course.slides]

    provider_used, result = present_with_provider(
        lesson,
        provider=args.meeting_provider,
        topic=course.title,
        duration_min=args.duration_min,
        elapsed_min=args.elapsed_min,
        realtime=args.realtime and args.meeting_provider == "mock",
        smart=smart,
        presentation_mode=present_mode,
        speak=not args.no_audio,
        voice=args.voice,
        tts_engine=args.tts_engine,
        sync_slides=not args.no_slides,
        open_meeting=args.open_meeting,
        slide_dir=out_dir / "slide_show",
        course_title=course.title,
        course_slides=course_slides,
        language=course.language,
        plan=plan,
        persona=args.persona,
        slide_source=slide_source,
        theme=theme,
        course_dir=out_dir,
        repo_root=_REPO,
        voice_sample=args.voice_sample,
    )
    interrupted = any(e.action == "interrupted" for e in result.events)
    if interrupted:
        print("\nPresentation stopped by user.", file=sys.stderr)
    result_path = out_dir / "presentation_result.json"
    result_path.write_text(json.dumps(result.to_dict(), indent=2), encoding="utf-8")
    print(json.dumps({
        "provider": provider_used,
        "join_url": result.meeting.join_url,
        "steps_presented": result.steps_presented,
        "total_seconds": result.total_seconds,
        "interrupted": interrupted,
        "presentation_result": str(result_path),
    }, indent=2))
    return 130 if interrupted else 0


if __name__ == "__main__":
    raise SystemExit(main())
