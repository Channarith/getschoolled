"""The self check must work, and the README must stay true.

A getting-started guide that quotes a stale test count or a dead endpoint costs
more time than no guide at all, so the claims are asserted rather than trusted.
"""

from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

from theodore_webcam_lab.main import app

LAB_ROOT = Path(__file__).resolve().parents[1]
README = LAB_ROOT / "README.md"
SELFCHECK = LAB_ROOT / "scripts" / "selfcheck.py"


def _readme() -> str:
    return README.read_text(encoding="utf-8")


# ------------------------------------------------------------------ self check
def test_selfcheck_reports_each_step_and_can_run_offline():
    """Offline it should pass its local checks and fail loudly on the API."""
    result = subprocess.run(
        [sys.executable, str(SELFCHECK), "--base-url", "http://127.0.0.1:9"],
        capture_output=True,
        text=True,
        timeout=120,
        env={**os.environ, "NO_COLOR": "1"},
    )
    out = result.stdout
    # Every offline stage is reported by name so a reader can see how far it got.
    for step in ("Python 3.11+", "Python dependencies", "Lab package imports",
                 "Webcam analysis", "Sobel imaging", "Tuning knobs in range",
                 "Tuning knobs change scoring"):
        assert step in out, f"self check never reported {step!r}:\n{out}"
    assert "[PASS] Webcam analysis" in out
    # Range-checking a knob proves nothing about whether scoring reads it, so the
    # offline run has to demonstrate the effect and say how many knobs it proved.
    assert "[PASS] Tuning knobs change scoring" in out
    assert "knobs change a scoring decision" in out
    # Unreachable API: must fail, name the step, and say what to do about it.
    assert "[FAIL] API reachable" in out
    assert "fix:" in out
    assert result.returncode == 1, "an unreachable API must be a non-zero exit"


def test_selfcheck_passes_end_to_end_when_it_starts_its_own_server():
    result = subprocess.run(
        [sys.executable, str(SELFCHECK), "--serve", "--port", "8123"],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NO_COLOR": "1"},
    )
    out = result.stdout
    assert result.returncode == 0, f"self check --serve failed:\n{out}\n{result.stderr}"
    for step in ("API reachable", "Frame evaluation", "Live metrics",
                 "Live monitor page", "Tuning API", "Tuning re-scores live session",
                 "Voice agent", "Webcam games"):
        assert f"[PASS] {step}" in out, f"{step} did not pass:\n{out}"
    assert "checks passed" in out


def test_readme_selfcheck_sample_matches_the_real_step_count():
    """The README pastes a sample run; a stale count there teaches the reader to
    ignore missing steps, which is how the tuning gap went unnoticed."""
    result = subprocess.run(
        [sys.executable, str(SELFCHECK), "--serve", "--port", "8124"],
        capture_output=True,
        text=True,
        timeout=180,
        env={**os.environ, "NO_COLOR": "1"},
    )
    actual = re.search(r"All (\d+) checks passed", result.stdout)
    assert actual, f"self check no longer prints a total:\n{result.stdout}"
    claimed = re.search(r"All (\d+) checks passed", _readme())
    assert claimed, "README no longer shows a sample self-check run"
    assert claimed.group(1) == actual.group(1), (
        f"README sample says {claimed.group(1)} checks, self check runs {actual.group(1)}"
    )


# ---------------------------------------------------------------------- README
def test_readme_test_count_matches_the_real_suite():
    """The quoted 'you should see N passed' has to be the truth."""
    claimed = re.search(r"You should see `(\d+) passed`", _readme())
    assert claimed, "README no longer states an expected test count"

    result = subprocess.run(
        [sys.executable, "-m", "pytest", str(LAB_ROOT / "tests"), "-q", "--collect-only"],
        capture_output=True,
        text=True,
        timeout=180,
    )
    collected = re.search(r"(\d+) tests? collected", result.stdout)
    assert collected, f"could not count tests:\n{result.stdout}"
    assert int(collected.group(1)) >= int(claimed.group(1)), (
        f"README promises at least {claimed.group(1)} tests but the suite has "
        f"only {collected.group(1)}"
    )


def test_readme_images_exist():
    referenced = set(re.findall(r"\((docs/screens/[^)]+)\)", _readme()))
    assert referenced, "README should show screenshots"
    for rel in referenced:
        assert (LAB_ROOT / rel).is_file(), f"README references a missing image: {rel}"


def test_readme_endpoints_are_real_routes():
    routes = {re.sub(r"\{[^}]+\}", "{x}", r.path) for r in app.routes}
    quoted = set(re.findall(r"(?:GET|POST|PATCH)\s*(/api/theodore/[^\s]+|/theodore/[^\s]+)", _readme()))
    assert quoted, "README should list the endpoints"
    for path in quoted:
        assert re.sub(r"\{[^}]+\}", "{x}", path) in routes, f"README documents a dead route: {path}"


def test_readme_scripts_exist():
    for rel in set(re.findall(r"scripts/[a-z_]+\.py", _readme())):
        assert (LAB_ROOT / rel).is_file(), f"README references a missing script: {rel}"


def test_readme_covers_the_failure_path():
    """The point of the guide: what to do when it does not work."""
    text = _readme()
    assert "selfcheck.py" in text
    assert "--serve" in text
    for symptom in ("Address already in use", "No metrics yet", "camera unavailable"):
        assert symptom in text, f"troubleshooting table lost the {symptom!r} row"
