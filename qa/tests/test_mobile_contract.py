"""K-API-1 — mobile<->backend contract test (QA V&V plan, Mobile dimension).

The mobile app ships a frozen set of endpoints it calls (apps/mobile/src/api.ts,
captured in apps/mobile/contract/endpoints.json). A backend PR that renames or
removes one of those routes silently breaks the shipped app with no device time.
This test loads each owning service's OpenAPI schema and asserts every mobile
route shape still exists.

Path params are matched structurally: a manifest path `/students/{id}` matches a
service route `/students/{student_id}` — the param NAME can differ, the SHAPE
cannot. That keeps the contract about "does the route mobile calls exist" without
coupling to server-side param naming.

Runs in the existing Python CI job (services already importable via conftest).
"""

from __future__ import annotations

import json
import re
from importlib import import_module
from pathlib import Path

import pytest

_ROOT = Path(__file__).resolve().parents[2]
_MANIFEST = _ROOT / "apps" / "mobile" / "contract" / "endpoints.json"

# Most services' Python package matches the service dir name; speech is the one
# exception (its src package is `speech_gw`).
_SERVICE_MODULES = {"speech": "speech_gw"}


def _normalize(path: str) -> str:
    """Collapse any {param} segment to a wildcard and drop a trailing slash."""
    norm = re.sub(r"\{[^}]+\}", "{*}", path)
    if len(norm) > 1:
        norm = norm.rstrip("/")
    return norm


def _load_service_paths(service: str) -> set[str]:
    """Return the normalized OpenAPI paths for a service's FastAPI app.

    conftest.py has already put each service's `src` on sys.path, so
    `<service>.main:app` imports cleanly.
    """
    module = import_module(f"{_SERVICE_MODULES.get(service, service)}.main")
    app = getattr(module, "app")
    openapi = app.openapi()
    return {_normalize(p) for p in openapi.get("paths", {})}


def _manifest() -> dict[str, list[str]]:
    data = json.loads(_MANIFEST.read_text())
    return data["services"]


def _cases() -> list[tuple[str, str]]:
    return [
        (service, path)
        for service, paths in _manifest().items()
        for path in paths
    ]


def test_manifest_exists_and_is_nonempty() -> None:
    services = _manifest()
    assert services, "endpoints.json has no services"
    total = sum(len(v) for v in services.values())
    assert total >= 40, f"expected the full mobile surface (~50 routes), got {total}"


@pytest.mark.parametrize("service,mobile_path", _cases())
def test_mobile_route_exists_in_service(service: str, mobile_path: str) -> None:
    service_paths = _load_service_paths(service)
    assert _normalize(mobile_path) in service_paths, (
        f"mobile calls {service} {mobile_path!r} but no matching route exists in "
        f"the service OpenAPI. Either the backend renamed/removed it (breaking the "
        f"shipped app) or apps/mobile/contract/endpoints.json is stale."
    )
