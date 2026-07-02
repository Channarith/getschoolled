"""RAG + taxonomy auto-tagging for harvested courses."""

from aoep_shared.harvest import ExtractedDoc, extract_text, infer_harvest_metadata, merge_tags


def test_infer_ml_book_metadata():
    text = (
        "Patterns, Predictions, and Actions\n\n"
        "Introduction to machine learning and deep learning algorithms.\n\n"
        "Supervised learning\n"
        "Training neural networks on labeled data for prediction tasks.\n\n"
        "Optimization\n"
        "Gradient descent and stochastic methods for model training.\n"
    )
    doc = extract_text(text, default_title="Patterns, Predictions, and Actions")
    meta = infer_harvest_metadata(doc)
    assert meta.subject in ("ai", "data-science", "programming", "general")
    assert meta.tags.access_tier in ("pro", "premium", "enterprise")
    assert meta.tags.price_usd >= 0.0
    assert meta.tags.career_path in (None, "data-scientist", "software-engineer", "engineer")
    assert meta.rationale


def test_infer_algebra_core_fundamental():
    text = (
        "Algebra Fundamentals\n\n"
        "Introduction\n"
        "Variables and expressions are the building blocks of algebra.\n\n"
        "Linear equations\n"
        "Solve for x in basic one-variable equations.\n"
    )
    doc = extract_text(text, default_title="Algebra Fundamentals")
    meta = infer_harvest_metadata(doc)
    assert meta.subject in ("mathematics", "general")
    assert meta.tags.core_fundamental or "algebra" in meta.tags.labels


def test_merge_tags_manual_override():
    doc = extract_text("Machine learning basics", default_title="ML")
    inferred = infer_harvest_metadata(doc)
    subject, tags = merge_tags(
        inferred,
        subject="custom-subject",
        access_tier="free",
        price_usd=0.0,
        career_path="nurse",
        core_fundamental=True,
        extra_labels=["manual"],
    )
    assert subject == "custom-subject"
    assert tags.access_tier == "free"
    assert tags.price_usd == 0.0
    assert tags.career_path == "nurse"
    assert tags.core_fundamental is True
    assert "manual" in tags.labels
