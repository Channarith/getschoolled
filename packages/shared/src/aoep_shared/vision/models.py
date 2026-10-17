"""Resolve and (lazily) download the OpenCV face models.

We use the OpenCV Zoo models:
  - YuNet  (face detection)   ~230 KB
  - SFace  (face recognition) ~37 MB, 128-d embeddings

Weights are NEVER committed (see .gitignore: *.onnx). They are downloaded once
to a cache dir (``VISION_MODEL_DIR`` or ``~/.cache/aoep/models``) and reused.
The perception image downloads them at build time into ``/opt/aoep/vision-models``
so a cloud pod does not need GitHub when a browser asks for one file.
"""

from __future__ import annotations

import logging
import os
import tempfile
import urllib.request
from typing import Dict, Optional, Tuple

logger = logging.getLogger(__name__)

_ZOO = "https://github.com/opencv/opencv_zoo/raw/main/models"

DETECTOR_NAME = "face_detection_yunet_2023mar.onnx"
RECOGNIZER_NAME = "face_recognition_sface_2021dec.onnx"

DETECTOR_URL = f"{_ZOO}/face_detection_yunet/{DETECTOR_NAME}"
RECOGNIZER_URL = f"{_ZOO}/face_recognition_sface/{RECOGNIZER_NAME}"

# Loose lower-bound size sanity checks (bytes) to detect truncated downloads.
_DETECTOR_MIN_BYTES = 150_000
_RECOGNIZER_MIN_BYTES = 30_000_000


class ModelsUnavailable(RuntimeError):
    """Raised when the face models are missing and cannot be downloaded."""


def default_model_dir() -> str:
    env = os.environ.get("VISION_MODEL_DIR")
    if env:
        return env
    return os.path.join(os.path.expanduser("~"), ".cache", "aoep", "models")


def _valid(path: str, min_bytes: int) -> bool:
    return os.path.isfile(path) and os.path.getsize(path) >= min_bytes


def _download(url: str, dest: str) -> None:
    # Unique temp file per call: two concurrent cold-cache downloads of the
    # same model used to share "<dest>.part" and could interleave writes into
    # a corrupt ONNX that still passed the size check. The temp file is also
    # removed when the download fails instead of being left on disk.
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    fd, tmp = tempfile.mkstemp(
        prefix=os.path.basename(dest) + ".", suffix=".part",
        dir=os.path.dirname(dest),
    )
    os.close(fd)
    try:
        urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed, trusted URL
        os.replace(tmp, dest)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


_MODEL_SPECS = {
    DETECTOR_NAME: (DETECTOR_URL, _DETECTOR_MIN_BYTES),
    RECOGNIZER_NAME: (RECOGNIZER_URL, _RECOGNIZER_MIN_BYTES),
}


def ensure_model(
    name: str, model_dir: str | None = None, *, allow_download: bool = True
) -> str:
    """Return the path for one face model, downloading only that file.

    A missing recognizer does not prevent the detector from being served,
    and the reverse. Raises :class:`ModelsUnavailable` when this file is
    missing and cannot be downloaded. The error text names the file only.
    """
    spec = _MODEL_SPECS.get(name)
    if spec is None:
        raise ModelsUnavailable(f"Unknown face model {name}.")
    url, min_bytes = spec
    directory = model_dir or default_model_dir()
    path = os.path.join(directory, name)
    if _valid(path, min_bytes):
        return path
    if not allow_download:
        raise ModelsUnavailable(
            f"Face model {name} is missing from {directory} and downloading is disabled."
        )
    try:
        _download(url, path)
    except Exception as exc:  # noqa: BLE001 - surface a clear, typed error
        raise ModelsUnavailable(f"Could not download face model {name}.") from exc
    if not _valid(path, min_bytes):
        raise ModelsUnavailable(f"Downloaded face model {name} is too small or corrupt.")
    return path


def ensure_models(
    model_dir: str | None = None, *, allow_download: bool = True
) -> Tuple[str, str]:
    """Return ``(detector_path, recognizer_path)``, downloading if needed.

    The recognition engine needs both files, so this still fails if either
    one cannot be obtained. Call :func:`ensure_model` to fetch just one.
    """
    return (
        ensure_model(DETECTOR_NAME, model_dir, allow_download=allow_download),
        ensure_model(RECOGNIZER_NAME, model_dir, allow_download=allow_download),
    )


def preload_models(model_dir: str | None = None) -> Dict[str, Optional[str]]:
    """Download each baked-or-cached model on its own.

    One failure does not cancel the other. Returns the path for each name,
    or ``None`` when that file is still missing. Logs the filename and the
    exception type only.
    """
    ready: Dict[str, Optional[str]] = {}
    for name in (DETECTOR_NAME, RECOGNIZER_NAME):
        try:
            ready[name] = ensure_model(name, model_dir)
        except ModelsUnavailable as exc:
            ready[name] = None
            logger.warning(
                "face model %s unavailable at startup (%s)",
                name,
                type(exc.__cause__ or exc).__name__,
            )
    return ready
