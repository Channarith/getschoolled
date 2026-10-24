"""Catalog database support that needs no database: license tiers, composition, migrations, bodies."""

from __future__ import annotations

import gzip
import json
import tomllib
from pathlib import Path

import pytest

from aoep_shared.catalog_db import migrate
from aoep_shared.catalog_db.bodies import BodyError, BodyLoader, deck_dict_from_body
from aoep_shared.catalog_db.compose import (
    DECK_ID_PREFIX,
    DeckRef,
    compose_courses,
    course_content_hash,
    deck_sha_from_deck_id,
    is_servable,
    local_license_tier,
    most_restrictive,
)
from aoep_shared.harvest.objectstore import LocalObjectStore, canonical_bytes, content_sha256, course_key


@pytest.mark.parametrize(
    "value,tier",
    [
        ("CC BY 4.0", "product_safe"),  # spaces collapse to cc-by-4.0
        ("cc-by-4.0", "product_safe"),
        ("cc-by", "product_safe"),
        ("CC0", "product_safe"),
        ("cc0-1.0", "product_safe"),
        ("public-domain", "product_safe"),
        ("MIT", "product_safe"),
        ("apache-2.0", "product_safe"),
        ("cc-by-sa-4.0", "share_alike"),
        ("GFDL", "share_alike"),
        ("cc-by-nc-4.0", "research_only"),
        ("cc-by-nc-sa-4.0", "research_only"),
        ("cc-by-nd-4.0", "research_only"),
        ("oer", "unknown"),
        ("", "unknown"),
        (None, "unknown"),
        ("all-rights-reserved", "unknown"),
        ("owned", "owned"),
    ],
)
def test_license_tiers(value, tier):
    assert local_license_tier(value) == tier


def test_license_urls_and_spdx_ids_use_the_harvester_parser():
    from aoep_shared.catalog_db.compose import license_tier

    assert license_tier("https://creativecommons.org/licenses/by/4.0/") == "product_safe"
    assert license_tier("https://creativecommons.org/licenses/by-nc/4.0/") == "research_only"
    assert license_tier("https://creativecommons.org/licenses/by-sa/3.0/") == "share_alike"
    assert license_tier("CC-BY-ND-4.0") == "research_only"
    assert license_tier("CC BY 4.0") == "product_safe"
    assert license_tier("whatever the seed says") == "unknown"


def test_most_restrictive_and_servable():
    assert most_restrictive(["product_safe", "share_alike"]) == "share_alike"
    assert most_restrictive(["owned", "product_safe"]) == "product_safe"
    assert most_restrictive(["product_safe", "weird"]) == "unknown"
    assert is_servable("product_safe") and is_servable("owned")
    assert not is_servable("share_alike")
    assert is_servable("share_alike", allow_share_alike=True)
    assert not is_servable("research_only", allow_share_alike=True)


def _deck(i: int, *, lic="cc-by-4.0", subject="biology", lang="en", url=None, tier=0) -> DeckRef:
    return DeckRef(
        sha256=f"{i:064x}", title=f"Lesson {i}", subject=subject, language=lang,
        source_url=url or "https://openstax.org/books/biology/p/ch1", license=lic, slides=11,
        quality_tier=tier, first_text=f"Intro text {i}",
    )


def test_compose_groups_eight_lessons_per_course_with_stable_ids():
    decks = [_deck(i) for i in range(20)]
    courses, rejected = compose_courses(decks, per_course=8)
    assert not rejected
    assert [len(c.decks) for c in courses] == [8, 8, 4]  # 4 >= min_modules(3): stays its own course
    again, _ = compose_courses(list(reversed(decks)), per_course=8)
    assert [c.course_id for c in courses] == [c.course_id for c in again]  # order of input never matters
    assert len({c.course_id for c in courses}) == 3
    first = courses[0].payload
    assert first["modules"][0]["deck_id"].startswith(DECK_ID_PREFIX)
    shas = {d.sha256 for d in decks}
    assert deck_sha_from_deck_id(first["modules"][0]["deck_id"]) in shas
    assert deck_sha_from_deck_id("obj:nothex") is None and deck_sha_from_deck_id("deck-1") is None


def test_compose_merges_a_tiny_tail_instead_of_a_stub_course():
    courses, _ = compose_courses([_deck(i) for i in range(17)], per_course=8)  # 8 + 8 + 1
    assert [len(c.decks) for c in courses] == [8, 9]


def test_compose_rejects_non_product_licenses_and_says_why():
    decks = [_deck(1), _deck(2, lic="cc-by-nc-sa-4.0"), _deck(3, lic=""), _deck(4, lic="cc-by-sa-4.0"), _deck(5, lic="oer")]
    courses, rejected = compose_courses(decks)
    assert [d.sha256 for c in courses for d in c.decks] == [decks[0].sha256]
    reasons = {d.sha256: r for d, r in rejected}
    assert len(rejected) == 4 and "research_only" in reasons[decks[1].sha256]
    allowed, rej2 = compose_courses(decks, allow_share_alike=True)
    assert len(rej2) == 3  # share-alike now allowed, NC/unknown/oer still not
    assert sum(len(c.decks) for c in allowed) == 2


def test_compose_course_license_is_its_most_restrictive_lesson():
    courses, _ = compose_courses([_deck(1), _deck(2, lic="cc-by-sa-4.0")], allow_share_alike=True)
    assert courses[0].license_tier == "share_alike"
    assert "license:share_alike" in courses[0].payload["tags"]


def test_compose_dedupes_the_same_body_and_separates_languages():
    decks = [_deck(1), _deck(1), _deck(2, lang="es")]
    courses, _ = compose_courses(decks)
    assert sorted(len(c.decks) for c in courses) == [1, 1]
    assert {c.payload["language"] for c in courses} == {"en", "es"}


def test_quality_tier_is_the_weakest_lesson():
    courses, _ = compose_courses([_deck(1, tier=1), _deck(2, tier=0)])
    assert courses[0].quality_tier == 0 and "tier:0" in courses[0].payload["tags"]


def test_content_hash_is_order_and_field_sensitive_but_whitespace_tolerant():
    mods = [{"title": "a", "deck_id": "d1"}, {"title": "b", "deck_id": "d2"}]
    h = course_content_hash("Algebra", "EN", "Math", mods)
    assert h == course_content_hash(" Algebra ", "en", "math", mods)
    assert h != course_content_hash("Algebra", "en", "math", list(reversed(mods)))
    assert h != course_content_hash("Algebra 2", "en", "math", mods)


# ----------------------------------------------------------------------------- migrations
def test_migrations_are_discoverable_ordered_and_checksummed():
    found = migrate.discover()
    assert [m.version for m in found] == sorted(m.version for m in found)
    assert found[0].name == "core" and len(found) >= 3
    assert all(len(m.checksum) == 64 for m in found)


def test_migration_discovery_rejects_bad_names_and_duplicates(tmp_path):
    (tmp_path / "001_a.sql").write_text("select 1;")
    (tmp_path / "001_b.sql").write_text("select 2;")
    with pytest.raises(ValueError, match="duplicate"):
        migrate.discover(tmp_path)
    (tmp_path / "001_b.sql").unlink()
    (tmp_path / "notes.sql").write_text("-- no")
    with pytest.raises(ValueError, match="must look like"):
        migrate.discover(tmp_path)


def test_every_sql_file_is_packaged():
    """A migration missing from package-data would crash the service at startup (as happened with
    friendly_error_copy.json): fail here instead."""
    cfg = tomllib.loads((Path(migrate.__file__).resolve().parents[3] / "pyproject.toml").read_text())
    patterns = cfg["tool"]["setuptools"]["package-data"]["aoep_shared"]
    base = Path(migrate.__file__).resolve().parents[1]
    packaged = set()
    for pattern in patterns:
        packaged.update(p.relative_to(base) for p in base.glob(pattern))
    for sql in migrate.SQL_DIR.glob("*.sql"):
        assert sql.relative_to(base) in packaged, f"{sql.name} is not covered by package-data"


# ----------------------------------------------------------------------------- bodies
def _put(store, body: dict) -> str:
    sha = content_sha256(canonical_bytes(body))
    store.put(course_key(sha), gzip.compress(canonical_bytes(body), mtime=0))
    return sha


def test_body_loader_roundtrip_cache_and_shape(tmp_path):
    store = LocalObjectStore(tmp_path)
    body = {"title": "Cells", "language": "en", "slides": [{"title": "S1", "body": "text", "narration": "say"}]}
    sha = _put(store, body)
    loader = BodyLoader(store)
    got = loader.load(DECK_ID_PREFIX + sha)
    assert got["title"] == "Cells"
    deck = deck_dict_from_body(DECK_ID_PREFIX + sha, got)
    assert deck["slides"][0]["narration"] == "say" and deck["deck_id"] == DECK_ID_PREFIX + sha
    (tmp_path / "courses").rename(tmp_path / "gone")  # second load is served from cache
    assert loader.load(DECK_ID_PREFIX + sha) is got


def test_body_loader_refuses_corrupt_oversized_and_foreign_ids(tmp_path):
    store = LocalObjectStore(tmp_path)
    with pytest.raises(BodyError):
        BodyLoader(store).load("deck-123")
    with pytest.raises(BodyError):
        BodyLoader(store).load(DECK_ID_PREFIX + "0" * 64)  # missing
    real = {"title": "X", "slides": []}
    sha = _put(store, real)
    store.put(course_key("1" * 64), gzip.compress(canonical_bytes({"title": "tampered"}), mtime=0))
    with pytest.raises(BodyError, match="integrity"):
        BodyLoader(store).load(DECK_ID_PREFIX + "1" * 64)
    with pytest.raises(BodyError, match="too large"):
        BodyLoader(store, max_bytes=10).load(DECK_ID_PREFIX + sha)
