from fastapi import FastAPI
from fastapi.testclient import TestClient

from theodore_children_webcam_lab.main import VisionStaticFiles


def _client(tmp_path):
    (tmp_path / "face_landmarker.task").write_bytes(b"x" * 64)
    app = FastAPI()
    app.mount("/vendor/vision", VisionStaticFiles(directory=tmp_path), name="v")
    return TestClient(app)


def test_vision_assets_carry_a_cache_policy(tmp_path):
    r = _client(tmp_path).get("/vendor/vision/face_landmarker.task")
    assert r.status_code == 200
    cc = r.headers["cache-control"]
    assert "max-age=86400" in cc and "public" in cc


def test_revalidation_still_works_and_keeps_the_policy(tmp_path):
    c = _client(tmp_path)
    etag = c.get("/vendor/vision/face_landmarker.task").headers["etag"]
    r = c.get("/vendor/vision/face_landmarker.task", headers={"If-None-Match": etag})
    assert r.status_code == 304
    assert "max-age=86400" in r.headers["cache-control"]


def test_missing_file_is_404_without_a_cache_policy(tmp_path):
    r = _client(tmp_path).get("/vendor/vision/nope.task")
    assert r.status_code == 404
    assert "max-age=86400" not in r.headers.get("cache-control", "")


def test_the_folder_urls_are_a_plain_404_not_a_redirect_loop(tmp_path, monkeypatch):
    from theodore_children_webcam_lab import main as m

    (tmp_path / "tasks-vision.mjs").write_text("export{}", encoding="utf-8")
    monkeypatch.setattr(m, "VISION_ASSET_DIR", tmp_path)
    app = FastAPI()
    app.add_api_route("/vendor/vision", lambda: m.Response(status_code=404), include_in_schema=False)
    app.mount("/vendor/vision", VisionStaticFiles(directory=tmp_path), name="v")
    c = TestClient(app, follow_redirects=False)
    assert c.get("/vendor/vision").status_code == 404
    assert c.get("/vendor/vision/").status_code == 404
    assert c.get("/vendor/vision/tasks-vision.mjs").status_code == 200
