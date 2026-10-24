"""Mobile release helpers: version parity, release manifests, and 'how stale is the shipped app?'.

Policy: no EAS / Expo cloud builds (see .cursor/rules/no-eas-build-mobile.mdc) and no OTA updates. The JS bundle is
embedded in every native build, so ANY change under the app's source ships only with a new native build.
"""
from __future__ import annotations

import hashlib
import json
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional, Tuple

# Paths whose change requires a NEW NATIVE BUILD, in two tiers.
NATIVE_PATHS = (
    "apps/mobile/app.json", "apps/mobile/app.config.js", "apps/mobile/package.json", "apps/mobile/plugins/",
    "apps/mobile/ios/", "apps/mobile/android/", "apps/mobile/scripts/mobile-patch-native.js",
    "apps/mobile/pnpm-lock.yaml",
)
BUNDLE_PATHS = ("apps/mobile/src/", "apps/mobile/assets/", "apps/mobile/App.tsx", "apps/mobile/index.ts",
                "apps/mobile/babel.config.js", "apps/mobile/metro.config.js", "packages/sdk/")
# Version-only edits do not make a build stale.
VERSION_KEYS = {"version", "versionCode", "buildNumber"}


def parse_version(text: str) -> tuple[int, int, int]:
    m = re.search(r"(\d+)\.(\d+)\.(\d+)", text or "")
    return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)  # type: ignore[return-value]


def compare_versions(a: str, b: str) -> int:
    pa, pb = parse_version(a), parse_version(b)
    return (pa > pb) - (pa < pb)


@dataclass
class Parity:
    ok: bool
    versions: dict[str, str] = field(default_factory=dict)
    problems: list[str] = field(default_factory=list)


def check_parity(repo_root: Path) -> Parity:
    """VERSION, apps/mobile/package.json, app.json (+ build number keys) and src/version.ts must agree."""
    v: dict[str, str] = {}
    problems: list[str] = []
    v["VERSION"] = (repo_root / "VERSION").read_text().strip()
    v["package.json"] = json.loads((repo_root / "apps/mobile/package.json").read_text()).get("version", "")
    expo = json.loads((repo_root / "apps/mobile/app.json").read_text()).get("expo", {})
    v["app.json"] = expo.get("version", "")
    ios_build = (expo.get("ios") or {}).get("buildNumber")
    if ios_build is not None:
        v["ios.buildNumber"] = str(ios_build)
    ts = (repo_root / "apps/mobile/src/version.ts").read_text()
    m = re.search(r'(?:GENERATED_VERSION|APP_VERSION)\s*=\s*"([^"]+)"', ts)
    v["src/version.ts"] = m.group(1) if m else ""
    for key, val in v.items():
        if not val:
            problems.append(f"{key}: missing")
        elif val != v["VERSION"]:
            problems.append(f"{key}={val} does not match VERSION={v['VERSION']}")
    return Parity(ok=not problems, versions=v, problems=problems)


def _strip_versions(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _strip_versions(x) for k, x in obj.items() if k not in VERSION_KEYS}
    if isinstance(obj, list):
        return [_strip_versions(x) for x in obj]
    return obj


def native_config_changed(old_text: str, new_text: str, kind: str) -> bool:
    """True when app.json / package.json changed in a way that is not just a version bump."""
    try:
        old, new = json.loads(old_text or "{}"), json.loads(new_text or "{}")
    except json.JSONDecodeError:
        return True
    if kind == "package.json":
        keep = ("dependencies", "devDependencies", "pnpm", "overrides", "resolutions", "scripts")
        old, new = {k: old.get(k) for k in keep}, {k: new.get(k) for k in keep}
    return _strip_versions(old) != _strip_versions(new)


def classify_changed_paths(paths: Iterable[str]) -> dict[str, list[str]]:
    native, bundle = [], []
    for p in paths:
        if p in ("apps/mobile/app.json", "apps/mobile/package.json"):
            native.append(p)  # caller refines with native_config_changed when it has both blobs
        elif p.startswith(NATIVE_PATHS):
            native.append(p)
        elif p.startswith(BUNDLE_PATHS) and "__tests__" not in p and not p.endswith((".test.ts", ".test.tsx")):
            bundle.append(p)
    return {"native": native, "bundle": bundle}


@dataclass
class Staleness:
    published_version: str
    main_version: str
    versions_behind: int
    native_commits_behind: int  # files, not commits: native-affecting files changed since the published tag
    bundle_commits_behind: int  # files changed in the embedded JS bundle since the published tag
    platform: str = "android"

    def line(self) -> str:
        if not self.published_version:
            return f"Mobile ({self.platform}): no published build found - build and publish one (scripts/mobile_release.sh)"
        if self.versions_behind == 0:
            return f"Mobile ({self.platform}): published build v{self.published_version} is current"
        return (f"Mobile ({self.platform}): build v{self.published_version} is {self.versions_behind} version(s) behind "
                f"v{self.main_version}; {self.native_commits_behind} native-affecting and "
                f"{self.bundle_commits_behind} bundled-JS file(s) changed since")

    @property
    def needs_build(self) -> bool:
        return self.native_commits_behind > 0 or self.bundle_commits_behind > 0 or not self.published_version


def published_version_fallback(repo_root: Path) -> str:
    """Before the first manifest exists, the download route serves the APK named in its DEFAULT_APK_URL."""
    route = repo_root / "apps/web/app/download/android/route.ts"
    try:
        m = re.search(r"releases/android/v(\d+\.\d+\.\d+)/", route.read_text())
    except OSError:
        return ""
    return m.group(1) if m else ""


GitRunner = Callable[[list[str]], str]


def _git(repo_root: Path) -> GitRunner:
    def run(args: list[str]) -> str:
        import os
        env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
        p = subprocess.run(["git", *args], cwd=str(repo_root), text=True, capture_output=True, env=env)
        return p.stdout if p.returncode == 0 else ""
    return run


def staleness(repo_root: Path, published_version: str, platform: str = "android",
              git: Optional[GitRunner] = None, ref: str = "origin/main") -> Staleness:
    """How far behind main is the build users can download? Counts commits on the release path, not just versions."""
    git = git or _git(repo_root)
    main_version = (git(["show", f"{ref}:VERSION"]) or (repo_root / "VERSION").read_text()).strip()
    if not published_version:
        return Staleness("", main_version, 0, 0, 0, platform)
    tag = f"v{published_version}"
    have_tag = bool(git(["rev-parse", "--verify", "--quiet", tag]).strip())
    tags = [t for t in git(["tag", "--list", "v*"]).split() if parse_version(t) > parse_version(published_version)
            and parse_version(t) <= parse_version(main_version)]
    versions_behind = len(tags) if tags else max(0, sum(a - b for a, b in zip(parse_version(main_version), parse_version(published_version))))
    native = bundle = 0
    if have_tag:
        changed = git(["diff", "--name-only", f"{tag}..{ref}", "--", "apps/mobile", "packages/sdk"]).split()
        kinds = classify_changed_paths(changed)
        refined: list[str] = []
        for p in kinds["native"]:
            if p in ("apps/mobile/app.json", "apps/mobile/package.json"):
                kind = "package.json" if p.endswith("package.json") else "app.json"
                if native_config_changed(git(["show", f"{tag}:{p}"]), git(["show", f"{ref}:{p}"]), kind):
                    refined.append(p)
            else:
                refined.append(p)
        native = len(refined)
        bundle = len(kinds["bundle"])
    return Staleness(published_version, main_version, versions_behind, native, bundle, platform)


# ----------------------------------------------------------------------------- release manifest

def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            h.update(chunk)
    return h.hexdigest()


def build_manifest(*, version: str, version_code: int, git_sha: str, apk_url: str, sha256: str, size: int,
                   built_at: str, min_supported: str = "") -> dict[str, Any]:
    return {
        "platform": "android", "version": version, "versionCode": version_code, "git_sha": git_sha,
        "url": apk_url, "sha256": sha256, "size": size, "built_at": built_at, "min_supported": min_supported,
        "filename": f"salareen-{version}-{version_code}-release.apk",
    }


def versions_to_prune(existing: Iterable[str], keep: int = 5) -> list[str]:
    """Release folder versions to delete: everything older than the newest `keep`."""
    ordered = sorted(set(existing), key=parse_version, reverse=True)
    return ordered[keep:]


def update_decision(current: str, manifest: Optional[dict[str, Any]], dismissed: str = "") -> dict[str, Any]:
    """Same logic the app uses: {'prompt': bool, 'force': bool, 'latest': str}. Kept here so it is tested once."""
    if not manifest or not manifest.get("version"):
        return {"prompt": False, "force": False, "latest": ""}
    latest = str(manifest["version"])
    newer = compare_versions(latest, current) > 0
    minimum = str(manifest.get("min_supported") or "")
    force = bool(minimum) and compare_versions(current, minimum) < 0
    return {"prompt": newer and (force or dismissed != latest), "force": force, "latest": latest}


_APK_NAME = re.compile(r"^salareen-(\d+\.\d+\.\d+)-(\d+)-release\.apk$")


def apk_identity(apk_name: str) -> Optional[Tuple[str, int]]:
    """(version, versionCode) from a build_release filename like salareen-0.97.11-9711-release.apk, else None.

    The manifest must describe the APK being published, never the checkout it happens to be published from;
    otherwise the app is told a newer version is available than the file actually is.
    """
    m = _APK_NAME.match(apk_name)
    return (m.group(1), int(m.group(2))) if m else None
