#!/usr/bin/env bash
# Show health of the local AI Classroom stack.
set -uo pipefail
PORTS=( "orchestrator:8000" "speech:8002" "perception:8003" "memory:8004" \
        "curriculum:8005" "billing:8006" "integrations:8007" "identity:8008" )
for p in "${PORTS[@]}"; do
  name="${p%%:*}"; port="${p##*:}"
  if curl -fsS "http://127.0.0.1:$port/health" >/dev/null 2>&1; then
    ver="$(curl -fsS "http://127.0.0.1:$port/version" 2>/dev/null | sed -n 's/.*"version":"\([^"]*\)".*/\1/p')"
    printf "  \033[1;32m●\033[0m %-13s http://localhost:%s   v%s\n" "$name" "$port" "${ver:-?}"
  else
    printf "  \033[1;31m○\033[0m %-13s http://localhost:%s   (down)\n" "$name" "$port"
  fi
done
if curl -fsS -o /dev/null "http://127.0.0.1:3000" 2>/dev/null; then
  printf "  \033[1;32m●\033[0m %-13s http://localhost:3000\n" "web"
else
  printf "  \033[1;31m○\033[0m %-13s http://localhost:3000   (down)\n" "web"
fi
