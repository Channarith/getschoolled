import json
import os
import subprocess
from pathlib import Path

import pytest

from aoep_shared import merge_train as mt

REPO = Path(__file__).resolve().parents[3]


def pr(number=1, **kw):
    base = {
        "number": number, "title": f"PR {number}", "author": {"login": "someone"},
        "labels": [{"name": "automerge"}], "headRefName": f"feat/x{number}", "isDraft": False,
        "mergeable": "MERGEABLE", "mergeStateStatus": "CLEAN", "files": [{"path": "apps/web/app/page.tsx"}],
        "statusCheckRollup": [],
    }
    base.update(kw)
    return base


POLICY = mt.Policy()


# ------------------------------------------------------------------ classification

def test_clean_labelled_pr_is_eligible():
    assert mt.classify_pr(pr(), POLICY).status == mt.ELIGIBLE


def test_unlabelled_pr_from_unlisted_author_is_skipped():
    d = mt.classify_pr(pr(labels=[]), POLICY)
    assert d.status == mt.SKIP


def test_allowlisted_author_needs_no_label():
    p = mt.Policy(allowlist_authors={"worker-bot"})
    assert mt.classify_pr(pr(labels=[], author={"login": "worker-bot"}), p).status == mt.ELIGIBLE


@pytest.mark.parametrize("path", [
    "infra/k8s-vke/ingress-vke.yaml", ".cursor/rules/no-eas-build-mobile.mdc", "services/identity/src/identity/main.py",
    "services/billing/src/x.py", "scripts/deploy_service.sh", "scripts/train/components.conf",
    "packages/shared/src/aoep_shared/harvest/sources.py", "training/promote.py", "training/promotion_gate.py",
    "apps/web/app/billing/page.tsx", "apps/web/.env.production", "db/migrations/0001.sql", "docs/my_secret_notes.txt",
])
def test_protected_paths_need_human_approval(path):
    d = mt.classify_pr(pr(files=[{"path": "apps/web/a.ts"}, {"path": path}]), POLICY)
    assert d.status == mt.NEEDS_HUMAN
    assert path in d.protected


def test_human_approved_label_unlocks_protected_paths():
    p = pr(files=[{"path": "infra/x.yaml"}], labels=[{"name": "automerge"}, {"name": "human-approved"}])
    assert mt.classify_pr(p, POLICY).status == mt.ELIGIBLE


def test_ordinary_paths_are_not_protected():
    assert mt.protected_hits(["apps/web/app/page.tsx", "apps/mobile/src/x.ts", "docs/a.txt", "training/evaluate.py"], POLICY) == []


def test_failing_pending_and_missing_checks():
    assert mt.classify_pr(pr(statusCheckRollup=[{"conclusion": "FAILURE"}]), POLICY).status == mt.BLOCKED
    assert mt.classify_pr(pr(statusCheckRollup=[{"status": "IN_PROGRESS"}]), POLICY).status == mt.WAIT
    assert mt.classify_pr(pr(statusCheckRollup=[{"conclusion": "SUCCESS"}]), POLICY).status == mt.ELIGIBLE
    strict = mt.Policy(allow_no_checks=False)
    assert mt.classify_pr(pr(), strict).status == mt.BLOCKED


def test_conflicts_and_behind_need_a_rebase():
    assert mt.classify_pr(pr(mergeable="CONFLICTING", mergeStateStatus="DIRTY"), POLICY).status == mt.NEEDS_REBASE
    assert mt.classify_pr(pr(mergeStateStatus="BEHIND"), POLICY).status == mt.NEEDS_REBASE
    assert mt.classify_pr(pr(mergeable="UNKNOWN", mergeStateStatus="UNKNOWN"), POLICY).status == mt.WAIT


def test_draft_and_needs_human_label():
    assert mt.classify_pr(pr(isDraft=True), POLICY).status == mt.SKIP
    assert mt.classify_pr(pr(labels=[{"name": "automerge"}, {"name": "needs-human"}]), POLICY).status == mt.NEEDS_HUMAN


def test_failed_version_check_means_rebase():
    assert mt.classify_pr(pr(), POLICY, version_ok=False).status == mt.NEEDS_REBASE
    assert mt.classify_pr(pr(), POLICY, version_ok=True).status == mt.ELIGIBLE


def test_select_tests_scopes_to_touched_areas():
    assert mt.select_tests(["docs/a.txt"]) == []
    cmds = mt.select_tests(["apps/web/app/x.ts", "packages/shared/src/a.py"])
    assert any("apps/web" in c for c in cmds) and any("packages/shared" in c for c in cmds)


# ------------------------------------------------------------------ components

def test_components_map_paths_in_a_safe_order():
    comps = mt.load_components(REPO)
    assert mt.components_for_paths(["apps/web/app/page.tsx"], comps) == ["web"]
    assert mt.components_for_paths(["subrepos/theodore_course_studio/x.py"], comps) == ["course-studio"]
    both = mt.components_for_paths(["apps/web/a.ts", "services/curriculum/src/a.py", "subrepos/theodore_children_webcam_lab/a.js"], comps)
    assert both == ["curriculum", "children-lab", "web"], "backends first, web last"
    fan = mt.components_for_paths(["packages/shared/src/aoep_shared/x.py"], comps)
    assert "web" not in fan and "children-lab" in fan and "curriculum" in fan
    assert mt.components_for_paths(["infra/k8s-vke/ingress-vke.yaml", "docs/a.txt"], comps) == []


def test_every_component_dockerfile_exists():
    for c in mt.load_components(REPO):
        assert (REPO / c.dockerfile).exists(), c.name


# ------------------------------------------------------------------ mechanical conflicts

def conflict(head, theirs):
    return f"<<<<<<< HEAD\n{head}=======\n{theirs}>>>>>>> pr\n"


def test_version_files_take_main():
    out = mt.resolve_conflict_text("VERSION", conflict("0.97.11\n", "0.97.10\n"))
    assert out == "0.97.11\n"


def test_changelog_keeps_both_sides_newest_first():
    head = "- 2026-10-24 - v0.97.11 - main change\n"
    theirs = "- 2026-10-24 - v0.97.12 - the PR change\n"
    out = mt.resolve_conflict_text("CHANGELOG.txt", "[unreleased]\n" + conflict(head, theirs))
    lines = out.splitlines()
    assert lines[0] == "[unreleased]"
    assert lines[1].startswith("- 2026-10-24 - v0.97.12") and lines[2].startswith("- 2026-10-24 - v0.97.11")


def test_other_files_are_not_mechanical():
    assert mt.resolve_conflict_text("apps/web/app/page.tsx", conflict("a\n", "b\n")) is None


def test_superseding_branch_never_reuses_a_name():
    assert mt.superseding_branch_name("feat/x", []) == "train/feat-x-r1"
    assert mt.superseding_branch_name("feat/x", ["train/feat-x-r1"]) == "train/feat-x-r2"
    assert mt.superseding_branch_name("cursor/a b", ["train/cursor-a-b-r1", "train/cursor-a-b-r2"]) == "train/cursor-a-b-r3"


# ------------------------------------------------------------------ rebase on a real fixture repo

# Git hooks export GIT_DIR / GIT_INDEX_FILE and friends; a fixture repo must never inherit them.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV = dict(CLEAN_ENV, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")


def g(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, env=ENV, text=True, capture_output=True, check=True).stdout


def commit(cwd, files: dict, msg):
    for name, text in files.items():
        p = Path(cwd) / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    g(cwd, "add", "-A")
    g(cwd, "commit", "-q", "-m", msg)


def fixture(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    g(repo, "init", "-q", "-b", "main")
    commit(repo, {"VERSION": "0.1.0\n", "CHANGELOG.txt": "[unreleased]\n- v0.1.0 - base\n", "src/a.py": "a = 1\n"}, "base")
    g(repo, "checkout", "-q", "-b", "feat")
    commit(repo, {"VERSION": "0.1.1\n", "CHANGELOG.txt": "[unreleased]\n- v0.1.1 - my change\n- v0.1.0 - base\n", "src/b.py": "b = 1\n"}, "my change")
    g(repo, "checkout", "-q", "main")
    commit(repo, {"VERSION": "0.1.2\n", "CHANGELOG.txt": "[unreleased]\n- v0.1.2 - someone else\n- v0.1.0 - base\n"}, "main moved")
    g(repo, "checkout", "-q", "feat")
    return repo


def test_version_collision_is_resolved_mechanically(tmp_path):
    repo = fixture(tmp_path)
    bumped = []

    def fake_bump(wt):
        bumped.append(wt)
        (Path(wt) / "VERSION").write_text("0.1.3\n")
        g(wt, "add", "-A")
        g(wt, "commit", "-q", "-m", "bump")

    def run(args, cwd, check=False, env=None):
        return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, env=dict(ENV, **(env or {})))

    res = mt.rebase_onto_main(repo, base="main", run=run, bump=fake_bump)
    assert res.ok, res.reason
    assert set(res.resolved) == {"VERSION", "CHANGELOG.txt"}
    assert bumped
    text = (repo / "CHANGELOG.txt").read_text()
    assert "my change" in text and "someone else" in text
    assert (repo / "VERSION").read_text().strip() == "0.1.3"
    assert (repo / "src/b.py").exists()


def test_non_mechanical_conflict_fails_closed_and_aborts(tmp_path):
    repo = fixture(tmp_path)
    # make src/a.py conflict on both sides
    g(repo, "checkout", "-q", "feat")
    commit(repo, {"src/a.py": "a = 'feature'\n"}, "feat edits a")
    g(repo, "checkout", "-q", "main")
    commit(repo, {"src/a.py": "a = 'main'\n"}, "main edits a")
    g(repo, "checkout", "-q", "feat")

    def run(args, cwd, check=False, env=None):
        return subprocess.run(args, cwd=str(cwd), text=True, capture_output=True, env=dict(ENV, **(env or {})))

    res = mt.rebase_onto_main(repo, base="main", run=run, bump=lambda wt: None)
    assert not res.ok
    assert "src/a.py" in res.reason
    assert not (repo / ".git" / "rebase-merge").exists() and not (repo / ".git" / "rebase-apply").exists(), "rebase was aborted"


# ------------------------------------------------------------------ merge verification

class FakeRun:
    def __init__(self, outputs):
        self.outputs, self.calls = outputs, []

    def __call__(self, args, cwd, check=False, env=None):
        self.calls.append(args)
        key = " ".join(args[:3])
        for prefix, (rc, out) in self.outputs.items():
            if key.startswith(prefix):
                return subprocess.CompletedProcess(args, rc, out, "")
        return subprocess.CompletedProcess(args, 0, "", "")


def test_merge_is_verified_not_assumed(tmp_path):
    top = str(tmp_path)
    ok = FakeRun({
        "git rev-parse --show-toplevel": (0, top + "\n"),
        "gh pr view": (0, json.dumps({"state": "MERGED", "mergeCommit": {"oid": "abc123def456"}})),
        "git merge-base --is-ancestor": (0, ""),
    })
    assert mt.merge_and_verify(7, tmp_path, run=ok) == "abc123def456"
    assert ["gh", "pr", "merge", "7", "--squash"] in ok.calls

    still_open = FakeRun({
        "git rev-parse --show-toplevel": (0, top + "\n"),
        "gh pr view": (0, json.dumps({"state": "OPEN", "mergeCommit": None})),
    })
    with pytest.raises(mt.MergeVerifyError):
        mt.merge_and_verify(7, tmp_path, run=still_open)

    not_on_main = FakeRun({
        "git rev-parse --show-toplevel": (0, top + "\n"),
        "gh pr view": (0, json.dumps({"state": "MERGED", "mergeCommit": {"oid": "abc"}})),
        "git merge-base --is-ancestor": (1, ""),
    })
    with pytest.raises(mt.MergeVerifyError):
        mt.merge_and_verify(7, tmp_path, run=not_on_main)


def test_merge_refuses_to_run_from_the_wrong_directory(tmp_path):
    wrong = FakeRun({"git rev-parse --show-toplevel": (128, "")})
    with pytest.raises(mt.MergeVerifyError):
        mt.merge_and_verify(7, tmp_path, run=wrong)
    assert not any(c[:3] == ["gh", "pr", "merge"] for c in wrong.calls)


# ------------------------------------------------------------------ pause + lock + summary

def test_kill_switch(tmp_path):
    (tmp_path / "scripts/train").mkdir(parents=True)
    mt.check_pause(tmp_path)
    (tmp_path / mt.PAUSE_FILE).write_text("stop")
    with pytest.raises(mt.TrainPaused):
        mt.check_pause(tmp_path)


def test_lock_is_exclusive_and_stale_locks_are_taken_over(tmp_path):
    path = tmp_path / "train.lock"
    a = mt.TrainLock(path)
    a.acquire()
    with pytest.raises(mt.TrainLocked):
        mt.TrainLock(path).acquire()
    a.release()
    path.write_text(json.dumps({"pid": 2_000_000_000, "started": 1}))  # no such process
    b = mt.TrainLock(path)
    b.acquire()
    b.release()
    assert not path.exists()


def test_summary_explains_what_is_stuck():
    ds = [
        mt.Decision(1, "ready one", mt.ELIGIBLE),
        mt.Decision(2, "protected", mt.NEEDS_HUMAN, ["touches 1 protected path(s)"], ["infra/a.yaml"]),
        mt.Decision(3, "checks", mt.WAIT, ["checks still running"]),
    ]
    text = mt.render_summary(ds, [{"number": 9, "sha": "deadbeefcafe", "title": "merged"}], [{"component": "web", "result": "ok"}],
                             "Mobile (android): build v0.97.3 is 8 version(s) behind v0.97.11")
    assert "DRY RUN" in text and "Stuck (and why)" in text and "protected: infra/a.yaml" in text
    assert "Merged:" in text and "deadbeef" in text and "web: ok" in text and "Mobile (android)" in text
    assert "PAUSED" in mt.render_summary([], [], [], paused=True)


def test_inherited_git_environment_never_reaches_git_calls(monkeypatch):
    monkeypatch.setenv("GIT_DIR", "/somewhere/else/.git")
    monkeypatch.setenv("GIT_INDEX_FILE", "/somewhere/else/index")
    monkeypatch.setenv("KEEP_ME", "1")
    env = mt.clean_git_env({"GIT_EDITOR": "true"})
    assert "GIT_DIR" not in env and "GIT_INDEX_FILE" not in env
    assert env["GIT_EDITOR"] == "true" and env["KEEP_ME"] == "1"
