#!/usr/bin/env python3
"""Migrate existing local bug reports to GitHub Issues.

Reads every report from the JSONL index that has no external_url (i.e. was
stored locally but never delivered to GitHub — either because the token wasn't
set at submission time, or because delivery failed transiently) and creates the
private and public GitHub issues now.

Usage:
    # Dry-run: show what would be created
    python3 scripts/migrate_bugs_to_github.py --dry-run

    # Live run against configured repos
    BUG_REPORT_GITHUB_TOKEN=ghp_xxx python3 scripts/migrate_bugs_to_github.py

    # Only process the 10 most recent undelivered reports
    python3 scripts/migrate_bugs_to_github.py --limit 10

    # Point at a non-default report directory
    python3 scripts/migrate_bugs_to_github.py --dir /data/bug-reports

Environment variables (same as the main service):
    BUG_REPORT_GITHUB_TOKEN           required
    BUG_REPORT_GITHUB_PRIVATE_REPO    e.g. Channarith/salareen-bug-reports
    BUG_REPORT_GITHUB_PUBLIC_REPO     e.g. Channarith/getschoolled
    AOEP_BUG_REPORT_DIR               override default report directory
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared.bug_reports import (  # noqa: E402
    BugReport,
    BugReportStore,
    _github_delivery,
    default_bug_report_dir,
)


def _rewrite_index(store: BugReportStore, updated: dict[str, BugReport]) -> None:
    """Rewrite the JSONL index with updated external_url / delivery_error fields."""
    index = store._index_path
    if not index.is_file():
        return
    lines = []
    for line in index.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            data = json.loads(line)
            rid = data.get("id", "")
            if rid in updated:
                data = updated[rid].model_dump()
            lines.append(json.dumps(data, separators=(",", ":")))
        except (json.JSONDecodeError, TypeError):
            lines.append(line)
    index.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true", help="Print what would happen without creating issues")
    parser.add_argument("--limit", type=int, default=0, help="Max reports to process (0 = all)")
    parser.add_argument("--dir", default="", help="Override bug report directory")
    parser.add_argument("--retry-errors", action="store_true", help="Also retry reports that previously had delivery errors")
    args = parser.parse_args(argv)

    report_dir = Path(args.dir).expanduser() if args.dir else default_bug_report_dir()
    store = BugReportStore.open(report_dir)

    all_reports = store.list_reports(limit=10_000)
    pending = [
        r for r in all_reports
        if not r.external_url and (args.retry_errors or not r.delivery_error)
    ]
    # list_reports returns newest-first; process oldest-first for chronological issues
    pending.reverse()

    if args.limit > 0:
        pending = pending[: args.limit]

    print(f"Bug report directory : {report_dir}")
    print(f"Total reports        : {len(all_reports)}")
    print(f"Already delivered    : {len(all_reports) - len(pending)}")
    print(f"To migrate           : {len(pending)}")
    if args.dry_run:
        print("(dry-run — no issues will be created)\n")

    if not pending:
        print("Nothing to migrate.")
        return 0

    import os
    private_repo = (
        os.environ.get("BUG_REPORT_GITHUB_PRIVATE_REPO", "").strip().strip("/")
        or os.environ.get("BUG_REPORT_GITHUB_REPO", "").strip().strip("/")
    )
    public_repo = os.environ.get("BUG_REPORT_GITHUB_PUBLIC_REPO", "").strip().strip("/")
    token = os.environ.get("BUG_REPORT_GITHUB_TOKEN", "").strip()

    if not args.dry_run:
        if not token:
            print("ERROR: BUG_REPORT_GITHUB_TOKEN is not set.", file=sys.stderr)
            return 1
        if not private_repo and not public_repo:
            print("ERROR: set BUG_REPORT_GITHUB_PRIVATE_REPO and/or BUG_REPORT_GITHUB_PUBLIC_REPO.", file=sys.stderr)
            return 1
        print(f"Private repo  : {private_repo or '(none)'}")
        print(f"Public repo   : {public_repo or '(none)'}")
        print()

    updated: dict[str, BugReport] = {}
    ok = 0
    failed = 0

    for i, report in enumerate(pending, 1):
        ts = time.strftime("%Y-%m-%d %H:%M", time.localtime(report.created_at))
        prefix = f"[{i}/{len(pending)}] {report.id} ({ts}) {report.platform} {report.category}"
        desc_preview = report.description[:60].replace("\n", " ")
        print(f"{prefix}: {desc_preview!r}")

        if args.dry_run:
            print(f"  → would create issue in {private_repo or public_repo}")
            continue

        try:
            private_url, public_url, error = _github_delivery(report, report_dir)
        except Exception as exc:
            error = str(exc)[:300]
            private_url = public_url = ""

        if private_url or public_url:
            report.destination = "github"
            report.private_issue_url = private_url
            report.public_issue_url = public_url
            report.external_url = private_url or public_url
            report.delivery_error = error  # may have partial errors (e.g. one screenshot failed)
            updated[report.id] = report
            print(f"  ✓ {private_url or public_url}")
            ok += 1
        else:
            report.delivery_error = error or "delivery returned no URL"
            updated[report.id] = report
            print(f"  ✗ {report.delivery_error}")
            failed += 1

        # Respect GitHub's secondary rate limit (max ~80 requests/minute for content writes)
        time.sleep(1.5)

    if not args.dry_run and updated:
        _rewrite_index(store, updated)
        print(f"\nDone. {ok} created, {failed} failed. Index updated.")
    elif args.dry_run:
        print(f"\nDry-run complete — {len(pending)} reports would be migrated.")

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
