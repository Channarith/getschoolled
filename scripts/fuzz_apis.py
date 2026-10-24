#!/usr/bin/env python3
"""Fuzz every FastAPI app in the repo for 5xx responses and slow routes.

Each app runs in its own subprocess (so import side effects and env never leak),
through Starlette's TestClient with fake upstreams: no Redis, no paid API keys,
no GPU. Valid, empty, malformed, oversized and unicode bodies are sent to every
route in the app's OpenAPI document.

  python3 scripts/fuzz_apis.py                      # all apps, normal mode
  python3 scripts/fuzz_apis.py --light              # fewer variants, no huge bodies
  python3 scripts/fuzz_apis.py --only identity,speech
  python3 scripts/fuzz_apis.py --headers            # non-ASCII auth headers on every request
  python3 scripts/fuzz_apis.py --auth               # signed-in: valid bearer token + admin headers
  python3 scripts/fuzz_apis.py --report out/fuzz.json

Exit status is 1 when any app returns a 5xx (or cannot be imported), so it can gate CI.
Routes that block for a long time on purpose can be skipped per app with
FUZZ_SKIP (comma-separated path fragments) or --skip app=frag1,frag2.
"""

from __future__ import annotations

import argparse
import importlib
import json
import os
import re
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# name -> (module:attribute, directory that must be on sys.path)
APPS: dict[str, tuple[str, str]] = {
    "identity": ("identity.main:app", "services/identity/src"),
    "billing": ("billing.main:app", "services/billing/src"),
    "memory": ("memory.main:app", "services/memory/src"),
    "perception": ("perception.main:app", "services/perception/src"),
    "speech": ("speech_gw.main:app", "services/speech/src"),
    "curriculum": ("curriculum.main:app", "services/curriculum/src"),
    "orchestrator": ("orchestrator.main:app", "services/orchestrator/src"),
    "integrations": ("integrations.main:app", "services/integrations/src"),
    "vision_agent": ("vision_agent.main:app", "services/vision_agent/src"),
    "webcam": ("webcam.main:app", "services/webcam/src"),
    "cosyvoice": ("server:app", "services/cosyvoice"),
    "children_lab": ("theodore_children_webcam_lab.main:app", "subrepos/theodore_children_webcam_lab/src"),
    "course_studio": ("theodore_course_studio.main:app", "subrepos/theodore_course_studio/src"),
    "audio_translation_lab": ("theodore_audio_translation_lab.main:app", "subrepos/theodore_audio_translation_lab/src"),
    "drive_lab": ("theodore_drive_lab.main:app", "subrepos/theodore_drive_lab/src"),
    "homework_lab": ("theodore_homework_lab.main:app", "subrepos/theodore_homework_lab/src"),
    "llm_lab": ("theodore_llm_lab.main:app", "subrepos/theodore_llm_lab/src"),
    "music_lab": ("theodore_music_lab.main:app", "subrepos/theodore_music_lab/src"),
    "rag_lab": ("theodore_rag_lab.main:app", "subrepos/theodore_rag_lab/src"),
    "webcam_lab": ("theodore_webcam_lab.main:app", "subrepos/theodore_webcam_lab/src"),
    "labs_theodore_webcam": ("theodore_webcam.main:app", "labs/theodore-webcam/src"),
    "labs_recognition_api": ("webcam_recognition.app:app", "labs/webcam-recognition-api/src"),
    "labs_recognition": ("webcam_lab.server:app", "labs/webcam-recognition/src"),
    "apps_webcam_lab": ("webcam_lab_app.main:app", "apps/webcam-lab/src"),
}

# Routes that run for minutes by design (training, course builds). By default they only
# get bodies that fail validation (bad JSON, a list, a string, an oversized blob) so the
# fuzzer can never start a real run; FUZZ_LONG=1 fuzzes them like any other route.
LONG_ROUTES: dict[str, str] = {
    "rag_lab": "/train,/training",
    "course_studio": "/courses/build,/training/run,/training/offline",
}

HUGE = "A" * 2_000_000
UNI = "héllo 你好 \U0001f697 ‮ ខ្មែរ \x00"
BAD_HEADER = "caféÿ.éx".encode("latin-1")
AUTH_USER = {"sub": "fuzz-user", "email": "fuzz@example.com"}


def _sample(openapi: dict, schema: dict, depth: int = 0, bad: bool = False):
    if depth > 12:  # self-referencing schemas ($ref cycles) must not recurse forever
        return None
    if "$ref" in schema:
        return _sample(openapi, openapi["components"]["schemas"][schema["$ref"].split("/")[-1]], depth + 1, bad)
    for key in ("anyOf", "oneOf"):
        if key in schema:
            return _sample(openapi, schema[key][0], depth + 1, bad)
    if "allOf" in schema:
        return _sample(openapi, schema["allOf"][0], depth + 1, bad)
    kind = schema.get("type")
    if "enum" in schema:
        return schema["enum"][0]
    if kind == "object" or "properties" in schema:
        if depth > 4:
            return {}
        return {k: _sample(openapi, v, depth + 1, bad) for k, v in schema.get("properties", {}).items()}
    if kind == "array":
        return [_sample(openapi, schema.get("items", {}), depth + 1, bad)] if depth < 4 else []
    if kind == "integer":
        return -1 if bad else 1
    if kind == "number":
        return 1e308 if bad else 1.5
    if kind == "boolean":
        return True
    return UNI if bad else "x"


class _FakeCosyModel:
    sample_rate = 24000

    def _audio(self, *args, **kwargs):
        yield {"tts_speech": [i / 40000.0 for i in range(240)]}

    inference_sft = inference_instruct2 = inference_zero_shot = inference_cross_lingual = _audio

    def list_available_spks(self):
        return ["en"]


# 501/503 mean "this engine or dependency is not available here", which is an honest,
# expected answer when the upstream is down. They are reported but are not failures.
UNAVAILABLE = (501, 503)


def _auth_headers(client) -> dict:
    """A valid session bearer token plus the operator headers, so handler bodies run."""
    from aoep_shared.auth import sign_token

    key = os.environ.get("AUTH_SIGNING_KEY", "dev-auth-signing-key").encode()
    token = sign_token(AUTH_USER, key)
    try:
        r = client.post("/auth/signup", json={"email": "fuzz-signup@example.com", "password": "Fuzz-pass-123!", "name": "Fuzz"})
        if r.status_code < 300 and isinstance(r.json(), dict) and r.json().get("token"):
            token = r.json()["token"]
    except Exception:
        pass
    return {
        "authorization": f"Bearer {token}",
        "x-admin-secret": os.environ.get("ADMIN_SECRET", ""),
        "x-internal-token": os.environ.get("INTERNAL_TOKEN", ""),
        "x-metrics-token": os.environ.get("METRICS_TOKEN", ""),
    }


def fuzz_one(name: str, light: bool, headers_mode: bool, auth_mode: bool) -> dict:
    """Runs inside the subprocess. Returns the report dict for one app."""
    for key in ("REDIS_URL", "XAI_API_KEY", "GROK_API_KEY", "ELEVENLABS_API_KEY", "OPENAI_API_KEY", "ANTHROPIC_API_KEY"):
        os.environ.pop(key, None)
    os.environ.setdefault("RATE_LIMIT_DISABLED", "1")
    spec, _ = APPS[name]
    module_name, attr = spec.split(":")
    started = time.time()
    try:
        module = importlib.import_module(module_name)
        app = getattr(module, attr)
        if name == "cosyvoice":  # no GPU here: a fake model exercises every synthesis mode
            app = module.build_app(model=_FakeCosyModel())
    except Exception as exc:  # import-level failure is itself a finding
        return {"app": name, "status": "import-failed", "error": f"{type(exc).__name__}: {exc}"[:300]}

    from fastapi.testclient import TestClient

    client = TestClient(app, raise_server_exceptions=False)
    openapi = app.openapi()
    skip = [s for s in os.environ.get("FUZZ_SKIP", "").split(",") if s] + ["/admin/shutdown"]  # stops the server by design
    long_frags = [] if os.environ.get("FUZZ_LONG") else [s for s in LONG_ROUTES.get(name, "").split(",") if s]
    base_headers = _auth_headers(client) if auth_mode else {}
    if headers_mode:
        base_headers = {**base_headers, "authorization": b"Bearer " + BAD_HEADER, "x-internal-token": BAD_HEADER,
                        "x-admin-secret": BAD_HEADER, "x-metrics-token": BAD_HEADER, "x-user-id": BAD_HEADER,
                        "x-api-key": BAD_HEADER}

    hits, count, skipped = [], 0, []
    for path, ops in openapi["paths"].items():
        if any(s in path for s in skip):
            skipped.append(path)
            continue
        is_long = any(s in path for s in long_frags)
        for method, op in ops.items():
            if method.lower() not in ("get", "post", "put", "patch", "delete"):
                continue
            if is_long and method.lower() == "get":
                continue
            fills = ("x", "../../etc/passwd", "ខ្មែរ-é", "0", "9" * 40)
            urls = []
            for fill in fills:
                url = path
                for p in op.get("parameters", []):
                    if p["in"] == "path":
                        url = url.replace("{" + p["name"] + "}", fill)
                urls.append(re.sub(r"\{[^}]+\}", fill, url))
            if light:
                urls = urls[:2]
            body_schema = op.get("requestBody", {}).get("content", {}).get("application/json", {}).get("schema")
            queries = [{}, {"q": UNI, "limit": "-1", "lang": "zz", "locale": "xx", "course_id": "../x", "id": "x"}]
            for p in op.get("parameters", []):
                if p["in"] == "query" and p.get("required"):
                    queries.append({p["name"]: "x"})
            variants = [] if is_long else [(u, q, None, None) for u in urls for q in queries]
            if method.lower() in ("post", "put", "patch", "delete"):
                for u in urls[:2]:
                    variants += [(u, {}, None, b"{not json"), (u, {}, [], None), (u, {}, "str", None)]
                    if not is_long:
                        variants += [(u, {}, None, None), (u, {}, {}, None)]
                    if not light:
                        variants += [(u, {}, None, HUGE.encode())]
                        if not is_long:
                            variants += [(u, {}, {"x": HUGE}, None)]
                    if body_schema is not None and not is_long:
                        variants += [(u, {}, _sample(openapi, body_schema), None), (u, {}, _sample(openapi, body_schema, bad=True), None)]
            for url, query, js, raw in variants:
                count += 1
                kwargs = {"params": query, "headers": dict(base_headers)}
                if raw is not None:
                    kwargs["content"] = raw
                    kwargs["headers"]["content-type"] = "application/json"
                elif js is not None:
                    kwargs["json"] = js
                if os.environ.get("FUZZ_TRACE"):
                    print(f"TRACE {method.upper()} {url[:100]} {str(js)[:60] if js is not None else (raw[:20] if raw else '')}", file=sys.stderr, flush=True)
                t0 = time.time()
                try:
                    r = client.request(method.upper(), url, **kwargs)
                    code, body = r.status_code, r.text[:160]
                except Exception as exc:
                    code, body = 599, f"{type(exc).__name__}: {exc}"[:160]
                dt = time.time() - t0
                if code >= 500 or dt > 5:  # includes the expected-unavailable codes; split below
                    hits.append({"code": code, "method": method.upper(), "url": url[:120], "seconds": round(dt, 1), "body": body,
                                 "request": (str(js) if js is not None else (repr(raw[:60]) if raw else str(query)))[:200]})
    unique, unavailable, seen = [], [], set()
    for h in hits:
        key = (h["code"], h["method"], h["url"].split("x")[0][:30], h["body"][:50])
        if key in seen:
            continue
        seen.add(key)
        (unavailable if h["code"] in UNAVAILABLE and h["seconds"] <= 5 else unique).append(h)
    return {"app": name, "status": "ok" if not unique else "5xx", "requests": count, "paths": len(openapi["paths"]),
            "skipped_paths": skipped, "hits": unique, "unavailable": unavailable,
            "seconds": round(time.time() - started, 1)}


def _child(name: str, light: bool, headers_mode: bool, auth_mode: bool) -> None:
    print("REPORT " + json.dumps(fuzz_one(name, light, headers_mode, auth_mode)))


def _env_for(name: str, args) -> dict:
    env = dict(os.environ)
    paths = [str(ROOT / "packages/shared/src"), str(ROOT / "packages/sdk/src"), str(ROOT / APPS[name][1])]
    # Sibling services are importable too (some apps import their neighbours).
    paths += [str(p) for p in sorted((ROOT / "services").glob("*/src"))]
    env["PYTHONPATH"] = os.pathsep.join(paths + [env.get("PYTHONPATH", "")])
    env.setdefault("AOEP_DATA_DIR", "/tmp/aoep-fuzz-data")
    # Keep every writable cache out of the repo: a stray drive_content_cache.db inside
    # packages/shared is read back as real audio-course content.
    env.setdefault("DRIVE_CONTENT_DB", "/tmp/aoep-fuzz-data/drive_content_cache.db")
    env.setdefault("LLM_LAB_OUT_DIR", "/tmp/aoep-fuzz-data/llm_lab")
    env.setdefault("THEODORE_COURSE_STUDIO_DATA", "/tmp/aoep-fuzz-data/course_studio")
    env.setdefault("AOEP_TRAINING_INTAKE", "/tmp/aoep-fuzz-data/intake")
    env.setdefault("AOEP_VOICE_OUTPUT", "/tmp/aoep-fuzz-data/voice_output")
    env["RATE_LIMIT_DISABLED"] = "1"
    if args.headers or args.auth:
        env.setdefault("DEPLOY_MODE", "cloud")
        env.setdefault("ADMIN_SECRET", "s3cret")
        env.setdefault("METRICS_TOKEN", "m3tric")
        env.setdefault("INTERNAL_TOKEN", "int3rnal")
        env.pop("INTERNAL_AUTH_DISABLED", None)
    if args.skip:
        for item in args.skip:
            app_name, _, frags = item.partition("=")
            if app_name == name:
                env["FUZZ_SKIP"] = frags
    return env


def _repo_litter() -> set[str]:
    """Untracked and ignored files, so a fuzz run that writes into the repo is visible."""
    proc = subprocess.run(["git", "status", "--porcelain", "--ignored", "-uall"], cwd=ROOT, capture_output=True, text=True)
    skip = ("node_modules", "__pycache__", ".pytest_cache", ".pyc", "tsbuildinfo", ".claude/")
    return {line[3:] for line in proc.stdout.splitlines() if line[:2] in ("??", "!!") and not any(s in line for s in skip)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default="", help="comma-separated app names")
    ap.add_argument("--light", action="store_true")
    ap.add_argument("--headers", action="store_true")
    ap.add_argument("--auth", action="store_true")
    ap.add_argument("--skip", action="append", default=[], help="app=frag1,frag2")
    ap.add_argument("--report", default="")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--child", default="", help=argparse.SUPPRESS)
    args = ap.parse_args()
    if args.child:
        _child(args.child, args.light, args.headers, args.auth)
        return 0
    if args.list:
        for name, (spec, path) in APPS.items():
            print(f"{name:24} {spec:46} {path}")
        return 0

    names = [n for n in (args.only.split(",") if args.only else APPS) if n]
    unknown = [n for n in names if n not in APPS]
    if unknown:
        print("unknown apps:", ", ".join(unknown), file=sys.stderr)
        return 2
    reports, failed = [], False
    before = _repo_litter()
    for name in names:
        cmd = [sys.executable, str(Path(__file__).resolve()), "--child", name]
        cmd += [f for f, on in (("--light", args.light), ("--headers", args.headers), ("--auth", args.auth)) if on]
        try:
            proc = subprocess.run(cmd, env=_env_for(name, args), cwd=ROOT, capture_output=True, text=True, timeout=1800)
            line = next((l for l in proc.stdout.splitlines() if l.startswith("REPORT ")), None)
            report = json.loads(line[7:]) if line else {"app": name, "status": "crashed", "error": f"exit {proc.returncode}: " + (proc.stderr or proc.stdout)[-2500:]}
        except subprocess.TimeoutExpired:
            report = {"app": name, "status": "timeout"}
        reports.append(report)
        flag = "OK " if report["status"] == "ok" else "!! "
        extra = (f"{report.get('requests', 0)} req, {len(report.get('hits', []))} failing, "
                 f"{len(report.get('unavailable', []))} unavailable(501/503)") if "requests" in report else report.get("error", report["status"])
        print(f"{flag}{name:24} {report['status']:14} {extra}")
        for hit in report.get("hits", []):
            print(f"     {hit['code']} {hit['method']} {hit['url']}  {hit['body'][:80]}")
            if os.environ.get("FUZZ_VERBOSE"):
                print(f"        request: {hit.get('request', '')}")
        failed = failed or report["status"] != "ok"
    litter = sorted(_repo_litter() - before)
    if litter:
        print("!! the run left files inside the repo (remove them, and point the writer at a temp dir):")
        for item in litter:
            print("     " + item)
    if args.report:
        out = Path(args.report)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(reports, indent=2))
        print("report written to", out)
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
