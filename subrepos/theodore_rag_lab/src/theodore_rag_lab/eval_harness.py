"""Golden-set RAG evaluation harness (offline)."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Iterable, List, Optional, Sequence

from .rag_tuning import RagTuning

_DATA = Path(__file__).resolve().parents[2] / "data" / "golden_qa.jsonl"


@dataclass
class GoldenExample:
    query: str
    expected_doc_ids: List[str] = field(default_factory=list)
    expected_answer: str = ""
    topic: str = ""

    @classmethod
    def from_dict(cls, row: dict) -> "GoldenExample":
        return cls(
            query=str(row.get("query") or "").strip(),
            expected_doc_ids=[str(x) for x in (row.get("expected_doc_ids") or [])],
            expected_answer=str(row.get("expected_answer") or "").strip(),
            topic=str(row.get("topic") or "").strip(),
        )


@dataclass
class EvalReport:
    n: int
    recall_at_k: float
    mrr: float
    groundedness: float
    latency_ms_avg: float
    rag_quality: float
    hits: int
    details: List[dict] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def load_golden(path: Optional[Path] = None) -> List[GoldenExample]:
    p = path or _DATA
    rows: List[GoldenExample] = []
    if not p.exists():
        return _builtin_golden()
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        rows.append(GoldenExample.from_dict(json.loads(line)))
    return rows or _builtin_golden()


def _builtin_golden() -> List[GoldenExample]:
    return [
        GoldenExample(
            "how do plants use sunlight",
            ["photosynthesis"],
            "Plants convert sunlight into energy through photosynthesis.",
            "bio",
        ),
        GoldenExample(
            "what is gravity",
            ["gravity"],
            "Gravity pulls objects toward the earth.",
            "physics",
        ),
        GoldenExample(
            "variables and data types in python",
            ["python"],
            "Python variables hold values of types like int, str, and list.",
            "cs",
        ),
    ]


def build_demo_index():
    """Small in-memory index used when sample-curriculum is unavailable."""
    try:
        from aoep_shared.rag import Document, RagIndex
    except Exception:  # noqa: BLE001
        return None
    return RagIndex(
        [
            Document.from_text(
                "photosynthesis",
                "Photosynthesis",
                "Plants convert sunlight into energy through photosynthesis in chloroplasts.",
            ),
            Document.from_text(
                "gravity",
                "Gravity",
                "Objects fall toward the earth due to gravity, a fundamental force.",
            ),
            Document.from_text(
                "python",
                "Python basics",
                "Python variables and data types include int, float, str, list, and dict.",
            ),
            Document.from_text(
                "fractions",
                "Fractions",
                "A fraction represents a part of a whole with a numerator and denominator.",
            ),
            Document.from_text(
                "supply_demand",
                "Supply and demand",
                "Market prices move when supply and demand for a good change.",
            ),
        ]
    )


def load_curriculum_index(curriculum_dir: Optional[str] = None):
    try:
        from aoep_shared.rag import RagIndex
    except Exception:  # noqa: BLE001
        return build_demo_index()
    roots = []
    if curriculum_dir:
        roots.append(Path(curriculum_dir))
    roots.append(Path("/workspace/sample-curriculum"))
    roots.append(Path(__file__).resolve().parents[4] / "sample-curriculum")
    for root in roots:
        if root.exists():
            idx = RagIndex.from_directory(root)
            if len(idx) > 0:
                return idx
    return build_demo_index()


def _token_overlap(a: str, b: str) -> float:
    ta = set((a or "").lower().split())
    tb = set((b or "").lower().split())
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / len(ta | tb)


def evaluate_index(
    index,
    examples: Sequence[GoldenExample],
    tuning: RagTuning,
    *,
    include_details: bool = False,
) -> EvalReport:
    if index is None or len(index) == 0:
        return EvalReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)

    try:
        from aoep_shared.groundedness import check_grounding
    except Exception:  # noqa: BLE001
        check_grounding = None

    hits = 0
    rr_sum = 0.0
    ground_sum = 0.0
    latency_sum = 0.0
    details: List[dict] = []
    n = 0

    for ex in examples:
        if not ex.query:
            continue
        n += 1
        t0 = time.perf_counter()
        retrieved = index.retrieve(ex.query, top_k=tuning.top_k)
        latency_sum += (time.perf_counter() - t0) * 1000.0
        retrieved = [r for r in retrieved if r.score >= tuning.min_score]

        rank = None
        for i, r in enumerate(retrieved, start=1):
            doc_id = r.document.doc_id
            # Match expected id as substring (curriculum paths) or exact.
            if any(
                exp == doc_id or exp in doc_id or doc_id.endswith(exp)
                for exp in ex.expected_doc_ids
            ):
                rank = i
                break
            # Soft match on title/text for demo docs.
            if any(
                exp.lower() in (r.document.title or "").lower()
                or exp.lower() in (r.document.text or "").lower()[:200]
                for exp in ex.expected_doc_ids
            ):
                rank = i
                break
        if rank is not None:
            hits += 1
            rr_sum += 1.0 / rank

        passages = [r.document.text for r in retrieved]
        context = "\n".join(passages)[: tuning.max_context_chars]
        answer = ex.expected_answer or (passages[0] if passages else "")
        if check_grounding is not None and answer and passages:
            report = check_grounding(
                answer,
                passages,
                support_threshold=tuning.groundedness_support,
                pass_threshold=tuning.groundedness_pass,
            )
            g = float(report.groundedness)
        else:
            g = _token_overlap(answer, context) if answer and context else 0.0
        ground_sum += g

        if include_details:
            details.append(
                {
                    "query": ex.query,
                    "rank": rank,
                    "groundedness": round(g, 4),
                    "top_docs": [r.document.doc_id for r in retrieved],
                }
            )

    if n == 0:
        return EvalReport(0, 0.0, 0.0, 0.0, 0.0, 0.0, 0)
    recall = hits / n
    mrr = rr_sum / n
    grounded = ground_sum / n
    latency = latency_sum / n
    # Blended quality: emphasize recall+MRR, keep grounding in the mix.
    quality = 0.45 * recall + 0.25 * mrr + 0.30 * grounded
    return EvalReport(
        n=n,
        recall_at_k=round(recall, 4),
        mrr=round(mrr, 4),
        groundedness=round(grounded, 4),
        latency_ms_avg=round(latency, 3),
        rag_quality=round(quality, 4),
        hits=hits,
        details=details if include_details else [],
    )


def sweep_presets(
    index,
    examples: Sequence[GoldenExample],
    preset_names: Optional[Iterable[str]] = None,
) -> List[dict[str, Any]]:
    from .rag_tuning import PRESETS

    names = list(preset_names or PRESETS.keys())
    out = []
    for name in names:
        tuning = RagTuning.preset(name)
        report = evaluate_index(index, examples, tuning)
        out.append({"preset": name, "tuning": tuning.to_dict(), "report": report.to_dict()})
    out.sort(key=lambda r: r["report"]["rag_quality"], reverse=True)
    return out
