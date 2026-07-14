"""Language name/normalization helpers used to answer learners in their tongue."""

from __future__ import annotations

from aoep_shared.languages import (
    SUPPORTED_LANGUAGES,
    language_name,
    normalize_language,
)


def test_every_supported_language_has_a_name():
    for code in SUPPORTED_LANGUAGES:
        assert language_name(code), f"missing name for {code}"


def test_normalize_language_coerces_locales():
    assert normalize_language("es-419") == "es"
    assert normalize_language("PT-BR") == "pt"
    assert normalize_language("EN") == "en"
    assert normalize_language("km") == "km"
    assert normalize_language("zz") == ""       # unsupported
    assert normalize_language("") == ""


def test_language_name_lookup():
    assert language_name("es") == "Spanish"
    assert language_name("km") == "Khmer"
    assert language_name("zz") == ""
