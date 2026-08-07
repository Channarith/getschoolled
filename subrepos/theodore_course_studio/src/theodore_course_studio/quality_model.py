"""Offline discriminative quality model: Good/Better vs Bad/reject pages."""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .page_features import page_features, token_counts


class LabeledPage(BaseModel):
    """One training example derived from the labeled corpus (or synthetic tests)."""

    source_id: str
    page_index: int = 0
    title: str = ""
    body: str = ""
    # +1 incorporate/good, -1 reject/bad, 0 moderate/unlabeled
    label: float = 0.0
    quality_name: str = "unlabeled"
    category: str = "other"


class QualityModel(BaseModel):
    """Fully offline linear + token contrast model. No LLM / no network."""

    version: int = 1
    bias: float = 0.0
    feature_weights: dict[str, float] = Field(default_factory=dict)
    token_weights: dict[str, float] = Field(default_factory=dict)
    epochs_trained: int = 0
    examples_seen: int = 0
    good_pages: int = 0
    bad_pages: int = 0
    updated_at_ms: int = 0
    notes: list[str] = Field(default_factory=list)

    def score_text(self, title: str, body: str) -> float:
        """Return roughly 0..1 quality estimate (sigmoid of raw score)."""
        return _sigmoid(self.raw_score(title, body))

    def raw_score(self, title: str, body: str) -> float:
        feats = page_features(title, body)
        total = self.bias
        for k, v in feats.items():
            total += self.feature_weights.get(k, 0.0) * v
        for tok, cnt in token_counts(title, body).items():
            total += self.token_weights.get(tok, 0.0) * math.log1p(cnt)
        return total

    def score_page(self, page: LabeledPage) -> float:
        return self.score_text(page.title, page.body)


def _sigmoid(x: float) -> float:
    # Stable sigmoid.
    if x >= 0:
        z = math.exp(-x)
        return 1.0 / (1.0 + z)
    z = math.exp(x)
    return z / (1.0 + z)


def fit_quality_model(
    pages: list[LabeledPage],
    *,
    model: QualityModel | None = None,
    learning_rate: float = 0.08,
    l2: float = 0.001,
    passes: int = 3,
    max_tokens: int = 4000,
) -> QualityModel:
    """
    Online logistic-style updates on labeled pages.

    label > 0 => positive (Good/Better/keep)
    label < 0 => negative (Bad/reject)
    label == 0 skipped for gradient (still counted in notes)
    """
    model = model or QualityModel()
    labeled = [p for p in pages if p.label != 0.0]
    if not labeled:
        model.notes.append("fit skipped — no +/- labeled pages")
        return model

    for _ in range(max(1, passes)):
        for page in labeled:
            y = 1.0 if page.label > 0 else 0.0
            pred = model.score_text(page.title, page.body)
            err = y - pred
            feats = page_features(page.title, page.body)
            # L2 toward zero + gradient.
            for k, v in feats.items():
                w = model.feature_weights.get(k, 0.0)
                model.feature_weights[k] = w + learning_rate * (err * v - l2 * w)
            for tok, cnt in token_counts(page.title, page.body).items():
                w = model.token_weights.get(tok, 0.0)
                model.token_weights[tok] = w + learning_rate * (
                    err * math.log1p(cnt) - l2 * w
                )
            model.bias += learning_rate * (err - l2 * model.bias)
            model.examples_seen += 1
            if y >= 0.5:
                model.good_pages += 1
            else:
                model.bad_pages += 1

    # Cap token table size for long runs.
    if len(model.token_weights) > max_tokens:
        top = sorted(model.token_weights.items(), key=lambda kv: abs(kv[1]), reverse=True)[
            :max_tokens
        ]
        model.token_weights = dict(top)

    model.epochs_trained += passes
    model.updated_at_ms = int(time.time() * 1000)
    return model


def evaluate_model(model: QualityModel, pages: list[LabeledPage]) -> dict[str, float]:
    labeled = [p for p in pages if p.label != 0.0]
    if not labeled:
        return {"accuracy": 0.0, "n": 0.0, "mean_good": 0.0, "mean_bad": 0.0}
    correct = 0
    good_scores: list[float] = []
    bad_scores: list[float] = []
    for page in labeled:
        s = model.score_page(page)
        pred_pos = s >= 0.5
        truth_pos = page.label > 0
        if pred_pos == truth_pos:
            correct += 1
        if truth_pos:
            good_scores.append(s)
        else:
            bad_scores.append(s)
    return {
        "accuracy": correct / len(labeled),
        "n": float(len(labeled)),
        "mean_good": sum(good_scores) / max(len(good_scores), 1),
        "mean_bad": sum(bad_scores) / max(len(bad_scores), 1),
        "separation": (
            (sum(good_scores) / max(len(good_scores), 1))
            - (sum(bad_scores) / max(len(bad_scores), 1))
        ),
    }


def save_model(model: QualityModel, path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(model.model_dump_json(indent=2), encoding="utf-8")
    return path


def load_model(path: Path) -> QualityModel | None:
    if not path.is_file():
        return None
    return QualityModel.model_validate_json(path.read_text(encoding="utf-8"))


def default_model_path(data_dir: Path) -> Path:
    return data_dir / "models" / "quality_model.json"


def model_to_public_dict(model: QualityModel) -> dict[str, Any]:
    return {
        "epochs_trained": model.epochs_trained,
        "examples_seen": model.examples_seen,
        "good_pages": model.good_pages,
        "bad_pages": model.bad_pages,
        "token_count": len(model.token_weights),
        "feature_count": len(model.feature_weights),
        "updated_at_ms": model.updated_at_ms,
    }
