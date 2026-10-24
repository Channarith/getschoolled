import copy
import json
from collections import Counter

from tts_bakeoff import adapters, schema
from tts_bakeoff.build_sentences import OUT, load, ordered_ids, render
from tts_bakeoff.sentences_master import CATEGORIES, LANGS, SENTENCES


def test_sentence_set_is_40_per_language_and_complete():
    assert len(SENTENCES) == 40
    for sid, row in SENTENCES.items():
        assert set(row) == set(LANGS), sid
        assert all(text.strip() for text in row.values()), sid
    counts = Counter(CATEGORIES[sid[0]] for sid in SENTENCES)
    assert counts == {"short": 8, "medium": 8, "long": 6, "numbers": 5, "dates": 4, "names": 3, "vocab": 3, "question": 3}


def test_committed_jsonl_matches_the_builder_and_is_deterministic():
    for lang in LANGS:
        assert (OUT / f"{lang}.jsonl").read_text(encoding="utf-8") == render(lang)
        assert render(lang) == render(lang)
        rows = load(lang)
        assert len(rows) == 40 and [r["id"] for r in rows] == ordered_ids()
        assert all(r["review_status"] == ("master" if lang == "en" else "unreviewed") for r in rows)


def test_a_limited_run_covers_a_mix_of_categories():
    first8 = [r["category"] for r in load("en", 8)]
    assert sorted(first8) == sorted({"short", "medium", "long", "numbers", "dates", "names", "vocab", "question"})
    assert sorted(ordered_ids()) == sorted(SENTENCES)


def test_scripts_are_what_they_claim():
    km = " ".join(r["text"] for r in load("km"))
    th = " ".join(r["text"] for r in load("th"))
    assert any("ក" <= ch <= "៿" for ch in km)
    assert any("฀" <= ch <= "๿" for ch in th)


def test_matrix_is_valid():
    assert schema.validate(schema.load()) == []


def test_every_claim_has_evidence_with_a_retrieval_date():
    for c in schema.load()["candidates"]:
        assert c["evidence"], c["id"]
        for ev in c["evidence"]:
            assert ev["url"].startswith("https://") and ev["quote"] and ev["retrieved"] == "2026-10-24", (c["id"], ev)


def test_non_commercial_models_are_never_shippable_or_product():
    cands = schema.candidates()
    for cid in ("fish-speech-1.5", "openaudio-s1-mini", "f5-tts", "mms-tts", "viettts", "xtts-v2"):
        assert not schema.shippable(cands[cid]), cid
        assert cands[cid]["role"] in {"reference", "excluded"}, cid
    assert schema.label(cands["fish-speech-1.5"]) == "NOT SHIPPABLE"
    assert schema.label(cands["xtts-v2"]) == "CHECK LICENSE"  # terms unreadable: unverified is not yes
    for c in cands.values():
        if c["role"] == "product":
            assert schema.shippable(c), c["id"]


def test_unverified_is_not_shippable():
    cands = schema.candidates()
    assert not schema.shippable(cands["qwen3-tts"])  # code license not read
    assert not schema.shippable(cands["kokoro"])


def test_coverage_of_the_hard_languages_is_recorded_honestly():
    cands = schema.candidates()
    open_shippable = {cid for cid, c in cands.items() if c["kind"] == "open" and schema.shippable(c)}
    khmer = {cid for cid in open_shippable if schema.covers(cands[cid], "km")}
    assert khmer == {"voxcpm2"}  # the only commercially usable open model with Khmer that we found
    assert not any(schema.covers(cands[c], "km") for c in ("cosyvoice2", "chatterbox", "kokoro", "qwen3-tts", "fish-speech-1.5"))
    assert schema.covers(cands["chatterbox"], "sw") and schema.covers(cands["voxcpm2"], "sw")
    assert not schema.covers(cands["voxcpm2"], "bn")  # nothing open and commercial covers Bengali


def test_adapters_named_in_the_matrix_exist():
    for c in schema.candidates().values():
        if c.get("adapter"):
            assert c["adapter"] in adapters.REGISTRY, c["id"]


def test_validator_catches_bad_data():
    data = schema.load()
    bad = copy.deepcopy(data)
    bad["candidates"][0]["license"]["code"]["commercial_ok"] = True  # unquoted yes
    bad["candidates"][0]["evidence"][0].pop("retrieved")
    bad["candidates"].append(copy.deepcopy(bad["candidates"][0]))
    problems = " | ".join(schema.validate(bad))
    assert "commercial_ok must be one of" in problems and "missing retrieved" in problems and "duplicate id" in problems
    nc_product = copy.deepcopy(data)
    for c in nc_product["candidates"]:
        if c["id"] == "fish-speech-1.5":
            c["role"] = "product"
    assert any("role product requires" in p for p in schema.validate(nc_product))


def test_jsonl_lines_are_valid_json():
    for lang in LANGS:
        for line in (OUT / f"{lang}.jsonl").read_text(encoding="utf-8").splitlines():
            json.loads(line)
