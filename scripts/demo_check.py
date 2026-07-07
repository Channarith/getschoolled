#!/usr/bin/env python3
"""Corporate-demo readiness gate: one command, one GO / NO-GO verdict.

Run against the deterministic demo stack (``make up-e2e``):

    make demo-check                # full gate
    python3 scripts/demo_check.py --skip-e2e --skip-stress   # probes + pytest only

Steps
  1. Targeted pytest subset covering the corporate demo path (seconds).
  2. Live stack probes: service health, seeded corporate programs, corporate
     lessons exposed, jobs board up (and pinned to the offline sample
     provider unless --allow-live-jobs).
  3. Playwright corporate E2E suite (apps/web/e2e/corporate).
  4. Stress smoke via qa/stress.py (functional pass-rate + latency SLA).

Exit code 0 = GO, 1 = NO-GO. Stdlib only, mirroring qa/stress.py.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

PYTEST_TARGETS = [
    "services/curriculum/tests/test_program_seeding.py",
    "services/curriculum/tests/test_jobs_api.py",
    "services/orchestrator/tests/test_corporate_lessons.py",
    "qa/tests/test_new_features_integration.py",
]

HEALTH_PROBES = [
    ("orchestrator", "http://localhost:8000/health"),
    ("memory", "http://localhost:8004/health"),
    ("curriculum", "http://localhost:8005/health"),
    ("identity", "http://localhost:8008/health"),
    ("web", "http://localhost:3000/"),
]


@dataclass
class StepResult:
    name: str
    ok: bool
    seconds: float
    detail: str = ""


def _get_json(url: str, timeout: float = 10.0):
    with urllib.request.urlopen(url, timeout=timeout) as res:  # noqa: S310
        return json.loads(res.read().decode("utf-8"))


def _http_ok(url: str, timeout: float = 10.0) -> bool:
    try:
        with urllib.request.urlopen(url, timeout=timeout) as res:  # noqa: S310
            return 200 <= res.status < 400
    except Exception:
        return False


def _run(cmd: list[str], *, cwd: Path = ROOT) -> tuple[bool, str]:
    proc = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    tail = "\n".join((proc.stdout + proc.stderr).strip().splitlines()[-12:])
    return proc.returncode == 0, tail


def step_pytest() -> StepResult:
    start = time.perf_counter()
    ok, tail = _run([sys.executable, "-m", "pytest", *PYTEST_TARGETS, "-q"])
    return StepResult("pytest (corporate demo subset)", ok, time.perf_counter() - start,
                      tail if not ok else tail.splitlines()[-1] if tail else "")


def step_probes(allow_live_jobs: bool) -> StepResult:
    start = time.perf_counter()
    problems: list[str] = []
    for name, url in HEALTH_PROBES:
        if not _http_ok(url):
            problems.append(f"{name} down ({url})")
    if not problems:
        try:
            programs = _get_json("http://localhost:8005/programs?audience=corporate")
            if not programs:
                problems.append("no corporate programs seeded (GET /programs?audience=corporate is empty)")
        except Exception as exc:
            problems.append(f"programs probe failed: {exc}")
        try:
            lessons = _get_json("http://localhost:8000/api/lessons")
            corporate = [l for l in lessons if l.get("audience") == "corporate"]
            if len(corporate) < 11:
                problems.append(f"expected >=11 corporate lessons, got {len(corporate)}")
        except Exception as exc:
            problems.append(f"lessons probe failed: {exc}")
        try:
            jobs = _get_json("http://localhost:8005/jobs?limit=3")
            if not jobs.get("jobs"):
                problems.append("jobs board returned no postings")
            elif not allow_live_jobs and jobs.get("source") != "sample":
                problems.append(
                    f"jobs source is '{jobs.get('source')}', not 'sample' — "
                    "network-nondeterministic for a demo (use make up-e2e, or pass --allow-live-jobs)"
                )
        except Exception as exc:
            problems.append(f"jobs probe failed: {exc}")
    return StepResult("stack probes (health + seeded demo data)",
                      not problems, time.perf_counter() - start, "; ".join(problems))


def step_playwright() -> StepResult:
    start = time.perf_counter()
    ok, tail = _run(["npx", "playwright", "test", "e2e/corporate"], cwd=ROOT / "apps" / "web")
    return StepResult("playwright corporate E2E", ok, time.perf_counter() - start,
                      "" if ok else tail)


def step_stress() -> StepResult:
    start = time.perf_counter()
    # Internal-only scenarios need the same dev token the dev/e2e stacks run
    # with (scripts/dev_up.sh, infra/compose/docker-compose.e2e.yml).
    os.environ.setdefault("INTERNAL_TOKEN", "dev-internal-token")
    ok, tail = _run([
        sys.executable, "qa/stress.py", "--smoke",
        "--max-error-rate", "0.01", "--max-p95-ms", "1500", "--min-functional", "0.99",
    ])
    return StepResult("stress smoke (qa/stress.py)", ok, time.perf_counter() - start,
                      "" if ok else tail)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--skip-e2e", action="store_true", help="skip the Playwright suite")
    ap.add_argument("--skip-stress", action="store_true", help="skip the stress smoke")
    ap.add_argument("--skip-pytest", action="store_true", help="skip the pytest subset")
    ap.add_argument("--allow-live-jobs", action="store_true",
                    help="don't require the offline sample jobs board")
    ap.add_argument("--json", metavar="PATH", help="also write results as JSON")
    args = ap.parse_args(argv)

    results: list[StepResult] = []
    if not args.skip_pytest:
        results.append(step_pytest())
    results.append(step_probes(args.allow_live_jobs))
    # E2E and stress need the live stack; only bother if the probes passed.
    probes_ok = results[-1].ok
    if not args.skip_e2e:
        if probes_ok:
            results.append(step_playwright())
        else:
            results.append(StepResult("playwright corporate E2E", False, 0.0,
                                      "skipped: stack probes failed"))
    if not args.skip_stress:
        if probes_ok:
            results.append(step_stress())
        else:
            results.append(StepResult("stress smoke (qa/stress.py)", False, 0.0,
                                      "skipped: stack probes failed"))

    go = all(r.ok for r in results)
    width = max(len(r.name) for r in results)
    print("\n=== Corporate demo readiness ===")
    for r in results:
        mark = "PASS" if r.ok else "FAIL"
        line = f"  {r.name.ljust(width)}  {mark}  {r.seconds:6.1f}s"
        print(line)
        if r.detail and not r.ok:
            for detail_line in r.detail.splitlines():
                print(f"      {detail_line}")
    print(f"\n  VERDICT: {'GO' if go else 'NO-GO'}\n")

    if args.json:
        Path(args.json).write_text(json.dumps({
            "go": go,
            "steps": [r.__dict__ for r in results],
            "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S%z"),
        }, indent=2))
    return 0 if go else 1


if __name__ == "__main__":
    raise SystemExit(main())
