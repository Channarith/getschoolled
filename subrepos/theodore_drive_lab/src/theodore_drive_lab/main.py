"""FastAPI app for Drive Mode fine-tune lab."""

from __future__ import annotations


# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .answer_grounding import evaluate_answers
from .bakeoff import get_runner
from .drive_tuning import PRESETS, DriveTuning
from .qualify_page import render_qualify_page
from .wake_eval import evaluate_wake, load_wake_cases, parse_wake_utterance

# Platform language set (Drive wake word is English; commands are multilingual).
DRIVE_LANGUAGES: tuple[str, ...] = (
    "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk",
    "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko",
    "vi", "th", "id", "sw", "el", "cs", "km",
)

app = FastAPI(title="Theodore Drive Lab", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def qualify() -> HTMLResponse:
    return HTMLResponse(render_qualify_page())


class TuningPatch(BaseModel):
    knobs: dict[str, Any] = Field(default_factory=dict)


class WakeParseRequest(BaseModel):
    text: str = Field(min_length=1)
    wake_required: bool | None = None


class BakeoffRequest(BaseModel):
    rounds: int = Field(default=12, ge=1, le=100)


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
        "service": "theodore-drive-lab",
        "wake_cases": len(runner.cases),
        "tuning": runner.tuning.to_dict(),
        **readiness,
        "supported_languages": list(DRIVE_LANGUAGES),
        "supported_language_count": len(DRIVE_LANGUAGES),
    }


@app.get("/api/drive/tuning")
def get_tuning() -> dict[str, Any]:
    runner = get_runner()
    return {"knobs": runner.tuning.to_dict(), "presets": sorted(PRESETS.keys())}


@app.patch("/api/drive/tuning")
def patch_tuning(req: TuningPatch) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = runner.tuning.patched(req.knobs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"knobs": runner.tuning.to_dict()}


@app.post("/api/drive/tuning/preset/{name}")
def apply_preset(name: str) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = DriveTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"preset": name, "knobs": runner.tuning.to_dict()}


@app.post("/api/drive/wake/eval")
def wake_eval() -> dict[str, Any]:
    runner = get_runner()
    report = evaluate_wake(load_wake_cases(), runner.tuning)
    runner.telemetry.record_wake()
    return {"report": report, "tuning": runner.tuning.to_dict()}


@app.post("/api/drive/wake/parse")
def wake_parse(req: WakeParseRequest) -> dict[str, Any]:
    runner = get_runner()
    wake_required = (
        runner.tuning.wake_required if req.wake_required is None else req.wake_required
    )
    return parse_wake_utterance(req.text, wake_required=wake_required)


@app.post("/api/drive/answer/eval")
def answer_eval() -> dict[str, Any]:
    runner = get_runner()
    report = evaluate_answers(tuning=runner.tuning)
    runner.telemetry.record_answer()
    return {"report": report, "tuning": runner.tuning.to_dict()}


@app.post("/api/drive/bakeoff")
def bakeoff(req: BakeoffRequest) -> dict[str, Any]:
    return get_runner().run_bakeoff(rounds=req.rounds)


@app.get("/api/drive/champion")
def champion() -> dict[str, Any]:
    return get_runner().champion


@app.get("/api/drive/telemetry")
def telemetry() -> dict[str, Any]:
    return get_runner().telemetry.snapshot()


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_drive_lab.main:app", host="0.0.0.0", port=8096, reload=False)


if __name__ == "__main__":
    main()
