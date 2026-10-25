"""Translation pipeline v2 with a fake NLLB engine (no GPU, no download)."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from aoep_shared import nllb
from aoep_shared import translation_v2 as v2
from aoep_shared.course_translation_library import load_translation, translation_path, save_translation

KHMER = {chr(97 + i): chr(0x1780 + i) for i in range(26)}
_KEEP = re.compile(r"(\[\[\s*\d+\s*\]\]|\d+(?:[.,]\d+)?)")
LOOP = "កក កក កក កក កក កក កក កក"


def fake_text(text: str, lang: str, *, keep_placeholders: bool = True) -> str:
    out = []
    for tok in _KEEP.split(text):
        if _KEEP.fullmatch(tok or ""):
            if keep_placeholders or not tok.startswith("[["):
                out.append(tok)
            continue
        if lang == "km":
            out.append("".join(KHMER.get(c.lower(), c) for c in tok))
        else:  # a Latin language: shift every letter so it never equals the English
            out.append("".join(chr((ord(c) - 97 + 1) % 26 + 97) if c.islower() else c for c in tok))
    return "".join(out)


class FakeEngine:
    name = "fake"
    model = "fake-1"

    def __init__(self, *, loop_when=None, drop_placeholders_when=None):
        self.calls = []
        self.loop_when = loop_when or (lambda text, gen: False)
        self.drop = drop_placeholders_when or (lambda gen: False)

    def translate(self, texts, source, target, gen):
        self.calls.append((list(texts), dict(gen)))
        out = []
        for t in texts:
            if self.loop_when(t, gen):
                out.append(LOOP)
            else:
                out.append(fake_text(t, target, keep_placeholders=not self.drop(gen)))
        return out


def course(extra: str = "", cid: str = "audio-demo") -> v2.CourseSource:
    return v2.CourseSource(
        cid,
        "Learning Fractions",
        "Science & Nature",
        [
            {"heading": "Meet Fractions", "text": f"Welcome to the course. Today we will learn about fractions and how to compare them. {extra}".strip()},
            {"heading": "Counting Steps", "text": "There are 12 steps in this lesson and each step takes about 5 minutes to finish. Take your time and breathe."},
            {"heading": "Wrap Up", "text": "You learned how Learning Fractions works and why Meet Fractions matters. Visit https://example.org/more for practice."},
        ],
    )


@pytest.fixture
def glossary():
    return v2.Glossary.load()


def test_source_hash_changes_with_the_english():
    a, b = course(), course("One more sentence about the lesson here.")
    assert a.sha == course().sha
    assert a.sha != b.sha
    assert v2.source_sha256("T", [{"heading": "h", "text": "x"}]) != v2.source_sha256("T2", [{"heading": "h", "text": "x"}])


def test_written_file_records_provenance_and_is_then_reused(tmp_path, glossary):
    eng = FakeEngine()
    src = course()
    res = v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    assert res.status == "written", res.reasons
    rec = load_translation(src.course_id, "km", tmp_path)
    prov = rec["provenance"]
    assert prov["source_sha256"] == src.sha and prov["pipeline"] == v2.PIPELINE_VERSION
    assert prov["engine"] == "fake" and prov["model"] == "fake-1" and prov["backfilled"] is False
    calls_before = len(eng.calls)
    again = v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    assert again.status == "reused" and len(eng.calls) == calls_before  # no skip-by-name, a verified reuse


def test_changed_english_is_not_reused(tmp_path, glossary):
    eng = FakeEngine()
    v2.translate_course(course(), "km", eng, glossary=glossary, root=tmp_path)
    changed = course("A brand new closing sentence for the lesson.")
    ok, why = v2.is_current(load_translation("audio-demo", "km", tmp_path), changed, "km")
    assert not ok and why == "source_changed"
    report = v2.check_library([changed], ["km", "es"], tmp_path)
    assert report["counts"] == {"source_changed": 1, "missing": 1}
    res = v2.translate_course(changed, "km", eng, glossary=glossary, root=tmp_path)
    assert res.status == "written"


def test_legacy_file_without_provenance_is_stale_even_with_matching_shape(tmp_path, glossary):
    src = course()
    legacy = {"course_id": src.course_id, "title": "x", "category": "c", "language": "km", "source": "batch",
              "segments": [{"heading": fake_text(s["heading"], "km"), "text": fake_text(s["text"], "km")} for s in src.segments]}
    save_translation(legacy, tmp_path)
    ok, why = v2.is_current(load_translation(src.course_id, "km", tmp_path), src, "km")
    assert not ok and why == "no_provenance"


def test_masking_restores_headings_urls_and_glossary(tmp_path, glossary):
    src = course()
    res = v2.translate_course(src, "km", FakeEngine(), glossary=glossary, root=tmp_path)
    assert res.status == "written"
    rec = load_translation(src.course_id, "km", tmp_path)
    heads = {s["heading"] for s in rec["segments"]}
    last = rec["segments"][2]["text"]
    assert "https://example.org/more" in last  # the URL survived exactly
    # the section titles mentioned inside the passage are the translated headings, not Latin leftovers
    assert fake_text("Meet Fractions", "km") in last and fake_text("Learning Fractions", "km") in last
    assert fake_text("Meet Fractions", "km") in heads
    # glossary: "fractions" in a maths passage became the pinned Khmer word, not the shares sense
    first = rec["segments"][0]["text"]
    assert "ប្រភាគ" in first and "ភាគហ៊ុន" not in first
    assert "fraction" in rec["provenance"]["glossary_terms_applied"] and rec["provenance"]["glossary_unreviewed"] is True


def test_glossary_term_is_skipped_outside_its_sense(glossary):
    entries = glossary.entries_for("A fraction of the people left early.", "km", "Business")
    assert entries == []  # no maths context word: the translator decides
    assert glossary.entries_for("Compare each fraction with its denominator.", "km", "")


def test_avoid_form_fails_a_segment(glossary):
    src = {"heading": "x", "text": "We will compare every fraction in the math lesson today."}
    bad = "យើងនឹងប្រៀបធៀបភាគហ៊ុននីមួយៗនៅក្នុងមេរៀនគណិតវិទ្យានៅថ្ងៃនេះ"
    assert "glossary_avoid" in v2.segment_findings("km", "ក", bad, src, glossary)


def test_loop_is_retried_with_stricter_settings(tmp_path, glossary):
    src = course("LOOPME is a sentence that the first attempt turns into a loop.")
    eng = FakeEngine(loop_when=lambda text, gen: "loopme" in text.lower() or "LOOPME" in text and gen.get("repetition_penalty") == 1.1)
    # loop only on the first rung (repetition_penalty 1.1)
    eng.loop_when = lambda text, gen: "LOOPME" in text and gen.get("repetition_penalty") == 1.1
    res = v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    assert res.status == "written", res.reasons
    assert res.retried == 1 and res.rungs.get("r1", 0) == 1
    assert any(g.get("repetition_penalty") == 1.2 for _t, g in eng.calls)  # the second rung really ran with new settings


def test_segment_that_never_recovers_is_never_written(tmp_path, glossary):
    src = course("LOOPME is a sentence that always loops no matter the settings.")
    eng = FakeEngine(loop_when=lambda text, gen: "LOOPME" in text)
    res = v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    assert res.status == "needs_fallback" and res.fallback == 1
    assert not translation_path("audio-demo", "km", tmp_path).exists()  # nothing shippable was written
    work = v2.fallback_work(tmp_path, ["km"])
    assert len(work) == 1 and work[0]["index"] == 0 and "degenerate_loop" in work[0]["findings"]
    est = v2.estimate_fallback(work, {src.course_id: src}, price_per_mtok=10.0)
    assert est["segments"] == 1 and est["est_cost_usd"] > 0


def test_lost_placeholders_fall_back_to_the_unmasked_rung(tmp_path, glossary):
    src = v2.CourseSource("audio-ph", "Plain Title", "Arts", [
        {"heading": "Opening Moves", "text": "In this lesson Opening Moves are explained slowly and clearly for every learner."},
        {"heading": "Second Part", "text": "The second part continues the story with more details about the lesson today."},
    ])
    eng = FakeEngine(drop_placeholders_when=lambda gen: True)
    res = v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    assert res.status == "written", res.reasons
    assert res.rungs.get("r4", 0) >= 1  # masked rungs lost their markers, only the unmasked rung could pass


def test_resumes_from_work_state_after_a_failure(tmp_path, glossary):
    src = course("LOOPME is a sentence that loops until the fallback fixes it.")
    eng = FakeEngine(loop_when=lambda text, gen: "LOOPME" in text)
    v2.translate_course(src, "km", eng, glossary=glossary, root=tmp_path)
    state = json.loads(v2.work_path(tmp_path, src.course_id, "km").read_text(encoding="utf-8"))
    assert state["source_sha256"] == src.sha
    assert state["segments"]["1"]["ok"] and state["segments"]["2"]["ok"] and not state["segments"]["0"]["ok"]


def test_fallback_is_off_by_default_capped_and_still_validated(tmp_path, glossary):
    src = course("LOOPME is a sentence that always loops no matter the settings.")
    v2.translate_course(src, "km", FakeEngine(loop_when=lambda t, g: "LOOPME" in t), glossary=glossary, root=tmp_path)
    calls = []

    def paid(text, source, target):
        calls.append(text)
        return fake_text(text, target)

    assert v2.run_fallback(tmp_path, {src.course_id: src}, ["km"], paid, glossary=glossary) == {"attempted": 0, "fixed": 0, "files_written": 0, "still_failing": 0}
    assert calls == []
    capped = v2.run_fallback(tmp_path, {src.course_id: src}, ["km"], paid, glossary=glossary, enabled=True, cap_segments=0)
    assert capped["attempted"] == 0 and not translation_path("audio-demo", "km", tmp_path).exists()
    bad = v2.run_fallback(tmp_path, {src.course_id: src}, ["km"], lambda t, s, g: LOOP, glossary=glossary, enabled=True)
    assert bad["fixed"] == 0 and bad["still_failing"] == 1  # a paid answer is not trusted because it is paid
    ok = v2.run_fallback(tmp_path, {src.course_id: src}, ["km"], paid, glossary=glossary, enabled=True)
    assert ok["fixed"] == 1 and ok["files_written"] == 1
    assert load_translation("audio-demo", "km", tmp_path)["provenance"]["engine"] == "grok-fallback"
    assert not v2.work_path(tmp_path, "audio-demo", "km").exists()


def test_catalog_runner_orders_languages_and_counts(tmp_path, glossary):
    sources = [course(cid="audio-a"), course(cid="audio-b")]
    seen = []
    stats = v2.run_catalog(sources, ["km", "es"], FakeEngine(), root=tmp_path, glossary=glossary,
                           progress=lambda res, done, total: seen.append((res.language, res.course_id, res.status)))
    assert [s[0] for s in seen] == ["km", "km", "es", "es"]
    assert stats["written"] == 4 and stats["reused"] == 0
    stats2 = v2.run_catalog(sources, ["km", "es"], FakeEngine(), root=tmp_path, glossary=glossary)
    assert stats2["reused"] == 4 and stats2["written"] == 0


def test_priority_order_puts_khmer_first():
    langs = v2.priority_languages()
    assert langs[:6] == ["km", "yue", "es", "zh", "fr", "it"] and langs[6:8] == ["th", "vi"]
    assert "en" not in langs


def test_migration_keeps_backfills_and_quarantines(tmp_path, glossary):
    src = course()
    url = "https://example.org/more"

    def legacy(text):  # a translation that kept the URL intact, as a good v1 file would
        return fake_text(text, "km").replace(fake_text(url, "km"), url)

    good = {"course_id": src.course_id, "title": "t", "category": "c", "language": "km", "source": "batch",
            "segments": [{"heading": fake_text(s["heading"], "km"), "text": legacy(s["text"])} for s in src.segments]}
    verdict, upgraded, why = v2.migrate_record(good, src, "km")
    assert verdict == "keep" and why == "backfilled"
    assert upgraded["provenance"]["backfilled"] is True and upgraded["provenance"]["source_sha256"] == src.sha
    # the old padded English: far more segments than today's
    padded = dict(good, segments=good["segments"] * 4)
    assert v2.migrate_record(padded, src, "km")[0] == "stale"
    # right count but the numbers are gone
    nonum = dict(good, segments=[dict(s, text=re.sub(r"\d+", "", s["text"])) for s in good["segments"]])
    assert v2.migrate_record(nonum, src, "km")[0] == "stale"
    # no English to check against
    assert v2.migrate_record(good, None, "km")[0] == "unverifiable"
    # a backfilled file is reusable, unless strict provenance is requested
    ok, _ = v2.is_current(upgraded, src, "km")
    assert ok
    ok2, why2 = v2.is_current(upgraded, src, "km", accept_backfilled=False)
    assert not ok2 and why2 == "backfilled"
    # and different English later makes the backfill stale
    assert v2.is_current(upgraded, course("Changed afterwards in a real way here."), "km")[1] == "source_changed"


def test_chunking_keeps_sentences_whole_and_markers_intact():
    text = "First sentence here. Second sentence follows. [[0]] stays in one piece. " * 5
    chunks = v2.chunk_text(text, max_words=12)
    assert all(len(c.split()) <= 14 for c in chunks)
    assert "".join(chunks).count("[[0]]") == text.count("[[0]]")
    assert len(v2.chunk_text(text, per_sentence=True)) == len(v2.split_sentences(text))
    assert v2.join_chunks(["你好。", "再见。"], "zh") == "你好。再见。"


# --- nllb.translate_batch generation settings ----------------------------------------

class _T:
    def __init__(self, rows):
        self.rows = rows
        self.shape = (len(rows), max(len(r) for r in rows))

    def to(self, device):
        return self


class _P:
    class device:
        type = "cpu"


class _Model:
    def __init__(self):
        self.kwargs = []

    def parameters(self):
        yield _P()

    def generate(self, **kw):
        self.kwargs.append(kw)
        return _T([[f"T:{r[0]}"] for r in kw["input_ids"].rows])


class _Tok:
    src_lang = None

    def convert_tokens_to_ids(self, tgt):
        return 7

    def __call__(self, batch, **_):
        return {"input_ids": _T([[t, "pad"] for t in batch]), "attention_mask": _T([[1, 1] for _ in batch])}

    def batch_decode(self, generated, skip_special_tokens=True):
        return [row[0] for row in generated.rows]


def test_generation_settings_reach_generate(monkeypatch):
    model = _Model()
    monkeypatch.setattr(nllb, "_get_model", lambda: (_Tok(), model))
    out = nllb.translate_batch(["hello"], source="en", target="km", gen={
        "num_beams": 6, "no_repeat_ngram_size": 3, "repetition_penalty": 1.3, "do_sample": True, "temperature": 0.6, "max_len_ratio": 2.0})
    assert out == ["T:hello"]
    kw = model.kwargs[0]
    assert kw["num_beams"] == 6 and kw["no_repeat_ngram_size"] == 3 and kw["repetition_penalty"] == 1.3
    assert kw["do_sample"] is True and kw["temperature"] == 0.6
    assert kw["max_new_tokens"] == max(16, int(2 * 2.0) + 10) and "max_length" not in kw


def test_without_gen_the_old_call_is_unchanged(monkeypatch):
    model = _Model()
    monkeypatch.setattr(nllb, "_get_model", lambda: (_Tok(), model))
    nllb.translate_batch(["hello"], source="en", target="km", num_beams=3)
    kw = model.kwargs[0]
    assert kw["max_length"] == 512 and kw["num_beams"] == 3 and "max_new_tokens" not in kw and "no_repeat_ngram_size" not in kw


def test_glossary_review_items_are_importable_rows():
    rows = v2.Glossary.load().review_items()
    assert rows and all(r["status"] == "unreviewed" for r in rows)
    khmer_fraction = [r for r in rows if r["term"] == "fraction" and r["language"] == "km"][0]
    assert khmer_fraction["proposed"] == "ប្រភាគ" and "ភាគហ៊ុន" in khmer_fraction["avoid"]
