"""Training run: walk every labeled pptx/pdf, classify, extract, queue rejects."""

from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from .corpus import default_corpus_root, default_data_dir, scan_corpus, write_corpus_index
from .extract import extract_document
from .labels import should_incorporate, should_review_queue
from .review_store import ReviewStore
from .types import QualityLabel, TrainingRunReport


def run_training_pass(
    *,
    corpus_root: Path | None = None,
    data_dir: Path | None = None,
    max_docs: int | None = None,
    extract_text: bool = True,
    seed_page_hints: bool = True,
) -> TrainingRunReport:
    root = (corpus_root or default_corpus_root()).resolve()
    data_dir = data_dir or default_data_dir()
    started = int(time.time() * 1000)
    run_id = f"train-{uuid.uuid4().hex[:10]}"
    docs = scan_corpus(root)
    write_corpus_index(docs, data_dir=data_dir)
    if max_docs is not None:
        docs = docs[: max(0, max_docs)]

    report = TrainingRunReport(
        run_id=run_id,
        corpus_root=str(root),
        started_at_ms=started,
        documents_scanned=len(docs),
    )
    reviews = ReviewStore(data_dir=data_dir)
    extracts_dir = data_dir / "training_runs" / run_id / "extracts"
    extracts_dir.mkdir(parents=True, exist_ok=True)

    for doc in docs:
        report.by_category[doc.category.value] = report.by_category.get(doc.category.value, 0) + 1
        report.by_quality[doc.quality_label.value] = (
            report.by_quality.get(doc.quality_label.value, 0) + 1
        )
        if doc.quality_label is QualityLabel.BAD:
            report.reject_ids.append(doc.source_id)
        elif should_incorporate(doc.quality_label):
            report.incorporate_ids.append(doc.source_id)
        if should_review_queue(doc.quality_label):
            report.review_queue_ids.append(doc.source_id)

        if not extract_text:
            continue
        extracted = extract_document(doc.path)
        if extracted.error:
            report.errors.append(f"{doc.source_id}: {extracted.error}")
        out = {
            "source_id": doc.source_id,
            "path": doc.path,
            "quality_label": doc.quality_label.value,
            "incorporate": doc.incorporate,
            "extractor": extracted.extractor,
            "error": extracted.error,
            "pages": [
                {
                    "index": p.index,
                    "title": p.title,
                    "text": p.text[:4000],
                    "marked_reject_hint": p.marked_reject_hint,
                    "char_count": len(p.text),
                }
                for p in extracted.pages
            ],
        }
        (extracts_dir / f"{doc.source_id}.json").write_text(
            json.dumps(out, indent=2), encoding="utf-8"
        )
        if seed_page_hints:
            for page in extracted.pages:
                if page.marked_reject_hint and reviews.get_page(doc.source_id, page.index) is None:
                    reviews.set_page_verdict(
                        source_id=doc.source_id,
                        page_index=page.index,
                        marked_reject=True,
                        comment="auto-seeded from annotation/drawing hint (confirm in UI)",
                    )

    report.finished_at_ms = int(time.time() * 1000)
    report.notes.append(
        "Filename policy: Good/Better → incorporate; Bad → reject; "
        "Moderate/Unlabeled → review queue."
    )
    report.notes.append(
        "Page rejects: circle+line marks should be confirmed in the studio UI; "
        "auto hints only seed when extractors see annotation/drawing density."
    )
    out_path = data_dir / "training_runs" / run_id / "report.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    latest = data_dir / "training_runs" / "latest.json"
    latest.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    return report
