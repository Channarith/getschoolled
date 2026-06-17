"""Pytest fixtures for the perception service.

Puts ``src`` on the path so ``import perception.*`` resolves, points the vision
provider at the test model cache, and provides session-scoped fixtures for the
face models, dataset, and a ready engine. Tests that need models/dataset skip
cleanly when the network is restricted.
"""

from __future__ import annotations

import os
import sys

import pytest

_HERE = os.path.dirname(os.path.abspath(__file__))
_SRC = os.path.abspath(os.path.join(_HERE, "..", "src"))
for _p in (_SRC, _HERE):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import _assets  # noqa: E402

# Make the perception app/provider use the test model cache before any import
# of perception.main builds its factory.
os.environ.setdefault("VISION_MODEL_DIR", _assets.MODELS_DIR)


@pytest.fixture(scope="session")
def models():
    try:
        return _assets.ensure_models()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"face models unavailable (restricted network?): {exc}")


@pytest.fixture(scope="session")
def dataset():
    try:
        return _assets.ensure_dataset()
    except Exception as exc:  # noqa: BLE001
        pytest.skip(f"face dataset unavailable (restricted network?): {exc}")


@pytest.fixture(scope="session")
def engine(models):
    from aoep_shared.vision import FaceRecognitionEngine

    detector, recognizer = models
    return FaceRecognitionEngine(detector, recognizer)
