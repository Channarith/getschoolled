from __future__ import annotations

import pytest

from theodore_audio_translation_lab.languages import BCP47, SUPPORTED_LANGUAGES, language_rows, normalize_language
from theodore_audio_translation_lab.models import SessionConfig


def test_all_27_platform_languages_present():
    assert len(SUPPORTED_LANGUAGES) == 27
    assert {"en", "es", "zh", "km"} <= set(SUPPORTED_LANGUAGES)
    assert len(language_rows()) == 27
    assert all(code in BCP47 for code in SUPPORTED_LANGUAGES)


def test_locale_normalization():
    assert normalize_language("zh-CN") == "zh"
    assert normalize_language("KM-kh") == "km"
    assert normalize_language("unknown") == ""


def test_session_config_normalizes_and_deduplicates():
    config = SessionConfig(
        session_id="room", source_language="ES-es", target_languages=["en-US", "en", "km-KH"]
    ).normalized()
    assert config.source_language == "es"
    assert config.target_languages == ["en", "km"]


def test_session_rejects_unknown_language():
    with pytest.raises(ValueError, match="unsupported source"):
        SessionConfig(source_language="zz").normalized()
