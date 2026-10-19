"""Smoke tests for scripts/validate_mascot_glb.py.

Uses the real apps/web/public/mascot3d/Fox.glb (CC-BY-4.0, 160 KB, three
baked clips Survey/Walk/Run) so the validator is exercised against a known-
good file. Also builds a tiny synthetic "bad" .glb in a tmp dir to prove
the failure paths fire.

Pure stdlib - no numpy, no pygltflib - so this runs in CI without extras.
"""

from __future__ import annotations

import json
import struct
from pathlib import Path

import pytest

from scripts.validate_mascot_glb import (
    HARD_SIZE_FAIL_BYTES,
    REQUIRED_CLIPS,
    main,
    validate_file,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
FOX_GLB = REPO_ROOT / "apps" / "web" / "public" / "mascot3d" / "Fox.glb"


def _make_fake_glb(gltf_json: dict) -> bytes:
    """Build a minimal valid .glb binary around a chosen glTF JSON header.

    No BIN chunk - the validator only reads the JSON chunk, which is enough
    for every assertion we make.
    """
    payload = json.dumps(gltf_json).encode("utf-8")
    # Pad JSON chunk to a 4-byte boundary with spaces per the glTF spec.
    while len(payload) % 4 != 0:
        payload += b" "
    chunk = struct.pack("<I4s", len(payload), b"JSON") + payload
    total = 12 + len(chunk)
    header = struct.pack("<4sII", b"glTF", 2, total)
    return header + chunk


def test_fox_glb_is_available_and_valid() -> None:
    """The shipped Fox.glb must pass - if it ever stops, the fox export broke."""
    assert FOX_GLB.exists(), f"missing fixture at {FOX_GLB}"
    report = validate_file(str(FOX_GLB))
    assert not report.failed, report.findings
    assert set(report.animation_names) >= set(REQUIRED_CLIPS)
    assert report.skin_count >= 1
    # Fox is 160 KB; keep the assertion loose so a minor re-encode is OK.
    assert report.size_bytes < 500 * 1024


def test_fox_glb_cli_exits_zero_and_prints_summary(capsys) -> None:
    rc = main([str(FOX_GLB)])
    out = capsys.readouterr().out
    assert rc == 0
    assert "PASS" in out
    assert "Survey" in out and "Walk" in out and "Run" in out


def test_missing_required_clip_fails(tmp_path: Path) -> None:
    """A rig that only exports Walk/Run (forgets Survey) must FAIL."""
    glb = tmp_path / "no_survey.glb"
    glb.write_bytes(
        _make_fake_glb({
            "asset": {"version": "2.0"},
            "animations": [{"name": "Walk"}, {"name": "Run"}],
            "skins": [{"joints": [0]}],
            "nodes": [{"name": "root"}],
            "meshes": [],
            "accessors": [],
        })
    )
    report = validate_file(str(glb))
    assert report.failed
    assert any("Survey" in f.message and f.kind == "fail" for f in report.findings)


def test_missing_skin_fails(tmp_path: Path) -> None:
    """A static (non-skinned) export must FAIL."""
    glb = tmp_path / "no_skin.glb"
    glb.write_bytes(
        _make_fake_glb({
            "asset": {"version": "2.0"},
            "animations": [{"name": n} for n in REQUIRED_CLIPS],
            "nodes": [{"name": "root"}],
            "meshes": [],
            "accessors": [],
        })
    )
    report = validate_file(str(glb))
    assert report.failed
    assert any("no skins" in f.message for f in report.findings if f.kind == "fail")


def test_case_insensitive_clips_warn_not_fail(tmp_path: Path) -> None:
    """Lowercase clip names should pass (fuzzy match) but emit a WARN."""
    glb = tmp_path / "lowercase.glb"
    glb.write_bytes(
        _make_fake_glb({
            "asset": {"version": "2.0"},
            "animations": [{"name": "survey"}, {"name": "walk"}, {"name": "run"}],
            "skins": [{"joints": [0]}],
            "nodes": [{"name": "root"}],
            "meshes": [],
            "accessors": [],
        })
    )
    report = validate_file(str(glb))
    assert not report.failed
    assert any(f.kind == "warn" and "case" in f.message.lower() for f in report.findings)


def test_oversize_file_fails(tmp_path: Path) -> None:
    """A .glb above the 5 MB hard ceiling must FAIL."""
    glb = tmp_path / "big.glb"
    # Pad the JSON chunk itself with filler to blow past the 5 MB ceiling.
    filler = "x" * (HARD_SIZE_FAIL_BYTES + 1024)
    glb.write_bytes(
        _make_fake_glb({
            "asset": {"version": "2.0"},
            "animations": [{"name": n} for n in REQUIRED_CLIPS],
            "skins": [{"joints": [0]}],
            "nodes": [{"name": "root"}],
            "meshes": [],
            "accessors": [],
            "_filler": filler,
        })
    )
    report = validate_file(str(glb))
    assert report.failed
    assert any("hard ceiling" in f.message for f in report.findings if f.kind == "fail")


def test_not_a_glb_fails(tmp_path: Path) -> None:
    """A random non-glb file must FAIL cleanly, not crash."""
    bad = tmp_path / "junk.bin"
    bad.write_bytes(b"this is not a glb file at all " * 10)
    report = validate_file(str(bad))
    assert report.failed


def test_json_mode_emits_parseable_report(capsys) -> None:
    rc = main(["--json", str(FOX_GLB)])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["passed"] is True
    assert "Survey" in parsed["animations"]


def test_missing_file_returns_errno_two(capsys) -> None:
    rc = main([str(FOX_GLB.parent / "does-not-exist.glb")])
    err = capsys.readouterr().err
    assert rc == 2
    assert "not found" in err
