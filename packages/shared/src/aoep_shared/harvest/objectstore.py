"""Content-addressed object storage for harvested courses (never git).

1M decks x ~55 KB JSON is ~55 GB raw but ~4.5 GB gzipped (measured 12x), so courses are
stored as gzip JSON objects named by the sha256 of their canonical bytes:

  courses/<aa>/<sha256>.json.gz      immutable, written once, safe to re-upload
  index/<name>.jsonl.gz              catalog index parts written by the publisher

Two backends share one interface: LocalObjectStore (tests, the three machines) and
S3ObjectStore (Vultr Object Storage or any S3-compatible service; boto3 imported lazily
so nothing else needs it). OBJECT_STORE_* env names follow services/harvester/RUNBOOK.txt.
"""

from __future__ import annotations

import gzip
import hashlib
import json
import os
from pathlib import Path
from typing import Iterator, Optional, Protocol


def canonical_bytes(obj: dict) -> bytes:
    """Stable serialization so the same course always hashes the same."""
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode(
        "utf-8"
    )


def content_sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def course_key(sha: str) -> str:
    return f"courses/{sha[:2]}/{sha}.json.gz"


class ObjectStore(Protocol):
    def put(self, key: str, data: bytes) -> bool: ...
    def get(self, key: str) -> bytes: ...
    def exists(self, key: str) -> bool: ...
    def list(self, prefix: str = "") -> Iterator[str]: ...


class LocalObjectStore:
    """Directory-backed store. put() is atomic and never overwrites an existing key."""

    def __init__(self, root: str | os.PathLike) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        if key.startswith("/") or ".." in Path(key).parts:
            raise ValueError(f"unsafe object key: {key!r}")
        return self.root / key

    def put(self, key: str, data: bytes) -> bool:
        """Returns True if written, False if the key already existed (idempotent)."""
        path = self._path(key)
        if path.exists():
            return False
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + f".tmp{os.getpid()}")
        tmp.write_bytes(data)
        os.replace(tmp, path)
        return True

    def get(self, key: str) -> bytes:
        return self._path(key).read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def list(self, prefix: str = "") -> Iterator[str]:
        base = self.root
        for p in sorted(base.rglob("*")):
            if p.is_file() and ".tmp" not in p.name:
                key = p.relative_to(base).as_posix()
                if key.startswith(prefix):
                    yield key


class S3ObjectStore:
    """S3-compatible backend (Vultr Object Storage). Requires boto3 only when used."""

    def __init__(
        self,
        *,
        bucket: str,
        endpoint_url: str,
        access_key: str,
        secret_key: str,
        region: str = "us-east-1",
        prefix: str = "",
    ) -> None:
        import boto3  # lazy: not a dependency of the rest of the package

        self.bucket = bucket
        self.prefix = prefix.strip("/")
        self._s3 = boto3.client(
            "s3",
            endpoint_url=endpoint_url,
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region,
        )

    @classmethod
    def from_env(cls) -> "S3ObjectStore":
        env = os.environ
        return cls(
            bucket=env["OBJECT_STORE_BUCKET"],
            endpoint_url=env["OBJECT_STORE_ENDPOINT"],
            access_key=env["OBJECT_STORE_ACCESS_KEY"],
            secret_key=env["OBJECT_STORE_SECRET_KEY"],
            region=env.get("OBJECT_STORE_REGION", "us-east-1"),
            prefix=env.get("OBJECT_STORE_PREFIX", ""),
        )

    def _k(self, key: str) -> str:
        return f"{self.prefix}/{key}" if self.prefix else key

    def exists(self, key: str) -> bool:
        from botocore.exceptions import ClientError

        try:
            self._s3.head_object(Bucket=self.bucket, Key=self._k(key))
            return True
        except ClientError as exc:
            if exc.response.get("Error", {}).get("Code") in ("404", "NoSuchKey", "NotFound"):
                return False
            raise

    def put(self, key: str, data: bytes) -> bool:
        if self.exists(key):
            return False
        self._s3.put_object(Bucket=self.bucket, Key=self._k(key), Body=data)
        return True

    def get(self, key: str) -> bytes:
        return self._s3.get_object(Bucket=self.bucket, Key=self._k(key))["Body"].read()

    def list(self, prefix: str = "") -> Iterator[str]:
        paginator = self._s3.get_paginator("list_objects_v2")
        strip = f"{self.prefix}/" if self.prefix else ""
        for page in paginator.paginate(Bucket=self.bucket, Prefix=self._k(prefix)):
            for item in page.get("Contents", []):
                yield item["Key"][len(strip) :]


def open_store(spec: Optional[str] = None) -> ObjectStore:
    """'s3' (from OBJECT_STORE_* env) or a directory path (default OBJECT_STORE_DIR or ./output/object_store)."""
    spec = spec or os.environ.get("OBJECT_STORE_DIR") or "output/object_store"
    return S3ObjectStore.from_env() if spec == "s3" else LocalObjectStore(spec)


def pack_course(course: dict) -> tuple[str, bytes]:
    """Returns (sha256 of canonical JSON, gzip bytes). gzip mtime is fixed for reproducibility."""
    raw = canonical_bytes(course)
    return content_sha256(raw), gzip.compress(raw, compresslevel=6, mtime=0)


def unpack_course(data: bytes) -> dict:
    return json.loads(gzip.decompress(data).decode("utf-8"))
