#!/usr/bin/env bash
# Probe memory pods for version + routes that the web app calls on every page load.
set -euo pipefail

NS="${NAMESPACE:-aoep}"

echo "=== memory pods ==="
kubectl -n "$NS" get pods -l app=memory -o wide 2>/dev/null || {
  echo "No memory deployment found in namespace $NS"
  exit 1
}

POD="$(kubectl -n "$NS" get pods -l app=memory \
  --field-selector=status.phase=Running \
  -o jsonpath='{.items[0].metadata.name}' 2>/dev/null || true)"
if [ -z "$POD" ]; then
  echo "No Running memory pod"
  exit 1
fi
echo "Probing pod: $POD"
echo ""

kubectl -n "$NS" exec "$POD" -- python3 - <<'PY'
import json
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
checks = [
    ("GET", "/version", None),
    ("GET", "/flags/access.homework_grader", None),
    ("GET", "/mascots/resolve?locale=en", None),
    ("GET", "/survey/onboarding?subject=test&tier=free", None),
]

def probe(method, path, body=None):
    req = urllib.request.Request(f"{BASE}{path}", data=body, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status, resp.read().decode()[:200]
    except urllib.error.HTTPError as exc:
        return exc.code, exc.read().decode()[:200]

fail = 0
for method, path, body in checks:
    code, snippet = probe(method, path, body)
    ok = code == 200
    if not ok:
        fail += 1
    print(f"{'OK' if ok else 'FAIL'} {code} {path}")
    if snippet.strip():
        print(f"  {snippet[:120]}")

if fail:
    print(
        f"\n{fail} check(s) failed — deploy memory (Deploy VKE with include_memory).",
        file=sys.stderr,
    )
    sys.exit(1)

print("\nMemory routes OK.")
PY
