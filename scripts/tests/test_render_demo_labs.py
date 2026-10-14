"""The demo-lab filter must keep each lab Deployment and Service."""

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
kind: Service
metadata:
  name: audio-lab
---
kind: Service
metadata:
  name: music
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
---
kind: Deployment
metadata:
  name: audio-lab
spec:
  template:
    spec:
      containers:
        - name: audio-lab
---
kind: Deployment
metadata:
  name: music
spec:
  template:
    spec:
      containers:
        - name: music
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
    assert proc.stdout.count("name: audio-lab") >= 2
    assert proc.stdout.count("name: music") >= 2


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
    assert proc.stdout.count("kind: Service") == 4


def test_render_demo_labs_can_emit_one_named_deployment() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--kind", "Deployment", "--name", "audio-lab"],
        input=SAMPLE,
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert "kind: Service" not in proc.stdout
    assert proc.stdout.count("kind: Deployment") == 1
    assert "name: audio-lab" in proc.stdout
    assert "name: course-studio" not in proc.stdout
    assert "name: children-lab" not in proc.stdout


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
apiVersion: v1
kind: Service
metadata:
  name: audio-lab
  namespace: aoep
---
apiVersion: v1
kind: Service
metadata:
  name: music
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
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: audio-lab
  namespace: aoep
spec:
  template:
    spec:
      containers:
        - name: audio-lab
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: music
  namespace: aoep
spec:
  template:
    spec:
      containers:
        - name: music
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
    assert proc.stdout.count("kind: Service") == 4


def test_render_demo_labs_refuses_a_partial_render() -> None:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT)],
        input="kind: Service\nmetadata:\n  name: course-studio\n",
        text=True,
        capture_output=True,
        check=False,
    )
    assert proc.returncode != 0
    assert "expected 8" in proc.stderr
