"""Print Theodore + xAI voice session config (dry-run by default)."""

from __future__ import annotations

import argparse
import json
import os
import sys

from webcam_vision_lab.scenarios.group_class import group_theodore_instructions
from webcam_vision_lab.scenarios.self_teach import self_teach_instructions
from webcam_vision_lab.scenarios.solo_class import solo_theodore_instructions
from webcam_vision_lab.voice.xai_voice_agent import XaiVoiceAgentConfig, build_session_update


def _load_lab_env() -> None:
    env_path = os.path.join(
        os.path.dirname(__file__), "..", "..", "..", "config", "lab.env"
    )
    if os.path.isfile(env_path):
        with open(env_path, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, val = line.split("=", 1)
                os.environ.setdefault(key.strip(), val.strip())


def main() -> None:
    parser = argparse.ArgumentParser(description="xAI voice agent lab harness")
    parser.add_argument(
        "--mode",
        choices=["solo", "group", "self_teach"],
        default=os.environ.get("WEBCAM_LAB_MODE", "solo"),
    )
    parser.add_argument(
        "--connect",
        action="store_true",
        help="Open WebSocket to xAI (requires XAI_API_KEY)",
    )
    args = parser.parse_args()

    _load_lab_env()
    instructions = {
        "solo": solo_theodore_instructions,
        "group": group_theodore_instructions,
        "self_teach": self_teach_instructions,
    }[args.mode]()

    config = XaiVoiceAgentConfig.from_env()
    config.instructions = instructions

    print(f"Mode: {args.mode}")
    print(f"Realtime URL: {config.realtime_url()}")
    print(f"Voice: {config.voice}")
    print(f"Instructions: {instructions[:120]}…")
    print("\nSession update payload:")
    print(json.dumps(build_session_update(config), indent=2))

    if args.connect:
        if not config.configured():
            print("ERROR: set XAI_API_KEY in config/lab.env or environment", file=sys.stderr)
            sys.exit(1)
        import asyncio

        async def _run() -> None:
            from webcam_vision_lab.voice.xai_voice_agent import connect_voice_agent

            ws = await connect_voice_agent(config)
            print("Connected — waiting for session.created…")
            msg = await ws.recv()
            print(msg)
            await ws.close()

        asyncio.run(_run())
    else:
        print("Pass --connect to open a live WebSocket (needs XAI_API_KEY).")


if __name__ == "__main__":
    main()
