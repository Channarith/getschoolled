#!/usr/bin/env python3
"""Comprehensive regression runner.

One command that runs the whole quality gate and emits a single report:
  1. Backend test matrix (pytest across packages/shared, services/*, training,
     apps/agent-runtime, scripts) - FUNCTIONAL CORRECTNESS + regression.
  2. Optional coverage (when pytest-cov is installed)                  - QUALITY.
  3. Web typecheck + lint (when apps/web deps are installed)           - FRONTEND.
  4. API stress smoke against any reachable services                  - PERF/QUALITY.

Each step is reported pass/fail with timing; a failing required step makes the
runner exit non-zero (CI/regression gate). Steps whose tooling is unavailable are
SKIPPED (not failed), so it runs anywhere.

  python3 qa/regression.py                 # full
  python3 qa/regression.py --fast          # skip stress + coverage
  python3 qa/regression.py --json qa_report.json
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import time
from pathlib import Path
from typing import List, Optional

ROOT = Path(__file__).resolve().parents[1]
TEST_GLOBS = [
    "packages/shared/tests", "services/curriculum/tests", "services/orchestrator/tests",
    "services/memory/tests", "services/speech/tests", "services/perception/tests",
    "services/billing/tests", "services/integrations/tests", "services/harvester/tests",
    "apps/agent-runtime/tests", "training/tests", "scripts/tests",
]


def _run(cmd: List[str], *, cwd: Optional[Path] = None) -> dict:
    start = time.perf_counter()
    proc = subprocess.run(cmd, cwd=str(cwd or ROOT), capture_output=True, text=True)
    return {
        "cmd": " ".join(cmd),
        "returncode": proc.returncode,
        "elapsed_s": round(time.perf_counter() - start, 2),
        "stdout_tail": proc.stdout[-2000:],
        "stderr_tail": proc.stderr[-1000:],
    }


def step_pytest(coverage: bool) -> dict:
    have_cov = coverage and __import__("importlib.util", fromlist=["util"]).find_spec("pytest_cov")
    cmd = [sys.executable, "-m", "pytest", *TEST_GLOBS, "-q"]
    if have_cov:
        cmd += ["--cov=packages/shared/src/aoep_shared", "--cov-report=term-missing:skip-covered"]
    res = _run(cmd)
    res["name"] = "backend-tests" + ("+coverage" if have_cov else "")
    res["required"] = True
    res["skipped"] = False
    return res


def step_web() -> dict:
    web = ROOT / "apps" / "web"
    if not (web / "node_modules").is_dir() or shutil.which("npm") is None:
        return {"name": "web-typecheck+lint", "skipped": True, "required": False,
                "reason": "apps/web deps or npm not available"}
    tc = _run(["npm", "run", "typecheck"], cwd=web)
    lint = _run(["npm", "run", "lint"], cwd=web)
    return {
        "name": "web-typecheck+lint",
        "skipped": False,
        "required": True,
        "returncode": tc["returncode"] or lint["returncode"],
        "elapsed_s": round(tc["elapsed_s"] + lint["elapsed_s"], 2),
        "stdout_tail": (tc["stdout_tail"] + "\n" + lint["stdout_tail"])[-2000:],
        "stderr_tail": (tc["stderr_tail"] + "\n" + lint["stderr_tail"])[-1000:],
    }


def step_stress() -> dict:
    res = _run([sys.executable, str(ROOT / "qa" / "stress.py"), "--smoke"])
    res["name"] = "api-stress-smoke"
    res["required"] = False    # only fails if a reachable service breaches SLA
    res["skipped"] = False
    return res


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--fast", action="store_true", help="skip coverage + stress")
    ap.add_argument("--no-web", action="store_true")
    ap.add_argument("--json", default=None)
    args = ap.parse_args(argv)

    steps: List[dict] = [step_pytest(coverage=not args.fast)]
    if not args.no_web:
        steps.append(step_web())
    if not args.fast:
        steps.append(step_stress())

    print("\n==== REGRESSION SUMMARY ====")
    overall_ok = True
    for s in steps:
        if s.get("skipped"):
            status = "SKIP"
        elif s["returncode"] == 0:
            status = "PASS"
        else:
            status = "FAIL"
            if s.get("required"):
                overall_ok = False
        print(f"  [{status}] {s['name']:<28} ({s.get('elapsed_s', 0)}s)")

    report = {"passed": overall_ok, "steps": steps, "timestamp": time.time()}
    if args.json:
        Path(args.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"\nreport -> {args.json}")
    print(f"\nOVERALL: {'PASS' if overall_ok else 'FAIL'}")
    return 0 if overall_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
