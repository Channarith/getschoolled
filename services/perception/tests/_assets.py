"""Test assets: face models + a small real multi-image-per-person dataset.

Models come from the OpenCV Zoo; the dataset is the well-known
``ageitgey/face_recognition`` knn examples (5 identities, several images each,
plus a held-out test set). Both are fetched once into a cache dir and reused.
If the network is restricted (no models/dataset), callers raise and tests skip.
"""

from __future__ import annotations

import json
import os
import ssl
import urllib.request
from typing import Dict, List, Tuple

CACHE = os.environ.get("FR_TEST_CACHE", "/tmp/aoep_fr_test")
MODELS_DIR = os.path.join(CACHE, "models")
FACES_DIR = os.path.join(CACHE, "faces")

_DATASET_API = (
    "https://api.github.com/repos/ageitgey/face_recognition/"
    "contents/examples/knn_examples"
)
_CTX = ssl.create_default_context()


def ensure_models() -> Tuple[str, str]:
    from aoep_shared.vision.models import ensure_models as _ensure

    return _ensure(MODELS_DIR)


def _listdir(url: str) -> list:
    with urllib.request.urlopen(url, context=_CTX, timeout=30) as resp:  # noqa: S310
        return json.load(resp)


def _fetch(url: str, dest: str) -> None:
    if os.path.isfile(dest) and os.path.getsize(dest) > 0:
        return
    os.makedirs(os.path.dirname(dest), exist_ok=True)
    urllib.request.urlretrieve(url, dest)  # noqa: S310


def ensure_dataset() -> Dict[str, object]:
    """Download train/test images; return paths grouped by identity.

    Returns ``{"train": {person: [paths]}, "test": [paths], "root": FACES_DIR}``.
    """
    train: Dict[str, List[str]] = {}
    marker = os.path.join(FACES_DIR, ".complete")

    if not os.path.exists(marker):
        for person in _listdir(_DATASET_API + "/train"):
            if person.get("type") != "dir":
                continue
            for f in _listdir(person["url"]):
                if f["name"].lower().endswith((".jpg", ".jpeg", ".png")):
                    _fetch(
                        f["download_url"],
                        os.path.join(FACES_DIR, "train", person["name"], f["name"]),
                    )
        for f in _listdir(_DATASET_API + "/test"):
            if f["name"].lower().endswith((".jpg", ".jpeg", ".png")):
                _fetch(f["download_url"], os.path.join(FACES_DIR, "test", f["name"]))
        os.makedirs(FACES_DIR, exist_ok=True)
        with open(marker, "w") as fh:
            fh.write("ok")

    for person in sorted(os.listdir(os.path.join(FACES_DIR, "train"))):
        pdir = os.path.join(FACES_DIR, "train", person)
        if os.path.isdir(pdir):
            train[person] = [
                os.path.join(pdir, n) for n in sorted(os.listdir(pdir))
            ]
    test_dir = os.path.join(FACES_DIR, "test")
    test = [os.path.join(test_dir, n) for n in sorted(os.listdir(test_dir))]
    return {"train": train, "test": test, "root": FACES_DIR}
