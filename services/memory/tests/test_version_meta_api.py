"""Standard /version + /__meta endpoints (provided by create_service)."""

from fastapi.testclient import TestClient
from memory.main import app

client = TestClient(app)


def test_version_endpoint():
    body = client.get("/version").json()
    assert body["service"] == "memory"
    assert body["version"]
    assert body["api_version"] == "1"
    assert "git_sha" in body and "build_time" in body


def test_health_includes_version():
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["version"]


def test_meta_lists_routes_for_automation():
    body = client.get("/__meta").json()
    assert body["service"] == "memory"
    assert body["route_count"] >= 1
    paths = {r["path"] for r in body["routes"]}
    # A few known memory routes should be discoverable.
    assert "/flags/evaluate" in paths
    assert "/survey/post-class" in paths
    assert "/version" in paths
    # Each route entry has methods.
    sample = body["routes"][0]
    assert "methods" in sample and isinstance(sample["methods"], list)
