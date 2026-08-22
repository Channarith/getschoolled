"""FastAPI app for the Theodore learn-through-music lab."""

from __future__ import annotations


# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


import logging
import os
from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from . import tts as tts_module
from .ask_ai import ask, explain_line
from .catalog import MEANING_LANGUAGES, Catalog, _audio_dir, import_songs, meaning_for_line
from .embeds import (
    ask_verse,
    explain_verse,
    get_embed,
    list_embeds,
    load_embeds,
    resolve_embed,
    video_dir,
)
from .media import load_clips, resolve_clip, videos_for
from .music_page import FAVICON_SVG, render_music_page, render_music_script
from .practice import (
    build_memory_drill,
    build_quiz,
    check_song_singing,
    grade_memory,
    grade_quiz,
    paraphrase_line,
    practice_menu,
)
from .pronounce import check_pronunciation
from .session import SessionMode, SessionStore
from .sing import VOICE_TAGS, sing_plan
from .storyboard import STORYBOARDS, storyboard_for
from .timing import alignment_for, song_timings
from .translations import language_catalog, language_name, translate_song, validate_language
from .tts import TTSUnavailable, synthesize, tts_status

_LOG = logging.getLogger(__name__)

app = FastAPI(title="Theodore Music Lab", version="0.5.0")

_CATALOG = Catalog()
_STORE = SessionStore(_CATALOG)


class StartSession(BaseModel):
    song_id: str = Field(min_length=1)
    mode: SessionMode = SessionMode.LINE_PAUSE
    meaning_language: str = "en"


class MeaningRequest(BaseModel):
    target_lang: str = ""
    line_no: Optional[int] = None


class LineMeaningRequest(BaseModel):
    song_id: str = Field(min_length=1)
    line_no: int = 1
    target_lang: str = "en"


class ImportPack(BaseModel):
    songs: list[dict[str, Any]] = Field(default_factory=list)


class SongTranslationRequest(BaseModel):
    song_id: str = Field(min_length=1)
    target_lang: str = "en"
    allow_llm: bool = True


class ExplainRequest(BaseModel):
    song_id: str = Field(min_length=1)
    line_no: Optional[int] = None
    target_lang: str = "en"


class AskRequest(BaseModel):
    song_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    line_no: Optional[int] = None
    target_lang: str = "en"


class PronounceRequest(BaseModel):
    song_id: str = Field(min_length=1)
    heard: str = ""
    line_no: Optional[int] = None
    target_lang: str = "en"
    # english = sing the lyric; translation = say the line in the learner's language
    practice: str = "english"
    # Optional override so "other ways to say it" can score against an alternate.
    target: str = ""


class QuizGradeRequest(BaseModel):
    song_id: str = Field(min_length=1)
    target_lang: str = "es"
    answers: dict[str, str] = Field(default_factory=dict)
    count: int = 8
    seed: str = ""


class MemoryGradeRequest(BaseModel):
    song_id: str = Field(min_length=1)
    target_lang: str = "es"
    direction: str = "en_to_target"
    answers: dict[str, str] = Field(default_factory=dict)
    count: int = 6
    seed: str = ""


class ParaphraseRequest(BaseModel):
    song_id: str = Field(min_length=1)
    line_no: Optional[int] = None
    target_lang: str = "en"
    allow_llm: bool = True


class SingCheckRequest(BaseModel):
    song_id: str = Field(min_length=1)
    target_lang: str = "es"
    practice: str = "translation"
    lines: list[dict[str, Any]] = Field(default_factory=list)


class EmbedAskRequest(BaseModel):
    embed_id: str = Field(min_length=1)
    question: str = Field(min_length=1)
    verse_no: Optional[int] = None
    target_lang: str = "en"
    allow_llm: bool = True


class EmbedExplainRequest(BaseModel):
    embed_id: str = Field(min_length=1)
    verse_no: Optional[int] = None
    target_lang: str = "en"
    allow_llm: bool = True


def _song_or_404(song_id: str):
    try:
        return _CATALOG.get(song_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown song '{song_id}'") from exc


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def music_lab_page() -> str:
    return render_music_page()


@app.get("/assets/music-lab.js", include_in_schema=False)
def music_lab_script() -> Response:
    """Serve the large player separately so the HTML cannot be truncated mid-script."""
    return Response(
        content=render_music_script(),
        media_type="application/javascript",
        headers={"cache-control": "no-cache"},
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    """Browsers ask for this on every page, including /health and /docs."""
    return Response(
        content=FAVICON_SVG,
        media_type="image/svg+xml",
        headers={"cache-control": "public, max-age=86400"},
    )


@app.get("/health")
def health() -> dict[str, Any]:
    featured = _CATALOG.featured()
    readiness: dict[str, Any] = {}
    try:
        from aoep_shared.env_bootstrap import speech_readiness

        readiness = speech_readiness()
    except Exception:  # noqa: BLE001
        pass
    speech = tts_status()
    return {
        "ok": True,
        "service": "theodore-music-lab",
        "songs": len(_CATALOG.songs),
        "featured_songs": len(featured),
        "meaning_languages": list(MEANING_LANGUAGES),
        "meaning_language_count": len(MEANING_LANGUAGES),
        "clips": len(load_clips()),
        "videos": len(videos_for()),
        "karaoke": True,
        "ask_ai": True,
        "storyboards": len(STORYBOARDS),
        "storyboard_scenes": sum(len(scenes) for scenes in STORYBOARDS.values()),
        "sing_along_languages": len(VOICE_TAGS),
        "neural_voices": tts_status(),
        "pronunciation_check": True,
        "song_practice": True,
        "practice_modes": [
            "pronounce",
            "quiz",
            "memory",
            "ask",
            "paraphrase",
            "sing",
        ],
        "vocal_aligned_songs": sum(
            1 for song in featured if alignment_for(song.song_id)
        ),
        "embeds": len(load_embeds()),
        "embed_pause_ask": sum(
            1 for row in load_embeds() if (row.get("verses") or [])
        ),
        "player": "/",
        "speech": speech,
        **readiness,
    }


@app.get("/api/tts/status")
def music_tts_status() -> dict[str, Any]:
    return tts_status()


@app.get("/api/tts")
@app.post("/api/tts")
def music_speak(text: str = "", language: str = "en", style: str = "warm") -> Response:
    """Neural speech for sing-along / narration (501 => client device voice)."""
    try:
        audio, mime, engine = tts_module.speak(text, language=language, style=style)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except TTSUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type=mime,
        headers={"X-TTS-Engine": engine, "Cache-Control": "no-store"},
    )


@app.get("/api/music/languages")
def languages() -> dict[str, Any]:
    return {
        "languages": list(MEANING_LANGUAGES),
        "count": len(MEANING_LANGUAGES),
        "catalog": language_catalog(),
    }


@app.get("/api/music/tts/status")
def tts_availability() -> dict[str, Any]:
    """Probed once by the player to choose server voices over device voices."""
    return tts_status()


@app.get("/api/music/tts")
def tts(text: str, lang: str = "en", rate: float = 1.0, gender: str = "female") -> Response:
    """One spoken line as MP3, so every language sings without an OS voice.

    501 (not 500) when no engine can render it: that is the client's cue to fall
    back to the device voice rather than show an error.
    """
    try:
        audio = synthesize(text, lang, rate=rate, gender=gender)
    except TTSUnavailable as exc:
        # Access logs show only the bare 501, which reads as "TTS is broken" when
        # the real cause is a blocked host or an unwritable cache. Say which.
        _LOG.warning("tts render failed lang=%s rate=%.2f: %s", lang, rate, exc)
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(
        content=audio,
        media_type="audio/mpeg",
        headers={"cache-control": "public, max-age=86400"},
    )


@app.get("/api/music/timing/{song_id}")
def song_timing(
    song_id: str, duration: float = 0.0, lead_in: float = -1.0
) -> dict[str, Any]:
    """Line + word timings that drive the bouncing ball and word highlighting."""
    song = _song_or_404(song_id)
    return song_timings(
        song,
        duration_sec=duration or None,
        lead_in_sec=None if lead_in < 0 else lead_in,
    )


@app.get("/api/music/storyboard/{song_id}")
def song_storyboard(
    song_id: str, target_lang: str = "en", duration: float = 0.0
) -> dict[str, Any]:
    """Timed scenes, backdrop art, cast and camera moves for the full-screen stage."""
    song = _song_or_404(song_id)
    if song_id not in STORYBOARDS:
        raise HTTPException(status_code=404, detail=f"No storyboard for '{song_id}'")
    try:
        language = validate_language(target_lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return storyboard_for(song, language=language, duration_sec=duration or None)


@app.get("/api/music/sing/{song_id}")
def song_sing_plan(
    song_id: str, target_lang: str = "es", duration: float = 0.0, allow_llm: bool = True
) -> dict[str, Any]:
    """Sing the English recording in another language: text, window, voice, rate."""
    song = _song_or_404(song_id)
    try:
        return sing_plan(
            song,
            target_lang,
            duration_sec=duration or None,
            allow_llm=allow_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/translate")
def translate(req: SongTranslationRequest) -> dict[str, Any]:
    """Every line of a song translated into one language (comprehensive)."""
    song = _song_or_404(req.song_id)
    try:
        return translate_song(song, req.target_lang, allow_llm=req.allow_llm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/explain")
def explain(req: ExplainRequest) -> dict[str, Any]:
    """Meaning, translation, key vocabulary and examples for one lyric line."""
    song = _song_or_404(req.song_id)
    try:
        return explain_line(song, req.line_no, req.target_lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/ask")
def ask_about_lyrics(req: AskRequest) -> dict[str, Any]:
    """Ask the AI anything about the lyrics, playing or paused."""
    song = _song_or_404(req.song_id)
    try:
        return ask(song, req.question, line_no=req.line_no, language=req.target_lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/pronounce")
def pronounce_line(req: PronounceRequest) -> dict[str, Any]:
    """Score a spoken/typed attempt at the current lyric line and coach corrections."""
    song = _song_or_404(req.song_id)
    try:
        return check_pronunciation(
            song,
            line_no=req.line_no,
            heard=req.heard,
            language=req.target_lang,
            practice=req.practice,
            target_override=req.target,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/practice/{song_id}")
def practice_modes(song_id: str, target_lang: str = "en") -> dict[str, Any]:
    """Menu of learning drills for one song (pronounce, quiz, memory, ask, …)."""
    song = _song_or_404(song_id)
    try:
        return practice_menu(song, target_lang)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/practice/{song_id}/quiz")
def practice_quiz(
    song_id: str, target_lang: str = "es", count: int = 8, seed: str = ""
) -> dict[str, Any]:
    """Multiple-choice quiz built from this song's vocabulary and lines."""
    song = _song_or_404(song_id)
    try:
        built = build_quiz(
            song,
            target_lang,
            count=count,
            seed=seed or f"{song_id}:{target_lang}:{count}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    # Never ship the answer key to the browser — grade rebuilds it from the seed.
    return {k: v for k, v in built.items() if k != "answer_key"} | {
        "seed": seed or f"{song_id}:{target_lang}:{count}"
    }


@app.post("/api/music/practice/quiz/grade")
def practice_quiz_grade(req: QuizGradeRequest) -> dict[str, Any]:
    """Score a quiz attempt (same seed regenerates the same questions)."""
    song = _song_or_404(req.song_id)
    try:
        return grade_quiz(
            song,
            language=req.target_lang,
            answers=req.answers,
            count=req.count,
            seed=req.seed or f"{req.song_id}:{req.target_lang}:{req.count}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/practice/{song_id}/memory")
def practice_memory(
    song_id: str,
    target_lang: str = "es",
    direction: str = "en_to_target",
    count: int = 6,
    seed: str = "",
) -> dict[str, Any]:
    """Flashcards that hide one side of each lyric line for recall practice."""
    song = _song_or_404(song_id)
    try:
        built = build_memory_drill(
            song,
            target_lang,
            direction=direction,
            count=count,
            seed=seed
            or f"mem:{song_id}:{target_lang}:{direction}:{count}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {k: v for k, v in built.items() if k != "answer_key"} | {
        "seed": seed or f"mem:{song_id}:{target_lang}:{direction}:{count}"
    }


@app.post("/api/music/practice/memory/grade")
def practice_memory_grade(req: MemoryGradeRequest) -> dict[str, Any]:
    """Score typed/spoken memory answers against the hidden side of each card."""
    song = _song_or_404(req.song_id)
    try:
        return grade_memory(
            song,
            language=req.target_lang,
            direction=req.direction,
            answers=req.answers,
            count=req.count,
            seed=req.seed
            or f"mem:{req.song_id}:{req.target_lang}:{req.direction}:{req.count}",
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/practice/paraphrase")
def practice_paraphrase(req: ParaphraseRequest) -> dict[str, Any]:
    """Other natural ways to say the current line, in the learner's language."""
    song = _song_or_404(req.song_id)
    try:
        return paraphrase_line(
            song,
            line_no=req.line_no,
            language=req.target_lang,
            allow_llm=req.allow_llm,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/practice/sing")
def practice_sing_song(req: SingCheckRequest) -> dict[str, Any]:
    """Score a whole-song attempt line by line in English or the target language."""
    song = _song_or_404(req.song_id)
    try:
        return check_song_singing(
            song,
            language=req.target_lang,
            practice=req.practice,
            lines=req.lines,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/clips")
def clips(song_id: str = "", target_lang: str = "en") -> dict[str, Any]:
    """Short lyric clips (line ranges of the featured songs) with translations."""
    rows: list[dict[str, Any]] = []
    for clip in load_clips():
        clip_song = str(clip.get("song_id") or "")
        if song_id and clip_song != song_id:
            continue
        try:
            song = _CATALOG.get(clip_song)
        except KeyError:
            continue
        try:
            rows.append(resolve_clip(song, clip, target_lang))
        except ValueError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"count": len(rows), "clips": rows}


@app.get("/api/music/videos")
def videos(song_id: str = "") -> dict[str, Any]:
    """Curated external lyric videos and channels (all have lyrics available)."""
    rows = videos_for(song_id)
    return {"count": len(rows), "videos": rows}


@app.get("/api/music/embeds")
def embeds(target_lang: str = "en", allow_llm: bool = False) -> dict[str, Any]:
    """YouTube embeds with optional pause-and-ask verse sheets."""
    try:
        rows = list_embeds(target_lang, allow_llm=allow_llm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    lang_name = language_name(target_lang) if target_lang != "en" else "English"
    return {
        "count": len(rows),
        "embeds": rows,
        "target_lang": target_lang,
        "target_lang_name": lang_name,
    }


@app.get("/api/music/embeds/{embed_id}")
def embed_detail(
    embed_id: str, target_lang: str = "en", allow_llm: bool = True
) -> dict[str, Any]:
    """One embed: YouTube player URL, verses, translations and teaching questions."""
    try:
        raw = get_embed(embed_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown embed '{embed_id}'") from exc
    try:
        result = resolve_embed(raw, target_lang, allow_llm=allow_llm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    result["target_lang"] = target_lang
    result["target_lang_name"] = language_name(target_lang) if target_lang != "en" else "English"
    return result


@app.post("/api/music/embeds/explain")
def embed_explain(req: EmbedExplainRequest) -> dict[str, Any]:
    """Meaning, vocabulary and prepared grammar/vocab questions for one verse."""
    try:
        return explain_verse(
            req.embed_id, req.verse_no, req.target_lang, allow_llm=req.allow_llm
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown embed '{req.embed_id}'") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/music/embeds/ask")
def embed_ask(req: EmbedAskRequest) -> dict[str, Any]:
    """Ask grammar, vocabulary or comprehension questions about the paused verse."""
    try:
        return ask_verse(
            req.embed_id,
            req.question,
            verse_no=req.verse_no,
            language=req.target_lang,
            allow_llm=req.allow_llm,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown embed '{req.embed_id}'") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/featured")
def featured_songs(offset: int = 0, limit: int = 0) -> dict[str, Any]:
    rows = []
    for song in _CATALOG.featured():
        rows.append(
            {
                "song_id": song.song_id,
                "language": song.language,
                "title_en": song.title_en,
                "topic": song.topic,
                "style": song.style,
                "license": song.license,
                "line_count": song.line_count,
                "featured": True,
                "audio_url": song.audio_url,
                "audio_file": song.audio_file,
                "animation": song.animation,
                "duration_hint_sec": song.duration_hint_sec,
            }
        )
    total = len(rows)
    start = max(0, offset)
    stop = total if limit <= 0 else min(total, start + min(limit, 25))
    page = rows[start:stop]
    return {
        "count": len(page),
        "total": total,
        "offset": start,
        "next_offset": stop if stop < total else None,
        "songs": page,
        "meaning_language_count": len(MEANING_LANGUAGES),
    }


@app.get("/api/music/songs")
def list_songs(
    language: str = "", topic: str = "", limit: int = 200, featured_only: bool = False
) -> dict[str, Any]:
    if featured_only:
        rows = [
            {
                "song_id": s.song_id,
                "language": s.language,
                "title_en": s.title_en,
                "topic": s.topic,
                "style": s.style,
                "license": s.license,
                "line_count": s.line_count,
                "featured": s.featured,
                "audio_url": s.audio_url,
                "audio_file": s.audio_file,
                "animation": s.animation,
                "duration_hint_sec": s.duration_hint_sec,
            }
            for s in _CATALOG.featured()
        ]
        return {"count": len(rows), "songs": rows, "total_catalog": len(_CATALOG.songs)}
    rows = _CATALOG.list(language=language, topic=topic, limit=limit)
    return {"count": len(rows), "songs": rows, "total_catalog": len(_CATALOG.songs)}


@app.get("/api/music/songs/{song_id}")
def get_song(song_id: str) -> dict[str, Any]:
    try:
        song = _CATALOG.get(song_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown song '{song_id}'") from exc
    payload = song.model_dump()
    payload["audio_url"] = song.audio_url
    return payload


@app.get("/api/music/audio/{filename}")
def get_audio(filename: str, request: Request) -> Response:
    """Serve a featured MP3 with byte-range seeking."""
    return _ranged_file(
        filename, request, _audio_dir(), "audio/mpeg", "Invalid audio filename"
    )


@app.get("/api/music/video/{filename}")
def get_video(filename: str, request: Request) -> Response:
    """Serve a local karaoke / lesson MP4 with byte-range seeking."""
    return _ranged_file(
        filename, request, video_dir(), "video/mp4", "Invalid video filename"
    )


def _ranged_file(
    filename: str,
    request: Request,
    root: Path,
    media_type: str,
    bad_name_detail: str,
) -> Response:
    safe = Path(filename).name
    if safe != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail=bad_name_detail)
    path = root / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"File not found: {safe}")

    size = path.stat().st_size
    headers = {"accept-ranges": "bytes", "cache-control": "public, max-age=3600"}
    raw_range = request.headers.get("range", "")
    if not raw_range.startswith("bytes="):
        return FileResponse(path, media_type=media_type, headers=headers)

    spec = raw_range.split("=", 1)[1].split(",")[0].strip()
    first, _, last = spec.partition("-")
    try:
        if first and last:
            start = int(first)
            end = int(last)
        elif first and not last:
            start = int(first)
            end = size - 1
        elif last and not first:
            suffix = int(last)
            if suffix <= 0:
                raise ValueError("empty suffix")
            start = max(0, size - suffix)
            end = size - 1
        else:
            raise ValueError("empty range")
    except ValueError:
        raise HTTPException(status_code=416, detail="Malformed Range header") from None
    if start < 0 or start >= size or end < start:
        return Response(
            status_code=416,
            headers={**headers, "content-range": f"bytes */{size}"},
        )
    end = min(end, size - 1)
    length = end - start + 1

    def stream() -> Iterator[bytes]:
        remaining = length
        with path.open("rb") as fh:
            fh.seek(start)
            while remaining > 0:
                chunk = fh.read(min(65536, remaining))
                if not chunk:
                    break
                remaining -= len(chunk)
                yield chunk

    return StreamingResponse(
        stream(),
        status_code=206,
        media_type=media_type,
        headers={
            **headers,
            "content-range": f"bytes {start}-{end}/{size}",
            "content-length": str(length),
        },
    )


@app.post("/api/music/meaning")
def line_meaning(req: LineMeaningRequest) -> dict[str, Any]:
    try:
        song = _CATALOG.get(req.song_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown song '{req.song_id}'") from exc
    line = next((ln for ln in song.lines if ln.line_no == req.line_no), None)
    if line is None:
        raise HTTPException(status_code=404, detail=f"Unknown line {req.line_no}")
    try:
        meaning = meaning_for_line(line, req.target_lang or "en")
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {
        "song_id": song.song_id,
        "line_no": line.line_no,
        "text": line.text,
        "meaning": meaning,
    }


def _require_import_secret(request: Request) -> None:
    expected = (os.environ.get("MUSIC_LAB_SECRET") or os.environ.get("ADMIN_SECRET") or "").strip()
    if not expected:
        raise HTTPException(status_code=403, detail="Catalog import is disabled")
    got = (
        request.headers.get("x-music-lab-secret")
        or request.headers.get("x-admin-secret")
        or ""
    ).strip()
    if got != expected:
        raise HTTPException(status_code=401, detail="Unauthorized")


@app.post("/api/music/import")
def import_pack(request: Request, req: ImportPack) -> dict[str, Any]:
    _require_import_secret(request)
    try:
        songs = import_songs(req.songs)
    except (KeyError, ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    added = _CATALOG.extend(songs)
    return {"imported": len(songs), "added": added, "total": len(_CATALOG.songs)}


@app.post("/api/music/session/start")
def session_start(req: StartSession) -> dict[str, Any]:
    try:
        return _STORE.start(
            req.song_id, mode=req.mode, meaning_language=req.meaning_language
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown song '{req.song_id}'") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/music/session/{session_id}")
def session_get(session_id: str) -> dict[str, Any]:
    try:
        sess = _STORE.get(session_id)
        song = _STORE.catalog.get(sess.song_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    return sess.snapshot(song)


@app.post("/api/music/session/{session_id}/play")
def session_play(session_id: str) -> dict[str, Any]:
    try:
        return _STORE.play(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/api/music/session/{session_id}/pause")
def session_pause(session_id: str) -> dict[str, Any]:
    try:
        return _STORE.pause(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/api/music/session/{session_id}/repeat")
def session_repeat(session_id: str) -> dict[str, Any]:
    try:
        return _STORE.repeat(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/api/music/session/{session_id}/continue")
def session_continue(session_id: str) -> dict[str, Any]:
    try:
        return _STORE.continue_(session_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/api/music/session/{session_id}/continuous")
def session_continuous(session_id: str, enabled: bool = True) -> dict[str, Any]:
    try:
        return _STORE.set_continuous(session_id, enabled=enabled)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc


@app.post("/api/music/session/{session_id}/meaning")
def session_meaning(session_id: str, req: MeaningRequest) -> dict[str, Any]:
    try:
        return _STORE.meaning(
            session_id, target_lang=req.target_lang, line_no=req.line_no
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Unknown session") from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_music_lab.main:app", host="0.0.0.0", port=8097, reload=False)


if __name__ == "__main__":
    main()
