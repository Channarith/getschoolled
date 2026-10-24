#!/usr/bin/env bash
# Install the reboot behavior for this Spark.
#
# After a reboot: STEM training resumes, the 222-course translation resumes
# on CPU, ingest stays at one worker while the exam is alive, and Khmer
# CosyVoice does not load. This does not arm aoep-spark-train.timer and it
# does not restart the STEM service.
set -euo pipefail
REPO="$(cd "$(dirname "$0")/../.." && pwd)"
UNIT_DIR="${XDG_CONFIG_HOME:-$HOME/.config}/systemd/user"
SHARE="$HOME/.local/share/aoep-train"
HOLD="$SHARE/hold-voice-train"
mkdir -p "$UNIT_DIR" "$SHARE"

install -m 0755 "$REPO/training/systemd/translate-forever.sh" "$SHARE/translate-forever.sh"
install -m 0755 "$REPO/training/systemd/voice-ingest-forever.sh" "$SHARE/voice-ingest-forever.sh"
install -m 0644 "$REPO/training/systemd/aoep-course-translate.service" "$UNIT_DIR/aoep-course-translate.service"

if [[ ! -f "$HOLD" ]]; then
  printf '%s\n' "Held so a reboot cannot load Khmer CosyVoice from the base weights while the STEM exam needs the GPU. Remove this file and re-enable aoep-voice-train.service only after that exam is finished." >"$HOLD"
fi

voice="$SHARE/voice-forever.sh"
if [[ -f "$voice" ]] && ! grep -q 'hold-voice-train' "$voice"; then
  python3 - "$voice" <<'PY'
import sys
from pathlib import Path
path = Path(sys.argv[1])
text = path.read_text()
guard = '''HOLD="${HOME}/.local/share/aoep-train/hold-voice-train"
if [[ -f "$HOLD" ]]; then
  echo "=== voice train held; not loading base weights $(date -Is) ==="
  sleep 3600
  exit 0
fi
'''
needle = "set -u\n"
if needle not in text:
    raise SystemExit("voice-forever.sh has no set -u line to anchor the hold")
path.write_text(text.replace(needle, needle + guard, 1))
PY
fi

systemctl --user daemon-reload
systemctl --user disable --now aoep-voice-train.service
systemctl --user enable aoep-course-translate.service
echo "voice-train: $(systemctl --user is-enabled aoep-voice-train.service || true)"
echo "course-translate: $(systemctl --user is-enabled aoep-course-translate.service)"
echo "hold: $HOLD"
echo "spark timer left untouched"
