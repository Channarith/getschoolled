"""Audit script and module on a fixture corpus, plus the serving gate."""

import importlib.util
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from aoep_shared.harvest.corpus_store import HarvestCorpusStore
from aoep_shared.harvest.license_audit import (
    BUCKET_OK,
    BUCKET_QUARANTINE,
    BUCKET_REVIEW,
    apply_quarantine,
    audit_db,
    classify_source,
    manifest,
    restore_quarantine,
    scan_course_files,
)
from aoep_shared.harvest.licensing import HarvestPolicy
from aoep_shared.harvest.serving import course_servable
from aoep_shared.harvest.queue import url_key

SCRIPT = Path(__file__).resolve().parents[3] / "scripts" / "harvest_license_audit.py"


def make_db(tmp_path, *, legacy=True):
    """A corpus shaped like the old ones: licenses are whatever the seeds claimed."""
    store = HarvestCorpusStore(tmp_path / "corpus.db")
    rows = [
        ("https://www.coursera.org/browse", "oer"),
        ("https://openstax.org/books/algebra", "cc-by"),                 # seed lied: the book is CC BY-NC-SA
        ("https://see.stanford.edu/Course/CS106A", "cc-by-nc-sa"),
        ("https://open.umn.edu/opentextbooks", "cc-by-nc"),
        ("https://www.nasa.gov/learning-resources/", "public-domain"),    # vetted site
        ("https://data.gov/metrics", "public-domain"),                    # never verified
        ("https://en.wikibooks.org/wiki/Algebra", "cc-by-sa"),
        ("https://example.net/empty", ""),
    ]
    for url, lic in rows:
        store.upsert_source(url=url, license=lic, title=url, subject="math")
        store.index_document(url=url, title=url, text="fractions are parts of a whole " * 8, subject="math")
        store.save_course(course_id="c-" + url_key(url)[:8], url=url, title=url, subject="math")
    store.save_course(course_id="orphan", url="https://nowhere.example/x", title="orphan", subject="math")
    if not legacy:
        return store
    # Make the DB look pre-provenance: no tier, no verification.
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE sources SET license_tier=NULL, license_verified_by=NULL")
    conn.commit()
    conn.close()
    return store


def test_classify_rules():
    def c(url, lic="", **extra):
        return classify_source({"url_key": "k", "url": url, "license": lic, **extra}).bucket

    assert c("https://www.coursera.org/x", "oer") == BUCKET_QUARANTINE
    assert c("https://openstax.org/b", "cc-by") == BUCKET_QUARANTINE          # denylist beats the seed's claim
    assert c("https://x.example.net/a", "cc-by-nc") == BUCKET_QUARANTINE
    assert c("https://x.example.net/a", "cc-by-nd") == BUCKET_QUARANTINE
    assert c("https://x.example.net/a", "all rights reserved") == BUCKET_QUARANTINE
    assert c("https://x.example.net/a", "") == BUCKET_QUARANTINE
    assert c("https://x.example.net/a", "cc-by") == BUCKET_REVIEW             # declared, never verified
    assert c("https://archive.org/details/x", "public-domain") == BUCKET_REVIEW
    assert c("https://www.nasa.gov/x", "public-domain") == BUCKET_OK            # vetted host
    assert c("https://x.example.net/a", "cc-by", license_tier="commercial_ok", license_verified_by="page") == BUCKET_OK
    assert c("https://en.wikibooks.org/x", "cc-by-sa") == BUCKET_QUARANTINE   # share-alike is off
    assert classify_source({"url_key": "k", "url": "https://en.wikibooks.org/x", "license": "cc-by-sa"},
                           HarvestPolicy(allow_share_alike=True)).bucket == BUCKET_OK


def test_audit_counts_sources_courses_and_chunks(tmp_path):
    store = make_db(tmp_path)
    report = audit_db(store.path)
    assert report.sources == 8 and report.courses == 9
    assert report.by_bucket == {BUCKET_QUARANTINE: 6, BUCKET_OK: 1, BUCKET_REVIEW: 1}
    # The orphan course has no source row, so it counts as unproven.
    assert report.courses_by_bucket[BUCKET_QUARANTINE] == 7
    assert report.by_license["oer"] == {BUCKET_QUARANTINE: 1}
    assert report.by_domain["coursera.org"][BUCKET_QUARANTINE] == 1
    text = report.text()
    assert "quarantine" in text and "coursera.org" in text
    assert any(e["url"].endswith("coursera.org/browse") for e in report.examples[BUCKET_QUARANTINE])


def test_audit_is_read_only(tmp_path):
    store = make_db(tmp_path)
    before = store.path.read_bytes()
    audit_db(store.path)
    assert store.path.read_bytes() == before


def test_apply_quarantines_and_restore_undoes_it(tmp_path):
    store = make_db(tmp_path)
    assert store.search("fractions", top_k=50)
    report = audit_db(store.path)
    out = apply_quarantine(store.path, report)
    assert out["sources_quarantined"] == 6 and out["courses_quarantined"] == 7      # 6 + the orphan
    conn = sqlite3.connect(store.path)
    flagged = conn.execute("SELECT url FROM sources WHERE quarantined=1").fetchall()
    assert len(flagged) == 6
    assert conn.execute("SELECT COUNT(*) FROM sources WHERE quarantined=0").fetchone()[0] == 2
    reasons = {r[0] for r in conn.execute("SELECT quarantine_reason FROM sources WHERE quarantined=1")}
    assert all(r.startswith("audit:") for r in reasons)
    # Nothing deleted, and only the two unflagged sources are searchable.
    assert conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0] == 8
    assert conn.execute("SELECT COUNT(*) FROM chunks").fetchone()[0] > 0
    urls = {h.source_url for h in store.search("fractions", top_k=50)}
    assert urls == {"https://www.nasa.gov/learning-resources/", "https://data.gov/metrics"}
    assert restore_quarantine(store.path) == {"sources_restored": 6, "courses_restored": 7}
    assert len({h.source_url for h in store.search("fractions", top_k=50)}) == 8


def test_restore_leaves_manual_quarantines_alone(tmp_path):
    store = make_db(tmp_path)
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE sources SET quarantined=1, quarantine_reason='owner decision' WHERE url LIKE '%data.gov%'")
    conn.commit()
    conn.close()
    apply_quarantine(store.path, audit_db(store.path))
    restore_quarantine(store.path)
    conn = sqlite3.connect(store.path)
    assert conn.execute("SELECT quarantine_reason FROM sources WHERE url LIKE '%data.gov%'").fetchone()[0] == "owner decision"


def test_include_needs_review_quarantines_unverified_sources_too(tmp_path):
    store = make_db(tmp_path)
    report = audit_db(store.path)
    out = apply_quarantine(store.path, report, include=(BUCKET_QUARANTINE, BUCKET_REVIEW))
    assert out["sources_quarantined"] == 7
    m = manifest(report, include=(BUCKET_QUARANTINE, BUCKET_REVIEW))
    assert len(m["sources"]) == 7 and {x["bucket"] for x in m["sources"]} == {BUCKET_QUARANTINE, BUCKET_REVIEW}


def test_new_pipeline_rows_with_proof_are_not_flagged(tmp_path):
    store = make_db(tmp_path, legacy=False)
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE sources SET license='cc-by', license_tier='commercial_ok', license_verified_by='page' "
                 "WHERE url LIKE '%example.net%'")
    conn.commit()
    conn.close()
    report = audit_db(store.path)
    verified = [f for f in report.findings if "example.net" in f.url]
    assert verified and verified[0].bucket == BUCKET_OK


def test_scan_course_files_separates_new_and_old_packages(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.course.json").write_text(json.dumps({"slides": []}))
    (tmp_path / "b").mkdir()
    (tmp_path / "b" / "y.course.json").write_text(json.dumps({"provenance": {"x": 1}, "license_tier": "commercial_ok"}))
    (tmp_path / "b" / "broken.course.json").write_text("{nope")
    store = make_db(tmp_path)
    found = scan_course_files(tmp_path, audit_db(store.path))
    assert found["with_provenance"] == 1 and found["without_provenance"] == 1
    assert found["tiers_with_provenance"] == {"commercial_ok": 1}


def _load_script():
    spec = importlib.util.spec_from_file_location("harvest_license_audit", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    sys.modules["harvest_license_audit"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_script_report_apply_and_restore(tmp_path, capsys):
    store = make_db(tmp_path)
    script = _load_script()
    out = tmp_path / "reports"
    for argv, needle in (
        ([str(store.path), "--out", str(out)], "read-only run; --apply would quarantine 6"),
        ([str(store.path), "--out", str(out), "--apply"], "sources_quarantined"),
        ([str(store.path), "--restore"], "sources_restored"),
    ):
        assert script.main(argv) == 0
        assert needle in capsys.readouterr().out
    files = sorted(p.name for p in out.iterdir())
    assert any(n.startswith("quarantine-manifest-") for n in files)
    assert any(n.startswith("audit-") and n.endswith(".json") for n in files)
    manifest_file = next(out.glob("quarantine-manifest-*.json"))
    assert len(json.loads(manifest_file.read_text())["sources"]) == 6


# ------------------------------------------------------------------ serving gate

@pytest.mark.parametrize(
    "tier,policy,ok",
    [
        ("commercial_ok", HarvestPolicy(), True),
        ("share_alike", HarvestPolicy(), False),
        ("share_alike", HarvestPolicy(allow_share_alike=True), True),
        ("non_commercial", HarvestPolicy(allow_share_alike=True), False),
        ("no_derivatives", HarvestPolicy(), False),
        ("unknown", HarvestPolicy(), False),
        ("proprietary", HarvestPolicy(), False),
    ],
)
def test_course_servable_by_tier(tier, policy, ok):
    data = {"license_tier": tier, "provenance": {"license_tier": tier, "license": {"spdx": "X"}}}
    assert course_servable(data, policy)[0] is ok


def test_courses_without_provenance_are_unverified_not_servable():
    ok, why = course_servable({"title": "old", "slides": []})
    assert not ok and "unverified" in why
    ok, why = course_servable({"provenance": {"x": 1}, "license_tier": "bogus"})
    assert not ok and "unknown license tier" in why
