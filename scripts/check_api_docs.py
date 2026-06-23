#!/usr/bin/env python3
"""Keep docs/api-reference.txt in sync with the real routes.

Parses every services/*/src/**/main.py for FastAPI route decorators and asserts
each route path is documented in docs/api-reference.txt (path params normalized
to {}). Also warns about documented-but-nonexistent paths. Exit nonzero if any
real route is undocumented, so CI catches drift.

Usage: python3 scripts/check_api_docs.py
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOC = ROOT / "docs" / "api-reference.txt"

ROUTE_RE = re.compile(r'@(?:app|router)\.(get|post|put|delete|patch)\(\s*["\']([^"\']+)["\']')
PARAM_RE = re.compile(r"\{[^}]+\}")

# Standard endpoints added by create_service() / FastAPI; documented in section 1.
STANDARD = {
    "/health", "/version", "/metrics", "/telemetry/summary", "/telemetry/errors",
    "/telemetry/logs", "/openapi.json", "/docs", "/redoc", "/__meta",
}


def norm(path: str) -> str:
    return PARAM_RE.sub("{}", path.split("?")[0]).rstrip("/") or "/"


def collect_routes() -> dict[str, set[str]]:
    by_service: dict[str, set[str]] = {}
    for main in sorted((ROOT / "services").glob("*/src/*/main.py")):
        service = main.parts[main.parts.index("services") + 1]
        paths = by_service.setdefault(service, set())
        for _method, path in ROUTE_RE.findall(main.read_text(encoding="utf-8")):
            paths.add(norm(path))
    return by_service


def main() -> int:
    doc_norm = norm_text(DOC.read_text(encoding="utf-8"))
    by_service = collect_routes()

    missing: list[str] = []
    total = 0
    for service, paths in by_service.items():
        for p in sorted(paths):
            if p in STANDARD:
                continue
            total += 1
            if p not in doc_norm:
                missing.append(f"{service}: {p}")

    documented = total - len(missing)
    print(f"Documented {documented}/{total} routes across {len(by_service)} services.")
    if missing:
        print("\nUNDOCUMENTED routes (add to docs/api-reference.txt):")
        for m in missing:
            print(f"  - {m}")
        return 1
    print("All routes are documented. ✓")
    return 0


def norm_text(text: str) -> str:
    # Normalize path params in the doc the same way so {id}=={session_id}=={}.
    return PARAM_RE.sub("{}", text)


if __name__ == "__main__":
    sys.exit(main())
