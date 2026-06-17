"""Object store provider implementations.

local  -> MinIO / filesystem.
cloud  -> S3-compatible bucket.

The key layout and URL scheme are identical across modes so recordings,
transcripts, frames, and slide assets are addressed the same way everywhere.
"""

from __future__ import annotations

from ..config import AppConfig
from .base import ObjectStoreProvider, ProviderInfo


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


class LocalObjectStore(_BaseObjectStore):
    impl = "minio-local"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="local")


class CloudObjectStore(_BaseObjectStore):
    impl = "s3-cloud"

    def __init__(self, config: AppConfig) -> None:
        super().__init__(config, mode="cloud")
