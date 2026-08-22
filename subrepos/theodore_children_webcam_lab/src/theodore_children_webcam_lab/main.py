"""FastAPI application for Theodore's children webcam play lab."""

from __future__ import annotations

try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001
    pass

import hashlib
import os
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from . import __version__, tts
from .analytics import AggregateAnalytics
from .children_page import FAVICON_SVG, render_children_page
from .game_engine import PICTURE_WORDS, fun_score, score_spoken

PACKAGE_DIR = Path(__file__).resolve().parent
STATIC_DIR = PACKAGE_DIR / "static"
VISION_ASSET_DIR = Path(
    os.environ.get("AOEP_VISION_ASSET_DIR") or PACKAGE_DIR / "vendor" / "vision"
)

app = FastAPI(
    title="Theodore Children Webcam Lab",
    version=__version__,
    description="Private, playful browser-local face and hand learning games for ages 4-10.",
)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if VISION_ASSET_DIR.is_dir():
    app.mount("/vendor/vision", StaticFiles(directory=VISION_ASSET_DIR), name="vision-assets")

_analytics = AggregateAnalytics()


class PronounceRequest(BaseModel):
    target: str = Field(min_length=1, max_length=80)
    heard: str = Field(default="", max_length=200)
    kind: Literal["letter", "word", "noun"] = "word"


class AnalyticsRequest(BaseModel):
    model_config = {"extra": "forbid"}
    activity_id: str = Field(min_length=1, max_length=80)
    age_band: str = "unknown"
    outcome: str = "unknown"
    attempts: int = Field(default=0, ge=0, le=100)
    duration_ms: int = Field(default=0, ge=0, le=3_600_000)
    fun_score: int = Field(default=0, ge=0, le=100)
    components: dict[str, Any] = Field(default_factory=dict)
    celebration_kind: str = ""
    miss_gag_id: str = ""
    theme_pack: str = ""
    seated_only: bool = False


def _asset_tag() -> str:
    """Fingerprint of the front-end sources.

    The version alone is not enough: edits during a release cycle leave it
    unchanged, so a browser keeps a cached script and the page appears not to
    pick up any fix. Hashing the files themselves changes the URL exactly when
    the code changes.
    """
    digest = hashlib.sha256(__version__.encode())
    for name in ("app.js", "vision_math.js", "app.css"):
        path = STATIC_DIR / name
        if path.is_file():
            digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def children_lab_page() -> str:
    return render_children_page(_asset_tag())


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> Response:
    return Response(FAVICON_SVG, media_type="image/svg+xml")


@app.get("/health")
def health() -> dict[str, Any]:
    return {
        "ok": True,
        "service": "theodore-children-webcam-lab",
        "version": __version__,
        "ages": [4, 10],
        "camera_uploads": False,
        "audio_uploads": False,
        "face_id": False,
        "two_hand_games": True,
        "face_expression_games": True,
        "movement_games": True,
        "fun_analytics": "local-first-opt-in-aggregate",
        "vision_assets": "self-hosted" if VISION_ASSET_DIR.is_dir() else "cdn-with-pointer-fallback",
        "speech": tts.tts_status(),
    }


@app.get("/api/child/content")
def content() -> dict[str, Any]:
    return {
        "letters": [
            {"letter": letter.upper(), "word": word}
            for letter, word in PICTURE_WORDS.items()
        ],
        "games": [
            "trace-letter", "trace-picture", "say-letter", "oh-behave", "heart",
            "idea", "fist-bump", "wow", "blow-kiss", "wink", "make-pose",
            "balloon", "fish", "popcorn", "fruit-cut", "air-drums", "bird-flap",
            "head-bop", "face-chase", "stand-sit", "dance-freeze", "rainbow-reach",
        ],
        "themes": ["cuddly", "hero", "mix"],
    }


@app.get("/api/tts/status")
def tts_status() -> dict[str, Any]:
    return tts.tts_status()


@app.get("/api/tts")
@app.post("/api/tts")
def speak(text: str = "", language: str = "en", style: str = "cheerful") -> Response:
    try:
        audio, mime, engine = tts.synthesize(text, language=language, style=style)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except tts.ProviderUnavailable as exc:
        raise HTTPException(status_code=501, detail=str(exc)) from exc
    return Response(
        audio,
        media_type=mime,
        headers={"X-TTS-Engine": engine, "Cache-Control": "no-store"},
    )


@app.post("/api/child/pronounce")
def pronounce(req: PronounceRequest) -> dict[str, Any]:
    return score_spoken(req.target, req.heard, kind=req.kind)


@app.post("/api/child/fun-score")
def calculate_fun(payload: dict[str, Any]) -> dict[str, Any]:
    allowed = {
        "completed", "attempts", "duration_ms", "target_ms", "combo",
        "celebration", "smile", "kept_going", "mobility_regions", "skipped",
    }
    return fun_score(**{key: value for key, value in payload.items() if key in allowed})


@app.post("/api/child/analytics")
def record_analytics(req: AnalyticsRequest) -> dict[str, Any]:
    try:
        return _analytics.record(req.model_dump())
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.get("/api/child/analytics/summary")
def analytics_summary() -> dict[str, Any]:
    return _analytics.snapshot()


def main() -> None:
    import uvicorn

    uvicorn.run(
        "theodore_children_webcam_lab.main:app",
        host="0.0.0.0",
        port=8018,
        reload=False,
    )


if __name__ == "__main__":
    main()
