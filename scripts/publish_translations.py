#!/usr/bin/env python3
"""Publish validated course translations from the Spark and kalel to the PRIVATE prefix of the object store.

  scripts/publish_translations.sh                  # pull + build + dry-run (changes nothing in the bucket)
  scripts/publish_translations.sh --yes            # ... then upload (private objects, manifest last)
  python3 scripts/publish_translations.py withdraw --lang km [--course audio-x] [--yes] [--prune]

Steps (each can be run alone):
  pull      rsync the libraries from each machine into <staging>/_src/<label>/ (read-only on the machines, key-based ssh only).
  build     keep only files that are a translation of TODAY's English and pass the v2 validator; newest valid wins; a valid
            published file is never replaced by a stale or held one; write <staging>/library and <staging>/_delivery.json.
  upload    dry-run unless --yes: upload changed files (ACL private) and the manifest LAST; --prune also deletes objects that
            left the manifest. Nothing is public: the service reads with the cluster's credentials.
  withdraw  remove a language and/or a course from the manifest (the service stops serving it at once), then --prune deletes objects.
  status    what the bucket manifest says (counts per language) and what the staging build would publish.

Credentials: OBJECT_STORE_ACCESS_KEY / OBJECT_STORE_SECRET_KEY (or AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY) from the environment or
config/local.env. They are passed to the `aws` CLI through its environment, never on a command line, and never printed.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared import translation_delivery as dl  # noqa: E402

DEFAULT_SOURCES = "spark=nvidia@192.168.1.107:.cache/aoep/course_translations_v2,kalel=cvanthin@192.168.1.118:.cache/aoep/course_translations_v2"
DEFAULT_ENDPOINT = "https://sjc1.vultrobjects.com"
DEFAULT_BUCKET = "salareen-prod"
DEFAULT_PREFIX = "course-translations"
CRED_NAMES = ("OBJECT_STORE_ACCESS_KEY", "OBJECT_STORE_SECRET_KEY", "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY", "AWS_PROFILE")


def staging_dir(arg: Optional[str]) -> Path:
    return Path(arg or os.environ.get("TRANSLATIONS_STAGING") or "~/translations-staging").expanduser()


def parse_sources(spec: str) -> Dict[str, Tuple[str, str]]:
    out: Dict[str, Tuple[str, str]] = {}
    for part in [p.strip() for p in spec.split(",") if p.strip()]:
        label, _, rest = part.partition("=")
        host, _, path = rest.partition(":")
        if label and host and path:
            out[label] = (host, path)
    return out


def load_env_names(path: Path) -> Dict[str, str]:
    """Read only the credential/config names we need from config/local.env (no shell sourcing, no printing)."""
    wanted = set(CRED_NAMES) | {"OBJECT_STORE_ENDPOINT", "OBJECT_STORE_BUCKET"}
    found: Dict[str, str] = {}
    try:
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, value = line.partition("=")
            key = key.strip().removeprefix("export ").strip()
            if key in wanted:
                found[key] = value.strip().strip('"').strip("'")
    except OSError:
        pass
    return found


def store_config() -> Dict[str, str]:
    file_values = load_env_names(ROOT / "config" / "local.env")
    get = lambda k, d="": os.environ.get(k) or file_values.get(k) or d  # noqa: E731
    key = get("OBJECT_STORE_ACCESS_KEY") or get("AWS_ACCESS_KEY_ID")
    secret = get("OBJECT_STORE_SECRET_KEY") or get("AWS_SECRET_ACCESS_KEY")
    return {
        "endpoint": get("OBJECT_STORE_ENDPOINT", DEFAULT_ENDPOINT),
        "bucket": get("OBJECT_STORE_BUCKET", DEFAULT_BUCKET),
        "prefix": (os.environ.get("TRANSLATIONS_PREFIX") or DEFAULT_PREFIX).strip("/"),
        "key": key, "secret": secret, "profile": get("AWS_PROFILE"),
    }


def aws_env(cfg: Dict[str, str]) -> Dict[str, str]:
    env = dict(os.environ)
    if cfg["key"] and cfg["secret"]:
        env["AWS_ACCESS_KEY_ID"], env["AWS_SECRET_ACCESS_KEY"] = cfg["key"], cfg["secret"]
    env.setdefault("AWS_DEFAULT_REGION", "us-east-1")
    env["AWS_EC2_METADATA_DISABLED"] = "true"
    return env


def aws(cfg: Dict[str, str], *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    cmd = ["aws", "--endpoint-url", cfg["endpoint"], *args]
    return subprocess.run(cmd, env=aws_env(cfg), check=False, text=True, capture_output=capture)


def have_credentials(cfg: Dict[str, str]) -> bool:
    return bool((cfg["key"] and cfg["secret"]) or cfg["profile"])


def remote_manifest(cfg: Dict[str, str]) -> Optional[dict]:
    if not have_credentials(cfg):
        return None
    done = aws(cfg, "s3", "cp", f"s3://{cfg['bucket']}/{cfg['prefix']}/{dl.DELIVERY_NAME}", "-", "--only-show-errors", capture=True)
    if done.returncode != 0 or not done.stdout.strip():
        return None
    return dl.parse_manifest(done.stdout.encode("utf-8"))


# ---- pull -------------------------------------------------------------------------------------------------------------------------

def cmd_pull(a: argparse.Namespace) -> int:
    stage = staging_dir(a.staging)
    sources = parse_sources(os.environ.get("TRANSLATIONS_SOURCES", DEFAULT_SOURCES))
    only = {s for s in (a.sources or "").split(",") if s}
    got = 0
    for label, (host, path) in sources.items():
        if only and label not in only:
            continue
        dest = stage / "_src" / label
        dest.mkdir(parents=True, exist_ok=True)
        # Pull only: the remote folder is never modified. _work/ holds unfinished segments and must never be published.
        cmd = ["rsync", "-a", "-e", "ssh -o BatchMode=yes -o ConnectTimeout=10", "--exclude=_work/", "--include=*/", "--include=*.json", "--exclude=*",
               f"{host}:{path.rstrip('/')}/", f"{dest}/"]
        done = subprocess.run(cmd, check=False, text=True, capture_output=True)
        if done.returncode == 0:
            n = sum(1 for _ in dest.rglob("*.json"))
            print(f"pull {label}: {n} files in {dest}")
            got += 1
        else:
            print(f"pull {label}: SKIPPED ({(done.stderr or 'unreachable').strip().splitlines()[-1][:120] if done.stderr else 'unreachable'})")
    if not got:
        print("no machine answered: nothing pulled (staging keeps what it had)")
    return 0


# ---- build ------------------------------------------------------------------------------------------------------------------------

def cmd_build(a: argparse.Namespace) -> int:
    from aoep_shared import translation_v2 as v2

    stage = staging_dir(a.staging)
    roots = {p.name: p for p in sorted((stage / "_src").glob("*")) if p.is_dir()} if (stage / "_src").is_dir() else {}
    if not roots:
        print("no pulled libraries under", stage / "_src", "(run pull first)")
        return 1
    sources = v2.audio_sources() + (v2.studio_sources() if a.studio else [])
    langs = [c for c in (a.languages.split(",") if a.languages else v2.translatable_languages()) if c and c != "en"]
    library = stage / "library"
    previous_manifest = None
    try:
        previous_manifest = dl.parse_manifest((stage / dl.DELIVERY_NAME).read_bytes())
    except OSError:
        pass
    chosen, skipped = dl.select_valid(
        roots, sources, langs, is_current=lambda rec, src, lang: v2.is_current(rec, src, lang),
        previous=(previous_manifest or {}).get("files") if previous_manifest else None,
        previous_dir=library if previous_manifest else None,
    )
    # Rebuild the library folder from exactly the selected files (a file that went stale must leave the set).
    staged = stage / "library.new"
    shutil.rmtree(staged, ignore_errors=True)
    for item in chosen:
        target = staged / item.rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(item.path, target)
    shutil.rmtree(library, ignore_errors=True)
    staged.replace(library) if chosen else library.mkdir(parents=True, exist_ok=True)
    manifest = dl.build_manifest(
        {i.rel: {"sha256": i.sha256, "size": i.size, "validated_at": i.validated_at, "source_sha256": i.source_sha256} for i in chosen},
        pipeline=v2.PIPELINE_VERSION,
    )
    (stage / dl.DELIVERY_NAME).write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    (stage / "_skipped.json").write_text(json.dumps(skipped, indent=1) + "\n", encoding="utf-8")
    per_lang: Dict[str, int] = {}
    for item in chosen:
        per_lang[item.rel.rsplit("/", 1)[1][:-5]] = per_lang.get(item.rel.rsplit("/", 1)[1][:-5], 0) + 1
    print(f"build: {len(chosen)} publishable files of {len(sources) * len(langs)} course x language slots; {len(skipped)} slots had files that failed the validator")
    for lang, n in sorted(per_lang.items(), key=lambda kv: -kv[1]):
        print(f"  {lang:>4}: {n:>4} / {len(sources)}")
    return 0


# ---- upload / withdraw ------------------------------------------------------------------------------------------------------------

def _need_creds(cfg: Dict[str, str], yes: bool) -> bool:
    if yes and not have_credentials(cfg):
        print("no object-store credentials found (OBJECT_STORE_ACCESS_KEY/SECRET_KEY in the environment or config/local.env); nothing uploaded")
        return False
    return True


def cmd_upload(a: argparse.Namespace) -> int:
    stage = staging_dir(a.staging)
    try:
        new = dl.parse_manifest((stage / dl.DELIVERY_NAME).read_bytes())
    except OSError:
        new = None
    if new is None:
        print("no valid staging manifest: run build first")
        return 1
    cfg = store_config()
    if not _need_creds(cfg, a.yes):
        return 1
    remote = remote_manifest(cfg)
    plan = dl.plan_upload(new["files"], (remote or {}).get("files"))
    where = f"s3://{cfg['bucket']}/{cfg['prefix']}/ (private)"
    print(f"target {where}")
    print(f"  upload {len(plan['upload'])}, unchanged {len(plan['unchanged'])}, leaving the manifest {len(plan['withdrawn'])}"
          f"{' (objects deleted: --prune)' if a.prune else ' (objects kept: add --prune to delete them)'}")
    if remote is None:
        print("  (remote manifest not readable here: treating everything as new)" if have_credentials(cfg) else "  (no credentials: remote comparison skipped)")
    shrink = len(plan["withdrawn"])
    remote_count = len((remote or {}).get("files") or {})
    if remote_count and not new["files"] and not a.allow_shrink:
        print("REFUSED: the staging build is EMPTY and would withdraw everything already published. Pull and build again, or pass --allow-shrink.")
        return 3
    if remote_count >= 20 and shrink > remote_count // 2 and not a.allow_shrink:
        print(f"REFUSED: {shrink} of {remote_count} published files would leave the manifest (more than half). Check the build, or pass --allow-shrink.")
        return 3
    if not a.yes:
        print("dry run: nothing was uploaded. Re-run with --yes to publish.")
        return 0
    failed = 0
    for rel in plan["upload"]:
        done = aws(cfg, "s3", "cp", str(stage / "library" / rel), f"s3://{cfg['bucket']}/{cfg['prefix']}/{rel}", "--acl", "private",
                   "--content-type", "application/json", "--cache-control", "no-store", "--only-show-errors", capture=True)
        if done.returncode != 0:
            failed += 1
            print(f"  FAILED {rel}")
    if failed:
        print(f"{failed} uploads failed: the manifest was NOT updated, the service keeps serving the previous set")
        return 2
    done = aws(cfg, "s3", "cp", str(stage / dl.DELIVERY_NAME), f"s3://{cfg['bucket']}/{cfg['prefix']}/{dl.DELIVERY_NAME}", "--acl", "private",
               "--content-type", "application/json", "--cache-control", "no-store", "--only-show-errors", capture=True)
    if done.returncode != 0:
        print("manifest upload failed")
        return 2
    if a.prune:
        for rel in plan["withdrawn"]:
            aws(cfg, "s3", "rm", f"s3://{cfg['bucket']}/{cfg['prefix']}/{rel}", "--only-show-errors", capture=True)
    print(f"published {len(new['files'])} files, manifest {new['generated_at']}")
    return 0


def cmd_withdraw(a: argparse.Namespace) -> int:
    if not a.lang and not a.course:
        print("give --lang and/or --course")
        return 1
    cfg = store_config()
    if not _need_creds(cfg, a.yes):
        return 1
    remote = remote_manifest(cfg)
    if remote is None:
        print("cannot read the bucket manifest here (credentials or network): nothing changed")
        return 1
    kept, removed = dl.drop_matching(remote["files"], lang=a.lang, course=a.course)
    print(f"withdraw: {len(removed)} files leave the manifest ({len(kept)} stay)")
    for rel in removed[:10]:
        print("  -", rel)
    if not a.yes:
        print("dry run: nothing changed. Re-run with --yes.")
        return 0
    manifest = dl.build_manifest(kept, pipeline=remote.get("pipeline") or "")
    tmp = staging_dir(a.staging) / "_withdraw_delivery.json"
    tmp.parent.mkdir(parents=True, exist_ok=True)
    tmp.write_text(json.dumps(manifest, indent=1, sort_keys=True) + "\n", encoding="utf-8")
    done = aws(cfg, "s3", "cp", str(tmp), f"s3://{cfg['bucket']}/{cfg['prefix']}/{dl.DELIVERY_NAME}", "--acl", "private",
               "--content-type", "application/json", "--cache-control", "no-store", "--only-show-errors", capture=True)
    if done.returncode != 0:
        print("manifest upload failed: nothing withdrawn")
        return 2
    if a.prune:
        for rel in removed:
            aws(cfg, "s3", "rm", f"s3://{cfg['bucket']}/{cfg['prefix']}/{rel}", "--only-show-errors", capture=True)
    print("withdrawn: the service stops serving these files within its refresh interval (default 5 minutes)")
    return 0


def cmd_status(a: argparse.Namespace) -> int:
    stage = staging_dir(a.staging)
    cfg = store_config()
    for label, manifest in (("staging", _safe_manifest(stage / dl.DELIVERY_NAME)), ("bucket", remote_manifest(cfg))):
        if manifest is None:
            print(f"{label}: no manifest" + (" (no credentials)" if label == "bucket" and not have_credentials(cfg) else ""))
            continue
        per: Dict[str, int] = {}
        for rel in manifest["files"]:
            code = rel.rsplit("/", 1)[1][:-5]
            per[code] = per.get(code, 0) + 1
        print(f"{label}: {manifest['count']} files, generated {manifest['generated_at']}, pipeline {manifest['pipeline']}")
        print("   " + "  ".join(f"{k}:{v}" for k, v in sorted(per.items(), key=lambda kv: -kv[1])))
    return 0


def _safe_manifest(path: Path) -> Optional[dict]:
    try:
        return dl.parse_manifest(path.read_bytes())
    except OSError:
        return None


def main(argv: Optional[List[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--staging", help="staging folder (default ~/translations-staging or $TRANSLATIONS_STAGING)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("pull"); p.add_argument("--sources", help="comma list of machine labels (default all)")
    b = sub.add_parser("build"); b.add_argument("--studio", action="store_true", help="also the Course Studio catalog"); b.add_argument("--languages")
    u = sub.add_parser("upload"); u.add_argument("--yes", action="store_true"); u.add_argument("--prune", action="store_true")
    u.add_argument("--allow-shrink", action="store_true", help="publish even if it removes more than half of what is published (or everything)")
    w = sub.add_parser("withdraw"); w.add_argument("--lang"); w.add_argument("--course"); w.add_argument("--yes", action="store_true"); w.add_argument("--prune", action="store_true")
    sub.add_parser("status")
    a = ap.parse_args(argv)
    return {"pull": cmd_pull, "build": cmd_build, "upload": cmd_upload, "withdraw": cmd_withdraw, "status": cmd_status}[a.cmd](a)


if __name__ == "__main__":
    raise SystemExit(main())
