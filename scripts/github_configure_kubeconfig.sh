#!/usr/bin/env bash
# Write ~/.kube/config for GitHub Actions deploy workflows.
#
# Required (one of):
#   KUBE_CONFIG_B64  — base64-encoded kubeconfig (preferred; one line, no newlines)
#   KUBE_CONFIG      — raw kubeconfig YAML (multiline GitHub secret)
#
# Generate KUBE_CONFIG_B64 from a VKE kubeconfig:
#   vultr-cli kubernetes config <cluster-id> > kubeconfig-vke.yaml
#   base64 -i kubeconfig-vke.yaml | tr -d '\n'    # macOS
#   base64 -w 0 kubeconfig-vke.yaml               # Linux
set -euo pipefail

CONFIG="${KUBECONFIG:-$HOME/.kube/config}"
mkdir -p "$(dirname "$CONFIG")"

write_config() {
  printf '%s' "$1" > "$CONFIG"
  chmod 600 "$CONFIG"
}

validate_config() {
  if [ ! -s "$CONFIG" ]; then
    echo "ERROR: kubeconfig file is empty" >&2
    return 1
  fi
  if ! python3 -c "
import sys
try:
    import yaml
except ImportError:
    sys.exit(0)
with open(sys.argv[1], encoding='utf-8', errors='replace') as f:
    yaml.safe_load(f)
" "$CONFIG" 2>/dev/null; then
    echo "ERROR: kubeconfig is not valid YAML" >&2
    return 1
  fi
  if ! kubectl config view --raw >/dev/null 2>&1; then
    echo "ERROR: kubectl cannot read kubeconfig" >&2
    return 1
  fi
  CTX="$(kubectl config current-context 2>/dev/null || echo unknown)"
  echo "OK kubeconfig loaded (context: ${CTX})"
  return 0
}

print_fix_hint() {
  echo "" >&2
  echo "Fix GitHub repo secret KUBE_CONFIG_B64:" >&2
  echo "  1. vultr-cli kubernetes config <cluster-id> > kubeconfig-vke.yaml" >&2
  echo "  2. base64 -i kubeconfig-vke.yaml | tr -d '\\n'   # macOS — paste ONE line" >&2
  echo "     base64 -w 0 kubeconfig-vke.yaml             # Linux" >&2
  echo "  3. Settings → Secrets → Actions → KUBE_CONFIG_B64 → update" >&2
  echo "  Do NOT paste raw YAML into KUBE_CONFIG_B64 unless it is base64-encoded." >&2
  echo "  Or use a multiline secret named KUBE_CONFIG with the raw YAML instead." >&2
  if [ -f "$CONFIG" ]; then
    echo "" >&2
    echo "Decoded file preview (first 3 lines):" >&2
    head -n 3 "$CONFIG" | sed 's/^/  /' >&2
  fi
}

# Preferred: regenerate a fresh kubeconfig straight from the Vultr API on every
# run. VKE client credentials rotate, so a once-captured KUBE_CONFIG_B64 silently
# expires and the deploy's roll step fails (cluster never picks up new images).
# With VULTR_API_KEY + VKE_CLUSTER_ID this is self-healing.
if [ -n "${VULTR_API_KEY:-}" ] && [ -n "${VKE_CLUSTER_ID:-}" ]; then
  echo "Fetching fresh kubeconfig from Vultr API for cluster ${VKE_CLUSTER_ID}…"
  RESP="$(curl -fsS -H "Authorization: Bearer ${VULTR_API_KEY}" \
    "https://api.vultr.com/v2/kubernetes/clusters/${VKE_CLUSTER_ID}/config" 2>/dev/null || true)"
  if [ -n "$RESP" ] && KCFG="$(printf '%s' "$RESP" | python3 -c \
      'import sys,json,base64; print(base64.b64decode(json.load(sys.stdin)["kube_config"]).decode())' 2>/dev/null)"; then
    write_config "$KCFG"
    if validate_config; then
      echo "OK kubeconfig regenerated from Vultr API."
      exit 0
    fi
    echo "WARN: Vultr API kubeconfig invalid — falling back to KUBE_CONFIG_B64…" >&2
  else
    echo "WARN: Vultr API config fetch/parse failed — falling back to KUBE_CONFIG_B64…" >&2
  fi
fi

if [ -n "${KUBE_CONFIG:-}" ]; then
  write_config "$KUBE_CONFIG"
  if validate_config; then
    exit 0
  fi
  print_fix_hint
  exit 1
fi

if [ -z "${KUBE_CONFIG_B64:-}" ]; then
  echo "ERROR: GitHub secret KUBE_CONFIG_B64 is empty (or KUBE_CONFIG not set)." >&2
  print_fix_hint
  exit 1
fi

# Collapse accidental newlines/spaces from copy-paste into the secret.
B64="$(printf '%s' "$KUBE_CONFIG_B64" | tr -d '[:space:]')"

DECODED=""
if DECODED="$(printf '%s' "$B64" | base64 -d 2>/dev/null)"; then
  write_config "$DECODED"
  if validate_config; then
    exit 0
  fi
  echo "WARN: base64 decoded but kubeconfig invalid — trying secret as raw YAML…" >&2
fi

# Common mistake: raw kubeconfig YAML stored in KUBE_CONFIG_B64 without encoding.
write_config "$KUBE_CONFIG_B64"
if validate_config; then
  echo "WARN: loaded raw YAML from KUBE_CONFIG_B64 — re-save as base64 for reliability." >&2
  exit 0
fi

echo "ERROR: could not load a valid kubeconfig from KUBE_CONFIG_B64." >&2
print_fix_hint
exit 1
