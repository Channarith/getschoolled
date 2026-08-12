from __future__ import annotations

from pathlib import Path

from theodore_course_studio.offline_trainer import OfflineTrainer, GenerationPolicy
from theodore_course_studio.quality_model import (
    LabeledPage,
    QualityModel,
    evaluate_model,
    fit_quality_model,
)


def _synth_bank() -> list[LabeledPage]:
    good_bodies = [
        "Identify active listening steps. Practice reflecting feelings before advising. Demonstrate empathy in difficult conversations.",
        "Explain how clear feedback improves team trust. Apply the situation-behavior-impact model. Avoid vague criticism.",
        "Leaders set vision and invite dissent. Learn to coach peers with open questions. Practice weekly 1:1 check-ins.",
        "Harassment policy requires reporting channels. Identify inappropriate conduct early. Explain bystander intervention options.",
        "Summarize negotiation interests versus positions. Demonstrate collaborative problem solving. Apply BATNA thinking carefully.",
        "Teach presentation structure: hook, points, ask. Practice concise slides. Avoid reading dense paragraphs aloud.",
        "Safety briefings name hazards and controls. Explain stop-work authority. Practice escalation when unsure.",
        "Mentorship goals should be measurable. Identify growth areas jointly. Apply monthly progress reviews.",
    ]
    bad_bodies = [
        "asdf qwer zxcv fluff fluff fluff ignore this junk page.",
        "Buy now!!! Click here spam offer unrelated to learning outcomes.",
        "lorem ipsum dolor sit amet consectetur adipiscing elit sed do.",
        "Random doodle page with no teaching value whatsoever blah blah.",
        "Copyright watermark only. No actionable learning point present.",
        "Broken OCR text: ^^^ ### $$$ meaningless glyphs for rejection.",
    ]
    bank: list[LabeledPage] = []
    for i, body in enumerate(good_bodies):
        bank.append(
            LabeledPage(
                source_id=f"good-{i}",
                page_index=0,
                title=f"Learning point {i+1}",
                body=body,
                label=1.0,
                quality_name="good" if i % 2 == 0 else "better",
                category="leadership",
            )
        )
    for i, body in enumerate(bad_bodies):
        bank.append(
            LabeledPage(
                source_id=f"bad-{i}",
                page_index=0,
                title=f"Reject {i+1}",
                body=body,
                label=-1.0,
                quality_name="bad",
                category="leadership",
            )
        )
    return bank


def test_quality_model_separates_good_and_bad():
    bank = _synth_bank()
    model = fit_quality_model(bank, passes=6, learning_rate=0.12)
    metrics = evaluate_model(model, bank)
    assert metrics["n"] >= 10
    assert metrics["accuracy"] >= 0.8
    assert metrics["separation"] > 0.1


def test_offline_trainer_improves_over_epochs(tmp_path: Path):
    data_dir = tmp_path / "data"
    trainer = OfflineTrainer(data_dir=data_dir, corpus_root=tmp_path / "empty_corpus")
    trainer.state = None
    # Manual prepare without scan — inject synthetic bank.
    from theodore_course_studio.offline_trainer import OfflineTrainerState
    import time

    run_id = "offline-test"
    trainer.state = OfflineTrainerState(
        run_id=run_id,
        corpus_root=str(tmp_path),
        started_at_ms=int(time.time() * 1000),
        policy=GenerationPolicy(max_slides=8, seed=3),
    )
    (data_dir / "offline_training" / run_id).mkdir(parents=True)
    trainer.page_bank = _synth_bank()
    trainer.model = QualityModel()
    state = trainer.run(epochs=12, fit_passes=3, checkpoint_every=3)
    assert state.epoch == 12
    assert state.status == "completed"
    assert state.best_course_score > 0.4
    assert (data_dir / "models" / "quality_model.json").is_file()
    assert (data_dir / "offline_training" / run_id / "state.json").is_file()
    # Later epochs should not collapse accuracy
    assert state.history[-1].model_accuracy >= 0.7
