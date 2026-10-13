#!/usr/bin/env python3
"""Async / multi-worker CosyVoice ingest across language pools (Spark-friendly).

Same queue as the Theodore RAG lab Voice training tab
(http://127.0.0.1:8095/ → Voice training). Progress is written to
output/cosyvoice_voice_queue_status.json so the lab can show a shell run.

Reads ``urls/cosyvoice_channels.json`` + expanded ``urls/cosyvoice_<pool>/*.txt``,
runs up to ``--workers`` channel ingests in parallel, merges each pool after
every channel finishes.

Examples:
  # expand then ingest (non-news first)
  python3 scripts/cosyvoice_expand_channels.py --workers 8
  python3 scripts/cosyvoice_batch_ingest.py --workers 3

  # one pool
  python3 scripts/cosyvoice_batch_ingest.py --pool zh,yue,en_gb --workers 2

  # status only
  python3 scripts/cosyvoice_batch_ingest.py --status

  # ask a running queue (shell or lab) to finish the current channel and stop
  python3 scripts/cosyvoice_batch_ingest.py --stop
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "packages" / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from aoep_shared.cosyvoice_ingest.queue import cli_main  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
