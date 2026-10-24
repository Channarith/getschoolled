"""The hard wall between the PRODUCT corpus (publishable) and the RESEARCH corpus (internal only)."""

import json
import sqlite3

import pytest

from aoep_shared.harvest.bundle import export_bundle, import_bundle, open_index
from aoep_shared.harvest.corpus_store import HarvestCorpusStore, default_research_corpus_path
from aoep_shared.harvest.crawl import open_crawl_session
from aoep_shared.harvest.errors import CorpusWallError
from aoep_shared.harvest.license_audit import audit_db, migrate_to_research
from aoep_shared.harvest.licensing import HarvestPolicy, assert_product_safe
from aoep_shared.harvest.objectstore import LocalObjectStore, pack_course
from aoep_shared.harvest.publish import PublishConfig, Publisher

TEXT = "fractions are parts of a whole " * 8


def prov(tier, spdx, corpus=None, verified="page"):
    p = {"license": {"tier": tier, "spdx": spdx, "evidence": "x"}, "license_verified_by": verified,
         "attribution": {"text": f"credit for {spdx}"}}
    if corpus:
        p["corpus"] = corpus
    return p


# ------------------------------------------------------------------ the product side

def test_product_corpus_refuses_non_product_text_and_courses(tmp_path):
    s = HarvestCorpusStore(tmp_path / "p.db", role="product")
    s.upsert_source(url="https://nc.example.net/a", license="cc-by-nc", status="diverted_research",
                    provenance=prov("non_commercial", "CC-BY-NC-4.0"))       # metadata row only: allowed
    with pytest.raises(CorpusWallError, match="non_commercial"):
        s.index_document(url="https://nc.example.net/a", title="A", text=TEXT)
    with pytest.raises(CorpusWallError, match="course"):
        s.save_course(course_id="c1", url="https://nc.example.net/a", title="A", subject="math")
    with pytest.raises(CorpusWallError):
        s.upsert_source(url="https://nc.example.net/b", license="cc-by-nc", status="ingested",
                        provenance=prov("non_commercial", "CC-BY-NC-4.0"))
    for tier in ("no_derivatives", "proprietary"):
        with pytest.raises(CorpusWallError):
            s.upsert_source(url=f"https://{tier}.example.net/", status="ingested", provenance=prov(tier, "X"))
    assert s.stats()["chunks"] == 0 and s.stats()["courses"] == 0


def test_product_corpus_takes_share_alike_only_with_the_switch(tmp_path):
    sa = prov("share_alike", "CC-BY-SA-4.0")
    off = HarvestCorpusStore(tmp_path / "off.db", role="product", policy=HarvestPolicy(allow_share_alike=False))
    with pytest.raises(CorpusWallError, match="share_alike"):
        off.upsert_source(url="https://sa.example.net/", status="ingested", provenance=sa)
    on = HarvestCorpusStore(tmp_path / "on.db", role="product", policy=HarvestPolicy(allow_share_alike=True))
    on.upsert_source(url="https://sa.example.net/", status="ingested", provenance=sa)
    assert on.index_document(url="https://sa.example.net/", title="A", text=TEXT) > 0
    default = HarvestCorpusStore(tmp_path / "default.db", role="product", policy=HarvestPolicy())   # ON by default
    default.upsert_source(url="https://sa.example.net/", status="ingested", provenance=sa)


def test_product_corpus_accepts_commercial_text_and_legacy_rows_without_a_tier(tmp_path):
    s = HarvestCorpusStore(tmp_path / "p.db")
    s.upsert_source(url="https://ok.example.net/", license="cc-by", status="ingested",
                    provenance=prov("commercial_ok", "CC-BY-4.0"))
    assert s.index_document(url="https://ok.example.net/", title="A", text=TEXT) > 0
    s.upsert_source(url="https://legacy.example.net/", license="cc-by")          # no provenance, no tier
    assert s.index_document(url="https://legacy.example.net/", title="A", text=TEXT) > 0
    assert s.role == "product"


# ------------------------------------------------------------------ the research side

def test_research_corpus_holds_text_only_and_only_non_product_tiers(tmp_path):
    r = HarvestCorpusStore(tmp_path / "r.db", role="research")
    r.upsert_source(url="https://nc.example.net/a", license="cc-by-nc", status="research",
                    provenance=prov("non_commercial", "CC-BY-NC-4.0"))
    assert r.index_document(url="https://nc.example.net/a", title="A", text=TEXT) > 0
    with pytest.raises(CorpusWallError, match="never courses"):
        r.save_course(course_id="c1", url="https://nc.example.net/a", title="A", subject="math")
    with pytest.raises(CorpusWallError, match="product corpus"):                  # product-safe belongs on the other side
        r.upsert_source(url="https://by.example.net/", status="research", provenance=prov("commercial_ok", "CC-BY-4.0"))
    with pytest.raises(CorpusWallError, match="verified license tier"):
        r.upsert_source(url="https://noprov.example.net/", status="research")
    with pytest.raises(CorpusWallError):
        r.index_document(url="https://never-registered.example.net/", title="A", text=TEXT)


def test_research_corpus_cannot_be_searched_from_a_product_path(tmp_path):
    r = HarvestCorpusStore(tmp_path / "r.db", role="research")
    r.upsert_source(url="https://nc.example.net/a", status="research", provenance=prov("non_commercial", "CC-BY-NC-4.0"))
    r.index_document(url="https://nc.example.net/a", title="A", text=TEXT)
    with pytest.raises(CorpusWallError, match="internal"):
        r.search("fractions")
    assert r.search("fractions", internal_use=True)


def test_the_role_is_stamped_into_the_file(tmp_path):
    HarvestCorpusStore(tmp_path / "r.db", role="research")
    with pytest.raises(CorpusWallError, match="research corpus"):
        HarvestCorpusStore(tmp_path / "r.db", role="product")                    # cannot be opened as the product corpus
    assert HarvestCorpusStore(tmp_path / "r.db").role == "research"             # reopening adopts the stored role
    HarvestCorpusStore(tmp_path / "p.db", role="product")
    with pytest.raises(CorpusWallError):
        HarvestCorpusStore(tmp_path / "p.db", role="research")
    with pytest.raises(ValueError):
        HarvestCorpusStore(tmp_path / "x.db", role="whatever")


def test_databases_from_before_the_wall_are_product_databases(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE corpus_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources (url_key TEXT PRIMARY KEY, url TEXT NOT NULL, license TEXT, subject TEXT, title TEXT,
            source_type TEXT, content_hash TEXT, status TEXT DEFAULT 'fetched', fetched_at TEXT, meta_json TEXT DEFAULT '{}');
        CREATE TABLE courses (course_id TEXT PRIMARY KEY, url_key TEXT, title TEXT NOT NULL, subject TEXT,
            composition_score INTEGER DEFAULT 0, json_path TEXT, pptx_path TEXT, theme_json TEXT DEFAULT '{}',
            media_json TEXT DEFAULT '{}', tags_json TEXT DEFAULT '{}', created_at TEXT NOT NULL);
        INSERT INTO corpus_meta VALUES('schema_version','1');""")
    old.commit()
    old.close()
    assert HarvestCorpusStore(path).role == "product"


def test_crawl_session_uses_two_different_files_and_refuses_to_share_one(tmp_path, monkeypatch):
    s = open_crawl_session(out_dir=tmp_path, repo_root=tmp_path, with_media=False, policy=HarvestPolicy())
    assert s.corpus.path != s.research_corpus.path
    assert (s.corpus.role, s.research_corpus.role) == ("product", "research")
    monkeypatch.setenv("AOEP_HARVEST_RESEARCH_DB", str(tmp_path / "harvest_corpus.db"))
    with pytest.raises(CorpusWallError, match="different file"):
        open_crawl_session(out_dir=tmp_path, repo_root=tmp_path, with_media=False, policy=HarvestPolicy())


def test_default_research_path_is_separate_and_overridable(monkeypatch, tmp_path):
    monkeypatch.delenv("AOEP_HARVEST_RESEARCH_DB", raising=False)
    assert default_research_corpus_path().name == "harvest_research_corpus.db"
    monkeypatch.setenv("AOEP_HARVEST_RESEARCH_DB", str(tmp_path / "r.db"))
    assert default_research_corpus_path() == tmp_path / "r.db"


# ------------------------------------------------------------------ publish-time assertions

@pytest.mark.parametrize(
    "kw,ok",
    [
        ({"tier": "commercial_ok"}, True),
        ({"license": "cc-by"}, True),
        ({"tier": "share_alike", "policy": HarvestPolicy(allow_share_alike=False)}, False),
        ({"tier": "share_alike"}, True),                                    # share-alike is ON by default
        ({"tier": "non_commercial"}, False),
        ({"license": "cc-by-nc"}, False),
        ({"tier": "commercial_ok", "corpus": "research"}, False),        # the corpus alone is enough
        ({"license": "oer"}, False),
        ({"license": None}, False),
        ({"tier": "bogus", "license": "cc-by-nc"}, False),
    ],
)
def test_assert_product_safe(kw, ok):
    if ok:
        assert_product_safe(**kw)
    else:
        with pytest.raises(CorpusWallError):
            assert_product_safe(**kw)


def test_assert_product_safe_share_alike_follows_the_policy():
    assert_product_safe(tier="share_alike", policy=HarvestPolicy(allow_share_alike=True))
    with pytest.raises(CorpusWallError):
        assert_product_safe(tier="share_alike", policy=HarvestPolicy(allow_share_alike=False))


def make_course(n):
    return {"course_id": f"c{n}", "title": f"Course {n}", "subject": "math", "language": "en",
            "slides": [{"title": f"s{i}", "body": f"Fractions {n} {i} " * 20, "narration": "x"} for i in range(3)]}


def test_a_research_corpus_cannot_be_exported_or_bundled(tmp_path):
    r = HarvestCorpusStore(tmp_path / "r.db", role="research")
    with pytest.raises(CorpusWallError, match="research corpus"):
        export_bundle(r.path, tmp_path / "bundle", machine="m", repo_root=tmp_path)
    assert not (tmp_path / "bundle").exists()


def test_the_product_index_cannot_be_opened_to_non_commercial_courses(tmp_path):
    idx = open_index(tmp_path / "idx.db")
    store = LocalObjectStore(tmp_path / "store")
    with pytest.raises(CorpusWallError, match="research corpus"):
        import_bundle(tmp_path / "nowhere", store, idx, require_commercial=False)


def _bundle_with(tmp_path, rec_extra):
    sha, gz = pack_course(make_course(1))
    b = tmp_path / "bundle"
    obj = b / "courses" / sha[:2] / f"{sha}.json.gz"
    obj.parent.mkdir(parents=True)
    obj.write_bytes(gz)
    (b / "manifest.jsonl").write_text(json.dumps({"sha256": sha, "bytes": len(gz)}) + "\n")
    rec = {"course_id": "c1", "sha256": sha, "title": "Course 1", "subject": "math", "language": "en", "slides": 3,
           "source_url": "https://x.example.net/", "license": "cc-by", "machine": "m", "harvested_at": "2026-10-24",
           **rec_extra}
    (b / "provenance.jsonl").write_text(json.dumps(rec) + "\n")
    import hashlib

    header = {"format": 1, "machine": "m", "created_utc": "2026-10-24", "courses": 1, "objects": 1,
              "manifest_sha256": hashlib.sha256((b / "manifest.jsonl").read_bytes()).hexdigest(),
              "provenance_sha256": hashlib.sha256((b / "provenance.jsonl").read_bytes()).hexdigest()}
    (b / "bundle.json").write_text(json.dumps(header))
    return b, sha


def test_research_marked_records_are_rejected_at_import_even_with_a_commercial_looking_license(tmp_path):
    b, _ = _bundle_with(tmp_path, {"corpus": "research"})
    idx = open_index(tmp_path / "idx.db")
    rep = import_bundle(b, LocalObjectStore(tmp_path / "store"), idx)
    assert rep.imported == 0 and rep.rejected_license == 1
    assert "research-corpus" in idx.execute("SELECT reason FROM rejected").fetchone()[0]


def test_publisher_re_asserts_the_wall_on_every_row(tmp_path):
    idx = open_index(tmp_path / "idx.db")
    store = LocalObjectStore(tmp_path / "store")
    published = []

    class Sink:
        def exists(self, sha):
            return False

        def publish(self, sha, payload):
            published.append(payload)

    good_sha, good_gz = pack_course(make_course(1))
    bad_sha, bad_gz = pack_course(make_course(2))
    for sha, gz in ((good_sha, good_gz), (bad_sha, bad_gz)):
        store.put(f"courses/{sha[:2]}/{sha}.json.gz", gz)
    cols = ("sha256,course_id,title,subject,language,slides,source_url,license,machine,tier,imported_at,"
            "license_tier,corpus")
    idx.execute(f"INSERT INTO courses ({cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (good_sha, "c1", "Course 1", "math", "en", 3, "https://ok/", "cc-by", "m", 1, "now", "commercial_ok", "product"))
    # A row that should never exist (e.g. a hand-edited index): declared cc-by but tier says non-commercial.
    idx.execute(f"INSERT INTO courses ({cols}) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (bad_sha, "c2", "Course 2", "math", "en", 3, "https://nc/", "cc-by", "m", 1, "now", "non_commercial", "product"))
    idx.commit()
    rep = Publisher(idx, store, Sink(), cfg=PublishConfig(check_existing=False, rate_per_sec=1000, burst=1000)).run()
    assert rep.published == 1 and rep.wall_blocked == 1 and rep.failed_permanent == 1
    assert len(published) == 1 and "corpus:product" in published[0]["tags"] and "license:commercial_ok" in published[0]["tags"]
    reason = idx.execute("SELECT reason FROM publish_failures WHERE sha256=?", (bad_sha,)).fetchone()[0]
    assert reason.startswith("wall:")


# ------------------------------------------------------------------ audit migration

def test_migrate_to_research_copies_only_eligible_text_and_leaves_the_product_db_alone(tmp_path):
    store = HarvestCorpusStore(tmp_path / "product.db")
    rows = [
        ("https://see.stanford.edu/Course/CS106A", "cc-by-nc-sa"),     # NC, lawful to read: migrates
        ("https://openstax.org/books/algebra", "cc-by"),               # known NC host, wrong claim: migrates
        ("https://www.coursera.org/browse", "oer"),                    # never harvest: stays out
        ("https://x.example.net/arr", "all rights reserved"),          # not lawful to reuse: stays out
        ("https://www.nasa.gov/x", "public-domain"),                   # product-safe: stays in product
    ]
    for url, lic in rows:
        store.upsert_source(url=url, license=lic, title=url)
        store.index_document(url=url, title=url, text=TEXT)
    before = store.path.read_bytes()
    report = audit_db(store.path)
    out = migrate_to_research(store.path, tmp_path / "research.db", report)
    assert out["sources_copied"] == 2 and out["chunks_written"] > 0
    assert store.path.read_bytes() == before                           # product db untouched
    r = HarvestCorpusStore(tmp_path / "research.db")
    assert r.role == "research"
    manifest = r.training_manifest()
    assert {m["url"] for m in manifest} == {"https://see.stanford.edu/Course/CS106A", "https://openstax.org/books/algebra"}
    assert all(m["corpus"] == "research" and m["license_tier"] == "non_commercial"
               and m["license_verified_by"] == "legacy-declared (unverified)" for m in manifest)
    assert not r.stats()["courses"]
