"""deploy_service.sh against a throwaway git repo with fake docker/kubectl/curl on PATH (no cluster, no registry)."""
import os
import re
import shutil
import stat
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "deploy_service.sh"
# Git hooks export GIT_DIR / GIT_INDEX_FILE and friends; a fixture repo must never inherit them.
CLEAN_ENV = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
ENV = dict(CLEAN_ENV, GIT_AUTHOR_NAME="t", GIT_AUTHOR_EMAIL="t@t", GIT_COMMITTER_NAME="t", GIT_COMMITTER_EMAIL="t@t")
BEFORE = "sha256:" + "b" * 64
AFTER = "sha256:" + "a" * 64

FAKE_DOCKER = r"""#!/usr/bin/env bash
echo "docker $*" >> "${FAKE_LOG}"
state="${FAKE_DIR}/built"
if [ "$1" = "buildx" ] && [ "$2" = "build" ]; then touch "${state}"; exit 0; fi
if [ "$1" = "buildx" ] && [ "$2" = "imagetools" ] && [ "$3" = "create" ]; then exit 0; fi
if [ "$1" = "buildx" ] && [ "$2" = "imagetools" ] && [ "$3" = "inspect" ]; then
  case "$*" in
    *"--format"*)
      if [ "${FAKE_LABEL:-ok}" = "ok" ]; then echo "{\"config\":{\"Labels\":{\"org.opencontainers.image.revision\":\"$(cat "${FAKE_DIR}/sha")\"}}}"; else echo '{"config":{"Labels":{}}}'; fi ;;
    *)
      if [ -f "${state}" ] && [ "${FAKE_SAME_DIGEST:-0}" = "0" ]; then echo "Digest:    ${FAKE_AFTER}"; else echo "Digest:    ${FAKE_BEFORE}"; fi ;;
  esac
  exit 0
fi
exit 0
"""
FAKE_KUBECTL = r"""#!/usr/bin/env bash
echo "kubectl $*" >> "${FAKE_LOG}"
case "$*" in
  *"get pods"*)
    if [ "${FAKE_PODS:-new}" = "new" ]; then echo "sjc.vultrcr.com/salareen/web@${FAKE_AFTER}"; else echo "sjc.vultrcr.com/salareen/web@${FAKE_BEFORE}"; fi ;;
  *"rollout status"*) [ "${FAKE_ROLLOUT:-ok}" = "ok" ] || exit 1 ;;
esac
exit 0
"""
FAKE_CURL = r"""#!/usr/bin/env bash
echo "curl $*" >> "${FAKE_LOG}"
printf '%s' "${FAKE_CODE:-200}"
"""
FAKE_RECORD = """#!/usr/bin/env bash
echo "record $*" >> "${FAKE_LOG}"
"""


def sh(args, cwd, **kw):
    return subprocess.run(args, cwd=cwd, env=kw.pop("env", ENV), text=True, capture_output=True, **kw)


def exe(path: Path, text: str):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


@pytest.fixture
def world(tmp_path):
    origin = tmp_path / "origin.git"
    work = tmp_path / "work"
    sh(["git", "init", "-q", "--bare", "-b", "main", str(origin)], tmp_path, check=True)
    work.mkdir()
    sh(["git", "init", "-q", "-b", "main"], work, check=True)
    sh(["git", "remote", "add", "origin", str(origin)], work, check=True)
    (work / "scripts/train").mkdir(parents=True)
    (work / "apps/web").mkdir(parents=True)
    shutil.copy(SCRIPT, work / "scripts/deploy_service.sh")
    exe(work / "scripts/record_deployment.sh", FAKE_RECORD)
    (work / "scripts/train/components.conf").write_text(
        "web|apps/web/Dockerfile|web|/,/demo/arcade|apps/web/\n# comment\ncurriculum|services/curriculum/Dockerfile|curriculum|/courses|services/curriculum/\n")
    (work / "apps/web/Dockerfile").write_text("FROM scratch\n")
    (work / "VERSION").write_text("0.9.9\n")
    sh(["git", "add", "-A"], work, check=True)
    sh(["git", "commit", "-q", "-m", "init"], work, check=True)
    sh(["git", "push", "-q", "origin", "main"], work, check=True)
    sha = sh(["git", "rev-parse", "HEAD"], work, check=True).stdout.strip()

    fake = tmp_path / "bin"
    fake.mkdir()
    exe(fake / "docker", FAKE_DOCKER)
    exe(fake / "kubectl", FAKE_KUBECTL)
    exe(fake / "curl", FAKE_CURL)
    state = tmp_path / "state"
    state.mkdir()
    (state / "sha").write_text(sha)
    log = tmp_path / "log"
    log.write_text("")
    env = dict(ENV, PATH=f"{fake}{os.pathsep}{os.environ['PATH']}", FAKE_LOG=str(log), FAKE_DIR=str(state),
               FAKE_BEFORE=BEFORE, FAKE_AFTER=AFTER, TRAIN_DIR=str(tmp_path / "train"))

    class W:
        pass

    w = W()
    w.work, w.sha, w.log, w.env, w.state = work, sha, log, env, state

    def run(*args, **extra):
        e = dict(env, **{k: str(v) for k, v in extra.items()})
        return subprocess.run(["bash", "scripts/deploy_service.sh", *args], cwd=work, env=e, text=True, capture_output=True)

    w.run = run
    w.calls = lambda: log.read_text().splitlines()
    return w


def test_no_unbraced_var_colon_tag_anywhere_in_the_script():
    text = SCRIPT.read_text()
    # the zsh trap: $var:word is a modifier in zsh. Every variable followed by ':' must be braced.
    bad = [ln for ln in text.splitlines() if re.search(r"\$[A-Za-z_][A-Za-z0-9_]*:[A-Za-z]", ln) and not ln.lstrip().startswith("#")]
    assert bad == []
    assert text.startswith("#!/usr/bin/env bash") and "set -euo pipefail" in text


def test_dry_run_prints_the_plan_and_runs_nothing(world):
    r = world.run("web", "--dry-run", "--skip-capacity")
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "sjc.vultrcr.com/salareen/web:latest" in out
    assert f"sjc.vultrcr.com/salareen/web:{world.sha[:12]}" in out
    assert "org.opencontainers.image.revision=" + world.sha in out
    assert "+ docker buildx build" in out and "+ kubectl -n aoep rollout restart deploy/web" in out
    assert "assert registry digest" in out and "curl https://www.salareen.com/demo/arcade" in out
    assert "latestatest" not in out and "webatest" not in out
    assert world.calls() == [], "a dry run must not execute docker, kubectl, curl or record anything"


def test_success_path_builds_verifies_and_records(world):
    r = world.run("web", "--skip-capacity", "--no-release")
    assert r.returncode == 0, r.stdout + r.stderr
    calls = "\n".join(world.calls())
    assert "buildx build" in calls and "-t sjc.vultrcr.com/salareen/web:latest" in calls
    assert f"-t sjc.vultrcr.com/salareen/web:{world.sha[:12]}" in calls
    assert "rollout restart deploy/web" in calls and "rollout status deploy/web" in calls
    assert f"record {world.sha} web v0.9.9 deployed, digest-verified" in calls and " success" in calls
    assert "imagetools create" not in calls, "no rollback on success"


def test_unchanged_registry_digest_fails_and_restores_the_previous_image(world):
    r = world.run("web", "--skip-capacity", "--no-release", FAKE_SAME_DIGEST=1)
    assert r.returncode != 0
    assert "registry digest unchanged" in r.stderr + r.stdout
    calls = "\n".join(world.calls())
    assert f"imagetools create --tag sjc.vultrcr.com/salareen/web:latest sjc.vultrcr.com/salareen/web@{BEFORE}" in calls
    assert "rollout restart deploy/web" in calls
    assert " failure" in calls and "FAILED web" in calls
    assert "digest-verified" not in calls


def test_image_without_the_expected_commit_is_rejected(world):
    r = world.run("web", "--skip-capacity", "--no-release", FAKE_LABEL="bad")
    assert r.returncode != 0
    assert "does not carry commit" in r.stdout + r.stderr
    assert "imagetools create" in "\n".join(world.calls())


def test_pods_running_the_old_digest_trigger_rollback(world):
    r = world.run("web", "--skip-capacity", "--no-release", FAKE_PODS="old")
    assert r.returncode != 0
    assert "not the pushed digest" in r.stdout + r.stderr
    assert "imagetools create" in "\n".join(world.calls())


def test_failed_rollout_triggers_rollback(world):
    r = world.run("web", "--skip-capacity", "--no-release", FAKE_ROLLOUT="fail")
    assert r.returncode != 0 and "rollout did not finish" in r.stdout + r.stderr
    assert "imagetools create" in "\n".join(world.calls())


def test_a_500_during_smoke_rolls_back_and_records_failure(world):
    r = world.run("web", "--skip-capacity", "--no-release", FAKE_CODE=500)
    assert r.returncode != 0
    assert "smoke / returned 500" in r.stdout + r.stderr
    calls = "\n".join(world.calls())
    assert "imagetools create" in calls and " failure" in calls
    assert " success" not in calls


def test_pause_file_blocks_everything(world):
    (world.work / "scripts/train/PAUSE").write_text("stop")
    r = world.run("web", "--skip-capacity")
    assert r.returncode != 0 and "paused" in r.stderr
    assert world.calls() == []


def test_unknown_component_and_missing_arg(world):
    assert world.run("nope", "--skip-capacity").returncode != 0
    assert world.run().returncode == 2


def test_refuses_a_commit_that_is_not_on_origin_main(world):
    (world.work / "extra.txt").write_text("x")
    sh(["git", "add", "-A"], world.work, check=True)
    sh(["git", "commit", "-q", "-m", "unpushed"], world.work, check=True)
    r = world.run("web", "--skip-capacity")
    assert r.returncode != 0 and "not on origin/main" in r.stderr
    assert world.calls() == []
    assert world.run("web", "--skip-capacity", "--dry-run", "--allow-unmerged").returncode == 0


def test_refuses_uncommitted_tracked_changes(world):
    (world.work / "VERSION").write_text("0.9.10\n")
    r = world.run("web", "--skip-capacity")
    assert r.returncode != 0 and "uncommitted" in r.stderr


def test_a_second_deploy_cannot_run_while_one_holds_the_lock(world):
    lock = Path(world.env["TRAIN_DIR"]) / "deploy.lock.d"
    lock.mkdir(parents=True)
    (lock / "pid").write_text(str(os.getppid()))  # a live process that is not us
    r = world.run("web", "--skip-capacity")
    assert r.returncode != 0 and "another deploy is running" in r.stderr
    assert world.calls() == []


def test_a_stale_lock_is_replaced(world):
    lock = Path(world.env["TRAIN_DIR"]) / "deploy.lock.d"
    lock.mkdir(parents=True)
    (lock / "pid").write_text("2000000000")
    r = world.run("web", "--skip-capacity", "--no-release")
    assert r.returncode == 0, r.stdout + r.stderr
    assert not lock.exists(), "lock released at exit"


def test_capacity_gate_refuses_a_full_cluster():
    sys_path = str(REPO / "scripts" / "train")
    import importlib.util
    spec = importlib.util.spec_from_file_location("capacity_gate", REPO / "scripts/train/capacity_gate.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    assert sys_path
    healthy = [{"state": "healthy", "mem_allocatable_mi": 3000, "mem_request_mi": 1000} for _ in range(4)]
    ok = {"nodes": healthy, "summary": {"notready": 0, "healthy_cpu_request_pct": 60}}
    assert mod.check(ok) == []
    assert any("CPU" in p for p in mod.check({"nodes": healthy, "summary": {"notready": 0, "healthy_cpu_request_pct": 95}}))
    assert any("healthy" in p for p in mod.check({"nodes": healthy[:2], "summary": {"notready": 0, "healthy_cpu_request_pct": 10}}))
    full_mem = [{"state": "healthy", "mem_allocatable_mi": 1000, "mem_request_mi": 990} for _ in range(4)]
    assert any("memory" in p for p in mod.check({"nodes": full_mem, "summary": {"notready": 0, "healthy_cpu_request_pct": 10}}))
    assert any("not ready" in p for p in mod.check({"nodes": healthy, "summary": {"notready": 1, "healthy_cpu_request_pct": 10}}))
