"""FastAPI app for the Theodore learn-through-music lab."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .catalog import MEANING_LANGUAGES, Catalog, import_songs
from .session import SessionMode, SessionStore

app = FastAPI(title="Theodore Music Lab", version="0.1.0")

_CATALOG = Catalog()
_STORE = SessionStore(_CATALOG)


class StartSession(BaseModel):
    song_id: str = Field(min_length=1)
    mode: SessionMode = SessionMode.LINE_PAUSE
    meaning_language: str = "en"


class MeaningRequest(BaseModel):
    target_lang: str = ""
    line_no: Optional[int] = None


class ImportPack(BaseModel):
    songs: list[dict[str, Any]] = Field(default_factory=list)


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "theodore-music-lab",
        "songs": len(_CATALOG.songs),
        "meaning_languages": list(MEANING_LANGUAGES),
        "meaning_language_count": len(MEANING_LANGUAGES),
    }


@app.get("/api/music/languages")
def languages() -> dict[str, Any]:
    return {"languages": list(MEANING_LANGUAGES), "count": len(MEANING_LANGUAGES)}


@app.get("/api/music/songs")
def list_songs(
    language: str = "", topic: str = "", limit: int = 200
) -> dict[str, Any]:
    rows = _CATALOG.list(language=language, topic=topic, limit=limit)
    return {"count": len(rows), "songs": rows, "total_catalog": len(_CATALOG.songs)}


@app.get("/api/music/songs/{song_id}")
def get_song(song_id: str) -> dict[str, Any]:
    try:
        song = _CATALOG.get(song_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=f"Unknown song '{song_id}'") from exc
    return song.model_dump()


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
