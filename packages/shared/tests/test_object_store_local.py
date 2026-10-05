"""Local filesystem object store (offline dev)."""

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.providers.object_store import LocalObjectStore


def test_local_object_store_writes_files(tmp_path, monkeypatch):
    monkeypatch.setenv("OBJECT_STORE_LOCAL_DIR", str(tmp_path))
    store = LocalObjectStore(AppConfig(deploy_mode=DeployMode.LOCAL, object_store_bucket="aoep"))
    url = store.put("recordings/demo.wav", b"RIFFdemo", content_type="audio/wav")
    assert url.endswith("/aoep/recordings/demo.wav")
    assert (tmp_path / "aoep" / "recordings" / "demo.wav").read_bytes() == b"RIFFdemo"
    assert store.info().impl == "filesystem-local"
