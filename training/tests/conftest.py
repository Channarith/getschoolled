"""Put the training/ dir on sys.path so ``import pipeline.*`` resolves."""

from __future__ import annotations

import os
import sys

_TRAINING_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if _TRAINING_DIR not in sys.path:
    sys.path.insert(0, _TRAINING_DIR)
