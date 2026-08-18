"""env_bootstrap: load config/local.env without clearing secrets."""

from __future__ import annotations

from pathlib import Path

from aoep_shared.env_bootstrap import apply_env_map, load_repo_env


def test_apply_env_map_skips_empty_and_preserves_existing(tmp_path: Path):
    env = {"XAI_API_KEY": "real-key", "OTHER": ""}
    applied = apply_env_map(
        {"XAI_API_KEY": "", "ELEVENLABS_API_KEY": "el", "OTHER": "x"},
        environ=env,
    )
    assert env["XAI_API_KEY"] == "real-key"
    assert env["ELEVENLABS_API_KEY"] == "el"
    assert "XAI_API_KEY" not in applied
    assert "ELEVENLABS_API_KEY" in applied


def test_load_repo_env_reads_local_env_and_upgrades_retired_model(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "local.env").write_text(
        "XAI_API_KEY=from-file\nXAI_MODEL=grok-2-1212\nELEVENLABS_API_KEY=\n",
        encoding="utf-8",
    )
    (tmp_path / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    env: dict[str, str] = {}
    report = load_repo_env(root=tmp_path, environ=env)
    assert env["XAI_API_KEY"] == "from-file"
    assert env["XAI_MODEL"] == "grok-4.3"
    assert "ELEVENLABS_API_KEY" not in env  # blank skipped
    assert report["xai_configured"] is True


def test_load_repo_env_does_not_overwrite_process_secret(tmp_path: Path):
    cfg = tmp_path / "config"
    cfg.mkdir()
    (cfg / "local.env").write_text("XAI_API_KEY=from-file\n", encoding="utf-8")
    (tmp_path / "VERSION").write_text("0.0.0\n", encoding="utf-8")
    env = {"XAI_API_KEY": "from-k8s"}
    load_repo_env(root=tmp_path, environ=env)
    assert env["XAI_API_KEY"] == "from-k8s"
