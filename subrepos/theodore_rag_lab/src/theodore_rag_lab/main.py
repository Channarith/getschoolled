"""FastAPI app for the Theodore RAG auto-tune lab."""

from __future__ import annotations

from typing import Any, Optional

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from .bakeoff_loop import get_runner
from .rag_tuning import PRESETS, RagTuning

app = FastAPI(title="Theodore RAG Lab", version="0.1.0")


class TuningPatch(BaseModel):
    knobs: dict[str, Any] = Field(default_factory=dict)


class TrainStart(BaseModel):
    hours: float = Field(default=1.0, gt=0.0, le=24.0)


@app.get("/health")
def health() -> dict[str, Any]:
    runner = get_runner()
    return {
        "ok": True,
        "service": "theodore-rag-lab",
        "docs": len(runner.index) if runner.index is not None else 0,
        "golden": len(runner.examples),
        "tuning": runner.tuning.to_dict(),
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
    # Use a fresh blocking run without fighting a background thread.
    hours = min(float(req.hours), 0.05)
    return runner.run_blocking(hours=hours)


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


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_rag_lab.main:app", host="0.0.0.0", port=8095, reload=False)


if __name__ == "__main__":
    main()
