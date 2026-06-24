"""Locale mascot catalog and resolver."""

from aoep_shared.languages import SUPPORTED_LANGUAGES
from aoep_shared.mascots import (
    MASCOT_CATALOG,
    DEFAULT_MASCOT_LOCALE,
    DEFAULT_MASCOT_PATH,
    mascot_asset_path,
    mascot_catalog_list,
    normalize_mascot_locale,
    resolve_mascot,
)


def test_catalog_covers_all_supported_languages():
    assert set(MASCOT_CATALOG) == set(SUPPORTED_LANGUAGES)
    assert len(MASCOT_CATALOG) == 27


def test_normalize_mascot_locale():
    assert normalize_mascot_locale("ja-JP") == "ja"
    assert normalize_mascot_locale("km_KH") == "km"
    assert normalize_mascot_locale(None) == DEFAULT_MASCOT_LOCALE
    assert normalize_mascot_locale("xx") == DEFAULT_MASCOT_LOCALE


def test_mascot_asset_path():
    assert mascot_asset_path("fr") == "/mascots/fr.svg"
    assert mascot_asset_path("en-US") == "/mascots/en.svg"


def test_resolve_mascot_enabled():
    r = resolve_mascot("ko")
    assert r["locale"] == "ko"
    assert r["path"] == "/mascots/ko.svg"
    assert r["localized"] is True
    assert r["variant"]["cultural_theme"] == "Seowon student"


def test_resolve_mascot_preview_override():
    r = resolve_mascot("en", preview_locale="th")
    assert r["locale"] == "th"
    assert r["path"] == "/mascots/th.svg"


def test_resolve_mascot_disabled():
    r = resolve_mascot("ja", enabled=False)
    assert r["path"] == DEFAULT_MASCOT_PATH
    assert r["localized"] is False


def test_mascot_catalog_list():
    items = mascot_catalog_list()
    assert len(items) == 27
    assert all("locale" in i and "path" in i for i in items)
