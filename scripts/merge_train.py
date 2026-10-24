#!/usr/bin/env python3
"""Merge train: merge eligible PRs one at a time, deploy what changed, report what is stuck and why.

DRY RUN BY DEFAULT. Nothing merges, pushes or deploys without --apply.

  python3 scripts/merge_train.py                  # classify every open PR, print the plan and the mobile staleness
  python3 scripts/merge_train.py --apply          # do it (one merge per run unless --max-merges)
  python3 scripts/merge_train.py --apply --no-deploy
  python3 scripts/merge_train.py --pr 777         # only look at one PR
  touch scripts/train/PAUSE                       # kill switch: nothing merges or deploys until the file is deleted

Rules (see docs/release-train.txt): eligible = 'automerge' label (or allowlisted author) AND mergeable/clean AND checks
not failing AND no protected path (infra, auth, billing, deploy scripts, license allowlist, promotion gate ...) unless
labelled 'human-approved'. A stale PR is rebased onto a NEW branch (never force-pushed) and a superseding PR is opened;
only mechanical conflicts (version files, changelog) are resolved, anything else is labelled needs-human.
"""
from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "packages" / "shared" / "src"))

from aoep_shared import merge_train as mt  # noqa: E402
from aoep_shared import mobile_release as mr  # noqa: E402

PR_FIELDS = "number,title,author,labels,headRefName,isDraft,mergeable,mergeStateStatus,baseRefName,files,statusCheckRollup,url"
DEFAULT_MANIFEST_URL = "https://salareen-prod.sjc1.vultrobjects.com/releases/android/latest.json"


def sh(args: list[str], cwd: Path = ROOT, check: bool = False) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check)


def list_open_prs(only: int | None) -> list[dict]:
    p = sh(["gh", "pr", "list", "--state", "open", "--base", "main", "--limit", "100", "--json", PR_FIELDS])
    if p.returncode != 0:
        raise SystemExit(f"gh pr list failed: {p.stderr.strip()[:300]}")
    prs = json.loads(p.stdout or "[]")
    return [x for x in prs if only is None or x["number"] == only]


def published_android_version() -> str:
    url = os.environ.get("ANDROID_MANIFEST_URL", DEFAULT_MANIFEST_URL)
    try:
        with urllib.request.urlopen(url, timeout=5) as r:  # noqa: S310 (fixed https manifest URL)
            return str(json.load(r).get("version", ""))
    except Exception:
        return ""


def mobile_line() -> str:
    try:
        published = published_android_version()
        note = ""
        if not published:
            published = mr.published_version_fallback(ROOT)
            note = " (no manifest published yet; using the APK the download route serves today)"
        if not published:
            return "Mobile (android): no published manifest and no default APK found"
        return mr.staleness(ROOT, published).line() + note
    except Exception as exc:  # the summary must never fail the train
        return f"Mobile staleness unavailable: {exc}"


def add_label(number: int, label: str) -> None:
    sh(["gh", "pr", "edit", str(number), "--add-label", label])


def remote_branches() -> list[str]:
    p = sh(["git", "ls-remote", "--heads", "origin"])
    return [line.split("refs/heads/", 1)[1] for line in p.stdout.splitlines() if "refs/heads/" in line]


def verify_in_worktree(pr: dict, run_tests: bool) -> bool | None:
    """Check the PR head in a throwaway worktree: version bump check + area-scoped tests. None = not checked."""
    tmp = Path(tempfile.mkdtemp(prefix=f"train-pr{pr['number']}-"))
    try:
        if sh(["git", "fetch", "-q", "origin", f"pull/{pr['number']}/head"]).returncode != 0:
            return None
        sh(["git", "worktree", "add", "--detach", str(tmp), "FETCH_HEAD"])
        ok = sh(["bash", "scripts/check_pr_version_bump.sh"], cwd=tmp).returncode == 0
        if ok and run_tests:
            paths = [f["path"] for f in pr.get("files") or []]
            for cmd in mt.select_tests(paths):
                if sh(["bash", "-lc", cmd], cwd=tmp).returncode != 0:
                    print(f"  test failed for #{pr['number']}: {cmd}")
                    return False
        return ok
    finally:
        sh(["git", "worktree", "remove", "--force", str(tmp)])
        shutil.rmtree(tmp, ignore_errors=True)


def rebase_to_new_pr(pr: dict, apply: bool) -> str:
    """Rebase onto main in a temp worktree, push to a NEW branch (never force), open a superseding PR."""
    head = pr["headRefName"]
    new_branch = mt.superseding_branch_name(head, remote_branches())
    if not apply:
        return f"would rebase #{pr['number']} ({head}) onto main and open a superseding PR from {new_branch}"
    sh(["git", "fetch", "-q", "origin", "main", head])
    tmp = Path(tempfile.mkdtemp(prefix=f"train-rebase{pr['number']}-"))
    try:
        sh(["git", "worktree", "add", "-b", new_branch, str(tmp), f"origin/{head}"])
        result = mt.rebase_onto_main(tmp, bump=mt.bump_with_repo_script)
        if not result.ok:
            add_label(pr["number"], mt.NEEDS_HUMAN_LABEL)
            return f"#{pr['number']} needs a human: {result.reason}"
        if sh(["git", "push", "-q", "-u", "origin", new_branch], cwd=tmp).returncode != 0:  # plain push, never --force
            return f"#{pr['number']}: pushing {new_branch} failed"
        body = f"Superseding #{pr['number']}: rebased onto main by the merge train (resolved mechanically: {', '.join(result.resolved) or 'none'}). The original PR is left open and untouched."
        created = sh(["gh", "pr", "create", "--head", new_branch, "--base", "main", "--title", f"{pr['title']} (rebased, supersedes #{pr['number']})", "--body", body, "--label", mt.AUTOMERGE_LABEL], cwd=tmp)
        return f"#{pr['number']} -> {created.stdout.strip() or created.stderr.strip()[:200]}"
    finally:
        sh(["git", "worktree", "remove", "--force", str(tmp)])
        shutil.rmtree(tmp, ignore_errors=True)


def deploy(component: str, sha: str, apply: bool) -> dict:
    cmd = ["bash", "scripts/deploy_service.sh", component, "--sha", sha]
    if not apply:
        cmd.append("--dry-run")
    p = sh(cmd)
    return {"component": component, "result": "ok" if p.returncode == 0 else f"FAILED (exit {p.returncode}): {(p.stdout + p.stderr).strip()[-300:]}", "ok": p.returncode == 0}


def run(args: argparse.Namespace) -> int:
    log_dir = ROOT / "output" / "train"
    summary_path = log_dir / "latest-summary.txt"
    policy = mt.load_policy(ROOT)
    components = mt.load_components(ROOT)
    paused = False
    try:
        mt.check_pause(ROOT)
    except mt.TrainPaused as exc:
        paused = True
        print(str(exc))
    decisions: list[mt.Decision] = []
    merged: list[dict] = []
    deployed: list[dict] = []
    actions: list[str] = []
    try:
        with mt.TrainLock(log_dir / "train.lock"):
            sh(["git", "fetch", "-q", "origin", "main"])
            prs = list_open_prs(args.pr)
            by_number = {p["number"]: p for p in prs}
            for pr in prs:
                decisions.append(mt.classify_pr(pr, policy))
            if not paused:
                rebased = 0
                for d in decisions:
                    pr = by_number[d.number]
                    if d.status == mt.NEEDS_REBASE and rebased < 1:
                        actions.append(rebase_to_new_pr(pr, args.apply))
                        rebased += 1
                budget = args.max_merges
                for d in decisions:
                    if d.status != mt.ELIGIBLE or budget <= 0:
                        continue
                    mt.check_pause(ROOT)
                    pr = by_number[d.number]
                    ok = verify_in_worktree(pr, run_tests=args.apply) if args.apply else None
                    d2 = mt.classify_pr(pr, policy, version_ok=ok)
                    if d2.status != mt.ELIGIBLE or ok is False:
                        d.status, d.reasons = d2.status if d2.status != mt.ELIGIBLE else mt.BLOCKED, d2.reasons or ["local verification failed"]
                        continue
                    if not args.apply:
                        actions.append(f"would merge #{d.number} {d.title[:60]}")
                        budget -= 1
                        continue
                    before = sh(["git", "rev-parse", "origin/main"]).stdout.strip()
                    try:
                        sha = mt.merge_and_verify(d.number, ROOT)
                    except mt.MergeVerifyError as exc:
                        d.status, d.reasons = mt.BLOCKED, [str(exc)]
                        mt.log_event(log_dir, "merge_failed", pr=d.number, error=str(exc))
                        continue
                    merged.append({"number": d.number, "sha": sha, "title": d.title})
                    mt.log_event(log_dir, "merged", pr=d.number, sha=sha)
                    budget -= 1
                    changed = sh(["git", "diff", "--name-only", before, sha]).stdout.split()
                    if not args.no_deploy:
                        for comp in mt.components_for_paths(changed, components):
                            mt.check_pause(ROOT)
                            res = deploy(comp, sha, apply=True)
                            deployed.append(res)
                            mt.log_event(log_dir, "deploy", component=comp, sha=sha, result=res["result"])
                            if not res["ok"]:
                                (ROOT / mt.PAUSE_FILE).write_text(f"deploy of {comp} failed at {sha}; train paused automatically\n")
                                paused = True
                                break
    except mt.TrainLocked as exc:
        print(str(exc))
        return 4
    except mt.TrainPaused as exc:
        paused = True
        print(str(exc))
    text = mt.render_summary(decisions, merged, deployed, mobile_line(), paused=paused, dry_run=not args.apply)
    if actions:
        text += "\nActions:\n" + "\n".join("  " + a for a in actions)
    log_dir.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(text + "\n", encoding="utf-8")
    print(text)
    if args.json:
        print(json.dumps([d.__dict__ for d in decisions], indent=2))
    return 3 if paused else 0


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--apply", action="store_true", help="actually merge/push/deploy (default: dry run)")
    ap.add_argument("--max-merges", type=int, default=1)
    ap.add_argument("--no-deploy", action="store_true")
    ap.add_argument("--pr", type=int)
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()
    top = sh(["git", "rev-parse", "--show-toplevel"]).stdout.strip()
    if Path(top).resolve() != ROOT.resolve():
        raise SystemExit(f"run from the repo root ({ROOT}), not {Path.cwd()}")
    os.chdir(ROOT)
    return run(args)


if __name__ == "__main__":
    raise SystemExit(main())
