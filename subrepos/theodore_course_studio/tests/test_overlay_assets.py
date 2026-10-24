import mimetypes
from pathlib import Path

from fastapi.testclient import TestClient

from theodore_course_studio.main import app

ROOT = Path(__file__).resolve().parents[1]


def test_tutorial_pictures_are_served_as_webp():
    client = TestClient(app)
    for name in ("tutorial-tap.webp", "tutorial-double.webp", "tutorial-dance.webp"):
        r = client.get(f"/api/studio/voice-overlay/{name}")
        assert r.status_code == 200, name
        assert r.headers["content-type"] == "image/webp", name


def test_webp_mime_type_is_registered():
    assert mimetypes.guess_type("x.webp")[0] == "image/webp"


def test_dockerfile_replaces_the_video_symlink_before_copying_the_real_file():
    # The repo stores voice_static/drivers-ed-intro.mp4 as a symlink into apps/web; COPY does not replace a symlink
    # and StaticFiles will not follow it, so the image must remove it first or the video 404s in production.
    text = (ROOT / "Dockerfile").read_text()
    rm = text.index("RUN rm -f /app/src/theodore_course_studio/voice_static/drivers-ed-intro.mp4")
    copy = text.index("COPY apps/web/public/video/drivers-ed-intro.mp4")
    assert rm < copy
