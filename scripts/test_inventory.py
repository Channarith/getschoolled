#!/usr/bin/env python3
"""Test inventory + release gate helper.

Answers "how many tests do we run?" authoritatively (via `pytest --collect-only`,
which expands parametrized cases) and maps every collected test to one of the
16 ecosystem sub-apps so we can see coverage per sub-app and find gaps.

Usage:
  python3 scripts/test_inventory.py              # collect + report
  python3 scripts/test_inventory.py --static     # fast: count `def test_` only
  python3 scripts/test_inventory.py --min 20     # CI gate: fail if a sub-app < 20

See docs/release-testing.txt for the x.0 release policy this supports.
"""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

# The 16 ecosystem sub-apps (see docs/release-testing.txt + the Our Story map).
SUBAPPS = [
    "AI tutor (live class)",
    "Live & group classes",
    "Human-in-the-loop",
    "Homework grader",
    "Adaptive learning",
    "Knowledge base (RAG) & trust",
    "Courses & catalog",
    "Careers",
    "Drive Mode (audio)",
    "Languages & speech",
    "Machine vision",
    "Arcade & rewards",
    "Accounts & profiles",
    "Consent, flags & compliance",
    "Integrations, webhooks & payments",
    "Course scraper",
]
OTHER = "Platform core / shared infra"
TRAINING = "Model training"


def classify(path: str, name: str) -> str:
    """Map a test path::name to a sub-app bucket."""
    p, n = path.lower(), name.lower()

    if "training/" in p:
        return TRAINING
    if "perception" in p or "test_vision" in p or "vision_embedding" in p:
        return "Machine vision"
    if "services/speech/" in p or any(k in n for k in ("language", "slang", "translation", "speech", "khmer")) \
            or "language_learning" in p or "languages_speech" in p:
        return "Languages & speech"
    if "services/billing/" in p or "payment" in p or "finance" in p or "entitlement" in p:
        return "Integrations, webhooks & payments"
    if "services/integrations/" in p or any(k in p for k in ("webhook", "lms_connector", "cloud_connector", "bridges")):
        return "Integrations, webhooks & payments"
    if "harvest" in p:
        return "Course scraper"
    if "services/identity/" in p:
        if "game" in n or "reward" in n:
            return "Arcade & rewards"
        return "Accounts & profiles"
    if "reward" in n or "test_games" in p or "test_ads" in p:
        return "Arcade & rewards"
    if "services/memory/" in p or any(k in n for k in ("flag", "consent", "legal", "compliance", "retention", "survey", "behavior")):
        return "Consent, flags & compliance"
    if "homework" in p:
        return "Homework grader"
    if "services/curriculum/" in p:
        if "job" in n or "skills" in n:
            return "Careers"
        if "audio" in n or "delivery" in n:
            return "Drive Mode (audio)"
        if any(k in n for k in ("scene", "provenance", "validation", "correction", "cograde", "knowledge")):
            return "Knowledge base (RAG) & trust"
        return "Courses & catalog"
    if "job" in n or "skills_taxonomy" in p:
        return "Careers"
    if "services/orchestrator/" in p or "apps/agent-runtime/" in p:
        if "hil" in n:
            return "Human-in-the-loop"
        if any(k in n for k in ("adaptive", "phase45", "assessment", "foresight", "bandit", "optimization")):
            return "Adaptive learning"
        if "embody" in n:
            return "Machine vision"   # embodiment/robot grouped under perception/robot
        if "group" in n or "bridge" in n:
            return "Live & group classes"
        return "AI tutor (live class)"
    if any(k in n for k in ("rag", "knowledge", "search", "scene", "provenance", "validation", "correction")):
        return "Knowledge base (RAG) & trust"
    if any(k in n for k in ("foresight", "bandit", "adaptive", "inference")):
        return "Adaptive learning"
    if "bridges" in n:
        return "Live & group classes"
    if "embod" in n or "edge" in n:
        return "Machine vision"
    if any(k in n for k in ("audio", "delivery")):
        return "Drive Mode (audio)"
    if any(k in n for k in ("catalog", "audio_courses", "notifications", "recommend")):
        return "Courses & catalog"
    return OTHER


def collect_node_ids() -> list[str]:
    """Collect per test directory and prefix each node id with its package path.

    pytest emits node ids relative to each package's own rootdir (e.g.
    "tests/test_x.py::y"), so we collect per directory and prepend the package
    path (the dir minus its trailing "tests") to recover the owning service.
    """
    venv_py = ROOT / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.exists() else sys.executable
    dirs = [ROOT / "packages/shared/tests"]
    dirs += sorted((ROOT / "services").glob("*/tests"))
    for extra in ("apps/agent-runtime/tests", "training/tests", "scripts/tests", "qa/tests"):
        if (ROOT / extra).exists():
            dirs.append(ROOT / extra)
    env = {**os.environ, "DEPLOY_MODE": "local", "INTERNAL_AUTH_DISABLED": "1",
           "RATE_LIMIT_DISABLED": "1", "ENABLE_TEST_ENDPOINTS": "1",
           "CURRICULUM_DIR": str(ROOT / "sample-curriculum")}
    ids: list[str] = []
    for d in dirs:
        prefix = str(d.parent.relative_to(ROOT)) + "/"   # e.g. "services/orchestrator/"
        proc = subprocess.run([py, "-m", "pytest", "--collect-only", "-q", "tests"],
                              cwd=d.parent, env=env, capture_output=True, text=True)
        found = [ln.strip() for ln in proc.stdout.splitlines() if ".py::" in ln]
        if not found:
            sys.stderr.write(f"[warn] no tests collected in {prefix}\n")
            sys.stderr.write(proc.stdout[-800:] + proc.stderr[-800:] + "\n")
        ids += [prefix + nid for nid in found]
    return ids


def static_counts() -> Counter:
    by_subapp: Counter = Counter()
    EX = {".venv", "node_modules", "site-packages", ".next", ".git"}
    for f in ROOT.rglob("test_*.py"):
        if set(f.parts) & EX:
            continue
        rel = str(f.relative_to(ROOT))
        for m in re.finditer(r"^\s*def (test_\w+)", f.read_text(errors="ignore"), re.M):
            by_subapp[classify(rel, m.group(1))] += 1
    return by_subapp


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--static", action="store_true", help="count def test_ only (no pytest)")
    ap.add_argument("--min", type=int, default=0, help="fail if any sub-app has < MIN tests")
    args = ap.parse_args()

    if args.static:
        counts = static_counts()
        mode = "defined test functions (static; parametrized cases expand at runtime)"
    else:
        ids = collect_node_ids()
        counts = Counter(classify(nid.split("::", 1)[0], nid.split("::", 1)[1]) for nid in ids)
        mode = "collected test cases (authoritative; includes parametrization)"

    total = sum(counts.values())
    print(f"TOTAL: {total} {mode}\n")
    print("By ecosystem sub-app (16):")
    for app_name in SUBAPPS:
        print(f"  {counts.get(app_name, 0):5d}  {app_name}")
    print("\nOther buckets:")
    for b in (OTHER, TRAINING):
        print(f"  {counts.get(b, 0):5d}  {b}")
    print("\nFrontend (apps/web): 0 automated  -> needs a JS test runner (vitest/jest)")
    print("Mobile  (apps/mobile): 0 automated -> needs a JS test runner (jest)")

    if args.min:
        below = [a for a in SUBAPPS if counts.get(a, 0) < args.min]
        if below:
            print(f"\nFAIL: these sub-apps are below --min {args.min}:")
            for a in below:
                print(f"  - {a} ({counts.get(a,0)})")
            return 1
        print(f"\nOK: every sub-app has >= {args.min} tests.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
