"""Publish the pre-rendered demo voice clips to Vultr Object Storage (S3 compatible) with the aws CLI.

  python3 -m tts_bakeoff.demo_voice.assets status
  python3 -m tts_bakeoff.demo_voice.assets sync [--assets DIR] [--dry-run] [--delete-missing] [--allow-deactivate ID] [--allow-shrink]
      (compares with the published list first and refuses to switch a live voice off or halve an index by accident)
  python3 -m tts_bakeoff.demo_voice.assets withdraw --speaker ID [--dry-run] [--yes]
  python3 -m tts_bakeoff.demo_voice.assets cors [--origin URL ...] [--apply]
  python3 -m tts_bakeoff.demo_voice.assets policy [--apply]

Same bucket as the Android releases (scripts/mobile_release.sh): OBJ_ENDPOINT / OBJ_BUCKET, objects under voice-assets/.
Clips are public-read PER OBJECT (--acl public-read, as the APK upload does), so the rest of the bucket stays private and no
bucket-level change is needed. `policy` is an optional prefix-scoped alternative. Credentials: VOICE_ASSETS_ACCESS_KEY /
VOICE_ASSETS_SECRET_KEY, AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY, an AWS_PROFILE, or OBJECT_STORE_ACCESS_KEY /
OBJECT_STORE_SECRET_KEY, from the environment or config/local.env. They reach `aws` only through its environment: never argv,
never printed. Stdlib only.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]
CLIP_CACHE = "public, max-age=31536000, immutable"   # clip keys are hashes of the text: never rewritten under the same key
JSON_CACHE = "public, max-age=300"                     # voices.json / index.json: a consent withdrawal lands within 5 minutes
DEFAULT_ORIGINS = ("https://salareen.com", "https://www.salareen.com")
VOICE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,40}")   # always used with fullmatch: "$" would also accept a trailing newline
CRED_PAIRS = (("VOICE_ASSETS_ACCESS_KEY", "VOICE_ASSETS_SECRET_KEY"), ("AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"),
              ("OBJECT_STORE_ACCESS_KEY", "OBJECT_STORE_SECRET_KEY"))
RULE_ID = "voice-assets"
POLICY_SID = "VoiceAssetsPublicRead"


@dataclass
class Settings:
    endpoint: str = "https://sjc1.vultrobjects.com"
    bucket: str = "salareen-prod"
    prefix: str = "voice-assets"
    public_base: str = ""
    creds: dict = field(default_factory=dict, repr=False)   # AWS_* env for the child process only
    cred_source: str = "none"

    @property
    def s3(self) -> str:
        return f"s3://{self.bucket}/{self.prefix}"


def read_env_file(path: Path, wanted: set[str]) -> dict[str, str]:
    """Only the wanted KEY=VALUE lines of a dotenv file; nothing else is read into the process."""
    out: dict[str, str] = {}
    if not path.is_file():
        return out
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        m = re.match(r"\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$", line)
        if m and m.group(1) in wanted:
            out[m.group(1)] = m.group(2).strip().strip("'\"")
    return out


def load_settings(env: dict | None = None, env_file: Path | None = None) -> Settings:
    env = dict(os.environ if env is None else env)
    names = {n for pair in CRED_PAIRS for n in pair}
    file_env = read_env_file(env_file if env_file is not None else ROOT / "config" / "local.env", names)
    s = Settings(endpoint=env.get("VOICE_ASSETS_ENDPOINT") or env.get("OBJ_ENDPOINT") or "https://sjc1.vultrobjects.com",
                 bucket=env.get("VOICE_ASSETS_BUCKET") or env.get("OBJ_BUCKET") or "salareen-prod",
                 prefix=(env.get("VOICE_ASSETS_PREFIX") or "voice-assets").strip("/"))
    u = urlparse(s.endpoint)
    if u.scheme != "https" or not u.hostname:
        raise SystemExit(f"endpoint must be https://<host>, got {s.endpoint!r}")
    s.endpoint = f"https://{u.hostname}"
    s.public_base = (env.get("VOICE_ASSETS_PUBLIC_BASE") or f"https://{s.bucket}.{u.hostname}").rstrip("/")
    if not re.fullmatch(r"[a-z0-9][a-z0-9.-]{1,61}[a-z0-9]", s.bucket) or not re.fullmatch(r"[A-Za-z0-9._-]+(/[A-Za-z0-9._-]+)*", s.prefix):
        raise SystemExit("bucket or prefix has unexpected characters")
    for src, pair in (("environment", env), ("config/local.env", file_env)):
        for ak, sk in CRED_PAIRS:
            if pair.get(ak) and pair.get(sk):
                s.creds = {"AWS_ACCESS_KEY_ID": pair[ak], "AWS_SECRET_ACCESS_KEY": pair[sk]}
                s.cred_source = f"{ak} ({src})"
                return s
    if env.get("AWS_PROFILE"):
        s.cred_source = f"AWS_PROFILE={env['AWS_PROFILE']}"
    return s


def aws_argv(s: Settings, *args: str) -> list[str]:
    return ["aws", "--endpoint-url", s.endpoint, *args]


def run_aws(s: Settings, *args: str, capture: bool = False) -> subprocess.CompletedProcess:
    env = {**os.environ, **s.creds}
    p = subprocess.run(aws_argv(s, *args), env=env, text=True, capture_output=capture)
    if p.returncode != 0:
        err = (p.stderr or "") if capture else ""
        for v in s.creds.values():
            err = err.replace(v, "***")
        raise SystemExit(f"aws failed (exit {p.returncode}): {' '.join(args[:3])} {err.strip()[:300]}")
    return p


def show(argv: list[str]) -> str:
    return " ".join(shlex.quote(a) for a in argv)


# ---------------------------------------------------------------------------- pre-upload sanity check
class SanityCheckUnavailable(RuntimeError):
    """The currently published list could not be read, so a safe comparison is impossible."""


def fetch_public_json(url: str, timeout: float = 15.0) -> dict | None:
    """A public-read JSON object, or None when it does not exist yet (404/403). Any other failure raises SanityCheckUnavailable."""
    req = urllib.request.Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "salareen-voice-assets/1"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:   # noqa: S310 - https URL built from the validated settings
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        if exc.code in (403, 404):
            return None
        raise SanityCheckUnavailable(f"{url}: HTTP {exc.code}") from exc
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SanityCheckUnavailable(f"{url}: {exc}") from exc


def _clip_set(index: dict | None) -> set[tuple[str, str]]:
    clips = (index or {}).get("clips") or {}
    return {(lang, h) for lang, hs in clips.items() for h in hs}


def local_indexes(root: Path, doc: dict) -> dict[str, dict]:
    out = {}
    for v in doc.get("voices", []):
        vid = str(v.get("id", ""))
        if not VOICE_ID.fullmatch(vid):
            continue
        try:
            out[vid] = json.loads((root / vid / "index.json").read_text(encoding="utf-8"))
        except (OSError, ValueError):
            out[vid] = {}
    return out


def remote_state(s: Settings) -> tuple[dict | None, dict[str, dict]]:
    base = f"{s.public_base}/{s.prefix}"
    doc = fetch_public_json(f"{base}/voices.json")
    idx = {}
    for v in (doc or {}).get("voices", []):
        vid = str(v.get("id", ""))
        if v.get("active") and VOICE_ID.fullmatch(vid):
            idx[vid] = fetch_public_json(f"{base}/{vid}/index.json") or {}
    return doc, idx


def publish_diff(local_doc: dict, local_idx: dict[str, dict], remote_doc: dict | None, remote_idx: dict[str, dict]) -> dict:
    """What this upload would change in what visitors get: voices switched on/off and clips added/removed per voice."""
    now = {str(v["id"]): bool(v.get("active")) for v in local_doc.get("voices", []) if v.get("id")}
    before = {str(v["id"]): bool(v.get("active")) for v in (remote_doc or {}).get("voices", []) if v.get("id")}
    diff = {"activated": sorted(i for i, on in now.items() if on and not before.get(i)),
            "deactivated": sorted(i for i, on in before.items() if on and not now.get(i)),
            "added": {}, "removed": {}, "shrunk": []}
    for vid in sorted(set(now) | set(before)):
        if not (now.get(vid) or before.get(vid)):
            continue
        new, old = _clip_set(local_idx.get(vid)) if now.get(vid) else set(), _clip_set(remote_idx.get(vid)) if before.get(vid) else set()
        if new - old:
            diff["added"][vid] = len(new - old)
        if old - new:
            diff["removed"][vid] = len(old - new)
        if old and now.get(vid) and len(new) * 2 < len(old):
            diff["shrunk"].append(vid)
    return diff


def format_diff(diff: dict) -> str:
    lines = ["what this upload changes for visitors:"]
    lines.append(f"  voices switched ON : {', '.join(diff['activated']) or '-'}")
    lines.append(f"  voices switched OFF: {', '.join(diff['deactivated']) or '-'}")
    for vid in sorted(set(diff["added"]) | set(diff["removed"])):
        lines.append(f"  {vid}: +{diff['added'].get(vid, 0)} clips listed, -{diff['removed'].get(vid, 0)} clips no longer listed")
    if not diff["added"] and not diff["removed"]:
        lines.append("  no clip listing changes")
    return "\n".join(lines)


def sanity_problems(diff: dict, allow_deactivate=(), allow_shrink: bool = False) -> list[str]:
    allowed = set(allow_deactivate or ())
    problems = [f"{vid} is ON in the published list and this upload would switch it OFF (add --allow-deactivate {vid} if that is intended; "
                "if you ran publish on a machine without the consent records, run it on the Spark instead)"
                for vid in diff["deactivated"] if vid not in allowed]
    if not allow_shrink:
        problems += [f"{vid}'s index.json would shrink to less than half of what is published (--allow-shrink if that is intended)" for vid in diff["shrunk"]]
    return problems


# ---------------------------------------------------------------------------- sync
def plan_sync(root: Path, s: Settings, delete_missing: bool = False, dryrun: bool = False) -> list[list[str]]:
    """aws arguments (without the endpoint) in the order they must run: clips, then each index.json, then voices.json last,
    so voices.json never points at a clip that is not there yet."""
    voices = root / "voices.json"
    if not voices.is_file():
        raise SystemExit(f"no {voices}: run 'python3 -m tts_bakeoff.demo_voice.render publish' first")
    doc = json.loads(voices.read_text(encoding="utf-8"))
    dr = ["--dryrun"] if dryrun else []
    # Only the clips of voices that are ACTIVE in voices.json and not marked REVOKED go up. A blanket "*.mp3" would also
    # publish clips of a voice that was switched off or whose speaker withdrew consent but whose files are still on disk.
    live = [v["id"] for v in doc.get("voices", [])
            if v.get("active") and VOICE_ID.fullmatch(str(v.get("id", ""))) and not (root / str(v["id"]) / "REVOKED").exists()]
    includes = [arg for vid in live for arg in ("--include", f"{vid}/*.mp3")]
    cmds: list[list[str]] = [["s3", "sync", str(root), s.s3 + "/", "--exclude", "*", *includes, "--exact-timestamps",
                              "--acl", "public-read", "--cache-control", CLIP_CACHE, "--content-type", "audio/mpeg",
                              *(["--delete"] if delete_missing else []), *dr]]
    for v in doc.get("voices", []):
        if v.get("id") in live:
            idx = root / v["id"] / "index.json"
            if not idx.is_file():
                raise SystemExit(f"{idx} missing: run render publish again")
            cmds.append(["s3", "cp", str(idx), f"{s.s3}/{v['id']}/index.json", "--acl", "public-read",
                         "--cache-control", JSON_CACHE, "--content-type", "application/json", *dr])
    cmds.append(["s3", "cp", str(voices), f"{s.s3}/voices.json", "--acl", "public-read", "--cache-control", JSON_CACHE,
                 "--content-type", "application/json", *dr])
    return cmds


def cmd_sync(a, s: Settings) -> int:
    root = Path(a.assets or os.environ.get("GS_VOICE_ASSETS") or Path.home() / "voice-assets").expanduser()
    mp3 = sorted(root.glob("*/*/*.mp3"))
    print(f"{len(mp3)} clips, {sum(p.stat().st_size for p in mp3) / 1e6:.1f} MB from {root} -> {s.s3}/  (public base {s.public_base}/{s.prefix})")
    cmds = plan_sync(root, s, a.delete_missing)
    local_doc = json.loads((root / "voices.json").read_text(encoding="utf-8"))
    if not getattr(a, "skip_sanity_check", False):
        try:
            remote_doc, remote_idx = remote_state(s)
        except SanityCheckUnavailable as exc:
            msg = f"cannot read the currently published list to compare against ({exc})"
            if a.dry_run:
                print(f"warning: {msg}; the safety check was skipped in this dry run")
            else:
                print(f"refusing to upload: {msg}. Check the network, or pass --skip-sanity-check to upload without the comparison.", file=sys.stderr)
                return 2
        else:
            diff = publish_diff(local_doc, local_indexes(root, local_doc), remote_doc, remote_idx)
            print(format_diff(diff))
            problems = sanity_problems(diff, getattr(a, "allow_deactivate", ()), getattr(a, "allow_shrink", False))
            if problems:
                for p in problems:
                    print(f"refusing to upload: {p}", file=sys.stderr)
                return 2
    if a.dry_run:
        for c in cmds:
            print("+", show(aws_argv(s, *c)))
        print("dry run: nothing uploaded, no credentials used")
        return 0
    for c in cmds:
        run_aws(s, *c)
    print(f"published. Web build arg NEXT_PUBLIC_VOICE_ASSETS_URL={s.public_base}/{s.prefix}  (mobile and Vision Play default to it)")
    return 0


# ---------------------------------------------------------------------------- withdraw
def deactivate_voice(doc: dict, voice: str) -> tuple[dict, bool]:
    found = False
    for v in doc.get("voices", []):
        if v.get("id") == voice or v.get("speaker") == voice:
            v["active"] = False
            found = True
    return doc, found


def cmd_withdraw(a, s: Settings) -> int:
    voice = a.speaker
    if not VOICE_ID.fullmatch(voice or "") or voice in {"voices", "voices.json"}:
        raise SystemExit(f"refusing speaker id {voice!r} (an empty or odd id would delete the wrong prefix)")
    target = f"{s.s3}/{voice}/"
    steps = [f"1. rewrite {s.s3}/voices.json with {voice} inactive (cache {JSON_CACHE}): clients stop looking the voice up",
             f"2. delete every object under {target}"]
    if a.dry_run or not a.yes:
        print("\n".join(steps))
        print("+", show(aws_argv(s, "s3", "rm", target, "--recursive", "--dryrun")))
        print("dry run: add --yes (without --dry-run) to do it" if not a.dry_run else "dry run: nothing changed")
        return 0
    cur = run_aws(s, "s3", "cp", f"{s.s3}/voices.json", "-", capture=True)
    doc, found = deactivate_voice(json.loads(cur.stdout), voice)
    if not found:
        print(f"note: {voice} is not listed in the remote voices.json; deleting its objects anyway", file=sys.stderr)
    import tempfile

    fd, tmp_name = tempfile.mkstemp(prefix=".voices-", suffix=".json")   # unpredictable name, mode 0600: no symlink games in /tmp
    tmp = Path(tmp_name)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(doc, indent=1))
    try:
        run_aws(s, "s3", "cp", str(tmp), f"{s.s3}/voices.json", "--acl", "public-read", "--cache-control", JSON_CACHE,
                "--content-type", "application/json")
    finally:
        tmp.unlink(missing_ok=True)
    run_aws(s, "s3", "rm", target, "--recursive")
    print(f"withdrawn: {voice} is inactive and its clips are deleted. Browsers may keep already-played clips for up to a year "
          f"(immutable cache); voices.json refreshes within 5 minutes. Also run: bakeoff revoke --speaker {voice}")
    return 0


# ---------------------------------------------------------------------------- cors / policy
def cors_rule(origins) -> dict:
    return {"ID": RULE_ID, "AllowedOrigins": list(origins), "AllowedMethods": ["GET", "HEAD"],
            "AllowedHeaders": ["Range", "Cache-Control", "Pragma", "If-None-Match", "If-Modified-Since"],
            "ExposeHeaders": ["ETag", "Content-Length", "Content-Range", "Accept-Ranges"], "MaxAgeSeconds": 3000}


def merge_cors(existing: dict | None, origins) -> dict:
    """put-bucket-cors REPLACES the whole bucket config, so keep every other rule and only swap ours."""
    rules = [r for r in (existing or {}).get("CORSRules", []) if r.get("ID") != RULE_ID]
    return {"CORSRules": [*rules, cors_rule(origins)]}


def policy_statement(s: Settings) -> dict:
    return {"Sid": POLICY_SID, "Effect": "Allow", "Principal": "*", "Action": ["s3:GetObject"],
            "Resource": [f"arn:aws:s3:::{s.bucket}/{s.prefix}/*"]}


def merge_policy(existing: dict | None, s: Settings) -> dict:
    doc = existing or {"Version": "2012-10-17", "Statement": []}
    doc["Statement"] = [x for x in doc.get("Statement", []) if x.get("Sid") != POLICY_SID] + [policy_statement(s)]
    return doc


def fetch_json(s: Settings, *args: str) -> dict | None:
    try:
        p = subprocess.run(aws_argv(s, *args), env={**os.environ, **s.creds}, text=True, capture_output=True)
    except FileNotFoundError:
        raise SystemExit("aws CLI not found")
    if p.returncode != 0:
        return None   # NoSuchCORSConfiguration / NoSuchBucketPolicy: nothing there yet
    data = json.loads(p.stdout or "{}")
    return json.loads(data["Policy"]) if "Policy" in data else data


def cmd_cors(a, s: Settings) -> int:
    merged = merge_cors(fetch_json(s, "s3api", "get-bucket-cors", "--bucket", s.bucket), a.origin or DEFAULT_ORIGINS)
    print(json.dumps(merged, indent=1))
    argv = aws_argv(s, "s3api", "put-bucket-cors", "--bucket", s.bucket, "--cors-configuration", json.dumps(merged))
    if not a.apply:
        print("\nnot applied (bucket-wide, keeps the existing rules). To apply:\n  ", show(argv))
        return 0
    run_aws(s, "s3api", "put-bucket-cors", "--bucket", s.bucket, "--cors-configuration", json.dumps(merged))
    print("CORS applied. Check:", f"curl -sI -H 'Origin: {DEFAULT_ORIGINS[0]}' {s.public_base}/{s.prefix}/voices.json | grep -i access-control")
    return 0


def cmd_policy(a, s: Settings) -> int:
    merged = merge_policy(fetch_json(s, "s3api", "get-bucket-policy", "--bucket", s.bucket), s)
    print(json.dumps(merged, indent=1))
    argv = aws_argv(s, "s3api", "put-bucket-policy", "--bucket", s.bucket, "--policy", json.dumps(merged))
    if not a.apply:
        print("\nnot applied. Optional: `sync` already makes each clip public-read with an object ACL. To apply this prefix policy:\n  ", show(argv))
        return 0
    run_aws(s, "s3api", "put-bucket-policy", "--bucket", s.bucket, "--policy", json.dumps(merged))
    print(f"policy applied. Verify prefix scope: {s.public_base}/{s.prefix}/voices.json must be 200 and a key outside "
          f"{s.prefix}/ that has no public ACL must be 403.")
    return 0


def cmd_status(a, s: Settings) -> int:
    print(json.dumps({"endpoint": s.endpoint, "bucket": s.bucket, "prefix": s.prefix, "public_base": f"{s.public_base}/{s.prefix}",
                      "credentials": s.cred_source, "aws_cli": bool(subprocess.run(["which", "aws"], capture_output=True).returncode == 0)}, indent=1))
    return 0


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("status")
    p = sub.add_parser("sync"); p.add_argument("--assets"); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--delete-missing", action="store_true", help="also delete remote clips that are no longer in the assets dir")
    p.add_argument("--allow-deactivate", action="append", default=[], metavar="VOICE", help="allow switching this published voice OFF (intended withdrawals only)")
    p.add_argument("--allow-shrink", action="store_true", help="allow a voice's index.json to shrink to less than half of what is published")
    p.add_argument("--skip-sanity-check", action="store_true", help="upload without comparing against the published list (for an unreachable network only)")
    p = sub.add_parser("withdraw"); p.add_argument("--speaker", required=True); p.add_argument("--dry-run", action="store_true")
    p.add_argument("--yes", action="store_true")
    p = sub.add_parser("cors"); p.add_argument("--origin", action="append"); p.add_argument("--apply", action="store_true")
    p = sub.add_parser("policy"); p.add_argument("--apply", action="store_true")
    a = ap.parse_args(argv)
    s = load_settings()
    return {"status": cmd_status, "sync": cmd_sync, "withdraw": cmd_withdraw, "cors": cmd_cors, "policy": cmd_policy}[a.cmd](a, s)


if __name__ == "__main__":
    raise SystemExit(main())
