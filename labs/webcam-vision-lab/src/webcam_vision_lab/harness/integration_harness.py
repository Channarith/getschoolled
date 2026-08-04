"""Check local AOEP services and optional presence-report smoke."""

from __future__ import annotations

import argparse
import os
import sys

try:
    import httpx
except ImportError:
    httpx = None  # type: ignore


def _base(name: str, default: str) -> str:
    return (os.environ.get(name) or default).rstrip("/")


def check_health(url: str, label: str) -> bool:
    if httpx is None:
        print(f"  {label}: skip (install httpx)")
        return True
    try:
        r = httpx.get(f"{url}/health", timeout=3.0)
        ok = r.status_code == 200
        print(f"  {label}: {'OK' if ok else 'FAIL'} ({r.status_code})")
        return ok
    except Exception as exc:
        print(f"  {label}: FAIL ({exc})")
        return False


def main() -> None:
    parser = argparse.ArgumentParser(description="AOEP integration harness")
    parser.add_argument("--check-only", action="store_true", help="Health checks only")
    args = parser.parse_args()

    orch = _base("ORCHESTRATOR_URL", "http://localhost:8000")
    perc = _base("PERCEPTION_URL", "http://localhost:8003")

    print("=== Service health ===")
    ok_orch = check_health(orch, "orchestrator")
    ok_perc = check_health(perc, "perception")

    if args.check_only:
        sys.exit(0 if ok_orch and ok_perc else 1)

    if not ok_orch:
        print("Start orchestrator: make run-orchestrator")
        sys.exit(1)

    print("\nIntegration scenarios are documented in README.txt.")
    print("Use apps/web /vision and /live-room for full webcam UI tests.")


if __name__ == "__main__":
    main()
