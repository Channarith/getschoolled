"""The demo-lab filter must keep both Deployments and both Services."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / "scripts" / "render_demo_labs.py"

SAMPLE = """\
kind: Service
metadata:
  name: web
---
kind: Service
metadata:
  name: course-studio
---
kind: Service
metadata:
  name: children-lab
---
kind: Deployment
metadata:
  name: course-studio
spec:
  template:
    spec:
      containers:
        - name: course-studio
---
kind: Deployment
metadata:
  name: children-lab
spec:
  template:
    spec:
      containers:
        - name: children-lab
"""


def test_render_demo_labs_keeps_only_the_labs() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input=SAMPLE,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "name: web" not in proc.stdout
    # Metadata plus the container name, so the string appears more than once.
    assert proc.stdout.count("name: course-studio") >= 2
    assert proc.stdout.count("name: children-lab") >= 2


def test_render_demo_labs_can_emit_services_without_images() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--kind", "Service"],
        input=SAMPLE,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "kind: Deployment" not in proc.stdout
    assert proc.stdout.count("kind: Service") == 2


def test_render_demo_labs_splits_kustomize_documents() -> None:
    kustomize = """\
apiVersion: v1
kind: Service
metadata:
  name: web
  namespace: aoep
---
apiVersion: v1
kind: Service
metadata:
  name: course-studio
  namespace: aoep
---
apiVersion: v1
kind: Service
metadata:
  name: children-lab
  namespace: aoep
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: course-studio
  namespace: aoep
spec:
  template:
    spec:
      containers:
        - name: course-studio
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: children-lab
  namespace: aoep
spec:
  template:
    spec:
      containers:
        - name: children-lab
"""
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--kind", "Service"],
        input=kustomize,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "kind: Deployment" not in proc.stdout
    assert proc.stdout.count("kind: Service") == 2


def test_render_demo_labs_refuses_a_partial_render() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="kind: Service\nmetadata:\n  name: course-studio\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "expected 4" in proc.stderr
