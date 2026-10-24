"""Crawler end to end with a fake network: what gets ingested, rejected, recorded and credited."""
# ruff: noqa: E402

import json
import sqlite3

import pytest

pytest.importorskip("pptx")

from aoep_shared.harvest import crawl as crawl_mod
from aoep_shared.harvest.corpus_store import HarvestCorpusStore, migrate_schema
from aoep_shared.harvest.crawl import open_crawl_session
from aoep_shared.harvest.errors import HarvestConfigError
from aoep_shared.harvest.licensing import HarvestPolicy
from aoep_shared.harvest.provenance import CREDITS_SLIDE_TITLE
from aoep_shared.harvest.serving import course_servable
from aoep_shared.harvest.sources import SourceSpec

BODY = """<h1>Fractions</h1><p>A fraction names a part of a whole. The numerator counts the parts we have.
The denominator tells how many equal parts make the whole. Fractions can be compared by finding a common
denominator, which is the same number of equal parts for both fractions {n}.</p>
<h2>Adding fractions</h2><p>To add fractions with the same denominator, add the numerators and keep the
denominator. For example one quarter plus two quarters is three quarters.</p>
<h2>Why it matters</h2><p>Cooking, building and sharing all use fractions every day.</p>"""


def page(n, license_url=None, head="", footer=""):
    link = f'<link rel="license" href="{license_url}">' if license_url else ""
    return (f'<html><head><title>Fractions {n}</title>{link}<meta name="author" content="Ada Teacher">{head}'
            f"</head><body>{BODY.format(n=n)}<footer>{footer}</footer></body></html>")


BY = "https://creativecommons.org/licenses/by/4.0/"
BY_SA = "https://creativecommons.org/licenses/by-sa/4.0/"
BY_NC = "https://creativecommons.org/licenses/by-nc-sa/4.0/"


@pytest.fixture()
def net(monkeypatch):
    pages: dict = {}
    fetched: list = []

    def fake_fetch(spec):
        fetched.append(spec.url)
        spec.fetch_info = {"final_url": spec.url, "headers": {}, "fetched_at": "2026-10-24T00:00:00+00:00",
                           "robots": {"allowed": True, "robots_status": "none", "robots_url": spec.url + "/robots.txt"}}
        return pages[spec.url].encode(), "html"

    monkeypatch.setattr(crawl_mod, "fetch_url", fake_fetch)
    return pages, fetched


def session(tmp_path, policy=None):
    s = open_crawl_session(out_dir=tmp_path, repo_root=tmp_path, with_media=False, policy=policy or HarvestPolicy())
    s.expand_links = False
    return s


def statuses(s):
    conn = s.corpus._connect()
    try:
        return {r["url"]: dict(r) for r in conn.execute("SELECT * FROM sources")}
    finally:
        conn.close()


def test_only_pages_that_prove_a_commercial_license_become_courses(tmp_path, net):
    pages, fetched = net
    pages.update({
        "https://good.example.net/a": page(1, BY),
        "https://nc.example.net/a": page(2, BY_NC),
        "https://none.example.net/a": page(3),
        "https://sa.example.net/a": page(4, BY_SA),
        "https://liar.example.net/a": page(5, BY_NC),
        "https://nd.example.net/a": page(6, "https://creativecommons.org/licenses/by-nd/4.0/"),
        "https://arr.example.net/a": page(7, footer="All rights reserved."),
    })
    s = session(tmp_path)
    s.enqueue_seeds([
        SourceSpec("https://good.example.net/a", subject="math"),
        SourceSpec("https://nc.example.net/a", subject="math"),
        SourceSpec("https://none.example.net/a", subject="math"),
        SourceSpec("https://sa.example.net/a", subject="math"),
        SourceSpec("https://liar.example.net/a", license="cc-by", subject="math"),     # seed lies, page says NC
        SourceSpec("https://nd.example.net/a", subject="math"),
        SourceSpec("https://arr.example.net/a", subject="math"),
        SourceSpec("https://www.khanacademy.org/x", license="cc-by", subject="math"),  # denied: never fetched
    ])
    metrics = s.run_once(max_items=20)
    rows = statuses(s)
    assert rows["https://good.example.net/a"]["status"] == "ingested"
    # Non-commercial and share-alike (switch off) are lawful to read: research corpus, never the product.
    for url in ("nc", "sa"):
        assert rows[f"https://{url}.example.net/a"]["status"] == "diverted_research"
    # Rejected outright: unknown, conflicting, no-derivatives, all rights reserved.
    for url in ("none", "liar", "nd", "arr"):
        assert rows[f"https://{url}.example.net/a"]["status"] == "rejected_license", url
    assert "https://www.khanacademy.org/x" not in fetched
    assert metrics.generated == 1 and metrics.research_diverted == 2 and metrics.skipped_license == 5
    # The product corpus holds text for the good page only; the research corpus holds the other two, nowhere else.
    def urls_with_chunks(store):
        conn = store._connect()
        try:
            return {r[0] for r in conn.execute(
                "SELECT s.url FROM chunks c JOIN sources s ON s.url_key=c.url_key GROUP BY s.url")}
        finally:
            conn.close()

    assert urls_with_chunks(s.corpus) == {"https://good.example.net/a"}
    assert urls_with_chunks(s.research_corpus) == {"https://nc.example.net/a", "https://sa.example.net/a"}
    assert s.research_corpus.path != s.corpus.path


def test_provenance_is_recorded_in_db_course_json_and_attribution_file(tmp_path, net):
    pages, _ = net
    pages["https://good.example.net/a"] = page(1, BY)
    s = session(tmp_path)
    s.enqueue_seeds([SourceSpec("https://good.example.net/a", subject="math")])
    s.run_once(max_items=5)
    src = statuses(s)["https://good.example.net/a"]
    assert (src["license_tier"], src["license_id"], src["license_verified_by"]) == ("commercial_ok", "CC-BY-4.0", "page")
    prov = json.loads(src["provenance_json"])
    assert prov["corpus"] == "product"
    assert prov["content_hash"] and prov["fetched_at"] and prov["robots"]["robots_status"] == "none"
    assert prov["attribution"]["author"] == "Ada Teacher"
    assert prov["recipe"]["pipeline"].startswith("aoep.harvest")
    pkg = next((tmp_path / "courses").glob("*/*.course.json"))
    course = json.loads(pkg.read_text())
    assert course["corpus"] == "product"
    assert course["license_tier"] == "commercial_ok" and "Ada Teacher" in course["attribution"]
    assert course["slides"][-1]["title"] == CREDITS_SLIDE_TITLE
    assert "CC-BY-4.0" in course["slides"][-1]["body"]
    credit = (pkg.parent / "ATTRIBUTION.txt").read_text()
    assert "Ada Teacher" in credit and "attribution" in credit.lower() and prov["content_hash"] in credit
    assert "Corpus: product" in credit
    ok, why = course_servable(course)
    assert ok, why
    row = sqlite3.connect(s.corpus.path).execute("SELECT license_tier FROM courses").fetchone()
    assert row[0] == "commercial_ok"


def test_share_alike_is_product_only_with_the_switch_and_carries_obligations(tmp_path, net):
    pages, _ = net
    pages["https://sa.example.net/a"] = page(1, BY_SA)
    off = session(tmp_path / "off")
    off.enqueue_seeds([SourceSpec("https://sa.example.net/a", subject="math")])
    off.run_once(max_items=5)
    assert statuses(off)["https://sa.example.net/a"]["status"] == "diverted_research"
    assert not list((tmp_path / "off" / "courses").glob("*/*"))               # no course from it
    on = session(tmp_path / "on", HarvestPolicy(allow_share_alike=True))
    on.enqueue_seeds([SourceSpec("https://sa.example.net/a", subject="math")])
    on.run_once(max_items=5)
    assert statuses(on)["https://sa.example.net/a"]["status"] == "ingested"
    course = json.loads(next((tmp_path / "on" / "courses").glob("*/*.course.json")).read_text())
    assert course["license_tier"] == "share_alike" and course["corpus"] == "product"
    assert any("share-alike" in o for o in course["license_obligations"])
    assert "same license" in course["attribution"]
    assert course_servable(course, HarvestPolicy(allow_share_alike=True))[0]
    assert not course_servable(course, HarvestPolicy())[0]


def test_non_commercial_text_lands_only_in_the_research_corpus_and_is_marked(tmp_path, net):
    pages, _ = net
    pages["https://nc.example.net/a"] = page(1, BY_NC)
    s = session(tmp_path)
    s.enqueue_seeds([SourceSpec("https://nc.example.net/a", subject="math")])
    s.run_once(max_items=5)
    assert statuses(s)["https://nc.example.net/a"]["status"] == "diverted_research"
    assert not s.corpus.search("fractions")                       # the product corpus never sees the text
    assert s.research_corpus.role == "research" and s.corpus.role == "product"
    hits = s.research_corpus.search("fractions", internal_use=True)
    assert hits and hits[0].meta.get("corpus") == "research" and hits[0].meta.get("internal_only") is True
    assert not list((tmp_path / "courses").glob("*/*"))           # nothing is exported or turned into a course
    manifest = s.research_corpus.training_manifest()
    assert len(manifest) == 1 and manifest[0]["corpus"] == "research" and manifest[0]["license_tier"] == "non_commercial"
    assert manifest[0]["content_hash"] and manifest[0]["chunks"] > 0


def test_research_corpus_is_on_by_default_and_can_be_switched_off(tmp_path, net):
    assert session(tmp_path / "on").research_corpus is not None
    off = session(tmp_path / "off", HarvestPolicy(research_enabled=False))
    assert off.research_corpus is None
    pages, _ = net
    pages["https://nc.example.net/a"] = page(1, BY_NC)
    off.enqueue_seeds([SourceSpec("https://nc.example.net/a", subject="math")])
    m = off.run_once(max_items=5)
    assert statuses(off)["https://nc.example.net/a"]["status"] == "rejected_license"
    assert m.research_diverted == 0


def test_children_of_a_page_do_not_inherit_its_license(tmp_path, net):
    pages, _ = net
    parent = page(1, BY, footer="").replace("</body>", '<a href="/child">next</a></body>')
    pages["https://good.example.net/a"] = parent
    pages["https://good.example.net/child"] = page(2)      # child has no license of its own
    s = session(tmp_path)
    s.expand_links = True
    s.enqueue_seeds([SourceSpec("https://good.example.net/a", license="cc-by", subject="math")])
    s.run_once(max_items=1)
    queued = s.queue.dequeue()
    assert queued is not None and queued.url.endswith("/child")
    assert queued.license is None and queued.meta["parent_license"] == "cc-by"
    s.queue.enqueue(queued)
    s.run_once(max_items=5)
    assert statuses(s)["https://good.example.net/child"]["status"] == "rejected_license"


def test_blocked_fetch_is_a_policy_skip_not_an_error(tmp_path, monkeypatch):
    from aoep_shared.harvest.errors import FetchBlocked

    def blocked(spec):
        raise FetchBlocked("robots.txt disallows")

    monkeypatch.setattr(crawl_mod, "fetch_url", blocked)
    s = session(tmp_path)
    s.enqueue_seeds([SourceSpec("https://x.example.net/a")])
    m = s.run_once(max_items=5)
    assert m.errors == 0


def test_missing_user_agent_stops_the_crawl_instead_of_counting_an_error(tmp_path, monkeypatch):
    def no_contact(spec):
        raise HarvestConfigError("HARVEST_USER_AGENT must name a real contact")

    monkeypatch.setattr(crawl_mod, "fetch_url", no_contact)
    s = session(tmp_path)
    s.enqueue_seeds([SourceSpec("https://x.example.net/a")])
    with pytest.raises(HarvestConfigError):
        s.run_once(max_items=5)


def test_non_html_sources_need_a_vetted_site_or_verified_seed(tmp_path):
    s = session(tmp_path)
    pdf = SourceSpec("https://x.example.net/doc.pdf", license="cc-by", source_type="pdf")
    ver, scan = s._verify(pdf, b"%PDF")
    assert not ver.decision.ingest and "non-HTML" in ver.decision.reason and scan is None
    verified = SourceSpec("https://x.example.net/doc.pdf", license="cc-by", source_type="pdf",
                          license_verified_by="ana", license_verified_at="2026-10-24",
                          license_evidence="https://x.example.net/terms")
    ver, _ = s._verify(verified, b"%PDF")
    assert ver.decision.ingest and ver.verified_by == "seed"
    vetted = SourceSpec("https://www.census.gov/x.pdf", license="public-domain", source_type="pdf")
    ver, _ = s._verify(vetted, b"%PDF")
    assert ver.decision.ingest and ver.verified_by == "vetted-site"


# ---------------------------------------------------------------- corpus store

def test_old_corpus_databases_are_migrated_in_place_without_losing_rows(tmp_path):
    path = tmp_path / "old.db"
    old = sqlite3.connect(path)
    old.executescript("""
        CREATE TABLE corpus_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
        CREATE TABLE sources (url_key TEXT PRIMARY KEY, url TEXT NOT NULL, license TEXT, subject TEXT, title TEXT,
            source_type TEXT, content_hash TEXT, status TEXT DEFAULT 'fetched', fetched_at TEXT, meta_json TEXT DEFAULT '{}');
        CREATE TABLE courses (course_id TEXT PRIMARY KEY, url_key TEXT, title TEXT NOT NULL, subject TEXT,
            composition_score INTEGER DEFAULT 0, json_path TEXT, pptx_path TEXT, theme_json TEXT DEFAULT '{}',
            media_json TEXT DEFAULT '{}', tags_json TEXT DEFAULT '{}', created_at TEXT NOT NULL);
        INSERT INTO corpus_meta VALUES('schema_version','1');
        INSERT INTO sources(url_key,url,license,title) VALUES('k1','https://old.example/a','cc-by-nc','Old');
    """)
    old.commit()
    old.close()
    store = HarvestCorpusStore(path)
    conn = sqlite3.connect(path)
    cols = {r[1] for r in conn.execute("PRAGMA table_info(sources)")}
    assert {"quarantined", "license_tier", "provenance_json", "attribution_json"} <= cols
    assert conn.execute("SELECT url, license, quarantined FROM sources").fetchall() == [("https://old.example/a", "cc-by-nc", 0)]
    assert conn.execute("SELECT value FROM corpus_meta WHERE key='schema_version'").fetchone()[0] == "2"
    migrate_schema(conn)          # idempotent
    conn.commit()
    assert store.stats()["sources"] == 1


def test_quarantined_sources_drop_out_of_retrieval(tmp_path):
    store = HarvestCorpusStore(tmp_path / "c.db")
    store.upsert_source(url="https://x.example.net/a", license="cc-by", title="A")
    store.index_document(url="https://x.example.net/a", title="A", text="fractions are parts of a whole " * 6, subject="math")
    assert store.search("fractions")
    conn = sqlite3.connect(store.path)
    conn.execute("UPDATE sources SET quarantined=1")
    conn.commit()
    assert store.search("fractions") == []
    assert store.search("parts of a whole") == []        # the LIKE fallback is filtered too
