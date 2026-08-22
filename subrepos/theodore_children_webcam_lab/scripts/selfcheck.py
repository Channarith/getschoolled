"""Offline self-check for the children webcam lab."""

from __future__ import annotations

import json

from fastapi.testclient import TestClient

from theodore_children_webcam_lab.main import app


def main() -> None:
    client = TestClient(app)
    health = client.get("/health")
    page = client.get("/")
    content = client.get("/api/child/content")
    result = {
        "health": health.status_code == 200 and health.json().get("ok") is True,
        "page": page.status_code == 200 and "Oh behave" in page.text,
        "letters": len(content.json().get("letters", [])) if content.status_code == 200 else 0,
        "camera_uploads": health.json().get("camera_uploads") if health.status_code == 200 else None,
    }
    print(json.dumps(result, indent=2, sort_keys=True))
    if not all((result["health"], result["page"], result["letters"] == 26)):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
