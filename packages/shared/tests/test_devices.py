"""CUDA policy: pick_device, the smoke check, overrides and the readiness payload (no real torch needed)."""
from __future__ import annotations

import logging

import pytest

from aoep_shared import devices
from aoep_shared.devices import DevicePolicyError, cuda_smoke, device_status, pick_device


class FakeTensor:
    def __init__(self, broken=False):
        self.broken = broken

    def __matmul__(self, other):
        if self.broken:
            raise RuntimeError("CUDA error: no kernel image is available for execution on the device")
        return self

    def sum(self):
        return self

    def item(self):
        return 1.0

    def half(self):
        return self


class FakeCuda:
    def __init__(self, available=True, broken=False):
        self.available, self.broken = available, broken

    def is_available(self):
        return self.available

    def synchronize(self):
        pass

    def get_device_name(self, i):
        return "NVIDIA GB10"

    def get_device_capability(self, i):
        return (12, 1)

    def get_arch_list(self):
        return ["sm_80", "sm_90"]

    def mem_get_info(self):
        return (50 * 1048576, 100 * 1048576)


class FakeLinear:
    def __init__(self, a, b):
        pass

    def to(self, device):
        return self

    def half(self):
        return self

    def __call__(self, x):
        return x


class FakeNN:
    Linear = FakeLinear


class FakeMps:
    def __init__(self, ok):
        self.ok = ok

    def is_available(self):
        return self.ok


class FakeBackends:
    def __init__(self, mps=False):
        self.mps = FakeMps(mps)


class FakeTorch:
    __version__ = "2.14.1+cu130"

    class version:
        cuda = "13.0"

    nn = FakeNN

    def __init__(self, available=True, broken=False, mps=False):
        self.cuda = FakeCuda(available, broken)
        self.backends = FakeBackends(mps)
        self._broken = broken

    def randn(self, *shape, device=None):
        return FakeTensor(self._broken)


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    for name in ("AOEP_HOST_ROLE", "AOEP_REQUIRE_CUDA", "AOEP_ALLOW_CPU", "CUDA_VISIBLE_DEVICES", "AOEP_SPARK_HOSTNAME_PATTERN"):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(devices, "HOST_ENV_FILE", tmp_path / "host.env")
    devices._reset_for_tests()
    yield
    devices._reset_for_tests()


def test_spark_role_requires_cuda_by_default(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    assert devices.require_cuda() is True
    monkeypatch.setenv("AOEP_REQUIRE_CUDA", "0")
    assert devices.require_cuda() is False


def test_role_from_host_env_file_and_hostname(monkeypatch, tmp_path):
    (tmp_path / "host.env").write_text("# comment\nAOEP_HOST_ROLE=spark\n", encoding="utf-8")
    assert devices.host_role() == "spark"
    (tmp_path / "host.env").unlink()
    monkeypatch.setattr(devices.socket, "gethostname", lambda: "Chans-Spark")
    assert devices.host_role() == "spark"
    monkeypatch.setattr(devices.socket, "gethostname", lambda: "Kal-el")
    assert devices.host_role() == "kalel"
    monkeypatch.setattr(devices.socket, "gethostname", lambda: "cvanthin-mlt")
    assert devices.host_role() == "other"


def pick(component, requested, torch):
    devices._reset_for_tests()  # the smoke result is cached per torch module; fakes reuse ids
    return pick_device(component, requested, torch)


def test_cuda_when_available(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    assert pick("nllb", None, FakeTorch()) == "cuda"
    assert pick("nllb", "auto", FakeTorch()) == "cuda"


def test_spark_missing_cuda_fails_fast_with_diagnostics(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    with pytest.raises(DevicePolicyError) as err:
        pick("nllb", None, FakeTorch(available=False))
    message = str(err.value)
    assert "CUDA is required" in message and "nllb" in message and "2.14.1+cu130" in message


def test_spark_broken_kernels_detected_by_smoke(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    torch = FakeTorch(broken=True)
    ok, detail = cuda_smoke(torch)
    assert not ok and "no kernel image" in detail
    with pytest.raises(DevicePolicyError):
        pick("asr", None, torch)


def test_spark_ignores_cpu_request_with_warning(monkeypatch, caplog):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    with caplog.at_level(logging.WARNING, logger="aoep.devices"):
        assert pick("nllb", "cpu", FakeTorch()) == "cuda"
    assert "ignoring the CPU request" in caplog.text


def test_spark_cuda_visible_devices_empty_is_overridden(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    monkeypatch.setenv("CUDA_VISIBLE_DEVICES", "")
    assert pick("nllb", None, FakeTorch()) == "cuda"
    import os

    assert "CUDA_VISIBLE_DEVICES" not in os.environ


def test_allow_cpu_honours_the_request_on_purpose(monkeypatch, caplog):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    monkeypatch.setenv("AOEP_ALLOW_CPU", "1")
    with caplog.at_level(logging.WARNING, logger="aoep.devices"):
        assert pick("nllb", "cpu", FakeTorch()) == "cpu"
    assert "by request" in caplog.text
    assert pick("nllb", None, FakeTorch(available=False)) == "cpu"


def test_kalel_prefers_cuda_but_allows_cpu(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "kalel")
    assert pick("nllb", None, FakeTorch()) == "cuda"
    assert pick("nllb", None, FakeTorch(available=False)) == "cpu"
    assert pick("nllb", "cpu", FakeTorch()) == "cpu"


def test_mac_uses_mps_else_cpu(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "mac")
    assert pick("x", None, FakeTorch(available=False, mps=True)) == "mps"
    assert pick("x", None, FakeTorch(available=False, mps=False)) == "cpu"


def test_device_status_reports_policy(monkeypatch):
    monkeypatch.setenv("AOEP_HOST_ROLE", "spark")
    ok = device_status("cuda", FakeTorch())
    assert ok["ok"] is True and ok["cuda_required"] is True and ok["gpu_free_mb"] == 50
    bad = device_status("cpu", FakeTorch())
    assert bad["ok"] is False and "CUDA required" in bad["reason"]
    monkeypatch.setenv("AOEP_ALLOW_CPU", "1")
    assert device_status("cpu", FakeTorch())["ok"] is True
