"""Build a labeled page bank from corpus extracts (offline, resumable)."""

from __future__ import annotations

import json
from pathlib import Path

from .corpus import default_data_dir, load_corpus_index, scan_corpus, write_corpus_index
from .extract import extract_document
from .quality_model import LabeledPage
from .review_store import ReviewStore
from .types import QualityLabel


def _label_for(quality: QualityLabel, marked_reject: bool) -> float:
    if marked_reject or quality is QualityLabel.BAD:
        return -1.0
    if quality in {QualityLabel.GOOD, QualityLabel.BETTER}:
        return 1.0
    if quality is QualityLabel.MODERATE:
        return 0.0
    return 0.0


def build_page_bank(
    *,
    data_dir: Path | None = None,
    corpus_root: Path | None = None,
    max_docs: int | None = None,
    prefer_cached_extracts: bool = True,
) -> list[LabeledPage]:
    """
    Assemble labeled pages for offline training.

    Prefers previously written extract JSON under data/training_runs/*/extracts
    so long runs can continue without re-reading huge PDFs every epoch.
    Falls back to live extract_document when needed.
    """
    data_dir = data_dir or default_data_dir()
    reviews = ReviewStore(data_dir=data_dir)
    docs = load_corpus_index(data_dir)
    if not docs:
        docs = scan_corpus(corpus_root)
        if docs:
            write_corpus_index(docs, data_dir=data_dir)
    if max_docs is not None:
        docs = docs[: max(0, max_docs)]

    extract_index = _index_cached_extracts(data_dir) if prefer_cached_extracts else {}
    bank: list[LabeledPage] = []
    for doc in docs:
        pages_payload = None
        cached = extract_index.get(doc.source_id)
        if cached is not None:
            pages_payload = cached
        else:
            extracted = extract_document(doc.path)
            pages_payload = [
                {
                    "index": p.index,
                    "title": p.title,
                    "text": p.text,
                    "marked_reject_hint": p.marked_reject_hint,
                }
                for p in extracted.pages
            ]
        for page in pages_payload:
            idx = int(page.get("index", 0))
            review = reviews.get_page(doc.source_id, idx)
            marked = bool(
                (review and review.marked_reject)
                or (review is None and page.get("marked_reject_hint"))
            )
            body = (page.get("text") or "")[:4000]
            title = (page.get("title") or "")[:200]
            if len(body.strip()) < 20 and not title.strip():
                continue
            bank.append(
                LabeledPage(
                    source_id=doc.source_id,
                    page_index=idx,
                    title=title,
                    body=body,
                    label=_label_for(doc.quality_label, marked),
                    quality_name=doc.quality_label.value,
                    category=doc.category.value,
                )
            )
    return bank


def save_page_bank(pages: list[LabeledPage], path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "count": len(pages),
        "pages": [p.model_dump(mode="json") for p in pages],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return path


def load_page_bank(path: Path) -> list[LabeledPage]:
    if not path.is_file():
        return []
    raw = json.loads(path.read_text(encoding="utf-8"))
    return [LabeledPage.model_validate(row) for row in raw.get("pages", [])]


def _index_cached_extracts(data_dir: Path) -> dict[str, list[dict]]:
    """Newest extract wins per source_id."""
    root = data_dir / "training_runs"
    if not root.is_dir():
        return {}
    found: dict[str, tuple[float, list[dict]]] = {}
    for path in root.glob("*/extracts/*.json"):
        try:
            raw = json.loads(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            continue
        sid = raw.get("source_id") or path.stem
        pages = raw.get("pages") or []
        mtime = path.stat().st_mtime
        prev = found.get(sid)
        if prev is None or mtime >= prev[0]:
            found[sid] = (mtime, pages)
    return {sid: pages for sid, (_m, pages) in found.items()}
