"""All-in-one education LLM training corpus + robot-portable export.

The CLI under ``training/`` already exports class transcripts and runs QLoRA
on a GPU box. This module is the missing lab contract: gather course-library
text, pedagogical user profiles, and webcam / audio / game / RAG learning
signals into the same instruction/response JSONL, then emit a GGUF+ONNX
humanoid pack that the edge runtime already knows how to flash.

No GPU, torch, or network is required for assemble / validate / robot-pack.
Real weight updates still go through ``training/run_finetune.py`` on a CUDA
host. Protected attributes (race, ethnicity) and raw names never enter
example context.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Mapping, Optional, Sequence, Tuple

CONDITIONING_FEATURES = (
    "age_band",
    "language",
    "reading_level",
    "learning_style",
    "professionalism",
    "prior_mastery",
)
PROTECTED_ATTRIBUTES = ("race", "ethnicity")
PII_KEYS = ("name", "full_name", "email", "phone", "face_id", "voiceprint")
SOURCES = ("library", "profiles", "webcam", "audio", "games", "rag")

_SLIDE_RE = re.compile(
    r"^SLIDE\s+(\d+)\s*\|\s*(.+)$",
    re.MULTILINE,
)
_LESSON_TITLE_RE = re.compile(r"^LESSON:\s*(.+)$", re.MULTILINE)
_LANG_RE = re.compile(r"^LANGUAGE:\s*(\S+)", re.MULTILINE)


def _safe_audience(raw: Optional[Mapping[str, Any]]) -> Dict[str, Any]:
    src = dict(raw or {})
    out: Dict[str, Any] = {}
    for key in CONDITIONING_FEATURES:
        if key in src and src[key] is not None:
            out[key] = src[key]
    if "prior_mastery" in out:
        try:
            out["prior_mastery"] = max(0.0, min(1.0, float(out["prior_mastery"])))
        except (TypeError, ValueError):
            out["prior_mastery"] = 0.5
    out.setdefault("age_band", "adult")
    out.setdefault("language", "en")
    out.setdefault("reading_level", "intermediate")
    out.setdefault("learning_style", "mixed")
    out.setdefault("professionalism", "neutral")
    out.setdefault("prior_mastery", 0.5)
    return out


def redact_record(row: Mapping[str, Any]) -> Dict[str, Any]:
    """Drop protected attributes and obvious PII from any mapping."""
    return {
        k: v
        for k, v in row.items()
        if k not in PROTECTED_ATTRIBUTES and k not in PII_KEYS
    }


@dataclass
class TrainingExample:
    instruction: str
    response: str
    context: Dict[str, Any]
    source: str
    reward: float = 1.0
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        ctx = _safe_audience(self.context)
        leaked = [k for k in PROTECTED_ATTRIBUTES if k in ctx]
        if leaked:
            raise ValueError(f"protected attribute(s) {leaked} leaked into context")
        return {
            "instruction": self.instruction.strip(),
            "response": self.response.strip(),
            "context": ctx,
            "reward": round(float(self.reward), 4),
            "tags": list(self.tags),
            "source": self.source,
        }


@dataclass
class CorpusRecord:
    source: str
    path: str
    payload: Dict[str, Any]


def _iter_json_rows(path: Path) -> Iterator[Dict[str, Any]]:
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if not text:
        return
    if path.suffix == ".jsonl":
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(row, dict):
                yield row
        return
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return
    if isinstance(data, list):
        for row in data:
            if isinstance(row, dict):
                yield row
    elif isinstance(data, dict):
        yield data


def parse_lesson_text(text: str, *, default_language: str = "en") -> Tuple[str, str, List[Dict[str, str]]]:
    """Parse sample-curriculum lesson.txt into title, language, slides."""
    title_m = _LESSON_TITLE_RE.search(text)
    title = title_m.group(1).strip() if title_m else "Untitled lesson"
    lang_m = _LANG_RE.search(text)
    language = (lang_m.group(1).strip() if lang_m else default_language) or default_language
    slides: List[Dict[str, str]] = []
    parts = re.split(r"(?=^SLIDE\s+\d+\s*\|)", text, flags=re.MULTILINE)
    for part in parts:
        m = _SLIDE_RE.search(part)
        if not m:
            continue
        body = part[m.end() :].strip()
        narration = ""
        facts: List[str] = []
        lines: List[str] = []
        for line in body.splitlines():
            if line.startswith("NARRATION:"):
                narration = line[len("NARRATION:") :].strip()
            elif line.startswith("FACT:"):
                facts.append(line[len("FACT:") :].strip())
            else:
                lines.append(line)
        content = " ".join(ln.strip() for ln in lines if ln.strip())
        slides.append(
            {
                "id": m.group(1),
                "title": m.group(2).strip(),
                "content": content,
                "narration": narration,
                "facts": " ".join(facts),
            }
        )
    # Standalone FACT lines after the last slide still belong to the lesson.
    trailing_facts = [
        ln[len("FACT:") :].strip()
        for ln in text.splitlines()
        if ln.startswith("FACT:")
    ]
    if trailing_facts and slides:
        slides[-1]["facts"] = " ".join(trailing_facts)
    return title, language, slides


def examples_from_lesson(
    text: str,
    *,
    audience: Optional[Mapping[str, Any]] = None,
    origin: str = "library",
) -> List[TrainingExample]:
    title, language, slides = parse_lesson_text(text)
    ctx = _safe_audience({"language": language, **dict(audience or {})})
    out: List[TrainingExample] = []
    for slide in slides:
        answer = slide.get("narration") or slide.get("content") or ""
        if not answer:
            continue
        out.append(
            TrainingExample(
                instruction=f"Teach the slide '{slide['title']}' from the lesson '{title}'.",
                response=answer,
                context=ctx,
                source="library",
                tags=[origin, f"slide-{slide['id']}", title.lower().replace(" ", "-")[:48]],
            )
        )
        facts = (slide.get("facts") or "").strip()
        if facts:
            out.append(
                TrainingExample(
                    instruction=f"What key facts should a learner remember from '{slide['title']}'?",
                    response=facts,
                    context=ctx,
                    source="library",
                    tags=[origin, "facts", title.lower().replace(" ", "-")[:48]],
                )
            )
    return out


def examples_from_course_json(obj: Mapping[str, Any]) -> List[TrainingExample]:
    title = str(obj.get("title") or obj.get("course_id") or "Course")
    language = str(obj.get("language") or "en")
    ctx = _safe_audience(obj.get("audience") or {"language": language})
    slides = obj.get("slides") or obj.get("lessons") or []
    out: List[TrainingExample] = []
    if isinstance(slides, list):
        for i, slide in enumerate(slides, start=1):
            if not isinstance(slide, dict):
                continue
            heading = str(slide.get("title") or slide.get("heading") or f"Slide {i}")
            answer = str(
                slide.get("narration")
                or slide.get("notes")
                or slide.get("body")
                or slide.get("text")
                or ""
            ).strip()
            if not answer:
                continue
            out.append(
                TrainingExample(
                    instruction=f"Teach '{heading}' from '{title}'.",
                    response=answer,
                    context=ctx,
                    source="library",
                    tags=["course-json", title.lower().replace(" ", "-")[:48]],
                )
            )
    return out


def examples_from_profile(row: Mapping[str, Any]) -> List[TrainingExample]:
    """Turn a pedagogical profile into a tone/adaptation example (no PII)."""
    clean = redact_record(row)
    ctx = _safe_audience(clean)
    style = ctx.get("learning_style", "mixed")
    age = ctx.get("age_band", "adult")
    lang = ctx.get("language", "en")
    mastery = ctx.get("prior_mastery", 0.5)
    instruction = (
        "Adapt the next teaching turn to this learner's profile. "
        "Do not mention identity, race, or names."
    )
    response = (
        f"Use a {ctx.get('professionalism', 'neutral')} register in {lang} for a "
        f"{age} learner who prefers {style} practice. Prior mastery is {mastery}. "
        "Keep explanations grounded in the current lesson and check understanding "
        "before advancing."
    )
    return [
        TrainingExample(
            instruction=instruction,
            response=response,
            context=ctx,
            source="profiles",
            tags=["profile-adapt"],
        )
    ]


def examples_from_webcam(row: Mapping[str, Any]) -> List[TrainingExample]:
    ctx = _safe_audience(row.get("audience") or row)
    signal = str(row.get("signal") or row.get("event") or "attention")
    coach = str(row.get("coach") or row.get("teacher") or "").strip()
    if not coach:
        coach = {
            "attention_drop": "I notice eyes left the lesson. Let's look back at the slide together.",
            "confusion": "That look tells me this step is muddy. I'll restate it in smaller pieces.",
            "success_pose": "Yes — that pose matches the goal. Nice work; we can try the next one.",
            "absence": "I cannot see a learner in frame, so I will pause the lesson until you return.",
        }.get(signal, "Stay with the activity; I am watching posture and attention, not identity.")
    return [
        TrainingExample(
            instruction=f"Webcam learning signal: {signal}. How should Theodore coach?",
            response=coach,
            context=ctx,
            source="webcam",
            tags=["webcam", signal],
        )
    ]


def examples_from_audio(row: Mapping[str, Any]) -> List[TrainingExample]:
    ctx = _safe_audience(row.get("audience") or row)
    student = str(row.get("transcript") or row.get("student") or row.get("instruction") or "").strip()
    teacher = str(row.get("teacher") or row.get("response") or row.get("reply") or "").strip()
    if not student or not teacher:
        return []
    return [
        TrainingExample(
            instruction=student,
            response=teacher,
            context=ctx,
            source="audio",
            tags=["audio", str(row.get("channel") or "mic")],
        )
    ]


def examples_from_game(row: Mapping[str, Any]) -> List[TrainingExample]:
    ctx = _safe_audience(row.get("audience") or row)
    game = str(row.get("game") or "play")
    outcome = str(row.get("outcome") or "attempt")
    coach = str(row.get("coach") or row.get("teacher") or "").strip()
    if not coach:
        if outcome in ("success", "pass", "win"):
            coach = f"{game} succeeded. Celebrate briefly, then raise the next challenge one step."
        else:
            coach = f"{game} missed. Name the target pose or motion again and invite one more try."
    return [
        TrainingExample(
            instruction=f"The learner just played {game} with outcome {outcome}. Coach the next beat.",
            response=coach,
            context=ctx,
            source="games",
            tags=["game", game, outcome],
        )
    ]


def examples_from_rag(row: Mapping[str, Any]) -> List[TrainingExample]:
    ctx = _safe_audience(row.get("audience") or row)
    question = str(row.get("question") or row.get("instruction") or "").strip()
    answer = str(row.get("answer") or row.get("response") or "").strip()
    if not question or not answer:
        return []
    passages = row.get("passages") or row.get("sources") or []
    if isinstance(passages, list) and passages:
        grounded = " Ground the answer in: " + " | ".join(str(p) for p in passages[:4])
        answer = answer + grounded
    return [
        TrainingExample(
            instruction=question,
            response=answer,
            context=ctx,
            source="rag",
            tags=["rag", str(row.get("topic") or "kb")],
        )
    ]


def _guess_source(path: Path) -> Optional[str]:
    name = path.name.lower()
    if "profile" in name:
        return "profiles"
    if "webcam" in name or "vision" in name:
        return "webcam"
    if "audio" in name or "transcript" in name:
        return "audio"
    if "game" in name:
        return "games"
    if "rag" in name or "golden" in name:
        return "rag"
    if path.suffix in {".txt"} or name.endswith(".course.json") or "lesson" in name:
        return "library"
    return None


def discover_files(roots: Sequence[Path]) -> List[Path]:
    found: List[Path] = []
    for root in roots:
        if not root.exists():
            continue
        if root.is_file():
            found.append(root)
            continue
        for path in sorted(root.rglob("*")):
            if not path.is_file():
                continue
            if path.suffix.lower() not in {".txt", ".json", ".jsonl"}:
                continue
            if path.name.startswith("."):
                continue
            if _guess_source(path):
                found.append(path)
    return found


def ingest_file(path: Path) -> List[TrainingExample]:
    source = _guess_source(path)
    if source is None:
        return []
    if path.suffix.lower() == ".txt" or path.name == "lesson.txt":
        return examples_from_lesson(path.read_text(encoding="utf-8", errors="replace"), origin=str(path))
    examples: List[TrainingExample] = []
    for row in _iter_json_rows(path):
        if source == "library":
            examples.extend(examples_from_course_json(row))
        elif source == "profiles":
            examples.extend(examples_from_profile(row))
        elif source == "webcam":
            examples.extend(examples_from_webcam(row))
        elif source == "audio":
            examples.extend(examples_from_audio(row))
        elif source == "games":
            examples.extend(examples_from_game(row))
        elif source == "rag":
            examples.extend(examples_from_rag(row))
    return examples


def assemble(roots: Sequence[os.PathLike[str] | str]) -> List[TrainingExample]:
    examples: List[TrainingExample] = []
    for path in discover_files([Path(r) for r in roots]):
        examples.extend(ingest_file(path))
    return examples


def counts_by_source(examples: Sequence[TrainingExample]) -> Dict[str, int]:
    counts = {s: 0 for s in SOURCES}
    for ex in examples:
        counts[ex.source] = counts.get(ex.source, 0) + 1
    return counts


def validate_examples(rows: Sequence[Mapping[str, Any]]) -> List[str]:
    problems: List[str] = []
    if not rows:
        problems.append("dataset is empty")
    for i, row in enumerate(rows):
        if not str(row.get("instruction") or "").strip() or not str(row.get("response") or "").strip():
            problems.append(f"row {i}: missing instruction/response")
        ctx = row.get("context") or {}
        if not isinstance(ctx, dict):
            problems.append(f"row {i}: context must be an object")
            continue
        leaked = [k for k in list(PROTECTED_ATTRIBUTES) + list(PII_KEYS) if k in ctx]
        if leaked:
            problems.append(f"row {i}: forbidden key(s) {leaked} in context")
    return problems


def write_jsonl(examples: Sequence[TrainingExample], path: Path) -> int:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as fh:
        for ex in examples:
            fh.write(json.dumps(ex.to_dict(), ensure_ascii=False) + "\n")
    return len(examples)


def robot_pack(
    *,
    model_id: str = "salareen-education",
    quantization: str = "Q4_K_M",
    embodiment: str = "robot",
    example_count: int = 0,
    sources: Optional[Mapping[str, int]] = None,
) -> Dict[str, Any]:
    """Portable on-device bundle matching apps/agent-runtime/edge/manifest.yaml."""
    return {
        "kind": "aoep-robot-llm-pack",
        "model_id": model_id,
        "portable": True,
        "embodiment": embodiment,
        "deploy_mode": "edge",
        "example_count": example_count,
        "sources": dict(sources or {}),
        "models": [
            {"role": "llm", "format": "gguf", "quantization": quantization, "path": "/models/llm.gguf"},
            {"role": "asr", "format": "onnx", "path": "/models/asr.onnx"},
            {"role": "tts", "format": "onnx", "path": "/models/tts.onnx"},
            {"role": "vision", "format": "onnx", "path": "/models/vision/"},
        ],
        "capabilities": {
            "library": True,
            "profiles": True,
            "webcam": True,
            "audio": True,
            "games": True,
            "rag": True,
        },
        "embodiment_contract": {
            "say": "robot speaker / on-device TTS",
            "gesture": "joint / servo motion from named teaching cues",
            "perceive": "robot cameras + mics into VisionProvider (no identity training)",
        },
        "safety": {
            "protected_attributes_in_weights": False,
            "hil_autonomy_required": True,
            "kill_switch": "halt say() and gesture()",
        },
        "next_gpu_step": (
            "On a CUDA host: python3 training/run_finetune.py --offline "
            "--base-model /models/education-base --train <this jsonl> "
            "--output /models/adapter  then llama-quantize to GGUF Q4_K_M."
        ),
        "flash": [
            "DRY_RUN=1 apps/agent-runtime/edge/package_edge.sh",
            "Mount /models/llm.gguf on Jetson Orin / Coral / x86 mini-PC",
            "DEPLOY_MODE=edge EMBODIMENT=robot",
        ],
    }


def simulate_robot_turn(text: str = "Today we learn fractions together.") -> Dict[str, Any]:
    """Prove the same teaching beat can drive a humanoid without GPU."""
    from .edge import edge_config, edge_smoke
    from .factory import ProviderFactory

    report = edge_smoke(ProviderFactory(edge_config(embodiment="robot")))
    from .providers.embodiment import MockRobotProvider, narrate

    robot = MockRobotProvider()
    actions = narrate(robot, text, gesture="wave")
    return {
        "offline": bool(report.get("offline")),
        "embodiment_target": report.get("embodiment_target"),
        "mock_actions": [
            {"modality": a.modality, "payload": a.payload} for a in actions
        ],
        "say": text,
        "gesture": "wave",
    }


def default_roots() -> List[Path]:
    here = Path(__file__).resolve()
    repo = here.parents[4] if len(here.parents) >= 5 else Path.cwd()
    roots: List[Path] = []
    env_roots = os.environ.get("AOEP_LLM_CORPUS") or ""
    for part in env_roots.split(os.pathsep):
        if part.strip():
            roots.append(Path(part.strip()))
    curriculum = os.environ.get("CURRICULUM_DIR")
    if curriculum:
        roots.append(Path(curriculum))
    else:
        sample = repo / "sample-curriculum"
        if sample.is_dir():
            roots.append(sample)
    return roots


def assemble_report(roots: Optional[Sequence[os.PathLike[str] | str]] = None) -> Dict[str, Any]:
    paths = [Path(p) for p in (roots if roots is not None else default_roots())]
    examples = assemble(paths)
    rows = [ex.to_dict() for ex in examples]
    problems = validate_examples(rows)
    by_source = counts_by_source(examples)
    return {
        "ok": not problems,
        "roots": [str(p) for p in paths],
        "files": [str(p) for p in discover_files(paths)],
        "example_count": len(examples),
        "by_source": by_source,
        "problems": problems,
        "preview": rows[:8],
    }
