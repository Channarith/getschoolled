from agent_runtime.worker import answer, build_config, narrate


def test_build_config_defaults_local():
    cfg = build_config("room-1")
    assert cfg.room == "room-1"
    assert cfg.deploy_mode in {"local", "cloud"}
    assert cfg.livekit_url


def test_answer_uses_context():
    out = answer("what is oxygen?", context="oxygen is released by photosynthesis")
    assert "oxygen is released" in out


def test_narrate_returns_bytes():
    assert isinstance(narrate("hello class"), bytes)
