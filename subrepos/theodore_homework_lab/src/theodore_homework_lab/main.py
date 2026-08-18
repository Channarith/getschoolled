"""FastAPI app for Theodore homework generate/grade quality lab."""

from __future__ import annotations


# Load config/local.env so XAI_API_KEY / ELEVENLABS_API_KEY / SPEECH_BASE_URL
# work without a manual `set -a; . config/local.env` in every shell.
try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline / without shared
    pass


from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from .generate import generate_assignment, generate_full_battery, wrap_shared_classic
from .grade import grade_assignment
from .methodologies import list_methodologies, methodology_count
from .models import LabAssignment
from .qualify_page import render_qualify_page
from .quality import PRESETS, HomeworkTuning, get_runner

try:
    from aoep_shared.languages import SUPPORTED_LANGUAGES as _LOCALES
except Exception:  # noqa: BLE001 — standalone lab
    _LOCALES = (
        "en", "es", "fr", "de", "it", "pt", "nl", "pl", "ru", "uk",
        "tr", "ar", "he", "hi", "bn", "ur", "fa", "zh", "ja", "ko",
        "vi", "th", "id", "sw", "el", "cs", "km",
    )

SUPPORTED_LOCALES: tuple[str, ...] = tuple(_LOCALES)

app = FastAPI(title="Theodore Homework Lab", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def qualify() -> HTMLResponse:
    return HTMLResponse(render_qualify_page())


class GenerateRequest(BaseModel):
    title: str = "Homework practice"
    passages: List[str] = Field(default_factory=lambda: [
        "photosynthesis: plants make food using light water and carbon dioxide"
    ])
    subject: str = "science"
    source: str = ""
    locale: str = "en"
    methodologies: Optional[List[str]] = None
    max_items: int = 12
    verse: str = ""
    meaning_en: str = ""
    media_uri: str = ""
    difficulty: str = "medium"


class GradeRequest(BaseModel):
    assignment: Dict[str, Any]
    answers: Any  # list or map


class TuningPatch(BaseModel):
    knobs: Dict[str, Any] = Field(default_factory=dict)


@app.get("/health")
def health() -> dict[str, Any]:
    runner = get_runner()
    readiness: Dict[str, Any] = {}
    try:
        from aoep_shared.env_bootstrap import speech_readiness

        readiness = speech_readiness()
    except Exception:  # noqa: BLE001
        pass
    return {
        "ok": True,
        "service": "theodore-homework-lab",
        "methodologies": methodology_count(),
        "tuning": runner.tuning.to_dict(),
        "champion": runner.champion,
        **readiness,
        "supported_locales": list(SUPPORTED_LOCALES),
        "supported_locale_count": len(SUPPORTED_LOCALES),
    }


@app.get("/api/homework/methodologies")
def methodologies(family: str = "") -> dict[str, Any]:
    rows = list_methodologies(family=family)
    return {
        "count": len(rows),
        "total_registered": methodology_count(),
        "methodologies": [
            {
                "id": m.id,
                "family": m.family,
                "label": m.label,
                "grading_mode": m.grading_mode.value,
                "description": m.description,
            }
            for m in rows
        ],
    }


@app.post("/api/homework/generate")
def api_generate(req: GenerateRequest) -> dict[str, Any]:
    locale = (req.locale or "en").strip().lower().split("-")[0]
    if locale not in SUPPORTED_LOCALES:
        raise HTTPException(
            status_code=422,
            detail=f"Unsupported locale '{req.locale}'. Supported: {', '.join(SUPPORTED_LOCALES)}",
        )
    context = {}
    if req.verse:
        context["verse"] = req.verse
    if req.meaning_en:
        context["meaning_en"] = req.meaning_en
    if req.media_uri:
        context["media_uri"] = req.media_uri
    try:
        assignment = generate_assignment(
            title=req.title,
            passages=req.passages,
            subject=req.subject,
            source=req.source,
            locale=locale,
            methodologies=req.methodologies,
            max_items=req.max_items,
            context=context,
            difficulty=req.difficulty,
        )
    except KeyError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"assignment": assignment.model_dump()}


@app.post("/api/homework/generate/battery")
def api_battery(req: GenerateRequest) -> dict[str, Any]:
    context = {"verse": req.verse or "Count with me one two three",
               "meaning_en": req.meaning_en or "Practice counting."}
    assignment = generate_full_battery(
        passages=req.passages,
        subject=req.subject,
        locale=req.locale,
        context=context,
        title=req.title or "Full methodology battery",
    )
    return {
        "assignment": assignment.model_dump(),
        "methodology_count": len(assignment.items),
        "registered": methodology_count(),
    }


@app.post("/api/homework/generate/shared-classic")
def api_shared_classic(req: GenerateRequest) -> dict[str, Any]:
    assignment = wrap_shared_classic(
        req.passages, title=req.title, subject=req.subject, locale=req.locale
    )
    return {"assignment": assignment.model_dump()}


@app.post("/api/homework/grade")
def api_grade(req: GradeRequest) -> dict[str, Any]:
    try:
        assignment = LabAssignment.model_validate(req.assignment)
    except Exception as exc:
        raise HTTPException(status_code=422, detail=f"Invalid assignment: {exc}") from exc
    # answers is typed Any — a null/scalar body must be a 422, not a 500.
    if req.answers is None or not isinstance(req.answers, (list, dict)):
        raise HTTPException(status_code=422, detail="answers must be a list or an object")
    try:
        report = grade_assignment(assignment, req.answers)
    except (TypeError, ValueError, KeyError, IndexError) as exc:
        raise HTTPException(status_code=422, detail=f"Could not grade answers: {exc}") from exc
    get_runner().telemetry.grade_calls += 1
    get_runner().telemetry.items_graded += len(report.items)
    return {"report": report.model_dump()}


@app.get("/api/homework/tuning")
def get_tuning() -> dict[str, Any]:
    return {"knobs": get_runner().tuning.to_dict(), "presets": list(PRESETS)}


@app.patch("/api/homework/tuning")
def patch_tuning(req: TuningPatch) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = runner.tuning.patched(req.knobs)
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    return {"knobs": runner.tuning.to_dict()}


@app.post("/api/homework/tuning/preset/{name}")
def preset(name: str) -> dict[str, Any]:
    runner = get_runner()
    try:
        runner.tuning = HomeworkTuning.preset(name)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return {"preset": name, "knobs": runner.tuning.to_dict()}


@app.post("/api/homework/eval/gold")
def eval_gold() -> dict[str, Any]:
    return get_runner().evaluate_once()


@app.post("/api/homework/bakeoff")
def bakeoff(rounds: int = 2) -> dict[str, Any]:
    return get_runner().run_blocking(rounds=max(1, min(rounds, 20)))


@app.get("/api/homework/telemetry")
def telemetry() -> dict[str, Any]:
    return get_runner().telemetry.snapshot()


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_homework_lab.main:app", host="0.0.0.0", port=8098, reload=False)


if __name__ == "__main__":
    main()
