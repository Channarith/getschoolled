"""Offline long-running trainer: improve course generation from labeled corpus."""

from __future__ import annotations

import json
import random
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field

from .corpus import default_corpus_root, default_data_dir
from .generate import CourseBuilder, _clean_block, _narration_for
from .page_bank import build_page_bank, load_page_bank, save_page_bank
from .quality_model import (
    LabeledPage,
    QualityModel,
    default_model_path,
    evaluate_model,
    fit_quality_model,
    load_model,
    model_to_public_dict,
    save_model,
)
from .training_run import run_training_pass
from .types import CategoryId, CourseSlide, StudioCourse


class GenerationPolicy(BaseModel):
    """Knobs the offline trainer mutates to improve course assembly."""

    min_body_chars: int = 40
    max_slides: int = 12
    better_bonus: float = 0.08
    good_bonus: float = 0.04
    reject_hard_filter: bool = True
    diversity_penalty: float = 0.02  # penalize many slides from same source
    model_weight: float = 1.0
    length_target_chars: int = 700
    length_tolerance: float = 0.35
    seed: int = 7


class EpochStats(BaseModel):
    epoch: int
    model_accuracy: float = 0.0
    model_separation: float = 0.0
    course_score: float = 0.0
    best_course_score: float = 0.0
    slides: int = 0
    elapsed_ms: int = 0
    policy: dict[str, Any] = Field(default_factory=dict)


class OfflineTrainerState(BaseModel):
    run_id: str
    corpus_root: str
    started_at_ms: int
    finished_at_ms: int = 0
    epoch: int = 0
    best_course_score: float = -1.0
    best_course_id: str = ""
    history: list[EpochStats] = Field(default_factory=list)
    policy: GenerationPolicy = Field(default_factory=GenerationPolicy)
    status: str = "running"  # running | completed | stopped | error
    message: str = ""
    offline: bool = True


@dataclass
class OfflineTrainer:
    """
    Lengthy offline trainer.

    Loop:
      1) (optional) corpus scan + extract once
      2) build/load page bank
      3) for each epoch: fit quality model → assemble scored course → mutate policy
      4) checkpoint model + policy + best course
    """

    data_dir: Path | None = None
    corpus_root: Path | None = None
    state: OfflineTrainerState | None = None
    model: QualityModel | None = None
    page_bank: list[LabeledPage] = field(default_factory=list)
    _stop: bool = False

    def __post_init__(self) -> None:
        self.data_dir = Path(self.data_dir or default_data_dir())
        self.corpus_root = Path(self.corpus_root or default_corpus_root())

    @property
    def run_dir(self) -> Path:
        assert self.state is not None
        return self.data_dir / "offline_training" / self.state.run_id

    def request_stop(self) -> None:
        self._stop = True

    def prepare(
        self,
        *,
        run_scan: bool = True,
        max_docs: int | None = None,
        resume_run_id: str | None = None,
        rebuild_bank: bool = False,
    ) -> OfflineTrainerState:
        self.data_dir.mkdir(parents=True, exist_ok=True)
        if resume_run_id:
            state_path = self.data_dir / "offline_training" / resume_run_id / "state.json"
            if not state_path.is_file():
                raise FileNotFoundError(f"no trainer state at {state_path}")
            self.state = OfflineTrainerState.model_validate_json(
                state_path.read_text(encoding="utf-8")
            )
            self.state.status = "running"
            self.state.message = "resumed"
            self.model = load_model(self.run_dir / "quality_model.json") or QualityModel()
            bank_path = self.run_dir / "page_bank.json"
            self.page_bank = load_page_bank(bank_path)
            if not self.page_bank:
                self.page_bank = build_page_bank(
                    data_dir=self.data_dir,
                    corpus_root=self.corpus_root,
                    max_docs=max_docs,
                )
                save_page_bank(self.page_bank, bank_path)
            return self.state

        if run_scan:
            run_training_pass(
                corpus_root=self.corpus_root,
                data_dir=self.data_dir,
                max_docs=max_docs,
                extract_text=True,
                seed_page_hints=True,
            )

        run_id = f"offline-{uuid.uuid4().hex[:10]}"
        self.state = OfflineTrainerState(
            run_id=run_id,
            corpus_root=str(self.corpus_root),
            started_at_ms=int(time.time() * 1000),
            policy=GenerationPolicy(),
            message="prepared",
        )
        self.run_dir.mkdir(parents=True, exist_ok=True)
        bank_path = self.run_dir / "page_bank.json"
        if rebuild_bank or not bank_path.is_file():
            self.page_bank = build_page_bank(
                data_dir=self.data_dir,
                corpus_root=self.corpus_root,
                max_docs=max_docs,
            )
            save_page_bank(self.page_bank, bank_path)
        else:
            self.page_bank = load_page_bank(bank_path)
        self.model = load_model(default_model_path(self.data_dir)) or QualityModel()
        self._checkpoint()
        return self.state

    def run(
        self,
        *,
        epochs: int | None = None,
        hours: float | None = None,
        target_score: float | None = None,
        fit_passes: int = 2,
        checkpoint_every: int = 1,
        seed: int | None = None,
    ) -> OfflineTrainerState:
        if self.state is None or not self.page_bank:
            self.prepare(run_scan=False)
        assert self.state is not None
        assert self.model is not None

        rng = random.Random(seed if seed is not None else self.state.policy.seed)
        deadline = None
        if hours is not None and hours > 0:
            deadline = time.time() + hours * 3600.0
        max_epochs = epochs if epochs is not None else (10_000_000 if deadline else 50)

        self.state.status = "running"
        self._stop = False
        while self.state.epoch < max_epochs:
            if self._stop:
                self.state.status = "stopped"
                self.state.message = "stop requested"
                break
            if deadline is not None and time.time() >= deadline:
                self.state.status = "completed"
                self.state.message = "time budget reached"
                break

            t0 = time.time()
            self.state.epoch += 1
            # Hold out ~20% pages for eval each epoch (deterministic shuffle by epoch).
            pages = list(self.page_bank)
            rng.shuffle(pages)
            split = max(1, int(len(pages) * 0.8)) if len(pages) > 5 else len(pages)
            train_pages = pages[:split]
            eval_pages = pages[split:] or pages

            self.model = fit_quality_model(
                train_pages,
                model=self.model,
                passes=fit_passes,
                learning_rate=0.06 + 0.02 * rng.random(),
            )
            metrics = evaluate_model(self.model, eval_pages)
            course, course_score = self._assemble_and_score(rng)
            if course_score > self.state.best_course_score and course is not None:
                self.state.best_course_score = course_score
                self.state.best_course_id = course.course_id
                CourseBuilder(data_dir=self.data_dir).save_course(course)
                (self.run_dir / "best_course.json").write_text(
                    course.model_dump_json(indent=2), encoding="utf-8"
                )

            stats = EpochStats(
                epoch=self.state.epoch,
                model_accuracy=float(metrics.get("accuracy", 0.0)),
                model_separation=float(metrics.get("separation", 0.0)),
                course_score=course_score,
                best_course_score=self.state.best_course_score,
                slides=len(course.slides) if course else 0,
                elapsed_ms=int((time.time() - t0) * 1000),
                policy=self.state.policy.model_dump(mode="json"),
            )
            self.state.history.append(stats)
            # Keep history bounded for multi-hour runs.
            if len(self.state.history) > 5000:
                self.state.history = self.state.history[-2500:]

            self._mutate_policy(rng, improved=course_score >= self.state.best_course_score - 1e-9)

            if target_score is not None and self.state.best_course_score >= target_score:
                self.state.status = "completed"
                self.state.message = f"hit target_score={target_score}"
                self._checkpoint()
                break

            if checkpoint_every > 0 and self.state.epoch % checkpoint_every == 0:
                self._checkpoint()

        if self.state.status == "running":
            self.state.status = "completed"
            self.state.message = self.state.message or "epochs finished"
        self.state.finished_at_ms = int(time.time() * 1000)
        self._checkpoint()
        # Promote best model to shared path for CourseBuilder.
        save_model(self.model, default_model_path(self.data_dir))
        save_model(self.model, self.run_dir / "quality_model.json")
        return self.state

    def _assemble_and_score(
        self, rng: random.Random
    ) -> tuple[StudioCourse | None, float]:
        assert self.state is not None and self.model is not None
        policy = self.state.policy
        candidates: list[tuple[float, LabeledPage]] = []
        source_counts: dict[str, int] = {}
        for page in self.page_bank:
            if policy.reject_hard_filter and page.label < 0:
                continue
            if len(page.body) < policy.min_body_chars:
                continue
            # Only assemble from positive / unlabeled (moderate) pages.
            if page.label < 0:
                continue
            base = self.model.score_page(page) * policy.model_weight
            if page.quality_name == "better":
                base += policy.better_bonus
            elif page.quality_name == "good":
                base += policy.good_bonus
            # Prefer mid-length teachable pages.
            n = len(page.body)
            target = policy.length_target_chars
            tol = max(policy.length_tolerance, 0.05)
            length_score = 1.0 - min(1.0, abs(n - target) / (target * tol + 1.0))
            base += 0.05 * length_score
            base -= policy.diversity_penalty * source_counts.get(page.source_id, 0)
            # Small noise for exploration across long runs.
            base += (rng.random() - 0.5) * 0.01
            candidates.append((base, page))

        candidates.sort(key=lambda x: x[0], reverse=True)
        slides: list[CourseSlide] = []
        used_sources: list[str] = []
        for score, page in candidates:
            if len(slides) >= policy.max_slides:
                break
            title = (page.title or f"Point {len(slides) + 1}")[:140]
            body = _clean_block(page.body)
            slides.append(
                CourseSlide(
                    index=len(slides),
                    title=title,
                    body=body,
                    narration=_narration_for(title, body),
                    source_page=page.page_index,
                    keep=True,
                    tags=[page.category, page.quality_name, f"q={score:.3f}"],
                )
            )
            used_sources.append(page.source_id)
            source_counts[page.source_id] = source_counts.get(page.source_id, 0) + 1

        if not slides:
            return None, 0.0

        cat = CategoryId.OTHER
        if slides[0].tags:
            try:
                cat = CategoryId(slides[0].tags[0])
            except Exception:  # noqa: BLE001
                cat = CategoryId.OTHER
        course = StudioCourse(
            course_id=f"course-{uuid.uuid4().hex[:10]}",
            title=f"{cat.value.replace('_', ' ').title()} — offline trained",
            category=cat,
            language="en",
            source_ids=sorted(set(used_sources)),
            slides=slides,
            profile_adaptations={
                "policy": policy.model_dump(mode="json"),
                "trainer_run": self.state.run_id,
                "epoch": self.state.epoch,
            },
            created_at_ms=int(time.time() * 1000),
            status="ready",
        )
        return course, self._score_course(course)

    def _score_course(self, course: StudioCourse) -> float:
        """Heuristic course quality using the current model + structure priors."""
        assert self.model is not None
        if not course.slides:
            return 0.0
        scores = [self.model.score_text(s.title, s.body) for s in course.slides]
        mean = sum(scores) / len(scores)
        # Reward coverage / variety of sources and punish ultra-short decks.
        source_bonus = min(0.1, 0.01 * len(set(course.source_ids)))
        length_bonus = 0.05 if 8 <= len(course.slides) <= 24 else 0.0
        # Penalize if any slide looks bad under model.
        weak = sum(1 for s in scores if s < 0.45) / len(scores)
        return max(0.0, min(1.0, mean + source_bonus + length_bonus - 0.2 * weak))

    def _mutate_policy(self, rng: random.Random, *, improved: bool) -> None:
        assert self.state is not None
        p = self.state.policy
        # If improved, small refine; else explore more.
        scale = 0.5 if improved else 1.0
        p.min_body_chars = int(
            max(20, min(200, p.min_body_chars + rng.randint(-5, 5) * scale))
        )
        p.max_slides = int(max(8, min(30, p.max_slides + rng.choice([-1, 0, 1]) * scale)))
        p.better_bonus = float(max(0.0, min(0.3, p.better_bonus + (rng.random() - 0.5) * 0.02 * scale)))
        p.good_bonus = float(max(0.0, min(0.2, p.good_bonus + (rng.random() - 0.5) * 0.015 * scale)))
        p.diversity_penalty = float(
            max(0.0, min(0.15, p.diversity_penalty + (rng.random() - 0.5) * 0.01 * scale))
        )
        p.length_target_chars = int(
            max(300, min(1600, p.length_target_chars + int((rng.random() - 0.5) * 80 * scale)))
        )
        p.model_weight = float(max(0.5, min(2.0, p.model_weight + (rng.random() - 0.5) * 0.05 * scale)))
        self.state.policy = p

    def _checkpoint(self) -> None:
        assert self.state is not None and self.model is not None
        self.run_dir.mkdir(parents=True, exist_ok=True)
        save_model(self.model, self.run_dir / "quality_model.json")
        save_model(self.model, default_model_path(self.data_dir))
        (self.run_dir / "state.json").write_text(
            self.state.model_dump_json(indent=2), encoding="utf-8"
        )
        (self.run_dir / "policy.json").write_text(
            self.state.policy.model_dump_json(indent=2), encoding="utf-8"
        )
        latest = self.data_dir / "offline_training" / "latest.json"
        latest.parent.mkdir(parents=True, exist_ok=True)
        latest.write_text(
            json.dumps(
                {
                    "run_id": self.state.run_id,
                    "epoch": self.state.epoch,
                    "status": self.state.status,
                    "best_course_score": self.state.best_course_score,
                    "best_course_id": self.state.best_course_id,
                    "model": model_to_public_dict(self.model),
                    "message": self.state.message,
                },
                indent=2,
            ),
            encoding="utf-8",
        )


def run_offline_training(
    *,
    data_dir: Path | None = None,
    corpus_root: Path | None = None,
    epochs: int | None = 25,
    hours: float | None = None,
    target_score: float | None = None,
    max_docs: int | None = None,
    run_scan: bool = True,
    resume_run_id: str | None = None,
    fit_passes: int = 2,
) -> OfflineTrainerState:
    trainer = OfflineTrainer(data_dir=data_dir, corpus_root=corpus_root)
    trainer.prepare(
        run_scan=run_scan and not resume_run_id,
        max_docs=max_docs,
        resume_run_id=resume_run_id,
    )
    return trainer.run(
        epochs=epochs,
        hours=hours,
        target_score=target_score,
        fit_passes=fit_passes,
    )
