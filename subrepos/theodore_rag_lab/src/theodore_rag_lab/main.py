"""FastAPI app for the Theodore RAG auto-tune lab."""

from __future__ import annotations


# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


from typing import Any, Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .bakeoff_loop import get_runner
from .dictionary_lab import (
    dialect_probe,
    dictionary_browse,
    dictionary_search,
    feedback_snapshot,
    grade_regurgitation,
    lab_catalog,
    regurgitation_deck,
    submit_feedback,
)
from .qualify_page import render_qualify_page
from .rag_tuning import PRESETS, RagTuning

app = FastAPI(title="Theodore RAG Lab", version="0.2.0")


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def qualify() -> HTMLResponse:
    return HTMLResponse(render_qualify_page())


class TuningPatch(BaseModel):
    knobs: dict[str, Any] = Field(default_factory=dict)


class TrainStart(BaseModel):
    hours: float = Field(default=1.0, gt=0.0, le=24.0)


class DialectProbeReq(BaseModel):
    text: str = "Welcome! We will walk through the lesson. Take your time. Nice work."
    dialect: str = "us_south"
    language: str = "en"
    title: str = "Practice"


class RegurgitateGrade(BaseModel):
    phrase: str
    answer: str
    language: str = "en"
    region: str = "global"
    dialect: str = ""
    learn: bool = True


class FeedbackReq(BaseModel):
    phrase: str
    meaning: str
    language: str = "en"
    region: str = "global"
    kind: str = "idiom"
    action: str = "correct"
    dialect: str = ""
    note: str = ""


@app.get("/health")
def health() -> dict[str, Any]:
    runner = get_runner()
    readiness: dict[str, Any] = {}
    try:
        from aoep_shared.env_bootstrap import speech_readiness

        readiness = speech_readiness()
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "service": "theodore-rag-lab",
        "docs": len(runner.index) if runner.index is not None else 0,
        "golden": len(runner.examples),
        "tuning": runner.tuning.to_dict(),
        "lexicon_total": cat["lexicon"].get("total", 0),
        "dialects": len(cat["dialects"]),
        "feedback_events": cat["feedback"].get("events", 0),
        "features": [
            "rag_tuning",
            "dictionary",
            "dialects",
            "regurgitation",
            "feedback_learning",
        ],
        **readiness,
    }


@app.get("/api/rag/tuning")
def get_tuning() -> dict[str, Any]:
    runner = get_runner()
    return {
        "knobs": runner.tuning.to_dict(),
        "presets": sorted(PRESETS.keys()),
    }


@app.patch("/api/rag/tuning")
def patch_tuning(req: TuningPatch) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = runner.tuning.patched(req.knobs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"knobs": runner.tuning.to_dict()}


@app.post("/api/rag/tuning/preset/{name}")
def apply_preset(name: str) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = RagTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"preset": name, "knobs": runner.tuning.to_dict()}


@app.post("/api/rag/eval")
def run_eval(details: bool = False) -> dict[str, Any]:
    runner = get_runner()
    report = runner.evaluate_once(include_details=details)
    return {"report": report, "tuning": runner.tuning.to_dict()}


@app.get("/api/rag/sweep")
def run_sweep() -> dict[str, Any]:
    runner = get_runner()
    return {"results": runner.sweep()}


@app.post("/api/rag/train/start")
def train_start(req: TrainStart) -> dict[str, Any]:
    runner = get_runner()
    return runner.start(hours=req.hours)


@app.post("/api/rag/train/run-blocking")
def train_blocking(req: TrainStart) -> dict[str, Any]:
    """Short synchronous bakeoff for CI / scripts (caps rounds)."""
    runner = get_runner()
    hours = min(float(req.hours), 0.05)
    try:
        return runner.run_blocking(hours=hours)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/api/rag/train/status")
def train_status() -> dict[str, Any]:
    return get_runner().status()


@app.post("/api/rag/train/stop")
def train_stop() -> dict[str, Any]:
    return get_runner().stop()


@app.get("/api/rag/champion")
def champion() -> dict[str, Any]:
    return get_runner().status().get("champion") or {}


@app.get("/api/rag/telemetry")
def telemetry() -> dict[str, Any]:
    return get_runner().telemetry.snapshot()


@app.get("/api/dictionary")
def api_dictionary(
    q: str = "",
    language: str = "",
    region: str = "",
    kind: str = "",
    limit: int = Query(default=40, ge=1, le=200),
) -> dict[str, Any]:
    if not any((q, language, region, kind)):
        return dictionary_browse(limit=limit)
    return dictionary_search(q=q, language=language, region=region, kind=kind, limit=limit)


@app.get("/api/dialects")
def api_dialects() -> dict[str, Any]:
    return lab_catalog()


@app.post("/api/dialects/probe")
def api_dialect_probe(req: DialectProbeReq) -> dict[str, Any]:
    return dialect_probe(req.text, req.dialect, language=req.language, title=req.title)


@app.get("/api/regurgitate/deck")
def api_regurgitate_deck(
    dialect: str = "",
    region: str = "",
    language: str = "",
    n: int = Query(default=8, ge=1, le=30),
) -> dict[str, Any]:
    return regurgitation_deck(dialect=dialect, region=region, language=language, n=n)


@app.post("/api/regurgitate/grade")
def api_regurgitate_grade(req: RegurgitateGrade) -> dict[str, Any]:
    return grade_regurgitation(
        phrase=req.phrase,
        answer=req.answer,
        language=req.language,
        region=req.region,
        dialect=req.dialect,
        learn=req.learn,
    )


@app.get("/api/feedback")
def api_feedback_get() -> dict[str, Any]:
    return feedback_snapshot()


@app.post("/api/feedback")
def api_feedback_post(req: FeedbackReq) -> dict[str, Any]:
    try:
        return submit_feedback(
            phrase=req.phrase,
            meaning=req.meaning,
            language=req.language,
            region=req.region,
            kind=req.kind,
            action=req.action,
            dialect=req.dialect,
            note=req.note,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_rag_lab.main:app", host="0.0.0.0", port=8095, reload=False)


if __name__ == "__main__":
    main()
