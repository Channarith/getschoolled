"""Preflight for the cloning models: what is missing before a clone run can work, and the command that fixes each thing.

  <model venv python> -m tts_bakeoff.voice_clone.doctor --model voxcpm2|cosyvoice2        (scripts/check_clone_models.sh runs both)

Run it with the model's own Python (the one scripts/run_voice_clone.sh uses): the imports are checked in that environment.
Read-only: it never downloads or installs anything.
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from tts_bakeoff import adapters

COSY_SETUP = (
    "git clone --recursive https://github.com/FunAudioLLM/CosyVoice.git ~/code/CosyVoice",
    "cd ~/code/CosyVoice && python3.10 -m venv .venv      # the CosyVoice README recommends Python 3.10",
    "cd ~/code/CosyVoice && .venv/bin/pip install -r requirements.txt   # on aarch64 some pins may need adjusting",
    "cd ~/code/CosyVoice && .venv/bin/python -c \"from modelscope import snapshot_download; "
    "snapshot_download('iic/CosyVoice2-0.5B', local_dir='pretrained_models/CosyVoice2-0.5B')\"",
)


def _cuda() -> str:
    try:
        import torch

        return f"torch {torch.__version__}, cuda {'available' if torch.cuda.is_available() else 'NOT available'}"
    except Exception as exc:  # noqa: BLE001
        return f"torch not importable ({type(exc).__name__})"


def diagnose(model: str) -> dict:
    adapter = adapters.get(model)
    chk = adapter.check()
    problems, fixes, notes = list(chk["problems"]), [], [f"python {sys.executable}", _cuda()]
    if model == "cosyvoice2":
        repo = Path(os.environ.get("COSYVOICE_REPO") or Path.home() / "code" / "CosyVoice")
        notes.append(f"repo {repo}; weights {adapter.model_dir()}; Matcha-TTS {'present' if (repo / 'third_party' / 'Matcha-TTS').is_dir() else 'MISSING'}")
        if not repo.is_dir():
            problems.append(f"CosyVoice repo not found at {repo}")
            fixes += list(COSY_SETUP)
        else:
            if not (repo / ".venv" / "bin" / "python").exists():
                problems.append(f"no virtualenv at {repo}/.venv")
                fixes += list(COSY_SETUP[1:3])
            if not (repo / "third_party" / "Matcha-TTS").is_dir():
                problems.append("third_party/Matcha-TTS is missing (the clone was not recursive)")
                fixes.append(f"cd {repo} && git submodule update --init --recursive")
        if not Path(adapter.model_dir()).is_dir():
            fixes.append(COSY_SETUP[3])
        notes.append("CosyVoice 2 does not list Cantonese: it is skipped for yue (use VoxCPM2)")
    if model == "voxcpm2":
        import sysconfig

        if not (Path(sysconfig.get_paths()["include"]) / "Python.h").exists():
            notes.append("Python.h missing: Triton cannot compile, so the run sets TORCHDYNAMO_DISABLE=1 (slower). Fix: sudo apt-get install -y python3.12-dev")
    return {"model": model, "ok": not problems, "problems": problems, "fixes": list(dict.fromkeys(fixes)), "notes": notes}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--model", required=True, choices=("voxcpm2", "cosyvoice2"))
    a = ap.parse_args(argv)
    r = diagnose(a.model)
    print(f"{r['model']}: {'READY' if r['ok'] else 'NOT READY'}")
    for n in r["notes"]:
        print(f"  note: {n}")
    for p in r["problems"]:
        print(f"  problem: {p}")
    for f in r["fixes"]:
        print(f"  fix: {f}")
    return 0 if r["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
