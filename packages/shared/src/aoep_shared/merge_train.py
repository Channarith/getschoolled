"""Merge/deploy train: decide which open PRs may merge, resolve version collisions, map changes to deployments.

Everything here is a pure function or takes an injectable runner so it can be tested without GitHub, git
remotes or a cluster. The CLI is scripts/merge_train.py. Safety rules, in short:

* dry run by default; nothing merges or deploys without --apply
* never force-push: a stale PR is rebased onto a NEW branch and a superseding PR is opened
* only mechanical conflicts (version files, top of the changelog) are resolved; anything else -> needs-human
* protected paths need the 'human-approved' label
* a merge is verified (PR state MERGED and the merge commit is an ancestor of origin/main), never assumed
* a PAUSE file stops everything; a lock file stops two trains running at once
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Optional

# ----------------------------------------------------------------------------- policy

PROTECTED_PREFIXES = (
    "infra/",
    ".cursor/rules/",
    ".github/",
    "services/identity/",
    "services/billing/",
    "scripts/deploy",
    "scripts/train/",
    "scripts/record_deployment.sh",
    "scripts/merge_train.py",
    "packages/shared/src/aoep_shared/merge_train.py",
    "packages/shared/src/aoep_shared/harvest/sources.py",
    "training/promotion_gate.py",
    "training/promote.py",
    "apps/web/app/billing/",
    "apps/web/app/login/",
)
PROTECTED_SUBSTRINGS = ("secret", "/migrations/", "migration", "credential", ".env", "id_rsa", "LICENSE_ALLOWLIST")

# Files whose conflicts are safe to resolve by taking main's side and re-running the version bump.
MECHANICAL_VERSION_FILES = (
    "VERSION",
    "build-info.txt",
    "apps/web/app/lib/version.ts",
    "apps/mobile/src/version.ts",
    "apps/web/package.json",
    "apps/mobile/package.json",
    "apps/mobile/app.json",
    "packages/sdk/pyproject.toml",
)
CHANGELOG = "CHANGELOG.txt"

AUTOMERGE_LABEL = "automerge"
HUMAN_LABEL = "human-approved"
NEEDS_HUMAN_LABEL = "needs-human"

PAUSE_FILE = "scripts/train/PAUSE"
ALLOWLIST_FILE = "scripts/train/allowlist.txt"
COMPONENTS_FILE = "scripts/train/components.conf"


@dataclass
class Policy:
    allowlist_authors: set[str] = field(default_factory=set)
    protected_prefixes: tuple[str, ...] = PROTECTED_PREFIXES
    protected_substrings: tuple[str, ...] = PROTECTED_SUBSTRINGS
    allow_no_checks: bool = True  # the repo has no CI: pre-push hooks and local tests are the gate


def load_policy(repo_root: Path) -> Policy:
    path = repo_root / ALLOWLIST_FILE
    names: set[str] = set()
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            line = line.split("#", 1)[0].strip()
            if line:
                names.add(line)
    return Policy(allowlist_authors=names)


def protected_hits(paths: Iterable[str], policy: Policy) -> list[str]:
    hits = []
    for p in paths:
        low = p.lower()
        if any(p.startswith(prefix) for prefix in policy.protected_prefixes) or any(
            s.lower() in low for s in policy.protected_substrings
        ):
            hits.append(p)
    return hits


# ----------------------------------------------------------------------------- classification

ELIGIBLE = "eligible"
NEEDS_REBASE = "needs-rebase"
NEEDS_HUMAN = "needs-human"
WAIT = "wait"
BLOCKED = "blocked"
SKIP = "skip"


@dataclass
class Decision:
    number: int
    title: str
    status: str
    reasons: list[str] = field(default_factory=list)
    protected: list[str] = field(default_factory=list)


def _labels(pr: dict[str, Any]) -> set[str]:
    return {(l.get("name") if isinstance(l, dict) else str(l)) for l in pr.get("labels") or []}


def _check_state(pr: dict[str, Any]) -> str:
    """'pass' | 'fail' | 'pending' | 'none' from gh's statusCheckRollup."""
    rollup = pr.get("statusCheckRollup") or []
    if not rollup:
        return "none"
    bad = {"FAILURE", "ERROR", "TIMED_OUT", "CANCELLED", "ACTION_REQUIRED", "STARTUP_FAILURE"}
    pending = {"PENDING", "IN_PROGRESS", "QUEUED", "WAITING", "EXPECTED", ""}
    state = "pass"
    for c in rollup:
        verdict = (c.get("conclusion") or c.get("state") or c.get("status") or "").upper()
        if verdict in bad:
            return "fail"
        if verdict in pending:
            state = "pending"
    return state


def classify_pr(pr: dict[str, Any], policy: Policy, version_ok: Optional[bool] = None) -> Decision:
    number = int(pr["number"])
    d = Decision(number=number, title=str(pr.get("title", "")), status=ELIGIBLE)
    labels = _labels(pr)
    author = ((pr.get("author") or {}).get("login") or "").strip()
    paths = [f["path"] if isinstance(f, dict) else str(f) for f in pr.get("files") or []]

    if pr.get("isDraft"):
        d.status, d.reasons = SKIP, ["draft"]
        return d
    if NEEDS_HUMAN_LABEL in labels:
        d.status, d.reasons = NEEDS_HUMAN, ["labelled needs-human"]
        return d
    if AUTOMERGE_LABEL not in labels and author not in policy.allowlist_authors:
        d.status, d.reasons = SKIP, ["no 'automerge' label and author not on the allowlist"]
        return d

    hits = protected_hits(paths, policy)
    if hits and HUMAN_LABEL not in labels:
        d.status = NEEDS_HUMAN
        d.protected = hits
        d.reasons.append(f"touches {len(hits)} protected path(s); needs the '{HUMAN_LABEL}' label")
        return d

    checks = _check_state(pr)
    if checks == "fail":
        d.status, d.reasons = BLOCKED, ["a check is failing"]
        return d
    if checks == "pending":
        d.status, d.reasons = WAIT, ["checks still running"]
        return d
    if checks == "none" and not policy.allow_no_checks:
        d.status, d.reasons = BLOCKED, ["no checks reported"]
        return d

    mergeable = (pr.get("mergeable") or "").upper()
    state = (pr.get("mergeStateStatus") or "").upper()
    if mergeable == "CONFLICTING" or state in {"DIRTY", "BEHIND"}:
        d.status, d.reasons = NEEDS_REBASE, [f"{mergeable or state}: needs a rebase onto main"]
        return d
    if mergeable in {"", "UNKNOWN"} or state in {"UNKNOWN", ""}:
        d.status, d.reasons = WAIT, ["GitHub has not computed mergeability yet"]
        return d
    if state not in {"CLEAN", "HAS_HOOKS"}:
        d.status, d.reasons = BLOCKED, [f"merge state {state}"]
        return d

    if version_ok is False:
        d.status, d.reasons = NEEDS_REBASE, ["version bump check failed (collision or missing bump)"]
        return d
    if version_ok is None:
        d.reasons.append("version bump not yet verified locally")
    return d


# ----------------------------------------------------------------------------- fast local test selection

def select_tests(paths: Iterable[str]) -> list[str]:
    """Cheap, area-scoped checks; unknown areas get none (the pre-push hook still ran for the author)."""
    paths = list(paths)
    cmds: list[str] = []

    def touches(*prefixes: str) -> bool:
        return any(p.startswith(prefixes) for p in paths)

    if touches("apps/web/"):
        cmds += ["npm --prefix apps/web run -s test:unit", "npm --prefix apps/web exec -- tsc --noEmit -p apps/web"]
    if touches("apps/mobile/"):
        cmds += ["pnpm --dir apps/mobile exec tsc --noEmit -p tsconfig.typecheck.json"]
    if touches("subrepos/theodore_children_webcam_lab/"):
        cmds += ["python3 -m pytest subrepos/theodore_children_webcam_lab/tests -q -x"]
    if touches("subrepos/theodore_course_studio/"):
        cmds += ["python3 -m pytest subrepos/theodore_course_studio/tests -q -x"]
    if touches("packages/shared/"):
        cmds += ["python3 -m pytest packages/shared/tests -q -x"]
    if touches("training/"):
        cmds += ["python3 -m pytest training -q -x"]
    return cmds


# ----------------------------------------------------------------------------- components -> deployments

@dataclass
class Component:
    name: str
    dockerfile: str
    deployment: str
    smoke_paths: list[str]
    prefixes: list[str]


def load_components(repo_root: Path) -> list[Component]:
    out: list[Component] = []
    for line in (repo_root / COMPONENTS_FILE).read_text(encoding="utf-8").splitlines():
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        name, dockerfile, deployment, smoke, prefixes = [x.strip() for x in line.split("|")]
        out.append(Component(name, dockerfile, deployment, [s for s in smoke.split(",") if s], [p for p in prefixes.split(",") if p]))
    return out


# Safe rollout order: backends first, the web app last (it proxies to the labs).
DEPLOY_ORDER = (
    "curriculum", "speech", "perception", "memory", "orchestrator", "integrations",
    "children-lab", "course-studio", "web",
)


def components_for_paths(paths: Iterable[str], components: list[Component]) -> list[str]:
    hit: set[str] = set()
    for p in paths:
        for c in components:
            if any(p.startswith(prefix) for prefix in c.prefixes):
                hit.add(c.name)
    ordered = [n for n in DEPLOY_ORDER if n in hit]
    ordered += sorted(hit - set(DEPLOY_ORDER))
    return ordered


# ----------------------------------------------------------------------------- mechanical conflict resolution

_CONFLICT = re.compile(r"<<<<<<< [^\n]*\n(.*?)=======\n(.*?)>>>>>>> [^\n]*\n", re.S)


def resolve_conflict_text(path: str, text: str) -> Optional[str]:
    """Return resolved text for a mechanical file, or None if this file is not mechanical.

    In a rebase, HEAD (first block) is main and the second block is the PR's change. Version files take main's side
    (the bump is re-run afterwards). The changelog keeps BOTH sides' entry lines, newest version first.
    """
    if path in MECHANICAL_VERSION_FILES:
        return _CONFLICT.sub(lambda m: m.group(1), text)
    if path == CHANGELOG:
        def union(m: "re.Match[str]") -> str:
            seen: list[str] = []
            for line in (m.group(1) + m.group(2)).splitlines():
                if line.strip() and line not in seen:
                    seen.append(line)
            def key(line: str) -> tuple[int, ...]:
                v = re.search(r"\bv(\d+)\.(\d+)\.(\d+)", line)
                return tuple(int(x) for x in v.groups()) if v else (0, 0, 0)
            seen.sort(key=key, reverse=True)
            return "\n".join(seen) + "\n"
        return _CONFLICT.sub(union, text)
    return None


@dataclass
class RebaseResult:
    ok: bool
    branch: str = ""
    reason: str = ""
    resolved: list[str] = field(default_factory=list)


Runner = Callable[..., "subprocess.CompletedProcess[str]"]


def clean_git_env(extra: Optional[dict[str, str]] = None) -> dict[str, str]:
    """os.environ without GIT_* (a git hook or an outer repo exports GIT_DIR/GIT_INDEX_FILE, which would silently
    point our git calls at the wrong repository), plus any explicit extras."""
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    env.update(extra or {})
    return env


def _default_run(args: list[str], cwd: Path, check: bool = False, env: Optional[dict[str, str]] = None):
    return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, check=check, env=env or clean_git_env())


def rebase_onto_main(worktree: Path, base: str = "origin/main", run: Runner = _default_run,
                     bump: Optional[Callable[[Path], None]] = None) -> RebaseResult:
    """Rebase the checked-out branch in `worktree` onto `base`. Fails closed on any non-mechanical conflict."""
    res = RebaseResult(ok=False)
    p = run(["git", "rebase", base], cwd=worktree)
    guard = 0
    while p.returncode != 0:
        guard += 1
        if guard > 50:
            run(["git", "rebase", "--abort"], cwd=worktree)
            res.reason = "too many rebase steps"
            return res
        files = run(["git", "diff", "--name-only", "--diff-filter=U"], cwd=worktree).stdout.split()
        if not files:
            run(["git", "rebase", "--abort"], cwd=worktree)
            res.reason = "rebase failed without conflicting files: " + (p.stderr or p.stdout)[:200]
            return res
        for f in files:
            full = worktree / f
            new = resolve_conflict_text(f, full.read_text(encoding="utf-8")) if full.exists() else None
            if new is None:
                run(["git", "rebase", "--abort"], cwd=worktree)
                res.reason = f"non-mechanical conflict in {f}"
                return res
            full.write_text(new, encoding="utf-8")
            run(["git", "add", f], cwd=worktree)
            res.resolved.append(f)
        env = clean_git_env({"GIT_EDITOR": "true"})
        p = run(["git", "rebase", "--continue"], cwd=worktree, env=env)
    if res.resolved and bump is not None:
        bump(worktree)
    res.ok = True
    return res


def bump_with_repo_script(worktree: Path) -> None:
    subprocess.run(["python3", "scripts/bump_pr_version.py"], cwd=str(worktree), check=True, capture_output=True, text=True, env=clean_git_env())
    subprocess.run(["git", "add", "-A", "VERSION", "build-info.txt", "CHANGELOG.txt", "apps", "packages/sdk"], cwd=str(worktree), check=False, capture_output=True, text=True, env=clean_git_env())
    subprocess.run(["git", "commit", "-q", "-m", "Bump version after rebase (merge train)"], cwd=str(worktree), check=False, capture_output=True, text=True, env=clean_git_env())


def superseding_branch_name(head_ref: str, existing: Iterable[str]) -> str:
    """Never force-push: pick a fresh branch name train/<head>-rN."""
    base = "train/" + re.sub(r"[^A-Za-z0-9._-]+", "-", head_ref).strip("-")
    taken = set(existing)
    n = 1
    while f"{base}-r{n}" in taken:
        n += 1
    return f"{base}-r{n}"


# ----------------------------------------------------------------------------- merge with verification

class MergeVerifyError(RuntimeError):
    pass


def merge_and_verify(number: int, repo_root: Path, run: Runner = _default_run, expect_cwd_is_repo: bool = True) -> str:
    """Squash-merge PR `number` and PROVE it landed. Returns the merge commit sha."""
    top = run(["git", "rev-parse", "--show-toplevel"], cwd=repo_root).stdout.strip()
    if expect_cwd_is_repo and (not top or Path(top).resolve() != Path(repo_root).resolve()):
        raise MergeVerifyError(f"refusing to run gh from {repo_root}: not the repo top level ({top!r})")
    m = run(["gh", "pr", "merge", str(number), "--squash"], cwd=repo_root)
    view = run(["gh", "pr", "view", str(number), "--json", "state,mergeCommit"], cwd=repo_root)
    try:
        data = json.loads(view.stdout or "{}")
    except json.JSONDecodeError as exc:
        raise MergeVerifyError(f"cannot read PR #{number} state: {exc}") from exc
    if data.get("state") != "MERGED":
        raise MergeVerifyError(f"PR #{number} is {data.get('state')!r} after merge: {(m.stderr or m.stdout)[:200]}")
    oid = ((data.get("mergeCommit") or {}).get("oid") or "").strip()
    if not oid:
        raise MergeVerifyError(f"PR #{number} merged but no merge commit reported")
    run(["git", "fetch", "-q", "origin", "main"], cwd=repo_root)
    anc = run(["git", "merge-base", "--is-ancestor", oid, "origin/main"], cwd=repo_root)
    if anc.returncode != 0:
        raise MergeVerifyError(f"merge commit {oid[:8]} is not on origin/main")
    return oid


# ----------------------------------------------------------------------------- lock, pause, log

class TrainPaused(RuntimeError):
    pass


class TrainLocked(RuntimeError):
    pass


def check_pause(repo_root: Path) -> None:
    if (repo_root / PAUSE_FILE).exists():
        raise TrainPaused(f"{PAUSE_FILE} exists: the train is paused (delete it to resume)")


def _pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


class TrainLock:
    """Exclusive lock file with stale-owner detection."""

    def __init__(self, path: Path, max_age_s: int = 3 * 3600):
        self.path, self.max_age_s = path, max_age_s
        self.held = False

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        for _ in range(2):
            try:
                fd = os.open(str(self.path), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            except FileExistsError:
                try:
                    info = json.loads(self.path.read_text())
                except Exception:
                    info = {}
                pid, started = int(info.get("pid", 0) or 0), float(info.get("started", 0) or 0)
                stale = (pid and not _pid_alive(pid)) or (started and time.time() - started > self.max_age_s)
                if not stale:
                    raise TrainLocked(f"another train run holds {self.path} (pid {pid})")
                self.path.unlink(missing_ok=True)
                continue
            with os.fdopen(fd, "w") as fh:
                json.dump({"pid": os.getpid(), "started": time.time()}, fh)
            self.held = True
            return
        raise TrainLocked(f"could not take {self.path}")

    def release(self) -> None:
        if self.held:
            self.path.unlink(missing_ok=True)
            self.held = False

    def __enter__(self) -> "TrainLock":
        self.acquire()
        return self

    def __exit__(self, *exc: object) -> None:
        self.release()


def log_event(log_dir: Path, event: str, **fields: Any) -> None:
    log_dir.mkdir(parents=True, exist_ok=True)
    rec = {"t": time.strftime("%Y-%m-%dT%H:%M:%S%z"), "event": event, **fields}
    with (log_dir / f"train-{time.strftime('%Y%m%d')}.jsonl").open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(rec, ensure_ascii=False) + "\n")


def render_summary(decisions: list[Decision], merged: list[dict[str, Any]], deployed: list[dict[str, Any]],
                   mobile_line: str = "", paused: bool = False, dry_run: bool = True) -> str:
    lines = [f"Merge train summary ({'DRY RUN' if dry_run else 'APPLIED'}){' - PAUSED' if paused else ''}"]
    if merged:
        lines.append("Merged:")
        lines += [f"  #{m['number']} -> {m.get('sha', '')[:8]} {m.get('title', '')}" for m in merged]
    if deployed:
        lines.append("Deployed:")
        lines += [f"  {d['component']}: {d['result']}" for d in deployed]
    stuck = [d for d in decisions if d.status not in (ELIGIBLE, SKIP)]
    if stuck:
        lines.append("Stuck (and why):")
        for d in stuck:
            lines.append(f"  #{d.number} [{d.status}] {d.title[:60]}: {'; '.join(d.reasons)}")
            for h in d.protected[:3]:
                lines.append(f"      protected: {h}")
    skipped = [d for d in decisions if d.status == SKIP]
    if skipped:
        lines.append(f"Skipped {len(skipped)} PR(s): no 'automerge' label (or draft). Add the label to include one.")
    ready = [d for d in decisions if d.status == ELIGIBLE]
    if ready:
        lines.append("Ready to merge:")
        lines += [f"  #{d.number} {d.title[:70]}" for d in ready]
    if mobile_line:
        lines.append(mobile_line)
    if len(lines) == 1:
        lines.append("Nothing to do.")
    return "\n".join(lines)
