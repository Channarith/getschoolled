#!/usr/bin/env python3
"""Launch Theodore Audio Translation Lab."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Theodore realtime audio translation lab")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8041)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    import uvicorn

    uvicorn.run(
        "theodore_audio_translation_lab.main:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        app_dir=str(ROOT / "src"),
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
