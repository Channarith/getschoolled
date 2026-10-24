#!/usr/bin/env python3
"""Mobile release helper used by scripts/mobile_release.sh and the merge train.

  python3 scripts/mobile_release.py parity                      # VERSION vs package.json vs app.json vs src/version.ts
  python3 scripts/mobile_release.py staleness [--published V]   # how far behind main is the downloadable build?
  python3 scripts/mobile_release.py manifest --apk FILE --url URL --out latest.json
  python3 scripts/mobile_release.py prune-list --keep 5 < versions.txt

No EAS / Expo cloud anything: builds are native only (see .cursor/rules/no-eas-build-mobile.mdc).
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared import mobile_release as mr  # noqa: E402

DEFAULT_MANIFEST_URL = "https://salareen-prod.sjc1.vultrobjects.com/releases/android/latest.json"


def cmd_parity(_: argparse.Namespace) -> int:
    p = mr.check_parity(ROOT)
    for k, v in p.versions.items():
        print(f"  {k:<18} {v}")
    if p.ok:
        print("version parity: ok")
        return 0
    print("version parity: MISMATCH")
    for problem in p.problems:
        print("  - " + problem)
    print("Fix with: python3 scripts/bump_pr_version.py (it updates every file), then rebuild.")
    return 1


def _published(args: argparse.Namespace) -> str:
    if args.published:
        return args.published
    url = args.manifest_url or os.environ.get("ANDROID_MANIFEST_URL", DEFAULT_MANIFEST_URL)
    try:
        with urllib.request.urlopen(url, timeout=8) as r:  # noqa: S310 (fixed https URL)
            return str(json.load(r).get("version", ""))
    except Exception:
        return mr.published_version_fallback(ROOT)


def cmd_staleness(args: argparse.Namespace) -> int:
    subprocess.run(["git", "fetch", "-q", "origin", "main", "--tags"], cwd=str(ROOT), capture_output=True)
    s = mr.staleness(ROOT, _published(args), args.platform)
    print(s.line())
    if args.json:
        print(json.dumps(s.__dict__, indent=2))
    return 2 if (args.strict and s.needs_build) else 0


def cmd_manifest(args: argparse.Namespace) -> int:
    apk = Path(args.apk)
    expo = json.loads((ROOT / "apps/mobile/app.json").read_text())["expo"]
    ident = mr.apk_identity(apk.name)
    if args.version:
        version, code = args.version, int(args.version_code or 0)
    elif ident:
        version, code = ident
    else:
        print(f"cannot tell the version of {apk.name}: use the build filename salareen-<ver>-<code>-release.apk "
              "or pass --version and --version-code", file=sys.stderr)
        return 2
    sha = subprocess.run(["git", "rev-parse", "HEAD"], cwd=str(ROOT), text=True, capture_output=True).stdout.strip()
    if version != expo["version"]:
        sha = ""  # built from an older commit than this checkout: do not claim HEAD's sha
    data = mr.build_manifest(
        version=version, version_code=code, git_sha=sha, apk_url=args.url, sha256=mr.sha256_file(apk),
        size=apk.stat().st_size, built_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(apk.stat().st_mtime)),
        min_supported=args.min_supported,
    )
    Path(args.out).write_text(json.dumps(data, indent=2) + "\n")
    print(json.dumps(data, indent=2))
    return 0


def cmd_prune(args: argparse.Namespace) -> int:
    for v in mr.versions_to_prune([ln.strip().lstrip("v") for ln in sys.stdin if ln.strip()], args.keep):
        print(v)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("parity").set_defaults(fn=cmd_parity)
    s = sub.add_parser("staleness")
    s.add_argument("--published", default="")
    s.add_argument("--manifest-url", default="")
    s.add_argument("--platform", default="android")
    s.add_argument("--json", action="store_true")
    s.add_argument("--strict", action="store_true", help="exit 2 when a new native build is needed")
    s.set_defaults(fn=cmd_staleness)
    m = sub.add_parser("manifest")
    m.add_argument("--apk", required=True)
    m.add_argument("--url", required=True)
    m.add_argument("--out", required=True)
    m.add_argument("--version", default="", help="override: version of the APK (default: parsed from its filename)")
    m.add_argument("--version-code", default="", help="override: versionCode of the APK")
    m.add_argument("--min-supported", default="")
    m.set_defaults(fn=cmd_manifest)
    pr = sub.add_parser("prune-list")
    pr.add_argument("--keep", type=int, default=5)
    pr.set_defaults(fn=cmd_prune)
    args = ap.parse_args()
    return args.fn(args)


if __name__ == "__main__":
    raise SystemExit(main())
