"""kalel_setup.sh: dry run changes nothing; --apply is refused off the kalel box; the torch index fallback works (fake uv/python)."""
from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

REPO = Path(__file__).resolve().parents[3]
SCRIPT = REPO / "scripts" / "fleet" / "kalel_setup.sh"


def run(home: Path, *args, extra_env=None, path=None):
    env = {"HOME": str(home), "PATH": path or os.environ["PATH"], "LC_ALL": "C", **(extra_env or {})}
    return subprocess.run(["bash", str(SCRIPT), *args], capture_output=True, text=True, env=env, timeout=60)


def test_syntax_and_dry_run_change_nothing(tmp_path):
    assert subprocess.run(["bash", "-n", str(SCRIPT)]).returncode == 0
    r = run(tmp_path)
    assert r.returncode == 0, r.stderr
    out = r.stdout
    assert "DRY RUN" in out and "sudo steps for you" in out and "none required" in out
    assert out.index("cu128") < out.index("cu129") < out.index("cu130")  # CUDA 12.8 first: Blackwell + CTranslate2's CUDA 12 libs
    assert "uv venv --python 3.12" in out and "bitsandbytes is NOT installed" in out
    assert list(tmp_path.rglob("*")) == [], "a dry run must not create anything"


def test_apply_is_refused_off_the_kalel_box(tmp_path):
    if os.uname().sysname == "Linux" and os.uname().machine == "x86_64" and subprocess.run(["which", "nvidia-smi"], capture_output=True).returncode == 0:
        return  # on a real NVIDIA Linux box --apply would run for real: not tested here
    r = run(tmp_path, "--apply")
    assert r.returncode == 3 and list(tmp_path.rglob("*")) == []


def _fake_bin(tmp: Path, failing_index: str):
    """A fake uv that 'installs' torch by recording the index, and a fake venv python that fails its smoke test for one index."""
    bindir = tmp / "bin"
    bindir.mkdir()
    uv = bindir / "uv"
    uv.write_text(f"""#!/usr/bin/env bash
set -e
if [ "$1" = venv ]; then v="${{@: -1}}"; mkdir -p "$v/bin" "$v/lib/python3.12/site-packages"
  printf '%s\\n' '#!/usr/bin/env bash' 'if [ "$1" = - ] || [ "$1" = -c ] ; then cat >/dev/null 2>&1 || true; fi' \\
    'li="$(cat "$(dirname "$0")/../last_index" 2>/dev/null || true)"; if [ -z "$li" ]; then echo "ModuleNotFoundError: No module named torch"; exit 1; fi' \\
    'if [ "$li" = {failing_index} ]; then echo "SMOKE FAIL: no kernels for sm_120"; exit 1; fi' \\
    'echo "SMOKE OK: kernels run on sm_120"' > "$v/bin/python"
  chmod +x "$v/bin/python"; printf '# fake activate\\n' > "$v/bin/activate"; exit 0; fi
if [ "$1" = pip ]; then for a in "$@"; do case "$a" in *whl/cu*) idx="${{a##*/}}"; v="${{PYBIN%/bin/python}}"; echo "$idx" > "$v/last_index" ;; esac; done
  echo "$@" >> "$HOME/uv-calls.log"; exit 0; fi
""")
    uv.chmod(uv.stat().st_mode | stat.S_IEXEC)
    for tool, out in (("nvidia-smi", "NVIDIA GeForce RTX 5060 Ti, 8151, 595.99"),):
        t = bindir / tool
        t.write_text(f"#!/usr/bin/env bash\necho '{out}'\n")
        t.chmod(t.stat().st_mode | stat.S_IEXEC)
    return bindir


def test_apply_falls_back_to_the_next_torch_index_when_the_kernel_test_fails(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bindir = _fake_bin(tmp_path, failing_index="cu128")
    venv = home / "venvs" / "gs-worker"
    repo = home / "getschoolled"
    (repo / ".git").mkdir(parents=True)
    (repo / "packages" / "shared" / "src").mkdir(parents=True)
    # the fake uv needs to know the venv python path to record the index
    r = run(home, "--apply", "--no-ct2", "--venv", str(venv), "--repo", str(repo),
            extra_env={"GS_ASSUME_LINUX": "1", "PYBIN": str(venv / "bin" / "python")}, path=f"{bindir}:/usr/bin:/bin")
    log = (home / "uv-calls.log").read_text()
    assert "whl/cu128" in log and "whl/cu129" in log and "whl/cu130" not in log, log  # cu128 failed, cu129 passed, stop there
    assert "keeping torch from cu129" in r.stdout, r.stdout + r.stderr
    assert "cu128 failed the kernel test" in r.stdout
    assert (venv / "gs-env.sh").is_file() and "gs-env.sh" in (venv / "bin" / "activate").read_text()
    assert "NLLB_PROFILE" in (venv / "gs-env.sh").read_text()
    assert (repo / ".venv").is_symlink()


def test_apply_stops_with_an_error_when_no_index_passes(tmp_path):
    home = tmp_path / "home"
    home.mkdir()
    bindir = _fake_bin(tmp_path, failing_index="cu128")
    venv = home / "venvs" / "gs-worker"
    repo = home / "getschoolled"
    (repo / ".git").mkdir(parents=True)
    r = run(home, "--apply", "--no-ct2", "--venv", str(venv), "--repo", str(repo),
            extra_env={"GS_ASSUME_LINUX": "1", "PYBIN": str(venv / "bin" / "python"), "GS_TORCH_INDEXES": "cu128"},
            path=f"{bindir}:/usr/bin:/bin")
    assert r.returncode == 4 and "no torch build passed the sm_120 kernel test" in r.stderr
