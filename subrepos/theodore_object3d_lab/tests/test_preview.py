"""Depth pictures stay whole when most pixels have no measurement."""

from __future__ import annotations

import numpy as np
from fastapi.testclient import TestClient

from theodore_object3d_lab.main import app
from theodore_object3d_lab.preview import colorize_depth, enhance_color, fill_small_holes, jpeg_bytes


def test_small_holes_fill_and_a_void_stays_empty():
    depth = np.zeros((30, 30), dtype=np.uint16)
    depth[8:12, 8:12] = 1000
    depth[10, 10] = 0
    filled = fill_small_holes(depth, passes=4)
    assert filled[10, 10] > 0
    assert filled[0, 0] == 0
    assert filled[28, 28] == 0


def test_sparse_depth_keeps_the_rest_of_the_picture():
    depth = np.zeros((48, 64), dtype=np.uint16)
    depth[:, 40:] = 1200
    rgb = np.full((48, 64, 3), 180, dtype=np.uint8)
    image, stats = colorize_depth(depth, 0.001, rgb, auto_range=True, fill_holes=True)
    assert image.shape == rgb.shape
    assert stats["coverage"] < 0.8
    assert int(image[10, 4].sum()) > 40
    assert not np.array_equal(image[10, 50], image[10, 4])


def test_near_and_far_are_different_colors():
    near = np.full((24, 24), 400, dtype=np.uint16)
    far = np.full((24, 24), 3500, dtype=np.uint16)
    rgb = np.zeros((24, 24, 3), dtype=np.uint8)
    near_img, _ = colorize_depth(near, 0.001, rgb, near_m=0.2, far_m=4.0, auto_range=False, fill_holes=False)
    far_img, _ = colorize_depth(far, 0.001, rgb, near_m=0.2, far_m=4.0, auto_range=False, fill_holes=False)
    assert not np.array_equal(near_img[8, 8], far_img[8, 8])


def test_enhance_keeps_a_bright_patch_brighter_than_the_corner():
    dark = np.full((32, 32, 3), 12, dtype=np.uint8)
    dark[8:24, 8:24] = 48
    out = enhance_color(dark, clahe=True, sharpen=0.4)
    assert out.shape == dark.shape
    assert out.dtype == np.uint8
    assert int(out[16, 16].mean()) >= int(out[0, 0].mean())


def test_jpeg_bytes_is_a_jpeg():
    image = np.zeros((8, 8, 3), dtype=np.uint8)
    image[:] = (20, 80, 90)
    blob = jpeg_bytes(image)
    assert blob[:2] == b"\xff\xd8"


def test_live_status_is_idle_and_controls_roundtrip():
    client = TestClient(app)
    status = client.get("/api/object3d/live/status")
    assert status.status_code == 200
    assert status.json()["running"] is False
    updated = client.post("/api/object3d/live/controls", json={"brightness": 12, "clahe": False})
    assert updated.status_code == 200
    controls = updated.json()["controls"]
    assert controls["brightness"] == 12
    assert controls["clahe"] is False
    reset = client.post("/api/object3d/live/reset")
    assert reset.json()["controls"]["brightness"] == 8
    assert reset.json()["controls"]["clahe"] is True
    rejected = client.post("/api/object3d/live/start", json={"camera": "nope"})
    assert rejected.status_code == 200
    assert rejected.json()["ok"] is False


def test_page_has_the_live_view_and_the_image_controls():
    page = TestClient(app).get("/lab").text
    assert "Synthetic bench" in page
    assert "CLAHE contrast" in page
    assert "Laser" in page
    assert "High density" in page
    assert "/api/object3d/live/frame.jpg" in page
    assert "Stop live" in page
