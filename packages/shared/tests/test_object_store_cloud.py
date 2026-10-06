"""Cloud object store (Vultr S3) with a fully mocked boto3 client.

No test in this module opens a socket or uploads to a live bucket.
"""

import hashlib
from pathlib import Path

import pytest

from aoep_shared.config import AppConfig, DeployMode
from aoep_shared.providers import object_store
from aoep_shared.providers.object_store import CloudObjectStore

_ENDPOINT = "https://sjc1.vultrobjects.com"
_BUCKET = "salareen-prod"
_ACCESS = "vultr-access"
_SECRET = "vultr-secret"
_IMMUTABLE = "public, max-age=31536000, immutable"


class _FakeS3:
    def __init__(self, *, error: Exception | None = None) -> None:
        self.puts: list[dict] = []
        self._error = error

    def put_object(self, **kwargs):
        if self._error is not None:
            raise self._error
        self.puts.append(kwargs)
        return {"ETag": '"mocked"'}


class _FakeBoto3:
    def __init__(self, s3: _FakeS3) -> None:
        self.s3 = s3
        self.client_calls: list[tuple[str, dict]] = []

    def client(self, service, **kwargs):
        self.client_calls.append((service, kwargs))
        return self.s3


class _FakeConfig:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs


def _config(**overrides) -> AppConfig:
    fields = {
        "deploy_mode": DeployMode.CLOUD,
        "object_store_endpoint": _ENDPOINT,
        "object_store_bucket": _BUCKET,
        "object_store_access_key": _ACCESS,
        "object_store_secret_key": _SECRET,
    }
    fields.update(overrides)
    return AppConfig(**fields)


def _install(monkeypatch, *, error: Exception | None = None):
    s3 = _FakeS3(error=error)
    boto = _FakeBoto3(s3)
    monkeypatch.setattr(object_store, "_load_boto3", lambda: (boto, _FakeConfig))
    return boto, s3


def _store(**overrides) -> CloudObjectStore:
    return CloudObjectStore(_config(**overrides))


def test_object_store_extra_pins_boto3():
    text = (Path(__file__).resolve().parents[1] / "pyproject.toml").read_text()
    assert "boto3==1.43.108" in text
    assert "object-store" in text


def test_put_uploads_content_type_and_returns_public_url(monkeypatch):
    boto, s3 = _install(monkeypatch)
    store = _store()
    url = store.put("recordings/demo.wav", b"RIFFdemo", content_type="audio/wav")
    again = store.put("recordings/demo.wav", b"RIFFdemo", content_type="audio/wav")

    assert url == again
    assert url == f"{_ENDPOINT}/{_BUCKET}/recordings/demo.wav"
    assert "?" not in url
    assert len(s3.puts) == 2
    uploaded = s3.puts[0]
    assert uploaded["Bucket"] == _BUCKET
    assert uploaded["Key"] == "recordings/demo.wav"
    assert uploaded["Body"] == b"RIFFdemo"
    assert uploaded["ContentType"] == "audio/wav"
    assert "CacheControl" not in uploaded

    service, kwargs = boto.client_calls[0]
    assert service == "s3"
    assert kwargs["endpoint_url"] == _ENDPOINT
    assert kwargs["aws_access_key_id"] == _ACCESS
    assert kwargs["aws_secret_access_key"] == _SECRET
    assert kwargs["region_name"] == "sjc1"
    assert kwargs["config"].kwargs == {
        "signature_version": "s3v4",
        "s3": {"addressing_style": "path"},
    }
    assert store.info().impl == "s3-cloud"
    assert store.info().mode == "cloud"


def test_default_content_type_and_leading_slash(monkeypatch):
    _boto, s3 = _install(monkeypatch)
    store = _store(object_store_endpoint=f"{_ENDPOINT}/")
    url = store.put("/slides/intro.bin", b"\x00\x01")
    assert url == f"{_ENDPOINT}/{_BUCKET}/slides/intro.bin"
    assert s3.puts[0]["Key"] == "slides/intro.bin"
    assert s3.puts[0]["ContentType"] == "application/octet-stream"
    assert s3.puts[0]["Body"] == b"\x00\x01"


def test_content_addressed_key_sets_immutable_cache_control(monkeypatch):
    _boto, s3 = _install(monkeypatch)
    payload = b"slide-bytes"
    digest = hashlib.sha256(payload).hexdigest()
    store = _store()
    url = store.put(f"assets/{digest}.png", payload, content_type="image/png")
    assert url == f"{_ENDPOINT}/{_BUCKET}/assets/{digest}.png"
    assert s3.puts[0]["ContentType"] == "image/png"
    assert s3.puts[0]["CacheControl"] == _IMMUTABLE
    assert s3.puts[0]["Key"] == f"assets/{digest}.png"


def test_sha256_prefix_and_uppercase_digest_are_content_addressed(monkeypatch):
    _boto, s3 = _install(monkeypatch)
    payload = b"deck"
    digest = hashlib.sha256(payload).hexdigest()
    store = _store()
    store.put(f"blobs/sha256-{digest.upper()}.bin", payload)
    store.put(f"blobs/{digest}/object", payload)
    assert s3.puts[0]["CacheControl"] == _IMMUTABLE
    assert s3.puts[1]["CacheControl"] == _IMMUTABLE


def test_unrelated_or_mismatched_hash_omits_immutable_cache(monkeypatch):
    _boto, s3 = _install(monkeypatch)
    payload = b"real-bytes"
    other = hashlib.sha256(b"other-bytes").hexdigest()
    store = _store()
    store.put("recordings/lesson.wav", payload, content_type="audio/wav")
    store.put(f"assets/{other}.bin", payload)
    assert "CacheControl" not in s3.puts[0]
    assert "CacheControl" not in s3.puts[1]


def test_non_vultr_endpoint_uses_generic_signing_region(monkeypatch):
    boto, _s3 = _install(monkeypatch)
    store = _store(object_store_endpoint="http://minio:9000")
    url = store.put("frames/1.jpg", b"jpeg", content_type="image/jpeg")
    assert url == "http://minio:9000/salareen-prod/frames/1.jpg"
    assert boto.client_calls[0][1]["region_name"] == "us-east-1"
    assert boto.client_calls[0][1]["endpoint_url"] == "http://minio:9000"


@pytest.mark.parametrize(
    "key",
    [
        "",
        "   ",
        "/",
        "..",
        "../secret",
        "a/../../b",
        "a/./b",
        "a//b",
        "a\\b",
        "a\x00b",
        " leading",
        "trailing ",
        "a" * 1025,
    ],
)
def test_invalid_keys_raise_before_any_client(monkeypatch, key):
    def _boom():
        raise AssertionError("client should not be built")

    monkeypatch.setattr(object_store, "_load_boto3", _boom)
    store = _store()
    with pytest.raises(ValueError):
        store.put(key, b"data")


def test_max_length_key_is_accepted(monkeypatch):
    _boto, s3 = _install(monkeypatch)
    key = "k" * 1024
    url = _store().put(key, b"x")
    assert url.endswith("/" + key)
    assert s3.puts[0]["Key"] == key


def test_non_bytes_payload_raises(monkeypatch):
    called = []
    monkeypatch.setattr(object_store, "_load_boto3", lambda: called.append(1))
    store = _store()
    with pytest.raises(TypeError, match="bytes"):
        store.put("recordings/a.wav", "not-bytes")  # type: ignore[arg-type]
    assert called == []


def test_missing_credentials_name_the_absent_settings(monkeypatch):
    called = []
    monkeypatch.setattr(object_store, "_load_boto3", lambda: called.append(1))
    both = _store(object_store_access_key="", object_store_secret_key="   ")
    with pytest.raises(RuntimeError, match="credentials are missing") as both_err:
        both.put("recordings/a.wav", b"x")
    assert "OBJECT_STORE_ACCESS_KEY" in str(both_err.value)
    assert "OBJECT_STORE_SECRET_KEY" in str(both_err.value)

    secret_only = _store(object_store_secret_key="")
    with pytest.raises(RuntimeError, match="OBJECT_STORE_SECRET_KEY"):
        secret_only.put("recordings/a.wav", b"x")
    assert called == []


def test_missing_endpoint_or_bucket(monkeypatch):
    called = []
    monkeypatch.setattr(object_store, "_load_boto3", lambda: called.append(1))
    store = _store(object_store_endpoint="  ", object_store_bucket="")
    with pytest.raises(RuntimeError, match="endpoint or bucket is missing") as exc:
        store.put("recordings/a.wav", b"x")
    message = str(exc.value)
    assert "OBJECT_STORE_ENDPOINT" in message
    assert "OBJECT_STORE_BUCKET" in message
    assert "credentials" not in message
    assert called == []


def test_missing_boto3_client_is_a_clear_error(monkeypatch):
    def _missing():
        raise ImportError("simulated missing boto3")

    monkeypatch.setattr(object_store, "_import_boto3", _missing)
    store = _store()
    with pytest.raises(RuntimeError, match="client is unavailable") as exc:
        store.put("recordings/a.wav", b"x")
    message = str(exc.value)
    assert "boto3 is not installed" in message
    assert "aoep-shared[object-store]" in message
    assert isinstance(exc.value.__cause__, ImportError)


def test_upload_errors_propagate_and_do_not_invent_a_url(monkeypatch):
    _install(monkeypatch, error=RuntimeError("simulated transport failure"))
    store = _store()
    with pytest.raises(RuntimeError, match="simulated transport failure"):
        store.put("recordings/a.wav", b"x")
