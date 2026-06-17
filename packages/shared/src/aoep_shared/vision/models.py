"""Resolve and (lazily) download the OpenCV face models.

We use the OpenCV Zoo models:
  - YuNet  (face detection)   ~230 KB
  - SFace  (face recognition) ~37 MB, 128-d embeddings

Weights are NEVER committed (see .gitignore: *.onnx). They are downloaded once
to a cache dir (``VISION_MODEL_DIR`` or ``~/.cache/aoep/models``) and reused. In
cloud mode the same files ship in the GPU image, so download is skipped.
"""

from __future__ import annotations

import os
import urllib.request
from typing import Tuple

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
    tmp = dest + ".part"
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, tmp)  # noqa: S310 - fixed, trusted URL
    os.replace(tmp, dest)


def ensure_models(
    model_dir: str | None = None, *, allow_download: bool = True
) -> Tuple[str, str]:
    """Return ``(detector_path, recognizer_path)``, downloading if needed.

    Raises :class:`ModelsUnavailable` if the files are missing and either
    downloading is disabled or the download fails (e.g. restricted network).
    """
    directory = model_dir or default_model_dir()
    detector = os.path.join(directory, DETECTOR_NAME)
    recognizer = os.path.join(directory, RECOGNIZER_NAME)

    for path, url, min_bytes in (
        (detector, DETECTOR_URL, _DETECTOR_MIN_BYTES),
        (recognizer, RECOGNIZER_URL, _RECOGNIZER_MIN_BYTES),
    ):
        if _valid(path, min_bytes):
            continue
        if not allow_download:
            raise ModelsUnavailable(
                f"Missing face model {os.path.basename(path)} in {directory} "
                f"and downloading is disabled."
            )
        try:
            _download(url, path)
        except Exception as exc:  # noqa: BLE001 - surface a clear, typed error
            raise ModelsUnavailable(
                f"Could not download {os.path.basename(path)} from {url}: {exc}"
            ) from exc
        if not _valid(path, min_bytes):
            raise ModelsUnavailable(
                f"Downloaded {os.path.basename(path)} is too small/corrupt."
            )

    return detector, recognizer
