import argparse
import importlib.util
import sys
from pathlib import Path

import pytest

from aoep_shared import translation_v2 as v2
from aoep_shared.course_translation_library import (
    EXTRA_TRANSLATION_LANGUAGES,
    TARGET_LANGUAGES,
    load_translation,
    normalize_translation_language,
    save_translation,
    translation_path,
)
from aoep_shared.languages import SUPPORTED_LANGUAGES, normalize_language
from aoep_shared.nllb import flores_code
from aoep_shared.translation_validate import script_fraction

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "translate_catalog_v2.py"


def _load_script():
    spec = importlib.util.spec_from_file_location("translate_catalog_v2_under_test", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = mod
    spec.loader.exec_module(mod)
    return mod


def _args(**kw):
    base = dict(languages="", exclude="", tier=3)
    base.update(kw)
    return argparse.Namespace(**base)


def test_priority_order_is_the_owners_order():
    order = v2.priority_languages()
    assert order[:6] == ["km", "yue", "es", "zh", "fr", "it"]
    assert order[6:8] == ["th", "vi"]
    assert order[8:17] == ["ja", "ko", "pt", "de", "ru", "ar", "hi", "id", "tr"]
    assert order[-1] == "tl"
    assert len(order) == len(set(order))


def test_priority_order_covers_every_translatable_language_exactly_once():
    assert set(v2.priority_languages()) == set(TARGET_LANGUAGES) | set(EXTRA_TRANSLATION_LANGUAGES)
    assert set(v2.PRIORITY_ORDER) == set(v2.priority_languages())


def test_tiers_are_prefixes_of_the_order():
    order = v2.priority_languages()
    assert list(v2.TIER1) == order[:8]
    assert list(v2.TIER1) + list(v2.TIER2) == order[:17]


def test_extra_languages_do_not_widen_the_platform_languages():
    assert "tl" not in SUPPORTED_LANGUAGES and len(SUPPORTED_LANGUAGES) == 27
    assert normalize_language("tl") == "" and normalize_language("fil") == ""
    assert normalize_language("yue") == "yue"  # existing behaviour, unchanged


@pytest.mark.parametrize("raw,want", [("tl", "tl"), ("fil", "tl"), ("fil-PH", "tl"), ("Tagalog", "tl"), ("tgl", "tl"),
                                      ("yue", "yue"), ("yue-HK", "yue"), ("cantonese", "yue"), ("zh-HK", "zh"),
                                      ("es-419", "es"), ("klingon", ""), ("", "")])
def test_normalize_translation_language(raw, want):
    assert normalize_translation_language(raw) == want


def test_tagalog_has_its_own_file_and_never_overwrites_english(tmp_path):
    rec = {"course_id": "audio-a", "title": "t", "category": "c", "language": "fil",
           "segments": [{"heading": "h", "text": "Kumusta"}]}
    path = save_translation(rec, tmp_path)
    assert path.name == "tl.json"
    assert translation_path("audio-a", "tl", tmp_path).name == "tl.json"
    assert not (tmp_path / "audio-a" / "en.json").exists()
    assert load_translation("audio-a", "tl", tmp_path)["language"] == "tl"


def test_nllb_codes_for_the_extras():
    assert flores_code("tl") == "tgl_Latn" and flores_code("fil") == "tgl_Latn"
    assert flores_code("yue") == "yue_Hant"


def test_validator_can_check_cantonese_and_tagalog_scripts():
    assert script_fraction("呢個係一個好簡單嘅句子，我哋一齊讀", "yue") > 0.9
    assert script_fraction("This is plain English text that is long enough", "yue") < 0.1
    assert script_fraction("Magandang umaga sa lahat ng mag-aaral", "tl") > 0.9


def test_script_accepts_extras_and_orders_languages():
    mod = _load_script()
    assert mod.pick_languages(_args(languages="km,yue,es,zh,fr,it")) == ["km", "yue", "es", "zh", "fr", "it"]
    assert mod.pick_languages(_args(languages="fil,Cantonese,km")) == ["tl", "yue", "km"]
    assert mod.pick_languages(_args(tier=1)) == list(v2.TIER1)
    assert mod.pick_languages(_args())[0] == "km"


def test_script_exclude_and_errors():
    mod = _load_script()
    assert mod.pick_languages(_args(languages="km,yue,es,zh", exclude="es,fil")) == ["km", "yue", "zh"]
    spark = mod.pick_languages(_args(exclude="fr,it,ja,ko"))
    assert "fr" not in spark and spark[:4] == ["km", "yue", "es", "zh"]
    with pytest.raises(SystemExit, match="unsupported language"):
        mod.pick_languages(_args(languages="km,klingon"))
    with pytest.raises(SystemExit, match="no languages left"):
        mod.pick_languages(_args(languages="km", exclude="km"))
