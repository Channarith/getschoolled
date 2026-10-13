#!/usr/bin/env python3
"""Drop links, videos, audio, channel lists, news, and databases into training.

Same intake as the RAG lab Drop training tab (http://127.0.0.1:8095/).

Drag files onto this command in a terminal, or paste links:

  python3 scripts/training_drop.py ./lesson.mp4 ./notes.db https://vimeo.com/123
  python3 scripts/training_drop.py --stdin <<'EOF'
  https://www.youtube.com/@ChinesePodTV
  https://example.com/news/story
  EOF

  python3 scripts/training_drop.py --train --max-urls 2 https://www.youtube.com/watch?v=abcdefghijk

YouTube and Vimeo (a video, channel, or playlist) are queued for voice
training. Other links, notes, CSV, JSON, and SQLite rows are staged for RAG.
``--train`` ingests only what was dropped, not the full language pools.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SHARED_SRC = ROOT / "packages" / "shared" / "src"
if str(SHARED_SRC) not in sys.path:
    sys.path.insert(0, str(SHARED_SRC))

from aoep_shared.training_intake import drop_training, train_dropped  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("items", nargs="*", help="File or directory paths, and http(s) links")
    parser.add_argument("--stdin", action="store_true", help="Also read paths and links from stdin")
    parser.add_argument("--language", default="en")
    parser.add_argument("--expand-limit", type=int, default=20, help="Videos to list from a channel")
    parser.add_argument("--fetch", action="store_true", help="Read public page text for non-video links")
    parser.add_argument("--train", action="store_true", help="Ingest the dropped voice files after staging")
    parser.add_argument("--max-urls", type=int, default=None)
    parser.add_argument("--root", type=Path, default=None, help="Intake directory")
    args = parser.parse_args(argv)

    items = list(args.items)
    if args.stdin or (not items and not sys.stdin.isatty()):
        items.extend(line.strip() for line in sys.stdin if line.strip())
    if not items and not args.train:
        parser.print_help()
        return 2

    links = [item for item in items if item.startswith(("http://", "https://", "@"))]
    paths = [Path(item) for item in items if item not in links]
    report = drop_training(
        links=links,
        paths=paths,
        language=args.language,
        expand_limit=max(0, args.expand_limit),
        fetch_pages=bool(args.fetch),
        root=args.root,
    )
    print(json.dumps({key: value for key, value in report.items() if key != "accepted"}, indent=2))
    print(json.dumps(report.get("accepted") or [], indent=2, ensure_ascii=False))
    if not args.train:
        skipped = [row for row in report.get("accepted") or [] if row.get("kind") == "skipped"]
        kept = len(report.get("accepted") or []) - len(skipped)
        return 0 if kept else 1
    trained = train_dropped(language=args.language, max_urls=args.max_urls, root=args.root)
    print(json.dumps(trained, indent=2, default=str))
    return 0 if trained.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
