"""FastAPI app for the Theodore all-in-one LLM training lab."""

from __future__ import annotations

try:
    from aoep_shared.env_bootstrap import ensure_lab_env

    ensure_lab_env()
except Exception:  # noqa: BLE001 — labs must still boot offline
    pass

import os
from pathlib import Path
from typing import Any, List, Optional

from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from aoep_shared.live_audio_agents import inject_client, install_live_audio_routes
from aoep_shared.llm_training import (
    assemble,
    assemble_report,
    counts_by_source,
    robot_pack,
    simulate_robot_turn,
    validate_examples,
    write_jsonl,
)

from .qualify_page import render_qualify_page
from .paths import fixture_root

app = FastAPI(title="Theodore LLM Lab", version="0.1.0")
install_live_audio_routes(app, lab_name="Theodore LLM Lab")


def _roots(include_curriculum: bool) -> List[Path]:
    roots = [fixture_root()]
    extra = (os.environ.get("AOEP_LLM_CORPUS") or "").strip()
    if extra:
        roots.extend(Path(p) for p in extra.split(os.pathsep) if p.strip())
    if include_curriculum:
        curriculum = os.environ.get("CURRICULUM_DIR") or ""
        if curriculum:
            roots.append(Path(curriculum))
        else:
            here = Path(__file__).resolve()
            sample = here.parents[4] / "sample-curriculum"
            if sample.is_dir():
                roots.append(sample)
    return roots


class AssembleReq(BaseModel):
    include_curriculum: bool = False
    out: Optional[str] = None


class RobotTurnReq(BaseModel):
    text: str = Field(default="Today we learn fractions together.", min_length=3, max_length=400)


@app.get("/", response_class=HTMLResponse)
@app.get("/lab", response_class=HTMLResponse)
def qualify() -> HTMLResponse:
    return HTMLResponse(inject_client(render_qualify_page()))


@app.get("/health")
def health() -> dict[str, Any]:
    report = assemble_report([fixture_root()])
    return {
        "ok": True,
        "service": "theodore-llm-lab",
        "features": [
            "library",
            "profiles",
            "webcam",
            "audio",
            "games",
            "rag",
            "qlora-check",
            "robot-gguf-pack",
        ],
        "fixture_examples": report["example_count"],
        "by_source": report["by_source"],
        "gpu_required_for_weight_update": True,
        "portable": True,
    }


@app.post("/api/llm/assemble")
def api_assemble(req: AssembleReq) -> dict[str, Any]:
    report = assemble_report(_roots(req.include_curriculum))
    written = None
    if req.out:
        examples = assemble(_roots(req.include_curriculum))
        written = write_jsonl(examples, Path(req.out))
        report["written"] = written
        report["out"] = req.out
    return report


@app.post("/api/llm/check")
def api_check(req: AssembleReq) -> dict[str, Any]:
    examples = assemble(_roots(req.include_curriculum))
    rows = [ex.to_dict() for ex in examples]
    problems = validate_examples(rows)
    return {
        "ok": not problems,
        "example_count": len(rows),
        "by_source": counts_by_source(examples),
        "problems": problems,
        "finetune": "python3 training/run_finetune.py --check --train <jsonl>",
        "gpu_next": "python3 training/run_finetune.py --offline --base-model /models/education-base --train <jsonl>",
    }


@app.post("/api/llm/robot-pack")
def api_pack(req: AssembleReq) -> dict[str, Any]:
    examples = assemble(_roots(req.include_curriculum))
    pack = robot_pack(
        example_count=len(examples),
        sources=counts_by_source(examples),
    )
    return {"ok": True, "pack": pack, "by_source": pack["sources"]}


@app.post("/api/llm/robot-turn")
def api_robot(req: RobotTurnReq) -> dict[str, Any]:
    turn = simulate_robot_turn(req.text)
    turn["ok"] = True
    return turn


def main() -> None:
    import uvicorn

    uvicorn.run("theodore_llm_lab.main:app", host="0.0.0.0", port=8019, reload=False)


if __name__ == "__main__":
    main()
