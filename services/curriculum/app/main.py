"""Curriculum / CMS service.

Phase6 owns authoring/import/management of decks + videos and the RAG content
pipeline. This skeleton exposes /health and lists the sample curriculum on disk.
"""

from __future__ import annotations

import os

from eduplatform_shared.service import create_service_app

app = create_service_app("curriculum")


def _root() -> str:
    env = os.environ.get("CURRICULUM_DIR")
    if env:
        return env
    here = os.path.dirname(os.path.abspath(__file__))
    repo_root = os.path.abspath(os.path.join(here, "..", "..", ".."))
    return os.path.join(repo_root, "sample-curriculum")


@app.get("/api/decks")
def decks() -> list[str]:
    root = _root()
    if not os.path.isdir(root):
        return []
    return sorted(
        name
        for name in os.listdir(root)
        if os.path.isfile(os.path.join(root, name, "lesson.txt"))
    )
