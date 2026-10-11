#!/usr/bin/env python3
"""Pipecat-oriented CosyVoice TTS service + minimal pipeline config.

Wraps the AOEP CosyVoice HTTP sidecar (COSYVOICE_URL /tts) so NVIDIA
voice-agent-examples / Pipecat stacks can treat it like a TTS service.

This module is intentionally dependency-light: it does not import pipecat at
import time. When pipecat is installed (see ~/code/voice-agent-examples),
``CosyVoiceTTSService`` can be dropped into a Pipeline as a frame processor
subclass if you extend it; ``synthesize`` / ``run_text_to_wav`` work standalone.

Env:
  COSYVOICE_URL           http://127.0.0.1:9880
  COSYVOICE_DEFAULT_SPK   英文女
  COSYVOICE_MODE          sft
  A2F_GRPC_URL            127.0.0.1:52000  (optional handoff)

Example:
  python3 scripts/pipecat_cosyvoice/pipeline_config.py --text "Hello."
  python3 scripts/pipecat_cosyvoice/pipeline_config.py --text "Hello." --to-a2f
"""
from __future__ import annotations

import argparse
import asyncio
import os
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

import httpx

ROOT = Path(__file__).resolve().parents[2]


@dataclass
class CosyVoicePipecatConfig:
    """Declarative config for a CosyVoice leg inside a Pipecat voice pipeline."""

    cosyvoice_url: str = field(
        default_factory=lambda: os.environ.get("COSYVOICE_URL", "http://127.0.0.1:9880").rstrip("/")
    )
    speaker: str = field(
        default_factory=lambda: os.environ.get("COSYVOICE_DEFAULT_SPK", "英文女")
    )
    mode: str = field(default_factory=lambda: os.environ.get("COSYVOICE_MODE", "sft"))
    language: str = "en"
    sample_rate: int = 24000
    a2f_grpc_url: str = field(
        default_factory=lambda: os.environ.get("A2F_GRPC_URL", "127.0.0.1:52000")
    )
    # Optional: path to NVIDIA voice-agent-examples checkout
    voice_agent_examples: str = field(
        default_factory=lambda: os.environ.get(
            "VOICE_AGENT_EXAMPLES", str(Path.home() / "code" / "voice-agent-examples")
        )
    )

    def as_dict(self) -> dict[str, Any]:
        return {
            "tts": {
                "service": "cosyvoice_http",
                "url": self.cosyvoice_url,
                "speaker": self.speaker,
                "mode": self.mode,
                "language": self.language,
                "sample_rate": self.sample_rate,
            },
            "animation": {
                "service": "audio2face_3d",
                "grpc_url": self.a2f_grpc_url,
            },
            "voice_agent_examples": self.voice_agent_examples,
        }


class CosyVoiceTTSService:
    """HTTP CosyVoice TTS usable from Pipecat or the A2F orchestrated loop."""

    def __init__(self, config: Optional[CosyVoicePipecatConfig] = None) -> None:
        self.config = config or CosyVoicePipecatConfig()

    def synthesize(self, text: str, *, language: Optional[str] = None) -> bytes:
        cfg = self.config
        payload = {
            "text": text,
            "language": language or cfg.language,
            "speaker": cfg.speaker,
            "mode": cfg.mode,
            "sample_rate": cfg.sample_rate,
        }
        with httpx.Client(timeout=120.0) as client:
            r = client.post(f"{cfg.cosyvoice_url}/tts", json=payload)
            r.raise_for_status()
            return r.content

    async def synthesize_async(self, text: str, *, language: Optional[str] = None) -> bytes:
        return await asyncio.to_thread(self.synthesize, text, language=language)


def run_text_to_wav(text: str, out: Path, config: Optional[CosyVoicePipecatConfig] = None) -> Path:
    svc = CosyVoiceTTSService(config)
    out.write_bytes(svc.synthesize(text))
    return out


def handoff_to_a2f(text: str, config: Optional[CosyVoicePipecatConfig] = None) -> int:
    """Delegate to the CosyVoice → A2F orchestrated loop (same process contract)."""
    cfg = config or CosyVoicePipecatConfig()
    loop = ROOT / "scripts" / "a2f_cosyvoice_loop" / "cosyvoice_a2f_loop.py"
    venv_py = ROOT / "scripts" / "a2f_cosyvoice_loop" / ".venv" / "bin" / "python"
    py = str(venv_py) if venv_py.is_file() else sys.executable
    env = os.environ.copy()
    env["COSYVOICE_URL"] = cfg.cosyvoice_url
    env["COSYVOICE_DEFAULT_SPK"] = cfg.speaker
    env["A2F_GRPC_URL"] = cfg.a2f_grpc_url
    return subprocess.call(
        [py, str(loop), "--once", "--text", text],
        env=env,
    )


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--text", default="Hello from the Pipecat CosyVoice config.")
    p.add_argument("--out", default="/tmp/pipecat_cosyvoice.wav")
    p.add_argument("--to-a2f", action="store_true", help="Also push PCM into A2F gRPC")
    p.add_argument("--print-config", action="store_true")
    args = p.parse_args()
    cfg = CosyVoicePipecatConfig()
    if args.print_config:
        import json

        print(json.dumps(cfg.as_dict(), indent=2, ensure_ascii=False))
        return
    path = run_text_to_wav(args.text, Path(args.out), cfg)
    print(f"wrote {path} ({path.stat().st_size} bytes)")
    if args.to_a2f:
        raise SystemExit(handoff_to_a2f(args.text, cfg))


if __name__ == "__main__":
    main()
