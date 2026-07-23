#!/usr/bin/env python3
"""Safe local teaching-loop example for SDK extenders.

Requires the local stack (at least orchestrator :8000 and identity :8008).
Uses AOEPClient.local() so remote URLs and privileged tokens are refused.

  python3 packages/sdk/examples/local_teaching_loop.py \\
      --email ada@example.com --password secret123
"""

from __future__ import annotations

import argparse
import sys

from aoep_sdk import AOEPClient, AOEPError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--email", default="ada@example.com")
    parser.add_argument("--password", default="secret123")
    parser.add_argument("--language", default="en")
    parser.add_argument(
        "--question",
        default="What gas do plants release during photosynthesis?",
    )
    args = parser.parse_args(argv)

    aoep = AOEPClient.local()
    try:
        aoep.authenticate(args.email, args.password)
        lessons = aoep.orchestrator.list_lessons(language=args.language)
        if not lessons:
            print("No lessons available from the local orchestrator.", file=sys.stderr)
            return 1
        lesson_id = lessons[0]["lesson_id"]
        started = aoep.orchestrator.start_session(lesson_id, class_type="solo")
        session_id = started["session"]["session_id"]
        aoep.orchestrator.advance(session_id)
        answer = aoep.orchestrator.ask(session_id, args.question, language=args.language)
    except AOEPError as exc:
        print(f"AOEP error: {exc}", file=sys.stderr)
        return 2

    print(f"lesson={lesson_id}")
    print(f"session={session_id}")
    print(f"answer={answer.get('text') or answer}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
