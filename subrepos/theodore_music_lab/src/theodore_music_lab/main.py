"""FastAPI app for the Theodore learn-through-music lab."""

from __future__ import annotations

from pathlib import Path
from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse, HTMLResponse
from pydantic import BaseModel, Field

from .catalog import MEANING_LANGUAGES, Catalog, _audio_dir, import_songs, meaning_for_line
from .music_page import render_music_page
from .session import SessionMode, SessionStore

app = FastAPI(title="Theodore Music Lab", version="0.2.0")

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
        "player": "/",
    }


@app.get("/api/music/languages")
def languages() -> dict[str, Any]:
    return {"languages": list(MEANING_LANGUAGES), "count": len(MEANING_LANGUAGES)}


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
def get_audio(filename: str) -> FileResponse:
    safe = Path(filename).name
    if safe != filename or ".." in filename or "/" in filename or "\\" in filename:
        raise HTTPException(status_code=400, detail="Invalid audio filename")
    path = _audio_dir() / safe
    if not path.is_file():
        raise HTTPException(status_code=404, detail=f"Audio not found: {safe}")
    return FileResponse(path, media_type="audio/mpeg", filename=safe)


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
