"""Object store provider implementations.

local  -> filesystem under OBJECT_STORE_LOCAL_DIR (offline dev) or MinIO URL.
cloud  -> Vultr Object Storage, an S3-compatible bucket, via boto3
          (optional extra ``aoep-shared[object-store]``).

The key layout and URL scheme are identical across modes so recordings,
transcripts, frames, and slide assets are addressed the same way everywhere.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from urllib.parse import urlparse

from ..config import AppConfig
from .base import ObjectStoreProvider, ProviderInfo

# One year. Content-addressed objects never change at a given key, so shared
# caches (Cloudflare in front of Vultr) may hold them indefinitely.
_IMMUTABLE_CACHE_CONTROL = "public, max-age=31536000, immutable"
_MAX_KEY_BYTES = 1024
_VULTR_HOST_SUFFIX = ".vultrobjects.com"


class _BaseObjectStore(ObjectStoreProvider):
    impl = "object-store"

    def __init__(self, config: AppConfig, *, mode: str) -> None:
        self._config = config
        self._mode = mode
        self._endpoint = config.object_store_endpoint
        self._bucket = config.object_store_bucket

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode=self._mode,
            impl=self.impl,
            endpoint=self._endpoint,
        )

    def url_for(self, key: str) -> str:
        # Deterministic, mode-agnostic addressing.
        return f"{self._endpoint.rstrip('/')}/{self._bucket}/{key.lstrip('/')}"

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        raise NotImplementedError(
            "Object store not reachable in this environment; configure MinIO "
            "(local) or an S3-compatible endpoint (cloud)."
        )


def _import_boto3():
    """Import boto3 and botocore Config. Split out so tests can simulate absence."""
    import boto3
    from botocore.config import Config

    return boto3, Config


def _load_boto3():
    """Return ``(boto3, Config)`` or raise a clear missing-client error."""
    try:
        return _import_boto3()
    except ImportError as exc:
        raise RuntimeError(
            "Vultr object store client is unavailable: boto3 is not installed. "
            "Install aoep-shared[object-store]."
        ) from exc


def _s3_region(endpoint: str) -> str:
    """SigV4 region. Vultr cluster hosts use their own region label."""
    host = (urlparse(endpoint).hostname or "").lower()
    if host.endswith(_VULTR_HOST_SUFFIX):
        region = host[: -len(_VULTR_HOST_SUFFIX)]
        if region and "." not in region:
            return region
    return "us-east-1"


def _validate_key(key: str) -> str:
    """Return a normalized relative key or raise ``ValueError``."""
    if not isinstance(key, str):
        raise ValueError("object key must be a string")
    if key == "" or key.strip() == "":
        raise ValueError("object key must be non-empty")
    if key != key.strip():
        raise ValueError("object key must not have leading or trailing whitespace")
    if any(ord(ch) < 32 or ch == "\\" for ch in key):
        raise ValueError("object key must not contain control characters or backslashes")
    normalized = key.lstrip("/")
    if not normalized:
        raise ValueError("object key must be non-empty")
    parts = normalized.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise ValueError(
            "object key must be a relative path without empty, '.' or '..' segments"
        )
    if len(normalized.encode("utf-8")) > _MAX_KEY_BYTES:
        raise ValueError(f"object key exceeds {_MAX_KEY_BYTES} bytes")
    return normalized


def _as_bytes(data: bytes) -> bytes:
    if isinstance(data, str) or not isinstance(data, (bytes, bytearray, memoryview)):
        raise TypeError("object data must be bytes")
    return bytes(data)


def _content_type(content_type: str) -> str:
    if not isinstance(content_type, str) or not content_type.strip():
        return "application/octet-stream"
    return content_type.strip()


def _is_content_addressed(key: str, payload: bytes) -> bool:
    """True when ``key`` embeds the sha256 hex digest of ``payload``."""
    digest = hashlib.sha256(payload).hexdigest()
    for segment in key.split("/"):
        lowered = segment.lower()
        if digest in lowered.split("."):
            return True
        stem = lowered.split(".", 1)[0]
        if stem in {digest, f"sha256-{digest}", f"sha256_{digest}"}:
            return True
    return False


def _local_store_root(config: AppConfig) -> Path:
    raw = (os.environ.get("OBJECT_STORE_LOCAL_DIR") or "").strip()
    base = Path(raw) if raw else Path.home() / ".cache" / "aoep" / "object-store"
    return base / config.object_store_bucket


class LocalObjectStore(_BaseObjectStore):
    impl = "filesystem-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")
        self._root = _local_store_root(config)

    def info(self) -> ProviderInfo:
        return ProviderInfo(
            capability=self.capability,
            mode="local",
            impl=self.impl,
            endpoint=f"file://{self._root}",
        )

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        dest = self._root / key.lstrip("/")
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
        return self.url_for(key)


class CloudObjectStore(_BaseObjectStore):
    """Vultr Object Storage (S3-compatible) via the pinned boto3 extra.

    ``put`` uploads with ``ContentType``. Content-addressed keys (the sha256 of
    the bytes is a path segment) also get a long-lived immutable ``CacheControl``.
    The return value is ``url_for(key)``: a deterministic public URL with no
    presigned query string.
    """

    impl = "s3-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
        self._access_key = ""
        self._secret_key = ""
        self._apply_settings()

    def _read_settings(self) -> tuple[str, str, str, str]:
        cfg = self._config
        return (
            (cfg.object_store_endpoint or "").strip(),
            (cfg.object_store_bucket or "").strip(),
            (cfg.object_store_access_key or "").strip(),
            (cfg.object_store_secret_key or "").strip(),
        )

    def _apply_settings(self) -> None:
        endpoint, bucket, access, secret = self._read_settings()
        self._endpoint = endpoint
        self._bucket = bucket
        self._access_key = access
        self._secret_key = secret

    def _require_settings(self) -> None:
        self._apply_settings()
        missing_target = []
        if not self._endpoint:
            missing_target.append("OBJECT_STORE_ENDPOINT")
        if not self._bucket:
            missing_target.append("OBJECT_STORE_BUCKET")
        if missing_target:
            raise RuntimeError(
                "Vultr object store endpoint or bucket is missing: set "
                + " and ".join(missing_target)
                + "."
            )
        missing_creds = []
        if not self._access_key:
            missing_creds.append("OBJECT_STORE_ACCESS_KEY")
        if not self._secret_key:
            missing_creds.append("OBJECT_STORE_SECRET_KEY")
        if missing_creds:
            raise RuntimeError(
                "Vultr object store credentials are missing: set "
                + " and ".join(missing_creds)
                + "."
            )

    def _s3_client(self):
        self._require_settings()
        boto3, config_cls = _load_boto3()
        return boto3.client(
            "s3",
            endpoint_url=self._endpoint,
            aws_access_key_id=self._access_key,
            aws_secret_access_key=self._secret_key,
            region_name=_s3_region(self._endpoint),
            config=config_cls(
                signature_version="s3v4",
                s3={"addressing_style": "path"},
            ),
        )

    def put(
        self,
        key: str,
        data: bytes,
        *,
        content_type: str = "application/octet-stream",
    ) -> str:
        normalized = _validate_key(key)
        payload = _as_bytes(data)
        ctype = _content_type(content_type)
        client = self._s3_client()
        params = {
            "Bucket": self._bucket,
            "Key": normalized,
            "Body": payload,
            "ContentType": ctype,
        }
        if _is_content_addressed(normalized, payload):
            params["CacheControl"] = _IMMUTABLE_CACHE_CONTROL
        client.put_object(**params)
        return self.url_for(normalized)
