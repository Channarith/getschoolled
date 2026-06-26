"""Regional dialect humanization."""

from aoep_shared.dialect import (
    dialect_intro,
    get_dialect,
    humanize_narration,
    list_dialects,
    normalize_dialect,
)


def test_california_intro_uses_casual_tone():
    intro = dialect_intro("Chemistry", ["Atoms", "Bonds"], "us_ca")
    assert "stoked" in intro.lower() or "holler" in intro.lower()


def test_texas_intro_uses_yall():
    intro = dialect_intro("History", ["Texas"], "us_tx")
    assert "y'all" in intro.lower() or "howdy" in intro.lower()


def test_humanize_replaces_formal_phrases():
    raw = "Welcome! We will walk through the lesson. Take your time."
    out = humanize_narration(raw, "us_ca")
    assert "stoked" in out.lower() or "cruise" in out.lower() or "no stress" in out.lower()


def test_mexican_spanish_intro():
    intro = dialect_intro("Química", ["Átomos"], "es_mx", language="es")
    assert "onda" in intro.lower() or "hoy" in intro.lower()


def test_list_dialects_includes_regions():
    ids = {d["id"] for d in list_dialects()}
    assert {"us_ca", "us_tx", "es_mx", "pt_br"}.issubset(ids)


def test_normalize_aliases():
    assert normalize_dialect("californian") == "us_ca"
    assert normalize_dialect("texan") == "us_tx"
