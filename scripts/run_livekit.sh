#!/usr/bin/env bash
# Run a LiveKit server locally for native dev (no Docker) so Salareen live-room
# video (tier 2) actually connects. Downloads the pinned livekit-server binary
# once into a cache, then runs it with keys that MATCH the orchestrator's
# LIVEKIT_API_KEY/SECRET — otherwise the server rejects minted tokens with 401.
#
# Usage: ./scripts/run_livekit.sh            # foreground on :7880
# Env:   LIVEKIT_API_KEY (default devkey), LIVEKIT_API_SECRET (default devsecret),
#        LIVEKIT_VERSION (default 1.8.0, matches infra/k8s/livekit.yaml).
set -euo pipefail

VERSION="${LIVEKIT_VERSION:-1.8.0}"
API_KEY="${LIVEKIT_API_KEY:-devkey}"
API_SECRET="${LIVEKIT_API_SECRET:-devsecret}"
CACHE="${AOEP_LIVEKIT_CACHE:-$HOME/.cache/aoep/livekit}"
BIN="$CACHE/livekit-server-$VERSION"

os="$(uname -s | tr '[:upper:]' '[:lower:]')"   # linux | darwin
arch="$(uname -m)"
case "$arch" in
  x86_64|amd64) arch=amd64 ;;
  arm64|aarch64) arch=arm64 ;;
  *) echo "unsupported arch: $arch" >&2; exit 1 ;;
esac

if [[ ! -x "$BIN" ]]; then
  mkdir -p "$CACHE"
  url="https://github.com/livekit/livekit/releases/download/v${VERSION}/livekit_${VERSION}_${os}_${arch}.tar.gz"
  echo "downloading livekit-server v$VERSION ($os/$arch)…"
  tmp="$(mktemp -d)"
  if ! curl -sSL -m 120 -o "$tmp/lk.tar.gz" "$url"; then
    echo "ERROR: could not download LiveKit ($url). Check network egress." >&2
    exit 1
  fi
  tar -xzf "$tmp/lk.tar.gz" -C "$tmp"
  mv "$tmp/livekit-server" "$BIN"
  chmod +x "$BIN"
  rm -rf "$tmp"
fi

echo "LiveKit v$VERSION on ws://localhost:7880 (keys: ${API_KEY}:${API_SECRET})"
# --dev = permissive local WebRTC; LIVEKIT_KEYS overrides the built-in
# placeholder (devkey:secret) so the keys match the orchestrator.
exec env LIVEKIT_KEYS="${API_KEY}: ${API_SECRET}" "$BIN" --dev --bind 0.0.0.0
