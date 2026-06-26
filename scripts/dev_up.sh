#!/usr/bin/env bash
# Bring the full AI Classroom stack up locally and wire everything together.
# macOS + Linux. One command: ./scripts/dev_up.sh   (or: make dev-all)
#
# - ensures the Python venv (.venv) and web deps exist (make install / web-install)
# - loads config/local.env, then overlays secrets from .env.local (gitignored)
#   so live integrations (LINKEDIN_API_KEY, STRIPE_API_KEY, ...) turn on
# - starts all 8 FastAPI services + the Next.js web app (idempotent: skips
#   anything already healthy), logging to ./logs/<name>.log
# - health-checks everything and prints a status summary + which live keys are set
set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"
LOGS="$ROOT/logs"; mkdir -p "$LOGS"

say() { printf "\033[1;36m%s\033[0m\n" "$*"; }
ok()  { printf "  \033[1;32m✓\033[0m %s\n" "$*"; }
warn(){ printf "  \033[1;33m!\033[0m %s\n" "$*"; }

# --- 1. dependencies ------------------------------------------------------- #
if [ ! -x "$ROOT/.venv/bin/uvicorn" ] && [ ! -x "$ROOT/.venv/bin/python3" ]; then
  say "Creating Python venv + installing backend deps (make install)…"
  make install
fi
if [ ! -d "$ROOT/apps/web/node_modules" ]; then
  say "Installing web deps (make web-install)…"
  make web-install
fi
VENV_PY="$ROOT/.venv/bin/python3"

# --- 2. environment / live keys ------------------------------------------- #
# Robust KEY=VALUE loader (same approach as scripts/run_local_service.sh, which
# avoids `source` because docker-style env files can break bash parsing).
load_env() {
  local file="$1"; [ -f "$file" ] || return 0
  while IFS= read -r line; do
    line="${line%%$'\r'}"
    [[ -z "$line" || "$line" =~ ^[[:space:]]*# ]] && continue
    local key="${line%%=*}" val="${line#*=}"
    [[ -z "$key" ]] && continue
    val="${val#\"}"; val="${val%\"}"
    export "$key=$val"
  done < "$file"
}
load_env "$ROOT/config/local.env"      # base defaults
load_env "$ROOT/.env.local"            # overlay real secrets (wins) for live mode
export DEPLOY_MODE="${DEPLOY_MODE:-local}"
export AUTH_SIGNING_KEY="${AUTH_SIGNING_KEY:-dev-auth-signing-key}"
export ADMIN_SECRET="${ADMIN_SECRET:-dev-admin-secret}"
export HIL_AUTONOMY="${HIL_AUTONOMY:-autonomous}"
export CURRICULUM_DIR="${CURRICULUM_DIR:-$ROOT/sample-curriculum}"
export ENABLE_TEST_ENDPOINTS="${ENABLE_TEST_ENDPOINTS:-1}"
export AOEP_GIT_SHA="${AOEP_GIT_SHA:-$(git rev-parse --short HEAD 2>/dev/null || echo dev)}"

# --- 3. services ----------------------------------------------------------- #
# name|port|module|dir
SERVICES=(
  "orchestrator|8000|orchestrator.main:app|services/orchestrator"
  "speech|8002|speech_gw.main:app|services/speech"
  "perception|8003|perception.main:app|services/perception"
  "memory|8004|memory.main:app|services/memory"
  "curriculum|8005|curriculum.main:app|services/curriculum"
  "billing|8006|billing.main:app|services/billing"
  "integrations|8007|integrations.main:app|services/integrations"
  "identity|8008|identity.main:app|services/identity"
)

healthy() { curl -fsS "http://127.0.0.1:$1/health" >/dev/null 2>&1; }
web_up()  { curl -fsS -o /dev/null "http://127.0.0.1:3000" >/dev/null 2>&1; }

say "Starting backend services…"
for spec in "${SERVICES[@]}"; do
  IFS="|" read -r name port module dir <<< "$spec"
  if healthy "$port"; then ok "$name already running (:$port)"; continue; fi
  ( cd "$ROOT/$dir" && PYTHONPATH=src nohup "$VENV_PY" -m uvicorn "$module" \
      --host 127.0.0.1 --port "$port" >"$LOGS/$name.log" 2>&1 & echo $! >"$LOGS/$name.pid" )
  ok "$name starting (:$port) — logs/$name.log"
done

say "Starting web app…"
if web_up; then ok "web already running (:3000)"; else
  ( cd "$ROOT/apps/web" && nohup npm run dev >"$LOGS/web.log" 2>&1 & echo $! >"$LOGS/web.pid" )
  ok "web starting (:3000) — logs/web.log"
fi

# --- 4. wait + health summary --------------------------------------------- #
say "Waiting for health…"
for _ in $(seq 1 30); do
  all=1
  for spec in "${SERVICES[@]}"; do IFS="|" read -r _ port _ _ <<< "$spec"; healthy "$port" || all=0; done
  web_up || all=0
  [ "$all" = 1 ] && break
  sleep 2
done

echo
say "AI Classroom — local stack"
for spec in "${SERVICES[@]}"; do
  IFS="|" read -r name port _ _ <<< "$spec"
  if healthy "$port"; then ok "$(printf '%-13s' "$name") http://localhost:$port  (/health /version /__meta /metrics)"
  else warn "$(printf '%-13s' "$name") NOT healthy — see logs/$name.log"; fi
done
if web_up; then ok "$(printf '%-13s' web) http://localhost:3000"; else warn "web not ready yet — see logs/web.log"; fi

echo
say "Live integrations"
any=0
for k in LINKEDIN_API_KEY JOBS_API_KEY STRIPE_API_KEY OPENAI_API_KEY LLM_BASE_URL \
         BING_SEARCH_KEY GOOGLE_CSE_KEY SENTRY_DSN OTEL_EXPORTER_OTLP_ENDPOINT; do
  if [ -n "${!k:-}" ]; then ok "$k set (live)"; any=1; fi
done
[ "$any" = 0 ] && warn "No live keys detected — running on mocks/sandbox."
[ -f "$ROOT/.env.local" ] || warn "No .env.local — add real keys there to enable live providers (see docs/run-local.txt)."
echo
echo "Status:  ./scripts/dev_status.sh   ·   Stop:  ./scripts/dev_down.sh   (make dev-down)"
