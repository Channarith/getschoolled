"""Home feed rails, popularity, kids filter, programs audience filter."""

from curriculum.catalog import CatalogStore
from curriculum.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def _seed():
    app.state.catalog = CatalogStore()
    mk = lambda **k: client.post("/courses", json=k).json()["course_id"]  # noqa: E731
    ids = {
        "astro": mk(title="Astronomy 101", category="Science", access_tier="free",
                    maturity_rating="all", duration_min=45, tags=["space"]),
        "py": mk(title="Python Bootcamp", category="Technology", access_tier="pro",
                 maturity_rating="all", hands_on=True, duration_min=120, tags=["python"]),
        "anatomy": mk(title="Human Anatomy", category="Medical", access_tier="premium",
                      maturity_rating="mature", duration_min=110, tags=["anatomy"]),
        "abc": mk(title="ABC Adventures", category="Early Learning", access_tier="free",
                  maturity_rating="kids", duration_min=15, tags=["letters"]),
    }
    return ids


def test_home_rails_structure():
    _seed()
    rails = client.get("/home").json()["rails"]
    keys = {r["key"] for r in rails}
    assert "live" in keys and "audio" in keys and "popular" in keys
    assert any(k.startswith("cat:") for k in keys)
    titles = {c["title"] for r in rails for c in r["courses"]}
    assert "Astronomy 101" in titles
    pop = next(r for r in rails if r["key"] == "popular")
    assert pop["title"] == "Popular now"
    assert "maturity_rating" in pop["courses"][0]


def test_popularity_orders_popular_rail():
    ids = _seed()
    for _ in range(25):
        client.post(f"/courses/{ids['py']}/view")
    rails = client.get("/home").json()["rails"]
    popular = next(r for r in rails if r["key"] == "popular")["courses"]
    titles = [c["title"] for c in popular]
    assert "Python Bootcamp" in titles


def test_view_unknown_course_404():
    _seed()
    assert client.post("/courses/nope/view").status_code == 404


def test_kids_feed_only_kid_rated():
    _seed()
    rails = client.get("/home", params={"kids": "true"}).json()["rails"]
    titles = {c["title"] for r in rails for c in r["courses"]}
    assert "ABC Adventures" in titles          # kids-rated included
    assert "Human Anatomy" not in titles        # mature excluded
    assert "Astronomy 101" not in titles        # general all-ages NOT in kids mode
    assert "Python Bootcamp" not in titles      # general all-ages NOT in kids mode


def test_search_maturity_filter_and_facets():
    _seed()
    kids = client.get("/courses/search", params={"maturity": "kids"}).json()
    assert {c["title"] for c in kids} == {"ABC Adventures"}
    facets = client.get("/courses/facets").json()
    assert "maturity_ratings" in facets and "kids" in facets["maturity_ratings"]
    assert "access_tiers" in facets
    assert "sources" in facets
    assert "lesson" in facets["sources"]


def test_programs_audience_filter():
    _seed()
    client.post("/programs", json={"title": "New Hire Onboarding", "audience": "corporate",
                                   "description": "Enterprise onboarding"})
    client.post("/programs", json={"title": "Grade 9 Science", "audience": "g9"})
    corp = client.get("/programs", params={"audience": "corporate"}).json()
    assert [p["title"] for p in corp] == ["New Hire Onboarding"]
