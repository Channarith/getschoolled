"""Service-side mirror of the delivered translations (private object storage -> local folder).

Turned on with ``AOEP_TRANSLATIONS_BACKEND=bucket``. The service then reads ``<prefix>/_delivery.json`` from the object store
(credentials ``OBJECT_STORE_ACCESS_KEY`` / ``OBJECT_STORE_SECRET_KEY`` and ``OBJECT_STORE_ENDPOINT`` / ``OBJECT_STORE_BUCKET`` that the
cluster already has), downloads only the files that list names, checks each file's sha256 and shape, and writes them under a local
mirror folder in the normal library layout. ``course_translation_library.library_dir()`` returns that folder, so every existing reader
(audio search, class translations, the studio) works unchanged.

Fail closed and quietly:
  * bucket unreachable, manifest missing or malformed -> keep what is already mirrored (or the baked ``AOEP_COURSE_TRANSLATION_DIR`` if the
    mirror never synced); nothing new is served, nothing raises into a request;
  * a file whose size, sha256 or shape is wrong is skipped and any older mirrored copy stays;
  * names are checked (no path escapes); files that left the manifest (withdrawn) are removed from the mirror.

Reads never block on the network after the first sync: refreshes run on a background thread, at most once per TTL.
"""
from __future__ import annotations

import json
import logging
import os
import threading
import time
from pathlib import Path
from typing import Any, Callable, Dict, Optional

from . import translation_delivery as delivery

log = logging.getLogger("aoep.translation_store")

ENV_BACKEND = "AOEP_TRANSLATIONS_BACKEND"
ENV_PREFIX = "AOEP_TRANSLATIONS_PREFIX"
ENV_MIRROR = "AOEP_TRANSLATIONS_MIRROR"
ENV_TTL = "AOEP_TRANSLATIONS_TTL_S"
ENV_BOOT_WAIT = "AOEP_TRANSLATIONS_BOOT_WAIT_S"
STATE_NAME = ".delivery-state.json"
SYNCED_NAME = ".synced"

_LOCK = threading.Lock()
_SYNC_LOCK = threading.Lock()
_last_attempt = 0.0
_thread: Optional[threading.Thread] = None
_client_factory: Optional[Callable[[], Any]] = None
_status: Dict[str, Any] = {"ok": None, "error": "", "synced_at": "", "files": 0, "generated_at": ""}


def enabled() -> bool:
    return os.environ.get(ENV_BACKEND, "").strip().lower() == "bucket"


def prefix() -> str:
    return (os.environ.get(ENV_PREFIX, "").strip().strip("/") or "course-translations") + "/"


def mirror_dir() -> Path:
    raw = os.environ.get(ENV_MIRROR, "").strip()
    return Path(raw).expanduser() if raw else Path("/tmp/aoep-course-translations")


def _ttl() -> float:
    try:
        return max(5.0, float(os.environ.get(ENV_TTL, "300")))
    except ValueError:
        return 300.0


def _boot_wait() -> float:
    try:
        return max(0.0, min(15.0, float(os.environ.get(ENV_BOOT_WAIT, "3"))))
    except ValueError:
        return 3.0


def set_client_factory(factory: Optional[Callable[[], Any]]) -> None:
    """Tests inject a fake S3 client; production builds a boto3 client from the cluster's OBJECT_STORE_* variables."""
    global _client_factory
    _client_factory = factory


def reset_for_tests() -> None:
    global _last_attempt, _thread
    with _LOCK:
        _last_attempt = 0.0
        _thread = None
        _status.update({"ok": None, "error": "", "synced_at": "", "files": 0, "generated_at": ""})


def _make_client() -> Any:
    if _client_factory is not None:
        return _client_factory()
    import boto3  # in aoep-shared's dependencies; import-guarded so a missing wheel only disables the mirror
    from botocore.config import Config

    key = os.environ.get("OBJECT_STORE_ACCESS_KEY", "")
    secret = os.environ.get("OBJECT_STORE_SECRET_KEY", "")
    endpoint = os.environ.get("OBJECT_STORE_ENDPOINT", "")
    if not (key and secret and endpoint):
        raise RuntimeError("object store credentials or endpoint are not configured")
    return boto3.client(
        "s3",
        endpoint_url=endpoint,
        aws_access_key_id=key,
        aws_secret_access_key=secret,
        region_name=os.environ.get("OBJECT_STORE_REGION", "us-east-1"),
        config=Config(signature_version="s3v4", connect_timeout=3, read_timeout=10, retries={"max_attempts": 2}),
    )


def _bucket() -> str:
    return os.environ.get("OBJECT_STORE_BUCKET", "")


def _get(client: Any, key: str, limit: int) -> bytes:
    resp = client.get_object(Bucket=_bucket(), Key=key)
    declared = resp.get("ContentLength")
    if isinstance(declared, int) and declared > limit:
        raise ValueError(f"{key}: object is larger than {limit} bytes")
    body = resp["Body"].read(limit + 1)
    if len(body) > limit:
        raise ValueError(f"{key}: object is larger than {limit} bytes")
    return body


def _read_state(root: Path) -> Dict[str, str]:
    try:
        data = json.loads((root / STATE_NAME).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return {k: v for k, v in data.items() if isinstance(k, str) and isinstance(v, str)} if isinstance(data, dict) else {}


def _atomic_bytes(path: Path, data: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_bytes(data)
    tmp.replace(path)


def _remember(root: Path, data: bytes) -> None:
    """Keep the library's own index.json (class title lookups) in step with the mirrored files."""
    try:
        from .course_translation_library import _remember as remember

        remember(json.loads(data.decode("utf-8")), root)
    except Exception:  # noqa: BLE001 - the index is a convenience; the file itself is already placed and verified
        log.debug("library index not updated", exc_info=True)


def sync_once(client: Optional[Any] = None) -> bool:
    """One full pass. True when the manifest was read and applied (individual files may still have been skipped)."""
    root = mirror_dir()
    try:
        client = client or _make_client()
        raw = _get(client, prefix() + delivery.DELIVERY_NAME, delivery.MAX_MANIFEST_BYTES)
    except Exception as exc:  # noqa: BLE001 - outage, missing manifest, bad credentials: stay quiet, keep what we have
        _status.update({"ok": False, "error": type(exc).__name__})
        log.warning("translations: manifest not read (%s)", type(exc).__name__)
        return False
    manifest = delivery.parse_manifest(raw)
    if manifest is None:
        _status.update({"ok": False, "error": "bad_manifest"})
        log.warning("translations: manifest rejected")
        return False
    with _SYNC_LOCK:
        state = _read_state(root)
        files: Dict[str, Dict[str, Any]] = manifest["files"]
        skipped = 0
        for rel, meta in files.items():
            local = root / rel
            if state.get(rel) == meta["sha256"] and local.is_file():
                continue
            try:
                data = _get(client, prefix() + rel, delivery.MAX_FILE_BYTES)
                if len(data) != meta["size"] or delivery.sha256_bytes(data) != meta["sha256"]:
                    raise ValueError("size or sha256 differs from the manifest")
                ok, why = delivery.light_record_check(data, rel)
                if not ok:
                    raise ValueError(why)
                _atomic_bytes(local, data)
                _remember(root, data)
                state[rel] = meta["sha256"]
            except Exception as exc:  # noqa: BLE001 - one bad file never stops the others; an older copy stays
                skipped += 1
                log.warning("translations: skipped %s (%s)", rel, type(exc).__name__)
        # Withdrawn files leave the mirror (only files this mirror placed itself are ever deleted).
        for rel in [r for r in state if r not in files]:
            try:
                (root / rel).unlink(missing_ok=True)
                parent = (root / rel).parent
                if parent != root and not any(parent.iterdir()):
                    parent.rmdir()
            except OSError:
                pass
            state.pop(rel, None)
        _atomic_bytes(root / STATE_NAME, json.dumps(state, sort_keys=True).encode("utf-8"))
        stamp = str(manifest.get("generated_at") or "")
        _atomic_bytes(root / SYNCED_NAME, (stamp or delivery.utc_now()).encode("utf-8"))
    _status.update({"ok": True, "error": "", "synced_at": delivery.utc_now(), "files": len(files) - skipped, "generated_at": stamp, "skipped": skipped})
    try:
        from . import audio_search

        audio_search.clear_cache()
    except Exception:  # noqa: BLE001
        pass
    return True


def _run_sync() -> None:
    try:
        sync_once()
    except Exception:  # noqa: BLE001 - never let the background thread die loudly
        log.warning("translations: sync failed", exc_info=True)


def ensure_fresh() -> None:
    """Start a refresh when the TTL has passed. The very first call waits briefly so a cold start already serves the bucket's files."""
    global _last_attempt, _thread
    now = time.monotonic()
    with _LOCK:
        if _thread is not None and _thread.is_alive():
            return
        first = _last_attempt == 0.0
        if not first and now - _last_attempt < _ttl():
            return
        _last_attempt = now
        _thread = threading.Thread(target=_run_sync, name="translations-sync", daemon=True)
        thread = _thread
    thread.start()
    if first:
        thread.join(_boot_wait())


def active_root(fallback: Path) -> Path:
    """The folder readers should use: the mirror once it has synced at least once, else the configured/baked ``fallback``."""
    if not enabled():
        return fallback
    try:
        ensure_fresh()
        mirror = mirror_dir()
        return mirror if (mirror / SYNCED_NAME).is_file() else fallback
    except Exception:  # noqa: BLE001 - reading translations must never raise because the mirror had a problem
        return fallback


def status() -> Dict[str, Any]:
    out = dict(_status)
    out.update({"enabled": enabled(), "mirror": str(mirror_dir()), "prefix": prefix(), "ttl_s": _ttl()})
    return out
