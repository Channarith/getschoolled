"""Voice catalog: accents/languages resolve, and dialect tags are valid."""

from __future__ import annotations

from aoep_shared.dialect import DIALECTS
from aoep_shared.voice_catalog import (
    VOICE_CATALOG,
    catalog_grouped,
    default_voice_for_language,
    get_voice,
    resolve_voice,
)


def test_catalog_has_requested_accents():
    accents = {v.accent for v in VOICE_CATALOG}
    for want in [
        "Texan (US South)",
        "British",
        "Australian",
        "Mandarin (China)",
        "Castilian",
        "Southern US",
        "New York",
        "Singaporean",
        "Beijing Mandarin",
        "Cantonese (Guangzhou/HK)",
        "Fujianese / Hokkien",
        "Canadian",
    ]:
        assert want in accents, want
    langs = {v.language for v in VOICE_CATALOG}
    assert {"en", "es", "zh", "fr", "de", "pt", "ja", "ar"} <= langs
    assert len(VOICE_CATALOG) >= 45


def test_ids_unique_and_edge_voices_present():
    ids = [v.id for v in VOICE_CATALOG]
    assert len(ids) == len(set(ids))                       # unique ids
    assert all(v.edge_voice.endswith("Neural") for v in VOICE_CATALOG)  # real MS voices


def test_dialect_tags_are_valid():
    # Every slang/dialect tag must map to a real DialectProfile.
    for v in VOICE_CATALOG:
        if v.dialect:
            assert v.dialect in DIALECTS, f"{v.id} -> unknown dialect {v.dialect}"


def test_get_and_resolve():
    tx = get_voice("en_us_tx_m")
    assert tx and tx.accent.startswith("Texan") and tx.dialect == "us_tx"
    gb = get_voice("en_gb_f")
    assert gb and gb.locale == "en-GB" and gb.edge_voice == "en-GB-SoniaNeural"
    # Unknown id falls back to the language default.
    assert resolve_voice("nope", language="es").language == "es"
    assert resolve_voice("", language="en").language == "en"
    assert default_voice_for_language("zh").language == "zh"


def test_grouped_for_picker():
    groups = catalog_grouped()
    by_lang = {g["language"]: g["voices"] for g in groups}
    assert "en" in by_lang and len(by_lang["en"]) >= 5
    # English group includes British + Australian + Texan.
    en_accents = {v["accent"] for v in by_lang["en"]}
    assert {"British", "Australian"} <= en_accents
