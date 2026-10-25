import json

from aoep_shared import course_translation_library as lib


def _write(root, course, lang, payload, filed_as=None):
    d = root / course
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{filed_as or lang}.json").write_text(json.dumps(payload), encoding="utf-8")


def _seg(text="hola", heading="Intro"):
    return {"heading": heading, "text": text, "kind": "narration"}


def test_a_good_file_loads(tmp_path):
    _write(tmp_path, "c1", "es", {"language": "es", "segments": [_seg()]})
    assert lib.load_translation("c1", "es", tmp_path)["segments"][0]["text"] == "hola"


def test_a_file_filed_under_another_language_is_not_served(tmp_path):
    _write(tmp_path, "c1", "fr", {"language": "es", "segments": [_seg()]}, filed_as="fr")
    assert lib.load_translation("c1", "fr", tmp_path) is None


def test_missing_language_field_still_loads(tmp_path):
    _write(tmp_path, "c1", "es", {"segments": [_seg()]})
    assert lib.load_translation("c1", "es", tmp_path) is not None


def test_non_list_or_empty_segments_are_refused(tmp_path):
    _write(tmp_path, "a", "es", {"language": "es", "segments": "text"})
    _write(tmp_path, "b", "es", {"language": "es", "segments": {"x": 1}})
    _write(tmp_path, "c", "es", {"language": "es", "segments": []})
    _write(tmp_path, "d", "es", [1, 2, 3])
    for cid in "abcd":
        assert lib.load_translation(cid, "es", tmp_path) is None


def test_malformed_rows_are_dropped_not_crashed_on(tmp_path):
    rows = [_seg("uno"), "junk", None, {"heading": "H"}, {"text": "no heading"}, _seg("dos", "Two")]
    _write(tmp_path, "c1", "es", {"language": "es", "segments": rows})
    got = lib.load_translation("c1", "es", tmp_path)
    assert [r["text"] for r in got["segments"]] == ["uno", "dos"]


def test_all_rows_malformed_is_no_translation(tmp_path):
    _write(tmp_path, "c1", "es", {"language": "es", "segments": ["x", {"text": ""}]})
    assert lib.load_translation("c1", "es", tmp_path) is None


def test_extra_languages_yue_and_tl_read_their_own_files(tmp_path):
    _write(tmp_path, "c1", "yue", {"language": "yue", "segments": [_seg("你好")]})
    _write(tmp_path, "c1", "tl", {"language": "tl", "segments": [_seg("kumusta")]})
    assert lib.load_translation("c1", "yue", tmp_path)["segments"][0]["text"] == "你好"
    assert lib.load_translation("c1", "fil", tmp_path)["segments"][0]["text"] == "kumusta"
    assert lib.load_translation("c1", "en", tmp_path) is None


def test_corrupt_json_is_no_translation(tmp_path):
    d = tmp_path / "c1"
    d.mkdir()
    (d / "es.json").write_text("{not json", encoding="utf-8")
    assert lib.load_translation("c1", "es", tmp_path) is None
