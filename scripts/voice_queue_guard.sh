#!/usr/bin/env bash
# Keep the voice training queue running. If a pass is alive, do nothing.
# If the previous pass finished or the box rebooted, start another one.
# Cached audio is skipped, so a new pass keeps gaining text.
set -u
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"
STATUS="output/cosyvoice_voice_queue_status.json"
LOG="output/cosyvoice_batch_ingest_stdout.log"

running_pid=""
if [[ -f "$STATUS" ]]; then
  running_pid="$(python3 -c 'import json; s=json.load(open("output/cosyvoice_voice_queue_status.json")); print(s.get("pid") or "" if s.get("running") else "")' 2>/dev/null || true)"
fi
if [[ -n "$running_pid" ]] && kill -0 "$running_pid" 2>/dev/null; then
  exit 0
fi
if pgrep -f 'cosyvoice_batch_ingest.py' >/dev/null 2>&1; then
  exit 0
fi
mkdir -p output
rm -f output/cosyvoice_voice_queue.stop
nohup bash scripts/run_voice_queues.sh >> "$LOG" 2>&1 &
echo "$(date) guard relaunched voice queues (pid $!)" >> output/voice_queue_guard.log
