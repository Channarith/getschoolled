"""Regression tests for scripts/post_deploy_smoke.sh (digest + tag modes).

Uses a stub kubectl in a temp bin dir so we never touch a real cluster.
Covers the v0.47.2 production failure: TAG mode must not compare digest hex
as a tag when a concurrent deploy leaves digest-pinned images in the namespace.
"""

from __future__ import annotations

import os
import stat
import subprocess
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SMOKE = ROOT / "scripts" / "post_deploy_smoke.sh"


def _write_kubectl_stub(
    tmp_path: Path,
    *,
    images: dict[str, str],
    available: dict[str, tuple[int, int]] | None = None,
) -> Path:
    """Return a bin/ dir with a kubectl stub that serves canned deployment data."""
    available = available or {svc: (1, 1) for svc in images}
    images_json = " ".join(f'["{k}"]="{v}"' for k, v in images.items())
    avail_json = " ".join(f'["{k}"]="{d}:{a}"' for k, (d, a) in available.items())
    script = textwrap.dedent(
        f"""\
        #!/usr/bin/env bash
        set -euo pipefail
        declare -A IMAGES=({images_json})
        declare -A AVAIL=({avail_json})
        svc=""
        prev=""
        for arg in "$@"; do
          if [[ "$prev" == "deployment" ]]; then
            svc="$arg"
          fi
          prev="$arg"
        done
        joined="$*"
        if [[ "$joined" == *"get deployment"* && "$joined" == *"jsonpath={{.spec.template.spec.containers[0].image}}"* ]]; then
          echo "${{IMAGES[$svc]:-}}"
        elif [[ "$joined" == *"jsonpath={{.spec.replicas}}"* ]]; then
          echo "${{AVAIL[$svc]:-}}" | cut -d: -f1
        elif [[ "$joined" == *"jsonpath={{.status.availableReplicas}}"* ]]; then
          echo "${{AVAIL[$svc]:-}}" | cut -d: -f2
        else
          echo "stub kubectl: unhandled: $*" >&2
          exit 2
        fi
        """
    )
    bindir = tmp_path / "bin"
    bindir.mkdir()
    kubectl = bindir / "kubectl"
    kubectl.write_text(script)
    kubectl.chmod(kubectl.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return bindir


def _run_smoke(
    tmp_path: Path,
    *,
    images: dict[str, str],
    env: dict[str, str],
    available: dict[str, tuple[int, int]] | None = None,
) -> subprocess.CompletedProcess[str]:
    bindir = _write_kubectl_stub(tmp_path, images=images, available=available)
    run_env = os.environ.copy()
    run_env["PATH"] = f"{bindir}:{run_env.get('PATH', '')}"
    run_env.setdefault("NS", "aoep-test")
    run_env.update(env)
    return subprocess.run(
        ["bash", str(SMOKE)],
        cwd=ROOT,
        env=run_env,
        capture_output=True,
        text=True,
        check=False,
    )


def test_digest_mode_passes_when_all_services_match(tmp_path: Path) -> None:
    digest = "sha256:deadbeef"
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "identity.digest").write_text(digest + "\n")

    proc = _run_smoke(
        tmp_path,
        images={"identity": f"registry/salareen/identity@{digest}"},
        env={"DIGEST_DIR": str(digests), "SERVICES": "identity"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "[identity] OK" in proc.stdout


def test_digest_mode_fails_on_tag_pinned_image(tmp_path: Path) -> None:
    """Reproduces deploy.yml digest smoke failing when manual deploy clobbered pins."""
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "identity.digest").write_text("sha256:expected\n")

    proc = _run_smoke(
        tmp_path,
        images={"identity": "registry/salareen/identity:5863800f15a3ef8f78481e425a87f10d31f59275"},
        env={"DIGEST_DIR": str(digests), "SERVICES": "identity"},
    )
    assert proc.returncode == 1
    assert "not digest-pinned" in proc.stdout


def test_digest_mode_fails_on_digest_mismatch(tmp_path: Path) -> None:
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "web.digest").write_text("sha256:expected\n")

    proc = _run_smoke(
        tmp_path,
        images={"web": "registry/salareen/web@sha256:actual"},
        env={"DIGEST_DIR": str(digests), "SERVICES": "web"},
    )
    assert proc.returncode == 1
    assert "digest=sha256:actual != expected=sha256:expected" in proc.stdout


def test_tag_mode_passes_on_matching_git_sha_tag(tmp_path: Path) -> None:
    tag = "5863800f15a3ef8f78481e425a87f10d31f59275"
    proc = _run_smoke(
        tmp_path,
        images={"identity": f"registry/salareen/identity:{tag}"},
        env={"TAG": tag, "SERVICES": "identity"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "[identity] OK" in proc.stdout


def test_tag_mode_fails_with_actionable_hint_on_digest_pinned_image(tmp_path: Path) -> None:
    """Reproduces deploy-vke-manual TAG smoke after deploy.yml digest-pinned the svc."""
    tag = "5863800f15a3ef8f78481e425a87f10d31f59275"
    digest = "sha256:af678368e57f55a908c350219dbb672c22c7dddce765297bde153a341951ed42"
    proc = _run_smoke(
        tmp_path,
        images={"identity": f"registry/salareen/identity@{digest}"},
        env={"TAG": tag, "SERVICES": "identity"},
    )
    assert proc.returncode == 1
    assert "digest-pinned" in proc.stdout
    assert "Use DIGEST_DIR" in proc.stdout
    # Must NOT emit the misleading v0.47.2 message comparing digest hex as tag.
    assert "tag=af678368" not in proc.stdout


def test_services_env_limits_checks_to_deployed_subset(tmp_path: Path) -> None:
    """Partial deploy should not fail on services left on old pins."""
    digest = "sha256:only-identity"
    digests = tmp_path / "digests"
    digests.mkdir()
    (digests / "identity.digest").write_text(digest + "\n")

    proc = _run_smoke(
        tmp_path,
        images={
            "identity": f"registry/salareen/identity@{digest}",
            # memory still on an old tag — would fail if we checked all services
            "memory": "registry/salareen/memory:old-tag",
        },
        env={"DIGEST_DIR": str(digests), "SERVICES": "identity"},
    )
    assert proc.returncode == 0, proc.stderr + proc.stdout
    assert "[identity] OK" in proc.stdout
    assert "memory" not in proc.stdout


def test_requires_digest_dir_or_tag(tmp_path: Path) -> None:
    proc = _run_smoke(tmp_path, images={}, env={})
    assert proc.returncode == 1
    assert "DIGEST_DIR" in proc.stderr or "DIGEST_DIR" in proc.stdout
