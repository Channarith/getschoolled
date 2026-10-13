"""Offline voice-training queue. Same runner as the RAG lab Voice training tab."""

from __future__ import annotations

from aoep_shared.cosyvoice_ingest.queue import cli_main


def main(argv: list[str] | None = None) -> int:
    return cli_main(argv)


if __name__ == "__main__":
    raise SystemExit(main())
