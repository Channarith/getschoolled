"""Offline tests for dictionary corpus, curriculum, audio cleanup, feedback."""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from aoep_shared.dictionary_audio import (
    clean_audio_file,
    estimate_qc,
    synthesize_tone_wav,
    write_wav_mono,
)
from aoep_shared.dictionary_corpus import (
    DictionaryEntry,
    approved_entries,
    english_inflections,
    ensure_layout,
    ingest_from_baseline_dir,
    merge_entries,
    route_entries,
    save_staging,
    should_queue_for_review,
    to_vocabulary_pack_record,
)
from aoep_shared.dictionary_curriculum import (
    build_curriculum,
    build_sentence_for_entry,
    next_read_aloud,
    score_read_aloud,
)
from aoep_shared.dictionary_feedback import DictionaryFeedbackStore

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "dictionary"


@pytest.fixture()
def dict_root(tmp_path, monkeypatch):
    root = tmp_path / "dictionary"
    monkeypatch.setenv("AOEP_DICTIONARY_DIR", str(root))
    ensure_layout(root)
    # Copy fixtures into baselines
    b = root / "baselines"
    b.mkdir(parents=True, exist_ok=True)
    for p in FIXTURES.iterdir():
        if p.is_file():
            (b / p.name).write_bytes(p.read_bytes())
    return root


def test_english_inflections_noun_verb():
    noun = english_inflections("school", "noun")
    assert noun["plural"] == "schools"
    verb = english_inflections("learn", "verb")
    assert verb["gerund"] == "learning"
    assert verb["past"] == "learned"
    irr = english_inflections("teach", "verb")
    assert irr["past"] == "taught"


def test_ingest_merge_and_route(dict_root):
    entries = ingest_from_baseline_dir(dict_root / "baselines")
    assert any(e.lemma == "school" for e in entries)
    school = next(e for e in entries if e.lemma == "school" and e.language == "en")
    assert "wordfreq" in school.sources or "khmer_pack" in school.sources
    assert school.ipa or school.gloss_en
    assert school.inflections.get("plural") == "schools"

    auto, queued = route_entries(entries)
    assert auto or queued
    # Idioms / slang / missing roman should queue
    assert any(e.kind in ("slang", "idiom") or "roman" in e.notes for e in queued)


def test_should_queue_figurative_and_mwe():
    e = DictionaryEntry(
        id="x", lemma="kick the bucket", language="en", kind="idiom", gloss_en="to die"
    )
    ok, reason = should_queue_for_review(e)
    assert ok and "kind" in reason


def test_export_vocabulary_record():
    e = DictionaryEntry(
        id="en-school",
        lemma="school",
        language="en",
        gloss_en="a place for teaching",
        translations={"km": {"target": "សាលា", "roman": "sala"}},
        review_status="auto",
    )
    km = to_vocabulary_pack_record(e, target_lang="km")
    assert km["target"] == "សាលា"
    assert km["language"] == "km"
    en = to_vocabulary_pack_record(e, target_lang="en")
    assert en["target"] == "school"


def test_feedback_apply(dict_root):
    e = DictionaryEntry(
        id="en-school-test",
        lemma="school",
        language="en",
        gloss_en="old",
        review_status="queued",
        inflections={"plural": "schools"},
    )
    save_staging([e], dict_root, "en")
    store = DictionaryFeedbackStore(dict_root / "review" / "feedback.json")
    store.record(
        entry_id="en-school-test",
        lemma="school",
        action="correct",
        gloss_en="a place for teaching and learning",
        inflections={"plural": "schools"},
    )
    n = store.apply_to_staging("en", dict_root)
    assert n >= 1
    from aoep_shared.dictionary_corpus import load_staging

    rows = load_staging(dict_root, "en")
    assert rows[0].review_status == "approved"
    assert "teaching" in rows[0].gloss_en


def test_curriculum_and_read_aloud(dict_root):
    entries = ingest_from_baseline_dir(dict_root / "baselines")
    merged = merge_entries(entries)
    auto, queued = route_entries(merged)
    save_staging(auto + queued, dict_root, "en")
    # Force some approved
    approved = []
    for e in auto + queued:
        if e.language != "en":
            continue
        e.review_status = "approved"
        approved.append(e)
    save_staging(approved, dict_root, "en")

    sentences = build_curriculum(approved, language="en", per_difficulty=5, seed=1)
    assert sentences
    assert any(s.source == "tatoeba" for s in sentences) or any(
        "school" in s.text.lower() for s in sentences
    )

    from aoep_shared.dictionary_curriculum import save_sentences

    save_sentences(sentences, dict_root, "en")
    prompt = next_read_aloud(language="en", learner_id="tester", root=dict_root, seed=2)
    assert prompt["sentence"]
    forms = [t["form"] for t in prompt["targets"]]
    result = score_read_aloud(
        sentence=prompt["sentence"],
        heard=prompt["sentence"],
        target_forms=forms,
        learner_id="tester",
        language="en",
        root=dict_root,
    )
    assert result["score"] >= 60
    assert result["stars"] >= 2

    # Missed focus word lowers score
    bad = score_read_aloud(
        sentence="Please say school clearly.",
        heard="Please say something clearly.",
        target_forms=["school"],
        learner_id="tester",
        language="en",
        root=dict_root,
    )
    assert "school" in bad["missed_forms"]


def test_sentence_prefers_tatoeba():
    e = DictionaryEntry(
        id="en-school",
        lemma="school",
        language="en",
        rarity=0.1,
        examples=[{"text": "She walked to school.", "source": "tatoeba", "target_forms": ["school"]}],
        review_status="auto",
    )
    s = build_sentence_for_entry(e, seed=0)
    assert s.source == "tatoeba"
    assert "school" in s.text.lower()


def test_audio_clean_qc(dict_root, tmp_path):
    raw = tmp_path / "tone.wav"
    synthesize_tone_wav(raw, seconds=0.5, hz=440.0, amplitude=0.4)
    crisp = tmp_path / "tone.crisp.wav"
    result = clean_audio_file(raw, crisp)
    assert result.ok
    assert result.crisp_path and result.crisp_path.is_file()
    assert result.snr_db is not None and result.snr_db >= 6

    # Near-silent fails QC after clean attempt
    silent = tmp_path / "silent.wav"
    write_wav_mono(silent, b"\x00\x00" * 1000)
    pcm = b"\x00\x00" * 1000
    ok, reason, _, _ = estimate_qc(pcm, 24000)
    assert not ok and reason in ("near_silent", "too_short", "low_snr")


def test_approved_filter():
    rows = [
        DictionaryEntry(id="a", lemma="a", review_status="auto"),
        DictionaryEntry(id="b", lemma="b", review_status="rejected"),
        DictionaryEntry(id="c", lemma="c", review_status="approved"),
    ]
    assert {e.id for e in approved_entries(rows)} == {"a", "c"}
