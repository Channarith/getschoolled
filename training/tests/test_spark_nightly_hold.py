import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "spark_nightly.sh"


def run(env_extra, tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), **env_extra}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=20)


def test_hold_file_pauses_before_taking_the_gpu_lock(tmp_path):
    hold = tmp_path / ".gs-hold" / "stem-train"
    hold.parent.mkdir()
    hold.write_text("data not grown yet\n")
    r = run({}, tmp_path)
    assert r.returncode == 0
    assert "paused by hold file" in r.stderr and "data not grown yet" in r.stderr
    assert not (tmp_path / ".gs-gpu.lock").exists(), "a paused loop must not take the GPU lock"


def test_custom_hold_path(tmp_path):
    hold = tmp_path / "pause-me"
    hold.write_text("x")
    r = run({"GS_STEM_HOLD_FILE": str(hold)}, tmp_path)
    assert r.returncode == 0 and "paused by hold file" in r.stderr
