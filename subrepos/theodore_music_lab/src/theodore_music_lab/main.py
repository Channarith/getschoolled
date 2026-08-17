"""FastAPI app for the Theodore learn-through-music lab."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Iterator, Optional

from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import FileResponse, HTMLResponse, StreamingResponse
from pydantic import BaseModel, Field

from .ask_ai import ask, explain_line
from .catalog import MEANING_LANGUAGES, Catalog, _audio_dir, import_songs, meaning_for_line
from .embeds import ask_verse, explain_verse, get_embed, list_embeds, load_embeds, resolve_embed
from .media import load_clips, resolve_clip, videos_for
from .music_page import render_music_page
from .session import SessionMode, SessionStore
from .sing import VOICE_TAGS, sing_plan
from .storyboard import STORYBOARDS, storyboard_for
from .timing import song_timings
from .translations import language_catalog, translate_song, validate_language

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


@app.get("/health")
def health() -> dict[str, Any]:
    featured = _CATALOG.featured()
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
        "embeds": len(load_embeds()),
        "embed_pause_ask": sum(
            1 for row in load_embeds() if (row.get("verses") or [])
        ),
        "player": "/",
    }


@app.get("/api/music/languages")
def languages() -> dict[str, Any]:
    return {
        "languages": list(MEANING_LANGUAGES),
        "count": len(MEANING_LANGUAGES),
        "catalog": language_catalog(),
    }


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
    return {"count": len(rows), "embeds": rows}


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
        return resolve_embed(raw, target_lang, allow_llm=allow_llm)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


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
def featured_songs() -> dict[str, Any]:
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
    return {
        "count": len(rows),
        "songs": rows,
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
    """Serve a featured MP3.

    Byte ranges are handled explicitly: without them a browser cannot seek, and
    seeking is what Restart, clip playback and click-a-line-to-jump all rely on.
    """
    safe = Path(filename).name
    if safe != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid audio filename")
    path = _audio_dir() / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio not found: {safe}")

    size = path.stat().st_size
    headers = {"accept-ranges": "bytes", "cache-control": "public, max-age=3600"}
    raw_range = request.headers.get("range", "")
    if not raw_range.startswith("bytes="):
        return FileResponse(path, media_type="audio/mpeg", headers=headers)

    spec = raw_range.split("=", 1)[1].split(",")[0].strip()
    first, _, last = spec.partition("-")
    try:
        start = int(first) if first else 0
        end = int(last) if last else size - 1
    except ValueError:
        raise HTTPException(status_code=416, detail="Malformed Range header") from None
    if start < 0 or start >= size:
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
        media_type="audio/mpeg",
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
    if line is None and song.lines:
        line = song.lines[0]
    if line is None:
        raise HTTPException(status_code=404, detail="Song has no lines")
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


@app.post("/api/music/import")
def import_pack(req: ImportPack) -> dict[str, Any]:
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
