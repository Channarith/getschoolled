"""Fetch hygiene: contact User-Agent, robots.txt, denylist, redirects, login walls, delays."""

import http.server
import threading

import pytest

from aoep_shared.harvest import fetcher
from aoep_shared.harvest.errors import FetchBlocked, HarvestConfigError
from aoep_shared.harvest.sources import SourceSpec
from aoep_shared.harvest.vetted_sources import is_denied, is_per_item_host, registry_summary, vetted_for

GOOD_UA = "TestCrawler/1.0 (+https://salareen.example.net/contact)"


class _Handler(http.server.BaseHTTPRequestHandler):
    robots = "User-agent: *\nDisallow: /private\nCrawl-delay: 3\n"
    robots_status = 200
    hits: list = []

    def log_message(self, *args):  # silence
        pass

    def do_GET(self):
        type(self).hits.append(self.path)
        if self.path == "/robots.txt":
            self.send_response(type(self).robots_status)
            self.end_headers()
            if type(self).robots_status == 200:
                self.wfile.write(type(self).robots.encode())
            return
        if self.path == "/redirect-to-khan":
            self.send_response(302)
            self.send_header("Location", "https://www.khanacademy.org/math")
            self.end_headers()
            return
        if self.path == "/paywalled":
            self.send_response(402)
            self.end_headers()
            return
        if self.path == "/forbidden":
            self.send_response(403)
            self.end_headers()
            return
        body = b"<html><head><title>Hello</title></head><body>hi</body></html>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("X-Robots-Tag", "noai")
        self.end_headers()
        self.wfile.write(body)


@pytest.fixture()
def server(monkeypatch):
    fetcher._ROBOTS.clear()
    fetcher._HOST_LAST.clear()
    _Handler.hits = []
    _Handler.robots_status = 200
    _Handler.robots = "User-agent: *\nDisallow: /private\nCrawl-delay: 3\n"
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    monkeypatch.setenv("HARVEST_USER_AGENT", GOOD_UA)
    slept = []
    monkeypatch.setattr(fetcher.time, "sleep", lambda s: slept.append(s))
    yield f"http://127.0.0.1:{srv.server_port}", slept
    srv.shutdown()


# ------------------------------------------------------------ user agent

@pytest.mark.parametrize(
    "ua",
    [
        "",
        "AOEP-Harvester/1.0",                                   # no contact
        "AOEP-Harvester/1.0 (+contact@example.org)",           # the old placeholder
        "Bot/1.0 (+https://example.com/about)",
    ],
)
def test_crawler_refuses_to_run_without_a_real_contact(monkeypatch, ua):
    monkeypatch.setenv("HARVEST_USER_AGENT", ua)
    monkeypatch.setattr("aoep_shared.config.load_config", lambda: type("C", (), {"harvest_user_agent": ""})())
    with pytest.raises(HarvestConfigError):
        fetcher._user_agent()


def test_contact_forms_that_are_accepted(monkeypatch):
    for ua in (GOOD_UA, "Bot/1.0 (mailto:ops@salareen.com)", "Bot/1.0 (ops@salareen.com)"):
        monkeypatch.setenv("HARVEST_USER_AGENT", ua)
        assert fetcher._user_agent() == ua


def test_fetch_page_does_nothing_when_the_user_agent_is_missing(monkeypatch):
    monkeypatch.delenv("HARVEST_USER_AGENT", raising=False)
    monkeypatch.setattr("aoep_shared.config.load_config", lambda: type("C", (), {"harvest_user_agent": ""})())
    with pytest.raises(HarvestConfigError):
        fetcher.fetch_page(SourceSpec("http://127.0.0.1:9/never"))


# ------------------------------------------------------------ robots.txt

def test_robots_disallow_blocks_without_fetching_the_page(server):
    base, _ = server
    with pytest.raises(FetchBlocked, match="robots.txt disallows"):
        fetcher.fetch_page(SourceSpec(base + "/private/page"))
    assert "/private/page" not in _Handler.hits
    assert "/robots.txt" in _Handler.hits


def test_robots_is_cached_per_host(server):
    base, _ = server
    fetcher.fetch_page(SourceSpec(base + "/a"))
    fetcher.fetch_page(SourceSpec(base + "/b"))
    assert _Handler.hits.count("/robots.txt") == 1


def test_missing_robots_txt_means_no_restrictions(server):
    base, _ = server
    _Handler.robots_status = 404
    res = fetcher.fetch_page(SourceSpec(base + "/private/page"))
    assert res.robots["robots_status"] == "none"


def test_robots_server_error_blocks_the_host(server):
    base, _ = server
    _Handler.robots_status = 503
    with pytest.raises(FetchBlocked, match="could not be read"):
        fetcher.fetch_page(SourceSpec(base + "/a"))


def test_crawl_delay_is_honored_per_host(server):
    base, slept = server
    fetcher.fetch_page(SourceSpec(base + "/a"))
    fetcher.fetch_page(SourceSpec(base + "/b"))
    assert any(s >= 2.5 for s in slept), slept       # robots asked for 3 seconds between requests


def test_fetch_records_headers_and_robots_for_provenance(server):
    base, _ = server
    res = fetcher.fetch_page(SourceSpec(base + "/a"))
    assert res.headers["x-robots-tag"] == "noai"
    assert res.robots["robots_url"].endswith("/robots.txt") and res.robots["allowed"]
    spec = SourceSpec(base + "/c")
    data, st = fetcher.fetch_url(spec)
    assert st == "html" and b"hi" in data and spec.fetch_info["final_url"].endswith("/c")


# ------------------------------------------------------------ blocks

def test_denylisted_hosts_are_never_requested(monkeypatch):
    monkeypatch.setenv("HARVEST_USER_AGENT", GOOD_UA)
    called = []
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", lambda *a, **k: called.append(a))
    for url in ("https://www.khanacademy.org/math", "https://www.udemy.com/course/x", "https://ck12.org/book/x",
                "https://www.coursera.org/learn/x", "https://www.youtube.com/watch?v=1", "https://arxiv.org/abs/1",
                "https://www.edx.org/learn/x", "https://www.linkedin.com/learning/x"):
        with pytest.raises(FetchBlocked, match="do-not-harvest"):
            fetcher.fetch_page(SourceSpec(url))
    assert called == []


def test_login_and_paywall_urls_are_refused(monkeypatch):
    monkeypatch.setenv("HARVEST_USER_AGENT", GOOD_UA)
    monkeypatch.setattr(fetcher.urllib.request, "urlopen", lambda *a, **k: pytest.fail("must not fetch"))
    for url in ("https://x.example.net/login", "https://x.example.net/account/login?next=/a",
                "https://x.example.net/users/sign_in", "https://x.example.net/subscribe"):
        with pytest.raises(FetchBlocked, match="login or paywall"):
            fetcher.fetch_page(SourceSpec(url))


def test_http_401_402_403_are_treated_as_walls(server):
    base, _ = server
    for path in ("/paywalled", "/forbidden"):
        with pytest.raises(FetchBlocked, match="login wall"):
            fetcher.fetch_page(SourceSpec(base + path))


def test_redirect_into_a_denied_host_is_blocked(server):
    base, _ = server
    with pytest.raises(FetchBlocked, match="do-not-harvest"):
        fetcher.fetch_page(SourceSpec(base + "/redirect-to-khan"))


def test_non_http_urls_are_unsupported(monkeypatch):
    monkeypatch.setenv("HARVEST_USER_AGENT", GOOD_UA)
    with pytest.raises(FetchBlocked, match="unsupported"):
        fetcher.fetch_page(SourceSpec("file:///etc/passwd"))


def test_extract_links_skips_denied_and_login_links():
    html = ('<a href="/lesson/1">a</a><a href="/login">b</a><a href="https://www.khanacademy.org/x">c</a>'
            '<a href="https://sub.nasa.gov/p">d</a>')
    links = fetcher.extract_links(html, base_url="https://www.nasa.gov/start")
    assert links == ["https://www.nasa.gov/lesson/1", "https://sub.nasa.gov/p"]


# ------------------------------------------------------------ registry

def test_denylist_matches_subdomains_but_not_lookalikes():
    assert is_denied("https://www.khanacademy.org/x") and is_denied("https://sub.khanacademy.org/x")
    assert is_denied("youtu.be") and is_denied("https://www.coursera.org/") and is_denied("https://ck12.org/b")
    # Non-commercial but lawful to read: NOT denied. The page check sends them to the research corpus.
    assert not is_denied("https://openstax.org/details/books") and not is_denied("https://ocw.mit.edu/courses")
    assert not is_denied("https://notkhanacademy.org/") and not is_denied("https://mit.edu/")
    assert not is_denied("u1")           # opaque test ids are not hosts


def test_vetted_sources_and_path_exclusions():
    assert vetted_for("https://en.wikipedia.org/wiki/Egypt").info().tier.value == "share_alike"
    assert vetted_for("https://www.gutenberg.org/ebooks/1").info().family == "pd"
    assert vetted_for("https://medlineplus.gov/diabetes.html") is not None
    assert vetted_for("https://medlineplus.gov/ency/article/000001.htm") is None     # A.D.A.M., copyrighted
    assert vetted_for("https://example.net/x") is None
    # Site-wide trust is NOT granted to per-item hosts.
    assert vetted_for("https://chem.libretexts.org/x") is None and is_per_item_host("https://chem.libretexts.org/x")
    assert is_per_item_host("https://archive.org/details/x") and is_per_item_host("https://www.oercommons.org/x")


def test_registry_never_vets_a_denied_host():
    summary = registry_summary()
    assert not set(summary["vetted"]) & set(summary["denied"])
    assert not set(summary["per_item"]) & set(summary["denied"])
    from aoep_shared.harvest.vetted_sources import RESEARCH_EXPECTED

    expected = {d.domain for d in RESEARCH_EXPECTED}
    assert {"openstax.org", "ocw.mit.edu"} <= expected
    assert not expected & set(summary["denied"]) and not expected & set(summary["vetted"])
