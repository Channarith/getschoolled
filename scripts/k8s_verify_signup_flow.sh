#!/usr/bin/env bash
# End-to-end signup + learning-profile smoke test on VKE (run where kubectl works).
# Confirms new accounts get a default student, can save the survey to identity
# (cloud-persisted onboarding_completed_at), and skip is also persisted.
set -euo pipefail

NS="${NAMESPACE:-aoep}"
EMAIL="signup-smoke-$(date +%s)@salareen.com"
PASSWORD="SmokeTest1"

echo "=== VKE new-account smoke test (namespace=$NS) ==="

POD="$(
  kubectl -n "$NS" get pods -l app=identity \
    -o jsonpath='{range .items[?(@.status.phase=="Running")]}{.metadata.name}{"\n"}{end}' \
    | head -n1
)"
if [[ -z "$POD" ]]; then
  echo "No Running identity pod." >&2
  exit 1
fi
echo "Identity pod: $POD"

kubectl -n "$NS" exec -i "$POD" -- env "SMOKE_EMAIL=$EMAIL" "SMOKE_PASSWORD=$PASSWORD" python3 - <<'PY'
import json
import os
import sys
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8000"
email = os.environ["SMOKE_EMAIL"]
password = os.environ["SMOKE_PASSWORD"]

def req(method, path, body=None, headers=None):
    h = dict(headers or {})
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        h.setdefault("content-type", "application/json")
    r = urllib.request.Request(f"{BASE}{path}", data=data, headers=h, method=method)
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            return resp.status, json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        return exc.code, json.loads(exc.read().decode() or "{}")

code, signup = req("POST", "/auth/signup", {
    "email": email, "password": password, "display_name": "Smoke Test",
})
if code != 200 or "token" not in signup:
    print("FAIL signup", code, signup, file=sys.stderr)
    sys.exit(1)
token = signup["token"]
auth = {"Authorization": f"Bearer {token}"}
print("OK signup", email)

code, students = req("GET", "/students", headers=auth)
if code != 200 or not students.get("students"):
    print("FAIL default student missing", code, students, file=sys.stderr)
    sys.exit(1)
sid = students["students"][0]["id"]
print("OK default student", sid)

answers = {
    "primary_style": "Mixed — no single style stands out",
    "pace": "Moderate and steady",
    "structure": "Step-by-step in order",
    "session_length": "About 10 minutes",
    "group_preference": "Either works for me",
    "reading_level": "Intermediate",
    "motivation": "Personal curiosity",
}
code, saved = req("POST", f"/students/{sid}/learning-profile", {"answers": answers}, auth)
if code != 200 or not saved.get("recorded"):
    print("FAIL learning-profile save", code, saved, file=sys.stderr)
    sys.exit(1)
print("OK learning-profile saved", saved.get("learner_category"))

code, prof = req("GET", f"/students/{sid}", headers=auth)
if code != 200 or not prof.get("onboarding_completed_at"):
    print("FAIL onboarding_completed_at not persisted", code, prof, file=sys.stderr)
    sys.exit(1)
print("OK onboarding_completed_at", prof["onboarding_completed_at"])

# Second account: skip path
email2 = email.replace("@", "+skip@")
code, signup2 = req("POST", "/auth/signup", {
    "email": email2, "password": password, "display_name": "Skip Test",
})
token2 = signup2["token"]
auth2 = {"Authorization": f"Bearer {token2}"}
sid2 = req("GET", "/students", headers=auth2)[1]["students"][0]["id"]
code, skipped = req("POST", f"/students/{sid2}/learning-profile/skip", headers=auth2)
if code != 200 or not skipped.get("skipped"):
    print("FAIL skip endpoint", code, skipped, file=sys.stderr)
    sys.exit(1)
code, prof2 = req("GET", f"/students/{sid2}", headers=auth2)
if not prof2.get("onboarding_completed_at"):
    print("FAIL skip not persisted", prof2, file=sys.stderr)
    sys.exit(1)
print("OK skip persisted")

print("\nAll new-account checks passed.")
PY

echo ""
echo "Tip: after Deploy VKE, also run:"
echo "  ./scripts/k8s_verify_qa_login.sh"
echo "  ./scripts/k8s_verify_memory.sh"
