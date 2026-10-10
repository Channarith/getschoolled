"""Drive /audio-lab must not be swallowed by the curriculum /audio ingress."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
INGRESS_FILES = (
    ROOT / "infra/k8s-vke/ingress-vke.yaml",
    ROOT / "infra/k8s-vke/ingress-ip.yaml",
)

_PATH = re.compile(r"^(\s*)- path:\s*(\S+)\s*$")
_TYPE = re.compile(r"^\s*pathType:\s*(\S+)\s*$")
_BACKEND = re.compile(r"service:\s*\{\s*name:\s*([A-Za-z0-9_-]+)")


def nginx_prefix_matches(location: str, path_type: str, request: str) -> bool:
    """ingress-nginx Prefix is a string prefix, so /audio matches /audio-lab."""
    path = request.split("?", 1)[0]
    if path_type == "Exact":
        return path == location
    return path == location or path.startswith(location)


def path_groups(text: str) -> list[list[dict[str, str]]]:
    groups: list[list[dict[str, str]]] = []
    current: list[dict[str, str]] | None = None
    entry: dict[str, str] | None = None
    for line in text.splitlines():
        if line.strip() == "paths:":
            current = []
            groups.append(current)
            entry = None
            continue
        matched = _PATH.match(line)
        if matched and current is not None:
            entry = {"path": matched.group(2), "pathType": "Prefix", "backend": ""}
            current.append(entry)
            continue
        if entry is None:
            continue
        typed = _TYPE.match(line)
        if typed:
            entry["pathType"] = typed.group(1)
        backend = _BACKEND.search(line)
        if backend:
            entry["backend"] = backend.group(1)
    return [group for group in groups if group]


def backend_for(paths: list[dict[str, str]], request: str) -> str:
    matches = [
        item
        for item in paths
        if nginx_prefix_matches(item["path"], item["pathType"], request)
    ]
    assert matches, request
    exact = [item for item in matches if item["pathType"] == "Exact"]
    pool = exact or matches
    return max(pool, key=lambda item: len(item["path"]))["backend"]


def audio_groups() -> list[list[dict[str, str]]]:
    found: list[list[dict[str, str]]] = []
    for path in INGRESS_FILES:
        for group in path_groups(path.read_text()):
            if any(item["path"] == "/audio" for item in group):
                found.append(group)
    return found


def test_audio_prefix_would_steal_the_lab_without_a_longer_path() -> None:
    stolen = backend_for(
        [{"path": "/audio", "pathType": "Prefix", "backend": "curriculum"},
         {"path": "/", "pathType": "Prefix", "backend": "web"}],
        "/audio-lab",
    )
    assert stolen == "curriculum"


def test_drive_audio_lab_reaches_web_and_courses_stay_on_curriculum() -> None:
    groups = audio_groups()
    # www, apex, api, and the bare-IP ingress.
    assert len(groups) == 4
    for group in groups:
        assert backend_for(group, "/audio-lab") == "web"
        assert backend_for(group, "/audio-lab?target=en&source=auto") == "web"
        assert backend_for(group, "/audio-lab-api/health") == "web"
        assert backend_for(group, "/audio-lab-api/api/languages") == "web"
        assert backend_for(group, "/audio-lab-api/api/live-audio/client.js") == "web"
        assert backend_for(group, "/audio/courses") == "curriculum"
        assert backend_for(group, "/audio/categories") == "curriculum"


def test_web_build_proxies_audio_lab_to_the_lab_service() -> None:
    dockerfile = (ROOT / "apps/web/Dockerfile").read_text()
    rewrite = (ROOT / "apps/web/next.config.mjs").read_text()
    labs = (ROOT / "infra/k8s/labs.yaml").read_text()
    assert "ARG AUDIO_LAB_ORIGIN=http://audio-lab:8041" in dockerfile
    assert 'source: "/audio-lab", destination: `${audioLab}/lab`' in rewrite
    assert 'source: "/audio-lab-api/:path*", destination: `${audioLab}/:path*`' in rewrite
    assert "name: audio-lab" in labs
    assert "containerPort: 8041" in labs
    assert (ROOT / "subrepos/theodore_audio_translation_lab/Dockerfile").is_file()
