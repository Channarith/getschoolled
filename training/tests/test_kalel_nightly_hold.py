import os
import subprocess
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "kalel_nightly.sh"


def run(env_extra, tmp_path):
    env = {"PATH": os.environ["PATH"], "HOME": str(tmp_path), **env_extra}
    return subprocess.run(["bash", str(SCRIPT)], env=env, capture_output=True, text=True, timeout=20)


def test_hold_file_pauses_before_taking_the_gpu_lock(tmp_path):
    hold = tmp_path / ".gs-hold" / "kalel-train"
    hold.parent.mkdir()
    hold.write_text("waiting for 3B weights\n")
    r = run({}, tmp_path)
    assert r.returncode == 0
    assert "paused by hold file" in r.stderr and "waiting for 3B weights" in r.stderr
    assert not (tmp_path / ".gs-gpu.lock").exists(), "a paused loop must not take the GPU lock"


def test_custom_hold_path(tmp_path):
    hold = tmp_path / "pause-me"
    hold.write_text("x")
    r = run({"GS_KALEL_HOLD_FILE": str(hold)}, tmp_path)
    assert r.returncode == 0 and "paused by hold file" in r.stderr


def test_kalel_finetune_config_exists_and_is_small():
    import yaml

    cfg = yaml.safe_load((Path(__file__).resolve().parents[1] / "config" / "finetune.kalel.yaml").read_text())
    assert cfg["method"] == "qlora"
    assert cfg["optim"]["batch_size"] == 1
    assert cfg["optim"]["max_length"] <= 512
    assert cfg["lora"]["r"] <= 16
