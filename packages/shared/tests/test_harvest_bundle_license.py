"""License safety on the path that carries courses between machines and into the catalog."""

import json
import sqlite3

import pytest

from aoep_shared.harvest.bundle import export_bundle, import_bundle, license_gate, open_index
from aoep_shared.harvest.corpus_store import HarvestCorpusStore
from aoep_shared.harvest.licensing import HarvestPolicy
from aoep_shared.harvest.objectstore import LocalObjectStore


def course(n):
    slides = [{"title": f"Lesson {n} part {i}", "body": f"Fractions and ratios number {n}-{i} " * 12,
               "narration": "x", "category": "concept"} for i in range(4)]
    return {"course_id": f"c{n}", "title": f"Course {n}", "subject": "math", "language": "en", "slides": slides}


def machine(tmp_path, rows):
    """rows: (n, declared_license, tier, verified_by, quarantined). Uses the real corpus schema."""
    store = HarvestCorpusStore(tmp_path / "m" / "corpus.db")
    (tmp_path / "m" / "courses").mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(store.path)
    for n, lic, tier, verified, quarantined in rows:
        path = tmp_path / "m" / "courses" / f"c{n}.course.json"
        path.write_text(json.dumps(course(n)))
        url = f"https://s{n}.example.net/"
        prov = {"attribution": {"text": f"Course {n} by Ada, licensed under {lic}."}} if verified else None
        store.upsert_source(url=url, license=lic, title=f"t{n}", subject="math", provenance=prov)
        store.save_course(course_id=f"c{n}", url=url, title=f"Course {n}", subject="math", json_path=str(path))
        conn.execute("UPDATE sources SET license_tier=?, license_verified_by=?, quarantined=? WHERE url=?",
                     (tier, verified, int(quarantined), url))
        conn.commit()     # release the write lock before the store writes the next row
    conn.close()
    return store.path, tmp_path / "m"


def run(tmp_path, rows, **kw):
    db, root = machine(tmp_path, rows)
    rep = export_bundle(db, tmp_path / "bundle", machine="m", repo_root=root)
    store = LocalObjectStore(tmp_path / "agg" / "store")
    idx = open_index(tmp_path / "agg" / "index.db")
    imp = import_bundle(tmp_path / "bundle", store, idx, **kw)
    reasons = [r["reason"] for r in idx.execute("SELECT reason FROM rejected")]
    return rep, imp, reasons, idx


def test_quarantined_courses_never_leave_the_machine(tmp_path):
    rep, imp, _, _ = run(tmp_path, [
        (1, "cc-by", "commercial_ok", "page", False),
        (2, "cc-by-nc", "non_commercial", None, True),
    ])
    assert rep.courses == 1 and rep.skipped_quarantined == 1
    assert imp.imported == 1


def test_bundle_provenance_carries_tier_verification_and_attribution(tmp_path):
    run(tmp_path, [(1, "cc-by", "commercial_ok", "page", False)])
    rec = json.loads((tmp_path / "bundle" / "provenance.jsonl").read_text().splitlines()[0])
    assert rec["license_tier"] == "commercial_ok" and rec["license_verified_by"] == "page"
    assert rec["attribution"].startswith("Course 1 by Ada")


def test_a_wrong_declared_license_cannot_override_the_verified_tier(tmp_path):
    # Declared cc-by, but the page check recorded non-commercial: the tier wins.
    _, imp, reasons, _ = run(tmp_path, [(1, "cc-by", "non_commercial", "page", False)])
    assert imp.imported == 0 and imp.rejected_license == 1
    assert any("non-commercial" in r for r in reasons)


def test_unverified_courses_are_held_back_when_publishing_requires_proof(tmp_path):
    rows = [(1, "cc-by", None, None, False), (2, "cc-by", "commercial_ok", "page", False)]
    _, lenient, _, _ = run(tmp_path / "a", rows)
    assert lenient.imported == 2                                        # compatibility default
    _, strict, reasons, _ = run(tmp_path / "b", rows, require_verified=True)
    assert strict.imported == 1 and strict.rejected_license == 1
    assert any("never verified" in r for r in reasons)


def test_share_alike_ships_only_with_the_policy_switch(tmp_path):
    rows = [(1, "cc-by-sa", "share_alike", "page", False)]
    _, off, reasons, _ = run(tmp_path / "off", rows, policy=HarvestPolicy(allow_share_alike=False))
    assert off.imported == 0 and any("share-alike" in r for r in reasons)
    _, default, _, _ = run(tmp_path / "default", rows)                       # ON by default (owner decision)
    assert default.imported == 1
    _, on, _, _ = run(tmp_path / "on", rows, policy=HarvestPolicy(allow_share_alike=True))
    assert on.imported == 1


@pytest.mark.parametrize(
    "lic,kw,ok",
    [
        ("cc-by", {}, True),
        ("cc-by-nc", {}, False),
        ("cc-by-nc", {"require_commercial": False}, True),       # explicit internal-research override
        ("cc-by-nd", {"require_commercial": False}, False),      # we adapt content: ND never passes
        ("oer", {}, False),
        (None, {}, False),
        ("all rights reserved", {"require_commercial": False}, False),
        ("cc-by", {"quarantined": True}, False),
        ("cc-by", {"tier": "non_commercial"}, False),
        ("cc-by", {"tier": "bogus"}, True),                       # unknown tier value falls back to parsing
    ],
)
def test_license_gate_cases(lic, kw, ok):
    assert license_gate(lic, **kw)[0] is ok


def test_old_corpus_without_license_columns_still_exports(tmp_path):
    root = tmp_path / "old"
    (root / "courses").mkdir(parents=True)
    db = root / "corpus.db"
    conn = sqlite3.connect(db)
    conn.executescript("""
      CREATE TABLE sources (url_key TEXT PRIMARY KEY, url TEXT, license TEXT, subject TEXT, title TEXT, source_type TEXT);
      CREATE TABLE courses (course_id TEXT PRIMARY KEY, url_key TEXT, title TEXT, subject TEXT,
                            composition_score INTEGER, json_path TEXT, created_at TEXT);""")
    path = root / "courses" / "c1.course.json"
    path.write_text(json.dumps(course(1)))
    conn.execute("INSERT INTO sources VALUES ('k','https://s.example.net/','cc-by','math','t','html')")
    conn.execute("INSERT INTO courses VALUES ('c1','k','Course 1','math',400,?, '2026-10-24')", (str(path),))
    conn.commit()
    conn.close()
    rep = export_bundle(db, tmp_path / "b", machine="old", repo_root=root)
    assert rep.courses == 1 and rep.skipped_quarantined == 0
