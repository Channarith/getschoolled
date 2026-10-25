#!/usr/bin/env bash
# Set up the iBuyPower ("kalel": Ubuntu, RTX 5060 Ti 8 GB, Blackwell sm_120) as a GPU worker. Run ON that machine.
#
#   scripts/fleet/kalel_setup.sh                 # dry run: read-only checks and the exact steps it would take
#   scripts/fleet/kalel_setup.sh --apply         # do them (idempotent: finished steps are skipped)
#   scripts/fleet/kalel_setup.sh --smoke         # only the CUDA kernel test + the repo's CUDA policy check
#
# Options / environment:  --repo PATH (GS_REPO, default ~/getschoolled)  --venv PATH (GS_WORKER_VENV, default ~/venvs/gs-worker)
#   --no-ct2 (skip CTranslate2 / faster-whisper)   --convert-ct2 (also convert NLLB-200-3.3B to an int8 CTranslate2 folder, ~17 GB download)   GS_TORCH_INDEXES="cu128 cu129 cu130" (tried in this order)
#
# What it never does: use sudo, change system Python or system packages, store credentials, or touch other folders.
# Python: the system Python (3.14 here) is too new for the ML wheels, so uv creates a private 3.12 venv.
# Torch: the first CUDA index whose wheel passes a REAL kernel test on this GPU is kept. cu128 goes first because Blackwell
#   (sm_120) needs CUDA >= 12.8 and CTranslate2 is built for CUDA 12 libraries; cu13 builds may break the int8 path.
set -euo pipefail

APPLY=0 SMOKE_ONLY=0 WITH_CT2=1 CONVERT=0
CT2_DIR="${NLLB_CT2_DIR:-$HOME/models/nllb-200-3.3B-ct2-int8}"
REPO="${GS_REPO:-$HOME/getschoolled}"
VENV="${GS_WORKER_VENV:-$HOME/venvs/gs-worker}"
REPO_URL="${GS_REPO_URL:-https://github.com/Channarith/getschoolled.git}"
INDEXES="${GS_TORCH_INDEXES:-cu128 cu129 cu130}"
UV_INSTALLER="https://astral.sh/uv/install.sh"
while [ $# -gt 0 ]; do
  case "$1" in
    --apply) APPLY=1 ;;
    --smoke) SMOKE_ONLY=1 ;;
    --no-ct2) WITH_CT2=0 ;;
    --convert-ct2) CONVERT=1 ;;
    --repo) REPO="${2:?}"; shift ;;
    --venv) VENV="${2:?}"; shift ;;
    -h|--help) sed -n 2,17p "$0"; exit 0 ;;
    *) echo "unknown option: $1" >&2; exit 64 ;;
  esac
  shift
done

say() { printf '%s\n' "$*"; }
step() { printf '\n== %s\n' "$*"; }
run() { if [ "$APPLY" = 1 ]; then printf '  + %s\n' "$*"; "$@"; else printf '  (would run) %s\n' "$*"; fi; }
find_uv() { command -v uv 2>/dev/null || { for p in "$HOME/.local/bin/uv" "$HOME/.cargo/bin/uv"; do [ -x "$p" ] && { echo "$p"; return; }; done; }; }

smoke_torch() {  # a real kernel on this GPU, not just torch.cuda.is_available()
  "$VENV/bin/python" - <<'PY'
import sys
import torch
print("torch", torch.__version__, "cuda build", torch.version.cuda)
if not torch.cuda.is_available():
    print("SMOKE FAIL: torch.cuda.is_available() is False"); sys.exit(1)
cap = torch.cuda.get_device_capability(0)
arch = f"sm_{cap[0]}{cap[1]}"
archs = torch.cuda.get_arch_list()
print("gpu", torch.cuda.get_device_name(0), arch, "wheel archs", archs)
if not any(a in archs for a in (arch, f"compute_{cap[0]}{cap[1]}")):
    print(f"SMOKE FAIL: this torch build has no kernels for {arch}"); sys.exit(1)
try:
    a = torch.randn(256, 256, device="cuda"); b = torch.randn(256, 256, device="cuda")
    gpu = (a @ b).cpu(); cpu = a.cpu() @ b.cpu()
    assert torch.allclose(gpu, cpu, atol=1e-2, rtol=1e-3), "matmul mismatch"
    lin = torch.nn.Linear(64, 64).cuda().half(); lin(torch.randn(4, 64, device="cuda").half()).sum().item()
    torch.cuda.synchronize()
    print(f"SMOKE OK: kernels run on {arch}")
except Exception as exc:
    print(f"SMOKE FAIL: {type(exc).__name__}: {exc}"); sys.exit(1)
PY
}

policy_check() {  # the repo's own CUDA policy (aoep_shared.devices), which every GPU job goes through
  [ -d "$REPO/packages/shared/src" ] || { say "  (repo not at $REPO yet: policy check skipped)"; return 0; }
  PYTHONPATH="$REPO/packages/shared/src" "$VENV/bin/python" -c \
    "from aoep_shared import devices; ok, why = devices.cuda_smoke(); print('repo CUDA policy:', 'OK' if ok else 'FAIL: ' + why); raise SystemExit(0 if ok else 1)"
}

ct2_check() {
  "$VENV/bin/python" - <<'PY' || say "  CTranslate2 CUDA is NOT usable here: use the fp16 profile (NLLB_PROFILE=8gb), not 8gb-ct2"
import ctranslate2
types = ctranslate2.get_supported_compute_types("cuda")
print("ctranslate2", ctranslate2.__version__, "cuda compute types:", sorted(types))
raise SystemExit(0 if {"int8_float16", "float16"} & set(types) else 1)
PY
}

if [ "$SMOKE_ONLY" = 1 ]; then
  [ -x "$VENV/bin/python" ] || { echo "no venv at $VENV: run with --apply first" >&2; exit 2; }
  smoke_torch && policy_check
  exit $?
fi

say "kalel GPU worker setup: $([ "$APPLY" = 1 ] && echo APPLY || echo 'DRY RUN (nothing is changed; add --apply to do it)')"
say "repo: $REPO   venv: $VENV   torch indexes (in order): $INDEXES"

step "1. this machine (read-only)"
OS="$(uname -s)"; ARCH="$(uname -m)"
say "  os: $OS $ARCH"
if { [ "$OS" != "Linux" ] || [ "$ARCH" != "x86_64" ]; } && [ -z "${GS_ASSUME_LINUX:-}" ]; then  # GS_ASSUME_LINUX is for the tests only
  say "  NOTE: this is not the kalel box (Linux x86_64). Dry run only."
  [ "$APPLY" = 1 ] && { echo "refusing --apply: run this on kalel" >&2; exit 3; }
fi
if command -v nvidia-smi >/dev/null 2>&1; then
  say "  gpu: $(nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1)"
else
  say "  no nvidia-smi: no NVIDIA driver on this machine"
  [ "$APPLY" = 1 ] && { echo "refusing --apply without an NVIDIA driver" >&2; exit 3; }
fi
say "  system python: $(python3 --version 2>&1) (left alone; a private 3.12 venv is created because new system Pythons lack ML wheels)"
say "  free disk: $(df -h "$HOME" | awk 'NR==2{print $4}')"
for tool in git curl; do command -v "$tool" >/dev/null 2>&1 && say "  $tool: ok" || say "  $tool: MISSING (needs: sudo apt install $tool, a step for you, not run here)"; done

step "2. uv (a user-level Python/venv manager, installs to ~/.local/bin)"
UV="$(find_uv || true)"
if [ -n "$UV" ]; then say "  already installed: $UV"; else
  say "  installer: $UV_INSTALLER (downloaded to a temp file first so you can read it, then run)"
  if [ "$APPLY" = 1 ]; then
    tmp="$(mktemp)"; curl -LsSf "$UV_INSTALLER" -o "$tmp"; say "  sha256 $(sha256sum "$tmp" | cut -d' ' -f1)"; sh "$tmp"; rm -f "$tmp"; UV="$(find_uv)"
  else say "  (would run) curl -LsSf $UV_INSTALLER -o <tmp> && sh <tmp>"; UV="uv"; fi
fi

step "3. Python 3.12 venv"
if [ -x "$VENV/bin/python" ] && "$VENV/bin/python" -c 'import sys; raise SystemExit(0 if sys.version_info[:2]==(3,12) else 1)' 2>/dev/null; then
  say "  already there: $VENV"
else run "$UV" venv --python 3.12 "$VENV"; fi

step "4. PyTorch for Blackwell (sm_120), first index that passes a real kernel test"
if [ -x "$VENV/bin/python" ] && smoke_torch >/dev/null 2>&1; then say "  already working:"; smoke_torch | sed 's/^/    /'; else
  for idx in $INDEXES; do
    say "  trying https://download.pytorch.org/whl/$idx"
    if ! run "$UV" pip install --python "$VENV/bin/python" --index-url "https://download.pytorch.org/whl/$idx" --extra-index-url https://pypi.org/simple torch; then
      say "  install from $idx failed, trying the next one"; continue
    fi
    if [ "$APPLY" = 1 ]; then
      if smoke_torch | sed 's/^/    /'; then say "  keeping torch from $idx"; break; fi
      say "  $idx failed the kernel test, trying the next one"
    fi
  done
  [ "$APPLY" = 1 ] && ! smoke_torch >/dev/null 2>&1 && { echo "no torch build passed the sm_120 kernel test: see output above" >&2; exit 4; }
fi

step "5. translation + speech dependencies (checked against this GPU in step 7)"
PKGS="transformers sentencepiece accelerate protobuf sacrebleu numpy soundfile"
[ "$WITH_CT2" = 1 ] && PKGS="$PKGS ctranslate2 faster-whisper"
run "$UV" pip install --python "$VENV/bin/python" $PKGS
say "  bitsandbytes is NOT installed: 8-bit on Blackwell is unverified; the 8gb profile uses fp16 and 8gb-ct2 uses CTranslate2 int8."

if [ "$CONVERT" = 1 ] && [ "$WITH_CT2" = 1 ]; then
  step "5b. NLLB-200-3.3B -> int8 CTranslate2 (one time; loads the full model in RAM, needs ~14 GB free)"
  if [ -d "$CT2_DIR" ] && [ -n "$(ls -A "$CT2_DIR" 2>/dev/null)" ]; then say "  already converted: $CT2_DIR"
  else run mkdir -p "$(dirname "$CT2_DIR")"; run "$VENV/bin/ct2-transformers-converter" --model facebook/nllb-200-3.3B --quantization int8_float16 --output_dir "$CT2_DIR"; fi
fi

step "6. repo and wiring"
if [ -d "$REPO/.git" ]; then say "  repo present: $REPO ($(git -C "$REPO" rev-parse --short HEAD 2>/dev/null)); fetching only, no checkout"; run git -C "$REPO" fetch -q origin || say "  fetch failed (offline or no credentials?): continuing with the checkout as it is"
else say "  clone: $REPO_URL (needs your git credentials; none are stored by this script)"; run git clone "$REPO_URL" "$REPO"; fi
run "$UV" pip install --python "$VENV/bin/python" -e "$REPO/packages/shared"
if [ ! -e "$REPO/.venv" ]; then run ln -s "$VENV" "$REPO/.venv"; else say "  $REPO/.venv exists: left alone (translate_on_machine.sh activates it)"; fi
ENVF="$VENV/gs-env.sh"
if [ "$APPLY" = 1 ]; then
  cat > "$ENVF" <<'ENVEOF'
# sourced by the venv's activate: CUDA 12 libraries that pip installed with torch (CTranslate2 needs them on the library path)
for d in "$VIRTUAL_ENV"/lib/python3.12/site-packages/nvidia/*/lib; do [ -d "$d" ] && export LD_LIBRARY_PATH="$d${LD_LIBRARY_PATH:+:$LD_LIBRARY_PATH}"; done
export NLLB_PROFILE="${NLLB_PROFILE:-8gb}"   # 8 GB card: distilled-1.3B fp16 unless the planner/you choose 8gb-ct2
ENVEOF
  grep -q gs-env.sh "$VENV/bin/activate" || printf '\n. "%s"\n' "$ENVF" >> "$VENV/bin/activate"
  say "  wrote $ENVF and hooked it into the venv's activate"
else say "  (would write) $ENVF (library path for the pip CUDA libs, NLLB_PROFILE default 8gb) and source it from the venv's activate"; fi

step "7. verify"
if [ "$APPLY" = 1 ]; then
  set +u  # venv activate scripts read variables that may be unset
  # shellcheck disable=SC1091
  . "$VENV/bin/activate"
  set -u
  smoke_torch && policy_check
  if [ "$WITH_CT2" = 1 ]; then ct2_check; fi
else say "  (would run) the kernel test on this GPU, the repo's CUDA policy check, and the CTranslate2 CUDA check"; fi

step "sudo steps for you (none are run by this script)"
say "  none required. Only if git or curl were reported MISSING above: sudo apt install git curl"
step "next"
say "  scripts/fleet/kalel_setup.sh --smoke"
say "  . $VENV/bin/activate && python3 scripts/nllb_profile_bench.py --profiles 8gb --langs km,th,vi,es,zh --n 200 --save-outputs ~/bench"
say "  (the 8gb-ct2 profile needs a one-time model conversion first: see docs/fleet-work-split.txt)"
