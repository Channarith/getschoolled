import json
from pathlib import Path

from aoep_shared.translation_validate import (
    HOLD,
    REJECT,
    SHIP,
    has_loop,
    numbers_in,
    script_fraction,
    unchanged_from_source,
    validate_library,
)

EN = "The Impressionists painted light outdoors in 1872. They sold 12 paintings at the first show, and critics laughed."
KM = "អ្នកគូរប្រាណនិយមគូររូបភាពពន្លឺខាងក្រៅនៅឆ្នាំ ១៨៧២។ ពួកគេបានលក់គំនូរ ១២ នៅការតាំងពិពណ៌លើកដំបូង ហើយអ្នករិះគន់សើច។"
ES = "Los impresionistas pintaron la luz al aire libre en 1872. Vendieron 12 cuadros en la primera exposición y los críticos se rieron."


def write(root: Path, course: str, lang: str, segments, **extra):
    path = root / course / f"{lang}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {"course_id": course, "language": lang, "source": "nllb", "segments": segments, **extra}
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def seg(heading, text):
    return {"heading": heading, "text": text, "kind": "narration"}


SRC = {"c1": [{"heading": "Light", "text": EN}]}


def verdict(report, course, lang):
    return next(r for r in report["rows"] if r["course_id"] == course and r["language"] == lang)


def test_good_files_ship_and_are_listed(tmp_path):
    write(tmp_path, "c1", "km", [seg("ពន្លឺ", KM)])
    write(tmp_path, "c1", "es", [seg("La luz", ES)])
    report = validate_library(tmp_path, sources=SRC)
    assert report["verdicts"] == {SHIP: 2}
    assert {(s["course_id"], s["language"]) for s in report["shippable"]} == {("c1", "km"), ("c1", "es")}
    assert all(s["sha256"] and s["bytes"] for s in report["shippable"])


def test_wrong_script_and_romanized_text_is_rejected(tmp_path):
    write(tmp_path, "c1", "km", [seg("Light", "Impressionists painted light outdoors and sold twelve paintings at the show")])
    row = verdict(validate_library(tmp_path, sources=SRC), "c1", "km")
    assert row["verdict"] == REJECT
    assert any("wrong_script" in r for r in row["reasons"])


def test_untranslated_english_is_rejected(tmp_path):
    write(tmp_path, "c1", "es", [seg("Light", EN)])
    row = verdict(validate_library(tmp_path, sources=SRC), "c1", "es")
    assert row["verdict"] == REJECT
    assert any("unchanged_from_english" in r for r in row["reasons"])


def test_segment_count_mismatch_is_rejected(tmp_path):
    write(tmp_path, "c1", "es", [seg("La luz", ES), seg("Más", ES)])
    row = verdict(validate_library(tmp_path, sources=SRC), "c1", "es")
    assert row["verdict"] == REJECT
    assert any(r.startswith("segment_count_mismatch") for r in row["reasons"])


def test_truncated_translation_is_held(tmp_path):
    long_en = (EN + " ") * 12
    write(tmp_path, "c1", "es", [seg("La luz", ES)])
    row = verdict(validate_library(tmp_path, sources={"c1": [{"heading": "Light", "text": long_en}]}), "c1", "es")
    assert row["verdict"] == HOLD
    assert any("length_outlier" in r for r in row["reasons"])


def test_degenerate_loop_and_markup_are_rejected(tmp_path):
    write(tmp_path, "c1", "es", [seg("La luz", "los cuadros " * 12)])
    write(tmp_path, "c2", "es", [seg("La luz", ES + " <unk> </s>")])
    report = validate_library(tmp_path)
    assert verdict(report, "c1", "es")["verdict"] == REJECT
    assert verdict(report, "c2", "es")["verdict"] == REJECT


def test_number_mismatch_is_held_but_rewritten_years_are_not(tmp_path):
    src = {"c1": [{"heading": "Light", "text": "They sold 12 paintings, 30 drawings and 4 prints in 1872."}]}
    write(tmp_path, "c1", "es", [seg("La luz", "Vendieron muchas pinturas, dibujos y grabados en el siglo diecinueve de Francia.")])
    row = verdict(validate_library(tmp_path, sources=src), "c1", "es")
    assert row["verdict"] == HOLD and any("number_mismatch" in r for r in row["reasons"])
    assert numbers_in("១២ and 12") == ["12", "12"]


def test_parse_errors_empty_and_bad_structure(tmp_path):
    (tmp_path / "c1").mkdir()
    (tmp_path / "c1" / "es.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "c2").mkdir()
    (tmp_path / "c2" / "es.json").write_text(json.dumps({"segments": []}), encoding="utf-8")
    (tmp_path / "c3").mkdir()
    (tmp_path / "c3" / "es.json").write_text(json.dumps({"segments": "x"}), encoding="utf-8")
    report = validate_library(tmp_path)
    assert {r["course_id"]: r["verdict"] for r in report["rows"]} == {"c1": REJECT, "c2": REJECT, "c3": REJECT}


def test_stray_partial_files_are_excluded(tmp_path):
    write(tmp_path, "c1", "es", [seg("La luz", ES)])
    (tmp_path / "c1" / "zh.partial").write_text("{}", encoding="utf-8")
    (tmp_path / "c1" / "latest").write_text("x", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    report = validate_library(tmp_path)
    assert report["files"] == 1
    whys = {Path(s["path"]).name: s["why"] for s in report["stray"]}
    assert "zh.partial" in whys and "latest" in whys and "notes.txt" in whys


def test_same_text_in_two_languages_is_held(tmp_path):
    write(tmp_path, "c1", "ru", [seg("Свет", "Импрессионисты писали свет на открытом воздухе в 1872 году и продали двенадцать картин.")])
    write(tmp_path, "c1", "uk", [seg("Свет", "Импрессионисты писали свет на открытом воздухе в 1872 году и продали двенадцать картин.")])
    report = validate_library(tmp_path)
    assert verdict(report, "c1", "uk")["verdict"] == HOLD


def test_peer_segment_counts_without_english_source(tmp_path):
    for lang in ("es", "fr", "de"):
        write(tmp_path, "c1", lang, [seg("T", ES), seg("U", ES + "!")])
    write(tmp_path, "c1", "it", [seg("T", ES)])
    row = verdict(validate_library(tmp_path), "c1", "it")
    assert row["verdict"] == HOLD and any("peer_count_mismatch" in r for r in row["reasons"])


def test_helpers():
    assert script_fraction(KM, "km") > 0.9
    assert script_fraction(ES, "km") < 0.1
    assert has_loop("la la la la la la la")
    assert not has_loop("one two three four")
    assert unchanged_from_source(EN, EN)
    assert not unchanged_from_source(EN, ES)
