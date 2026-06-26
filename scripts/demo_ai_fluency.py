#!/usr/bin/env python3
"""Ad-hoc demo: prove the live-class agent can learn+teach the AI Fluency course.

Drives the orchestrator FastAPI app exactly like apps/web does:
list lessons -> start session -> advance slides -> ask grounded questions.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("DEPLOY_MODE", "local")
os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
os.environ.setdefault("INTERNAL_AUTH_DISABLED", "1")

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.abspath(os.path.join(HERE, "..", "services", "orchestrator", "src"))
if SRC not in sys.path:
    sys.path.insert(0, SRC)

from fastapi.testclient import TestClient  # noqa: E402
from orchestrator.main import app  # noqa: E402

LESSON = "ai-fluency-essentials"
client = TestClient(app)


def main() -> int:
    lessons = client.get("/api/lessons").json()
    ids = {l["lesson_id"]: l["title"] for l in lessons}
    print(f"Loaded {len(ids)} lessons.")
    if LESSON not in ids:
        print(f"FAIL: {LESSON} not found in /api/lessons")
        return 1
    print(f"Found new course: {LESSON} -> '{ids[LESSON]}'\n")

    start = client.post(
        "/api/sessions", json={"lesson_id": LESSON, "class_type": "group"}
    )
    if start.status_code != 200:
        print(f"FAIL start_session {start.status_code}: {start.text}")
        return 1
    view = start.json()
    sid = view["session"]["session_id"]
    total = len(view["lesson"]["slides"])
    print(f"Started session {sid} | {total} slides")
    print(f"  Slide 1: {view['slide']['title']}")
    print(f"    narration: {view['slide']['narration']}\n")

    # Walk a few slides to show delivery.
    for _ in range(3):
        s = client.post(f"/api/sessions/{sid}/advance").json()
        print(f"  -> Slide {s['index'] + 1}: {s['title']}")
    print()

    questions = [
        "What is a hallucination and why is it dangerous?",
        "Can I paste confidential customer data into a public AI tool?",
        "What makes a good prompt?",
        "Is AI generally smarter than humans across everything?",
    ]
    for q in questions:
        a = client.post(
            f"/api/sessions/{sid}/ask", json={"text": q, "language": "en"}
        ).json()
        print(f"Q: {q}")
        print(f"A: {a['text']}")
        print(
            f"   [grounded={a['grounded']} risk={a['hallucination_risk']:.2f} "
            f"citations={len(a['citations'])}]\n"
        )
    print("DEMO_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
