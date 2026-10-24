"""Import tooling: product-corpus gate, idempotency, resume, dry run (no database needed)."""

from __future__ import annotations

import gzip
import json

from aoep_shared.catalog_db.compose import DeckRef
from curriculum import catalog_import as ci
from curriculum.catalog import CatalogStore, Course, Module


class FakeStore:
    """Records bulk_insert calls and behaves like PgCatalogStore.bulk_insert (never overwrites)."""

    def __init__(self):
        self.courses: dict[str, Course] = {}
        self.sources: dict[str, list] = {}
        self.calls = 0

    def known_deck_shas(self, shas):
        have = {m.deck_id[4:] for c in self.courses.values() for m in c.modules}
        return {s for s in shas if s in have}

    def bulk_insert(self, courses, sources=None):
        self.calls += 1
        inserted = skipped = 0
        for c in courses:
            if c.course_id in self.courses:
                skipped += 1
                continue
            self.courses[c.course_id] = c
            self.sources[c.course_id] = (sources or {}).get(c.course_id, [])
            inserted += 1
        return inserted, skipped


def _deck(i, lic="cc-by-4.0", **kw):
    return DeckRef(sha256=f"{i:064x}", title=f"L{i}", subject="biology", language="en",
                   source_url="https://openstax.org/books/bio/p/1", license=lic, slides=10,
                   first_text="hello", **kw)


def test_dry_run_writes_nothing_and_reports_the_plan():
    composed, report = ci.compose_report([_deck(i) for i in range(10)] + [_deck(99, lic="cc-by-nc-4.0")])
    store = FakeStore()
    out = ci.write_courses(store, composed, report, dry_run=True)
    assert store.calls == 0 and out.dry_run
    assert out.courses_composed == 1 and out.decks_rejected == 1  # 10 lessons: the 2-lesson tail merges
    assert out.rejected_by_reason == {"license tier 'research_only'": 1}


def test_apply_inserts_courses_with_provenance_and_is_idempotent():
    decks = [_deck(i) for i in range(16)]
    composed, report = ci.compose_report(decks)
    store = FakeStore()
    r1 = ci.write_courses(store, composed, report, dry_run=False, batch=1)
    assert r1.courses_inserted == 2 and len(store.courses) == 2
    assert all(len(v) == 8 and v[0]["license_tier"] == "product_safe" for v in store.sources.values())
    composed2, rep2 = ci.compose_report(list(reversed(decks)))
    r2 = ci.write_courses(store, composed2, rep2, dry_run=False)
    assert r2.courses_inserted == 0 and r2.courses_skipped_existing == 2  # same ids: nothing added twice


def test_adding_decks_later_builds_only_new_courses_and_never_reshuffles_old_ones():
    store = FakeStore()
    first, rep = ci.compose_report([_deck(i) for i in range(8)])
    ci.write_courses(store, first, rep, dry_run=False)
    old_ids = set(store.courses)
    decks = [_deck(i) for i in range(16)]
    second, rep2 = ci.compose_report(decks, known_shas=store.known_deck_shas(d.sha256 for d in decks))
    out = ci.write_courses(store, second, rep2, dry_run=False)
    assert rep2.decks_already_imported == 8 and out.courses_inserted == 1
    assert old_ids <= set(store.courses) and len(store.courses) == 2
    used = [m.deck_id for c in store.courses.values() for m in c.modules]
    assert len(used) == len(set(used)) == 16  # no lesson in two courses
    again, rep3 = ci.compose_report(decks, known_shas=store.known_deck_shas(d.sha256 for d in decks))
    assert not again and rep3.decks_already_imported == 16  # re-running adds nothing


def test_non_product_decks_never_reach_the_store():
    decks = [_deck(1), _deck(2, lic="all-rights-reserved"), _deck(3, lic="cc-by-sa-4.0"), _deck(4, lic="oer")]
    composed, report = ci.compose_report(decks)
    store = FakeStore()
    ci.write_courses(store, composed, report, dry_run=False)
    shas = {d.sha256 for c in composed for d in c.decks}
    assert shas == {_deck(1).sha256}
    assert all("license:product_safe" in c.tags for c in store.courses.values())


def test_resume_state_skips_what_was_already_written(tmp_path):
    composed, report = ci.compose_report([_deck(i) for i in range(40)], per_course=8)  # 5 courses
    state = tmp_path / "state.json"
    store = FakeStore()
    ci.write_courses(store, composed, report, dry_run=False, batch=2, state_file=state)
    assert json.loads(state.read_text())["done"] == 5
    store2 = FakeStore()
    again, rep2 = ci.compose_report([_deck(i) for i in range(40)], per_course=8)
    out = ci.write_courses(store2, again, rep2, dry_run=False, batch=2, state_file=state)
    assert out.resumed_from == 5 and store2.calls == 0


def test_bundle_reader_gets_titles_and_preview_text(tmp_path):
    sha = "ab" * 32
    body = {"title": "t", "slides": [{"body": "The cell is the basic unit of life."}]}
    obj = tmp_path / "courses" / sha[:2] / f"{sha}.json.gz"
    obj.parent.mkdir(parents=True)
    obj.write_bytes(gzip.compress(json.dumps(body).encode()))
    (tmp_path / "provenance.jsonl").write_text(json.dumps({
        "sha256": sha, "title": "Cells", "subject": "biology", "language": "en", "slides": 9,
        "source_url": "https://openstax.org/b/1", "license": "cc-by-4.0", "harvested_at": "2026-10-24"}) + "\n")
    [deck] = list(ci.decks_from_bundle(tmp_path))
    assert deck.title == "Cells" and deck.first_text.startswith("The cell")
    composed, _ = ci.compose_report([deck])
    assert composed[0].payload["description"].startswith("The cell")


def test_json_catalog_import_keeps_courses_as_they_are(tmp_path):
    src = CatalogStore(path=str(tmp_path / "catalog.json"))
    src.create_course(Course(course_id="keep1", title="Hand authored", modules=[Module(title="m", deck_id="d1")]))
    courses = ci.courses_from_json_catalog(tmp_path / "catalog.json")
    store = FakeStore()
    out = ci.write_plain_courses(store, courses, ci.ImportReport(), dry_run=False)
    assert out.courses_inserted == 1 and store.courses["keep1"].title == "Hand authored"
    assert ci.write_plain_courses(FakeStore(), courses, ci.ImportReport(), dry_run=True).courses_inserted == 0
