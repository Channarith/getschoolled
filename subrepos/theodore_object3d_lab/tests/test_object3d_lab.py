"""The object3d lab bench runs without a camera."""

from __future__ import annotations

from fastapi.testclient import TestClient

from theodore_object3d_lab.bench import run_bench
from theodore_object3d_lab.devices import TOOLS, connected_cameras, sdk_status
from theodore_object3d_lab.main import app


def test_bench_recognizes_and_answers():
    report = run_bench()
    assert report["ok"], report["checks"]
    assert report["checks"]["identified_nearest"]
    assert report["checks"]["sign_exit"]
    assert report["checks"]["live_probe_is_hot"]


def test_devices_do_not_crash_when_a_sdk_is_missing():
    status = sdk_status()
    assert "pyrealsense2" in status
    assert "depthai" in status
    cameras = connected_cameras()
    assert cameras
    assert {row["camera"] for row in cameras} <= {"realsense", "oak"}


def test_tools_name_the_camera_and_the_scripts():
    names = {tool["name"] for tool in TOOLS}
    assert "Intel RealSense Viewer" in names
    assert "Luxonis DepthAI demo" in names
    assert "object3d_ask.py" in names


def test_lab_pages_and_bench_endpoint():
    client = TestClient(app)
    health = client.get("/health")
    assert health.status_code == 200
    assert health.json()["service"] == "theodore-object3d-lab"
    page = client.get("/lab")
    assert page.status_code == 200
    assert "Synthetic bench" in page.text
    assert "/api/live-audio/client.js" in page.text
    bench = client.post("/api/object3d/bench")
    assert bench.status_code == 200
    assert bench.json()["ok"] is True


def test_enroll_synthetic_then_ask_who_made_it():
    client = TestClient(app)
    app.state.gallery = None
    app.state.last = []
    enrolled = client.post("/api/object3d/enroll", json={
        "label": "blue block",
        "maker": "Lab",
        "year": 2024,
        "camera": "",
    })
    assert enrolled.status_code == 200
    body = enrolled.json()
    assert body["ok"] is True
    assert "blue block" in body["labels"]
    asked = client.post("/api/object3d/ask", json={"question": "who made it?"})
    assert "Lab" in asked.json()["answer"]
    far = client.post("/api/object3d/ask", json={"question": "how far is it?"})
    assert "away" in far.json()["answer"]


def test_unknown_camera_is_a_reported_error():
    client = TestClient(app)
    captured = client.post("/api/object3d/capture", json={"camera": "no-such-camera"})
    assert captured.status_code == 200
    assert captured.json()["ok"] is False
